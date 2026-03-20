---
name: module-architecture
description: Expert in the MyMind modular system and BaseModule implementation.
---
# Module Architecture

**Trigger:** "new module", "yeni modül", "modül ekle", "BaseModule", "extend"

**Description:**
Knows the MyMind modular system.
Every module implements `BaseModule` from `core/base_module.py`.

**Required Methods:**
- `name`
- `description`
- `version`
- `router`
- `on_startup()`
- `on_shutdown()`
- `health_check()`
- `get_dashboard_summary()`

**Module Auto-discovery:**
`core/module_registry.py` scans `/modules/*/module.py`.

**New Module Scaffold:**
Run `python scripts/new_module.py --name X --description Y`.
Module router is auto-mounted at `/api/{module_name}/`.
Modules declare dependencies in metadata — registry loads in dependency order.
