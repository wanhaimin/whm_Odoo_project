@echo off
echo ========================================
echo 取消供应商的客户标记
echo ========================================
echo.

REM 激活虚拟环境
call venv\Scripts\activate.bat

echo 正在修改客户标记...
python odoo\odoo-bin shell -c odoo.conf -d odoo_dev_new << EOF
# 查找包含 "树志" 的联系人
partner = env['res.partner'].search([('name', 'ilike', '树志')], limit=1)

if partner:
    print(f"\n找到联系人: {partner.name}")
    print(f"当前客户排名: {partner.customer_rank}")
    print(f"当前供应商排名: {partner.supplier_rank}")
    
    # 取消客户标记
    partner.customer_rank = 0
    
    # 保存
    env.cr.commit()
    
    print(f"\n修改后客户排名: {partner.customer_rank}")
    print(f"修改后供应商排名: {partner.supplier_rank}")
    print("\n✅ 已成功取消客户标记!")
else:
    print("\n❌ 未找到包含 '树志' 的联系人")

EOF

echo.
echo 修改完成!
pause
