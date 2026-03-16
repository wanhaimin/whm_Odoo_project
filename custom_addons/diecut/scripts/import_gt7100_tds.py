# -*- coding: utf-8 -*-
from __future__ import annotations

import csv
from collections import OrderedDict
from pathlib import Path

from odoo import Command


BRAND_NAME = "3m"
CATEGORY_XMLID = "diecut.category_tape_foam"
SERIES_NAME = "3M GT7100 \u7cfb\u5217"
BASE_DIR = Path("/mnt/extra-addons/diecut/scripts")
DRAFT_DIR = BASE_DIR / "tds_import_drafts"

PAINTED = "\u6d82\u88c5\u677f"
PVC = "PVC\u677f"
PAINTED_PVC = "\u6d82\u88c5\u677f/PVC\u677f"
PEEL_SUFFIX = "180\u5ea6\u5265\u79bb\u529b"
SHEAR_SUFFIX = "\u526a\u5207\u5f3a\u5ea6"
GRAY = "\u7070\u8272"
WHITE = "\u767d\u8272"
ADHESIVE = "\u4e19\u70ef\u9178\u538b\u654f\u80f6"
BASE_MATERIAL = "\u4e9a\u514b\u529b\u6ce1\u68c9"
DEG_C = "23\u00b0C"
HOT_80 = "80\u00b0C"
WARM_40 = "40\u00b0C"


def _u(text):
    return text


def _name(subject, state, suffix):
    return f"{subject}-{state}-{suffix}"


def _peel_desc(subject, state_text):
    return f"{PEEL_SUFFIX}\uff0c\u6d4b\u8bd5\u5bf9\u8c61\u4e3a{subject}\uff0c{state_text}\u3002"


def _shear_desc(state_text):
    return f"{SHEAR_SUFFIX}\uff0c\u6d4b\u8bd5\u5bf9\u8c61\u4e3a{PAINTED_PVC}\u7ec4\u5408\uff0c{state_text}\u3002"


STATES = OrderedDict(
    [
        ("immediate", ("\u5373\u65f6\u72b6\u6001", "\u5373\u65f6\u72b6\u6001")),
        ("normal", ("\u5e38\u6e29\u72b6\u6001", "\u5e38\u6e29\u9759\u7f6e\u540e\u6d4b\u5f97")),
        ("high_temp", ("\u9ad8\u6e29\u72b6\u6001", "\u7ecf\u5e38\u6e29\u9759\u7f6e\u540e\u518d\u8fdb\u884c\u9ad8\u6e29\u5904\u7406")),
        ("heat_aging", ("\u70ed\u8001\u5316\u540e", "\u7ecf\u70ed\u8001\u5316\u540e\u6d4b\u5f97")),
        ("warm_water", ("\u6e29\u6c34\u6d78\u6ce1\u540e", "\u7ecf\u6e29\u6c34\u6d78\u6ce1\u540e\u6d4b\u5f97")),
        ("gasoline", ("\u6c7d\u6cb9\u6d78\u6ce1\u540e", "\u7ecf\u6c7d\u6cb9\u6d78\u6ce1\u540e\u6d4b\u5f97")),
        ("wax_remover", ("\u9664\u8721\u5242\u6d78\u6ce1\u540e", "\u7ecf\u9664\u8721\u5242\u6d78\u6ce1\u540e\u6d4b\u5f97")),
    ]
)

TEST_CONDITIONS = {
    "immediate": f"{DEG_C} 20 \u5206\u949f",
    "normal": f"{DEG_C} 24 \u5c0f\u65f6",
    "high_temp": f"{DEG_C} 24h -> {HOT_80}",
    "heat_aging": f"{DEG_C} 24h -> {HOT_80} 336h -> {DEG_C} 24h",
    "warm_water": f"{DEG_C} 24h -> {WARM_40} \u6e29\u6c34 336h -> {DEG_C} 24h",
    "gasoline": f"{DEG_C} 24h -> \u6c7d\u6cb9 1h -> {DEG_C} 24h",
    "wax_remover": f"{DEG_C} 24h -> \u9664\u8721\u5242 1h -> {DEG_C} 24h",
}

PEEL_TEST_METHOD = (
    "180\u5ea6\u5265\u79bb\u529b\uff1b25 mm \u5bbd\uff0c25 \u03bcm PET \u80cc\u6750\uff0c5 kg \u6eda\u538b\uff0c50 mm/min\u3002"
)
SHEAR_TEST_METHOD = "\u526a\u5207\u5f3a\u5ea6\uff1b25 mm \u00d7 25 mm \u642d\u63a5\uff0c5 kg \u6eda\u538b\uff0c50 mm/min\u3002"
PEEL_PAINTED_REMARK = f"\u6d4b\u8bd5\u57fa\u6750\uff1a{PAINTED}\u3002"
PEEL_PVC_REMARK = f"\u6d4b\u8bd5\u57fa\u6750\uff1a{PVC}\uff0c\u6d4b\u8bd5\u524d\u4f7f\u7528 3M N-210NT \u5e95\u6d82\u3002"
SHEAR_REMARK = f"\u6d4b\u8bd5\u57fa\u6750\uff1a{PAINTED_PVC}\u7ec4\u5408\u3002"

SERIES_FEATURES = "\n".join(
    [
        "\u5bf9\u6c7d\u8f66\u6f06\u9762\u4e0e\u57fa\u6750\u5177\u6709\u4f18\u5f02\u7684\u6700\u7ec8\u7c98\u63a5\u529b\u548c\u4fdd\u6301\u529b",
        "\u6ee1\u8db3\u591a\u9879 OEM \u89c4\u8303\u8981\u6c42",
        "\u80fd\u591f\u8ddf\u968f\u5851\u6599\u4ef6\u56e0\u6e29\u5ea6\u53d8\u5316\u4ea7\u751f\u7684\u6536\u7f29\u4e0e\u4f38\u957f",
        "\u7c98\u5f39\u6027\u6ce1\u68c9\u82af\u5177\u5907\u826f\u597d\u5e94\u529b\u91ca\u653e\u4e0e\u590d\u6742\u66f2\u9762\u8d34\u670d\u80fd\u529b",
        "\u5728\u4e0d\u540c\u6e29\u5ea6\u6761\u4ef6\u4e0b\u4fdd\u6301\u826f\u597d\u7c98\u63a5\u6027\u80fd",
        "\u5177\u5907\u8010\u5019\u3001\u8010\u6eb6\u5242\u4e0e\u8010\u9ad8\u6e29\u80fd\u529b",
    ]
)
SERIES_DESCRIPTION = (
    "3M GT7100 \u7cfb\u5217\u4e3a\u9762\u5411\u6c7d\u8f66\u5185\u5916\u9970\u4ef6\u56fa\u5b9a\u5e94\u7528\u8bbe\u8ba1\u7684"
    f"{BASE_MATERIAL}\u80f6\u5e26\uff0c\u91c7\u7528{ADHESIVE}\u4f53\u7cfb\uff0c"
    "\u517c\u5177\u9ad8\u67d4\u987a\u6027\u3001\u8010\u73af\u5883\u6027\u4e0e\u4f18\u5f02\u7684\u957f\u671f\u7c98\u63a5\u8868\u73b0\u3002"
)
SERIES_APPLICATIONS_HTML = (
    '<div data-oe-version="2.0"><ul>'
    "<li>\u6c7d\u8f66\u5916\u9970\u6761\u56fa\u5b9a</li>"
    "<li>\u6c7d\u8f66\u5185\u9970\u4ef6\u56fa\u5b9a</li>"
    "</ul></div>"
)
SPECIAL_APPLICATIONS_HTML = (
    '<div data-oe-version="2.0"><p>\u7ea2\u8272\u534a\u900f\u660e\u805a\u4e59\u70ef\u79bb\u578b\u819c\uff1b'
    "\u79bb\u578b\u819c\u539a\u5ea6\u4e0d\u8ba1\u5165\u603b\u539a\u5ea6\u3002</p></div>"
)

ITEMS = [
    ("GT7102", "0.2", GRAY, 10),
    ("GT7104", "0.4", GRAY, 20),
    ("GT7106", "0.6", GRAY, 30),
    ("GT7108", "0.8", GRAY, 40),
    ("GT7110", "1.0", GRAY, 50),
    ("GT7112", "1.2", GRAY, 60),
    ("GT7116", "1.6", GRAY, 70),
    ("GT7120", "2.0", GRAY, 80),
    ("GT7125", "2.5", GRAY, 90),
    ("GT7130", "3.0", WHITE, 100),
    ("GT7135", "3.5", WHITE, 110),
    ("GT7140", "4.0", WHITE, 120),
]


def _build_params():
    rows = []
    subject_defs = [
        ("peel_180_painted", PAINTED, PEEL_SUFFIX, PEEL_TEST_METHOD, PEEL_PAINTED_REMARK),
        ("peel_180_pvc", PVC, PEEL_SUFFIX, PEEL_TEST_METHOD, PEEL_PVC_REMARK),
        ("shear_painted_pvc", PAINTED_PVC, SHEAR_SUFFIX, SHEAR_TEST_METHOD, SHEAR_REMARK),
    ]
    order = [
        ("immediate", 10),
        ("normal", 20),
        ("high_temp", 30),
        ("heat_aging", 40),
        ("warm_water", 50),
    ]
    for prefix, subject, suffix, method, remark in subject_defs[:2]:
        for state_key, base_seq in order:
            label, desc_label = STATES[state_key]
            rows.append(
                (
                    f"{prefix}_{state_key}",
                    _name(subject, label, suffix),
                    _peel_desc(subject, desc_label),
                    "N/cm",
                    base_seq + (0 if prefix.endswith("painted") else 50),
                    method,
                    TEST_CONDITIONS[state_key],
                    remark,
                )
            )
    for state_key, sequence in [
        ("immediate", 110),
        ("normal", 120),
        ("high_temp", 130),
        ("warm_water", 140),
        ("gasoline", 150),
        ("wax_remover", 160),
    ]:
        label, desc_label = STATES[state_key]
        rows.append(
            (
                f"shear_painted_pvc_{state_key}",
                _name(PAINTED_PVC, label, SHEAR_SUFFIX),
                _shear_desc(desc_label),
                "MPa",
                sequence,
                SHEAR_TEST_METHOD,
                TEST_CONDITIONS[state_key],
                SHEAR_REMARK,
            )
        )
    return rows


PARAMS = _build_params()
PARAM_META = OrderedDict(
    (
        param_key,
        {
            "name": name,
            "description": description,
            "unit": unit,
            "sequence": sequence,
            "test_method": test_method,
            "test_condition": test_condition,
            "remark": remark,
        },
    )
    for param_key, name, description, unit, sequence, test_method, test_condition, remark in PARAMS
)


def _read_value_rows():
    source = DRAFT_DIR / "gt7100_catalog_item_specs.csv"
    rows = []
    with source.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            rows.append(
                {
                    "item_code": row["item_code"].strip(),
                    "param_key": row["param_key"].strip(),
                    "value": row["value"].strip(),
                    "sequence": int(row["sequence"] or 0),
                }
            )
    return rows


def _write_csv(path: Path, fieldnames, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _replace_rows(target_path: Path, key_names, new_rows):
    existing_rows = []
    key_set = {tuple((row.get(key) or "").strip() for key in key_names) for row in new_rows}
    fieldnames = list(new_rows[0].keys())
    if target_path.exists():
        with target_path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            if reader.fieldnames:
                fieldnames = reader.fieldnames
            for row in reader:
                row_key = tuple((row.get(key) or "").strip() for key in key_names)
                if row_key in key_set:
                    continue
                existing_rows.append(row)
    _write_csv(target_path, fieldnames, existing_rows + new_rows)


def build_rows():
    value_rows = _read_value_rows()
    series_rows = [
        {
            "brand_id_xml": "",
            "brand_name": BRAND_NAME,
            "series_name": SERIES_NAME,
            "product_features": SERIES_FEATURES,
            "product_description": SERIES_DESCRIPTION,
            "main_applications": SERIES_APPLICATIONS_HTML,
            "active": "1",
            "sequence": "10",
        }
    ]
    item_rows = []
    for code, thickness, color, sequence in ITEMS:
        item_rows.append(
            {
                "brand_id_xml": "",
                "brand_name": BRAND_NAME,
                "categ_id_xml": "category_tape_foam",
                "series_name": SERIES_NAME,
                "name": f"3M {code}",
                "code": code,
                "catalog_status": "published",
                "active": "1",
                "sequence": str(sequence),
                "equivalent_type": "",
                "product_features": SERIES_FEATURES,
                "product_description": SERIES_DESCRIPTION,
                "main_applications": SERIES_APPLICATIONS_HTML,
                "special_applications": SPECIAL_APPLICATIONS_HTML,
                "variant_thickness": thickness,
                "variant_adhesive_thickness": "",
                "variant_color": color,
                "variant_adhesive_type": ADHESIVE,
                "variant_base_material": BASE_MATERIAL,
                "variant_ref_price": "0.0",
                "variant_is_rohs": "0",
                "variant_is_reach": "0",
                "variant_is_halogen_free": "0",
                "variant_fire_rating": "none",
            }
        )
    param_rows = [
        {
            "param_key": param_key,
            "name": meta["name"],
            "value_type": "float",
            "description": meta["description"],
            "unit": meta["unit"],
            "selection_options": "",
            "sequence": str(meta["sequence"]),
            "active": "1",
        }
        for param_key, meta in PARAM_META.items()
    ]
    category_param_rows = [
        {
            "categ_id_xml": "category_tape_foam",
            "param_key": param_key,
            "param_name": meta["name"],
            "unit_override": meta["unit"],
            "sequence": str(meta["sequence"]),
            "required": "0",
            "active": "1",
            "show_in_form": "1",
            "allow_import": "1",
        }
        for param_key, meta in PARAM_META.items()
    ]
    item_spec_rows = []
    for row in value_rows:
        meta = PARAM_META[row["param_key"]]
        item_spec_rows.append(
            {
                "brand_id_xml": "",
                "brand_name": BRAND_NAME,
                "categ_id_xml": "category_tape_foam",
                "item_code": row["item_code"],
                "param_key": row["param_key"],
                "param_name": meta["name"],
                "value": row["value"],
                "unit": meta["unit"],
                "test_method": meta["test_method"],
                "test_condition": meta["test_condition"],
                "remark": meta["remark"],
                "sequence": str(row["sequence"]),
            }
        )
    return series_rows, item_rows, param_rows, category_param_rows, item_spec_rows


def write_corrected_csvs():
    series_rows, item_rows, param_rows, category_param_rows, item_spec_rows = build_rows()
    _write_csv(DRAFT_DIR / "gt7100_catalog_series.csv", list(series_rows[0].keys()), series_rows)
    _write_csv(DRAFT_DIR / "gt7100_catalog_items.csv", list(item_rows[0].keys()), item_rows)
    _write_csv(DRAFT_DIR / "gt7100_catalog_params.csv", list(param_rows[0].keys()), param_rows)
    _write_csv(
        DRAFT_DIR / "gt7100_catalog_category_params.csv",
        list(category_param_rows[0].keys()),
        category_param_rows,
    )
    _write_csv(DRAFT_DIR / "gt7100_catalog_item_specs.csv", list(item_spec_rows[0].keys()), item_spec_rows)

    _replace_rows(BASE_DIR / "catalog_series.csv", ("brand_name", "series_name"), series_rows)
    _replace_rows(BASE_DIR / "catalog_items.csv", ("brand_name", "code"), item_rows)
    _replace_rows(BASE_DIR / "catalog_params.csv", ("param_key",), param_rows)
    _replace_rows(BASE_DIR / "catalog_category_params.csv", ("categ_id_xml", "param_key"), category_param_rows)
    _replace_rows(BASE_DIR / "catalog_item_specs.csv", ("item_code", "param_key"), item_spec_rows)
    return {
        "series": len(series_rows),
        "items": len(item_rows),
        "params": len(param_rows),
        "category_params": len(category_param_rows),
        "item_specs": len(item_spec_rows),
    }


def import_to_odoo(env):
    category = env.ref(CATEGORY_XMLID)
    brand = env["diecut.brand"].search([("name", "=", BRAND_NAME)], limit=1)
    if not brand:
        brand = env["diecut.brand"].create({"name": BRAND_NAME})

    series_model = env["diecut.catalog.series"].sudo()
    item_model = env["diecut.catalog.item"].sudo()
    param_model = env["diecut.catalog.param"].sudo()
    config_model = env["diecut.catalog.spec.def"].sudo()

    series = series_model.search([("brand_id", "=", brand.id), ("name", "=", SERIES_NAME)], limit=1)
    if not series:
        series = series_model.search([("brand_id", "=", brand.id), ("name", "ilike", "GT7100")], limit=1)
    series_vals = {
        "brand_id": brand.id,
        "name": SERIES_NAME,
        "product_features": SERIES_FEATURES,
        "product_description": SERIES_DESCRIPTION,
        "main_applications": SERIES_APPLICATIONS_HTML,
        "sequence": 10,
        "active": True,
    }
    if series:
        series.write(series_vals)
    else:
        series = series_model.create(series_vals)

    params_by_key = {}
    for param_key, meta in PARAM_META.items():
        param = param_model.search([("param_key", "=", param_key)], limit=1)
        vals = {
            "name": meta["name"],
            "param_key": param_key,
            "value_type": "float",
            "description": meta["description"],
            "unit": meta["unit"],
            "selection_options": False,
            "sequence": meta["sequence"],
            "active": True,
        }
        if param:
            param.write(vals)
        else:
            param = param_model.create(vals)
        params_by_key[param_key] = param

    configs_by_key = {}
    for param_key, meta in PARAM_META.items():
        param = params_by_key[param_key]
        config = config_model.search([("categ_id", "=", category.id), ("param_id", "=", param.id)], limit=1)
        vals = {
            "categ_id": category.id,
            "param_id": param.id,
            "name": meta["name"],
            "param_key": param_key,
            "value_type": "float",
            "unit": meta["unit"],
            "unit_override": meta["unit"],
            "selection_options": False,
            "sequence": meta["sequence"],
            "required": False,
            "active": True,
            "show_in_form": True,
            "allow_import": True,
        }
        if config:
            config.write(vals)
        else:
            config = config_model.create(vals)
        configs_by_key[param_key] = config

    value_map = OrderedDict()
    for row in _read_value_rows():
        value_map.setdefault(row["item_code"], []).append(row)

    imported_codes = []
    for code, thickness, color_name, sequence in ITEMS:
        color_id = item_model._resolve_or_create_taxonomy_id("diecut.color", color_name)
        adhesive_id = item_model._resolve_or_create_taxonomy_id("diecut.catalog.adhesive.type", ADHESIVE)
        base_id = item_model._resolve_or_create_taxonomy_id("diecut.catalog.base.material", BASE_MATERIAL)
        spec_commands = [Command.clear()]
        for row in value_map[code]:
            meta = PARAM_META[row["param_key"]]
            config = configs_by_key[row["param_key"]]
            spec_commands.append(
                Command.create(
                    {
                        "param_id": config.param_id.id,
                        "category_param_id": config.id,
                        "sequence": row["sequence"],
                        "param_key": config.param_key,
                        "param_name": config.name,
                        "unit": config.unit_override or config.unit,
                        "value_float": float(row["value"]),
                        "test_method": meta["test_method"],
                        "test_condition": meta["test_condition"],
                        "remark": meta["remark"],
                    }
                )
            )
        item_vals = {
            "name": f"3M {code}",
            "brand_id": brand.id,
            "categ_id": category.id,
            "series_id": series.id,
            "series_text": series.name,
            "code": code,
            "catalog_status": "published",
            "active": True,
            "sequence": sequence,
            "product_features": SERIES_FEATURES,
            "product_description": SERIES_DESCRIPTION,
            "main_applications": SERIES_APPLICATIONS_HTML,
            "special_applications": SPECIAL_APPLICATIONS_HTML,
            "variant_thickness": thickness,
            "variant_color": color_id,
            "variant_adhesive_type": adhesive_id,
            "variant_base_material": base_id,
            "variant_ref_price": 0.0,
            "variant_is_rohs": False,
            "variant_is_reach": False,
            "variant_is_halogen_free": False,
            "variant_fire_rating": "none",
            "spec_line_ids": spec_commands,
        }
        item = item_model.search([("brand_id", "=", brand.id), ("code", "=", code)], limit=1)
        ctx = dict(env.context, skip_spec_autofill=True, allow_spec_categ_change=True, skip_series_sync=True)
        if item:
            item.with_context(**ctx).write(item_vals)
        else:
            item = item_model.with_context(**ctx).create(item_vals)
        imported_codes.append(item.code)

    target_items = item_model.search([("brand_id", "=", brand.id), ("code", "in", imported_codes)])
    param_model.search([("param_key", "in", list(params_by_key))])._refresh_usage_counts()
    config_model.search([("categ_id", "=", category.id), ("param_id", "in", [param.id for param in params_by_key.values()])])._refresh_line_count()
    series._refresh_usage_counts()
    target_items._refresh_taxonomy_usage_counts_from_map(target_items._collect_taxonomy_usage_ids())
    env.cr.commit()
    return {
        "series_id": series.id,
        "item_count": len(imported_codes),
        "param_count": len(params_by_key),
        "spec_count": sum(len(rows) for rows in value_map.values()),
        "codes": imported_codes,
    }


if "env" in globals():
    counts = write_corrected_csvs()
    result = import_to_odoo(env)
    print({"csv": counts, "import": result})
