---
phase: 05-user-schema-email-password-auth
plan: 07
subsystem: testing

tags: [pytest, sqlalchemy, savepoint, asyncpg, fastapi-dependency-overrides, redis, test-fixtures]

# Dependency graph
requires:
  - phase: 05-user-schema-email-password-auth
    provides: User ORM model + auth_initial migration (plan 05-03), engine/sessionmaker on app.state (Phase 2), Redis lifespan + get_redis seam (Phase 5)
provides:
  - SAVEPOINT-based per-test rollback (db_session) compatible with service-level session.commit()
  - async_client fixture wired with app.dependency_overrides[get_db] + app.dependency_overrides[get_redis] so route handlers reached via ASGITransport see the same SAVEPOINT-wrapped session and the same Redis client tests flush
  - Smoke test asserting the rollback contract (two consecutive inserts of the same UNIQUE email both succeed)
  - User.role SAEnum bug fixed (lowercase values match the CHECK constraint)
affects: [05-08, 06-rbac-wiring, 07-telegram-otp, 08-clients-module, all-future-integration-tests]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - SQLAlchemy 2.0 cookbook "Joining a session into an external transaction" (engine.connect → trans.begin → bind session with join_transaction_mode="create_savepoint" → trans.rollback on teardown)
    - FastAPI dependency-override seam to wire test fixtures into ASGITransport-bound routes (get_db, get_redis)
    - SAEnum + values_callable pattern for StrEnum-to-DB binding when CHECK constraint uses values, not names

key-files:
  created:
    - apps/backend/tests/integration/test_db_session_savepoint.py
  modified:
    - apps/backend/tests/conftest.py
    - apps/backend/app/modules/auth/models.py
    - apps/backend/alembic/versions/0001_auth.py

key-decisions:
  - "db_session opens its own connection on app.state.engine and runs the connectivity probe INSIDE the outer transaction (not before begin()) — calling connection.execute() before begin() autobegins a competing transaction and breaks begin()"
  - "async_client now depends on db_session (pytest fixture composition) and installs both get_db and get_redis overrides; the get_redis override is preventative (mirrors current get_redis behaviour) so a future per-request connection in get_redis doesn't silently desync test fixtures from route code"
  - "Used values_callable on SAEnum so role binds the StrEnum value ('owner') instead of the member name ('OWNER'); migration sa.Enum literals updated to match so alembic check stays clean"

patterns-established:
  - "Pattern: per-test SAVEPOINT rollback — open connection, begin outer trans, bind AsyncSession with join_transaction_mode='create_savepoint', rollback outer trans on teardown"
  - "Pattern: ASGITransport + dependency-override seam — async_client installs app.dependency_overrides[get_db] / [get_redis] and clears them in finally"
  - "Pattern: StrEnum-to-CHECK-constraint binding — SAEnum(values_callable=lambda enum_cls: [e.value for e in enum_cls]) emits values, not names"

requirements-completed: [TEST-01]

# Metrics
duration: ~12min
completed: 2026-05-02
---

# Phase 05 Plan 07: SAVEPOINT-Based Per-Test Rollback Summary

**db_session now wraps every test in an outer transaction with `join_transaction_mode="create_savepoint"`, so service-level `session.commit()` calls become nested SAVEPOINTs that the outer rollback wipes on teardown — Plan 08's auth integration tests can reuse the same UNIQUE email across cases without IntegrityError, and the async_client now wires `get_db` + `get_redis` overrides so ASGITransport-bound routes see the same session and Redis client the test fixtures flush.**

## Performance

- **Duration:** ~12 min
- **Started:** 2026-05-02T12:53Z (approximate)
- **Completed:** 2026-05-02T13:05:47Z
- **Tasks:** 2 of 2
- **Files modified:** 4 (1 created, 3 modified)

## Accomplishments

- `db_session` switched from rollback-only to SAVEPOINT-pattern per the SQLAlchemy 2.0 cookbook. Outer transaction wipes EVERYTHING the test wrote, including service-level commits.
- `async_client` extended to install `app.dependency_overrides[get_db]` and `app.dependency_overrides[get_redis]`, with `app.dependency_overrides.clear()` cleanup in `finally`. Closes the visibility gap between fixture-seeded data and ASGI-transport-bound route handlers under READ COMMITTED.
- Smoke test (`test_db_session_savepoint.py`) inserts the same UNIQUE email in two consecutive tests and both pass — proves the rollback contract empirically and would FAIL loudly under the old fixture.
- Pre-existing `User.role` enum-binding bug discovered and auto-fixed (Rule 1) so the smoke test (and future Phase 5/8 integration tests) can actually insert users.

## Task Commits

Each task was committed atomically:

1. **Task 1: Upgrade db_session fixture to SAVEPOINT-based rollback** — `b257c86` (test)
2. **Deviation auto-fix (Rule 1): User.role SAEnum lowercase values** — `62f70dc` (fix)
3. **Task 2: Add SAVEPOINT smoke test asserting service commits roll back** — `3a89e0a` (test)

## Files Created/Modified

- `apps/backend/tests/conftest.py` — db_session now uses engine.connect + trans.begin + async_sessionmaker(bind=connection, join_transaction_mode="create_savepoint"); async_client gained dependency overrides for get_db + get_redis with clear() on teardown; connectivity probe moved inside the outer transaction to avoid autobegin clash
- `apps/backend/tests/integration/test_db_session_savepoint.py` — created; two-test pair that re-inserts the same UNIQUE email to prove SAVEPOINT rollback wipes service commits
- `apps/backend/app/modules/auth/models.py` — User.role now uses `values_callable=lambda enum_cls: [e.value for e in enum_cls]` so SAEnum binds StrEnum values ('owner', 'reception') instead of member names ('OWNER', 'RECEPTION')
- `apps/backend/alembic/versions/0001_auth.py` — sa.Enum literals updated from `("OWNER", "RECEPTION", ...)` to `("owner", "reception", ...)` so the migration matches the model and `alembic check` stays clean

## Decisions Made

- **Probe inside the outer transaction** (not before `connection.begin()`): the original plan put the `select 1` probe before `begin()`, but on a fresh AsyncConnection, `execute()` autobegins an implicit transaction that then conflicts with the explicit `begin()` and raises `InvalidRequestError`. Solution: open the connection, call `begin()` first (skip on failure), then run `select 1` inside that transaction. Skip semantics preserved.
- **async_client also overrides get_redis**: the plan flagged this as preventative; kept it because a future per-request Redis connection in `get_redis` would silently desync test fixtures from route code without the override.
- **Auto-fix the User.role bug now** (Rule 1, scope-justified): the bug was pre-existing in plan 05-03 but blocked Task 2 of plan 05-07 from completing AND would block every Phase 5/8 integration test that inserts a user. Fix is two lines (model + migration) and is verified by `alembic check` staying green.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] User.role SAEnum sent member names instead of values, violating the CHECK constraint**
- **Found during:** Task 2 (writing the SAVEPOINT smoke test) — first integration test attempting `INSERT INTO users` raised `asyncpg.exceptions.CheckViolationError: new row for relation "users" violates check constraint "ck_users_role"`.
- **Issue:** `apps/backend/app/modules/auth/models.py:36-39` declared `role: Mapped[Role] = mapped_column(SAEnum(Role, native_enum=False, length=16, validate_strings=True), ...)`. Default SAEnum behaviour with a `StrEnum` is to bind the *member name* (`'OWNER'`/`'RECEPTION'`). The CHECK constraint at `apps/backend/app/modules/auth/models.py:48` and `alembic/versions/0001_auth.py:48` accepts only lowercase *values* (`'owner'`/`'reception'`), per D-07 (frontend-parity contract). Result: every User insert raised IntegrityError.
- **Fix:** Added `values_callable=lambda enum_cls: [e.value for e in enum_cls]` to the `SAEnum(...)` call so the binding emits values, and updated `alembic/versions/0001_auth.py` `sa.Enum("OWNER", "RECEPTION", ...)` → `sa.Enum("owner", "reception", ...)` so autogenerate stays clean.
- **Files modified:** `apps/backend/app/modules/auth/models.py`, `apps/backend/alembic/versions/0001_auth.py`
- **Verification:** `uv run alembic downgrade base && uv run alembic upgrade head` succeeds; `uv run pytest tests/integration/test_alembic_clean.py` exits 0 (TEST-08 still green); `uv run pytest tests/integration/test_db_session_savepoint.py` exits 0 (both tests pass, verifying inserts now work AND rollback works); full backend test suite (119 tests) exits 0.
- **Committed in:** `62f70dc` (separate fix commit between Task 1 and Task 2 commits)

**2. [Rule 1 - Bug] Connectivity probe order broke transaction setup**
- **Found during:** Task 1 verification (alembic_clean test failure)
- **Issue:** The plan body literally instructed `await connection.execute(text("select 1"))` *before* `await connection.begin()`. On a fresh AsyncConnection, `execute()` autobegins an implicit transaction; the subsequent explicit `connection.begin()` then raises `sqlalchemy.exc.InvalidRequestError: This connection has already initialized a SQLAlchemy Transaction() object via begin() or autobegin; can't call begin() here unless rollback() or commit() is called first.`
- **Fix:** Restructured the fixture to call `engine.connect()` first (skip on failure), then `connection.begin()` (skip on failure), then run the `select 1` probe *inside* the outer transaction. `connection.close()` is called from a `finally` block to guarantee the connection returns to the pool even if `begin()` succeeded but a subsequent step failed.
- **Files modified:** `apps/backend/tests/conftest.py`
- **Verification:** `uv run pytest tests/integration/test_alembic_clean.py` exits 0 (was failing with InvalidRequestError before this change).
- **Committed in:** `b257c86` (part of Task 1 commit)

---

**Total deviations:** 2 auto-fixed (2 Rule 1 bugs)
**Impact on plan:** Both fixes were necessary for correctness. The User.role fix is technically inherited from plan 05-03, but it was caught here because this plan introduced the first integration test that inserts a User — without it, the smoke test could not pass and Plan 08 integration tests would have hit the same wall. No scope creep: only the failing column declaration + matching migration line were touched.

## Issues Encountered

- Initial Task 1 verification (`pytest tests/integration/test_alembic_clean.py`) errored with `InvalidRequestError: This connection has already initialized a SQLAlchemy Transaction()` because the connectivity probe ran before `connection.begin()`. Resolved by reordering probe + begin (see deviation #2).
- Initial Task 2 verification failed with `CheckViolationError` on the first `INSERT INTO users`. Resolved by fixing the SAEnum binding (see deviation #1) and re-running the migration on the dev compose Postgres (`alembic downgrade base` → `alembic upgrade head`).

## User Setup Required

None — all fixes are within the codebase. Developers running tests locally need a running compose Postgres + applied migrations (unchanged from previous Phase 5 plans).

## Next Phase Readiness

- Plan 05-08 (`test_login.py`, `test_refresh.py`, `test_logout.py`) can now rely on:
  - `db_session` rolls back service commits (TEST-01).
  - `async_client` routes through the SAVEPOINT-wrapped session (data seeded in fixtures is visible to handlers).
  - `app.state.redis` is the same client routes use (fixtures can flush rate-limit / session keys safely).
  - User inserts actually work (role bug fixed).
- Plan 08 (Clients module) and any other phase needing integration tests inherits the same contract.
- No blockers, no concerns.

## Self-Check: PASSED

Verification:
- File `apps/backend/tests/conftest.py` — modified (HEAD~2: b257c86)
- File `apps/backend/tests/integration/test_db_session_savepoint.py` — created (HEAD: 3a89e0a)
- File `apps/backend/app/modules/auth/models.py` — modified (HEAD~1: 62f70dc)
- File `apps/backend/alembic/versions/0001_auth.py` — modified (HEAD~1: 62f70dc)
- Commit b257c86 — present in `git log`
- Commit 62f70dc — present in `git log`
- Commit 3a89e0a — present in `git log`
- Plan-level verification (`pytest tests/integration/test_alembic_clean.py tests/integration/test_db_session_savepoint.py -x`): 4 passed
- Full backend suite: 119 passed
- mypy + ruff: clean on all modified files

---
*Phase: 05-user-schema-email-password-auth*
*Plan: 07*
*Completed: 2026-05-02*
