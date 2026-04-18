# -*- coding: utf-8 -*-

from odoo import SUPERUSER_ID, api


_PLACEHOLDER_NAMES = {"false", "none", "null", "nil", "n/a", "na"}


def _cleanup_placeholder_taxonomy(env, model_name):
    model = env[model_name].sudo().with_context(active_test=False)
    bad_records = model.search([])
    bad_records = bad_records.filtered(lambda rec: (rec.name or "").strip().casefold() in _PLACEHOLDER_NAMES)
    if not bad_records:
        return

    bad_ids = bad_records.ids
    for ref_model, field_name in model._usage_counter_specs():
        if ref_model not in env:
            continue
        refs = env[ref_model].sudo().with_context(active_test=False).search([(field_name, "in", bad_ids)])
        if refs:
            refs.write({field_name: False})

    model._refresh_all_usage_counts()
    bad_records._refresh_usage_counts()
    bad_records.with_context(skip_merge_unlink_guard=True).unlink()
    model._refresh_all_usage_counts()


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    for model_name in (
        "diecut.color",
        "diecut.catalog.base.material",
        "diecut.catalog.adhesive.type",
    ):
        _cleanup_placeholder_taxonomy(env, model_name)
