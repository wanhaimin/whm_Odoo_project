# -*- coding: utf-8 -*-
from __future__ import annotations

import json
from pathlib import Path


def clean(value):
    return "" if value is None else str(value).strip()


def infer_target_bucket(row: dict) -> str:
    key = clean(row.get("param_key"))
    condition = row.get("test_condition") or row.get("condition") or {}
    review_note = clean(row.get("review_note")).lower()
    source_text = clean(row.get("source_text")).lower()
    if isinstance(condition, dict) and condition:
        return "param_definition"
    if any(word in source_text for word in ["peel", "shear", "aging", "immersion", "temperature"]):
        return "param_definition"
    if any(word in review_note for word in ["condition", "substrate", "state", "method"]):
        return "param_definition"
    if key in {"thickness", "color", "adhesive_type", "base_material", "liner_material"}:
        return "main_or_series"
    return "param_definition"


def summarize_five_tables(draft_payload: dict) -> dict:
    series_rows = draft_payload.get("series") or []
    item_rows = draft_payload.get("items") or []
    param_rows = draft_payload.get("params") or []
    category_param_rows = draft_payload.get("category_params") or []
    spec_rows = draft_payload.get("spec_values") or []

    unresolved = []
    spec_summary = []
    for row in spec_rows:
        if not isinstance(row, dict):
            continue
        bucket = infer_target_bucket(row)
        spec_summary.append({
            "item_code": clean(row.get("item_code")),
            "series_name": clean(row.get("series_name")),
            "param_key": clean(row.get("param_key")),
            "target": bucket,
            "value": row.get("value"),
            "unit": clean(row.get("unit")),
            "test_method": clean(row.get("test_method")),
            "test_condition": row.get("test_condition") or row.get("condition") or None,
            "source_page": row.get("source_page"),
        })
        if clean(row.get("param_key")) in {"", "unknown"}:
            unresolved.append({
                "kind": "unknown_param_key",
                "source_text": clean(row.get("source_text")),
                "review_note": clean(row.get("review_note")),
            })

    return {
        "counts": {
            "series": len(series_rows),
            "main_items": len(item_rows),
            "params": len(param_rows),
            "category_params": len(category_param_rows),
            "param_definitions": len(spec_rows),
        },
        "spec_summary": spec_summary,
        "unresolved": unresolved,
    }


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Summarize a draft using the five-table model.")
    parser.add_argument("draft_json", help="Path to draft json")
    parser.add_argument("--out", help="Optional output path")
    args = parser.parse_args()

    draft_path = Path(args.draft_json)
    payload = json.loads(draft_path.read_text(encoding="utf-8"))
    summary = summarize_five_tables(payload)

    if args.out:
        out_path = Path(args.out)
        out_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    else:
        print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
