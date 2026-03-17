# -*- coding: utf-8 -*-
from __future__ import annotations

import re


CORE_VALUE_MAP = {
    "light blue": "浅蓝色",
    "blue": "蓝色",
    "black": "黑色",
    "clear": "透明",
    "paper": "纸",
    "non-woven cloth": "无纺布",
    "non woven cloth": "无纺布",
    "acrylic pressure sensitive adhesive": "丙烯酸压敏胶",
}

STATE_VALUE_MAP = {
    "immediate": "即时状态",
    "initial state": "初始状态",
    "normal state": "常温状态",
    "at high temperature": "高温状态",
    "heat aging": "热老化后",
    "humidity aging": "湿热老化后",
}

SUBSTRATE_VALUE_MAP = {
    "painted panel": "涂装板",
    "polypropylene": "PP板",
    "headliner a (non-woven cloth surface)": "顶棚A（无纺布表面）",
}


def clean_text(value):
    return str(value or "").strip()


def map_known_value(value):
    cleaned = clean_text(value)
    if not cleaned:
        return value
    return CORE_VALUE_MAP.get(cleaned.lower(), value)


def translate_structure_value(value):
    cleaned = clean_text(value)
    if not cleaned:
        return value
    translated = (
        cleaned.replace("Paper liner", "纸质离型层")
        .replace("Acrylic pressure sensitive adhesive", "丙烯酸压敏胶层")
        .replace("Non-woven cloth", "无纺布基材")
    )
    return translated if translated != cleaned and "/" in translated else value


def translate_shelf_life_value(value):
    cleaned = clean_text(value)
    if not cleaned:
        return value
    match = re.search(
        r"Three years \((?P<months>\d+)\s*months\).*?stored at (?P<temp>[\d.]+(?:°|º)?C) and (?P<rh>[\d.]+% relative humidity)",
        cleaned,
        flags=re.I,
    )
    if not match:
        return value
    temp = match.group("temp").replace("º", "°")
    return f"自生产日期起保质期三年（{match.group('months')}个月），建议在 {temp} / {match.group('rh')} 条件下储存。"


def translate_condition(condition):
    if not isinstance(condition, dict):
        return condition
    translated = dict(condition)
    state = clean_text(translated.get("state"))
    substrate = clean_text(translated.get("substrate"))
    if state:
        translated["state"] = STATE_VALUE_MAP.get(state.lower(), translated["state"])
    if substrate:
        lowered = substrate.lower()
        for key, mapped in SUBSTRATE_VALUE_MAP.items():
            if key in lowered:
                translated["substrate"] = mapped
                break
    return translated


def normalize_source_label(value: str) -> str:
    return (
        clean_text(value)
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

