# -*- coding: utf-8 -*-

from odoo import SUPERUSER_ID, api


_TABLE = "diecut_catalog_item"


def _existing_columns(cr, table_name):
    cr.execute(
        """
        SELECT column_name
          FROM information_schema.columns
         WHERE table_name = %s
        """,
        (table_name,),
    )
    return {row[0] for row in cr.fetchall()}


def _clean_placeholder_main_fields(env):
    placeholders = ("false", "none", "null")
    existing_columns = _existing_columns(env.cr, _TABLE)
    for column_name in ("thickness", "adhesive_thickness", "thickness_std"):
        if column_name not in existing_columns:
            continue
        env.cr.execute(
            f"""
            UPDATE {_TABLE}
               SET "{column_name}" = NULL
             WHERE lower(trim(COALESCE("{column_name}", ''))) IN %s
            """,
            (placeholders,),
        )


def _migrate_variant_main_fields_to_canonical(env):
    existing_columns = _existing_columns(env.cr, _TABLE)
    column_map = {
        "thickness": "variant_thickness",
        "adhesive_thickness": "variant_adhesive_thickness",
        "color_id": "variant_color",
        "adhesive_type_id": "variant_adhesive_type",
        "base_material_id": "variant_base_material",
        "thickness_std": "variant_thickness_std",
        "ref_price": "variant_ref_price",
        "is_rohs": "variant_is_rohs",
        "is_reach": "variant_is_reach",
        "is_halogen_free": "variant_is_halogen_free",
        "catalog_structure_image": "variant_catalog_structure_image",
        "fire_rating": "variant_fire_rating",
    }
    for field_name, legacy_column in column_map.items():
        if field_name not in existing_columns or legacy_column not in existing_columns:
            continue
        env.cr.execute(
            f"""
            UPDATE {_TABLE}
               SET "{field_name}" = COALESCE("{field_name}", "{legacy_column}")
             WHERE "{legacy_column}" IS NOT NULL
            """
        )


def _migrate_variant_taxonomy_text_columns(env):
    item_model = env["diecut.catalog.item"].sudo()
    existing_columns = _existing_columns(env.cr, _TABLE)
    column_map = {
        "color_id": "variant_color_legacy_text",
        "adhesive_type_id": "variant_adhesive_type_legacy_text",
        "base_material_id": "variant_base_material_legacy_text",
    }
    legacy_columns = [column for column in column_map.values() if column in existing_columns]
    if not legacy_columns:
        return

    select_sql = ", ".join(["id"] + legacy_columns)
    env.cr.execute(f"SELECT {select_sql} FROM {_TABLE}")
    for row in env.cr.dictfetchall():
        record = item_model.browse(row["id"])
        if not record.exists():
            continue
        vals = {}
        for field_name, legacy_column in column_map.items():
            legacy_value = row.get(legacy_column)
            if item_model._clean_placeholder_text(legacy_value) in (False, None, ""):
                continue
            if record[field_name]:
                continue
            vals[field_name] = item_model._resolve_or_create_taxonomy_id(
                item_model._TAXONOMY_MODEL_BY_FIELD[field_name], legacy_value
            )
        if vals:
            record.with_context(skip_series_sync=True, skip_spec_autofill=True).write(vals)


def _migrate_variant_spec_columns_to_lines(env):
    existing_columns = _existing_columns(env.cr, _TABLE)
    legacy_spec_map = {
        "variant_peel_strength": ("peel_strength", "剥离力"),
        "variant_structure": ("structure", "结构描述"),
        "variant_sus_peel": ("sus_peel", "SUS剥离力"),
        "variant_pe_peel": ("pe_peel", "PE剥离力"),
        "variant_dupont": ("dupont", "DuPont冲击"),
        "variant_push_force": ("push_force", "推出力"),
        "variant_removability": ("removability", "可移除性"),
        "variant_tumbler": ("tumbler", "Tumbler滚球"),
        "variant_holding_power": ("holding_power", "保持力"),
    }
    active_legacy_fields = [field_name for field_name in legacy_spec_map if field_name in existing_columns]
    if not active_legacy_fields:
        return

    spec_def_model = env["diecut.catalog.spec.def"].sudo()
    line_model = env["diecut.catalog.item.spec.line"].sudo()
    select_sql = ", ".join(["id", "categ_id"] + active_legacy_fields)
    legacy_field_order = list(legacy_spec_map.keys())
    env.cr.execute(f"SELECT {select_sql} FROM {_TABLE}")
    for row in env.cr.dictfetchall():
        categ_id = row.get("categ_id")
        if not categ_id:
            continue
        for field_name, (param_key, param_name) in legacy_spec_map.items():
            if field_name not in active_legacy_fields:
                continue
            legacy_value = row.get(field_name)
            if line_model._is_placeholder_text(legacy_value) or legacy_value in (False, None, ""):
                continue
            spec_def = spec_def_model.search([("categ_id", "=", categ_id), ("param_key", "=", param_key)], limit=1)
            if not spec_def:
                spec_def = spec_def_model.create(
                    {
                        "name": param_name,
                        "param_key": param_key,
                        "categ_id": categ_id,
                        "value_type": "char",
                        "sequence": 1000 + legacy_field_order.index(field_name),
                        "required": False,
                        "active": True,
                        "show_in_form": True,
                        "allow_import": True,
                    }
                )
            line_vals = {
                "catalog_item_id": row["id"],
                "param_id": spec_def.param_id.id,
                "category_param_id": spec_def.id,
                "sequence": spec_def.sequence,
                "param_key": spec_def.param_key,
                "param_name": spec_def.name,
                "value_raw": str(legacy_value).strip() if legacy_value not in (False, None, "") else False,
                "unit": line_model._clean_placeholder_text(spec_def.unit_override or spec_def.unit),
            }
            line = line_model.search(
                [("catalog_item_id", "=", row["id"]), ("param_id", "=", spec_def.param_id.id)],
                limit=1,
            )
            if line:
                line.write(line_vals)
            else:
                line_model.create(line_vals)


def _drop_variant_compatibility_columns(env):
    drop_columns = [
        "variant_thickness",
        "variant_adhesive_thickness",
        "variant_color",
        "variant_peel_strength",
        "variant_structure",
        "variant_adhesive_type",
        "variant_base_material",
        "variant_sus_peel",
        "variant_pe_peel",
        "variant_dupont",
        "variant_push_force",
        "variant_removability",
        "variant_tumbler",
        "variant_holding_power",
        "variant_thickness_std",
        "variant_color_std",
        "variant_adhesive_std",
        "variant_base_material_std",
        "variant_ref_price",
        "variant_is_rohs",
        "variant_is_reach",
        "variant_is_halogen_free",
        "variant_catalog_structure_image",
        "variant_fire_rating",
        "variant_color_legacy_text",
        "variant_adhesive_type_legacy_text",
        "variant_base_material_legacy_text",
    ]
    existing_columns = _existing_columns(env.cr, _TABLE)
    for column_name in drop_columns:
        if column_name in existing_columns:
            env.cr.execute(f'ALTER TABLE {_TABLE} DROP COLUMN IF EXISTS "{column_name}"')
    env.cr.execute(
        """
        DELETE FROM ir_model_fields
         WHERE model = 'diecut.catalog.item'
           AND name = ANY(%s)
        """,
        (drop_columns,),
    )


def _cleanup_variant_compatibility_fields(env):
    _migrate_variant_main_fields_to_canonical(env)
    _migrate_variant_taxonomy_text_columns(env)
    _migrate_variant_spec_columns_to_lines(env)
    _drop_variant_compatibility_columns(env)
    _clean_placeholder_main_fields(env)
    env["diecut.color"].sudo()._refresh_all_usage_counts()
    env["diecut.catalog.adhesive.type"].sudo()._refresh_all_usage_counts()
    env["diecut.catalog.base.material"].sudo()._refresh_all_usage_counts()
    env["diecut.catalog.series"].sudo()._refresh_all_usage_counts()


def pre_init_hook(cr):
    return None


def post_init_hook(cr, registry):
    env = api.Environment(cr, SUPERUSER_ID, {})
    item_model = env["diecut.catalog.item"]
    item_model._migrate_product_info_fields()
    _cleanup_variant_compatibility_fields(env)
