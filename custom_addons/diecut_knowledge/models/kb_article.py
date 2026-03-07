# -*- coding: utf-8 -*-

import json

from odoo import api, fields, models
from odoo.exceptions import UserError


class DiecutKbArticle(models.Model):
    _name = "diecut.kb.article"
    _description = "知识库文章"
    _parent_name = "parent_id"
    _parent_store = True
    _order = "parent_path, sequence, id desc"

    name = fields.Char(string="标题", required=True, index=True)
    active = fields.Boolean(string="启用", default=True)
    sequence = fields.Integer(string="排序", default=10)
    parent_id = fields.Many2one(
        "diecut.kb.article",
        string="上级页面",
        index=True,
        ondelete="set null",
    )
    child_ids = fields.One2many("diecut.kb.article", "parent_id", string="子页面")
    parent_path = fields.Char(index=True)
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
    )

    catalog_item_id = fields.Many2one(
        "diecut.catalog.item",
        string="关联型号",
        ondelete="set null",
        index=True,
    )
    brand_id = fields.Many2one(
        "diecut.brand",
        string="品牌",
        related="catalog_item_id.brand_id",
        store=True,
        readonly=True,
    )
    categ_id = fields.Many2one(
        "product.category",
        string="材料分类",
        related="catalog_item_id.categ_id",
        store=True,
        readonly=True,
    )

    summary = fields.Text(string="摘要")
    content_html = fields.Html(string="旧正文缓存", sanitize=True)
    publish_date = fields.Datetime(string="发布时间")
    icon = fields.Char(string="图标")
    is_favorite = fields.Boolean(string="收藏", default=False)
    last_edited_uid = fields.Many2one("res.users", string="最后编辑人", readonly=True)
    last_edited_at = fields.Datetime(string="最后编辑时间", readonly=True)
    block_ids = fields.One2many("diecut.kb.block", "article_id", string="内容块")

    def action_open_full_editor(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "知识库文章",
            "res_model": "diecut.kb.article",
            "res_id": self.id,
            "view_mode": "form",
            "target": "current",
            "context": {
                "form_view_initial_mode": "edit",
            },
        }

    @api.model
    def kb_get_workspace_tree(self):
        records = self.search([], order="parent_path, sequence, id")
        return [
            {
                "id": rec.id,
                "name": rec.name,
                "parent_id": rec.parent_id.id if rec.parent_id else False,
                "state": rec.state,
                "icon": rec.icon or "",
                "is_favorite": bool(rec.is_favorite),
            }
            for rec in records
        ]

    @api.model
    def kb_load_page_payload(self, article_id):
        article = self.browse(article_id).exists()
        if not article:
            return {"article": False, "blocks": []}

        blocks = self.env["diecut.kb.block"].search(
            [("article_id", "=", article.id)],
            order="sequence, id",
        )
        return {
            "article": {
                "id": article.id,
                "name": article.name,
                "summary": article.summary or "",
                "state": article.state,
                "parent_id": article.parent_id.id if article.parent_id else False,
                "path": article.parent_path or "",
                "last_edited_at": article.last_edited_at.isoformat() if article.last_edited_at else False,
                "last_edited_uid": article.last_edited_uid.name if article.last_edited_uid else False,
            },
            "blocks": [block.to_client_dict() for block in blocks],
        }

    @api.model
    def kb_touch_article(self, article_id):
        article = self.browse(article_id).exists()
        if article:
            article.write(
                {
                    "last_edited_uid": self.env.user.id,
                    "last_edited_at": fields.Datetime.now(),
                }
            )
        return True

    @api.model
    def kb_apply_block_ops(self, article_id, ops):
        article = self.browse(article_id).exists()
        if not article:
            return {"ok": False, "error": "article_not_found"}

        Block = self.env["diecut.kb.block"]
        created_ids = []
        for op in ops or []:
            op_type = op.get("type")
            if op_type == "create":
                vals = {
                    "article_id": article.id,
                    "parent_block_id": op.get("parent_block_id") or False,
                    "sequence": int(op.get("sequence") or 10),
                    "depth": int(op.get("depth") or 0),
                    "block_type": op.get("block_type") or "paragraph",
                    "content_json": json.dumps(op.get("content") or {"text": ""}, ensure_ascii=False),
                    "collapsed": bool(op.get("collapsed")),
                }
                new_block = Block.create(vals)
                created_ids.append(new_block.id)
            elif op_type == "update":
                block = Block.browse(op.get("id")).exists()
                if not block or block.article_id.id != article.id:
                    continue
                vals = {}
                if "block_type" in op:
                    vals["block_type"] = op.get("block_type") or block.block_type
                if "content" in op:
                    vals["content_json"] = json.dumps(op.get("content") or {"text": ""}, ensure_ascii=False)
                if "collapsed" in op:
                    vals["collapsed"] = bool(op.get("collapsed"))
                if "sequence" in op:
                    vals["sequence"] = int(op.get("sequence") or block.sequence)
                if "depth" in op:
                    vals["depth"] = int(op.get("depth") or block.depth)
                if "parent_block_id" in op:
                    vals["parent_block_id"] = op.get("parent_block_id") or False
                if vals:
                    block.write(vals)
            elif op_type == "delete":
                block = Block.browse(op.get("id")).exists()
                if block and block.article_id.id == article.id:
                    block.unlink()

        self.kb_touch_article(article.id)
        return {"ok": True, "created_ids": created_ids}

    @api.model
    def kb_create_page(self, name, parent_id=False):
        page_name = (name or "").strip() or "新页面"
        vals = {
            "name": page_name,
            "parent_id": parent_id or False,
            "state": "draft",
        }
        record = self.create(vals)
        return {
            "id": record.id,
            "name": record.name,
        }

    @api.model
    def kb_archive_page(self, article_id):
        article = self.browse(article_id).exists()
        if not article:
            return {"ok": False, "error": "article_not_found"}
        article.write({"active": False})
        return {"ok": True}

    def action_restore_from_recycle(self):
        self.write({"active": True})
        return True

    def action_permanent_delete(self):
        for record in self:
            if record.active:
                raise UserError("请先将页面移入垃圾回收站后再永久删除。")
        # keep unlink restricted in ACL, allow permanent deletion only via recycle-bin action
        self.sudo().unlink()
        return {"type": "ir.actions.client", "tag": "reload"}
