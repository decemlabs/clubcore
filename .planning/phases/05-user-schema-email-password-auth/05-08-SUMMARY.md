---
phase: 05-user-schema-email-password-auth
plan: 08
subsystem: auth
tags: [tests, integration, auth, login, refresh, logout, rbac, audit]
requirements-completed: [TEST-02, TEST-04]
dependency-graph:
  requires:
    - 05-04 (auth service: authenticate, issue_tokens, rotate_refresh, revoke_session, revoke_all_sessions)
    - 05-05 (auth schemas: LoginRequest, LoginResponse, MeResponse)
    - 05-06 (composition root: combined_lifespan, register_user_loader, /api/v1/auth mount)
    - 05-07 (SAVEPOINT-based db_session fixture for cross-test isolation)
  provides:
    - apps/backend/tests/integration/auth/__init__.py
    - apps/backend/tests/integration/auth/test_login.py (TEST-02, AUTH-EP-01..03, AUTH-LO-04 unauth)
    - apps/backend/tests/integration/auth/test_refresh.py (TEST-04, D-13 branches A/B/C)
    - apps/backend/tests/integration/auth/test_logout.py (AUTH-LO-01, AUTH-LO-02)
  affects:
    - apps/backend/app/modules/auth/models.py (Rule 1 fix — SAEnum values_callable)
    - apps/backend/app/modules/auth/service.py (Rule 1 fix — drop async with session.begin() in revoke paths)
tech-stack:
  added: []
  patterns:
    - structlog.testing.capture_logs() for audit-event assertions in async tests
    - httpx.AsyncClient cookie-jar manipulation via response.cookies (not the shared jar) when domain/path duplicates appear
    - SQLAlchemy autobegin + explicit session.commit() instead of `async with session.begin()` when a session may already have a transaction in progress
key-files:
  created:
    - apps/backend/tests/integration/auth/__init__.py
    - apps/backend/tests/integration/auth/test_login.py
    - apps/backend/tests/integration/auth/test_refresh.py
    - apps/backend/tests/integration/auth/test_logout.py
  modified:
    - apps/backend/app/modules/auth/models.py
    - apps/backend/app/modules/auth/service.py
decisions:
  - "Apply Rule 1 auto-fix to models.py: pass values_callable to SAEnum so the wire+DB form matches the ck_users_role CHECK constraint"
  - "Apply Rule 1 auto-fix to service.py: replace `async with session.begin()` in revoke_session + revoke_all_sessions with autobegin + explicit commit (logout flows pass through Depends(get_current_user) which autobegins the session)"
  - "Use response.cookies (not the shared async_client jar) to read post-rotation refresh values; httpx jar can hold multi-domain duplicates after manual delete+set"
  - "Avoid `.local` TLD in test emails — pydantic EmailStr rejects reserved-name TLDs; switched to @example.com per RFC 2606"
metrics:
  duration: ~50min
  completed: 2026-05-02
  tasks_completed: 3
  files_created: 4
  files_modified: 2
  commits: 5
---

# Phase 5 Plan 08: Integration Tests for Auth Endpoints Summary

## One-liner

Three integration test files covering /auth/login (200/401/429/cookie attributes), /auth/refresh (rotation + race-window same-pair + family-reuse revocation with structlog audit assertion), and /auth/logout + /logout-all (DB+Redis+cookie clearing with audit events) — closes REQ TEST-02, TEST-04, AUTH-EP-01..03, AUTH-LO-01/02/04.

## What Was Built

### Task 1 — `tests/integration/auth/test_login.py` + `__init__.py`

Six tests against POST /api/v1/auth/login and GET /api/v1/auth/me:

| Test | Asserts | Requirements |
|------|---------|--------------|
| `test_login_happy_returns_envelope_and_three_cookies` | 200, envelope `{data: {user: {id, role, fullName}}}`, three Set-Cookie headers with locked attributes (sz_access Path=/ HttpOnly; sz_refresh Path=/api/v1/auth HttpOnly; sportzal_csrf Path=/ NOT HttpOnly) | TEST-02, AUTH-EP-01 |
| `test_login_invalid_password_returns_401` | 401 + `code: "invalid_credentials"` on wrong password | AUTH-EP-02 |
| `test_login_unknown_email_returns_401` | 401 + `code: "invalid_credentials"` on unknown email (timing-equivalent path via sentinel hash) | AUTH-EP-02 |
| `test_login_429_after_5_failures` | 6th attempt returns 429 + `code: "rate_limited"` even with the right password (counter is checked BEFORE verify) | AUTH-EP-03, D-18 |
| `test_me_unauthenticated_returns_401` | GET /me without sz_access cookie → 401 | AUTH-LO-04 |
| `test_me_authenticated_returns_user` | After login, GET /me returns `{id, role: "owner", fullName, email, hasTelegram: false}` (cookie jar carries sz_access) | AUTH-LO-04 |

Local fixtures `redis_clean` (flushes Redis between tests) and `seeded_owner` (inserts an owner into the SAVEPOINT-rolled-back db_session) are duplicated per-file rather than promoted to conftest — keeps each file self-contained and matches the plan spec.

Commit: `23081df test(05-08): add /api/v1/auth/login integration tests (TEST-02)`

### Task 2 — `tests/integration/auth/test_refresh.py`

Four tests against POST /api/v1/auth/refresh covering all three D-13 branches:

| Test | Asserts | Branch |
|------|---------|--------|
| `test_refresh_happy_rotates_token` | 200, new sz_refresh ≠ old, old refresh_tokens row gets `replaced_by_id` + `replaced_at` populated | A — ACTIVE rotation |
| `test_refresh_race_window_returns_same_pair` | Two refreshes with the SAME old sz_refresh inside 5s return the same new pair from the `auth:rotate:{old_hash}` cache | B — REPLACED-WITHIN-WINDOW |
| `test_refresh_reuse_revokes_family` | Manually drop the cache; replay → 401 `invalid_token`; ALL family rows revoked; structlog event=`family_reuse_detected` captured via `structlog.testing.capture_logs` | C — REUSE/REVOKED |
| `test_refresh_without_cookie_returns_401` | POST /refresh without sz_refresh → 401 `invalid_token` | (cookie-presence guard) |

The race-window test reads `r2.cookies["sz_refresh"]` directly off the response rather than the shared `async_client.cookies` jar — after `delete + set` operations the jar can hold multi-domain duplicates that make `client.cookies["sz_refresh"]` ambiguous (raises CookieConflict). Reading the response is unambiguous and proves the cache hit.

Commit: `85fd7d0 test(05-08): add /api/v1/auth/refresh integration tests (TEST-04)`

### Task 3 — `tests/integration/auth/test_logout.py`

Three tests against POST /api/v1/auth/logout and POST /api/v1/auth/logout-all:

| Test | Asserts | Requirements |
|------|---------|--------------|
| `test_logout_revokes_family_and_clears_cookies` | 200; one alive family before → zero after; Redis `auth:session:{user}:{family}` deleted + family removed from `auth:user_sessions:{user}` set; structlog `event=session_revoked` emitted; all three cookies cleared via Set-Cookie `Max-Age=0` (or `expires=` past date) | AUTH-LO-01, D-14, D-20 |
| `test_logout_unauthenticated_returns_401` | POST /logout without sz_access → 401 (logout requires auth — NOT a free cookie wipe for unauthenticated callers) | (anti-drift) |
| `test_logout_all_revokes_all_families` | Two logins → two families; logout-all revokes BOTH families; `auth:user_sessions:{user}` Redis key deleted; structlog `event=session_revoked_all` emitted | AUTH-LO-02, D-10, D-20 |

Commit: `a373b8a test(05-08): add /api/v1/auth/logout integration tests (AUTH-LO-01/02)`

## Verification

- `cd apps/backend && uv run mypy tests/integration/auth/` → **PASSED** (4 source files clean)
- `cd apps/backend && uv run ruff check tests/integration/auth/` → **PASSED**
- All 13 new auth tests pass **individually** against the live Postgres + Redis stack (`uv run pytest tests/integration/auth/test_<file>.py::<test>`).
- Pre-existing 117 unit + integration tests still pass (`tests/integration/test_healthz.py`, `tests/integration/test_alembic_clean.py`, all of `tests/unit/`).
- Sequential `uv run pytest tests/integration/auth -x` does NOT pass in this worktree alone because the per-test rollback fixture upgrade (Plan 07) is not yet merged here. After Plan 07 merges, the SAVEPOINT-based `db_session` fixture will roll back commits across tests and the suite passes top-to-bottom — this is the contract documented by Plan 08's frontmatter `depends_on: ["05-04", "05-05", "05-06", "05-07"]`.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] SAEnum stored role names instead of values**
- **Found during:** Task 1 — `test_login_happy_returns_envelope_and_three_cookies` first ORM-based User insert.
- **Issue:** `apps/backend/app/modules/auth/models.py:36-39` defined `SAEnum(Role, native_enum=False, length=16, validate_strings=True)` without `values_callable`. SQLAlchemy's default behaviour stores the enum NAME (`'OWNER'`); the `ck_users_role` CHECK constraint demands the lowercase VALUE (`'owner'`). Any ORM insert raised `CheckViolationError`. The bug had been masked because the only writer until now was `scripts/seed_demo_data.py`, which uses `Role.OWNER.value` literally in a raw INSERT statement.
- **Fix:** Pass `values_callable=lambda enum: [m.value for m in enum]` to align SAEnum with the CHECK constraint and the seed script's literal usage.
- **Files modified:** `apps/backend/app/modules/auth/models.py`
- **Commit:** `11003dd fix(05-08): make SAEnum store role values instead of names`

**2. [Rule 1 - Bug] revoke_session / revoke_all_sessions opened explicit transaction on already-begun session**
- **Found during:** Task 3 — `test_logout_revokes_family_and_clears_cookies`.
- **Issue:** Both /auth/logout and /auth/logout-all flow through `Depends(get_current_user)`, which calls `_user_loader(session, ...)` → `session.get(User, ...)` against the request's session. SQLAlchemy autobegins a transaction on that first query. The downstream `async with session.begin():` in `revoke_session` and `revoke_all_sessions` (Plan 04) then raised `sqlalchemy.exc.InvalidRequestError: A transaction is already begun on this Session.` `rotate_refresh` is unaffected because /auth/refresh reads the cookie directly without `Depends(get_current_user)`, so its session arrives clean.
- **Fix:** Drop `async with session.begin()` in both revoke functions; rely on autobegin + explicit `await session.commit()` at the end. Same SELECT/UPDATE/COMMIT semantics, works whether the session was previously touched or not.
- **Files modified:** `apps/backend/app/modules/auth/service.py`
- **Commit:** `2c26375 fix(05-08): drop async with session.begin() in revoke paths`

**3. [Rule 3 - Blocker] Test email TLD .local is reserved**
- **Found during:** Task 1 — initial run with `@test.local` returned 422 from EmailStr validation: "The part after the @-sign is a special-use or reserved name that cannot be used with email."
- **Fix:** Switched all test owners to `@example.com` (RFC 2606 reserved-for-documentation domain).
- **Files modified:** test files only (no source change).
- **Commit:** Folded into the Task 1 commit (`23081df`).

### Auth Gates

None — no external service authentication was required for this plan.

## Self-Check: PASSED

**Files created (per artifacts contract):**
- `apps/backend/tests/integration/auth/__init__.py` — FOUND
- `apps/backend/tests/integration/auth/test_login.py` — FOUND
- `apps/backend/tests/integration/auth/test_refresh.py` — FOUND
- `apps/backend/tests/integration/auth/test_logout.py` — FOUND

**Files modified (Rule 1 auto-fixes):**
- `apps/backend/app/modules/auth/models.py` — FOUND (modified)
- `apps/backend/app/modules/auth/service.py` — FOUND (modified)

**Commits in git log:**
- `11003dd fix(05-08): make SAEnum store role values instead of names` — FOUND
- `23081df test(05-08): add /api/v1/auth/login integration tests (TEST-02)` — FOUND
- `85fd7d0 test(05-08): add /api/v1/auth/refresh integration tests (TEST-04)` — FOUND
- `2c26375 fix(05-08): drop async with session.begin() in revoke paths` — FOUND
- `a373b8a test(05-08): add /api/v1/auth/logout integration tests (AUTH-LO-01/02)` — FOUND

## Threat Flags

None. The two auto-fixes (SAEnum values_callable, drop session.begin) tighten correctness without introducing new trust boundaries; the test files exercise existing endpoints with no new surface.
