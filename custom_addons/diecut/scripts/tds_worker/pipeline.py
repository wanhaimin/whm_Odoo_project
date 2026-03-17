# -*- coding: utf-8 -*-
from __future__ import annotations

import importlib.util
import json
import re
import sys
from csv import DictWriter
from datetime import datetime
from pathlib import Path

from .cache import (
    build_extract_cache_key,
    build_understanding_cache_key,
    build_single_cache_key,
    build_struct_cache_key,
    build_vision_cache_key,
    load_json_cache,
    save_json_cache,
    sha256_bytes,
    sha256_json,
    sha256_text,
)
from .client import BaseOdooClient, create_odoo_client
from .diagnostics.timers import StageTimer
from .extract.pdf_extract import extract_pdf_text_and_images
from .models import ExtractedDocument, PipelineResult
from .normalize.draft_postprocess import postprocess_draft
from .prompt.context_builder import build_context_signature
from .review import summarize_five_tables
from .prompt.single_pass import build_single_pass_prompt
from .prompt.struct_pass import build_struct_prompt
from .prompt.understand_pass import build_understanding_prompt
from .prompt.vision_pass import build_vision_prompt
from .settings import WorkerSettings
from .understanding_schema import DocumentUnderstandingPayload, normalize_understanding_payload


PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

ATTACHMENT_CACHE_WARN_THRESHOLD = 8 * 1024 * 1024
REPORT_DIR = PROJECT_ROOT / "diecut" / "scripts" / "tds_import_drafts"
UNMATCHED_REVIEW_FILE = REPORT_DIR / "tds_unmatched_review.csv"
IMPORT_REPORT_FILE = REPORT_DIR / "tds_import_report.csv"


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


OpenClawAdapter = _load_openclaw_adapter()
infer_brand_skill_name, load_skill_bundle = _load_skill_context()


def strip_json_fence(text):
    value = (text or "").strip()
    if value.startswith("```"):
        value = re.sub(r"^```(?:json)?", "", value).strip()
        value = re.sub(r"```$", "", value).strip()
    return value


def parse_json_loose(text):
    value = strip_json_fence(text)
    try:
        return json.loads(value)
    except Exception:
        pass
    match = re.search(r"(\{[\s\S]*\}|\[[\s\S]*\])", value)
    if match:
        return json.loads(match.group(1))
    raise ValueError("Model did not return valid JSON.")


def coerce_json_object(value):
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


def validate_draft_payload(payload):
    try:
        from .models_schema import TdsDraftPayload

        return TdsDraftPayload.model_validate(payload or {}).model_dump(mode="python")
    except Exception:
        value = payload if isinstance(payload, dict) else {}
        # Fallback when pydantic is unavailable in container runtime.
        normalized = {}
        for bucket in ("series", "items", "params", "category_params", "spec_values", "unmatched"):
            normalized[bucket] = value.get(bucket) if isinstance(value.get(bucket), list) else []
        return normalized


def get_draft_schema_errors(payload) -> list[str]:
    try:
        from pydantic import ValidationError
        from .models_schema import TdsDraftPayload

        TdsDraftPayload.model_validate(payload or {})
        return []
    except ImportError:
        return ["pydantic_not_available"]
    except ValidationError as exc:
        issues = []
        for error in exc.errors():
            loc = ".".join(str(item) for item in (error.get("loc") or []))
            msg = clean_text(error.get("msg"))
            if loc:
                issues.append(f"{loc}: {msg}")
            else:
                issues.append(msg or "validation_error")
        return issues[:20]
    except Exception as exc:
        return [f"schema_check_exception: {exc}"]


def is_draft_schema_valid(payload: dict) -> bool:
    return len(get_draft_schema_errors(payload)) == 0


def validate_understanding_payload(payload):
    try:
        return DocumentUnderstandingPayload.model_validate(payload or {}).model_dump(mode="python")
    except Exception:
        return normalize_understanding_payload(payload if isinstance(payload, dict) else {})


def clean_text(value):
    return str(value or "").strip()


def _coerce_text(value) -> str:
    if isinstance(value, str):
        return clean_text(value)
    if isinstance(value, list):
        lines = [clean_text(item) for item in value if clean_text(item)]
        return "\n".join(lines).strip()
    if isinstance(value, dict):
        text = clean_text(value.get("text")) if hasattr(value, "get") else ""
        if text:
            return text
    return clean_text(value)


MAIN_ITEM_CONCEPT_ROUTE = {
    "thickness": "thickness",
    "thickness_std": "thickness_std",
    "adhesive_thickness": "adhesive_thickness",
    "color": "color_name",
    "color_name": "color_name",
    "core_color": "color_name",
    "adhesive_type": "adhesive_type_name",
    "adhesive_system": "adhesive_type_name",
    "adhesive": "adhesive_type_name",
    "base_material": "base_material_name",
    "base_material_type": "base_material_name",
    "core": "base_material_name",
    "liner_material": "liner_material_name",
    "liner": "liner_material_name",
}

CONTENT_ROUTE_TO_SERIES = {
    "product_description": "product_description",
    "product_features": "product_features",
    "main_applications": "main_applications",
    "special_applications": "special_applications",
    "processing_note": "special_applications",
    "construction_note": "special_applications",
    "performance_note": "special_applications",
    "storage_note": "special_applications",
}

CONTENT_ROUTE_TO_ITEM = {
    "item_features": "item_features",
    "equivalent_notes": "equivalent_notes",
}

EQUIVALENT_NEEDLES = ("equivalent", "replacement", "substitute", "compatible with")
APPLICATION_NEEDLES = ("application", "applications", "recommended use", "end use")
FEATURE_NEEDLES = ("feature", "features", "benefit", "advantages")
DESCRIPTION_NEEDLES = ("description", "overview", "general description")
PROCESS_NEEDLES = ("processing", "tabbing", "die cutting", "rotary", "flat bed", "laser")
STORAGE_NEEDLES = ("shelf life", "storage")
LEGAL_NEEDLES = ("warranty", "liability", "disclaimer", "regulatory")
METHOD_NEEDLES = ("test method", "method", "conditions/test parameter")


def _slugify_token(value: str) -> str:
    token = re.sub(r"[^a-z0-9]+", "_", clean_text(value).lower()).strip("_")
    token = re.sub(r"_+", "_", token)
    return token or "unknown"


def _join_text(prev: str, new: str) -> str:
    left = clean_text(prev)
    right = clean_text(new)
    if not right:
        return left
    if not left:
        return right
    if right in left:
        return left
    return f"{left}\n{right}"


def _contains_any(text: str, needles: tuple[str, ...]) -> bool:
    haystack = clean_text(text).lower()
    return any(needle in haystack for needle in needles)


def _build_performance_metric_base(concept: str, label: str) -> str:
    concept_key = clean_text(concept).lower()
    label_key = clean_text(label).lower()
    if "peel" in concept_key or "peel" in label_key:
        return "peel_180"
    if "shear" in concept_key or "shear" in label_key:
        return "shear"
    if "tack" in concept_key or "tack" in label_key:
        return "initial_tack"
    return _slugify_token(concept_key or label_key)


def _build_conditional_param_key(concept: str, label: str, condition: dict | None) -> str:
    condition = condition if isinstance(condition, dict) else {}
    substrate = clean_text(condition.get("substrate"))
    state = clean_text(condition.get("state"))
    if not substrate and not state:
        return clean_text(concept).lower() or _slugify_token(label)
    metric_base = _build_performance_metric_base(concept, label)
    substrate_key = _slugify_token(substrate) if substrate else "generic"
    state_key = _slugify_token(state) if state else "generic"
    return f"{metric_base}_{substrate_key}_{state_key}"


def _is_item_specific_text(text: str, item_code: str, known_codes: set[str]) -> bool:
    value = clean_text(text)
    code = clean_text(item_code).upper()
    if code and code in value.upper():
        return True
    upper = value.upper()
    return any(candidate in upper for candidate in known_codes if candidate)


def _classify_unmatched_type(row_type: str, source_label: str, content: str) -> str:
    row_key = clean_text(row_type).lower()
    label = clean_text(source_label).lower()
    text = clean_text(content).lower()
    merged = " ".join([row_key, label, text])
    if _contains_any(merged, LEGAL_NEEDLES):
        return "legal_disclaimer"
    if _contains_any(merged, METHOD_NEEDLES):
        return "method_definition"
    if _contains_any(merged, PROCESS_NEEDLES):
        return "processing_guidance"
    if _contains_any(merged, ("accessory", "tabbing tape")):
        return "accessory_info"
    if _contains_any(merged, ("ocr", "uncertain", "illegible")):
        return "ocr_uncertain"
    if "missing" in merged or "dictionary" in merged or "candidate_param" in merged:
        return "missing_param_key"
    return "ambiguous_mapping"


def _upsert_param_row(params_by_key: dict, param_key: str, display_name: str, source_label: str):
    key = clean_text(param_key)
    if not key:
        return
    if key in params_by_key:
        return
    params_by_key[key] = {
        "param_key": key,
        "name": clean_text(display_name) or key,
        "source_label": source_label,
    }


def _normalize_scope(scope: str) -> str:
    value = clean_text(scope).lower()
    if value in {"series", "item", "mixed"}:
        return value
    return "unknown"


def _normalize_content_type(content_type: str) -> tuple[str, str]:
    value = clean_text(content_type).lower()
    if value.startswith("series."):
        return value.split(".", 1)[1], "series"
    if value.startswith("items.") or value.startswith("item."):
        return value.split(".", 1)[1], "item"
    return value, "unknown"


def _coerce_scope_from_flag(row: dict) -> str:
    if row.get("series_scope") is True:
        return "series"
    if row.get("series_scope") is False:
        return "item"
    return _normalize_scope(row.get("scope"))


def _infer_candidate_items_from_tables(understanding_payload: dict) -> list[dict]:
    inferred = []
    seen = set()
    for table in understanding_payload.get("tables") or []:
        if not isinstance(table, dict):
            continue
        table_type = clean_text(table.get("type") or table.get("table_type")).lower()
        if table_type not in {"item_matrix", "property_table"}:
            continue
        for row in table.get("rows") or []:
            if not isinstance(row, dict):
                continue
            code = clean_text(row.get("Product") or row.get("item_code") or row.get("型号"))
            if not code or code in seen:
                continue
            seen.add(code)
            inferred.append(
                {
                    "item_code": code,
                    "item_name": code,
                    "series_name": clean_text(
                        ((understanding_payload.get("document_meta") or {}).get("series_name"))
                    )
                    or None,
                    "page": table.get("page"),
                    "source": "table_row",
                    "source_text": clean_text(table.get("title")),
                    "confidence": table.get("confidence"),
                }
            )
    return inferred


def _infer_candidate_content_from_sections(understanding_payload: dict) -> list[dict]:
    inferred = []
    for section in understanding_payload.get("sections") or []:
        if not isinstance(section, dict):
            continue
        section_type = clean_text(section.get("type") or section.get("section_type")).lower()
        section_title = clean_text(section.get("title") or section.get("section_title"))
        scope = _coerce_scope_from_flag(section)
        text = clean_text(section.get("content") or section.get("text"))
        bullets = section.get("bullets") if isinstance(section.get("bullets"), list) else []
        layers = section.get("layers") if isinstance(section.get("layers"), list) else []
        if bullets:
            text = "\n".join(clean_text(item) for item in bullets if clean_text(item))
        elif layers:
            text = " / ".join(clean_text((layer or {}).get("name")) for layer in layers if isinstance(layer, dict))
        if not text:
            continue
        content_type = None
        merged = f"{section_title} {text}".lower()
        if section_type in {"product_description", "description", "general_description"} or _contains_any(merged, DESCRIPTION_NEEDLES):
            content_type = "product_description"
        elif section_type in {"features", "key_features"} or _contains_any(merged, FEATURE_NEEDLES):
            content_type = "product_features"
        elif section_type in {"applications", "application", "main_applications"} or _contains_any(merged, APPLICATION_NEEDLES):
            content_type = "main_applications"
        elif section_type in {"processing", "tabbing"} or _contains_any(merged, PROCESS_NEEDLES):
            content_type = "processing_note"
        elif section_type in {"construction", "structure"}:
            content_type = "construction_note"
        elif section_type in {"storage", "shelf_life"} or _contains_any(merged, STORAGE_NEEDLES):
            content_type = "storage_note"
        elif section_type in {"result_table", "performance_notes", "performance"}:
            content_type = "performance_note"
        elif _contains_any(merged, EQUIVALENT_NEEDLES):
            content_type = "equivalent_notes"
        if not content_type:
            continue
        inferred.append(
            {
                "content_id": f"sec-{clean_text(section.get('section_id') or section_title or len(inferred) + 1)}",
                "page": section.get("page"),
                "section_id": clean_text(section.get("section_id")) or None,
                "content_type": content_type,
                "scope": scope,
                "item_code": clean_text(section.get("item_code")) or None,
                "text": text,
                "source_text": text if len(text) <= 400 else text[:400],
                "mapping_reason": f"Inferred from section '{section_title or section_type}'.",
                "confidence": section.get("confidence"),
            }
        )
    return inferred


def _infer_candidate_facts_from_sections(understanding_payload: dict) -> list[dict]:
    inferred = []
    for section in understanding_payload.get("sections") or []:
        if not isinstance(section, dict):
            continue
        section_type = clean_text(section.get("type") or section.get("section_type")).lower()
        scope = _coerce_scope_from_flag(section)
        if section_type in {"structure", "construction"}:
            layers = section.get("layers") if isinstance(section.get("layers"), list) else []
            value = " / ".join(
                clean_text((layer or {}).get("name")) for layer in layers if isinstance(layer, dict) and clean_text((layer or {}).get("name"))
            )
            if value:
                inferred.append(
                    {
                        "fact_id": f"sec-structure-{len(inferred) + 1}",
                        "page": section.get("page"),
                        "section_id": clean_text(section.get("section_id")) or None,
                        "table_id": None,
                        "scope": scope,
                        "item_code": None,
                        "series_name": clean_text(((understanding_payload.get("document_meta") or {}).get("series_name"))) or None,
                        "label": "Structure",
                        "normalized_concept": "structure",
                        "value": value,
                        "raw_value": value,
                        "unit": None,
                        "source_text": value,
                        "mapping_reason": "Inferred from Product Construction section layers.",
                        "confidence": section.get("confidence"),
                    }
                )
        if section_type in {"processing", "tabbing"}:
            value = clean_text(section.get("content") or section.get("text"))
            if value:
                inferred.append(
                    {
                        "fact_id": f"sec-processing-{len(inferred) + 1}",
                        "page": section.get("page"),
                        "section_id": clean_text(section.get("section_id")) or None,
                        "table_id": None,
                        "scope": scope,
                        "item_code": None,
                        "series_name": clean_text(((understanding_payload.get("document_meta") or {}).get("series_name"))) or None,
                        "label": "Processing Compatibility",
                        "normalized_concept": "processing_compatibility",
                        "value": value,
                        "raw_value": value,
                        "unit": None,
                        "source_text": value,
                        "mapping_reason": "Inferred from processing/tabbing narrative section.",
                        "confidence": section.get("confidence"),
                    }
                )
        if section_type in {"storage", "shelf_life"}:
            value = clean_text(section.get("content") or section.get("text"))
            if value:
                inferred.append(
                    {
                        "fact_id": f"sec-storage-{len(inferred) + 1}",
                        "page": section.get("page"),
                        "section_id": clean_text(section.get("section_id")) or None,
                        "table_id": None,
                        "scope": scope,
                        "item_code": None,
                        "series_name": clean_text(((understanding_payload.get("document_meta") or {}).get("series_name"))) or None,
                        "label": "Shelf Life and Storage",
                        "normalized_concept": "shelf_life_storage",
                        "value": value,
                        "raw_value": value,
                        "unit": None,
                        "source_text": value,
                        "mapping_reason": "Inferred from storage/shelf-life narrative section.",
                        "confidence": section.get("confidence"),
                    }
                )
    return inferred


def _infer_candidate_facts_from_tables(understanding_payload: dict) -> list[dict]:
    inferred = []
    for table in understanding_payload.get("tables") or []:
        if not isinstance(table, dict):
            continue
        table_type = clean_text(table.get("type") or table.get("table_type")).lower()
        table_title = clean_text(table.get("title"))
        page = table.get("page")
        rows = table.get("rows") if isinstance(table.get("rows"), list) else []
        if table_type in {"item_matrix", "property_table"}:
            for row in rows:
                if not isinstance(row, dict):
                    continue
                item_code = clean_text(row.get("Product") or row.get("item_code") or row.get("型号"))
                if not item_code:
                    continue
                cell_maps = [
                    ("Thickness", "thickness"),
                    ("Core Color", "color"),
                    ("Adhesive", "adhesive_type"),
                    ("Core", "base_material"),
                    ("Base Material", "base_material"),
                    ("Liner", "liner_material"),
                ]
                for source_label, concept in cell_maps:
                    value_obj = row.get(source_label)
                    unit = None
                    value = value_obj
                    if isinstance(value_obj, dict):
                        value = value_obj.get("value")
                        unit = clean_text(value_obj.get("unit")) or None
                    if value in (None, "", []):
                        continue
                    inferred.append(
                        {
                            "fact_id": f"tbl-{concept}-{item_code}-{len(inferred) + 1}",
                            "page": page,
                            "section_id": None,
                            "table_id": clean_text(table.get("table_id") or table_title) or None,
                            "scope": "item",
                            "item_code": item_code,
                            "series_name": clean_text(((understanding_payload.get("document_meta") or {}).get("series_name"))) or None,
                            "label": source_label,
                            "normalized_concept": concept,
                            "value": value,
                            "raw_value": clean_text(value_obj) if not isinstance(value_obj, dict) else clean_text(value_obj.get("value")),
                            "unit": unit,
                            "source_text": table_title or source_label,
                            "mapping_reason": f"Inferred from table '{table_title}' row Product={item_code}, column {source_label}.",
                            "confidence": table.get("confidence"),
                        }
                    )
        elif table_type in {"performance_table", "result_table"}:
            for row in rows:
                if not isinstance(row, dict):
                    continue
                substrate = clean_text(row.get("Substrate"))
                condition = clean_text(row.get("Conditions/Test Parameter") or row.get("Condition") or row.get("Test Parameter"))
                for key, value in row.items():
                    key_text = clean_text(key)
                    if not re.match(r"^GT\d+", key_text, flags=re.I):
                        continue
                    if value in (None, "", []):
                        continue
                    inferred.append(
                        {
                            "fact_id": f"tbl-peel-{key_text}-{len(inferred) + 1}",
                            "page": page,
                            "section_id": None,
                            "table_id": clean_text(table.get("table_id") or table_title) or None,
                            "scope": "item",
                            "item_code": key_text.upper(),
                            "series_name": clean_text(((understanding_payload.get("document_meta") or {}).get("series_name"))) or None,
                            "label": f"180 Peel {substrate} {condition}".strip(),
                            "normalized_concept": "peel_strength_180",
                            "value": value,
                            "raw_value": clean_text(value),
                            "unit": clean_text(((table.get("meta") or {}).get("unit"))) or None,
                            "source_text": table_title or "performance_table",
                            "mapping_reason": f"Inferred from performance table '{table_title}' for {key_text} under {substrate}/{condition}.",
                            "confidence": table.get("confidence"),
                            "condition": {
                                "substrate": substrate or None,
                                "state": condition or None,
                            },
                        }
                    )
    return inferred


def enrich_understanding_payload(understanding_payload: dict) -> dict:
    payload = normalize_understanding_payload(understanding_payload if isinstance(understanding_payload, dict) else {})

    candidate_items = payload.get("candidate_items") if isinstance(payload.get("candidate_items"), list) else []
    if not candidate_items:
        candidate_items = _infer_candidate_items_from_tables(payload)

    candidate_content = payload.get("candidate_content") if isinstance(payload.get("candidate_content"), list) else []
    inferred_content = _infer_candidate_content_from_sections(payload)
    if inferred_content:
        candidate_content = [*candidate_content, *inferred_content]

    candidate_facts = payload.get("candidate_facts") if isinstance(payload.get("candidate_facts"), list) else []
    inferred_facts = [
        *_infer_candidate_facts_from_sections(payload),
        *_infer_candidate_facts_from_tables(payload),
    ]
    if inferred_facts:
        candidate_facts = [*candidate_facts, *inferred_facts]

    deduped_content = []
    seen_content = set()
    for row in candidate_content:
        if not isinstance(row, dict):
            continue
        signature = (
            clean_text(row.get("content_type")).lower(),
            _normalize_scope(row.get("scope")),
            clean_text(row.get("item_code")).upper(),
            clean_text(row.get("text")),
        )
        if signature in seen_content:
            continue
        seen_content.add(signature)
        deduped_content.append(row)

    deduped_facts = []
    seen_facts = set()
    for row in candidate_facts:
        if not isinstance(row, dict):
            continue
        condition = row.get("condition") if isinstance(row.get("condition"), dict) else {}
        signature = (
            clean_text(row.get("normalized_concept")).lower(),
            _normalize_scope(row.get("scope")),
            clean_text(row.get("item_code")).upper(),
            clean_text(row.get("label")).lower(),
            clean_text(row.get("value")),
            clean_text(row.get("unit")).lower(),
            clean_text(condition.get("substrate")).lower(),
            clean_text(condition.get("state")).lower(),
        )
        if signature in seen_facts:
            continue
        seen_facts.add(signature)
        deduped_facts.append(row)

    payload["candidate_items"] = candidate_items
    payload["candidate_content"] = deduped_content
    payload["candidate_facts"] = deduped_facts
    return payload


def map_understanding_to_draft(
    understanding_payload: dict,
    validate_output: bool = True,
    return_stats: bool = False,
) -> dict | tuple[dict, dict]:
    meta = understanding_payload.get("document_meta") if isinstance(understanding_payload.get("document_meta"), dict) else {}
    draft = {
        "series": [],
        "items": [],
        "params": [],
        "category_params": [],
        "spec_values": [],
        "unmatched": [],
    }
    route_stats = {
        "content_to_series": 0,
        "content_to_items": 0,
        "content_dropped": 0,
        "facts_to_items": 0,
        "facts_to_spec": 0,
        "facts_dropped": 0,
        "methods_to_params": 0,
        "unmatched_by_type": {},
    }

    series_row = {
        "series_name": clean_text(meta.get("series_name")),
        "brand_name": clean_text(meta.get("brand_name")),
        "category_name": "",
        "source_label": "document_meta",
    }

    items_by_code: dict[str, dict] = {}
    for item in understanding_payload.get("candidate_items") or []:
        if not isinstance(item, dict):
            continue
        code = clean_text(item.get("item_code") or item.get("code"))
        if not code:
            continue
        item_row = items_by_code.setdefault(
            code,
            {
                "code": code,
                "name": clean_text(item.get("item_name") or item.get("name")) or code,
                "series_name": clean_text(item.get("series_name")) or series_row.get("series_name"),
                "brand_name": clean_text(item.get("brand_name")) or series_row.get("brand_name") or clean_text(meta.get("brand_name")),
                "source_page": item.get("page") or item.get("source_page"),
                "source_text": clean_text(item.get("source_text")),
                "source_label": clean_text(item.get("source") or item.get("source_label")) or "candidate_items",
            },
        )
        searchable_fields = item.get("main_searchable_fields") if isinstance(item.get("main_searchable_fields"), dict) else {}
        for concept, field in MAIN_ITEM_CONCEPT_ROUTE.items():
            source_obj = item if concept in item else searchable_fields
            if concept not in source_obj:
                continue
            value_obj = source_obj.get(concept)
            if isinstance(value_obj, dict):
                raw_value = value_obj.get("value")
                unit = clean_text(value_obj.get("unit"))
                item_row[field] = f"{raw_value} {unit}".strip() if raw_value not in (None, "") else ""
            elif value_obj not in (None, "", []):
                item_row[field] = str(value_obj)
    known_codes = {code.upper() for code in items_by_code.keys()}
    if not series_row.get("series_name") and items_by_code:
        first_item = next(iter(items_by_code.values()))
        series_row["series_name"] = clean_text(first_item.get("series_name"))
    if not series_row.get("brand_name") and items_by_code:
        first_item = next(iter(items_by_code.values()))
        series_row["brand_name"] = clean_text(first_item.get("brand_name"))

    for content in understanding_payload.get("candidate_content") or []:
        if not isinstance(content, dict):
            continue
        raw_content_type = clean_text(content.get("content_type"))
        content_type, inferred_scope = _normalize_content_type(raw_content_type)
        text = _coerce_text(content.get("text") or content.get("value") or content.get("content"))
        if not text:
            continue
        scope = _normalize_scope(content.get("scope"))
        if scope == "unknown":
            scope = inferred_scope
        item_code = clean_text(content.get("item_code"))
        content_kind = content_type or "unknown"
        # equivalent notes must be explicit replacement semantics
        if content_kind == "equivalent_notes" and not _contains_any(text, EQUIVALENT_NEEDLES):
            route_stats["content_dropped"] += 1
            continue
        if content_type in CONTENT_ROUTE_TO_SERIES and scope in {"series", "mixed", "unknown"}:
            field_name = CONTENT_ROUTE_TO_SERIES[content_type]
            series_row[field_name] = _join_text(series_row.get(field_name), text)
            route_stats["content_to_series"] += 1
            continue
        if content_type in CONTENT_ROUTE_TO_ITEM and (scope in {"item", "mixed"} or item_code):
            if content_type == "item_features" and not _is_item_specific_text(text, item_code, known_codes):
                series_row["special_applications"] = _join_text(series_row.get("special_applications"), text)
                route_stats["content_to_series"] += 1
                continue
            if item_code and item_code not in items_by_code:
                items_by_code[item_code] = {"code": item_code, "name": item_code, "series_name": series_row.get("series_name")}
            target_code = item_code or (next(iter(items_by_code.keys())) if items_by_code else "")
            if target_code:
                target = items_by_code.setdefault(target_code, {"code": target_code, "name": target_code})
                field_name = CONTENT_ROUTE_TO_ITEM[content_type]
                target[field_name] = _join_text(target.get(field_name), text)
                route_stats["content_to_items"] += 1
                continue
        unmatched_type = _classify_unmatched_type("content_unresolved", raw_content_type, text)
        draft["unmatched"].append(
            {
                "type": unmatched_type,
                "source_label": raw_content_type or "candidate_content",
                "content": text,
                "reason": clean_text(content.get("mapping_reason")) or "No deterministic content routing target.",
                "source_page": content.get("page") or content.get("source_page"),
                "source_text": _coerce_text(content.get("source_text")),
                "confidence": content.get("confidence"),
            }
        )
        route_stats["content_dropped"] += 1
        route_stats["unmatched_by_type"][unmatched_type] = route_stats["unmatched_by_type"].get(unmatched_type, 0) + 1

    params_by_key: dict[str, dict] = {}
    fallback_brand_name = clean_text(meta.get("brand_name")) or clean_text(series_row.get("brand_name"))
    if not fallback_brand_name and items_by_code:
        fallback_brand_name = clean_text(next(iter(items_by_code.values())).get("brand_name"))
    for fact in understanding_payload.get("candidate_facts") or []:
        if not isinstance(fact, dict):
            continue
        concept = clean_text(fact.get("normalized_concept") or fact.get("param_key")).lower()
        label = clean_text(fact.get("label") or fact.get("param_name")) or concept
        value = fact.get("value")
        if value in (None, "", []):
            route_stats["facts_dropped"] += 1
            continue
        scope = _normalize_scope(fact.get("scope"))
        item_code = clean_text(fact.get("item_code") or fact.get("code"))
        condition = fact.get("condition") if isinstance(fact.get("condition"), dict) else {}
        if concept in MAIN_ITEM_CONCEPT_ROUTE and scope in {"item", "mixed"}:
            if item_code and item_code not in items_by_code:
                items_by_code[item_code] = {"code": item_code, "name": item_code, "series_name": series_row.get("series_name")}
            target_code = item_code or (next(iter(items_by_code.keys())) if items_by_code else "")
            if target_code:
                items_by_code[target_code][MAIN_ITEM_CONCEPT_ROUTE[concept]] = str(value)
                route_stats["facts_to_items"] += 1
                continue
        if concept == "processing_compatibility" and scope in {"series", "unknown", "mixed"} and not item_code:
            series_row["special_applications"] = _join_text(series_row.get("special_applications"), str(value))
            route_stats["content_to_series"] += 1
            continue

        base_key = concept or _slugify_token(clean_text(fact.get("label")))
        has_condition = bool(clean_text(condition.get("substrate")) or clean_text(condition.get("state")))
        is_performance = any(
            token in base_key for token in ("peel", "shear", "strength", "tack")
        ) or _contains_any(label, ("peel", "shear", "剥离", "剪切"))
        param_key = _build_conditional_param_key(base_key, label, condition) if (is_performance and has_condition) else base_key
        _upsert_param_row(params_by_key, param_key, label, "candidate_facts")
        if param_key in params_by_key and param_key != base_key:
            params_by_key[param_key]["source"] = params_by_key[param_key].get("source") or "auto_generated"
            params_by_key[param_key]["parse_hint"] = params_by_key[param_key].get("parse_hint") or "auto expanded from condition-aware performance fact"
        draft["spec_values"].append(
            {
                "brand_name": clean_text(fact.get("brand_name")) or fallback_brand_name or None,
                "item_code": item_code or None,
                "series_name": clean_text(fact.get("series_name")) or series_row.get("series_name") or None,
                "scope": "item" if scope == "item" else "series" if scope == "series" else None,
                "param_key": param_key,
                "param_name": label,
                "value": value,
                "raw_value": clean_text(fact.get("raw_value")),
                "unit": clean_text(fact.get("unit")) or None,
                "source_label": "candidate_facts",
                "source_page": fact.get("page") or fact.get("source_page"),
                "source_text": clean_text(fact.get("source_text")),
                "review_note": clean_text(fact.get("mapping_reason")),
                "confidence": fact.get("confidence"),
                "condition": condition or None,
            }
        )
        route_stats["facts_to_spec"] += 1

    for method in understanding_payload.get("methods") or []:
        if not isinstance(method, dict):
            continue
        concept = clean_text(method.get("related_concept")).lower()
        method_name = clean_text(method.get("method_name"))
        text = clean_text(method.get("text"))
        if not method_name and not concept:
            continue
        param_key = concept or _slugify_token(method_name)
        _upsert_param_row(params_by_key, param_key, method_name or param_key, "methods")
        params_by_key[param_key]["method_html"] = _join_text(params_by_key[param_key].get("method_html"), text or clean_text(method.get("source_text")))
        cond_lines = method.get("conditions") if isinstance(method.get("conditions"), list) else []
        if cond_lines:
            params_by_key[param_key]["parse_hint"] = _join_text(
                params_by_key[param_key].get("parse_hint"),
                "\n".join(clean_text(item) for item in cond_lines if clean_text(item)),
            )
        route_stats["methods_to_params"] += 1

    for unresolved in understanding_payload.get("unresolved") or []:
        if not isinstance(unresolved, dict):
            continue
        unresolved_type = _classify_unmatched_type(
            clean_text(unresolved.get("problem_type")) or "unresolved",
            clean_text(unresolved.get("section_id")),
            clean_text(unresolved.get("content")),
        )
        if unresolved_type == "legal_disclaimer":
            continue
        draft["unmatched"].append(
            {
                "type": unresolved_type,
                "source_label": "unresolved",
                "content": clean_text(unresolved.get("content")),
                "reason": clean_text(unresolved.get("reason")) or "LLM marked unresolved.",
                "candidate_param_key": clean_text(unresolved.get("candidate_concept")) or None,
                "source_page": unresolved.get("page"),
                "source_text": clean_text(unresolved.get("source_text")),
                "confidence": unresolved.get("confidence"),
            }
        )
        route_stats["unmatched_by_type"][unresolved_type] = route_stats["unmatched_by_type"].get(unresolved_type, 0) + 1

    has_narrative = any(
        clean_text(series_row.get(key))
        for key in ("product_description", "product_features", "main_applications", "special_applications")
    ) or any(
        isinstance(row, dict) and clean_text(row.get("content_type")).lower() in CONTENT_ROUTE_TO_SERIES
        for row in (understanding_payload.get("candidate_content") or [])
    )
    has_series_hint = bool(clean_text(series_row.get("series_name")) or any(clean_text(row.get("series_name")) for row in items_by_code.values()))
    if not clean_text(series_row.get("series_name")) and items_by_code:
        series_row["series_name"] = clean_text(next(iter(items_by_code.values())).get("series_name"))

    if (has_series_hint and has_narrative) or clean_text(series_row.get("series_name")) or clean_text(series_row.get("brand_name")):
        draft["series"].append(series_row)

    draft["items"] = list(items_by_code.values())
    draft["params"] = list(params_by_key.values())
    output = validate_draft_payload(draft) if validate_output else draft
    if return_stats:
        return output, route_stats
    return output


def summarize_understanding(payload: dict) -> dict:
    return {
        "sections": len(payload.get("sections") or []),
        "tables": len(payload.get("tables") or []),
        "candidate_items": len(payload.get("candidate_items") or []),
        "candidate_facts": len(payload.get("candidate_facts") or []),
        "candidate_content": len(payload.get("candidate_content") or []),
        "methods": len(payload.get("methods") or []),
        "unresolved": len(payload.get("unresolved") or []),
    }


def evaluate_quality_gate(
    draft_payload: dict,
    timings_ms: dict,
    baseline_ms: int,
    schema_errors: list[str] | None = None,
    route_drop_stats: dict | None = None,
) -> dict:
    required = ("series", "items", "params", "category_params", "spec_values", "unmatched")
    required_presence = all(isinstance(draft_payload.get(name), list) for name in required)
    schema_errors = schema_errors or []
    schema_valid = len(schema_errors) == 0
    current_ms = sum(int(v) for v in timings_ms.values())
    latency_increase = 0.0 if baseline_ms <= 0 else (current_ms - baseline_ms) / float(baseline_ms)
    gate = {
        "schema_valid_rate": 1.0 if schema_valid else 0.0,
        "required_buckets_presence": 1.0 if required_presence else 0.0,
        "pipeline_fail_rate": 0.0,
        "latency_increase": latency_increase,
        "schema_errors": schema_errors[:10],
        "route_drop_stats": route_drop_stats or {},
    }
    gate["passed"] = (
        gate["schema_valid_rate"] >= 0.99
        and gate["required_buckets_presence"] >= 1.0
        and gate["pipeline_fail_rate"] <= 0.02
        and gate["latency_increase"] <= 0.30
    )
    return gate


def normalize_context(task: dict):
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


def _load_draft_cache_with_legacy(namespace: str, cache_key: str):
    cached = load_json_cache(namespace, cache_key)
    if cached:
        return cached
    legacy = load_json_cache("draft", cache_key)
    if legacy:
        save_json_cache(namespace, cache_key, legacy)
    return legacy


def _estimate_attachment_b64_size(attachments: list[dict]) -> int:
    size = 0
    for item in attachments or []:
        content = item.get("content") if isinstance(item, dict) else ""
        if isinstance(content, str):
            size += len(content)
    return size


def _append_csv_row(path: Path, headers: list[str], row: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    file_exists = path.exists()
    with path.open("a", encoding="utf-8-sig", newline="") as fp:
        writer = DictWriter(fp, fieldnames=headers)
        if not file_exists:
            writer.writeheader()
        writer.writerow({key: row.get(key, "") for key in headers})


def _write_unmatched_review(task: dict, draft_payload: dict):
    rows = draft_payload.get("unmatched") or []
    if not isinstance(rows, list) or not rows:
        return 0
    headers = [
        "source_document",
        "brand",
        "category",
        "item_code",
        "unmatched_type",
        "source_page",
        "source_label",
        "content",
        "reason",
        "candidate_param_key",
        "candidate_name",
        "decision",
        "final_param_key",
        "final_target_bucket",
        "review_note",
    ]
    item_code = ""
    items = draft_payload.get("items") or []
    if isinstance(items, list) and items and isinstance(items[0], dict):
        item_code = clean_text(items[0].get("code"))
    written = 0
    for row in rows:
        if not isinstance(row, dict):
            continue
        _append_csv_row(
            UNMATCHED_REVIEW_FILE,
            headers,
            {
                "source_document": task.get("source_document_id"),
                "brand": task.get("brand"),
                "category": task.get("category"),
                "item_code": item_code,
                "unmatched_type": row.get("type") or "",
                "source_page": row.get("source_page") or "",
                "source_label": row.get("source_label") or "",
                "content": row.get("content") or row.get("excerpt") or "",
                "reason": row.get("reason") or "",
                "candidate_param_key": row.get("candidate_param_key") or "",
                "candidate_name": row.get("candidate_name") or "",
                "decision": "",
                "final_param_key": "",
                "final_target_bucket": "",
                "review_note": row.get("review_note") or "",
            },
        )
        written += 1
    return written


def _write_import_report(task: dict, result: PipelineResult, settings: WorkerSettings, unmatched_rows: int):
    headers = [
        "run_at",
        "source_document_id",
        "mode",
        "model",
        "series_count",
        "items_count",
        "params_count",
        "category_params_count",
        "spec_values_count",
        "unmatched_count",
        "unmatched_written",
        "cache_flags",
        "timings_ms",
        "warnings",
    ]
    draft = result.draft_payload or {}
    _append_csv_row(
        IMPORT_REPORT_FILE,
        headers,
        {
            "run_at": datetime.now().isoformat(timespec="seconds"),
            "source_document_id": task.get("source_document_id"),
            "mode": result.mode,
            "model": settings.model,
            "series_count": len(draft.get("series") or []),
            "items_count": len(draft.get("items") or []),
            "params_count": len(draft.get("params") or []),
            "category_params_count": len(draft.get("category_params") or []),
            "spec_values_count": len(draft.get("spec_values") or []),
            "unmatched_count": len(draft.get("unmatched") or []),
            "unmatched_written": unmatched_rows,
            "cache_flags": json.dumps(result.metrics.get("cache_flags") or {}, ensure_ascii=False),
            "timings_ms": json.dumps(result.metrics.get("timings_ms") or {}, ensure_ascii=False),
            "warnings": json.dumps(result.metrics.get("warnings") or [], ensure_ascii=False),
        },
    )


def _write_understanding_json(task: dict, understanding_payload: dict):
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    source_id = task.get("source_document_id")
    source_name = clean_text(task.get("primary_attachment_name")) or f"source_{source_id}"
    safe_stem = Path(source_name).stem
    output_path = REPORT_DIR / f"{safe_stem}_understanding.json"
    output_path.write_text(
        json.dumps(understanding_payload or {}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return output_path


def _write_draft_json(task: dict, draft_payload: dict):
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    source_id = task.get("source_document_id")
    source_name = clean_text(task.get("primary_attachment_name")) or f"source_{source_id}"
    safe_stem = Path(source_name).stem
    output_path = REPORT_DIR / f"{safe_stem}_draft.json"
    output_path.write_text(
        json.dumps(draft_payload or {}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return output_path


def _write_five_table_review_json(task: dict, draft_payload: dict):
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    source_id = task.get("source_document_id")
    source_name = clean_text(task.get("primary_attachment_name")) or f"source_{source_id}"
    safe_stem = Path(source_name).stem
    output_path = REPORT_DIR / f"{safe_stem}_five_table_review.json"
    summary = summarize_five_tables(draft_payload or {})
    output_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return output_path, summary


def _extract_document(client: BaseOdooClient, task: dict, settings: WorkerSettings) -> ExtractedDocument:
    source_document_id = int(task.get("source_document_id") or 0)
    source_filename = task.get("primary_attachment_name") or ""
    mime_type = task.get("primary_attachment_mimetype") or ""
    raw_text_from_task = clean_text(task.get("raw_text"))

    if not task.get("attachment_download_url"):
        file_hash = sha256_text(raw_text_from_task or f"source:{source_document_id}")
        return ExtractedDocument(
            raw_text=raw_text_from_task,
            attachments=[],
            page_count=0,
            source_filename=source_filename,
            mime_type=mime_type,
            file_hash=file_hash,
            used_cache=False,
        )

    binary = client.download_attachment(task["attachment_download_url"])
    file_hash = sha256_bytes(binary)
    extract_cache_key = build_extract_cache_key(source_document_id, file_hash, settings.fast_mode)
    cached = load_json_cache("extract", extract_cache_key)
    if cached:
        return ExtractedDocument(
            raw_text=clean_text(cached.get("raw_text")),
            attachments=cached.get("attachments") or [],
            page_count=int(cached.get("page_count") or 0),
            source_filename=cached.get("source_filename") or source_filename,
            mime_type=cached.get("mime_type") or mime_type,
            file_hash=file_hash,
            used_cache=True,
        )

    raw_text = raw_text_from_task
    attachments = []
    page_count = 0
    name = source_filename or "source.pdf"
    if mime_type == "application/pdf" or name.lower().endswith(".pdf"):
        extracted = extract_pdf_text_and_images(
            binary,
            name,
            max_text_pages=settings.pdf_max_text_pages_fast if settings.fast_mode else settings.pdf_max_text_pages_full,
            max_image_pages=settings.pdf_max_image_pages_fast if settings.fast_mode else settings.pdf_max_image_pages_full,
        )
        raw_text = clean_text(extracted.get("raw_text"))
        attachments = extracted.get("attachments") or []
        page_count = int(extracted.get("page_count") or 0)

    save_json_cache(
        "extract",
        extract_cache_key,
        {
            "raw_text": raw_text,
            "attachments": attachments,
            "page_count": page_count,
            "source_filename": source_filename,
            "mime_type": mime_type,
        },
    )
    return ExtractedDocument(
        raw_text=raw_text,
        attachments=attachments,
        page_count=page_count,
        source_filename=source_filename,
        mime_type=mime_type,
        file_hash=file_hash,
        used_cache=False,
    )


def _call_vision(adapter, settings: WorkerSettings, task: dict, raw_text: str, attachments: list, context: dict):
    prompt = build_vision_prompt(task, raw_text, context)
    result = adapter.agent(
        message=prompt,
        agent_id=settings.agent_id,
        session_key=f"agent:{settings.agent_id}:tds-worker-{task['source_document_id']}-vision",
        timeout=settings.vision_timeout,
        attachments=attachments,
    )
    return parse_json_loose(result.get("text"))


def _call_understand(adapter, settings: WorkerSettings, task: dict, raw_text: str, attachments: list, context: dict):
    prompt = build_understanding_prompt(task, raw_text, context, fast_mode=settings.fast_mode)
    result = adapter.agent(
        message=prompt,
        agent_id=settings.agent_id,
        session_key=f"agent:{settings.agent_id}:tds-worker-{task['source_document_id']}-understand",
        timeout=settings.struct_timeout,
        attachments=attachments or None,
    )
    parsed = parse_json_loose(result.get("text"))
    return validate_understanding_payload(parsed)


def _call_struct(adapter, settings: WorkerSettings, task: dict, raw_text: str, vision_payload: dict, context: dict):
    prompt = build_struct_prompt(task, raw_text, vision_payload, context)
    result = adapter.agent(
        message=prompt,
        agent_id=settings.agent_id,
        session_key=f"agent:{settings.agent_id}:tds-worker-{task['source_document_id']}-struct",
        timeout=settings.struct_timeout,
    )
    parsed = parse_json_loose(result.get("text"))
    return validate_draft_payload(parsed)


def _call_single(adapter, settings: WorkerSettings, task: dict, raw_text: str, attachments: list, context: dict):
    prompt = build_single_pass_prompt(task, raw_text, context, fast_mode=settings.fast_mode)
    result = adapter.agent(
        message=prompt,
        agent_id=settings.agent_id,
        session_key=f"agent:{settings.agent_id}:tds-worker-{task['source_document_id']}-single",
        timeout=settings.single_pass_timeout_fast if settings.fast_mode else settings.single_pass_timeout_full,
        attachments=attachments or None,
    )
    parsed = parse_json_loose(result.get("text"))
    return validate_draft_payload(parsed)


def _load_or_build_vision_payload(
    adapter,
    settings: WorkerSettings,
    task: dict,
    extracted: ExtractedDocument,
    runtime_context: dict,
    existing_vision_payload: dict,
    cache_flags: dict,
    timer: StageTimer,
):
    source_document_id = int(task["source_document_id"])
    vision_context_signature = build_context_signature(
        task,
        runtime_context,
        raw_text=extracted.raw_text,
        param_limit=18,
        category_limit=8,
    )
    vision_cache_key = build_vision_cache_key(
        source_document_id=source_document_id,
        file_hash=extracted.file_hash,
        model=settings.model,
        context_signature=vision_context_signature,
    )
    cached_vision = load_json_cache("vision", vision_cache_key)
    if cached_vision and isinstance(cached_vision.get("vision_payload"), dict):
        cache_flags["vision_hit"] = 1
        cache_flags["vision_source"] = "local_cache"
        return cached_vision["vision_payload"], vision_context_signature
    if existing_vision_payload and isinstance(existing_vision_payload, dict):
        cache_flags["vision_hit"] = 0
        cache_flags["vision_from_existing"] = 1
        cache_flags["vision_source"] = "odoo_existing"
        save_json_cache("vision", vision_cache_key, {"vision_payload": existing_vision_payload})
        return existing_vision_payload, vision_context_signature
    cache_flags["vision_hit"] = 0
    cache_flags["vision_source"] = "model_call"
    with timer.track("vision_pass"):
        vision_payload = _call_vision(
            adapter,
            settings,
            task,
            extracted.raw_text,
            extracted.attachments,
            runtime_context,
        )
    save_json_cache("vision", vision_cache_key, {"vision_payload": vision_payload})
    return vision_payload, vision_context_signature


def _generate_legacy_draft(
    adapter,
    settings: WorkerSettings,
    task: dict,
    extracted: ExtractedDocument,
    runtime_context: dict,
    existing_vision_payload: dict,
    cache_flags: dict,
    timer: StageTimer,
):
    source_document_id = int(task["source_document_id"])
    raw_text = extracted.raw_text
    attachments = extracted.attachments
    mode = "legacy_dual_pass"
    single_context_signature = build_context_signature(
        task,
        runtime_context,
        raw_text=raw_text,
        param_limit=16 if settings.fast_mode else 24,
        category_limit=8 if settings.fast_mode else 12,
    )
    struct_context_signature = build_context_signature(
        task,
        runtime_context,
        raw_text=raw_text,
        param_limit=24,
        category_limit=12,
    )

    if settings.prefer_single_pass:
        single_cache_key = build_single_cache_key(
            source_document_id=source_document_id,
            file_hash=extracted.file_hash,
            model=settings.model,
            context_signature=single_context_signature,
            fast_mode=settings.fast_mode,
        )
        cached_single = _load_draft_cache_with_legacy("single_pass", single_cache_key)
        if cached_single and isinstance(cached_single.get("draft_payload"), dict):
            cache_flags["draft_hit"] = 1
            return validate_draft_payload(cached_single["draft_payload"]), (
                "legacy_single_pass_fast" if settings.fast_mode else "legacy_single_pass"
            )
        try:
            with timer.track("single_pass"):
                draft_payload = _call_single(adapter, settings, task, raw_text, attachments, runtime_context)
            save_json_cache("single_pass", single_cache_key, {"draft_payload": draft_payload})
            return draft_payload, "legacy_single_pass_fast" if settings.fast_mode else "legacy_single_pass"
        except Exception:
            pass

    vision_payload, _ = _load_or_build_vision_payload(
        adapter=adapter,
        settings=settings,
        task=task,
        extracted=extracted,
        runtime_context=runtime_context,
        existing_vision_payload=existing_vision_payload,
        cache_flags=cache_flags,
        timer=timer,
    )
    vision_signature = sha256_json(vision_payload)[:16]
    struct_cache_key = build_struct_cache_key(
        source_document_id=source_document_id,
        file_hash=extracted.file_hash,
        model=settings.model,
        context_signature=struct_context_signature,
        vision_signature=vision_signature,
    )
    cached_struct = _load_draft_cache_with_legacy("struct", struct_cache_key)
    if cached_struct and isinstance(cached_struct.get("draft_payload"), dict):
        cache_flags["draft_hit"] = 1
        return validate_draft_payload(cached_struct["draft_payload"]), mode
    with timer.track("struct_pass"):
        draft_payload = _call_struct(adapter, settings, task, raw_text, vision_payload, runtime_context)
    save_json_cache("struct", struct_cache_key, {"draft_payload": draft_payload})
    return draft_payload, mode


def _process_one_task(client: BaseOdooClient, settings: WorkerSettings, task: dict) -> PipelineResult:
    source_document_id = int(task["source_document_id"])
    timer = StageTimer()
    cache_flags = {
        "extract_hit": 0,
        "vision_hit": 0,
        "draft_hit": 0,
        "vision_from_existing": 0,
        "vision_source": "none",
        "understanding_hit": 0,
    }
    warnings = []
    quality_gate = {}

    with timer.track("extract"):
        extracted = _extract_document(client, task, settings)
    cache_flags["extract_hit"] = 1 if extracted.used_cache else 0

    attachment_size_est = _estimate_attachment_b64_size(extracted.attachments)
    if attachment_size_est > ATTACHMENT_CACHE_WARN_THRESHOLD:
        warnings.append(
            f"extract attachments cached payload is large (~{attachment_size_est} chars base64), "
            "consider blob/path cache strategy later"
        )

    raw_text = extracted.raw_text
    runtime_context = normalize_context(task)
    existing_vision_payload = coerce_json_object(task.get("existing_vision_payload"))
    vision_payload = {}
    mode = "cognitive_v2"
    understanding_summary = {}
    understanding_signature = ""

    baseline_context_signature = build_context_signature(
        task,
        runtime_context,
        raw_text=raw_text,
        param_limit=24,
        category_limit=12,
    )
    understanding_cache_key = build_understanding_cache_key(
        source_document_id=source_document_id,
        file_hash=extracted.file_hash,
        model=settings.model,
        context_signature=baseline_context_signature,
    )

    with OpenClawAdapter(
        gateway_url=settings.gateway_url,
        token=settings.gateway_token,
        timeout=240,
    ) as adapter:
        cached_understanding = load_json_cache("understanding", understanding_cache_key)
        if cached_understanding and isinstance(cached_understanding.get("understanding_payload"), dict):
            understanding_payload = validate_understanding_payload(cached_understanding.get("understanding_payload"))
            cache_flags["understanding_hit"] = 1
            cache_flags["understanding_source"] = "local_cache"
        else:
            with timer.track("understand"):
                understanding_payload = _call_understand(
                    adapter,
                    settings,
                    task,
                    raw_text,
                    extracted.attachments,
                    runtime_context,
                )
            cache_flags["understanding_hit"] = 0
            cache_flags["understanding_source"] = "model_call"

        understanding_payload = enrich_understanding_payload(understanding_payload)
        save_json_cache("understanding", understanding_cache_key, {"understanding_payload": understanding_payload})

        understanding_signature = sha256_json(understanding_payload)[:16]
        understanding_summary = summarize_understanding(understanding_payload)
        with timer.track("map_to_buckets"):
            mapped_payload_raw, route_drop_stats = map_understanding_to_draft(
                understanding_payload,
                validate_output=False,
                return_stats=True,
            )
        schema_errors = get_draft_schema_errors(mapped_payload_raw)
        mapped_payload = validate_draft_payload(mapped_payload_raw)
        mapped_timings = {
            key: value
            for key, value in timer.metrics.items()
            if key in {"extract", "understand", "map_to_buckets"}
        }
        quality_gate = evaluate_quality_gate(
            mapped_payload,
            mapped_timings,
            baseline_ms=0,
            schema_errors=schema_errors,
            route_drop_stats=route_drop_stats,
        )
        if quality_gate.get("passed"):
            draft_payload = mapped_payload
            mode = "cognitive_v2"
        else:
            warnings.append(f"quality_gate_failed={json.dumps(quality_gate, ensure_ascii=False)}")
            with timer.track("legacy_fallback"):
                draft_payload, legacy_mode = _generate_legacy_draft(
                    adapter=adapter,
                    settings=settings,
                    task=task,
                    extracted=extracted,
                    runtime_context=runtime_context,
                    existing_vision_payload=existing_vision_payload,
                    cache_flags=cache_flags,
                    timer=timer,
                )
            mode = f"{legacy_mode}+fallback_from_cognitive"

    with timer.track("postprocess"):
        draft_payload = postprocess_draft(task, draft_payload, runtime_context)

    timings_ms = {
        key: value
        for key, value in timer.metrics.items()
        if key in {"extract", "understand", "map_to_buckets", "single_pass", "vision_pass", "struct_pass", "legacy_fallback", "postprocess"}
    }
    metrics = {
        "timings_ms": timings_ms,
        "cache_flags": cache_flags,
        "warnings": warnings,
        "attachment_base64_chars": attachment_size_est,
        "quality_gate": quality_gate,
        "understanding_signature": understanding_signature,
        "understanding_summary": understanding_summary,
        "understanding_payload": understanding_payload,
    }
    return PipelineResult(
        source_document_id=source_document_id,
        mode=mode,
        raw_len=len(raw_text or ""),
        image_pages=len(extracted.attachments or []),
        vision_payload=vision_payload,
        draft_payload=draft_payload,
        context_used=runtime_context,
        metrics=metrics,
    )


def run_once(settings: WorkerSettings, limit=1, source_id=None):
    client = create_odoo_client(
        base_url=settings.odoo_base_url,
        token=settings.worker_token,
        db_name=settings.odoo_db,
        transport=settings.odoo_transport,
    )
    pending = client.pending_tasks(limit=limit, include_draft=True, source_document_id=source_id)
    tasks = pending.get("tasks") or []
    if not tasks:
        print("No pending tasks")
        return 0

    processed = 0
    for task in tasks:
        source_document_id = task["source_document_id"]
        run_id = f"run-{source_document_id}"
        try:
            client.mark_processing(source_document_id=source_document_id, worker_id="openclaw-worker", run_id=run_id)
            result = _process_one_task(client, settings, task)
            understanding_payload = result.metrics.get("understanding_payload") or {}
            understanding_file = _write_understanding_json(task, understanding_payload)
            draft_file = _write_draft_json(task, result.draft_payload)
            five_table_file, five_table_summary = _write_five_table_review_json(task, result.draft_payload)
            result.metrics["five_table_summary"] = five_table_summary
            if "understanding_payload" in result.metrics:
                result.metrics.pop("understanding_payload", None)
            unmatched_written = _write_unmatched_review(task, result.draft_payload)
            _write_import_report(task, result, settings, unmatched_written)
            result_message = (
                f"OpenClaw worker parsed ({result.mode}) with skill context bundle. "
                f"skills={','.join(result.context_used.get('skills_loaded') or []) or 'none'}; "
                f"raw_len={result.raw_len}; image_pages={result.image_pages}; "
                f"timings_ms={json.dumps(result.metrics.get('timings_ms') or {}, ensure_ascii=False)}; "
                f"cache_flags={json.dumps(result.metrics.get('cache_flags') or {}, ensure_ascii=False)}; "
                f"understanding_signature={result.metrics.get('understanding_signature') or ''}; "
                f"understanding_summary={json.dumps(result.metrics.get('understanding_summary') or {}, ensure_ascii=False)}; "
                f"quality_gate={json.dumps(result.metrics.get('quality_gate') or {}, ensure_ascii=False)}; "
                f"report_file={IMPORT_REPORT_FILE.name}; unmatched_file={UNMATCHED_REVIEW_FILE.name}; "
                f"understanding_file={understanding_file.name}; draft_file={draft_file.name}; "
                f"five_table_file={five_table_file.name}; "
                f"five_table_counts={json.dumps((result.metrics.get('five_table_summary') or {}).get('counts') or {}, ensure_ascii=False)}; "
                f"unmatched_rows={unmatched_written}"
            )
            if result.metrics.get("warnings"):
                result_message += f"; warnings={json.dumps(result.metrics.get('warnings'), ensure_ascii=False)}"
            client.mark_parsed(
                source_document_id=source_document_id,
                payload={
                    "source_document_id": source_document_id,
                    "vision_payload": json.dumps(result.vision_payload, ensure_ascii=False, indent=2),
                    "draft_payload": json.dumps(result.draft_payload, ensure_ascii=False, indent=2),
                    "unmatched_payload": json.dumps(
                        result.draft_payload.get("unmatched") or [], ensure_ascii=False, indent=2
                    ),
                    "parse_version": f"worker:openclaw({settings.model})+{result.mode}+skill-v1+norm-v2+cachefix-v1+cognitive-v2",
                    "context_used": json.dumps(result.context_used, ensure_ascii=False, indent=2),
                    "result_message": result_message,
                    "line_count": len(result.draft_payload.get("spec_values") or []),
                },
            )
            client.submit_review(source_document_id=source_document_id)
            print(f"Parsed source_document_id={source_document_id}")
            processed += 1
        except Exception as exc:
            debug_payload = {"task": task}
            try:
                client.mark_failed(
                    source_document_id=source_document_id,
                    error_code=exc.__class__.__name__,
                    error_message=str(exc),
                    debug_payload=json.dumps(debug_payload, ensure_ascii=False, indent=2),
                )
            except Exception:
                pass
            print(f"Failed source_document_id={source_document_id}: {exc}")
    return processed

