
import xmlrpc.client

url = "http://localhost:8070"
db = "odoo"
username = "admin" # Guessing admin/admin
password = "admin"

try:
    common = xmlrpc.client.ServerProxy('{}/xmlrpc/2/common'.format(url))
    uid = common.authenticate(db, username, password, {})
    
    if not uid:
        print("Auth failed")
        exit()

    models = xmlrpc.client.ServerProxy('{}/xmlrpc/2/object'.format(url))
    
    # Check fields for diecut.quote
    fields = models.execute_kw(db, uid, password, 'ir.model.fields', 'search_read',
        [[['model', 'in', ['diecut.quote', 'diecut.quote.material.line', 'material.material']]]],
        {'fields': ['name', 'model', 'ttype', 'ondelete']}
    )
    
    print("Checking for mismatches...")
    # I cannot easily check code here, but I can list what DB thinks.
    for f in fields:
        if f['ttype'] == 'char' and f.get('ondelete'):
             print(f"SUSPICIOUS: Char field with ondelete: {f['model']}.{f['name']}")
        
        # Also check if I know it should be Char but DB says Selection
        known_chars = ['quote_category', 'step_1', 'step_2']
        if f['name'] in known_chars and f['ttype'] != 'char':
             print(f"MISMATCH: {f['model']}.{f['name']} is {f['ttype']} in DB but should be Char!")

except Exception as e:
    print(f"Error: {e}")
