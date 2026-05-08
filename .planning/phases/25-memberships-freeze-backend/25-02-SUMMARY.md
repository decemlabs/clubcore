---
phase: 25-memberships-freeze-backend
plan: 02
subsystem: database
tags: [memberships, freeze, repository, sql-aggregate, postgres, integration-test]

# Dependency graph
requires:
  - phase: 25-memberships-freeze-backend
    plan: 01
    provides: MembershipFreezePeriod ORM + freeze_days_limit_snapshot column + uq_membership_freeze_periods_active_per_membership partial unique index.
provides:
  - insert_freeze_period (caller-owns-flush write helper)
  - get_open_freeze_period (read helper, ended_at IS NULL filter)
  - get_freeze_period_by_id (test/debug read helper via session.get)
  - compute_freeze_days_used (single SQL aggregate; CEIL(seconds / 86400) sum)
  - _freeze_days_used_subquery (SA Subquery with membership_id + days_used; reserved for list-view LEFT JOIN)
  - make_user / make_client integration fixtures (DB-direct seeding for freeze tests)
  - tests/integration/memberships/test_freeze_helpers.py (Postgres-backed sanity for compute_freeze_days_used)
affects: [25-03-service, 25-04-schemas-router, 25-05-tests]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Single SQL aggregate via text() with named bind for per-row freeze_days_used: CEIL(EXTRACT(EPOCH FROM (COALESCE(ended_at, now()) - started_at)) / 86400) — byte-stable with Python math.ceil; collapses MSK and UTC because seconds-based ceil is timezone-agnostic for fixed UTC+3."
    - "Reusable SA Subquery (group_by membership_id) for the list-view LEFT JOIN — kept dormant in Plan 25-02; service path will use the per-row scalar via compute_freeze_days_used in Plan 25-03 (D-25-18 admits per-row scalar at default page=20)."
    - "Caller-owns-txn invariant preserved: repository continues to issue zero session.flush() / session.commit() calls; service layer (Plan 25-03) owns the UoW so audit row co-writes."

key-files:
  created:
    - apps/backend/tests/integration/memberships/test_freeze_helpers.py
    - .planning/phases/25-memberships-freeze-backend/25-02-SUMMARY.md
  modified:
    - apps/backend/app/modules/memberships/repository.py
    - apps/backend/tests/integration/memberships/conftest.py

key-decisions:
  - "compute_freeze_days_used uses a hand-written text() statement with named-parameter bind (matches the literal SQL contracted in CONTEXT D-25-16; the alternative SA-functional form is reserved for the list-view subquery so we keep two distinct expressions for two distinct callsites)."
  - "today_msk parameter retained in compute_freeze_days_used signature (ignored at SQL level — del-bound) because it is part of the D-25-16 contract for forward-compat with a future calendar-day refactor; removing it would break Plan 25-03's service-layer call shape."
  - "Five repository helpers landed in a single module-level section after expire_due_rows (clean grouping), keeping the existing Phase 17 + Phase 18 sections untouched and find_active_for_client byte-identical (D-25-17)."
  - "Auto-fixed Plan 25-01 fixture gap (Rule 3): make_plan / make_membership were not yet passing freeze_days_limit / freeze_days_limit_snapshot, so post-Plan-01 integration tests were silently broken. Added the field plumbing and two new fixtures (make_user, make_client) so Plan 25-02's Postgres-backed sanity test could run inside the existing SAVEPOINT pattern."

patterns-established:
  - "Postgres-backed integration sanity test at the repository-layer boundary closes the verification_derivation gap for hand-written text() SQL — applied here for compute_freeze_days_used; Plans 25-03..05 inherit the Membership / FreezePeriod fixture stack."

requirements-completed:
  - MEM-FRZ-02
  - MEM-FRZ-03
  - MEM-FRZ-EP-03

# Metrics
duration: 4min
completed: 2026-05-08
---

# Phase 25 Plan 02: Repository Helpers for Freeze Periods Summary

**Five caller-owns-txn repository helpers (insert / get-open / get-by-id / compute-days-used / list-view subquery) plus a Postgres-backed sanity test for the SQL aggregate — bedrock for Plan 25-03 service composition.**

## Performance

- **Duration:** ~4 min
- **Started:** 2026-05-08T20:35:29Z
- **Tasks:** 2
- **Files modified/created:** 4 (1 modified repository, 1 modified conftest, 1 new test, 1 SUMMARY)

## Accomplishments

- `insert_freeze_period(session, *, membership_id, started_by, started_at)` writes a row with `ended_at=NULL` via `session.add(period)`; no flush, no commit (caller owns the transactional moment per repository.py module docstring).
- `get_open_freeze_period(session, membership_id)` returns the (at most one) freeze period where `ended_at IS NULL`. Defence-in-depth: returns `None` for the impossible state where `status='frozen'` yet no open period exists; service layer raises.
- `get_freeze_period_by_id(session, period_id)` is a thin `session.get` wrapper for tests / debug paths.
- `compute_freeze_days_used(session, membership_id, *, today_msk)` issues a single scalar SQL aggregate `SELECT COALESCE(SUM(CEIL(EXTRACT(EPOCH FROM (COALESCE(ended_at, now()) - started_at)) / 86400)), 0)::int FROM membership_freeze_periods WHERE membership_id = :membership_id`. `today_msk` is currently unused at SQL level (seconds-based ceil collapses MSK and UTC for fixed UTC+3) but retained in the signature for forward-compat per D-25-16.
- `_freeze_days_used_subquery()` returns a SA `Subquery` with `(membership_id, days_used)` columns built from the SA-functional equivalent of the same expression — reserved for a future list-view LEFT JOIN; current Plan 25-03 service path will use the per-row scalar.
- `tests/integration/memberships/test_freeze_helpers.py` exercises the aggregate against real Postgres with two cases: (a) no periods → 0, (b) closed period of 1.5 days → 2 (verifies `ceil(1.5) == 2`, byte-stable with Python `math.ceil`).
- `find_active_for_client` is byte-identical (D-25-17 resolver no-touch invariant preserved).

## Task Commits

1. **Task 1: insert_freeze_period + get_open_freeze_period + get_freeze_period_by_id** — `4a2bb2e` (feat)
2. **Task 2: compute_freeze_days_used + _freeze_days_used_subquery + Postgres-backed integration test** — `1e25967` (feat)

## Files Created/Modified

- `apps/backend/app/modules/memberships/repository.py` — added Phase 25 freeze helpers section (5 functions, ~120 LOC) and broadened SQLAlchemy imports (`Integer`, `Subquery`, `text`); module docstring + existing Phase 16/17/18 sections untouched.
- `apps/backend/tests/integration/memberships/conftest.py` — extended `make_plan` with `freeze_days_limit: int = 14`; extended `make_membership` to populate `freeze_days_limit_snapshot=plan.freeze_days_limit`; added `make_user` and `make_client` fixtures for DB-direct seeding (auto-counters keep emails / phones unique within a test).
- `apps/backend/tests/integration/memberships/test_freeze_helpers.py` — new file; two `pytest.mark.asyncio` cases asserting zero-rows-returns-0 and 1.5-day-closed-period rounds up to 2.

## Decisions Made

- Followed plan as specified — D-25-16, D-25-17, D-25-18 implemented verbatim.
- `today_msk` is forwarded as `del today_msk` (declared as unused at SQL level) inside `compute_freeze_days_used` to keep mypy/ruff happy without dropping the parameter from the contract.
- Five helpers were placed at the END of `repository.py` (after `expire_due_rows`) under a `Phase 25 — MembershipFreezePeriod helpers` section banner — keeps the Phase 16/17/18 sections fully untouched and groups freeze logic for Plan 25-03 readability.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Updated `make_plan` / `make_membership` for Phase 25 NOT NULL columns**
- **Found during:** Task 2 (running the new integration test).
- **Issue:** Plan 25-01 added `MembershipPlan.freeze_days_limit` and `Membership.freeze_days_limit_snapshot` as NOT NULL, but the Phase 17 conftest fixtures `make_plan` and `make_membership` did not pass these fields. Inserts emit NULL, hitting `null value in column ... violates not-null constraint`. The existing `tests/integration/memberships/test_list_expiring.py` file was already broken silently (ran via `uv run pytest tests/integration/memberships/test_list_expiring.py -x` and reproduced the failure).
- **Fix:** Extended `make_plan` to accept `freeze_days_limit: int = 14`; extended `make_membership` to wire `freeze_days_limit_snapshot=plan.freeze_days_limit`. No call-site updates needed (kwarg defaults preserve backward-compat with all existing callers).
- **Files modified:** `apps/backend/tests/integration/memberships/conftest.py`
- **Verification:** `uv run pytest tests/integration/memberships/test_list_expiring.py tests/integration/memberships/test_resolver.py tests/integration/memberships/test_freeze_helpers.py -x -q` — 22/22 passed.
- **Committed in:** `1e25967` (Task 2 commit).

**2. [Rule 3 - Blocking] Added `make_user` and `make_client` fixtures**
- **Found during:** Task 2 (test file authoring).
- **Issue:** Plan 25-02 Task 2 instructs the executor to use `make_user` / `make_membership` fixtures and verify availability via `grep -E "def (make_user|make_membership)"` of the conftest, falling back to module-level fixtures otherwise. The conftest had `make_membership` and `make_plan` only; no `make_user`, and `make_membership` requires a real `client_id` (FK RESTRICT to `clients.id`) so a `make_client` analog is also required.
- **Fix:** Added `make_user(role='reception', ...)` (mirrors the existing `_seed_user` helper but with auto-counter unique emails) and `make_client(...)` (auto-seeds an owner via `make_user` for `created_by_user_id`, auto-counter phone). Both follow the SAVEPOINT-mode commit pattern of `make_plan` / `make_membership`.
- **Files modified:** `apps/backend/tests/integration/memberships/conftest.py`
- **Verification:** `uv run pytest tests/integration/memberships/test_freeze_helpers.py -x -q` — 2/2 passed.
- **Committed in:** `1e25967` (Task 2 commit).

---

**Total deviations:** 2 auto-fixed (both blocking)
**Impact on plan:** No scope creep — both fixes were directly required for the Plan 25-02 acceptance criteria (`pytest tests/integration/memberships/test_freeze_helpers.py -x -q exits 0`) to pass on a Plan-25-01 schema.

## Issues Encountered

- Initial test run revealed the pre-existing fixture gap above; fixed inline in Task 2 commit.
- `ruff` flagged `password: str = "hunter22hunter22"` in the new `make_user` fixture (S107 hardcoded password); resolved with `# noqa: S107 -- test password literal` matching the pattern at the top of the file.

## Verification Evidence

- `uv run python -c "from app.modules.memberships.repository import insert_freeze_period, get_open_freeze_period, get_freeze_period_by_id, compute_freeze_days_used, _freeze_days_used_subquery"` — exits 0 (all 5 symbols importable).
- `uv run python -c "...; sq = _freeze_days_used_subquery(); assert 'membership_id' in [c.name for c in sq.c]; assert 'days_used' in [c.name for c in sq.c]"` — OK.
- `uv run mypy app/modules/memberships/repository.py` — `Success: no issues found in 1 source file`.
- `uv run mypy app/modules/memberships/ tests/integration/memberships/conftest.py tests/integration/memberships/test_freeze_helpers.py` — `Success: no issues found in 9 source files`.
- `uv run ruff check app/modules/memberships/ tests/integration/memberships/` — `All checks passed!`.
- `uv run pytest tests/integration/memberships/test_freeze_helpers.py -x -q` — `2 passed in 0.23s`.
- `uv run pytest tests/integration/memberships/test_list_expiring.py tests/integration/memberships/test_resolver.py tests/integration/memberships/test_freeze_helpers.py -x -q` — `22 passed in 2.73s` (no regression on prior membership integration tests).
- `uv run pytest tests/unit/ -x -q` — `301 passed in 0.48s` (no unit-test regression).
- `grep -E 'session\.(commit|flush)\(\)' app/modules/memberships/repository.py | grep -v '^#'` — only the docstring line "Transaction control: NO `session.commit()` and NO `session.flush()` calls live here." matches; no actual call sites exist (caller-owns-txn invariant preserved).
- `find_active_for_client` body: `git diff` shows the function is byte-identical (only additions appear in the diff).

## User Setup Required
None — no external service configuration required.

## Next Phase Readiness
- Plan 25-03 (service layer) can now compose `repository.insert_freeze_period`, `repository.get_open_freeze_period`, and `repository.compute_freeze_days_used` as building blocks for `service.freeze_membership` / `service.unfreeze_membership` / cancel-during-freeze branch (D-25-07..09).
- The `_freeze_days_used_subquery` helper is reserved for a future list-view optimisation; Plan 25-04 (schemas/router) can ship the per-row scalar via `compute_freeze_days_used` per D-25-18 admission for default page=20.
- The `make_user` / `make_client` / extended `make_plan` / `make_membership` fixtures are now sufficient to compose freeze-cycle / freeze-limit / freeze-race integration tests in Plan 25-05 without further conftest churn.
- No blockers.

## Self-Check: PASSED

**Files verified:**
- FOUND: apps/backend/app/modules/memberships/repository.py (5 freeze helpers present: insert_freeze_period, get_open_freeze_period, get_freeze_period_by_id, compute_freeze_days_used, _freeze_days_used_subquery)
- FOUND: apps/backend/tests/integration/memberships/test_freeze_helpers.py (2 test functions: zero_rows_returns_zero, one_closed_period_ceil_rounds_up)
- FOUND: apps/backend/tests/integration/memberships/conftest.py (make_user + make_client fixtures present, make_plan / make_membership populate freeze fields)

**Commits verified:**
- FOUND: 4a2bb2e (Task 1)
- FOUND: 1e25967 (Task 2)

---
*Phase: 25-memberships-freeze-backend*
*Completed: 2026-05-08*
