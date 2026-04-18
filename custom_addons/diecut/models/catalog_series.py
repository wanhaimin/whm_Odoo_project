# -*- coding: utf-8 -*-

from odoo import api, fields, models
from odoo.exceptions import ValidationError


class DiecutCatalogSeries(models.Model):
    _name = "diecut.catalog.series"
    _description = "材料系列模板"
    _order = "brand_id, sequence, name, id"

    _TEMPLATE_FIELDS = ("product_features", "product_description", "main_applications")
    _SERIES_TAG_ALIAS_MAP = {
        "function_tag_ids": "default_function_tag_ids",
        "application_tag_ids": "default_application_tag_ids",
        "feature_tag_ids": "default_feature_tag_ids",
    }

    name = fields.Char(string="系列名称", required=True, index=True)
    brand_id = fields.Many2one("diecut.brand", string="品牌", required=True, index=True)
    active = fields.Boolean(string="启用", default=True)
    sequence = fields.Integer(string="排序", default=10)
    linked_item_count = fields.Integer(string="目录条目数", readonly=True, default=0)
    selection_priority = fields.Integer(string="选型优先级", default=10)

    product_features = fields.Text(string="产品特点模板")
    product_description = fields.Text(string="产品描述模板")
    main_applications = fields.Html(string="主要应用模板")
    brand_platform_id = fields.Many2one(
        "diecut.catalog.brand.platform",
        string="品牌平台",
        domain="[('brand_id', '=', brand_id)]",
        index=True,
    )
    default_scene_ids = fields.Many2many(
        "diecut.catalog.selection.scene",
        "diecut_catalog_series_scene_rel",
        "series_id",
        "scene_id",
        string="默认场景",
    )

    default_function_tag_ids = fields.Many2many(
        "product.tag",
        "diecut_catalog_series_function_tag_rel",
        "series_id",
        "tag_id",
        string="默认功能标签",
    )
    default_application_tag_ids = fields.Many2many(
        "diecut.catalog.application.tag",
        "diecut_catalog_series_application_tag_rel",
        "series_id",
        "tag_id",
        string="默认应用标签",
    )
    default_feature_tag_ids = fields.Many2many(
        "diecut.catalog.feature.tag",
        "diecut_catalog_series_feature_tag_rel",
        "series_id",
        "tag_id",
        string="默认特性标签",
    )

    # Compatibility alias: series is now the main maintenance entry.
    function_tag_ids = fields.Many2many(
        "product.tag",
        string="功能标签",
        compute="_compute_series_tag_aliases",
        inverse="_inverse_series_tag_aliases",
    )
    application_tag_ids = fields.Many2many(
        "diecut.catalog.application.tag",
        string="应用标签",
        compute="_compute_series_tag_aliases",
        inverse="_inverse_series_tag_aliases",
    )
    feature_tag_ids = fields.Many2many(
        "diecut.catalog.feature.tag",
        string="特性标签",
        compute="_compute_series_tag_aliases",
        inverse="_inverse_series_tag_aliases",
    )

    default_substrate_tag_ids = fields.Many2many(
        "diecut.catalog.substrate.tag",
        "diecut_catalog_series_substrate_tag_rel",
        "series_id",
        "tag_id",
        string="默认被粘物标签",
    )
    default_structure_tag_ids = fields.Many2many(
        "diecut.catalog.structure.tag",
        "diecut_catalog_series_structure_tag_rel",
        "series_id",
        "tag_id",
        string="默认结构标签",
    )
    default_environment_tag_ids = fields.Many2many(
        "diecut.catalog.environment.tag",
        "diecut_catalog_series_environment_tag_rel",
        "series_id",
        "tag_id",
        string="默认环境标签",
    )
    default_process_tag_ids = fields.Many2many(
        "diecut.catalog.process.tag",
        "diecut_catalog_series_process_tag_rel",
        "series_id",
        "tag_id",
        string="默认工艺标签",
    )

    _sql_constraints = [
        ("diecut_catalog_series_brand_name_uniq", "unique(brand_id, name)", "同一品牌下系列名称不能重复。"),
    ]

    @api.depends("default_function_tag_ids", "default_application_tag_ids", "default_feature_tag_ids")
    def _compute_series_tag_aliases(self):
        for record in self:
            record.function_tag_ids = record.default_function_tag_ids
            record.application_tag_ids = record.default_application_tag_ids
            record.feature_tag_ids = record.default_feature_tag_ids

    def _inverse_series_tag_aliases(self):
        for record in self:
            record.default_function_tag_ids = record.function_tag_ids
            record.default_application_tag_ids = record.application_tag_ids
            record.default_feature_tag_ids = record.feature_tag_ids

    @classmethod
    def _normalize_series_tag_alias_vals(cls, vals):
        normalized = dict(vals or {})
        for alias_field, storage_field in cls._SERIES_TAG_ALIAS_MAP.items():
            if alias_field in normalized and storage_field not in normalized:
                normalized[storage_field] = normalized.pop(alias_field)
        return normalized

    def _refresh_usage_counts(self):
        if not self:
            return
        self.env.cr.execute(
            """
            UPDATE diecut_catalog_series
               SET linked_item_count = 0
             WHERE id = ANY(%s)
            """,
            (list(self.ids),),
        )
        self.env.cr.execute(
            """
            UPDATE diecut_catalog_series series
               SET linked_item_count = counts.cnt
              FROM (
                    SELECT series_id, COUNT(*) AS cnt
                      FROM diecut_catalog_item
                     WHERE series_id = ANY(%s)
                     GROUP BY series_id
                   ) counts
             WHERE series.id = counts.series_id
            """,
            (list(self.ids),),
        )

    @api.model
    def _refresh_all_usage_counts(self):
        self.with_context(active_test=False).search([])._refresh_usage_counts()
        return True

    def _sync_items_from_series(self, sync_name=False):
        item_model = self.env["diecut.catalog.item"].sudo()
        for series in self:
            linked_items = item_model.search([("series_id", "=", series.id)])
            if not linked_items:
                continue
            vals = {
                "product_features": series.product_features or False,
                "product_description": series.product_description or False,
                "main_applications": series.main_applications or False,
            }
            linked_items.with_context(skip_series_sync=True).write(vals)

    def write(self, vals):
        vals = self._normalize_series_tag_alias_vals(vals)
        if "brand_id" in vals:
            target_brand_id = vals.get("brand_id")
            item_model = self.env["diecut.catalog.item"].sudo()
            for series in self:
                has_linked_items = bool(item_model.search_count([("series_id", "=", series.id)]))
                if series.brand_id.id != target_brand_id and has_linked_items:
                    raise ValidationError("该系列已被型号引用，不能直接修改品牌。请先解除引用后再修改。")

        result = super().write(vals)

        should_sync_template = bool(set(self._TEMPLATE_FIELDS).intersection(vals.keys()))
        should_sync_name = "name" in vals
        if should_sync_template or should_sync_name:
            self._sync_items_from_series(sync_name=should_sync_name)
        return result

    @api.model_create_multi
    def create(self, vals_list):
        vals_list = [self._normalize_series_tag_alias_vals(vals) for vals in vals_list]
        return super().create(vals_list)

    @api.constrains("brand_id")
    def _check_brand_has_no_mismatch_items(self):
        item_model = self.env["diecut.catalog.item"].sudo()
        for series in self:
            mismatch_count = item_model.search_count(
                [("series_id", "=", series.id), ("brand_id", "!=", series.brand_id.id)]
            )
            if mismatch_count:
                raise ValidationError("检测到型号品牌与系列品牌不一致，请先修复后再保存。")

    @api.constrains("brand_id", "brand_platform_id")
    def _check_brand_platform_brand_match(self):
        return True
