# -*- coding: utf-8 -*-
from odoo import api, fields, models


class CatalogOpsLog(models.Model):
    _name = "diecut.catalog.ops.log"
    _description = "数据运维日志"
    _order = "id desc"

    @api.model
    def _selection_operation(self):
        return [
            ("export_csv", "导出CSV"),
            ("generate_assets", "从CSV生成JSON/XML"),
            ("sync_csv_to_db", "CSV同步入库"),
            ("import_xml", "导入指定XML"),
            ("cleanup_xml", "清理未匹配品牌XML"),
            ("edit_csv", "CSV轻量编辑"),
        ]

    operation = fields.Selection(
        selection="_selection_operation",
        string="操作",
        required=True,
    )
    operator_id = fields.Many2one("res.users", string="执行人", default=lambda self: self.env.user, readonly=True)
    success = fields.Boolean(string="成功", default=True, readonly=True)
    detail = fields.Text(string="明细", readonly=True)

