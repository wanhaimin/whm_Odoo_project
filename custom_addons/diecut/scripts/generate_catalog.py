import os
import json
import csv
import re
from collections import defaultdict


def text_to_html(text: str) -> str:
    """将纯文本转为 Odoo 期望的富文本 HTML。
    - 如果已经是 HTML（包含 <p> 或 <br>）则原样返回
    - 否则按换行符拆分段落，每段用 <p>...</p> 包裹
    """
    if not text or not text.strip():
        return ''
    # 已经是 HTML，直接返回
    if re.search(r'<[a-z][a-z0-9]*[\s>]', text, re.IGNORECASE):
        return text
    # 纯文本：按换行拆分段落，包裹 <p>
    paragraphs = [line.strip() for line in text.strip().split('\n') if line.strip()]
    return ''.join(f'<p>{p}</p>' for p in paragraphs)

# ==========================================
# 选型目录自动生成器 (Catalog Generator)
# 用法：将业务部门维护好的系列表(series.csv)和变体表(variants.csv)放入本脚本同级目录。
# 运行即可自动在上一级的 data 目录生成 XML 和 JSON。
# ==========================================

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(SCRIPT_DIR, '..', 'data')

SERIES_CSV = os.path.join(SCRIPT_DIR, 'series.csv')
VARIANTS_CSV = os.path.join(SCRIPT_DIR, 'variants.csv')
JSON_OUTPUT = os.path.join(DATA_DIR, 'catalog_materials.json')
SAFE_MODE = True  # 安全模式：不删除现有XML、不自动改写__manifest__.py
# 你已确认“CSV为准”后可开启：
# - True: 删除 data/ 下不在当前 CSV 品牌集合中的 catalog_*_data.xml
# - False: 保留历史 XML（仅生成/覆盖本次品牌）
PRUNE_UNMATCHED_BRAND_XML = True

def generate_template_csvs():
    """如果目录里没有 CSV 模板文件，则自动生成示例模板供业务人员填写"""
    if not os.path.exists(SERIES_CSV):
        with open(SERIES_CSV, 'w', encoding='utf-8-sig', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['brand_id_xml', 'categ_id_xml', 'series_xml_id', 'name', 'series_name', 'catalog_base_material', 'catalog_adhesive_type', 'catalog_characteristics', 'catalog_features', 'catalog_applications'])
            writer.writerow(['brand_tesa', 'category_tape_foam', 'catalog_tesa_example', 'tesa® 示例系列', '754xx', 'PET', '丙烯酸', '耐化学', '黑色。', '防水。应用。'])
        print(f"[*] 已生成示例系列总表模板: {SERIES_CSV}")

    if not os.path.exists(VARIANTS_CSV):
        with open(VARIANTS_CSV, 'w', encoding='utf-8-sig', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['series_xml_id', 'default_code', 'variant_thickness', 'variant_color', 'variant_adhesive_type', 'variant_base_material', 'variant_peel_strength'])
            writer.writerow(['catalog_tesa_example', '75405-EX', '50 µm', '黑色', '丙烯酸', 'PET', '180°:17.6 N/cm'])
            writer.writerow(['catalog_tesa_example', '75410-EX', '100 µm', '黑色', '丙烯酸', 'PET', '180°:17.6 N/cm'])
        print(f"[*] 已生成示例型号明细表模板: {VARIANTS_CSV}")


def read_csv_safe(filepath):
    try:
        with open(filepath, 'r', encoding='utf-8-sig', newline='') as f:
            rows = list(csv.reader(f))
            return [[col.replace('\r', '') for col in row] for row in rows]
    except UnicodeDecodeError:
        with open(filepath, 'r', encoding='gbk', newline='') as f:
            rows = list(csv.reader(f))
            return [[col.replace('\r', '') for col in row] for row in rows]


def brand_to_xml_filename(brand_xml_id: str) -> str:
    """将 brand xml id 映射到脚本产物文件名。"""
    if brand_xml_id.startswith('brand_ui_'):
        parts = brand_xml_id.split('_')
        brand_str = "_".join(parts[2:-1]) if len(parts) >= 4 else parts[-1]
    elif brand_xml_id.startswith('brand_'):
        brand_str = brand_xml_id.replace('brand_', '')
    else:
        brand_str = brand_xml_id
    return f"catalog_{brand_str}_data.xml"

def run_generator():
    generate_template_csvs()

    # 1. 读入变体表 (血肉)
    variants_by_series = defaultdict(list)
    variant_headers = []
    
    variants_data = read_csv_safe(VARIANTS_CSV)
    if variants_data:
        headers = variants_data[0]
        variant_headers = headers
        for row in variants_data[1:]:
            if not row or not row[0].strip(): continue
            row_dict = dict(zip(headers, row))
            series_id = row_dict.pop('series_xml_id', '')
            if not series_id: continue
            clean_dict = {k: v.strip() for k, v in row_dict.items() if v and v.strip()}
            if clean_dict:
                variants_by_series[series_id].append(clean_dict)

    # 2. 读入系列表，并按品牌归类 (骨架)
    series_by_brand = defaultdict(list)
    series_data = read_csv_safe(SERIES_CSV)
    if series_data:
        headers = series_data[0]
        for row in series_data[1:]:
            if not row:
                continue
            row_dict = dict(zip(headers, row))
            # 以 series_xml_id 作为系列主键，brand 允许为空
            if not row_dict.get('series_xml_id', '').strip():
                continue
            brand_xml_id = row_dict.get('brand_id_xml', '').strip()
            series_by_brand[brand_xml_id].append(row_dict)

    # 3. 产出 JSON
    json_output_data = []
    # 所有有变体数据的系列加入 JSON
    for series_id, variants in variants_by_series.items():
        # 如果 xml_id 忘了加前缀，可以在这里进行强制规范，这里假设填写的是纯ID（即如：catalog_tesa_754）
        full_xml_id = f"diecut.{series_id}" if not series_id.startswith('diecut.') else series_id
        json_output_data.append({
            "series_xml_id": full_xml_id,
            "variants": variants
        })
    
    with open(JSON_OUTPUT, 'w', encoding='utf-8') as f:
        json.dump(json_output_data, f, ensure_ascii=False, indent=4)
    print(f"[+] 成功生成 JSON 数据文件，包含 {len(json_output_data)} 个系列：{JSON_OUTPUT}")

    # ============================================================
    # 3.1 可选：按 CSV 品牌集合清理未匹配 XML
    # ============================================================
    target_filenames = {brand_to_xml_filename(k) for k in series_by_brand.keys()}
    if PRUNE_UNMATCHED_BRAND_XML:
        deleted = 0
        for existing_file in os.listdir(DATA_DIR):
            if not (existing_file.startswith('catalog_') and existing_file.endswith('_data.xml')):
                continue
            if existing_file not in target_filenames:
                file_to_del = os.path.join(DATA_DIR, existing_file)
                try:
                    os.remove(file_to_del)
                    deleted += 1
                    print(f"[-] 已删除未匹配品牌XML: {existing_file}")
                except Exception as e:
                    print(f"[!] 删除失败 {existing_file}: {e}")
        print(f"[*] 已按CSV品牌清理，删除 {deleted} 个文件。")
    elif SAFE_MODE:
        print("[*] SAFE_MODE=ON：不会删除任何 catalog_*_data.xml 文件。")

    # ============================================================
    # 4. 产出 XML
    # ============================================================
    for brand_xml_id, series_list in series_by_brand.items():
        # 同步品牌名解析逻辑，防止 UI 导出记录出现数字品牌名
        xml_filename = brand_to_xml_filename(brand_xml_id)
        brand_str = xml_filename[len("catalog_"):-len("_data.xml")]
        xml_filepath = os.path.join(DATA_DIR, xml_filename)
        
        xml_lines = []
        xml_lines.append('<?xml version="1.0" encoding="utf-8"?>')
        xml_lines.append('<odoo>')

        xml_lines.append('    <data noupdate="1">')
        
        # （可选保留：记录原用来生成变体的相关代码位置已转移至 ORM 处理）
        xml_lines.append('        <!-- 注意：此系列下变体的属性及变体行绑定（Attribute Values & Lines）')
        xml_lines.append('             已全权交由 _load_catalog_base_data_from_json 钩子在 Python ORM 层面动态生成，')
        xml_lines.append('             以支持 Odoo 中型号的新增、废弃，避免 XML External ID 强绑定的 Another model is using 错误。 -->')
        xml_lines.append('')
        xml_lines.append('')

        # 自动生成品牌定义（注意：如果是 UI 手动创建的品牌，不要生成 record，因为没办法得知原来的准确名字，且防止将其改名为数字）
        brand_name_display = brand_str.title() if brand_str else "Unknown Brand"
        if brand_xml_id and not brand_xml_id.startswith('brand_ui_exported'):
            xml_lines.append('        <!-- 品牌（每次升级同步） -->')
            xml_lines.append(f'        <record id="{brand_xml_id}" model="diecut.brand">')
            xml_lines.append(f'            <field name="name">{brand_name_display}</field>')
            xml_lines.append(f'        </record>')
            xml_lines.append('')

        xml_lines.append('        <!-- 选型目录产品模板（每次升级同步 CSV 中的描述） -->')
        for s in series_list:
            xml_lines.append(f'        <record id="{s["series_xml_id"]}" model="product.template">')
            xml_lines.append(f'            <field name="name"><![CDATA[{s.get("name", "")}]]></field>')
            xml_lines.append(f'            <field name="is_catalog">True</field>')
            xml_lines.append(f'            <field name="catalog_status">published</field>')
            categ_xml_id = s.get("categ_id_xml") or "category_tape_foam"
            xml_lines.append(f'            <field name="categ_id" ref="{categ_xml_id}" />')
            if brand_xml_id:
                xml_lines.append(f'            <field name="brand_id" ref="{brand_xml_id}" />')
            xml_lines.append(f'            <field name="catalog_base_material"><![CDATA[{s.get("catalog_base_material", "")}]]></field>')
            xml_lines.append(f'            <field name="catalog_adhesive_type"><![CDATA[{s.get("catalog_adhesive_type", "")}]]></field>')
            xml_lines.append(f'            <field name="catalog_characteristics"><![CDATA[{s.get("catalog_characteristics", "")}]]></field>')
            features_val = s.get('catalog_features', '')
            applications_val = text_to_html(s.get('catalog_applications', ''))
            xml_lines.append(f'            <field name="catalog_features"><![CDATA[{features_val}]]></field>')
            xml_lines.append(f'            <field name="catalog_applications"><![CDATA[{applications_val}]]></field>')
            xml_lines.append(f'            <field name="series_name"><![CDATA[{s.get("series_name", "")}]]></field>')
            xml_lines.append(f'            <field name="purchase_ok">False</field>')
            xml_lines.append(f'            <field name="sale_ok">False</field>')
            xml_lines.append(f'            <field name="type">consu</field>')
            xml_lines.append(f'        </record>')

        xml_lines.append('    </data>')
        xml_lines.append('</odoo>')
        
        with open(xml_filepath, 'w', encoding='utf-8') as f:
            f.write("\n".join(xml_lines))
        print(f"[+] 成功生成 XML 骨架文件：{xml_filepath}")

    # ============================================================
    # 动态覆写 load_json_data.xml，注入当前时间戳，确保每次升级模块都触发执行钩子！
    # ============================================================
    import datetime
    load_xml_filepath = os.path.join(DATA_DIR, 'load_json_data.xml')
    load_xml_content = f"""<?xml version="1.0" encoding="utf-8"?>
<odoo>
    <!-- CSV / JSON 更新时间戳: {datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")} -->
    <data noupdate="0">
        <function model="product.template" name="_load_catalog_base_data_from_json" />
    </data>
</odoo>
"""
    with open(load_xml_filepath, 'w', encoding='utf-8') as f:
        f.write(load_xml_content)
    print(f"[+] 成功更新触发器文件：{load_xml_filepath}")

    # ============================================================
    # 安全模式：不自动更新 __manifest__.py
    # ============================================================
    # 说明：自动改写 manifest 在多人协作/升级场景容易引入不可预期问题。
    # 如需新增 data XML，请手动评审后再登记到 __manifest__.py。
    if SAFE_MODE:
        print("[*] SAFE_MODE=ON：未自动修改 __manifest__.py。")

    print("\n[OK] 转换结束。")

if __name__ == '__main__':
    run_generator()
