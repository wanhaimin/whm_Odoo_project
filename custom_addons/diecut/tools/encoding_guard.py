# -*- coding: utf-8 -*-

from __future__ import annotations


SUSPICIOUS_MARKERS = ("锟斤拷", "ï»¿", "\ufffd")


def _looks_suspicious(value):
    if not isinstance(value, str):
        return []
    hits = []
    for marker in SUSPICIOUS_MARKERS:
        if marker in value:
            hits.append(marker)
    if "????" in value:
        hits.append("????")
    elif "???" in value:
        hits.append("???")
    elif "??" in value and any("\u4e00" <= char <= "\u9fff" for char in value):
        hits.append("??")
    return hits


def find_suspicious_text_entries(payload, prefix=""):
    findings = []
    if isinstance(payload, dict):
        for key, value in payload.items():
            next_prefix = f"{prefix}.{key}" if prefix else str(key)
            findings.extend(find_suspicious_text_entries(value, next_prefix))
        return findings
    if isinstance(payload, list):
        for index, value in enumerate(payload):
            next_prefix = f"{prefix}[{index}]"
            findings.extend(find_suspicious_text_entries(value, next_prefix))
        return findings
    if isinstance(payload, str):
        markers = _looks_suspicious(payload)
        if markers:
            findings.append(
                {
                    "path": prefix or "<value>",
                    "markers": markers,
                    "preview": payload[:120],
                }
            )
    return findings


def format_suspicious_entries(findings, limit=12):
    lines = []
    for item in findings[:limit]:
        marker_text = ",".join(item["markers"])
        lines.append(f"{item['path']}: {marker_text} -> {item['preview']}")
    if len(findings) > limit:
        lines.append(f"... 另有 {len(findings) - limit} 处可疑内容")
    return "\n".join(lines)


def _text_quality_score(value):
    """Higher is better. Prefer normal Chinese/ASCII business text."""
    if not isinstance(value, str) or not value:
        return 0
    cjk = sum(1 for ch in value if "\u4e00" <= ch <= "\u9fff")
    ascii_ok = sum(1 for ch in value if ch.isascii() and (ch.isalnum() or ch in " .,:;_-/()[]%#&+"))
    weird = sum(1 for ch in value if not ch.isascii() and not ("\u4e00" <= ch <= "\u9fff"))
    suspicious = len(_looks_suspicious(value))
    return cjk * 3 + ascii_ok - weird * 2 - suspicious * 5


def repair_mojibake_text(value):
    """Try repairing common mojibake (UTF-8 bytes decoded as GBK/GB18030)."""
    if not isinstance(value, str) or not value:
        return value
    best = value
    best_score = _text_quality_score(value)
    candidates = []
    for source_enc in ("gbk", "gb18030", "big5"):
        try:
            repaired = value.encode(source_enc, errors="strict").decode("utf-8", errors="strict")
            candidates.append(repaired)
        except Exception:
            continue
    for repaired in candidates:
        score = _text_quality_score(repaired)
        if score > best_score + 3:
            best = repaired
            best_score = score
    return best


def deep_repair_mojibake(payload):
    """Recursively repair text fields in dict/list payload."""
    if isinstance(payload, dict):
        return {k: deep_repair_mojibake(v) for k, v in payload.items()}
    if isinstance(payload, list):
        return [deep_repair_mojibake(v) for v in payload]
    if isinstance(payload, str):
        return repair_mojibake_text(payload)
    return payload
