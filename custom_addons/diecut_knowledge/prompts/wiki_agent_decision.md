# Task: Wiki Agent Decision

Follow `llm_wiki_schema.md`.

Decide which evidence layers should be used for the user question.

Evidence layers:

- compiled Wiki.
- raw source documents.
- catalog structured facts.

Rules:

- Do not stop at weak Wiki matches.
- Model lists, parameter lookup, and material recommendations must check raw sources and catalog facts.
- Set `wiki_sufficient=true` only when selected Wiki evidence can directly answer the question.
- Only select ids from provided candidate lists.
- Return JSON only.

Expected JSON fields:

- intent.
- wiki_sufficient.
- use_layers.
- selected_wiki_ids.
- selected_source_ids.
- selected_item_ids.
- answer_strategy.
- compile_gap_required.
- reason.
