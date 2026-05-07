---
phase: 18-arq-scheduled-expire-memberships
plan: 05
subsystem: backend
tags: [backend, arq, tests, integration, idempotency, structlog-test]

# Dependency graph
requires:
  - phase: 18-arq-scheduled-expire-memberships
    provides: "Plan 18-02 — async def expire_memberships(ctx) -> int worker entry coroutine"
  - phase: 18-arq-scheduled-expire-memberships
    provides: "Plan 18-01 — service._expire_due_memberships(session, today=None) -> int (private SVC001 bulk-expire orchestrator + LOCKED membership_expired audit emit)"
  - phase: 5-database-foundation
    provides: "tests/conftest.py db_session fixture using async_sessionmaker(join_transaction_mode='create_savepoint') for SAVEPOINT-isolated per-test rollback"
provides:
  - "tests/integration/workers/ — new top-level test scope mirroring tests/integration/{clients,memberships,...}/"
  - "Fixtures: seeded_user, seeded_plan, seeded_client, make_membership_with_dates, worker_ctx (hand-built ARQ ctx wrapping the SAVEPOINT db_session)"
  - "ARQ-TEST-01 (test_expire_memberships.py) — 3-row happy-path proof + inclusive-end_date invariant + summary log line capture"
  - "ARQ-TEST-02 (test_expire_memberships_idempotent.py) — two-call SQL-level idempotency proof + count=0 summary log on no-op"
  - "Pattern: structlog.testing.capture_logs() works correctly across multiple tests despite cache_logger_on_first_use=True via bind-attribute reset autouse fixture (W-3)"
affects: [18-06 verification — overall phase test pass, automated proof for ROADMAP SC #1 + #2]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "ARQ ctx test double — _SavepointSessionmaker wraps the SAVEPOINT-mode db_session so the worker's `async with session_factory() as session` yields the same session the test seeds against"
    - "structlog.testing.capture_logs() per-call isolation — two separate `with structlog.testing.capture_logs() as ...` contexts in the idempotency test isolate first vs second worker call's log streams"
    - "Cached-logger invalidation pattern (Phase 18 W-3) — autouse fixture deletes `_log.__dict__['bind']` on the module-level structlog BoundLoggerLazyProxy so capture_logs sees emissions even after `create_app()` reconfigures structlog mid-suite"

key-files:
  created:
    - "apps/backend/tests/integration/workers/__init__.py"
    - "apps/backend/tests/integration/workers/conftest.py"
    - "apps/backend/tests/integration/workers/test_expire_memberships.py"
    - "apps/backend/tests/integration/workers/test_expire_memberships_idempotent.py"
  modified: []

key-decisions:
  - "W-2 SAVEPOINT auto-restart resolved via Branch A — the outer `db_session` fixture in apps/backend/tests/conftest.py:101 already uses `async_sessionmaker(..., join_transaction_mode='create_savepoint')` (SQLAlchemy 2.0 built-in). The shim `_SavepointSessionmaker.__call__` simply yields `db_session` directly; no `await session.begin_nested()` needed in `__aenter__`. The idempotency test's two consecutive `session.commit()` calls succeed because `create_savepoint` mode auto-begins a new nested transaction on the next operation after each release."
  - "Rule 3 fix on `seeded_client` — the Plan 18-05 stub spec used `Client(full_name=..., phone=...)` but the canonical Client ORM model (apps/backend/app/modules/clients/models.py) has `last_name`/`first_name` NOT NULL columns and a NOT NULL `created_by_user_id` FK to `users.id`. The fixture seeds the actual schema (last_name='Тестовый', first_name='Клиент', phone='+79990000001', created_by_user_id=seeded_user.id). Required adding a `seeded_user` fixture upstream of `seeded_client` to satisfy the FK."
  - "W-3 (Rule 1 bug) discovered during overall verification: structlog.testing.capture_logs missed events on the second test in a run because the module-level `_log = structlog.get_logger(...)` in `app/workers/scheduled/expire_memberships.py` caches its BoundLogger under `cache_logger_on_first_use=True`, and each test's `create_app()` calls `configure_logging` which replaces `_CONFIG.default_processors` with a fresh list. Fixed by an autouse fixture that deletes `_log.__dict__['bind']` before each test, forcing re-resolution against the live config."
  - "Both tests use `pytest_asyncio.mode = 'auto'` (project default per apps/backend/pyproject.toml) — no `@pytest.mark.asyncio` decorator needed. The plan template carried the decorator in its CONCRETE block; we omitted it to match project convention."

patterns-established:
  - "Pattern: ARQ scheduled-worker integration test layout — `tests/integration/workers/{conftest.py, test_<job>.py, test_<job>_idempotent.py}` per scheduled job, with fixtures seeding the FK chain (User → Client → Plan → Membership) directly via SAVEPOINT-mode session"
  - "Pattern: idempotency assertion shape — call worker twice in sequence; first call returns N, second returns 0; assert audit_log row count is unchanged between calls; assert two separate `capture_logs` contexts each see exactly one summary line with `count=N` / `count=0`"
  - "Pattern: cached-logger reset autouse fixture for any test scope that calls module-level structlog loggers AND uses `capture_logs` — required for any test file that mixes `create_app()` (per-test reconfigure) with structlog event assertions"

requirements-completed: [ARQ-TEST-01, ARQ-TEST-02]

# Metrics
duration: 5min
completed: 2026-05-07
---

# Phase 18 Plan 05: ARQ `expire_memberships` integration tests Summary

**Two integration tests prove the Plan 18-02 worker entry satisfies ARQ-TEST-01 (correctness — count=1, inclusive end_date stays active, exactly 1 audit row, exactly 1 summary log line) and ARQ-TEST-02 (idempotency — second call returns 0, no duplicate audit row, count=0 summary on no-op) using real Postgres + SAVEPOINT-isolated per-test rollback.**

## Performance

- **Duration:** ~5 min
- **Started:** 2026-05-07T19:00:55Z
- **Completed:** 2026-05-07T19:06:14Z
- **Tasks:** 3 (Task 1 conftest + Tasks 2/3 the two tests) + 1 deviation commit (W-3 logger cache fix)
- **Files created:** 4

## Accomplishments

- **`apps/backend/tests/integration/workers/__init__.py` + `conftest.py` shipped** — new test scope with `seeded_user`, `seeded_plan`, `seeded_client`, `make_membership_with_dates`, `worker_ctx` fixtures. Module docstring documents the W-2 SAVEPOINT auto-restart dependency on the outer `db_session` fixture's `join_transaction_mode='create_savepoint'`.
- **`test_expire_memberships.py` (ARQ-TEST-01) shipped** — 3-row fixture (yesterday/today/tomorrow). One call to `await expire_memberships(worker_ctx)` returns count=1, inserts exactly 1 `membership_expired` audit row with `payload={"client_id": "<uuid-str>"}` and `actor_user_id=None`, flips the yesterday row to `status='expired'`, leaves today + tomorrow rows `status='active'` (inclusive end_date invariant), and emits exactly 1 structlog INFO `expire_memberships_complete count=1` line.
- **`test_expire_memberships_idempotent.py` (ARQ-TEST-02) shipped** — same 3-row fixture. Two consecutive worker calls: first returns 1 + 1 audit row + count=1 summary; second returns 0 + 0 new audit rows (`audit_count_after_second == 1`) + count=0 summary log line. Proves SQL-level `WHERE status='active'` idempotency gate (Pitfall 4); proves CD-03 invariant that summary line emits even on no-op runs.
- **Rule 1 bug fix (W-3)** — autouse fixture in workers conftest invalidates the module-level `_log` BoundLogger cache before each test, so `structlog.testing.capture_logs()` correctly intercepts events when multiple tests run in sequence with intervening `create_app()` reconfigures.
- mypy strict (4 source files in `tests/integration/workers/`) clean; ruff clean; lint-imports green (3 contracts kept). Combined run with the existing `tests/integration/memberships/test_expire_due_memberships_service.py` (Plan 18-01 tests) passes 6/6 in 0.51s.

## Task Commits

Each task was committed atomically:

1. **Task 1: tests/integration/workers/ scope + conftest fixtures** — `b9114cd` (test)
2. **Task 2: ARQ-TEST-01 happy-path test** — `399119b` (test)
3. **Task 3: ARQ-TEST-02 idempotency test** — `a77eac4` (test)
4. **W-3 fix: invalidate cached structlog logger between worker tests** — `28bc2da` (fix) — Rule 1 bug discovered during overall verification (both tests passed in isolation; second test failed when run together with first)

## Files Created/Modified

- **Created** `apps/backend/tests/integration/workers/__init__.py` (1 line) — package marker.
- **Created** `apps/backend/tests/integration/workers/conftest.py` (199 lines) — fixtures (seeded_user / seeded_plan / seeded_client / make_membership_with_dates / worker_ctx) + autouse `_reset_worker_logger_cache` (W-3). Module docstring documents both W-2 (SAVEPOINT auto-restart) and the Rule 3 fix on `seeded_client` schema (NOT NULL `created_by_user_id` FK requires upstream `seeded_user`).
- **Created** `apps/backend/tests/integration/workers/test_expire_memberships.py` (78 lines) — `test_expire_memberships_flips_only_overdue_active_rows` covering ARQ-TEST-01.
- **Created** `apps/backend/tests/integration/workers/test_expire_memberships_idempotent.py` (87 lines) — `test_expire_memberships_idempotent` covering ARQ-TEST-02.

## Decisions Made

- **W-2 SAVEPOINT branch chosen: A (built-in `join_transaction_mode='create_savepoint'`).** Verified `apps/backend/tests/conftest.py:101` already uses `join_transaction_mode='create_savepoint'`. The `_SavepointSessionmaker._SessionContext.__aenter__` simply returns `db_session` directly. Two consecutive worker calls in the idempotency test both succeed — the SQLAlchemy 2.0 built-in mode auto-begins a fresh nested transaction on the next operation after each `session.commit()` releases the SAVEPOINT. Branch B (explicit `await session.begin_nested()` per `__aenter__`) was NOT needed and is documented inline as a regression-fallback only.
- **Skip `@pytest.mark.asyncio` decorator.** Project pyproject.toml sets `asyncio_mode = "auto"`. Plan template included the decorator; we omitted to match the existing pattern in `tests/integration/memberships/`.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Schema mismatch] Fixed `seeded_client` shape to match canonical Client ORM**

- **Found during:** Task 1 — reading `apps/backend/app/modules/clients/models.py`.
- **Issue:** Plan 18-05 stub used `Client(full_name="ARQ Test Client", phone="+79990000001")`. The actual model has NO `full_name` field; required NOT NULL columns are `last_name`, `first_name`, `phone`, AND `created_by_user_id` (FK to `users.id` ON DELETE RESTRICT).
- **Fix:** Added a `seeded_user` fixture (Owner role, valid bcrypt hash via `app.core.security.hash_password`); changed `seeded_client` to `Client(last_name='Тестовый', first_name='Клиент', phone='+79990000001', created_by_user_id=seeded_user.id)`.
- **Files modified:** `apps/backend/tests/integration/workers/conftest.py`.
- **Commit:** `b9114cd` (Task 1).

**2. [Rule 1 - Bug] Fixed structlog `capture_logs` missing events on second test in a run**

- **Found during:** Overall verification (both tests passed in isolation; the idempotency test failed when run together with the happy-path test).
- **Issue:** Module-level `_log = structlog.get_logger(...)` in `app/workers/scheduled/expire_memberships.py` is a BoundLoggerLazyProxy that caches its bound logger on first use (per `cache_logger_on_first_use=True`). The cached BoundLogger holds a reference to `_CONFIG.default_processors` from the FIRST test's `configure_logging()` invocation. Each subsequent test's `app` fixture builds a fresh app via `create_app()`, which calls `configure_logging` and replaces `_CONFIG.default_processors` with a NEW list. `structlog.testing.capture_logs()` mutates the new list, but the cached logger still uses the old reference, so capture_logs sees zero events.
- **Fix:** Added an autouse `_reset_worker_logger_cache` fixture to the workers conftest that deletes the cached `bind` attribute on the module-level `_log` proxy before each test. The proxy's `__getattr__` then re-resolves processors from the live `_CONFIG.default_processors` on the next call.
- **Files modified:** `apps/backend/tests/integration/workers/conftest.py`.
- **Commit:** `28bc2da` (W-3 fix).

No architectural changes (Rule 4) were required.

## Confirmation: inclusive end_date invariant proven

`test_expire_memberships.py` line 64:

```python
assert inclusive_today.status == "active", (
    "today's row stays active until tomorrow's tick (inclusive end_date)"
)
```

The 3-row fixture seeds `end_date ∈ {today-1, today, today+1}`. After one worker call, only the today-1 row flips. The today row's `status` stays `'active'` because the SQL filter is strict `<` (`Membership.end_date < :today`). This is the inclusive-end_date invariant from Phase 15 Key Decisions, restated in ROADMAP SC #1.

## Confirmation: SQL-level idempotency proven

`test_expire_memberships_idempotent.py` lines 75-83:

```python
audit_count_after_second = await db_session.scalar(
    select(func.count())
    .select_from(AuditLog)
    .where(AuditLog.action == "membership_expired")
)
assert audit_count_after_second == 1, (
    f"second call must NOT insert duplicate audit row; ..."
)
```

After two consecutive worker calls, `count('membership_expired') == 1` in the audit_log. The second call's bulk UPDATE matches zero rows (its `WHERE status='active'` filter excludes the just-flipped row), so its audit-emit loop iterates zero times. ARQ `unique=True` plays no role — this is pure SQL-level defence (Pitfall 4 mitigation).

## Confirmation: W-2 branch chosen

Branch A — outer conftest's `join_transaction_mode='create_savepoint'`. The `_SavepointSessionmaker._SessionContext.__aenter__` yields `db_session` directly with no `begin_nested()` call. Both worker calls in the idempotency test commit successfully; no `InvalidRequestError` or `PendingRollbackError`. The Branch B fallback (explicit `await session.begin_nested()` per `__aenter__`) is documented inline in the conftest module docstring for any future regression that drops `create_savepoint` from the outer fixture.

## Issues Encountered

W-3 (described above as Rule 1 deviation #2) — the second test's `capture_logs` block initially saw zero events. Fixed via the autouse logger-cache invalidation fixture. No other issues.

## User Setup Required

None — purely backend test code. Tests skip cleanly if local Postgres is unavailable (the outer `db_session` fixture's connectivity probe handles the skip — see `apps/backend/tests/conftest.py:75-91`).

## Next Phase Readiness

- **Plan 18-06 (verification)** can run `cd apps/backend && uv run pytest tests/integration/workers/ tests/unit/workers/ -v` and combine the integration-test pass with the WorkerSettings unit tests (Plan 18-03). All Phase 18 SC items #1 (single-transaction UPDATE), #2 (idempotent retry), and #3 (cron tick at 06:05 MSK — proven structurally via Plan 18-03) now have automated proofs.
- **No blockers.** All static gates green; both ARQ-TEST-01 + ARQ-TEST-02 pass; mypy strict + ruff + lint-imports clean.

## Self-Check: PASSED

Files created exist:

- `apps/backend/tests/integration/workers/__init__.py` — verified via `test -f`
- `apps/backend/tests/integration/workers/conftest.py` — verified via `test -f` + `uv run python -c "from tests.integration.workers import conftest"` exit 0
- `apps/backend/tests/integration/workers/test_expire_memberships.py` — verified via `test -f`
- `apps/backend/tests/integration/workers/test_expire_memberships_idempotent.py` — verified via `test -f`

Commits exist:

- `b9114cd` — test(18-05): add tests/integration/workers/ scope + conftest fixtures
- `399119b` — test(18-05): add ARQ-TEST-01 — expire_memberships happy-path test
- `a77eac4` — test(18-05): add ARQ-TEST-02 — expire_memberships idempotency test
- `28bc2da` — fix(18-05): invalidate cached structlog logger between worker tests

Acceptance gates run and passed:

- `cd apps/backend && uv run pytest tests/integration/workers/ -v` → 2 passed in 0.22s
- `cd apps/backend && uv run mypy tests/integration/workers/` → Success: no issues found in 4 source files
- `cd apps/backend && uv run ruff check tests/integration/workers/` → All checks passed!
- `cd apps/backend && uv run lint-imports` → 3 contracts kept, 0 broken
- Combined regression run with existing memberships service tests: `pytest tests/integration/memberships/test_expire_due_memberships_service.py tests/integration/workers/ -v` → 6 passed in 0.51s

---

*Phase: 18-arq-scheduled-expire-memberships*
*Completed: 2026-05-07*
