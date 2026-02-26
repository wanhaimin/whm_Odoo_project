import sys
import xmlrpc.client

url = 'http://localhost:8070'
db = 'Odoo19-diecut'
username = 'admin'
password = '12' # Default local testing admin password usually
common = xmlrpc.client.ServerProxy('{}/xmlrpc/2/common'.format(url))
try:
    uid = common.authenticate(db, username, password, {})
    if not uid:
        print("Auth failed using password 12. Trying admin/admin...")
        password = 'admin'
        uid = common.authenticate(db, username, password, {})
except Exception as e:
    print("Cannot connect via xmlrpc.")
    sys.exit(1)

if not uid:
    print("Authentication failed.")
    sys.exit(1)

models = xmlrpc.client.ServerProxy('{}/xmlrpc/2/object'.format(url))
suppliers = models.execute_kw(db, uid, password, 'product.supplierinfo', 'search_read', [[]], {'fields': ['id', 'price_per_m2', 'price']})

count = 0
for supplier in suppliers:
    if supplier.get('price_per_m2') and supplier['price_per_m2'] > 0:
        models.execute_kw(db, uid, password, 'product.supplierinfo', 'write', [[supplier['id']], {
            'price': supplier['price_per_m2']
        }])
        count += 1

print(f"✅ Fast API Fix: Updated {count} supplier records to sync price with price_per_m2.")
