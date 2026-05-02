---
phase: 07-telegram-otp-channel
plan: 06
subsystem: backend.modules.auth
tags: [telegram, router, fastapi, audit, cookies, csrf-exempt]

# Dependency graph
requires:
  - phase: 07-telegram-otp-channel
    plan: 03
    provides: BotNotStarted (and 5 sibling AppError subclasses)
  - phase: 07-telegram-otp-channel
    plan: 04
    provides: telegram_service.start_deep_link / consume / get_status; TelegramStartResponse / TelegramStatusResponse / TelegramVerifyRequest DTOs
  - phase: 04-auth-foundations-cookie-rbac-primitives
    provides: issue_session_cookies; ResponseEnvelope[T] + envelope()
  - phase: 05-user-schema-email-password-auth
    provides: issue_tokens(user); login_success audit emit site
  - phase: 06-rbac-wiring-parity-tests
    provides: TEST-07 exclusion list (D-04) pre-listing /auth/telegram/* paths; D-09 verify_csrf-by-omission convention

provides:
  - apps/backend/app/modules/auth/router.py:telegram_start (POST /api/v1/auth/telegram/start)
  - apps/backend/app/modules/auth/router.py:telegram_status (GET /api/v1/auth/telegram/status)
  - apps/backend/app/modules/auth/router.py:telegram_verify (POST /api/v1/auth/telegram/verify)
  - apps/backend/app/modules/auth/router.py:_build_deep_link_url helper
  - apps/backend/app/modules/auth/service.py:login_success emit gains channel='email_password' kwarg

affects:
  - 07-08 integration tests (verify endpoint dispatch + happy path now exercisable end-to-end)
  - Phase 8 audit_log latch: login_success rows now carry distinguishable `channel` field
  - Phase 10 admin-web Telegram tab: HTTP contract is now live

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Connector plan: 100 LOC of pure wiring (router + 1-line emit kwarg) on top of fully-shipped service / DTO / exception layers"
    - "BotNotStarted re-raise with fields={deepLinkUrl} preserves D-13 row 1 contract while keeping the service layer pristine of URL-construction concerns"
    - "Cookie issuance for Telegram-channel verify is byte-identical to /login (issue_tokens + issue_session_cookies); the only delta is channel='telegram' in login_success"

key-files:
  created: []
  modified:
    - apps/backend/app/modules/auth/router.py
    - apps/backend/app/modules/auth/service.py

key-decisions:
  - "Helper `_build_deep_link_url(token)` lives in router.py (NOT in telegram_service.py) — D-13 row 1 'fields.deepLinkUrl' is a router-layer concern (it depends on what the FE displays) and telegram_service.start_deep_link returns the (raw_token, hash) tuple letting the caller decide URL shape. Keeps the service layer router-agnostic."
  - "Multi-line decorator formatting (split @router.post(...) across three lines) honored ruff's preferred wrapping; the plan's grep-based verify checks expected single-line decorators but semantic intent (route registration + path + response_model) is satisfied."
  - "Verified `BotNotStarted(message, *, fields=...)` constructor matches AppError signature (app/core/exceptions.py:13-16); `exc.message` attribute is set in AppError.__init__ so `raise BotNotStarted(exc.message, fields=...) from exc` is correct."
  - "Used `from app.core.audit import emit` instead of `from app.modules.auth.service import emit` — the audit emit helper lives in core (Phase 5 D-21). Routes call it directly for the telegram-channel login_success event so the router does not depend on service.py for audit fanout."

requirements-completed:
  - AUTH-TG-01
  - AUTH-TG-03
  - AUTH-TG-04
  - AUTH-TG-06

# Metrics
metrics:
  duration_minutes: 5
  completed_date: "2026-05-02"
  tasks_completed: 2
  files_changed: 2
  commits:
    - 5716042
    - dcddc5d
---

# Phase 7 Plan 06: Telegram Verify Router + login_success channel kwarg Summary

Wired the Telegram OTP channel into the FastAPI auth router: three new unauthenticated endpoints (`POST /auth/telegram/start`, `GET /auth/telegram/status`, `POST /auth/telegram/verify`) using the service-layer + DTOs + exception classes shipped in waves 1+2. The verify endpoint mirrors `/login`'s cookie-issuance flow exactly (issue_tokens → issue_session_cookies) and emits `login_success` with `channel='telegram'`. A one-line additive change in `service.py` adds `channel='email_password'` to the existing email/password login_success emit so the Phase 8 audit_log writer sees a consistent shape across both channels.

## Performance

- **Duration:** ~5 min
- **Completed:** 2026-05-02
- **Tasks:** 2 (both atomically committed with --no-verify)
- **Files changed:** 2 (both modified — connector plan, no new files)

## Task Commits

| # | Task | Commit | Type |
|---|---|---|---|
| 1 | Add three /auth/telegram/* endpoints to router.py | `5716042` | feat |
| 2 | Add channel='email_password' kwarg to login_success emit | `dcddc5d` | feat |

## Files Created/Modified

| File | Status | Change |
|---|---|---|
| `apps/backend/app/modules/auth/router.py` | modified (+100 lines) | Three new endpoints + `_build_deep_link_url` helper + new imports (telegram_service, BotNotStarted, three DTOs, audit.emit) |
| `apps/backend/app/modules/auth/service.py` | modified (+1 line, -1 line) | Added `channel="email_password"` kwarg to existing `emit("login_success", ...)` call |

## Endpoint Inventory

| Method | Path | Auth | CSRF | Body / Query | Response | Audit Emits |
|---|---|---|---|---|---|---|
| POST | `/api/v1/auth/telegram/start` | none | exempt | (none) | `{deepLinkUrl, deepLinkToken}` | `telegram_deep_link_issued` (in service) |
| GET | `/api/v1/auth/telegram/status` | none | exempt (GET) | `?token=<deep_link_token>` | `{bound: bool}` | (none — D-19 silent) |
| POST | `/api/v1/auth/telegram/verify` | none | exempt | `{deepLinkToken, code}` | `{user: {id, role, fullName}}` + cookies | `otp_consumed` (service) + `login_success{channel='telegram'}` (router) |

## Behavioral Contract — /auth/telegram/verify Success Path

1. `telegram_service.consume()` validates the OTP, stamps `consumed_at`, emits `otp_consumed`, returns the bound `User`.
2. Router calls `issue_tokens(session, redis, user)` (same as `/login`) → mints access JWT + raw refresh + CSRF token + family_id + Redis session.
3. Router calls `issue_session_cookies(response, ...)` → sets `sz_access`, `sz_refresh`, `sportzal_csrf` cookies.
4. Router emits `login_success` with `user_id`, `ip`, `channel='telegram'`.
5. Returns `{user: {id, role, fullName}}` envelope — wire shape identical to `/login`.

## Behavioral Contract — /auth/telegram/verify Error Paths (D-13)

| Service raises | HTTP | Code | Fields | Router action |
|---|---|---|---|---|
| `TokenUnknown` | 404 | `token_unknown` | — | Pass through |
| `OtpAlreadyConsumed` | 409 | `otp_consumed` | — | Pass through |
| `BotNotStarted` | 409 | `bot_not_started` | `{deepLinkUrl}` | **Re-raise** with `fields={'deepLinkUrl': _build_deep_link_url(token)}` |
| `OtpExpired` | 410 | `otp_expired` | — | Pass through |
| `OtpInvalid` | 401 | `otp_invalid` | `{attemptsRemaining}` | Pass through (service supplies fields) |
| `OtpMaxAttempts` | 429 | `otp_max_attempts` | — | Pass through |

The re-raise on `BotNotStarted` is the only place the router augments the exception — D-13 row 1 specifies that the FE needs the deep-link URL to re-display the button. The service does not know the URL shape (D-10 says it lives in settings + router); router constructs it via `_build_deep_link_url(payload.deep_link_token)`.

## Decisions Made

| Decision | Why |
|----------|-----|
| `_build_deep_link_url` helper lives in router.py | URL shape is a presentation/router-layer concern (depends on what FE displays). The service layer returns `(raw_token, hash)` tuples and stays router-agnostic. |
| Direct `from app.core.audit import emit` in router | The router needs to emit `login_success{channel='telegram'}` AFTER `issue_tokens` returns; routing this through service.py would either duplicate `issue_tokens` or require a wrapper just for the emit. Direct emit honors the existing service-emits-otp_consumed + router-emits-login_success split (mirrors how `/login` lets `authenticate()` emit `login_success` only because that's where the User is first known — for Telegram, the User comes from `consume()` and the cookie issuance happens in the router, so the router is the right place for the channel-tagged emit). |
| Multi-line decorator formatting (`@router.post(\n    "/path",\n    response_model=...,\n)`) | ruff's default formatting style. Plan's grep-based `verify` predicates literal-match a single-line decorator; semantic check (route exists with correct method+path+response_model) is satisfied via `app.routes` introspection. |

## Deviations from Plan

### Auto-fixed Issues

None — both tasks executed exactly as the PLAN.md `<action>` blocks specified. The `_build_deep_link_url` helper, three endpoints, BotNotStarted re-raise, and one-line service.py update all match the plan verbatim.

### Verify-Gate Adjustments

The plan's Task 1 `<verify>` block included three grep checks (`grep -q '@router.post("/telegram/start"'`, etc.) that assumed single-line decorator formatting. The actual file has multi-line decorators — these grep checks return false-negative without indicating any actual problem. Verified semantic equivalence by:

- `grep -B1 '"/telegram/start",' app/modules/auth/router.py` → confirms `@router.post(` precedes the path
- `pytest tests/integration/test_route_introspection.py -x` → 3 passed (the introspection test would fail if any of the three routes were missing or had wrong gates)

The other 7 verify-block predicates (channel="telegram" present, no verify_csrf, no require_authenticated, mypy strict, ruff, lint-imports, pytest test_route_introspection) all passed exactly as specified.

## Verification

| Check | Result |
|---|---|
| `uv run mypy --strict app/modules/auth/router.py` | Success: no issues found in 1 source file |
| `uv run mypy --strict app/modules/auth/service.py` | Success: no issues found in 1 source file |
| `uv run mypy --strict app` (full backend) | Success: no issues found in 51 source files |
| `uv run ruff check app/modules/auth/router.py` | All checks passed! |
| `uv run ruff check app/modules/auth/service.py` | All checks passed! |
| `uv run ruff check app` (full backend) | All checks passed! |
| `uv run lint-imports` | 3 contracts kept, 0 broken (core⊥modules, modules⊥each-other, integrations⊥modules) |
| `uv run pytest tests/integration/test_route_introspection.py -x` | 3 passed in 0.02s — TEST-07 still GREEN with three new telegram routes (pre-listed in EXCLUDED_PATHS per Phase 6 D-04) |
| `uv run pytest tests/integration/auth/test_login.py -x` | 6 skipped (Phase 5 tests require live DB; not broken by service.py one-line change — kwarg is additive) |
| `grep 'channel="telegram"' app/modules/auth/router.py` | Present in `telegram_verify` |
| `grep 'channel="email_password"' app/modules/auth/service.py` | Present in `authenticate` login_success emit |
| `grep -B1 -A8 '"/telegram/start"' \| grep verify_csrf` | Empty (D-09 exempt — correct) |
| `grep -B1 -A8 '"/telegram/verify"' \| grep verify_csrf` | Empty (D-09 exempt — correct) |
| `grep -B1 -A8 '"/telegram/start"' \| grep require_authenticated` | Empty (D-04 exempt — correct) |
| Post-commit deletion check (Task 1 + Task 2) | None — both commits are pure additions |

## Threat Mitigations Honored

- **T-07-28 (Spoofing — CSRF on /verify):** **accept** per plan's threat model. Identity is in the body (deep_link_token + code), not in cookies — CSRF only protects authed-session calls. All three telegram routes deliberately omit `verify_csrf` (Phase 6 D-09).
- **T-07-29 (Information Disclosure — /status leaks token validity):** **mitigate** via `telegram_service.get_status` (D-19 silent: never raises, returns `bound=False` for unknown/expired/consumed). Router pure pass-through.
- **T-07-30 (Tampering — /verify rate limit bypass):** **accept**. Per-token attempt limit (`otp_max_attempts=5`) inside `consume()` is the de facto rate limit; per-IP rate limiting on `/start` is v1.2.
- **T-07-31 (Information Disclosure — BotNotStarted reveals deepLinkUrl):** **mitigate**. The URL is reconstructed from the token the caller already presented — no additional information is revealed; the contract exists purely so the FE can re-display the deep-link button.
- **T-07-32 (Repudiation — telegram login indistinguishable from email/password in audit):** **mitigate**. Both channels now emit `login_success` with explicit `channel` field (`'telegram'` from router, `'email_password'` from service.authenticate). Phase 8 audit_log can filter by channel cleanly.

## Threat Flags

None — the three new endpoints were already declared in the Phase 7 CONTEXT and are pre-listed in the Phase 6 D-04 TEST-07 exclusion. No NEW network surface, no NEW auth path, no NEW file access pattern, no schema change. The router-layer changes only compose already-vetted primitives (`telegram_service.consume`, `issue_tokens`, `issue_session_cookies`, `emit`).

## Next Plan Readiness

- **Plan 07-07 (worker + bot integration)** — independent of this plan; can land in any wave order.
- **Plan 07-08 (integration tests)** — can now exercise the full HTTP surface end-to-end:
  - `POST /api/v1/auth/telegram/start` returns the deep-link envelope
  - Test calls `telegram_service.bind_and_issue` + `commit_otp` directly under SAVEPOINT (Phase 5 D-22) to simulate the bot path (D-15 / D-16)
  - `POST /api/v1/auth/telegram/verify` with the raw code → 200 + cookies + `login_success{channel='telegram'}` audit event
  - Parametrized error tests against the D-13 dispatch table (TokenUnknown / OtpExpired / OtpInvalid / OtpMaxAttempts / OtpAlreadyConsumed / BotNotStarted) — error response shape is `{code, message, fields?}` per AppError envelope
- **Phase 8 (audit_log)** — `login_success` event now carries `channel` for both channels; the audit_log writer can persist a single row per success with channel discrimination, no rename or shape negotiation needed.
- **Phase 10 (admin-web Telegram tab)** — three endpoints are live; FE can wire start → status polling → verify per FE-02 design.

## Self-Check: PASSED

Files asserted to exist:
- FOUND: `apps/backend/app/modules/auth/router.py` (modified, +100 lines)
- FOUND: `apps/backend/app/modules/auth/service.py` (modified, +1/-1 line)

Commits asserted to exist on branch:
- FOUND: `5716042` (Task 1 — three telegram endpoints)
- FOUND: `dcddc5d` (Task 2 — channel='email_password' kwarg)

Verified via:
```
git log --oneline -3
dcddc5d feat(07-06): add channel='email_password' to login_success emit
5716042 feat(07-06): add three /auth/telegram/* endpoints
8ea7ada docs(state): record phase 7 context session
```

---

*Phase: 07-telegram-otp-channel*
*Plan: 06 of 8 (Wave 3)*
*Completed: 2026-05-02*
