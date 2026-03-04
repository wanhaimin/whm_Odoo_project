# -*- coding: utf-8 -*-

import logging

from odoo import api, models


_logger = logging.getLogger(__name__)


class DiecutCatalogShadowService(models.AbstractModel):
    _name = "diecut.catalog.shadow.service"
    _description = "新架构影子迁移服务"

    _MODEL_FIELD_MAP = [
        ("name", "name"),
        ("code", "default_code"),
        ("catalog_status", "catalog_status"),
        ("brand_id", "catalog_brand_id"),
        ("categ_id", "catalog_categ_id"),
        ("erp_enabled", "is_activated"),
        ("erp_product_tmpl_id", "activated_product_tmpl_id"),
        ("variant_thickness", "variant_thickness"),
        ("variant_color", "variant_color"),
        ("variant_adhesive_type", "variant_adhesive_type"),
        ("variant_base_material", "variant_base_material"),
        ("variant_thickness_std", "variant_thickness_std"),
        ("variant_color_std", "variant_color_std"),
        ("variant_adhesive_std", "variant_adhesive_std"),
        ("variant_base_material_std", "variant_base_material_std"),
        ("variant_ref_price", "variant_ref_price"),
        ("variant_note", "variant_note"),
        ("variant_is_rohs", "variant_is_rohs"),
        ("variant_is_reach", "variant_is_reach"),
        ("variant_is_halogen_free", "variant_is_halogen_free"),
        ("variant_fire_rating", "variant_fire_rating"),
    ]
    _ATTACHMENT_FIELD_MAP = [
        ("variant_tds_file", "variant_tds_file", "binary"),
        ("variant_tds_filename", "variant_tds_filename", "char"),
        ("variant_msds_file", "variant_msds_file", "binary"),
        ("variant_msds_filename", "variant_msds_filename", "char"),
        ("variant_datasheet", "variant_datasheet", "binary"),
        ("variant_datasheet_filename", "variant_datasheet_filename", "char"),
        ("variant_catalog_structure_image", "variant_catalog_structure_image", "binary"),
    ]

    @api.model
    def _legacy_series_code(self, template):
        xml_map = template.get_external_id() if template else {}
        xml_full = xml_map.get(template.id) if template else None
        if xml_full and "." in xml_full:
            return xml_full.split(".", 1)[1].upper()
        if template and template.series_name:
            return template.series_name.strip().upper().replace(" ", "_")
        if template and template.name:
            return template.name.strip().upper().replace(" ", "_")
        return f"LEGACY_{template.id if template else 0}"

    @api.model
    def _get_or_create_default_series(self, catalog_model, brand):
        series = catalog_model.search(
            [
                ("item_level", "=", "series"),
                ("brand_id", "=", brand.id),
                ("is_system_default_series", "=", True),
            ],
            limit=1,
        )
        if series:
            return series
        return catalog_model.create(
            {
                "item_level": "series",
                "name": "未分系列",
                "brand_id": brand.id,
                "series_code": "DEFAULT",
                "is_system_default_series": True,
                "catalog_status": "draft",
                "sequence": 9999,
            }
        )

    @api.model
    def shadow_backfill_from_legacy(self, dry_run=False, limit=None):
        catalog_model = self.env["diecut.catalog.item"].with_context(skip_shadow_sync=True)
        domain = [("product_tmpl_id.is_catalog", "=", True)]
        variants = self.env["product.product"].search(domain, limit=limit)
        series_cache = {}
        stats = {
            "total_variants": len(variants),
            "series_upserted": 0,
            "models_upserted": 0,
            "models_skipped_no_code": 0,
            "models_skipped_no_brand": 0,
            "errors": 0,
        }

        for variant in variants:
            template = variant.product_tmpl_id
            brand = variant.catalog_brand_id or template.brand_id
            if not brand:
                stats["models_skipped_no_brand"] += 1
                continue

            series_name = (template.series_name or "").strip()
            if series_name:
                series_key = ("legacy", template.id)
                if series_key not in series_cache:
                    series = catalog_model.search(
                        [
                            ("item_level", "=", "series"),
                            ("legacy_tmpl_id", "=", template.id),
                        ],
                        limit=1,
                    )
                    series_vals = {
                        "item_level": "series",
                        "name": series_name,
                        "brand_id": brand.id,
                        "categ_id": template.categ_id.id,
                        "series_code": self._legacy_series_code(template),
                        "catalog_status": template.catalog_status or "draft",
                        "legacy_tmpl_id": template.id,
                        "is_system_default_series": False,
                    }
                    if not dry_run:
                        try:
                            if series:
                                series.write(series_vals)
                            else:
                                series = catalog_model.create(series_vals)
                            stats["series_upserted"] += 1
                        except Exception as exc:
                            stats["errors"] += 1
                            _logger.warning("[CatalogShadowService] 系列回填失败 tmpl=%s err=%s", template.id, exc)
                            continue
                    else:
                        stats["series_upserted"] += 1
                        if not series:
                            series = catalog_model.new(series_vals)
                    series_cache[series_key] = series
                series = series_cache[series_key]
            else:
                series_key = ("default", brand.id)
                if series_key not in series_cache:
                    if not dry_run:
                        try:
                            series = self._get_or_create_default_series(catalog_model, brand)
                            stats["series_upserted"] += 1
                        except Exception as exc:
                            stats["errors"] += 1
                            _logger.warning("[CatalogShadowService] 默认系列回填失败 brand=%s err=%s", brand.id, exc)
                            continue
                    else:
                        series = catalog_model.search(
                            [
                                ("item_level", "=", "series"),
                                ("brand_id", "=", brand.id),
                                ("is_system_default_series", "=", True),
                            ],
                            limit=1,
                        )
                        stats["series_upserted"] += 1
                        if not series:
                            series = catalog_model.new(
                                {
                                    "item_level": "series",
                                    "name": "未分系列",
                                    "brand_id": brand.id,
                                    "series_code": "DEFAULT",
                                    "is_system_default_series": True,
                                    "catalog_status": "draft",
                                    "sequence": 9999,
                                }
                            )
                    series_cache[series_key] = series
                series = series_cache[series_key]

            code = (variant.default_code or "").strip()
            if not code:
                stats["models_skipped_no_code"] += 1
                continue

            model_vals = {
                "item_level": "model",
                "name": variant.name or code,
                "brand_id": brand.id,
                "categ_id": (variant.catalog_categ_id or template.categ_id).id,
                "code": code,
                "parent_id": getattr(series, "id", False),
                "catalog_status": variant.catalog_status or template.catalog_status or "draft",
                "legacy_tmpl_id": template.id,
                "legacy_variant_id": variant.id,
                "erp_enabled": bool(variant.is_activated),
                "erp_product_tmpl_id": variant.activated_product_tmpl_id.id,
                "variant_thickness": variant.variant_thickness,
                "variant_color": variant.variant_color,
                "variant_adhesive_type": variant.variant_adhesive_type,
                "variant_base_material": variant.variant_base_material,
                "variant_thickness_std": variant.variant_thickness_std,
                "variant_color_std": variant.variant_color_std,
                "variant_adhesive_std": variant.variant_adhesive_std,
                "variant_base_material_std": variant.variant_base_material_std,
                "variant_ref_price": variant.variant_ref_price,
                "variant_note": variant.variant_note,
                "variant_is_rohs": variant.variant_is_rohs,
                "variant_is_reach": variant.variant_is_reach,
                "variant_is_halogen_free": variant.variant_is_halogen_free,
                "variant_fire_rating": variant.variant_fire_rating,
                "variant_tds_file": variant.variant_tds_file,
                "variant_tds_filename": variant.variant_tds_filename,
                "variant_msds_file": variant.variant_msds_file,
                "variant_msds_filename": variant.variant_msds_filename,
                "variant_datasheet": variant.variant_datasheet,
                "variant_datasheet_filename": variant.variant_datasheet_filename,
                "variant_catalog_structure_image": variant.variant_catalog_structure_image,
            }

            if dry_run:
                stats["models_upserted"] += 1
                continue

            model_rec = catalog_model.search(
                [
                    ("item_level", "=", "model"),
                    ("legacy_variant_id", "=", variant.id),
                ],
                limit=1,
            )
            try:
                if model_rec:
                    model_rec.write(model_vals)
                else:
                    catalog_model.create(model_vals)
                stats["models_upserted"] += 1
            except Exception as exc:
                stats["errors"] += 1
                _logger.warning("[CatalogShadowService] 型号回填失败 variant=%s err=%s", variant.id, exc)

        return stats

    @api.model
    def get_duplicate_model_ids(self):
        self.env.cr.execute(
            """
            SELECT dci.id
            FROM diecut_catalog_item dci
            JOIN (
                SELECT brand_id, lower(trim(code)) AS key_code
                FROM diecut_catalog_item
                WHERE item_level = 'model' AND code IS NOT NULL AND trim(code) <> ''
                GROUP BY brand_id, lower(trim(code))
                HAVING COUNT(*) > 1
            ) dup
                ON dup.brand_id = dci.brand_id
               AND dup.key_code = lower(trim(dci.code))
            WHERE dci.item_level = 'model' AND dci.code IS NOT NULL AND trim(dci.code) <> ''
            """
        )
        return [row[0] for row in self.env.cr.fetchall()]

    @api.model
    def shadow_reconcile_report(self):
        catalog_model = self.env["diecut.catalog.item"]
        legacy_model_count = self.env["product.product"].search_count([("product_tmpl_id.is_catalog", "=", True)])
        shadow_model_count = catalog_model.search_count([("item_level", "=", "model")])

        self.env.cr.execute(
            """
            SELECT COUNT(1)
            FROM product_product pp
            JOIN product_template pt ON pt.id = pp.product_tmpl_id
            WHERE pt.is_catalog = TRUE
              AND NOT EXISTS (
                  SELECT 1
                  FROM diecut_catalog_item dci
                  WHERE dci.item_level = 'model' AND dci.legacy_variant_id = pp.id
              )
            """
        )
        missing_shadow_count = self.env.cr.fetchone()[0]

        self.env.cr.execute(
            """
            SELECT COUNT(1)
            FROM (
                SELECT brand_id, lower(trim(code)) AS k, count(*)
                FROM diecut_catalog_item
                WHERE item_level = 'model' AND code IS NOT NULL AND trim(code) <> ''
                GROUP BY brand_id, lower(trim(code))
                HAVING count(*) > 1
            ) t
            """
        )
        duplicate_brand_code_count = self.env.cr.fetchone()[0]

        orphan_model_count = catalog_model.search_count([("item_level", "=", "model"), ("parent_id", "=", False)])

        return {
            "legacy_model_count": legacy_model_count,
            "shadow_model_count": shadow_model_count,
            "missing_shadow_count": missing_shadow_count,
            "duplicate_brand_code_count": duplicate_brand_code_count,
            "orphan_model_count": orphan_model_count,
        }

    @api.model
    def compare_mapped_fields(self, limit=None, sample_size=20):
        domain = [("item_level", "=", "model"), ("legacy_variant_id", "!=", False)]
        items = self.env["diecut.catalog.item"].search(domain, limit=limit)
        mismatch_counts = {}
        samples = []
        mismatch_rows = 0

        for item in items:
            variant = item.legacy_variant_id
            row_mismatch = {}
            for item_field, legacy_field in self._MODEL_FIELD_MAP:
                if legacy_field not in variant._fields:
                    continue
                left = item[item_field]
                right = variant[legacy_field]

                left_norm = self._normalize_compare_value(left)
                right_norm = self._normalize_compare_value(right)

                if item_field == "variant_ref_price":
                    left_norm = round(float(left_norm or 0.0), 4)
                    right_norm = round(float(right_norm or 0.0), 4)

                if left_norm != right_norm:
                    mismatch_counts[item_field] = mismatch_counts.get(item_field, 0) + 1
                    row_mismatch[item_field] = {"new": left_norm, "legacy": right_norm}

            if row_mismatch and len(samples) < sample_size:
                mismatch_rows += 1
                samples.append(
                    {
                        "item_id": item.id,
                        "legacy_variant_id": variant.id,
                        "code": item.code,
                        "mismatches": row_mismatch,
                    }
                )
            elif row_mismatch:
                mismatch_rows += 1

        total = len(items)
        return {
            "total_checked": total,
            "mismatch_field_count": len(mismatch_counts),
            "mismatch_counts": mismatch_counts,
            "sample_mismatches": samples,
            "all_match": not bool(mismatch_counts),
            "sample_size": sample_size,
            "limit": limit,
            "mapping_fields": [f[0] for f in self._MODEL_FIELD_MAP],
            "sample_rows": mismatch_rows,
        }

    @api.model
    def compare_attachment_fields(self, limit=None, sample_size=20):
        domain = [("item_level", "=", "model"), ("legacy_variant_id", "!=", False)]
        items = self.env["diecut.catalog.item"].search(domain, limit=limit)
        mismatch_counts = {}
        samples = []
        mismatch_rows = 0

        for item in items:
            variant = item.legacy_variant_id
            row_mismatch = {}
            for item_field, legacy_field, field_kind in self._ATTACHMENT_FIELD_MAP:
                if legacy_field not in variant._fields:
                    continue
                left = item[item_field]
                right = variant[legacy_field]

                if field_kind == "binary":
                    left_norm = bool(left)
                    right_norm = bool(right)
                else:
                    left_norm = self._normalize_compare_value(left)
                    right_norm = self._normalize_compare_value(right)

                if left_norm != right_norm:
                    mismatch_counts[item_field] = mismatch_counts.get(item_field, 0) + 1
                    row_mismatch[item_field] = {"new": left_norm, "legacy": right_norm}

            if row_mismatch and len(samples) < sample_size:
                mismatch_rows += 1
                samples.append(
                    {
                        "item_id": item.id,
                        "legacy_variant_id": variant.id,
                        "code": item.code,
                        "mismatches": row_mismatch,
                    }
                )
            elif row_mismatch:
                mismatch_rows += 1

        return {
            "total_checked": len(items),
            "mismatch_field_count": len(mismatch_counts),
            "mismatch_counts": mismatch_counts,
            "sample_mismatches": samples,
            "all_match": not bool(mismatch_counts),
            "sample_size": sample_size,
            "limit": limit,
            "mapping_fields": [f[0] for f in self._ATTACHMENT_FIELD_MAP],
            "sample_rows": mismatch_rows,
        }

    @api.model
    def refresh_model_fields_from_legacy(self, limit=None):
        domain = [("item_level", "=", "model"), ("legacy_variant_id", "!=", False)]
        items = self.env["diecut.catalog.item"].search(domain, limit=limit)
        updated = 0
        for item in items:
            variant = item.legacy_variant_id
            vals = {
                "name": variant.name,
                "code": variant.default_code,
                "catalog_status": variant.catalog_status,
                "brand_id": variant.catalog_brand_id.id,
                "categ_id": variant.catalog_categ_id.id,
                "erp_enabled": bool(variant.is_activated),
                "erp_product_tmpl_id": variant.activated_product_tmpl_id.id,
                "variant_thickness": variant.variant_thickness,
                "variant_color": variant.variant_color,
                "variant_adhesive_type": variant.variant_adhesive_type,
                "variant_base_material": variant.variant_base_material,
                "variant_thickness_std": variant.variant_thickness_std,
                "variant_color_std": variant.variant_color_std,
                "variant_adhesive_std": variant.variant_adhesive_std,
                "variant_base_material_std": variant.variant_base_material_std,
                "variant_ref_price": variant.variant_ref_price,
                "variant_note": variant.variant_note,
                "variant_is_rohs": variant.variant_is_rohs,
                "variant_is_reach": variant.variant_is_reach,
                "variant_is_halogen_free": variant.variant_is_halogen_free,
                "variant_fire_rating": variant.variant_fire_rating,
                "variant_tds_file": variant.variant_tds_file,
                "variant_tds_filename": variant.variant_tds_filename,
                "variant_msds_file": variant.variant_msds_file,
                "variant_msds_filename": variant.variant_msds_filename,
                "variant_datasheet": variant.variant_datasheet,
                "variant_datasheet_filename": variant.variant_datasheet_filename,
                "variant_catalog_structure_image": variant.variant_catalog_structure_image,
            }
            item.with_context(skip_shadow_sync=True).write(vals)
            updated += 1
        return {"total": len(items), "updated": updated}

    @api.model
    def _normalize_compare_value(self, value):
        if isinstance(value, models.BaseModel):
            return value.id if value else False
        if isinstance(value, str):
            return value.strip()
        return value
