---
phase: 18-arq-scheduled-expire-memberships
plan: 01
subsystem: backend
tags: [backend, arq, memberships, sql, audit, sqlalchemy, ruff, ast-gate]

# Dependency graph
requires:
  - phase: 17-membership-instances-resolver-backend
    provides: "Membership ORM model + status='active|expired|cancelled'; update_membership_status repo helper; _assert_can_expire service helper"
  - phase: 15-foundations-rbac-audit-taxonomy-helper-hoisting
    provides: "LOCKED_AUDIT_EVENTS frozenset incl. (membership_expired, membership); AST commit-gate (SVC001) + AST audit-taxonomy walker"
provides:
  - "repository.expire_due_rows(session, today) -> Sequence[Row[(UUID, UUID)]] — single-statement bulk UPDATE…RETURNING(id, client_id) helper"
  - "service._expire_due_memberships(session, today=None) -> int — private orchestrator with SVC001 marker; iterates rows emitting per-row literal-string audit emits; returns count"
  - "ruff.toml lint.external = ['SVC'] — registers SVC001 prefix as a known external rule code so RUF102 no longer fires on the production callsite"
affects: [18-02 worker entry, 18-03 WorkerSettings, 18-04 docker-compose, 18-05 integration tests, 18-06 verification]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Bulk UPDATE…RETURNING via SQLAlchemy Core for co-transactional N-row mutate + audit emit (Pitfall 4 mitigation)"
    - "SVC001 caller-owns-txn marker on private (`_`-prefixed) service helper consumed by ARQ worker (Phase 18 D-01) — first production use"
    - "ruff lint.external = ['SVC'] to register a non-native rule prefix for noqa markers consumed by an AST gate"

key-files:
  created:
    - "apps/backend/tests/integration/memberships/test_expire_due_rows.py"
    - "apps/backend/tests/integration/memberships/test_expire_due_memberships_service.py"
  modified:
    - "apps/backend/app/modules/memberships/repository.py — added expire_due_rows + Row/update/Sequence imports"
    - "apps/backend/app/modules/memberships/service.py — added _expire_due_memberships + date import"
    - "apps/backend/ruff.toml — added [lint] external = ['SVC']"

key-decisions:
  - "Worker, NOT service, owns session.commit (D-01) — service helper carries SVC001 marker"
  - "Bulk path skips _assert_can_expire (D-03) — SQL WHERE status='active' is the gate, MVCC isolates concurrent admin cancels"
  - "today is datetime.date computed in Python (D-05) — TZ-unambiguous against TZ=UTC container; production passes today=None and service falls back to ZoneInfo('Europe/Moscow')"
  - "Strict `<` filter on end_date — inclusive end_date semantics (Phase 15 Key Decisions): a row with end_date == today stays active until tomorrow's tick"
  - "ruff.toml gains lint.external = ['SVC'] so RUF102 does not fire on the SVC001 marker (first production callsite)"

patterns-established:
  - "Service-level bulk-mutate helper (`_<verb>_due_<resources>`) — pattern for future scheduled expiry jobs (e.g. v1.3+ expire_otps, aggregate_visits_daily)"
  - "Private (`_`-prefixed) async def carrying `# noqa: SVC001 caller-owns-txn` on the def line — accepted by AST commit-gate, rejected if either prefix or marker missing"
  - "Test files use AST walking (NOT raw text search) when verifying source-text contracts so docstring text doesn't false-positive"

requirements-completed: [ARQ-02]

# Metrics
duration: 6min
completed: 2026-05-07
---

# Phase 18 Plan 01: Bulk-expire helpers Summary

**Single-statement `UPDATE memberships SET status='expired' WHERE end_date < :today AND status='active' RETURNING id, client_id` repository helper plus a private SVC001-marked service orchestrator that emits one literal-string `audit.emit("membership_expired", "membership", actor_user_id=None, ...)` per affected row — ready for the Plan 18-02 worker entry to wrap with `await session.commit()`.**

## Performance

- **Duration:** ~6 min
- **Started:** 2026-05-07T18:29:18Z
- **Completed:** 2026-05-07T18:35:12Z
- **Tasks:** 2 (both TDD: RED then GREEN, 4 commits)
- **Files modified:** 5 (2 created, 3 modified)

## Accomplishments

- `repository.expire_due_rows(session, today)` issues exactly one SQL statement and returns `(membership_id, client_id)` tuples for every row flipped from `active` to `expired`. Verified by 5 integration tests covering: due row found, idempotent retry returns 0, status='cancelled' is skipped, inclusive `end_date == today` stays active.
- `service._expire_due_memberships(session, today=None) -> int` orchestrates the bulk path: resolves `today` to `datetime.now(ZoneInfo('Europe/Moscow')).date()` when absent, calls the repository helper, emits per-row audit events with the locked taxonomy `("membership_expired", "membership")`, and returns the integer count. Verified by 4 integration tests + AST static check.
- AST commit-gate at `tests/unit/test_service_commit_gate.py` accepts the new private helper because the def line carries `# noqa: SVC001 caller-owns-txn`. AST audit-taxonomy gate at `tests/unit/test_audit_taxonomy.py` accepts the new emit callsite because both `event` and `resource_type` are literal strings already in `LOCKED_AUDIT_EVENTS`.
- Full backend test suite (486 tests) passes; mypy strict (65 source files) clean; ruff (whole tree) clean; import-linter (3 contracts) green.

## Task Commits

Each task was committed atomically using TDD (RED then GREEN):

1. **Task 1 RED — failing tests for expire_due_rows** — `9ea91c1` (test)
2. **Task 1 GREEN — expire_due_rows bulk repository helper** — `daa2f40` (feat)
3. **Task 2 RED — failing tests for _expire_due_memberships service** — `6db2a8b` (test)
4. **Task 2 GREEN — _expire_due_memberships private orchestrator + ruff.toml SVC external + test cleanup** — `9a5d7e5` (feat)

## Files Created/Modified

- **Created** `apps/backend/tests/integration/memberships/test_expire_due_rows.py` — 5 tests covering bulk SQL behavior + static no-commit/no-flush check.
- **Created** `apps/backend/tests/integration/memberships/test_expire_due_memberships_service.py` — 4 tests covering service-level orchestration: 1 due → returns 1 + audit row inserted with locked payload shape; 0 due → returns 0; today=None → MSK fallback; AST static check (private name + SVC001 marker + no commit/flush + no `_assert_can_expire`).
- **Modified** `apps/backend/app/modules/memberships/repository.py` — added `Sequence` from `collections.abc`, `Row` and `update` from `sqlalchemy`, and `expire_due_rows` helper at end of file.
- **Modified** `apps/backend/app/modules/memberships/service.py` — added `date` to existing datetime import; appended `_expire_due_memberships` private orchestrator with `# noqa: SVC001 caller-owns-txn` marker on the def line.
- **Modified** `apps/backend/ruff.toml` — added `[lint] external = ["SVC"]` so RUF102 does not fire on the SVC001 noqa.

## Verbatim audit emit callsite (proof of literal-string compliance)

```python
        await audit.emit(
            session,
            "membership_expired",  # LITERAL (Phase 15 INFRA-11 AST gate)
            actor_user_id=None,  # system-driven cron — no human actor
            resource_type="membership",  # LITERAL
            resource_id=membership_id,
            client_id=str(client_id),  # JSONB-serialisable
        )
```

`("membership_expired", "membership")` is in `LOCKED_AUDIT_EVENTS` (`app/core/audit.py:110`); both arguments are `ast.Constant(str)` so `tests/unit/test_audit_taxonomy.py::test_every_audit_emit_uses_literal_strings` and `::test_every_audit_emit_pair_is_in_locked_set` both pass.

## SVC001 + private-name decision rationale

Per Phase 18 D-01, the worker (Plan 18-02 `app.workers.scheduled.expire_memberships:expire_memberships(ctx)`) is the transaction owner — it opens the session from `ctx["sessionmaker"]`, calls `_expire_due_memberships`, and `await session.commit()`s. The service helper therefore MUST NOT commit, but it IS a write path (it enrolls audit_log INSERTs in the session via `audit.emit`). The Phase 15 INFRA-13 AST commit-gate flags exactly this shape unless one of two conditions holds:

1. The function carries `await session.commit()`, OR
2. The function name starts with `_` AND the def line carries `# noqa: SVC001 caller-owns-txn`.

Since (1) is forbidden by D-01, only (2) remains. Both halves are mandatory: a public name + SVC001 marker is rejected by `test_synthetic_public_function_with_svc001_is_rejected`; a private name without the marker is rejected by `test_synthetic_missing_commit_is_detected`.

## Confirmation that `_assert_can_expire` was NOT called from the bulk path (D-03)

`tests/integration/memberships/test_expire_due_memberships_service.py::test_expire_due_memberships_source_carries_svc001_marker_and_no_commit` walks the AST of `_expire_due_memberships` and asserts no `ast.Call` with `func.id == "_assert_can_expire"` appears. The bulk path's gate is `WHERE status='active'` in the SQL; Postgres MVCC isolates concurrent admin cancels (whichever transaction commits first wins; the loser sees 0 rows). Per CD-06 the helper itself stays in `service.py` for the Phase 17 TESTS-10 9-cell unit matrix.

## Decisions Made

- All key decisions were locked at plan time (D-01 through D-05, CD-06). Implementation followed verbatim.
- One implementation-time decision: register the `SVC` prefix as `lint.external` in `ruff.toml` rather than per-file-ignore RUF102. The marker is a project-wide invariant (any future private write-path helper called from a worker will reuse it), so a tree-wide registration is cheaper than annotating every callsite.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 — Blocking] ruff RUF102 on SVC001 marker**
- **Found during:** Task 2 (after appending `_expire_due_memberships` to service.py)
- **Issue:** ruff reported `RUF102 [*] Invalid rule code in `# noqa`: SVC001` because `SVC` is not a native ruff rule prefix. Removing the marker would make the AST commit-gate reject the function (the marker is mandatory per Phase 15 INFRA-13 / Phase 18 D-01); keeping it failed `uv run ruff check`. Mutually exclusive without configuration.
- **Fix:** Added `external = ["SVC"]` under `[lint]` in `apps/backend/ruff.toml` with a docstring explaining the rationale. Ruff now treats `SVC001` as a known external code and does not flag it as invalid.
- **Files modified:** `apps/backend/ruff.toml`
- **Verification:** `uv run --frozen ruff check .` passes (whole tree). AST commit-gate still passes. No other behaviour change.
- **Committed in:** `9a5d7e5` (Task 2 GREEN commit)

**2. [Rule 1 — Bug] Static no-commit test false-positived on docstring text**
- **Found during:** Task 2 GREEN run (after implementing `_expire_due_memberships`)
- **Issue:** The first version of `test_expire_due_memberships_source_carries_svc001_marker_and_no_commit` used `"session.commit" in body` as a string search. The function's docstring legitimately quotes `await session.commit()` to document the worker's commit ownership — so the test failed even though no actual call existed.
- **Fix:** Replaced raw-text body inspection with AST walking — parse the function with `ast.parse`, locate the `_expire_due_memberships` AsyncFunctionDef, and walk its body looking for `ast.Call` nodes with `func.attr in {"commit", "flush"}` whose `func.value` is `ast.Name("session")`. Docstring text is `ast.Constant(str)`, never `ast.Call`, so it doesn't match.
- **Files modified:** `apps/backend/tests/integration/memberships/test_expire_due_memberships_service.py`
- **Verification:** Test passes; the same approach also detects `_assert_can_expire` calls correctly.
- **Committed in:** `9a5d7e5` (Task 2 GREEN commit, alongside the implementation)

**3. [Rule 1 — Bug] Unused `uuid4` import in test file**
- **Found during:** Task 2 GREEN ruff sweep
- **Issue:** F401 unused import in `test_expire_due_rows.py` (left over from earlier draft).
- **Fix:** Dropped `uuid4` from the `from uuid import …` line.
- **Files modified:** `apps/backend/tests/integration/memberships/test_expire_due_rows.py`
- **Verification:** ruff clean.
- **Committed in:** `9a5d7e5` (alongside Task 2 GREEN commit)

**4. [Rule 1 — Style] SIM102 nested-if in test file**
- **Found during:** Task 2 GREEN ruff sweep
- **Issue:** ruff suggested combining nested `if isinstance(func, ast.Attribute):` with the inner predicate via `and`.
- **Fix:** Flattened to a single composite `if` expression.
- **Files modified:** `apps/backend/tests/integration/memberships/test_expire_due_memberships_service.py`
- **Verification:** ruff clean.
- **Committed in:** `9a5d7e5` (alongside Task 2 GREEN commit)

---

**Total deviations:** 4 auto-fixed (1 blocking config, 3 small bugs/style in own added files)
**Impact on plan:** All four deviations addressed problems in code added by THIS plan (the SVC001 callsite + new test files). No pre-existing code was touched. Repository helper / service helper / AST gate behaviour unchanged. Plan acceptance criteria all met verbatim.

## Issues Encountered

- The `# noqa: SVC001 caller-owns-txn` marker is a Phase 15 INFRA-13 invariant but was previously documented only in `app/core/services.py` docstrings, never in production code. This plan is the first to use it on a real callsite, which exposed the latent ruff RUF102 issue. Fixed in `ruff.toml` (deviation 1 above) so future plans (e.g. 18-02 worker entry, future v1.3+ scheduled jobs) won't re-encounter the failure.

## User Setup Required

None — purely backend internal helpers. No external service configuration. Plan 18-04 will add the `arq-worker` docker-compose service and require `DATABASE_URL` / `REDIS_URL` env wiring; this plan only adds Python code.

## Next Phase Readiness

- **Plan 18-02 (Worker entry)** can import `app.modules.memberships.service._expire_due_memberships` and wrap it with `await session.commit()` exactly per D-01.
- **Plan 18-05 (Integration tests for the worker)** can build atop the existing test fixtures (`make_plan` / `make_membership` / `db_session`) — the helpers are already exercised there.
- **No blockers.** All static gates (mypy strict, ruff, lint-imports, AST commit-gate, AST audit-taxonomy) green; full backend test suite (486 tests) green.

## Self-Check: PASSED

Files created exist:

- `apps/backend/app/modules/memberships/repository.py` — verified contains `async def expire_due_rows`
- `apps/backend/app/modules/memberships/service.py` — verified contains `async def _expire_due_memberships(  # noqa: SVC001 caller-owns-txn`
- `apps/backend/ruff.toml` — verified contains `external = ["SVC"]`
- `apps/backend/tests/integration/memberships/test_expire_due_rows.py` — created (5 tests)
- `apps/backend/tests/integration/memberships/test_expire_due_memberships_service.py` — created (4 tests)

Commits exist:

- `9ea91c1` — test(18-01): add failing tests for expire_due_rows repository helper
- `daa2f40` — feat(18-01): add expire_due_rows bulk repository helper
- `6db2a8b` — test(18-01): add failing tests for _expire_due_memberships service orchestrator
- `9a5d7e5` — feat(18-01): add _expire_due_memberships private service orchestrator

Acceptance gates run and passed:

- `cd apps/backend && uv run pytest tests/unit/test_service_commit_gate.py tests/unit/test_audit_taxonomy.py` → 10 passed
- `cd apps/backend && uv run mypy app/modules/memberships/` → Success: no issues found in 6 source files
- `cd apps/backend && uv run lint-imports` → 3 contracts kept, 0 broken
- `cd apps/backend && uv run pytest` (full suite) → 486 passed
- `cd apps/backend && uv run ruff check .` → All checks passed

---

*Phase: 18-arq-scheduled-expire-memberships*
*Completed: 2026-05-07*
