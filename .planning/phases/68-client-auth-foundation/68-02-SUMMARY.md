---
phase: 68-client-auth-foundation
plan: "02"
subsystem: backend/security
tags: [client-auth, jwt, cookies, security, isolation]
dependency_graph:
  requires: []
  provides:
    - ClientAccessTokenClaims
    - encode_client_token
    - decode_client_token
    - issue_client_session_cookies
    - clear_client_session_cookies
  affects:
    - app/core/dependencies.py (will import decode_client_token in plan 68-03)
    - app/modules/client_auth/router.py (will import issue/clear_client_session_cookies)
tech_stack:
  added: []
  patterns:
    - "frozen dataclass client JWT claims (no role, aud=client)"
    - "PyJWT verify_aud=False + manual guard → specific wrong_audience error code"
    - "Path-scoped refresh cookie /api/v1/client (D-10)"
key_files:
  created: []
  modified:
    - apps/backend/app/core/security.py
decisions:
  - "D-07: staff tokens stay aud-less; client tokens carry aud=client — isolation via separate decode rules"
  - "D-08: decode_client_token is fully parallel to decode_access_token; client tokens never route through staff decode"
  - "D-10: cc_client_refresh Path=/api/v1/client prevents cookie collision with staff cc_refresh Path=/api/v1/auth on same origin"
  - "PyJWT verify_aud=False used so manual aud check yields specific wrong_audience error code (not generic invalid_token)"
metrics:
  duration: "~4 minutes"
  completed: "2026-05-29T17:04:05Z"
  tasks_completed: 2
  files_modified: 1
---

# Phase 68 Plan 02: Client JWT + Cookie Primitives Summary

Five new symbols added to `app/core/security.py` providing isolated client JWT encode/decode and cookie issue/clear helpers. Staff `AccessTokenClaims`, `encode_access_token`, `decode_access_token`, `issue_session_cookies`, and `clear_session_cookies` are byte-unchanged (CISO-01 / D-07 frozen contract).

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Add ClientAccessTokenClaims + encode_client_token + decode_client_token | af161efc | apps/backend/app/core/security.py |
| 2 | Add issue_client_session_cookies + clear_client_session_cookies | af161efc | apps/backend/app/core/security.py |

## What Was Built

**`ClientAccessTokenClaims`** — frozen dataclass with `sub`, `aud`, `typ`, `iat`, `exp`; no `role` field. The absence of `role` is the structural guarantee that client claims can never be confused with staff claims.

**`encode_client_token(client_id, *, now)`** — mirrors `encode_access_token` exactly but emits `aud="client"` in the payload and omits `role`. Uses `settings.access_token_ttl_seconds`, HS256 with `settings.secret_key`.

**`decode_client_token(token)`** — mirrors `decode_access_token` with three changes: (1) `require=["aud"]` so staff tokens (no `aud` claim) raise `invalid_token` via `MissingRequiredClaimError`; (2) `verify_aud=False` so PyJWT's built-in audience check does not swallow the error into `invalid_token` — the manual `payload.get("aud") != "client"` guard then raises the specific `wrong_audience` code; (3) no `Role` coercion — a client token passed to `decode_access_token` fails because `role` claim is absent.

**`issue_client_session_cookies`** — sets `cc_client_access` (`path="/"`), `cc_client_refresh` (`path="/api/v1/client"`, D-10), and `clubcore_client_csrf` (`path="/"`, `httponly=False` for double-submit). Cookie names use `cc_client_*` prefix to prevent collision with staff `cc_*` cookies on the same origin (CISO-05 / T-68-07).

**`clear_client_session_cookies`** — deletes all three cookies with attributes matching the issuer exactly (path/httponly/samesite/secure), per T-68-08 mitigation. Attribute mismatch causes silent browser no-op.

## Verification Results

- `uv run mypy --strict app/core/security.py` → `Success: no issues found in 1 source file`
- `uv run ruff check app/core/security.py` → `All checks passed!`
- Round-trip: `encode_client_token` → `decode_client_token` yields `aud=="client"`, no `role` attribute
- Staff token (no `aud`) rejected by `decode_client_token` with `invalid_token`
- Client token (no `role`) rejected by `decode_access_token` with `invalid_token`
- Wrong-aud token yields `wrong_audience` specifically
- `git diff` shows zero changes to staff symbols (lines 31–292 byte-identical)
- `/api/v1/client` appears 5 times (2× in `issue_client_session_cookies`, 2× in `clear_client_session_cookies`, 1× in comment)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] PyJWT auto-validates aud claim causing round-trip failure**

- **Found during:** Task 1 verification (`encode_client_token` → `decode_client_token` raised `invalid_token`)
- **Issue:** PyJWT 2.12.1 automatically validates the `aud` claim when it is present in the token and no `audience` kwarg is passed — raising `InvalidAudienceError` (a subclass of `InvalidTokenError`). This caused the round-trip test to fail with `invalid_token` instead of succeeding.
- **Fix:** Added `"verify_aud": False` to the `options` dict in `decode_client_token`. The `require=["aud"]` remains so tokens without `aud` still raise `invalid_token`. The manual `payload.get("aud") != "client"` guard then produces the specific `wrong_audience` error code as required by the plan spec.
- **Files modified:** `apps/backend/app/core/security.py`
- **Commit:** af161efc

## Known Stubs

None. All five symbols are fully implemented with no hardcoded empty values or TODO placeholders.

## Threat Flags

No new threat surface beyond what is documented in the plan's `<threat_model>`. All T-68-05 through T-68-09 mitigations are implemented:
- T-68-05: `decode_client_token` asserts `aud=="client"`; staff `decode_access_token` validates `role` against `Role` enum
- T-68-06: HS256 with `settings.secret_key`; bad signature → `invalid_token`
- T-68-07: Distinct `cc_client_*` cookie names + refresh `Path=/api/v1/client`
- T-68-08: `clear_client_session_cookies` replicates issuer Path/HttpOnly/SameSite/Secure exactly
- T-68-09: `clubcore_client_csrf` is `httponly=False` — intentional (double-submit pattern, accepted risk)

## Self-Check: PASSED

- security.py: FOUND
- commit af161efc: FOUND
- ClientAccessTokenClaims: FOUND
- decode_client_token: FOUND
- issue_client_session_cookies: FOUND
- clear_client_session_cookies: FOUND
