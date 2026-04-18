# -*- coding: utf-8 -*-
from odoo import api, SUPERUSER_ID


RATE_FIELDS = (
    "transport_rate",
    "management_rate",
    "utility_rate",
    "packaging_rate",
    "depreciation_rate",
    "profit_rate",
)


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    Quote = env["diecut.quote"].sudo()
    for field_name in RATE_FIELDS:
        records = Quote.search([(field_name, ">=", 1.0)])
        for record in records:
            record[field_name] = record[field_name] / 100.0
