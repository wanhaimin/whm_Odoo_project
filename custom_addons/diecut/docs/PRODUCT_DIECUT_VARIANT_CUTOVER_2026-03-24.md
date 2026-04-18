# Product Diecut Variant Cutover (2026-03-24)

## Scope

This cutover targets the remaining active legacy surface in
[`product_diecut.py`](E:/workspace/my_odoo_project/custom_addons/diecut/models/product_diecut.py),
especially the `product.product`-level `variant_*` fields that are still part of the runtime model.

The goal is to finish the retirement pattern we already applied to
`diecut.catalog.item`: keep canonical business fields, move legacy values
through migrations, and remove runtime compatibility fields from active code.

## Current State

### Active legacy fields on `product.product`

Main-field duplicates:

- `variant_thickness`
- `variant_adhesive_thickness`
- `variant_color`
- `variant_adhesive_type`
- `variant_base_material`
- `variant_ref_price`
- `variant_is_rohs`
- `variant_is_reach`
- `variant_is_halogen_free`
- `variant_fire_rating`
- `variant_catalog_structure_image`

Standardization helpers:

- `variant_thickness_std`
- `variant_color_std`
- `variant_adhesive_std`
- `variant_base_material_std`

Legacy long-tail/spec payload:

- `variant_peel_strength`
- `variant_structure`
- `variant_sus_peel`
- `variant_pe_peel`
- `variant_dupont`
- `variant_push_force`
- `variant_removability`
- `variant_tumbler`
- `variant_holding_power`
- `variant_note`

Legacy document payload:

- `variant_tds_file`
- `variant_tds_filename`
- `variant_msds_file`
- `variant_msds_filename`
- `variant_datasheet`
- `variant_datasheet_filename`

Migration patch field still alive at runtime:

- `color = fields.Char('Color Fix')`

### Active logic tied to those fields

- `_build_variant_std_vals_from_raw`
- `_build_variant_std_vals`
- `create`
- `write`

These still reinforce the legacy field family during normal record writes.

## Cutover Classification

### Keep as canonical runtime fields

On `product.template` / catalog side we already have the canonical surface:

- `thickness`
- `adhesive_thickness`
- `color_id`
- `adhesive_type_id`
- `base_material_id`
- `thickness_std`
- `ref_price`
- `is_rohs`
- `is_reach`
- `is_halogen_free`
- `catalog_structure_image`
- `fire_rating`
- `spec_line_ids`

### Migrate then delete

#### Direct main-field migration

Map legacy `product.product.variant_*` data into canonical fields where safe:

- `variant_ref_price -> ref_price`
- `variant_is_rohs -> is_rohs`
- `variant_is_reach -> is_reach`
- `variant_is_halogen_free -> is_halogen_free`
- `variant_fire_rating -> fire_rating`
- `variant_catalog_structure_image -> catalog_structure_image`

#### Taxonomy-backed migration

These must migrate through normalized taxonomy resolution, not raw text copy:

- `variant_color -> color_id`
- `variant_adhesive_type -> adhesive_type_id`
- `variant_base_material -> base_material_id`

#### Standardized field migration

- `variant_thickness_std -> thickness_std`

#### Long-tail/spec migration

Move these values into structured spec records rather than keeping them on the product model:

- `variant_peel_strength`
- `variant_structure`
- `variant_sus_peel`
- `variant_pe_peel`
- `variant_dupont`
- `variant_push_force`
- `variant_removability`
- `variant_tumbler`
- `variant_holding_power`
- `variant_note`

#### Document payload migration

These need an explicit destination decision before deletion:

- `variant_tds_file`
- `variant_tds_filename`
- `variant_msds_file`
- `variant_msds_filename`
- `variant_datasheet`
- `variant_datasheet_filename`

Recommended rule:

- migrate to template-level attachments if the business still needs them;
- otherwise export/archive externally and remove from runtime schema.

### Delete as migration-only patch

- `color = fields.Char('Color Fix')`

This should be replaced by a one-time migration that resolves the old char column to `color_id` and then removes the patch field from runtime code.

## Execution Plan

### Phase 1: Safe repository cleanup

- remove generated `variant_*` CSV/JSON artifacts from the repo;
- ignore worker caches and draft outputs;
- remove already-retired `catalog_spec_defs` script files.

### Phase 2: Migration preparation

- add a dedicated migration for `product.product` legacy variant data;
- map direct scalar fields first;
- resolve taxonomy text fields through dictionary lookup/create policies;
- convert long-tail legacy fields into structured spec records.

### Phase 3: Runtime model cleanup

- delete `variant_*` fields from `product_diecut.py`;
- remove `_build_variant_std_vals_from_raw` and related sync logic;
- remove `color = Char('Color Fix')` from the runtime model.

### Phase 4: Validation

- module upgrade `-u diecut`;
- verify `ir_model_fields` cleanup;
- verify PostgreSQL columns removed;
- run UI regression for material/product forms;
- verify no source files still reference `variant_*` except migrations/docs.

## Risks

The highest-risk area is the document payload and long-tail spec migration.
Those values should not be silently dropped. They need either:

1. a target attachment/spec structure, or
2. an explicit archival decision.

Until that mapping is implemented, runtime deletion should stop before the final drop step.
