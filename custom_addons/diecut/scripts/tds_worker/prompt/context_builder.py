# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import re
from typing import Any


def clean_text(value) -> str:
    return str(value or "").strip()


def join_lines(values, limit=12):
    if not isinstance(values, list):
        return ""
    lines = []
    for value in values[:limit]:
        text = clean_text(value)
        if text:
            lines.append(f"- {text}")
    return "\n".join(lines)


def trim_dict_rows(rows, keys, limit):
    output = []
    if not isinstance(rows, list):
        return output
    for row in rows[:limit]:
        if not isinstance(row, dict):
            continue
        output.append({k: row.get(k) for k in keys if row.get(k) not in (None, False, "", [])})
    return output


# Industry field router (not brand-specific rules).
KEYWORD_RULES = {
    "thickness": [r"\bthickness\b", r"\btotal thickness\b", r"\boverall thickness\b", r"厚度"],
    "adhesive": [r"\badhesive\b", r"\bpressure sensitive adhesive\b", r"\bacrylic adhesive\b", r"胶系", r"压敏胶"],
    "base_material": [r"\bbase material\b", r"\bcarrier\b", r"\bbacking\b", r"\bfoam core\b", r"基材", r"载体", r"背材"],
    "color": [r"\bcolor\b", r"\bcolour\b", r"颜色"],
    "liner": [r"\bliner\b", r"\brelease liner\b", r"离型", r"离型膜", r"离型纸"],
    "shelf_life": [r"\bshelf life\b", r"\bstorage\b", r"\bstorage conditions?\b", r"保质期", r"储存", r"存放"],
    "peel": [r"\bpeel\b", r"\bpeel adhesion\b", r"\b180 peel\b", r"剥离", r"剥离力"],
    "painted_panel": [r"\bpainted panel\b", r"喷涂板", r"涂装板"],
    "pp": [r"\bpolypropylene\b", r"\bpp\b", r"PP板"],
    "headliner": [r"\bheadliner\b", r"顶棚"],
    "pluck": [r"\bpluck\b", r"拔脱"],
    "torque": [r"\btorque\b", r"\btwist resistance\b", r"扭矩"],
    "static_shear": [r"\bstatic shear\b", r"\bshear holding\b", r"\bshear\b", r"静态剪切", r"剪切强度", r"持粘"],
    "structure": [r"\bconstruction\b", r"\bproduct construction\b", r"\bstructure\b", r"结构", r"构成"],
    "method": [r"\btest method\b", r"\bprocedure\b", r"\btesting\b", r"\btypical results\b", r"测试方法", r"典型结果", r"试验方法"],
    "general_description": [r"\bgeneral description\b", r"\bproduct description\b", r"\boverview\b", r"产品描述", r"概述"],
    "features": [r"\bfeatures\b", r"\bbenefits\b", r"\badvantages\b", r"产品特性", r"特点", r"优势"],
    "applications": [r"\bapplications\b", r"\btypical applications\b", r"\brecommended uses?\b", r"\bend uses?\b", r"主要应用", r"应用", r"用途"],
    "equivalent": [r"\bequivalent\b", r"\breplacement\b", r"\bsubstitute\b", r"相当品", r"替代"],
    "processing": [
        r"\bprocessing compatibility\b",
        r"\bdie cutting\b",
        r"\brotary\b",
        r"\bflat bed\b",
        r"\blaser die cutting\b",
        r"加工兼容性",
        r"模切",
    ],
}


def collect_document_keywords(task: dict, raw_text: str) -> dict[str, bool]:
    filename = clean_text(task.get("primary_attachment_name"))
    title = clean_text(task.get("name"))
    source_text = "\n".join([filename, title, clean_text(raw_text)]).lower()

    flags = {}
    for key, patterns in KEYWORD_RULES.items():
        flags[key] = any(re.search(pattern, source_text, flags=re.I) for pattern in patterns)

    flags["dc_series"] = bool(re.search(r"\bdc\d{3,5}\b", source_text, flags=re.I))
    flags["gt_series"] = bool(re.search(r"\bgt\d{3,5}\b", source_text, flags=re.I))
    flags["vhb_series"] = bool(re.search(r"\bvhb\b", source_text, flags=re.I))
    flags["is_3m"] = "3m" in source_text
    return flags


TOP_LEVEL_PARAM_WHITELIST = {
    "thickness",
    "color",
    "adhesive_type",
    "base_material",
    "liner_material",
    "shelf_life_storage",
    "structure",
}

TOPIC_TO_PARAM_KEYS = {
    "thickness": {"thickness", "total_thickness", "carrier_thickness", "substrate_thickness"},
    "adhesive": {"adhesive_type", "adhesive_system", "adhesive_backing"},
    "base_material": {"base_material", "base_material_type", "base_film_type", "cloth_base_type", "paper_base_type"},
    "color": {"color", "color_tone"},
    "liner": {"liner_material", "liner_option_sc2", "liner_option_pet", "release_force"},
    "shelf_life": {"shelf_life_storage", "shelf_life"},
    "peel": {
        "peel_strength_180",
        "peel_strength",
        "foil_peel_strength",
        "peel_180_painted_immediate",
        "peel_180_painted_initial",
        "peel_180_painted_normal",
        "peel_180_painted_high_temp",
        "peel_180_painted_heat_aging",
        "peel_180_painted_humidity_aging",
        "peel_180_painted_warm_water",
        "peel_180_pvc_immediate",
        "peel_180_pvc_normal",
        "peel_180_pvc_high_temp",
        "peel_180_pvc_heat_aging",
        "peel_180_pvc_warm_water",
        "peel_180_pp_initial",
        "peel_180_pp_normal",
        "peel_180_headliner_immediate",
        "peel_180_headliner_initial",
        "peel_180_headliner_normal",
        "peel_180_headliner_high_temp",
        "peel_180_headliner_heat_aging",
        "peel_180_headliner_humidity_aging",
        "peel_180_painted_panel_initial",
        "peel_180_painted_panel_normal",
    },
    "painted_panel": {
        "peel_180_painted_immediate",
        "peel_180_painted_initial",
        "peel_180_painted_normal",
        "peel_180_painted_high_temp",
        "peel_180_painted_heat_aging",
        "peel_180_painted_humidity_aging",
        "peel_180_painted_warm_water",
        "peel_180_painted_panel_initial",
        "peel_180_painted_panel_normal",
    },
    "pp": {"peel_180_pp_initial", "peel_180_pp_normal"},
    "headliner": {
        "peel_180_headliner_immediate",
        "peel_180_headliner_initial",
        "peel_180_headliner_normal",
        "peel_180_headliner_high_temp",
        "peel_180_headliner_heat_aging",
        "peel_180_headliner_humidity_aging",
    },
    "pluck": {"pluck_testing"},
    "torque": {"torque_testing"},
    "static_shear": {
        "static_shear_70c",
        "shear_painted_pvc_immediate",
        "shear_painted_pvc_normal",
        "shear_painted_pvc_high_temp",
        "shear_painted_pvc_warm_water",
        "shear_painted_pvc_gasoline",
        "shear_painted_pvc_wax_remover",
        "holding_power",
    },
    "structure": {"structure"},
}


def should_keep_param(row: dict[str, Any], keyword_flags: dict[str, bool]) -> bool:
    param_key = clean_text(row.get("param_key"))
    if not param_key:
        return False
    if param_key in TOP_LEVEL_PARAM_WHITELIST:
        return True
    if row.get("is_main_field"):
        return True
    for topic, keys in TOPIC_TO_PARAM_KEYS.items():
        if keyword_flags.get(topic) and param_key in keys:
            return True
    return False


def filter_param_dictionary_snapshot(snapshot: list[dict[str, Any]], keyword_flags: dict[str, bool], limit: int = 24):
    if not isinstance(snapshot, list):
        return []
    kept = []
    for row in snapshot:
        if not isinstance(row, dict):
            continue
        if should_keep_param(row, keyword_flags):
            kept.append(row)
    kept.sort(
        key=lambda row: (
            0 if row.get("is_main_field") else 1,
            0 if row.get("spec_category") or row.get("spec_category_name") else 1,
            clean_text(row.get("param_key")),
        )
    )
    return kept[:limit]


CANONICAL_PRIORITY_GROUPS = [
    ["adhesive_type", "adhesive_system"],
    ["color", "color_tone"],
    ["peel_strength_180", "peel_strength", "foil_peel_strength"],
    ["shelf_life_storage", "shelf_life"],
    ["base_material", "base_material_type"],
]

EXACT_DROP_KEYS = {
    "peel_180_painted_panel_initial",
    "peel_180_painted_panel_normal",
}


def dedupe_semantic_params(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not isinstance(rows, list):
        return []
    by_key = {}
    for row in rows:
        key = clean_text(row.get("param_key"))
        if key and key not in EXACT_DROP_KEYS:
            by_key[key] = row
    for group in CANONICAL_PRIORITY_GROUPS:
        present = [key for key in group if key in by_key]
        if len(present) <= 1:
            continue
        for loser in present[1:]:
            by_key.pop(loser, None)
    return list(by_key.values())


def filter_few_shots(skill_bundle: dict, keyword_flags: dict[str, bool], limit: int = 4) -> list[str]:
    examples = skill_bundle.get("few_shot_examples") or []
    picked = []
    match_rules = [
        ("pluck", ["pluck"]),
        ("torque", ["torque"]),
        ("static_shear", ["static shear"]),
        ("liner", ["liner"]),
        ("peel", ["painted panel", "peel"]),
        ("gt_series", ["gt7100"]),
        ("dc_series", ["dc2000", "pluck", "torque", "static shear"]),
    ]
    lower_examples = [(ex, clean_text(ex).lower()) for ex in examples]
    for topic, needles in match_rules:
        if not keyword_flags.get(topic):
            continue
        for ex, low in lower_examples:
            if any(n in low for n in needles) and ex not in picked:
                picked.append(ex)
    for ex in examples:
        if ex not in picked:
            picked.append(ex)
        if len(picked) >= limit:
            break
    return picked[:limit]


def filter_negative_rules(skill_bundle: dict, keyword_flags: dict[str, bool], limit: int = 5) -> list[str]:
    rules = skill_bundle.get("negative_rules") or []
    picked = []
    for rule in rules:
        low = clean_text(rule).lower()
        if "legal disclaimers" in low:
            picked.append(rule)
        elif "marketing" in low:
            picked.append(rule)
        elif keyword_flags.get("color") and "legend colors" in low:
            picked.append(rule)
        elif keyword_flags.get("peel") and "typical results" in low:
            picked.append(rule)
        elif keyword_flags.get("is_3m") and "competitor chart lines" in low:
            picked.append(rule)
    result = []
    seen = set()
    for item in picked:
        if item not in seen:
            seen.add(item)
            result.append(item)
    return result[:limit]


def filter_task_instructions(skill_bundle: dict, limit: int = 5) -> list[str]:
    instructions = skill_bundle.get("task_instructions") or []
    return instructions[:limit]


def filter_field_mapping_guidance(skill_bundle: dict, keyword_flags: dict[str, bool], limit: int = 6) -> list[str]:
    rules = skill_bundle.get("field_mapping_guidance") or []
    picked = []
    for rule in rules:
        low = clean_text(rule).lower()
        if "series-level" in low:
            picked.append(rule)
        elif "item matrix" in low:
            picked.append(rule)
        elif "measured technical metrics" in low:
            picked.append(rule)
        elif keyword_flags.get("method") and "method_html" in low:
            picked.append(rule)
        elif "main searchable fields" in low:
            picked.append(rule)
        elif keyword_flags.get("liner") and "liner" in low:
            picked.append(rule)
    deduped = []
    seen = set()
    for item in picked:
        if item not in seen:
            seen.add(item)
            deduped.append(item)
    return deduped[:limit]


def build_content_routing_guidance(keyword_flags: dict[str, bool]) -> list[str]:
    rules = [
        "Narrative product overview belongs to series.product_description.",
        "Feature bullets and non-numeric selling points belong to series.product_features.",
        "Application bullets or recommended-use sections belong to series.main_applications.",
        "Item-specific differences or model-specific descriptive notes belong to items.item_features.",
        "Competitive references, replacement hints, or substitute notes belong to items.equivalent_notes.",
        "Do not push descriptive narrative into unmatched if it can fit product_description, product_features, main_applications, item_features, or equivalent_notes.",
    ]
    if keyword_flags.get("structure"):
        rules.append(
            "Construction or structure summaries may also be kept as descriptive product content when they are not precise measurable spec values."
        )
    if keyword_flags.get("processing"):
        rules.append(
            "Processing compatibility text such as rotary, flat bed, or laser die cutting belongs to spec_values.processing_compatibility or series/product description, not unmatched."
        )
    return rules


def filter_param_aliases(skill_bundle: dict, filtered_params: list[dict[str, Any]], limit: int = 12) -> dict[str, list[str]]:
    aliases = skill_bundle.get("param_aliases") or {}
    allowed_keys = {clean_text(row.get("param_key")) for row in filtered_params}
    result = {}
    for key, names in aliases.items():
        if key in allowed_keys:
            result[key] = names[:6] if isinstance(names, list) else names
    for fallback in ("thickness", "adhesive_type", "base_material"):
        if fallback in aliases and fallback not in result:
            result[fallback] = aliases[fallback][:6] if isinstance(aliases[fallback], list) else aliases[fallback]
    return dict(list(result.items())[:limit])


def filter_category_param_snapshot(snapshot: list[dict[str, Any]], filtered_params: list[dict[str, Any]], limit: int = 16):
    if not isinstance(snapshot, list):
        return []
    allowed_keys = {clean_text(row.get("param_key")) for row in filtered_params}
    kept = []
    for row in snapshot:
        if not isinstance(row, dict):
            continue
        if clean_text(row.get("param_key")) in allowed_keys:
            kept.append(row)
    return kept[:limit]


def build_model_context_payload(
    task: dict,
    context: dict,
    raw_text: str = "",
    param_limit: int = 24,
    category_limit: int = 16,
):
    skill_bundle = context.get("skill_bundle") or {}
    keyword_flags = collect_document_keywords(task, raw_text)

    full_param_snapshot = context.get("param_dictionary_snapshot") or []
    filtered_params = filter_param_dictionary_snapshot(full_param_snapshot, keyword_flags, limit=param_limit)
    filtered_params = dedupe_semantic_params(filtered_params)

    filtered_category_params = filter_category_param_snapshot(
        context.get("category_param_snapshot") or [],
        filtered_params,
        limit=category_limit,
    )

    return {
        "task_instructions": filter_task_instructions(skill_bundle, limit=5),
        "field_mapping_guidance": filter_field_mapping_guidance(skill_bundle, keyword_flags, limit=6),
        "content_routing_guidance": build_content_routing_guidance(keyword_flags),
        "negative_rules": filter_negative_rules(skill_bundle, keyword_flags, limit=5),
        "few_shot_examples": filter_few_shots(skill_bundle, keyword_flags, limit=4),
        "param_aliases": filter_param_aliases(skill_bundle, filtered_params, limit=10),
        "param_dictionary_snapshot": filtered_params,
        "category_param_snapshot": filtered_category_params,
        "keyword_flags": keyword_flags,
        "main_field_whitelist": (context.get("main_field_whitelist") or [])[:12],
        "required_buckets": ((skill_bundle.get("output_schema") or {}).get("required_buckets") or [])[:6],
        "main_item_fields": ((skill_bundle.get("output_schema") or {}).get("main_item_fields") or [])[:12],
    }


def build_model_context_text(
    task: dict,
    context: dict,
    raw_text: str = "",
    param_limit: int = 24,
    category_limit: int = 16,
) -> str:
    payload = build_model_context_payload(
        task=task,
        context=context,
        raw_text=raw_text,
        param_limit=param_limit,
        category_limit=category_limit,
    )
    keyword_lines = [f"- {k}" for k, value in payload["keyword_flags"].items() if value]
    return f"""
TASK PROFILE
- title: {task.get('name') or ''}
- brand: {task.get('brand') or context.get('source_context', {}).get('brand_name') or ''}
- category: {task.get('category') or context.get('source_context', {}).get('category_name') or ''}
- attachment: {task.get('primary_attachment_name') or ''}

BUSINESS GOAL
- Parse a material TDS into Odoo draft data.
- Use existing dictionary keys when possible.
- Uncertain values must go to unmatched with reason.

REQUIRED BUCKETS
{join_lines(payload["required_buckets"], limit=6)}

MAIN ITEM FIELDS
{join_lines(payload["main_item_fields"], limit=12)}

DOCUMENT KEYWORD HITS
{chr(10).join(keyword_lines) if keyword_lines else '- none'}

TASK INSTRUCTIONS
{join_lines(payload["task_instructions"], limit=5)}

FIELD MAPPING GUIDANCE
{join_lines(payload["field_mapping_guidance"], limit=6)}

CONTENT ROUTING GUIDANCE
{join_lines(payload["content_routing_guidance"], limit=8)}

NEGATIVE RULES
{join_lines(payload["negative_rules"], limit=5)}

FEW-SHOT EXAMPLES
{join_lines(payload["few_shot_examples"], limit=4)}

MAIN FIELD WHITELIST
{join_lines(payload["main_field_whitelist"], limit=12)}

PARAM ALIASES
{json.dumps(payload["param_aliases"], ensure_ascii=False, indent=2)}

PARAMETER DICTIONARY SNAPSHOT
{json.dumps(trim_dict_rows(
payload["param_dictionary_snapshot"],
[
"param_key", "name", "canonical_name_zh", "canonical_name_en",
"value_type", "preferred_unit", "is_main_field", "main_field_name", "spec_category"
],
param_limit
), ensure_ascii=False, indent=2)}

CATEGORY PARAM SNAPSHOT
{json.dumps(trim_dict_rows(
payload["category_param_snapshot"],
["categ_name", "param_key", "param_name", "required", "show_in_form", "allow_import", "unit_override"],
category_limit
), ensure_ascii=False, indent=2)}
""".strip()


def build_context_signature(
    task: dict,
    context: dict,
    raw_text: str = "",
    param_limit: int = 24,
    category_limit: int = 16,
) -> str:
    from ..cache import sha256_json

    payload = build_model_context_payload(
        task=task,
        context=context,
        raw_text=raw_text,
        param_limit=param_limit,
        category_limit=category_limit,
    )
    signature_payload = {
        "task_instructions": payload.get("task_instructions"),
        "field_mapping_guidance": payload.get("field_mapping_guidance"),
        "content_routing_guidance": payload.get("content_routing_guidance"),
        "negative_rules": payload.get("negative_rules"),
        "few_shot_examples": payload.get("few_shot_examples"),
        "param_aliases": payload.get("param_aliases"),
        "param_dictionary_snapshot": payload.get("param_dictionary_snapshot"),
        "category_param_snapshot": payload.get("category_param_snapshot"),
        "main_field_whitelist": payload.get("main_field_whitelist"),
        "required_buckets": payload.get("required_buckets"),
        "main_item_fields": payload.get("main_item_fields"),
        "keyword_flags": payload.get("keyword_flags"),
    }
    return sha256_json(signature_payload)[:16]

