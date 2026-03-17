# Five-Table Model

Use this as the canonical business model for material AI/TDS work in diecut.

## 1. Main table

Purpose: searchable item/material master.

Typical fields:
- code
- name
- series
- category
- thickness
- color
- adhesive type
- base material
- liner type

Rule: keep only high-frequency, stable, search-oriented attributes here.

## 2. Param table

Purpose: global parameter dictionary.

Typical fields:
- param_key
- standard names
- units
- value type
- is_main_field
- main_field_name
- target bucket
- parse hints

Rule: stabilize naming here; do not let each document invent new semantics.

## 3. Param category table

Purpose: connect params to categories.

Typical fields:
- category id
- param_key
- required
- sequence
- allow_import
- show_in_form

Rule: parameter applicability belongs here, not inside ad hoc prompt text.

## 4. Series table

Purpose: family-level shared product context.

Typical content:
- series name
- brand
- description
- applications
- common feature bullets
- common storage / processing / construction notes

Rule: if a statement applies to the whole family, route here first.

## 5. Param definition table

Purpose: actual spec lines / values.

Typical fields:
- item_code or series_name
- param_key
- value
- unit
- test_method
- test_condition
- remark
- source page
- source text

Rule: any value that depends on substrate, state, conditioning, method, or environment belongs here.
