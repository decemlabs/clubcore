# Phase 23: Hygiene + active sessions backend (parallel-eligible) - Context

**Gathered:** 2026-05-08
**Status:** Ready for planning

<domain>
## Phase Boundary

Phase 23 closes two v1.1 carryover error-mapping gaps and ships the backend endpoints the admin-web FE-09 SessionsList consumes:

**In scope:**

- **HYG-01** — `/auth/login` Argon2 verify-error path returns 401 `invalid_credentials` (not 500). The `verify_password` helper (`apps/backend/app/core/security.py:127-145`) already maps `VerifyMismatchError` and `InvalidHashError` to `InvalidPassword('invalid_credentials')`; the gap is operational telemetry: a NEW WARNING-level structlog emit `event=login_verify_error` with `{reason: 'verify_mismatch'|'invalid_hash'|'other', email_lower, ip}` (no raw hash, no password, no user_id). The existing `login_failed` audit row stays generic (`reason='invalid_credentials'` — preserves Phase 5 AUTH-EP-02 timing/info equivalence). Existing rate-limit (5/15min) is verified by an integration test that loops the tampered-hash path 6× and asserts the 6th returns 429.
- **HYG-02** — Invalid-UUID `sz_access` cookie returns 401 `invalid_session` (not 500). Wrap `UUID(claims.sub)` at `apps/backend/app/core/dependencies.py:221` in try/except and raise a NEW exception class `InvalidSession(AppError, code='invalid_session', status_code=401)` distinct from `InvalidAccessToken(code='invalid_token')`. `sz_refresh` is a base64url(32) opaque token (sha256-hashed for DB lookup, never UUID-parsed), so no second wrap site is required; the audit explicitly documents this in CONTEXT to forestall confusion at plan-phase.
- **HYG-03** — NEW endpoints (FE-09 consumer):
  - `GET /api/v1/auth/sessions` — returns the user's active session families as the standard pagination envelope `{items, total, page, pageSize}` (page=1, pageSize=20 default; max 100). Sort: `is_current=true` first, then `last_used_at DESC`. Each item: `{family_id, created_at, last_used_at, user_agent (nullable), channel, is_current}`. `is_current` is resolved by sha256-hashing the request's `sz_refresh` cookie (if present) and matching against `RefreshToken.token_hash` to derive the family_id; absent cookie ⇒ `is_current=false` for every item.
  - `POST /api/v1/auth/sessions/{family_id}/revoke` — CSRF-gated (signature-level `Depends(verify_csrf)` mirroring `/logout-all` at `apps/backend/app/modules/auth/router.py:142`). Idempotent: already-revoked family returns 204. Unknown family OR family belonging to another user returns 404 (collapsed code prevents enumeration). Self-revoke (revoking the family that issued THIS request's `sz_refresh`) is allowed and clears `sz_access` + `sz_refresh` + `sportzal_csrf` cookies on the response (matrix matches `/logout`). Emits `audit.session_revoked` with `resource_type='auth_session'`, `resource_id=family_id`. The existing `POST /api/v1/auth/logout-all` retains its current behavior unchanged.

**Out of scope (explicitly deferred):**

- IP capture per session — privacy/legal exposure (РФ GDPR analog) outweighs forensic gain at v1 single-zal scale. Revisits if SOC requirements arrive.
- `expires_at` / `last_seen_at_age` / `created_age_seconds` derived fields on the row — FE-09 computes display strings client-side from `created_at` + `last_used_at`.
- Family-level rate limit on `/sessions/{id}/revoke` — RBAC + auth dep already gate it; no enumeration vector remains after the 404-collapse decision.
- Schema-level migration to add `user_agent` and `channel` columns to `refresh_tokens` (CD-01 — see Claude's Discretion below).
- FE-09 itself — that's Phase 22's `22-05-PLAN`. Phase 23 ships only the backend slice + drift-gate refresh.
- Touching `/auth/login` happy path or `/auth/refresh` rotation flow.

</domain>

<decisions>
## Implementation Decisions

### Sessions list response shape (HYG-03)

- **D-23-1:** Response uses the LOCKED pagination envelope `{items, total, page, pageSize}` per PROJECT.md convention. Defaults: `page=1, pageSize=20`; max `pageSize=100`. No required query params; FE-09 calls without params and gets the implicit page 1. Mirrors v1.2 list endpoints (memberships/visits) — same query parser, same envelope assertion in OpenAPI contract tests.
- **D-23-2:** Sort order is `is_current=true` first, then `last_used_at DESC`. The "this is your current device" UX hint is server-resolved.
- **D-23-3:** `is_current` resolution: read `sz_refresh` from the request, sha256 it, look up `RefreshToken.token_hash` to derive `family_id`, mark that item `is_current=true`. If `sz_refresh` is absent (cookie path is `/api/v1/auth/*` so it should be present, but be defensive), every item carries `is_current=false`. Reuses the existing unique index on `RefreshToken.token_hash`. NO new family_id claim added to the access JWT (rejected — would touch the Phase 4 D-?? token shape).
- **D-23-4:** Each item carries exactly `{family_id, created_at, last_used_at, user_agent (str | null), channel, is_current}`. No `expires_at`, no `ip`, no derived ages. FE-09 computes display strings from the timestamps.

### Revoke endpoint semantics (HYG-03)

- **D-23-5:** Path: `POST /api/v1/auth/sessions/{family_id}/revoke`. Mounted inside the existing auth router (sibling of `/logout-all`). Both `sz_access` (Path=/) and `sz_refresh` (Path=/api/v1/auth) cookies reach the route.
- **D-23-6:** Unknown family_id (does not exist OR belongs to another user) returns **404 not_found**. Collapsed code prevents enumeration of other users' family_ids.
- **D-23-7:** Already-revoked family returns **204** (idempotent no-op). Mirrors `/logout` precedent at `apps/backend/app/modules/auth/router.py:130` ("idempotent: if absent or already revoked, the cookie still cleared").
- **D-23-8:** Self-revoke (revoking the family bound to this request's `sz_refresh`) is **allowed and clears the cookie matrix on the response** — equivalent to `/logout` for that family. FE-09 "revoke this device" works without a second flow.
- **D-23-9:** CSRF: signature-level `Depends(verify_csrf)` mirroring `/logout-all` at `apps/backend/app/modules/auth/router.py:142`. NOT relying on global mutating-method middleware alone.
- **D-23-10:** Audit event: `session_revoked` with `resource_type='auth_session'`, `resource_id=family_id`. **Likely a NEW entry in `LOCKED_AUDIT_EVENTS`** — plan-phase agent confirms the taxonomy delta and the TESTS-08 / TESTS-09 impact (the locked-event meta-test must accept the new pair). If audit taxonomy enforcement blocks, `session_revoked` falls back to reusing the existing `logout` event with a `target_family_id` payload field; default is to extend the frozenset.

### Error codes + logging (HYG-01 + HYG-02)

- **D-23-11 (HYG-02):** NEW exception class `InvalidSession(AppError, code='invalid_session', status_code=401)` lives in `apps/backend/app/core/exceptions.py` (sibling to `InvalidAccessToken`). The `code` value is the FE/contract-visible identifier; this is distinct from the existing `invalid_token` so FE-09 / future surface code can branch on it.
- **D-23-12 (HYG-02):** Single wrap site at `apps/backend/app/core/dependencies.py:221` — `try: user = await _user_loader(session, UUID(claims.sub)) except ValueError: raise InvalidSession('invalid_session')`. `sz_refresh` is NOT UUID-parsed anywhere (sha256(token) → `RefreshToken.token_hash` lookup at `apps/backend/app/modules/auth/service.py:300, 438`); no second wrap is needed. Plan-phase agent re-greps `UUID(` callsites in `app/core/` and `app/modules/auth/` to confirm no other untrusted-input parses leak 500s.
- **D-23-13 (HYG-01):** TWO emits per failed verify path — keep the existing `login_failed` audit DB write generic (`reason='invalid_credentials'`) to preserve Phase 5 AUTH-EP-02 timing/info equivalence (an attacker must not be able to distinguish wrong-password from non-existent-email from corrupted-hash); ADD a NEW structlog WARNING emit `event=login_verify_error` with `{reason: 'verify_mismatch'|'invalid_hash'|'other', email_lower, ip}`. This separates security forensics (audit log) from ops monitoring (structlog), with the security-sensitive distinguisher visible only in operator-side logs, not the audit row that ships to compliance reviewers.
- **D-23-14 (HYG-01):** WARNING-level structlog NEVER carries: raw plain password, encoded hash bytes, user_id (sentinel-hash path doesn't know it on lookup miss), telegram_chat_id, full request headers. Email is lower-cased per existing rate-limit normalization (`apps/backend/app/modules/auth/service.py:109`). IP is `request.client.host` if available else `null` (mirroring the existing `rbac_forbidden` audit emit pattern at `apps/backend/app/core/dependencies.py:275`).

### Test coverage (LOCKED — user-selected at discuss-phase)

- **D-23-15 (HYG-01 mandatory):** Integration test seeds a User with a corrupted password_hash (e.g. literal `'NOT_A_VALID_ARGON2_HASH'`); `POST /auth/login` returns 401 `invalid_credentials` (not 500); audit row written; structlog WARNING captured.
- **D-23-16 (HYG-01 mandatory):** Integration test loops the tampered-hash login path 5× under the rate-limit window (5/15min) and asserts the 6th returns 429 `too_many_requests` — proves the rate-limit chokepoint is reached BEFORE the verify call (Phase 5 AUTH-EP-02 invariant).
- **CD-02 (default to apply, HYG-02 + HYG-03 tests):** Plan-phase ships parallel coverage:
  - HYG-02: integration test signs an access JWT with the live secret_key but `sub='not-a-uuid'`; hits a protected route; asserts 401 `invalid_session`. Falsifies the previous 500 path.
  - HYG-03: integration tests for envelope shape, sort order (incl. `is_current` resolution), pagination defaults + cap, revoke 204 idempotency, revoke unknown-family 404, revoke cross-user 404, self-revoke cookie-clear matrix, audit emit assertion.
  These are CD because the user explicitly LOCKED only the HYG-01 tests; success criteria 2 + 3 in ROADMAP nonetheless require evidence, so default is to ship them. User overrides at plan-phase review with "drop HYG-02/HYG-03 tests".

### Claude's Discretion (finalised at `/gsd-plan-phase`)

- **CD-01 (default to apply): Session metadata storage — hybrid (Redis-only + lazy DB hydration).** The `RefreshToken` table currently has no `user_agent` and no `channel` columns; the Redis session value already carries `last_seen_at` (`apps/backend/app/modules/auth/service.py:218-219`). Plan-phase agent extends the Redis session JSON to `{family_id, last_seen_at, refresh_token_hash, user_agent, channel}` written at `_track_session()` and `rotate_session()`; the `/sessions` GET reads from Redis (fast, no JOIN), falls back to `RefreshToken.created_at` for `created_at`. NO Alembic migration on `refresh_tokens` columns in this phase. Trade-off accepted: pre-Phase-23 sessions in Redis lack `user_agent`/`channel` until next rotation — they render as `null` / `'email_password'` (default fallback) for the first refresh window. Acceptable because real session count is 1–3 and rotation TTL is short.
- **CD-03 (default to apply): Plan layout — single PLAN.md.** Phase 23 is small enough (3 requirements, 1 router file, 1 dependencies file, 1 exceptions file, 1 service file, ~6 tests, 1 schema.d.ts regen) that the plan ships as `23-01-PLAN.md` rather than splitting. Plan-phase agent reverses to multi-plan only if the OpenAPI / drift-gate refresh introduces parallel-able work.
- **CD-04 (default to apply): Atomic-commit-per-task** — same precedent as v1.1 / Phase 21 / Phase 22 CD-02. The executor agent does this by default.
- **CD-05 (default to apply): OpenAPI schema.d.ts regeneration** — the new endpoints + the new `InvalidSession` error class force a single regeneration commit (Phase 21 D-21-* invariants). `packages/api-client/src/schema.contract.test.ts` (already conditional per Phase 21 D-21-2) flips the sessions-paths assertion from "expected absent" to "expected present" with the locked path strings.

### Locked-not-discussed (carried verbatim from PROJECT / REQUIREMENTS / Phase 4–21 decisions)

- **AppError hierarchy** — new `InvalidSession` extends `AppError`, uses the existing exception_handler wiring for `code` + `status_code` + `WWW-Authenticate` (or whichever 401 metadata is conventional in `apps/backend/app/core/exceptions.py`).
- **Pagination envelope `{items, total, page, pageSize}`** — Phase 4 D-?? + project convention. Sessions list honors verbatim.
- **camelCase wire format** — schema.d.ts emits `familyId`, `createdAt`, `lastUsedAt`, `userAgent`, `channel`, `isCurrent`, `pageSize`. FE consumes verbatim.
- **CSRF SIGNATURE-level dep** — `Depends(verify_csrf)` precedent at `/logout`, `/logout-all` (`apps/backend/app/modules/auth/router.py:115, 142`).
- **Audit emit literal `resource_type=`** — Phase 15 INFRA-11 / D-11: AST literal-only enforcement. `resource_type='auth_session'` MUST be a literal at the callsite.
- **Cookie matrix (D-17)** — `sz_access` Path=/, `sz_refresh` Path=/api/v1/auth, `sportzal_csrf` Path=/. Self-revoke clears all three (D-23-8).
- **structlog field naming** — existing `event_kv` shape; locked field set per Phase 4 / Phase 5 / Phase 6 precedents.
- **Rate-limit on /login** — 5/15min per-email-lower (`apps/backend/app/modules/auth/rate_limit.py`). Phase 23 does NOT modify; verifies it still chokepoints before the verify call.
- **Phase 21 drift gate** — single regen commit covers `apps/backend/openapi.json` + `packages/api-client/src/schema.d.ts` + the contract test uplift. CI is the gate.
- **No `apps/admin-web` changes in Phase 23** — FE-09 consumer lives in Phase 22 22-05-PLAN.
- **No alembic migrations** in Phase 23 (CD-01 keeps schema unchanged; the `refresh_tokens` columns stay as-is).
- **Branded UUIDv4 IDs** — `family_id` is `UUID` on the wire (lowercase hyphenated string). FE-09 brands it as `FamilyId`.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Project context (read first)
- `.planning/PROJECT.md` — pinned РФ/СНГ stack + camelCase wire format Key Decision (Phase 4) + Pagination envelope Key Decision (Phase 4) + v1.1 hygiene минимум note line 27.
- `.planning/REQUIREMENTS.md` §"Hygiene — v1.1 Carryover (Phase 23, parallel-eligible)" — HYG-01, HYG-02, HYG-03 verbatim. The requirements-status table at file end (rows `HYG-01..HYG-03 | Phase 23 | Pending`) flips to Complete on phase verification.
- `.planning/REQUIREMENTS.md` §"Frontend Wiring — admin-web (Phase 22)" FE-09 — names Phase 23 as the producer of `GET /api/v1/auth/sessions` + per-family revoke.
- `.planning/ROADMAP.md` §"Phase 23: Hygiene + active sessions backend (parallel-eligible)" — Goal + Success Criteria 1-3.
- `.planning/STATE.md` §"Decisions" — accumulated v1.2 decisions; Phase 23 D-23-* will be appended on phase verification.

### Phase 22 outputs (consumer of Phase 23 surface)
- `.planning/phases/22-admin-web-wiring-memberships-visits-active-sessions-ui/22-CONTEXT.md` §"Active-sessions UI (FE-09) sequencing vs Phase 23" + §"Plan layout" CD-01 plan #5 — confirms FE-09 is `22-05-PLAN.md`, blocked on Phase 23 main merge.
- `apps/admin-web/src/features/auth/` — host directory FE-09 will extend (or sibling `features/auth-sessions/`).
- `apps/admin-web/src/routes/_protected/settings.tsx` — likely FE-09 mount point.

### Backend codebase — auth module
- `apps/backend/app/modules/auth/router.py` — host file for the NEW `/sessions` GET + `/sessions/{family_id}/revoke` POST. Mirrors `/logout-all` at lines 141-152 for CSRF + auth-dep matrix.
- `apps/backend/app/modules/auth/service.py` lines 173-225 — `_track_session` + Redis session-value JSON shape. CD-01 (hybrid metadata) extends the JSON with `user_agent` + `channel`.
- `apps/backend/app/modules/auth/service.py` lines 274-410 — `rotate_session` (refresh path). The rotated session value also carries `user_agent` + `channel` under CD-01.
- `apps/backend/app/modules/auth/service.py` lines 422-485 — `revoke_session` precedent (revokes by presented_token; the new endpoint revokes by `family_id` directly — plan-phase agent factors out a shared `_revoke_family(user_id, family_id)` helper).
- `apps/backend/app/modules/auth/models.py` lines 63-103 — `RefreshToken` ORM model. `created_at` (TimestampMixin), `family_id`, `token_hash`, `expires_at`, `revoked_at`. NO `user_agent`, NO `channel` columns (CD-01 keeps it that way).
- `apps/backend/app/modules/auth/schemas.py` — Pydantic response models. NEW: `ActiveSessionItem`, `ActiveSessionsListResponse` (envelope-typed), `RevokeSessionResponse`.
- `apps/backend/app/modules/auth/rate_limit.py` — `check_login_rate` / `bump_login_rate` (5/15min). HYG-01 D-23-16 test asserts this still chokepoints before verify.

### Backend codebase — core
- `apps/backend/app/core/security.py` lines 113-145 — `verify_password` already maps `VerifyMismatchError` and `InvalidHashError` to `InvalidPassword('invalid_credentials')`. HYG-01 closure adds the structlog WARNING emit at the caller (`auth/service.py:115-143`).
- `apps/backend/app/core/security.py` lines 72-110 — `decode_access_token`. NO change in Phase 23 (sub stays as `str` in `AccessTokenClaims`; the UUID parse is wrapped at the caller per D-23-12).
- `apps/backend/app/core/security.py` lines 200-290 — cookie issue/clear matrix (D-17). Self-revoke (D-23-8) reuses `clear_session_cookies()`.
- `apps/backend/app/core/dependencies.py` lines 194-224 — `get_current_user`. HYG-02 wraps line 221 (`UUID(claims.sub)`) in try/except → raises `InvalidSession('invalid_session')`.
- `apps/backend/app/core/exceptions.py` lines 53-69 — `InvalidAccessToken` + `InvalidPassword` precedents. NEW: `InvalidSession(AppError, code='invalid_session', status_code=401)` sibling.
- `apps/backend/app/core/permissions.py` — `Action` / `Resource` enums + `can()`. Sessions endpoints are role-agnostic (every authenticated user manages own sessions); they use `get_current_user` only, NOT `require_permission`.
- `apps/backend/app/core/audit.py` (or equivalent — Phase 15 INFRA-11) — `audit.emit` + `LOCKED_AUDIT_EVENTS` frozenset. NEW entry `('session_revoked', 'auth_session')` per D-23-10 (taxonomy delta).

### Backend codebase — API surface
- `apps/backend/app/api/v1/router.py` — auth router inclusion (already mounts `/auth`). NO changes; new routes land inside the auth router.
- `apps/backend/openapi.json` — current spec. Phase 23 forces a single regen commit (CD-05).
- `packages/api-client/src/schema.d.ts` — current typed transport (verified at Phase 22: `paths['/api/v1/auth/sessions']` and `paths['/api/v1/auth/sessions/{family_id}/revoke']` are MISSING). Phase 23 regen adds them.
- `packages/api-client/src/schema.contract.test.ts` — Phase 21 D-21-2 conditional sessions assertion flips from "expected absent" to "expected present" with the locked path strings.
- `packages/api-client/src/fetcher.ts` — generic transport. NO changes.

### Backend codebase — tests
- `apps/backend/tests/integration/` — host dir for HYG-01/HYG-02/HYG-03 integration tests. Existing precedents:
  - `apps/backend/tests/integration/rbac/test_owner_only.py` — protected-route + auth-dep test pattern.
  - `apps/backend/tests/integration/test_visits_meta.py` — recent (Phase 22) integration-test layout precedent.
- `apps/backend/tests/unit/test_security.py` — `verify_password` unit tests; Phase 23 may extend with corrupted-hash branch coverage.
- `apps/backend/tests/_fixtures/owner_routes.py` — fixture pattern for tampered-cookie / tampered-JWT construction.
- `apps/backend/tests/conftest.py` (top-level) — `httpx ASGITransport` + `pytest-asyncio` setup per CLAUDE.md backend test convention.

### Conventions
- `.planning/codebase/STRUCTURE.md` — backend tree + "Where to Add New Code".
- `.planning/codebase/CONVENTIONS.md` — backend formatting/linting/naming/imports/state-data conventions.
- `.planning/codebase/TESTING.md` — pytest layout (integration vs unit; ASGITransport).
- `apps/backend/CLAUDE.md` (if present) — module conventions.

### Third-party docs (read on demand)
- [argon2-cffi exceptions reference](https://argon2-cffi.readthedocs.io/en/stable/api.html#exceptions) — `VerifyMismatchError`, `InvalidHashError` semantics for HYG-01 logging detail.
- [PyJWT decode + leeway](https://pyjwt.readthedocs.io/en/stable/api.html#jwt.decode) — confirms HYG-02 wrap site is downstream of decode (decode_access_token is unchanged).
- [FastAPI dependency injection — security parameters](https://fastapi.tiangolo.com/tutorial/dependencies/) — for the `Depends(verify_csrf)` signature-level pattern.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets

- **`apps/backend/app/core/security.py:127-145`** (`verify_password`) — already maps Argon2 verify errors to `InvalidPassword('invalid_credentials')`. HYG-01 closure adds caller-side structlog WARNING; the helper itself is untouched.
- **`apps/backend/app/core/security.py:200-290`** (cookie matrix issue/clear) — D-17 precedent for `clear_session_cookies()` reused by D-23-8 self-revoke.
- **`apps/backend/app/modules/auth/router.py:62-152`** — `/login`, `/logout`, `/logout-all` route shapes. New `/sessions` GET + `/sessions/{family_id}/revoke` POST mirror the auth-dep + CSRF + audit-emit ordering.
- **`apps/backend/app/modules/auth/service.py:173-225`** (`_track_session`) — Redis session-value writer. CD-01 extends the JSON with `user_agent` + `channel`.
- **`apps/backend/app/modules/auth/service.py:422-485`** (`revoke_session`) — by-presented-token revoke precedent. The new endpoint factors out a `_revoke_family(user_id, family_id)` helper used by both flows.
- **`apps/backend/app/core/dependencies.py:194-224`** (`get_current_user`) — HYG-02 wrap site (line 221).
- **`apps/backend/app/core/exceptions.py:53-69`** — `InvalidAccessToken` + `InvalidPassword` precedents for the NEW `InvalidSession`.
- **`apps/backend/app/core/permissions.py`** — sessions endpoints are role-agnostic (no `require_permission` call).
- **`apps/backend/app/modules/auth/rate_limit.py`** — `check_login_rate` / `bump_login_rate` reused by the HYG-01 D-23-16 test.
- **`apps/backend/tests/_fixtures/owner_routes.py`** — fixture precedent for tampered-cookie / tampered-JWT construction.
- **`packages/api-client/src/schema.contract.test.ts`** — conditional sessions-paths assertion already in place per Phase 21 D-21-2; Phase 23 flips the condition.

### Established Patterns

- **AppError + handler** — `code`, `status_code`, optional `fields` payload. Every 401 surfaces with the right shape automatically; no manual `JSONResponse` plumbing.
- **Audit emit literal `resource_type=`** — Phase 15 INFRA-11 / D-11 AST literal-only enforcement. `'auth_session'` is a literal at the callsite.
- **Pagination envelope** — `{items, total, page, pageSize}` for every list endpoint.
- **CSRF SIGNATURE-level dep** — `Depends(verify_csrf)` at the route signature, not via middleware.
- **Cookie matrix** — `sz_access` Path=/, `sz_refresh` Path=/api/v1/auth, `sportzal_csrf` Path=/.
- **Atomic-commit-per-task** — v1.1 / Phase 21 / Phase 22 precedent.
- **Drift gate** — single regen commit covers backend openapi.json + packages/api-client schema.d.ts + the contract test.
- **timing/info equivalence on /login** — Phase 5 AUTH-EP-02 invariant. Audit row stays generic; only structlog (operator side) carries the verify-error reason.

### Integration Points

- **`apps/backend/app/modules/auth/router.py`** — Phase 23 ADDS two route handlers + their schemas import.
- **`apps/backend/app/modules/auth/schemas.py`** — Phase 23 ADDS `ActiveSessionItem`, `ActiveSessionsListResponse`, `RevokeSessionResponse`.
- **`apps/backend/app/modules/auth/service.py`** — Phase 23 ADDS `list_user_sessions(user_id, page, page_size, presented_refresh_token | None) -> envelope` + `_revoke_family(user_id, family_id) -> bool` + extends `_track_session` / `rotate_session` with `user_agent` + `channel` Redis writes (CD-01).
- **`apps/backend/app/core/dependencies.py:221`** — Phase 23 wraps `UUID(claims.sub)` in try/except.
- **`apps/backend/app/core/exceptions.py`** — Phase 23 ADDS `InvalidSession`.
- **`apps/backend/app/core/audit.py`** (or wherever `LOCKED_AUDIT_EVENTS` lives) — Phase 23 ADDS `('session_revoked', 'auth_session')` entry.
- **`apps/backend/openapi.json` + `packages/api-client/src/schema.d.ts`** — Phase 23 regenerates (single drift-gate refresh commit).
- **`packages/api-client/src/schema.contract.test.ts`** — Phase 23 flips the conditional sessions-paths assertion (Phase 21 D-21-2).
- **`apps/backend/tests/integration/`** — Phase 23 ADDS `test_auth_login_argon2_hygiene.py`, `test_auth_invalid_session.py`, `test_auth_sessions_endpoints.py` (or equivalent split per plan-phase).
- **NO changes to** `apps/admin-web/**`, `app/main.py` Lifespan, `apps/backend/alembic/`, `docker-compose.yml`, `.importlinter`, `apps/backend/app/integrations/telegram/**`, `apps/backend/app/modules/visits/**`, `apps/backend/app/modules/memberships/**`, `apps/backend/app/modules/clients/**`, fetcher.ts, the swap-seam, OWNER_ONLY matrix, RBAC enums.

</code_context>

<specifics>
## Specific Ideas

- **Two-channel separation for HYG-01** is the architectural headline: audit row stays opaque (timing/info equivalence — Phase 5 AUTH-EP-02 invariant), structlog carries the verify-error reason for ops triage. Anyone reading the audit log alone cannot distinguish wrong-password from corrupted-hash from non-existent-email — that's the security promise. Anyone reading structlog can spot a corrupted-hash spike (= data integrity issue, possibly a botched migration) immediately.
- **InvalidSession is a NEW class, not a message override on InvalidAccessToken** — distinct typed code lets FE-09 / future surface code branch on `code === 'invalid_session'` (cookie tampered, force re-login UX) vs `code === 'invalid_token'` (token expired, auto-refresh UX). The two paths have different recovery flows.
- **404-collapse on revoke is deliberate, not a corner cut** — the standard advice for "is this resource yours" lookups in auth/admin APIs. Distinguishing 404 from 403 is an enumeration vector. The audit row still captures the attempted family_id for forensic review.
- **`is_current` resolution via sz_refresh sha256 is the cheapest correct answer** — reuses the existing unique index on `RefreshToken.token_hash`, no JWT shape change, no Redis read. The single-edge case (sz_refresh absent because the request came from `/api/v1/auth/sessions` and the cookie path is `/api/v1/auth`) needs verification at plan-phase: the path scope matches, so the cookie WILL be sent; the defensive `is_current=false` fallback only triggers in adversarial / curl-debugging scenarios.
- **CD-01 hybrid metadata storage** keeps Phase 23 small (no Alembic migration). Trade-off accepted: pre-Phase-23 sessions render `user_agent=null` + `channel='email_password'` until the next refresh writes the new fields. Real-world session count is 1-3, rotation TTL is short, so the degraded window is hours. v1.3+ revisits if richer audit (e.g. parsed user-agent device family) becomes needed.
- **Phase 23 is parallel-eligible with Phase 22's first four sub-plans** (22-01 through 22-04). 22-05-PLAN (FE-09) is the only consumer; sequencing is governed by Phase 22 D-22-2 ("FE-09 ships LAST inside Phase 22, after Phase 23 main-merge").
- **Test fixture for HYG-02**: a hand-signed access JWT with the live `secret_key.get_secret_value()`, payload `{sub: 'not-a-uuid', role: 'reception', typ: 'access', iat, exp}`, sets the `sz_access` cookie, hits any `Depends(get_current_user)` route. Pre-Phase-23 this returns 500; post-Phase-23 it returns 401 `invalid_session`.
- **Test fixture for HYG-01**: insert a User row with `password_hash='NOT_A_VALID_ARGON2_HASH'` directly via the SQLAlchemy session (bypassing `hash_password`). Then `POST /auth/login` with that user's email and any password. Argon2id parser raises `InvalidHashError` → `verify_password` raises `InvalidPassword` → `/login` handler returns 401 `invalid_credentials` + emits the new structlog WARNING.

</specifics>

<deferred>
## Deferred Ideas

- **Schema migration to add `user_agent` and `channel` columns to `refresh_tokens`** — CD-01 picks Redis-only hybrid. Migration revisits if (a) Redis eviction policy changes and we need durable session metadata, or (b) audit-log forensic requirements grow.
- **IP capture per session** — privacy/legal exposure (РФ GDPR analog). Revisits if compliance / SOC2 work surfaces.
- **`expires_at` on the session row** — FE-09 doesn't need it for v1; computes "expires in N days" from `created_at` + the known refresh TTL constant. Add if user feedback shows confusion.
- **family_id claim in the access JWT** — rejected at discuss-phase (touches Phase 4 D-?? token shape). Revisits if `is_current` resolution proves expensive at scale (>1000 active families per user — not happening at v1.x).
- **Family-level rate limit on `/sessions/{id}/revoke`** — auth dep + 404-collapse + CSRF already gate enumeration. Revisits if abuse vector emerges.
- **Push notification on revoke** — out of v1.2 entirely. The revoking user already knows; the revoked device just sees a 401 on next refresh.
- **Distinct audit event for self-revoke vs cross-family-revoke** — single `session_revoked` with payload field `is_self` would preserve forensic detail. Revisits at audit-log read UI work in v1.3+.
- **Bulk revoke (revoke all but current)** — different from `/logout-all` (which revokes including current). Could ship as `POST /sessions/revoke-others`. Revisits if FE-09 user testing surfaces "log out everywhere except this device" as a common ask.
- **Per-channel sessions filter on GET /sessions** — `?channel=telegram` query param. v1 user lacks the volume to need it.
- **HYG-02/HYG-03 integration tests as MANDATORY (not CD)** — user locked only HYG-01 tests; CD-02 default-applies HYG-02/HYG-03 tests. User overrides at plan-phase review if they want to drop them.
- **Re-greping for other untrusted-input UUID parses** — D-23-12 lists this as a plan-phase audit step. If others surface, they're scoped to a follow-up phase, not Phase 23.

</deferred>

---

*Phase: 23-hygiene-active-sessions-backend-parallel-eligible*
*Context gathered: 2026-05-08*
