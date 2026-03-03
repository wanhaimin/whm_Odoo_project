import os
import json
import csv
import xml.etree.ElementTree as ET

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(SCRIPT_DIR, '..', 'data')

def export_data():
    series_rows = []
    
    xml_files = sorted(
        f for f in os.listdir(DATA_DIR)
        if f.startswith('catalog_') and f.endswith('.xml') and f != 'catalog_materials.json'
    )
    for xf in xml_files:
        path = os.path.join(DATA_DIR, xf)
        if not os.path.exists(path):
            continue
            
        try:
            tree = ET.parse(path)
            root = tree.getroot()
        except ET.ParseError as e:
            print(f"[!] 跳过无法解析的 XML: {xf} -> {e}")
            continue
        
        # 提取 product.template 的记录
        for record in root.findall('.//record[@model="product.template"]'):
            series_id = record.get('id')
            
            row = {
                'series_xml_id': series_id,
                'name': '',
                'series_name': '',
                'brand_id_xml': '',
                'categ_id_xml': '',
                'catalog_base_material': '',
                'catalog_adhesive_type': '',
                'catalog_characteristics': '',
                'catalog_features': '',
                'catalog_applications': ''
            }
            
            for field in record.findall('field'):
                name = field.get('name')
                ref = field.get('ref')
                text = field.text or ''
                
                if name == 'name': row['name'] = text.strip()
                elif name == 'series_name': row['series_name'] = text.strip()
                elif name == 'catalog_base_material': row['catalog_base_material'] = text.strip()
                elif name == 'catalog_adhesive_type': row['catalog_adhesive_type'] = text.strip()
                elif name == 'catalog_characteristics': row['catalog_characteristics'] = text.strip()
                elif name == 'catalog_features': row['catalog_features'] = text.strip()
                elif name == 'catalog_applications': row['catalog_applications'] = text.strip()
                elif name == 'brand_id': row['brand_id_xml'] = ref
                elif name == 'categ_id': row['categ_id_xml'] = ref
                
            series_rows.append([
                row['brand_id_xml'], row['categ_id_xml'], row['series_xml_id'],
                row['name'], row['series_name'], row['catalog_base_material'],
                row['catalog_adhesive_type'], row['catalog_characteristics'],
                row['catalog_features'], row['catalog_applications']
            ])

    with open(os.path.join(SCRIPT_DIR, 'series.csv'), 'w', encoding='utf-8-sig', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['brand_id_xml', 'categ_id_xml', 'series_xml_id', 'name', 'series_name', 'catalog_base_material', 'catalog_adhesive_type', 'catalog_characteristics', 'catalog_features', 'catalog_applications'])
        writer.writerows(series_rows)
        
    print(f"[+] 成功导出 {len(series_rows)} 个系列架构到 series.csv")

    
    json_path = os.path.join(DATA_DIR, 'catalog_materials.json')
    variants_rows = []
    # 保证这些核心列在前面
    base_headers = ['series_xml_id', 'default_code', 'variant_thickness', 'variant_color', 'variant_adhesive_type', 'variant_base_material', 'variant_peel_strength']
    extra_headers = set()
    
    if os.path.exists(json_path):
        with open(json_path, 'r', encoding='utf-8') as f:
            materials_data = json.load(f)
            
        # 收集所有的额外字段列
        for series in materials_data:
            for var in series.get('variants', []):
                for k in var.keys():
                    if k not in base_headers:
                        extra_headers.add(k)
                        
        headers_list = base_headers + sorted(list(extra_headers))
        
        for series in materials_data:
            # 兼容带有 diecut. 前缀的场景
            series_id = series.get('series_xml_id', '').replace('diecut.', '')
            for var in series.get('variants', []):
                row = []
                for h in headers_list:
                    if h == 'series_xml_id':
                        row.append(series_id)
                    else:
                        row.append(var.get(h, ''))
                variants_rows.append(row)
                
        with open(os.path.join(SCRIPT_DIR, 'variants.csv'), 'w', encoding='utf-8-sig', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(headers_list)
            writer.writerows(variants_rows)
            
        print(f"[+] 成功导出 {len(variants_rows)} 个变体数据到 variants.csv")

if __name__ == '__main__':
    export_data()
