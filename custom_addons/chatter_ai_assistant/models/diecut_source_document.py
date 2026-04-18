# -*- coding: utf-8 -*-

import base64
import html
import json
import mimetypes
import re

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError


class DiecutCatalogSourceDocument(models.Model):
    _inherit = "diecut.catalog.source.document"

    chatter_ai_last_run_state = fields.Selection(
        [
            ("running", "Running"),
            ("succeeded", "Succeeded"),
            ("failed", "Failed"),
        ],
        string="Last AI Run State",
        readonly=True,
        copy=False,
    )
    chatter_ai_last_run_action = fields.Char(string="Last AI Action", readonly=True, copy=False)
    chatter_ai_last_run_at = fields.Datetime(string="Last AI Run At", readonly=True, copy=False)
    chatter_ai_last_run_message = fields.Text(string="Last AI Run Message", readonly=True, copy=False)
    chatter_ai_preserved_parse_version = fields.Char(string="Preserved Parse Version", readonly=True, copy=False)
    chatter_ai_preserved_import_status = fields.Char(string="Preserved Import Status", readonly=True, copy=False)
    chatter_ai_status_banner_html = fields.Html(
        string="AI Status Banner",
        compute="_compute_chatter_ai_status_banner_html",
        sanitize=False,
    )

    @api.depends(
        "chatter_ai_last_run_state",
        "chatter_ai_last_run_action",
        "chatter_ai_last_run_at",
        "chatter_ai_last_run_message",
        "chatter_ai_preserved_parse_version",
        "chatter_ai_preserved_import_status",
        "parse_version",
        "import_status",
    )
    def _compute_chatter_ai_status_banner_html(self):
        labels = {
            "extract_source": "提取原文",
            "identify_handbook": "识别手册结构",
            "parse": "解析",
            "extract_params": "参数提取",
            "reparse": "重新识别",
            "summarize": "总结",
        }
        state_classes = {
            "running": "alert alert-info",
            "succeeded": "alert alert-success",
            "failed": "alert alert-warning",
        }
        for record in self:
            state = record.chatter_ai_last_run_state
            if not state:
                record.chatter_ai_status_banner_html = False
                continue
            action_label = labels.get(record.chatter_ai_last_run_action, record.chatter_ai_last_run_action or "AI 任务")
            parts = []
            if state == "running":
                parts.append("<strong>%s进行中。</strong>" % action_label)
                if record.chatter_ai_preserved_parse_version or record.parse_version:
                    parts.append(
                        "当前页面暂时保留旧草稿：%s / %s。"
                        % (
                            html.escape(record.chatter_ai_preserved_parse_version or record.parse_version or "-"),
                            html.escape(record.chatter_ai_preserved_import_status or record.import_status or "-"),
                        )
                    )
            elif state == "succeeded":
                parts.append("<strong>%s成功。</strong>" % action_label)
                parts.append(
                    "当前草稿已更新为 %s / %s。"
                    % (
                        html.escape(record.parse_version or "-"),
                        html.escape(record.import_status or "-"),
                    )
                )
            else:
                parts.append("<strong>%s失败，未覆盖旧草稿。</strong>" % action_label)
                parts.append(
                    "当前仍保留上一版草稿：%s / %s。"
                    % (
                        html.escape(record.chatter_ai_preserved_parse_version or record.parse_version or "-"),
                        html.escape(record.chatter_ai_preserved_import_status or record.import_status or "-"),
                    )
                )
            if record.chatter_ai_last_run_message:
                parts.append(html.escape(record.chatter_ai_last_run_message))
            record.chatter_ai_status_banner_html = (
                '<div class="%s" role="alert">%s</div>'
                % (state_classes.get(state, "alert alert-secondary"), " ".join(parts))
            )

    def _chatter_ai_mark_run_started(self, run):
        for record in self:
            values = {
                "chatter_ai_last_run_state": "running",
                "chatter_ai_last_run_action": run.document_action or run.task_type or "chat",
                "chatter_ai_last_run_at": fields.Datetime.now(),
                "chatter_ai_last_run_message": False,
            }
            if run.document_action in ("parse", "extract_params", "reparse", "extract_source", "identify_handbook"):
                values.update(
                    {
                        "chatter_ai_preserved_parse_version": record.parse_version or False,
                        "chatter_ai_preserved_import_status": record.import_status or False,
                    }
                )
            record.write(values)

    def _chatter_ai_mark_run_success(self, run, payload):
        summary = self._chatter_ai_user_summary(run.document_action, payload)
        self.write(
            {
                "chatter_ai_last_run_state": "succeeded",
                "chatter_ai_last_run_action": run.document_action or run.task_type or "chat",
                "chatter_ai_last_run_at": fields.Datetime.now(),
                "chatter_ai_last_run_message": summary,
                "chatter_ai_preserved_parse_version": False,
                "chatter_ai_preserved_import_status": False,
            }
        )

    def _chatter_ai_user_summary(self, action, payload):
        self.ensure_one()
        if action == "identify_handbook":
            review = self.handbook_review_id
            series_count = len(review.series_ids) if review else 0
            model_count = sum(review.series_ids.mapped("model_count")) if review else 0
            issue_count = sum(review.series_ids.mapped("issue_count")) if review else 0
            family_name = (review.family_name if review else False) or self.name or "手册"
            return "已识别《%s》的手册结构，生成 %s 个系列、%s 个型号候选，异常 %s 条。正在打开系列总览页。" % (
                family_name,
                series_count,
                model_count,
                issue_count,
            )
        return payload.get("summary") or payload.get("reply_text") or False

    def _chatter_ai_mark_run_failure(self, run, error_message):
        self.write(
            {
                "chatter_ai_last_run_state": "failed",
                "chatter_ai_last_run_action": run.document_action or run.task_type or "chat",
                "chatter_ai_last_run_at": fields.Datetime.now(),
                "chatter_ai_last_run_message": error_message or False,
            }
        )

    @api.model
    def _chatter_ai_extract_urls(self, text):
        if not text:
            return []
        return re.findall(r"https?://[^\s]+", text)

    def _chatter_ai_resolve_source_attachments(self, message_attachments=False):
        self.ensure_one()
        attachments = message_attachments or self.env["ir.attachment"]
        if attachments:
            return attachments
        primary = self._get_effective_primary_attachment()
        if primary:
            return primary
        return self.env["ir.attachment"]

    def _chatter_ai_source_kind(self, attachments=False, message_text=False):
        self.ensure_one()
        attachment = (attachments or self.env["ir.attachment"])[:1]
        if attachment:
            guessed = self._guess_source_type_from_attachment(attachment)
            return "image" if guessed == "ocr" else guessed
        if self._chatter_ai_extract_urls(message_text) or self.source_url:
            return "webpage"
        if self.raw_text:
            return "text"
        return "mixed"

    @api.model
    def _guess_source_type_from_attachment(self, attachment):
        if not attachment:
            return "mixed"
        mimetype = attachment.mimetype or mimetypes.guess_type(attachment.name or "")[0] or ""
        filename = (attachment.name or "").lower()
        if mimetype.startswith("image/"):
            return "ocr"
        if mimetype == "application/pdf" or filename.endswith(".pdf"):
            return "pdf"
        if any(filename.endswith(ext) for ext in (".htm", ".html", ".mht", ".mhtml")):
            return "url"
        if mimetype.startswith("text/"):
            return "manual"
        return "mixed"

    @api.model
    def _chatter_ai_dictionary_enhanced_mode(self, message_text):
        text = (message_text or "").strip().lower()
        if not text:
            return False
        keywords = [
            "参数字典",
            "按字典",
            "用已有参数",
            "统一命名",
            "字典项",
            "dictionary",
            "param key",
            "param_key",
            "existing param",
        ]
        return any(token in text for token in keywords)

    @api.model
    def _chatter_ai_dictionary_index(self, context):
        rows = []
        for row in (context.get("param_dictionary_snapshot") or []):
            if not isinstance(row, dict):
                continue
            rows.append(
                {
                    "param_key": row.get("param_key") or False,
                    "name": row.get("name") or False,
                    "canonical_name_zh": row.get("canonical_name_zh") or False,
                    "canonical_name_en": row.get("canonical_name_en") or False,
                    "aliases_text": row.get("aliases_text") or False,
                    "is_main_field": bool(row.get("is_main_field")),
                    "main_field_name": row.get("main_field_name") or False,
                    "spec_category": row.get("spec_category") or False,
                    "preferred_unit": row.get("preferred_unit") or False,
                }
            )
        return rows

    @api.model
    def _chatter_ai_collect_dictionary_terms(self, current_draft, message_text, raw_text):
        terms = set()
        raw_excerpt = (raw_text or "")[:12000]
        draft_payload = current_draft if isinstance(current_draft, dict) else {}
        for bucket in ("params", "category_params", "spec_values"):
            for row in draft_payload.get(bucket) or []:
                if not isinstance(row, dict):
                    continue
                for key in ("param_key", "param_name", "name", "display_name"):
                    value = row.get(key)
                    if isinstance(value, str) and value.strip():
                        terms.add(value.strip().lower())
        source_text = "\n".join(part for part in [message_text or "", raw_excerpt] if part)
        if source_text:
            lowered = source_text.lower()
            for token in re.split(r"[\s,;:，。；、?()（）\[\]{}]+", lowered):
                token = token.strip()
                if len(token) >= 2:
                    terms.add(token)
        return terms

    @api.model
    def _chatter_ai_dictionary_candidates(self, context, *, current_draft=False, message_text=False, raw_text=False):
        index_rows = self._chatter_ai_dictionary_index(context)
        if not index_rows:
            return []
        terms = self._chatter_ai_collect_dictionary_terms(current_draft, message_text, raw_text)
        raw_excerpt = (raw_text or "")[:12000].lower()
        message_lower = (message_text or "").lower()
        candidates = []
        for row in index_rows:
            haystacks = [
                row.get("param_key") or "",
                row.get("name") or "",
                row.get("canonical_name_zh") or "",
                row.get("canonical_name_en") or "",
                row.get("aliases_text") or "",
            ]
            haystacks = [item.lower() for item in haystacks if item]
            matched = any(item in terms for item in haystacks if item)
            if not matched and raw_excerpt:
                matched = any(item and item in raw_excerpt for item in haystacks)
            if not matched and message_lower:
                matched = any(item and item in message_lower for item in haystacks)
            if matched:
                candidates.append(row)
        return candidates[:80]

    @api.model
    def _chatter_ai_compact_copilot_context(self, context):
        context = context if isinstance(context, dict) else {}
        skill_bundle = context.get("skill_bundle") or {}
        compact_bundle = {
            "skills_loaded": skill_bundle.get("skills_loaded") or [],
            "task_instructions": (skill_bundle.get("task_instructions") or [])[:8],
            "field_mapping_guidance": (skill_bundle.get("field_mapping_guidance") or [])[:8],
            "negative_rules": (skill_bundle.get("negative_rules") or [])[:6],
            "few_shot_examples": (skill_bundle.get("few_shot_examples") or [])[:4],
            "output_schema": skill_bundle.get("output_schema") or {},
            "param_aliases": skill_bundle.get("param_aliases") or {},
        }
        dictionary_index = self._chatter_ai_dictionary_index(context)
        main_field_rules = [
            {
                "param_key": row.get("param_key"),
                "main_field_name": row.get("main_field_name"),
                "name": row.get("name"),
            }
            for row in dictionary_index
            if row.get("is_main_field") and row.get("param_key") and row.get("main_field_name")
        ]
        return {
            "skill_profile": context.get("skill_profile") or False,
            "brand_skill": context.get("brand_skill") or False,
            "skills_loaded": context.get("skills_loaded") or compact_bundle["skills_loaded"],
            "skill_bundle": compact_bundle,
            "source_context": context.get("source_context") or {},
            "main_field_whitelist": context.get("main_field_whitelist") or [],
            "main_field_rules": main_field_rules,
            "category_param_snapshot": context.get("category_param_snapshot") or [],
            "dictionary_index": dictionary_index,
        }

    def _chatter_ai_runtime_payload(self, attachments=False, message_text=False):
        self.ensure_one()
        urls = self._chatter_ai_extract_urls(message_text)
        current_draft = False
        if self.draft_payload:
            try:
                current_draft = self._load_draft_payload()
            except ValidationError:
                current_draft = False
        copilot_context = self._build_copilot_context(base_payload=current_draft or False)
        compact_context = self._chatter_ai_compact_copilot_context(copilot_context)
        dictionary_enhanced = self._chatter_ai_dictionary_enhanced_mode(message_text)
        dictionary_candidates = self._chatter_ai_dictionary_candidates(
            copilot_context,
            current_draft=current_draft,
            message_text=message_text,
            raw_text=self.raw_text,
        )
        compact_context["dictionary_enhanced_mode"] = dictionary_enhanced
        compact_context["dictionary_candidates"] = dictionary_candidates if (dictionary_enhanced or dictionary_candidates) else []
        return {
            "source_kind": self._chatter_ai_source_kind(attachments=attachments, message_text=message_text),
            "source_url": (urls[:1] or [self.source_url or False])[0],
            "raw_text": self.raw_text or False,
            "current_draft_payload": current_draft,
            "copilot_context": compact_context,
        }

    def _chatter_ai_sync_preview_image(self, attachments):
        self.ensure_one()
        image_attachment = (attachments or self.env["ir.attachment"]).filtered(
            lambda item: (item.mimetype or "").startswith("image/")
        )[:1]
        if not image_attachment:
            return False
        self.write(
            {
                "extracted_image": image_attachment.datas,
                "extracted_image_filename": image_attachment.name,
            }
        )
        return image_attachment

    def action_extract_source(self):
        run_model = self.env["chatter.ai.run"]
        for record in self:
            run_model.create_document_run(
                record,
                document_action="extract_source",
                prompt_text="提取原文，并尽量导出文档里的图片附件。",
                requesting_user=self.env.user,
            )
        return True

    def action_generate_draft(self):
        run_model = self.env["chatter.ai.run"]
        for record in self:
            run_model.create_document_run(
                record,
                document_action="parse",
                prompt_text="AI生成草稿。",
                requesting_user=self.env.user,
            )
        return True

    def _chatter_ai_apply_result(self, action, payload):
        self.ensure_one()
        action = (action or "chat").strip()
        structured = payload.get("draft_payload") or payload.get("draft") or payload.get("structured_payload")
        if action in ("parse", "extract_params", "reparse") and isinstance(structured, dict):
            normalized = self._normalize_generated_payload(structured)
            self._run_encoding_precheck(normalized)
            values = {
                "draft_payload": json.dumps(normalized, ensure_ascii=False, indent=2),
                "unmatched_payload": json.dumps(normalized.get("unmatched") or [], ensure_ascii=False, indent=2),
                "parse_version": payload.get("parse_version") or "openclaw-%s" % action,
                "import_status": "generated",
                "result_message": payload.get("summary") or payload.get("reply_text") or "OpenClaw draft generated.",
            }
            if payload.get("raw_text") and not self.raw_text:
                values["raw_text"] = payload["raw_text"]
            self.write(values)
            if hasattr(self, "_refresh_handbook_review_from_current_draft") and self.handbook_review_id:
                self._refresh_handbook_review_from_current_draft(
                    summary=payload.get("summary") or payload.get("reply_text") or False,
                    confidence=payload.get("confidence", False),
                )
        elif action == "identify_handbook":
            review_payload = self._normalize_handbook_review_payload(payload)
            review = self._upsert_handbook_review(review_payload)
            handbook_summary = self._chatter_ai_user_summary(action, payload)
            self.write(
                {
                    "handbook_review_id": review.id,
                    "parse_version": payload.get("parse_version") or "openclaw-handbook-review",
                    "import_status": "review",
                    "result_message": handbook_summary or "OpenClaw handbook structure identified.",
                }
            )
            payload = dict(payload, summary=handbook_summary, reply_text=handbook_summary)
        elif action == "summarize":
            self.write(
                {
                    "result_message": payload.get("summary") or payload.get("reply_text") or "OpenClaw summary generated.",
                }
            )
        elif action == "extract_source":
            values = {
                "parse_version": payload.get("parse_version") or "openclaw-extract",
                "import_status": "extracted",
                "result_message": payload.get("summary") or payload.get("reply_text") or "OpenClaw source extraction completed.",
            }
            if "raw_text" in payload:
                values["raw_text"] = payload.get("raw_text") or False
            self.write(values)
        else:
            raise UserError("Unsupported document action: %s" % action)
        return {
            "reply_text": payload.get("reply_text") or payload.get("summary") or "Done.",
            "summary": payload.get("summary") or payload.get("reply_text") or "Done.",
        }
