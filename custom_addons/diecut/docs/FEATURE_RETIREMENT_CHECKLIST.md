# Feature Retirement Checklist

## Purpose

Use this checklist whenever a feature is deleted or retired from the `diecut` module.

The goal is full-stack retirement:

- UI entry removed
- Python runtime removed
- data and config removed
- database fields cleaned
- migrations isolated
- docs and templates updated

Do not treat "XML hidden" as completed retirement.

## 1. Define The Retirement Target

Capture the exact identifiers first:

- feature name
- model names
- field names
- XML IDs
- config keys
- menu/action IDs
- scripts and docs that mention the feature

## 2. Entry Layer

Remove or disable:

- views
- buttons
- menus
- actions
- JS triggers
- chatter hooks
- cron/server actions

## 3. Runtime Layer

Remove:

- `models/*.py`
- `wizard/*.py`
- `controllers/*.py`
- helper services and mixins
- `__init__.py` imports

If a file only exists for the retired feature, delete it.

## 4. Data Layer

Check and clean:

- `__manifest__.py`
- `data/*.xml`
- `security/ir.model.access.csv`
- `ir.config_parameter`
- seeded users / partners / bots
- XML IDs in `ir.model.data`

## 5. Database Layer

Decide explicitly:

- migrate and keep data
- or delete obsolete fields/tables

Rules:

- one-time compatibility belongs in `migrations/`
- runtime models should stay clean
- remove stale `ir_model_fields`
- remove stale `ir_ui_view` residue if a field was removed

## 6. Repo Layer

Update or remove:

- CSV templates
- generator scripts
- sample payloads
- docs
- tests
- generated artifacts

## 7. Verification

### Code grep

Search for:

- model names
- field names
- XML IDs
- config keys
- human-facing feature names

### Module upgrade

Run:

```powershell
docker exec my_odoo_project_devcontainer-web-1 odoo -d odoo -u diecut --stop-after-init --db_host=db --db_user=odoo --db_password=odoo
```

### Database checks

Verify:

- no stale fields
- no stale tables
- no stale config keys
- no stale XML IDs

### Browser regression

Verify:

- page opens
- no dead button
- no missing-field crash
- no ghost menu entry

## 8. Completion Standard

A feature is only "retired" when:

1. users cannot trigger it
2. runtime code is removed
3. data/config references are removed
4. DB artifacts are migrated or deleted
5. docs no longer describe it as active

If any of these are missing, the retirement is incomplete.
