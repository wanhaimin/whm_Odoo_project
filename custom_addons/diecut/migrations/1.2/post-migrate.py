# -*- coding: utf-8 -*-

from odoo import SUPERUSER_ID, api


TABLE = "diecut_catalog_item"


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


def _migrate_series_text_to_series(env):
    if "series_text" not in _existing_columns(env.cr, TABLE):
        return

    series_model = env["diecut.catalog.series"].sudo()
    env.cr.execute(
        f"""
        SELECT id, brand_id, series_id, series_text, product_features, product_description, main_applications
          FROM {TABLE}
         WHERE brand_id IS NOT NULL
           AND NULLIF(trim(COALESCE(series_text, '')), '') IS NOT NULL
        """
    )
    grouped = {}
    for row in env.cr.dictfetchall():
        series_name = (row.get("series_text") or "").strip()
        if not series_name:
            continue
        grouped.setdefault((row["brand_id"], series_name), []).append(row)

    for (brand_id, series_name), rows in grouped.items():
        series = series_model.search(
            [("brand_id", "=", brand_id), ("name", "=", series_name)],
            limit=1,
        )
        if not series:
            values = {"brand_id": brand_id, "name": series_name}
            for field_name in ("product_features", "product_description", "main_applications"):
                field_value = next((row.get(field_name) for row in rows if row.get(field_name)), False)
                if field_value:
                    values[field_name] = field_value
            series = series_model.create(values)
        else:
            write_vals = {}
            for field_name in ("product_features", "product_description", "main_applications"):
                if series[field_name]:
                    continue
                field_value = next((row.get(field_name) for row in rows if row.get(field_name)), False)
                if field_value:
                    write_vals[field_name] = field_value
            if write_vals:
                series.write(write_vals)

        row_ids = [row["id"] for row in rows if row.get("series_id") != series.id]
        if row_ids:
            env.cr.execute(
                f"""
                UPDATE {TABLE}
                   SET series_id = %s
                 WHERE id = ANY(%s)
                """,
                (series.id, row_ids),
            )


def _drop_series_text_column(env):
    if "series_text" in _existing_columns(env.cr, TABLE):
        env.cr.execute(f'ALTER TABLE {TABLE} DROP COLUMN IF EXISTS "series_text"')
    env.cr.execute(
        """
        DELETE FROM ir_model_data
         WHERE model = 'ir.model.fields'
           AND res_id IN (
               SELECT id
                 FROM ir_model_fields
                WHERE model = 'diecut.catalog.item'
                  AND name = 'series_text'
           )
        """
    )
    env.cr.execute(
        """
        DELETE FROM ir_model_fields
         WHERE model = 'diecut.catalog.item'
           AND name = 'series_text'
        """
    )


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    _migrate_series_text_to_series(env)
    _drop_series_text_column(env)
