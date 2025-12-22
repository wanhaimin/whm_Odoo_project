# find_error_view.py
import logging

try:
    env = self.env
    cr = env.cr

    print("Searching for <t t-esc=\"pager['total']\"/> in ir.ui.view...", flush=True)
    
    cr.execute("""
        SELECT id, name, key, xmlid
        FROM ir_ui_view 
        WHERE arch_db LIKE '%pager[%total%]%'
    """)
    views = cr.fetchall()
    
    if views:
        print(f"Found {len(views)} views:", flush=True)
        for v in views:
            print(f"ID: {v[0]}, Name: {v[1]}, Key: {v[2]}, XMLID: {v[3]}", flush=True)
    else:
        print("No matching views found in database arch_db.", flush=True)

except Exception as e:
    print(f"Error: {e}", flush=True)
