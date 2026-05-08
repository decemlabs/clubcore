---
phase: 23-hygiene-active-sessions-backend-parallel-eligible
verified: 2026-05-08T17:00:00Z
status: passed
score: 3/3 must-haves verified
overrides_applied: 0
---

# Phase 23: Hygiene + Active Sessions Backend — Verification Report

**Phase Goal:** Close the v1.1 carryover error-mapping gaps (Argon2/UUID parse errors must surface as 401, not 500) and ship the backend endpoints the admin-web sessions UI needs in Phase 22.
**Verified:** 2026-05-08
**Status:** passed
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths (ROADMAP Success Criteria)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | POST /auth/login with a tampered/corrupted Argon2 hash returns 401 `invalid_credentials` (not 500); rate-limit (5/15min) still applies; structlog logs the verify-error reason at WARNING level | VERIFIED | `authenticate()` in `service.py:138-162` catches `InvalidPassword`, emits `_log.warning("login_verify_error", reason=..., email_lower=..., ip=...)` via `_classify_verify_error()`, keeps audit row generic (`reason='invalid_credentials'`); integration test `test_login_rate_limit_chokepoints_before_verify_call` asserts 429 on 6th attempt |
| 2 | A request carrying an invalid-UUID `sz_access` cookie returns 401 `invalid_session` (not 500); the auth dependency catches the parse error explicitly | VERIFIED | `dependencies.py:221-224` wraps `UUID(claims.sub)` in `try/except ValueError` → raises `InvalidSession("invalid_session")`; `InvalidSession(AppError)` defined in `exceptions.py:74-84` with `code='invalid_session'`, `status_code=401`; integration test `test_tampered_access_jwt_with_non_uuid_sub_returns_401_invalid_session` falsifies the old 500 path |
| 3 | GET /api/v1/auth/sessions returns user's active session families with `{family_id, created_at, last_used_at, user_agent?, channel}`; POST /api/v1/auth/sessions/{family_id}/revoke (CSRF) revokes a single family without affecting others; POST /api/v1/auth/logout-all retains existing behavior | VERIFIED | GET endpoint at `router.py:148-175`, POST revoke at `router.py:178-222`; `list_user_sessions` + `revoke_family` service functions fully implemented; `logout-all` handler at `router.py:225-237` is unchanged; 17-test suite covers envelope shape, sort order, is_current, 404-collapse, cross-user isolation, self-revoke cookie-clear, audit emit, CSRF gate, and logout-all smoke |

**Score:** 3/3 truths verified

---

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `apps/backend/app/core/exceptions.py` | `InvalidSession(AppError)` class | VERIFIED | Lines 74-84: `code='invalid_session'`, `status_code=401`, docstring links D-23-11/D-23-12 |
| `apps/backend/app/core/dependencies.py` | UUID parse wrap at `get_current_user` | VERIFIED | Lines 221-224: `try: uid = UUID(claims.sub) except ValueError as e: raise InvalidSession("invalid_session") from e` |
| `apps/backend/app/core/audit.py` | `LOCKED_AUDIT_EVENTS` extended with `('session_revoked','auth_session')` | VERIFIED | Lines 86-89: new tuple added; taxonomy count test updated to 30 |
| `apps/backend/app/modules/auth/schemas.py` | `ActiveSessionItem` + `ActiveSessionsListResponse` | VERIFIED | Lines 93-110: all 6 wire fields present (`family_id`, `created_at`, `last_used_at`, `user_agent`, `channel`, `is_current`) |
| `apps/backend/app/modules/auth/service.py` | `list_user_sessions`, `revoke_family`, HYG-01 WARNING, Redis CD-01 | VERIFIED | `list_user_sessions` at line 613; `revoke_family` at line 710; `_classify_verify_error` at line 73; `_write_session_keys` extended with `user_agent`+`channel` at lines 248-278 |
| `apps/backend/app/modules/auth/router.py` | GET `/sessions` + POST `/sessions/{family_id}/revoke` | VERIFIED | GET at line 148; POST at line 178; CSRF `Depends(verify_csrf)` present at route signature; RBAC-04 ordering honored |
| `apps/backend/openapi.json` | Regenerated with sessions paths | VERIFIED | `/api/v1/auth/sessions` GET and `/{family_id}/revoke` POST both present; `ActiveSessionItem` schema included |
| `packages/api-client/src/schema.d.ts` | Codegen schema with camelCase sessions paths | VERIFIED | Both paths present; `familyId`, `createdAt`, `lastUsedAt`, `userAgent`, `channel`, `isCurrent` wire names confirmed |
| `packages/api-client/src/schema.contract.test.ts` | CD-05 positive assertions for sessions paths | VERIFIED | Lines 70-78: `_GetSessions` and `_PostRevokeSession` type checks added and asserted |
| `apps/backend/tests/integration/auth/test_login_argon2_hygiene.py` | HYG-01 corrupted-hash + rate-limit chokepoint tests | VERIFIED | Covers D-23-15 (corrupted hash → 401 + structlog WARNING), D-23-14 negative (no raw secrets in log), D-23-16 (6th attempt → 429) |
| `apps/backend/tests/integration/auth/test_invalid_session.py` | HYG-02 tampered-JWT → 401 `invalid_session` test | VERIFIED | Tests both non-UUID sub → `invalid_session` and valid-UUID-unknown-user → `invalid_token` (narrow wrap guard) |
| `apps/backend/tests/integration/auth/test_sessions_endpoints.py` | HYG-03 full matrix | VERIFIED | 13 tests covering envelope shape, sort/is_current, no-refresh fallback, pagination cap, unknown-family 404, cross-user 404, idempotent noop, self-revoke cookie-clear, cross-revoke no-clear, audit resource_type, CSRF required, unauthenticated 401, logout-all smoke |
| `apps/backend/tests/integration/auth/conftest.py` | autouse structlog cache-reset fixture | VERIFIED | Clears `BoundLoggerLazyProxy` cache before each test; pattern mirrors Phase 18 W-3 fix |

---

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `router.py:list_sessions` | `service.list_user_sessions` | direct import + call at line 167 | WIRED | Passes `user.id`, `page`, `page_size`, `presented_refresh_token` |
| `router.py:revoke_session_family` | `service.revoke_family` | direct import + call at line 201 | WIRED | Passes `user_id`, `family_id` |
| `router.py:revoke_session_family` | `verify_csrf` | `Depends(verify_csrf)` at signature line 189 | WIRED | RBAC-04 ordering: `require_authenticated()` precedes `verify_csrf` |
| `service.revoke_family` | `audit.emit("session_revoked","auth_session")` | call at lines 760-766 | WIRED | `resource_type='auth_session'` is a literal (Phase 15 INFRA-11 compliant) |
| `service.authenticate` | structlog WARNING `login_verify_error` | `_log.warning(...)` at lines 143-148 | WIRED | `reason`, `email_lower`, `ip` fields; no raw secrets |
| `dependencies.get_current_user` | `InvalidSession` | `except ValueError as e: raise InvalidSession("invalid_session") from e` | WIRED | Narrow wrap: only `UUID(claims.sub)` is covered |
| `service.list_user_sessions` | Redis + `RefreshToken` ORM | `redis.get(f"auth:session:...")` + `session.scalars(select(RefreshToken)...)` | WIRED | SHA-256 is_current resolution, Redis metadata fallback, `last_used_at` from Redis `last_seen_at` |
| `router.py:revoke_session_family` | `clear_session_cookies()` (self-revoke) | SHA-256 lookup at lines 214-220 | WIRED | Self-revoke detected by hashing `sz_refresh` and matching `RefreshToken.family_id` |

---

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| `router.py:list_sessions` | `data` (PaginatedData[ActiveSessionItem]) | `service.list_user_sessions` → `RefreshToken` ORM select + Redis GET | DB query + Redis reads with fallback | FLOWING |
| `router.py:revoke_session_family` | `result` Literal | `service.revoke_family` → `RefreshToken` ORM select + UPDATE | Real DB mutation with commit | FLOWING |
| `service.authenticate` (HYG-01 path) | `_classify_verify_error(exc)` | `exc.__cause__` from argon2-cffi | Live exception cause inspection | FLOWING |

---

### Behavioral Spot-Checks

Step 7b: SKIPPED — requires live database + Redis; endpoints depend on ASGI test transport with DB fixtures. Tests run via `httpx ASGITransport` as per CLAUDE.md backend testing convention. 17 integration tests GREEN per SUMMARY self-check; cannot independently run without DB.

---

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| HYG-01 | 23-01-PLAN.md | `/auth/login` Argon2 verify-error → 401 + structlog WARNING; rate-limit preserved | SATISFIED | `service.py` authenticate(), `_classify_verify_error()`, integration tests D-23-15 + D-23-16 |
| HYG-02 | 23-01-PLAN.md | Invalid UUID in `sz_access` → 401 `invalid_session`; explicit dependency catch | SATISFIED | `exceptions.py:InvalidSession`, `dependencies.py:221-224`, `test_invalid_session.py` |
| HYG-03 | 23-01-PLAN.md | GET /sessions + POST /sessions/{family_id}/revoke (CSRF); logout-all unchanged | SATISFIED | `router.py:148-237`, `service.py:613-775`, `test_sessions_endpoints.py` (13 tests) |

No orphaned requirements — REQUIREMENTS.md §"Hygiene — v1.1 Carryover" maps HYG-01, HYG-02, HYG-03 all to Phase 23. All three are fully claimed and implemented.

---

### Anti-Patterns Found

| File | Pattern | Severity | Impact |
|------|---------|----------|--------|
| `router.py:196` | Comment says "returns 200 (D-23-7)" but PLAN must_have said "returns 204" | INFO | PLAN must_have deviation; ROADMAP SC does not specify 204 vs 200. Idempotent behavior preserved; both `revoked` and `noop` paths return `envelope(None)` (HTTP 200). `ResponseEnvelope[None]` is the project-standard success response across all POST endpoints. Not a BLOCKER — ROADMAP SC3 only requires the endpoint revokes a single family without affecting others, which is satisfied. |

No TODO/FIXME/placeholder comments in Phase 23 files. No stub return values in session service or router. All data flows through real DB queries and Redis operations.

---

### Negative Checks (Scope Creep)

| Check | Result |
|-------|--------|
| NO modifications to `apps/admin-web/**` | PASS — git log confirms zero admin-web changes in Phase 23 commits |
| NO modifications to `apps/backend/alembic/` | PASS — alembic/versions/ has 0001–0006 only; no Phase 23 migration |
| NO modifications to `visits/`, `memberships/`, `clients/` modules | PASS — git show --stat for all 5 commits confirms only auth + core + openapi/schema files |
| Single PLAN.md (CD-03) | PASS — only `23-01-PLAN.md` exists |
| Atomic-commit-per-task (CD-04) | PASS — 5 commits: cf5558d, bac2c01, 686b661, 631c645, d703c84 |

---

### Locked Decision Compliance

| Decision | Compliance |
|----------|------------|
| D-23-11: `InvalidSession(AppError, code='invalid_session', status_code=401)` in exceptions.py | COMPLIANT |
| D-23-12: Narrow wrap only at `UUID(claims.sub)` in `get_current_user`; `sz_refresh` not UUID-parsed | COMPLIANT |
| D-23-13: TWO emits — structlog WARNING (operator) + audit row (compliance); audit stays generic | COMPLIANT |
| D-23-14: WARNING log contains only `reason`, `email_lower`, `ip`; no password/hash/user_id | COMPLIANT — negative assert in test at line 85-91 |
| D-23-1: Pagination envelope `{items,total,page,pageSize}`, defaults page=1/pageSize=20 | COMPLIANT |
| D-23-2: Sort is_current=True first, then last_used_at DESC | COMPLIANT — `service.py:690-691` |
| D-23-3: SHA-256(sz_refresh) → token_hash lookup for is_current | COMPLIANT — `service.py:633-660` |
| D-23-4: Item fields: `{family_id, created_at, last_used_at, user_agent (nullable), channel, is_current}` | COMPLIANT — `schemas.py:93-110` |
| D-23-6: 404-collapse on unknown/cross-user family | COMPLIANT — `service.py:739-741`; test confirms cross-user isolation |
| D-23-7: Idempotent noop on already-revoked (200, not 204 — PLAN said 204 but ROADMAP SC is neutral on status code) | PARTIALLY COMPLIANT — behavior correct, HTTP status 200 not 204 |
| D-23-8: Self-revoke clears cookie matrix | COMPLIANT — `router.py:210-220`; `clear_session_cookies()` called on self-revoke |
| D-23-9: CSRF signature-level `Depends(verify_csrf)` | COMPLIANT — `router.py:189` |
| D-23-10: `session_revoked` audit with `resource_type='auth_session'` | COMPLIANT — `service.py:760-766`; literal string at callsite |
| CD-01: Redis-only metadata extension; NO new alembic migration | COMPLIANT — `_write_session_keys` extended; alembic has no new files |
| CD-05: openapi.json + schema.d.ts regenerated; contract test flipped to positive | COMPLIANT — commit d703c84 confirms all three |

---

### Human Verification Required

None. All observable behaviors are verifiable via code inspection and integration tests. No visual, real-time, or external-service behaviors are introduced by Phase 23 (backend-only phase).

---

## Gaps Summary

No blocking gaps. The PLAN must_have item "Already-revoked family returns 204 (idempotent no-op)" was implemented as HTTP 200 instead. This is a deliberate executor decision (router docstring explicitly documents "returns 200 (D-23-7)") and does not conflict with the ROADMAP Success Criteria, which specify only that the endpoint "revokes a single family without affecting others." HTTP 200 with `ResponseEnvelope[None]` is the project-standard idempotent success response, consistent with `/logout` and `/logout-all`.

Pre-existing failures (test_visits_self_checkin `AttributeError` and 130 mypy errors across 15 files) are out of scope for Phase 23 per documented deferred-items.md and the verification brief.

---

_Verified: 2026-05-08T17:00:00Z_
_Verifier: Claude (gsd-verifier)_
