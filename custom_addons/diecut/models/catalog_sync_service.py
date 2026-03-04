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
            if (not changed_fields or "variant_thickness" in changed_fields) and "variant_thickness" in variant._fields:
                vals["variant_thickness"] = item.variant_thickness
            if (not changed_fields or "variant_color" in changed_fields) and "variant_color" in variant._fields:
                vals["variant_color"] = item.variant_color
            if (not changed_fields or "variant_adhesive_type" in changed_fields) and "variant_adhesive_type" in variant._fields:
                vals["variant_adhesive_type"] = item.variant_adhesive_type
            if (not changed_fields or "variant_base_material" in changed_fields) and "variant_base_material" in variant._fields:
                vals["variant_base_material"] = item.variant_base_material
            if (not changed_fields or "variant_thickness_std" in changed_fields) and "variant_thickness_std" in variant._fields:
                vals["variant_thickness_std"] = item.variant_thickness_std
            if (not changed_fields or "variant_color_std" in changed_fields) and "variant_color_std" in variant._fields:
                vals["variant_color_std"] = item.variant_color_std
            if (not changed_fields or "variant_adhesive_std" in changed_fields) and "variant_adhesive_std" in variant._fields:
                vals["variant_adhesive_std"] = item.variant_adhesive_std
            if (not changed_fields or "variant_base_material_std" in changed_fields) and "variant_base_material_std" in variant._fields:
                vals["variant_base_material_std"] = item.variant_base_material_std
            if (not changed_fields or "variant_ref_price" in changed_fields) and "variant_ref_price" in variant._fields:
                vals["variant_ref_price"] = item.variant_ref_price
            if (not changed_fields or "variant_note" in changed_fields) and "variant_note" in variant._fields:
                vals["variant_note"] = item.variant_note
            if (not changed_fields or "variant_is_rohs" in changed_fields) and "variant_is_rohs" in variant._fields:
                vals["variant_is_rohs"] = item.variant_is_rohs
            if (not changed_fields or "variant_is_reach" in changed_fields) and "variant_is_reach" in variant._fields:
                vals["variant_is_reach"] = item.variant_is_reach
            if (not changed_fields or "variant_is_halogen_free" in changed_fields) and "variant_is_halogen_free" in variant._fields:
                vals["variant_is_halogen_free"] = item.variant_is_halogen_free
            if (not changed_fields or "variant_fire_rating" in changed_fields) and "variant_fire_rating" in variant._fields:
                vals["variant_fire_rating"] = item.variant_fire_rating
            if (not changed_fields or "variant_tds_file" in changed_fields) and "variant_tds_file" in variant._fields:
                vals["variant_tds_file"] = item.variant_tds_file
            if (not changed_fields or "variant_tds_filename" in changed_fields) and "variant_tds_filename" in variant._fields:
                vals["variant_tds_filename"] = item.variant_tds_filename
            if (not changed_fields or "variant_msds_file" in changed_fields) and "variant_msds_file" in variant._fields:
                vals["variant_msds_file"] = item.variant_msds_file
            if (not changed_fields or "variant_msds_filename" in changed_fields) and "variant_msds_filename" in variant._fields:
                vals["variant_msds_filename"] = item.variant_msds_filename
            if (not changed_fields or "variant_datasheet" in changed_fields) and "variant_datasheet" in variant._fields:
                vals["variant_datasheet"] = item.variant_datasheet
            if (not changed_fields or "variant_datasheet_filename" in changed_fields) and "variant_datasheet_filename" in variant._fields:
                vals["variant_datasheet_filename"] = item.variant_datasheet_filename
            if (
                (not changed_fields or "variant_catalog_structure_image" in changed_fields)
                and "variant_catalog_structure_image" in variant._fields
            ):
                vals["variant_catalog_structure_image"] = item.variant_catalog_structure_image
            if vals:
                variant.with_context(skip_shadow_sync=True).write(vals)
