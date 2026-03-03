import odoo
from odoo import api, SUPERUSER_ID
import csv
import json
import re
from html import unescape

# 可选：是否在导出时自动补齐外部ID（会写库）
# - False: 纯只读导出（默认，最安全）
# - True:  为界面新建但缺失xml_id的记录创建 ir.model.data
AUTO_CREATE_EXTERNAL_IDS = True
MODULE_NAME = 'diecut'


def strip_html(html_str: str) -> str:
    """将 Odoo 富文本 HTML 转为干净的纯文本，供 Excel 编辑。
    - 去掉所有 <tag> 标签（含 <img> 等）
    - 解码 HTML 实体 (&amp; → &, &lt; → < 等)
    - 合并多余空行
    """
    if not html_str:
        return ''
    # 将 <br>, <br/>, </p> 替换为换行，保留段落间距
    text = re.sub(r'<br\s*/?>', '\n', html_str, flags=re.IGNORECASE)
    text = re.sub(r'</p>', '\n', text, flags=re.IGNORECASE)
    # 去掉所有 HTML 标签
    text = re.sub(r'<[^>]+>', '', text)
    # 解码 HTML 实体
    text = unescape(text)
    # 合并连续空行为单个换行
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def _slug(text: str) -> str:
    text = (text or '').strip().lower()
    text = re.sub(r'[^a-z0-9\u4e00-\u9fff]+', '_', text)
    return text.strip('_') or 'x'


def _ensure_external_id(env, record, model_name: str, fallback_prefix: str) -> str:
    """为缺失xml_id的记录补齐外部ID，返回 local id。"""
    if not record:
        return ''
    xml_map = record.get_external_id()
    full = xml_map.get(record.id)
    if full:
        return full.split(".", 1)[1] if "." in full else full

    base = f"{fallback_prefix}_{_slug(getattr(record, 'name', '') or getattr(record, 'display_name', ''))}_{record.id}"
    name = base
    seq = 1
    while env['ir.model.data'].search_count([('module', '=', MODULE_NAME), ('name', '=', name)]):
        seq += 1
        name = f"{base}_{seq}"

    env['ir.model.data'].create({
        'module': MODULE_NAME,
        'name': name,
        'model': model_name,
        'res_id': record.id,
        'noupdate': True,
    })
    return name


def local_xml_id(record, fallback_prefix: str, env=None, model_name: str = '') -> str:
    """优先返回外部ID的 local part（去掉 module. 前缀）。

    该导出脚本必须保持只读：不创建 ir.model.data，不写库。
    """
    if not record:
        return ''
    xml_map = record.get_external_id()
    full = xml_map.get(record.id)
    if full and "." in full:
        return full.split(".", 1)[1]
    if full:
        return full
    if AUTO_CREATE_EXTERNAL_IDS and env and model_name:
        return _ensure_external_id(env, record, model_name, fallback_prefix)
    return f"{fallback_prefix}_{record.id}"

# Setup env
odoo.tools.config.parse_config(['-c', '/etc/odoo/odoo.conf', '-d', 'odoo', '--db_host=db', '--db_user=odoo', '--db_password=odoo'])
import odoo.modules.registry
registry = odoo.modules.registry.Registry('odoo')

with registry.cursor() as cr:
    env = api.Environment(cr, SUPERUSER_ID, {'lang': 'zh_CN'})
    
    # 1. Export series to series.csv
    tmpl_recs = env['product.template'].search([('is_catalog', '=', True)])
    
    series_rows = []
    tmpl_local_xml_map = {}
    for tmpl in tmpl_recs:
        series_xml_id = local_xml_id(tmpl, 'catalog_ui', env=env, model_name='product.template')
        tmpl_local_xml_map[tmpl.id] = series_xml_id
        brand_xml = local_xml_id(tmpl.brand_id, 'brand_ui', env=env, model_name='diecut.brand') if tmpl.brand_id else ''
        categ_xml = local_xml_id(tmpl.categ_id, 'categ_ui', env=env, model_name='product.category') if tmpl.categ_id else ''

        series_rows.append([
            brand_xml,
            categ_xml,
            series_xml_id,
            tmpl.name or '',
            tmpl.series_name or '',
            tmpl.catalog_base_material or '',
            tmpl.catalog_adhesive_type or '',
            tmpl.catalog_characteristics or '',
            strip_html(tmpl.catalog_features or ''),
            strip_html(tmpl.catalog_applications or '')
        ])
        
    with open('/mnt/extra-addons/diecut/scripts/series.csv', 'w', encoding='utf-8-sig', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['brand_id_xml', 'categ_id_xml', 'series_xml_id', 'name', 'series_name', 'catalog_base_material', 'catalog_adhesive_type', 'catalog_characteristics', 'catalog_features', 'catalog_applications'])
        writer.writerows(series_rows)
        
    # 2. Export variants to variants.csv
    variant_recs = env['product.product'].search([('product_tmpl_id.is_catalog', '=', True)])
    
    # Collect all possible keys from variant fields
    base_headers = ['series_xml_id', 'default_code', 'variant_thickness', 'variant_color', 'variant_adhesive_type', 'variant_base_material', 'variant_peel_strength']
    extra_headers = set()
    
    variant_fields = []
    for fname, field in env['product.product']._fields.items():
        if not fname.startswith('variant_'):
            continue
        if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', fname):
            continue
        if fname in (
            'variant_seller_ids',
            'variant_tds_file',
            'variant_msds_file',
            'variant_datasheet',
            'variant_catalog_structure_image',
            'variant_tds_filename',
            'variant_msds_filename',
            'variant_datasheet_filename',
            'variant_replacement_catalog_ids',
        ):
            continue
        if not field.store:
            continue
        variant_fields.append(fname)
    
    for v in variant_recs:
        for f in variant_fields:
            if getattr(v, f):
                if f not in base_headers:
                    extra_headers.add(f)
                    
    headers_list = base_headers + sorted(list(extra_headers))
    
    variants_rows = []
    json_data = {}
    
    for v in variant_recs:
        series_xml_id = tmpl_local_xml_map.get(v.product_tmpl_id.id) or local_xml_id(
            v.product_tmpl_id, 'catalog_ui', env=env, model_name='product.template'
        )
        code = v.default_code or ''
        
        row = []
        v_dict = {'default_code': code}
        
        for h in headers_list:
            if h == 'series_xml_id':
                row.append(series_xml_id)
            elif h == 'default_code':
                row.append(code)
            else:
                val = getattr(v, h)
                val_str = str(val) if val else ''
                row.append(val_str)
                if val:
                    v_dict[h] = val_str
                    
        variants_rows.append(row)
        
        if series_xml_id not in json_data:
            json_data[series_xml_id] = []
        json_data[series_xml_id].append(v_dict)
        
    with open('/mnt/extra-addons/diecut/scripts/variants.csv', 'w', encoding='utf-8-sig', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(headers_list)
        writer.writerows(variants_rows)
        
    # Also reconstruct catalog_materials.json
    json_out = []
    for s_id, vars_list in json_data.items():
        json_out.append({
            'series_xml_id': "diecut." + s_id,
            'variants': vars_list
        })
        
    with open('/mnt/extra-addons/diecut/data/catalog_materials.json', 'w', encoding='utf-8') as f:
        json.dump(json_out, f, ensure_ascii=False, indent=4)
        
    if AUTO_CREATE_EXTERNAL_IDS:
        env.cr.commit()
        print("[+] 已自动补齐缺失外部ID（品牌/分类/系列）。")
    print(f"[+] Exported {len(series_rows)} series and {len(variants_rows)} variants to CSV.")
    print(f"[+] Reconstructed catalog_materials.json with {len(json_out)} series.")
