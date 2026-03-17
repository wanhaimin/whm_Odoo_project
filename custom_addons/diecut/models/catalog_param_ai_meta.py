# -*- coding: utf-8 -*-

from odoo import fields, models


class DiecutCatalogParamAiMeta(models.Model):
    _inherit = "diecut.catalog.param"

    target_bucket = fields.Selection(
        [
            ("items", "型号主字段"),
            ("series", "系列主字段"),
            ("spec_values", "参数值"),
            ("notes", "说明/备注"),
        ],
        string="目标桶",
        default="spec_values",
    )
    target_field = fields.Char(string="目标字段")
    scope_hint = fields.Selection(
        [
            ("item", "item"),
            ("series", "series"),
            ("both", "both"),
        ],
        string="范围提示",
        default="item",
    )
    section_hints = fields.Char(string="章节提示")
    extraction_priority = fields.Integer(string="提取优先级", default=50)
    llm_enabled = fields.Boolean(string="LLM可提取", default=True)
    is_note_field = fields.Boolean(string="说明型参数", default=False)
    is_method_field = fields.Boolean(string="方法型参数", default=False)
    is_numeric_preferred = fields.Boolean(string="优先数值", default=False)
    allow_series_fallback = fields.Boolean(string="允许系列回退", default=False)
    confidence_rule = fields.Char(string="置信度规则")
