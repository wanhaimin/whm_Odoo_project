# -*- coding: utf-8 -*-
from odoo import api, SUPERUSER_ID


RATE_FIELDS = (
    "transport_rate",
    "management_rate",
    "utility_rate",
    "packaging_rate",
    "depreciation_rate",
)

DEFAULT_RATE_FIXES = {
    "transport_rate": {1.0: 0.01},
    "management_rate": {5.0: 0.03, 0.05: 0.03},
    "utility_rate": {2.0: 0.01, 0.02: 0.01},
    "packaging_rate": {1.0: 0.01},
    "depreciation_rate": {2.0: 0.01, 0.02: 0.01},
}


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    Quote = env["diecut.quote"].sudo()

    for field_name in RATE_FIELDS:
        for record in Quote.search([(field_name, ">=", 1.0)]):
            record[field_name] = record[field_name] / 100.0

    for field_name, value_map in DEFAULT_RATE_FIXES.items():
        for old_value, new_value in value_map.items():
            records = Quote.search([(field_name, "=", old_value)])
            records.write({field_name: new_value})
