# -*- coding: utf-8 -*-

import html
import json
import mimetypes
import re

from odoo import api, fields, models
from odoo.exceptions import ValidationError

from ..tools import (
    find_suspicious_text_entries,
    format_suspicious_entries,
    infer_brand_skill_name,
    load_skill_bundle,
)


class DiecutCatalogParamCategory(models.Model):
    _name = "diecut.catalog.param.category"
    _description = "参数分类"
    _order = "sequence, name, id"

    name = fields.Char(string="分类名称", required=True)
    code = fields.Char(string="分类编码", index=True)
    parent_id = fields.Many2one("diecut.catalog.param.category", string="上级分类", index=True)
    child_ids = fields.One2many("diecut.catalog.param.category", "parent_id", string="下级分类")
    description = fields.Text(string="分类说明")
    sequence = fields.Integer(string="排序", default=10)
    active = fields.Boolean(string="启用", default=True)
    param_count = fields.Integer(string="参数数量", compute="_compute_param_count")

    _name_uniq = models.Constraint(
        "UNIQUE(name)",
        "参数分类名称必须唯一。",
    )

    @api.depends("child_ids")
    def _compute_param_count(self):
        grouped = self.env["diecut.catalog.param"].read_group(
            [("spec_category_id", "in", self.ids)],
            ["spec_category_id"],
            ["spec_category_id"],
        )
        count_map = {
            group["spec_category_id"][0]: group["spec_category_id_count"]
            for group in grouped
            if group.get("spec_category_id")
        }
        for record in self:
            record.param_count = count_map.get(record.id, 0)


class DiecutCatalogSourceDocument(models.Model):
    _name = "diecut.catalog.source.document"
    _description = "AI/TDS 来源文档"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "create_date desc, id desc"

    _DRAFT_BUCKETS = ("series", "items", "params", "category_params", "spec_values", "unmatched")
    _PLACEHOLDER_TEXTS = {"false", "none", "null", "nil", "n/a", "na"}

    name = fields.Char(string="标题", required=True, tracking=True)
    active = fields.Boolean(string="启用", default=True)
    source_type = fields.Selection(
        [
            ("pdf", "PDF"),
            ("url", "网页"),
            ("ocr", "OCR"),
            ("manual", "手工录入"),
        ],
        string="来源类型",
        required=True,
        default="pdf",
        tracking=True,
    )
    source_url = fields.Char(string="来源 URL")
    source_file = fields.Binary(string="兼容文件入口", attachment=True)
    source_filename = fields.Char(string="源文件名")
    primary_attachment_id = fields.Many2one(
        "ir.attachment",
        string="主解析附件",
        domain="[('res_model', '=', 'diecut.catalog.source.document'), ('res_id', '=', id)]",
    )
    attachment_count = fields.Integer(string="附件数", compute="_compute_attachment_info")
    primary_attachment_name = fields.Char(string="主附件名称", compute="_compute_attachment_info")
    primary_attachment_mimetype = fields.Char(string="主附件类型", compute="_compute_attachment_info")
    brand_id = fields.Many2one("diecut.brand", string="品牌", index=True)
    categ_id = fields.Many2one("product.category", string="建议分类", index=True)
    skill_profile = fields.Char(string="Skill 配置", default="generic_tds_v1+diecut_domain_v1", tracking=True)
    brand_skill_name = fields.Char(string="品牌 Skill", tracking=True)
    context_used = fields.Text(string="Copilot 上下文", readonly=True)
    raw_text = fields.Text(string="原文文本")
    parse_version = fields.Char(string="解析版本", default="draft-v1")
    import_status = fields.Selection(
        [
            ("draft", "草稿"),
            ("extracted", "已提取"),
            ("generated", "已生成"),
            ("validated", "已校验"),
            ("review", "待复核"),
            ("applied", "已入库"),
            ("rejected", "已驳回"),
        ],
        string="导入状态",
        default="draft",
        tracking=True,
    )
    extracted_image = fields.Binary(string="提取图片", attachment=True)
    extracted_image_filename = fields.Char(string="提取图片文件名")
    draft_payload = fields.Text(
        string="结构化草稿JSON",
        help="JSON 结构：series/items/params/category_params/spec_values/unmatched",
    )
    result_message = fields.Text(string="处理结果")
    unmatched_payload = fields.Text(string="未识别项")
    draft_summary = fields.Text(string="草稿摘要", compute="_compute_draft_preview")
    draft_preview_html = fields.Html(string="结构化预览", compute="_compute_draft_preview", sanitize=False)
    line_count = fields.Integer(string="关联参数值数", compute="_compute_line_count")

    _RETIRED_CHATTER_AI_COLUMNS = (
        "draft_prev_payload",
        "draft_revision_count",
        "last_revision_instruction",
        "ai_refine_in_progress",
    )
    _RETIRED_CHATTER_AI_CONFIG_KEYS = (
        "diecut.ai_mode_auto_enabled",
        "diecut.ai_mode_qa_partner_xmlid",
        "diecut.ai_mode_refine_partner_xmlid",
        "diecut.ai_qa_reply_lang",
        "diecut.ai_qa_aliases",
        "diecut.ai_refine_aliases",
    )
    _RETIRED_CHATTER_AI_XMLIDS = (
        "partner_ai_qa",
        "partner_ai_refine",
        "user_ai_qa",
        "user_ai_refine",
        "config_ai_mode_auto_enabled",
        "config_ai_mode_qa_partner_xmlid",
        "config_ai_mode_refine_partner_xmlid",
        "config_ai_qa_reply_lang",
        "config_ai_qa_aliases",
    )
    _RETIRED_CHATTER_AI_MESSAGE_PATTERNS = (
        "@AI",
        "@AI闂瓟",
        "@AI淇",
        "@Copilot",
        "@TDS鍔╂墜",
    )
    _RETIRED_LEGACY_AI_COLUMNS = (
        "vision_payload",
        "worker_run_id",
        "worker_id",
        "queued_at",
        "processing_started_at",
        "parsed_at",
        "failed_at",
        "worker_attempt_count",
        "worker_last_error_code",
        "worker_last_error_message",
        "worker_debug_payload",
    )
    _RETIRED_LEGACY_AI_XMLIDS = (
        "menu_material_catalog_ai_settings",
        "action_diecut_ai_settings_wizard",
        "view_diecut_ai_settings_wizard_form",
        "access_diecut_ai_settings_wizard",
    )

    @api.model
    def _table_exists(self, table_name):
        self.env.cr.execute(
            """
            SELECT 1
              FROM information_schema.tables
             WHERE table_name = %s
            """,
            (table_name,),
        )
        return bool(self.env.cr.fetchone())

    @api.model
    def _column_exists(self, table_name, column_name):
        self.env.cr.execute(
            """
            SELECT 1
              FROM information_schema.columns
             WHERE table_name = %s
               AND column_name = %s
            """,
            (table_name, column_name),
        )
        return bool(self.env.cr.fetchone())

    @api.model
    def _cleanup_retired_chatter_ai_artifacts(self):
        cr = self.env.cr

        cr.execute(
            """
            DELETE FROM ir_config_parameter
             WHERE key = ANY(%s)
            """,
            (list(self._RETIRED_CHATTER_AI_CONFIG_KEYS),),
        )
        cr.execute(
            """
            DELETE FROM ir_model_fields
             WHERE model = %s
               AND name = ANY(%s)
            """,
            (self._name, list(self._RETIRED_CHATTER_AI_COLUMNS)),
        )

        partner_ids = []
        user_ids = []
        cr.execute(
            """
            SELECT model, res_id
              FROM ir_model_data
             WHERE module = %s
               AND name = ANY(%s)
            """,
            ("diecut", list(self._RETIRED_CHATTER_AI_XMLIDS)),
        )
        for model_name, res_id in cr.fetchall():
            if model_name == "res.partner":
                partner_ids.append(res_id)
            elif model_name == "res.users":
                user_ids.append(res_id)

        message_domain = [
            "|",
            ("author_id", "in", partner_ids or [0]),
            "&",
            ("model", "in", ["diecut.catalog.source.document", "discuss.channel"]),
            "|",
            "|",
            "|",
            "|",
            ("body", "ilike", self._RETIRED_CHATTER_AI_MESSAGE_PATTERNS[0]),
            ("body", "ilike", self._RETIRED_CHATTER_AI_MESSAGE_PATTERNS[1]),
            ("body", "ilike", self._RETIRED_CHATTER_AI_MESSAGE_PATTERNS[2]),
            ("body", "ilike", self._RETIRED_CHATTER_AI_MESSAGE_PATTERNS[3]),
            ("body", "ilike", self._RETIRED_CHATTER_AI_MESSAGE_PATTERNS[4]),
        ]
        retired_messages = self.env["mail.message"].sudo().with_context(tracking_disable=True).search(message_domain)
        if retired_messages:
            retired_messages.unlink()

        if partner_ids and self._table_exists("discuss_channel_member"):
            cr.execute(
                """
                SELECT DISTINCT channel_id
                  FROM discuss_channel_member
                 WHERE partner_id = ANY(%s)
                """,
                (partner_ids,),
            )
            channel_ids = [row[0] for row in cr.fetchall() if row and row[0]]
            if channel_ids:
                cr.execute(
                    """
                    DELETE FROM discuss_channel_member
                     WHERE channel_id = ANY(%s)
                    """,
                    (channel_ids,),
                )
                if self._table_exists("discuss_channel"):
                    cr.execute(
                        """
                        DELETE FROM discuss_channel
                         WHERE id = ANY(%s)
                        """,
                        (channel_ids,),
                    )

        if user_ids:
            cr.execute(
                """
                UPDATE res_users
                   SET active = FALSE
                 WHERE id = ANY(%s)
                """,
                (user_ids,),
            )
        if partner_ids:
            cr.execute(
                """
                UPDATE res_partner
                   SET active = FALSE
                 WHERE id = ANY(%s)
                """,
                (partner_ids,),
            )

        cr.execute(
            """
            DELETE FROM ir_model_data
             WHERE module = %s
               AND name = ANY(%s)
            """,
            ("diecut", list(self._RETIRED_CHATTER_AI_XMLIDS)),
        )

    @api.model
    def _cleanup_retired_legacy_ai_artifacts(self):
        cr = self.env.cr
        cr.execute(
            """
            DELETE FROM ir_config_parameter
             WHERE key = %s
                OR key LIKE %s
            """,
            ("diecut.tds_copilot_api_token", "diecut.ai_tds_%"),
        )
        if self._table_exists("ir_model_data"):
            self.env.cr.execute(
                """
                SELECT model, res_id
                  FROM ir_model_data
                 WHERE module = %s
                   AND name = ANY(%s)
                """,
                ("diecut", list(self._RETIRED_LEGACY_AI_XMLIDS)),
            )
            for model_name, res_id in cr.fetchall():
                if not model_name or not res_id:
                    continue
                self.env[model_name].sudo().browse(res_id).exists().unlink()
            cr.execute(
                """
                DELETE FROM ir_model_data
                 WHERE module = %s
                   AND name = ANY(%s)
                """,
                ("diecut", list(self._RETIRED_LEGACY_AI_XMLIDS)),
            )

    def init(self):
        super().init()
        self._cleanup_retired_chatter_ai_artifacts()
        self._cleanup_retired_legacy_ai_artifacts()
        for column_name in self._RETIRED_CHATTER_AI_COLUMNS:
            if self._column_exists(self._table, column_name):
                self.env.cr.execute(
                    f'ALTER TABLE {self._table} DROP COLUMN IF EXISTS "{column_name}"'
                )
        for column_name in self._RETIRED_LEGACY_AI_COLUMNS:
            if self._column_exists(self._table, column_name):
                self.env.cr.execute(
                    f'ALTER TABLE {self._table} DROP COLUMN IF EXISTS "{column_name}"'
                )

    @api.depends("message_ids", "primary_attachment_id")
    def _compute_attachment_info(self):
        attachment_model = self.env["ir.attachment"].sudo()
        for record in self:
            attachments = attachment_model.search(
                [
                    ("res_model", "=", self._name),
                    ("res_id", "=", record.id),
                    ("res_field", "=", False),
                    ("type", "=", "binary"),
                ],
                order="id desc",
            )
            primary = record.primary_attachment_id if record.primary_attachment_id in attachments else attachments[:1]
            record.attachment_count = len(attachments)
            record.primary_attachment_name = primary.name if primary else False
            record.primary_attachment_mimetype = primary.mimetype if primary else False

    def _resolve_brand_skill_name(self):
        self.ensure_one()
        return (
            (self.brand_skill_name or "").strip()
            or infer_brand_skill_name(
                brand_name=self.brand_id.name if self.brand_id else "",
                filename=self.primary_attachment_name or self.source_filename or "",
                title=" ".join(filter(None, [self.name or "", (self.raw_text or "")[:500]])),
            )
            or False
        )

    @api.model
    def _main_field_whitelist(self):
        return [
            "manufacturer_id",
            "thickness",
            "thickness_std",
            "adhesive_thickness",
            "color_id",
            "adhesive_type_id",
            "base_material_id",
            "ref_price",
            "is_rohs",
            "is_reach",
            "is_halogen_free",
            "fire_rating",
        ]

    def _build_category_param_snapshot(self, limit=60):
        self.ensure_one()
        if not self.categ_id:
            return []
        rows = self.env["diecut.catalog.spec.def"].sudo().search(
            [("categ_id", "=", self.categ_id.id), ("active", "=", True)],
            order="sequence, id",
            limit=limit,
        )
        return [
            {
                "categ_name": row.categ_id.name,
                "param_key": row.param_id.param_key,
                "param_name": row.param_id.name,
                "required": row.required,
                "show_in_form": row.show_in_form,
                "allow_import": row.allow_import,
                "unit_override": row.unit_override or False,
            }
            for row in rows
            if row.param_id
        ]

    def _build_copilot_context(self, base_payload=False):
        self.ensure_one()
        brand_skill = self._resolve_brand_skill_name()
        skill_profile = (self.skill_profile or "generic_tds_v1+diecut_domain_v1").strip()
        skill_bundle = load_skill_bundle(skill_profile, brand_skill)
        heuristic_snapshot = False
        if base_payload:
            enrichment_builder = getattr(type(self), "_build_ai_enrichment_context", None)
            if enrichment_builder:
                try:
                    heuristic_snapshot = enrichment_builder(self, base_payload)
                except Exception:
                    heuristic_snapshot = False
        return {
            "skill_profile": skill_profile,
            "brand_skill": brand_skill or False,
            "skills_loaded": skill_bundle.get("skills_loaded") or [],
            "skill_bundle": skill_bundle,
            "source_context": {
                "title": self.name,
                "source_type": self.source_type,
                "brand_name": self.brand_id.name if self.brand_id else False,
                "category_name": self.categ_id.name if self.categ_id else False,
                "primary_attachment_name": self.primary_attachment_name or self.source_filename or False,
            },
            "main_field_whitelist": self._main_field_whitelist(),
            "category_param_snapshot": self._build_category_param_snapshot(),
            "param_dictionary_snapshot": self._build_param_context() if hasattr(self, "_build_param_context") else [],
            "heuristic_snapshot": heuristic_snapshot,
        }

    @api.depends("message_ids")
    def _compute_line_count(self):
        grouped = self.env["diecut.catalog.item.spec.line"].read_group(
            [("source_document_id", "in", self.ids)],
            ["source_document_id"],
            ["source_document_id"],
        )
        count_map = {
            group["source_document_id"][0]: group["source_document_id_count"]
            for group in grouped
            if group.get("source_document_id")
        }
        for record in self:
            record.line_count = count_map.get(record.id, 0)

    @api.depends("draft_payload", "unmatched_payload")
    def _compute_draft_preview(self):
        for record in self:
            try:
                payload = json.loads(record.draft_payload or "{}")
            except Exception:
                payload = {}
            if not isinstance(payload, dict):
                payload = {}
            counts = {bucket: len(payload.get(bucket) or []) for bucket in self._DRAFT_BUCKETS}
            record.draft_summary = (
                f"系列 {counts['series']} 条，型号 {counts['items']} 条，参数 {counts['params']} 条，"
                f"分类参数 {counts['category_params']} 条，参数值 {counts['spec_values']} 条，未识别 {counts['unmatched']} 条"
            )
            record.draft_preview_html = record._build_draft_preview_html(payload)

    def _build_draft_preview_html(self, payload):
        self.ensure_one()
        sections = [
            ("series", "系列"),
            ("items", "型号"),
            ("params", "参数字典"),
            ("category_params", "分类参数"),
            ("spec_values", "参数值"),
            ("unmatched", "未识别项"),
        ]
        cards = []
        for bucket, label in sections:
            cards.append(
                "<div style='padding:8px 12px;border:1px solid #ddd;border-radius:8px;min-width:120px;'>"
                f"<div style='font-size:12px;color:#666;'>{label}</div>"
                f"<div style='font-size:20px;font-weight:600;'>{len(payload.get(bucket) or [])}</div>"
                "</div>"
            )
        html_parts = [
            "<div style='display:flex;gap:12px;flex-wrap:wrap;margin-bottom:16px;'>%s</div>" % "".join(cards)
        ]
        for bucket, label in sections:
            rows = payload.get(bucket) or []
            html_parts.append(f"<h3 style='margin:16px 0 8px 0;'>{label}</h3>")
            if not rows:
                html_parts.append("<div style='color:#999;margin-bottom:12px;'>鏃?/div>")
                continue
            if bucket == "unmatched":
                html_parts.append("<ul style='margin:0 0 16px 18px;padding:0;'>")
                for row in rows[:20]:
                    excerpt = html.escape(str((row or {}).get("excerpt") or row or ""))
                    html_parts.append(f"<li style='margin-bottom:6px;white-space:pre-wrap;'>{excerpt}</li>")
                html_parts.append("</ul>")
                if len(rows) > 20:
                    html_parts.append(f"<div style='color:#999;'>鍏朵綑 {len(rows) - 20} 鏉¤鏌ョ湅鍘熷 JSON銆?/div>")
                continue

            columns = []
            for row in rows[:20]:
                if isinstance(row, dict):
                    for key in row.keys():
                        if key not in columns:
                            columns.append(key)
            columns = columns[:6]
            header_cells = "".join(
                f"<th style='text-align:left;border-bottom:1px solid #ddd;padding:6px 8px;background:#f7f7f7;'>{html.escape(str(col))}</th>"
                for col in columns
            )
            html_parts.append(
                f"<table style='width:100%;border-collapse:collapse;margin-bottom:16px;'><thead><tr>{header_cells}</tr></thead><tbody>"
            )
            for row in rows[:20]:
                html_parts.append("<tr>")
                for col in columns:
                    value = ""
                    if isinstance(row, dict):
                        value = row.get(col)
                    if value in (False, None):
                        rendered = ""
                    else:
                        text_value = str(value).strip()
                        rendered = "" if text_value.lower() in {"false", "none", "null"} else html.escape(text_value)
                    html_parts.append(
                        f"<td style='vertical-align:top;border-bottom:1px solid #eee;padding:6px 8px;white-space:pre-wrap;'>{rendered}</td>"
                    )
                html_parts.append("</tr>")
            html_parts.append("</tbody></table>")
            if len(rows) > 20:
                html_parts.append(f"<div style='color:#999;margin-bottom:12px;'>鍏朵綑 {len(rows) - 20} 鏉¤鏌ョ湅鍘熷 JSON銆?/div>")
        return "".join(html_parts)

    @api.depends("draft_payload", "unmatched_payload")
    def _compute_draft_preview(self):
        for record in self:
            try:
                payload = json.loads(record.draft_payload or "{}")
            except Exception:
                payload = {}
            if not isinstance(payload, dict):
                payload = {}
            counts = {bucket: len(payload.get(bucket) or []) for bucket in self._DRAFT_BUCKETS}
            record.draft_summary = (
                f"系列 {counts['series']} 条，型号 {counts['items']} 条，参数 {counts['params']} 条，"
                f"分类参数 {counts['category_params']} 条，参数值 {counts['spec_values']} 条，未识别 {counts['unmatched']} 条"
            )
            record.draft_preview_html = record._build_draft_preview_html(payload)

    @api.model
    def _strip_html_markup(self, value):
        text = self._clean_text(value or "")
        if not text:
            return ""
        text = re.sub(r"<br\s*/?>", "\n", text, flags=re.I)
        text = re.sub(r"</p\s*>", "\n", text, flags=re.I)
        text = re.sub(r"<li\s*>", "• ", text, flags=re.I)
        text = re.sub(r"<[^>]+>", " ", text)
        text = re.sub(r"\s+", " ", text)
        return text.strip()

    @api.model
    def _preview_columns_for_bucket(self, bucket):
        mapping = {
            "series": [
                ("brand_name", "品牌"),
                ("series_name", "系列"),
                ("name", "系列标题"),
                ("series_description", "产品描述"),
                ("series_features", "产品特性"),
                ("series_applications", "主要应用"),
            ],
            "items": [
                ("brand_name", "品牌"),
                ("code", "型号"),
                ("name", "名称"),
                ("catalog_status", "目录状态"),
                ("thickness", "厚度"),
                ("color_name", "颜色"),
                ("adhesive_type_name", "胶系"),
                ("base_material_name", "基材"),
            ],
            "params": [
                ("param_key", "参数键"),
                ("name", "参数名称"),
                ("spec_category_name", "参数分类"),
                ("value_type", "值类型"),
                ("preferred_unit", "单位"),
                ("dictionary_status", "参数状态"),
                ("route_label", "写入位置"),
                ("method_summary", "方法摘要"),
            ],
            "category_params": [
                ("categ_name", "材料分类"),
                ("param_key", "参数键"),
                ("name", "参数名称"),
                ("required", "必填"),
                ("show_in_form", "表单显示"),
                ("allow_import", "允许导入"),
                ("unit_override", "分类单位"),
            ],
            "spec_values": [
                ("item_code", "型号"),
                ("param_name", "参数"),
                ("display_value", "值"),
                ("unit", "单位"),
                ("test_method", "测试方法"),
                ("test_condition", "测试条件"),
                ("remark", "备注"),
            ],
            "unmatched": [
                ("excerpt", "原文片段"),
                ("reason", "原因"),
                ("candidate_param_key", "候选参数键"),
            ],
        }
        return mapping.get(bucket, [])

    @api.model
    def _preview_value(self, bucket, row, column):
        if not isinstance(row, dict):
            return row or ""
        boolean_columns = {"required", "show_in_form", "allow_import", "is_main_field", "active", "candidate_new"}
        if bucket == "series" and column == "series_description":
            return self._series_description_text(row)
        if bucket == "series" and column == "series_features":
            return self._series_features_text(row)
        if bucket == "series" and column == "series_applications":
            return self._series_applications_text(row)
        if bucket == "params" and column == "dictionary_status":
            return self._preview_param_dictionary_status(row)
        if bucket == "params" and column == "route_label":
            if row.get("is_main_field"):
                field_name = row.get("main_field_name") or ""
                return f"涓昏〃瀛楁 / {field_name}" if field_name else "涓昏〃瀛楁"
            return "鍙傛暟鍊艰〃"
        if bucket == "params" and column == "method_summary":
            return self._strip_html_markup(row.get("method_html"))[:120]
        if bucket == "params" and column == "spec_category_name":
            return row.get("spec_category_name") or row.get("spec_category") or ""
        if bucket == "items" and column == "color_name":
            return row.get("color_name") or row.get("color") or row.get("color_id") or ""
        if bucket == "items" and column == "adhesive_type_name":
            return row.get("adhesive_type_name") or row.get("adhesive_type") or row.get("adhesive_type_id") or ""
        if bucket == "items" and column == "base_material_name":
            return row.get("base_material_name") or row.get("base_material") or row.get("base_material_id") or ""
        if bucket == "spec_values" and column == "item_code":
            return row.get("item_code") or row.get("code") or row.get("item_name") or ""
        if bucket == "spec_values" and column == "param_name":
            return row.get("param_name") or row.get("name") or row.get("param_key") or ""
        if bucket == "spec_values" and column == "display_value":
            direct = row.get("display_value")
            if direct not in (False, None, ""):
                return direct
            for key in ("value", "value_display", "value_raw", "value_text", "raw_value_text", "value_char", "value_float", "value_selection"):
                candidate = row.get(key)
                if candidate not in (False, None, ""):
                    return candidate
            if row.get("value_boolean") is True:
                return "?"
            if row.get("value_boolean") is False and "value_boolean" in row:
                return "?"
            return ""
        if column == "excerpt":
            return row.get("excerpt") or row.get("text") or row.get("raw") or ""
        value = row.get(column)
        if isinstance(value, bool):
            if column in boolean_columns:
                return "?" if value else "?"
            return ""
        if isinstance(value, (list, tuple)):
            return ", ".join(str(item) for item in value if item not in (False, None, ""))
        if isinstance(value, dict):
            return json.dumps(value, ensure_ascii=False)
        return value or ""

    def _render_preview_table(self, bucket, rows):
        columns = self._preview_columns_for_bucket(bucket)
        if not columns:
            return ""
        header_cells = "".join(
            f"<th style='text-align:left;border-bottom:1px solid #ddd;padding:6px 8px;background:#f7f7f7;'>{html.escape(label)}</th>"
            for _column, label in columns
        )
        html_parts = [
            "<table style='width:100%;border-collapse:collapse;margin-bottom:16px;'>",
            f"<thead><tr>{header_cells}</tr></thead><tbody>",
        ]
        for row in rows[:20]:
            html_parts.append("<tr>")
            for column, _label in columns:
                value = self._preview_value(bucket, row, column)
                rendered = html.escape("" if value in (False, None) else str(value))
                html_parts.append(
                    f"<td style='vertical-align:top;border-bottom:1px solid #eee;padding:6px 8px;white-space:pre-wrap;'>{rendered}</td>"
                )
            html_parts.append("</tr>")
        html_parts.append("</tbody></table>")
        if len(rows) > 20:
            html_parts.append(f"<div style='color:#999;margin-bottom:12px;'>另有 {len(rows) - 20} 条记录未展示，请查看原始 JSON。</div>")
        return "".join(html_parts)

    def _build_draft_preview_html(self, payload):
        self.ensure_one()
        sections = [
            ("series", "系列"),
            ("items", "型号"),
            ("params", "参数字典"),
            ("category_params", "分类参数"),
            ("spec_values", "参数值"),
            ("unmatched", "未识别项"),
        ]
        cards = []
        for bucket, label in sections:
            cards.append(
                "<div style='padding:8px 12px;border:1px solid #ddd;border-radius:8px;min-width:120px;'>"
                f"<div style='font-size:12px;color:#666;'>{label}</div>"
                f"<div style='font-size:20px;font-weight:600;'>{len(payload.get(bucket) or [])}</div>"
                "</div>"
            )
        html_parts = [
            "<div style='display:flex;gap:12px;flex-wrap:wrap;margin-bottom:16px;'>%s</div>" % "".join(cards),
            (
                "<div style='margin-bottom:12px;padding:10px 12px;background:#f8fbff;border:1px solid #d8e8ff;"
                "border-radius:8px;color:#36506b;'>"
                "这里显示的是人工校验视图，已按业务结构拆成可读表格。默认只显示前 20 条记录，"
                "如需完整结构，请查看“原始 JSON”。"
                "</div>"
            ),
        ]
        for bucket, label in sections:
            rows = payload.get(bucket) or []
            html_parts.append(f"<h3 style='margin:16px 0 8px 0;'>{label}</h3>")
            if not rows:
                html_parts.append("<div style='color:#999;margin-bottom:12px;'>暂无</div>")
                continue
            html_parts.append(self._render_preview_table(bucket, rows))
        return "".join(html_parts)

    def _get_chatter_attachments(self):
        self.ensure_one()
        return self.env["ir.attachment"].sudo().search(
            [
                ("res_model", "=", self._name),
                ("res_id", "=", self.id),
                ("res_field", "=", False),
                ("type", "=", "binary"),
            ],
            order="id desc",
        )

    @api.model
    def _is_parseable_attachment(self, attachment):
        mimetype = attachment.mimetype or mimetypes.guess_type(attachment.name or "")[0] or ""
        return (
            mimetype.startswith("image/")
            or mimetype == "application/pdf"
            or (attachment.name or "").lower().endswith(".pdf")
        )

    def _get_effective_primary_attachment(self):
        self.ensure_one()
        attachments = self._get_chatter_attachments()
        if self.primary_attachment_id and self.primary_attachment_id in attachments and self._is_parseable_attachment(self.primary_attachment_id):
            return self.primary_attachment_id
        return next((attachment for attachment in attachments if self._is_parseable_attachment(attachment)), False)

    @staticmethod
    def _clean_text(value):
        if not value:
            return False
        text = str(value).replace("\r\n", "\n").replace("\r", "\n")
        text = text.replace("\x00", "")
        text = re.sub(r"[ \t]+", " ", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        normalized = text.strip()
        if not normalized:
            return False
        if normalized.casefold() in DiecutCatalogSourceDocument._PLACEHOLDER_TEXTS:
            return False
        return normalized

    def _build_param_context(self):
        params = self.env["diecut.catalog.param"].sudo().search([("active", "=", True)], order="sequence, id")
        rows = []
        for param in params:
            rows.append(
                {
                    "param_key": param.param_key,
                    "name": param.name,
                    "canonical_name_zh": param.canonical_name_zh,
                    "canonical_name_en": param.canonical_name_en,
                    "aliases_text": param.aliases_text,
                    "method_html": param.method_html,
                    "value_type": param.value_type,
                    "preferred_unit": param.preferred_unit or param.unit,
                    "is_main_field": param.is_main_field,
                    "main_field_name": param.main_field_name,
                    "spec_category": param.spec_category_id.name if param.spec_category_id else False,
                }
            )
        return rows

    @api.model
    def _normalize_generated_payload(self, payload):
        data = payload if isinstance(payload, dict) else {}
        normalized = {}
        for bucket in self._DRAFT_BUCKETS:
            value = data.get(bucket) or []
            normalized[bucket] = value if isinstance(value, list) else []
        return normalized

    def _load_draft_payload(self):
        self.ensure_one()
        payload = self.draft_payload or "{}"
        try:
            data = json.loads(payload)
        except Exception as exc:
            raise ValidationError("结构化草稿不是合法的 JSON。") from exc
        if not isinstance(data, dict):
            raise ValidationError("结构化草稿必须是 JSON 对象。")
        return data

    def _run_encoding_precheck(self, payload):
        self.ensure_one()
        findings = []
        if self.raw_text:
            findings.extend(find_suspicious_text_entries(self.raw_text, prefix="raw_text"))
        findings.extend(find_suspicious_text_entries(payload, prefix="draft_payload"))
        if findings:
            detail = format_suspicious_entries(findings)
            self.write(
                {
                    "import_status": "draft",
                    "result_message": "检测到疑似乱码或编码异常内容，已阻止继续处理。\n" + detail,
                }
            )
            raise ValidationError("检测到疑似乱码或编码异常内容，请先修正后再继续。\n" + detail)

    def action_validate_draft(self):
        for record in self:
            payload = record._load_draft_payload()
            record._run_encoding_precheck(payload)
            bucket_sizes = {
                "series": len(payload.get("series") or []),
                "items": len(payload.get("items") or []),
                "params": len(payload.get("params") or []),
                "category_params": len(payload.get("category_params") or []),
                "spec_values": len(payload.get("spec_values") or []),
                "unmatched": len(payload.get("unmatched") or []),
            }
            record.write(
                {
                    "import_status": "review" if bucket_sizes["unmatched"] else "validated",
                    "result_message": (
                        "草稿校验通过。\n"
                        f"系列:{bucket_sizes['series']} 型号:{bucket_sizes['items']} 参数:{bucket_sizes['params']} "
                        f"分类参数:{bucket_sizes['category_params']} 参数值:{bucket_sizes['spec_values']} "
                        f"未识别:{bucket_sizes['unmatched']}"
                    ),
                    "unmatched_payload": json.dumps(payload.get("unmatched") or [], ensure_ascii=False, indent=2),
                    "context_used": json.dumps(record._build_copilot_context(payload), ensure_ascii=False, indent=2),
                }
            )
        return True

    def _run_document_action_via_chatter_ai(self, document_action, prompt_text):
        run_model = self.env.get("chatter.ai.run")
        if not run_model:
            raise ValidationError("chatter_ai_assistant is required for document AI actions.")
        for record in self:
            run_model.create_document_run(
                record,
                document_action=document_action,
                prompt_text=prompt_text,
                requesting_user=self.env.user,
            )
        return True

    def action_extract_source(self):
        return self._run_document_action_via_chatter_ai(
            "extract_source",
            "提取原文，并尽量导出文档里的图片附件。",
        )

    def action_generate_draft(self):
        return self._run_document_action_via_chatter_ai(
            "parse",
            "AI生成草稿。",
        )

    def action_apply_draft(self):
        for record in self:
            payload = record._load_draft_payload()
            record._run_encoding_precheck(payload)
            apply_stats = record._apply_payload(payload)
            skipped = int((apply_stats or {}).get("spec_values_skipped") or 0)
            message = "AI/TDS 草稿已入库。"
            if skipped:
                message = f"{message} 跳过 {skipped} 条无法写入参数值的记录。"
            record.write(
                {
                    "import_status": "applied",
                    "result_message": message,
                    "draft_payload": json.dumps(payload, ensure_ascii=False, indent=2),
                    "unmatched_payload": json.dumps(payload.get("unmatched") or [], ensure_ascii=False, indent=2),
                    "context_used": json.dumps(record._build_copilot_context(payload), ensure_ascii=False, indent=2),
                }
            )
        return True

    def _resolve_brand(self, raw_value):
        if not raw_value:
            return False
        return self.env["diecut.brand"].search([("name", "=", str(raw_value).strip())], limit=1) or False

    def _resolve_manufacturer(self, raw_value):
        if not raw_value:
            return False
        raw_text = str(raw_value).strip()
        if not raw_text:
            return False
        partner_model = self.env["res.partner"].sudo().with_context(active_test=False)
        exact = partner_model.search(
            [
                ("is_company", "=", True),
                "|",
                ("short_name", "=", raw_text),
                ("name", "=", raw_text),
            ],
            limit=1,
        )
        if exact:
            return exact
        return partner_model.search(
            [
                ("is_company", "=", True),
                "|",
                ("short_name", "ilike", raw_text),
                ("name", "ilike", raw_text),
            ],
            limit=1,
        ) or False

    def _resolve_category(self, raw_value):
        if not raw_value:
            return False
        return self.env["product.category"].search([("name", "=", str(raw_value).strip())], limit=1) or False

                        "草稿校验通过。\n"
                        f"系列:{bucket_sizes['series']} 型号:{bucket_sizes['items']} 参数:{bucket_sizes['params']} "
                        f"分类参数:{bucket_sizes['category_params']} 参数值:{bucket_sizes['spec_values']} "
                        f"未识别:{bucket_sizes['unmatched']}"
                if isinstance(candidate, str):
                    text = candidate.strip()
                    if text and text.lower() not in {"false", "none", "null"}:
                        return text
                else:
                    return candidate
        return False

    @api.model
    def _preview_text_from_rich_value(self, value):
        if value in (False, None, ""):
            return ""
        if isinstance(value, (list, tuple)):
            return "\n".join(str(item).strip() for item in value if str(item).strip())
        if isinstance(value, dict):
            return json.dumps(value, ensure_ascii=False)
        text = str(value).strip()
        if not text or text.lower() in {"false", "none", "null"}:
            return ""
        if "<" in text and ">" in text:
            return self._strip_html_markup(text)
        return text

    @api.model
    def _preview_param_dictionary_status(self, row):
        if not isinstance(row, dict):
            return ""
        if row.get("candidate_new") is True:
            return "建议新建"
        param_key = (row.get("param_key") or "").strip().lower()
        if not param_key:
            return ""
        param = self.env["diecut.catalog.param"].sudo().search([("param_key", "=", param_key)], limit=1)
        return "复用现有" if param else "待确认"

    @api.model
    def _series_features_text(self, row):
        return self._preview_text_from_rich_value(
            self._pick_first_non_empty(row.get("product_features"), row.get("features"))
        )

    @api.model
    def _series_applications_text(self, row):
        return self._preview_text_from_rich_value(
            self._pick_first_non_empty(row.get("main_applications"), row.get("applications"))
        )

    @api.model
    def _series_description_text(self, row):
        return self._preview_text_from_rich_value(
            self._pick_first_non_empty(row.get("product_description"), row.get("description"))
        )

    @api.model
    def _normalize_series_text_field(self, value):
        text = self._preview_text_from_rich_value(value)
        return text or False

    @api.model
    def _normalize_series_applications_field(self, value):
        if value in (False, None, ""):
            return False
        if isinstance(value, str):
            text = value.strip()
            if not text or text.lower() in {"false", "none", "null"}:
                return False
            if "<" in text and ">" in text:
                return text
            lines = [line.strip("•").strip() for line in re.split(r"[\r\n]+", text) if line.strip()]
            return self._html_bullets(lines) if len(lines) > 1 else text
        if isinstance(value, (list, tuple)):
            lines = [str(item).strip() for item in value if str(item).strip()]
            return self._html_bullets(lines)
        return str(value)

    @api.model
    def _safe_float_or_false(self, value):
        if value in (False, None, ""):
            return False
        try:
            return float(value)
        except Exception:
            text = str(value).replace(",", "")
            match = re.search(r"-?\d+(?:\.\d+)?", text)
            if not match:
                return False
            try:
                return float(match.group(0))
            except Exception:
                return False

    @api.model
    def _coerce_spec_raw_value(self, param, row):
        value_type = (param.value_type or "char").strip()
        raw_value = self._pick_first_non_empty(
            row.get("value"),
            row.get("value_display"),
            row.get("value_raw"),
            row.get("value_text"),
            row.get("raw_value_text"),
            row.get("display_value"),
            row.get("value_char"),
            row.get("value_float"),
            row.get("value_selection"),
            row.get("value_boolean"),
        )
        if raw_value is False:
            return False, False, "缺少值"

        if value_type == "float":
            number = self._safe_float_or_false(raw_value)
            if number is False:
                return False, False, "浮点值无法解析"
            return True, number, False

        if value_type == "boolean":
            if isinstance(raw_value, bool):
                return True, raw_value, False
            normalized = str(raw_value).strip().lower()
            if normalized in ("1", "true", "yes", "y", "是", "对", "真"):
                return True, True, False
            if normalized in ("0", "false", "no", "n", "否", "错", "假"):
                return True, False, False
            return False, False, "布尔值无法解析"

        if value_type == "selection":
            text = str(raw_value).strip()
            if not text:
                return False, False, "选项值为空"
            options = param.get_selection_options_list()
            if options:
                if text in options:
                    return True, text, False
                option_map = {str(opt).strip().lower(): opt for opt in options}
                mapped = option_map.get(text.lower())
                if mapped:
                    return True, mapped, False
                return False, False, "选项值不在允许范围内"
            return True, text, False

        return True, str(raw_value).strip(), False

    def _apply_payload(self, payload):
        self.ensure_one()
        param_model = self.env["diecut.catalog.param"].sudo()
        category_param_model = self.env["diecut.catalog.spec.def"].sudo()
        series_model = self.env["diecut.catalog.series"].sudo()
        category_model = self.env["diecut.catalog.param.category"].sudo()
        item_model = self.env["diecut.catalog.item"].sudo().with_context(
            skip_spec_autofill=True,
            allow_spec_categ_change=True,
        )
        apply_stats = {
            "spec_values_total": 0,
            "spec_values_applied": 0,
            "spec_values_skipped": 0,
        }
        unmatched = payload.setdefault("unmatched", [])
        if not isinstance(unmatched, list):
            unmatched = []
            payload["unmatched"] = unmatched

        param_map = {}
        for row in payload.get("params") or []:
            param_key = (row.get("param_key") or "").strip().lower()
            if not param_key:
                continue
            normalize_optional = param_model._normalize_optional_text
            method_html = row.get("method_html") or False
            description = normalize_optional(row.get("description"))
            if not description and method_html:
                description = normalize_optional(self._strip_html_markup(method_html)[:300])
            vals = {
                "name": row.get("name") or param_key,
                "param_key": param_key,
                "value_type": row.get("value_type") or "char",
                "description": description,
                "method_html": method_html,
                "unit": normalize_optional(row.get("unit")),
                "preferred_unit": normalize_optional(row.get("preferred_unit")) or normalize_optional(row.get("unit")) or False,
                "common_units": normalize_optional(row.get("common_units")),
                "canonical_name_zh": normalize_optional(row.get("canonical_name_zh")) or normalize_optional(row.get("name")) or False,
                "canonical_name_en": normalize_optional(row.get("canonical_name_en")),
                "aliases_text": normalize_optional(row.get("aliases_text")),
                "parse_hint": normalize_optional(row.get("parse_hint")),
                "is_main_field": bool(row.get("is_main_field")),
                "main_field_name": row.get("main_field_name") or False,
            }
            if row.get("spec_category_name"):
                spec_category = category_model.search([("name", "=", str(row["spec_category_name"]).strip())], limit=1)
                if spec_category:
                    vals["spec_category_id"] = spec_category.id
            param = param_model.search([("param_key", "=", param_key)], limit=1)
            if param:
                param.write(vals)
            else:
                param = param_model.create(vals)
            param_map[param_key] = param

        series_map = {}
        for row in payload.get("series") or []:
            brand = self._resolve_brand(row.get("brand_name")) or self.brand_id
            series_name = (row.get("name") or row.get("series_name") or "").strip()
            if not (brand and series_name):
                continue
            series = series_model.search([("brand_id", "=", brand.id), ("name", "=", series_name)], limit=1)
            vals = {
                "brand_id": brand.id,
                "name": series_name,
                "product_features": self._normalize_series_text_field(
                    self._pick_first_non_empty(row.get("product_features"), row.get("features"))
                ),
                "product_description": self._normalize_series_text_field(
                    self._pick_first_non_empty(row.get("product_description"), row.get("description"))
                ),
                "main_applications": self._normalize_series_applications_field(
                    self._pick_first_non_empty(row.get("main_applications"), row.get("applications"))
                ),
            }
            if series:
                series.write(vals)
            else:
                series = series_model.create(vals)
            series_map[(brand.id, series_name)] = series

        for row in payload.get("category_params") or []:
            categ = self._resolve_category(row.get("category_name")) or self.categ_id
            param_key = (row.get("param_key") or "").strip().lower()
            param = param_map.get(param_key) or param_model.search([("param_key", "=", param_key)], limit=1)
            if not (categ and param):
                continue
            vals = {
                "categ_id": categ.id,
                "param_id": param.id,
                "name": param.name,
                "param_key": param.param_key,
                "value_type": param.value_type,
                "unit": param.unit,
                "selection_options": param.selection_options,
                "unit_override": row.get("unit_override") or False,
                "sequence": int(row.get("sequence") or 10),
                "required": bool(row.get("required")),
                "active": row.get("active", True),
                "show_in_form": row.get("show_in_form", True),
                "allow_import": row.get("allow_import", True),
            }
            config = category_param_model.search([("categ_id", "=", categ.id), ("param_id", "=", param.id)], limit=1)
            if config:
                config.write(vals)
            else:
                category_param_model.create(vals)

        item_map = {}
        for row in payload.get("items") or []:
            brand = self._resolve_brand(row.get("brand_name")) or self.brand_id
            code = (row.get("code") or "").strip()
            if not (brand and code):
                continue
            series_name = (row.get("series_name") or "").strip()
            series = series_map.get((brand.id, series_name)) if series_name else False
            if not series and series_name:
                series = series_model.search([("brand_id", "=", brand.id), ("name", "=", series_name)], limit=1)
            categ = self._resolve_category(row.get("category_name")) or self.categ_id
            manufacturer = self._resolve_manufacturer(
                row.get("manufacturer_name")
                or row.get("manufacturer")
                or row.get("maker_name")
            )
            vals = {
                "brand_id": brand.id,
                "manufacturer_id": manufacturer.id if manufacturer else False,
                "code": code,
                "name": row.get("name") or code,
                "categ_id": categ.id if categ else False,
                "series_id": series.id if series else False,
                "catalog_status": row.get("catalog_status") or "draft",
            }
            item = item_model.search([("brand_id", "=", brand.id), ("code", "=", code)], limit=1)
            if item:
                item.write(vals)
            else:
                item = item_model.create(vals)
            if self.extracted_image and not item.catalog_structure_image:
                item.write({"catalog_structure_image": self.extracted_image})
            item_map[(brand.id, code)] = item

        for row in payload.get("spec_values") or []:
            apply_stats["spec_values_total"] += 1
            brand = self._resolve_brand(row.get("brand_name")) or self.brand_id
            code = (row.get("item_code") or row.get("code") or "").strip()
            param_key = (row.get("param_key") or "").strip().lower()
            item = item_map.get((brand.id if brand else 0, code))
            param = param_map.get(param_key) or param_model.search([("param_key", "=", param_key)], limit=1)
            if not (item and param):
                apply_stats["spec_values_skipped"] += 1
                unmatched.append(
                    {
                        "excerpt": row.get("source_excerpt") or str(row)[:200],
                        "reason": "未找到匹配的型号或参数字典",
                        "candidate_param_key": param_key or False,
                    }
                )
                continue
            ok, normalized_value, reject_reason = self._coerce_spec_raw_value(param, row)
            if not ok:
                apply_stats["spec_values_skipped"] += 1
                unmatched.append(
                    {
                        "excerpt": row.get("source_excerpt") or str(row)[:200],
                        "reason": f"参数值跳过：{reject_reason}",
                        "candidate_param_key": param.param_key,
                    }
                )
                continue
            try:
                applied = item.apply_param_payload(
                    param=param,
                    raw_value=normalized_value,
                    unit=row.get("unit"),
                    test_method=row.get("test_method"),
                    test_condition=row.get("test_condition"),
                    remark=row.get("remark"),
                    source_document=self,
                    source_excerpt=row.get("source_excerpt"),
                    confidence=row.get("confidence"),
                    is_ai_generated=True,
                    review_status=row.get("review_status") or "pending",
                    conditions=row.get("conditions") or [],
                )
                if not applied:
                    apply_stats["spec_values_skipped"] += 1
                    continue
                apply_stats["spec_values_applied"] += 1
            except Exception as exc:  # 闃叉鍗曟潯寮傚父闃绘柇鏁存壒鍏ュ簱
                apply_stats["spec_values_skipped"] += 1
                unmatched.append(
                    {
                        "excerpt": row.get("source_excerpt") or str(row)[:200],
                        "reason": f"鍙傛暟鍊煎叆搴撳け璐ワ細{str(exc)[:120]}",
                        "candidate_param_key": param.param_key,
                    }
                )
        if hasattr(self, "_extract_and_apply_method_images"):
            self._extract_and_apply_method_images(param_keys=set(param_map.keys()))
        return apply_stats

    @api.model
    def _clean_text(self, value):
        text = super()._clean_text(value) if hasattr(super(), "_clean_text") else None
        text = text or (str(value).replace("\r\n", "\n").replace("\r", "\n").replace("\x00", "") if value else "")
        if not text:
            return False
        replacements = {
            "?": " ",
            "庐": " ",
            "渭m": "um",
            "GT71 00": "GT7100",
            "GT71 02": "GT7102",
            "GT71 04": "GT7104",
            "GT71 06": "GT7106",
            "GT71 08": "GT7108",
            "GT71 12": "GT7112",
            "GT71 16": "GT7116",
            "GT71 20": "GT7120",
            "GT71 25": "GT7125",
            "GT71 30": "GT7130",
            "GT71 35": "GT7135",
            "GT71 40": "GT7140",
            "GT 7100": "GT7100",
            "Acry lic": "Acrylic",
            "ad hesion": "adhesion",
            "sensi tive": "sensitive",
            "perf ormance": "performance",
            "Param e ters": "Parameters",
            "typical p erformance": "typical performance",
            "Wat e r": "Water",
            "we ather": "weather",
            "pane l": "panel",
            "polyethylene liner Acrylic pressure sensi tive": "polyethylene liner Acrylic pressure sensitive adhesive",
            "Heat -aging": "Heat-aging",
            "Wax -remover": "Wax-remover",
            "one -way": "one-way",
            "pressure- sensitive": "pressure-sensitive",
        }
        for src, dst in replacements.items():
            text = text.replace(src, dst)
        text = re.sub(r"\b([A-Z]{1,5}\d{2})\s+(\d{2})\b", r"\1\2", text)
        text = re.sub(r"[ \t]+", " ", text)
        lines = [line.strip() for line in text.split("\n")]
        merged = []
        buffer = ""
        for line in lines:
            if not line:
                if buffer:
                    merged.append(buffer.strip())
                    buffer = ""
                continue
            if not buffer:
                buffer = line
                continue
            joinable = (
                buffer[-1] not in ".:;!?"
                and (line[:1].islower() or buffer.endswith((",", "-", "->")) or len(buffer) < 48)
                and not re.match(r"^(?:[A-Z][A-Za-z ]{2,40}|[A-Z]{1,5}\d{4,5}\b|[鈥?-])$", line)
            )
            if joinable:
                sep = "" if buffer[-1].isalnum() and line[:1].isalnum() and len(line.split()) <= 2 else " "
                buffer = f"{buffer}{sep}{line}".strip()
            else:
                merged.append(buffer.strip())
                buffer = line
        if buffer:
            merged.append(buffer.strip())
        text = "\n".join(merged)
        text = re.sub(r"\n{3,}", "\n\n", text)
        normalized = text.strip()
        if not normalized:
            return False
        if normalized.casefold() in self._PLACEHOLDER_TEXTS:
            return False
        return normalized

    @api.model
    def _guess_global_specs(self, text):
        lowered = (text or "").lower()
        guessed = {}
        if any(token in lowered for token in ("black", "黑色")):
            guessed["color_name"] = "黑色"
        elif any(token in lowered for token in ("white", "白色")):
            guessed["color_name"] = "白色"
        if any(token in lowered for token in ("acrylic foam", "亚克力泡棉", "泡棉基材")):
            guessed["base_material_name"] = "亚克力泡棉"
        if any(token in lowered for token in ("pressure sensitive adhesive", "acrylic adhesive", "压敏胶", "亚克力胶")):
            guessed["adhesive_type_name"] = "丙烯酸胶"
        return guessed

    @api.model
    def _compact_parse_text(self, text):
        return re.sub(r"\s+", " ", self._clean_text(text) or "").strip()

    @api.model
    def _extract_section_text(self, compact_text, start_markers, stop_markers):
        haystack = compact_text or ""
        lowered = haystack.lower()
        start_positions = []
        for marker in start_markers:
            pos = lowered.find(marker.lower())
            if pos >= 0:
                start_positions.append((pos, marker))
        if not start_positions:
            return ""
        start_pos, marker = sorted(start_positions, key=lambda item: item[0])[0]
        section_start = start_pos + len(marker)
        end_candidates = []
        for marker in stop_markers:
            pos = lowered.find(marker.lower(), section_start)
            if pos >= 0:
                end_candidates.append(pos)
        section_end = min(end_candidates) if end_candidates else len(haystack)
        return haystack[section_start:section_end].strip(" :-\n")

    @api.model
    def _html_bullets(self, values):
        clean_values = [html.escape(str(value).strip()) for value in values if str(value).strip()]
        if not clean_values:
            return False
        return "<ul>%s</ul>" % "".join(f"<li>{value}</li>" for value in clean_values)

    @api.model
    def _extract_item_rows_from_physical_properties(self, compact_text, series_name, guessed):
        section = self._extract_section_text(
            compact_text,
            ["Physical Properties"],
            ["Tabbing", "Performance Properties", "Shelf Life", "Technical Data Sheet"],
        )
        rows = []
        seen = set()
        current_color = guessed.get("color_name")
        explicit_color_by_code = {}
        for explicit_match in re.finditer(
            r"\b([A-Z]{1,5}\d{4})\b.{0,40}?Acrylic Foam Core\s+(Gray|Grey|White|榛戣壊|鐧借壊)",
            section,
            flags=re.I,
        ):
            token = (explicit_match.group(2) or "").lower()
            if token in ("gray", "grey"):
                explicit_color_by_code[explicit_match.group(1).upper()] = "鐏拌壊"
            elif token == "white":
                explicit_color_by_code[explicit_match.group(1).upper()] = "鐧借壊"
            elif token == "榛戣壊":
                explicit_color_by_code[explicit_match.group(1).upper()] = "榛戣壊"
            elif token == "鐧借壊":
                explicit_color_by_code[explicit_match.group(1).upper()] = "鐧借壊"
        pattern = re.compile(
            r"\b([A-Z]{1,5}\d{4})\b(?:(?!\b[A-Z]{1,5}\d{4}\b).){0,120}?"
            r"(Gray|Grey|White|榛戣壊|鐧借壊)?(?:(?!\b[A-Z]{1,5}\d{4}\b).){0,40}?"
            r"(\d+(?:\.\d+)?)\s*mm",
            re.I,
        )
        for match in pattern.finditer(section):
            code = (match.group(1) or "").upper()
            if not code or code == (series_name or "").upper():
                continue
            if code in seen:
                continue
            if explicit_color_by_code.get(code):
                current_color = explicit_color_by_code[code]
            color_token = (match.group(2) or "").lower()
            if color_token in ("gray", "grey"):
                current_color = "鐏拌壊"
            elif color_token == "white":
                current_color = "鐧借壊"
            thickness = match.group(3)
            seen.add(code)
            rows.append(
                {
                    "code": code,
                    "name": code,
                    "thickness": thickness,
                    "thickness_std": f"{int(round(float(thickness) * 1000))}um",
                    "color_name": current_color,
                    "base_material_name": guessed.get("base_material_name"),
                    "adhesive_type_name": guessed.get("adhesive_type_name"),
                }
            )
        return rows

    @api.model
    def _extract_numeric_row_after_label(self, section_text, label, expected_count):
        pattern = re.escape(label).replace(r"\ ", r"\s+") + r"\s+((?:\d+(?:\.\d+)?\s+){%s}\d+(?:\.\d+)?)" % max(expected_count - 1, 0)
        match = re.search(pattern, section_text, flags=re.I)
        if not match:
            return []
        return re.findall(r"\d+(?:\.\d+)?", match.group(1))

    @api.model
    def _ensure_candidate_param(self, payload, known_params, param_key, name, value_type="char", unit=False, **extra):
        existing = next((row for row in payload["params"] if row.get("param_key") == param_key), None)
        row = existing or {"param_key": param_key}
        row.update(
            {
                "name": name,
                "canonical_name_zh": extra.get("canonical_name_zh") or name,
                "canonical_name_en": extra.get("canonical_name_en") or False,
                "value_type": value_type,
                "preferred_unit": extra.get("preferred_unit") or unit or False,
                "common_units": extra.get("common_units") or unit or False,
                "unit": unit or False,
                "spec_category_name": extra.get("spec_category_name") or False,
                "is_main_field": extra.get("is_main_field", False),
                "main_field_name": extra.get("main_field_name") or False,
                "method_html": extra.get("method_html") or False,
                "candidate_new": param_key not in known_params,
            }
        )
        if not existing:
            payload["params"].append(row)
        return row

    @api.model
    def _append_spec_value_rows(self, payload, codes, param_key, values, unit=False, test_method=False, test_condition=False, source_excerpt=False):
        if not codes or not values or len(values) != len(codes):
            return
        for code, value in zip(codes, values):
            payload["spec_values"].append(
                {
                    "item_code": code,
                    "param_key": param_key,
                    "value": value,
                    "unit": unit or False,
                    "test_method": test_method or False,
                    "test_condition": test_condition or False,
                    "source_excerpt": source_excerpt or test_condition or False,
                    "review_status": "pending",
                }
            )

    @api.model
    def _append_series_wide_rows(self, payload, codes, param_key, value, unit=False, test_method=False, test_condition=False, source_excerpt=False):
        clean_value = self._clean_text(value)
        if not clean_value:
            return
        for code in codes:
            payload["spec_values"].append(
                {
                    "item_code": code,
                    "param_key": param_key,
                    "value": clean_value,
                    "unit": unit or False,
                    "test_method": test_method or False,
                    "test_condition": test_condition or False,
                    "source_excerpt": source_excerpt or clean_value[:300],
                    "review_status": "pending",
                }
            )

    @api.model
    def _extract_summary_sentence(self, section_text):
        compact = self._compact_parse_text(section_text)
        if not compact:
            return ""
        sentences = re.split(r"(?<=[.!?])\s+", compact)
        return next((sentence.strip() for sentence in sentences if len(sentence.strip()) > 20), compact[:300])

    @api.model
    def _build_method_html(self, title, section_text, summary=False):
        lines = [line.strip() for line in (section_text or "").split("\n") if line.strip()]
        parts = [f"<h4>{html.escape(title)}</h4>"]
        if summary:
            parts.append(f"<p>{html.escape(summary)}</p>")
        if lines:
            parts.append("<ul>%s</ul>" % "".join(f"<li>{html.escape(line)}</li>" for line in lines[:8]))
        return "".join(parts)

