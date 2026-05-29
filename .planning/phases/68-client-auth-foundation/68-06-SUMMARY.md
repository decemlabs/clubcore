---
phase: 68-client-auth-foundation
plan: "06"
subsystem: backend-tests
tags: [security, testing, client-auth, isolation, anti-oracle, idor, phase-gate]
dependency_graph:
  requires: [68-05]
  provides: [phase-68-contract-proof]
  affects: [test-suite]
tech_stack:
  added: []
  patterns:
    - SAVEPOINT-rollback test harness (existing)
    - httpx ASGITransport over Cookie header (not per-request cookies=)
    - autouse monkeypatch for OTP sender stub
key_files:
  created:
    - apps/backend/tests/integration/client_auth/__init__.py
    - apps/backend/tests/integration/client_auth/conftest.py
    - apps/backend/tests/integration/client_auth/test_otp_isolation.py
    - apps/backend/tests/integration/client_auth/test_idor.py
    - apps/backend/tests/integration/client_auth/test_session_lifecycle.py
    - apps/backend/tests/integration/client_auth/test_byte_parity.py
  modified:
    - apps/backend/app/core/audit.py
    - apps/backend/tests/integration/test_phase51_audit_chain_invariants.py
    - apps/backend/tests/unit/test_audit_taxonomy.py
    - apps/backend/.env (not tracked — DATABASE_URL corrected from sportzal → clubcore)
decisions:
  - Cookie header over per-request cookies= to avoid httpx DeprecationWarning (filterwarnings=error)
  - autouse stub_client_otp_sender depends on app fixture to ensure it runs after lifespan
  - Refresh token rotation asserted by uniqueness; access token equality acceptable within same second
  - OtpMaxAttempts maps to HTTP 429 (service exception definition), not 401
metrics:
  duration: 45min
  completed: "2026-05-29"
  tasks_completed: 3
  files_created: 6
  files_modified: 4
---

# Phase 68 Plan 06: Security Test Suite (Phase Contract Proof) Summary

15 integration tests proving the Phase 68 security contract: two-principal isolation, anti-oracle byte-parity, parametrized IDOR sweep, full session lifecycle, and CISO-01 byte-parity guard.

## What Was Built

Four test modules in `apps/backend/tests/integration/client_auth/` with a shared conftest:

### `conftest.py`
- `stub_client_otp_sender` (autouse): monkeypatches `_client_otp_sender` to a no-op AFTER the `app` fixture runs the lifespan — prevents real Telegram API calls in tests
- `redis_clean`: flushes Redis per test (prevents rate-limit key bleed)
- `seeded_staff`, `linked_client`, `unlinked_client`, `soft_deleted_client`: DB fixtures for the 4 phone states

### `test_otp_isolation.py` (7 tests)
- `test_staff_token_rejected_by_client_endpoint` (CISO-02): staff `cc_access` token → `GET /client/me` → 401
- `test_client_token_rejected_by_staff_endpoint` (CISO-02 reverse): client `cc_client_access` → `GET /clients` → 401
- `test_otp_request_anti_oracle[linked_phone|unlinked_phone|unknown_phone|soft_deleted_phone]` (CAUTH-02): 4-case parametrize, each asserting 202
- `test_otp_request_anti_oracle_body_parity` (CAUTH-02): all 4 cases in one test; asserts byte-identical response body

### `test_idor.py` (2 tests)
- `test_get_me_returns_only_own_id[True|False]` (CISO-04): parametrized over both (A attacks B, B attacks A) orderings; asserts `data.id == attacker.id` AND `!= victim.id`

### `test_session_lifecycle.py` (3 tests)
- `test_full_session_lifecycle` (CAUTH-04): OTP request → verify (3 cookies with correct Path/HttpOnly/non-HttpOnly attributes) → GET /me 200 → refresh rotation (new refresh token) → logout (all 3 cookies cleared) → GET /me 401 (no cookie)
- `test_otp_rate_limited` (CAUTH-06): direct Redis counter manipulation to exceed daily cap; assert 429
- `test_otp_brute_force_blocked` (CAUTH-06): (max_attempts-1) wrong codes → 401 `otp_invalid`; final wrong → 429 `otp_max_attempts`

### `test_byte_parity.py` (3 tests)
- `test_no_role_client_in_permissions` (CISO-01): `"CLIENT" not in Role.__members__`; `permissions.py` source contains no `Role.CLIENT`
- `test_client_principal_has_no_role` (CISO-01): `ClientPrincipal` has no `role` annotation (D-07)
- `test_admin_web_can_ts_unchanged` (CISO-01): `can.ts` exists; no `Role.CLIENT` or `| 'client'` role union

## Test Execution Results

All 15 tests PASS with live Postgres (`clubcore` DB, migration 0044_client_refresh_token applied) and Redis.

```
15 passed in 5.54s
```

Pre-existing test failures (unrelated to this plan, confirmed via git stash):
- `test_otp_email_anti_oracle` (timing)
- `test_telegram_start.*` (2 tests)
- `test_telegram_verify_*.` (4 tests)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] LOCKED_AUDIT_EVENTS missing Phase 68 client auth events**
- **Found during:** Task 1 execution (first linked_phone OTP request)
- **Issue:** `audit.emit('client_otp_requested', resource_type='otp')` raised `AuditEventNotLockedError` — Phase 68 service uses 6 new audit event pairs but none were pre-registered in the frozenset (INFRA-15 discipline: register before any callsite)
- **Fix:** Added 6 Phase 68 event pairs to `LOCKED_AUDIT_EVENTS` in `app/core/audit.py`; updated count assertions in `test_audit_taxonomy.py` and `test_phase51_audit_chain_invariants.py` from 93 → 100
- **Files modified:** `app/core/audit.py`, `tests/unit/test_audit_taxonomy.py`, `tests/integration/test_phase51_audit_chain_invariants.py`
- **Commit:** `b1970e93`

**2. [Rule 1 - Bug] httpx per-request `cookies={}` raises DeprecationWarning (treated as error)**
- **Found during:** Task 1 execution (`test_staff_token_rejected_by_client_endpoint`)
- **Issue:** `pytest filterwarnings = ["error"]` treats all warnings as errors. httpx ≥0.27 raises `DeprecationWarning` for per-request `cookies={}` parameters.
- **Fix:** Replaced all `cookies={"name": "value"}` per-request parameters with `headers={"Cookie": "name=value; name2=value2"}` direct Cookie header strings
- **Files modified:** `test_otp_isolation.py`, `test_idor.py`, `test_session_lifecycle.py`
- **Commits:** `f3ee5724`, `6decbbc9`

**3. [Rule 1 - Bug] Real Telegram API called in tests for linked_client OTP requests**
- **Found during:** Task 1 execution (linked_phone anti-oracle test)
- **Issue:** `create_app()` registers a real Telegram bot sender via `register_client_otp_sender()` during the app lifespan. Tests with a `linked_client` (telegram_user_id set) triggered real Telegram API calls → `NetworkError`.
- **Fix:** Added `autouse=True` `stub_client_otp_sender` fixture in `conftest.py` that depends on `app` (ensures lifespan runs first) then monkeypatches `_client_otp_sender` to a no-op async callable.
- **Files modified:** `conftest.py`
- **Commit:** `f3ee5724`

**4. [Rule 1 - Bug] .env DATABASE_URL pointed to non-existent `sportzal` database**
- **Found during:** Task 1 (IDOR test initial run)
- **Issue:** `apps/backend/.env` contained `DATABASE_URL=...sportzal` but the running Postgres database is named `clubcore`. Also, migrations `0043_client_auth_otp` and `0044_client_refresh_token` had not been applied.
- **Fix:** Applied pending Alembic migrations to `clubcore` database. Updated `.env` to point to `clubcore`. (`.env` is not tracked by git.)
- **Files modified:** `.env` (untracked)
- **Commit:** N/A (infrastructure fix)

**5. [Rule 1 - Bug] `OtpMaxAttempts` HTTP status is 429 not 401**
- **Found during:** Task 2 (`test_otp_brute_force_blocked`)
- **Issue:** Test incorrectly asserted `status_code == 401` for `OtpMaxAttempts`. The exception class defines `status_code = 429` (too many requests, not unauthorized).
- **Fix:** Updated assertion to `status_code == 429`
- **Files modified:** `test_session_lifecycle.py`
- **Commit:** `6decbbc9`

**6. [Rule 1 - Bug] Access token "not rotated" assertion fails due to second-precision iat**
- **Found during:** Task 2 (`test_full_session_lifecycle`)
- **Issue:** `encode_client_token()` uses `int(issued.timestamp())` — second-precision. Two tokens minted within the same second (test environment) produce identical JWTs. Asserting `new_access_token != access_token` fails.
- **Fix:** Removed the access token equality assertion; kept only the refresh token rotation assertion (uses `secrets.token_urlsafe(48)` — cryptographically unique per call). Added comment explaining the design.
- **Files modified:** `test_session_lifecycle.py`
- **Commit:** `6decbbc9`

**7. [Rule 1 - Bug] test_byte_parity.py path computation for can.ts was off by one level**
- **Found during:** Task 3 execution
- **Issue:** Path traversal used `.parent.parent.parent.parent.parent` (5 levels) but the test file is 6 levels deep from repo root, leading to a doubled `apps/apps/admin-web/...` path.
- **Fix:** Changed to 6 `.parent` calls
- **Files modified:** `test_byte_parity.py`
- **Commit:** `76cdb264`

**8. [Rule 1 - Bug] `pytestmark = pytest.mark.asyncio` on sync tests in test_byte_parity.py**
- **Found during:** Task 3 execution
- **Issue:** Module-level `pytestmark = pytest.mark.asyncio` applied to sync test functions — pytest raised `PytestWarning` (treated as error) because sync functions are marked as asyncio.
- **Fix:** Removed `pytestmark` from `test_byte_parity.py`; tests run as standard sync functions.
- **Files modified:** `test_byte_parity.py`
- **Commit:** `76cdb264`

## Acceptance Criteria Status

| Criterion | Status |
|-----------|--------|
| `tests/integration/client_auth/test_otp_isolation.py` exists with required functions | PASS |
| staff token on `GET /client/me` → 401 | PASS |
| client token on `GET /clients` → 401 | PASS |
| anti-oracle test: ≥4 phone states, identical status + body | PASS |
| `test_idor.py` parametrizes both (A→B, B→A) orderings | PASS |
| IDOR: `/me` returns attacker's own id, never victim's | PASS |
| `test_session_lifecycle`: 3 cookies issued on verify | PASS |
| refresh cookie `Path=/api/v1/client` | PASS |
| refresh rotation: new refresh token different | PASS |
| logout clears all 3 cookies | PASS |
| post-logout `/me` returns 401 | PASS |
| rate-limit 429 on exceeding daily cap | PASS |
| brute-force block: `otp_max_attempts` 429 after N wrong codes | PASS |
| `test_byte_parity.py`: `"CLIENT" not in Role.__members__` | PASS |
| `test_byte_parity.py`: `ClientPrincipal` has no `role` annotation | PASS |
| `test_byte_parity.py`: `can.ts` carries no client-role reference | PASS |
| `git diff --quiet permissions.py can.ts` succeeds | PASS |
| `pytest --collect-only` succeeds (15 tests) | PASS |
| mypy strict passes on test files | PASS |
| ruff passes on test files | PASS |

## Known Stubs

None — all test assertions are wired to live implementation paths.

## Threat Flags

None — test files only; no new network endpoints, auth paths, or schema changes.

## Self-Check: PASSED

Files created:
- FOUND: apps/backend/tests/integration/client_auth/__init__.py
- FOUND: apps/backend/tests/integration/client_auth/conftest.py
- FOUND: apps/backend/tests/integration/client_auth/test_otp_isolation.py
- FOUND: apps/backend/tests/integration/client_auth/test_idor.py
- FOUND: apps/backend/tests/integration/client_auth/test_session_lifecycle.py
- FOUND: apps/backend/tests/integration/client_auth/test_byte_parity.py

Commits:
- FOUND: f3ee5724 — test(68-06): add client_auth test package + isolation + anti-oracle tests
- FOUND: 6decbbc9 — test(68-06): add IDOR sweep + full session lifecycle + rate-limit/brute-force tests
- FOUND: 76cdb264 — test(68-06): add CISO-01 byte-parity guard test
- FOUND: b1970e93 — fix(68-06): register Phase 68 client auth events in LOCKED_AUDIT_EVENTS
