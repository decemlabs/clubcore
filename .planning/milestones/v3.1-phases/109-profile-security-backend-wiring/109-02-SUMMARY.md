---
phase: 109-profile-security-backend-wiring
plan: "02"
subsystem: backend-auth
tags: [routes, profile-update, password-change, csrf, integration-tests, prof-01, prof-02]
dependency_graph:
  requires:
    - "109-01: ProfileUpdateRequest + ChangePasswordRequest schemas"
    - "109-01: update_profile() + change_password() service functions"
    - "109-01: profile_updated LOCKED audit event"
  provides:
    - "PATCH /api/v1/auth/me (PROF-01) — authenticated + CSRF-gated profile update"
    - "POST /api/v1/auth/change-password (PROF-02) — authenticated + CSRF-gated password change"
    - "Integration test file test_profile_update.py (7 scenarios)"
    - "Integration test file test_change_password.py (7 scenarios)"
  affects:
    - apps/backend/app/modules/auth/router.py
    - apps/backend/tests/integration/auth/test_profile_update.py
    - apps/backend/tests/integration/auth/test_change_password.py
tech_stack:
  added: []
  patterns:
    - "PATCH route with optional-fields body + all-None guard (422 ValidationAppError)"
    - "204 No Content route (response_model=None, status_code=204)"
    - "cc_refresh → sha256 → RefreshToken.family_id resolution reused from revoke_session_family"
    - "Two independent AsyncClients sharing SAVEPOINT session for revoke-others-keeps-current test"
key_files:
  created:
    - apps/backend/tests/integration/auth/test_profile_update.py
    - apps/backend/tests/integration/auth/test_change_password.py
  modified:
    - apps/backend/app/modules/auth/router.py
decisions:
  - "D-109-02-204-SHAPE: change-password returns 204 No Content (response_model=None, status_code=HTTP_204_NO_CONTENT) — no ResponseEnvelope wrapper; FE 204 contract requires empty body"
  - "D-109-02-ALL-NONE-422: PATCH /me with both full_name and email None raises ValidationAppError(422) inline in the route — a no-op PATCH is a client bug; guard added before service call"
  - "D-109-02-NIL-UUID-FALLBACK: if cc_refresh cookie is absent or unresolvable, effective_family_id falls back to UUID(int=0) — revoke-all fallback; very unlikely while access token was valid"
  - "D-109-02-REDUNDANT-CAST: update_profile() returns User (not CurrentUser), so the cast(User, ...) from GET /me pattern is not needed — update_profile return typed directly"
metrics:
  duration: "~18 minutes"
  completed: "2026-06-14T19:15:00Z"
  tasks_completed: 3
  tasks_total: 3
  files_modified: 3
---

# Phase 109 Plan 02: Profile & Security — Route Wiring + Integration Tests Summary

**One-liner:** Wired `PATCH /api/v1/auth/me` (PROF-01) and `POST /api/v1/auth/change-password` (PROF-02) into auth router with `require_authenticated()` + `verify_csrf` RBAC-04 ordering, plus 14 passing ASGITransport integration tests proving the full contract.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Wire PATCH /auth/me and POST /auth/change-password routes | 979d081b | app/modules/auth/router.py |
| 2 | Integration tests for PATCH /auth/me (PROF-01) | 9214758c | tests/integration/auth/test_profile_update.py |
| 3 | Integration tests for POST /auth/change-password (PROF-02) | 3713e33a | tests/integration/auth/test_change_password.py |

## What Was Built

### Task 1 — auth/router.py

**`PATCH /api/v1/auth/me`**
- Auth dep `require_authenticated()` declared FIRST, then `verify_csrf` (RBAC-04 401-before-403 preserved, T-109-08 / T-109-07)
- Body: `ProfileUpdateRequest` (both fields optional, extra=forbid on base)
- All-None body guard: raises `ValidationAppError(422)` inline — a no-op PATCH is a client bug
- Calls `update_profile(session, user_id=user.id, full_name=..., email=...)` from Plan 01
- Returns `ResponseEnvelope[MeResponse]` echo (same shape as GET /me, no redundant cast needed since update_profile returns `User`)
- Duplicate email propagates as `ConflictError` 409 with `fields.email` (D-109-01-CONFLICT)

**`POST /api/v1/auth/change-password`**
- Same auth+CSRF dep ordering (RBAC-04)
- Body: `ChangePasswordRequest` (min_length=12 on new_password)
- Resolves `current_family_id` from `cc_refresh` cookie via sha256 → token_hash → `RefreshToken.family_id` lookup (reused from `revoke_session_family` lines 217-223)
- Fallback: `UUID(int=0)` if cookie absent/unresolvable (revoke-all; extremely rare)
- Calls `change_password(session, redis, user_id=..., ..., current_family_id=...)` from Plan 01
- Returns `204 No Content` (`response_model=None`, `status_code=HTTP_204_NO_CONTENT`) — no response body

Duplicate-email error status: **409** with `code="conflict"` and `fields={"email": "Этот адрес уже используется"}` (ConflictError base class — D-109-01-CONFLICT from Plan 01).

### Task 2 — test_profile_update.py (7 tests)

1. **Happy path** — PATCH fullName + email → 200 MeResponse echo; GET /me confirms DB persistence
2. **Partial update** — PATCH fullName only → 200; email unchanged
3. **Email-taken → 409** — ConflictError with fields.email (NOT 500); owner's email unchanged after
4. **Extra field rejected** — PATCH `{"theme":"dark"}` → 422 (extra=forbid from BackendSchemaBase)
5. **CSRF required** — PATCH without X-CSRF-Token → 403 csrf_mismatch
6. **Auth required** — no cookies → 401 invalid_token (RBAC-04: 401 before 403)
7. **Audit row** — `profile_updated` AuditLog row written, changed_fields present, no raw name/password in payload

### Task 3 — test_change_password.py (7 tests)

1. **Revoke-others-keeps-current** — two independent AsyncClients sharing SAVEPOINT session; Client A changes password; Client B's `RefreshToken.revoked_at` IS NOT NULL; Client A's row revoked_at IS NULL; Client A GET /me still 200 (T-109-10 proven)
2. **Wrong current password** — 401 invalid_credentials; no families revoked; original password still logs in
3. **New password too short** — `{"newPassword":"short"}` → 422 (12-char floor)
4. **CSRF required** — POST without X-CSRF-Token → 403 csrf_mismatch
5. **Auth required** — no cookies → 401 invalid_token (RBAC-04)
6. **Audit row** — `password_changed_revokes_sessions` AuditLog row, `family_count=1`, no password/hash in payload
7. **Hash actually changed** — new password → 200 login; old password → 401

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Redundant cast removed**
- **Found during:** Task 1 (mypy --strict)
- **Issue:** `cast(User, updated_user)` was a redundant-cast error — `update_profile()` already returns `User` directly (unlike the GET /me route which casts from `CurrentUser`)
- **Fix:** Used `updated_user` fields directly without cast
- **Files modified:** apps/backend/app/modules/auth/router.py
- **Commit:** 979d081b

**2. [Rule 1 - Bug] Spurious await on hash_password.__module__ in test**
- **Found during:** Task 3 first test run
- **Issue:** `assert seeded_owner.password_hash == await hash_password.__module__` was nonsensical — `__module__` is a string, not a coroutine
- **Fix:** Replaced with a direct login check using the original password to confirm hash unchanged
- **Files modified:** tests/integration/auth/test_change_password.py
- **Commit:** 3713e33a

## Threat Surface Scan

New network endpoints introduced:

| Flag | File | Description |
|------|------|-------------|
| threat_flag: new_endpoint | apps/backend/app/modules/auth/router.py | PATCH /api/v1/auth/me — authenticated staff profile update |
| threat_flag: new_endpoint | apps/backend/app/modules/auth/router.py | POST /api/v1/auth/change-password — self-service password change |

Both endpoints are in the plan's threat model (T-109-07..T-109-13 all mitigated). No unplanned surface introduced.

## Self-Check: PASSED

Files exist:
- apps/backend/app/modules/auth/router.py — FOUND (modified)
- apps/backend/tests/integration/auth/test_profile_update.py — FOUND (created)
- apps/backend/tests/integration/auth/test_change_password.py — FOUND (created)

Commits:
- 979d081b — FOUND (feat: wire PATCH /auth/me + POST /auth/change-password routes)
- 9214758c — FOUND (test: integration tests for PATCH /auth/me)
- 3713e33a — FOUND (test: integration tests for POST /auth/change-password)

Verification smoke:
- PATCH /me and POST /change-password routes registered: PASSED
- mypy --strict router.py: PASSED
- ruff check all 3 files: PASSED
- lint-imports contracts: 3 kept, 0 broken: PASSED
- 14 new tests green: PASSED
- route-introspection + RBAC parity (7 tests): PASSED
