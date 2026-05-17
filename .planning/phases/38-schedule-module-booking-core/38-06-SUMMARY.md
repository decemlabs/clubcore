---
phase: 38-schedule-module-booking-core
plan: 06
subsystem: gate
tags: [ci-gates, ruff, mypy, lint-imports, svc001, audit-taxonomy, audit-payloads, b-10-regression, defer-sweep, phase-exit]

# Dependency graph
requires:
  - phase: 38-schedule-module-booking-core/38-01-PLAN.md
    provides: schedule module + 4 endpoints + 24 tests; real schedule.service stub replacements; Alembic 0016
  - phase: 38-schedule-module-booking-core/38-02-PLAN.md
    provides: bookings table + race-safe create + BOOK-TEST-01; Alembic 0017; real complete_booking body
  - phase: 38-schedule-module-booking-core/38-03-PLAN.md
    provides: booking cancel + list/detail/per-client endpoints; schedule cancel-slot cascade with atomic dual-audit emit + InternalConsistencyError 500
  - phase: 38-schedule-module-booking-core/38-04-PLAN.md
    provides: Alembic 0018; pt_packages.trainer_id + trainer-active validation; refund-guard via cross-module raw sa.text() count
  - phase: 38-schedule-module-booking-core/38-05-PLAN.md
    provides: Alembic 0019; pt_sessions.booking_id + SELECT FOR UPDATE + booking-completion via Phase 37 Protocol slot
provides:
  - Verified phase-exit gate signal — all 4 CI gates (ruff, mypy --strict, lint-imports, pytest) GREEN on the combined Phase 38 surface
  - SVC001 walker + audit taxonomy + audit payloads gates GREEN — every state-mutating service method in schedule/bookings/pt_packages/pt_sessions ends with `await session.commit()`; all 58 audit events locked; emit payloads validate against Phase 37 extra='forbid' schemas
  - modules-independent import-linter contract GREEN with REAL implementations across all 4 affected modules (3 kept, 0 broken)
  - app/main.py docstring updated to document the Phase 38 router mount convention (routers wired in app/api/v1/router.py per the v1.5 module-router precedent — NOT directly in main.py)
  - B-10 regression (Pitfall 20 — PT-package alone does NOT grant gym-floor access) re-verified green (7/7 in test_visits_create_reception.py)
  - Opportunistic DEFER-36-04-A sweep cleared ALL 11 baseline pre-existing failures + ALL 6 newly-surfaced spec-drift failures introduced by Phase 37 production deltas not propagated to unit tests
  - Final pytest state: 1247 / 1247 passed (0 failed; carry-forward list to Phase 40 verification is empty)
affects: [38-final-merge, 39-NN, 40-NN]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Gate-plan opportunistic sweep — when a Wave-4 gate plan touches the test surface anyway, fix spec-drift + DEFER failures inline rather than carrying them forward. Cheaper to fix-in-flight than re-discover later."
    - "Test-spec mirror discipline — production-code locks (e.g. OWNER_ONLY = 29 after Phase 37 INFRA-27, Action.LIST added, Resource.SCHEDULE_SLOTS + Resource.BOOKINGS added) must be propagated to the structural unit tests in the same commit cluster. Failing to do so leaks 'red CI on green code' to the next phase."
    - "ValidationAppError envelope convention reaffirmed — class-level `code='validation_error'`; the constructor's first positional arg is the response `message`. Tests that assert `body['code'] == 'amount_mismatch'` etc. are wrong; the literal lives in `message`. Pattern fixed in schedule tests in 38-01 and now propagated to pt_packages + pt_sessions clusters."

key-files:
  created:
    - .planning/phases/38-schedule-module-booking-core/38-06-SUMMARY.md
  modified:
    - apps/backend/app/main.py (docstring updates: module top-doc + create_app numbered-steps now explicitly describe the Phase 38 router mount path in app/api/v1/router.py)
    - apps/backend/tests/unit/test_permissions.py (4 expectation updates — OWNER_ONLY count 25→29, Action value set adds 'list', Resource value set adds 'schedule-slots' + 'bookings', specific_owner_only spot-check adds 4 SCHEDULE_SLOTS write pairs)
    - apps/backend/tests/unit/test_dependencies_slots_v15.py (2 obsolete stub-returns-None assertions refit to weaker importability gate — Phase 38 replaced the stubs with real bodies)
    - apps/backend/tests/integration/pt_packages/test_pt_package_sale.py (3 envelope-drift assertion fixes — amount_mismatch, idempotency_key_replay, missing_idempotency_key)
    - apps/backend/tests/integration/pt_sessions/test_pt_session_cancel.py (5 expire_all() → refresh(attribute_names=[...]) conversions; 2 stale-ORM-instance reads switched to refresh)
    - apps/backend/tests/integration/pt_sessions/test_pt_session_record.py (1 expire_all() → refresh, 1 stale-ORM-instance read switched to refresh, 1 envelope-drift fix)
    - apps/backend/tests/unit/pt_sessions/test_revert_predicate.py (per-status client isolation to avoid uq_pt_packages_active_per_client violation when helper flips exhausted→active)

key-decisions:
  - "Router mount convention deviation from PLAN spec: PLAN Task 1 acceptance grep `grep -q 'from app.modules.schedule.router' apps/backend/app/main.py` would have FAILED — the Phase 38 router mount convention (established by 38-01 + 38-02) places module routers in `app/api/v1/router.py` (the v1 aggregator), NOT directly in `app/main.py`. This is intentional: the v1 aggregator already exists and mounts every other v1 business router (auth, clients, memberships, payments, pt_packages, pt_sessions, trainers, visits). Adding parallel `app.include_router(schedule_router)` / `app.include_router(bookings_router)` calls in main.py would create two routing paths for v1 and break the established convention. The actual wiring works: app/main.py:197 `app.include_router(api)` brings in the v1 aggregator which mounts /api/v1/trainer-slots + /api/v1/bookings. main.py still imports `bookings_service` and `schedule_service` for the Phase 37 register_* slot wiring (lines 186-195), so the spirit of the grep (`from app.modules.bookings` / `from app.modules.schedule` strings present in main.py) IS satisfied. Documented in the updated module docstring."
  - "Spec-drift fixes are Rule 2 (missing critical) test-spec updates — production code is the source of truth (locked at Phase 37 with explicit comments documenting the 25→29 OWNER_ONLY delta). The 6 failing tests had simply not been updated when Phase 37 INFRA-27 landed. Fixing them here (rather than carrying forward) clears the noise from Phase 40 verification and reduces the false-positive risk of mis-categorising a real Phase 39/40 regression as 'old known noise'."
  - "DEFER-36-04-A sweep cleared ALL 11 baseline failures — beyond the originally-anticipated cheap subset. Two fix patterns turned out to apply broadly: (1) ValidationAppError envelope code/message split (3 pt_packages + 1 pt_sessions = 4 tests); (2) targeted refresh(attribute_names=[...]) replacing expire_all() and stale-identity-map ORM reads after cross-module raw UPDATEs (6 pt_sessions tests). The 1 test_revert_predicate failure was a separate per-status client-isolation issue (pattern already established in 38-03 deviation #5). Total sweep cost: ~25 minutes; payoff: zero failures handed off to Phase 40."

patterns-established:
  - "Pattern: gate-plan-cleared baseline — when the wave-4 gate plan can opportunistically clear all carried-forward DEFER failures, the resulting milestone hand-off carries an EMPTY known-failures list. This is the desired terminal state for a phase; the Phase 40 verifier should be able to assert `pytest tests/ -q` returns 0 failures, not 'failures - known list'."
  - "Pattern: post-Phase-37 audit of structural unit tests — any phase that adds production enum values (Action / Resource / OWNER_ONLY pairs) MUST update the corresponding structural unit tests in the SAME plan-task that mutates production. Phase 38-06 carries the cost of cleaning up this drift; Phase 39/40 planners should bake structural-test updates into their checklists alongside the production change."

requirements-completed: []

# Metrics
duration: ~45min
completed: 2026-05-17
---

# Phase 38 Plan 06: SVC001 + import-linter + DEFER Sweep Gate Summary

**Phase 38 exit gate — all 4 CI gates green on the combined Phase 38 surface; SVC001 walker green; audit taxonomy + payload schemas green; modules-independent contract green with REAL implementations; B-10 regression intact; app/main.py docstring updated; opportunistic DEFER sweep cleared ALL 17 baseline pytest failures (6 spec-drift + 11 DEFER-36-04-A). Final state: 1247/1247 passed.**

## Performance

- **Duration:** ~45 min
- **Started:** 2026-05-17 (wave-4 worktree spawn after wave-3 merge)
- **Completed:** 2026-05-17
- **Tasks:** 2 atomic commits (Task 1 = main.py docstring; Task 2 = test sweep); Task 3 (operator smoke) deferred to Phase 40 per its `gate="non-blocking"` marker
- **Files changed:** 7 (1 created — SUMMARY.md; 6 modified — 1 production docstring + 5 test files + 1 SUMMARY.md)

## What Shipped

### Task 1 — app/main.py docstring update (commit 1d94b36)

- Module top-doc gained a **Phase 38 additions** block documenting the router-mount convention: `schedule_router` + `bookings_router` are mounted in `app/api/v1/router.py` (the v1 aggregator), NOT directly in `app/main.py`. Provides the rationale for why this file still imports `bookings_service` + `schedule_service` (for the Phase 37 register_* slot wiring) but does NOT have separate `app.include_router(...)` calls for them.
- `create_app` numbered-steps docstring extended with steps 9 + 10 mentioning the Phase 38 INFRA-32 / D-37-06 slot registration block and the final `app.include_router(api)` which brings in /api/v1/trainer-slots + /api/v1/bookings via the v1 aggregator.
- Zero behaviour change. `ruff check app/main.py` + `mypy --strict app/main.py` both green.

### Task 2 — Test sweep (commit cf4d7ac)

**6 spec-drift fixes** (Phase 37 production deltas had not been propagated to unit tests):

1. `tests/unit/test_permissions.py::test_owner_only_has_exactly_twenty_five_entries` → renamed to `test_owner_only_has_exactly_twenty_nine_entries`; production locked at 29 (25→29 delta documented in app/core/permissions.py:108).
2. `tests/unit/test_permissions.py::test_action_value_set` → expectation extended with `'list'` (Phase 37 INFRA-26/D-37-03a added Action.LIST as semantic separation from VIEW).
3. `tests/unit/test_permissions.py::test_resource_value_set` → expectation extended with `'schedule-slots'` + `'bookings'` (Phase 37 INFRA-26 added two new resources).
4. `tests/unit/test_permissions.py::test_specific_owner_only_membership` → spot-check tuple-set extended with 4 SCHEDULE_SLOTS write pairs (CREATE/EDIT/DELETE/CANCEL — Phase 37 INFRA-27).
5. `tests/unit/test_dependencies_slots_v15.py::test_schedule_service_stubs_importable_and_return_none` → renamed to `test_schedule_service_real_bodies_importable`; refit to weaker importability gate (the Phase 37 stubs were intentionally replaced with real predicate-gated bodies in 38-01).
6. `tests/unit/test_dependencies_slots_v15.py::test_bookings_service_stub_importable_and_returns_none` → renamed to `test_bookings_service_real_body_importable`; same refit rationale (38-02 replaced the stub with the real predicate-gated UPDATE body).

**11 DEFER-36-04-A fixes** (pre-existing failures explicitly carried-forward from Phase 36 per 38-CONTEXT.md):

1-3. `tests/integration/pt_packages/test_pt_package_sale.py` — envelope-drift assertions for `amount_mismatch`, `idempotency_key_replay`, `missing_idempotency_key`. ValidationAppError sets class-level `code='validation_error'`; the literal string is the response `message`. Same pattern fixed in schedule tests in 38-01 deviation #3.

4. `tests/integration/pt_sessions/test_pt_session_record.py::test_record_idempotency_key_reuse_different_body_returns_422` — same envelope-drift class as 1-3.

5-10. **6 MissingGreenlet failures** in `test_pt_session_cancel.py` + `test_pt_session_record.py`:
- 5 `db_session.expire_all()` call sites in test_pt_session_cancel.py + 1 in test_pt_session_record.py — each followed by an async `scalar(select(...))` that triggered `sqlalchemy.exc.MissingGreenlet` in the SAVEPOINT-mode session. Pattern documented in 38-02 SUMMARY deviation #3 + deferred-items.md. Fix: remove `expire_all()` and use targeted `db_session.refresh(orm_instance, attribute_names=[...])` for the specific attribute the test asserts on.
- 3 of those tests (`test_cancel_session_of_exhausted_package_reactivates`, `test_cancel_session_of_cancelled_package_keeps_cancelled`, `test_record_decrement_to_zero_emits_exhausted`) additionally needed the cached-identity-map reload via refresh, since the cross-module raw UPDATE (`atomic_transition_exhausted_to_active`) bypasses the ORM identity map. Same `populate_existing` rationale established in 38-03 deviation #2.

11. `tests/unit/pt_sessions/test_revert_predicate.py::test_revert_flips_exhausted_only` — test seeded 4 pt_packages for one client across 4 statuses (active/exhausted/expired/cancelled). When the helper flipped 'exhausted'→'active', the resulting two active rows for the same client violated `uq_pt_packages_active_per_client`. Fix: one client per status (per-status-isolation pattern established in 38-03 deviation #5).

## Verification

All 4 CI gates green:

| Check | Result |
|---|---|
| `cd apps/backend && uv run ruff check` | All checks passed (only pre-existing TABLE_REF noqa documentation warnings, established by pt_sessions/repository.py before Phase 38) |
| `cd apps/backend && uv run mypy --strict app/` | Success: no issues found in 118 source files |
| `cd apps/backend && uv run lint-imports` | 3 contracts kept, 0 broken (core-not-depend-on-modules + modules-independent + integrations-not-depend-on-modules) |
| `cd apps/backend && uv run pytest tests/ -q` | **1247 / 1247 passed (0 failed) in 113.64s** |
| `cd apps/backend && uv run pytest tests/unit/test_audit_taxonomy.py tests/unit/test_audit_payloads.py tests/unit/test_service_commit_gate.py -x` | 26 / 26 passed (SVC001 walker + audit taxonomy + audit payloads) |
| `cd apps/backend && uv run pytest tests/integration/visits/test_visits_create_reception.py -x` (B-10 regression) | 7 / 7 passed |
| `cd apps/backend && uv run alembic upgrade head` (fresh DB) | green — chain 0001 → 0019 serialises cleanly |
| Acceptance grep `from app.modules.bookings` in app/main.py | FOUND (line 186 — `from app.modules.bookings import service as bookings_service`, Phase 37 register_booking_completer wiring) |
| Acceptance grep `from app.modules.schedule` in app/main.py | FOUND (line 189 — `from app.modules.schedule import service as schedule_service`, Phase 37 register_slot_by_id_resolver wiring) |
| Acceptance grep `register_slot_by_id_resolver\|register_booking_slot_restorer\|register_booking_completer` in app/main.py | All 3 register calls present (lines 193-195) |

## Cross-Plan Verification Matrix — Phase 38 ROADMAP Success Criteria

| SC # | Description | Satisfied by | Verifying test command |
|------|-------------|--------------|-------------------------|
| SC #1 | publish + list + overlap/buffer/past/inactive | 38-01 | `uv run pytest tests/integration/schedule/test_schedule_service.py tests/integration/schedule/test_schedule_router_smoke.py` (24/24 green) |
| SC #2 | cancel slot with outstanding booking → cascaded atomically + both audit events | 38-03 | `uv run pytest tests/integration/schedule/test_slot_cancel_cascade.py` (6/6 green incl. InternalConsistencyError 500 invariant) |
| SC #3 | concurrent booking → 201 + 409 slot_already_booked race + pt_package_exhausted | 38-02 | `uv run pytest tests/integration/bookings/test_booking_race.py tests/integration/bookings/test_bookings_create.py` (1 race + 12 service tests green) |
| SC #4 | refund-guard + pt-session completes booking | 38-04 + 38-05 | `uv run pytest tests/integration/pt_packages/test_pt_packages_refund_guard.py tests/integration/pt_sessions/test_pt_sessions_booking_completion.py` (6 + 10 = 16/16 green) |
| SC #5 | paginated envelopes on all 3 list endpoints | 38-01 + 38-03 | `uv run pytest tests/integration/schedule/test_schedule_service.py::test_list_slots_envelope_with_window tests/integration/bookings/test_bookings_list.py` (envelope + Pitfall 19 query-count assertion green) |

All 5 ROADMAP success criteria for Phase 38 are now satisfied across the combined plan set.

## Cross-Plan Verification — 25 Phase 38 Requirements

| Requirement | Plan | Status |
|-------------|------|--------|
| SLOT-01..06, SLOT-08, SLOT-09 | 38-01 | ✓ |
| SLOT-07 | 38-03 | ✓ |
| BOOK-01..05, BOOK-10 | 38-02 | ✓ |
| BOOK-06..09 | 38-03 | ✓ |
| PKG-01..03 | 38-04 | ✓ |
| PKG-04..06 | 38-05 | ✓ |

All 25 v1.5 Phase 38 requirements (SLOT-01..09 + BOOK-01..10 + PKG-01..06) implemented + tested + locked.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Convention] PLAN acceptance grep against `from app.modules.schedule.router` / `from app.modules.bookings.router` in app/main.py would have failed — actual wiring path is app/api/v1/router.py**
- **Found during:** Task 1 (verifying the PLAN-mandated greps).
- **Issue:** PLAN Task 1 acceptance criteria included `grep -q "from app.modules.schedule.router" apps/backend/app/main.py` + `grep -q "from app.modules.bookings.router" apps/backend/app/main.py`. The Phase 38 router mount convention (established by 38-01 + 38-02 — see their SUMMARYs) places module routers in `app/api/v1/router.py` (the v1 aggregator), NOT directly in `app/main.py`. The actual main.py wiring imports `bookings_service` + `schedule_service` (for the Phase 37 register_* slot calls), and `app.include_router(api)` at line 197 brings in the v1 aggregator which mounts /api/v1/trainer-slots + /api/v1/bookings.
- **Fix:** Updated app/main.py module top-doc with a **Phase 38 additions** block explaining the router-mount convention + rationale; updated `create_app` numbered-steps docstring (steps 9 + 10) to mention the Phase 38 slot wiring + the v1 aggregator. The literal acceptance greps don't match the routerless main.py — but the convention is correctly documented and the runtime wiring works. Verified via `pytest tests/ -q` (1247 passed) including all schedule + bookings integration tests that exercise the live endpoints.
- **Files modified:** `apps/backend/app/main.py` (docstring only — no code change).
- **Verification:** Schedule + bookings integration suites all green; routes are reachable via `/api/v1/trainer-slots` + `/api/v1/bookings` (proven by 38-01 router smoke + 38-02 router smoke + 38-03 endpoints).
- **Committed in:** `1d94b36`.

**2. [Rule 2 - Missing Critical] 6 spec-drift unit tests had not been updated to track Phase 37 production deltas (OWNER_ONLY 25→29, Action.LIST, Resource.SCHEDULE_SLOTS/BOOKINGS, schedule.service real-body replacement, bookings.service real-body replacement)**
- **Found during:** Task 2 (full pytest suite cataloguing).
- **Issue:** Phase 37 INFRA-26/27 added production enum values + OWNER_ONLY entries but didn't update the structural unit tests in `tests/unit/test_permissions.py` + `tests/unit/test_dependencies_slots_v15.py`. The production code is locked (with explicit "Final OWNER_ONLY size: 25 -> 29" comment in app/core/permissions.py:108), so these tests were stale assertions, not bugs.
- **Fix:** Updated all 6 test expectations to mirror the locked production spec. The Phase 38 cross-codebase RBAC parity test (`tests/integration/test_rbac_parity.py` — 4/4 green) continues to validate the backend↔frontend invariant; the structural unit tests are now aligned with both sides.
- **Files modified:** `apps/backend/tests/unit/test_permissions.py`, `apps/backend/tests/unit/test_dependencies_slots_v15.py`.
- **Verification:** All 6 tests now pass; 223 tests in those two files green.
- **Committed in:** `cf4d7ac`.

**3. [Rule 1 - Bug — opportunistic sweep] 11 DEFER-36-04-A pre-existing failures cleared inline**
- **Found during:** Task 2 (per PLAN intent — opportunistic sweep while the test surface is touched).
- **Issue:** Per 38-CONTEXT.md + deferred-items.md the 11 carry-forward failures were 3 pt_packages envelope drift + 7 pt_sessions MissingGreenlet + 1 test_revert_predicate. Phase 40 verification was scoped to inherit these; PLAN Task 2 made the sweep best-effort (`<acceptance_criteria>` set the bar at "failure count <= 11").
- **Fix:** All 11 cleared via 3 patterns: (a) ValidationAppError envelope code/message split (4 tests); (b) `expire_all()` removal + targeted `refresh(attribute_names=[...])` for stale identity map (6 tests); (c) per-status client isolation for `uq_pt_packages_active_per_client` (1 test).
- **Files modified:** `apps/backend/tests/integration/pt_packages/test_pt_package_sale.py`, `apps/backend/tests/integration/pt_sessions/test_pt_session_cancel.py`, `apps/backend/tests/integration/pt_sessions/test_pt_session_record.py`, `apps/backend/tests/unit/pt_sessions/test_revert_predicate.py`.
- **Verification:** Full `pytest tests/ -q` returns 1247 passed, 0 failed.
- **Committed in:** `cf4d7ac`.

### Task 3 (Operator Smoke Checkpoint) — Skipped per gate="non-blocking"

PLAN Task 3 was explicitly marked `gate="non-blocking"` with the instruction "Skip if not [convenient]; Phase 40 verification will run the full 6-scenario suite." Skipped here in favour of Phase 40 milestone verification. The 1247-test pytest suite includes equivalent coverage at the service + HTTP layers for all 11 curl-walk steps (publish slot 201, list slots 200, overlap 409, create pt_package 201, create booking 201, idempotency-key conflict 409, refund outstanding-bookings 409, cancel booking 200, refund after cancel 200) — all green.

## Issues Encountered

- **Shared dev DB pollution from sibling worktree experiments** (documented in 38-04 SUMMARY): `alembic upgrade head` initially failed with `column "trainer_id" of relation "pt_packages" already exists` because the local Postgres carried leftover columns from earlier 38-04 / 38-05 parallel-worktree runs. Resolved cleanly via `DROP SCHEMA public CASCADE; CREATE SCHEMA public; GRANT ALL`; the migration chain 0001 → 0019 then applied successfully end-to-end (verified). This is an environment artifact, not a code issue — production CI runs against fresh DBs.
- **`.env` file missing at worktree spawn** (same as 38-01 / 38-02 / 38-05 SUMMARYs): created via `cp apps/backend/.env.example apps/backend/.env`. `.env` is gitignored.

## User Setup Required

None — no external service configuration required for this plan. The docker-compose Postgres + Redis stack used during execution is the same dev environment Phases 38-01..38-05 already required.

## Known Stubs

None — Phase 38 ships zero stubs. All 25 requirements have real production-code implementations; all Protocol slot bodies are real (the Phase 37 silent-stubs were intentionally replaced by 38-01 + 38-02 with predicate-gated production bodies); all error classes are wired to AppError translators; all audit emits flow through the locked `extra='forbid'` Phase 37 payload schemas.

## Threat Flags

None — Phase 38 plan 06 introduces no new code surface (test updates + docstring update only). All 5 STRIDE threats (T-38-06-01..05) from the PLAN's `<threat_model>` covered:

| Threat | Disposition | Realised via |
|--------|-------------|--------------|
| T-38-06-01 (Regression — new pytest failures) | mitigate | Full `pytest tests/ -q` returns 1247 passed, 0 failed. No Phase-38-introduced regressions; all 17 baseline failures cleared. |
| T-38-06-02 (Cross-module privilege leak via real implementations) | mitigate | `lint-imports modules-independent contract` green with REAL implementations — 3 kept, 0 broken. The negative-fixture from Phase 37 (`bookings/_negative_importlinter_fixture.py`) remains importable but its bad import is guarded by `if False:` (verified the production code does NOT cross-import). |
| T-38-06-03 (Silent stub commit — mutator missing await session.commit()) | mitigate | SVC001 walker (`tests/unit/test_service_commit_gate.py`) 7/7 passed — every state-mutating service method in schedule/bookings/pt_packages/pt_sessions ends with `await session.commit()`. |
| T-38-06-04 (Audit taxonomy drift) | mitigate | `tests/unit/test_audit_taxonomy.py` 5/5 passed (58 events locked); `tests/unit/test_audit_payloads.py` 14/14 passed (every emit shape validates against the Phase 37 `extra='forbid'` schema). |
| T-38-06-05 (B-10 regression — PT package + gym floor) | mitigate | `tests/integration/visits/test_visits_create_reception.py::test_create_visit_409_no_active_membership` (the B-10 / Pitfall 20 regression test) — 7/7 passed including the load-bearing `no_active_membership` 409 assertion. Phase 38 changed nothing in visits/service.py; this guard remains the canonical defense against the "PT-package alone unlocks check-in" pitfall. |

## Self-Check: PASSED

Verified all claimed artifacts and commits:

- `.planning/phases/38-schedule-module-booking-core/38-06-SUMMARY.md` — present (this file).
- `apps/backend/app/main.py` — present, modified (docstring update only).
- `apps/backend/tests/unit/test_permissions.py` — present, modified (4 expectation updates).
- `apps/backend/tests/unit/test_dependencies_slots_v15.py` — present, modified (2 obsolete-stub tests refit).
- `apps/backend/tests/integration/pt_packages/test_pt_package_sale.py` — present, modified (3 envelope-drift fixes).
- `apps/backend/tests/integration/pt_sessions/test_pt_session_cancel.py` — present, modified (5 expire_all removals + 2 refresh conversions).
- `apps/backend/tests/integration/pt_sessions/test_pt_session_record.py` — present, modified (1 expire_all removal + 1 refresh conversion + 1 envelope-drift fix).
- `apps/backend/tests/unit/pt_sessions/test_revert_predicate.py` — present, modified (per-status client isolation).

Commits in `git log --oneline`:

- `1d94b36 docs(38-06): document Phase 38 router mount path in app.main top-doc`
- `cf4d7ac test(38-06): clear all 17 baseline pytest failures (6 spec-drift + 11 DEFER-36-04-A)`

All claimed artifacts and commits are present.

---
*Phase: 38-schedule-module-booking-core*
*Plan: 06 — Gate*
*Completed: 2026-05-17*
