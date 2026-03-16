# -*- coding: utf-8 -*-

from odoo import api, fields, models
from odoo.exceptions import ValidationError


class DiecutCatalogSpecBulkAddWizard(models.TransientModel):
    _name = "diecut.catalog.spec.bulk.add.wizard"
    _description = "批量添加分类参数"

    categ_id = fields.Many2one("product.category", string="材料分类", required=True, readonly=True)
    spec_category_filter_id = fields.Many2one(
        "diecut.catalog.param.category",
        string="参数分类筛选",
    )
    search_term = fields.Char(string="关键字")
    available_param_ids = fields.Many2many(
        "diecut.catalog.param",
        compute="_compute_available_param_ids",
        string="可选参数",
    )
    available_param_count = fields.Integer(
        string="候选数量",
        compute="_compute_available_param_ids",
    )
    param_ids = fields.Many2many(
        "diecut.catalog.param",
        "diecut_catalog_spec_bulk_add_param_rel",
        "wizard_id",
        "param_id",
        string="待添加参数",
        domain="[('id', 'in', available_param_ids)]",
    )

    @api.depends("categ_id", "spec_category_filter_id", "search_term")
    def _compute_available_param_ids(self):
        param_model = self.env["diecut.catalog.param"].sudo()
        spec_model = self.env["diecut.catalog.spec.def"].sudo()
        for wizard in self:
            wizard.available_param_ids = [(5, 0, 0)]
            wizard.available_param_count = 0
            if not wizard.categ_id:
                continue
            domain = [("active", "=", True)]
            if wizard.spec_category_filter_id:
                domain.append(("spec_category_id", "=", wizard.spec_category_filter_id.id))
            if wizard.search_term:
                term = wizard.search_term.strip()
                if term:
                    domain.extend(
                        [
                            "|",
                            "|",
                            ("name", "ilike", term),
                            ("param_key", "ilike", term),
                            ("canonical_name_en", "ilike", term),
                        ]
                    )
            existing_param_ids = spec_model.search([("categ_id", "=", wizard.categ_id.id)]).mapped("param_id").ids
            if existing_param_ids:
                domain.append(("id", "not in", existing_param_ids))
            available_params = param_model.search(domain, order="spec_category_id, sequence, name, id")
            wizard.available_param_ids = [(6, 0, available_params.ids)]
            wizard.available_param_count = len(available_params)

    def action_apply(self):
        self.ensure_one()
        selected_params = self.param_ids
        if not selected_params:
            raise ValidationError("请至少选择一个参数后再执行批量添加。")

        spec_model = self.env["diecut.catalog.spec.def"].sudo()
        existing_configs = spec_model.search(
            [
                ("categ_id", "=", self.categ_id.id),
                ("param_id", "in", selected_params.ids),
            ]
        )
        existing_param_ids = set(existing_configs.mapped("param_id").ids)
        params_to_create = selected_params.filtered(lambda param: param.id not in existing_param_ids)

        max_sequence = 0
        current_last = spec_model.search([("categ_id", "=", self.categ_id.id)], order="sequence desc, id desc", limit=1)
        if current_last:
            max_sequence = current_last.sequence or 0

        create_vals = []
        for index, param in enumerate(params_to_create.sorted(key=lambda p: (p.sequence, p.name or "", p.id)), start=1):
            create_vals.append(
                {
                    "categ_id": self.categ_id.id,
                    "param_id": param.id,
                    "name": param.name,
                    "param_key": param.param_key,
                    "value_type": param.value_type,
                    "unit": param.unit,
                    "selection_options": param.selection_options,
                    "required": False,
                    "show_in_form": True,
                    "allow_import": True,
                    "active": True,
                    "unit_override": False,
                    "sequence": max_sequence + index * 10,
                }
            )
        if create_vals:
            spec_model.create(create_vals)

        added_count = len(create_vals)
        skipped_count = len(selected_params) - added_count
        message = f"已新增 {added_count} 条参数配置"
        if skipped_count:
            message += f"，跳过 {skipped_count} 条已存在参数"
        message += "。"
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": "批量添加完成",
                "message": message,
                "type": "success",
                "sticky": False,
                "next": {"type": "ir.actions.act_window_close"},
            },
        }
