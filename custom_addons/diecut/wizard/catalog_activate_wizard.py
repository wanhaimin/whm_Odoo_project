# -*- coding: utf-8 -*-
import re

from odoo import api, fields, models


class CatalogActivateWizard(models.TransientModel):
    _name = "diecut.catalog.activate.wizard"
    _description = "选型目录启用向导"

    catalog_item_id = fields.Many2one("diecut.catalog.item", string="源选型目录", readonly=True, required=True)

    product_name = fields.Char(string="产品名称", required=True)
    default_code = fields.Char(string="内部参考/型号")
    categ_id = fields.Many2one(
        "product.category",
        string="产品分类",
        required=True,
        domain="[('category_type', '=', 'raw')]",
    )
    brand_id = fields.Many2one("diecut.brand", string="品牌")
    material_type = fields.Char(string="材质/牌号")
    thickness = fields.Float(string="厚度 (mm)", digits=(16, 3))

    width = fields.Float(string="宽度 (mm)", digits=(16, 0))
    length = fields.Float(string="长度 (M)", digits=(16, 3))
    rs_type = fields.Selection(
        [
            ("R", "卷料"),
            ("S", "片料"),
        ],
        string="形态 (R/S)",
        default="R",
    )
    main_vendor_id = fields.Many2one(
        "res.partner",
        string="主要供应商",
        domain="[('supplier_rank', '>', 0)]",
    )
    manufacturer_id = fields.Many2one(
        "res.partner",
        string="制造商",
        domain="[('is_company', '=', True)]",
    )

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        catalog_item_id = res.get("catalog_item_id") or self.env.context.get("default_catalog_item_id")
        if not catalog_item_id:
            return res

        item = self.env["diecut.catalog.item"].browse(catalog_item_id)
        brand_name = item.brand_id.name or ""
        variant_code = item.code or ""
        base_material = item.base_material_id.name if item.base_material_id else ""
        series_short = item.series_id.name or "" if item.series_id else ""

        res["product_name"] = f"{brand_name} {variant_code} {base_material}{series_short}".strip()
        res["default_code"] = variant_code
        res["categ_id"] = item.categ_id.id if item.categ_id else False
        res["brand_id"] = item.brand_id.id if item.brand_id else False
        res["manufacturer_id"] = item.manufacturer_id.id if item.manufacturer_id else False
        res["material_type"] = base_material

        thickness_val = item.thickness_std or item.thickness
        res["thickness"] = self._parse_thickness(thickness_val)
        return res

    @staticmethod
    def _parse_thickness(thickness_str):
        if not thickness_str:
            return 0.0

        source = thickness_str.strip()
        is_mm = "mm" in source.lower() and "渭m" not in source.lower() and "um" not in source.lower()
        match = re.search(r"([\d.]+)", source)
        if not match:
            return 0.0

        value = float(match.group(1))
        if is_mm:
            return value
        if value > 10:
            return value / 1000.0
        return value

    def action_confirm(self):
        self.ensure_one()
        item = self.catalog_item_id

        self.env.cr.execute(
            "SELECT id FROM diecut_catalog_item WHERE id = %s FOR UPDATE",
            [item.id],
        )
        item = self.env["diecut.catalog.item"].browse(item.id)

        if item.erp_enabled and item.erp_product_tmpl_id:
            if self.env.context.get("from_gray_catalog_item"):
                if self.env.context.get("is_split_view_action"):
                    return {"type": "ir.actions.act_window_close", "infos": {"noReload": True}}
                return {"type": "ir.actions.client", "tag": "reload"}
            return {
                "type": "ir.actions.act_window",
                "res_model": "product.template",
                "res_id": item.erp_product_tmpl_id.id,
                "view_mode": "form",
                "target": "current",
            }

        new_product_vals = {
            "name": self.product_name,
            "default_code": self.default_code,
            "categ_id": self.categ_id.id,
            "is_raw_material": True,
            "purchase_ok": True,
            "sale_ok": False,
            "type": "consu",
            "is_storable": True,
            "thickness": self.thickness,
            "width": self.width,
            "length": self.length,
            "rs_type": self.rs_type,
            "brand_id": self.brand_id.id if self.brand_id else False,
            "manufacturer_id": self.manufacturer_id.id if self.manufacturer_id else False,
            "material_type": self.material_type,
            "density": False,
            "adhesion": False,
            "material_transparency": False,
            "tensile_strength": False,
            "tear_strength": False,
            "temp_resistance_min": False,
            "temp_resistance_max": False,
            "is_rohs": item.is_rohs,
            "is_reach": item.is_reach,
            "is_halogen_free": item.is_halogen_free,
            "fire_rating": item.fire_rating,
            "datasheet": False,
            "datasheet_filename": False,
            "application": "",
            "process_note": "",
            "main_vendor_id": self.main_vendor_id.id if self.main_vendor_id else False,
        }

        if item.color_id:
            new_product_vals["color_id"] = item.color_id.id

        new_product = self.env["product.template"].create(new_product_vals)
        item.with_context(skip_shadow_sync=True).write(
            {
                "erp_enabled": True,
                "erp_product_tmpl_id": new_product.id,
            }
        )

        if self.env.context.get("from_gray_catalog_item"):
            if self.env.context.get("is_split_view_action"):
                return {"type": "ir.actions.act_window_close", "infos": {"noReload": True}}
            return {"type": "ir.actions.client", "tag": "reload"}

        return {
            "type": "ir.actions.act_window",
            "res_model": "product.template",
            "res_id": new_product.id,
            "view_mode": "form",
            "target": "current",
        }
