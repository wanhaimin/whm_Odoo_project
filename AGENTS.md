# AGENTS.md - Odoo Diecut Project Development Guide

## Project Overview

This is an Odoo 19 ERP project for the diecut/模切 (die-cutting) industry. The main custom module is located in `custom_addons/diecut`.

---

## Environment & Access

| Item | Value |
|------|-------|
| Odoo URL | http://localhost:8070 |
| Login | admin / admin |
| Database | odoo |
| Container Name | my_odoo_project_devcontainer-web-1 |
| Custom Addons Path | custom_addons/ |

---

## Build/Lint/Test Commands

### Starting Odoo (Windows)
```powershell
# Option 1: Double-click Start_Odoo.bat
# Option 2: Manually
cd .devcontainer
docker-compose up -d
```

### Stopping Odoo
```powershell
# Option 1: Double-click Stop_Odoo.bat
# Option 2: Manually
cd .devcontainer
docker-compose down
```

### Restarting Container
```powershell
docker restart my_odoo_project_devcontainer-web-1
```

### Viewing Logs
```powershell
# Real-time logs
docker-compose -f .devcontainer/docker-compose.yml logs -f web

# Last 50 lines
docker-compose -f .devcontainer/docker-compose.yml logs -f --tail=50 web
```

### Upgrading Module
```powershell
docker exec my_odoo_project_devcontainer-web-1 odoo -d odoo -u diecut --stop-after-init --db_host=db --db_user=odoo --db_password=odoo
```

### Running Single Test
Odoo tests are typically run via pytest with the `--test-tags` flag or by specifying the test file:
```powershell
# Run specific test file (from within container)
docker exec my_odoo_project_devcontainer-web-1 odoo -d odoo -c /etc/odoo/odoo.conf --test-file /path/to/test.py

# Or using pytest if configured
docker exec my_odoo_project_devcontainer-web-1 pytest /mnt/extra-addons/diecut/tests/test_your_test.py
```

Note: Odoo's native test runner uses `--test-enable` flag.

---

## Code Style Guidelines

### General Rules
- Follow Odoo 19 development conventions
- Python 3 with Odoo ORM
- Use Chinese for user-facing strings (field labels, error messages)
- Use English for internal code (method names, comments for technical details)

### Python Code Style

#### Imports (Standard Odoo Pattern)
```python
# -*- coding: utf-8 -*-
from datetime import date
import re
from odoo import models, fields, api, Command
import logging
from odoo.exceptions import ValidationError
```

#### Model Naming
- Model class names: `CamelCase` (e.g., `ProductTemplate`, `DiecutBrand`)
- Internal model `_name`: `snake_case` with dots (e.g., `'diecut.brand'`)
- Description: Chinese (e.g., `_description = '品牌'`)

#### Field Naming
- Use `snake_case` for all field names
- Field `string` parameter: Chinese for UI labels
```python
name = fields.Char(string='品牌名称', required=True)
is_raw_material = fields.Boolean(string="是原材料", default=False)
```

#### Method Naming
- Use `snake_case` with appropriate prefix:
  - `_compute_*` for computed fields
  - `_onchange_*` for onchange methods
  - `_inverse_*` for inverse methods
  - `action_*` for button actions
  - `_check_*` or `_constrains_*` for constraints

#### Decorators
```python
@api.constrains('field_name')
def _check_something(self):
    """Constraint check method"""
    pass

@api.depends('dependent_field')
def _compute_something(self):
    """Computed field method"""
    pass

@api.onchange('field_name')
def _onchange_something(self):
    """Onchange method"""
    pass

@api.model
def some_model_method(self):
    """Model-level method (not recordset)"""
    pass
```

### XML View Guidelines

#### Structure
- Use standard Odoo view architecture (form, tree, kanban, search)
- Use Bootstrap 5 classes for enhanced UI (cards, grid)
- Avoid direct DOM manipulation - use Odoo Owl VDOM patterns

```xml
<!-- Example: Bootstrap card structure -->
<div class="row g-3">
    <div class="col-md-4">
        <div class="card shadow-sm border-0">
            <!-- content -->
        </div>
    </div>
</div>
```

#### Field References
```xml
<field name="name"/>
<field name="is_raw_material"/>
```

### Error Handling

#### Validation Errors
```python
from odoo.exceptions import ValidationError

@api.constrains('field')
def _check_something(self):
    for record in self:
        if condition:
            raise ValidationError('错误信息：具体描述')
```

#### Logging
```python
import logging
_logger = logging.getLogger(__name__)

_logger.info('Informational message')
_logger.warning('Warning message')
_logger.error('Error message')
```

### Security & Permissions

- New models require entries in `security/ir.model.access.csv`
- Follow Odoo access control patterns
- Use `sudo()` method when needed but be mindful of security

---

## Diecut Module Specific Guidelines

### Core Data Model (from SKILL.md)

The system extends `product.template` with two mutually exclusive flags:

1. **`is_catalog=True`**: Selection catalog material (technical reference only)
   - NOT part of sales/purchase/stock business flow
   - Must filter in search views with domain: `[('is_catalog', '=', False)]`

2. **`is_raw_material=True`**: ERP raw material (actual business entity)
   - Participates in production and procurement
   - Has specific form (roll R / sheet S), width, length, supplier

### Price Calculation Rules

**All materials use RMB/m² as base unit:**
- `product.supplierinfo.price` = `price_per_m2`
- Area (m²) = width(mm) / 1000 × length(m)
- Roll/Sheet cost = price_per_m2 × area
- Kg price = price_per_m2 × area ÷ weight

### Catalog Data Initialization

- Use Excel/CSV files for variant data maintenance (NOT XML functions)
- Python generator scripts create base data (product.template, attributes)
- JSON file manages variant-specific parameters
- XML triggers `_load_catalog_base_data_from_json()` on upgrade

### View Design (ADR-010)

- Use Bootstrap 5 Card & Grid for form beautification
- NO direct DOM manipulation - use Owl VDOM extension patterns
- Dynamic column hiding: intercept Owl's `getActiveColumns()` via `@web/core/utils/patch`

---

## Development Workflow

1. **Understand Requirements** - Read user requirements carefully, ask if unclear
2. **Write Code** - Modify Python models (models/), XML views, JS frontend
3. **Deploy Update**:
   ```powershell
   docker restart my_odoo_project_devcontainer-web-1
   docker exec my_odoo_project_devcontainer-web-1 odoo -d odoo -u diecut --stop-after-init
   ```
4. **Browser Verify** - Navigate to http://localhost:8070, test functionality
5. **Fix Loop** - Repeat until correct
6. **Report** - Show what was done and verification results

---

## File Locations

| Path | Description |
|------|-------------|
| `custom_addons/diecut/` | Main diecut module |
| `custom_addons/diecut/models/` | Python model files |
| `custom_addons/diecut/views/` | XML view files |
| `custom_addons/diecut/controllers/` | Controller files |
| `custom_addons/diecut/wizard/` | Wizard files |
| `custom_addons/diecut/scripts/` | Data generation scripts |
| `custom_addons/diecut/data/` | Data XML/JSON files |
| `custom_addons/diecut/security/` | Access control files |
| `.devcontainer/` | Docker configuration |
| `odoo/` | Odoo source code (read-only) |

---

## Key Files Reference

- `.agent/skills/odoo_diecut_dev/SKILL.md` - Diecut module development guide
- `.agent/workflows/dev-loop.md` - Development workflow
- `custom_addons/diecut/docs/DESIGN_MANUAL.md` - Detailed design documentation
- `README.md` - Project overview and basic commands
