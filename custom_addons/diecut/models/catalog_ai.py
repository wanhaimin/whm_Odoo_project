# -*- coding: utf-8 -*-

import base64
import html
import json
import mimetypes
import os
import re
from io import BytesIO

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError

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
    source_filename = fields.Char(string="文件名")
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
    context_used = fields.Text(string="上下文快照", readonly=True)
    raw_text = fields.Text(string="原始文本")
    parse_version = fields.Char(string="解析版本", default="draft-v1")
    import_status = fields.Selection(
        [
            ("draft", "草稿"),
            ("extracted", "已提取"),
            ("generated", "已生成"),
            ("validated", "已校验"),
            ("review", "待确认"),
            ("applied", "已入库"),
            ("rejected", "已驳回"),
        ],
        string="导入状态",
        default="draft",
        tracking=True,
    )
    extracted_image = fields.Binary(string="提取图片", attachment=True)
    extracted_image_filename = fields.Char(string="图片文件名")
    draft_payload = fields.Text(
        string="结构化草稿",
        help="JSON 结构：series/items/params/category_params/spec_values/unmatched",
    )
    result_message = fields.Text(string="处理结果")
    unmatched_payload = fields.Text(string="未识别项")
    draft_summary = fields.Text(string="草稿摘要", compute="_compute_draft_preview")
    draft_preview_html = fields.Html(string="结构化预览", compute="_compute_draft_preview", sanitize=False)
    line_count = fields.Integer(string="关联参数值数", compute="_compute_line_count")

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
            "heuristic_snapshot": self._build_ai_enrichment_context(base_payload) if base_payload else False,
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
                html_parts.append("<div style='color:#999;margin-bottom:12px;'>无</div>")
                continue
            if bucket == "unmatched":
                html_parts.append("<ul style='margin:0 0 16px 18px;padding:0;'>")
                for row in rows[:20]:
                    excerpt = html.escape(str((row or {}).get("excerpt") or row or ""))
                    html_parts.append(f"<li style='margin-bottom:6px;white-space:pre-wrap;'>{excerpt}</li>")
                html_parts.append("</ul>")
                if len(rows) > 20:
                    html_parts.append(f"<div style='color:#999;'>其余 {len(rows) - 20} 条请查看原始 JSON。</div>")
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
                html_parts.append(f"<div style='color:#999;margin-bottom:12px;'>其余 {len(rows) - 20} 条请查看原始 JSON。</div>")
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
                f"分类参数 {counts['category_params']} 条，参数值 {counts['spec_values']} 条，未识别 {counts['unmatched']} 条。"
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
                ("product_description", "产品描述"),
                ("main_applications", "主要应用"),
            ],
            "items": [
                ("brand_name", "品牌"),
                ("code", "型号"),
                ("name", "名称"),
                ("catalog_status", "状态"),
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
                ("excerpt", "未识别内容"),
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
        if bucket == "params" and column == "route_label":
            if row.get("is_main_field"):
                field_name = row.get("main_field_name") or ""
                return f"主表字段 / {field_name}" if field_name else "主表字段"
            return "参数值表"
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
            for key in ("value", "value_text", "raw_value_text", "value_char", "value_float", "value_selection"):
                candidate = row.get(key)
                if candidate not in (False, None, ""):
                    return candidate
            if row.get("value_boolean") is True:
                return "是"
            if row.get("value_boolean") is False and "value_boolean" in row:
                return "否"
            return ""
        if column == "excerpt":
            return row.get("excerpt") or row.get("text") or row.get("raw") or ""
        value = row.get(column)
        if isinstance(value, bool):
            if column in boolean_columns:
                return "是" if value else "否"
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
            html_parts.append(f"<div style='color:#999;margin-bottom:12px;'>其余 {len(rows) - 20} 条请查看原始 JSON。</div>")
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
                "这里展示的是人工校验视图，已按业务结构拆成可读表格。默认只显示前 20 条记录；"
                "如果需要完整结构，请再查看“原始 JSON”。"
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
        return text.strip() or False

    @staticmethod
    def _decode_binary_field(binary_value):
        if not binary_value:
            return b""
        if isinstance(binary_value, bytes):
            return base64.b64decode(binary_value)
        return base64.b64decode(binary_value.encode())

    def _read_attachment_bytes(self, attachment):
        self.ensure_one()
        if not attachment:
            return b""
        if attachment.datas:
            return self._decode_binary_field(attachment.datas)
        if attachment.store_fname:
            return attachment._file_read(attachment.store_fname)
        return b""

    def _extract_text_from_pdf(self, payload_bytes):
        text_parts = []
        try:
            import pdfplumber
        except ImportError:
            pdfplumber = None
        if pdfplumber:
            with pdfplumber.open(BytesIO(payload_bytes)) as pdf:
                for page in pdf.pages:
                    page_text = self._clean_text(page.extract_text() or "")
                    if page_text:
                        text_parts.append(page_text)
        else:
            try:
                from PyPDF2 import PdfReader
            except ImportError as exc:
                raise UserError("当前环境未安装 pdfplumber 或 PyPDF2，无法提取 PDF 文本。") from exc
            reader = PdfReader(BytesIO(payload_bytes))
            for page in reader.pages:
                page_text = self._clean_text(page.extract_text() or "")
                if page_text:
                    text_parts.append(page_text)
        return self._clean_text("\n\n".join(text_parts))

    def _extract_pdf_preview_image(self, payload_bytes, filename):
        try:
            import pypdfium2 as pdfium
        except ImportError:
            return False, False
        pdf = pdfium.PdfDocument(payload_bytes)
        try:
            if len(pdf) < 1:
                return False, False
            page = pdf[0]
            bitmap = page.render(scale=2)
            image = bitmap.to_pil()
            buffer = BytesIO()
            image.save(buffer, format="JPEG", quality=90)
            encoded = base64.b64encode(buffer.getvalue())
            base_name = os.path.splitext(filename or "source")[0]
            return encoded, f"{base_name}_preview.jpg"
        finally:
            pdf.close()

    def _extract_text_from_image(self, payload_bytes, filename):
        try:
            from PIL import Image
        except ImportError as exc:
            raise UserError("当前环境未安装 Pillow，无法处理图片。") from exc

        try:
            import pytesseract
        except ImportError:
            pytesseract = None

        if pytesseract:
            image = Image.open(BytesIO(payload_bytes))
            text = pytesseract.image_to_string(image, lang="eng+chi_sim")
            return self._clean_text(text)
        if self._has_openai_config():
            return self._extract_text_from_image_via_openai(payload_bytes, filename)
        raise UserError("当前环境未安装 pytesseract，且未配置 OpenAI，无法识别图片文本。")

    def _extract_text_from_image_via_openai(self, payload_bytes, filename):
        mime = mimetypes.guess_type(filename or "")[0] or "image/png"
        data_url = "data:%s;base64,%s" % (mime, base64.b64encode(payload_bytes).decode())
        response = self._openai_request(
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "请只输出图片中的可读文本，不要解释，不要翻译。"},
                        {"type": "image_url", "image_url": {"url": data_url}},
                    ],
                }
            ],
            max_tokens=2000,
        )
        return self._clean_text(response)

    def _extract_text_from_url(self, url):
        try:
            import requests
            from bs4 import BeautifulSoup
        except ImportError as exc:
            raise UserError("当前环境缺少 requests 或 beautifulsoup4，无法抓取网页。") from exc

        resp = requests.get(url, timeout=30, headers={"User-Agent": "Mozilla/5.0"})
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        for tag in soup(["script", "style", "noscript"]):
            tag.decompose()
        text = soup.get_text("\n", strip=True)
        return self._clean_text(text)

    def _guess_source_type_from_attachment(self, attachment):
        mimetype = attachment.mimetype or mimetypes.guess_type(attachment.name or "")[0] or ""
        if mimetype == "application/pdf" or (attachment.name or "").lower().endswith(".pdf"):
            return "pdf"
        if mimetype.startswith("image/"):
            return "ocr"
        return "manual"

    def _extract_source_payload(self):
        self.ensure_one()
        attachment = self._get_effective_primary_attachment()
        if attachment:
            payload_bytes = self._read_attachment_bytes(attachment)
            source_type = self._guess_source_type_from_attachment(attachment)
            if source_type == "pdf":
                text = self._extract_text_from_pdf(payload_bytes)
                preview, preview_name = self._extract_pdf_preview_image(payload_bytes, attachment.name)
            elif source_type == "ocr":
                text = self._extract_text_from_image(payload_bytes, attachment.name)
                preview = base64.b64encode(payload_bytes)
                preview_name = attachment.name
            else:
                text = False
                preview = False
                preview_name = False
            return {
                "source_type": source_type,
                "source_filename": attachment.name,
                "primary_attachment_id": attachment.id,
                "raw_text": text,
                "extracted_image": preview,
                "extracted_image_filename": preview_name,
                "result_message": "原文提取完成。",
                "parse_version": "extract-v1",
                "import_status": "extracted",
            }

        if self.source_file:
            payload_bytes = self._decode_binary_field(self.source_file)
            filename = self.source_filename or self.name
            if (filename or "").lower().endswith(".pdf"):
                text = self._extract_text_from_pdf(payload_bytes)
                preview, preview_name = self._extract_pdf_preview_image(payload_bytes, filename)
                source_type = "pdf"
            else:
                text = self._extract_text_from_image(payload_bytes, filename)
                preview = base64.b64encode(payload_bytes)
                preview_name = filename
                source_type = "ocr"
            return {
                "source_type": source_type,
                "raw_text": text,
                "extracted_image": preview,
                "extracted_image_filename": preview_name,
                "result_message": "原文提取完成。",
                "parse_version": "extract-v1",
                "import_status": "extracted",
            }

        if self.source_url:
            return {
                "source_type": "url",
                "raw_text": self._extract_text_from_url(self.source_url),
                "result_message": "网页正文提取完成。",
                "parse_version": "extract-v1",
                "import_status": "extracted",
            }

        if self.raw_text:
            return {
                "raw_text": self._clean_text(self.raw_text),
                "result_message": "已使用现有原文内容。",
                "parse_version": "extract-v1",
                "import_status": "extracted",
            }
        raise UserError("未找到可解析的来源。请先在 chatter 上传 PDF/图片，或填写来源 URL / 原始文本。")

    def _has_openai_config(self):
        return bool(os.getenv("OPENAI_API_KEY"))

    def _openai_request(self, messages, max_tokens=4000):
        try:
            import requests
        except ImportError as exc:
            raise UserError("当前环境未安装 requests，无法调用 OpenAI。") from exc

        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise UserError("未配置 OPENAI_API_KEY。")
        api_url = os.getenv("OPENAI_API_URL") or "https://api.openai.com/v1/chat/completions"
        model = os.getenv("OPENAI_MODEL") or "gpt-4.1-mini"
        payload = {
            "model": model,
            "messages": messages,
            "temperature": 0.1,
            "max_tokens": max_tokens,
        }
        resp = requests.post(
            api_url,
            timeout=90,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json=payload,
        )
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"]

    @api.model
    def _strip_json_fence(self, content):
        text = (content or "").strip()
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?\s*", "", text)
            text = re.sub(r"\s*```$", "", text)
        return text.strip()

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

    def _generate_draft_with_openai(self):
        self.ensure_one()
        text = self._clean_text(self.raw_text)
        if not text:
            raise UserError("请先提取原文，再生成 AI 草稿。")
        prompt = (
            "你是 Odoo 材料系统的 TDS 解析器。"
            "请根据给定原文、品牌、建议分类、参数字典和主字段路由规则，"
            "输出严格 JSON，对齐为 keys: series/items/params/category_params/spec_values/unmatched。"
            "只允许使用已存在的 param_key；如果遇到未知参数，请放到 unmatched，"
            "或放到 params 并标记 candidate_new=true。"
            "如果原文包含标准测试方法、图例说明、测试步骤或判读口径，可写入 params[*].method_html。"
            "不要输出解释文字。"
        )
        content = self._openai_request(
            messages=[
                {"role": "system", "content": prompt},
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "title": self.name,
                            "brand_name": self.brand_id.name if self.brand_id else False,
                            "category_name": self.categ_id.name if self.categ_id else False,
                            "text": text,
                            "param_dictionary": self._build_param_context(),
                        },
                        ensure_ascii=False,
                    ),
                },
            ],
            max_tokens=5000,
        )
        payload = json.loads(self._strip_json_fence(content))
        return self._normalize_generated_payload(payload), "ai-v1"

    @api.model
    def _guess_series_name(self, title, text):
        candidates = []
        if title:
            candidates.extend(re.findall(r"\b[A-Z]{1,5}\d{3,5}(?:[A-Z0-9-]*)\b", title.upper()))
        if text:
            candidates.extend(re.findall(r"\b[A-Z]{1,5}\d{3,5}(?:[A-Z0-9-]*)\b", text.upper()))
        seen = []
        for candidate in candidates:
            if candidate not in seen:
                seen.append(candidate)
        return seen[0] if seen else (title or "未命名来源")

    @api.model
    def _find_distinct_codes(self, text):
        if not text:
            return []
        matches = re.findall(r"\b[A-Z]{1,5}\d{3,5}(?:[-/#][A-Z0-9]+)?\b", text.upper())
        codes = []
        for match in matches:
            if match not in codes:
                codes.append(match)
        return codes[:50]

    @api.model
    def _guess_global_specs(self, text):
        lowered = (text or "").lower()
        guessed = {}
        if any(token in lowered for token in ("black", "黑色")):
            guessed["color_name"] = "黑色"
        elif any(token in lowered for token in ("white", "白色")):
            guessed["color_name"] = "白色"
        if any(token in lowered for token in ("acrylic foam", "丙烯酸泡棉")):
            guessed["base_material_name"] = "丙烯酸泡棉"
        if any(token in lowered for token in ("acrylic adhesive", "丙烯酸胶")):
            guessed["adhesive_type_name"] = "丙烯酸胶"
        return guessed

    @api.model
    def _extract_thickness_for_code(self, code, text):
        if not text:
            return False, False
        line = next((raw_line for raw_line in text.splitlines() if code in raw_line.upper()), "")
        mm_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:mm|MM)\b", line)
        um_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:μm|um|UM)\b", line)
        if mm_match:
            thickness = mm_match.group(1)
            return thickness, f"{int(round(float(thickness) * 1000))}μm"
        if um_match:
            um_value = float(um_match.group(1))
            return str(round(um_value / 1000, 4)), f"{int(round(um_value))}μm"
        return False, False

    def _generate_draft_heuristic(self):
        self.ensure_one()
        text = self._clean_text(self.raw_text)
        series_name = self._guess_series_name(self.name, text)
        codes = self._find_distinct_codes(text)
        guessed = self._guess_global_specs(text)
        payload = {bucket: [] for bucket in self._DRAFT_BUCKETS}

        payload["series"].append(
            {
                "brand_name": self.brand_id.name if self.brand_id else False,
                "name": series_name,
                "product_description": (text[:500] if text else False),
            }
        )

        known_params = {param.param_key: param for param in self.env["diecut.catalog.param"].sudo().search([])}
        defaults = {
            "thickness": ("厚度", "float", "mm", True, "thickness"),
            "thickness_std": ("厚度(标准)", "char", "μm", True, "thickness_std"),
            "color": ("颜色", "char", False, True, "color_id"),
            "adhesive_type": ("胶系", "char", False, True, "adhesive_type_id"),
            "base_material": ("基材", "char", False, True, "base_material_id"),
        }
        for param_key, (name, value_type, unit, is_main, main_field_name) in defaults.items():
            if param_key not in known_params:
                payload["params"].append(
                    {
                        "param_key": param_key,
                        "name": name,
                        "value_type": value_type,
                        "unit": unit,
                        "is_main_field": is_main,
                        "main_field_name": main_field_name,
                        "candidate_new": True,
                    }
                )

        for code in codes:
            thickness, thickness_std = self._extract_thickness_for_code(code, text)
            payload["items"].append(
                {
                    "brand_name": self.brand_id.name if self.brand_id else False,
                    "series_name": series_name,
                    "category_name": self.categ_id.name if self.categ_id else False,
                    "code": code,
                    "name": code,
                    "catalog_status": "draft",
                }
            )
            if thickness:
                payload["spec_values"].append({"brand_name": self.brand_id.name if self.brand_id else False, "item_code": code, "param_key": "thickness", "value": thickness, "unit": "mm", "review_status": "pending"})
            if thickness_std:
                payload["spec_values"].append({"brand_name": self.brand_id.name if self.brand_id else False, "item_code": code, "param_key": "thickness_std", "value": thickness_std, "unit": "μm", "review_status": "pending"})
            if guessed.get("color_name"):
                payload["spec_values"].append({"brand_name": self.brand_id.name if self.brand_id else False, "item_code": code, "param_key": "color", "value": guessed["color_name"], "review_status": "pending"})
            if guessed.get("adhesive_type_name"):
                payload["spec_values"].append({"brand_name": self.brand_id.name if self.brand_id else False, "item_code": code, "param_key": "adhesive_type", "value": guessed["adhesive_type_name"], "review_status": "pending"})
            if guessed.get("base_material_name"):
                payload["spec_values"].append({"brand_name": self.brand_id.name if self.brand_id else False, "item_code": code, "param_key": "base_material", "value": guessed["base_material_name"], "review_status": "pending"})

        for line in (text or "").splitlines()[:40]:
            if line and len(line) > 10:
                payload["unmatched"].append({"excerpt": line[:300]})
        return self._normalize_generated_payload(payload), "heuristic-v1"

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

    def action_extract_source(self):
        for record in self:
            payload = record._extract_source_payload()
            brand_skill = record._resolve_brand_skill_name()
            payload.update(
                {
                    "skill_profile": record.skill_profile or "generic_tds_v1+diecut_domain_v1",
                    "brand_skill_name": brand_skill,
                    "context_used": json.dumps(record._build_copilot_context(), ensure_ascii=False, indent=2),
                }
            )
            record.write(payload)
        return True

    def action_generate_draft(self):
        for record in self:
            if not record.raw_text:
                record.action_extract_source()
            if not record.raw_text:
                raise UserError("未提取到原文，无法生成草稿。")
            if record._has_openai_config():
                payload, parse_version = record._generate_draft_with_openai()
                message = "AI 草稿已生成。"
            else:
                payload, parse_version = record._generate_draft_heuristic()
                message = "未检测到 OpenAI 配置，已使用本地启发式规则生成草稿，请人工复核。"
            record._run_encoding_precheck(payload)
            record.write(
                {
                    "draft_payload": json.dumps(payload, ensure_ascii=False, indent=2),
                    "unmatched_payload": json.dumps(payload.get("unmatched") or [], ensure_ascii=False, indent=2),
                    "parse_version": parse_version,
                    "import_status": "generated",
                    "result_message": message,
                }
            )
        return True

    @api.model
    def _preview_value(self, bucket, row, column):
        if not isinstance(row, dict):
            return row or ""
        boolean_columns = {"required", "show_in_form", "allow_import", "is_main_field", "active", "candidate_new"}
        if bucket == "params" and column == "route_label":
            if row.get("is_main_field"):
                field_name = row.get("main_field_name") or ""
                return f"主表字段 / {field_name}" if field_name else "主表字段"
            return "参数值表"
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
        if bucket == "category_params" and column == "name":
            param_name = row.get("param_name") or row.get("name")
            if not param_name and row.get("param_key"):
                param = self.env["diecut.catalog.param"].sudo().search([("param_key", "=", row.get("param_key"))], limit=1)
                param_name = param.name if param else False
            return param_name or row.get("param_key") or ""
        if bucket == "spec_values" and column == "item_code":
            return row.get("item_code") or row.get("code") or row.get("item_name") or ""
        if bucket == "spec_values" and column == "param_name":
            param_name = row.get("param_name") or row.get("name")
            if not param_name and row.get("param_key"):
                param = self.env["diecut.catalog.param"].sudo().search([("param_key", "=", row.get("param_key"))], limit=1)
                param_name = param.name if param else False
            return param_name or row.get("param_key") or ""
        if bucket == "spec_values" and column == "display_value":
            direct = row.get("display_value")
            if direct not in (False, None, ""):
                return direct
            for key in ("value", "value_text", "raw_value_text", "value_char", "value_float", "value_selection"):
                candidate = row.get(key)
                if candidate not in (False, None, ""):
                    return candidate
            if row.get("value_boolean") is True:
                return "是"
            if row.get("value_boolean") is False and "value_boolean" in row:
                return "否"
            return ""
        if column == "excerpt":
            return row.get("excerpt") or row.get("text") or row.get("raw") or ""
        value = row.get(column)
        if isinstance(value, bool):
            if column in boolean_columns:
                return "是" if value else "否"
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
                if isinstance(value, str):
                    text_value = value.strip()
                else:
                    text_value = "" if value in (False, None) else str(value)
                if text_value.lower() in {"false", "none", "null"}:
                    text_value = ""
                if bucket == "spec_values" and column in {"unit", "test_condition"} and text_value == "否":
                    text_value = ""
                rendered = html.escape(text_value)
                html_parts.append(
                    f"<td style='vertical-align:top;border-bottom:1px solid #eee;padding:6px 8px;white-space:pre-wrap;'>{rendered}</td>"
                )
            html_parts.append("</tr>")
        html_parts.append("</tbody></table>")
        if len(rows) > 20:
            html_parts.append(f"<div style='color:#999;margin-bottom:12px;'>其余 {len(rows) - 20} 条请查看原始 JSON。</div>")
        return "".join(html_parts)

    @api.model
    def _get_ai_runtime_config(self):
        icp = self.env["ir.config_parameter"].sudo()
        provider_defaults = {
            "disabled": {
                "api_url": "",
                "model": "",
            },
            "openai": {
                "api_url": "https://api.openai.com/v1/chat/completions",
                "model": "gpt-4.1-mini",
            },
            "deepseek": {
                "api_url": "https://api.deepseek.com/chat/completions",
                "model": "deepseek-chat",
            },
            "qwen": {
                "api_url": "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions",
                "model": "qwen-vl-max-latest",
            },
        }
        provider = (
            self.env.context.get("diecut_ai_provider")
            or icp.get_param("diecut.ai_tds_provider")
            or ("openai" if (icp.get_param("diecut.ai_tds_openai_api_key") or os.getenv("OPENAI_API_KEY")) else "disabled")
        )
        defaults = provider_defaults.get(provider or "disabled", provider_defaults["disabled"])
        return {
            "provider": provider or "disabled",
            "api_key": self.env.context.get("diecut_ai_api_key")
            or icp.get_param("diecut.ai_tds_openai_api_key")
            or os.getenv("OPENAI_API_KEY"),
            "api_url": self.env.context.get("diecut_ai_api_url")
            or icp.get_param("diecut.ai_tds_openai_api_url")
            or os.getenv("OPENAI_API_URL")
            or defaults["api_url"],
            "model": self.env.context.get("diecut_ai_model")
            or icp.get_param("diecut.ai_tds_openai_model")
            or os.getenv("OPENAI_MODEL")
            or defaults["model"],
        }

    def _has_openai_config(self):
        config = self._get_ai_runtime_config()
        return config["provider"] in {"openai", "deepseek", "qwen"} and bool(config["api_key"])

    def _openai_request(self, messages, max_tokens=4000):
        try:
            import requests
        except ImportError as exc:
            raise UserError("当前环境未安装 requests，无法调用 AI 接口。") from exc

        config = self._get_ai_runtime_config()
        if config["provider"] not in {"openai", "deepseek", "qwen"} or not config["api_key"]:
            raise UserError("当前未配置可用的 AI 兼容接口。")

        payload = {
            "model": config["model"],
            "messages": messages,
            "temperature": 0.1,
            "max_tokens": max_tokens,
        }
        response = requests.post(
            config["api_url"],
            timeout=90,
            headers={
                "Authorization": f"Bearer {config['api_key']}",
                "Content-Type": "application/json",
            },
            json=payload,
        )
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"]

    @api.model
    def _get_ai_provider_label(self, provider):
        return {
            "disabled": "本地增强规则",
            "openai": "OpenAI",
            "deepseek": "DeepSeek",
            "qwen": "通义千问(Qwen)",
        }.get(provider or "disabled", provider or "AI")

    def action_generate_draft(self):
        for record in self:
            if not record.raw_text:
                record.action_extract_source()
            if not record.raw_text:
                raise UserError("未提取到原文，无法生成草稿。")
            if record._has_openai_config():
                payload, parse_version = record._generate_draft_with_openai()
                config = record._get_ai_runtime_config()
                provider_label = record._get_ai_provider_label(config["provider"])
                message = f"AI 草稿已生成。当前引擎：{provider_label} / {config['model']}"
            else:
                payload, parse_version = record._generate_draft_heuristic()
                message = "未检测到 AI 配置，已使用本地增强规则生成草稿，请人工复核。"
            record._run_encoding_precheck(payload)
            record.write(
                {
                    "draft_payload": json.dumps(payload, ensure_ascii=False, indent=2),
                    "unmatched_payload": json.dumps(payload.get("unmatched") or [], ensure_ascii=False, indent=2),
                    "parse_version": parse_version,
                    "import_status": "generated",
                    "result_message": message,
                }
            )
        return True

    @api.model
    def _get_ai_runtime_config(self):
        icp = self.env["ir.config_parameter"].sudo()
        provider_defaults = {
            "disabled": {
                "api_url": "",
                "model": "",
            },
            "openai": {
                "api_url": "https://api.openai.com/v1/chat/completions",
                "model": "gpt-4.1-mini",
            },
            "deepseek": {
                "api_url": "https://api.deepseek.com/chat/completions",
                "model": "deepseek-chat",
            },
            "qwen": {
                "api_url": "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions",
                "model": "qwen-vl-max-latest",
            },
        }
        provider = (
            self.env.context.get("diecut_ai_provider")
            or icp.get_param("diecut.ai_tds_provider")
            or ("openai" if (icp.get_param("diecut.ai_tds_openai_api_key") or os.getenv("OPENAI_API_KEY")) else "disabled")
        )
        defaults = provider_defaults.get(provider or "disabled", provider_defaults["disabled"])
        return {
            "provider": provider or "disabled",
            "api_key": self.env.context.get("diecut_ai_api_key")
            or icp.get_param("diecut.ai_tds_openai_api_key")
            or os.getenv("OPENAI_API_KEY"),
            "api_url": self.env.context.get("diecut_ai_api_url")
            or icp.get_param("diecut.ai_tds_openai_api_url")
            or os.getenv("OPENAI_API_URL")
            or defaults["api_url"],
            "model": self.env.context.get("diecut_ai_model")
            or icp.get_param("diecut.ai_tds_openai_model")
            or os.getenv("OPENAI_MODEL")
            or defaults["model"],
        }

    def _has_openai_config(self):
        config = self._get_ai_runtime_config()
        return config["provider"] in {"openai", "deepseek", "qwen"} and bool(config["api_key"])

    def _openai_request(self, messages, max_tokens=4000):
        try:
            import requests
        except ImportError as exc:
            raise UserError("当前环境未安装 requests，无法调用 AI 接口。") from exc

        config = self._get_ai_runtime_config()
        if config["provider"] not in {"openai", "deepseek", "qwen"} or not config["api_key"]:
            raise UserError("当前未配置可用的 AI 兼容接口。")

        payload = {
            "model": config["model"],
            "messages": messages,
            "temperature": 0.1,
            "max_tokens": max_tokens,
        }
        resp = requests.post(
            config["api_url"],
            timeout=90,
            headers={
                "Authorization": f"Bearer {config['api_key']}",
                "Content-Type": "application/json",
            },
            json=payload,
        )
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"]

    @api.model
    def _get_ai_provider_label(self, provider):
        labels = {
            "disabled": "本地增强规则",
            "openai": "OpenAI",
            "deepseek": "DeepSeek",
            "qwen": "通义千问(Qwen)",
        }
        return labels.get(provider or "disabled", provider or "AI")

    def action_generate_draft(self):
        for record in self:
            if not record.raw_text:
                record.action_extract_source()
            if not record.raw_text:
                raise UserError("未提取到原文，无法生成草稿。")
            if record._has_openai_config():
                payload, parse_version = record._generate_draft_with_openai()
                config = record._get_ai_runtime_config()
                provider_label = record._get_ai_provider_label(config["provider"])
                message = f"AI 草稿已生成。当前引擎：{provider_label} / {config['model']}"
            else:
                payload, parse_version = record._generate_draft_heuristic()
                message = "未检测到 AI 配置，已使用本地增强规则生成草稿，请人工复核。"
            record._run_encoding_precheck(payload)
            record.write(
                {
                    "draft_payload": json.dumps(payload, ensure_ascii=False, indent=2),
                    "unmatched_payload": json.dumps(payload.get("unmatched") or [], ensure_ascii=False, indent=2),
                    "parse_version": parse_version,
                    "import_status": "generated",
                    "result_message": message,
                }
            )
        return True

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

    def action_apply_draft(self):
        for record in self:
            payload = record._load_draft_payload()
            record._run_encoding_precheck(payload)
            apply_stats = record._apply_payload(payload)
            skipped = int((apply_stats or {}).get("spec_values_skipped") or 0)
            message = "AI/TDS 草稿已入库。"
            if skipped:
                message = f"{message} 技术参数有 {skipped} 条因类型/映射问题被跳过，已记录到未识别项。"
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

    def _resolve_category(self, raw_value):
        if not raw_value:
            return False
        return self.env["product.category"].search([("name", "=", str(raw_value).strip())], limit=1) or False

    @api.model
    def _pick_first_non_empty(self, *candidates):
        for candidate in candidates:
            if candidate not in (False, None, ""):
                if isinstance(candidate, str):
                    text = candidate.strip()
                    if text:
                        return text
                else:
                    return candidate
        return False

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
            row.get("value_text"),
            row.get("raw_value_text"),
            row.get("display_value"),
            row.get("value_char"),
            row.get("value_float"),
            row.get("value_selection"),
            row.get("value_boolean"),
        )
        if raw_value is False:
            return False, False, "参数值为空"

        if value_type == "float":
            number = self._safe_float_or_false(raw_value)
            if number is False:
                return False, False, "数值型参数无法解析为数字"
            return True, number, False

        if value_type == "boolean":
            if isinstance(raw_value, bool):
                return True, raw_value, False
            normalized = str(raw_value).strip().lower()
            if normalized in ("1", "true", "yes", "y", "是", "有", "通过"):
                return True, True, False
            if normalized in ("0", "false", "no", "n", "否", "无", "不通过"):
                return True, False, False
            return False, False, "布尔型参数无法识别为是/否"

        if value_type == "selection":
            text = str(raw_value).strip()
            if not text:
                return False, False, "枚举参数值为空"
            options = param.get_selection_options_list()
            if options:
                if text in options:
                    return True, text, False
                option_map = {str(opt).strip().lower(): opt for opt in options}
                mapped = option_map.get(text.lower())
                if mapped:
                    return True, mapped, False
                return False, False, "枚举值不在参数字典选项范围内"
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
                "product_features": row.get("product_features") or False,
                "product_description": row.get("product_description") or False,
                "main_applications": row.get("main_applications") or False,
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
            vals = {
                "brand_id": brand.id,
                "code": code,
                "name": row.get("name") or code,
                "categ_id": categ.id if categ else False,
                "series_id": series.id if series else False,
                "series_text": series.name if series else series_name or False,
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
                        "reason": "参数值无法落库：未匹配到型号或参数字典",
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
                item.apply_param_payload(
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
                )
                apply_stats["spec_values_applied"] += 1
            except Exception as exc:  # 防止单条异常阻断整批入库
                apply_stats["spec_values_skipped"] += 1
                unmatched.append(
                    {
                        "excerpt": row.get("source_excerpt") or str(row)[:200],
                        "reason": f"参数值入库失败：{str(exc)[:120]}",
                        "candidate_param_key": param.param_key,
                    }
                )
        if hasattr(self, "_extract_and_apply_method_images"):
            self._extract_and_apply_method_images(param_keys=set(param_map.keys()))
        return apply_stats

    @api.model
    def _get_ai_runtime_config(self):
        icp = self.env["ir.config_parameter"].sudo()
        provider = (
            self.env.context.get("diecut_ai_provider")
            or icp.get_param("diecut.ai_tds_provider")
            or ("openai" if (icp.get_param("diecut.ai_tds_openai_api_key") or os.getenv("OPENAI_API_KEY")) else "disabled")
        )
        return {
            "provider": provider or "disabled",
            "api_key": self.env.context.get("diecut_ai_api_key")
            or icp.get_param("diecut.ai_tds_openai_api_key")
            or os.getenv("OPENAI_API_KEY"),
            "api_url": self.env.context.get("diecut_ai_api_url")
            or icp.get_param("diecut.ai_tds_openai_api_url")
            or os.getenv("OPENAI_API_URL")
            or "https://api.openai.com/v1/chat/completions",
            "model": self.env.context.get("diecut_ai_model")
            or icp.get_param("diecut.ai_tds_openai_model")
            or os.getenv("OPENAI_MODEL")
            or "gpt-4.1-mini",
        }

    def _has_openai_config(self):
        config = self._get_ai_runtime_config()
        return config["provider"] in {"openai", "deepseek", "qwen"} and bool(config["api_key"])

    def _openai_request(self, messages, max_tokens=4000):
        try:
            import requests
        except ImportError as exc:
            raise UserError("当前环境未安装 requests，无法调用 AI 接口。") from exc

        config = self._get_ai_runtime_config()
        if config["provider"] not in {"openai", "deepseek", "qwen"} or not config["api_key"]:
            raise UserError("当前未配置可用的 OpenAI 兼容接口。")

        payload = {
            "model": config["model"],
            "messages": messages,
            "temperature": 0.1,
            "max_tokens": max_tokens,
        }
        resp = requests.post(
            config["api_url"],
            timeout=90,
            headers={
                "Authorization": f"Bearer {config['api_key']}",
                "Content-Type": "application/json",
            },
            json=payload,
        )
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"]

    @api.model
    def _clean_text(self, value):
        text = super()._clean_text(value) if hasattr(super(), "_clean_text") else None
        text = text or (str(value).replace("\r\n", "\n").replace("\r", "\n").replace("\x00", "") if value else "")
        if not text:
            return False
        replacements = {
            "™": " ",
            "®": " ",
            "μm": "um",
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
                and not re.match(r"^(?:[A-Z][A-Za-z ]{2,40}|[A-Z]{1,5}\d{4,5}\b|[•.-])$", line)
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
        return text.strip() or False

    @api.model
    def _guess_global_specs(self, text):
        lowered = (text or "").lower()
        guessed = {}
        if any(token in lowered for token in ("black", "黑色")):
            guessed["color_name"] = "黑色"
        elif any(token in lowered for token in ("white", "白色")):
            guessed["color_name"] = "白色"
        if any(token in lowered for token in ("acrylic foam", "亚克力泡棉", "丙烯酸泡棉")):
            guessed["base_material_name"] = "丙烯酸泡棉"
        if any(token in lowered for token in ("pressure sensitive adhesive", "acrylic adhesive", "压敏胶", "丙烯酸胶")):
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
            r"\b([A-Z]{1,5}\d{4})\b.{0,40}?Acrylic Foam Core\s+(Gray|Grey|White|黑色|白色)",
            section,
            flags=re.I,
        ):
            token = (explicit_match.group(2) or "").lower()
            if token in ("gray", "grey"):
                explicit_color_by_code[explicit_match.group(1).upper()] = "灰色"
            elif token == "white":
                explicit_color_by_code[explicit_match.group(1).upper()] = "白色"
            elif token == "黑色":
                explicit_color_by_code[explicit_match.group(1).upper()] = "黑色"
            elif token == "白色":
                explicit_color_by_code[explicit_match.group(1).upper()] = "白色"
        pattern = re.compile(
            r"\b([A-Z]{1,5}\d{4})\b(?:(?!\b[A-Z]{1,5}\d{4}\b).){0,120}?"
            r"(Gray|Grey|White|黑色|白色)?(?:(?!\b[A-Z]{1,5}\d{4}\b).){0,40}?"
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
                current_color = "灰色"
            elif color_token == "white":
                current_color = "白色"
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

    def _generate_draft_with_openai(self):
        self.ensure_one()
        text = self._clean_text(self.raw_text)
        if not text:
            raise UserError("请先提取原文，再生成 AI 草稿。")
        config = self._get_ai_runtime_config()
        prompt = (
            "你是 Odoo 材料系统的 TDS 解析器。"
            "请根据给定原文、品牌、建议分类、参数字典和主字段路由规则，"
            "输出严格 JSON，顶层 keys 必须是 series/items/params/category_params/spec_values/unmatched。"
            "已知参数优先复用 param_key；未知参数请放入 unmatched，或放入 params 并标记 candidate_new=true。"
            "如果原文包含标准测试方法、图例说明、测试步骤或判读口径，可写入 params[*].method_html。"
            "不要输出任何 JSON 之外的解释。"
        )
        content = self._openai_request(
            messages=[
                {"role": "system", "content": prompt},
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "title": self.name,
                            "brand_name": self.brand_id.name if self.brand_id else False,
                            "category_name": self.categ_id.name if self.categ_id else False,
                            "text": text,
                            "param_dictionary": self._build_param_context(),
                        },
                        ensure_ascii=False,
                    ),
                },
            ],
            max_tokens=5000,
        )
        payload = json.loads(self._strip_json_fence(content))
        return self._normalize_generated_payload(payload), f"ai-v1:{config['model']}"

    def _generate_draft_heuristic(self):
        self.ensure_one()
        text = self._clean_text(self.raw_text)
        compact_text = self._compact_parse_text(text)
        payload = {bucket: [] for bucket in self._DRAFT_BUCKETS}
        known_params = {param.param_key: param for param in self.env["diecut.catalog.param"].sudo().search([])}

        guessed = self._guess_global_specs(compact_text)
        series_name = self._guess_series_name(self.name, compact_text)

        description_section = self._extract_section_text(
            compact_text,
            ["General Description"],
            ["Product Construction", "Physical Properties", "Tabbing", "Performance Properties"],
        )
        features_section = self._extract_section_text(
            compact_text,
            ["offers the following key features:", "key features:"],
            ["Some typical applications", "Product Construction", "Physical Properties"],
        )
        applications_section = self._extract_section_text(
            compact_text,
            ["Some typical applications", "applications include:"],
            ["Product Construction", "Physical Properties", "Tabbing", "Performance Properties"],
        )
        feature_parts = [part.strip(" .") for part in re.split(r"\.\s+", features_section) if len(part.strip(" .")) > 8]
        application_parts = [part.strip(" .") for part in re.split(r"\.\s+", applications_section) if len(part.strip(" .")) > 8]

        payload["series"].append(
            {
                "brand_name": self.brand_id.name if self.brand_id else False,
                "series_name": series_name,
                "name": series_name,
                "product_description": description_section[:1200] or False,
                "product_features": "\n".join(feature_parts[:8]) or False,
                "main_applications": self._html_bullets(application_parts[:8]),
            }
        )

        self._ensure_candidate_param(payload, known_params, "thickness", "厚度", "float", "mm", is_main_field=True, main_field_name="thickness", spec_category_name="尺寸厚度")
        self._ensure_candidate_param(payload, known_params, "thickness_std", "厚度(标准)", "char", "um", is_main_field=True, main_field_name="thickness_std", spec_category_name="尺寸厚度")
        self._ensure_candidate_param(payload, known_params, "color", "颜色", "char", False, is_main_field=True, main_field_name="color_id", spec_category_name="基础规格")
        self._ensure_candidate_param(payload, known_params, "adhesive_type", "胶系", "char", False, is_main_field=True, main_field_name="adhesive_type_id", spec_category_name="基础规格")
        self._ensure_candidate_param(payload, known_params, "base_material", "基材", "char", False, is_main_field=True, main_field_name="base_material_id", spec_category_name="基础规格")

        item_rows = self._extract_item_rows_from_physical_properties(compact_text, series_name, guessed)
        if not item_rows:
            codes = [code for code in self._find_distinct_codes(compact_text) if code != series_name]
            for code in codes:
                thickness, thickness_std = self._extract_thickness_for_code(code, compact_text)
                item_rows.append(
                    {
                        "code": code,
                        "name": code,
                        "thickness": thickness or False,
                        "thickness_std": thickness_std or False,
                        "color_name": guessed.get("color_name"),
                        "adhesive_type_name": guessed.get("adhesive_type_name"),
                        "base_material_name": guessed.get("base_material_name"),
                    }
                )

        codes = [row["code"] for row in item_rows]
        for row in item_rows:
            payload["items"].append(
                {
                    "brand_name": self.brand_id.name if self.brand_id else False,
                    "series_name": series_name,
                    "category_name": self.categ_id.name if self.categ_id else False,
                    "code": row["code"],
                    "name": row["name"],
                    "catalog_status": "draft",
                    "thickness": row.get("thickness"),
                    "color_name": row.get("color_name"),
                    "adhesive_type_name": row.get("adhesive_type_name"),
                    "base_material_name": row.get("base_material_name"),
                }
            )
            if row.get("thickness"):
                payload["spec_values"].append({"item_code": row["code"], "param_key": "thickness", "value": row["thickness"], "unit": "mm", "review_status": "pending"})
            if row.get("thickness_std"):
                payload["spec_values"].append({"item_code": row["code"], "param_key": "thickness_std", "value": row["thickness_std"], "unit": "um", "review_status": "pending"})
            if row.get("color_name"):
                payload["spec_values"].append({"item_code": row["code"], "param_key": "color", "value": row["color_name"], "review_status": "pending"})
            if row.get("adhesive_type_name"):
                payload["spec_values"].append({"item_code": row["code"], "param_key": "adhesive_type", "value": row["adhesive_type_name"], "review_status": "pending"})
            if row.get("base_material_name"):
                payload["spec_values"].append({"item_code": row["code"], "param_key": "base_material", "value": row["base_material_name"], "review_status": "pending"})

        peel_section = self._extract_section_text(compact_text, ["180° Peel Adhesion to Painted Panel", "180 Peel Adhesion to Painted Panel"], ["Shear Strength", "Shelf Life", "Pluck Testing", "Torque Testing"])
        if peel_section and len(codes) >= 4:
            painted_section = self._extract_section_text(peel_section, ["Painted panel Immediate State"], ["PVC panel Immediate State"])
            pvc_section = self._extract_section_text(peel_section, ["PVC panel Immediate State"], ["Painted panel:", "PVC panel :", "Shear Strength", "Shelf Life"])
            peel_maps = [
                (painted_section or peel_section, "Immediate State", "peel_180_painted_immediate", "涂装板-即时状态-180度剥离力"),
                (painted_section or peel_section, "Normal State", "peel_180_painted_normal", "涂装板-常温状态-180度剥离力"),
                (painted_section or peel_section, "High Temperature", "peel_180_painted_high_temp", "涂装板-高温状态-180度剥离力"),
                (painted_section or peel_section, "Heat-aging", "peel_180_painted_heat_aging", "涂装板-热老化后-180度剥离力"),
                (painted_section or peel_section, "Warm Water Immersion", "peel_180_painted_warm_water", "涂装板-温水浸泡后-180度剥离力"),
                (pvc_section or peel_section, "Immediate State", "peel_180_pvc_immediate", "PVC板-即时状态-180度剥离力"),
                (pvc_section or peel_section, "Normal State", "peel_180_pvc_normal", "PVC板-常温状态-180度剥离力"),
                (pvc_section or peel_section, "High Temperature", "peel_180_pvc_high_temp", "PVC板-高温状态-180度剥离力"),
                (pvc_section or peel_section, "Heat-aging", "peel_180_pvc_heat_aging", "PVC板-热老化后-180度剥离力"),
                (pvc_section or peel_section, "Warm Water Immersion", "peel_180_pvc_warm_water", "PVC板-温水浸泡后-180度剥离力"),
            ]
            for section_text, label, param_key, name in peel_maps:
                values = self._extract_numeric_row_after_label(section_text, label, len(codes))
                if values:
                    self._ensure_candidate_param(payload, known_params, param_key, name, "float", "N/cm", spec_category_name="粘接性能")
                    self._append_spec_value_rows(payload, codes, param_key, values, "N/cm", "180° Peel Adhesion", label, label)

        shear_section = self._extract_section_text(compact_text, ["Shear Strength"], ["Shelf Life", "Pluck Testing", "Torque Testing", "Static Shear"])
        if shear_section and len(codes) >= 4:
            shear_maps = [
                ("Immediate State", "shear_painted_pvc_immediate", "涂装板/PVC板-即时状态-剪切强度"),
                ("Normal State", "shear_painted_pvc_normal", "涂装板/PVC板-常温状态-剪切强度"),
                ("High Temperature", "shear_painted_pvc_high_temp", "涂装板/PVC板-高温状态-剪切强度"),
                ("Warm Water Immersion", "shear_painted_pvc_warm_water", "涂装板/PVC板-温水浸泡后-剪切强度"),
                ("Gasoline Immersion", "shear_painted_pvc_gasoline", "涂装板/PVC板-汽油浸泡后-剪切强度"),
                ("Wax-remover immersion", "shear_painted_pvc_wax_remover", "涂装板/PVC板-除蜡剂浸泡后-剪切强度"),
            ]
            for label, param_key, name in shear_maps:
                values = self._extract_numeric_row_after_label(shear_section, label, len(codes))
                if values:
                    self._ensure_candidate_param(payload, known_params, param_key, name, "float", "MPa", spec_category_name="粘接性能")
                    self._append_spec_value_rows(payload, codes, param_key, values, "MPa", "Shear Strength", label, label)

        shelf_section = self._extract_section_text(compact_text, ["Shelf Life"], ["Pluck Testing", "Torque Testing", "Static Shear", "Technical Data Sheet"])
        if shelf_section:
            summary = self._extract_summary_sentence(shelf_section)
            self._ensure_candidate_param(payload, known_params, "shelf_life_storage", "保质期与储存", "char", False, spec_category_name="包装与储存")
            self._append_series_wide_rows(payload, codes, "shelf_life_storage", summary, False, "Shelf Life", False, summary[:200])

        section_params = [
            ("Pluck Testing", "Torque Testing", "pluck_testing", "拔脱测试", "测试验证"),
            ("Torque Testing", "Static Shear", "torque_testing", "扭矩测试", "测试验证"),
            ("Static Shear", "Technical Data Sheet", "static_shear_70c", "70度静态剪切", "可靠性"),
        ]
        for start, stop, param_key, name, category_name in section_params:
            section_text = self._extract_section_text(compact_text, [start], [stop])
            if not section_text:
                continue
            summary = self._extract_summary_sentence(section_text)
            method_html = self._build_method_html(name, section_text, summary)
            self._ensure_candidate_param(
                payload,
                known_params,
                param_key,
                name,
                "char" if param_key == "static_shear_70c" else "char",
                "hour" if param_key == "static_shear_70c" else False,
                spec_category_name=category_name,
                method_html=method_html,
            )
            self._append_series_wide_rows(payload, codes, param_key, summary, "hour" if param_key == "static_shear_70c" else False, name, False, summary[:200])

        extracted_param_keys = {row.get("param_key") for row in payload["spec_values"] if row.get("param_key")}
        if self.categ_id:
            for param_key in sorted(extracted_param_keys):
                param = known_params.get(param_key)
                if not param and not any(row.get("param_key") == param_key for row in payload["params"]):
                    continue
                payload["category_params"].append(
                    {
                        "category_name": self.categ_id.name,
                        "param_key": param_key,
                        "name": (param.name if param else next((row.get("name") for row in payload["params"] if row.get("param_key") == param_key), param_key)),
                        "required": False,
                        "show_in_form": True,
                        "allow_import": True,
                    }
                )

        if len(payload["items"]) < 1:
            for line in (text or "").splitlines()[:20]:
                if line and len(line) > 10:
                    payload["unmatched"].append({"excerpt": line[:300], "reason": "未能可靠识别为已知结构"})
        elif len(payload["spec_values"]) < max(len(codes) * 3, 6):
            for line in (text or "").splitlines():
                if line and len(line) > 12 and any(keyword in line for keyword in ("Testing", "Immersion", "Adhesion", "Shear", "Shelf Life")):
                    payload["unmatched"].append({"excerpt": line[:300], "reason": "识别到性能段落但未完全结构化"})
                    if len(payload["unmatched"]) >= 8:
                        break

        return self._normalize_generated_payload(payload), "heuristic-v2"

    def action_generate_draft(self):
        for record in self:
            if not record.raw_text:
                record.action_extract_source()
            if not record.raw_text:
                raise UserError("未提取到原文，无法生成草稿。")
            if record._has_openai_config():
                payload, parse_version = record._generate_draft_with_openai()
                config = record._get_ai_runtime_config()
                message = f"AI 草稿已生成。当前引擎：OpenAI / {config['model']}"
            else:
                payload, parse_version = record._generate_draft_heuristic()
                message = "未检测到 AI 配置，已使用本地增强规则生成草稿，请人工复核。"
            record._run_encoding_precheck(payload)
            record.write(
                {
                    "draft_payload": json.dumps(payload, ensure_ascii=False, indent=2),
                    "unmatched_payload": json.dumps(payload.get("unmatched") or [], ensure_ascii=False, indent=2),
                    "parse_version": parse_version,
                    "import_status": "generated",
                    "result_message": message,
                }
            )
        return True
