# -*- coding: utf-8 -*-
import csv
import json
import os


SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(SCRIPT_DIR, '..', 'data')
CSV_INPUT = os.path.join(SCRIPT_DIR, 'catalog_items.csv')
JSON_OUTPUT = os.path.join(DATA_DIR, 'catalog_materials.json')


def read_csv_safe(filepath):
    with open(filepath, 'r', encoding='utf-8-sig', newline='') as f:
        rows = list(csv.reader(f))
    return [[col.replace('\r', '') for col in row] for row in rows]


def ensure_csv_template():
    if os.path.exists(CSV_INPUT):
        return
    os.makedirs(SCRIPT_DIR, exist_ok=True)
    headers = [
        'brand_id_xml',
        'categ_id_xml',
        'name',
        'code',
        'series_text',
        'catalog_status',
        'active',
        'sequence',
        'equivalent_type',
        'product_features',
        'product_description',
        'main_applications',
        'variant_thickness',
        'variant_adhesive_thickness',
        'variant_color',
        'variant_peel_strength',
        'variant_structure',
        'variant_adhesive_type',
        'variant_base_material',
        'variant_sus_peel',
        'variant_pe_peel',
        'variant_dupont',
        'variant_push_force',
        'variant_removability',
        'variant_tumbler',
        'variant_holding_power',
        'variant_ref_price',
        'variant_is_rohs',
        'variant_is_reach',
        'variant_is_halogen_free',
        'variant_fire_rating',
    ]
    example = [
        'brand_tesa',
        'category_tape_foam',
        'tesa 4980',
        '4980',
        '498xx',
        'published',
        '1',
        '10',
        '',
        '',
        '',
        '<p><strong>典型应用</strong></p><p>消费电子缓冲</p>',
        '0.08mm',
        '',
        '透明',
        '8.6 N/cm',
        '',
        '改性丙烯酸',
        'PET',
        '',
        '',
        '',
        '',
        '',
        '',
        '',
        '0',
        '1',
        '1',
        '1',
        'none',
    ]
    with open(CSV_INPUT, 'w', encoding='utf-8-sig', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        writer.writerow(example)
    print(f"[*] 已生成单CSV模板: {CSV_INPUT}")


def record_key(record):
    brand = str(record.get('brand_id_xml') or '').strip().lower()
    code = str(record.get('code') or '').strip().lower()
    if not brand or not code:
        return None
    return f"{brand}::{code}"


def is_blank(value):
    return value in (None, False, '')


def load_existing_json_payload():
    if not os.path.exists(JSON_OUTPUT):
        return [], []
    with open(JSON_OUTPUT, 'r', encoding='utf-8') as f:
        payload = json.load(f)

    if not isinstance(payload, list):
        return [], [payload]

    normalized = []
    passthrough = []
    for item in payload:
        if isinstance(item, dict) and item.get('brand_id_xml') and item.get('code'):
            normalized.append(item)
        else:
            passthrough.append(item)
    return normalized, passthrough


def build_csv_snapshot_records(incoming_records):
    """Strict snapshot by CSV (last duplicate row wins by brand+code)."""
    snapshot = {}
    order = []
    for rec in incoming_records:
        key = record_key(rec)
        if not key:
            continue
        if key not in snapshot:
            order.append(key)
        snapshot[key] = dict(rec)
    return [snapshot[k] for k in order]


def read_catalog_csv_records():
    rows = read_csv_safe(CSV_INPUT)
    if not rows:
        return []
    headers = [h.strip() for h in rows[0]]

    records = []
    for row in rows[1:]:
        if not row:
            continue
        row_dict = dict(zip(headers, row))
        clean = {}
        for key, value in row_dict.items():
            clean[key] = value.strip() if isinstance(value, str) else value
        if not any(clean.values()):
            continue
        records.append(clean)
    return records


def run_generator():
    ensure_csv_template()
    os.makedirs(DATA_DIR, exist_ok=True)

    incoming = read_catalog_csv_records()
    existing, passthrough = load_existing_json_payload()
    merged = build_csv_snapshot_records(incoming)
    existing_keys = {record_key(rec) for rec in existing if record_key(rec)}
    merged_keys = {record_key(rec) for rec in merged if record_key(rec)}
    removed_count = len(existing_keys - merged_keys)

    with open(JSON_OUTPUT, 'w', encoding='utf-8') as f:
        json.dump(passthrough + merged, f, ensure_ascii=False, indent=4)

    print('[+] JSON 严格同步完成')
    print(f'    incoming: {len(incoming)}')
    print(f'    existing(normalized): {len(existing)}')
    print(f'    removed: {removed_count}')
    print(f'    passthrough: {len(passthrough)}')
    print(f'    merged: {len(merged)}')
    print(f'    output: {JSON_OUTPUT}')


if __name__ == '__main__':
    run_generator()
