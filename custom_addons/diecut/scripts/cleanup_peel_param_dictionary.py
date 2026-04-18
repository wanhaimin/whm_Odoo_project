# -*- coding: utf-8 -*-
import json


STANDARD_PARAM_KEY = "peel_strength_180"
STANDARD_SCHEMA = [
    {"key": "substrate", "label": "\u88ab\u8d34\u5408\u7269", "sequence": 10},
    {"key": "state", "label": "\u72b6\u6001", "sequence": 20},
    {"key": "temperature", "label": "\u6e29\u5ea6", "sequence": 30},
    {"key": "dwell_time", "label": "\u9a7b\u7559\u65f6\u95f4", "sequence": 40},
]
LEGACY_KEYS = ["peel_strength", "foil_peel_strength", "peel_adhesion"]


def main():
    param_model = env["diecut.catalog.param"].sudo()
    spec_line_model = env["diecut.catalog.item.spec.line"].sudo()

    standard_param = param_model.search([("param_key", "=", STANDARD_PARAM_KEY)], limit=1)
    if standard_param:
        env.cr.execute(
            """
            UPDATE diecut_catalog_param
               SET name = %s,
                   description = %s,
                   condition_schema_json = %s,
                   active = TRUE
             WHERE id = %s
            """,
            (
                "180\u00b0\u5265\u79bb\u529b",
                (
                    "\u6807\u51c6\u5265\u79bb\u529b\u53c2\u6570\uff0c\u8bf7\u4f18\u5148\u4f7f\u7528\u8be5\u53c2\u6570\uff0c"
                    "\u5e76\u901a\u8fc7\u6761\u4ef6\u660e\u7ec6\u8bb0\u5f55\u88ab\u8d34\u5408\u7269\u3001\u72b6\u6001\u3001"
                    "\u6e29\u5ea6\u3001\u9a7b\u7559\u65f6\u95f4\u7b49\u7ef4\u5ea6\u3002"
                ),
                json.dumps(STANDARD_SCHEMA, ensure_ascii=False, indent=2),
                standard_param.id,
            ),
        )

    legacy_params = param_model.search([("param_key", "in", LEGACY_KEYS)])
    for param in legacy_params:
        line_count = spec_line_model.search_count([("param_id", "=", param.id)])
        description = (param.description or "").strip()
        compat_note = (
            "\u5386\u53f2\u517c\u5bb9\u53c2\u6570\uff0c\u65b0\u6570\u636e\u8bf7\u4f18\u5148\u4f7f\u7528"
            " \u300c180\u00b0\u5265\u79bb\u529b\u300d \u5e76\u901a\u8fc7\u6761\u4ef6\u660e\u7ec6\u627f\u8f7d"
            "\u88ab\u8d34\u5408\u7269\u3001\u72b6\u6001\u7b49\u7ef4\u5ea6\u3002"
        )
        if compat_note not in description:
            description = f"{description}\n{compat_note}".strip()
        if line_count == 0:
            active = False
            name = f"{param.name or param.param_key}\uff08\u5386\u53f2\u505c\u7528\uff09"
        else:
            active = True
            name = f"{(param.name or param.param_key).replace('\uff08\u5386\u53f2\u505c\u7528\uff09', '')}\uff08\u517c\u5bb9\uff09"
        env.cr.execute(
            """
            UPDATE diecut_catalog_param
               SET name = %s,
                   description = %s,
                   active = %s
             WHERE id = %s
            """,
            (name, description, active, param.id),
        )

    obsolete_params = param_model.search(
        [
            "|",
            ("param_key", "=ilike", "peel_180_%"),
            ("param_key", "=ilike", "180_peel_%"),
        ]
    )
    disabled = 0
    for param in obsolete_params:
        line_count = spec_line_model.search_count([("param_id", "=", param.id)])
        if line_count:
            continue
        name = param.name or param.param_key
        if "\u5386\u53f2\u505c\u7528" not in (param.name or ""):
            name = f"{name}\uff08\u5386\u53f2\u505c\u7528\uff09"
        env.cr.execute(
            """
            UPDATE diecut_catalog_param
               SET name = %s,
                   active = FALSE
             WHERE id = %s
            """,
            (name, param.id),
        )
        disabled += 1

    print(f"standard_param={standard_param.id if standard_param else 'missing'}")
    print(f"legacy_updated={len(legacy_params)}")
    print(f"obsolete_disabled={disabled}")
    env.cr.commit()


main()
