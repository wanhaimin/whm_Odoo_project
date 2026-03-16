# -*- coding: utf-8 -*-

from odoo import api, fields, models


class ProductCategoryCatalogParam(models.Model):
    _inherit = "product.category"

    category_param_ids = fields.One2many(
        "diecut.catalog.spec.def",
        "categ_id",
        string="分类参数配置",
    )
    category_param_count = fields.Integer(
        string="参数配置数",
        compute="_compute_category_param_count",
    )

    @api.depends("category_param_ids")
    def _compute_category_param_count(self):
        for record in self:
            record.category_param_count = len(record.category_param_ids)

    def action_open_category_param_bulk_wizard(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "批量添加分类参数",
            "res_model": "diecut.catalog.spec.bulk.add.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_categ_id": self.id,
            },
        }

    def action_open_category_param_overview(self):
        self.ensure_one()
        action = self.env.ref("diecut.action_diecut_catalog_spec_def").read()[0]
        action["domain"] = [("categ_id", "=", self.id)]
        action["context"] = {
            "default_categ_id": self.id,
            "search_default_group_categ": 0,
        }
        return action


class DiecutCatalogSpecDef(models.Model):
    _inherit = "diecut.catalog.spec.def"

    @api.onchange("param_id")
    def _onchange_param_id_prefill_fields(self):
        for record in self:
            record._sync_from_param_definition()

    def _sync_from_param_definition(self):
        self.ensure_one()
        if not self.param_id:
            return
        self.name = self.param_id.name
        self.param_key = self.param_id.param_key
        self.value_type = self.param_id.value_type
        self.unit = self.param_id.unit
        self.selection_options = self.param_id.selection_options

    @api.model_create_multi
    def create(self, vals_list):
        vals_list = [self._prepare_prefilled_vals(vals) for vals in vals_list]
        return super().create(vals_list)

    def write(self, vals):
        vals = self._prepare_prefilled_vals(vals, current_record=self[:1])
        return super().write(vals)

    @api.model
    def _prepare_prefilled_vals(self, vals, current_record=None):
        prepared = dict(vals or {})
        param_id = prepared.get("param_id") or (current_record.param_id.id if current_record and current_record.param_id else False)
        if not param_id:
            return prepared
        param = self.env["diecut.catalog.param"].browse(param_id)
        if not prepared.get("name"):
            prepared["name"] = param.name
        if not prepared.get("param_key"):
            prepared["param_key"] = param.param_key
        if not prepared.get("value_type"):
            prepared["value_type"] = param.value_type
        if "unit" not in prepared:
            prepared["unit"] = param.unit
        if "selection_options" not in prepared:
            prepared["selection_options"] = param.selection_options
        return prepared
