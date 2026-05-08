---
phase: 23-hygiene-active-sessions-backend-parallel-eligible
plan: "01"
subsystem: auth
tags:
  - auth
  - sessions
  - hygiene
  - error-mapping
  - csrf
  - structlog
dependency_graph:
  requires:
    - Phase 5 auth service (authenticate, verify_password, AppError hierarchy)
    - Phase 6 CSRF gate (verify_csrf)
    - Phase 9 pagination (PaginatedData, PageQuery)
    - Phase 13 audit.emit / LOCKED_AUDIT_EVENTS
  provides:
    - InvalidSession(AppError) exception class
    - UUID parse wrap at get_current_user (HYG-02)
    - login_verify_error structlog WARNING with reason/email_lower/ip (HYG-01)
    - Redis session JSON extended with user_agent + channel (CD-01)
    - list_user_sessions service function (HYG-03)
    - revoke_family service function (HYG-03)
    - GET /api/v1/auth/sessions endpoint
    - POST /api/v1/auth/sessions/{family_id}/revoke endpoint
    - session_revoked audit event in LOCKED_AUDIT_EVENTS (taxonomy delta)
    - openapi.json + schema.d.ts updated with sessions surface
  affects:
    - Phase 22 FE-09 (admin-web sessions management UI — unblocked by this plan)
    - Any FE code branching on `code === 'invalid_session'` vs `code === 'invalid_token'`
tech_stack:
  added: []
  patterns:
    - structlog BoundLoggerLazyProxy cache reset fixture (conftest.py autouse, same as Phase 18 W-3)
    - LOCKED_AUDIT_EVENTS frozenset AST gate extended to 30 entries
    - SHA-256 token-hash-to-family_id resolution for is_current (no extra DB column)
    - 404-collapse on unknown-family AND cross-user family (enumeration prevention)
    - Self-revoke detection via sha256(sz_refresh) lookup in revoke router handler
key_files:
  created:
    - apps/backend/app/core/exceptions.py (InvalidSession class added)
    - apps/backend/tests/integration/auth/conftest.py
    - apps/backend/tests/integration/auth/test_login_argon2_hygiene.py
    - apps/backend/tests/integration/auth/test_invalid_session.py
    - apps/backend/tests/integration/auth/test_sessions_endpoints.py
  modified:
    - apps/backend/app/core/dependencies.py (UUID parse wrap)
    - apps/backend/app/core/audit.py (LOCKED_AUDIT_EVENTS +1 entry, 30 total)
    - apps/backend/tests/unit/test_audit_taxonomy.py (count 29→30)
    - apps/backend/app/modules/auth/schemas.py (ActiveSessionItem, ActiveSessionsListResponse)
    - apps/backend/app/modules/auth/service.py (HYG-01 WARNING + CD-01 Redis + list_user_sessions + revoke_family)
    - apps/backend/app/modules/auth/router.py (GET /sessions + POST /sessions/{family_id}/revoke)
    - apps/backend/openapi.json (193 insertions — sessions paths + ActiveSessionItem schema)
    - packages/api-client/src/schema.d.ts (158 insertions — sessions paths typed)
    - packages/api-client/src/schema.contract.test.ts (Phase 23 CD-05 positive assertions)
decisions:
  - "HYG-01: structlog WARNING emitted by authenticate() caller (service.py), not inside verify_password(); this keeps verify_password() boundary narrow and lets the caller control log context (ip, email_lower)"
  - "HYG-02: InvalidSession raised only at UUID(claims.sub) — the NARROWEST safe wrap site; valid UUID for non-existent user still returns invalid_token (user_not_found) to preserve existing FE branching"
  - "CD-01: Redis session JSON extended with user_agent+channel; NO new DB column; Redis is truth for display metadata, Postgres RefreshToken is truth for revocation state"
  - "is_current resolution: SHA-256(sz_refresh cookie) → RefreshToken.token_hash lookup (no new cookie, no new claim); fallback to None when no sz_refresh presented (e.g., short-lived token users)"
  - "404-collapse: unknown family_id AND cross-user family_id both return 404 not_found to prevent session enumeration (D-23-6)"
  - "Self-revoke: detected in router by hashing the presented sz_refresh and looking up its family_id; triggers clear_session_cookies() on the response"
  - "conftest.py autouse fixture: clears structlog BoundLoggerLazyProxy cache on auth.service._log before each test; required because cache_logger_on_first_use=True caches processor chain on first call, breaking capture_logs() in subsequent tests"
metrics:
  duration: "~90 minutes (across two sessions)"
  completed: "2026-05-08"
  tasks_completed: 5
  files_changed: 14
---

# Phase 23 Plan 01: Auth Hygiene + Sessions Backend Summary

Closes two v1.1 carryover error-mapping gaps (HYG-01: Argon2 verify-error returns 401 with structlog WARNING instead of 500; HYG-02: tampered cookie UUID parse raises InvalidSession(401) instead of ValueError(500)) and ships GET/POST /auth/sessions backend endpoints with Redis-only metadata extension, audit integration, and byte-stable drift-gate refresh.

## Tasks Completed

| Task | Name | Commit | Key Files |
|------|------|--------|-----------|
| 1 | InvalidSession + UUID wrap + audit taxonomy | cf5558d | exceptions.py, dependencies.py, audit.py, test_audit_taxonomy.py |
| 2 | Sessions service layer | bac2c01 | auth/service.py, auth/schemas.py |
| 3 | Sessions router | 686b661 | auth/router.py |
| 4 | Integration tests (17 tests GREEN) | 631c645 | test_login_argon2_hygiene.py, test_invalid_session.py, test_sessions_endpoints.py |
| 5 | Drift gate refresh + structlog cache fix | d703c84 | openapi.json, schema.d.ts, schema.contract.test.ts, tests/integration/auth/conftest.py |

## What Was Built

### HYG-01: Argon2 verify-error → 401 + structlog WARNING

`authenticate()` in `auth/service.py` now catches `InvalidPassword` (which is raised by `verify_password()` for both `VerifyMismatchError` and `InvalidHashError`), emits `_log.warning("login_verify_error", reason=..., email_lower=..., ip=...)`, and re-raises. The `_classify_verify_error()` helper inspects `exc.__cause__` to set `reason` to one of `invalid_hash`, `verify_mismatch`, or `other`. The audit row stays generic (`reason='invalid_credentials'`) to preserve the Phase 5 AUTH-EP-02 timing/info equivalence invariant.

The structlog `reason=invalid_hash` value is visible in ops logs for triage without leaking any raw material (D-23-14 negative assert: no `password`, `password_hash`, `user_id`, etc. in the warning).

### HYG-02: Tampered UUID → 401 invalid_session

`get_current_user` in `dependencies.py` wraps the existing `UUID(claims.sub)` call in a `try/except ValueError` that raises `InvalidSession("invalid_session")`. The wrap site is minimal — only the UUID parse is wrapped. A valid UUID for a non-existent user still falls through to the user_loader path and returns `invalid_token` (user_not_found), preserving the FE branching: `invalid_session` = cookie tampered (force re-login), `invalid_token` = token expired (auto-refresh).

### HYG-03: GET /api/v1/auth/sessions + POST /api/v1/auth/sessions/{family_id}/revoke

**Service layer (`list_user_sessions`):**
- Fetches alive `RefreshToken` rows for the user, aggregates by `family_id` (Python, not SQL DISTINCT ON — real session counts are bounded 1-3)
- Reads Redis per-family key for `last_used_at`, `user_agent`, `channel`; falls back to created_at / None / 'email_password' when Redis has no metadata (pre-CD-01 sessions)
- Resolves `is_current` via SHA-256(presented_refresh_token) → `token_hash` lookup in `RefreshToken` table
- Sorts: `is_current=True` first, then `last_used_at DESC`

**Service layer (`revoke_family`):**
- Fetches `RefreshToken` rows for family + user; returns `"not_found"` if none (404-collapse for cross-user enumeration prevention)
- Returns `"noop"` if all already revoked (idempotent)
- Otherwise: sets `revoked_at`, emits `audit.emit("session_revoked", resource_type="auth_session", ...)`, commits, cleans Redis; returns `"revoked"`

**Router:**
- `GET /sessions`: CSRF-exempt (GET semantics), passes `sz_refresh` cookie value to `list_user_sessions`
- `POST /sessions/{family_id}/revoke`: RBAC-04 ordering (require_authenticated BEFORE verify_csrf), maps service results to HTTP responses, detects self-revoke and clears cookie matrix

**Redis metadata extension (CD-01):**
`_write_session_keys()` now accepts `user_agent: str | None = None` and `channel: str = "email_password"`. The session JSON stored in Redis gains both fields. `issue_tokens()` and `rotate_refresh()` pass these through. No Alembic migration required.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] structlog BoundLogger cache breaks capture_logs() in sequential tests**
- **Found during:** Task 5 verification (full suite run revealed HYG-01 test failing after 10 other tests)
- **Issue:** `configure_logging()` sets `cache_logger_on_first_use=True`. After the first test invokes `_log` in `auth.service`, the `BoundLoggerLazyProxy` caches the processor chain. `structlog.testing.capture_logs()` in subsequent tests replaces the current config's processor list, but the cached logger still points at the old list — so `capture_logs` misses the `login_verify_error` WARNING entirely. The test passed in isolation but failed when run after others.
- **Fix:** Added `tests/integration/auth/conftest.py` with `@pytest.fixture(autouse=True)` that deletes `service_mod._log.__dict__["bind"]` before each test. This forces the lazy proxy to re-resolve processors from the current config on its next call. Identical pattern to Phase 18 W-3 fix in `tests/integration/workers/conftest.py`.
- **Files modified:** `apps/backend/tests/integration/auth/conftest.py` (new)
- **Commit:** d703c84

### Out-of-Scope Pre-existing Issues

Logged to `deferred-items.md`:
- `tests/integration/visits/test_visits_self_checkin.py::test_self_checkin_happy_path` — pre-existing `AttributeError: 'tuple' object has no attribute 'channel'` failure, present before Phase 23 started (confirmed via git stash regression check)
- 130 mypy errors across 15 files — all pre-existing, same counts before and after Phase 23 execution

## Known Stubs

None. All session data is live (from Redis + Postgres). The `user_agent`/`channel` fields return `None`/'email_password' fallbacks for pre-CD-01 sessions (sessions created before this plan), which is intentional and documented.

## Threat Flags

| Flag | File | Description |
|------|------|-------------|
| threat_flag: new_authenticated_endpoint | apps/backend/app/modules/auth/router.py | GET /api/v1/auth/sessions — no RBAC check (intentional: users manage own sessions only); CSRF-exempt per GET semantics |
| threat_flag: new_authenticated_endpoint | apps/backend/app/modules/auth/router.py | POST /api/v1/auth/sessions/{family_id}/revoke — CSRF-gated; 404-collapse prevents session enumeration |

Both endpoints are covered by the plan's threat model. No additional surface introduced beyond what HYG-03 specified.

## Self-Check

### Created files exist:
- apps/backend/app/core/exceptions.py — modified (InvalidSession added)
- apps/backend/tests/integration/auth/conftest.py — new
- apps/backend/tests/integration/auth/test_login_argon2_hygiene.py — new
- apps/backend/tests/integration/auth/test_invalid_session.py — new
- apps/backend/tests/integration/auth/test_sessions_endpoints.py — new

### Commits exist:
- cf5558d Task 1
- bac2c01 Task 2
- 686b661 Task 3
- 631c645 Task 4
- d703c84 Task 5

### Test counts:
- 589 tests pass (excluding pre-existing test_visits_self_checkin.py failure)
- 17 new integration tests in Phase 23 test files

## Self-Check: PASSED
