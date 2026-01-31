# env = self.env # Assumed running in Odoo Shell where 'env' is global
print("Starting Sync...")
materials = env['my.material'].search([]) # type: ignore
print(f"Found {len(materials)} materials.")
for mat in materials:
    try:
        mat._create_or_update_product()
        # Ensure purchase_ok is True
        if mat.product_id:
            mat.product_id.write({'purchase_ok': True, 'sale_ok': True, 'detailed_type': 'product'})
            print(f"Synced {mat.name} -> {mat.product_id.name} (ID: {mat.product_id.id})")
    except Exception as e:
        print(f"Error syncing {mat.name}: {e}")

env.cr.commit() # type: ignore
print("Sync Finished.")
