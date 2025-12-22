#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
取消供应商的客户标记
"""

import sys
import os

# 添加 Odoo 路径
sys.path.append(os.path.join(os.path.dirname(__file__), 'odoo'))

import odoo
from odoo import api

# 配置
config_file = 'odoo.conf'
db_name = 'odoo_dev_new'

# 初始化 Odoo
odoo.tools.config.parse_config(['-c', config_file])

# 连接数据库
with odoo.api.Environment.manage():
    registry = odoo.registry(db_name)
    with registry.cursor() as cr:
        env = api.Environment(cr, odoo.SUPERUSER_ID, {})
        
        # 查找包含 "树志" 的联系人
        Partner = env['res.partner']
        partner = Partner.search([('name', 'ilike', '树志')], limit=1)
        
        if partner:
            print(f"\n找到联系人: {partner.name}")
            print(f"当前客户排名: {partner.customer_rank}")
            print(f"当前供应商排名: {partner.supplier_rank}")
            
            # 取消客户标记
            partner.write({'customer_rank': 0})
            
            # 提交事务
            cr.commit()
            
            print(f"\n修改后客户排名: {partner.customer_rank}")
            print(f"修改后供应商排名: {partner.supplier_rank}")
            print("\n✅ 已成功取消客户标记!")
        else:
            print("\n❌ 未找到包含 '树志' 的联系人")
