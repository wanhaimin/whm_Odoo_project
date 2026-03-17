# -*- coding: utf-8 -*-
from __future__ import annotations

from .context_builder import build_model_context_text


def build_understanding_prompt(task: dict, raw_text: str, context: dict, fast_mode: bool = False) -> str:
    context_text = build_model_context_text(
        task,
        context,
        raw_text=raw_text,
        param_limit=16 if fast_mode else 24,
        category_limit=8 if fast_mode else 12,
    )
    excerpt = (raw_text or "")[:36000]
    return (
        "You are the Document Understanding Agent for an Odoo TDS copilot.\n"
        "Your job is to understand the document first, not to generate final Odoo import buckets.\n"
        "Return strict JSON only, with exactly these top-level keys:\n"
        "document_meta, sections, tables, candidate_items, candidate_facts, candidate_content, methods, unresolved.\n"
        "Do not output markdown. Do not output prose outside JSON.\n\n"
        "Rules:\n"
        "- Separate narrative content from measurable parameters.\n"
        "- Candidate content types must prioritize: product_description, product_features, main_applications, special_applications, item_features, equivalent_notes, processing_note, construction_note, performance_note, storage_note.\n"
        "- Candidate facts should include main searchable concepts (thickness/color/adhesive_type/base_material/liner_material) and condition-aware performance facts (peel/shear with substrate + state).\n"
        "- Identify item matrix/table structures and scope (series/item/mixed/unknown).\n"
        "- Include source_page/source_text/confidence where possible.\n"
        "- Include mapping_reason for candidate_facts and candidate_content.\n"
        "- Uncertain evidence must go to unresolved with reason.\n\n"
        f"{context_text}\n\n"
        "DOCUMENT EXCERPT\n"
        f"{excerpt}"
    )
