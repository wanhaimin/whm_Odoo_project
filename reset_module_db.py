#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
重置卡住的 Odoo 模块状态 - 使用直接数据库连接
"""

import psycopg2

# 数据库连接参数 - 请根据您的实际配置修改
DB_HOST = 'localhost'
DB_PORT = 5432
DB_NAME = 'odoo_dev_new'  # 您的数据库名
DB_USER = 'odoo'     # 修改为您的数据库用户
DB_PASSWORD = 'odoo' # 修改为您的数据库密码

MODULE_NAME = 'diecut_custom'

try:
    # 连接数据库
    conn = psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    
    cursor = conn.cursor()
    
    # 查询当前模块状态
    cursor.execute(
        "SELECT id, name, state FROM ir_module_module WHERE name = %s",
        (MODULE_NAME,)
    )
    result = cursor.fetchone()
    
    if result:
        module_id, name, current_state = result
        print(f"找到模块: {name}")
        print(f"当前状态: {current_state}")
        
        # 更新状态为 installed
        cursor.execute(
            "UPDATE ir_module_module SET state = 'installed' WHERE name = %s",
            (MODULE_NAME,)
        )
        
        conn.commit()
        print(f"✓ 模块状态已成功重置为 'installed'")
        print("\n请刷新浏览器页面查看效果")
        
    else:
        print(f"未找到模块: {MODULE_NAME}")
    
    cursor.close()
    conn.close()
    
except psycopg2.Error as e:
    print(f"数据库错误: {e}")
    print("\n如果连接失败,请检查:")
    print("1. PostgreSQL 服务是否正在运行")
    print("2. 数据库名称、用户名、密码是否正确")
    print("3. 数据库连接参数(host, port)是否正确")
except Exception as e:
    print(f"发生错误: {e}")
