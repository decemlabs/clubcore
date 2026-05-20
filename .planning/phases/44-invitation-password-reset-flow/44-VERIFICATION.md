---
phase: 44-invitation-password-reset-flow
verified: 2026-05-20T00:00:00Z
status: passed
score: 5/5 success criteria verified
overrides_applied: 1
overrides:
  - must_have: "ROADMAP SC #2: bumps users.password_changed_at"
    reason: "D-44-02 explicitly supersedes this clause. The roadmap's 'password_changed_at' wording was inherited from an earlier itsdangerous-stateless design proposal. D-41-04 chose DB-table token storage with single-SQL atomic-consume on password_reset_tokens.consumed_at instead. No users.password_changed_at column exists in the schema; the forensic timestamp lives on the password_reset_completed audit row.created_at. CONTEXT § Schema decisions documents the override; legacy roadmap phrasing accepted."
    accepted_by: "Phase 44 D-44-02 (planner/owner sign-off in CONTEXT.md)"
    accepted_at: "2026-05-20T00:00:00Z"
requirements_covered:
  - id: RESET-01
    status: satisfied
  - id: RESET-02
    status: satisfied
  - id: RESET-03
    status: satisfied
  - id: RESET-04
    status: satisfied
  - id: RESET-05
    status: satisfied
---

# Phase 44: Invitation + Password-Reset Flow — Verification Report

**Phase Goal:** A pending-invitation user can accept their invitation by setting an initial password via email link; any user can reset their password via email link with full anti-oracle protection; existing operators can revoke outstanding invitations.

**Verified:** 2026-05-20
**Status:** passed
**Re-verification:** No — initial verification

---

## 1. Goal Achievement — Per-Success-Criterion Checklist

The phase goal decomposes into ROADMAP's 5 explicit success criteria. Each is verified against the codebase, not against SUMMARY.md narrative.

### SC #1 — Anti-oracle `/password-reset/request` (RESET-01)

**Roadmap promise:** Identical 202 + identical body + bounded-equal timing (within 100ms tolerance) for all 4 cases (existing-active / existing-deactivated / owner-account / non-existent); `password_reset_requested` audit row emitted in BOTH branches (known and unknown email); `test_password_reset_no_oracle.py` from Phase 41 now passes.

| Claim | Evidence | Status |
|------|---------|--------|
| Identical 202 + envelope across 4 cases | `password_reset_service.py:181-330` — single `await session.commit()` + `_floor_response_time(started)` exit on every branch; router returns `envelope(None)` regardless | VERIFIED |
| Bounded timing floor | `password_reset_service.py:74-126` — `_RESPONSE_FLOOR_SECONDS = 0.5`; `_floor_response_time()` awaited on every return path (success / rate-limit / Branch A/B/C) | VERIFIED |
| Audit emit in BOTH known + unknown branches | `password_reset_service.py:268-278` (Branch A), `:302-312` (Branch B deactivated/soft-deleted), `:317-327` (Branch C unknown) — three `audit.emit("password_reset_requested", ...)` calls | VERIFIED |
| 5/15min IP + 1/min + 5/hour email rate limits | `reset_rate_limit.py:36-41` — three thresholds `_IP_LIMIT=5/_IP_WINDOW=900`, `_EMAIL_MIN_LIMIT=1/_MIN_WINDOW=60`, `_EMAIL_HOUR_LIMIT=5/_HOUR_WINDOW=3600` | VERIFIED |
| `test_password_reset_no_oracle.py` ungated (no xfail) + PASSES | `tests/integration/auth/test_password_reset_no_oracle.py:53` — `pytestmark = pytest.mark.asyncio` (no `xfail`); line-3 docstring narrates the Phase 44 ungate history. `uv run pytest` returns 1 passed | VERIFIED |
| Audit-row dual-branch assertion (D-44-30) | Same test, `:197-237` — asserts 4 rows (1 per case), `actor_user_id IS NULL`, `audit_correlation_id` non-None per request | VERIFIED |

**SC #1 status:** ✓ VERIFIED

### SC #2 — Atomic-consume `/password-reset/confirm` (RESET-02)

**Roadmap promise:** Atomically consumes the token via single-SQL `RETURNING`, updates `users.password_hash`, bumps `users.password_changed_at`, revokes ALL refresh-token families, emits `password_reset_completed` in same UoW, returns 200; replay → 410 generic body.

| Claim | Evidence | Status |
|------|---------|--------|
| Single-SQL `UPDATE … RETURNING` atomic-consume | `password_reset_service.py:128-178` `_atomic_consume_token()` — single `update(PasswordResetToken).values(consumed_at=func.now()).returning(...)` with `WHERE consumed_at IS NULL AND expires_at > NOW()` | VERIFIED |
| `users.password_hash` updated (Argon2id) | `password_reset_service.py:383-388` — `await hash_password(new_password)` + `update(User).values(password_hash=new_hash)`. `hash_password` is the Argon2id helper at `app/core/security.py` | VERIFIED |
| Bumps `users.password_changed_at` | NOT IMPLEMENTED — column does not exist in `app/core/models.py`. Per **D-44-02** the roadmap text is superseded by D-41-04: DB-table atomic-consume on `password_reset_tokens.consumed_at` replaces the column-bump approach. Forensic timestamp lives on the `password_reset_completed` audit row's `created_at`. | OVERRIDE (D-44-02 — accepted) |
| Revoke ALL refresh-token families | `password_reset_service.py:392-398` — calls the `get_user_session_invalidator()` Protocol slot. Slot is registered at `app/main.py:270` via `register_user_session_invalidator(invalidate_all_families_for_user)` (Phase 43 D-43-26 wiring). | VERIFIED |
| `password_reset_completed` audit in same UoW | `password_reset_service.py:402-413` — `audit.emit("password_reset_completed", ...)`; payload shape locked by `PasswordResetCompletedPayload` (`audit_payloads.py:630`) | VERIFIED |
| Single service.commit() (SVC001) | `password_reset_service.py:416` — `await session.commit()`. SVC001 walker scope includes this file per D-41-28 | VERIFIED |
| Returns 200 on success | `router.py:461-481` — `status_code=200`, returns `envelope(None)` | VERIFIED |
| Replay/expired/invalid → 410 generic | `password_reset_service.py:376-377` raises `InvalidOrExpiredTokenError` (status 410, code `invalid_or_expired_token`); same exception covers all 3 cases per D-44-15 | VERIFIED |

**SC #2 status:** ✓ VERIFIED (with D-44-02 override on `password_changed_at`)

### SC #3 — Invitation Accept (RESET-04)

**Roadmap promise:** `POST /users/invitations/accept {token, password, fullName}` receives token from invitation email and gets login cookie pair; soft-deleted-email re-use INSERTS a new row (never UPDATEs the soft-deleted row); emits `user_invitation_accepted` with new `user_id`.

| Claim | Evidence | Status |
|------|---------|--------|
| Endpoint exists at `POST /api/v1/users/invitations/accept` | `app/modules/users/router.py:216-287` `accept_invitation_endpoint`. Mounted at `app/api/v1/router.py:35` via `users_router` (prefix `/users`) | VERIFIED |
| Token + password + full_name body schema | `app/modules/users/schemas.py:87-100` `InvitationAcceptRequest` with `token` (max=128), `password` (max=256), `full_name` (max=128, optional) | VERIFIED |
| Login cookie pair issued on success | `app/modules/users/router.py:266-277` — `issue_tokens(session, redis, user)` + `issue_session_cookies(response, access_token=, refresh_token=, csrf_token=, secure=)` mirroring `/auth/login` verbatim | VERIFIED |
| INSERT-only on soft-deleted-email (PITFALLS Pitfall 4) | Per **D-44-20** the INSERT-only invariant is satisfied at Phase 43 `create_user` (the row exists in `status='pending_invitation'` when accept runs). Accept performs UPDATE-only. Verified: `grep -c "session.add(User(" password_reset_service.py` = **0**. | VERIFIED |
| `user_invitation_accepted` audit emit | `password_reset_service.py:518-528` — `audit.emit("user_invitation_accepted", ...)` with `accepted_user_id`, `invitation_token_id`, `audit_correlation_id`. Payload schema `UserInvitationAcceptedPayload` registered at `audit_payloads.py:537/739` | VERIFIED |

**SC #3 status:** ✓ VERIFIED

### SC #4 — Token TTL + URL Fragment + Rate Limits (RESET-03)

**Roadmap promise:** Invitation TTL = 7d; password-reset TTL = 1h (OWASP 2025 floor); tokens in URL fragment or POST body — never URL path; rate-limit 5/15min IP + 1/min + 5/hour email with the same generic 202 on rate-limit hit.

| Claim | Evidence | Status |
|------|---------|--------|
| Password-reset TTL = 1 hour | `app/modules/auth/constants.py:19` — `PASSWORD_RESET_TOKEN_TTL: Final[timedelta] = timedelta(hours=1)`. Consumed at issue time `password_reset_service.py:262` (`expires_at = datetime.now(UTC) + PASSWORD_RESET_TOKEN_TTL`) and at SELECT predicate (`expires_at > func.now()` in `_atomic_consume_token`) | VERIFIED |
| Invitation TTL = 7 days | Inherited from Phase 43 — `app/modules/users/constants.py:INVITATION_TOKEN_TTL` (not modified in Phase 44; Phase 44 accept-flow consumes pre-existing rows) | VERIFIED |
| Token in URL fragment (NEVER path) | `password_reset_service.py:282-283` — `reset_url = f"{base}/auth/password-reset#token={raw_token}"` (fragment `#token=...`). `confirm` consumes via POST body (`PasswordResetConfirmBody.token`) per `router.py:467-481`. No `/{token}` path parameter exists. | VERIFIED |
| Rate-limit-hit returns same generic 202 (D-44-11) | `password_reset_service.py:215-227` — `except RateLimited` triggers structlog WARN + floor + early `return`; router still returns 202 + envelope(None). NO 429. | VERIFIED |
| Locked Russian templates | `app/modules/auth/email_templates.py:91-111` — `PASSWORD_RESET_EMAIL` EmailTemplate registered (subject + html + text). `USER_INVITATION_EMAIL` template inherited from Phase 43 in `app/modules/users/email_templates.py`. | VERIFIED |
| AST gate covers `PASSWORD_RESET_EMAIL` callsite | `tests/unit/test_locked_email_templates_ast.py:299-318` — asserts literal `"PASSWORD_RESET_EMAIL"` exists exactly once as `ast.Constant(str)` at a dispatcher callsite. Grep evidence: `template_id="PASSWORD_RESET_EMAIL"` at `password_reset_service.py:292` (1 callsite). | VERIFIED |

**SC #4 status:** ✓ VERIFIED

### SC #5 — Revoke + Already-Accepted Race (RESET-05)

**Roadmap promise:** Owner can `POST /users/invitations/{id}/revoke` and observe `user_invitation_revoked` + token immediately invalid; revoking an already-accepted invitation returns 409 `invitation_already_accepted`.

| Claim | Evidence | Status |
|------|---------|--------|
| Revoke endpoint exists | `app/modules/users/router.py:180-196` — `POST /invitations/{token_id}/revoke` with `require_permission(UPDATE, USERS)` + `verify_csrf`. Already shipped at Phase 43 D-43-19. | VERIFIED |
| `user_invitation_revoked` audit emit | `app/modules/users/service.py:422` — `audit.emit("user_invitation_revoked", ...)` (Phase 43 implementation) | VERIFIED |
| Token immediately invalid after revoke | Atomic-consume in `_atomic_consume_token` checks `consumed_at IS NULL AND expires_at > NOW()`; revoke sets `consumed_at=NOW()` so subsequent accept returns `None` → 410 invalid_or_expired_token | VERIFIED |
| Already-accepted invitation → 409 `invitation_already_accepted` | `app/modules/users/service.py:407,418` raises `InvitationAlreadyAcceptedError` (status 409, code `invitation_already_accepted`). Cross-coverage tests: `tests/integration/auth/test_invitation_accept.py:706 test_revoke_already_accepted_invitation_returns_409` + `:645 test_accept_with_revoked_token_returns_410` | VERIFIED |

**SC #5 status:** ✓ VERIFIED

---

## 2. Critical Invariant Grep Evidence

Every invariant declared in the verification context — run on the live codebase:

| Invariant | Expected | Actual | Status |
|----------|----------|--------|--------|
| `payload=` count in `password_reset_service.py` (CR-01 flat-kwargs discipline) | 0 | **0** | ✓ |
| `template_id="PASSWORD_RESET_EMAIL"` literal at dispatcher callsite (D-41-11) | 1 | **1** (`password_reset_service.py:292`) | ✓ |
| `await session.commit()` count in `password_reset_service.py` (SVC001 walker scope per D-41-28) | 6 | **6** | ✓ |
| `session.add(User(` count in `password_reset_service.py` (D-44-20 — accept is UPDATE-only, never INSERT) | 0 | **0** | ✓ |
| `xfail-strict` marker on `test_password_reset_no_oracle.py` (D-44-29 / D-41-17 atomic ungate) | absent at marker level | **absent** (`pytestmark = pytest.mark.asyncio` only; line-3 narration in docstring only) | ✓ |

---

## 3. Required Artifacts

| Artifact | Status | Notes |
|----------|--------|-------|
| `app/modules/auth/constants.py` (PASSWORD_RESET_TOKEN_TTL = 1h) | ✓ VERIFIED | Final[timedelta] = timedelta(hours=1) |
| `app/modules/auth/reset_rate_limit.py` (3-key fixed-window) | ✓ VERIFIED | 6 functions: 3 × `check_…` + 3 × `bump_…` |
| `app/modules/auth/email_templates.py` (PASSWORD_RESET_EMAIL) | ✓ VERIFIED | Locked Russian subject + html + text |
| `app/modules/auth/exceptions.py` (3 new exceptions) | ✓ VERIFIED | `InvalidOrExpiredTokenError(410)`, `WeakPasswordError(422)`, `InvitationAlreadyAcceptedError(409)` |
| `app/modules/auth/password_reset_service.py` (3 service fns + helper) | ✓ VERIFIED | `_atomic_consume_token` + `request_password_reset` + `confirm_password_reset` + `accept_invitation`; 538 lines |
| `app/modules/auth/router.py` (2 endpoints) | ✓ VERIFIED | `/password-reset/request` (202) + `/password-reset/confirm` (200) |
| `app/modules/users/router.py` (accept endpoint) | ✓ VERIFIED | `/invitations/accept` returns ResponseEnvelope[LoginResponse] |
| `app/modules/auth/schemas.py` (2 request bodies) | ✓ VERIFIED | `PasswordResetRequestBody` + `PasswordResetConfirmBody` |
| `app/modules/users/schemas.py` (accept body) | ✓ VERIFIED | `InvitationAcceptRequest` |
| `app/workers/scheduled/cleanup_password_reset_tokens.py` | ✓ VERIFIED | 30-day retention DELETE |
| `app/workers/__init__.py` (cron registration) | ✓ VERIFIED | `cleanup_password_reset_tokens` registered in `functions` + `cron(hour=0, minute=30)` |

## 4. Key Link / Wiring Verification

| From | To | Via | Status |
|------|-----|-----|--------|
| `/auth/password-reset/request` router | `password_reset_service.request_password_reset` | `await password_reset_service.request_password_reset(session, redis, email=..., client_ip=...)` (router.py:455) | ✓ WIRED |
| `/auth/password-reset/confirm` router | `password_reset_service.confirm_password_reset` | `await password_reset_service.confirm_password_reset(...)` (router.py:478) | ✓ WIRED |
| `/users/invitations/accept` router | `password_reset_service.accept_invitation` | router.py:253 — cross-module delegate | ✓ WIRED |
| `confirm_password_reset` | `invalidate_all_families_for_user` | via `get_user_session_invalidator()` Protocol slot | ✓ WIRED (registered at `app/main.py:270`) |
| `request_password_reset` | `EmailDispatcher` | `await get_email_dispatcher()(template_id="PASSWORD_RESET_EMAIL", ...)` (password_reset_service.py:291) | ✓ WIRED |
| `request_password_reset` | Redis rate-limiter | `reset_rate_limit.check_*` + `bump_*` (password_reset_service.py:215-233) | ✓ WIRED |
| `_atomic_consume_token` | `password_reset_tokens` table | single-SQL `UPDATE … RETURNING` on `PasswordResetToken` ORM (password_reset_service.py:157-172) | ✓ WIRED |
| `cleanup_password_reset_tokens` cron | `password_reset_tokens` table | `DELETE … WHERE expires_at < NOW() - INTERVAL '30 days'` (cleanup_password_reset_tokens.py:67-69) | ✓ WIRED |
| `auth_router` mount | `/api/v1/auth/*` | `app/api/v1/router.py:39` | ✓ WIRED |
| `users_router` mount | `/api/v1/users/*` | inherited Phase 43 mount | ✓ WIRED |

## 5. Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Phase 44 test suite passes | `uv run pytest tests/integration/auth/test_password_reset_no_oracle.py tests/integration/auth/test_password_reset_{confirm,rate_limit}.py tests/integration/auth/test_invitation_accept{,_insert_only}.py tests/unit/auth/test_password_reset_email_render.py tests/integration/workers/test_cleanup_password_reset_tokens.py tests/unit/test_locked_email_templates_ast.py -q` | **29 passed in 12.54s** | ✓ PASS |
| Broader auth + users + workers surface | `uv run pytest tests/integration/auth/ tests/integration/users/ tests/integration/workers/test_cleanup_password_reset_tokens.py tests/unit/auth/ tests/unit/test_locked_email_templates_ast.py -q` | **115 passed in 27.74s** | ✓ PASS |
| Ruff (Phase 44 files) | `uv run ruff check app/modules/auth/ app/workers/scheduled/cleanup_password_reset_tokens.py app/workers/__init__.py app/modules/users/router.py app/modules/users/schemas.py` | **All checks passed!** | ✓ PASS |
| Import-linter contracts | `uv run lint-imports` | **3 kept, 0 broken** (`core ⊄ modules`, `modules ⊄ modules`, `integrations ⊄ modules`) | ✓ PASS |

> **mypy note:** `app/modules/auth/{router,service,telegram_service}.py` still emits 3 pre-existing errors (`Module "app.modules.auth.models" does not explicitly export attribute "User"`). Confirmed pre-existing — Phase 41 hoist+shim (`commit 1b63d83`). NOT a Phase 44 regression. No Phase 44 file introduces new mypy errors.

## 6. Requirements Coverage (RESET-01..05)

| Req | Description | Source Plan | Status | Evidence |
|-----|------------|------------|--------|----------|
| RESET-01 | Anti-oracle 4-case identical 202 + dual-branch audit + 500ms timing + 3-key rate limit | 44-01 / 44-04 / 44-05 / 44-06 / 44-07 | ✓ SATISFIED | SC #1 above |
| RESET-02 | Atomic-consume `RETURNING` + Argon2 rotate + revoke-all + 410 generic on replay | 44-03 / 44-04 / 44-05 / 44-07 | ✓ SATISFIED | SC #2 above (with D-44-02 override on `password_changed_at`) |
| RESET-03 | URL-fragment token; invitation TTL=7d; reset TTL=1h; locked Russian templates | 44-01 / 44-02 / 44-09 | ✓ SATISFIED | SC #4 above |
| RESET-04 | `/users/invitations/accept` INSERT-only on soft-deleted-email + 200 + cookie pair | 44-04 / 44-05 / 44-08 | ✓ SATISFIED | SC #3 above (INSERT-only invariant pre-satisfied at Phase 43 create-user per D-44-20) |
| RESET-05 | `/users/invitations/{id}/revoke` + `user_invitation_revoked` audit + 409 on already-accepted | Phase 43 D-43-19 + 44-08 cross-coverage tests | ✓ SATISFIED | SC #5 above |

## 7. Anti-Patterns Scan

Scanned Phase 44-modified files: `password_reset_service.py`, `router.py` (auth + users), `email_templates.py`, `exceptions.py`, `schemas.py` (auth + users), `constants.py`, `reset_rate_limit.py`, `workers/scheduled/cleanup_password_reset_tokens.py`, `workers/__init__.py`.

| Pattern | Result | Severity |
|---------|--------|----------|
| `TBD\|FIXME\|XXX` debt markers | 0 hits in Phase 44 files | OK |
| `TODO` markers | Pre-existing only (none introduced by Phase 44) | OK |
| Empty implementations / `return null/{}/[]` placeholders | 0 in Phase 44 files | OK |
| `payload=` audit-emit anti-pattern (CR-01) | 0 in `password_reset_service.py` | OK |
| Console.log-only handlers | N/A (Python) | OK |
| Bare empty returns at "stub" entry points | None — all 3 service fns ship full bodies | OK |

## 8. Human Verification Required

None. All checks are programmatically verifiable. The single architectural deviation (no `users.password_changed_at` column) is documented in CONTEXT.md as **D-44-02** with planner sign-off; accepted via override block.

## 9. Goal-Backward Summary

> **Phase goal:** A pending-invitation user can accept their invitation by setting an initial password via email link; any user can reset their password via email link with full anti-oracle protection; existing operators can revoke outstanding invitations.

**Decomposition:**

1. *"pending-invitation user can accept via email link"* — `POST /api/v1/users/invitations/accept` exists, validates token via atomic-consume on `password_reset_tokens` (purpose=invitation), updates the existing pending-status user row in a single UPDATE…RETURNING, issues login cookies. ✓
2. *"any user can reset their password via email link"* — `POST /api/v1/auth/password-reset/request` issues token + email; `POST /api/v1/auth/password-reset/confirm` consumes token, rotates Argon2 hash, revokes all sessions. ✓
3. *"full anti-oracle protection"* — 4-case identical 202 + 500ms floor + dual-branch audit + rate-limit-as-202 (D-44-11). `test_password_reset_no_oracle.py` ungated from xfail-strict and now PASSING. ✓
4. *"existing operators can revoke outstanding invitations"* — Phase 43 `/users/invitations/{id}/revoke` shipped at D-43-19; Phase 44 adds cross-coverage tests proving the revoke ↔ accept race lock works end-to-end. ✓

All four goal clauses are observably true in the codebase. The phase delivers what the goal promised.

---

## VERIFICATION PASSED

**Status:** passed — 5/5 success criteria verified, 5/5 requirements satisfied, all 5 critical invariants grep-confirmed, 115 phase tests passing, ruff clean, import-linter contracts kept.

The one architectural deviation (no `users.password_changed_at` column — ROADMAP SC #2 literal text) is formally accepted via override block (D-44-02: DB-table single-SQL atomic-consume on `password_reset_tokens.consumed_at` supersedes the column-bump approach per Phase 41 D-41-04; forensic timestamp lives on `password_reset_completed` audit row).

_Verified: 2026-05-20_
_Verifier: Claude (gsd-verifier)_
