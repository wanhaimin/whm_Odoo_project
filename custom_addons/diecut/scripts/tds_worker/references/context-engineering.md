# Context Engineering

Do not dump all source text into one prompt. Assemble the minimum useful context for the current material/document.

## Build context from these layers

1. source package
2. brand profile
3. category profile
4. parameter dictionary snapshot
5. category-param snapshot
6. prior review/failure patterns

## Recommended orchestration

### Pass 1 — document understanding
Identify document type, scope, tables, sections, candidate series/items, and risk notes.

### Pass 2 — main-field extraction
Extract item codes and high-frequency searchable fields.

### Pass 3 — conditional spec extraction
Extract peel/shear/aging/immersion/thermal/etc. with conditions preserved.

### Pass 4 — routing and review
Map to the five tables and record unresolved issues.

## Anti-patterns

Avoid:
- forcing all values into flat fields
- guessing missing dictionary mappings
- collapsing multiple test conditions into one value
- losing source traceability during normalization
