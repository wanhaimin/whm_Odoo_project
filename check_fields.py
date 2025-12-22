import odoo
import os
import sys

# Setup Odoo
conf_path = 'odoo.conf'
odoo.tools.config.parse_config(['-c', conf_path])
registry = odoo.registry(odoo.tools.config['db_name'])

with registry.cursor() as cr:
    env = odoo.api.Environment(cr, odoo.SUPERUSER_ID, {})
    model = env['my.material']
    print(f"Model keys: {list(model._fields.keys())}")
    print(f"Website Published defined: {'website_published' in model._fields}")
    if 'website_published' in model._fields:
        field = model._fields['website_published']
        print(f"Field type: {field.type}")
        print(f"Field related: {field.related}")
    
    cr.execute("SELECT column_name FROM information_schema.columns WHERE table_name='my_material'")
    print(f"DB Columns: {[r[0] for r in cr.fetchall()]}")
