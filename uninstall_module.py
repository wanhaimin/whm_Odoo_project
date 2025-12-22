# uninstall_module.py
import odoo
from odoo import api, SUPERUSER_ID

odoo.tools.config.parse_config(['-c', 'odoo.conf'])
registry = odoo.registry('odoo_dev_new')
with registry.cursor() as cr:
    env = api.Environment(cr, SUPERUSER_ID, {})
    mod = env['ir.module.module'].search([('name', '=', 'diecut_custom')])
    if mod:
        mod.button_immediate_uninstall()
        print("模块已强制卸载")
    else:
        print("未找到模块")
