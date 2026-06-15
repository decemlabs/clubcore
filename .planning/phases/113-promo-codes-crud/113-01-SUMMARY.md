---
phase: 113-promo-codes-crud
plan: "01"
subsystem: backend
tags: [promo-codes, rbac, migration, admin-crud]

dependency_graph:
  requires:
    - "0071_seed_settings (alembic head)"
    - "app.core.permissions OWNER_ONLY (42 entries)"
    - "apps/admin-app can.ts / registry.ts (42 entries)"
  provides:
    - "Migration 0072 — nullable description column on promo_codes"
    - "Admin CRUD API — GET/POST/PATCH /api/v1/promo-codes"
    - "RBAC parity at 45 entries (backend permissions.py == frontend can.ts)"
    - "PromoCodeCreateRequest / PromoCodeUpdateRequest / PromoCodeListItemResponse DTOs"
    - "Repository with correlated used_count subquery"
    - "Service: create/update/deactivate_promo_code with UPPER-normalization + alive-uniqueness"
  affects:
    - "apps/backend/app/api/v1/router.py (new promo-codes route)"
    - "apps/admin-app/src/shared/session/can.ts (45 entries)"
    - "apps/admin-app/src/shared/session/registry.ts (Resource union + 'promo-codes')"
    - "apps/backend/tests/integration/test_rbac_parity.py (count 42->45)"

tech_stack:
  added: []
  patterns:
    - "Correlated scalar subquery for used_count aggregate (cross-module raw count via SQLAlchemy func.count)"
    - "UPPER-normalize + alive-uniqueness IntegrityError -> 409 pattern"
    - "RBAC-04 ordering: require_permission BEFORE verify_csrf on all write routes"
    - "CurrentUser Protocol in service layer (mirrors users/service.py pattern)"

key_files:
  created:
    - apps/backend/alembic/versions/0072_promo_codes_description.py
    - apps/backend/app/modules/promo_codes/schemas.py
    - apps/backend/app/modules/promo_codes/repository.py
    - apps/backend/app/modules/promo_codes/router.py
  modified:
    - apps/backend/app/modules/promo_codes/models.py
    - apps/backend/app/modules/promo_codes/service.py
    - apps/backend/app/api/v1/router.py
    - apps/backend/app/core/permissions.py
    - apps/admin-app/src/shared/session/can.ts
    - apps/admin-app/src/shared/session/registry.ts
    - apps/backend/tests/integration/test_rbac_parity.py

decisions:
  - "Used CurrentUser Protocol (not User ORM model) in service function signatures — mirrors users/service.py convention and avoids cross-module ORM type leak"
  - "Repository insert_promo_code returns the PromoCode ORM instance (not a DTO) — service calls model_validate at the router boundary"
  - "Pre-existing ruff issues in service.py fixed inline (RUF002 ambiguous minus sign, SIM108 ternary) as they blocked verification command — logged as Rule 1 deviation"
  - "E501 in models.py line 59 suppressed with noqa comment (pre-existing long line) rather than reformatting"

metrics:
  duration: "~8 minutes"
  completed_date: "2026-06-15"
  tasks_completed: 3
  tasks_total: 3
  files_created: 4
  files_modified: 7
---

# Phase 113 Plan 01: Promo Codes Backend CRUD + RBAC Parity Summary

**One-liner:** Promo codes admin CRUD (list with used_count/create/edit/deactivate) with Alembic migration 0072, RBAC parity at 45 entries, and all write routes secured with RBAC-04 ordering.

## Tasks Completed

| Task | Name | Commit | Key Files |
|------|------|--------|-----------|
| 1 | Model column + Alembic migration 0072 | ebcbd3dd | models.py (+description), 0072_promo_codes_description.py |
| 2 | Schemas + repository + service | 6e3250e4 | schemas.py, repository.py, service.py |
| 3 | Router + API registration + RBAC parity | 2249f9d1 | router.py, api/v1/router.py, permissions.py, can.ts, registry.ts, parity test |

## What Was Built

### Migration 0072
- `apps/backend/alembic/versions/0072_promo_codes_description.py` — additive nullable `String(500)` `description` column on `promo_codes` table
- `down_revision = "0071_seed_settings"` — correctly chains from head
- Round-trip clean (upgrade → downgrade → upgrade verified)
- Applied to running local Postgres

### Schemas (apps/backend/app/modules/promo_codes/schemas.py)
- `PromoCodeCreateRequest(BackendSchemaBase)` — code, discount_type (Literal), discount_value (int), max_uses, per_client_limit, valid_from/until, applicable_to, description; validators: discount_value > 0, applicable_to ∈ {membership, pt_package}, percentage ≤ 10000 (100%)
- `PromoCodeUpdateRequest(BackendSchemaBase)` — all fields optional (partial edit)
- `PromoCodeListQuery(PageQuery)` — active: bool | None = None
- `PromoCodeListItemResponse(ResponseData)` — full row + used_count aggregate
- `PromoCodeResponse(ResponseData)` — create/edit response shape

### Repository (apps/backend/app/modules/promo_codes/repository.py)
- `list_promo_codes` — predicates (deleted_at IS NULL + optional is_active), total COUNT, correlated `func.count()` scalar subquery for `used_count` per row, order_by created_at DESC + id DESC, offset/limit from PageQuery
- `get_alive` — fetch by id WHERE deleted_at IS NULL
- `insert_promo_code` — no commit/flush (caller owns UoW)
- `update_promo_code` — setattr loop from values dict
- `deactivate_promo_code` — bulk UPDATE is_active=False WHERE deleted_at IS NULL

### Service (apps/backend/app/modules/promo_codes/service.py — extended)
New error classes: `PromoCodeNotFoundError` (404), `PromoCodeAlreadyExistsError` (409), `PromoCodeValidationError` (422)

New CRUD functions:
- `create_promo_code` — UPPER-normalize code, insert, commit; IntegrityError on `uq_promo_codes_code_alive` → 409
- `update_promo_code` — load alive or 404, exclude_unset dict, UPPER-normalize code if present, commit; same conflict mapping
- `deactivate_promo_code` — load alive or 404, deactivate, commit

### Router (apps/backend/app/modules/promo_codes/router.py)
- `GET ""` — LIST permission, no CSRF; returns paginated envelope with used_count
- `POST ""` (201) — CREATE permission BEFORE verify_csrf; returns PromoCodeResponse
- `PATCH "/{promo_id}"` — EDIT permission BEFORE verify_csrf; returns PromoCodeResponse
- `PATCH "/{promo_id}/deactivate"` (204) — DELETE permission BEFORE verify_csrf; returns None

RBAC-04 ordering invariant enforced on all write routes.

### RBAC Parity (permissions.py + can.ts + registry.ts + parity test)
- `Resource.PROMO_CODES = "promo-codes"` added to backend Resource StrEnum
- 3 OWNER_ONLY pairs: `(CREATE, PROMO_CODES)`, `(EDIT, PROMO_CODES)`, `(DELETE, PROMO_CODES)`
- `'promo-codes'` added to frontend Resource union in registry.ts
- 3 mirroring entries in can.ts OWNER_ONLY array
- `test_owner_only_count_is_forty_two` → `test_owner_only_count_is_forty_five`, both asserts updated to `== 45`
- All 4 parity test functions green

### API Registration
- `promo_codes_router` imported and registered at prefix `/promo-codes` in `app/api/v1/router.py`
- Alphabetically sorted in import block (between payroll and pt-package-plans)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Pre-existing ruff errors in service.py blocked verification**
- **Found during:** Task 2 verification (`uv run ruff check app/modules/promo_codes/`)
- **Issue:** Two `RUF002` (ambiguous `−` MINUS SIGN in docstrings) and `SIM108` (if-else → ternary) errors existed in the original service.py before this plan. They caused the module-wide ruff check to fail.
- **Fix:** Replaced ambiguous `−` with `-` (HYPHEN-MINUS) in two docstrings; converted if/else to ternary operator.
- **Files modified:** `apps/backend/app/modules/promo_codes/service.py`
- **Commit:** 6e3250e4

**2. [Rule 1 - Bug] Pre-existing E501 in models.py**
- **Found during:** Task 2 verification
- **Issue:** Line 59 in models.py (discount_value comment) was 101 chars, exceeding the 100-char limit. Pre-existing before this plan.
- **Fix:** Added `# noqa: E501` to suppress (reformatting would change a comment unrelated to this plan's change).
- **Files modified:** `apps/backend/app/modules/promo_codes/models.py`
- **Commit:** 6e3250e4

**3. [Rule 1 - Bug] Service actor type was `User` ORM model (mypy error)**
- **Found during:** Task 3 verification (mypy on router.py)
- **Issue:** Service CRUD functions declared `actor: User` (ORM model). Routers pass `CurrentUser` (Protocol). mypy reported incompatible types.
- **Fix:** Changed service function signatures to use `CurrentUser` Protocol (from `app.core.dependencies`), matching all other service patterns (users/service.py, etc.).
- **Files modified:** `apps/backend/app/modules/promo_codes/service.py`
- **Commit:** 2249f9d1

**4. [Rule 1 - Bug] Import ordering in api/v1/router.py caused ruff I001**
- **Found during:** Task 3 ruff check
- **Issue:** `promo_codes_router` was imported between `payments_router` and `payroll_router` in alphabetical block; alphabetically `payroll` comes before `promo_codes`.
- **Fix:** Reordered to payments → payroll → promo_codes.
- **Files modified:** `apps/backend/app/api/v1/router.py`
- **Commit:** 2249f9d1

## Threat Surface Scan

No new threat surface beyond the plan's threat model. All mitigations applied:
- T-113-01: OWNER_ONLY write pairs enforced (parity test green)
- T-113-02: verify_csrf on all write routes, require_permission before verify_csrf (RBAC-04)
- T-113-03: UPPER-normalize + uq_promo_codes_code_alive IntegrityError → 409
- T-113-04: discount_value > 0 and percentage ≤ 10000 validated in schemas; DB CheckConstraints as defense-in-depth
- T-113-06: BackendSchemaBase extra='forbid' on all request DTOs

## Self-Check: PASSED

All key files verified present on disk:
- FOUND: apps/backend/alembic/versions/0072_promo_codes_description.py
- FOUND: apps/backend/app/modules/promo_codes/schemas.py
- FOUND: apps/backend/app/modules/promo_codes/repository.py
- FOUND: apps/backend/app/modules/promo_codes/router.py
- FOUND: .planning/phases/113-promo-codes-crud/113-01-SUMMARY.md

All commits verified in git log:
- FOUND: ebcbd3dd (migration + model)
- FOUND: 6e3250e4 (schemas + repository + service)
- FOUND: 2249f9d1 (router + RBAC parity)
