# -*- coding: utf-8 -*-

import base64
import json
import mimetypes
import re

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
        search="_search_compiled_article_count",
        string="编译文章数",
        compute="_compute_compiled_knowledge_links",
    )
    compile_block_reason = fields.Char(
        string="编译提示",
        compute="_compute_compiled_knowledge_links",
    )
    knowledge_source_kind = fields.Selection(
        [
            ("tds", "TDS / 技术数据表"),
            ("selection_guide", "选型指南"),
            ("application_note", "应用说明"),
            ("processing_experience", "加工经验"),
            ("qa", "问答资料"),
            ("raw", "通用资料"),
        ],
        string="资料类型",
        compute="_compute_knowledge_source_kind",
        store=True,
        readonly=True,
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
    route_plan_state = fields.Selection(
        [
            ("draft", "待生成方案"),
            ("ready", "待确认"),
            ("confirmed", "已确认"),
            ("running", "执行中"),
            ("done", "已完成"),
            ("review", "需人工审核"),
            ("failed", "方案失败"),
        ],
        string="处理方案状态",
        default="draft",
        index=True,
        copy=False,
        tracking=True,
    )
    route_plan_summary = fields.Text(string="AI 处理方案摘要", readonly=True, copy=False)
    route_plan_json = fields.Text(string="AI 处理方案 JSON", readonly=True, copy=False)
    route_plan_error = fields.Text(string="处理方案错误", readonly=True, copy=False)
    route_plan_generated_at = fields.Datetime(string="方案生成时间", readonly=True, copy=False)
    route_plan_confirmed_at = fields.Datetime(string="方案确认时间", readonly=True, copy=False)

    vault_raw_path = fields.Char(string="Vault Raw 路径", readonly=True, copy=False, index=True)
    vault_file_hash = fields.Char(string="Vault 文件 Hash", readonly=True, copy=False, index=True)
    vault_sync_state = fields.Selection(
        [
            ("missing", "文件缺失"),
            ("discovered", "新发现"),
            ("none", "未同步"),
            ("imported", "已导入"),
            ("processed", "已处理"),
            ("failed", "失败"),
            ("skipped", "已跳过"),
        ],
        string="Vault 同步状态",
        default="none",
        readonly=True,
        copy=False,
        index=True,
    )
    vault_last_synced_at = fields.Datetime(string="Vault 最近同步时间", readonly=True, copy=False)
    vault_error = fields.Text(string="Vault 同步错误", readonly=True, copy=False)

    wiki_compile_state = fields.Selection(
        [
            ("pending", "待增量编译"),
            ("queued", "已加入队列"),
            ("compiled", "已增量编译"),
            ("review", "已增量编译"),
            ("failed", "编译失败"),
            ("skipped", "已跳过"),
        ],
        string="Wiki 增量状态",
        default="pending",
        index=True,
        copy=False,
    )
    wiki_compile_hash = fields.Char(string="Wiki 编译 Hash", readonly=True, copy=False, index=True)
    wiki_compiled_at = fields.Datetime(string="Wiki 最近编译时间", readonly=True, copy=False)
    wiki_compile_error = fields.Text(string="Wiki 编译错误", readonly=True, copy=False)

    def action_open_ai_advisor(self):
        self.ensure_one()
        return {
            "type": "ir.actions.client",
            "tag": "diecut_ai_advisor",
            "params": {
                "mode": "source",
                "model": self._name,
                "record_id": self.id,
                "record_name": self.name or self.primary_attachment_name or "",
            },
        }

    @api.model
    def cron_scan_raw_inbox(self):
        from ..services.kb_vault_mirror import KbVaultMirror

        limit = int(
            self.env["ir.config_parameter"].sudo().get_param(
                "diecut_knowledge.vault_raw_batch_limit", default="20"
            )
            or 20
        )
        return KbVaultMirror(self.env).scan_raw_inbox(limit=limit)

    @api.model
    def _notify(self, kind, message, next_action=None):
        params = {
            "title": "资料收件箱",
            "message": message,
            "type": kind,
            "sticky": False,
        }
        if next_action:
            params["next"] = next_action
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": params,
        }

    @api.model
    def action_scan_raw_inbox(self):
        from ..services.kb_vault_mirror import KbVaultMirror

        limit = int(
            self.env["ir.config_parameter"].sudo().get_param(
                "diecut_knowledge.vault_raw_batch_limit", default="20"
            )
            or 20
        )
        try:
            result = KbVaultMirror(self.env).scan_raw_inbox(limit=limit)
        except Exception as exc:
            return self._notify("danger", "Vault 资料同步失败：%s" % exc)
        record_ids = self._vault_sync_result_ids(result)
        if record_ids:
            return self._notify(
                "success" if not result.get("errors") else "warning",
                self._vault_sync_message(result),
                next_action=self._raw_inbox_result_action(record_ids),
            )
        return self._notify(
            "warning" if result.get("errors") else "info",
            "Vault raw 目录没有发现可同步变化。目录：%s；错误：%s。"
            % (result.get("raw_path") or result.get("inbox_path") or "raw", len(result.get("errors") or [])),
        )

    @api.model
    def action_sync_vault_sources_and_queue(self):
        from ..services.kb_vault_mirror import KbVaultMirror

        limit = int(
            self.env["ir.config_parameter"].sudo().get_param(
                "diecut_knowledge.vault_raw_batch_limit", default="20"
            )
            or 20
        )
        try:
            result = KbVaultMirror(self.env).scan_raw_inbox(limit=limit, enqueue_compile=True)
        except Exception as exc:
            return self._notify("danger", "Vault 同步并排队失败：%s" % exc)
        record_ids = self._vault_sync_result_ids(result)
        return self._notify(
            "success" if not result.get("errors") else "warning",
            self._vault_sync_message(result, include_queue=True),
            next_action=self._raw_inbox_result_action(record_ids) if record_ids else None,
        )

    @api.model
    def _vault_sync_result_ids(self, result):
        return (
            (result.get("created_ids") or [])
            + (result.get("updated_ids") or [])
            + (result.get("unchanged_ids") or [])
            + (result.get("missing_ids") or [])
        )

    @api.model
    def _vault_sync_message(self, result, include_queue=False):
        message = "Vault 同步完成：新建 %(created)s，更新 %(updated)s，已有 %(unchanged)s，缺失 %(missing)s，错误 %(errors)s。"
        if include_queue:
            message = "Vault 同步完成：新建 %(created)s，更新 %(updated)s，已有 %(unchanged)s，缺失 %(missing)s，新增编译队列 %(queued)s，错误 %(errors)s。"
        return message % {
            "created": result.get("created", 0),
            "updated": result.get("updated", 0),
            "unchanged": result.get("unchanged", 0),
            "missing": result.get("missing", 0),
            "queued": result.get("queued", 0),
            "errors": len(result.get("errors") or []),
        }

    @api.model
    def _raw_inbox_result_action(self, record_ids):
        return {
            "type": "ir.actions.act_window",
            "name": "Vault 资料同步结果",
            "res_model": "diecut.catalog.source.document",
            "view_mode": "list,form",
            "views": [(False, "list"), (False, "form")],
            "domain": [("id", "in", record_ids)],
            "context": {
                "default_source_type": "pdf",
                "search_default_group_by_import_status": 0,
            },
            "target": "current",
        }

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._ensure_primary_attachment_from_source_file()
        return records

    def write(self, vals):
        graph_sensitive = {
            "name",
            "brand_id",
            "categ_id",
            "source_file",
            "source_filename",
            "primary_attachment_id",
            "raw_text",
            "knowledge_parsed_text",
            "knowledge_parsed_markdown",
        }
        result = super().write(vals)
        if {"source_file", "source_filename"} & set(vals):
            self._ensure_primary_attachment_from_source_file()
        if graph_sensitive & set(vals):
            articles = self.mapped("compiled_article_ids").filtered(lambda article: article.exists())
            if articles:
                articles.write({"last_graph_checked_at": False})
                self.env["diecut.kb.wiki.log"].sudo().create(
                    [
                        {
                            "event_type": "lint",
                            "name": ("资料变化，Wiki 图谱待复核：%s" % record.name)[:200],
                            "article_id": article.id,
                            "source_document_id": record.id,
                            "summary": "资料标题、品牌、分类或解析正文发生变化，旧 Wiki 关系需要由 Graph Agent 重新判断。",
                        }
                        for record in self
                        for article in record.compiled_article_ids.filtered(lambda item: item.exists())
                    ]
                )
        return result

    @api.depends("name", "source_type", "primary_attachment_name", "source_filename", "raw_text")
    def _compute_knowledge_source_kind(self):
        for record in self:
            haystack = " ".join(
                filter(
                    None,
                    [
                        record.name or "",
                        record.primary_attachment_name or "",
                        record.source_filename or "",
                        (record.raw_text or "")[:3000],
                    ],
                )
            ).lower()
            if re.search(r"\btds\b|technical data sheet|数据表|技术数据|datasheet", haystack):
                kind = "tds"
            elif any(token in haystack for token in ("选型", "selection guide", "selection handbook", "选型手册")):
                kind = "selection_guide"
            elif any(token in haystack for token in ("application", "应用", "方案", "case study")):
                kind = "application_note"
            elif any(token in haystack for token in ("加工", "工艺", "经验", "process", "troubleshooting")):
                kind = "processing_experience"
            elif any(token in haystack for token in ("faq", "问答", "问题", "qa", "q&a")):
                kind = "qa"
            else:
                kind = "raw"
            record.knowledge_source_kind = kind

    @api.depends("line_count", "import_status", "draft_payload", "brand_id", "name", "raw_text", "knowledge_parse_state")
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

    @api.model
    def _search_compiled_article_count(self, operator, value):
        Article = self.env["diecut.kb.article"].sudo()
        grouped = Article.read_group(
            [("compile_source_document_id", "!=", False), ("active", "=", True)],
            ["compile_source_document_id"],
            ["compile_source_document_id"],
        )
        ids_with_articles = [row["compile_source_document_id"][0] for row in grouped if row.get("compile_source_document_id")]
        try:
            numeric_value = int(value or 0)
        except Exception:
            numeric_value = 0
        positive_ops = {">", ">=", "!=", "not in"}
        if operator in positive_ops and numeric_value <= 0:
            return [("id", "in", ids_with_articles)]
        if operator in ("=", "<=", "<") and numeric_value <= 0:
            return [("id", "not in", ids_with_articles)]
        return [("id", "in", ids_with_articles)]

    def _get_compile_block_reason(self, items, compilable_items):
        self.ensure_one()
        if not (self.knowledge_parsed_text or self.knowledge_parsed_markdown or self.raw_text or self.result_message):
            return "请先解析原始资料，或补充可用于编译的正文文本。"
        if self.knowledge_source_kind == "tds" and self.import_status != "applied":
            return "这是 TDS 资料：可先编译 Wiki；如需进入材料选型库，请使用“抽取材料参数”生成结构化草稿并人工入库。"
        if not items:
            return "当前资料还没有匹配到结构化产品；可以先编译 Wiki，文章会按风险规则进入发布或人工审核。"
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
            raise UserError(self.compile_block_reason or "当前资料还没有可用于知识编译的已入库产品。")
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

    def action_generate_route_plan(self):
        from ..services.kb_compiler import KbCompiler

        ok_count = fail_count = 0
        compiler = KbCompiler(self.env)
        for record in self:
            result = compiler.generate_source_route_plan(record)
            if result.get("ok"):
                ok_count += 1
            else:
                fail_count += 1
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": "AI 处理方案",
                "message": f"方案生成完成：成功 {ok_count} / 失败 {fail_count}。请确认后再执行。",
                "type": "success" if fail_count == 0 else "warning",
                "sticky": bool(fail_count),
            },
        }

    def action_reset_route_plan(self):
        pending = self.env["diecut.kb.compile.job"].sudo().search([
            ("source_document_id", "in", self.ids),
            ("state", "in", ["pending", "processing"]),
        ])
        if pending:
            pending.write({"state": "done", "error_message": "处理方案已重置"})
        self.write({
            "route_plan_state": "draft",
            "route_plan_summary": False,
            "route_plan_json": False,
            "route_plan_error": False,
            "route_plan_generated_at": False,
            "route_plan_confirmed_at": False,
        })
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": "AI 处理方案",
                "message": "已重置处理方案，可以重新生成。",
                "type": "success",
                "sticky": False,
            },
        }

    def action_confirm_route_plan_execute(self):
        from ..services.kb_compiler import KbCompiler

        ok_count = fail_count = 0
        compiler = KbCompiler(self.env)
        for record in self:
            result = compiler.execute_source_route_plan(record)
            if result.get("ok"):
                ok_count += 1
            else:
                fail_count += 1
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": "确认方案并执行",
                "message": f"执行完成：成功 {ok_count} / 失败 {fail_count}。",
                "type": "success" if fail_count == 0 else "warning",
                "sticky": bool(fail_count),
            },
        }

    def action_extract_material_draft(self):
        run_action = getattr(self, "action_generate_draft", None)
        if not callable(run_action):
            raise UserError("当前环境未安装或未启用 AI/TDS 草稿生成能力。")
        run_action()
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": "材料参数抽取",
                "message": "已提交 AI/TDS 抽取任务。完成后请在草稿编辑页校验，并人工执行“入库草稿”。",
                "type": "success",
                "sticky": False,
            },
        }

    def _load_route_plan(self):
        self.ensure_one()
        if not self.route_plan_json:
            return {}
        try:
            data = json.loads(self.route_plan_json)
        except Exception:
            return {}
        return data if isinstance(data, dict) else {}

    def _ensure_primary_attachment_from_source_file(self):
        attachment_model = self.env["ir.attachment"].sudo()
        for record in self:
            if record.primary_attachment_id or not record.source_file:
                continue
            filename = record.source_filename or record.name or "source-file"
            existing = attachment_model.search(
                [
                    ("res_model", "=", record._name),
                    ("res_id", "=", record.id),
                    ("res_field", "=", False),
                    ("name", "=", filename),
                    ("type", "=", "binary"),
                ],
                limit=1,
            )
            attachment = existing or attachment_model.create(
                {
                    "name": filename,
                    "res_model": record._name,
                    "res_id": record.id,
                    "type": "binary",
                    "datas": record.source_file,
                    "mimetype": mimetypes.guess_type(filename)[0] or "application/octet-stream",
                }
            )
            record.with_context(skip_source_file_attachment=True).sudo().write({"primary_attachment_id": attachment.id})

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

    def action_rebuild_wiki_graph_agent(self):
        from ..services.kb_compiler import KbCompiler

        compiler = KbCompiler(self.env)
        total_links = 0
        total_articles = 0
        for record in self:
            source_text = compiler._get_source_document_text(record)
            linked_items = record.compilable_item_ids or record.compiled_item_ids
            for article in record.compiled_article_ids.filtered(lambda item: item.exists() and item.state != "archived"):
                result = compiler._connect_article_to_wiki_graph(
                    article,
                    record,
                    linked_items,
                    source_text,
                    reset_existing=True,
                )
                total_links += result.get("links", 0)
                total_articles += 1
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": "Wiki 图谱 Agent",
                "message": f"图谱复核完成：处理 {total_articles} 篇 Wiki，新增或刷新 {total_links} 条关联。",
                "type": "success",
                "sticky": False,
            },
        }



    def action_view_parsed_source(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "解析内容",
            "res_model": self._name,
            "view_mode": "form",
            "views": [(False, "form")],
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
            raise UserError("当前资料还没有已生成的 Wiki 页面。")
        return {
            "type": "ir.actions.act_window",
            "name": "Wiki 页面",
            "res_model": "diecut.kb.article",
            "view_mode": "list,kanban,form",
            "views": [(False, "list"), (False, "kanban"), (False, "form")],
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
            "name": "Wiki 文章",
            "res_model": "diecut.kb.article",
            "view_mode": "list,kanban,form",
            "views": [(False, "list"), (False, "kanban"), (False, "form")],
            "domain": domain,
            "search_view_id": self.env.ref("diecut_knowledge.view_diecut_kb_article_search").id,
            "context": {
                "search_default_ai_compiled": 1,
            },
            "target": "current",
        }

    def _ensure_source_compile_job(self):
        Job = self.env["diecut.kb.compile.job"].sudo()
        created = Job.browse()
        for record in self:
            existing = Job.search([
                ("source_document_id", "=", record.id),
                ("job_type", "=", "source_document"),
                ("state", "in", ["pending", "processing"]),
            ], limit=1)
            if existing:
                continue
            created |= Job.create({
                "source_document_id": record.id,
                "job_type": "source_document",
                "source_layer": "raw_source",
                "source_reason": "Queued by source document incremental ingest.",
            })
        return created

    def _incremental_source_hash(self):
        self.ensure_one()
        text = self.knowledge_parsed_markdown or self.knowledge_parsed_text or self.raw_text or self.result_message or ""
        payload = {
            "id": self.id,
            "vault_file_hash": self.vault_file_hash or "",
            "path": self.vault_raw_path or self.source_filename or self.primary_attachment_name or "",
            "parse_state": self.knowledge_parse_state or "",
            "parse_method": self.knowledge_parse_method or "",
            "page_count": self.knowledge_page_count or 0,
            "text_hash": __import__("hashlib").sha1(text.encode("utf-8")).hexdigest(),
            "items": self.compiled_item_ids.ids,
        }
        return __import__("hashlib").sha1(json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()

    def _incremental_group_key(self):
        self.ensure_one()
        brand = self.brand_id.name if self.brand_id else ""
        item_brand = self.compiled_item_ids[:1].brand_id.name if self.compiled_item_ids[:1].brand_id else ""
        category = self.categ_id.complete_name if self.categ_id else ""
        item_category = self.compiled_item_ids[:1].categ_id.complete_name if self.compiled_item_ids[:1].categ_id else ""
        title = (self.name or self.primary_attachment_name or self.source_filename or "source").lower()
        tokens = re.findall(r"[A-Za-z0-9][A-Za-z0-9\-_/]{1,}|[\u4e00-\u9fff]{2,8}", title)
        keyword = tokens[0] if tokens else str(self.id)
        return "|".join(
            [
                (brand or item_brand or "no-brand").strip().lower(),
                (self.knowledge_source_kind or "raw").strip().lower(),
                (category or item_category or keyword).strip().lower(),
            ]
        )[:240]

    @api.model
    def _incremental_compile_domain(self):
        return [
            ("vault_file_hash", "!=", False),
            ("vault_sync_state", "!=", "missing"),
            "|",
            ("knowledge_parse_state", "=", "parsed"),
            ("raw_text", "!=", False),
        ]

    def _has_running_incremental_job(self):
        if not self:
            return {}
        Job = self.env["diecut.kb.compile.job"].sudo()
        existing = Job.search(
            [
                ("job_type", "=", "wiki_incremental"),
                ("state", "in", ["pending", "processing"]),
                ("incremental_source_document_ids", "in", self.ids),
            ]
        )
        result = {source_id: False for source_id in self.ids}
        for job in existing:
            for source in job.incremental_source_document_ids:
                result[source.id] = True
        return result

    @api.model
    def cron_enqueue_incremental_wiki_compile(self):
        return self._enqueue_incremental_wiki_compile()

    @api.model
    def action_enqueue_incremental_wiki_compile(self):
        result = self._enqueue_incremental_wiki_compile()
        return self._notify(
            "success" if result.get("created") else "info",
            "增量编译入队完成：创建 %s 个主题任务，覆盖 %s 条资料。"
            % (result.get("created", 0), result.get("source_count", 0)),
        )

    @api.model
    def _enqueue_incremental_wiki_compile(self, sources=False):
        config = self.env["ir.config_parameter"].sudo()
        source_limit = int(config.get_param("diecut_knowledge.incremental_wiki_batch_limit", default="20") or 20)
        group_limit = int(config.get_param("diecut_knowledge.incremental_wiki_group_limit", default="5") or 5)
        context_limit = int(config.get_param("diecut_knowledge.incremental_wiki_context_article_limit", default="12") or 12)
        candidates = sources or self.search(self._incremental_compile_domain(), limit=source_limit * 3, order="write_date asc, id asc")
        running_map = candidates._has_running_incremental_job()
        changed = self.browse()
        hash_by_id = {}
        for source in candidates:
            current_hash = source._incremental_source_hash()
            hash_by_id[source.id] = current_hash
            if running_map.get(source.id):
                continue
            if source.wiki_compile_hash and source.wiki_compile_hash == current_hash and source.wiki_compile_state == "compiled":
                continue
            changed |= source
            if len(changed) >= source_limit:
                break
        groups = {}
        for source in changed:
            groups.setdefault(source._incremental_group_key(), self.browse())
            groups[source._incremental_group_key()] |= source
        Job = self.env["diecut.kb.compile.job"].sudo()
        created = Job.browse()
        from ..services.kb_compiler import KbCompiler

        compiler = KbCompiler(self.env)
        for group_key, group_sources in list(groups.items())[:group_limit]:
            target_articles = compiler.find_incremental_wiki_targets(group_sources, limit=context_limit)
            existing = Job.search(
                [
                    ("job_type", "=", "wiki_incremental"),
                    ("state", "in", ["pending", "processing"]),
                    ("compile_group_key", "=", group_key),
                ],
                limit=1,
            )
            if existing:
                continue
            snapshot = {
                str(source.id): hash_by_id.get(source.id) or source._incremental_source_hash()
                for source in group_sources
            }
            # 根据资料解析状态确定 source_layer
            is_all_parsed = all(s.knowledge_parse_state == "parsed" for s in group_sources)
            has_any_parsed = any(s.knowledge_parse_state == "parsed" for s in group_sources)
            source_layer = "raw_source" if is_all_parsed else ("mixed" if has_any_parsed else "wiki")
            job = Job.create(
                {
                    "job_type": "wiki_incremental",
                    "incremental_source_document_ids": [(6, 0, group_sources.ids)],
                    "target_article_ids": [(6, 0, target_articles.ids)],
                    "compile_group_key": group_key,
                    "source_hash_snapshot": json.dumps(snapshot, ensure_ascii=False, sort_keys=True),
                    "source_layer": source_layer,
                    "source_reason": "Karpathy-style full-library-aware incremental Wiki compile.",
                    "input_summary": "Sources: %s\nCandidate articles: %s"
                    % (", ".join(group_sources.mapped("name")[:10]), ", ".join(target_articles.mapped("name")[:10])),
                }
            )
            created |= job
            group_sources.write({"wiki_compile_state": "queued", "wiki_compile_error": False})
        return {"created": len(created), "job_ids": created.ids, "source_count": sum(len(job.incremental_source_document_ids) for job in created)}

    def action_one_click_ingest(self):
        ok_count, fail_count = 0, 0
        for record in self:
            if record.knowledge_parse_state != "parsed":
                record.action_parse_for_knowledge()
                record = self.browse(record.id)
                if record.knowledge_parse_state != "parsed":
                    fail_count += 1
                    continue
            self._enqueue_incremental_wiki_compile(sources=record)
            ok_count += 1
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": "Wiki 编译队列",
                "message": "解析完成 %s 个，已按增量规则加入 Wiki 编译队列。" % ok_count,
                "type": "success" if fail_count == 0 else "warning",
                "sticky": bool(fail_count),
            },
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
