# -*- coding: utf-8 -*-

from odoo import api, fields, models
from odoo.exceptions import ValidationError


class DiecutKbCitation(models.Model):
    _name = "diecut.kb.citation"
    _description = "Wiki 来源引用"
    _order = "article_id, page_ref, id"

    article_id = fields.Many2one(
        "diecut.kb.article",
        string="Wiki 页面",
        required=True,
        index=True,
        ondelete="cascade",
    )
    source_document_id = fields.Many2one(
        "diecut.catalog.source.document",
        string="来源资料",
        index=True,
        ondelete="set null",
    )
    source_attachment_id = fields.Many2one("ir.attachment", string="来源附件", ondelete="set null")
    claim_text = fields.Text(string="知识断言", required=True)
    page_ref = fields.Char(string="来源页码")
    excerpt = fields.Text(string="来源片段")
    confidence = fields.Float(string="置信度", default=0.6)
    state = fields.Selection(
        [
            ("valid", "有效"),
            ("review", "待复核"),
            ("conflict", "冲突"),
        ],
        string="状态",
        default="valid",
        index=True,
    )

    @api.constrains("confidence")
    def _check_confidence(self):
        for record in self:
            if record.confidence < 0 or record.confidence > 1:
                raise ValidationError("引用置信度必须在 0 到 1 之间。")
