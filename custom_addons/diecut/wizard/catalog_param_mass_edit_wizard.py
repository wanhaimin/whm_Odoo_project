# -*- coding: utf-8 -*-

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError


class CatalogParamMassEditWizard(models.TransientModel):
    _name = "diecut.catalog.param.mass.edit.wizard"
    _description = "参数字典批量处理向导"

    param_id = fields.Many2one("diecut.catalog.param", string="参数字典", required=True, readonly=True)
    target_ids = fields.Many2many("diecut.catalog.item", string="目标型号", readonly=True)
    target_count = fields.Integer(string="选中数量", compute="_compute_target_count")
    operation = fields.Selection(
        [
            ("remove", "批量删除该参数"),
            ("add", "批量添加该参数"),
        ],
        string="操作",
        required=True,
        default="remove",
    )
    result_message = fields.Text(string="执行结果", readonly=True)

    @api.depends("target_ids")
    def _compute_target_count(self):
        for wizard in self:
            wizard.target_count = len(wizard.target_ids)

    @api.model
    def action_open_from_context(self):
        active_ids = self.env.context.get("active_ids") or []
        param_id = self.env.context.get("current_param_id")
        if not active_ids:
            raise UserError("请先在列表中勾选要处理的型号。")
        if not param_id:
            raise UserError("请先从参数字典打开“引用型号”列表，再执行批量处理。")
        param = self.env["diecut.catalog.param"].browse(param_id)
        if not param.exists():
            raise UserError("当前参数不存在，请重新进入。")
        if param.is_main_field:
            raise UserError("主字段参数请通过材料字段批量修改，不支持通过参数行入口批量增删。")
        wizard = self.create(
            {
                "param_id": param.id,
                "target_ids": [(6, 0, active_ids)],
            }
        )
        return wizard._reload_action()

    def _reload_action(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "批量处理参数",
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
        }

    def _check_param_supported(self):
        self.ensure_one()
        if self.param_id.is_main_field:
            raise ValidationError("主字段参数不支持通过参数行入口批量增删。")

    def _build_add_summary(self, added_count, existing_count, incompatible_items):
        lines = [
            f"目标型号数：{self.target_count}",
            f"新增成功：{added_count}",
            f"已存在跳过：{existing_count}",
            f"不兼容跳过：{len(incompatible_items)}",
        ]
        if incompatible_items:
            lines.append("")
            lines.append("以下型号因材料分类不允许该参数，未添加：")
            for item in incompatible_items[:20]:
                lines.append(f"- {item.code or item.name}")
            if len(incompatible_items) > 20:
                lines.append(f"- 其余 {len(incompatible_items) - 20} 个型号未展示")
        return "\n".join(lines)

    def _build_remove_summary(self, removed_count, missing_count):
        return "\n".join(
            [
                f"目标型号数：{self.target_count}",
                f"删除成功：{removed_count}",
                f"未找到该参数：{missing_count}",
            ]
        )

    def action_execute(self):
        self.ensure_one()
        self._check_param_supported()
        if not self.target_ids:
            raise UserError("没有可处理的目标型号，请重新选择。")

        line_model = self.env["diecut.catalog.item.spec.line"].sudo()
        param = self.param_id.sudo()

        if self.operation == "remove":
            lines = line_model.search(
                [
                    ("catalog_item_id", "in", self.target_ids.ids),
                    ("param_id", "=", param.id),
                ]
            )
            removed_count = len(lines)
            if lines:
                lines.unlink()
            missing_count = self.target_count - removed_count
            self.result_message = self._build_remove_summary(removed_count, missing_count)
        else:
            existing_item_ids = set(
                line_model.search(
                    [
                        ("catalog_item_id", "in", self.target_ids.ids),
                        ("param_id", "=", param.id),
                    ]
                ).mapped("catalog_item_id").ids
            )
            create_vals = []
            incompatible_items = []
            existing_count = 0
            for item in self.target_ids.sudo():
                if item.id in existing_item_ids:
                    existing_count += 1
                    continue
                if not item.categ_id:
                    incompatible_items.append(item)
                    continue
                allowed_map = item._get_effective_category_param_map(item.categ_id.id)
                if param.id not in allowed_map:
                    incompatible_items.append(item)
                    continue
                create_vals.append(
                    {
                        "catalog_item_id": item.id,
                        "param_id": param.id,
                    }
                )
            if create_vals:
                line_model.create(create_vals)
            self.result_message = self._build_add_summary(
                added_count=len(create_vals),
                existing_count=existing_count,
                incompatible_items=incompatible_items,
            )

        self.env["diecut.catalog.param"].sudo().browse(param.id)._refresh_usage_counts()
        self.env["diecut.catalog.spec.def"].sudo()._refresh_line_count()
        return self._reload_action()
