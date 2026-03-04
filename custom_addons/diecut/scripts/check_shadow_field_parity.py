# -*- coding: utf-8 -*-

"""
Usage (inside Odoo container):
odoo shell -d odoo -c /etc/odoo/odoo.conf --shell-file /mnt/extra-addons/diecut/scripts/check_shadow_field_parity.py --shell-interface=python
"""

import json


def main():
    if "env" not in globals():
        print("ERROR: this script must run in odoo shell context")
        return

    report = env["diecut.catalog.shadow.service"].compare_mapped_fields(limit=None, sample_size=20)
    print(json.dumps(report, ensure_ascii=False, indent=2, default=str))


main()
