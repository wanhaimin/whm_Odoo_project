# -*- coding: utf-8 -*-

from odoo import api, models
from odoo.exceptions import ValidationError


class DiecutCatalogRuntimeService(models.AbstractModel):
    _name = "diecut.catalog.runtime.service"
    _description = "目录运行时路由服务"

    PARAM_KEY = "diecut.catalog.read_model"

    @api.model
    def get_read_mode(self):
        mode = (self.env["ir.config_parameter"].sudo().get_param(self.PARAM_KEY) or "legacy_split").strip()
        if mode not in ("legacy_split", "new_gray"):
            mode = "legacy_split"
        return mode

    @api.model
    def set_read_mode(self, mode):
        if mode not in ("legacy_split", "new_gray"):
            raise ValidationError("无效的目录读取模式。")
        self.env["ir.config_parameter"].sudo().set_param(self.PARAM_KEY, mode)

    @api.model
    def action_open_catalog_entry(self):
        mode = self.get_read_mode()
        if mode == "new_gray":
            return self.env.ref("diecut.action_diecut_catalog_item_gray").read()[0]
        return self.env.ref("diecut.action_material_catalog_variant_split").read()[0]
