# -*- coding: utf-8 -*-

import base64
import mimetypes

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
    knowledge_parse_state = fields.Selection(
        [
            ("pending", "待解析"),
            ("parsed", "已解析"),
            ("failed", "解析失败"),
            ("skipped", "已跳过"),
        ],
        string="知识解析状态",
        default="pending",
        index=True,
        copy=False,
    )
    knowledge_parsed_text = fields.Text(string="知识解析文本", copy=False)
    knowledge_parsed_markdown = fields.Text(string="知识解析 Markdown", copy=False)
    knowledge_parse_method = fields.Char(string="知识解析方式", readonly=True, copy=False)
    knowledge_page_count = fields.Integer(string="知识解析页数", readonly=True, copy=False)
    knowledge_parse_error = fields.Text(string="知识解析错误", readonly=True, copy=False)
    knowledge_parsed_at = fields.Datetime(string="知识解析时间", readonly=True, copy=False)

    @api.depends("line_count", "import_status", "draft_payload", "brand_id", "name")
    def _compute_compiled_knowledge_links(self):
        for record in self:
            items = record._get_linked_catalog_items()
            compilable_items = items.filtered(
                lambda item: item.active and item.catalog_status in ("review", "published")
            )
            item_articles = items.mapped("compiled_article_id").filtered(lambda article: article.exists())
            source_articles = self.env["diecut.kb.article"].search(
                [("compile_source_document_id", "=", record.id), ("active", "=", True)]
            )
            articles = item_articles | source_articles
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
            if self.knowledge_parsed_text or self.raw_text:
                return "当前资料还没有匹配到结构化产品；可以先编译 Wiki，但会进入人工复核。"
            return "当前资料还没有匹配到已入库产品，也没有可编译的解析文本。"
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

    def action_parse_for_knowledge(self):
        from ..services import pdf_extractor as extractor

        ok_count = fail_count = 0
        for record in self:
            attachment = record._get_knowledge_primary_attachment()
            if not attachment:
                record.write({
                    "knowledge_parse_state": "failed",
                    "knowledge_parse_error": "没有可解析的 PDF 或图片附件。",
                    "knowledge_parsed_at": fields.Datetime.now(),
                })
                fail_count += 1
                continue
            try:
                file_bytes = base64.b64decode(attachment.datas or b"")
            except Exception as exc:
                record.write({
                    "knowledge_parse_state": "failed",
                    "knowledge_parse_error": f"附件解码失败：{exc}",
                    "knowledge_parsed_at": fields.Datetime.now(),
                })
                fail_count += 1
                continue

            name = (attachment.name or record.primary_attachment_name or "").lower()
            mimetype = attachment.mimetype or mimetypes.guess_type(name)[0] or ""
            if mimetype == "application/pdf" or name.endswith(".pdf"):
                result = extractor.extract_pdf_text(file_bytes)
            elif mimetype.startswith("image/"):
                result = extractor.extract_image_text(file_bytes)
            else:
                result = {
                    "ok": False,
                    "text": "",
                    "markdown": "",
                    "page_count": 0,
                    "method": "skipped",
                    "error": f"不支持解析此类型：{mimetype or name or 'unknown'}",
                }

            vals = {
                "knowledge_parsed_text": result.get("text") or "",
                "knowledge_parsed_markdown": result.get("markdown") or "",
                "knowledge_parse_method": result.get("method") or "skipped",
                "knowledge_page_count": result.get("page_count") or 0,
                "knowledge_parse_error": result.get("error") or False,
                "knowledge_parsed_at": fields.Datetime.now(),
            }
            if result.get("ok"):
                vals["knowledge_parse_state"] = "parsed"
                ok_count += 1
            else:
                vals["knowledge_parse_state"] = "failed"
                fail_count += 1
            record.write(vals)

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": "知识资料解析",
                "message": f"解析完成：成功 {ok_count} / 失败 {fail_count}",
                "type": "success" if fail_count == 0 else "warning",
                "sticky": bool(fail_count),
            },
        }

    def action_compile_knowledge_articles(self):
        return self.action_compile_wiki()

    def action_compile_wiki(self):
        from ..services.kb_compiler import KbCompiler

        ok_count = fail_count = 0
        last_result = {}
        compiler = KbCompiler(self.env)
        for record in self:
            result = compiler.compile_from_source_document(record, force=True)
            last_result = result
            if result.get("ok"):
                ok_count += 1
            else:
                fail_count += 1
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": "Wiki 知识编译",
                "message": f"编译完成：成功 {ok_count} / 失败 {fail_count}"
                + (f"；{last_result.get('error')}" if fail_count and last_result.get("error") else ""),
                "type": "success" if fail_count == 0 else "warning",
                "sticky": bool(fail_count),
            },
        }

    def action_one_click_ingest(self):
        """一键入库：解析 → 编译 → 丰富 → lint → 标记同步"""
        from ..services.kb_compiler import KbCompiler

        ok_count, fail_count = 0, 0
        for record in self:
            # Step 1: 解析（如果尚未解析）
            if record.knowledge_parse_state != "parsed":
                parse_result = record.action_parse_for_knowledge()
                # 重新读取以获取解析后状态
                record = self.browse(record.id)
                if record.knowledge_parse_state != "parsed":
                    fail_count += 1
                    continue

            # Step 2: 异步加入编译队列（而非阻塞）
            self.env["diecut.kb.compile.job"].create({
                "source_document_id": record.id,
                "job_type": "source_document",
            })
            ok_count += 1

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": "一键入库",
                "message": f"解析完成 {ok_count} 个，已加入编译队列。队列处理完成后将自动同步到 Dify。",
                "type": "success" if fail_count == 0 else "warning",
                "sticky": bool(fail_count),
            },
        }

    def action_view_parsed_source(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "解析内容",
            "res_model": self._name,
            "view_mode": "form",
            "res_id": self.id,
            "target": "current",
        }

    def _get_knowledge_primary_attachment(self):
        self.ensure_one()
        if self.primary_attachment_id:
            return self.primary_attachment_id.sudo()
        if hasattr(self, "_get_effective_primary_attachment"):
            attachment = self._get_effective_primary_attachment()
            if attachment:
                return attachment.sudo()
        return self.env["ir.attachment"].sudo().search(
            [("res_model", "=", self._name), ("res_id", "=", self.id), ("type", "=", "binary")],
            limit=1,
            order="id",
        )

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

    @api.model
    def cron_compile_pending_sources(self):
        limit = int(
            self.env["ir.config_parameter"].sudo().get_param(
                "diecut_knowledge.source_compile_batch_limit", default="5"
            )
            or 5
        )
        sources = self.search(
            [
                ("import_status", "=", "applied"),
                "|",
                ("knowledge_parse_state", "=", "parsed"),
                ("raw_text", "!=", False),
            ],
            limit=limit,
            order="write_date asc, id asc",
        )
        ok_count = fail_count = 0
        from ..services.kb_compiler import KbCompiler

        compiler = KbCompiler(self.env)
        for source in sources:
            result = compiler.compile_from_source_document(source)
            if result.get("ok"):
                ok_count += 1
            else:
                fail_count += 1
        return {"total": len(sources), "ok": ok_count, "failed": fail_count}
