# -*- coding: utf-8 -*-

from odoo import api, fields, models
from odoo.exceptions import ValidationError


class DiecutCatalogSpecDef(models.Model):
    _name = "diecut.catalog.spec.def"
    _description = "材料技术参数定义"
    _order = "categ_id, sequence, id"

    name = fields.Char(string="参数名称", required=True)
    param_key = fields.Char(string="参数键", required=True, index=True)
    categ_id = fields.Many2one("product.category", string="适用分类", required=True, index=True)
    value_type = fields.Selection(
        [
            ("char", "文本"),
            ("float", "数值"),
            ("boolean", "布尔"),
            ("selection", "枚举"),
        ],
        string="值类型",
        required=True,
        default="char",
    )
    unit = fields.Char(string="默认单位")
    selection_options = fields.Text(
        string="枚举选项",
        help="用于 selection 类型，支持按英文逗号或换行分隔。",
    )
    sequence = fields.Integer(string="排序", default=10)
    required = fields.Boolean(string="必填", default=False)
    active = fields.Boolean(string="启用", default=True)
    show_in_form = fields.Boolean(string="表单显示", default=True)
    allow_import = fields.Boolean(string="允许导入", default=True)
    line_count = fields.Integer(string="已使用条数", compute="_compute_line_count")

    _categ_param_key_uniq = models.Constraint(
        "UNIQUE(categ_id, param_key)",
        "同一分类下参数键不能重复。",
    )

    @api.depends("categ_id")
    def _compute_line_count(self):
        grouped = self.env["diecut.catalog.item.spec.line"].read_group(
            [("spec_def_id", "in", self.ids)],
            ["spec_def_id"],
            ["spec_def_id"],
        )
        counts = {item["spec_def_id"][0]: item["spec_def_id_count"] for item in grouped}
        for record in self:
            record.line_count = counts.get(record.id, 0)

    @api.constrains("param_key")
    def _check_param_key(self):
        for record in self:
            key = (record.param_key or "").strip()
            if not key:
                raise ValidationError("参数键不能为空。")
            if any(ch.isspace() for ch in key):
                raise ValidationError("参数键不能包含空白字符。")

    def get_selection_options_list(self):
        self.ensure_one()
        raw = (self.selection_options or "").replace("\r", "\n")
        values = []
        for part in raw.replace(",", "\n").split("\n"):
            item = part.strip()
            if item:
                values.append(item)
        return values


class DiecutCatalogItemSpecLine(models.Model):
    _name = "diecut.catalog.item.spec.line"
    _description = "材料技术参数值"
    _order = "sequence, id"

    catalog_item_id = fields.Many2one(
        "diecut.catalog.item",
        string="目录型号",
        required=True,
        ondelete="cascade",
        index=True,
    )
    spec_def_id = fields.Many2one(
        "diecut.catalog.spec.def",
        string="参数定义",
        required=True,
        index=True,
        domain="[('id', 'in', catalog_item_id.spec_def_domain_ids)]",
    )
    categ_id = fields.Many2one(
        "product.category",
        string="材料分类",
        related="catalog_item_id.categ_id",
        store=True,
        readonly=True,
        index=True,
    )
    sequence = fields.Integer(string="排序", default=10)
    param_key = fields.Char(string="参数键", index=True)
    param_name = fields.Char(string="参数名称")
    value_type = fields.Selection(
        related="spec_def_id.value_type",
        string="值类型",
        store=True,
        readonly=True,
    )
    value_char = fields.Char(string="文本值")
    value_float = fields.Float(string="数值")
    value_boolean = fields.Boolean(string="布尔值")
    value_selection = fields.Char(string="枚举值")
    value_text = fields.Char(
        string="参数值",
        compute="_compute_value_text",
        inverse="_inverse_value_text",
        help="统一显示和编辑参数值。",
    )
    display_value = fields.Char(string="展示值", compute="_compute_display_value")
    unit = fields.Char(string="单位")
    test_method = fields.Char(string="测试方法")
    test_condition = fields.Char(string="测试条件")
    remark = fields.Char(string="备注")

    _item_spec_def_uniq = models.Constraint(
        "UNIQUE(catalog_item_id, spec_def_id)",
        "同一型号下同一参数不能重复。",
    )

    @api.depends("value_type", "value_char", "value_float", "value_boolean", "value_selection")
    def _compute_value_text(self):
        for record in self:
            if record.value_type == "float":
                record.value_text = "" if record.value_float in (False, None) else f"{record.value_float:g}"
            elif record.value_type == "boolean":
                if record.value_boolean is True:
                    record.value_text = "是"
                elif record.value_boolean is False:
                    record.value_text = ""
                else:
                    record.value_text = ""
            elif record.value_type == "selection":
                record.value_text = record.value_selection or ""
            else:
                record.value_text = record.value_char or ""

    def _inverse_value_text(self):
        for record in self:
            raw = (record.value_text or "").strip()
            if record.value_type == "float":
                record.value_char = False
                record.value_boolean = False
                record.value_selection = False
                record.value_float = float(raw) if raw else 0.0
            elif record.value_type == "boolean":
                normalized = raw.lower()
                if not raw:
                    record.value_boolean = False
                elif normalized in ("1", "true", "yes", "y", "是"):
                    record.value_boolean = True
                elif normalized in ("0", "false", "no", "n", "否"):
                    record.value_boolean = False
                else:
                    raise ValidationError("布尔类型参数仅支持 是/否、true/false、1/0。")
                record.value_char = False
                record.value_float = 0.0
                record.value_selection = False
            elif record.value_type == "selection":
                record.value_char = False
                record.value_float = 0.0
                record.value_boolean = False
                record.value_selection = raw or False
            else:
                record.value_float = 0.0
                record.value_boolean = False
                record.value_selection = False
                record.value_char = raw or False

    @api.depends("value_text", "unit")
    def _compute_display_value(self):
        for record in self:
            value = (record.value_text or "").strip()
            unit = (record.unit or "").strip()
            record.display_value = f"{value} {unit}".strip() if value else ""

    @api.onchange("spec_def_id")
    def _onchange_spec_def_id(self):
        for record in self:
            record._sync_from_spec_def()

    def _sync_from_spec_def(self):
        self.ensure_one()
        if not self.spec_def_id:
            return
        self.sequence = self.spec_def_id.sequence
        self.param_key = self.spec_def_id.param_key
        self.param_name = self.spec_def_id.name
        if not self.unit:
            self.unit = self.spec_def_id.unit

    def _value_fields(self):
        return {
            "char": "value_char",
            "float": "value_float",
            "boolean": "value_boolean",
            "selection": "value_selection",
        }

    def _has_value(self):
        self.ensure_one()
        if self.value_type == "float":
            return self.value_float not in (False, None, 0.0) or self.value_text not in (False, "")
        if self.value_type == "boolean":
            return bool(self.value_boolean)
        if self.value_type == "selection":
            return bool((self.value_selection or "").strip())
        return bool((self.value_char or "").strip())

    @api.constrains("catalog_item_id", "spec_def_id")
    def _check_category_match(self):
        for record in self:
            if not record.spec_def_id or not record.catalog_item_id or not record.catalog_item_id.categ_id:
                continue
            category_chain = record.catalog_item_id._get_category_chain_ids(record.catalog_item_id.categ_id.id)
            if record.spec_def_id.categ_id.id not in category_chain:
                raise ValidationError("参数定义必须属于当前型号分类或其上级分类。")

    @api.constrains("value_type", "value_char", "value_float", "value_boolean", "value_selection", "spec_def_id")
    def _check_value_payload(self):
        for record in self:
            if not record.spec_def_id:
                continue
            payload = {
                "char": bool((record.value_char or "").strip()),
                "float": record.value_float not in (False, None, 0.0),
                "boolean": bool(record.value_boolean),
                "selection": bool((record.value_selection or "").strip()),
            }
            for key, has_value in payload.items():
                if key != record.value_type and has_value:
                    raise ValidationError("技术参数只能填写与值类型匹配的字段。")
            if record.value_type == "selection" and record.value_selection:
                options = record.spec_def_id.get_selection_options_list()
                if options and record.value_selection not in options:
                    raise ValidationError("枚举参数值不在定义范围内。")

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for record in records:
            record._sync_from_spec_def()
        return records

    def write(self, vals):
        res = super().write(vals)
        if "spec_def_id" in vals:
            for record in self:
                record._sync_from_spec_def()
        return res
