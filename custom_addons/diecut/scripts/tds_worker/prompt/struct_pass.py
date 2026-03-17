# -*- coding: utf-8 -*-
from __future__ import annotations

import json

from .context_builder import build_model_context_text


def build_struct_prompt(task: dict, raw_text: str, vision_payload: dict, context: dict) -> str:
    context_text = build_model_context_text(task, context, raw_text=raw_text, param_limit=24, category_limit=12)
    return (
        "You are the Structuring Agent for an Odoo TDS Copilot.\n"
        "Use the full document excerpt, the vision analysis, and the business context to produce the final draft.\n"
        "Return strict JSON with exactly these top-level keys: series, items, params, category_params, spec_values, unmatched.\n"
        "Do not emit markdown. Do not emit prose outside JSON.\n\n"
        "IMPORTANT ROUTING RULES:\n"
        "- General Description, Product Description, and overview narrative belong to series.product_description.\n"
        "- Feature bullets, key benefits, and product strengths belong to series.product_features.\n"
        "- Applications and recommended use cases belong to series.main_applications.\n"
        "- Item-specific descriptive differences belong to items.item_features.\n"
        "- Equivalent or substitute references belong to items.equivalent_notes.\n"
        "- Technical measurable values belong to spec_values.\n"
        "- Method narratives may go to params.method_html or descriptive method fields.\n"
        "- Do not send useful narrative product content to unmatched unless no suitable content field exists.\n\n"
        f"{context_text}\n\n"
        "VISION PAYLOAD\n"
        f"{json.dumps(vision_payload or {}, ensure_ascii=False, indent=2)}\n\n"
        "DOCUMENT EXCERPT\n"
        f"{(raw_text or '')[:90000]}"
    )
