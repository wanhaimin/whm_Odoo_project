# -*- coding: utf-8 -*-

from odoo import SUPERUSER_ID, api


_PLACEHOLDERS = {"false", "none", "null", "nil", "n/a", "na"}


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


def _clean_text(value):
    if value in (False, None):
        return False
    cleaned = str(value).strip()
    if not cleaned or cleaned.casefold() in _PLACEHOLDERS:
        return False
    return cleaned


def _normalize_thickness_std(value):
    text = _clean_text(value)
    if not text:
        return False
    normalized = text.lower().replace("μm", "um").replace("µm", "um").replace(" ", "")
    import re

    match = re.search(r"(\d+(?:\.\d+)?)", normalized)
    if not match:
        return False
    number = float(match.group(1))
    is_um = "um" in normalized
    is_mm = "mm" in normalized and not is_um
    if is_um:
        um_value = number
    elif is_mm:
        um_value = number * 1000.0
    else:
        um_value = number if number > 10 else number * 1000.0
    rounded = round(um_value, 1)
    if rounded.is_integer():
        return f"{int(rounded)}μm"
    return f"{rounded:g}μm"


def _parse_thickness_mm(value):
    normalized = _normalize_thickness_std(value)
    if not normalized:
        return False
    raw = normalized.lower().replace("μm", "").strip()
    try:
        return round(float(raw) / 1000.0, 6)
    except ValueError:
        return False


def _resolve_taxonomy_id(env, model_name, raw_value):
    text = _clean_text(raw_value)
    if not text:
        return False
    model = env[model_name].sudo().with_context(active_test=False)
    record = model.search([("name", "=", text)], limit=1)
    if not record:
        record = model.create({"name": text})
    return record.id


def _aggregate_variant_values(env):
    pp_columns = _existing_columns(env.cr, "product_product")
    desired_columns = [
        "variant_thickness",
        "variant_adhesive_thickness",
        "variant_color",
        "variant_adhesive_type",
        "variant_base_material",
        "variant_thickness_std",
        "variant_ref_price",
        "variant_is_rohs",
        "variant_is_reach",
        "variant_is_halogen_free",
        "variant_fire_rating",
        "variant_catalog_structure_image",
    ]
    active_columns = [name for name in desired_columns if name in pp_columns]
    if not active_columns:
        return {}

    select_sql = ", ".join(["product_tmpl_id"] + active_columns)
    env.cr.execute(f"SELECT {select_sql} FROM product_product ORDER BY product_tmpl_id, id")
    aggregated = {}
    for row in env.cr.dictfetchall():
        product_tmpl_id = row["product_tmpl_id"]
        bucket = aggregated.setdefault(product_tmpl_id, {})
        for field_name in active_columns:
            value = row.get(field_name)
            if field_name in {"variant_is_rohs", "variant_is_reach", "variant_is_halogen_free"}:
                if value:
                    bucket[field_name] = True
                continue
            if field_name == "variant_ref_price":
                if value not in (False, None) and field_name not in bucket:
                    bucket[field_name] = value
                continue
            if field_name == "variant_catalog_structure_image":
                if value and field_name not in bucket:
                    bucket[field_name] = value
                continue
            cleaned = _clean_text(value)
            if cleaned and field_name not in bucket:
                bucket[field_name] = cleaned
    return aggregated


def _migrate_product_template_canonical_fields(env):
    aggregated = _aggregate_variant_values(env)
    if not aggregated:
        return

    template_model = env["product.template"].sudo().with_context(active_test=False)
    for product_tmpl_id, data in aggregated.items():
        template = template_model.browse(product_tmpl_id)
        if not template.exists():
            continue

        vals = {}
        if data.get("variant_adhesive_thickness") and not template.adhesive_thickness:
            vals["adhesive_thickness"] = data["variant_adhesive_thickness"]

        thickness_std = _normalize_thickness_std(data.get("variant_thickness_std") or data.get("variant_thickness"))
        if thickness_std and not template.thickness_std:
            vals["thickness_std"] = thickness_std

        thickness_mm = _parse_thickness_mm(data.get("variant_thickness_std") or data.get("variant_thickness"))
        if thickness_mm and not template.thickness:
            vals["thickness"] = thickness_mm

        if data.get("variant_color"):
            if not template.color_id:
                color_id = _resolve_taxonomy_id(env, "diecut.color", data["variant_color"])
                if color_id:
                    vals["color_id"] = color_id
            if not template.material_color:
                vals["material_color"] = data["variant_color"]

        if data.get("variant_adhesive_type") and not template.adhesive_type_id:
            adhesive_type_id = _resolve_taxonomy_id(env, "diecut.catalog.adhesive.type", data["variant_adhesive_type"])
            if adhesive_type_id:
                vals["adhesive_type_id"] = adhesive_type_id

        if data.get("variant_base_material") and not template.base_material_id:
            base_material_id = _resolve_taxonomy_id(env, "diecut.catalog.base.material", data["variant_base_material"])
            if base_material_id:
                vals["base_material_id"] = base_material_id

        if data.get("variant_ref_price") not in (False, None) and not template.ref_price:
            vals["ref_price"] = data["variant_ref_price"]

        if data.get("variant_is_rohs") and not template.is_rohs:
            vals["is_rohs"] = True
        if data.get("variant_is_reach") and not template.is_reach:
            vals["is_reach"] = True
        if data.get("variant_is_halogen_free") and not template.is_halogen_free:
            vals["is_halogen_free"] = True

        fire_rating = _clean_text(data.get("variant_fire_rating"))
        if fire_rating and fire_rating != "none" and (not template.fire_rating or template.fire_rating == "none"):
            vals["fire_rating"] = fire_rating

        if data.get("variant_catalog_structure_image") and not template.catalog_structure_image:
            vals["catalog_structure_image"] = data["variant_catalog_structure_image"]

        if vals:
            template.write(vals)

    env["diecut.color"].sudo()._refresh_all_usage_counts()


def _drop_retired_columns(env):
    product_product_columns = _existing_columns(env.cr, "product_product")
    product_template_columns = _existing_columns(env.cr, "product_template")

    retired_variant_columns = [
        "variant_thickness",
        "variant_adhesive_thickness",
        "variant_color",
        "variant_adhesive_type",
        "variant_base_material",
        "variant_ref_price",
        "variant_thickness_std",
        "variant_color_std",
        "variant_adhesive_std",
        "variant_base_material_std",
        "variant_is_rohs",
        "variant_is_reach",
        "variant_is_halogen_free",
        "variant_fire_rating",
        "variant_catalog_structure_image",
    ]
    for column_name in retired_variant_columns:
        if column_name in product_product_columns:
            env.cr.execute(f'ALTER TABLE product_product DROP COLUMN IF EXISTS "{column_name}"')

    if "color" in product_template_columns:
        env.cr.execute('ALTER TABLE product_template DROP COLUMN IF EXISTS "color"')

    env.cr.execute(
        """
        DELETE FROM ir_model_fields
         WHERE (model = 'product.product' AND name = ANY(%s))
            OR (model = 'product.template' AND name = 'color')
        """,
        (retired_variant_columns,),
    )


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    _migrate_product_template_canonical_fields(env)
    _drop_retired_columns(env)
