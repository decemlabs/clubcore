---
phase: 75-backend-field-additions
plan: "01"
subsystem: backend
tags: [client-portal, notif-prefs, membership, jsonb, alembic, tdd]
dependency_graph:
  requires: []
  provides: [price_kopecks-on-membership, auto_renew-on-membership, notif_prefs-on-client-me]
  affects: [apps/backend/app/modules/client_portal, apps/backend/app/modules/clients]
tech_stack:
  added: []
  patterns:
    - "CAST(:param AS jsonb) for JSONB bind in asyncpg text() statements (vs ::jsonb which conflicts with $N params)"
    - "BackendSchemaBase (extra=forbid) for inbound strict DTOs (NotifPrefs)"
    - "Server-side defaults applied in service layer when JSONB column is NULL"
key_files:
  created:
    - apps/backend/alembic/versions/0050_clients_notif_prefs.py
    - apps/backend/tests/modules/client_portal/test_notif_prefs_service.py
    - apps/backend/tests/integration/client_portal/test_notif_prefs_route.py
  modified:
    - apps/backend/app/modules/client_portal/schemas.py
    - apps/backend/app/modules/clients/models.py
    - apps/backend/app/modules/client_portal/repository.py
    - apps/backend/app/modules/client_portal/service.py
decisions:
  - "CAST(:notif_prefs AS jsonb) syntax used instead of ::jsonb operator — asyncpg translates :name→$N and the :: suffix caused a PostgresSyntaxError; CAST() function form is unambiguous"
  - "NotifPrefs inherits BackendSchemaBase (extra=forbid) not ResponseData (extra=ignore) — the interfaces block in PLAN.md corrected the PATTERNS.md claim"
  - "_NOTIF_DEFAULTS applied server-side in service.get_client_me when notif_prefs IS NULL — no DB DEFAULT, no backfill"
metrics:
  duration: "~20min"
  completed: "2026-06-02T16:29:51Z"
  tasks: 3
  files: 7
---

# Phase 75 Plan 01: Backend Field Additions (priceKopecks + notifPrefs) Summary

**One-liner:** additive JSONB notif_prefs column + membership price exposure via Alembic 0050, strict NotifPrefs schema (BackendSchemaBase), server-side defaults, and ASGI integration tests.

## Tasks Completed

| Task | Name | Commit | Key Files |
|------|------|--------|-----------|
| 1 | Schemas + Client model + Alembic 0050 | deae0874 | schemas.py, clients/models.py, 0050_clients_notif_prefs.py |
| 2 | Repository + service wiring | ee277095 | repository.py, service.py |
| 3 | Service + ASGI integration tests | d988f517 | test_notif_prefs_service.py, test_notif_prefs_route.py |

## What Was Built

**PMEM-01 — Membership price fields:**
- `ClientMembershipResponse` gains `price_kopecks: int` and `auto_renew: bool | None`
- `repository.fetch_client_membership` SELECT now includes `price_kopecks_snapshot`
- `service.get_client_membership` constructs with `price_kopecks=int(r["price_kopecks_snapshot"])` and `auto_renew=None`

**NOTIF-01 — Notification preferences persistence:**
- `NotifPrefs(BackendSchemaBase)` with four required bool fields (promo/schedule/trainer/sound); `extra="forbid"` via BackendSchemaBase rejects unknown keys at the wire layer (422)
- `Client` ORM model gains `notif_prefs: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)`
- Alembic 0050 adds column additively; downgrade drops it cleanly
- `ClientProfileUpdateRequest` gains `notif_prefs: NotifPrefs | None = None`
- `ClientMeResponse` gains `notif_prefs: NotifPrefs` (required)
- `_NOTIF_DEFAULTS = {promo: True, schedule: True, trainer: True, sound: False}` applied server-side when column is NULL
- repository `update_client_profile` persists via `CAST(:notif_prefs AS jsonb)` fixed literal fragment

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] asyncpg incompatibility with ::jsonb cast in text() named params**
- **Found during:** Task 3 (first test run)
- **Issue:** `notif_prefs = :notif_prefs::jsonb` causes a PostgresSyntaxError because asyncpg translates `:name` to `$N` positionally, and the `::jsonb` suffix after the original param name is left as-is, producing invalid SQL
- **Fix:** Changed to `notif_prefs = CAST(:notif_prefs AS jsonb)` and bind value as `json.dumps(payload.notif_prefs.model_dump())`
- **Files modified:** `apps/backend/app/modules/client_portal/repository.py`
- **Commit:** d988f517

**2. [Rule 1 - Bug] Import order in service.py caused ruff I001**
- **Found during:** Task 3 ruff check
- **Issue:** `import app.modules.promo_codes.service as _promo_service` placed after `from app.modules.client_portal.schemas import (...)` violating isort order
- **Fix:** Moved to correct position before the `from app.modules...` block; auto-fixed by `ruff check --fix`
- **Files modified:** `apps/backend/app/modules/client_portal/service.py`
- **Commit:** d988f517

## Verification Results

- `alembic upgrade head` → 0050_clients_notif_prefs applied cleanly
- `alembic downgrade -1` → column dropped cleanly; `alembic upgrade head` re-applies
- `pytest tests/modules/client_portal/test_notif_prefs_service.py tests/integration/client_portal/test_notif_prefs_route.py` → 9/9 passed
- `ruff check app tests` (scoped to new files) → All checks passed
- `mypy app` → Success: no issues found in 224 source files
- `lint-imports` → 3 contracts kept, 0 broken

## Known Stubs

None — all fields wire through to real data:
- `price_kopecks` sources from `memberships.price_kopecks_snapshot` (existing DB column)
- `auto_renew` is explicitly `None` per D-75-01 (no auto-renewal domain concept in v2.1); this is intentional, not a placeholder
- `notif_prefs` persists to and reads from `clients.notif_prefs` (new column)

## Threat Surface Scan

No new threat surface beyond what was declared in the plan's `<threat_model>`. All three trust boundaries (T-75-01, T-75-02, T-75-03) are mitigated as planned:
- T-75-01: IDOR-safe `:client_id` bind in fetch_client_membership (existing guard)
- T-75-02: NotifPrefs `extra="forbid"` rejects unknown keys at 422; CAST bind prevents SQL injection
- T-75-03: fetch_client_me + update_client_profile carry mandatory `:client_id` bind + `deleted_at IS NULL`

## Self-Check: PASSED

- [x] `apps/backend/alembic/versions/0050_clients_notif_prefs.py` — exists
- [x] `apps/backend/app/modules/client_portal/schemas.py` — contains NotifPrefs, price_kopecks, auto_renew, notif_prefs on request+response
- [x] `apps/backend/app/modules/clients/models.py` — contains notif_prefs JSONB mapped_column
- [x] `apps/backend/app/modules/client_portal/repository.py` — contains notif_prefs SELECT + SET branches
- [x] `apps/backend/app/modules/client_portal/service.py` — contains _NOTIF_DEFAULTS + wiring
- [x] `apps/backend/tests/modules/client_portal/test_notif_prefs_service.py` — 5 tests all pass
- [x] `apps/backend/tests/integration/client_portal/test_notif_prefs_route.py` — 4 tests all pass
- [x] Commits deae0874, ee277095, d988f517 exist in git log
