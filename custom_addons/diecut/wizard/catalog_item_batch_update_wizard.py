# -*- coding: utf-8 -*-

import json

from odoo import Command, api, fields, models
from odoo.exceptions import UserError, ValidationError


class CatalogItemBatchUpdateWizard(models.TransientModel):
    _name = "diecut.catalog.item.batch.update.wizard"
    _description = "Catalog 批量修改向导"

    target_ids = fields.Many2many("diecut.catalog.item", string="目标记录")
    target_count = fields.Integer(string="选中数量", compute="_compute_target_count")
    line_ids = fields.One2many(
        "diecut.catalog.item.batch.update.line",
        "wizard_id",
        string="待修改字段",
        copy=False,
    )

    target_categ_id = fields.Many2one("product.category", string="目标材料分类")
    categ_change_policy = fields.Selection(
        [
            ("keep_specs", "策略3：仅改分类（不兼容则拦截）"),
            ("rebuild_specs", "策略1：清空并按新分类模板重建参数"),
        ],
        string="分类变更策略",
        default="keep_specs",
        required=True,
    )

    has_incompatible = fields.Boolean(string="存在不兼容参数", readonly=True, default=False)
    incompatible_payload = fields.Text(string="不兼容处理数据", readonly=True)
    result_message = fields.Text(string="执行结果", readonly=True)

    @api.depends("target_ids")
    def _compute_target_count(self):
        for wizard in self:
            wizard.target_count = len(wizard.target_ids)

    @api.model
    def _allowed_field_names(self):
        return [
            "series_id",
            "series_text",
            "categ_id",
            "product_features",
            "product_description",
            "main_applications",
            "special_applications",
            "catalog_status",
            "thickness",
            "adhesive_thickness",
            "color_id",
            "adhesive_type_id",
            "base_material_id",
            "ref_price",
            "is_rohs",
            "is_reach",
            "is_halogen_free",
            "fire_rating",
        ]

    @api.model
    def _allowed_field_meta(self):
        item_model = self.env["diecut.catalog.item"]
        meta = {}
        for field_name in self._allowed_field_names():
            field = item_model._fields.get(field_name)
            if not field:
                continue
            if field.type not in ("char", "text", "html", "float", "boolean", "selection", "many2one"):
                continue
            selection = []
            if field.type == "selection":
                selection = list(field.selection(item_model) if callable(field.selection) else field.selection or [])
            meta[field_name] = {
                "name": field_name,
                "label": field.string or field_name,
                "type": field.type,
                "selection": selection,
                "relation": getattr(field, "comodel_name", False),
            }
        return meta

    @api.model
    def action_open_from_context(self):
        active_ids = self.env.context.get("active_ids") or []
        if not active_ids:
            raise UserError("请先在列表中勾选要批量修改的型号。")
        wizard = self.create({"target_ids": [(6, 0, active_ids)]})
        return wizard._reload_action()

    def _reload_action(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "批量修改字段",
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
        }

    def _check_series_batch_write_safety(self, update_vals, target_records=None):
        if "series_id" not in update_vals:
            return
        series = self.env["diecut.catalog.series"].browse(update_vals["series_id"])
        if not series.exists():
            raise ValidationError("所选系列不存在。")
        records = target_records or self.target_ids
        target_brands = records.mapped("brand_id")
        if len(target_brands) > 1:
            raise ValidationError("批量修改系列时，目标型号必须属于同一品牌。")
        if target_brands and target_brands[0].id != series.brand_id.id:
            raise ValidationError("所选系列与目标型号品牌不一致，无法批量更新。")

    def _parse_lines_to_update_vals(self):
        self.ensure_one()
        if not self.line_ids:
            return {}
        meta = self._allowed_field_meta()
        update_vals = {}
        for line in self.line_ids:
            field_name, has_value, value = line.to_write_pair(meta)
            if field_name in update_vals:
                raise ValidationError(f"字段重复：{line.field_label}")
            if has_value:
                update_vals[field_name] = value
        return update_vals

    def _collect_category_compatibility(self, records, target_categ):
        incompatible = []
        compatible_records = self.env["diecut.catalog.item"]
        incompatible_records = self.env["diecut.catalog.item"]
        for record in records:
            allowed_map = record._get_effective_category_param_map(target_categ.id)
            bad_lines = record.spec_line_ids.filtered(lambda line: line.param_id.id not in allowed_map)
            if bad_lines:
                incompatible_records |= record
                for line in bad_lines:
                    category_param = line.category_param_id
                    incompatible.append(
                        {
                            "item_id": record.id,
                            "item_code": record.code or record.name,
                            "param_name": line.param_name or line.param_id.name,
                            "param_key": line.param_key or line.param_id.param_key,
                            "spec_def_categ": category_param.categ_id.display_name if category_param else "未知来源",
                        }
                    )
            else:
                compatible_records |= record
        return compatible_records, incompatible_records, incompatible

    def _apply_category_change(self, records, target_categ, policy):
        records = records.exists()
        rebuilt_count = 0
        if not records:
            return rebuilt_count

        if policy == "rebuild_specs":
            for record in records:
                commands = [Command.clear()] + record._build_default_spec_line_commands(target_categ.id)
                record.with_context(allow_spec_categ_change=True, skip_spec_autofill=True).write(
                    {
                        "categ_id": target_categ.id,
                        "spec_line_ids": commands,
                    }
                )
                rebuilt_count += 1
            return rebuilt_count

        if policy == "keep_specs":
            records.with_context(allow_spec_categ_change=True, skip_spec_autofill=True).write({"categ_id": target_categ.id})
            return rebuilt_count

        raise ValidationError("不支持的分类变更策略。")

    def _sync_erp_category(self, changed_records, target_categ):
        changed_records = changed_records.exists()
        if not changed_records:
            return 0, 0
        erp_records = changed_records.filtered(lambda rec: rec.erp_enabled and rec.erp_product_tmpl_id)
        if erp_records:
            erp_records.mapped("erp_product_tmpl_id").write({"categ_id": target_categ.id})
        synced = len(erp_records)
        skipped = len(changed_records) - synced
        return synced, skipped

    def _build_result_message(
        self,
        *,
        total_count,
        success_count,
        failed_count,
        updated_field_count,
        rebuilt_count,
        erp_synced_count,
        erp_skipped_count,
        incompatible_entries=None,
        include_incompatible_hint=False,
    ):
        lines = [
            f"总目标数：{total_count}",
            f"成功数：{success_count}",
            f"失败数：{failed_count}",
            f"更新字段数：{updated_field_count}",
            f"参数重建数：{rebuilt_count}",
            f"ERP分类同步成功：{erp_synced_count}",
            f"ERP分类同步跳过：{erp_skipped_count}",
        ]
        incompatible_entries = incompatible_entries or []
        if incompatible_entries:
            lines.append("")
            lines.append(f"不兼容参数条目：{len(incompatible_entries)}")
            for entry in incompatible_entries[:20]:
                lines.append(
                    f"- 型号[{entry['item_code']}] 参数[{entry['param_name']}] "
                    f"定义分类[{entry['spec_def_categ']}] 不属于目标分类继承链"
                )
            if len(incompatible_entries) > 20:
                lines.append(f"- ... 其余 {len(incompatible_entries) - 20} 条未展示")
        if include_incompatible_hint:
            lines.append("")
            lines.append("可点击“同步更新新分类参数列表”继续处理：不兼容记录重建参数，兼容记录仅改分类。")
        return "\n".join(lines)

    def _prepare_category_change_payload(self, update_vals):
        self.ensure_one()
        update_vals = dict(update_vals or {})
        target_categ_id = self.target_categ_id.id
        if update_vals.get("categ_id"):
            target_categ_id = update_vals["categ_id"]
            update_vals.pop("categ_id", None)
        if not target_categ_id:
            return None, update_vals
        target_categ = self.env["product.category"].browse(target_categ_id)
        if not target_categ.exists():
            raise ValidationError("目标材料分类不存在。")
        return target_categ, update_vals

    def action_execute(self):
        self.ensure_one()
        if not self.target_ids:
            raise UserError("没有可更新的目标记录，请重新选择。")

        self.has_incompatible = False
        self.incompatible_payload = False

        update_vals = self._parse_lines_to_update_vals()
        target_categ, update_vals = self._prepare_category_change_payload(update_vals)
        if not target_categ and not update_vals:
            raise UserError("没有可执行的修改。留空字段不会更新，请至少填写一个值。")

        total_count = len(self.target_ids)
        success_count = total_count
        rebuilt_count = 0
        erp_synced_count = 0
        erp_skipped_count = 0

        if target_categ:
            compatible_records, incompatible_records, incompatible_entries = self._collect_category_compatibility(
                self.target_ids, target_categ
            )
            if self.categ_change_policy == "keep_specs" and incompatible_records:
                payload = {
                    "target_categ_id": target_categ.id,
                    "update_vals": update_vals,
                    "compatible_ids": compatible_records.ids,
                    "incompatible_ids": incompatible_records.ids,
                    "incompatible_entries": incompatible_entries,
                }
                self.has_incompatible = True
                self.incompatible_payload = json.dumps(payload, ensure_ascii=False)
                self.result_message = self._build_result_message(
                    total_count=total_count,
                    success_count=0,
                    failed_count=total_count,
                    updated_field_count=len(update_vals),
                    rebuilt_count=0,
                    erp_synced_count=0,
                    erp_skipped_count=0,
                    incompatible_entries=incompatible_entries,
                    include_incompatible_hint=True,
                )
                return self._reload_action()

            rebuilt_count += self._apply_category_change(self.target_ids, target_categ, self.categ_change_policy)
            erp_synced_count, erp_skipped_count = self._sync_erp_category(self.target_ids, target_categ)

        if update_vals:
            self._check_series_batch_write_safety(update_vals, target_records=self.target_ids)
            self.target_ids.write(update_vals)

        self.result_message = self._build_result_message(
            total_count=total_count,
            success_count=success_count,
            failed_count=0,
            updated_field_count=len(update_vals),
            rebuilt_count=rebuilt_count,
            erp_synced_count=erp_synced_count,
            erp_skipped_count=erp_skipped_count,
        )
        return self._reload_action()

    def action_execute_resolve_incompatible(self):
        self.ensure_one()
        if not self.has_incompatible or not self.incompatible_payload:
            raise UserError("当前没有待处理的不兼容记录。")
        try:
            payload = json.loads(self.incompatible_payload)
        except Exception as exc:
            raise UserError("不兼容处理数据无效，请重新执行批量修改。") from exc

        target_categ = self.env["product.category"].browse(payload.get("target_categ_id"))
        if not target_categ.exists():
            raise UserError("目标分类不存在，请重新执行批量修改。")

        compatible_records = self.env["diecut.catalog.item"].browse(payload.get("compatible_ids", [])).exists()
        incompatible_records = self.env["diecut.catalog.item"].browse(payload.get("incompatible_ids", [])).exists()
        update_vals = payload.get("update_vals") or {}
        total_count = len(compatible_records) + len(incompatible_records)

        rebuilt_count = 0
        rebuilt_count += self._apply_category_change(compatible_records, target_categ, "keep_specs")
        rebuilt_count += self._apply_category_change(incompatible_records, target_categ, "rebuild_specs")
        all_changed_records = compatible_records | incompatible_records
        erp_synced_count, erp_skipped_count = self._sync_erp_category(all_changed_records, target_categ)

        if update_vals:
            self._check_series_batch_write_safety(update_vals, target_records=all_changed_records)
            all_changed_records.write(update_vals)

        self.has_incompatible = False
        self.incompatible_payload = False
        self.result_message = self._build_result_message(
            total_count=total_count,
            success_count=total_count,
            failed_count=0,
            updated_field_count=len(update_vals),
            rebuilt_count=rebuilt_count,
            erp_synced_count=erp_synced_count,
            erp_skipped_count=erp_skipped_count,
        )
        return self._reload_action()


class CatalogItemBatchUpdateLine(models.TransientModel):
    _name = "diecut.catalog.item.batch.update.line"
    _description = "Catalog 批量修改明细"
    _order = "id"

    wizard_id = fields.Many2one(
        "diecut.catalog.item.batch.update.wizard",
        string="向导",
        required=True,
        ondelete="cascade",
    )
    field_name = fields.Selection(selection="_selection_field_name", string="字段", required=True)
    field_label = fields.Char(string="字段名称", compute="_compute_field_meta")
    field_type = fields.Char(string="字段类型", compute="_compute_field_meta")

    value_char = fields.Char(string="文本值")
    value_text = fields.Text(string="长文本值")
    value_float = fields.Char(string="数值")
    value_categ_id = fields.Many2one("product.category", string="产品分类")
    value_series_id = fields.Many2one("diecut.catalog.series", string="系列")
    value_color_id = fields.Many2one("diecut.color", string="颜色")
    value_adhesive_type_id = fields.Many2one("diecut.catalog.adhesive.type", string="胶系")
    value_base_material_id = fields.Many2one("diecut.catalog.base.material", string="基材")
    value_boolean = fields.Selection(
        [("true", "是"), ("false", "否")],
        string="布尔值",
    )
    value_selection = fields.Selection(selection="_selection_value_selection", string="枚举值")

    _uniq_field_per_wizard = models.Constraint(
        "unique(wizard_id, field_name)",
        "同一字段不能重复添加。",
    )

    @api.model
    def _selection_field_name(self):
        meta = self.env["diecut.catalog.item.batch.update.wizard"]._allowed_field_meta()
        return [(name, item["label"]) for name, item in meta.items()]

    @api.model
    def _selection_value_selection(self):
        meta = self.env["diecut.catalog.item.batch.update.wizard"]._allowed_field_meta()
        result = []
        seen = set()
        for item in meta.values():
            if item["type"] != "selection":
                continue
            for key, label in item.get("selection", []):
                if key in seen:
                    continue
                seen.add(key)
                result.append((key, label))
        return result

    @api.depends("field_name")
    def _compute_field_meta(self):
        meta = self.env["diecut.catalog.item.batch.update.wizard"]._allowed_field_meta()
        for line in self:
            field_meta = meta.get(line.field_name or "")
            line.field_label = field_meta["label"] if field_meta else False
            line.field_type = field_meta["type"] if field_meta else False

    @api.onchange("field_name")
    def _onchange_field_name_reset_values(self):
        for line in self:
            line.value_char = False
            line.value_text = False
            line.value_float = False
            line.value_categ_id = False
            line.value_series_id = False
            line.value_color_id = False
            line.value_adhesive_type_id = False
            line.value_base_material_id = False
            line.value_boolean = False
            line.value_selection = False

    @api.constrains("field_name")
    def _check_field_name_whitelist(self):
        meta = self.env["diecut.catalog.item.batch.update.wizard"]._allowed_field_meta()
        for line in self:
            if line.field_name and line.field_name not in meta:
                raise ValidationError("字段不在批量修改白名单中。")

    def to_write_pair(self, meta):
        self.ensure_one()
        field_name = self.field_name
        field_meta = meta.get(field_name)
        if not field_meta:
            raise ValidationError(f"字段不允许批量修改：{field_name}")

        field_type = field_meta["type"]
        if field_type == "char":
            value = (self.value_char or "").strip()
            return field_name, bool(value), value
        if field_type == "text":
            value = (self.value_text or "").strip()
            return field_name, bool(value), value
        if field_type == "html":
            value = (self.value_text or "").strip()
            return field_name, bool(value), value
        if field_type == "float":
            raw = (self.value_float or "").strip()
            if not raw:
                return field_name, False, 0.0
            try:
                return field_name, True, float(raw)
            except Exception as exc:
                raise ValidationError(f"字段 {field_meta['label']} 的数值格式非法：{raw}") from exc
        if field_type == "boolean":
            if not self.value_boolean:
                return field_name, False, False
            return field_name, True, self.value_boolean == "true"
        if field_type == "selection":
            value = self.value_selection
            if not value:
                return field_name, False, False
            allowed = {key for key, _label in field_meta.get("selection", [])}
            if value not in allowed:
                raise ValidationError(f"字段 {field_meta['label']} 的枚举值非法。")
            return field_name, True, value
        if field_type == "many2one":
            if field_name == "categ_id":
                if not self.value_categ_id:
                    return field_name, False, False
                return field_name, True, self.value_categ_id.id
            if field_name == "series_id":
                if not self.value_series_id:
                    return field_name, False, False
                return field_name, True, self.value_series_id.id
            if field_name == "color_id":
                if not self.value_color_id:
                    return field_name, False, False
                return field_name, True, self.value_color_id.id
            if field_name == "adhesive_type_id":
                if not self.value_adhesive_type_id:
                    return field_name, False, False
                return field_name, True, self.value_adhesive_type_id.id
            if field_name == "base_material_id":
                if not self.value_base_material_id:
                    return field_name, False, False
                return field_name, True, self.value_base_material_id.id
            raise ValidationError(f"字段 {field_meta['label']} 暂不支持当前关联类型批量修改。")

        raise ValidationError(f"暂不支持的字段类型：{field_type}")
