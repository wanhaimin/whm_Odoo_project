# -*- coding: utf-8 -*-

CODES = [
    "93005LE",
    "93005LEB",
    "93010LE",
    "93015LE",
    "93020LE",
    "9471LE",
    "9472LE",
    "9495LE",
    "9671LE",
    "9672LE",
]

SHARED_SPECS = [
    ("adhesion_hse_level", "\u9ad8", False),
    ("adhesion_lse_level", "\u9ad8", False),
    ("long_term_heat_resistance", "93", "\u00b0C"),
    ("short_term_heat_resistance", "149", "\u00b0C"),
    ("solvent_resistance_level", "\u4e2d", False),
]


def main():
    item_model = env["diecut.catalog.item"].sudo()
    param_model = env["diecut.catalog.param"].sudo()
    items = item_model.search([("brand_id.name", "=", "3M"), ("code", "in", CODES)])
    for item in items:
        for param_key, raw_value, unit in SHARED_SPECS:
            param = param_model.search([("param_key", "=", param_key)], limit=1)
            if not param:
                continue
            item.apply_param_payload(
                param=param,
                raw_value=raw_value,
                unit=unit or False,
                source_excerpt=f"{item.code} {param.name} {raw_value}{(' ' + unit) if unit else ''}",
            )
    env.cr.commit()
    print(f"updated_items={len(items)}")


main()
