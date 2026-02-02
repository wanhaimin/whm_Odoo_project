#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
创建QC检验员演示账户
用户名: joel.willis
密码: qc123456
"""

import xmlrpc.client

# Odoo连接配置
url = 'http://localhost:8070'
db = 'odoo'
username = 'admin'  # 使用管理员账户创建用户
password = 'admin'

# 连接到Odoo
common = xmlrpc.client.ServerProxy(f'{url}/xmlrpc/2/common')
uid = common.authenticate(db, username, password, {})

if not uid:
    print("❌ 管理员登录失败！请检查admin密码")
    exit(1)

models = xmlrpc.client.ServerProxy(f'{url}/xmlrpc/2/object')

# 1. 创建QC检验员用户
print("📝 正在创建QC检验员账户...")
user_data = {
    'name': 'Joel Willis',
    'login': 'joel.willis',
    'email': 'joel.willis@example.com',
    'password': 'qc123456',
    'groups_id': [(6, 0, [
        # 基础用户组
        models.execute_kw(db, uid, password,
            'ir.model.data', 'xmlid_to_res_id', ['base.group_user']),
    ])],
}

# 检查用户是否已存在
existing_user = models.execute_kw(db, uid, password,
    'res.users', 'search_read',
    [[('login', '=', 'joel.willis')]],
    {'fields': ['id', 'name'], 'limit': 1})

if existing_user:
    joel_user_id = existing_user[0]['id']
    print(f"✅ 用户已存在: Joel Willis (ID: {joel_user_id})")
    # 更新密码
    models.execute_kw(db, uid, password,
        'res.users', 'write',
        [[joel_user_id], {'password': 'qc123456'}])
    print("🔑 密码已重置为: qc123456")
else:
    joel_user_id = models.execute_kw(db, uid, password,
        'res.users', 'create',
        [user_data])
    print(f"✅ 创建成功: Joel Willis (ID: {joel_user_id})")

# 2. 创建一个测试刀模并分配QC任务给Joel
print("\n📦 正在创建测试刀模...")

# 获取已存在的刀模或创建新的
mold_data = {
    'code': 'DEMO-QC-001',
    'name': 'QC演示刀模',
    'mold_type': 'steel',
    'state': 'draft',
}

existing_mold = models.execute_kw(db, uid, password,
    'diecut.mold', 'search_read',
    [[('code', '=', 'DEMO-QC-001')]],
    {'fields': ['id', 'code', 'state'], 'limit': 1})

if existing_mold:
    mold_id = existing_mold[0]['id']
    print(f"✅ 测试刀模已存在 (ID: {mold_id})")
    # 重置为草稿状态
    models.execute_kw(db, uid, password,
        'diecut.mold', 'write',
        [[mold_id], {'state': 'draft', 'qc_assigned_to': False}])
else:
    mold_id = models.execute_kw(db, uid, password,
        'diecut.mold', 'create',
        [mold_data])
    print(f"✅ 创建测试刀模成功 (ID: {mold_id})")

# 3. 提交QC检验并分配给Joel
print(f"\n🔍 正在分配QC检验任务给 Joel Willis...")

# 更新刀模状态为QC检验并分配给Joel
models.execute_kw(db, uid, password,
    'diecut.mold', 'write',
    [[mold_id], {
        'state': 'qc_inspection',
        'qc_assigned_to': joel_user_id,
    }])

# 创建活动提醒
activity_type_id = models.execute_kw(db, uid, password,
    'mail.activity.type', 'search',
    [[('name', '=', 'To Do')]], {'limit': 1})

if activity_type_id:
    activity_data = {
        'res_model_id': models.execute_kw(db, uid, password,
            'ir.model', 'search',
            [[('model', '=', 'diecut.mold')]], {'limit': 1})[0],
        'res_id': mold_id,
        'activity_type_id': activity_type_id[0],
        'summary': f'QC检验: DEMO-QC-001',
        'note': '''
            <p><strong>刀模QC检验任务</strong></p>
            <ul>
                <li>刀模编号: DEMO-QC-001</li>
                <li>刀模名称: QC演示刀模</li>
                <li>提交人: Administrator</li>
            </ul>
            <p>请及时进行QC检验并标记为合格或不合格。</p>
        ''',
        'user_id': joel_user_id,
    }
    
    activity_id = models.execute_kw(db, uid, password,
        'mail.activity', 'create',
        [activity_data])
    print(f"✅ 创建活动提醒成功 (ID: {activity_id})")

print("\n" + "="*60)
print("🎉 QC检验员演示账户创建完成！")
print("="*60)
print(f"""
📋 账户信息:
   姓名: Joel Willis
   用户名: joel.willis
   密码: qc123456
   
📦 测试刀模:
   编号: DEMO-QC-001
   名称: QC演示刀模
   状态: QC检验中
   
🔍 Joel的待办任务:
   1. 登录系统 (http://localhost:8070)
   2. 点击右上角的"活动"图标查看待办
   3. 或进入"模切管理 → 配置 → 刀模库"
   4. 打开刀模 DEMO-QC-001
   5. 点击"QC合格"或"QC不合格"完成检验
   
✅ 检验流程:
   - 点击"QC合格" → 刀模变为"可使用"状态
   - 点击"QC不合格" → 必须填写QC备注 → 刀模退回"草稿"状态
""")
