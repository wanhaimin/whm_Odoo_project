# -*- coding: utf-8 -*-
from __future__ import annotations

from .translators import clean_text, map_known_value


IGNORED_TYPES = {"regulatory_contact", "contact_info", "marketing_claim", "legal_disclaimer"}


def process_unmatched(payload: dict, context: dict) -> dict:
    remaining = []
    items = payload.get("items") or []

    for row in payload.get("unmatched") or []:
        if not isinstance(row, dict):
            continue
        if row.get("type") in IGNORED_TYPES:
            continue

        source_label = clean_text(row.get("source_label")).lower()
        content = clean_text(row.get("content"))

        if row.get("type") == "classification_gap" and items:
            inferred = clean_text(items[0].get("category_name"))
            if inferred:
                continue

        if row.get("type") == "alias_candidate":
            continue

        if source_label == "duplicate headliner a blocks" and items:
            review_note = clean_text(items[0].get("review_note"))
            items[0]["review_note"] = (
                f"{review_note} " if review_note else ""
            ) + "顶棚A（无纺布表面）存在重复测试区块，第二组结果仅保留用于人工复核。"
            continue

        if source_label == "performance note" and items:
            review_note = clean_text(items[0].get("review_note"))
            items[0]["review_note"] = (
                f"{review_note} " if review_note else ""
            ) + "性能备注：离型面粘接性能低于当前数值，带下划线的值表示顶棚布面破坏。"
            continue

        if source_label == "liner" and content:
            row["candidate_param_key"] = "liner_material"
            row["candidate_name"] = "离型材料"
            row["content"] = map_known_value(content)
            row["reason"] = "已识别为离型材料候选，请人工确认。"
        elif source_label == "painted panel - initial state":
            row["candidate_param_key"] = "peel_180_painted_initial"
            row["candidate_name"] = "涂装板-初始状态-180度剥离力"
        elif source_label == "painted panel - humidity aging":
            row["candidate_param_key"] = "peel_180_painted_humidity_aging"
            row["candidate_name"] = "涂装板-湿热老化后-180度剥离力"

        remaining.append(row)

    payload["unmatched"] = remaining
    return payload

