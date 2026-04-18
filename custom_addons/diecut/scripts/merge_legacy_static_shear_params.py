# -*- coding: utf-8 -*-
import json


STANDARD_PARAM_KEY = "static_shear"
STANDARD_PARAM_NAME = "\u9759\u6001\u526a\u5207"
STANDARD_PARAM_DESC = (
    "\u6807\u51c6\u9759\u6001\u526a\u5207\u53c2\u6570\uff0c\u8bf7\u901a\u8fc7\u6761\u4ef6\u660e\u7ec6"
    "\u627f\u8f7d\u6d4b\u8bd5\u6e29\u5ea6\u6216\u5176\u4ed6\u72b6\u6001\u7ef4\u5ea6\u3002"
)
STANDARD_SCHEMA = [
    {"key": "temperature", "label": "\u6d4b\u8bd5\u6e29\u5ea6", "sequence": 10},
]

LEGACY_MAP = {
    "static_shear_23c": {
        "temperature": "23\u00b0C",
    },
    "static_shear_40c": {
        "temperature": "40\u00b0C",
    },
    "static_shear_70c": {
        "temperature": "70\u00b0C",
    },
}


def _get_or_update_standard_param(param_model):
    param = param_model.search([("param_key", "=", STANDARD_PARAM_KEY)], limit=1)
    values = {
        "name": STANDARD_PARAM_NAME,
        "param_key": STANDARD_PARAM_KEY,
        "value_type": "char",
        "selection_role": "detail_only",
        "display_group": "bonding",
        "description": STANDARD_PARAM_DESC,
        "condition_schema_json": json.dumps(STANDARD_SCHEMA, ensure_ascii=False, indent=2),
        "active": True,
    }
    if param:
        param.write(values)
        return param
    return param_model.create(values)


def _ensure_category_defs(env, standard_param, legacy_params):
    spec_def_model = env["diecut.catalog.spec.def"].sudo()
    defs_by_categ = {}
    legacy_defs = spec_def_model.search([("param_id", "in", legacy_params.ids)])
    for legacy_def in legacy_defs:
        existing = spec_def_model.search(
            [("categ_id", "=", legacy_def.categ_id.id), ("param_id", "=", standard_param.id)],
            limit=1,
        )
        if not existing:
            existing = spec_def_model.create(
                {
                    "param_id": standard_param.id,
                    "categ_id": legacy_def.categ_id.id,
                    "name": standard_param.name,
                    "param_key": standard_param.param_key,
                    "value_type": "char",
                    "unit": False,
                    "sequence": legacy_def.sequence,
                    "required": legacy_def.required,
                    "active": legacy_def.active,
                    "show_in_form": legacy_def.show_in_form,
                    "allow_import": legacy_def.allow_import,
                    "unit_override": False,
                }
            )
        defs_by_categ[legacy_def.categ_id.id] = existing
    return legacy_defs, defs_by_categ


def _migrate_lines(env, standard_param, legacy_params, defs_by_categ):
    line_model = env["diecut.catalog.item.spec.line"].sudo()
    condition_model = env["diecut.catalog.item.spec.condition"].sudo()
    lines = line_model.search([("param_id", "in", legacy_params.ids)], order="id")
    touched_items = env["diecut.catalog.item"]
    migrated_count = 0
    created_conditions = 0
    for line in lines:
        mapping = LEGACY_MAP.get(line.param_id.param_key)
        categ_id = line.catalog_item_id.categ_id.id if line.catalog_item_id and line.catalog_item_id.categ_id else False
        category_def = defs_by_categ.get(categ_id)
        updates = {
            "param_id": standard_param.id,
            "param_key": standard_param.param_key,
            "param_name": standard_param.name,
            "category_param_id": category_def.id if category_def else False,
            "unit": False,
            "normalized_unit": False,
            "value_kind": "text",
        }
        if line.value_number not in (False, None):
            updates["value_raw"] = str(line.value_number)
        if line.value_display and line.value_display not in (False, ""):
            unit = (line.unit or "").strip()
            if unit and line.value_display.endswith(f" {unit}"):
                updates["value_raw"] = line.value_display[: -(len(unit) + 1)]
            elif line.value_raw:
                updates["value_raw"] = line.value_raw
            else:
                updates["value_raw"] = line.value_display
        line.write(updates)
        line.condition_ids.unlink()
        if mapping:
            condition_model.create(
                {
                    "spec_line_id": line.id,
                    "sequence": 10,
                    "condition_key": "temperature",
                    "condition_label": "\u6d4b\u8bd5\u6e29\u5ea6",
                    "condition_value": mapping["temperature"],
                }
            )
            created_conditions += 1
        migrated_count += 1
        touched_items |= line.catalog_item_id
    if touched_items:
        touched_items._compute_selection_search_text()
    env["diecut.catalog.param"].sudo()._refresh_usage_counts()
    env["diecut.catalog.spec.def"].sudo()._refresh_line_count()
    return migrated_count, created_conditions


def _cleanup_legacy(legacy_defs, legacy_params):
    legacy_def_count = len(legacy_defs)
    if legacy_defs:
        legacy_defs.unlink()
    removable = legacy_params.filtered(lambda p: p.param_key != STANDARD_PARAM_KEY)
    removable_count = len(removable)
    if removable:
        removable.unlink()
    return legacy_def_count, removable_count


def main():
    param_model = env["diecut.catalog.param"].sudo()
    legacy_keys = list(LEGACY_MAP.keys())
    legacy_params = param_model.search([("param_key", "in", legacy_keys)], order="id")
    standard_param = _get_or_update_standard_param(param_model)
    if not legacy_params:
        print(f"standard_param_id={standard_param.id}")
        print("legacy_params=0")
        env.cr.commit()
        return
    legacy_defs, defs_by_categ = _ensure_category_defs(env, standard_param, legacy_params)
    migrated_count, created_conditions = _migrate_lines(env, standard_param, legacy_params, defs_by_categ)
    legacy_def_count, removable_count = _cleanup_legacy(legacy_defs, legacy_params)
    env["diecut.catalog.param"].sudo().browse(standard_param.id)._refresh_usage_counts()
    env["diecut.catalog.spec.def"].sudo()._refresh_line_count()
    print(f"standard_param_id={standard_param.id}")
    print(f"migrated_lines={migrated_count}")
    print(f"created_conditions={created_conditions}")
    print(f"legacy_defs_removed={legacy_def_count}")
    print(f"legacy_params_removed={removable_count}")
    env.cr.commit()


main()
