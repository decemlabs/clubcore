# Phase 23: Hygiene + active sessions backend (parallel-eligible) - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-08
**Phase:** 23-hygiene-active-sessions-backend-parallel-eligible
**Areas discussed:** Sessions list response shape, Revoke endpoint semantics, Error codes + logging (HYG-01 + HYG-02)

**Areas presented but not selected:** Session metadata source (handled as CD-01)

---

## Sessions list response shape

### Q1 — Envelope shape

| Option | Description | Selected |
|--------|-------------|----------|
| Pagination envelope | `{items,total,page,pageSize}`. Honors PROJECT.md convention; FE-09 ignores total/page. | ✓ |
| Bare items array (typed) | `{items: [...]}` or just `[...]`. Auth /me precedent. | |
| Capped envelope, no page param | `{items, total}` only — server caps at 20. | |

**User's choice:** Pagination envelope.

### Q2 — Sort order

| Option | Description | Selected |
|--------|-------------|----------|
| `last_used_at DESC` | Most recently active first. | |
| `created_at DESC` | Newest sign-in first. | |
| Current session first, then `last_used_at DESC` | Pin request's own family at top with is_current marker. | ✓ |

**User's choice:** Current session first, then last_used_at DESC.

### Q3 — is_current marker resolution

| Option | Description | Selected |
|--------|-------------|----------|
| Match presented sz_refresh hash to row.family_id | sha256(sz_refresh) → token_hash lookup → derive family_id. | ✓ |
| Match access token claim | Add family_id claim to JWT; touches Phase 4 token shape. | |
| Skip is_current; sort only by last_used_at DESC | Drop the concept entirely. | |

**User's choice:** Match presented sz_refresh hash to row.family_id.

### Q4 — Default cap and pagination params

| Option | Description | Selected |
|--------|-------------|----------|
| page=1, pageSize=20 default; max 100; no required params | Mirrors v1.2 list endpoints. | ✓ |
| Hard-cap server-side, no page/pageSize knobs | Smallest API surface; strips params from OpenAPI for this route. | |
| page=1, pageSize=10 default; max 50 | Tighter cap; small precedent fork. | |

**User's choice:** page=1, pageSize=20 default; max 100.

### Q5 — Active-session row content

| Option | Description | Selected |
|--------|-------------|----------|
| expires_at (ISO) | Refresh token expiry. | |
| ip (last seen) | Adds privacy/legal exposure. | |
| is_current (bool) | Already locked by Q3 — listed for completeness. | |
| No extras — stick to HYG-03 fields + is_current | Smallest surface. | ✓ |

**User's choice:** No extras — stick to HYG-03 fields + is_current.

---

## Revoke endpoint semantics

### Q6 — Unknown family_id OR cross-user

| Option | Description | Selected |
|--------|-------------|----------|
| 404 not_found for both unknown and cross-user | Prevents enumeration. | ✓ |
| 204 idempotent for both | Smallest FE error surface but masks bugs. | |
| 404 unknown / 403 cross-user | Distinct codes; leaks existence. | |

**User's choice:** 404 not_found for both unknown and cross-user.

### Q7 — Already-revoked family

| Option | Description | Selected |
|--------|-------------|----------|
| 204 idempotent (no-op) | Mirrors /logout precedent. | ✓ |
| 409 conflict already_revoked | Distinct signal; needs FE handling. | |

**User's choice:** 204 idempotent.

### Q8 — Self-revoke handling

| Option | Description | Selected |
|--------|-------------|----------|
| Allowed; equivalent to /logout for that family | Server clears cookies on response. | ✓ |
| Allowed; no cookie clearing | Next refresh attempt 401s and FE handles logout. | |
| Forbid — must use /logout for self-family | Symmetric API; FE-09 must branch on is_current. | |

**User's choice:** Allowed; equivalent to /logout for that family.

### Q9 — Path mounting

| Option | Description | Selected |
|--------|-------------|----------|
| GET /api/v1/auth/sessions + POST /api/v1/auth/sessions/{family_id}/revoke | Inside auth router beside /logout-all. | ✓ |
| List under /api/v1/sessions, revoke under /api/v1/auth/sessions/... | Splits surface — no good reason. | |

**User's choice:** GET /api/v1/auth/sessions + POST /api/v1/auth/sessions/{family_id}/revoke.

### Q10 — CSRF coupling

| Option | Description | Selected |
|--------|-------------|----------|
| Signature-level Depends(verify_csrf) mirroring /logout-all | Explicit at route. | ✓ |
| Rely on global CSRF middleware only | Less verbose; risks fall-out if config changes. | |

**User's choice:** Signature-level Depends(verify_csrf).

### Q11 — Audit event name

| Option | Description | Selected |
|--------|-------------|----------|
| `session_revoked` (resource_type=auth_session) | Distinct entry; needs LOCKED_AUDIT_EVENTS delta. | ✓ |
| Reuse `logout` (resource_type=session) | Shifts semantics — less precise. | |
| Reuse `logout_all` | Misleading. | |

**User's choice:** session_revoked (resource_type=auth_session).

---

## Error codes + logging (HYG-01 + HYG-02)

### Q12 — HYG-02 invalid_session error code shape

| Option | Description | Selected |
|--------|-------------|----------|
| Reuse InvalidAccessToken with new message 'invalid_session' | Smallest blast; FE sees same code='invalid_token'. | |
| New InvalidSession exception class (401, code='invalid_session') | Distinct typed code; FE-09 can branch on it. | ✓ |
| Reuse ValidationAppError (422) | Wrong status. | |

**User's choice:** New InvalidSession exception class.

### Q13 — Where to wrap the UUID parse

| Option | Description | Selected |
|--------|-------------|----------|
| dependencies.py:221 — try/except around UUID(claims.sub) | Single site; sz_access flow only. | ✓ |
| Also harden sz_refresh parsing site(s) | sz_refresh is base64url, not UUID-parsed; zero new coverage. | |
| Push UUID typing into AccessTokenClaims (pydantic) | Couples to Phase 4 token schema. | |

**User's choice:** dependencies.py:221 — try/except around UUID(claims.sub).

### Q14 — HYG-01 Argon2 verify-error logging shape

| Option | Description | Selected |
|--------|-------------|----------|
| event=login_verify_error + reason + email_lower + ip | Distinct structlog WARNING from existing audit emit. | |
| Extend existing login_failed audit emit with reason field | Conflates audit DB write and structlog channels. | |
| Two emits: existing login_failed audit + NEW structlog login_verify_error WARNING | Belt and suspenders; clear channel separation. | ✓ |

**User's choice:** Two emits — existing login_failed audit + NEW structlog login_verify_error WARNING.

### Q15 — HYG-01 audit row distinguisher

| Option | Description | Selected |
|--------|-------------|----------|
| No — audit emit stays generic 'invalid_credentials'; structlog WARNING carries detail | Preserves Phase 5 AUTH-EP-02 timing/info equivalence. | ✓ |
| Yes — add 'verify_error_kind' to audit row | More forensic detail but leaks user existence. | |

**User's choice:** No — audit emit stays generic; structlog WARNING carries the detail.

### Q16 — Test coverage targets (multi-select)

| Option | Description | Selected |
|--------|-------------|----------|
| HYG-01: tampered-Argon2 hash in DB → /auth/login → 401 invalid_credentials | Falsifies the 500 path. | ✓ |
| HYG-01: rate-limit still enforced after verify-error | 6th attempt → 429, not 500. | ✓ |
| HYG-02: tampered sz_access (valid sig, non-UUID sub) → 401 invalid_session | Falsifies the 500 path. | (CD-02) |
| HYG-03: sessions list shape + revoke matrix | Envelope, sort, pagination, idempotency, self-revoke cookie clear. | (CD-02) |

**User's choice:** Locked HYG-01 tests as MUST. HYG-02 + HYG-03 tests captured as Claude's Discretion (CD-02) — default to apply since success criteria 2 and 3 require evidence.

---

## Claude's Discretion

- **CD-01 — Session metadata storage (hybrid Redis-only).** User skipped this gray area at the top-level selection. Default: extend the Redis session JSON with `user_agent` + `channel` (no Alembic migration on `refresh_tokens`). Pre-Phase-23 sessions degrade to `user_agent=null` + `channel='email_password'` until next rotation.
- **CD-02 — HYG-02 + HYG-03 integration tests** ship by default. User explicitly locked only HYG-01 tests; success criteria 2 and 3 require evidence so default-apply.
- **CD-03 — Single 23-01-PLAN.md** rather than splitting; phase scope is small.
- **CD-04 — Atomic-commit-per-task** per v1.1 / Phase 21 / Phase 22 precedent.
- **CD-05 — Single drift-gate refresh commit** for `apps/backend/openapi.json` + `packages/api-client/src/schema.d.ts` + `schema.contract.test.ts` uplift.

## Deferred Ideas

- Schema migration to add `user_agent` + `channel` columns to `refresh_tokens`.
- IP capture per session (РФ GDPR analog).
- `expires_at` on the session row.
- `family_id` claim in the access JWT.
- Family-level rate limit on `/sessions/{id}/revoke`.
- Push notification on revoke.
- Distinct audit events for self-revoke vs cross-family-revoke.
- Bulk revoke (`/sessions/revoke-others`).
- Per-channel sessions filter (`?channel=telegram`).
- Re-greping for other untrusted-input UUID parses across `app/core/` + `app/modules/`.
