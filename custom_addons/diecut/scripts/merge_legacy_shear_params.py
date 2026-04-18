# -*- coding: utf-8 -*-
import json


STANDARD_PARAM_KEY = "shear_strength"
STANDARD_PARAM_NAME = "\u526a\u5207\u5f3a\u5ea6"
STANDARD_PARAM_DESC = (
    "\u6807\u51c6\u526a\u5207\u5f3a\u5ea6\u53c2\u6570\uff0c\u8bf7\u901a\u8fc7\u6761\u4ef6\u660e\u7ec6"
    "\u627f\u8f7d\u88ab\u8d34\u5408\u7269\u548c\u6d4b\u8bd5\u72b6\u6001/\u6d78\u6ce1\u6761\u4ef6\u3002"
)
STANDARD_SCHEMA = [
    {"key": "substrate", "label": "\u88ab\u8d34\u5408\u7269", "sequence": 10},
    {"key": "state", "label": "\u6761\u4ef6\u72b6\u6001", "sequence": 20},
]

LEGACY_MAP = {
    "shear_painted_pvc_immediate": {
        "name": "\u6d82\u88c5\u677f/PVC\u677f-\u5373\u65f6\u72b6\u6001-\u526a\u5207\u5f3a\u5ea6",
        "conditions": [
            {
                "condition_key": "substrate",
                "condition_label": "\u88ab\u8d34\u5408\u7269",
                "condition_value": "\u6d82\u88c5\u677f/PVC\u677f",
                "sequence": 10,
            },
            {
                "condition_key": "state",
                "condition_label": "\u6761\u4ef6\u72b6\u6001",
                "condition_value": "\u5373\u65f6\u72b6\u6001",
                "sequence": 20,
            },
        ],
    },
    "shear_painted_pvc_normal": {
        "name": "\u6d82\u88c5\u677f/PVC\u677f-\u5e38\u6e29\u72b6\u6001-\u526a\u5207\u5f3a\u5ea6",
        "conditions": [
            {
                "condition_key": "substrate",
                "condition_label": "\u88ab\u8d34\u5408\u7269",
                "condition_value": "\u6d82\u88c5\u677f/PVC\u677f",
                "sequence": 10,
            },
            {
                "condition_key": "state",
                "condition_label": "\u6761\u4ef6\u72b6\u6001",
                "condition_value": "\u5e38\u6e29\u72b6\u6001",
                "sequence": 20,
            },
        ],
    },
    "shear_painted_pvc_high_temp": {
        "name": "\u6d82\u88c5\u677f/PVC\u677f-\u9ad8\u6e29\u72b6\u6001-\u526a\u5207\u5f3a\u5ea6",
        "conditions": [
            {
                "condition_key": "substrate",
                "condition_label": "\u88ab\u8d34\u5408\u7269",
                "condition_value": "\u6d82\u88c5\u677f/PVC\u677f",
                "sequence": 10,
            },
            {
                "condition_key": "state",
                "condition_label": "\u6761\u4ef6\u72b6\u6001",
                "condition_value": "\u9ad8\u6e29\u72b6\u6001",
                "sequence": 20,
            },
        ],
    },
    "shear_painted_pvc_warm_water": {
        "name": "\u6d82\u88c5\u677f/PVC\u677f-\u6e29\u6c34\u6d78\u6ce1\u540e-\u526a\u5207\u5f3a\u5ea6",
        "conditions": [
            {
                "condition_key": "substrate",
                "condition_label": "\u88ab\u8d34\u5408\u7269",
                "condition_value": "\u6d82\u88c5\u677f/PVC\u677f",
                "sequence": 10,
            },
            {
                "condition_key": "state",
                "condition_label": "\u6761\u4ef6\u72b6\u6001",
                "condition_value": "\u6e29\u6c34\u6d78\u6ce1\u540e",
                "sequence": 20,
            },
        ],
    },
    "shear_painted_pvc_gasoline": {
        "name": "\u6d82\u88c5\u677f/PVC\u677f-\u6c7d\u6cb9\u6d78\u6ce1\u540e-\u526a\u5207\u5f3a\u5ea6",
        "conditions": [
            {
                "condition_key": "substrate",
                "condition_label": "\u88ab\u8d34\u5408\u7269",
                "condition_value": "\u6d82\u88c5\u677f/PVC\u677f",
                "sequence": 10,
            },
            {
                "condition_key": "state",
                "condition_label": "\u6761\u4ef6\u72b6\u6001",
                "condition_value": "\u6c7d\u6cb9\u6d78\u6ce1\u540e",
                "sequence": 20,
            },
        ],
    },
    "shear_painted_pvc_wax_remover": {
        "name": "\u6d82\u88c5\u677f/PVC\u677f-\u9664\u8721\u5242\u6d78\u6ce1\u540e-\u526a\u5207\u5f3a\u5ea6",
        "conditions": [
            {
                "condition_key": "substrate",
                "condition_label": "\u88ab\u8d34\u5408\u7269",
                "condition_value": "\u6d82\u88c5\u677f/PVC\u677f",
                "sequence": 10,
            },
            {
                "condition_key": "state",
                "condition_label": "\u6761\u4ef6\u72b6\u6001",
                "condition_value": "\u9664\u8721\u5242\u6d78\u6ce1\u540e",
                "sequence": 20,
            },
        ],
    },
}


def _get_or_create_standard_param(param_model):
    param = param_model.search([("param_key", "=", STANDARD_PARAM_KEY)], limit=1)
    values = {
        "name": STANDARD_PARAM_NAME,
        "param_key": STANDARD_PARAM_KEY,
        "value_type": "float",
        "selection_role": "detail_only",
        "display_group": "bonding",
        "unit": "MPa",
        "preferred_unit": "MPa",
        "common_units": "MPa",
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
        if legacy_def.categ_id.id in defs_by_categ:
            continue
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
                    "value_type": standard_param.value_type,
                    "unit": legacy_def.unit or standard_param.unit,
                    "sequence": legacy_def.sequence,
                    "required": legacy_def.required,
                    "active": legacy_def.active,
                    "show_in_form": legacy_def.show_in_form,
                    "allow_import": legacy_def.allow_import,
                    "unit_override": legacy_def.unit_override,
                }
            )
        defs_by_categ[legacy_def.categ_id.id] = existing
    return legacy_defs, defs_by_categ


def _migrate_lines(env, standard_param, legacy_params, defs_by_categ):
    line_model = env["diecut.catalog.item.spec.line"].sudo()
    condition_model = env["diecut.catalog.item.spec.condition"].sudo()
    migrated_lines = line_model.search([("param_id", "in", legacy_params.ids)], order="id")
    touched_items = env["diecut.catalog.item"]
    migrated_count = 0
    condition_count = 0
    for line in migrated_lines:
        mapping = LEGACY_MAP.get(line.param_id.param_key)
        if not mapping:
            continue
        categ_id = line.catalog_item_id.categ_id.id if line.catalog_item_id and line.catalog_item_id.categ_id else False
        category_def = defs_by_categ.get(categ_id)
        line.write(
            {
                "param_id": standard_param.id,
                "param_key": standard_param.param_key,
                "param_name": standard_param.name,
                "category_param_id": category_def.id if category_def else False,
                "unit": line.unit or standard_param.unit or False,
                "normalized_unit": line.normalized_unit or standard_param.preferred_unit or standard_param.unit or False,
            }
        )
        line.condition_ids.unlink()
        for condition in mapping["conditions"]:
            condition_model.create(dict(condition, spec_line_id=line.id))
            condition_count += 1
        migrated_count += 1
        touched_items |= line.catalog_item_id
    if touched_items:
        touched_items._compute_selection_search_text()
    env["diecut.catalog.param"].sudo()._refresh_usage_counts()
    env["diecut.catalog.spec.def"].sudo()._refresh_line_count()
    return migrated_count, condition_count, migrated_lines


def _cleanup_legacy(env, legacy_params, legacy_defs):
    legacy_def_count = len(legacy_defs)
    legacy_defs.unlink()
    removable_params = legacy_params.filtered(lambda p: not p.line_count and not p.category_config_count)
    removable_count = len(removable_params)
    if removable_params:
        removable_params.unlink()
    return legacy_def_count, removable_count


def main():
    param_model = env["diecut.catalog.param"].sudo()
    legacy_params = param_model.search([("param_key", "in", list(LEGACY_MAP.keys()))], order="id")
    if not legacy_params:
        print("legacy_params=0")
        return

    standard_param = _get_or_create_standard_param(param_model)
    legacy_defs, defs_by_categ = _ensure_category_defs(env, standard_param, legacy_params)
    migrated_count, condition_count, migrated_lines = _migrate_lines(env, standard_param, legacy_params, defs_by_categ)
    legacy_def_count, removable_count = _cleanup_legacy(env, legacy_params, legacy_defs)

    print(f"standard_param_id={standard_param.id}")
    print(f"migrated_lines={migrated_count}")
    print(f"created_conditions={condition_count}")
    print(f"legacy_defs_removed={legacy_def_count}")
    print(f"legacy_params_removed={removable_count}")
    print(f"remaining_legacy_params={param_model.search_count([('param_key', 'in', list(LEGACY_MAP.keys()))])}")
    print(f"current_standard_line_count={param_model.browse(standard_param.id).line_count}")
    env.cr.commit()


main()
