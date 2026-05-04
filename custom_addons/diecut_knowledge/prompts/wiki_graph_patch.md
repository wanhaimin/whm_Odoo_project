# Task: Wiki Graph Patch

Follow `llm_wiki_schema.md`.

Maintain Wiki graph relations for the current article using the article content, raw source, existing links, and candidate old Wiki pages.

Requirements:

- Keep, remove, or create links based on business meaning.
- Do not create a strong relation from keyword overlap alone.
- If old links came from a wrong title or wrong source interpretation, propose removal.
- If uncertain, set review_required and explain in notes.
- Only reference candidate page ids.
- Markdown `[[wiki-slug|Title]]` links and Odoo graph links must describe the same semantic relationships.
- If a Markdown double-link exists but the evidence is weak, mark it for review instead of silently strengthening it.

Return JSON only with links, remove_link_ids, review_required, and notes.
