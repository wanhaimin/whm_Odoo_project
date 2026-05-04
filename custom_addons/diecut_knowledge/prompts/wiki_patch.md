# Task: Wiki Patch

Follow `llm_wiki_schema.md`.

Compile the raw source, parsed text, catalog facts, candidate old Wiki pages, and citation evidence into a Wiki Patch JSON object that Odoo can validate and apply.

Requirements:

- Do not create isolated pages if reliable old pages can be updated or linked.
- Prefer update or merge review when an existing page already covers the topic.
- Every key fact must have a source citation when possible.
- Conflicts must set review requirements and create contradiction evidence.
- `content_md` should be Obsidian-friendly Markdown. Use `[[wiki-slug|Title]]` links for related Wiki pages and preserve source/citation sections.
- When filesystem mirror metadata is present, keep frontmatter-compatible values stable; Odoo will write the final frontmatter.
- Return JSON only.

Expected fields include page data, citations, links, conflicts, risk notes, review flag, and related material draft requirement when applicable.
