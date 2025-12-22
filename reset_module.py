#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
重置卡住的 Odoo 模块状态
"""

import odoorpc

# 连接到 Odoo
odoo = odoorpc.ODOO('localhost', port=8069)
odoo.login('odoo_db', 'admin', 'admin')  # 请根据实际情况修改数据库名、用户名和密码

# 查找 diecut_custom 模块
Module = odoo.env['ir.module.module']
module_ids = Module.search([('name', '=', 'diecut_custom')])

if module_ids:
    module = Module.browse(module_ids[0])
    print(f"当前模块状态: {module.state}")
    
    # 重置状态为 installed
    Module.write(module_ids, {'state': 'installed'})
    print("模块状态已重置为 'installed'")
else:
    print("未找到 diecut_custom 模块")
