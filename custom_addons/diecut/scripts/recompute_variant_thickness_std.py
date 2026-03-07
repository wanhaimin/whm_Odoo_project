# -*- coding: utf-8 -*-

"""Recompute variant_thickness_std from variant_thickness for all variants.

Run with:
odoo shell -d odoo -c /etc/odoo/odoo.conf --shell-file /mnt/extra-addons/diecut/scripts/recompute_variant_thickness_std.py
"""

batch_size = 500
Product = env['product.product'].with_context(active_test=False)

ids = Product.search([]).ids
total = len(ids)
updated = 0

for start in range(0, total, batch_size):
    batch_ids = ids[start:start + batch_size]
    batch = Product.browse(batch_ids)
    for record in batch:
        new_val = record._normalize_thickness_std(record.variant_thickness)
        if record.variant_thickness_std != new_val:
            record.with_context(skip_variant_std_sync=True).write({
                'variant_thickness_std': new_val,
            })
            updated += 1
    env.cr.commit()

print(f"[DIECUT] variant_thickness_std recompute done: updated={updated}, total={total}")

raise SystemExit(0)
