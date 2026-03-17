# TDS Worker Integration Plan

## Goal

Make `scripts/tds_worker/` the single logic home for AI/TDS parsing, routing, review, and evolution-related assets, while keeping CSV templates and CSV exchange files at `scripts/` level.

## Agreed boundary

### Keep inside `scripts/tds_worker/`
- extract logic
- prompt logic
- pipeline logic
- normalization logic
- review/audit logic
- five-table references
- self-evolution references and rules
- reusable brand/category profiles later

### Keep outside `scripts/tds_worker/`
- CSV templates
- CSV exports/import exchange files
- batch output folders such as `tds_import_drafts/`
- one-off test artifacts and screenshots

## Current first-step integration

Integrated into `tds_worker/`:
- `references/five-table-model.md`
- `references/context-engineering.md`
- `references/self-evolution-policy.md`
- `review/five_table_review.py`

## Next steps

1. move five-table routing helpers from workspace experiments into project `tds_worker/`
2. add profile folders under `tds_worker/` for brands/categories
3. wire review summary generation into the main pipeline/postprocess stage
4. replace remaining hardcoded external experiment paths with project-aware config
5. separate CSV templates, generated CSVs, and review artifacts more clearly under `scripts/`
