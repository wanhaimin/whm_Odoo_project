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
            ("generate_assets", "从CSV严格同步JSON"),
            ("sync_csv_to_db", "CSV同步入库"),
            ("cutover_baseline_snapshot", "生成切换基线记录"),
            ("edit_csv", "CSV轻量编辑"),
            ("view_fields_manual", "字段维护清单"),
        ]

    operation = fields.Selection(selection="_selection_operation", string="操作", required=True)
    operator_id = fields.Many2one("res.users", string="执行人", default=lambda self: self.env.user, readonly=True)
    success = fields.Boolean(string="成功", default=True, readonly=True)
    detail = fields.Text(string="明细", readonly=True)

    read_mode = fields.Selection([("legacy_split", "旧架构"), ("new_gray", "新架构")], string="入口模式", readonly=True)
    legacy_model_count = fields.Integer(string="旧模型型号数", readonly=True)
    shadow_model_count = fields.Integer(string="新模型型号数", readonly=True)
    missing_shadow_count = fields.Integer(string="缺失影子", readonly=True)
    duplicate_brand_code_count = fields.Integer(string="重复品牌+编码组", readonly=True)
    orphan_model_count = fields.Integer(string="series_text缺失数", readonly=True)
    mapped_all_match = fields.Boolean(string="字段一致", readonly=True)
    mapped_mismatch_field_count = fields.Integer(string="字段异常数", readonly=True)
    mapped_sample_rows = fields.Integer(string="字段异常记录数", readonly=True)
    attachment_all_match = fields.Boolean(string="附件一致", readonly=True)
    attachment_mismatch_field_count = fields.Integer(string="附件异常数", readonly=True)
    attachment_sample_rows = fields.Integer(string="附件异常记录数", readonly=True)
    baseline_payload = fields.Text(string="基线JSON", readonly=True)
