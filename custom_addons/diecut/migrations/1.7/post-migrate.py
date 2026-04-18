# -*- coding: utf-8 -*-
from odoo import api, SUPERUSER_ID


def _placeholder_domains():
    return [
        ("name", "=", False),
        ("name", "=", ""),
        ("name", "=ilike", "false"),
        ("name", "=ilike", "none"),
        ("name", "=ilike", "null"),
        ("name", "=ilike", "nil"),
        ("name", "=ilike", "n/a"),
        ("name", "=ilike", "na"),
    ]


def _cleanup_invalid_taxonomy_records(env, model_name, ref_specs):
    if model_name not in env:
        return
    model = env[model_name].with_context(active_test=False)
    bad_records = model.browse()
    for condition in _placeholder_domains():
        bad_records |= model.search([condition])
    if not bad_records:
        return

    for ref_model, ref_field in ref_specs:
        if ref_model not in env:
            continue
        rows = env[ref_model].with_context(active_test=False).search([(ref_field, "in", bad_records.ids)])
        if rows:
            rows.sudo().write({ref_field: False})

    bad_records.with_context(skip_merge_unlink_guard=True).sudo().unlink()


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    _cleanup_invalid_taxonomy_records(
        env,
        "diecut.color",
        [
            ("diecut.catalog.item", "color_id"),
            ("product.template", "color_id"),
        ],
    )
    _cleanup_invalid_taxonomy_records(
        env,
        "diecut.catalog.base.material",
        [
            ("diecut.catalog.item", "base_material_id"),
            ("product.template", "base_material_id"),
        ],
    )
    _cleanup_invalid_taxonomy_records(
        env,
        "diecut.catalog.adhesive.type",
        [
            ("diecut.catalog.item", "adhesive_type_id"),
            ("product.template", "adhesive_type_id"),
        ],
    )
