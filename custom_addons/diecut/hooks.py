# -*- coding: utf-8 -*-

from odoo import SUPERUSER_ID, api


_TABLE = "diecut_catalog_item"
_LEGACY_COLUMNS = {
    "variant_color": "variant_color_legacy_text",
    "variant_adhesive_type": "variant_adhesive_type_legacy_text",
    "variant_base_material": "variant_base_material_legacy_text",
}


def _column_exists(cr, table_name, column_name):
    cr.execute(
        """
        SELECT 1
          FROM information_schema.columns
         WHERE table_name = %s
           AND column_name = %s
        """,
        (table_name, column_name),
    )
    return bool(cr.fetchone())


def _column_data_type(cr, table_name, column_name):
    cr.execute(
        """
        SELECT data_type
          FROM information_schema.columns
         WHERE table_name = %s
           AND column_name = %s
        """,
        (table_name, column_name),
    )
    row = cr.fetchone()
    return row[0] if row else None


def pre_init_hook(cr):
    for column_name, legacy_column in _LEGACY_COLUMNS.items():
        if not _column_exists(cr, _TABLE, column_name):
            continue
        if _column_exists(cr, _TABLE, legacy_column):
            continue
        data_type = _column_data_type(cr, _TABLE, column_name)
        if data_type not in ("character varying", "text"):
            continue
        cr.execute(
            f'ALTER TABLE {_TABLE} RENAME COLUMN "{column_name}" TO "{legacy_column}"'
        )


def post_init_hook(cr, registry):
    env = api.Environment(cr, SUPERUSER_ID, {})
    env["diecut.catalog.item"]._migrate_variant_taxonomy_many2one()
    env["diecut.color"].sudo()._refresh_all_usage_counts()
    env["diecut.catalog.adhesive.type"].sudo()._refresh_all_usage_counts()
    env["diecut.catalog.base.material"].sudo()._refresh_all_usage_counts()
