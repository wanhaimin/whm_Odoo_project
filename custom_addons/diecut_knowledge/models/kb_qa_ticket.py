# -*- coding: utf-8 -*-

from odoo import api, fields, models
from odoo.exceptions import UserError


class DiecutKbQaTicket(models.Model):
    _name = "diecut.kb.qa_ticket"
    _description = "客户问答工单"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "write_date desc, id desc"

    name = fields.Char(string="问题摘要", required=True, index=True, tracking=True)
    active = fields.Boolean(string="启用", default=True)

    state = fields.Selection(
        [
            ("draft", "草稿"),
            ("review", "评审中"),
            ("published", "已发布"),
            ("archived", "已归档"),
        ],
        string="状态",
        default="draft",
        required=True,
        index=True,
        tracking=True,
    )

    category_id = fields.Many2one(
        "diecut.kb.category",
        string="知识分类",
        required=True,
        index=True,
        tracking=True,
        ondelete="restrict",
        domain=[("code", "=", "customer_qa")],
    )

    question = fields.Text(string="客户问题", tracking=True)
    answer = fields.Text(string="答复内容", tracking=True)

    customer_name = fields.Char(string="客户名称", tracking=True)
    contact_info = fields.Char(string="联系方式", help="邮箱 / 电话 / 微信等。")
    source = fields.Selection(
        [
            ("manual", "手工录入"),
            ("import", "批量导入"),
            ("web_form", "网页表单"),
            ("email", "邮件"),
            ("chat", "在线客服"),
            ("phone", "电话"),
            ("other", "其他"),
        ],
        string="来源渠道",
        default="manual",
        tracking=True,
    )
    source_ref = fields.Char(string="原始编号", help="原工单/邮件/系统的编号，用于追溯。")

    related_brand_ids = fields.Many2many(
        "diecut.brand",
        "diecut_kb_qa_ticket_brand_rel",
        "ticket_id",
        "brand_id",
        string="关联品牌",
    )
    related_item_ids = fields.Many2many(
        "diecut.catalog.item",
        "diecut_kb_qa_ticket_item_rel",
        "ticket_id",
        "item_id",
        string="关联型号",
    )

    keywords = fields.Char(string="关键词", help="逗号分隔，用于检索过滤。")
    resolved_date = fields.Date(string="解决日期")
    resolved_by_uid = fields.Many2one("res.users", string="答复人")
    view_count = fields.Integer(string="查阅次数", default=0)

    # ---------------------------- Dify sync ----------------------------------
    sync_status = fields.Selection(
        [
            ("pending", "待同步"),
            ("synced", "已同步"),
            ("failed", "同步失败"),
            ("skipped", "已跳过"),
        ],
        string="同步状态",
        default="pending",
        index=True,
        tracking=True,
    )
    dify_dataset_id = fields.Char(string="Dify 知识库ID", readonly=True, copy=False)
    dify_document_id = fields.Char(string="Dify 文档ID", readonly=True, copy=False)
    last_sync_at = fields.Datetime(string="最近同步时间", readonly=True, copy=False)
    sync_error = fields.Text(string="同步错误", readonly=True, copy=False)

    # ---------------------------- write hook ---------------------------------

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get("category_id"):
                cat = self.env["diecut.kb.category"].search(
                    [("code", "=", "customer_qa")], limit=1
                )
                if cat:
                    vals["category_id"] = cat.id
        return super().create(vals_list)

    def write(self, vals):
        sync_triggers = {
            "name", "question", "answer", "category_id", "state",
            "keywords", "customer_name", "source", "source_ref",
            "related_brand_ids", "related_item_ids",
        }
        internal = {"sync_status", "dify_dataset_id", "dify_document_id",
                    "last_sync_at", "sync_error"}
        trigger = bool(sync_triggers & set(vals.keys())) and not (
            set(vals.keys()) <= internal
        )
        result = super().write(vals)
        if trigger:
            for record in self:
                if record.sync_status == "synced" and vals.get("state") != "archived":
                    super(DiecutKbQaTicket, record).write({"sync_status": "pending"})
        return result

    # ---------------------------- workflow -----------------------------------

    def action_submit_review(self):
        for record in self:
            if record.state != "draft":
                raise UserError("只有草稿状态可以提交评审。")
        self.write({"state": "review"})
        return True

    def action_publish(self):
        for record in self:
            if record.state not in ("draft", "review"):
                raise UserError("只有草稿或评审中的工单可以发布。")
            if not record.question or not record.answer:
                raise UserError(f"工单 [{record.name}] 问题或答复为空，无法发布。")
        self.write({
            "state": "published",
            "resolved_date": fields.Date.context_today(self),
            "sync_status": "pending",
        })
        return True

    def action_back_to_draft(self):
        self.write({"state": "draft"})
        return True

    def action_archive(self):
        self.write({"state": "archived", "active": False, "sync_status": "pending"})
        return True

    # ---------------------------- Dify sync ----------------------------------

    def action_request_sync(self):
        from ..services.qa_ticket_sync import QaTicketSync

        sync = QaTicketSync(self.env)
        ok_count, fail_count = 0, 0
        for record in self:
            result = sync.sync_ticket(record)
            if result.get("ok"):
                ok_count += 1
            else:
                fail_count += 1
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": "问答 → Dify 同步",
                "message": f"成功 {ok_count} 条 / 失败 {fail_count} 条",
                "type": "success" if fail_count == 0 else "warning",
                "sticky": False,
            },
        }

    def action_mark_pending(self):
        self.write({"sync_status": "pending"})
        return True

    def action_open_ai_advisor(self):
        self.ensure_one()
        return {
            "type": "ir.actions.client",
            "tag": "diecut_ai_advisor",
            "params": {
                "model": self._name,
                "record_id": self.id,
                "record_name": self.name or "",
            },
        }

    @api.model
    def cron_sync_pending_tickets(self):
        from ..services.qa_ticket_sync import QaTicketSync

        return QaTicketSync(self.env).sync_pending()
