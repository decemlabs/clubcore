---
phase: 25-memberships-freeze-backend
plan: 05
subsystem: memberships
tags: [test, backend, freeze, state-machine, integration, ci-gates]
requires:
  - 25-01 (migration 0008_freeze + ORM)
  - 25-02 (repository helpers + freeze period)
  - 25-03 (service-layer freeze cycle)
  - 25-04 (schemas + endpoints)
provides:
  - 16-cell exhaustive state machine coverage
  - Pure-helper ceil rounding unit test
  - 6 integration test files (cycle, limit, endpoints, race, resolver, cancel-during-freeze)
  - Phase 25 backend test suite green (658 tests pass)
  - All CI gates green (ruff, mypy, lint-imports, alembic check)
affects:
  - apps/backend/tests/unit/memberships/* (state machine extension)
  - apps/backend/tests/integration/memberships/* (6 new files + conftest extension)
  - apps/backend/tests/integration/{visits,telegram_bot,workers}/* (Plan 25-04 fixture repair)
  - apps/backend/tests/unit/memberships/test_schemas.py (deferred fixture fold-in)
  - apps/backend/app/modules/memberships/{repository,service}.py (Rule 1/3 fixes)
  - apps/backend/app/core/permissions.py (E501 cleanup)
tech-stack:
  added: []
  patterns:
    - Race-test pattern via db_session_real_commit + asyncio.gather (Phase 19 visits mirror)
    - 4x4 state machine matrix expansion via parametrize
    - Telegram /checkin oracle-safe DM verification
    - Audit dual-emit ordering invariant (membership_unfrozen → membership_cancelled)
    - explicit-dict response projection (replaces broken from_attributes pattern)
key-files:
  created:
    - apps/backend/tests/unit/memberships/test_freeze_days_computation.py
    - apps/backend/tests/integration/memberships/test_freeze_cycle.py
    - apps/backend/tests/integration/memberships/test_freeze_limit.py
    - apps/backend/tests/integration/memberships/test_freeze_endpoints.py
    - apps/backend/tests/integration/memberships/test_freeze_race.py
    - apps/backend/tests/integration/memberships/test_freeze_resolver.py
    - apps/backend/tests/integration/memberships/test_cancel_during_freeze.py
  modified:
    - apps/backend/tests/unit/memberships/test_state_machine.py
    - apps/backend/tests/unit/memberships/test_schemas.py
    - apps/backend/tests/integration/memberships/conftest.py
    - apps/backend/tests/integration/memberships/test_*_crud.py
    - apps/backend/tests/integration/memberships/test_*_rbac.py
    - apps/backend/tests/integration/memberships/test_*_audit.py
    - apps/backend/tests/integration/memberships/test_plans_*.py
    - apps/backend/tests/integration/memberships/test_audit_writes.py
    - apps/backend/tests/integration/visits/conftest.py
    - apps/backend/tests/integration/visits/test_visits_concurrent.py
    - apps/backend/tests/integration/telegram_bot/test_checkin_handler.py
    - apps/backend/tests/integration/telegram_bot/test_checkin_dm_days_remaining.py
    - apps/backend/tests/integration/workers/conftest.py
    - apps/backend/tests/unit/test_permissions.py
    - apps/backend/app/modules/memberships/service.py
    - apps/backend/app/modules/memberships/repository.py
    - apps/backend/app/core/permissions.py
decisions:
  - Audit ordering for cancel-during-freeze cannot be asserted via DB-level chronology (UUID PK + Postgres now() returns tx-start), so the test asserts SET-equality of actions plus the days_added=0 sentinel as the unambiguous discriminator, and cross-tx chronology (freeze tx < cancel tx) where created_at differs.
  - The freezeDaysUsed display value at the moment of freeze is 0 (SQL CEIL of ~0 seconds), not 1; the max(1, ...) clamp only fires on unfreeze for the days_added audit value. Test docstring documents this.
  - Test simulates elapsed freeze time by mutating started_at directly via db_session (avoids freezegun per Phase 24 D-24-06); buffer of +30 seconds prevents now()-advance during the unfreeze HTTP roundtrip from pushing delta over 5d → ceil=6.
metrics:
  duration: ~1.5h
  completed: 2026-05-09
  tasks_completed: 4
  files_created: 7
  files_modified: 19
  commits: 4
  tests_added: 28
  total_tests_passing: 658
---

# Phase 25 Plan 05: Test Coverage + CI Gate Verification Summary

Add the test coverage that proves Phase 25 freeze cycle behaviour: 16-cell state machine matrix extension, pure-helper ceil rounding test, and 6 integration tests covering happy path, limit exhaustion, race, resolver rejection, cancel-during-freeze, and endpoint RBAC/shape. Also fix several pre-existing breakages introduced by Plan 25-04 that prevented the backend test suite from running cleanly.

## What Was Built

**Unit tests (Task 1):**

- `tests/unit/memberships/test_state_machine.py` extended from 9 cells to 16 cells (4 sources × 4 actions). 5 allowed transitions, 11 invalid_transition cells. Imports `_assert_can_freeze` and `_assert_can_unfreeze` thin wrappers. `test_central_helper_matches_per_helper_guards` extended to cover the 3 new Phase 25 edges.
- `tests/unit/memberships/test_freeze_days_computation.py` — pure-function tests for `max(1, math.ceil(delta_seconds / 86400))` at boundary cases (zero, exact, fractional, just-over-exact, multi-period sum). Asserts byte-stable parity with the SQL aggregate `CEIL(EXTRACT(EPOCH FROM ...) / 86400)`.

**Integration tests — happy paths + endpoints (Task 2):**

- `test_freeze_cycle.py` (MEM-FRZ-TEST-01): full E2E sell→freeze→simulate-elapsed→unfreeze; asserts end_date += 5 days, freezeDaysUsed=5, freezeDaysRemaining=9, audit pair (membership_frozen + membership_unfrozen with days_added=5).
- `test_freeze_limit.py` (MEM-FRZ-TEST-02): three boundary tests for 409 freeze_limit_exceeded — exactly at limit (14 days closed → blocks), above limit (15 → blocks with used=15), below limit (10 days closed → succeeds).
- `test_freeze_endpoints.py` (MEM-FRZ-EP-01..03): 12 tests covering RBAC matrix (anonymous→401, reception→200, owner→200), CSRF enforcement (missing header→403), response shape (4 camelCase keys: freezeDaysLimitSnapshot, freezeDaysUsed, freezeDaysRemaining, currentFreezePeriod), currentFreezePeriod object shape, GET-after-unfreeze nullability, invalid_transition guards on cancelled→freeze and active→unfreeze, and 404 membership_not_found.

**Integration tests — race + resolver + cancel-during-freeze (Task 3):**

- `test_freeze_race.py` (MEM-FRZ-TEST-03): 5 parallel POST /freeze on same membership; asserts exactly 1×200 + 4×409 already_frozen, exactly 1 open period in DB, exactly 1 membership_frozen audit row (losing tasks rollback before emit). Mirrors `tests/integration/visits/test_visits_concurrent.py` pattern with constraint name + endpoint swapped. Uses local `db_session_real_commit` fixture added to memberships conftest.
- `test_freeze_resolver.py` (MEM-FRZ-06): 3 tests — D-25-17 invariant (resolve_active_membership_by_client returns None for frozen client), reception POST /api/v1/visits → 409 no_active_membership, and Telegram /checkin → generic Russian DM (oracle-safe per Phase 20 D-5; same DM as a stranger).
- `test_cancel_during_freeze.py` (MEM-FRZ-07): cancel-during-freeze emits both membership_unfrozen (days_added=0 sentinel) and membership_cancelled in same UoW; end_date UNCHANGED from pre-freeze; reception forbidden from cancelling (CANCEL,MEMBERSHIPS in OWNER_ONLY).

**Verification (Task 4):**

- Full test suite: 658 tests pass (`pytest tests/`).
- ruff: clean (0 errors).
- mypy: clean (71 source files).
- lint-imports: 3 contracts kept, 0 broken.
- alembic check: no new upgrade operations detected.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 — Bug] `_build_membership_response` raised ValidationError on every freeze/unfreeze response**

- **Found during:** Task 2 (test_freeze_cycle first run).
- **Issue:** The Phase 25 D-25-12 "locked projection mechanism" used `MembershipResponse.model_validate(membership, from_attributes=True).model_copy(update=overlay)`. But Pydantic raises `ValidationError: freeze_days_used / freeze_days_remaining / current_freeze_period Field required` because `model_validate(ORM, from_attributes=True)` validates the ORM attributes directly — and those 3 fields are NOT ORM columns. `model_copy(update=...)` only fires AFTER validation succeeds, so the overlay is never applied.
- **Fix:** Replaced with explicit-dict construction (lists every ORM field by name plus the 3 service-computed freeze fields) and a single `MembershipResponse.model_validate(payload)` call. Same fix applied to `list_memberships` per-row projection (which had the identical broken pattern).
- **Files modified:** `apps/backend/app/modules/memberships/service.py`
- **Commits:** 97077ac, e3b8511

**2. [Rule 1 — Bug] `repository.insert_plan` and `repository.insert_membership` did not pass freeze_days_limit / freeze_days_limit_snapshot**

- **Found during:** Task 4 (full pytest run, NotNullViolationError on `freeze_days_limit` and `freeze_days_limit_snapshot`).
- **Issue:** Plan 25-04 added `freeze_days_limit` to `MembershipPlanCreateRequest` and `freeze_days_limit_snapshot` to the Membership model + DB column NOT NULL, but the production INSERT helpers in repository.py never read those fields. Every POST /api/v1/membership-plans and every POST /api/v1/memberships hit NOT NULL violation.
- **Fix:** Added `freeze_days_limit=data.freeze_days_limit` to insert_plan ORM construction; added `freeze_days_limit_snapshot=plan.freeze_days_limit` to insert_membership.
- **Files modified:** `apps/backend/app/modules/memberships/repository.py`
- **Commit:** e3b8511

**3. [Rule 3 — Blocking] Test integration fixtures missing freeze_days_limit / freeze_days_limit_snapshot**

- **Found during:** Task 2 (test_freeze_cycle first run, then full suite).
- **Issue:** 7 memberships integration test files hardcoded `VALID_PLAN` literal without `freezeDaysLimit`. Several visits, telegram_bot, and workers test seeds constructed `MembershipPlan` and `Membership` ORM rows without the required new fields. All resulted in 422 validation errors or NotNullViolation on test setup.
- **Fix:** Added `"freezeDaysLimit": 14` to all VALID_PLAN literals; added `freeze_days_limit=14` and `freeze_days_limit_snapshot=plan.freeze_days_limit` to all raw ORM seeds across 5 test packages. Also folded in the deferred test_schemas.py fixture failure (Plan 25-03's deferred-items.md item) — added freeze_days_limit=14 to all `MembershipPlanCreateRequest` constructions and the 4 freeze fields to MembershipResponse fixtures.
- **Files modified:** 12 test files across `tests/integration/memberships/`, `tests/integration/visits/`, `tests/integration/telegram_bot/`, `tests/integration/workers/`, plus `tests/unit/memberships/test_schemas.py`.
- **Commits:** 2731452, 97077ac, e3b8511

**4. [Rule 1 — Bug] Resolver test settings mutation leaked across the suite**

- **Found during:** Task 4 (test_visits_meta failed when run after test_freeze_resolver).
- **Issue:** First draft of test_freeze_resolver mutated `settings.gym_hours_start = time(0, 0)` directly. Settings is cached via lru_cache, so the mutation persisted into later tests; test_visits_meta_200_reception expected default `07:00` and got `00:00`.
- **Fix:** Switched to `monkeypatch.setattr(settings, "gym_hours_start", time(0, 0))` so the mutation is undone at test teardown (mirrors test_checkin_handler.py:_open_gym_hours pattern).
- **Files modified:** `apps/backend/tests/integration/memberships/test_freeze_resolver.py`
- **Commit:** e3b8511

**5. [Rule 3 — Blocking] Pre-existing E501 ruff errors blocked CI gate verification**

- **Found during:** Task 4 (ruff check exited with errors).
- **Issue:** 2 pre-existing E501 line-length violations in `app/core/permissions.py:45` (PROFILE comment, 112 chars) and `tests/unit/test_permissions.py:40` (Verbatim comment, 111 chars). Both pre-date Phase 25; logged in deferred-items.md by Plan 25-01. Blocked Task 4 acceptance criterion `ruff check ... exits 0`.
- **Fix:** Trimmed both comments to ≤100 chars without changing semantics.
- **Files modified:** `apps/backend/app/core/permissions.py`, `apps/backend/tests/unit/test_permissions.py`
- **Commit:** e3b8511

### Test Naming Notes

- `test_freeze_response_currentFreezePeriod_object_shape` and `test_membership_get_after_unfreeze_currentFreezePeriod_null` use camelCase identifiers because they explicitly reference the camelCase API field name `currentFreezePeriod`. Added `# noqa: N802` with rationale rather than rename — matches the convention used elsewhere (e.g. test_schemas.py asserting wire format keys).

### Audit Ordering Test Adjustment

The PATTERNS.md and CONTEXT.md guidance to assert "audit_log.id auto-increment provides chronological ordering" was incorrect: `AuditLog` uses `UUIDPkMixin` (gen_random_uuid()), so id-ordering is random across rows. Postgres `now()` returns transaction-start, so same-UoW emits share `created_at`. The test instead asserts:

1. SET-equality of the 3 expected actions (membership_frozen, membership_unfrozen, membership_cancelled).
2. Cross-tx chronology where created_at differs (frozen tx < cancel tx).
3. The `days_added=0` sentinel on the unfrozen row as the unambiguous cancel-during-freeze discriminator (implicitly verifies the unfrozen emit is part of the cancel UoW, not the freeze UoW).

The D-25-09 invariant — "unfrozen MUST be emitted BEFORE cancelled in the same UoW" — is held by the service code and verified at READ-time by the lexical order of the `audit.emit()` calls in service.py:558 and service.py:584. The test cannot inspect the in-transaction emit order post-commit; it inspects the OUTCOME (both rows present, both in cancel UoW).

## Phase 25 — Plan 25-05 Completion State

All 4 tasks complete. 6 integration test files + 1 new unit test file + state machine matrix extended to 16 cells. Phase 25 test contributions:

| Wave | Plan  | Tests added |
|------|-------|-------------|
| 1    | 25-01 | 0 (migration + ORM)         |
| 2    | 25-02 | 2 (repository helpers — freeze_helpers.py)  |
| 3    | 25-03 | 0 (service layer — covered here)  |
| 4    | 25-04 | 0 (schemas + endpoints — covered here)  |
| 5    | 25-05 | 28 (16-cell matrix + 9 ceil + 12 endpoints + 3 limit + 3 resolver + 2 cancel + 1 race + 1 cycle = 47 tests in new files; 16 of those are parametrize cells of one test) |

Total backend test suite: **658 tests passing** (up from ~610 pre-Phase-25). Phase 29 milestone target was ≥600 — exceeded.

## Self-Check: PASSED

- [x] `apps/backend/tests/unit/memberships/test_state_machine.py` exists and contains `("active", "freeze", "ok")`, `("frozen", "unfreeze", "ok")`, `("frozen", "cancel", "ok")`, ≥11 `"invalid_transition"` cells.
- [x] `apps/backend/tests/unit/memberships/test_freeze_days_computation.py` exists and contains `math.ceil`.
- [x] All 6 new integration test files exist and pass under pytest.
- [x] `git log --all | grep 2731452` → present (Task 1 commit).
- [x] `git log --all | grep 97077ac` → present (Task 2 commit).
- [x] `git log --all | grep 3878ae4` → present (Task 3 commit).
- [x] `git log --all | grep e3b8511` → present (Rule fixes commit).
- [x] Full pytest run: 658 tests pass, 0 failed.
- [x] ruff check: clean.
- [x] mypy: clean.
- [x] lint-imports: 3 contracts kept, 0 broken.
- [x] alembic check: no new upgrade operations.
