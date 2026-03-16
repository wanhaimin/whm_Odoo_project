# -*- coding: utf-8 -*-

import argparse
import base64
import importlib.util
import json
import os
import re
import sys
from io import BytesIO
from pathlib import Path

import requests

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def _load_module(module_name, file_path):
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def _load_openclaw_adapter():
    module = _load_module(
        "diecut_openclaw_adapter",
        PROJECT_ROOT / "diecut" / "tools" / "openclaw_adapter.py",
    )
    return module.OpenClawAdapter


def _load_skill_context():
    module = _load_module(
        "diecut_tds_skill_context",
        PROJECT_ROOT / "diecut" / "tools" / "tds_skill_context.py",
    )
    return module.infer_brand_skill_name, module.load_skill_bundle


OpenClawAdapter = _load_openclaw_adapter()  # noqa: E402
infer_brand_skill_name, load_skill_bundle = _load_skill_context()  # noqa: E402


def _strip_json_fence(text):
    value = (text or "").strip()
    if value.startswith("```"):
        value = re.sub(r"^```(?:json)?", "", value).strip()
        value = re.sub(r"```$", "", value).strip()
    return value


def _parse_json_loose(text):
    value = _strip_json_fence(text)
    try:
        return json.loads(value)
    except Exception:
        pass
    match = re.search(r"(\{[\s\S]*\}|\[[\s\S]*\])", value)
    if match:
        return json.loads(match.group(1))
    raise ValueError("Model did not return valid JSON.")


def _load_openclaw_settings():
    cfg_path = Path.home() / ".openclaw" / "openclaw.json"
    config = {}
    if cfg_path.exists():
        try:
            config = json.loads(cfg_path.read_text(encoding="utf-8"))
        except Exception:
            config = {}
    gateway_port = (((config.get("gateway") or {}).get("port")) or 18789)
    gateway = os.environ.get("OPENCLAW_GATEWAY_URL") or f"ws://127.0.0.1:{gateway_port}"
    token = (
        os.environ.get("OPENCLAW_GATEWAY_TOKEN")
        or (((config.get("gateway") or {}).get("auth") or {}).get("token"))
        or config.get("gatewayToken")
        or ""
    )
    agent_id = os.environ.get("OPENCLAW_AGENT_ID") or "odoo-diecut-dev"
    model = os.environ.get("OPENCLAW_MODEL") or "openai-codex/gpt-5.4"
    return {
        "gateway_url": gateway,
        "token": token,
        "agent_id": agent_id,
        "model": model,
    }


def _extract_pdf_text_and_images(binary, filename, max_text_pages=8, max_image_pages=3):
    try:
        import pypdfium2 as pdfium
    except ImportError as exc:
        raise RuntimeError("Missing pypdfium2, cannot parse PDF.") from exc

    doc = pdfium.PdfDocument(binary)
    texts = []
    attachments = []
    try:
        page_count = min(len(doc), max_text_pages)
        base_name = Path(filename or "source").stem
        for index in range(page_count):
            page = doc[index]
            try:
                textpage = page.get_textpage()
                page_text = textpage.get_text_range() or ""
                if page_text.strip():
                    texts.append(f"[PAGE {index + 1}]\n{page_text.strip()}")
            except Exception:
                pass
            if index < max_image_pages:
                bitmap = page.render(scale=1.6)
                image = bitmap.to_pil()
                buffer = BytesIO()
                image.save(buffer, format="JPEG", quality=82, optimize=True)
                attachments.append(
                    {
                        "name": f"{base_name}_page_{index + 1}.jpg",
                        "content": base64.b64encode(buffer.getvalue()).decode(),
                        "encoding": "base64",
                        "mimeType": "image/jpeg",
                    }
                )
        return "\n\n".join(texts).strip(), attachments
    finally:
        doc.close()


def _safe_list(value, limit=0):
    if not isinstance(value, list):
        return []
    return value[:limit] if limit else value


def _trim_dict_rows(rows, keys, limit):
    output = []
    for row in _safe_list(rows, limit=limit):
        if not isinstance(row, dict):
            continue
        output.append({key: row.get(key) for key in keys if row.get(key) not in (None, False, "", [])})
    return output


def _normalize_context(task):
    context = task.get("context_used") or {}
    if isinstance(context, str):
        try:
            context = json.loads(context)
        except Exception:
            context = {}
    if not isinstance(context, dict):
        context = {}
    brand_skill = (
        task.get("brand_skill_name")
        or context.get("brand_skill")
        or infer_brand_skill_name(
            brand_name=task.get("brand") or "",
            filename=task.get("primary_attachment_name") or "",
            title=task.get("name") or "",
        )
    )
    skill_profile = task.get("skill_profile") or context.get("skill_profile") or "generic_tds_v1+diecut_domain_v1"
    skill_bundle = load_skill_bundle(skill_profile, brand_skill)
    context["skill_profile"] = skill_profile
    context["brand_skill"] = brand_skill or ""
    context["skills_loaded"] = skill_bundle.get("skills_loaded") or []
    context["skill_bundle"] = skill_bundle
    return context


def _aliases_text(skill_bundle, limit=12):
    lines = []
    aliases = skill_bundle.get("param_aliases") or {}
    for index, (param_key, names) in enumerate(aliases.items()):
        if index >= limit:
            break
        clean_names = ", ".join(str(name) for name in (names or [])[:6] if name)
        if clean_names:
            lines.append(f"- {param_key}: {clean_names}")
    return "\n".join(lines)


def _join_lines(values, limit=12):
    output = []
    for value in _safe_list(values, limit=limit):
        clean = str(value or "").strip()
        if clean:
            output.append(f"- {clean}")
    return "\n".join(output)


def _build_model_context_text(task, context, param_limit=80, category_limit=80, instr_limit=20):
    skill_bundle = context.get("skill_bundle") or {}
    param_snapshot = _trim_dict_rows(
        context.get("param_dictionary_snapshot") or [],
        ["param_key", "name", "canonical_name_zh", "canonical_name_en", "spec_category_name", "value_type", "preferred_unit", "is_main_field", "main_field_name", "parse_hint"],
        param_limit,
    )
    category_snapshot = _trim_dict_rows(
        context.get("category_param_snapshot") or [],
        ["categ_name", "param_key", "param_name", "required", "show_in_form", "allow_import", "unit_override"],
        category_limit,
    )
    source_context = context.get("source_context") or {}
    output_schema = (skill_bundle.get("output_schema") or {}).get("required_buckets") or []
    text = f"""
TASK PROFILE
- title: {task.get('name') or ''}
- brand: {task.get('brand') or source_context.get('brand_name') or ''}
- category: {task.get('category') or source_context.get('category_name') or ''}
- attachment: {task.get('primary_attachment_name') or source_context.get('primary_attachment_name') or ''}
- skill_profile: {context.get('skill_profile') or ''}
- brand_skill: {context.get('brand_skill') or ''}

BUSINESS GOAL
- Parse a material TDS into Odoo draft data.
- Use existing dictionary keys when possible.
- Main fields should map to item core fields only when the dictionary marks them as main fields.
- Anything uncertain should go to unmatched with a reason.

OUTPUT BUCKETS
{_join_lines(output_schema, limit=12)}

TASK INSTRUCTIONS
{_join_lines(skill_bundle.get('task_instructions') or [], limit=instr_limit)}

FIELD MAPPING GUIDANCE
{_join_lines(skill_bundle.get('field_mapping_guidance') or [], limit=instr_limit)}

DOMAIN / BRAND CONVENTIONS
{_join_lines(skill_bundle.get('brand_or_domain_conventions') or [], limit=instr_limit)}

TABLE PATTERNS
{_join_lines(skill_bundle.get('table_patterns') or [], limit=instr_limit)}

METHOD PATTERNS
{_join_lines(skill_bundle.get('method_patterns') or [], limit=instr_limit)}

NEGATIVE RULES
{_join_lines(skill_bundle.get('negative_rules') or [], limit=instr_limit)}

PARAMETER ALIASES
{_aliases_text(skill_bundle, limit=20)}

MAIN FIELD WHITELIST
{_join_lines(context.get('main_field_whitelist') or [], limit=30)}

PARAMETER DICTIONARY SNAPSHOT
{json.dumps(param_snapshot, ensure_ascii=False, indent=2)}

CATEGORY PARAM SNAPSHOT
{json.dumps(category_snapshot, ensure_ascii=False, indent=2)}
""".strip()
    return text


def _build_vision_prompt(task, raw_text, context):
    context_text = _build_model_context_text(task, context)
    return (
        "You are the Vision Parser for an Odoo TDS Copilot.\n"
        "Read the attached PDF page images together with the extracted text.\n"
        "Return strict JSON with exactly these top-level keys: sections, tables, charts, methods, candidate_items.\n"
        "Each section should include a short label and page reference if visible.\n"
        "Each table should summarize what it contains and the likely business meaning.\n"
        "Each chart should include title, legend hints, axes hints, and business meaning.\n"
        "Each method should include test name, summary, and whether it looks like a reusable standard method card.\n"
        "candidate_items should contain likely item codes and any nearby thickness or variant hints.\n"
        "Do not emit markdown. Do not emit prose outside JSON.\n\n"
        f"{context_text}\n\n"
        "DOCUMENT EXCERPT\n"
        f"{(raw_text or '')[:60000]}"
    )


def _build_struct_prompt(task, raw_text, vision_payload, context):
    context_text = _build_model_context_text(task, context)
    return (
        "You are the Structuring Agent for an Odoo TDS Copilot.\n"
        "Use the full document excerpt, the vision analysis, and the business context to produce the final draft.\n"
        "Return strict JSON with exactly these top-level keys: series, items, params, category_params, spec_values, unmatched.\n"
        "Do not return a patch. Return the full draft.\n"
        "Prefer existing dictionary param_key values when there is a good fit.\n"
        "When a value belongs in item core fields, still keep the routing consistent with the dictionary main-field flag.\n"
        "Methods such as Pluck, Torque, and Static Shear should become reusable method cards in params[].method_html when appropriate.\n"
        "Use unmatched only for genuinely uncertain or out-of-schema content, and always include a reason.\n"
        "Do not emit markdown. Do not emit prose outside JSON.\n\n"
        f"{context_text}\n\n"
        "VISION PAYLOAD\n"
        f"{json.dumps(vision_payload or {}, ensure_ascii=False, indent=2)}\n\n"
        "DOCUMENT EXCERPT\n"
        f"{(raw_text or '')[:90000]}"
    )


def _build_single_pass_prompt(task, raw_text, context, fast_mode=False):
    if fast_mode:
        context_text = _build_model_context_text(task, context, param_limit=12, category_limit=12, instr_limit=6)
        excerpt = (raw_text or "")[:12000]
        speed_note = (
            "FAST MODE: prioritize core fields, item codes, and high-confidence parameter candidates. "
            "Do not try exhaustive extraction in this pass."
        )
    else:
        context_text = _build_model_context_text(task, context, param_limit=24, category_limit=24, instr_limit=8)
        excerpt = (raw_text or "")[:24000]
        speed_note = "FULL MODE: extract as complete as possible."
    return (
        "You are the single-pass TDS copilot for an Odoo diecut ERP.\n"
        "Read the attached PDF page images and text excerpt, then output final strict JSON.\n"
        "Top-level keys must be exactly: series, items, params, category_params, spec_values, unmatched.\n"
        "Do not output markdown. Do not output explanation text outside JSON.\n"
        "Use existing param_key values whenever possible.\n"
        "Main fields (thickness/color/adhesive/base material) should be populated in items.\n"
        "Long-tail technical values should go to spec_values with condition/unit/source labels when possible.\n"
        "Uncertain values must go to unmatched with reason.\n\n"
        f"{speed_note}\n\n"
        f"{context_text}\n\n"
        "DOCUMENT EXCERPT\n"
        f"{excerpt}"
    )


def _normalize_draft_payload(payload):
    if not isinstance(payload, dict):
        payload = {}
    for bucket in ("series", "items", "params", "category_params", "spec_values", "unmatched"):
        if not isinstance(payload.get(bucket), list):
            payload[bucket] = []
    return payload


def _build_vision_payload(adapter, settings, task, raw_text, attachments, context):
    if not attachments:
        return {}
    prompt = _build_vision_prompt(task, raw_text, context)
    result = adapter.agent(
        message=prompt,
        agent_id=settings["agent_id"],
        session_key=f"agent:{settings['agent_id']}:tds-worker-{task['source_document_id']}-vision",
        timeout=720,
        attachments=attachments,
    )
    return _parse_json_loose(result.get("text"))


def _build_struct_payload(adapter, settings, task, raw_text, vision_payload, context):
    prompt = _build_struct_prompt(task, raw_text, vision_payload, context)
    result = adapter.agent(
        message=prompt,
        agent_id=settings["agent_id"],
        session_key=f"agent:{settings['agent_id']}:tds-worker-{task['source_document_id']}-struct",
        timeout=900,
    )
    payload = _parse_json_loose(result.get("text"))
    return _normalize_draft_payload(payload)


def _build_single_pass_payload(adapter, settings, task, raw_text, attachments, context, fast_mode=False):
    prompt = _build_single_pass_prompt(task, raw_text, context, fast_mode=fast_mode)
    result = adapter.agent(
        message=prompt,
        agent_id=settings["agent_id"],
        session_key=f"agent:{settings['agent_id']}:tds-worker-{task['source_document_id']}-single",
        timeout=120 if fast_mode else 480,
        attachments=attachments or None,
    )
    payload = _parse_json_loose(result.get("text"))
    return _normalize_draft_payload(payload)


def _coerce_json_object(value):
    if not value:
        return {}
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except Exception:
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


_CORE_VALUE_MAP = {
    "light blue": "浅蓝色",
    "blue": "蓝色",
    "black": "黑色",
    "clear": "透明",
    "paper": "纸",
    "non-woven cloth": "无纺布",
    "non woven cloth": "无纺布",
    "acrylic pressure sensitive adhesive": "丙烯酸压敏胶",
}

_STATE_VALUE_MAP = {
    "immediate": "即时状态",
    "initial state": "初始状态",
    "normal state": "常温状态",
    "at high temperature": "高温状态",
    "heat aging": "热老化后",
    "humidity aging": "湿热老化后",
}

_SUBSTRATE_VALUE_MAP = {
    "painted panel": "涂装板",
    "polypropylene": "PP板",
    "headliner a (non-woven cloth surface)": "顶棚A（无纺布表面）",
}

_INFERRED_CATEGORY_RULES = [
    {
        "match": ("无纺布", "non-woven cloth", "non woven cloth"),
        "category_name": "原材料 / 胶带类 / 棉纸/无纺布双面胶带",
    },
    {
        "match": ("泡棉", "foam", "acrylic foam"),
        "category_name": "原材料 / 胶带类 / 泡棉胶带",
    },
]

_PARAM_CATEGORY_FALLBACK = {
    "peel_strength_180": "粘接性能",
    "structure": "基础规格",
    "shelf_life_storage": "包装与储存",
}


def _clean_text(value):
    return str(value or "").strip()


def _map_known_value(value):
    cleaned = _clean_text(value)
    if not cleaned:
        return value
    mapped = _CORE_VALUE_MAP.get(cleaned.lower())
    return mapped or value


def _translate_structure_value(value):
    cleaned = _clean_text(value)
    if not cleaned:
        return value
    translated = (
        cleaned.replace("Paper liner", "纸质离型层")
        .replace("Acrylic pressure sensitive adhesive", "丙烯酸压敏胶层")
        .replace("Non-woven cloth", "无纺布基材")
    )
    if translated != cleaned and "/" in translated:
        return translated
    return value


def _translate_shelf_life_value(value):
    cleaned = _clean_text(value)
    if not cleaned:
        return value
    match = re.search(
        r"Three years \((?P<months>\d+)\s*months\).*?stored at (?P<temp>[\d.]+°C) and (?P<rh>[\d.]+% relative humidity)",
        cleaned,
        flags=re.I,
    )
    if match:
        return f"自生产日期起保质期三年（{match.group('months')}个月），建议在 {match.group('temp')} / {match.group('rh')} 条件下储存。"
    return value


def _translate_condition(condition):
    if not isinstance(condition, dict):
        return condition
    translated = dict(condition)
    state = _clean_text(translated.get("state"))
    substrate = _clean_text(translated.get("substrate"))
    if state:
        translated["state"] = _STATE_VALUE_MAP.get(state.lower(), translated["state"])
    if substrate:
        lowered = substrate.lower()
        for key, mapped in _SUBSTRATE_VALUE_MAP.items():
            if key in lowered:
                translated["substrate"] = mapped
                break
    return translated


def _infer_category_name(item):
    haystack = " ".join(
        _clean_text(item.get(key))
        for key in ("base_material_name", "adhesive_type_name", "series_name", "review_note", "name", "code")
    ).lower()
    for rule in _INFERRED_CATEGORY_RULES:
        if any(keyword.lower() in haystack for keyword in rule["match"]):
            return rule["category_name"]
    return False


def _build_param_meta_map(context):
    mapping = {}
    for row in context.get("param_dictionary_snapshot") or []:
        if not isinstance(row, dict):
            continue
        key = _clean_text(row.get("param_key"))
        if key:
            if row.get("spec_category") and not row.get("spec_category_name"):
                row = dict(row)
                row["spec_category_name"] = row.get("spec_category")
            mapping[key] = row
    return mapping


def _append_category_param_rows(payload, param_meta_map):
    existing = set()
    rows = []
    payload_param_map = {
        _clean_text(row.get("param_key")): row
        for row in (payload.get("params") or [])
        if isinstance(row, dict) and _clean_text(row.get("param_key"))
    }
    for row in payload.get("category_params") or []:
        if not isinstance(row, dict):
            continue
        key = _clean_text(row.get("param_key"))
        category_name = _clean_text(row.get("category_name") or row.get("categ_name"))
        if key and category_name:
            existing.add((key, category_name))
        rows.append(row)
    used_keys = []
    for bucket in ("params", "spec_values"):
        for row in payload.get(bucket) or []:
            if not isinstance(row, dict):
                continue
            key = _clean_text(row.get("param_key"))
            if key and key not in used_keys:
                used_keys.append(key)
    for key in used_keys:
        meta = param_meta_map.get(key) or {}
        payload_param = payload_param_map.get(key) or {}
        category_name = _clean_text(meta.get("spec_category_name")) or _PARAM_CATEGORY_FALLBACK.get(key, "")
        if not category_name and key.startswith("peel_"):
            category_name = "粘接性能"
        if not category_name or (key, category_name) in existing:
            continue
        rows.append(
            {
                "param_key": key,
                "category_name": category_name,
                "categ_name": category_name,
                "param_name": (
                    meta.get("canonical_name_zh")
                    or meta.get("name")
                    or payload_param.get("canonical_name_zh")
                    or payload_param.get("name")
                    or False
                ),
                "source": "postprocess",
            }
        )
        existing.add((key, category_name))
    payload["category_params"] = rows


def _post_process_unmatched(payload, context):
    remaining = []
    items = payload.get("items") or []
    ignored_types = {"regulatory_contact", "contact_info", "marketing_claim", "legal_disclaimer"}
    for row in payload.get("unmatched") or []:
        if not isinstance(row, dict):
            continue
        if row.get("type") in ignored_types:
            continue
        source_label = _clean_text(row.get("source_label")).lower()
        content = _clean_text(row.get("content"))
        if row.get("type") == "classification_gap" and items:
            inferred = _clean_text(items[0].get("category_name"))
            if inferred:
                continue
        if row.get("type") == "alias_candidate":
            continue
        if source_label == "liner" and content:
            row["candidate_param_key"] = "liner_material"
            row["candidate_name"] = "离型材料"
            row["content"] = _map_known_value(content)
            row["reason"] = "已识别为离型材料候选，但当前参数字典缺少通用 liner_material 键，建议人工确认是否新增。"
        elif source_label == "painted panel - initial state":
            row["candidate_param_key"] = "peel_180_painted_initial"
            row["candidate_name"] = "涂装板-初始状态-180度剥离力"
        elif source_label == "painted panel - humidity aging":
            row["candidate_param_key"] = "peel_180_painted_humidity_aging"
            row["candidate_name"] = "涂装板-湿热老化后-180度剥离力"
        remaining.append(row)
    payload["unmatched"] = remaining


def _post_process_draft(task, payload, context):
    if not isinstance(payload, dict):
        return payload
    param_meta_map = _build_param_meta_map(context)

    for row in payload.get("items") or []:
        if not isinstance(row, dict):
            continue
        for key in ("color_name", "adhesive_type_name", "base_material_name"):
            row[key] = _map_known_value(row.get(key))
        category_name = _clean_text(row.get("category_name"))
        if not category_name:
            inferred = _infer_category_name(row)
            if inferred:
                row["category_name"] = inferred
                row["review_note"] = (
                    (_clean_text(row.get("review_note")) + " " if _clean_text(row.get("review_note")) else "")
                    + f"Category inferred as {inferred}."
                ).strip()

    for row in payload.get("params") or []:
        if not isinstance(row, dict):
            continue
        key = _clean_text(row.get("param_key"))
        meta = param_meta_map.get(key) or {}
        if meta:
            row["name"] = row.get("name") or meta.get("canonical_name_zh") or meta.get("name")

    for row in payload.get("spec_values") or []:
        if not isinstance(row, dict):
            continue
        row["condition"] = _translate_condition(row.get("condition"))
        if row.get("param_key") == "structure":
            row["value"] = _translate_structure_value(row.get("value"))
        elif row.get("param_key") == "shelf_life_storage":
            row["value"] = _translate_shelf_life_value(row.get("value"))
        elif row.get("param_key") == "liner_material":
            row["value"] = _map_known_value(row.get("value"))
        if row.get("param_key") == "peel_strength_180" and isinstance(row.get("condition"), dict):
            condition = row["condition"]
            substrate = _clean_text(condition.get("substrate"))
            state = _clean_text(condition.get("state"))
            if substrate == "涂装板":
                if state == "即时状态":
                    row["param_key"] = "peel_180_painted_immediate"
                elif state == "常温状态":
                    row["param_key"] = "peel_180_painted_normal"
                elif state == "高温状态":
                    row["param_key"] = "peel_180_painted_high_temp"
                elif state == "热老化后":
                    row["param_key"] = "peel_180_painted_heat_aging"
            else:
                derived = _derive_specific_peel_meta_from_row(row)
                if derived and derived.get("review_only"):
                    review_note = _clean_text((payload.get("items") or [{}])[0].get("review_note"))
                    (payload.get("items") or [{}])[0]["review_note"] = (
                        f"{review_note} " if review_note else ""
                    ) + derived["review_note"]
                elif derived:
                    row["param_key"] = derived["param_key"]
                    row["param_name"] = derived["param_name"]
                    _upsert_param_definition(payload, param_meta_map, derived["param_key"], derived["param_name"])
        row["source_label"] = (
            _clean_text(row.get("source_label"))
            .replace("Painted Panel", "涂装板")
            .replace("Polypropylene", "PP板")
            .replace("Headliner A", "顶棚A")
            .replace("Immediate", "即时状态")
            .replace("Initial state", "初始状态")
            .replace("Normal state", "常温状态")
            .replace("At high temperature", "高温状态")
            .replace("Heat aging", "热老化后")
            .replace("Humidity aging", "湿热老化后")
        )
    _append_category_param_rows(payload, param_meta_map)
    _post_process_unmatched(payload, context)
    return payload


_CORE_VALUE_MAP = {
    "light blue": "浅蓝色",
    "blue": "蓝色",
    "black": "黑色",
    "clear": "透明",
    "paper": "纸",
    "non-woven cloth": "无纺布",
    "non woven cloth": "无纺布",
    "acrylic pressure sensitive adhesive": "丙烯酸压敏胶",
}

_STATE_VALUE_MAP = {
    "immediate": "即时状态",
    "initial state": "初始状态",
    "normal state": "常温状态",
    "at high temperature": "高温状态",
    "heat aging": "热老化后",
    "humidity aging": "湿热老化后",
}

_SUBSTRATE_VALUE_MAP = {
    "painted panel": "涂装板",
    "polypropylene": "PP板",
}

_INFERRED_CATEGORY_RULES = [
    {
        "match": ("无纺布", "non-woven cloth", "non woven cloth"),
        "category_name": "原材料 / 胶带类 / 棉纸/无纺布双面胶带",
    },
    {
        "match": ("泡棉", "foam", "acrylic foam"),
        "category_name": "原材料 / 胶带类 / 泡棉胶带",
    },
]

_PARAM_CATEGORY_FALLBACK = {
    "peel_strength_180": "粘接性能",
    "structure": "基础规格",
    "shelf_life_storage": "包装与储存",
    "liner_material": "基础规格",
    "peel_180_painted_initial": "粘接性能",
    "peel_180_painted_humidity_aging": "粘接性能",
    "peel_180_pp_immediate": "粘接性能",
    "peel_180_pp_initial": "粘接性能",
    "peel_180_pp_normal": "粘接性能",
    "peel_180_pp_high_temp": "粘接性能",
    "peel_180_pp_heat_aging": "粘接性能",
    "peel_180_pp_humidity_aging": "粘接性能",
    "peel_180_headliner_a_immediate": "粘接性能",
    "peel_180_headliner_a_initial": "粘接性能",
    "peel_180_headliner_a_normal": "粘接性能",
    "peel_180_headliner_a_high_temp": "粘接性能",
    "peel_180_headliner_a_heat_aging": "粘接性能",
    "peel_180_headliner_a_humidity_aging": "粘接性能",
}


def _translate_structure_value(value):
    cleaned = _clean_text(value)
    if not cleaned:
        return value
    translated = (
        cleaned.replace("Paper liner", "纸质离型层")
        .replace("Acrylic pressure sensitive adhesive", "丙烯酸压敏胶层")
        .replace("Non-woven cloth", "无纺布基材")
    )
    if translated != cleaned and "/" in translated:
        return translated
    return value


def _translate_shelf_life_value(value):
    cleaned = _clean_text(value)
    if not cleaned:
        return value
    match = re.search(
        r"Three years \((?P<months>\d+)\s*months\).*?stored at (?P<temp>[\d.]+(?:°|º|掳)?C) and (?P<rh>[\d.]+% relative humidity)",
        cleaned,
        flags=re.I,
    )
    if match:
        temp = match.group("temp").replace("掳", "°").replace("º", "°")
        return f"自生产日期起保质期三年（{match.group('months')}个月），建议在 {temp} / {match.group('rh')} 条件下储存。"
    return value


def _translate_condition(condition):
    if not isinstance(condition, dict):
        return condition
    translated = dict(condition)
    state = _clean_text(translated.get("state"))
    substrate = _clean_text(translated.get("substrate"))
    if state:
        translated["state"] = _STATE_VALUE_MAP.get(state.lower(), translated["state"])
    if substrate:
        lowered = substrate.lower()
        for key, mapped in _SUBSTRATE_VALUE_MAP.items():
            if key in lowered:
                translated["substrate"] = mapped
                break
    return translated


def _infer_category_name(item):
    haystack = " ".join(
        _clean_text(item.get(key))
        for key in ("base_material_name", "adhesive_type_name", "series_name", "review_note", "name", "code")
    ).lower()
    for rule in _INFERRED_CATEGORY_RULES:
        if any(keyword.lower() in haystack for keyword in rule["match"]):
            return rule["category_name"]
    return False


def _build_param_meta_map(context):
    mapping = {}
    for row in context.get("param_dictionary_snapshot") or []:
        if not isinstance(row, dict):
            continue
        key = _clean_text(row.get("param_key"))
        if key:
            normalized = dict(row)
            if normalized.get("spec_category") and not normalized.get("spec_category_name"):
                normalized["spec_category_name"] = normalized.get("spec_category")
            mapping[key] = normalized
    return mapping


def _state_suffix(state):
    mapping = {
        "即时状态": "immediate",
        "初始状态": "initial",
        "常温状态": "normal",
        "高温状态": "high_temp",
        "热老化后": "heat_aging",
        "湿热老化后": "humidity_aging",
    }
    return mapping.get(_clean_text(state), "")


def _derive_specific_peel_meta(condition):
    if not isinstance(condition, dict):
        return None
    substrate = _clean_text(condition.get("substrate"))
    state = _clean_text(condition.get("state"))
    suffix = _state_suffix(state)
    block = _clean_text(condition.get("block"))
    if not substrate or not suffix:
        return None
    if substrate == "PP板":
        return {
            "param_key": f"peel_180_pp_{suffix}",
            "param_name": f"PP板-{state}-180度剥离力",
        }
    if substrate == "顶棚A（无纺布表面）":
        if block:
            return {
                "review_only": True,
                "review_note": f"顶棚A（无纺布表面）存在重复结果区块：{state}（{block}）",
            }
        return {
            "param_key": f"peel_180_headliner_a_{suffix}",
            "param_name": f"顶棚A（无纺布表面）-{state}-180度剥离力",
        }
    return None


def _derive_specific_peel_meta_from_row(row):
    if not isinstance(row, dict):
        return None
    condition = row.get("condition") if isinstance(row.get("condition"), dict) else {}
    derived = _derive_specific_peel_meta(condition)
    if derived:
        return derived
    source_label = _clean_text(row.get("source_label"))
    label_map = (
        ("PP板 - ", "peel_180_pp", "PP板"),
        ("Headliner A - ", "peel_180_headliner_a", "顶棚A（无纺布表面）"),
        ("顶棚A - ", "peel_180_headliner_a", "顶棚A（无纺布表面）"),
    )
    for prefix, key_prefix, zh_label in label_map:
        if source_label.startswith(prefix):
            state = source_label.replace(prefix, "", 1)
            suffix = _state_suffix(state)
            if not suffix:
                return None
            if "second block" in source_label.lower():
                return {
                    "review_only": True,
                    "review_note": f"{zh_label}存在重复结果区块：{state}",
                }
            return {
                "param_key": f"{key_prefix}_{suffix}",
                "param_name": f"{zh_label}-{state}-180度剥离力",
            }
    return None


def _append_category_param_rows(payload, param_meta_map):
    existing = set()
    rows = []
    for row in payload.get("category_params") or []:
        if not isinstance(row, dict):
            continue
        key = _clean_text(row.get("param_key"))
        category_name = _clean_text(row.get("category_name") or row.get("categ_name"))
        if key and category_name:
            existing.add((key, category_name))
        rows.append(row)
    used_keys = []
    for bucket in ("params", "spec_values"):
        for row in payload.get(bucket) or []:
            if not isinstance(row, dict):
                continue
            key = _clean_text(row.get("param_key"))
            if key and key not in used_keys:
                used_keys.append(key)
    for key in used_keys:
        meta = param_meta_map.get(key) or {}
        category_name = _clean_text(meta.get("spec_category_name")) or _PARAM_CATEGORY_FALLBACK.get(key, "")
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


def _upsert_param_definition(payload, param_meta_map, param_key, candidate_name):
    if not param_key:
        return
    exists = any(
        isinstance(row, dict) and _clean_text(row.get("param_key")) == param_key
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
        "spec_category_name": meta.get("spec_category_name") or _PARAM_CATEGORY_FALLBACK.get(param_key) or False,
        "source": "postprocess",
    }
    payload.setdefault("params", []).append(row)
    param_meta_map[param_key] = {
        "canonical_name_zh": row.get("canonical_name_zh") or row.get("name") or False,
        "canonical_name_en": row.get("canonical_name_en") or False,
        "name": row.get("name") or False,
        "preferred_unit": row.get("preferred_unit") or False,
        "value_type": row.get("value_type") or "char",
        "spec_category_name": row.get("spec_category_name") or False,
    }


def _promote_candidate_unmatched(payload, param_meta_map):
    remaining = []
    for row in payload.get("unmatched") or []:
        if not isinstance(row, dict):
            continue
        candidate_key = _clean_text(row.get("candidate_param_key"))
        candidate_name = _clean_text(row.get("candidate_name"))
        content = _clean_text(row.get("content"))
        source_label = _clean_text(row.get("source_label"))
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
                    "value": _map_known_value(content),
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
                if _clean_text(spec.get("param_key")) != "peel_strength_180":
                    continue
                spec_source_label = _clean_text(spec.get("source_label")).lower()
                spec_condition = spec.get("condition") if isinstance(spec.get("condition"), dict) else {}
                substrate = _clean_text(spec_condition.get("substrate"))
                state = _clean_text(spec_condition.get("state"))
                if substrate != "涂装板":
                    continue
                if candidate_key == "peel_180_painted_initial" and (spec_source_label == source_key or state == "初始状态"):
                    spec["param_key"] = candidate_key
                    promoted = True
                elif candidate_key == "peel_180_painted_humidity_aging" and (spec_source_label == source_key or state == "湿热老化后"):
                    spec["param_key"] = candidate_key
                    promoted = True

        if not promoted:
            remaining.append(row)
    payload["unmatched"] = remaining


def _post_process_unmatched(payload, context):
    remaining = []
    items = payload.get("items") or []
    ignored_types = {"regulatory_contact", "contact_info", "marketing_claim", "legal_disclaimer"}
    for row in payload.get("unmatched") or []:
        if not isinstance(row, dict):
            continue
        if row.get("type") in ignored_types:
            continue
        source_label = _clean_text(row.get("source_label")).lower()
        content = _clean_text(row.get("content"))
        if row.get("type") == "classification_gap" and items:
            inferred = _clean_text(items[0].get("category_name"))
            if inferred:
                continue
        if row.get("type") == "alias_candidate":
            continue
        if source_label == "duplicate headliner a blocks" and items:
            review_note = _clean_text(items[0].get("review_note"))
            items[0]["review_note"] = (
                f"{review_note} " if review_note else ""
            ) + "顶棚A（无纺布表面）存在重复测试区块，第二组结果已保留为辅助复核信息。"
            continue
        if source_label == "performance note" and items:
            review_note = _clean_text(items[0].get("review_note"))
            items[0]["review_note"] = (
                f"{review_note} " if review_note else ""
            ) + "性能注记：离型面粘接性能低于当前数值，带下划线的值表示顶棚布面破坏。"
            continue
        if source_label == "liner" and content:
            row["candidate_param_key"] = "liner_material"
            row["candidate_name"] = "离型材料"
            row["content"] = _map_known_value(content)
            row["reason"] = "已识别为离型材料候选，请确认是否写入正式参数。"
        elif source_label == "painted panel - initial state":
            row["candidate_param_key"] = "peel_180_painted_initial"
            row["candidate_name"] = "涂装板-初始状态-180度剥离力"
        elif source_label == "painted panel - humidity aging":
            row["candidate_param_key"] = "peel_180_painted_humidity_aging"
            row["candidate_name"] = "涂装板-湿热老化后-180度剥离力"
        remaining.append(row)
    payload["unmatched"] = remaining


def _post_process_draft(task, payload, context):
    if not isinstance(payload, dict):
        return payload
    param_meta_map = _build_param_meta_map(context)

    for row in payload.get("items") or []:
        if not isinstance(row, dict):
            continue
        for key in ("color_name", "adhesive_type_name", "base_material_name"):
            row[key] = _map_known_value(row.get(key))
        category_name = _clean_text(row.get("category_name"))
        if not category_name:
            inferred = _infer_category_name(row)
            if inferred:
                row["category_name"] = inferred
                review_note = _clean_text(row.get("review_note"))
                row["review_note"] = (
                    f"{review_note} " if review_note else ""
                ) + f"Category inferred as {inferred}."

    for row in payload.get("params") or []:
        if not isinstance(row, dict):
            continue
        key = _clean_text(row.get("param_key"))
        meta = param_meta_map.get(key) or {}
        if meta:
            row["name"] = row.get("name") or meta.get("canonical_name_zh") or meta.get("name")

    for row in payload.get("spec_values") or []:
        if not isinstance(row, dict):
            continue
        row["condition"] = _translate_condition(row.get("condition"))
        if row.get("param_key") == "structure":
            row["value"] = _translate_structure_value(row.get("value"))
        elif row.get("param_key") == "shelf_life_storage":
            row["value"] = _translate_shelf_life_value(row.get("value"))
        elif row.get("param_key") == "liner_material":
            row["value"] = _map_known_value(row.get("value"))
        if row.get("param_key") == "peel_strength_180" and isinstance(row.get("condition"), dict):
            condition = row["condition"]
            substrate = _clean_text(condition.get("substrate"))
            state = _clean_text(condition.get("state"))
            if substrate == "涂装板":
                if state == "即时状态":
                    row["param_key"] = "peel_180_painted_immediate"
                elif state == "常温状态":
                    row["param_key"] = "peel_180_painted_normal"
                elif state == "高温状态":
                    row["param_key"] = "peel_180_painted_high_temp"
                elif state == "热老化后":
                    row["param_key"] = "peel_180_painted_heat_aging"
        row["source_label"] = (
            _clean_text(row.get("source_label"))
            .replace("Painted Panel", "涂装板")
            .replace("Polypropylene", "PP板")
            .replace("Immediate", "即时状态")
            .replace("Initial state", "初始状态")
            .replace("Normal state", "常温状态")
            .replace("At high temperature", "高温状态")
            .replace("Heat aging", "热老化后")
            .replace("Humidity aging", "湿热老化后")
        )

    _post_process_unmatched(payload, context)
    _promote_candidate_unmatched(payload, param_meta_map)
    _append_category_param_rows(payload, param_meta_map)
    return payload


# Final clean overrides to avoid historical encoding drift in earlier helper blocks.
def _state_suffix(state):
    normalized = _clean_text(state)
    mapping = {
        "\u5373\u65f6\u72b6\u6001": "immediate",
        "\u521d\u59cb\u72b6\u6001": "initial",
        "\u5e38\u6e29\u72b6\u6001": "normal",
        "\u9ad8\u6e29\u72b6\u6001": "high_temp",
        "\u70ed\u8001\u5316\u540e": "heat_aging",
        "\u6e7f\u70ed\u8001\u5316\u540e": "humidity_aging",
        "Immediate": "immediate",
        "Initial state": "initial",
        "Normal state": "normal",
        "At high temperature": "high_temp",
        "Heat aging": "heat_aging",
        "Humidity aging": "humidity_aging",
    }
    return mapping.get(normalized, "")


def _derive_specific_peel_meta(condition):
    if not isinstance(condition, dict):
        return None
    substrate = _clean_text(condition.get("substrate"))
    state = _clean_text(condition.get("state"))
    suffix = _state_suffix(state)
    block = _clean_text(condition.get("block"))
    lowered = substrate.lower()
    if not suffix:
        return None
    if substrate == "\u0050\u0050\u677f" or "polypropylene" in lowered:
        return {
            "param_key": f"peel_180_pp_{suffix}",
            "param_name": f"\u0050\u0050\u677f-{state}-180\u5ea6\u5265\u79bb\u529b",
        }
    if substrate == "\u9876\u68da\u0041\uff08\u65e0\u7eba\u5e03\u8868\u9762\uff09" or "headliner a" in lowered:
        if block:
            return {
                "review_only": True,
                "review_note": f"\u9876\u68da\u0041\uff08\u65e0\u7eba\u5e03\u8868\u9762\uff09\u5b58\u5728\u91cd\u590d\u7ed3\u679c\u533a\u5757\uff1a{state}\uff08{block}\uff09",
            }
        return {
            "param_key": f"peel_180_headliner_a_{suffix}",
            "param_name": f"\u9876\u68da\u0041\uff08\u65e0\u7eba\u5e03\u8868\u9762\uff09-{state}-180\u5ea6\u5265\u79bb\u529b",
        }
    return None


def _derive_specific_peel_meta_from_row(row):
    if not isinstance(row, dict):
        return None
    condition = row.get("condition") if isinstance(row.get("condition"), dict) else {}
    derived = _derive_specific_peel_meta(condition)
    if derived:
        return derived
    source_label = _clean_text(row.get("source_label"))
    lowered = source_label.lower()
    for prefix, key_prefix, zh_label in (
        ("PP\u677f - ", "peel_180_pp", "\u0050\u0050\u677f"),
        ("Polypropylene - ", "peel_180_pp", "\u0050\u0050\u677f"),
        ("Headliner A - ", "peel_180_headliner_a", "\u9876\u68da\u0041\uff08\u65e0\u7eba\u5e03\u8868\u9762\uff09"),
        ("\u9876\u68da\u0041 - ", "peel_180_headliner_a", "\u9876\u68da\u0041\uff08\u65e0\u7eba\u5e03\u8868\u9762\uff09"),
    ):
        if source_label.startswith(prefix):
            state = source_label.replace(prefix, "", 1)
            suffix = _state_suffix(state)
            if not suffix:
                return None
            if "second block" in lowered or "\u7b2c\u4e8c" in source_label:
                return {
                    "review_only": True,
                    "review_note": f"{zh_label}\u5b58\u5728\u91cd\u590d\u7ed3\u679c\u533a\u5757\uff1a{state}",
                }
            return {
                "param_key": f"{key_prefix}_{suffix}",
                "param_name": f"{zh_label}-{state}-180\u5ea6\u5265\u79bb\u529b",
            }
    return None


def _post_process_draft(task, payload, context):
    if not isinstance(payload, dict):
        return payload
    param_meta_map = _build_param_meta_map(context)

    for row in payload.get("items") or []:
        if not isinstance(row, dict):
            continue
        for key in ("color_name", "adhesive_type_name", "base_material_name"):
            row[key] = _map_known_value(row.get(key))
        category_name = _clean_text(row.get("category_name"))
        if not category_name:
            inferred = _infer_category_name(row)
            if inferred:
                row["category_name"] = inferred
                review_note = _clean_text(row.get("review_note"))
                row["review_note"] = (f"{review_note} " if review_note else "") + f"Category inferred as {inferred}."

    for row in payload.get("params") or []:
        if not isinstance(row, dict):
            continue
        key = _clean_text(row.get("param_key"))
        meta = param_meta_map.get(key) or {}
        if meta:
            row["name"] = row.get("name") or meta.get("canonical_name_zh") or meta.get("name")

    items = payload.get("items") or [{}]
    review_target = items[0] if items else {}
    for row in payload.get("spec_values") or []:
        if not isinstance(row, dict):
            continue
        row["condition"] = _translate_condition(row.get("condition"))
        if row.get("param_key") == "structure":
            row["value"] = _translate_structure_value(row.get("value"))
        elif row.get("param_key") == "shelf_life_storage":
            row["value"] = _translate_shelf_life_value(row.get("value"))
        elif row.get("param_key") == "liner_material":
            row["value"] = _map_known_value(row.get("value"))

        if row.get("param_key") == "peel_strength_180" and isinstance(row.get("condition"), dict):
            condition = row["condition"]
            substrate = _clean_text(condition.get("substrate"))
            state = _clean_text(condition.get("state"))
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
                derived = _derive_specific_peel_meta_from_row(row)
                if derived and derived.get("review_only"):
                    review_note = _clean_text(review_target.get("review_note"))
                    review_target["review_note"] = (f"{review_note} " if review_note else "") + derived["review_note"]
                elif derived:
                    row["param_key"] = derived["param_key"]
                    row["param_name"] = derived["param_name"]
                    _upsert_param_definition(payload, param_meta_map, derived["param_key"], derived["param_name"])

        row["source_label"] = (
            _clean_text(row.get("source_label"))
            .replace("Painted Panel", "\u6d82\u88c5\u677f")
            .replace("Polypropylene", "\u0050\u0050\u677f")
            .replace("Headliner A", "\u9876\u68da\u0041")
            .replace("Immediate", "\u5373\u65f6\u72b6\u6001")
            .replace("Initial state", "\u521d\u59cb\u72b6\u6001")
            .replace("Normal state", "\u5e38\u6e29\u72b6\u6001")
            .replace("At high temperature", "\u9ad8\u6e29\u72b6\u6001")
            .replace("Heat aging", "\u70ed\u8001\u5316\u540e")
            .replace("Humidity aging", "\u6e7f\u70ed\u8001\u5316\u540e")
        )

    _post_process_unmatched(payload, context)
    _promote_candidate_unmatched(payload, param_meta_map)
    _append_category_param_rows(payload, param_meta_map)
    return payload


class OdooWorkerClient:
    def __init__(self, base_url, token, db_name="odoo"):
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.db_name = db_name
        self.session = requests.Session()

    @property
    def _headers(self):
        return {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }

    def post_json(self, path, payload):
        full_payload = {"db": self.db_name, "worker_token": self.token}
        full_payload.update(payload or {})
        response = self.session.post(
            self.base_url + path,
            headers=self._headers,
            data=json.dumps(full_payload, ensure_ascii=False).encode("utf-8"),
            timeout=120,
        )
        response.raise_for_status()
        return response.json()

    def get_binary(self, url):
        separator = "&" if "?" in url else "?"
        response = self.session.get(
            f"{url}{separator}worker_token={self.token}",
            headers={"Authorization": f"Bearer {self.token}"},
            timeout=240,
        )
        response.raise_for_status()
        return response.content


def run_once(base_url, worker_token, limit=1, db_name="odoo", source_id=None):
    client = OdooWorkerClient(base_url, worker_token, db_name=db_name)
    settings = _load_openclaw_settings()
    pending_payload = {"limit": limit, "include_draft": True}
    if source_id:
        pending_payload["source_document_id"] = int(source_id)
    pending = client.post_json("/api/material/extract/pending_tasks", pending_payload)
    tasks = pending.get("tasks") or []
    if not tasks:
        print("No pending tasks")
        return 0

    processed = 0
    prefer_single_pass = os.environ.get("OPENCLAW_SINGLE_PASS", "1").strip().lower() not in ("0", "false", "no")
    fast_mode = os.environ.get("OPENCLAW_FAST_MODE", "1").strip().lower() not in ("0", "false", "no")
    for task in tasks:
        source_id = task["source_document_id"]
        run_id = f"run-{source_id}"
        try:
            client.post_json(
                "/api/material/extract/mark_processing",
                {"source_document_id": source_id, "worker_id": "openclaw-worker", "run_id": run_id},
            )
            raw_text = _clean_text(task.get("raw_text"))
            attachments = []
            existing_vision_payload = _coerce_json_object(task.get("existing_vision_payload"))
            if task.get("attachment_download_url"):
                binary = client.get_binary(task["attachment_download_url"])
                name = task.get("primary_attachment_name") or "source.pdf"
                mime = task.get("primary_attachment_mimetype") or ""
                if mime == "application/pdf" or name.lower().endswith(".pdf"):
                    if fast_mode:
                        raw_text, attachments = _extract_pdf_text_and_images(
                            binary, name, max_text_pages=3, max_image_pages=0
                        )
                    else:
                        raw_text, attachments = _extract_pdf_text_and_images(binary, name)
                elif not raw_text:
                    raw_text = ""

            runtime_context = _normalize_context(task)
            with OpenClawAdapter(
                gateway_url=settings["gateway_url"],
                token=settings["token"],
                timeout=240,
            ) as adapter:
                mode = "dual_pass"
                vision_payload = existing_vision_payload
                if prefer_single_pass:
                    try:
                        draft_payload = _build_single_pass_payload(
                            adapter, settings, task, raw_text, attachments, runtime_context, fast_mode=fast_mode
                        )
                        mode = "single_pass_fast" if fast_mode else "single_pass"
                    except Exception:
                        if attachments:
                            vision_payload = _build_vision_payload(
                                adapter, settings, task, raw_text, attachments, runtime_context
                            )
                        draft_payload = _build_struct_payload(
                            adapter, settings, task, raw_text, vision_payload, runtime_context
                        )
                else:
                    if attachments:
                        vision_payload = _build_vision_payload(
                            adapter, settings, task, raw_text, attachments, runtime_context
                        )
                    draft_payload = _build_struct_payload(
                        adapter, settings, task, raw_text, vision_payload, runtime_context
                    )
            draft_payload = _post_process_draft(task, draft_payload, runtime_context)

            result_message = (
                f"OpenClaw worker parsed ({mode}) with skill context bundle. "
                f"skills={','.join(runtime_context.get('skills_loaded') or []) or 'none'}; "
                f"raw_len={len(raw_text or '')}; image_pages={len(attachments or [])}"
            )
            client.post_json(
                "/api/material/extract/mark_parsed",
                {
                    "source_document_id": source_id,
                    "vision_payload": json.dumps(vision_payload, ensure_ascii=False, indent=2),
                    "draft_payload": json.dumps(draft_payload, ensure_ascii=False, indent=2),
                    "unmatched_payload": json.dumps(draft_payload.get("unmatched") or [], ensure_ascii=False, indent=2),
                    "parse_version": f"worker:openclaw({settings['model']})+{mode}+skill-v1+norm-v1",
                    "context_used": json.dumps(runtime_context, ensure_ascii=False, indent=2),
                    "result_message": result_message,
                    "line_count": len(draft_payload.get("spec_values") or []),
                },
            )
            client.post_json("/api/material/material/submit_review", {"source_document_id": source_id})
            print(f"Parsed source_document_id={source_id}")
            processed += 1
        except Exception as exc:
            debug_payload = {"task": task}
            try:
                client.post_json(
                    "/api/material/extract/mark_failed",
                    {
                        "source_document_id": source_id,
                        "error_code": exc.__class__.__name__,
                        "error_message": str(exc),
                        "debug_payload": json.dumps(debug_payload, ensure_ascii=False, indent=2),
                    },
                )
            except Exception:
                pass
            print(f"Failed source_document_id={source_id}: {exc}")
    return processed


def main():
    parser = argparse.ArgumentParser(description="OpenClaw TDS worker")
    parser.add_argument("--base-url", default=os.environ.get("ODOO_BASE_URL", "http://localhost:8070"))
    parser.add_argument("--worker-token", default=os.environ.get("DIECUT_TDS_WORKER_TOKEN") or os.environ.get("OPENCLAW_GATEWAY_TOKEN"))
    parser.add_argument("--db", default=os.environ.get("ODOO_DB", "odoo"))
    parser.add_argument("--limit", type=int, default=1)
    parser.add_argument("--source-id", type=int, default=0)
    args = parser.parse_args()
    if not args.worker_token:
        raise SystemExit("Missing worker token. Set DIECUT_TDS_WORKER_TOKEN or OPENCLAW_GATEWAY_TOKEN.")
    run_once(args.base_url, args.worker_token, limit=args.limit, db_name=args.db, source_id=args.source_id or None)


if __name__ == "__main__":
    main()
