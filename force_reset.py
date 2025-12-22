import odoo
from odoo import api, SUPERUSER_ID

try:
    odoo.tools.config.parse_config(['-c', 'odoo.conf'])
    registry = odoo.registry('odoo_dev_new')
    with registry.cursor() as cr:
        env = api.Environment(cr, SUPERUSER_ID, {})
        
        # 1. 强制设为“未安装”状态
        print("Resetting module state...")
        mod = env['ir.module.module'].search([('name', '=', 'diecut_custom')])
        if mod:
            mod.write({'state': 'uninstalled'})
            cr.commit()
            print("Module state set to 'uninstalled'.")
            
        # 2. 清除冲突的模型数据记录
        print("Cleaning up model data residuals...")
        models_to_clean = [
            'material.category', 'material.material', 
            'sample.order', 'sample.order.line', 
            'diecut.quote', 'diecut.quote.layer'
        ]
        for m_name in models_to_clean:
            cr.execute("DELETE FROM ir_model_data WHERE module='diecut_custom' AND model='ir.model' AND name like %s", (f'model_{m_name.replace(".","_")}',))
            print(f"Cleaned XML ID for {m_name}")
        
        cr.commit()
        print("--- DONE ---")
except Exception as e:
    print(f"Error occurred: {e}")
