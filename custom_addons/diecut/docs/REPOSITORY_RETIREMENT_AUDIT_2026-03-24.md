# Repository Retirement Audit - 2026-03-24

## Scope

This audit checks whether previously retired or partially retired features still leave residues in the repo.

## Clean Or Expected Migration Residue

### `series_text`

Only found in migration files:

- `migrations/1.1/pre-migrate.py`
- `migrations/1.2/post-migrate.py`

Status:

- expected
- acceptable as migration-only residue

### Chatter AI runtime

Only found as cleanup keys in:

- `models/catalog_ai.py`

Current matches:

- `diecut.ai_mode_auto_enabled`
- `diecut.ai_mode_qa_partner_xmlid`
- `diecut.ai_mode_refine_partner_xmlid`
- `@AI问答`
- `@AI修订`

Status:

- not active runtime feature
- currently cleanup residue
- acceptable short term, but can be moved to a dedicated cleanup migration later for cleaner runtime code

## High Attention Residue

### `product_diecut.py` still contains many `variant_*` fields

File:

- `models/product_diecut.py`

This is separate from the already cleaned `diecut.catalog.item` path. It still contains a large legacy-style field set such as:

- `variant_thickness`
- `variant_color`
- `variant_adhesive_type`
- `variant_base_material`
- `variant_peel_strength`
- `variant_structure`
- more related `variant_*` fields

Status:

- active code residue
- high maintenance cost
- should be treated as its own retirement/refactor batch

### Hooks still contain `variant_*` migration cleanup

File:

- `hooks.py`

This is expected only if it is still serving migration compatibility. If runtime no longer needs those helpers, consider moving the entire variant cleanup path into versioned `migrations/`.

Status:

- medium priority
- acceptable temporarily
- should be reduced over time

## Generated Artifact Residue

The repo still contains generated or working files that should not be treated as stable source-of-truth:

- `scripts/.tds_worker_cache/...`
- `scripts/tds_import_drafts/...`
- rendered PDF working folders
- ad hoc audit CSVs and temporary payload JSONs

Status:

- not runtime code
- but they increase repo noise
- should be cleaned or ignored explicitly

## Recommended Next Cleanup Batches

### Batch 1

Retire or refactor `models/product_diecut.py` legacy `variant_*` surface if that path is no longer strategic.

### Batch 2

Move remaining cleanup-only chatter AI keys out of `models/catalog_ai.py` into migrations or one-time cleanup scripts.

### Batch 3

Clean generated artifacts under:

- `custom_addons/diecut/scripts/.tds_worker_cache`
- `custom_addons/diecut/scripts/tds_import_drafts`

and formalize ignore rules if needed.

## Conclusion

The project is in a better state than before, but retirement work is still uneven across subsystems.

The biggest remaining structural risk is:

- legacy `variant_*` surface in `product_diecut.py`

The biggest repo hygiene risk is:

- generated artifacts and temporary payloads living beside source files
