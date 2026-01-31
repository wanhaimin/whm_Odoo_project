import xmlrpc.client
import sys

try:
    url = 'http://localhost:8070'
    db = 'my_odoo_project'
    username = 'admin'
    password = 'admin'

    common = xmlrpc.client.ServerProxy('{}/xmlrpc/2/common'.format(url))
    uid = common.authenticate(db, username, password, {})
    models = xmlrpc.client.ServerProxy('{}/xmlrpc/2/object'.format(url))

    # Search for all materials
    ids = models.execute_kw(db, uid, password, 'my.material', 'search', [[]])
    print(f"Found {len(ids)} materials to sync.")

    # Read them to get names (optional, just for logging) and force a write
    materials = models.execute_kw(db, uid, password, 'my.material', 'read', [ids, ['name']])
    
    for mat in materials:
        print(f"Syncing material: {mat['name']} (ID: {mat['id']})")
        # Write the same name back to trigger the 'write' method override
        models.execute_kw(db, uid, password, 'my.material', 'write', [[mat['id']], {'name': mat['name']}])

    print("Success: All materials have been synced to Products.")

except Exception as e:
    print(f"Error: {e}")
