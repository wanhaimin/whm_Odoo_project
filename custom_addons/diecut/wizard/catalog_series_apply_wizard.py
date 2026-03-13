# -*- coding: utf-8 -*-

from odoo import fields, models
from odoo.exceptions import UserError


class DiecutCatalogSeriesApplyWizard(models.TransientModel):
    _name = "diecut.catalog.series.apply.wizard"
    _description = "应用系列模板"

    catalog_item_id = fields.Many2one("diecut.catalog.item", string="型号", required=True, ondelete="cascade")
    apply_mode = fields.Selection(
        [("fill_empty", "仅填空"), ("overwrite", "覆盖全部")],
        string="应用方式",
        default="fill_empty",
        required=True,
    )

    def action_apply(self):
        self.ensure_one()
        item = self.catalog_item_id
        if not item or not item.exists():
            raise UserError("目标型号不存在。")
        item.action_apply_series_template(self.apply_mode)
        return {"type": "ir.actions.act_window_close"}
