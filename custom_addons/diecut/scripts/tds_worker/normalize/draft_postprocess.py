# -*- coding: utf-8 -*-
from __future__ import annotations

from .peel_rules import derive_specific_peel_meta_from_row
from .translators import (
    clean_text,
    map_known_value,
    normalize_source_label,
    translate_condition,
    translate_shelf_life_value,
    translate_structure_value,
)
from .unmatched import process_unmatched


INFERRED_CATEGORY_RULES = [
    {
        "match": ("无纺布", "non-woven cloth", "non woven cloth"),
        "category_name": "原材料/胶带类/棉纸/无纺布双面胶带",
    },
    {
        "match": ("泡棉", "foam", "acrylic foam"),
        "category_name": "原材料/胶带类/泡棉胶带",
    },
]

PARAM_CATEGORY_FALLBACK = {
    "peel_strength_180": "粘接性能",
    "structure": "基础规格",
    "shelf_life_storage": "包装与储存",
}

MAIN_FIELD_ROUTE_MAP = {
    "thickness": "thickness",
    "thickness_std": "thickness_std",
    "adhesive_thickness": "adhesive_thickness",
    "color": "color_id",
    "adhesive_type": "adhesive_type_id",
    "base_material": "base_material_id",
    "ref_price": "ref_price",
    "is_rohs": "is_rohs",
    "is_reach": "is_reach",
    "is_halogen_free": "is_halogen_free",
    "fire_rating": "fire_rating",
}

NOTE_PARAM_KEYS = {
    "structure",
    "processing_compatibility",
    "pluck_testing",
    "torque_testing",
    "shelf_life_storage",
    "liner_option_sc2",
    "liner_option_pet",
}

PARAM_NAME_ZH_FALLBACK = {
    "thickness": "厚度",
    "thickness_std": "厚度标准值",
    "adhesive_thickness": "胶层厚度",
    "color": "颜色",
    "adhesive_type": "胶系",
    "base_material": "基材",
    "liner_material": "离型材料",
    "shelf_life_storage": "保质期与储存",
    "structure": "结构",
    "density": "密度",
    "hardness": "硬度",
    "elongation_at_break": "断裂延展率",
    "tensile_strength": "拉伸强度",
    "initial_tack": "初粘力",
    "short_term_temperature_resistance": "短期耐温",
    "long_term_temperature_resistance": "长期耐温",
    "foil_peel_strength": "箔材剥离强度",
    "peel_strength_180": "180度剥离力",
    "shear_strength": "剪切强度",
    "static_shear_23c": "23℃静态剪切",
    "static_shear_70c": "70℃静态剪切",
    "processing_compatibility": "加工兼容性",
}

PARAM_LABEL_ZH_FALLBACK = {
    "thickness": "厚度",
    "adhesive thickness": "胶层厚度",
    "color": "颜色",
    "adhesive type": "胶系",
    "base material": "基材",
    "liner material": "离型材料",
    "shelf life and storage": "保质期与储存",
    "structure": "结构",
    "density": "密度",
    "hardness": "硬度",
    "elongation at break": "断裂延展率",
    "tensile strength": "拉伸强度",
    "initial tack": "初粘力",
    "short term temperature resistance": "短期耐温",
    "long term temperature resistance": "长期耐温",
    "foil peel strength": "箔材剥离强度",
    "180 peel adhesion": "180度剥离力",
    "shear strength": "剪切强度",
}


def _looks_english_or_key_like(value: str, param_key: str) -> bool:
    text = clean_text(value)
    key = clean_text(param_key)
    if not text:
        return True
    if key and text.lower() == key.lower():
        return True
    # Pure ASCII-ish names are usually key-like labels in this pipeline.
    return all(ord(ch) < 128 for ch in text)


def _resolve_preferred_zh_name(meta: dict, candidate_name: str, param_key: str) -> str:
    zh = clean_text(meta.get("canonical_name_zh")) if isinstance(meta, dict) else ""
    en = clean_text(meta.get("canonical_name_en")) if isinstance(meta, dict) else ""
    name = clean_text(meta.get("name")) if isinstance(meta, dict) else ""
    candidate = clean_text(candidate_name)
    if zh:
        return zh
    if candidate and not _looks_english_or_key_like(candidate, param_key):
        return candidate
    if name and not _looks_english_or_key_like(name, param_key):
        return name
    if en and not _looks_english_or_key_like(en, param_key):
        return en
    return candidate or name or en or param_key


def _translate_param_name_to_zh(candidate: str, param_key: str) -> str:
    text = clean_text(candidate)
    key = clean_text(param_key).lower()
    if not _looks_english_or_key_like(text, key):
        return text
    if key in PARAM_NAME_ZH_FALLBACK:
        return PARAM_NAME_ZH_FALLBACK[key]
    lower = text.lower()
    if lower in PARAM_LABEL_ZH_FALLBACK:
        return PARAM_LABEL_ZH_FALLBACK[lower]
    return text


def _promote_narrative_unmatched_to_series(payload: dict) -> dict:
    series_rows = payload.get("series") or []
    if not series_rows or not isinstance(series_rows[0], dict):
        return payload

    series = series_rows[0]
    remaining = []
    for row in payload.get("unmatched") or []:
        if not isinstance(row, dict):
            continue

        source_label = clean_text(row.get("source_label")).lower()
        content = clean_text(row.get("content"))
        if not content:
            continue

        if ("general description" in source_label or "product description" in source_label) and not clean_text(
            series.get("product_description")
        ):
            series["product_description"] = content
            continue

        if ("application" in source_label or "recommended use" in source_label) and not clean_text(
            series.get("main_applications")
        ):
            series["main_applications"] = content
            continue

        remaining.append(row)

    payload["unmatched"] = remaining
    return payload


def _infer_category_name(item: dict) -> str:
    haystack = " ".join(
        [
            clean_text(item.get("base_material_name")),
            clean_text(item.get("series_name")),
            clean_text(item.get("item_name")),
            clean_text(item.get("description")),
        ]
    ).lower()
    for rule in INFERRED_CATEGORY_RULES:
        if any(keyword in haystack for keyword in rule["match"]):
            return rule["category_name"]
    return ""


def _build_param_meta_map(context: dict, payload: dict) -> dict:
    meta = {}
    for row in context.get("param_dictionary_snapshot") or []:
        if not isinstance(row, dict):
            continue
        key = clean_text(row.get("param_key"))
        if not key:
            continue
        meta[key] = {
            "name": row.get("name"),
            "canonical_name_zh": row.get("canonical_name_zh"),
            "canonical_name_en": row.get("canonical_name_en"),
            "preferred_unit": row.get("preferred_unit"),
            "value_type": row.get("value_type"),
            "spec_category_name": row.get("spec_category_name"),
        }
    for row in payload.get("params") or []:
        if not isinstance(row, dict):
            continue
        key = clean_text(row.get("param_key"))
        if not key:
            continue
        meta.setdefault(
            key,
            {
                "name": row.get("name"),
                "canonical_name_zh": row.get("canonical_name_zh") or row.get("name"),
                "canonical_name_en": row.get("canonical_name_en"),
                "preferred_unit": row.get("preferred_unit"),
                "value_type": row.get("value_type"),
                "spec_category_name": row.get("spec_category_name"),
            },
        )
    return meta


def _upsert_param_definition(payload: dict, param_meta_map: dict, param_key: str, candidate_name: str):
    if not param_key:
        return
    exists = any(
        isinstance(row, dict) and clean_text(row.get("param_key")) == param_key
        for row in (payload.get("params") or [])
    )
    if exists:
        return
    meta = param_meta_map.get(param_key) or {}
    row = {
        "param_key": param_key,
        "name": candidate_name or meta.get("canonical_name_zh") or meta.get("name") or param_key,
        "canonical_name_zh": meta.get("canonical_name_zh") or candidate_name or False,
        "canonical_name_en": meta.get("canonical_name_en") or False,
        "value_type": meta.get("value_type") or "char",
        "preferred_unit": meta.get("preferred_unit") or False,
        "spec_category_name": meta.get("spec_category_name") or PARAM_CATEGORY_FALLBACK.get(param_key) or False,
        "source": "postprocess",
    }
    payload.setdefault("params", []).append(row)
    param_meta_map[param_key] = {
        "name": row["name"],
        "canonical_name_zh": row["canonical_name_zh"],
        "canonical_name_en": row["canonical_name_en"],
        "preferred_unit": row["preferred_unit"],
        "value_type": row["value_type"],
        "spec_category_name": row["spec_category_name"],
    }


def _promote_candidate_unmatched(payload: dict, param_meta_map: dict):
    remaining = []
    for row in payload.get("unmatched") or []:
        if not isinstance(row, dict):
            continue
        candidate_key = clean_text(row.get("candidate_param_key"))
        candidate_name = clean_text(row.get("candidate_name"))
        content = clean_text(row.get("content"))
        source_label = clean_text(row.get("source_label"))
        meta = param_meta_map.get(candidate_key) or {}
        if not candidate_key or not meta:
            remaining.append(row)
            continue

        _upsert_param_definition(payload, param_meta_map, candidate_key, candidate_name)
        promoted = False

        if candidate_key == "liner_material" and content:
            payload.setdefault("spec_values", []).append(
                {
                    "param_key": candidate_key,
                    "param_name": candidate_name or meta.get("canonical_name_zh") or meta.get("name") or "离型材料",
                    "value": map_known_value(content),
                    "unit": False,
                    "source_label": "离型材料",
                    "source": "postprocess",
                }
            )
            promoted = True
        elif candidate_key in ("peel_180_painted_initial", "peel_180_painted_humidity_aging"):
            source_key = source_label.lower()
            for spec in payload.get("spec_values") or []:
                if not isinstance(spec, dict):
                    continue
                if clean_text(spec.get("param_key")) != "peel_strength_180":
                    continue
                spec_source_label = clean_text(spec.get("source_label")).lower()
                spec_condition = spec.get("condition") if isinstance(spec.get("condition"), dict) else {}
                substrate = clean_text(spec_condition.get("substrate"))
                state = clean_text(spec_condition.get("state"))
                if substrate != "涂装板":
                    continue
                if candidate_key == "peel_180_painted_initial" and (
                    spec_source_label == source_key or state == "初始状态"
                ):
                    spec["param_key"] = candidate_key
                    promoted = True
                elif candidate_key == "peel_180_painted_humidity_aging" and (
                    spec_source_label == source_key or state == "湿热老化后"
                ):
                    spec["param_key"] = candidate_key
                    promoted = True

        if not promoted:
            remaining.append(row)
    payload["unmatched"] = remaining


def _append_category_param_rows(payload: dict, param_meta_map: dict):
    existing = set()
    rows = []
    for row in payload.get("category_params") or []:
        if not isinstance(row, dict):
            continue
        key = clean_text(row.get("param_key"))
        category_name = clean_text(row.get("category_name") or row.get("categ_name"))
        if key and category_name:
            existing.add((key, category_name))
        rows.append(row)

    used_keys = []
    for bucket in ("params", "spec_values"):
        for row in payload.get(bucket) or []:
            if not isinstance(row, dict):
                continue
            key = clean_text(row.get("param_key"))
            if key and key not in used_keys:
                used_keys.append(key)

    for key in used_keys:
        meta = param_meta_map.get(key) or {}
        category_name = clean_text(meta.get("spec_category_name")) or PARAM_CATEGORY_FALLBACK.get(key, "")
        if not category_name and key.startswith("peel_"):
            category_name = "粘接性能"
        if not category_name or (key, category_name) in existing:
            continue
        rows.append(
            {
                "param_key": key,
                "category_name": category_name,
                "categ_name": category_name,
                "param_name": meta.get("canonical_name_zh") or meta.get("name") or False,
                "source": "postprocess",
            }
        )
        existing.add((key, category_name))
    payload["category_params"] = rows


def _apply_route_tags(payload: dict):
    """Route tags are metadata for downstream import mapping."""
    for row in payload.get("params") or []:
        if not isinstance(row, dict):
            continue
        key = clean_text(row.get("param_key"))
        if key in MAIN_FIELD_ROUTE_MAP:
            row["is_main_field"] = True
            row["main_field_name"] = row.get("main_field_name") or MAIN_FIELD_ROUTE_MAP[key]
            row["target_bucket"] = row.get("target_bucket") or "items"
            row["target_field"] = row.get("target_field") or MAIN_FIELD_ROUTE_MAP[key]
            row["scope_hint"] = row.get("scope_hint") or "item"
        else:
            row["target_bucket"] = row.get("target_bucket") or "spec_values"
            row["scope_hint"] = row.get("scope_hint") or "item"
        if key in NOTE_PARAM_KEYS:
            row["is_note_field"] = True

    for row in payload.get("spec_values") or []:
        if not isinstance(row, dict):
            continue
        row["target_bucket"] = "spec_values"
        key = clean_text(row.get("param_key"))
        if key in NOTE_PARAM_KEYS:
            row["note_semantics"] = "true"


def normalize_items(payload: dict, context: dict) -> dict:
    for row in payload.get("items") or []:
        if not isinstance(row, dict):
            continue
        for key in ("color_name", "adhesive_type_name", "base_material_name"):
            row[key] = map_known_value(row.get(key))
        if not clean_text(row.get("category_name")):
            inferred = _infer_category_name(row)
            if inferred:
                row["category_name"] = inferred
                review_note = clean_text(row.get("review_note"))
                row["review_note"] = (f"{review_note} " if review_note else "") + f"Category inferred as {inferred}."
    return payload


def normalize_params(payload: dict, context: dict, param_meta_map: dict) -> dict:
    for row in payload.get("params") or []:
        if not isinstance(row, dict):
            continue
        key = clean_text(row.get("param_key"))
        meta = param_meta_map.get(key) or {}
        if meta:
            current_name = clean_text(row.get("name"))
            if _looks_english_or_key_like(current_name, key):
                row["name"] = _translate_param_name_to_zh(
                    _resolve_preferred_zh_name(meta, current_name, key),
                    key,
                )
            if _looks_english_or_key_like(clean_text(row.get("canonical_name_zh")), key):
                resolved = _resolve_preferred_zh_name(meta, current_name, key)
                translated = _translate_param_name_to_zh(resolved, key)
                row["canonical_name_zh"] = translated if translated != key else row.get("canonical_name_zh") or False
        elif _looks_english_or_key_like(clean_text(row.get("name")), key):
            row["name"] = _translate_param_name_to_zh(clean_text(row.get("name")), key)
    return payload


def normalize_spec_values(payload: dict, context: dict, param_meta_map: dict) -> dict:
    items = payload.get("items") or [{}]
    review_target = items[0] if items else {}

    for row in payload.get("spec_values") or []:
        if not isinstance(row, dict):
            continue

        row["condition"] = translate_condition(row.get("condition"))

        if row.get("param_key") == "structure":
            row["value"] = translate_structure_value(row.get("value"))
        elif row.get("param_key") == "shelf_life_storage":
            row["value"] = translate_shelf_life_value(row.get("value"))
        elif row.get("param_key") == "liner_material":
            row["value"] = map_known_value(row.get("value"))

        if row.get("param_key") == "peel_strength_180" and isinstance(row.get("condition"), dict):
            condition = row["condition"]
            substrate = clean_text(condition.get("substrate"))
            state = clean_text(condition.get("state"))
            if substrate == "涂装板":
                if state == "即时状态":
                    row["param_key"] = "peel_180_painted_immediate"
                elif state == "初始状态":
                    row["param_key"] = "peel_180_painted_initial"
                elif state == "常温状态":
                    row["param_key"] = "peel_180_painted_normal"
                elif state == "高温状态":
                    row["param_key"] = "peel_180_painted_high_temp"
                elif state == "热老化后":
                    row["param_key"] = "peel_180_painted_heat_aging"
                elif state == "湿热老化后":
                    row["param_key"] = "peel_180_painted_humidity_aging"
            else:
                derived = derive_specific_peel_meta_from_row(row)
                if derived and derived.get("review_only"):
                    review_note = clean_text(review_target.get("review_note"))
                    review_target["review_note"] = (f"{review_note} " if review_note else "") + derived["review_note"]
                elif derived:
                    row["param_key"] = derived["param_key"]
                    row["param_name"] = derived["param_name"]
                    _upsert_param_definition(payload, param_meta_map, derived["param_key"], derived["param_name"])

        row["source_label"] = normalize_source_label(row.get("source_label"))
        key = clean_text(row.get("param_key"))
        meta = param_meta_map.get(key) or {}
        current_param_name = clean_text(row.get("param_name"))
        if meta and _looks_english_or_key_like(current_param_name, key):
            row["param_name"] = _translate_param_name_to_zh(
                _resolve_preferred_zh_name(meta, current_param_name, key),
                key,
            )
        elif _looks_english_or_key_like(current_param_name, key):
            row["param_name"] = _translate_param_name_to_zh(current_param_name, key)

    return payload


def postprocess_draft(task: dict, payload: dict, context: dict) -> dict:
    if not isinstance(payload, dict):
        payload = {}
    for bucket in ("series", "items", "params", "category_params", "spec_values", "unmatched"):
        if not isinstance(payload.get(bucket), list):
            payload[bucket] = []

    param_meta_map = _build_param_meta_map(context, payload)
    payload = normalize_items(payload, context)
    payload = normalize_params(payload, context, param_meta_map)
    payload = normalize_spec_values(payload, context, param_meta_map)
    payload = _promote_narrative_unmatched_to_series(payload)
    payload = process_unmatched(payload, context)
    _promote_candidate_unmatched(payload, param_meta_map)
    _append_category_param_rows(payload, param_meta_map)
    _apply_route_tags(payload)
    return payload
