# -*- coding: utf-8 -*-

from odoo import api, fields, models
from odoo.exceptions import ValidationError


class DiecutCatalogSeries(models.Model):
    _name = "diecut.catalog.series"
    _description = "材料系列模板"
    _order = "brand_id, sequence, name, id"

    _TEMPLATE_FIELDS = ("product_features", "product_description", "main_applications")

    name = fields.Char(string="系列名称", required=True, index=True)
    brand_id = fields.Many2one("diecut.brand", string="品牌", required=True, index=True)
    active = fields.Boolean(string="启用", default=True)
    sequence = fields.Integer(string="排序", default=10)
    linked_item_count = fields.Integer(string="目录条目数", readonly=True, default=0)

    product_features = fields.Text(string="产品特点模板")
    product_description = fields.Text(string="产品描述模板")
    main_applications = fields.Html(string="主要应用模板")

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

    _sql_constraints = [
        ("diecut_catalog_series_brand_name_uniq", "unique(brand_id, name)", "同一品牌下系列名称不能重复。"),
    ]

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
            if sync_name:
                vals["series_text"] = series.name or False
            linked_items.with_context(skip_series_sync=True).write(vals)

    def write(self, vals):
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

    @api.constrains("brand_id")
    def _check_brand_has_no_mismatch_items(self):
        item_model = self.env["diecut.catalog.item"].sudo()
        for series in self:
            mismatch_count = item_model.search_count(
                [("series_id", "=", series.id), ("brand_id", "!=", series.brand_id.id)]
            )
            if mismatch_count:
                raise ValidationError("检测到型号品牌与系列品牌不一致，请先修复后再保存。")
