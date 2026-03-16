# -*- coding: utf-8 -*-

import base64
import os
from io import BytesIO

from odoo import models


class DiecutCatalogSourceDocumentOpenClawVisionRuntime(models.Model):
    _inherit = "diecut.catalog.source.document"

    def _extract_pdf_page_images(self, payload_bytes, filename=False, max_pages=4):
        try:
            import pypdfium2 as pdfium
        except ImportError:
            return []
        pdf = pdfium.PdfDocument(payload_bytes)
        images = []
        try:
            page_count = min(len(pdf), max_pages)
            base_name = os.path.splitext(filename or "source")[0]
            for index in range(page_count):
                page = pdf[index]
                bitmap = page.render(scale=1.35)
                image = bitmap.to_pil()
                buffer = BytesIO()
                image.save(buffer, format="JPEG", quality=78, optimize=True)
                images.append(
                    {
                        "name": f"{base_name}_page_{index + 1}.jpg",
                        "data_url": "data:image/jpeg;base64,%s" % base64.b64encode(buffer.getvalue()).decode(),
                    }
                )
            return images
        finally:
            pdf.close()

    def _build_vision_messages(self, source_bytes, filename, text_excerpt):
        copilot_context = self._build_copilot_context()
        mime = "image/png"
        if (filename or "").lower().endswith(".pdf"):
            mime = "image/jpeg"
        elif "." in (filename or ""):
            import mimetypes

            mime = mimetypes.guess_type(filename or "")[0] or "image/png"
        data_url = f"data:{mime};base64,{base64.b64encode(source_bytes).decode()}"
        prompt = (
            "你是 TDS 视觉解析器。请阅读图片或 PDF 页面预览，输出严格 JSON。"
            "顶层 keys 必须为：sections, tables, charts, methods, candidate_items。"
            "sections 用于产品描述/特性/应用；tables 用于物性表和型号矩阵；"
            "charts 用于图表标题、图例、坐标轴和结论；methods 用于测试方法区块；"
            "candidate_items 用于识别到的型号/厚度候选。不要输出 JSON 以外的任何内容。"
        )
        return [
            {"role": "system", "content": prompt},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": f"原文摘录：{(text_excerpt or '')[:12000]}"},
                    {"type": "text", "text": "Copilot 上下文：\n%s" % self._render_skill_context_text(copilot_context)},
                    {"type": "image_url", "image_url": {"url": data_url}},
                ],
            },
        ]

    def _build_multi_page_vision_messages(self, source_images, text_excerpt):
        copilot_context = self._build_copilot_context()
        prompt = (
            "你是 TDS 视觉解析器。请综合阅读多页 PDF 截图，输出严格 JSON。"
            "顶层 keys 必须为：sections, tables, charts, methods, candidate_items。"
            "sections 用于产品描述/特性/应用；tables 用于物性表和型号矩阵；"
            "charts 用于图表标题、图例、坐标轴和结论；methods 用于测试方法区块；"
            "candidate_items 用于识别到的型号/厚度候选。不要输出 JSON 以外的任何内容。"
        )
        content = [
            {"type": "text", "text": f"原文摘录：{(text_excerpt or '')[:12000]}"},
            {"type": "text", "text": "Copilot 上下文：\n%s" % self._render_skill_context_text(copilot_context)},
        ]
        for source_image in source_images or []:
            content.append({"type": "image_url", "image_url": {"url": source_image["data_url"]}})
        return [{"role": "system", "content": prompt}, {"role": "user", "content": content}]

    def _generate_vision_payload(self, source_bytes=False, filename=False):
        self.ensure_one()
        if not self._has_ai_role_config("vision"):
            return {}
        payload_bytes = source_bytes
        payload_name = filename
        if not payload_bytes:
            attachment = self._get_effective_primary_attachment()
            if attachment:
                payload_bytes = self._read_attachment_bytes(attachment)
                payload_name = attachment.name
        if not payload_bytes and self.source_file:
            payload_bytes = self._decode_binary_field(self.source_file)
            payload_name = self.source_filename or self.name
        if not payload_bytes:
            return {}

        if (payload_name or "").lower().endswith(".pdf"):
            source_images = self._extract_pdf_page_images(payload_bytes, payload_name, max_pages=2)
            if source_images:
                messages = self._build_multi_page_vision_messages(source_images, self.raw_text or "")
            else:
                preview, preview_name = self._extract_pdf_preview_image(payload_bytes, payload_name)
                payload_bytes = base64.b64decode(preview or b"") if preview else payload_bytes
                payload_name = preview_name or payload_name
                messages = self._build_vision_messages(payload_bytes, payload_name, self.raw_text or "")
        else:
            messages = self._build_vision_messages(payload_bytes, payload_name, self.raw_text or "")

        content = self.with_context(diecut_ai_timeout_seconds=480)._ai_request("vision", messages, max_tokens=2200, json_mode=True)
        try:
            return self._parse_json_loose(self._strip_json_fence(content))
        except Exception:
            return {"raw": content}
