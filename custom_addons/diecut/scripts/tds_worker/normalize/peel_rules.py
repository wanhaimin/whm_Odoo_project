# -*- coding: utf-8 -*-
from __future__ import annotations

from .translators import clean_text


def state_suffix(state):
    mapping = {
        "即时状态": "immediate",
        "初始状态": "initial",
        "常温状态": "normal",
        "高温状态": "high_temp",
        "热老化后": "heat_aging",
        "湿热老化后": "humidity_aging",
        "Immediate": "immediate",
        "Initial state": "initial",
        "Normal state": "normal",
        "At high temperature": "high_temp",
        "Heat aging": "heat_aging",
        "Humidity aging": "humidity_aging",
    }
    return mapping.get(clean_text(state), "")


def derive_specific_peel_meta(condition):
    if not isinstance(condition, dict):
        return None
    substrate = clean_text(condition.get("substrate"))
    state = clean_text(condition.get("state"))
    suffix = state_suffix(state)
    block = clean_text(condition.get("block"))
    lowered = substrate.lower()

    if not suffix:
        return None

    if substrate == "PP板" or "polypropylene" in lowered:
        return {
            "param_key": f"peel_180_pp_{suffix}",
            "param_name": f"PP板-{state}-180度剥离力",
        }

    if substrate == "顶棚A（无纺布表面）" or "headliner a" in lowered:
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


def derive_specific_peel_meta_from_row(row):
    if not isinstance(row, dict):
        return None
    condition = row.get("condition") if isinstance(row.get("condition"), dict) else {}
    derived = derive_specific_peel_meta(condition)
    if derived:
        return derived
    source_label = clean_text(row.get("source_label"))
    lowered = source_label.lower()
    for prefix, key_prefix, zh_label in (
        ("PP板 - ", "peel_180_pp", "PP板"),
        ("Polypropylene - ", "peel_180_pp", "PP板"),
        ("Headliner A - ", "peel_180_headliner_a", "顶棚A（无纺布表面）"),
        ("顶棚A - ", "peel_180_headliner_a", "顶棚A（无纺布表面）"),
    ):
        if source_label.startswith(prefix):
            state = source_label.replace(prefix, "", 1)
            suffix = state_suffix(state)
            if not suffix:
                return None
            if "second block" in lowered or "第二" in source_label:
                return {
                    "review_only": True,
                    "review_note": f"{zh_label}存在重复结果区块：{state}",
                }
            return {
                "param_key": f"{key_prefix}_{suffix}",
                "param_name": f"{zh_label}-{state}-180度剥离力",
            }
    return None

