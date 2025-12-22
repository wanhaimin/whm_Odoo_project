import odoo
from odoo import api, SUPERUSER_ID
import sys

def check():
    try:
        registry = odoo.modules.registry.Registry('odoo_dev_new')
        with registry.cursor() as cr:
            env = api.Environment(cr, SUPERUSER_ID, {})
            model_name = 'my.material'
            if model_name not in env:
                print(f"Model {model_name} not found in environment.")
                return

            model = env[model_name]
            print(f"Model found: {model._name}")
            
            fields = model._fields.keys()
            print(f"Total fields: {len(fields)}")
            
            target_fields = ['is_published', 'website_published', 'website_url']
            for field in target_fields:
                if field in fields:
                    print(f"Field '{field}' exists.")
                    f_obj = model._fields[field]
                    print(f"  Type: {f_obj.type}")
                    print(f"  Related: {f_obj.related}")
                else:
                    print(f"Field '{field}' does NOT exist.")

    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    check()
