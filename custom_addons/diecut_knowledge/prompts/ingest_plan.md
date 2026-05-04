# Task: Ingest Plan

Follow `llm_wiki_schema.md`.

Read the raw source summary and produce a processing plan. The source may come from Odoo upload, pasted text, or a filesystem `raw/inbox` file mirrored into an Odoo source document. Do not execute the import.

Return one JSON object with:

- source_kind: `tds`, `selection_guide`, `application_note`, `processing_experience`, `qa`, or `raw`.
- source_intake: `odoo_upload`, `raw_inbox`, `manual_text`, or `unknown`.
- summary.
- recommended_actions: choose from `parse_source`, `compile_wiki`, `generate_faq`, `extract_material_draft`, `cross_reference`, `merge_existing`, `archive`.
- target_outputs: choose from `wiki`, `faq`, `material_draft`, `application_note`, `comparison`.
- requires_human_review.
- risk_level: `low`, `medium`, or `high`.
- risk_notes.
- wiki_strategy: `create`, `update_existing`, `merge_review`, `review_only`, or `skip`.
- related_keywords.

Return JSON only, without Markdown fences or `<think>`.
