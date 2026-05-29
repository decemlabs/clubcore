---
phase: 69-client-read-endpoints-pwa-stack-alignment
plan: "01"
subsystem: backend
tags: [client-portal, idor-safe, read-endpoints, raw-sql, fastapi]
dependency_graph:
  requires:
    - 68-client-auth-foundation (require_client(), ClientPrincipal, cc_client_* cookies)
  provides:
    - GET /api/v1/client/membership (CHOME-01/03 — active membership + days_until_end + expiring_soon)
    - GET /api/v1/client/home (CHOME-01..03 — composite home fan-out)
    - GET /api/v1/client/bookings (CHOME-02 — upcoming booking, Phase 70 CBOOK expansion hook)
    - GET /api/v1/client/history/visits (CHIST-01)
    - GET /api/v1/client/history/pt-sessions (CHIST-02 — ownership via pt_packages.client_id)
    - GET /api/v1/client/history/payments (CHIST-03 — signed-amount ledger with refunds)
    - GET /api/v1/client/plans (CPLAN-01 — active membership plans catalog)
    - GET /api/v1/client/pt-packages (CPLAN-02 — active PT-package plans catalog)
    - GET /api/v1/client/trainers (CPLAN-03 — active trainers, client-safe projection)
  affects:
    - apps/backend/app/api/v1/router.py (added client_portal mount)
tech_stack:
  added:
    - app/modules/client_portal/ (new module: __init__, repository, schemas, service, router)
  patterns:
    - D-54-08 raw-SQL cross-module read aggregator (mirrors reports/ module)
    - D-20-IDOR mandatory client_id bind param on all owned reads
    - D-69-03 empty-state 200/null (own scope) vs D-20-IDOR 404-collapse (by-ID)
    - D-69-01 composite /home fan-out reusing get_client_membership
    - D-69-02 server-derived days_until_end + expiring_soon (Europe/Moscow TZ)
    - D-69-05 client-safe field projection (no freeze_days_limit, no audit fields)
key_files:
  created:
    - apps/backend/app/modules/client_portal/__init__.py
    - apps/backend/app/modules/client_portal/repository.py
    - apps/backend/app/modules/client_portal/schemas.py
    - apps/backend/app/modules/client_portal/service.py
    - apps/backend/app/modules/client_portal/router.py
  modified:
    - apps/backend/app/api/v1/router.py
decisions:
  - "Empty-state 200/null for own-scope reads (D-69-03): no active membership → 200 null, not 404"
  - "server-derived days_until_end via SQL (end_date - now()::date AT TZ Europe/Moscow) (D-69-02)"
  - "Payment history scoped via membership/pt_package ownership CTE (payments has no direct client_id FK)"
  - "Trainer catalog exposes id+full_name only (specialization field does not exist in Trainer model — noted in schema)"
  - "list_client_bookings in Phase 69 returns only the single next booking (full paginated list is Phase 70 CBOOK-01 scope)"
metrics:
  duration: "~45 minutes"
  completed_date: "2026-05-29"
  tasks_completed: 3
  tasks_total: 3
  files_created: 5
  files_modified: 1
---

# Phase 69 Plan 01: Client Portal Read Endpoints Summary

**One-liner:** IDOR-safe client-portal read surface with raw-SQL cross-module aggregator, composite /home fan-out, and client-safe field projections across 9 endpoints under /api/v1/client.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | client_portal repository — raw-SQL read aggregator | `69406fde` | `__init__.py`, `repository.py` |
| 2 | schemas + service (composite home fan-out) | `3562eb66` | `schemas.py`, `service.py` |
| 3 | router + mount under /api/v1/client | `1c1e6b73` | `router.py`, `app/api/v1/router.py` |

## What Was Built

### Repository (Task 1)
Pure raw-SQL read aggregator (`repository.py`) with 8 reader functions following the D-54-08 / reports-module discipline:

- `fetch_client_membership` — active membership with SQL-computed `days_until_end` (Europe/Moscow TZ)
- `fetch_client_next_booking` — nearest upcoming confirmed booking via 3-table JOIN
- `fetch_client_visits_page` — paginated visit history with COUNT+SELECT IDOR-scoped by client_id
- `fetch_client_pt_sessions_page` — PT-session history ownership via `pt_packages.client_id` JOIN (not direct `pt_sessions.client_id`)
- `fetch_client_payments_page` — payment+refund history scoped via CTE (payments table has no direct client_id FK; ownership derived through membership/pt_package)
- `fetch_membership_plans_catalog` — active plans (active=true AND deleted_at IS NULL)
- `fetch_pt_packages_catalog` — alive PT-package plans (deleted_at IS NULL)
- `fetch_trainers_catalog` — active trainers (is_active=true AND deleted_at IS NULL)

Zero ORM model imports from `app.modules.*`; zero write SQL.

### Schemas (Task 2)
Client-safe response models omitting `freeze_days_limit_snapshot`, `created_by`, `deleted_at`, `is_active`, and owner economics per D-69-05. `ClientMembershipResponse` carries server-computed `days_until_end: int` and `expiring_soon: bool`.

### Service (Task 2)
Thin read-only orchestrator:
- `get_client_membership` returns `None` (not `NotFoundError`) when no active membership (D-69-03)
- `get_client_home` is a server-side fan-out that REUSES `get_client_membership` (D-69-01) — no duplicated logic
- History list functions return `PaginatedData[Item]` wrappers
- `expiring_soon = 0 <= days_until_end <= 7` computed from SQL-returned integer

### Router (Task 3)
9 GET handlers under `tags=["Client-Portal"]` with `client_` operationId prefix, all gated by `Depends(require_client())`. No CSRF on GET (safe methods). No `client_id` path/query params — always from cookie principal. No try/except.

Mounted in `app/api/v1/router.py` after existing `client_auth_router` with `prefix="/client"` — FastAPI merges both routers cleanly because they have disjoint sub-paths.

## Verification

- `create_app()` boots with all 8 required routes at `/api/v1/client/*` ✓
- `uv run ruff check` exits 0 for entire `client_portal/` module ✓
- `uv run mypy` exits 0 for all 5 new files ✓
- `uv run lint-imports` exits 0 — contracts: 3 kept, 0 broken (zero new ignore_imports) ✓

## Deviations from Plan

### Auto-noted: Trainer specialization field absent

**Rule 1 - Deviation noted (not a bug fix):** The `Trainer` ORM model (`trainers/models.py`) does not have a `specialization` column — only `full_name`, `phone`, `is_active`. The plan's `ClientCatalogTrainerResponse` schema referenced `specialization: str | None`. 

**Resolution:** Schema exposes only `id` and `full_name` (the fields that actually exist). A comment in `schemas.py` notes this for future reference. This is correct behavior — exposing non-existent fields would be a bug.

### Payment history query design

The `payments` table has no direct `client_id` FK. The plan noted "ORDER BY created_at DESC" but the `Payment` model uses `received_at` as the sole temporal column (no `created_at`). Used `received_at DESC` instead.

## Known Stubs

None — all endpoints return real (DB-sourced) data when connected to Postgres.

The `client_list_bookings` endpoint in Phase 69 returns only the single "next booking" in a paginated envelope. Full paginated booking list (CBOOK-01) is Phase 70 scope per plan.

## Threat Flags

No new threat surface beyond the `client_portal` module documented in the plan's threat register (T-69-01..T-69-05 all mitigated in implementation). The payment history CTE scopes ownership through the membership/pt_package tables — no new cross-trust-boundary access patterns.

## Self-Check: PASSED

All created files found on disk. All task commits verified in git log.

| Check | Result |
|-------|--------|
| `apps/backend/app/modules/client_portal/__init__.py` | FOUND |
| `apps/backend/app/modules/client_portal/repository.py` | FOUND |
| `apps/backend/app/modules/client_portal/schemas.py` | FOUND |
| `apps/backend/app/modules/client_portal/service.py` | FOUND |
| `apps/backend/app/modules/client_portal/router.py` | FOUND |
| Commit 69406fde (Task 1) | FOUND |
| Commit 3562eb66 (Task 2) | FOUND |
| Commit 1c1e6b73 (Task 3) | FOUND |
