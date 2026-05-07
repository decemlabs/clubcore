---
phase: 18-arq-scheduled-expire-memberships
plan: 02
subsystem: backend
tags: [backend, arq, workers, transaction-owner, structlog, mypy-strict]

# Dependency graph
requires:
  - phase: 18-arq-scheduled-expire-memberships
    provides: "Plan 18-01 — service._expire_due_memberships(session, today=None) -> int (private SVC001-marked bulk-expire orchestrator)"
  - phase: 7-telegram-bot-worker
    provides: "D-06 worker -> owning-module exception template + AsyncExitStack/sessionmaker pattern in app/workers/telegram_bot.py"
provides:
  - "app/workers/scheduled/__init__.py — namespace marker for ARQ scheduled jobs"
  - "app/workers/scheduled/expire_memberships.py — async def expire_memberships(ctx: dict[str, Any]) -> int — Phase 18 D-01 transaction owner"
  - "Locked summary-event shape `<job_name>_complete count=N` for all future scheduled jobs (CD-03)"
affects: [18-03 WorkerSettings registers expire_memberships in functions/cron_jobs, 18-05 integration tests exercise this entry coroutine, 18-06 verification]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "ARQ scheduled-job entry coroutine — async def <job>(ctx: dict[str, Any]) -> int, transaction owner per D-01"
    - "Worker -> owning-module service import (D-09) — file in app/workers/scheduled/<job>.py imports app.modules.<owner>.service exclusively"
    - "End-of-run summary structlog INFO `<job_name>_complete count=N` AFTER session.commit() returns (CD-03 / Pitfall 14 mitigation)"

key-files:
  created:
    - "apps/backend/app/workers/scheduled/__init__.py"
    - "apps/backend/app/workers/scheduled/expire_memberships.py"
  modified: []

key-decisions:
  - "Worker entry, not service helper, owns `await session.commit()` (D-01) — the `async with session_factory() as session:` block scopes the transaction; commit happens in the worker after the helper returns"
  - "Summary log line `_log.info('expire_memberships_complete', count=count)` is emitted AFTER commit returns successfully (CD-03) — proves the cron tick booted, the connection worked, and the SQL resolved"
  - "Service helper imported as `from app.modules.memberships import service as memberships_service` and called as `memberships_service._expire_due_memberships(session)` — leading underscore is intentional (private worker-only contract)"
  - "No try/except wrapping the session block — exceptions MUST propagate so the SQLAlchemy unit-of-work rolls back; the SQL-level idempotency gate (`WHERE status='active'`) makes retry safe (D-01)"
  - "No explicit `today=` argument — production path passes `today=None` so the service computes `datetime.now(ZoneInfo('Europe/Moscow')).date()` per D-05"

patterns-established:
  - "Pattern: ARQ worker entry signature — `async def <job>(ctx: dict[str, Any]) -> int` with required `ctx['sessionmaker']` populated by `WorkerSettings.on_startup` (Plan 18-03 wires this)"
  - "Pattern: structlog logger naming — `structlog.get_logger('workers.scheduled.<job>')` mirrors module path, integrates with `merge_contextvars` for job_id/job_name correlation"
  - "Pattern: file-level docstring documents D-09 worker -> owning-module exception verbatim (mirrors `app/workers/telegram_bot.py` D-06 prose) — no contract change needed in `.importlinter`"

requirements-completed: [ARQ-01]

# Metrics
duration: 1min
completed: 2026-05-07
---

# Phase 18 Plan 02: ARQ `expire_memberships` worker entry Summary

**Thin transaction-owner coroutine `async def expire_memberships(ctx) -> int` that ARQ invokes per cron tick — opens session from `ctx['sessionmaker']`, delegates the bulk UPDATE + per-row audit emits to Plan 18-01's `_expire_due_memberships`, awaits `session.commit()`, then emits the locked structlog INFO `expire_memberships_complete count=N` ops summary line.**

## Performance

- **Duration:** ~1 min
- **Started:** 2026-05-07T18:44:09Z
- **Completed:** 2026-05-07T18:45:32Z
- **Tasks:** 2 (Task 1 namespace marker + Task 2 worker entry)
- **Files modified:** 2 (both newly created)

## Accomplishments

- `app/workers/scheduled/__init__.py` namespace marker shipped — docstring locks the convention that each `app/workers/scheduled/<job>.py` is the I/O fanout for ONE owning module's recurring task (no cross-module imports inside scheduled files).
- `app/workers/scheduled/expire_memberships.py` shipped — `async def expire_memberships(ctx: dict[str, Any]) -> int` opens a session from `ctx['sessionmaker']`, calls `memberships_service._expire_due_memberships(session)` (Plan 18-01), awaits `session.commit()`, emits `_log.info("expire_memberships_complete", count=count)` AFTER commit returns, and returns the int count for ARQ's result store.
- File docstring documents D-09 (worker -> owning-module exception) and D-01 (worker is transaction owner) verbatim — mirror of `app/workers/telegram_bot.py` lines 1-12 D-06 prose.
- mypy strict (10 source files in `app/workers/`) clean; ruff (`app/workers/scheduled/`) clean; import-linter (3 contracts) green — confirming D-09 is a documented exception, not a contract relaxation.

## Task Commits

Each task was committed atomically:

1. **Task 1: Create `app/workers/scheduled/__init__.py` namespace marker** — `df3cbba` (feat)
2. **Task 2: Create `app/workers/scheduled/expire_memberships.py` worker entry** — `c025da0` (feat)

_Note: Plan-level frontmatter declared `tdd="true"` on Task 2, but the phase-context override (provided in the executor prompt) directed: "Integration tests in Plan 18-05 will exercise this — do NOT add tests in 18-02. The plan's own verify step is just import + signature checks." Followed phase-context override; tests deferred to Plan 18-05 per the explicit phase-level direction._

## Files Created/Modified

- **Created** `apps/backend/app/workers/scheduled/__init__.py` (16 lines) — namespace marker. Docstring documents D-06/D-09 worker -> owning-module exception; lists current (`expire_memberships.py` -> memberships) and future (`notify_expiring.py`, `aggregate_visits_daily.py`) examples; locks the rule that scheduled files MUST NOT import services from two different modules.
- **Created** `apps/backend/app/workers/scheduled/expire_memberships.py` (72 lines) — worker entry coroutine. Single public `async def expire_memberships(ctx: dict[str, Any]) -> int`. Imports the service helper as `from app.modules.memberships import service as memberships_service`. Body opens session via `async with session_factory() as session:`, calls the helper with no explicit `today=` (production path uses MSK fallback per D-05), awaits commit, emits summary log AFTER commit, returns count. No try/except — exceptions propagate so the unit-of-work rolls back.

## Decisions Made

All decisions were locked at plan time (D-01, D-09, CD-03, plus the implicit Phase 18 specifics around no-try/except and no-explicit-today). Implementation followed the plan's CONCRETE content verbatim. One execution-time choice:

- **Skip TDD on Task 2 per phase-context override.** The plan's `<task tdd="true">` would normally trigger RED -> GREEN, but the executor's `<phase_context>` block (load-bearing operator instruction) explicitly directed: "Test note: Integration tests in Plan 18-05 will exercise this — do NOT add tests in 18-02." Tests deferred to Plan 18-05's `tests/integration/workers/` scope per CD-05 anyway. The plan's own automated verify steps (mypy + ruff + lint-imports + import-name check) all pass.

## Deviations from Plan

None — plan executed exactly as written. CONCRETE content blocks copied verbatim; all 13 acceptance-criteria literal-string checks for Task 2 confirmed via grep:

```
✓ async def expire_memberships(ctx: dict[str, Any]) -> int:
✓ from app.modules.memberships import service as memberships_service
✓ session_factory = ctx["sessionmaker"]
✓ async with session_factory() as session:
✓ count = await memberships_service._expire_due_memberships(session)
✓ await session.commit()
✓ _log.info("expire_memberships_complete", count=count)
✓ Phase 18 D-09 in docstring
✓ Phase 18 D-01 in docstring
✓ commit line (66) appears BEFORE log line (71)
```

## Confirmation: summary log AFTER commit returns

`apps/backend/app/workers/scheduled/expire_memberships.py` line ordering:

```
Line 65:  async with session_factory() as session:
Line 66:      count = await memberships_service._expire_due_memberships(session)
Line 67:      await session.commit()
Line 68:  (session block exits)
Line 69:  # Summary log AFTER commit returns successfully (CD-03). NOT an audit
Line 70:  # event — payload carries the count only; ...
Line 71:  _log.info("expire_memberships_complete", count=count)
Line 72:  return count
```

The `_log.info` line is OUTSIDE the `async with` session block AND positionally after `await session.commit()` — so a commit failure (e.g. integrity violation, connection drop) raises before the log line is reached, and the cron tick logs no spurious "complete" line.

## Confirmation: lint-imports green proves D-09 is a documented exception, not a contract relaxation

`uv run lint-imports` output:

```
Analyzed 67 files, 114 dependencies.
core must not import modules KEPT
modules cannot import each other KEPT
integrations must not import modules KEPT
Contracts: 3 kept, 0 broken.
```

Reading the contracts in `apps/backend/.importlinter`:

- `core-not-depend-on-modules`: forbids `app.core` -> `app.modules`. The new file lives in `app.workers.scheduled`, not `app.core`. Unaffected.
- `modules-independent`: forbids cross-module imports between `app.modules.*` siblings. The new file is in `app.workers.*`, not `app.modules.*`. Unaffected.
- `integrations-not-depend-on-modules`: forbids `app.integrations` -> `app.modules`. The new file is in `app.workers.scheduled`, not `app.integrations`. Unaffected.

No contract enforces `app.workers ⊥ app.modules`. The `app.workers.scheduled.expire_memberships -> app.modules.memberships.service` edge is therefore legal under existing contracts; D-09 is **documentation of an intentional architectural choice** in `app/workers/__init__.py`'s and the new file's docstrings, not a relaxation of any existing rule.

## Issues Encountered

None.

## User Setup Required

None — purely backend internal Python code. No external service configuration, no env-var changes. Plan 18-04 will add the `arq-worker` docker-compose service and wire `DATABASE_URL` / `REDIS_URL`; this plan only adds the entry coroutine.

## Next Phase Readiness

- **Plan 18-03 (WorkerSettings)** can register `expire_memberships` directly: `from app.workers.scheduled.expire_memberships import expire_memberships` then `functions = [expire_memberships]` and `cron_jobs = [cron(expire_memberships, hour=3, minute=5, unique=True, keep_cronjob_progress=60)]`. The function name (`expire_memberships`) matches the cron-resolution invariant from CD-04 (`assert all(c.coroutine.__name__ in {f.__name__ for f in functions} ...)`).
- **Plan 18-05 (Integration tests)** can build a `ctx = {"sessionmaker": db_session_factory}` and call `await expire_memberships(ctx)` directly — no real ARQ runtime needed; it's just an async function call.
- **No blockers.** All static gates green; Plan 18-01 dependency satisfied; D-09 / D-01 / CD-03 wiring all confirmed via literal-string acceptance checks.

## Self-Check: PASSED

Files created exist:

- `apps/backend/app/workers/scheduled/__init__.py` — verified via `test -f` + `uv run python -c "import app.workers.scheduled"` exit 0
- `apps/backend/app/workers/scheduled/expire_memberships.py` — verified via `test -f` + `uv run python -c "from app.workers.scheduled.expire_memberships import expire_memberships; assert expire_memberships.__name__ == 'expire_memberships'"` exit 0

Commits exist:

- `df3cbba` — feat(18-02): add app/workers/scheduled namespace marker
- `c025da0` — feat(18-02): add expire_memberships ARQ worker entry

Acceptance gates run and passed:

- `cd apps/backend && uv run mypy app/workers/scheduled/` → Success: no issues found in 2 source files
- `cd apps/backend && uv run mypy app/workers/` (sanity, full workers tree) → Success: no issues found in 10 source files
- `cd apps/backend && uv run ruff check app/workers/scheduled/` → All checks passed!
- `cd apps/backend && uv run lint-imports` → 3 contracts kept, 0 broken
- `cd apps/backend && uv run python -c "from app.workers.scheduled.expire_memberships import expire_memberships"` → exit 0

---

*Phase: 18-arq-scheduled-expire-memberships*
*Completed: 2026-05-07*
