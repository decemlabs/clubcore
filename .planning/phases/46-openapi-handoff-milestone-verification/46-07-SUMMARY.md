---
phase: 46-openapi-handoff-milestone-verification
plan: 07
subsystem: verification.race-tests
tags: [VER-10, D-46-14, SVC001, race, real-commit, anti-oracle, deactivate, refresh]
dependency_graph:
  requires:
    - phase: 43
      decision: D-43-20 (refresh anti-oracle 4-case parity)
    - phase: 43
      decision: CR-04 (deactivate atomic UoW — single commit covers
        UPDATE + revoke_all + session_revoked_all audit + user_deactivated audit)
    - phase: 45
      decision: D-45-28 (real-commit engine pattern for race tests)
    - phase: 38
      decision: BOOK-TEST-01 (real-commit engine + ASGI auth via _build_authed_client)
  provides:
    - VER-10 race test #3 (deactivate + refresh)
  affects:
    - apps/backend/app/modules/users/service.py (regression catch surface)
    - apps/backend/app/modules/auth/service.py (regression catch surface)
tech_stack:
  added: []
  patterns:
    - real_commit_engine fixture (own AsyncEngine + TRUNCATE teardown)
    - asgi-lifespan LifespanManager + create_app() per-test
    - asyncio.gather concurrent HTTP calls against the real ASGI app
    - dual cookie-jar AsyncClients (owner + target) for SAVEPOINT-free auth
key_files:
  created:
    - apps/backend/tests/integration/test_deactivate_refresh_race.py
  modified: []
decisions:
  - "Accept BOTH race orderings (deactivate-first 401 + refresh-first 200→next 401)
    rather than forcing one — Phase 43 Plan 43-10 documented that the observable
    code under real prod sequencing oscillates between Branch A
    (account_inactive→invalid_session) and Branch C
    (family_reuse_detected→invalid_token) depending on whether the deactivate
    UoW commits before the refresh service-layer probe runs. Pinning to one
    branch would produce flaky CI."
  - "Accept the FULL anti-oracle-safe code set {account_inactive, invalid_token,
    invalid_session} for the failure branch, mirroring the test plan's grep-gate
    contract. The current rotate_refresh implementation maps to invalid_session
    (Phase 43 D-43-20 harmonisation), but keeping account_inactive in the set
    guards against a future Plan-43-10 reversal where the explicit code is
    restored."
  - "Use real_commit_engine + LifespanManager+create_app, NOT the
    SAVEPOINT-wrapped db_session. The deactivate UoW commits across multiple
    service calls and rotate_refresh equally commits — neither composes with
    the outer SAVEPOINT and the race is observable only across SEPARATE
    COMMITTED transactions (mirrors BOOK-TEST-01 + D-45-28 reasoning)."
  - "Build authed clients via login HTTP POST (not by direct cookie injection)
    so the test exercises the same cookie threading the prod client uses; this
    is also how BOOK-TEST-01 and the refresh anti-oracle 4-case fixtures
    bootstrap their sessions."
metrics:
  duration: ~10min
  tasks_completed: 1
  files_created: 1
  files_modified: 0
  completed_date: 2026-05-20
---

# Phase 46 Plan 07: Deactivate + Refresh Race Test Summary

VER-10 race test #3 lands: concurrent `PATCH /users/{id}/deactivate` (owner)
+ `POST /auth/refresh` (target) under `asyncio.gather` against real Postgres,
asserting SVC001 service-owns-txn atomicity in
`users/service.deactivate_user` + `auth/service.refresh_session`.

## Objective

Catch any regression that splits the deactivate-and-revoke UoW (Phase 43
CR-04). Specifically: if `repository.deactivate_user` and
`get_user_session_invalidator()(...)` ever committed in separate UoWs, the
target user's `/auth/refresh` could observe `is_active=true` after the
family was already revoked (or vice versa) — silently slipping a fresh
access cookie to a deactivated user. The race test exposes this regression
because the next refresh call would still succeed.

## Implementation

### File: `apps/backend/tests/integration/test_deactivate_refresh_race.py` (284 lines)

Single test `test_deactivate_refresh_race` + a `real_commit_engine` fixture.

**Fixture (`real_commit_engine`):**
- Creates an independent `AsyncEngine` via `create_async_engine(settings.database_url)`.
- Defensively probes Postgres at entry; skips on unreachable Postgres.
- Teardown: `TRUNCATE refresh_tokens, users, audit_log RESTART IDENTITY CASCADE`.

**Test flow:**
1. Seed one OWNER + one RECEPTION user (both `is_active=True`) via the
   real-commit session — each gets a unique email keyed on `uuid4().hex[:8]`
   to avoid collisions across reruns.
2. Build the real FastAPI app via `create_app()` inside an
   `asgi-lifespan.LifespanManager` context so `app.state.engine` /
   `app.state.redis` are populated.
3. Flush Redis to evict any prior-test rate-limit / idempotency keys.
4. Build two `AsyncClient` instances via `_build_authed_client` —
   each logs in via `POST /api/v1/auth/login` against the REAL app
   (no SAVEPOINT override), populating its own cookie jar with
   `sz_access` / `sz_refresh` / `sportzal_csrf`.
5. Race: `asyncio.gather(_deactivate(), _refresh())`:
   - `_deactivate`: `PATCH /api/v1/users/{target_id}/deactivate` with the
     owner's `X-CSRF-Token` header.
   - `_refresh`: `POST /api/v1/auth/refresh` (CSRF-exempt per Phase 6 D-09).
6. Assert:
   - `deact_status in {200, 204}`.
   - If `refresh_status == 401`: `code in {account_inactive, invalid_token,
     invalid_session}`.
   - Else `refresh_status == 200`: issue a second refresh and assert it
     returns 401 with a code in the same set (SVC001 atomic-UoW invariant).
7. Post-race DB invariant: `users.is_active = false` for the target.

## Acceptance Gates (all green)

| Gate | Expected | Actual |
|------|----------|--------|
| File exists | yes | yes |
| `grep -c asyncio.gather` | ≥1 | 5 |
| `grep -c "account_inactive\|invalid_token\|invalid_session"` | ≥3 | 10 |
| `grep -c real_commit_engine` | ≥1 | 3 |
| `grep -c "TRUNCATE.*users\|TRUNCATE.*refresh"` | ≥1 | 1 |
| Asserts `is_active is False` | yes | yes |
| Test passes (or skips) | 1 passed/skipped | **1 passed in 0.42s** |
| Line count | ≥120 | 284 |

## Observed Race Ordering

Local run (single iteration): refresh-first path triggered — the
race-loss was caught on the SECOND `/auth/refresh` call as the
SVC001 atomic UoW invariant requires. The test passes deterministically
because it accepts BOTH orderings; CI flakiness from PG scheduler
variance is structurally impossible by design.

## Deviations from Plan

### Auto-applied adjustments

**1. [Rule 3 - blocker] Removed `--no-cov` flag from verify command**
- **Found during:** Task 1 (initial test run)
- **Issue:** `pytest tests/integration/test_deactivate_refresh_race.py -v --no-cov`
  failed with `pytest: error: unrecognized arguments: --no-cov` — coverage
  plugin is not installed in this repo's pytest env (asyncio + anyio only;
  see `pyproject.toml` plugin list).
- **Fix:** Ran without `--no-cov`. No further change required.
- **Files modified:** none
- **Commit:** n/a (test-runner invocation only)

**2. [Rule 2 - missing critical functionality] Wrapped HTTP race in
`LifespanManager(create_app())`**
- **Found during:** Task 1 authoring
- **Issue:** The plan body sketched `app = create_app()` without
  `LifespanManager` and without a Redis flush. Without the lifespan, the
  ASGI request would crash on the missing `app.state.engine` (per
  `tests/conftest.py` top-doc comment); without the Redis flush,
  rate-limit / idempotency keys from prior tests can mask the race.
- **Fix:** Wrapped the HTTP body in `async with LifespanManager(app):`
  and added `await app.state.redis.flushdb()` before client construction
  — matches the BOOK-TEST-01 + tests/conftest.py `app` fixture pattern.
- **Files modified:** `apps/backend/tests/integration/test_deactivate_refresh_race.py`
- **Commit:** 91aad56 (single atomic commit per plan)

**3. [Rule 1 - bug avoidance] Used unique email per run**
- **Found during:** Task 1 authoring
- **Issue:** Hard-coded race-owner / race-target emails would collide on
  re-run within the same Postgres instance because the test commits real
  rows and only TRUNCATEs at FIXTURE teardown — between commit and
  teardown, a retry would fail with a UNIQUE violation.
- **Fix:** Keyed both emails on `uuid4().hex[:8]` so reruns are
  collision-free.
- **Files modified:** `apps/backend/tests/integration/test_deactivate_refresh_race.py`
- **Commit:** 91aad56

**4. [Rule 1 - bug avoidance] Used `_build_authed_client` per-user
instead of cookie sharing on a single client**
- **Found during:** Task 1 authoring
- **Issue:** The plan sketch used two `AsyncClient` context managers
  (`owner_client` + `target_client`) but the cookie copy
  `recheck.cookies = target_client.cookies` for the second-refresh case
  would not get the rotated `sz_refresh` if the first refresh succeeded
  (httpx cookie jar mutation is in-place on `target_client`, so
  reusing it directly already carries the rotated cookies).
- **Fix:** Reused `target_client` for the second refresh instead of
  building a `recheck` client. Cleaner and avoids the cookie-copy bug.
- **Files modified:** `apps/backend/tests/integration/test_deactivate_refresh_race.py`
- **Commit:** 91aad56

### Auth gates

None — both logins succeeded against the locally-running Postgres /
Redis. No interactive user step required.

## Threat Flags

None — the test does NOT introduce new network endpoints, auth paths,
file-access patterns, or schema changes. It exercises existing surface
(`/api/v1/auth/login`, `/api/v1/auth/refresh`, `/api/v1/users/{id}/deactivate`)
that is already in the Phase 43 threat model.

## Known Stubs

None.

## Self-Check: PASSED

- [x] File `apps/backend/tests/integration/test_deactivate_refresh_race.py` exists
- [x] Commit `91aad56` exists on branch `worktree-agent-a90286c6b3c5e49b1`
- [x] `pytest` reports `1 passed` (0.42s)
- [x] All grep acceptance gates green
- [x] No STATE.md / ROADMAP.md modifications (worktree-parallel-executor
      constraint honoured)
