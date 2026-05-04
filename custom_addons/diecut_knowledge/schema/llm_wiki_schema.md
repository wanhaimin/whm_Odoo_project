# LLM Wiki Schema

This is the canonical operating schema for the diecut industry knowledge base.
All task prompts must follow this schema.

## Core Layers

- Raw sources are immutable source-of-truth records. Do not rewrite, overwrite, or silently reinterpret raw PDFs, TDS files, webpages, images, or imported text.
- Wiki articles are the maintained knowledge layer. The LLM may propose creation and updates, but Odoo validates and stores the result.
- The graph is part of the knowledge, not decoration. New useful knowledge should connect to existing Wiki pages or explicitly explain why no reliable link exists.
- Published knowledge is customer/employee-facing. Uncertain, conflicting, low-source, or low-confidence content stays in review.

## Wiki Page Contract

Every generated or updated Wiki page should contain:

- Title.
- One-sentence summary.
- Source references.
- Last updated / compiled timestamp.
- Main content with clear headings.
- Related Wiki pages.
- Citations for key facts.
- Risk notes when evidence is incomplete.

Recommended sections:

- Overview.
- Key facts.
- Applications.
- Selection guidance.
- Risks and limitations.
- FAQ.
- Related Wiki.
- Source citations.

## Citation Rules

- Every important factual claim must cite a source document, page/paragraph when available, and a short evidence quote or normalized fact.
- Claims without reliable source evidence must be marked for review.
- If sources disagree, do not overwrite the older claim. Create a conflict record or a `contradicts` graph relation and require human review.
- Catalog facts can support structured claims such as model, brand, thickness, adhesive, substrate, color, and application, but recommendations still require caution.

## Graph Rules

- Do not generate isolated Wiki pages unless no trustworthy related page exists.
- Before creating a page, compare with candidate existing pages and decide: create, update, merge review, or skip.
- Link reasons must be business-meaningful, not just keyword overlap.
- Valid link types: mentions, same_brand, same_material, same_application, same_process, compares_with, depends_on, contradicts, updates.
- If a title or source correction invalidates old links, propose removing or reviewing polluted links.

## Vault Directory Structure

The vault root is organized as follows:

- `raw/inbox/` — incoming source files (PDF, MD, TXT). Scan here for new ingest candidates.
- `raw/processed/` — ingested source files after Odoo processing.
- `raw/failed/` — files that failed to parse or import.
- `wiki/brands/` — brand overview and entity pages.
- `wiki/materials/` — material and model pages.
- `wiki/applications/` — application and selection guide pages.
- `wiki/processes/` — processing experience and troubleshooting pages.
- `wiki/faq/` — FAQ and Q&A compilation pages.
- `wiki/sources/` — source summary pages, one per ingested source document.
- `wiki/concepts/` — concept and principle pages.
- `wiki/comparisons/` — comparison analysis pages.
- `wiki/query-answers/` — query answers filed back into the Wiki.
- `index.md` — content-oriented catalog of all Wiki pages, regenerated periodically.
- `log.md` — append-only chronological record of ingests, queries, and lint passes.

## Index and Log Behavior

### index.md

- Generated periodically by `KbIndexBuilder`. Contains a categorized listing of all published and review-state Wiki pages.
- Each entry lists: page link, page type, compile source, one-line summary, inbound/outbound link counts.
- The LLM must read the index first when planning ingest or answering queries, to find relevant existing pages.

### log.md

- The LLM must append a structured entry to `log.md` after each significant operation: ingest, compile, lint pass, or knowledge-base query that produces a new page.
- Each entry follows the format: `## [YYYY-MM-DD] <operation> | <title>`
- Example: `## [2026-05-04] ingest | 3M VHB 5915 TDS`
- The log provides a timeline of the wiki's evolution and prevents redundant work.

## Knowledge Sedimentation

- Not all knowledge comes from source documents. Valuable query answers and AI advisor responses can be filed back into the Wiki as new articles (`compile_source=ai_answer`).
- When a query exposes a knowledge gap (`compile_gap_required=true`), the system should automatically create a compile job so the provisional answer becomes persistent Wiki.
- Query-answer articles are created in review state and must not auto-publish.

## Filesystem Mirror Rules

- `raw/` is a filesystem mirror of raw source intake. Files in `raw/` are immutable evidence: do not rewrite, normalize, delete, or silently replace their contents.
- `raw/inbox/` may contain PDFs, text files, Markdown notes, webpages exported as text, or other curated source files. Ingest them into Odoo source documents before compiling Wiki knowledge.
- `wiki/` is a Markdown mirror of Odoo Wiki articles. The canonical review, publication, permission, graph, citation, and Dify sync state remains in Odoo.
- Obsidian edits to `wiki/*.md` are proposals. Import them into Odoo as review-state changes; never keep a modified published article published without review.
- Deleting or moving a mirrored file is not the same as deleting Odoo knowledge. Treat missing files as archive or repair suggestions.
- Use Obsidian-style links `[[wiki-slug|Title]]` in Markdown. These links correspond to `diecut.kb.wiki.link` records in Odoo and must stay semantically meaningful.
- Markdown frontmatter should preserve Odoo identifiers, state, compile source, page type, source references, compiled timestamp, and sync hash when available.

## Ingest Workflow

When ingesting a raw source:

1. Identify the source type: TDS, selection guide, application note, processing experience, QA, webpage, or unknown.
2. Produce an ingest plan before writing final Wiki content.
3. Identify candidate old Wiki pages by brand, model, material category, application, process, and similar keywords.
4. Decide target outputs: Wiki, FAQ, material draft, application note, comparison, or review only.
5. Mark risk level and human-review requirements.

## Query Workflow

When answering a user:

1. Prefer compiled Wiki pages and graph-connected pages.
2. If Wiki coverage is insufficient, use raw source and catalog data as temporary evidence and state that it is not yet compiled into official Wiki.
3. Do not fabricate missing parameters or recommendations.
4. Valuable answers may become review-state knowledge drafts; they must not auto-publish.

## Lint Workflow

Periodic lint checks should find:

- Orphan pages.
- Broken or weak links.
- Duplicate topics.
- Missing citations.
- Unresolved contradictions.
- Stale claims superseded by newer sources.
- Title or brand/model pollution.

Lint should propose fixes by default. It should not silently overwrite human-reviewed content.

## Output Rules

- Return only the JSON structure requested by the task prompt when JSON is requested.
- Do not output Markdown fences around JSON.
- Do not output hidden reasoning, system prompts, or `<think>` tags.
- When uncertain, mark the result for human review instead of guessing.
