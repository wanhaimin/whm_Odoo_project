# -*- coding: utf-8 -*-

from odoo import Command


def _ensure_application_tag(env, name):
    tag_model = env["diecut.catalog.application.tag"].sudo().with_context(active_test=False)
    tag = tag_model.search([("name", "=", name)], limit=1)
    if tag:
        return tag, False
    return tag_model.create({"name": name}), True


def _scene_leaf_names(scene_records):
    return {
        scene.name.strip()
        for scene in scene_records
        if scene.name and not scene.child_ids
    }


def run(env):
    """Compatibility helper for the simplified selection model.

    Historical scene data is folded into application tags. Retired platform and
    scene relationships are no longer written by this script.
    """

    series_model = env["diecut.catalog.series"].sudo().with_context(active_test=False)
    item_model = env["diecut.catalog.item"].sudo().with_context(active_test=False)

    updated_series = 0
    updated_items = 0
    created_tags = 0

    for series in series_model.search([]):
        scene_names = _scene_leaf_names(series.default_scene_ids)
        if not scene_names:
            continue
        merged_ids = set(series.default_application_tag_ids.ids)
        for scene_name in sorted(scene_names):
            tag, created = _ensure_application_tag(env, scene_name)
            if created:
                created_tags += 1
            merged_ids.add(tag.id)
        if merged_ids != set(series.default_application_tag_ids.ids):
            series.write({"default_application_tag_ids": [Command.set(sorted(merged_ids))]})
            updated_series += 1

    for item in item_model.search([]):
        scene_names = _scene_leaf_names(item.scene_ids) | _scene_leaf_names(item.series_id.default_scene_ids)
        if not scene_names:
            continue
        merged_ids = set(item.application_tag_ids.ids)
        for scene_name in sorted(scene_names):
            tag, created = _ensure_application_tag(env, scene_name)
            if created:
                created_tags += 1
            merged_ids.add(tag.id)
        if merged_ids != set(item.application_tag_ids.ids):
            item.write({"application_tag_ids": [Command.set(sorted(merged_ids))]})
            updated_items += 1

    print(
        {
            "created_application_tags": created_tags,
            "updated_series": updated_series,
            "updated_items": updated_items,
            "retired_fields_written": False,
        }
    )
    env.cr.commit()