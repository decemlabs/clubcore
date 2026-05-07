---
phase: 16-membership-plans-catalog-backend
plan: "02"
subsystem: backend/memberships
tags: [backend, pydantic, schemas, dto, validation, exceptions]
dependency_graph:
  requires:
    - "apps/backend/app/core/schemas.py (BackendSchemaBase + ResponseData)"
    - "apps/backend/app/core/pagination.py (PageQuery)"
    - "apps/backend/app/core/exceptions.py (ConflictError + NotFoundError)"
  provides:
    - "MEM-PLAN-EP-01..03 DTO surface for Plan 03 (repository/service) and Plan 04 (router)"
    - "PlanNameExistsError + PlanNotFoundError for Plan 03 service IntegrityError translation"
  affects:
    - "apps/backend/app/modules/memberships/service.py (Plan 03 — imports PlanNameExistsError, PlanNotFoundError)"
    - "apps/backend/app/modules/memberships/router.py (Plan 04 — imports schemas for response_model)"
    - "apps/backend/tests/unit/memberships/test_schemas.py (Plan 05 — validates D-01/D-04/D-05/D-06/D-07/D-08/D-09)"
tech_stack:
  added: []
  patterns:
    - "Pydantic v2 BackendSchemaBase (extra='forbid') for inbound DTOs — extra field rejection covers D-04 immutable duration_days"
    - "model_validator(mode='before') explicit-null guard (D-05) — mirrors clients D-01"
    - "field_validator(mode='before') trim-only normalization (D-01) — preserves casing"
    - "StrEnum module-local sort enum (CD-04) — mirrors ClientSort location"
key_files:
  created:
    - apps/backend/app/modules/memberships/schemas.py
  modified:
    - apps/backend/app/core/exceptions.py
decisions:
  - "D-03: PlanNameExistsError and PlanNotFoundError aggregate in core/exceptions.py (not per-module)"
  - "D-04: BackendSchemaBase extra='forbid' covers duration_days immutability — no custom validator needed"
  - "D-05: explicit-null model_validator rejects {key: null} with canonical message; caller omits key to leave field unchanged"
  - "D-07: PATCH-able fields are name, price_kopecks, active only; duration_days intentionally absent from UpdateRequest"
  - "D-09: MembershipPlanListQuery has NO q field — catalog <=20 rows, search not justified in Phase 16"
metrics:
  duration_minutes: 8
  completed_date: "2026-05-07"
  tasks_completed: 2
  tasks_total: 2
  files_created: 1
  files_modified: 1
---

# Phase 16 Plan 02: Membership Plan DTOs and Domain Exceptions Summary

**One-liner:** Pydantic v2 DTOs (Create/Update/Response/ListQuery + MembershipPlanSort) and two domain exceptions (PlanNotFoundError 404, PlanNameExistsError 409) wiring the wire-contract surface that Plans 03 and 04 consume.

## What Was Built

### core/exceptions.py — Two new domain exceptions

- `PlanNotFoundError(NotFoundError)` — code `plan_not_found`, status 404. Raised when GET/PATCH/DELETE references a non-existent or soft-deleted plan.
- `PlanNameExistsError(ConflictError)` — code `plan_name_exists`, status 409. Raised by service IntegrityError translation when `uq_membership_plans_name_alive` constraint fires on POST/PATCH.

Both follow the `PhoneExistsError` / `ClientNotFoundError` shape exactly. Wire codes are locked — Plan 04 router exception handler maps `AppError.code` into the response envelope.

### memberships/schemas.py — Five DTO classes

**MembershipPlanSort (StrEnum):** `CREATED_AT_DESC` (default), `NAME_ASC`. Module-local per CD-04, mirrors `ClientSort` location.

**MembershipPlanCreateRequest(BackendSchemaBase):**
- Fields: `name` (str, min=1, max=120), `duration_days` (int, ge=1, le=3650), `price_kopecks` (int, ge=0, le=10**11), `active` (bool, default=True)
- D-01: `_trim` field_validator (mode='before') on `name` — strips whitespace, preserves casing; Pydantic min_length=1 fires after trim so `"   "` becomes `""` and rejects
- D-06: bounds are defence-in-depth atop DB CHECK constraints

**MembershipPlanUpdateRequest(BackendSchemaBase):**
- Fields: `name | None`, `price_kopecks | None`, `active | None` — D-07
- `duration_days` deliberately absent — `BackendSchemaBase.extra='forbid'` returns stock 422 "Extra inputs are not permitted" with the rejected key name when payload contains `durationDays` — D-04
- `_reject_explicit_null` model_validator (mode='before') — D-05 canonical message: "Explicit null not supported for: [...]. Omit the key to leave the field unchanged."
- `_trim` field_validator on `name` — D-01

**MembershipPlanResponse(ResponseData):**
- Fields: `id`, `name`, `duration_days`, `price_kopecks`, `active`, `created_at`, `updated_at`
- `deleted_at` intentionally omitted — soft-deleted rows are 404'd at repository boundary

**MembershipPlanListQuery(PageQuery):**
- Inherits `page` (default=1) and `page_size` (default=20, max=100) from PageQuery
- `active: bool | None = None` — optional filter; omit = return both active and inactive alive plans (D-08)
- `sort: MembershipPlanSort = CREATED_AT_DESC` — D-08
- No `q` field — D-09

## Key Implementation Notes

- `BackendSchemaBase.extra='forbid'` is the mechanism for D-04 — cleaner than an explicit field+validator that always raises
- `from __future__ import annotations` is not needed in schemas.py (no PaginatedData generics requiring PEP 563 deferred evaluation); it was included per template but the import block is minimal
- Import-linter contracts unchanged — `app.modules.memberships.schemas` consumes only `app.core.*` symbols

## Decisions Made

- D-04 coverage via `extra='forbid'`: `BackendSchemaBase` config eliminates the need for any `duration_days`-specific validator in `MembershipPlanUpdateRequest` — Pydantic itself names the rejected key in the 422 response, making the error self-documenting
- No `InvalidPlanError` 422 class added — Pydantic stock 422 covers all bound violations (D-06) and the plan explicitly prohibits dead code

## Commits

| Task | Commit | Description |
|------|--------|-------------|
| Task 1 | 3b09eb2 | feat(16-02): add PlanNotFoundError and PlanNameExistsError to core/exceptions.py |
| Task 2 | 83c54c8 | feat(16-02): create memberships/schemas.py with all DTOs and Sort enum |

## Deviations from Plan

None — plan executed exactly as written. The `duration_days` grep count of 5 (vs plan's expected 1) is because the docstrings and MembershipPlanResponse legitimately reference the term; the acceptance criterion spirit (not a field in UpdateRequest) is fully met.

## Verification Results

- All automated smoke tests pass (D-01/D-04/D-05/D-06/D-08 spot-checks from plan verification step)
- `ruff check .` — 0 errors (1 auto-fixed: I001 import sort order)
- `mypy app/` — 0 errors across 62 source files
- `lint-imports` — all contracts KEPT (62 files, 94 dependencies analyzed)
- `git diff --exit-code apps/backend/openapi.json` — unchanged (no router wiring in this plan)

## Known Stubs

None. Both files ship complete, functional code with no placeholders.

## Threat Flags

None. All 6 threats from the plan's threat model are mitigated by the implementation:
- T-16-02-01: mass assignment covered by `extra='forbid'` on BackendSchemaBase
- T-16-02-02: whitespace injection covered by `_trim` validator
- T-16-02-03: deleted_at omitted from MembershipPlanResponse
- T-16-02-04: price ceiling `le=10**11` in schema layer
- T-16-02-05: explicit null rejected by `_reject_explicit_null` model_validator
- T-16-02-06: RBAC deferred to Plan 04 router (accepted)

## Self-Check: PASSED

- `/Users/andre/Workspace/Development/clubcore/apps/backend/app/modules/memberships/schemas.py` — FOUND
- `/Users/andre/Workspace/Development/clubcore/apps/backend/app/core/exceptions.py` (modified) — FOUND
- commit 3b09eb2 — FOUND
- commit 83c54c8 — FOUND
