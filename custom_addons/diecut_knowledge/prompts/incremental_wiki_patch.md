# Task: Incremental Wiki Patch

Follow `llm_wiki_schema.md`.

You are updating an enterprise LLM Wiki from a batch of newly ingested or changed raw sources. Return one JSON object only. Do not return Markdown fences, HTML, explanations, or hidden reasoning.

Use the `schema` object in the user context as the exact contract. The top-level JSON must contain:

- `schema_version`
- `topic`
- `patches`
- `remove_link_ids`
- `review_required`
- `risk_level`
- `risk_notes`

Each entry in `patches` must contain:

- `operation`: one of `create_article`, `update_article`, `merge_into_existing`, `mark_conflict`, `review_only`
- `target_article_id`: required for update or merge operations when a candidate target is selected
- `title`
- `wiki_slug`
- `wiki_page_type`
- `summary`
- `content_md`
- `keywords`
- `source_document_ids`
- `citations`
- `links`
- `conflicts`
- `review_required`
- `risk_level`
- `risk_notes`

Rules:

- Prefer updating or merging into candidate Wiki targets when they already cover the topic.
- Create a new article only when no candidate target is reliable.
- Every key factual claim in `content_md` needs a citation in `citations`.
- Citation `source_document_id` values must come from the supplied `sources`.
- Link `target_id` values must come from candidate Wiki targets or the Wiki index.
- If the evidence is weak, conflicting, scanned poorly, or mostly inferred, use `review_only` or set `review_required` to true.
- If no safe article can be created or updated, still return a `review_only` patch explaining the issue in `summary`, `content_md`, and `risk_notes`.

Minimal valid shape:

{
  "schema_version": "odoo-llm-wiki-v1",
  "topic": {
    "group_key": "brand|kind|keyword",
    "title": "Topic title",
    "summary": "Why these sources belong together"
  },
  "patches": [
    {
      "operation": "review_only",
      "target_article_id": null,
      "title": "Topic title",
      "wiki_slug": "topic-title",
      "wiki_page_type": "source_summary",
      "summary": "Short summary",
      "content_md": "# Topic title\n\n## Overview\n\nEvidence-backed summary.\n\n## Source citations\n\n- See cited source excerpt.",
      "keywords": ["keyword"],
      "source_document_ids": [123],
      "citations": [
        {
          "claim_text": "Evidence-backed claim",
          "source_document_id": 123,
          "page_ref": "",
          "excerpt": "Short source excerpt",
          "confidence": 0.7,
          "state": "review"
        }
      ],
      "links": [],
      "conflicts": [],
      "review_required": true,
      "risk_level": "medium",
      "risk_notes": ["Needs human review before publication"]
    }
  ],
  "remove_link_ids": [],
  "review_required": true,
  "risk_level": "medium",
  "risk_notes": []
}
