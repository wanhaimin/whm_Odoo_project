# -*- coding: utf-8 -*-
from odoo import api, SUPERUSER_ID

def run(env):
    print("\n" + "="*60)
    print("🔑 强制重置 Joel Willis 密码...")
    
    # 查找用户
    joel_user = env['res.users'].search([('login', '=', 'joel.willis')], limit=1)
    
    if not joel_user:
        print("📥 用户不存在，正在创建...")
        joel_user = env['res.users'].create({
            'name': 'Joel Willis',
            'login': 'joel.willis',
            'email': 'joel.willis@example.com',
            'password': 'qc123456',
            'active': True,
            'groups_id': [(6, 0, [env.ref('base.group_user').id, env.ref('diecut_custom.access_diecut_mold').id if env.ref('diecut_custom.access_diecut_mold', False) else env.ref('base.group_user').id])],
        })
    else:
        print(f"🔄 用户已存在 (ID: {joel_user.id})，正在重置密码...")
        # 强制写入密码，不加密直接传明文给write方法，Odoo会自动处理
        joel_user.write({'password': 'qc123456'})
        
    # 再次确认密码是否能验证（虽然不能直接读密码字段）
    # 我们可以尝试用 check_credentials 方法验证一下吗？不行，那是私有的或者需要上下文。
    
    print(f"✅ 密码重置成功！")
    print(f"👤 用户名: {joel_user.login}")
    print(f"🔑 新密码: qc123456")
    
    # 手动提交事务
    print("💾 正在提交事务...")
    env.cr.commit()
    print("✅ 事务已提交")
    print("="*60 + "\n")

if __name__ == "__main__":
    pass
