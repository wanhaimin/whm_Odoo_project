import odoo
from odoo import api, SUPERUSER_ID

def check():
    conf = odoo.tools.config
    # Add path to your config file if needed
    # conf.parse_config(['-c', 'odoo.conf'])
    
    registry = odoo.modules.registry.Registry('odoo_dev_new')
    with registry.cursor() as cr:
        env = api.Environment(cr, SUPERUSER_ID, {})
        model = env['my.material']
        print(f"Model: {model._name}")
        print(f"Fields: {sorted(model._fields.keys())}")
        print(f"is_published in fields: {'is_published' in model._fields}")
        if 'is_published' in model._fields:
            print(f"is_published Definition: {model._fields['is_published']}")

if __name__ == "__main__":
    # This might need more setup for Odoo environment
    pass
