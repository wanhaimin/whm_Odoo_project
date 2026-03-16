# -*- coding: utf-8 -*-

import re

from odoo import api, fields, models
from odoo.exceptions import ValidationError


class DiecutCatalogTaxonomyMixin(models.AbstractModel):
    _name = "diecut.catalog.taxonomy.mixin"
    _description = "Catalog Taxonomy Mixin"

    name = fields.Char(string="名称", required=True, index=True)
    active = fields.Boolean(string="启用", default=True)
    sequence = fields.Integer(string="排序", default=10)
    note = fields.Text(string="备注")

    _name_unique = models.Constraint("UNIQUE(name)", "名称不能重复。")

    @staticmethod
    def _normalize_name(value):
        if not value:
            return False
        text = re.sub(r"\s+", " ", str(value).strip())
        return text or False

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if "name" in vals:
                vals["name"] = self._normalize_name(vals.get("name"))
        return super().create(vals_list)

    def write(self, vals):
        if "name" in vals:
            vals["name"] = self._normalize_name(vals.get("name"))
        return super().write(vals)

    @api.constrains("name")
    def _check_name_not_empty(self):
        for record in self:
            if not record.name:
                raise ValidationError("名称不能为空。")


class DiecutCatalogTaxonomyUsageMixin(models.AbstractModel):
    _name = "diecut.catalog.taxonomy.usage.mixin"
    _description = "Catalog Taxonomy Usage Mixin"

    usage_count_total = fields.Integer(string="总使用量", default=0, readonly=True, copy=False)
    usage_count_catalog_item = fields.Integer(string="目录条目数量", default=0, readonly=True, copy=False)
    usage_count_product_template = fields.Integer(string="产品模板数量", default=0, readonly=True, copy=False)
    usage_count_other = fields.Integer(string="其他模型数量", default=0, readonly=True, copy=False)
    usage_count_breakdown = fields.Text(string="按模型统计", readonly=True, copy=False)

    @api.model
    def _usage_counter_specs(self):
        return []

    @api.model
    def _usage_alias_map(self):
        return {
            "diecut.catalog.item": "catalog_item",
            "product.template": "product_template",
        }

    @api.model
    def _build_usage_stats(self, target_ids):
        stats = {
            rec_id: {
                "total": 0,
                "catalog_item": 0,
                "product_template": 0,
                "other": 0,
                "model_counts": {},
            }
            for rec_id in target_ids
        }
        if not stats:
            return stats

        alias_map = self._usage_alias_map()
        for model_name, field_name in self._usage_counter_specs():
            if model_name not in self.env:
                continue

            groups = (
                self.env[model_name]
                .sudo()
                .with_context(active_test=False)
                .read_group(
                    [(field_name, "in", list(target_ids))],
                    [field_name],
                    [field_name],
                    lazy=False,
                )
            )
            alias = alias_map.get(model_name)
            for group in groups:
                ref_value = group.get(field_name)
                if not ref_value:
                    continue
                rec_id = ref_value[0]
                count = int(group.get("__count", 0))
                if not count or rec_id not in stats:
                    continue

                model_counts = stats[rec_id]["model_counts"]
                model_counts[model_name] = model_counts.get(model_name, 0) + count
                stats[rec_id]["total"] += count

                if alias == "catalog_item":
                    stats[rec_id]["catalog_item"] += count
                elif alias == "product_template":
                    stats[rec_id]["product_template"] += count
                else:
                    stats[rec_id]["other"] += count

        for rec_id, values in stats.items():
            lines = [f"{model_name}: {count}" for model_name, count in sorted(values["model_counts"].items())]
            values["breakdown"] = "\n".join(lines)
        return stats

    def _refresh_usage_counts(self):
        records = self.with_context(active_test=False)
        if not records:
            return True

        stats = self._build_usage_stats(records.ids)
        query = f"""
            UPDATE {self._table}
               SET usage_count_total = %s,
                   usage_count_catalog_item = %s,
                   usage_count_product_template = %s,
                   usage_count_other = %s,
                   usage_count_breakdown = %s
             WHERE id = %s
        """
        for record in records:
            values = stats.get(record.id, {})
            self.env.cr.execute(
                query,
                (
                    values.get("total", 0),
                    values.get("catalog_item", 0),
                    values.get("product_template", 0),
                    values.get("other", 0),
                    values.get("breakdown", ""),
                    record.id,
                ),
            )
        records.invalidate_recordset(
            [
                "usage_count_total",
                "usage_count_catalog_item",
                "usage_count_product_template",
                "usage_count_other",
                "usage_count_breakdown",
            ]
        )
        return True

    @api.model
    def _refresh_all_usage_counts(self):
        self.with_context(active_test=False).search([])._refresh_usage_counts()
        return True

    @api.model
    def _search_usage_count_total(self, operator_symbol, value):
        supported = {"=", "==", "!=", "<>", ">", ">=", "<", "<="}
        if operator_symbol not in supported:
            raise ValidationError("不支持的操作符，仅支持 = != > >= < <=。")

        normalized_operator = operator_symbol
        if normalized_operator == "==":
            normalized_operator = "="
        if normalized_operator == "<>":
            normalized_operator = "!="
        return [("usage_count_total", normalized_operator, int(value or 0))]

    def unlink(self):
        self._refresh_usage_counts()
        for record in self:
            if record.usage_count_total > 0:
                raise ValidationError(
                    f"【{record.display_name}】仍被引用 {record.usage_count_total} 次，不能删除。请先停用或解除引用。"
                )
        return super().unlink()


class DiecutCatalogAdhesiveType(models.Model):
    _name = "diecut.catalog.adhesive.type"
    _description = "胶系字典"
    _inherit = ["diecut.catalog.taxonomy.mixin", "diecut.catalog.taxonomy.usage.mixin"]
    _order = "sequence, name, id"

    @api.model
    def _usage_counter_specs(self):
        return [("diecut.catalog.item", "adhesive_type_id")]


class DiecutCatalogBaseMaterial(models.Model):
    _name = "diecut.catalog.base.material"
    _description = "基材字典"
    _inherit = ["diecut.catalog.taxonomy.mixin", "diecut.catalog.taxonomy.usage.mixin"]
    _order = "sequence, name, id"

    @api.model
    def _usage_counter_specs(self):
        return [("diecut.catalog.item", "base_material_id")]


class DiecutColor(models.Model):
    _name = "diecut.color"
    _inherit = ["diecut.color", "diecut.catalog.taxonomy.usage.mixin"]
    _description = "颜色字典"
    _order = "sequence, name, id"

    active = fields.Boolean(string="启用", default=True)
    sequence = fields.Integer(string="排序", default=10)
    note = fields.Text(string="备注")
    _name_unique = models.Constraint("UNIQUE(name)", "名称不能重复。")

    @api.model
    def _usage_counter_specs(self):
        return [
            ("diecut.catalog.item", "color_id"),
            ("product.template", "color_id"),
        ]

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if "name" in vals:
                vals["name"] = DiecutCatalogTaxonomyMixin._normalize_name(vals.get("name"))
        return super().create(vals_list)

    def write(self, vals):
        if "name" in vals:
            vals["name"] = DiecutCatalogTaxonomyMixin._normalize_name(vals.get("name"))
        return super().write(vals)
