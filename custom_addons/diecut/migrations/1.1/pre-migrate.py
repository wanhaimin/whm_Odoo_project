# -*- coding: utf-8 -*-


def _clean_series_text_view_residue(cr):
    escaped_variants = (
        '<field name=\\"series_text\\" invisible=\\"1\\"/>',
        '<field name=\\"series_text\\" invisible=\\"1\\" />',
    )
    arch_expr = "arch_db::text"
    for needle in escaped_variants:
        arch_expr = f"replace({arch_expr}, %s, '')"
    cr.execute(
        f"""
        UPDATE ir_ui_view
           SET arch_db = ({arch_expr})::jsonb
         WHERE arch_db::text LIKE %s
        """,
        ('%series_text%', *escaped_variants),
    )

    raw_variants = (
        '<field name="series_text" invisible="1"/>',
        '<field name="series_text" invisible="1" />',
    )
    arch_prev_expr = "COALESCE(arch_prev, '')"
    for needle in raw_variants:
        arch_prev_expr = f"replace({arch_prev_expr}, %s, '')"
    cr.execute(
        f"""
        UPDATE ir_ui_view
           SET arch_prev = NULLIF({arch_prev_expr}, '')
         WHERE COALESCE(arch_prev, '') LIKE %s
        """,
        ('%series_text%', *raw_variants),
    )


def _clean_series_text_field_metadata(cr):
    cr.execute(
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
    cr.execute(
        """
        DELETE FROM ir_model_fields
         WHERE model = 'diecut.catalog.item'
           AND name = 'series_text'
        """
    )


def migrate(cr, version):
    _clean_series_text_view_residue(cr)
    _clean_series_text_field_metadata(cr)
