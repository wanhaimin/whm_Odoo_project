import odoo
from odoo import api, SUPERUSER_ID

try:
    odoo.tools.config.parse_config(['-c', 'odoo.conf'])
    registry = odoo.registry('odoo_dev_new')
    with registry.cursor() as cr:
        env = api.Environment(cr, SUPERUSER_ID, {})
        models_to_check = [
            'material.category',
            'material.material',
            'sample.order',
            'diecut.quote'
        ]
        print("--- Checking Models ---")
        for model_name in models_to_check:
            model = env['ir.model'].search([('model', '=', model_name)])
            if model:
                print(f"Model {model_name}: FOUND (ID: {model.id})")
                # Check XML ID
                data = env['ir.model.data'].search([('model', '=', 'ir.model'), ('res_id', '=', model.id)])
                if data:
                    print(f"  XML ID: {data.module}.{data.name}")
                else:
                    print(f"  XML ID: NOT FOUND")
            else:
                print(f"Model {model_name}: NOT FOUND")
except Exception as e:
    print(f"Error: {e}")
