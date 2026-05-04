# Task: Wiki Retrieval Planner

Follow `llm_wiki_schema.md`.

Select which candidate Wiki pages are truly useful for answering the user question.

Rules:

- Only select ids from the candidate list.
- Strictly match models, brands, material categories, applications, and process problems.
- Broadly related pages must not replace specific model facts.
- Return an empty list if candidates cannot answer the question.
- Select at most 8 pages.

Return JSON only:

`{"selected_ids": [1, 2], "reason": "short reason"}`
