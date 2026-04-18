# -*- coding: utf-8 -*-

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError


class DiecutCatalogMergeWizard(models.TransientModel):
    _name = "diecut.catalog.merge.wizard"
    _description = "字典主记录合并向导"

    model_name = fields.Char(string="目标模型", required=True, readonly=True)
    model_label = fields.Char(string="模型名称", readonly=True)
    line_ids = fields.One2many("diecut.catalog.merge.wizard.line", "wizard_id", string="待合并记录")
    master_line_id = fields.Many2one(
        "diecut.catalog.merge.wizard.line",
        string="保留记录（主记录）",
        domain="[('wizard_id', '=', id)]",
    )
    record_count = fields.Integer(string="记录数", compute="_compute_record_count")
    result_message = fields.Text(string="执行结果", readonly=True)

    @api.depends("line_ids")
    def _compute_record_count(self):
        for wizard in self:
            wizard.record_count = len(wizard.line_ids)

    @api.model
    def _supported_models(self):
        return {
            "diecut.color",
            "diecut.catalog.adhesive.type",
            "diecut.catalog.base.material",
            "product.tag",
            "diecut.catalog.application.tag",
            "diecut.catalog.feature.tag",
            "diecut.catalog.substrate.tag",
            "diecut.catalog.structure.tag",
            "diecut.catalog.environment.tag",
            "diecut.catalog.process.tag",
            "diecut.catalog.param",
        }

    @api.model
    def action_open_from_context(self):
        active_model = self.env.context.get("active_model")
        active_ids = list(dict.fromkeys(self.env.context.get("active_ids") or []))
        if active_model not in self._supported_models():
            raise UserError("当前模型暂不支持主记录合并。")
        if len(active_ids) < 2:
            raise UserError("请在列表中至少勾选两条记录后再执行合并。")

        model = self.env[active_model].sudo().with_context(active_test=False)
        model._check_merge_access()
        records = model.browse(active_ids).exists()
        if len(records) != len(active_ids):
            raise UserError("所选记录中包含已失效数据，请刷新后重试。")

        wizard = self.create(
            {
                "model_name": active_model,
                "model_label": model._description or active_model,
                "line_ids": [
                    fields.Command.create(
                        {
                            "res_id": record.id,
                            "record_label": self._build_record_display_name(record),
                            "usage_summary": self._build_usage_summary(record),
                        }
                    )
                    for record in records
                ],
            }
        )
        return wizard._reload_action()

    @api.model
    def _build_usage_summary(self, record):
        if "usage_count_total" in record._fields:
            return f"引用数：{record.usage_count_total}"
        if record._name == "diecut.catalog.param":
            return f"分类配置：{record.category_config_count}；参数值：{record.line_count}"
        return "暂无直接引用"

    @api.model
    def _build_record_display_name(self, record):
        name = ""
        try:
            name = (record.name_get()[:1][0][1] if record.name_get() else "") or ""
        except Exception:
            name = ""
        name = (name or record.display_name or record.name or "").strip()
        if record._name == "diecut.catalog.param":
            key = (record.param_key or "").strip()
            if key:
                return f"{name} [{key}]"
        return name or f"{record._description or record._name}#{record.id}"

    def _reload_action(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "合并到主记录",
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
        }

    def action_execute(self):
        self.ensure_one()
        if self.record_count < 2:
            raise ValidationError("至少需要两条记录才能执行合并。")
        if not self.master_line_id:
            raise ValidationError("请先明确选择一条保留记录（主记录）。")

        master_id = self.master_line_id.res_id
        source_ids = self.line_ids.filtered(lambda line: line.id != self.master_line_id.id).mapped("res_id")
        if not source_ids:
            raise ValidationError("请至少保留一条源记录用于合并。")

        summary = (
            self.env[self.model_name]
            .sudo()
            .with_context(active_test=False)
            .merge_records(master_id=master_id, source_ids=source_ids)
        )

        moved_refs = summary.get("moved_refs", 0)
        deleted_sources = summary.get("deleted_sources", 0)
        source_names = "、".join(
            self.line_ids.filtered(lambda line: line.id != self.master_line_id.id).mapped("record_label")
        )
        extra_parts = []
        if summary.get("merged_category_configs"):
            extra_parts.append(f"分类参数配置迁移：{summary['merged_category_configs']}")
        if summary.get("moved_spec_lines"):
            extra_parts.append(f"参数值迁移：{summary['moved_spec_lines']}")
        detail = "；".join(extra_parts)
        self.result_message = (
            f"主记录：{summary.get('master_name') or self.master_line_id.record_label}\n"
            f"删除记录：{source_names or '无'}\n"
            f"迁移引用：{moved_refs}\n"
            f"删除源记录：{deleted_sources}"
            + (f"\n{detail}" if detail else "")
        )
        return self._reload_action()


class DiecutCatalogMergeWizardLine(models.TransientModel):
    _name = "diecut.catalog.merge.wizard.line"
    _description = "字典主记录合并向导行"
    _order = "id"
    _rec_name = "record_label"

    wizard_id = fields.Many2one("diecut.catalog.merge.wizard", required=True, ondelete="cascade")
    res_id = fields.Integer(string="记录ID", required=True, readonly=True)
    record_label = fields.Char(string="记录名称", readonly=True)
    usage_summary = fields.Char(string="引用摘要", readonly=True)
    action_result = fields.Char(string="操作结果", compute="_compute_action_result")

    @api.depends("wizard_id.master_line_id")
    def _compute_action_result(self):
        for line in self:
            if not line.wizard_id.master_line_id:
                line.action_result = "待定"
            elif line.wizard_id.master_line_id.id == line.id:
                line.action_result = "保留"
            else:
                line.action_result = "删除"

