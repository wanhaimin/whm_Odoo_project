# -*- coding: utf-8 -*-

from odoo import api, fields, models
from odoo.exceptions import UserError

_BUSINESS_FIELDS = {
    "name",
    "code",
    "brand_id",
    "series_id",
    "categ_id",
    "manufacturer_id",
    "thickness",
    "thickness_std",
    "adhesive_thickness",
    "color_id",
    "adhesive_type_id",
    "base_material_id",
    "is_rohs",
    "is_reach",
    "is_halogen_free",
    "fire_rating",
    "catalog_status",
    "active",
    "product_features",
    "product_description",
    "main_applications",
    "special_applications",
    "equivalent_type",
    "spec_line_ids",
    "function_tag_ids",
    "application_tag_ids",
    "feature_tag_ids",
}

_SYNC_INTERNAL_FIELDS = {
    "dify_sync_status",
    "dify_dataset_id",
    "dify_document_id",
    "dify_last_sync_at",
    "dify_sync_error",
}

_COMPILE_INTERNAL_FIELDS = {
    "compile_status",
    "compiled_article_id",
    "last_compiled_at",
    "compile_hash",
    "compile_error",
}


class DiecutCatalogItem(models.Model):
    _inherit = "diecut.catalog.item"

    dify_sync_status = fields.Selection(
        [
            ("pending", "待同步"),
            ("synced", "已同步"),
            ("failed", "同步失败"),
            ("skipped", "已跳过"),
        ],
        string="Dify 同步状态",
        default="pending",
        index=True,
        copy=False,
    )
    dify_dataset_id = fields.Char(string="Dify 知识库ID", readonly=True, copy=False)
    dify_document_id = fields.Char(string="Dify 文档ID", readonly=True, copy=False)
    dify_last_sync_at = fields.Datetime(string="最近同步时间", readonly=True, copy=False)
    dify_sync_error = fields.Text(string="同步错误", readonly=True, copy=False)

    compile_status = fields.Selection(
        [
            ("pending", "待编译"),
            ("compiled", "已编译"),
            ("stale", "待重编译"),
            ("failed", "编译失败"),
            ("skipped", "已跳过"),
        ],
        string="知识编译状态",
        default="pending",
        index=True,
        copy=False,
    )
    compiled_article_id = fields.Many2one(
        "diecut.kb.article",
        string="编译文章",
        readonly=True,
        copy=False,
        ondelete="set null",
    )
    last_compiled_at = fields.Datetime(string="最近编译时间", readonly=True, copy=False)
    compile_hash = fields.Char(string="编译哈希", readonly=True, copy=False)
    compile_error = fields.Text(string="编译错误", readonly=True, copy=False)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            vals.setdefault("dify_sync_status", "pending")
            vals.setdefault("compile_status", "pending")
        return super().create(vals_list)

    def write(self, vals):
        touched = set(vals.keys())
        triggers_business = bool(_BUSINESS_FIELDS & touched)
        result = super().write(vals)
        if triggers_business and not (touched <= (_SYNC_INTERNAL_FIELDS | _COMPILE_INTERNAL_FIELDS)):
            pending_sync = self.env["diecut.catalog.item"]
            pending_compile_stale = self.env["diecut.catalog.item"]
            pending_compile_fresh = self.env["diecut.catalog.item"]
            for record in self:
                if record.dify_sync_status == "synced":
                    pending_sync |= record
                if record.compiled_article_id:
                    pending_compile_stale |= record
                else:
                    pending_compile_fresh |= record
            if pending_sync:
                models.Model.write(pending_sync, {"dify_sync_status": "pending", "compile_error": False})
            if pending_compile_stale:
                models.Model.write(pending_compile_stale, {"compile_status": "stale", "compile_error": False})
            if pending_compile_fresh:
                models.Model.write(pending_compile_fresh, {"compile_status": "pending", "compile_error": False})
        return result

    def action_dify_sync_now(self):
        from ..services.dify_product_sync import DifyProductSync

        sync = DifyProductSync(self.env)
        ok_count, fail_count, skip_count = 0, 0, 0
        for item in self:
            result = sync.sync_item(item)
            if result.get("action") == "skip":
                skip_count += 1
            elif result.get("ok"):
                ok_count += 1
            else:
                fail_count += 1
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": "产品 → Dify 同步",
                "message": f"成功 {ok_count} 个 / 失败 {fail_count} 个 / 跳过 {skip_count} 个",
                "type": "success" if fail_count == 0 else "warning",
                "sticky": False,
            },
        }

    def action_dify_mark_pending(self):
        self.write({"dify_sync_status": "pending"})
        return True

    def action_compile_knowledge(self):
        Job = self.env["diecut.kb.compile.job"]
        count = 0
        for item in self:
            Job.create({
                "item_id": item.id,
                "job_type": "catalog_item",
            })
            count += 1
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": "AI 知识编译",
                "message": f"已加入编译队列（{count} 个），队列处理完成后请查看相关文章。",
                "type": "success",
                "sticky": False,
            },
        }

    def action_compile_comparison(self):
        if len(self) < 2:
            raise UserError("对比分析至少需要选中 2 个产品。")
        from ..services.kb_compiler import KbCompiler

        result = KbCompiler(self.env).compile_comparison(self)
        if result.get("ok"):
            return {
                "type": "ir.actions.act_window",
                "name": "对比分析文章",
                "res_model": "diecut.kb.article",
                "view_mode": "form",
                "res_id": result["article_id"],
                "target": "current",
            }
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": "AI 对比编译",
                "message": result.get("error", "未知错误"),
                "type": "danger",
                "sticky": True,
            },
        }

    def action_open_compiled_article(self):
        self.ensure_one()
        if not self.compiled_article_id:
            raise UserError("当前产品还没有关联的编译文章。")
        return {
            "type": "ir.actions.act_window",
            "name": "编译文章",
            "res_model": "diecut.kb.article",
            "view_mode": "form",
            "res_id": self.compiled_article_id.id,
            "target": "current",
        }

    def action_open_ai_advisor(self):
        self.ensure_one()
        return {
            "type": "ir.actions.client",
            "tag": "diecut_ai_advisor",
            "params": {
                "mode": "ai",
                "model": self._name,
                "record_id": self.id,
                "record_name": f"[{self.brand_id.name or ''}] {self.code or ''} {self.name or ''}".strip(),
            },
        }

    @api.model
    def cron_dify_sync_pending_items(self):
        from ..services.dify_product_sync import DifyProductSync

        return DifyProductSync(self.env).sync_pending()

    @api.model
    def cron_compile_pending_items(self):
        from ..services.kb_compiler import KbCompiler

        limit = int(
            self.env["ir.config_parameter"].sudo().get_param(
                "diecut_knowledge.compile_batch_limit", default="5"
            )
            or 5
        )
        return KbCompiler(self.env).compile_pending(limit=limit)
