# -*- coding: utf-8 -*-

import base64
import html
import json
import os

from odoo import api, fields, models
from odoo.exceptions import UserError


class DiecutCatalogSourceDocument(models.Model):
    _inherit = "diecut.catalog.source.document"

    matched_catalog_item_id = fields.Many2one(
        "diecut.catalog.item",
        string="Matched Catalog Item",
        readonly=True,
        copy=False,
        index=True,
    )
    chatter_ai_trace_id = fields.Char(string="OpenClaw Trace ID", readonly=True, copy=False, index=True)
    chatter_ai_external_source_platform = fields.Char(string="External Source Platform", readonly=True, copy=False)
    chatter_ai_external_document_type = fields.Char(string="External Document Type", readonly=True, copy=False)

    def _openclaw_import_secret_is_valid(self, token):
        config = self.env["chatter.ai.run"].sudo()._config()
        secret = config.get("worker_shared_secret")
        return bool(secret and token and token == secret)

    def _normalize_external_document_type(self, document_type):
        value = (document_type or "").strip().lower()
        if value in ("tds", "tech", "technical", "technical_datasheet", "technical-data-sheet"):
            return "tds"
        if value in ("msds", "sds", "safety", "safety_datasheet"):
            return "msds"
        if value in ("sgs", "report", "test_report"):
            return "sgs"
        if value in ("datasheet", "data_sheet", "spec", "specification"):
            return "datasheet"
        return "datasheet"

    def _content_field_by_document_type(self, document_type):
        normalized = self._normalize_external_document_type(document_type)
        if normalized == "tds":
            return "tds_content"
        if normalized == "msds":
            return "msds_content"
        return "datasheet_content"

    def _source_type_for_import_payload(self, payload):
        filename = (payload.get("source_filename") or "").lower()
        if payload.get("source_url") and not payload.get("source_file_base64"):
            return "url"
        if filename.endswith(".pdf"):
            return "pdf"
        if filename.endswith((".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif", ".tif", ".tiff")):
            return "ocr"
        return "manual"

    def _decode_import_file(self, item):
        item = item or {}
        if item.get("datas"):
            return base64.b64decode(item["datas"])
        if item.get("content_base64"):
            return base64.b64decode(item["content_base64"])
        if item.get("base64"):
            return base64.b64decode(item["base64"])
        path = item.get("path")
        if path and os.path.exists(path):
            with open(path, "rb") as handle:
                return handle.read()
        return False

    def _prepare_generated_file_rows(self, payload):
        rows = []
        source_name = payload.get("source_filename") or payload.get("filename") or False
        source_file = payload.get("source_file") or {}
        source_file_base64 = payload.get("source_file_base64")
        if source_file_base64 or source_file.get("datas") or source_file.get("content_base64") or source_file.get("path"):
            rows.append(
                {
                    "name": source_file.get("name") or source_name or "source-file",
                    "mimetype": source_file.get("mimetype") or payload.get("source_mimetype") or "application/octet-stream",
                    "datas": source_file.get("datas") or source_file.get("content_base64") or source_file_base64,
                    "path": source_file.get("path"),
                    "is_primary": True,
                }
            )
        for item in payload.get("generated_files") or []:
            if not isinstance(item, dict):
                continue
            rows.append(
                {
                    "name": item.get("name") or os.path.basename(item.get("path") or "") or "generated-file",
                    "mimetype": item.get("mimetype") or "application/octet-stream",
                    "datas": item.get("datas") or item.get("content_base64") or item.get("base64"),
                    "path": item.get("path"),
                    "is_primary": False,
                }
            )
        return rows

    def _create_import_attachments(self, payload):
        self.ensure_one()
        attachments = self.env["ir.attachment"]
        primary_attachment = self.env["ir.attachment"]
        for item in self._prepare_generated_file_rows(payload):
            raw = self._decode_import_file(item)
            if not raw:
                continue
            attachment = self.env["ir.attachment"].sudo().create(
                {
                    "name": item.get("name") or "attachment",
                    "datas": base64.b64encode(raw),
                    "mimetype": item.get("mimetype") or "application/octet-stream",
                    "res_model": self._name,
                    "res_id": self.id,
                    "type": "binary",
                }
            )
            attachments |= attachment
            if item.get("is_primary") and not primary_attachment:
                primary_attachment = attachment
        if primary_attachment:
            self.write({"primary_attachment_id": primary_attachment.id})
        return attachments, primary_attachment

    def _render_import_content_html(self, payload):
        html_value = payload.get("content_html")
        if html_value:
            return html_value
        raw_text = payload.get("raw_text") or ""
        if raw_text:
            return "<pre>%s</pre>" % html.escape(raw_text)
        return False

    def _serialize_import_json(self, value, default):
        if value in (False, None, ""):
            return json.dumps(default, ensure_ascii=False, indent=2)
        if isinstance(value, str):
            try:
                loaded = json.loads(value)
            except Exception:
                return value
            return json.dumps(loaded, ensure_ascii=False, indent=2)
        return json.dumps(value, ensure_ascii=False, indent=2)

    @api.model
    def import_openclaw_material_update(self, payload):
        payload = payload or {}
        brand_name = payload.get("brand") or payload.get("brand_name")
        material_code = (payload.get("material_code") or payload.get("code") or "").strip()
        if not brand_name or not material_code:
            raise UserError("brand and material_code are required.")

        brand = self._resolve_brand(brand_name)
        if not brand:
            raise UserError("Unable to resolve brand: %s" % brand_name)

        item_model = self.env["diecut.catalog.item"].sudo().with_context(active_test=False)
        matched_items = item_model.search([("brand_id", "=", brand.id), ("code", "=", material_code)])
        conflict = len(matched_items) > 1
        matched = len(matched_items) == 1
        matched_item = matched_items[:1]
        document_type = self._normalize_external_document_type(payload.get("document_type"))
        content_field = self._content_field_by_document_type(document_type)
        content_html = self._render_import_content_html(payload)
        title = (
            payload.get("title")
            or payload.get("name")
            or "%s %s %s" % (brand.display_name, material_code, document_type.upper())
        )
        raw_text = payload.get("raw_text") or False
        draft_payload = self._serialize_import_json(payload.get("draft_payload"), {})
        unmatched_payload = self._serialize_import_json(payload.get("unmatched_payload"), [])
        import_status = "generated" if json.loads(draft_payload or "{}") else ("extracted" if raw_text else "draft")
        parse_version = payload.get("parse_version") or "openclaw-import-update"
        source_doc = self.sudo().with_context(tracking_disable=True, mail_create_nolog=True).create(
            {
                "name": title,
                "source_type": self._source_type_for_import_payload(payload),
                "source_url": payload.get("source_url") or False,
                "source_filename": payload.get("source_filename") or payload.get("filename") or False,
                "brand_id": brand.id,
                "categ_id": matched_item.categ_id.id if matched_item and matched_item.categ_id else False,
                "raw_text": raw_text,
                "parse_version": parse_version,
                "import_status": import_status,
                "draft_payload": draft_payload,
                "unmatched_payload": unmatched_payload,
                "result_message": payload.get("summary") or payload.get("reply_text") or False,
                "matched_catalog_item_id": matched_item.id if matched_item else False,
                "chatter_ai_trace_id": payload.get("trace_id") or payload.get("run_id") or False,
                "chatter_ai_external_source_platform": payload.get("source_platform") or "openclaw",
                "chatter_ai_external_document_type": document_type,
            }
        )
        attachments, _primary = source_doc._create_import_attachments(payload)
        if raw_text and not attachments.filtered(lambda att: (att.name or "").lower().endswith(".txt")):
            txt_attachment = self.env["ir.attachment"].sudo().create(
                {
                    "name": "%s_raw_text.txt" % material_code,
                    "datas": base64.b64encode((raw_text or "").encode("utf-8")),
                    "mimetype": "text/plain",
                    "res_model": source_doc._name,
                    "res_id": source_doc.id,
                    "type": "binary",
                }
            )
            attachments |= txt_attachment
        updated_fields = []
        if matched and content_html:
            matched_item.sudo().write({content_field: content_html})
            updated_fields.append(content_field)
        if matched:
            updated_fields.extend(
                [
                    "source_document.raw_text",
                    "source_document.draft_payload",
                    "source_document.unmatched_payload",
                ]
            )
        elif conflict:
            source_doc.write(
                {
                    "result_message": "Matched multiple catalog items for %s %s. No catalog content was updated."
                    % (brand.display_name, material_code)
                }
            )
        else:
            source_doc.write(
                {
                    "result_message": "No existing catalog item matched %s %s. No catalog content was updated."
                    % (brand.display_name, material_code)
                }
            )
        source_doc.message_post(
            body=(
                "<p><strong>OpenClaw import pilot</strong></p>"
                "<p>Brand: %s</p><p>Code: %s</p><p>Document type: %s</p>"
                "<p>Matched existing item: %s</p><p>Conflict: %s</p>"
                % (
                    html.escape(brand.display_name or ""),
                    html.escape(material_code),
                    html.escape(document_type),
                    "yes" if matched else "no",
                    "yes" if conflict else "no",
                )
            ),
            attachment_ids=attachments.ids,
            message_type="comment",
            subtype_xmlid="mail.mt_note",
        )
        return {
            "matched": matched,
            "conflict": conflict,
            "catalog_item_id": matched_item.id if matched else False,
            "source_document_id": source_doc.id,
            "updated_fields": updated_fields,
            "document_type": document_type,
        }
