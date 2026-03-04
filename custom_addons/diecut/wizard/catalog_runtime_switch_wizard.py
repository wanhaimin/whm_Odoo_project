# -*- coding: utf-8 -*-

from odoo import api, fields, models


class CatalogRuntimeSwitchWizard(models.TransientModel):
    _name = "diecut.catalog.runtime.switch.wizard"
    _description = "目录统一入口切换"

    read_mode = fields.Selection(
        [("legacy_split", "旧架构分栏"), ("new_gray", "新架构灰度")],
        string="统一入口模式",
        required=True,
    )

    @api.model
    def default_get(self, fields_list):
        vals = super().default_get(fields_list)
        vals["read_mode"] = self.env["diecut.catalog.runtime.service"].get_read_mode()
        return vals

    def action_apply(self):
        self.ensure_one()
        self.env["diecut.catalog.runtime.service"].set_read_mode(self.read_mode)
        return {
            "type": "ir.actions.act_window",
            "name": "目录统一入口切换",
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
        }

    def action_open_entry(self):
        self.ensure_one()
        return self.env["diecut.catalog.runtime.service"].action_open_catalog_entry()
