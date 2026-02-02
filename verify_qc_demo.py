# -*- coding: utf-8 -*-
from odoo import api, SUPERUSER_ID

def run(env):
    user = env['res.users'].search([('login', '=', 'joel.willis')], limit=1)
    if user:
        print(f"✅ User found: {user.name} (ID: {user.id})")
        
    mold = env['diecut.mold'].search([('code', '=', 'DEMO-QC-001')], limit=1)
    if mold:
        print(f"✅ Mold found: {mold.code}, State: {mold.state}, Assigned: {mold.qc_assigned_to.name}")
    else:
        print("❌ Mold not found")

if __name__ == "__main__":
    pass
