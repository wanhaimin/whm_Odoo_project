# -*- coding: utf-8 -*-

import re

from odoo import SUPERUSER_ID, api


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


def _parse_peel_strength_n_per_25mm(raw_value):
    if raw_value in (False, None):
        return False
    text = str(raw_value).strip().lower()
    if not text:
        return False
    match = re.search(r"(\d+(?:\.\d+)?)\s*n\s*/\s*cm", text)
    if not match:
        return False
    n_per_cm = float(match.group(1))
    return round(n_per_cm * 2.5, 4)


def _migrate_variant_peel_strength(env):
    existing_columns = _existing_columns(env.cr, "product_product")
    if "variant_peel_strength" not in existing_columns:
        return

    env.cr.execute(
        """
        SELECT product_tmpl_id, variant_peel_strength
          FROM product_product
         WHERE variant_peel_strength IS NOT NULL
           AND trim(variant_peel_strength) <> ''
         ORDER BY product_tmpl_id, id
        """
    )
    aggregated = {}
    for product_tmpl_id, raw_value in env.cr.fetchall():
        parsed = _parse_peel_strength_n_per_25mm(raw_value)
        if parsed is False:
            continue
        aggregated.setdefault(product_tmpl_id, set()).add(parsed)

    template_model = env["product.template"].sudo().with_context(active_test=False)
    for template_id, values in aggregated.items():
        if len(values) != 1:
            continue
        template = template_model.browse(template_id)
        if not template.exists():
            continue
        if template.adhesion not in (False, None, 0):
            continue
        template.write({"adhesion": next(iter(values))})


def _drop_retired_variant_fields(env):
    existing_columns = _existing_columns(env.cr, "product_product")
    retired_columns = [
        "variant_peel_strength",
        "variant_structure",
        "variant_sus_peel",
        "variant_pe_peel",
        "variant_dupont",
        "variant_push_force",
        "variant_removability",
        "variant_tumbler",
        "variant_holding_power",
        "variant_note",
        "variant_tds_filename",
        "variant_msds_filename",
        "variant_datasheet_filename",
        "variant_ribbon_id",
    ]
    for column_name in retired_columns:
        if column_name in existing_columns:
            env.cr.execute(f'ALTER TABLE product_product DROP COLUMN IF EXISTS "{column_name}"')

    env.cr.execute(
        """
        DELETE FROM ir_attachment
         WHERE res_model = 'product.product'
           AND res_field = ANY(%s)
        """,
        (["variant_tds_file", "variant_msds_file", "variant_datasheet"],),
    )

    env.cr.execute(
        """
        DELETE FROM ir_model_fields
         WHERE model = 'product.product'
           AND name = ANY(%s)
        """,
        (
            [
                "catalog_categ_id",
                "catalog_brand_id",
                "variant_peel_strength",
                "variant_structure",
                "variant_sus_peel",
                "variant_pe_peel",
                "variant_dupont",
                "variant_push_force",
                "variant_removability",
                "variant_tumbler",
                "variant_holding_power",
                "variant_note",
                "variant_tds_file",
                "variant_tds_filename",
                "variant_msds_file",
                "variant_msds_filename",
                "variant_datasheet",
                "variant_datasheet_filename",
                "variant_ribbon_id",
                "variant_seller_ids",
                "variants_default_code",
            ],
        ),
    )


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    _migrate_variant_peel_strength(env)
    _drop_retired_variant_fields(env)
