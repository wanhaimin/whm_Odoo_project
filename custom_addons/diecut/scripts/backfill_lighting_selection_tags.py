# -*- coding: utf-8 -*-
import json
from pathlib import Path


DRAFT_PATH = Path("/mnt/extra-addons/diecut/scripts/tds_import_drafts/iatd_lighting_brochure_draft.json")

SERIES_RULES = {
    "3M VHB LSE系列": {
        "function": ["粘接固定", "缓冲减震"],
        "application": ["LED灯条背胶", "户外灯饰背胶", "LED结构粘接", "小夜灯固定", "LED扩散板粘接"],
        "feature": ["低表面能粘接", "耐候", "防水密封", "易模切"],
    },
    "3M VHB LVO系列": {
        "function": ["粘接固定", "缓冲减震"],
        "application": ["LED灯条背胶", "户外灯饰背胶", "LED结构粘接", "小夜灯固定", "LED扩散板粘接"],
        "feature": ["低VOC低气味", "耐候", "防水密封", "易模切"],
    },
    "3M VHB 4941系列": {
        "function": ["粘接固定", "缓冲减震"],
        "application": ["LED灯条背胶", "户外灯饰背胶", "LED结构粘接", "小夜灯固定", "LED扩散板粘接"],
        "feature": ["耐候", "防水密封", "易模切"],
    },
    "3M VHB 5952系列": {
        "function": ["粘接固定", "缓冲减震"],
        "application": ["LED灯条背胶", "户外灯饰背胶", "LED结构粘接", "小夜灯固定", "LED扩散板粘接"],
        "feature": ["耐候", "防水密封", "易模切"],
    },
    "3M VHB 4910系列": {
        "function": ["粘接固定", "缓冲减震"],
        "application": ["LED灯条背胶", "LED结构粘接", "LED扩散板粘接"],
        "feature": ["透明粘接", "耐候", "防水密封", "易模切"],
    },
    "3M VHB RP+系列": {
        "function": ["粘接固定", "缓冲减震"],
        "application": ["LED灯条背胶", "户外灯饰背胶", "LED结构粘接", "小夜灯固定", "LED扩散板粘接"],
        "feature": ["耐候", "防水密封", "易模切"],
    },
    "3M VHB GPH系列": {
        "function": ["粘接固定", "缓冲减震"],
        "application": ["LED结构粘接", "户外灯饰背胶", "LED扩散板粘接"],
        "feature": ["耐高温", "耐候", "防水密封", "易模切"],
    },
    "3M VHB 4950系列": {
        "function": ["粘接固定", "缓冲减震"],
        "application": ["LED结构粘接", "户外灯饰背胶", "LED扩散板粘接"],
        "feature": ["耐候", "防水密封", "易模切"],
    },
    "3M VHB GPL系列": {
        "function": ["粘接固定", "缓冲减震"],
        "application": ["LED结构粘接", "户外灯饰背胶", "LED扩散板粘接"],
        "feature": ["高初粘", "耐候", "防水密封", "易模切"],
    },
    "3M VHB 5611系列": {
        "function": ["粘接固定", "缓冲减震"],
        "application": ["LED结构粘接", "户外灯饰背胶", "LED扩散板粘接"],
        "feature": ["耐候", "防水密封", "易模切"],
    },
    "3M 转移胶膜系列": {
        "function": ["粘接固定"],
        "application": ["LED灯条背胶", "显示面板固定", "铭牌粘贴"],
        "feature": ["薄型结构固定", "易模切"],
    },
    "3M PET双面胶系列": {
        "function": ["粘接固定"],
        "application": ["LED灯条背胶", "显示面板固定", "铭牌粘贴"],
        "feature": ["薄型结构固定", "易模切"],
    },
    "3M 棉纸双面胶系列": {
        "function": ["粘接固定"],
        "application": ["LED灯条背胶", "显示面板固定", "铭牌粘贴"],
        "feature": ["薄型结构固定", "易模切"],
    },
    "3M PE泡棉胶带系列": {
        "function": ["粘接固定", "缓冲减震"],
        "application": ["LED模组背胶", "显示面板固定", "铭牌粘贴", "电线电缆固定"],
        "feature": ["高初粘", "易模切"],
    },
    "3M 防篡改标签系列": {
        "function": ["标识装饰", "防拆防伪"],
        "application": ["变压器标签", "电源标签", "防拆封签"],
        "feature": ["防篡改", "耐久标识"],
    },
    "3M 耐久性标签系列": {
        "function": ["标识装饰"],
        "application": ["变压器标签", "电源标签", "铭牌粘贴"],
        "feature": ["耐久标识"],
    },
    "3M 底涂剂系列": {
        "function": ["附着力提升"],
        "application": ["表面预处理"],
        "feature": ["提升附着力"],
    },
}

CODE_RULES = {
    "9495LE": {"feature": ["低表面能粘接"]},
    "93015LE": {"feature": ["低表面能粘接"]},
    "9495MP": {"feature": ["薄型结构固定"]},
    "4905": {"feature": ["透明粘接"]},
    "4910": {"feature": ["透明粘接"]},
    "4915": {"feature": ["透明粘接"]},
    "4918": {"feature": ["透明粘接"]},
    "GPH060": {"feature": ["耐高温"]},
    "GPH110": {"feature": ["耐高温"]},
    "GPH160": {"feature": ["耐高温"]},
    "GPL040": {"feature": ["高初粘"]},
    "GPL060": {"feature": ["高初粘"]},
    "GPL080": {"feature": ["高初粘"]},
    "GPL110": {"feature": ["高初粘"]},
    "GPL160": {"feature": ["高初粘"]},
    "GPL200": {"feature": ["高初粘"]},
    "LVO-060BF": {"feature": ["低VOC低气味"]},
    "LVO-110BF": {"feature": ["低VOC低气味"]},
    "LVO-160BF": {"feature": ["低VOC低气味"]},
    "7613T": {"feature": ["防篡改"]},
    "7110": {"feature": ["防篡改"]},
    "AP111": {"feature": ["提升附着力"]},
    "AP115": {"feature": ["提升附着力"]},
    "94底涂剂": {"feature": ["提升附着力"]},
    "UPUV底涂剂": {"feature": ["提升附着力"]},
}


def _load_codes_and_series():
    payload = json.loads(DRAFT_PATH.read_text(encoding="utf-8"))
    series_names = sorted({row.get("series_name") for row in payload.get("items") or [] if row.get("series_name")})
    codes = [row.get("code") for row in payload.get("items") or [] if row.get("code")]
    return series_names, codes


def _ensure_records(model_name, names, extra_vals=None):
    model = env[model_name].sudo()
    result = {}
    for index, name in enumerate(names, start=1):
        record = model.search([("name", "=", name)], limit=1)
        vals = dict(extra_vals or {})
        vals.setdefault("sequence", index * 10)
        if not record:
            vals["name"] = name
            record = model.create(vals)
        else:
            write_vals = {}
            for key, value in vals.items():
                if key in record._fields and not record[key]:
                    write_vals[key] = value
            if write_vals:
                record.write(write_vals)
        result[name] = record
    return result


def _merge_m2m(record, field_name, target_ids):
    target_ids = set(target_ids or [])
    current_ids = set(record[field_name].ids)
    merged = sorted(current_ids | target_ids)
    if merged != sorted(current_ids):
        record.write({field_name: [(6, 0, merged)]})
        return True
    return False


series_names, target_codes = _load_codes_and_series()

function_names = sorted(
    {
        name
        for rules in list(SERIES_RULES.values()) + list(CODE_RULES.values())
        for name in rules.get("function", [])
    }
)
application_names = sorted(
    {
        name
        for rules in list(SERIES_RULES.values()) + list(CODE_RULES.values())
        for name in rules.get("application", [])
    }
)
feature_names = sorted(
    {
        name
        for rules in list(SERIES_RULES.values()) + list(CODE_RULES.values())
        for name in rules.get("feature", [])
    }
)

function_tags = _ensure_records("product.tag", function_names)
application_tags = _ensure_records("diecut.catalog.application.tag", application_names)
feature_tags = _ensure_records("diecut.catalog.feature.tag", feature_names)

brand = env["diecut.brand"].sudo().search([("name", "=", "3M")], limit=1)
if not brand:
    raise RuntimeError("未找到 3M 品牌。")

series_model = env["diecut.catalog.series"].sudo()
item_model = env["diecut.catalog.item"].sudo()

series_records = series_model.search([("brand_id", "=", brand.id), ("name", "in", series_names)])
series_by_name = {record.name: record for record in series_records}

updated_series = 0
updated_items = 0

for series_name, rules in SERIES_RULES.items():
    series = series_by_name.get(series_name)
    if not series:
        continue
    if _merge_m2m(series, "default_function_tag_ids", [function_tags[name].id for name in rules.get("function", [])]):
        updated_series += 1
    if _merge_m2m(series, "default_application_tag_ids", [application_tags[name].id for name in rules.get("application", [])]):
        updated_series += 1
    if _merge_m2m(series, "default_feature_tag_ids", [feature_tags[name].id for name in rules.get("feature", [])]):
        updated_series += 1

items = item_model.search([("brand_id", "=", brand.id), ("code", "in", target_codes)])
for item in items:
    series_rules = SERIES_RULES.get(item.series_id.name or "", {})
    code_rules = CODE_RULES.get(item.code or "", {})
    function_ids = [function_tags[name].id for name in series_rules.get("function", []) + code_rules.get("function", [])]
    application_ids = [application_tags[name].id for name in series_rules.get("application", []) + code_rules.get("application", [])]
    feature_ids = [feature_tags[name].id for name in series_rules.get("feature", []) + code_rules.get("feature", [])]

    changed = False
    changed |= _merge_m2m(item, "function_tag_ids", function_ids)
    changed |= _merge_m2m(item, "application_tag_ids", application_ids)
    changed |= _merge_m2m(item, "feature_tag_ids", feature_ids)
    if changed:
        updated_items += 1

print(
    json.dumps(
        {
            "target_series": len(series_names),
            "matched_series": len(series_records),
            "target_items": len(target_codes),
            "matched_items": len(items),
            "updated_series_writes": updated_series,
            "updated_items": updated_items,
        },
        ensure_ascii=False,
    )
)
env.cr.commit()
