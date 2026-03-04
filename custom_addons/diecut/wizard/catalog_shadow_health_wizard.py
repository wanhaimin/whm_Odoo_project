# -*- coding: utf-8 -*-

from odoo import api, fields, models


class CatalogShadowHealthWizard(models.TransientModel):
    _name = "diecut.catalog.shadow.health.wizard"
    _description = "新架构影子健康检查"

    legacy_model_count = fields.Integer(string="旧模型型号数", readonly=True)
    shadow_model_count = fields.Integer(string="新模型型号数", readonly=True)
    missing_shadow_count = fields.Integer(string="缺失影子记录", readonly=True)
    duplicate_brand_code_count = fields.Integer(string="品牌+编码重复组", readonly=True)
    orphan_model_count = fields.Integer(string="孤儿型号(无父系列)", readonly=True)

    @api.model
    def default_get(self, fields_list):
        vals = super().default_get(fields_list)
        vals.update(self._get_report_vals())
        return vals

    @api.model
    def _get_report_vals(self):
        report = self.env["diecut.catalog.shadow.service"].shadow_reconcile_report()
        return {
            "legacy_model_count": report["legacy_model_count"],
            "shadow_model_count": report["shadow_model_count"],
            "missing_shadow_count": report["missing_shadow_count"],
            "duplicate_brand_code_count": report["duplicate_brand_code_count"],
            "orphan_model_count": report["orphan_model_count"],
        }

    def action_refresh(self):
        self.ensure_one()
        self.write(self._get_report_vals())
        return {
            "type": "ir.actions.act_window",
            "name": "新架构影子健康检查",
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
        }

    def action_open_integrity_issues(self):
        self.ensure_one()
        action = self.env.ref("diecut.action_diecut_catalog_item_gray").read()[0]
        action["name"] = "新架构条目（结构异常）"
        action["domain"] = ["|", ("is_orphan", "=", True), ("is_duplicate_key", "=", True)]
        action["context"] = {
            "search_default_filter_level_model": 1,
            "search_default_filter_integrity_issue": 1,
        }
        return action
