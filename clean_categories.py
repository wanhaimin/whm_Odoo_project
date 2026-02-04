
Category = env['product.category']
IrModelData = env['ir.model.data']

xml_names = ['原材料', '胶带类', '双面胶带', '单面胶带', '导电胶带', '导热胶带', '泡棉类', 'PE泡棉', 'IXPE泡棉', 'PU泡棉', '离型膜', '保护膜', '屏蔽材料', '铜箔', '铝箔', '导电布', '其他辅料', '半成品', '分切料', '复合材料', '成品', '模切件', '定制产品']

safe_cat = Category.search([], limit=1)

def table_exists(table_name):
    env.cr.execute("SELECT count(*) FROM information_schema.tables WHERE table_name = %s", (table_name,))
    return env.cr.fetchone()[0] > 0

print("--- 再次尝试清理的双面胶带等冲突项 ---")

for cat_name in xml_names:
    existing = Category.search([('name', '=', cat_name)])
    for cat in existing:
        xml_id_record = IrModelData.search([('model', '=', 'product.category'), ('res_id', '=', cat.id)])
        if not xml_id_record:
            print(f"正在强制重定向并删除: {cat_name} (ID: {cat.id})")
            try:
                if table_exists('material_material'):
                    # 将引用指向安全分类，而不是 NULL
                    env.cr.execute("UPDATE material_material SET category_id = %s WHERE category_id = %s", (safe_cat.id, cat.id,))
                if table_exists('my_material'):
                    env.cr.execute("UPDATE my_material SET category_id = %s WHERE category_id = %s", (safe_cat.id, cat.id,))
                if table_exists('product_template'):
                    env.cr.execute("UPDATE product_template SET categ_id = %s WHERE categ_id = %s", (safe_cat.id, cat.id,))
                
                env.cr.commit()
                cat.unlink()
                env.cr.commit()
                print(f"删除成功: {cat_name}")
            except Exception as e:
                env.cr.rollback()
                print(f"删除 {cat_name} 仍然失败: {str(e)}")

print("--- 清理结束 ---")
