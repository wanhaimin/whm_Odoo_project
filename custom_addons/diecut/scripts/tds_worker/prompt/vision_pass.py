# -*- coding: utf-8 -*-
from __future__ import annotations

from .context_builder import build_model_context_text


def build_vision_prompt(task: dict, raw_text: str, context: dict) -> str:
    context_text = build_model_context_text(task, context, raw_text=raw_text, param_limit=18, category_limit=8)
    return (
        "You are the Vision Parser for an Odoo TDS Copilot.\n"
        "Read the attached PDF page images together with the extracted text.\n"
        "Identify narrative sections such as General Description, Features, Benefits, Applications, and Product Construction.\n"
        "Tables should be separated from narrative descriptive sections.\n"
        "Return strict JSON with exactly these top-level keys: sections, tables, charts, methods, candidate_items.\n"
        "Do not emit markdown. Do not emit prose outside JSON.\n\n"
        f"{context_text}\n\n"
        "DOCUMENT EXCERPT\n"
        f"{(raw_text or '')[:60000]}"
    )
