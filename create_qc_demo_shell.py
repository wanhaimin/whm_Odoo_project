# -*- coding: utf-8 -*-
import logging
from odoo import api, SUPERUSER_ID

def run(env):
    print("\n" + "="*60)
    print("🚀 开始创建演示数据...")
    
    # 1. 创建QC检验员用户
    user_model = env['res.users']
    user_vals = {
        'name': 'Joel Willis',
        'login': 'joel.willis',
        'email': 'joel.willis@example.com',
        'password': 'qc123456',
        'active': True,
    }
    
    # 查找或创建用户
    existing_user = user_model.search([('login', '=', 'joel.willis')], limit=1)
    if existing_user:
        joel_user = existing_user
        joel_user.write({'password': 'qc123456'})
        print(f"✅ 用户已存在，密码已重置: {joel_user.name}")
    else:
        # 添加基础用户组
        group_user = env.ref('base.group_user')
        user_vals['groups_id'] = [(6, 0, [group_user.id])]
        joel_user = user_model.create(user_vals)
        print(f"✅ 用户创建成功: {joel_user.name}")

    # 2. 创建测试刀模
    mold_model = env['diecut.mold']
    mold_vals = {
        'code': 'DEMO-QC-001',
        'name': 'QC演示刀模',
        'mold_type': 'steel',
        'state': 'draft',
    }
    
    mold = mold_model.search([('code', '=', 'DEMO-QC-001')], limit=1)
    if mold:
        # 重置状态
        mold.write({'state': 'draft', 'qc_assigned_to': False})
        print(f"✅ 刀模已存在，已重置: {mold.code}")
    else:
        mold = mold_model.create(mold_vals)
        print(f"✅ 刀模创建成功: {mold.code}")

    # 3. 分配QC任务
    print(f"🔍 正在分配QC检验任务给 {joel_user.name}...")
    
    # 通过向导逻辑分配（模拟）或者直接写入
    mold.write({
        'state': 'qc_inspection',
        'qc_assigned_to': joel_user.id,
    })
    
    # 创建活动
    activity_type = env.ref('mail.mail_activity_data_todo', raise_if_not_found=False)
    if not activity_type:
        activity_type = env['mail.activity.type'].search([('name', '=', 'To Do')], limit=1)
        
    if activity_type:
        env['mail.activity'].create({
            'res_model_id': env['ir.model']._get('diecut.mold').id,
            'res_id': mold.id,
            'activity_type_id': activity_type.id,
            'summary': 'QC检验: DEMO-QC-001',
            'note': '<p>请及时进行QC检验</p>',
            'user_id': joel_user.id,
        })
        print(f"✅ 活动任务已分配")

    # 提交修改
    env.cr.commit()
    
    print("\n" + "="*60)
    print("🎉 演示环境准备就绪！")
    print(f"👉 登录账号: joel.willis")
    print(f"👉 登录密码: qc123456")
    print("="*60 + "\n")

if __name__ == "__main__":
    # 该脚本将通过 odoo shell 运行，不需要在这里初始化
    pass
