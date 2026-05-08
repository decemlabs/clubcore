---
phase: 25-memberships-freeze-backend
plan: 04
subsystem: api
tags: [memberships, freeze, schemas, router, rbac, fastapi, pydantic]

# Dependency graph
requires:
  - phase: 25-memberships-freeze-backend
    plan: 01
    provides: MembershipFreezePeriod ORM, freeze_days_limit_snapshot, freeze_days_limit, MEMBERSHIP_STATUS_TRANSITIONS populated, FreezeLimitExceededError, AlreadyFrozenError.
  - phase: 25-memberships-freeze-backend
    plan: 02
    provides: insert_freeze_period / get_open_freeze_period / compute_freeze_days_used / _freeze_days_used_subquery repository helpers.
provides:
  - MembershipStatus.FROZEN enum value (D-25-13)
  - FreezePeriodResponse schema (D-25-12)
  - MembershipResponse + 4 freeze projection fields (D-25-12)
  - MembershipPlanCreateRequest.freeze_days_limit + MembershipPlanResponse.freeze_days_limit (D-25-10)
  - POST /api/v1/memberships/{id}/freeze (MEM-FRZ-EP-01)
  - POST /api/v1/memberships/{id}/unfreeze (MEM-FRZ-EP-02)
  - cancel_membership docstring updated for frozen source (D-25-20)
affects: [25-03-service, 25-05-tests, 26-renewal, 28-frontend]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Pydantic immutability via inherited extra='forbid': MembershipPlanUpdateRequest left UNCHANGED so PATCH payloads with `freezeDaysLimit` are rejected with stock 422 (no service-layer guard needed)."
    - "Two new POST mutation endpoints follow RBAC-04 ordering precedent (require_permission Depends declared BEFORE verify_csrf Depends in signature; tests/integration/test_route_introspection.py enforces statically)."
    - "Wave 3 ordering: # type: ignore[attr-defined] markers on service.freeze_membership / service.unfreeze_membership callsites — service flow lands in Plan 25-03 (Wave 4); the marker is grep-verified as removed by 25-03's acceptance criteria."

key-files:
  created:
    - .planning/phases/25-memberships-freeze-backend/25-04-SUMMARY.md
  modified:
    - apps/backend/app/modules/memberships/schemas.py
    - apps/backend/app/modules/memberships/router.py

key-decisions:
  - "Wave 3 ordering resolution: chose `# type: ignore[attr-defined]` markers over a stub `raise NotImplementedError` in service.py — markers are localised to two router callsites and Plan 25-03 grep-verifies their removal as acceptance, whereas a stub would persist as a zombie service entry until Wave 4."
  - "MembershipPlanUpdateRequest left untouched per D-25-11 — Pydantic's inherited extra='forbid' is the immutability gate; adding a service-layer guard would be redundant and divergent from the duration_days precedent (Phase 16 D-04)."
  - "BackendSchemaBase alias_generator handles the snake_case -> camelCase wire conversion for all 5 new fields (freeze_days_limit_snapshot, freeze_days_used, freeze_days_remaining, current_freeze_period, freeze_days_limit) — verified via model_dump(by_alias=True) roundtrip."
  - "Both freeze + unfreeze endpoints use (CREATE, MEMBERSHIPS) (reception+owner) per CONTEXT D-25-19, NOT in OWNER_ONLY — matches REQUIREMENTS MEM-FRZ-EP-01/02 wording and mirrors create_membership permission shape."

patterns-established:
  - "Schema-first wave ordering for response surface changes: ship Pydantic field additions to a Response model BEFORE the service that returns those fields, so extra='forbid' (in BackendSchemaBase descendants where used) doesn't reject field additions at runtime in intermediate phases."

requirements-completed:
  - MEM-FRZ-01
  - MEM-FRZ-06
  - MEM-FRZ-EP-01
  - MEM-FRZ-EP-02
  - MEM-FRZ-EP-03

# Metrics
duration: 3min
completed: 2026-05-08
---

# Phase 25 Plan 04: Schemas + Router for Freeze Contract Summary

**Phase 25's user-visible API contract: 2 new POST endpoints (`/freeze`, `/unfreeze`), `MembershipStatus.FROZEN`, `FreezePeriodResponse` + 4 projection fields on `MembershipResponse`, and `freeze_days_limit` on the plan create/response schemas. Built on Plans 25-01 and 25-02; service flow lands in Plan 25-03 (Wave 4).**

## Performance

- **Duration:** ~3 min
- **Started:** 2026-05-08T20:42:13Z
- **Completed:** 2026-05-08T20:44:43Z
- **Tasks:** 2
- **Files modified:** 2 (no files created beyond SUMMARY.md)

## Accomplishments

- `MembershipStatus.FROZEN = "frozen"` added — `?status=frozen` query filter accepted automatically; existing consumers (filters, response serialisation) handle the new value via StrEnum.
- `FreezePeriodResponse(ResponseData)` introduced with the 5 fields (`id`, `started_at`, `started_by`, `ended_at`, `ended_by`) per D-25-12; docstring documents the open-period invariant when surfaced as `current_freeze_period`.
- `MembershipResponse` extended with 4 freeze projection fields appended in declaration order: `freeze_days_limit_snapshot`, `freeze_days_used`, `freeze_days_remaining`, `current_freeze_period`. JSON wire emits camelCase via `BackendSchemaBase.alias_generator` (verified via `model_dump(by_alias=True)` roundtrip emitting `freezeDaysLimitSnapshot`).
- `MembershipPlanCreateRequest` gains `freeze_days_limit: int = Field(ge=1, le=365)` (no default — owner-explicit at creation) per D-25-10. `MembershipPlanResponse` mirrors with `freeze_days_limit: int`.
- `MembershipPlanUpdateRequest` deliberately left untouched (D-25-11) — `extra='forbid'` (inherited from `BackendSchemaBase`) auto-rejects PATCH payloads containing `freezeDaysLimit` with a stock 422; this preserves MEM-FRZ-01 immutability without a parallel service-layer guard.
- `POST /api/v1/memberships/{id}/freeze` registered (`memberships_router`): `(CREATE, MEMBERSHIPS)` permission, `verify_csrf`, 200 OK with `ResponseEnvelope[MembershipResponse]`, summary lists the 3 expected 409 codes (`freeze_limit_exceeded`, `already_frozen`, `invalid_transition`).
- `POST /api/v1/memberships/{id}/unfreeze` registered with the same shape, summary calls out `invalid_transition` only.
- RBAC-04 ordering preserved on both new endpoints: `Depends(require_permission(...))` declared BEFORE `Depends(verify_csrf)`. `tests/integration/test_route_introspection.py` passes (3/3) statically asserting this for every mutation endpoint.
- `cancel_membership` route: signature byte-identical (D-25-20); docstring extended to mention frozen-source acceptance (closes open period without `end_date` extension; emits `membership_unfrozen` with `days_added=0` BEFORE `membership_cancelled` in the same UoW; Owner-only via existing `(CANCEL, MEMBERSHIPS) ∈ OWNER_ONLY`).
- Module docstring updated with the 2 new Phase 25 routes appended to the route surface block.

## Task Commits

1. **Task 1: schemas.py extensions (FROZEN enum, FreezePeriodResponse, 4 MembershipResponse fields, freeze_days_limit on plan request/response)** — `eaeeeb5` (feat)
2. **Task 2: router.py — POST /freeze + POST /unfreeze + cancel_membership docstring** — `4b7bc21` (feat)

## Files Created/Modified

- `apps/backend/app/modules/memberships/schemas.py` — added `FROZEN` enum value, `FreezePeriodResponse` class, 4 projection fields on `MembershipResponse`, `freeze_days_limit` on `MembershipPlanCreateRequest` + `MembershipPlanResponse`. Total +25 LOC.
- `apps/backend/app/modules/memberships/router.py` — added 2 new mutation endpoints (`freeze_membership`, `unfreeze_membership`), updated module docstring with Phase 25 endpoint surface block, extended `cancel_membership` docstring for frozen-source acceptance per D-25-20. Total +79 LOC, -3 LOC (docstring rewrite).

## Decisions Made

- Followed plan as specified — D-25-10..13, D-25-19, D-25-20 implemented verbatim.
- **Wave 3 ordering — chose `# type: ignore[attr-defined]` markers (option 1)** at the two `service.freeze_membership` / `service.unfreeze_membership` callsites. Rationale: localised to router.py (2 lines), grep-verified for removal by Plan 25-03's acceptance criteria, and avoids leaving a stub `raise NotImplementedError` body in `service.py` that would survive past Wave 4 if Plan 03's first task missed it. Each marker carries a comment `# Wave 4: service.freeze_membership defined in Plan 03` so the intent is self-documenting.
- Summary string for `/freeze` endpoint split across two adjacent string literals (Python implicit concatenation) to keep within ruff's 100-char line width — preserves the full "(reception+owner; 409 freeze_limit_exceeded / already_frozen / invalid_transition)" wording without a `# noqa: E501` opt-out.

## Deviations from Plan

None — plan executed exactly as written. The Wave 3 ordering resolution (`# type: ignore`) was an explicit branch documented in the plan's `<wave_3_ordering_note>`; the choice between options 1 and 2 was the only freedom granted.

## Issues Encountered

- None. Both tasks were single-file edits with no surrounding refactor required. The acceptance criteria's grep checks for `freeze_days_limit_snapshot: int` and `current_freeze_period: FreezePeriodResponse | None` (and the negative grep `freezeDaysLimit` returning 0) all matched on the first edit.

## Verification Evidence

### Task 1 (schemas)
- `uv run python -c "...; assert MembershipStatus.FROZEN == 'frozen'; ... print('OK')"` — exits 0.
- `uv run python -c "from app.modules.memberships.schemas import MembershipResponse; m = MembershipResponse.model_construct(freeze_days_limit_snapshot=14); d = m.model_dump(by_alias=True, exclude_unset=True); assert 'freezeDaysLimitSnapshot' in d, d"` — exits 0 (alias_generator roundtrip OK).
- `uv run mypy app/modules/memberships/schemas.py` — `Success: no issues found in 1 source file`.
- `uv run ruff check app/modules/memberships/schemas.py` — `All checks passed!`.
- All grep acceptance checks pass: `FROZEN = "frozen"` (1), `class FreezePeriodResponse(ResponseData)` (1), `freeze_days_limit_snapshot: int` (1), `freeze_days_used: int` (1), `freeze_days_remaining: int` (1), `current_freeze_period: FreezePeriodResponse | None` (1), `freeze_days_limit: int = Field(ge=1, le=365)` (1), `freezeDaysLimit` (0 — no manual aliasing), `MembershipPlanUpdateRequest` does not contain `freeze_days_limit` (0).

### Task 2 (router)
- `uv run mypy app/modules/memberships/schemas.py app/modules/memberships/router.py` — `Success: no issues found in 2 source files`.
- `uv run ruff check app/modules/memberships/schemas.py app/modules/memberships/router.py` — `All checks passed!`.
- `uv run pytest tests/integration/test_route_introspection.py -x -q` — `3 passed in 0.03s` (RBAC-04 ordering verified statically for all mutation endpoints, including the 2 new ones).
- All grep acceptance checks pass: `"/{membership_id}/freeze"` (1), `"/{membership_id}/unfreeze"` (1), `async def freeze_membership` (1), `async def unfreeze_membership` (1), `require_permission(Action.CREATE, Resource.MEMBERSHIPS)` (3 — includes existing `create_membership` + 2 new endpoints; ≥2 required).
- RBAC-04 dependency ordering verified by AWK extraction: in both `freeze_membership` and `unfreeze_membership` signatures, `require_permission` line precedes `verify_csrf` line.
- `cancel_membership` signature byte-identical: `git diff` shows only docstring text additions and the 2 new endpoint definitions appended after the route; no `def cancel_membership(` or parameter list lines deleted.

### Plan-level verify gates
- `uv run mypy app/modules/memberships/schemas.py app/modules/memberships/router.py` — clean.
- `uv run ruff check app/modules/memberships/` — clean (entire module, including unmodified files).
- `uv run pytest tests/integration/test_route_introspection.py -x -q` — 3/3 passed.
- Full pytest is intentionally NOT run at this gate — service flows arrive in Plan 25-03 (Wave 4); Plan 25-05 (Wave 5) runs the integration suite.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- **Plan 25-03 (Wave 4):** can implement `service.freeze_membership` and `service.unfreeze_membership` (and extend `service.cancel_membership` for frozen source) against the 5 new schema fields and the 2 new router endpoints. Plan 03's acceptance criteria includes grep-verifying that the two `# type: ignore[attr-defined]` markers are removed from `router.py` once the service definitions land.
- **Plan 25-05 (Wave 5):** can compose the 7 planned freeze integration tests (cycle, limit, race, resolver, cancel-during-freeze, endpoints RBAC matrix, and the days_used computation) — all required schemas and routes are now present.
- **Phase 28 (FE drift gate):** OpenAPI surface now exposes 2 new POST operations + `FreezePeriodResponse` schema + 4 new `MembershipResponse` fields + `freeze_days_limit` on `MembershipPlanCreateRequest` and `MembershipPlanResponse`. `apps/backend/openapi.json` regen deferred to Phase 28 per D-25-25 (CI drift gate is milestone-end, not per-commit).
- No blockers.

## Self-Check: PASSED

**Files verified:**
- FOUND: apps/backend/app/modules/memberships/schemas.py (FreezePeriodResponse + 4 freeze fields + FROZEN enum + freeze_days_limit on plan request/response present)
- FOUND: apps/backend/app/modules/memberships/router.py (POST /{id}/freeze + POST /{id}/unfreeze present; cancel docstring mentions frozen source)
- FOUND: .planning/phases/25-memberships-freeze-backend/25-04-SUMMARY.md (this file)

**Commits verified:**
- FOUND: eaeeeb5 (Task 1)
- FOUND: 4b7bc21 (Task 2)

---
*Phase: 25-memberships-freeze-backend*
*Completed: 2026-05-08*
