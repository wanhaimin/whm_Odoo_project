# -*- coding: utf-8 -*-

import json
import logging
import os
import re

_logger = logging.getLogger(__name__)


_SKILL_DIR = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "data", "tds_skills"))


def infer_brand_skill_name(brand_name="", filename="", title=""):
    haystack = " ".join(str(value or "") for value in (brand_name, filename, title)).lower()
    if "3m" in haystack:
        return "brand_3m_v1"
    if "tesa" in haystack:
        return "brand_tesa_v1"
    return ""


def _normalize_skill_names(skill_profile, brand_skill_name=""):
    names = []
    for value in re.split(r"[,+\s]+", str(skill_profile or "")):
        cleaned = value.strip()
        if cleaned and cleaned not in names:
            names.append(cleaned)
    if not names:
        names = ["generic_tds_v1", "diecut_domain_v1"]
    brand_cleaned = str(brand_skill_name or "").strip()
    if brand_cleaned and brand_cleaned not in names:
        names.append(brand_cleaned)
    return names


def _load_skill_file(skill_name):
    path = os.path.join(_SKILL_DIR, f"{skill_name}.json")
    if not os.path.exists(path):
        _logger.warning("TDS skill file not found: %s", path)
        return {}
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def load_skill_bundle(skill_profile, brand_skill_name=""):
    skill_names = _normalize_skill_names(skill_profile, brand_skill_name)
    merged = {
        "skills_loaded": [],
        "task_instructions": [],
        "output_schema": {},
        "field_mapping_guidance": [],
        "param_aliases": {},
        "brand_or_domain_conventions": [],
        "table_patterns": [],
        "method_patterns": [],
        "negative_rules": [],
        "few_shot_examples": [],
    }
    for skill_name in skill_names:
        data = _load_skill_file(skill_name)
        if not data:
            continue
        merged["skills_loaded"].append(skill_name)
        for key in ("task_instructions", "field_mapping_guidance", "brand_or_domain_conventions", "table_patterns", "method_patterns", "negative_rules", "few_shot_examples"):
            values = data.get(key) or []
            if isinstance(values, list):
                merged[key].extend(values)
        schema = data.get("output_schema") or {}
        if isinstance(schema, dict):
            merged["output_schema"].update(schema)
        aliases = data.get("param_aliases") or {}
        if isinstance(aliases, dict):
            for alias_key, alias_values in aliases.items():
                existing = merged["param_aliases"].setdefault(alias_key, [])
                for alias_value in alias_values or []:
                    if alias_value not in existing:
                        existing.append(alias_value)
    return merged
