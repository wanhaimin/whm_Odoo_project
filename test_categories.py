# -*- coding: utf-8 -*-
env = self.env
raw_products = env['product.template'].search([('is_raw_material', '=', True)])
print("Products mapped as raw material:")
for p in raw_products:
    print(p.name, p.categ_id.name, p.categ_id.category_type)

# Let's see what category search_panel_select_range returns for raw_material_categ_id
# We don't have that method directly, but let's check what categories exist.
all_cats = env['product.category'].search([('category_type', '!=', 'raw')])
print("\nNon-raw Categories:")
for c in all_cats:
    print(c.name, c.category_type, c.parent_id.name)
