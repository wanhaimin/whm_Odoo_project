# -*- coding: utf-8 -*-

import base64
import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class DiecutKbAttachment(models.Model):
    _name = "diecut.kb.attachment"
    _description = "知识库附件"
    _order = "article_id, sequence, id"

    name = fields.Char(string="名称", required=True)
    sequence = fields.Integer(string="排序", default=10)
    article_id = fields.Many2one(
        "diecut.kb.article",
        string="所属文章",
        required=True,
        index=True,
        ondelete="cascade",
    )

    file_data = fields.Binary(string="文件", attachment=True, required=True)
    file_name = fields.Char(string="文件名")
    mimetype = fields.Char(string="文件类型")
    file_size = fields.Integer(string="文件大小(字节)", readonly=True)

    attachment_kind = fields.Selection(
        [
            ("pdf", "PDF 文档"),
            ("image", "图片"),
            ("drawing", "工程图纸"),
            ("video", "视频"),
            ("other", "其他"),
        ],
        string="附件类型",
        default="other",
    )

    parse_state = fields.Selection(
        [
            ("pending", "待解析"),
            ("parsing", "解析中"),
            ("parsed", "已解析"),
            ("failed", "解析失败"),
            ("skipped", "已跳过"),
        ],
        string="解析状态",
        default="pending",
        index=True,
    )
    needs_ocr = fields.Boolean(string="需要 OCR", default=False)
    parsed_text = fields.Text(string="提取文本", help="PDF/OCR 后提取出来的纯文本，用于灌入 Dify。")
    parsed_markdown = fields.Text(string="提取 Markdown", help="带页码标记的 markdown 形态，便于人工预览和导入正文。")
    parse_method = fields.Selection(
        [
            ("pdfplumber", "PDF 文本层"),
            ("ocr_paddle", "PaddleOCR"),
            ("ocr_tesseract", "Tesseract"),
            ("manual", "手工录入"),
            ("skipped", "未解析"),
        ],
        string="解析方式",
        readonly=True,
    )
    page_count = fields.Integer(string="页数", readonly=True)
    parse_error = fields.Text(string="解析错误", readonly=True)
    parsed_at = fields.Datetime(string="解析时间", readonly=True)

    description = fields.Text(string="说明")

    @api.onchange("file_name")
    def _onchange_file_name(self):
        for record in self:
            name = (record.file_name or "").lower()
            if not name:
                continue
            if name.endswith(".pdf"):
                record.attachment_kind = "pdf"
            elif name.endswith((".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp")):
                record.attachment_kind = "image"
            elif name.endswith((".dwg", ".dxf", ".step", ".stp", ".iges")):
                record.attachment_kind = "drawing"
            elif name.endswith((".mp4", ".mov", ".avi", ".mkv")):
                record.attachment_kind = "video"
            else:
                record.attachment_kind = "other"
            if not record.name:
                record.name = record.file_name

    def action_mark_skipped(self):
        self.write({"parse_state": "skipped"})
        return True

    def action_request_parse(self):
        self.write({
            "parse_state": "pending",
            "parse_error": False,
        })
        return True

    def action_extract_text(self):
        """立即解析（PDF/图片）。"""
        from ..services import pdf_extractor as extractor

        ok_count, fail_count = 0, 0
        for record in self:
            if record.parse_state == "parsing":
                continue
            if not record.file_data:
                record._mark_parse_failed("文件为空")
                fail_count += 1
                continue
            record.write({"parse_state": "parsing", "parse_error": False})
            try:
                file_bytes = base64.b64decode(record.file_data)
            except Exception as exc:
                record._mark_parse_failed(f"附件解码失败：{exc}")
                fail_count += 1
                continue

            try:
                if record.attachment_kind == "pdf" or (record.file_name or "").lower().endswith(".pdf"):
                    result = extractor.extract_pdf_text(file_bytes)
                elif record.attachment_kind == "image":
                    result = extractor.extract_image_text(file_bytes)
                else:
                    record._mark_parse_failed(f"不支持解析此类型：{record.attachment_kind}")
                    fail_count += 1
                    continue
            except Exception as exc:
                _logger.exception("PDF/图片解析异常")
                record._mark_parse_failed(f"解析异常：{exc}")
                fail_count += 1
                continue

            if result.get("ok"):
                record.write({
                    "parse_state": "parsed",
                    "parsed_text": result.get("text") or "",
                    "parsed_markdown": result.get("markdown") or "",
                    "parse_method": result.get("method") or "skipped",
                    "page_count": result.get("page_count") or 0,
                    "needs_ocr": False,
                    "parse_error": False,
                    "parsed_at": fields.Datetime.now(),
                })
                ok_count += 1
            else:
                record.write({
                    "parse_state": "failed",
                    "parsed_text": result.get("text") or "",
                    "parsed_markdown": result.get("markdown") or "",
                    "parse_method": result.get("method") or "skipped",
                    "page_count": result.get("page_count") or 0,
                    "needs_ocr": bool(result.get("needs_ocr")),
                    "parse_error": (result.get("error") or "")[:2000],
                    "parsed_at": fields.Datetime.now(),
                })
                fail_count += 1
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": "附件解析",
                "message": f"成功 {ok_count} 个 / 失败 {fail_count} 个",
                "type": "success" if fail_count == 0 else "warning",
                "sticky": False,
                "next": {"type": "ir.actions.act_window_close"},
            },
        }

    def _mark_parse_failed(self, message: str):
        self.write({
            "parse_state": "failed",
            "parse_error": (message or "")[:2000],
            "parsed_at": fields.Datetime.now(),
        })

    @api.model
    def cron_extract_pending_attachments(self):
        """定时扫 pending 附件自动解析（默认禁用）。"""
        limit = int(
            self.env["ir.config_parameter"].sudo().get_param(
                "diecut_knowledge.attachment_batch_limit", default="10"
            ) or 10
        )
        targets = self.search(
            [("parse_state", "=", "pending"), ("file_data", "!=", False)],
            limit=limit,
            order="create_date asc, id asc",
        )
        if targets:
            targets.action_extract_text()
        return {"processed": len(targets)}
