# -*- coding: utf-8 -*-

from odoo import api, fields, models
from odoo.exceptions import ValidationError


class DiecutKbWikiLink(models.Model):
    _name = "diecut.kb.wiki.link"
    _description = "Wiki 图谱关联"
    _order = "confidence desc, write_date desc, id desc"

    active = fields.Boolean(string="启用", default=True)
    source_article_id = fields.Many2one(
        "diecut.kb.article",
        string="来源 Wiki",
        required=True,
        index=True,
        ondelete="cascade",
    )
    target_article_id = fields.Many2one(
        "diecut.kb.article",
        string="目标 Wiki",
        required=True,
        index=True,
        ondelete="cascade",
    )
    link_type = fields.Selection(
        [
            ("mentions", "提到"),
            ("same_brand", "同品牌"),
            ("same_material", "同材料体系"),
            ("same_application", "同应用场景"),
            ("same_process", "同工艺问题"),
            ("compares_with", "对比关系"),
            ("depends_on", "依赖基础知识"),
            ("contradicts", "存在冲突"),
            ("updates", "更新旧结论"),
        ],
        string="关联类型",
        required=True,
        default="mentions",
        index=True,
    )
    anchor_text = fields.Char(string="锚文本")
    reason = fields.Text(string="关联原因")
    confidence = fields.Float(string="置信度", default=0.6)
    source_document_id = fields.Many2one(
        "diecut.catalog.source.document",
        string="来源资料",
        index=True,
        ondelete="set null",
    )
    created_by_compile_id = fields.Many2one(
        "diecut.kb.compile.job",
        string="编译任务",
        index=True,
        ondelete="set null",
    )

    @api.constrains("source_article_id", "target_article_id")
    def _check_not_self_link(self):
        for record in self:
            if record.source_article_id == record.target_article_id:
                raise ValidationError("Wiki 图谱关联不能指向自身。")

    @api.constrains("confidence")
    def _check_confidence(self):
        for record in self:
            if record.confidence < 0 or record.confidence > 1:
                raise ValidationError("关联置信度必须在 0 到 1 之间。")

    @api.model_create_multi
    def create(self, vals_list):
        clean_vals = []
        for vals in vals_list:
            source_id = vals.get("source_article_id")
            target_id = vals.get("target_article_id")
            link_type = vals.get("link_type") or "mentions"
            if source_id and target_id:
                existing = self.search(
                    [
                        ("source_article_id", "=", source_id),
                        ("target_article_id", "=", target_id),
                        ("link_type", "=", link_type),
                    ],
                    limit=1,
                )
                if existing:
                    update_vals = {
                        key: value
                        for key, value in vals.items()
                        if key in {"anchor_text", "reason", "confidence", "source_document_id", "active"} and value
                    }
                    if update_vals:
                        existing.write(update_vals)
                    continue
            clean_vals.append(vals)
        return super().create(clean_vals) if clean_vals else self.browse()
