# -*- coding: utf-8 -*-

from odoo import api, models


class DiecutCatalogSyncService(models.AbstractModel):
    _name = "diecut.catalog.sync.service"
    _description = "新旧目录双写同步服务"

    @api.model
    def sync_items_to_legacy(self, items, changed_fields=None):
        items = items.exists()
        if not items:
            return
        for item in items:
            self._sync_single_item_to_legacy(item, changed_fields=changed_fields)

    @api.model
    def _sync_single_item_to_legacy(self, item, changed_fields=None):
        changed_fields = set(changed_fields or [])
        if item.item_level == "series" and item.legacy_tmpl_id:
            vals = {}
            if not changed_fields or "name" in changed_fields:
                vals["series_name"] = item.name
            if (not changed_fields or "categ_id" in changed_fields) and "categ_id" in item.legacy_tmpl_id._fields:
                vals["categ_id"] = item.categ_id.id
            if (not changed_fields or "catalog_status" in changed_fields) and "catalog_status" in item.legacy_tmpl_id._fields:
                vals["catalog_status"] = item.catalog_status
            if (not changed_fields or "brand_id" in changed_fields) and "brand_id" in item.legacy_tmpl_id._fields:
                vals["brand_id"] = item.brand_id.id
            if vals:
                item.legacy_tmpl_id.with_context(skip_shadow_sync=True).write(vals)
            return

        if item.item_level == "model" and item.legacy_variant_id:
            variant = item.legacy_variant_id
            vals = {}
            if not changed_fields or "code" in changed_fields:
                vals["default_code"] = item.code
            if not changed_fields or "name" in changed_fields:
                vals["name"] = item.name
            if (not changed_fields or "catalog_status" in changed_fields) and "catalog_status" in variant._fields:
                vals["catalog_status"] = item.catalog_status
            if (not changed_fields or "erp_enabled" in changed_fields) and "is_activated" in variant._fields:
                vals["is_activated"] = item.erp_enabled
            if (
                (not changed_fields or "erp_product_tmpl_id" in changed_fields)
                and "activated_product_tmpl_id" in variant._fields
            ):
                vals["activated_product_tmpl_id"] = item.erp_product_tmpl_id.id
            if (not changed_fields or "brand_id" in changed_fields) and "catalog_brand_id" in variant._fields:
                vals["catalog_brand_id"] = item.brand_id.id
            if (not changed_fields or "categ_id" in changed_fields) and "catalog_categ_id" in variant._fields:
                vals["catalog_categ_id"] = item.categ_id.id
            if vals:
                variant.with_context(skip_shadow_sync=True).write(vals)
