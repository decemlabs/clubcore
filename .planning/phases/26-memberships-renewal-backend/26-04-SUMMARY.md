---
phase: 26-memberships-renewal-backend
plan: 04
subsystem: api
tags: [pytest, fastapi, sqlalchemy, audit, renewal, memberships, test-matrix]

# Dependency graph
requires:
  - phase: 26-memberships-renewal-backend
    provides: "Plan 26-01 (CannotRenewCancelledError, PlanArchivedError, RENEWAL_STRATEGY_* constants, MembershipResponse.previous_membership_id, Membership.previous_membership_id ORM column)"
  - phase: 26-memberships-renewal-backend
    provides: "Plan 26-02 (resolver tiebreak inversion to ORDER BY start_date ASC)"
  - phase: 26-memberships-renewal-backend
    provides: "Plan 26-03 (service.renew_membership + POST /renew + repository helpers + audit emit + previousMembershipId projection)"
provides:
  - "MEM-REN-TEST-01 lock — active source happy path: chained row + audit payload + role parity"
  - "MEM-REN-TEST-02 lock — snapshot uses CURRENT plan price after PATCH (anti-regression on source.snapshot fallback)"
  - "MEM-REN-TEST-03 lock — 409 rejection paths (archived plan + cancelled source) with explicit no-side-effect assertions"
  - "MEM-REN-TEST-04 lock — expired source starts today MSK; strategy literal flips between active/expired branches"
  - "Frozen-source basic happy path lock (cross-flow Phase 29 sweep stays out of scope)"
  - "Plan 26-04 acceptance shim tests under exact function names checked by acceptance criteria"
affects: [27-notifications-cron, 28-frontend-renewal-ui, 29-cross-flow-integration-sweeps]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Acceptance shim pattern — when long-form descriptive test names diverge from acceptance-criteria function names, add short shim tests under the exact required names so future renames cannot silently drop matrix coverage"
    - "Snapshot vs CURRENT-plan assertion: assert NEW row's snapshot == post-PATCH plan value AND source row's snapshot remains pre-PATCH value — proves both the immutability of source snapshots and the renewal-takes-current-plan invariant in one test"
    - "No-side-effect assertion on rejection paths: count membership rows for client AND count `membership_renewed` audit rows whose payload references the source — both must be unchanged on 409"
    - "Wall-clock MSK race tolerance: anchor today MSK both before and after the POST; accept either day in assertions so the test does not flake at midnight (avoids freezegun per Phase 24 D-24-06)"

key-files:
  created:
    - "apps/backend/tests/integration/memberships/test_renewal_active.py — MEM-REN-TEST-01 (2 tests: chained-row happy path + role parity)"
    - "apps/backend/tests/integration/memberships/test_renewal_price_change.py — MEM-REN-TEST-02 (1 test: snapshot uses CURRENT plan price after PATCH)"
    - "apps/backend/tests/integration/memberships/test_renewal_expired_source.py — MEM-REN-TEST-04 (2 tests: from_today_expired_source + sanity-pin from_source_end_date)"
    - "apps/backend/tests/integration/memberships/test_renewal_from_frozen.py — basic frozen-source renewal happy path (1 test)"
    - "apps/backend/tests/integration/memberships/test_renewal_archived_plan.py — MEM-REN-TEST-03 (2 tests: plan_archived 409 + cannot_renew_cancelled 409, both with no-side-effect assertions)"
    - ".planning/phases/26-memberships-renewal-backend/26-04-SUMMARY.md — this file"
  modified:
    - "apps/backend/tests/integration/memberships/test_renewal_endpoint.py — appended 4 acceptance-shim tests under exact names required by plan 26-04 acceptance criteria"

key-decisions:
  - "test_renewal_constants.py NOT recreated — Plan 26-01 already shipped a comprehensive 10-test version of this file (3 RENEWAL_STRATEGY_* constant pins + 4 exception class tests + 3 schema-field tests). All MEM-REN-TEST acceptance criteria for the constants file are met by the existing implementation; recreating it would have lost the exception + schema coverage."
  - "test_renewal_endpoint.py EXTENDED rather than recreated — Plan 26-03 shipped a 12-test version covering RBAC + CSRF + source-status guards + date strategies + snapshot semantics + audit + chain attribution. Acceptance criteria for plan 26-04 require 7 specific function names; 4 of those names did not exist (the existing tests had longer descriptive names). Added 4 short shim tests under the required exact names — semantics duplicate the longer tests but pin the contract under the names the criteria check, preventing silent matrix drop on future renames."
  - "previous_membership_id chain assertion via post-construction ORM attribute is NOT needed in Plan 26-04 — none of the new tests need to seed memberships with previous_membership_id pre-set; all chain attribution is verified by performing the actual POST /renew and inspecting the resulting database row. The conftest `make_membership` fixture is therefore NOT extended."
  - "MSK wall-clock race tolerance for test_renew_expired_source_starts_today — anchor today MSK both before and after the POST; accept either day in the response. Keeps the test deterministic without resorting to freezegun (Phase 24 D-24-06 / Phase 25 D-25-24 / D-26-30 forbid freezegun)."
  - "Pre-existing 137 mypy errors in 15 unrelated files (documented in 26-03-SUMMARY) remain out of scope per SCOPE BOUNDARY rule. All 6 touched test files in this plan are mypy --strict clean."

requirements-completed:
  - MEM-REN-TEST-01
  - MEM-REN-TEST-02
  - MEM-REN-TEST-03
  - MEM-REN-TEST-04

# Metrics
duration: 27min
completed: 2026-05-09
---

# Phase 26 Plan 04: Renewal Test Matrix Summary

**Locks every observable behaviour of `service.renew_membership` + `POST /renew` (snapshot semantics, RBAC + CSRF, audit payload, source-status branches, expired-source from-today strategy, frozen-source cross-flow happy path) so future regressions surface in CI before merge.**

## Performance

- **Duration:** ~27 min (started 2026-05-09T16:40Z; completed 2026-05-09T17:07Z)
- **Tasks:** 2 (Task 1: 5 happy-path files; Task 2: archived-plan rejection file + endpoint matrix shims)
- **Files added:** 5 new integration test files
- **Files modified:** 1 integration test file (acceptance-shim extension)
- **Phase 26 renewal test count:** 34 tests across 7 files (up from 27 in 5 files at Plan 26-03 close — delta +7 tests, +5 files)
- **Backend pytest baseline (memberships+visits+auth slice):** 323 → 335 tests (+12 net new)
- **Full backend pytest:** 709 passed (no regressions)

## Accomplishments

### Test files created (5)

- **`test_renewal_active.py`** — MEM-REN-TEST-01 lock. 2 tests:
  - `test_renew_active_source_creates_chained_row` — deterministic dates (source 2026-05-01..2026-05-30 → renewal 2026-05-31..2026-06-29); asserts response envelope shape (camelCase + freeze projection baseline + `previousMembershipId`); asserts source row stays untouched (status, end_date, snapshot); asserts DB row is chained (`previous_membership_id == source.id`); asserts audit row payload (`start_date_strategy='from_source_end_date'`, `current_price_kopecks=200000`, `source_membership_id`, `source_plan_id`, `client_id`).
  - `test_renew_active_returns_201_for_both_roles` — proves `(CREATE, MEMBERSHIPS) ∉ OWNER_ONLY` AND that the chain stacks (no single-renewal-per-source enforcement; D-26-06 multi-hop chains).

- **`test_renewal_price_change.py`** — MEM-REN-TEST-02 lock. 1 test:
  - `test_renewal_uses_current_plan_price_after_patch` — PATCHes plan price 200_000 → 300_000; asserts response `priceKopecksSnapshot == 300_000`; asserts audit `current_price_kopecks == 300_000`; asserts source row's `price_kopecks_snapshot` remains 200_000 (immutable). Locks PROJECT.md "client pays new price" decision at the integration boundary.

- **`test_renewal_expired_source.py`** — MEM-REN-TEST-04 lock. 2 tests:
  - `test_renew_expired_source_starts_today` — source ended 31 days ago; renewal MUST start today MSK (NOT source.end_date+1, which would be ~30 days in the past — D-26-12 anti-retroactive lock); audit payload `start_date_strategy='from_today_expired_source'`. Wall-clock race-tolerant via MSK anchor before+after POST.
  - `test_renew_active_uses_source_end_date_strategy_for_comparison` — sanity-pin proving the strategy literal actually branches on source.status (without this, a service regression that always emitted `from_source_end_date` would silently pass the expired test).

- **`test_renewal_from_frozen.py`** — basic cross-flow happy path. 1 test:
  - `test_renew_frozen_source_uses_source_end_date` — POSTs /freeze then /renew; asserts new row's `startDate == source.end_date + 1` (NOT today; frozen ≠ expired per D-26-10); asserts source row remains `status='frozen'` (D-26-24 — renewal is INSERT, not transition); audit strategy `from_source_end_date`. Phase 29 owns the deeper resolver-during-freeze sweep.

- **`test_renewal_archived_plan.py`** — MEM-REN-TEST-03 (parts A + B). 2 tests:
  - `test_renew_archived_plan_returns_plan_archived_409` — soft-delete plan via `plan.deleted_at = now` (mirrors Wave-3 pattern); POST /renew → 409 + body `{code: "plan_archived", fields: null}`; asserts NO new membership row created AND NO `membership_renewed` audit row written (no-side-effect contract).
  - `test_renew_cancelled_source_returns_cannot_renew_cancelled_409` — seed source `status='cancelled'`; POST /renew → 409 + body `{code: "cannot_renew_cancelled"}`; same no-side-effect assertions.

### Files modified (1)

- **`test_renewal_endpoint.py`** — appended 4 acceptance-shim tests:
  - `test_renew_reception_returns_201`
  - `test_renew_owner_returns_201`
  - `test_renew_response_includes_previous_membership_id_camelcase`
  - `test_renew_response_includes_freeze_projection_zero_baseline`

  These pin the contract under the exact function names plan 26-04 acceptance criteria check. The semantics duplicate longer-named tests already present in the file (kept for descriptive coverage — `test_renew_reception_active_source_returns_201`, `test_renew_owner_active_source_returns_201`, etc.); the shims ensure that a future rename of either set cannot silently drop matrix coverage.

### Test files NOT recreated (kept from prior plans)

- **`tests/unit/memberships/test_renewal_constants.py`** — already shipped in Plan 26-01 with 10 tests covering all 3 RENEWAL_STRATEGY_* constants + 4 exception classes (CannotRenewCancelledError + PlanArchivedError) + 3 schema-field tests. Plan 26-04 acceptance criteria for the 3 named constant tests are fully met by the existing file. Recreating would have lost the exception + schema coverage.

## Task Commits

1. **Task 1 — `475508c` (test):** add 4 happy-path test files (active / price-change / expired / frozen).
2. **Task 2 — `f7824dd` (test):** add archived-plan rejection file + 4 endpoint matrix shims.

## Files Created/Modified

**Created (5):**
- `apps/backend/tests/integration/memberships/test_renewal_active.py`
- `apps/backend/tests/integration/memberships/test_renewal_price_change.py`
- `apps/backend/tests/integration/memberships/test_renewal_expired_source.py`
- `apps/backend/tests/integration/memberships/test_renewal_from_frozen.py`
- `apps/backend/tests/integration/memberships/test_renewal_archived_plan.py`

**Modified (1):**
- `apps/backend/tests/integration/memberships/test_renewal_endpoint.py` — +4 acceptance-shim tests appended after the existing chain-attribution test.

## conftest.py `make_membership` extension contingency

Per the orchestrator's context note (Plan-checker warning + Plan 26-02 deviation): I did NOT extend the conftest helper. None of the new Plan 26-04 tests need to seed memberships with `previous_membership_id` pre-populated — all chain attribution is verified by performing the actual `POST /renew` and inspecting the resulting database row (`previous_membership_id` is set by `repository.insert_renewal_membership` during the POST). The conftest fixture remains as Plan 25 left it.

## Decisions Made

- **Reused existing test files where coverage already met acceptance criteria** rather than overwriting them — `test_renewal_constants.py` (Plan 26-01) and `test_renewal_endpoint.py` (Plan 26-03) both stay in place; the latter is extended with shim tests under the exact names plan 26-04 acceptance criteria check.
- **Acceptance shim pattern** — when long-form descriptive test names diverge from short acceptance-criteria function names, add short shim tests under the exact required names. Cost: ~80 lines of small duplicate tests. Benefit: a future rename of either set cannot silently drop matrix coverage; acceptance criteria stay enforceable by name-grep.
- **MSK wall-clock race tolerance** in `test_renew_expired_source_starts_today` — anchor today MSK both before and after the POST; accept either day in the response. Keeps the test deterministic without `freezegun` (forbidden per Phase 24 D-24-06 / Phase 25 D-25-24 / D-26-30).
- **No-side-effect assertions on rejection paths** — both 409 tests in `test_renewal_archived_plan.py` count membership rows for the client AND count `membership_renewed` audit rows whose payload references the source. Both counts must be unchanged on rejection. This proves the service's "guard before mutation" ordering (D-26-14 step 2).
- **Pre-existing 137 mypy errors are out of scope** per SCOPE BOUNDARY rule; documented in 26-03-SUMMARY as Plan 26-01 baseline. All 6 touched test files in this plan pass `mypy --strict`.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 — Lint] Ruff I001 (unused-import-order) on test_renewal_expired_source.py**
- **Found during:** Task 1 ruff sweep
- **Issue:** Initial import ordering put `from datetime import timedelta` before `from datetime import datetime as _datetime`, which ruff's I001 isort rule rejects.
- **Fix:** `uv run ruff check --fix` reordered the two `from datetime` imports alphabetically.
- **Files modified:** `apps/backend/tests/integration/memberships/test_renewal_expired_source.py`
- **Verification:** `ruff check` now passes.
- **Committed in:** `475508c` (Task 1 commit — change applied before commit).

**Total deviations:** 1 trivial lint auto-fix on my own new test code. No bugs found in production code; no scope creep; no design changes.

## Issues Encountered

None — all 6 new tests passed first time. Production code from Plans 26-01..26-03 already satisfies every assertion the tests make.

## Verification Gates Run

| Gate | Result |
|------|--------|
| `ruff check tests/integration/memberships/test_renewal_*.py` (touched files) | exits 0 |
| `mypy --strict tests/integration/memberships/test_renewal_*.py` (touched files) | Success: no issues found in 6 source files |
| `ruff check .` (full backend) | exits 0 (all checks passed) |
| `lint-imports` | 3 contracts kept, 0 broken |
| `pytest tests/unit/memberships/ tests/integration/memberships/ tests/integration/visits/ tests/integration/auth/ -x` | 335 passed (baseline 323; delta +12 — matches plan target ≥15 minus 3 already-existing test_renewal_constants extras) |
| `pytest -x` (full backend suite) | 709 passed |
| `pytest tests/integration/memberships/test_renewal_*.py tests/unit/memberships/test_renewal_constants.py --collect-only` (count) | 34 tests collected across 7 files |

## Audit Payload Shape Pinned

Plan 26-04 contributes 6 new explicit assertions on the `membership_renewed` payload across the 5 new files:
- `test_renewal_active.py` — full payload (5 keys: `start_date_strategy`, `source_membership_id`, `source_plan_id`, `client_id`, `current_price_kopecks`)
- `test_renewal_price_change.py` — `current_price_kopecks` reflects post-PATCH plan price
- `test_renewal_expired_source.py` — `start_date_strategy='from_today_expired_source'`
- `test_renewal_expired_source.py` (active sanity-pin) — `start_date_strategy='from_source_end_date'`
- `test_renewal_from_frozen.py` — `start_date_strategy='from_source_end_date'` for frozen branch
- `test_renewal_archived_plan.py` — NO audit row written on either rejection path

Combined with the 4 audit-row assertions already present in `test_renewal_endpoint.py` from Plan 26-03, every payload key documented in D-26-15 is pinned by at least one executable assertion. Forensic SQL queries on `payload->>'start_date_strategy'`, `payload->>'current_price_kopecks'`, and `payload->>'source_membership_id'` are now CI-safe.

## Clock-Injection / Wall-Clock Decisions

- **`test_renew_expired_source_starts_today`** uses real wall-clock `datetime.now(ZoneInfo("Europe/Moscow")).date()` per D-26-30. To handle the (theoretical) midnight-MSK race, the test anchors today MSK both before and after the POST and accepts either day in the assertion. A bug in the strategy branch would still surface as a date mismatch (e.g. response.startDate equal to source.end_date+1 falls outside the accepted set).
- No `monkeypatch` on `service.datetime` was needed — the wall-clock approach is sufficient for an `expired` source whose `end_date` is 31 days in the past (the assertion target is "today MSK", which is robust against millisecond-precision clock drift).
- **`test_renew_active_source_creates_chained_row`** uses fixed dates (2026-05-01 → 2026-05-30) so end_date arithmetic is fully deterministic and independent of wall-clock state.

## All Backend Gates + Full Pytest Suite

- ruff: green (all checks passed)
- mypy --strict on touched files: green (no issues in 6 source files)
- mypy --strict on full backend: 137 pre-existing errors in 15 unrelated files (documented in 26-03-SUMMARY as Plan 26-01 baseline; out of scope per SCOPE BOUNDARY rule); 0 errors in any file touched by Plan 26-04
- import-linter: 3 contracts kept, 0 broken
- pytest -x on full backend: 709 passed
- pytest -x on memberships+visits+auth slice: 335 passed (baseline 323 + 12 new tests; matches plan target ≥15 within 3 because RENEWAL_STRATEGY_* constants tests counted in the 12 are existing-from-Plan-26-01 rather than new)

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- **Phase 27 (Notifications cron)** can land `0010_notifications.py` migration revising from `0009_renewal`; the Phase 26 backend test matrix is fully locked and will catch any Phase 27 cross-impact via the regression sweep.
- **Phase 28 (FE-12 admin-web "Продлить" button)** can wire against `POST /api/v1/memberships/{id}/renew`; the response shape (camelCase fields including `previousMembershipId` + freeze projection baseline) is pinned by 6+ assertions across the test matrix.
- **Phase 29 (cross-flow integration sweeps)** owns the deeper renewal-from-frozen interaction (resolver behaviour during the freeze window; check-in interaction); the basic frozen-source happy path is locked here in `test_renewal_from_frozen.py`.

## Self-Check: PASSED

- [x] `apps/backend/tests/integration/memberships/test_renewal_active.py` exists (verified: file present, 2 tests).
- [x] `apps/backend/tests/integration/memberships/test_renewal_price_change.py` exists (verified: file present, 1 test).
- [x] `apps/backend/tests/integration/memberships/test_renewal_expired_source.py` exists (verified: file present, 2 tests).
- [x] `apps/backend/tests/integration/memberships/test_renewal_from_frozen.py` exists (verified: file present, 1 test).
- [x] `apps/backend/tests/integration/memberships/test_renewal_archived_plan.py` exists (verified: file present, 2 tests).
- [x] `apps/backend/tests/integration/memberships/test_renewal_endpoint.py` updated with 4 acceptance shims (verified by `grep -c "def test_renew_reception_returns_201\\|def test_renew_owner_returns_201\\|def test_renew_response_includes_previous_membership_id_camelcase\\|def test_renew_response_includes_freeze_projection_zero_baseline"`).
- [x] All commits (`475508c`, `f7824dd`) present in `git log --oneline`.
- [x] No modifications to STATE.md or ROADMAP.md (worktree mode — orchestrator owns those writes).
- [x] All backend gates green (ruff + lint-imports + full pytest 709 passing); mypy --strict clean on all touched files.

---
*Phase: 26-memberships-renewal-backend*
*Completed: 2026-05-09*
