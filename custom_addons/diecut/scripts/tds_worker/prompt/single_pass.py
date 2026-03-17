# -*- coding: utf-8 -*-
from __future__ import annotations

from .context_builder import build_model_context_text


def build_single_pass_prompt(task: dict, raw_text: str, context: dict, fast_mode: bool = False) -> str:
    if fast_mode:
        context_text = build_model_context_text(task, context, raw_text=raw_text, param_limit=16, category_limit=8)
        excerpt = (raw_text or "")[:12000]
        speed_note = "FAST MODE: prioritize core item fields, series narrative content, and high-confidence parameter candidates."
    else:
        context_text = build_model_context_text(task, context, raw_text=raw_text, param_limit=24, category_limit=12)
        excerpt = (raw_text or "")[:24000]
        speed_note = "FULL MODE: extract as complete as possible."

    return (
        "You are the single-pass TDS copilot for an Odoo diecut ERP.\n"
        "Read the attached PDF page images and text excerpt, then output final strict JSON.\n"
        "Top-level keys must be exactly: series, items, params, category_params, spec_values, unmatched.\n"
        "Do not output markdown. Do not output explanation text outside JSON.\n"
        "Use existing param_key values whenever possible.\n"
        "Uncertain values must go to unmatched with reason.\n\n"
        "IMPORTANT ROUTING RULES:\n"
        "- General Description, Overview, or Product Description text should populate series.product_description.\n"
        "- Features, Benefits, or Advantages text should populate series.product_features.\n"
        "- Applications, Typical Applications, or Recommended Uses should populate series.main_applications.\n"
        "- Item-specific descriptive differences should populate items.item_features.\n"
        "- Equivalent, replacement, or substitute notes should populate items.equivalent_notes when present.\n"
        "- Do not drop useful narrative product content into unmatched if it can fit description/features/applications.\n"
        "- Keep measurable technical values in spec_values.\n\n"
        f"{speed_note}\n\n"
        f"{context_text}\n\n"
        "DOCUMENT EXCERPT\n"
        f"{excerpt}"
    )
