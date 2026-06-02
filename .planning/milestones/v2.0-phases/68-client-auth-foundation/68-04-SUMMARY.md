---
phase: 68-client-auth-foundation
plan: "04"
subsystem: client-auth
tags: [auth, otp, session, redis, rate-limit, anti-oracle, security]
dependency_graph:
  requires: [68-01, 68-02, 68-03]
  provides: [client_otp_service, client_session_rotation, client_logout, client_email_update]
  affects: [client_auth_router, main_composition_root]
tech_stack:
  added: []
  patterns:
    - _constant_time_floor anti-oracle floor (mirrors auth/service.py)
    - 3-branch refresh rotation with family reuse detection (mirrors rotate_refresh)
    - rate-limit-before-lookup ordering (CAUTH-02)
    - composition-root OTP sender slot (D-01)
    - partial-unique IntegrityError → 409 email_unavailable (D-06)
key_files:
  created:
    - apps/backend/app/modules/client_auth/rate_limit.py
    - apps/backend/app/modules/client_auth/service.py
  modified:
    - apps/backend/.importlinter
decisions:
  - "register_client_otp_sender composition-root slot: bot sender is None until plan 05 wires it; request_client_otp silently skips DM in test/unconfigured mode"
  - "OtpCode.deep_link_token_hash placeholder uses client-otp:{uuid4().hex} prefix (non-overlapping with real sha256 hashes, mirrors email-channel: pattern)"
  - "revoke_client_session uses pipeline for Redis cleanup (vs individual calls in auth/service.py) — simpler for logout where ordering doesn't matter"
metrics:
  duration: ~15m
  completed: "2026-05-29"
  tasks: 3
  files: 3
---

# Phase 68 Plan 04: Client Auth Service Layer Summary

Client OTP request/verify + 3-branch refresh rotation + logout + email-only profile update with anti-oracle, rate-limiting, and strict auth:client:* Redis namespace isolation.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | client_auth/rate_limit.py (isolated per-IP + per-phone limiters) | d6f45dcb | rate_limit.py, .importlinter |
| 2 | request_client_otp (anti-oracle) + verify_client_otp (issue session) | 22dbb3fe | service.py |
| 3 | rotate_client_refresh (3-branch) + revoke_client_session + update_client_me | 22dbb3fe | service.py |

## What Was Built

### `app/modules/client_auth/rate_limit.py`

Three isolated Redis rate limiters for client OTP requests (D-11):
- `check_client_ip_rate` / `bump_client_ip_rate`: 5 requests/15min per IP (`ratelimit:client_otp_ip:{ip}`)
- `check_client_otp_cooldown` / `record_client_otp_sent`: 60s cooldown per phone (`ratelimit:client_otp_cooldown:{phone}`)
- `check_client_otp_daily` / `bump_client_otp_daily`: 5 requests/24h per phone (`ratelimit:client_otp_daily:{phone}`)

Keys are strictly `ratelimit:client_otp_*` — no overlap with staff `ratelimit:login:{email}` limiter.

### `app/modules/client_auth/service.py`

Five service functions:

**`request_client_otp(session, redis, phone, *, ip)`**
- Captures `t_start`, wraps body in `try/finally: await _constant_time_floor(t_start)`
- Rate-limit checks (3 checks) run BEFORE `select(Client)` lookup — CAUTH-02 invariant
- Unknown/unlinked/soft-deleted phone → silent `return` (D-02 anti-oracle)
- Consumes prior active OtpCode, inserts fresh `OtpCode(client_id=...)`, audit.emit before commit
- Bumps Redis counters post-commit; calls `_client_otp_sender` if registered (D-01)

**`verify_client_otp(session, redis, phone, code) → (access, refresh, csrf)`**
- Inline consume/attempts logic against `OtpCode.client_id` — does NOT call `telegram_service.consume()`
- Increments `attempts` + commits before raising on mismatch (counter cannot be rewound)
- Raises `OtpMaxAttempts` when `attempts >= settings.otp_max_attempts`
- On success: mints `ClientRefreshToken`, writes `auth:client:session:{client_id}:{family_id}` + `auth:client:user_sessions:{client_id}` keys
- Returns `(encode_client_token(...), raw_refresh, csrf)`

**`rotate_client_refresh(session, redis, presented_token) → (access, refresh, csrf)`**
- Branch (A) ACTIVE: rotates, caches pair at `auth:client:rotate:{hash}`, updates session keys
- Branch (B) REPLACED-WITHIN-WINDOW: returns cached pair (idempotent double-submit)
- Branch (C) REUSE/REVOKED: revokes whole family, emits `client_family_reuse_detected`, raises `InvalidSession`
- All keys in `auth:client:*` namespace — CISO-05 isolation confirmed by grep

**`revoke_client_session(session, redis, presented_token)`**
- Idempotent: unknown token returns without error
- Revokes all family rows; cleans `auth:client:session:` and `auth:client:user_sessions:` via pipeline

**`update_client_me(session, client_id, email) → Client`**
- Updates `email` only (D-04); `IntegrityError` on partial-unique `lower(email)` mapped to `ConflictError("email_unavailable")` — generic 409, non-enumerating (D-06)

### `.importlinter` updates

- Added `app.modules.client_auth` to `modules-independent` contract
- Added 3 narrow `ignore_imports` edges for cross-module reads:
  - `client_auth.service → auth.exceptions` (OtpExpired/OtpInvalid/OtpMaxAttempts)
  - `client_auth.service → auth.models` (OtpCode — shared D-03 table)
  - `client_auth.service → clients.models` (Client — phone-first lookup)

## Security Properties Verified

| Requirement | Verification |
|-------------|-------------|
| CAUTH-02 anti-oracle | rate-limit checks at lines 178-180, `select(Client)` at 182-183 — ordering verified by AST scan |
| CAUTH-02 timing floor | `_constant_time_floor` in `finally:` block covers RateLimited + all exception paths |
| D-02 silent no-op | `if client is None or client.telegram_user_id is None: return` |
| CISO-05 namespace | grep confirms `auth:client:*` only, zero `auth:session:` / `auth:user_sessions:` in service.py |
| CAUTH-04 family reuse | Branch (C) revokes whole family + emits `client_family_reuse_detected` |
| CAUTH-06 brute-force | inline attempts++ + OtpMaxAttempts cap in verify_client_otp |
| D-06 email 409 | IntegrityError → `ConflictError("email_unavailable")` — no enumeration signal |

## Deviations from Plan

### Auto-applied (Rule 2 — Missing Critical Functionality)

**1. [Rule 2 - Missing] Composition-root OTP sender slot**
- **Found during:** Task 2 (request_client_otp)
- **Issue:** The HTTP server process does not run the Telegram bot long-poll loop. The plan referred to "reuse the telegram sender" but `send_otp_dm(bot, ...)` requires a `Bot` instance only available in the worker process.
- **Fix:** Added `register_client_otp_sender(sender)` composition-root slot (mirrors `register_user_session_invalidator` pattern). Slot is `None` by default; `request_client_otp` silently skips the DM when unregistered (test/dev mode). Plan 05 wires the real bot sender in `create_app()`.
- **Files modified:** `app/modules/client_auth/service.py` (added `ClientOtpSender` type alias + `_client_otp_sender` slot + `register_client_otp_sender`)
- **Commit:** 22dbb3fe

**2. [Rule 2 - Missing] import-linter registration for client_auth module**
- **Found during:** Task 1 (creating rate_limit.py)
- **Issue:** `app.modules.client_auth` was not in the `modules-independent` contract; cross-module imports to `auth` and `clients` would be silently unchecked.
- **Fix:** Added module to contract + 3 narrow `ignore_imports` edges for legitimate cross-module reads.
- **Files modified:** `apps/backend/.importlinter`
- **Commit:** 22dbb3fe

## Known Stubs

None — all functions are fully implemented. The OTP DM send path has `_client_otp_sender is None` guard (test/unconfigured mode); this is intentional and documented; Plan 05 wires the real sender.

## Threat Flags

No new network endpoints or trust boundaries introduced in this plan. The service functions are internal and called only by the client_auth router (Plan 05).

## Self-Check: PASSED

Files exist:
- `apps/backend/app/modules/client_auth/rate_limit.py` — FOUND
- `apps/backend/app/modules/client_auth/service.py` — FOUND

Commits exist:
- `d6f45dcb` — FOUND (feat(68-04): add client OTP rate limiters)
- `22dbb3fe` — FOUND (feat(68-04): implement client auth service)

Tooling gates:
- `uv run mypy --strict app/modules/client_auth/` — PASSED (0 issues)
- `uv run ruff check app/modules/client_auth/` — PASSED (0 issues)
- `uv run lint-imports` — PASSED (3 kept, 0 broken)
- `grep auth:client: service.py` — FOUND
- `grep -E "auth:session:|auth:user_sessions:" service.py` — NOT FOUND (correct)
- `grep ratelimit:login rate_limit.py` — NOT FOUND (correct)
