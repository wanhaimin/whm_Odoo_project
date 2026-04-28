# -*- coding: utf-8 -*-

from odoo import api, fields, models
from odoo.exceptions import UserError


class DiecutCatalogSourceDocument(models.Model):
    _inherit = "diecut.catalog.source.document"

    compiled_item_ids = fields.Many2many(
        "diecut.catalog.item",
        compute="_compute_compiled_knowledge_links",
        string="关联产品",
    )
    compiled_item_count = fields.Integer(
        string="关联产品数",
        compute="_compute_compiled_knowledge_links",
    )
    compilable_item_ids = fields.Many2many(
        "diecut.catalog.item",
        compute="_compute_compiled_knowledge_links",
        string="可编译产品",
    )
    compilable_item_count = fields.Integer(
        string="可编译产品数",
        compute="_compute_compiled_knowledge_links",
    )
    compiled_article_ids = fields.Many2many(
        "diecut.kb.article",
        compute="_compute_compiled_knowledge_links",
        string="编译文章",
    )
    compiled_article_count = fields.Integer(
        string="编译文章数",
        compute="_compute_compiled_knowledge_links",
    )
    compile_block_reason = fields.Char(
        string="编译提示",
        compute="_compute_compiled_knowledge_links",
    )

    @api.depends("line_count", "import_status", "draft_payload", "brand_id", "name")
    def _compute_compiled_knowledge_links(self):
        for record in self:
            items = record._get_linked_catalog_items()
            compilable_items = items.filtered(
                lambda item: item.active and item.catalog_status in ("review", "published")
            )
            articles = items.mapped("compiled_article_id").filtered(lambda article: article.exists())
            record.compiled_item_ids = items
            record.compiled_item_count = len(items)
            record.compilable_item_ids = compilable_items
            record.compilable_item_count = len(compilable_items)
            record.compiled_article_ids = articles
            record.compiled_article_count = len(articles)
            record.compile_block_reason = record._get_compile_block_reason(items, compilable_items)

    def _get_compile_block_reason(self, items, compilable_items):
        self.ensure_one()
        if self.import_status != "applied":
            return "请先完成 AI/TDS 资料入库，再生成知识文章。"
        if not items:
            return "当前 AI/TDS 资料还没有匹配到已入库产品。"
        if not compilable_items:
            status_names = dict(self.env["diecut.catalog.item"]._fields["catalog_status"].selection)
            statuses = sorted(set(items.mapped("catalog_status")))
            readable = "、".join(status_names.get(status, status or "未设置") for status in statuses)
            return "已匹配到产品，但目录状态为 %s；请先发布或进入评审后再编译。" % readable
        return False

    def _get_linked_catalog_items(self):
        self.ensure_one()
        spec_line_model = self.env["diecut.catalog.item.spec.line"].sudo()
        item_model = self.env["diecut.catalog.item"].sudo()

        items = spec_line_model.search([("source_document_id", "=", self.id)]).mapped("catalog_item_id")
        if items:
            return items.filtered(lambda item: item.exists())

        payload = {}
        if hasattr(self, "_load_draft_payload"):
            try:
                payload = self._load_draft_payload() or {}
            except Exception:
                payload = {}

        candidates = []
        for row in (payload.get("items") or []):
            candidates.append(
                {
                    "brand_name": row.get("brand_name"),
                    "code": row.get("code") or row.get("item_code") or row.get("series_name"),
                }
            )
        for row in (payload.get("spec_values") or []):
            candidates.append(
                {
                    "brand_name": row.get("brand_name"),
                    "code": row.get("item_code") or row.get("code"),
                }
            )

        found = item_model.browse()
        for candidate in candidates:
            code = (candidate.get("code") or "").strip()
            if not code:
                continue
            domain = [("code", "=", code)]
            brand = self._resolve_brand(candidate.get("brand_name")) or self.brand_id
            if brand:
                domain.append(("brand_id", "=", brand.id))
            item = item_model.search(domain, limit=1)
            if item:
                found |= item
        return found.filtered(lambda item: item.exists())

    def _get_compilable_items(self):
        self.ensure_one()
        items = self.compilable_item_ids
        if not items:
            raise UserError(self.compile_block_reason or "当前 AI/TDS 资料还没有可用于知识编译的已入库产品。")
        return items

    def action_compile_knowledge_articles(self):
        items = self._get_compilable_items()
        return items.action_compile_knowledge()

    def action_open_compiled_articles(self):
        self.ensure_one()
        if not self.compiled_article_ids:
            raise UserError("当前 AI/TDS 资料还没有已生成的编译文章。")
        return {
            "type": "ir.actions.act_window",
            "name": "编译文章",
            "res_model": "diecut.kb.article",
            "view_mode": "list,kanban,form",
            "domain": [("id", "in", self.compiled_article_ids.ids)],
            "context": {
                "search_default_ai_compiled": 1,
            },
            "target": "current",
        }

    def action_open_compile_workspace(self):
        self.ensure_one()
        domain = [("compile_source", "!=", "manual")]
        if self.compiled_item_ids:
            domain = [("compile_source_item_id", "in", self.compiled_item_ids.ids)]
        return {
            "type": "ir.actions.act_window",
            "name": "知识编译工作台",
            "res_model": "diecut.kb.article",
            "view_mode": "list,kanban,form",
            "domain": domain,
            "search_view_id": self.env.ref("diecut_knowledge.view_diecut_kb_article_search").id,
            "context": {
                "search_default_ai_compiled": 1,
            },
            "target": "current",
        }
