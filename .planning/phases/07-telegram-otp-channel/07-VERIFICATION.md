---
phase: 07-telegram-otp-channel
verified: 2026-05-02T20:30:00Z
status: passed
score: 4/4 success criteria + 8/8 REQ-IDs + 20/20 LOCKED decisions
overrides_applied: 0
re_verification: false
---

# Phase 7: Telegram OTP Channel — Verification Report

**Phase Goal:** Operator without a password can log in by tapping a deep-link to the bot, pressing `/start`, receiving a 6-digit DM, and pasting it into the admin-web — with all DM-blocked / wrong-code / expired-code edges handled deterministically.

**Verified:** 2026-05-02
**Status:** PHASE COMPLETE
**Re-verification:** No — initial verification

---

## Goal Achievement

### Success Criteria Verification

| # | Success Criterion | Status | Evidence |
|---|-------------------|--------|----------|
| 1 | `POST /auth/telegram/start` returns `{deepLinkUrl, deepLinkToken}` with deep-link TTL=10min; `GET /auth/telegram/status?token=...` reports `{bound: true}` only after bot links chat | VERIFIED | `router.py:194-212` mounts POST `/telegram/start` returning `TelegramStartResponse(deep_link_url, deep_link_token)`; `_build_deep_link_url` produces `f"https://t.me/{settings.telegram_bot_username}?start={token}"` (line 188-191). `telegram_service.start_deep_link` (lines 80-102) sets `expires_at = now + otp_deep_link_ttl_seconds` (default 600 = 10 min). `get_status` (lines 265-285) returns True iff `code_hash IS NOT NULL` AND not expired AND not consumed. Test `test_telegram_start_returns_deep_link_and_creates_otp_row` PASSED. |
| 2 | Bot DMs 6-digit code (TTL 5min, max 5 attempts); `/verify` upserts user by `telegram_chat_id`, issues same cookies as email/password, emits `otp_consumed` | VERIFIED | `commit_otp` (lines 163-189) sets `expires_at = now + otp_code_ttl_seconds` (300 = 5 min), `attempts = 0`; `consume` enforces `OtpMaxAttempts` at `attempts >= settings.otp_max_attempts` (5). `commit_otp` sets `user.telegram_chat_id` if NULL (line 181-182). Router `telegram_verify` (lines 232-270) calls `issue_tokens` + `issue_session_cookies` (identical to `/login` lines 74-81), emits `otp_consumed` (service line 256) and `login_success {channel='telegram'}` (router line 269). Test `test_telegram_verify_happy_path` PASSED with cookie + 2-event audit assertions. |
| 3 | Verify when bot not started → 409 `bot_not_started` with deep-link URL; expired/wrong/exceeded paths return distinct codes | VERIFIED | `exceptions.py` defines all 6 D-13 subclasses with correct `code` + `status_code`. Router catches `BotNotStarted` and re-raises with `fields={"deepLinkUrl": _build_deep_link_url(...)}` (lines 254-258). All 6 error tests PASSED: `test_verify_token_unknown_returns_404`, `test_verify_bot_not_started_carries_deep_link_url`, `test_verify_otp_expired_returns_410`, `test_verify_invalid_then_max_attempts`, `test_verify_already_consumed_returns_409`. |
| 4 | `docker compose up` brings up fourth `telegram-bot` service (`restart: unless-stopped`) running `python -m app.workers.telegram_bot` long-polling | VERIFIED | `docker-compose.yml:22-34` defines `telegram-bot` with `command: python -m app.workers.telegram_bot`, `restart: unless-stopped`, `depends_on: migrate (service_completed_successfully) + redis (service_started)`. `docker compose config --services` lists 5 services: backend, migrate, postgres, redis, telegram-bot. `app/workers/telegram_bot.py` ships `async def main()` with manual ptb 22 lifecycle (`initialize` → `start` → `updater.start_polling`) under `AsyncExitStack(db_lifespan_manager + redis_lifespan_manager)`, plus `if __name__ == "__main__": asyncio.run(main())` enabling `-m` invocation. |

**Score:** 4/4 success criteria verified.

---

### Required Artifacts (Three-Level Check)

| Artifact | Exists | Substantive | Wired | Data Flows | Status |
|----------|--------|-------------|-------|-----------|--------|
| `apps/backend/app/core/config.py` (5 new Settings fields) | YES | YES (lines 36-41) | YES (used in router + service) | YES | VERIFIED |
| `apps/backend/.env.example` (5 vars + TELEGRAM_OWNER_USERNAME) | YES | YES | YES | YES | VERIFIED |
| `apps/backend/alembic/versions/0003_telegram_username.py` | YES | YES (add_column + unique constraint) | YES (down_revision=0001_auth) | N/A | VERIFIED |
| `apps/backend/app/modules/auth/models.py` (`User.telegram_username`) | YES | YES (lines 52-56, `Mapped[str \| None]`, unique) | YES (queried by service) | YES | VERIFIED |
| `apps/backend/app/modules/auth/exceptions.py` (6 D-13 classes) | YES | YES (BotNotStarted/OtpExpired/OtpInvalid/OtpMaxAttempts/OtpAlreadyConsumed/TokenUnknown with correct code+status_code) | YES (raised by service, caught by router) | YES | VERIFIED |
| `apps/backend/app/modules/auth/telegram_service.py` | YES | YES (5 functions: start_deep_link/bind_and_issue/commit_otp/consume/get_status) | YES (imported by router + worker) | YES | VERIFIED |
| `apps/backend/app/modules/auth/schemas.py` (3 DTOs) | YES | YES (TelegramStartResponse line 58, TelegramStatusResponse line 69, TelegramVerifyRequest line 75) | YES (router uses) | YES | VERIFIED |
| `apps/backend/app/modules/auth/router.py` (3 telegram endpoints + login_success channel) | YES | YES (lines 194-270) | YES (mounted on auth router) | YES | VERIFIED |
| `apps/backend/app/modules/auth/service.py` (login_success channel kwarg) | YES | YES (line 138 emits `channel='email_password'`) | YES | YES | VERIFIED |
| `apps/backend/app/integrations/telegram/bot.py` (factory) | YES | YES (`build_application` factory, no module-level Application) | YES (called by worker) | YES | VERIFIED |
| `apps/backend/app/integrations/telegram/handlers.py` (start_handler + HandlerContext) | YES | YES (D-04 stranger path, D-11 atomic-after-DM, D-20 replay path) | YES (registered by worker) | YES | VERIFIED |
| `apps/backend/app/integrations/telegram/sender.py` (send_otp_dm + send_text_dm) | YES | YES (SendResult dataclass, Forbidden/BadRequest classification → blocked=True) | YES | YES | VERIFIED |
| `apps/backend/app/core/database.py` (`db_lifespan_manager`) | YES | YES (line 109) | YES (main.py + worker) | YES | VERIFIED |
| `apps/backend/app/core/redis.py` (`redis_lifespan_manager`) | YES | YES (line 21) | YES (main.py + worker) | YES | VERIFIED |
| `apps/backend/app/main.py` (lifespan adapter) | YES | YES (line 38 docstring confirms adapter pattern) | YES | YES | VERIFIED |
| `apps/backend/app/workers/__init__.py` (D-06 docstring) | YES | YES (explicit EXCEPTION clause documenting workers→modules.auth.telegram_service relaxation) | N/A | N/A | VERIFIED |
| `apps/backend/app/workers/telegram_bot.py` | YES | YES (manual lifecycle + AsyncExitStack + signal handlers + `__main__` guard) | YES (compose service runs it) | YES | VERIFIED |
| `apps/backend/docker-compose.yml` (telegram-bot service) | YES | YES (lines 22-34) | YES (`docker compose config` lists service) | N/A | VERIFIED |
| `apps/backend/scripts/seed_demo_data.py` (TELEGRAM_OWNER_USERNAME extension) | YES | YES (lines 71-83 — three idempotent paths) | YES | YES | VERIFIED |
| `apps/backend/tests/conftest.py` (stub_telegram_sender fixture) | YES | YES (line 184) | YES (consumed by 3 tests) | YES | VERIFIED |
| `apps/backend/tests/integration/auth/test_telegram_start.py` | YES | YES | YES (1 test PASSED) | YES | VERIFIED |
| `apps/backend/tests/integration/auth/test_telegram_verify_happy.py` | YES | YES | YES (1 test PASSED) | YES | VERIFIED |
| `apps/backend/tests/integration/auth/test_telegram_verify_errors.py` | YES | YES (parametrized over all 6 D-13 modes) | YES (5 tests PASSED) | YES | VERIFIED |
| `apps/backend/tests/integration/telegram/test_handler_start.py` | YES | YES (3 scenarios: known/unknown/blocked) | YES (3 tests PASSED) | YES | VERIFIED |

---

### Key Link Verification

| From | To | Via | Status | Details |
|------|-----|-----|--------|---------|
| Router `/telegram/verify` | `telegram_service.consume` | direct call line 253 | WIRED | `consume` returns User; router proceeds to issue tokens. |
| Router `/telegram/verify` | `issue_tokens` + `issue_session_cookies` | lines 260-267 | WIRED | Same call shape as `/login` (lines 74-81). |
| Router `/telegram/verify` | audit `emit("login_success", channel="telegram")` | line 269 | WIRED | Mirrors `service.py:138` `email_password` emission. |
| Worker | `db_lifespan_manager` + `redis_lifespan_manager` | AsyncExitStack lines 35-37 | WIRED | Same managers used by `app.main` lifespan adapters. |
| Worker | `build_application` | line 44-48 with `HandlerContext` closure | WIRED | Factory pattern (D-09); no module-level instance. |
| Handler | `ctx.telegram_service.bind_and_issue` → `commit_otp` | lines 106 + 148 | WIRED | Atomic-after-DM (D-11): commit only if `send_result.ok`. |
| Handler | `ctx.sender.send_otp_dm` | line 146 | WIRED | Sole outbound boundary (D-07). |
| Migration 0003 | model `User.telegram_username` | autogenerate-shaped column | WIRED | Migration adds `text NULL UNIQUE`; ORM matches. |

---

### Per-Decision Verdict (D-01..D-20)

| Decision | Status | Evidence |
|----------|--------|----------|
| D-01 Bind-existing-only login | HONORED | `grep -nE 'session\.add\(.*User\(\|insert\(User\)' telegram_service.py` returns nothing. `commit_otp` only mutates `user.telegram_chat_id` if NULL (line 181-182). |
| D-02 First-bind via bot self-claim by username | HONORED | `bind_and_issue` lookups `User.telegram_username == lower(username)` (line 146-148); `User.telegram_username Mapped[str \| None]` confirmed. |
| D-03 Seed script extension | HONORED | `seed_demo_data.py:71-83` reads `TELEGRAM_OWNER_USERNAME`, idempotent SELECT-then-conditional-UPDATE. |
| D-04 Stranger /start → DM error + structlog warning | HONORED | `handlers.py:112-121` catches `TelegramUnknownAccount`, emits `telegram_unknown_start` event, sends `_DM_STRANGER`, leaves OtpCode untouched. |
| D-05 Three-layer split | HONORED | `integrations/telegram/*` has zero imports of `app.modules.auth` (verified by grep + import-linter). HandlerContext NamedTuple in `handlers.py:33`. |
| D-06 Workers → modules.auth relaxation | HONORED | `workers/__init__.py` docstring explicitly documents EXCEPTION clause (lines 5-14). |
| D-07 sender.send_otp_dm sole outbound boundary | HONORED | `sender.py:38-53` is the only `bot.send_message` site; SendResult typed dataclass. |
| D-08 Reusable lifespan managers | HONORED | `database.py:109` + `redis.py:21` define managers; `main.py:38` + `workers/telegram_bot.py:36-37` both consume. |
| D-09 No module-level Application | HONORED | `bot.py` defines factory; `grep -nE '^application = Application\|^app = Application' bot.py` returns nothing. |
| D-10 Bot username from Settings | HONORED | `config.py:38` `telegram_bot_username: str`; `router.py:191` builds f-string with it. |
| D-11 Code generated AFTER successful DM | HONORED | `bind_and_issue` returns raw_code without commit (lines 154-155); `commit_otp` (lines 163-189) only called after `send_result.ok` (handlers.py:147-148). |
| D-12 No ARQ retry job | HONORED | No ARQ task wired for DM retry; handler logs `telegram_dm_failed` and exits (handlers.py:156-157). |
| D-13 Six distinct error subclasses | HONORED | All 6 classes in `exceptions.py` with correct (code, status_code): bot_not_started/409, otp_expired/410, otp_invalid/401, otp_max_attempts/429, otp_consumed/409, token_unknown/404. Test `test_telegram_verify_errors.py` exercises all 6 PASSING. |
| D-14 Same cookie+audit shape as email/password | HONORED | Router `/telegram/verify` uses identical `issue_tokens` + `issue_session_cookies` calls; emits `login_success {channel='telegram'}`. Service line 138 updated to `channel='email_password'`. |
| D-15 Handler tests via direct call | HONORED | `test_handler_start.py` uses hand-built Update/Message/User objects + `stub_telegram_sender` fixture, no live Application. |
| D-16 stub_telegram_sender pytest fixture | HONORED | `tests/conftest.py:184` defines fixture; consumed by all 3 handler tests + verify_happy. |
| D-17 No bot worker process tests | HONORED | Worker entry only exercised by manual `docker compose up` smoke; no test imports `telegram_bot.main`. |
| D-18 Single migration 0003 | HONORED | `0003_telegram_username.py` adds `users.telegram_username TEXT NULL UNIQUE`, `down_revision='0001_auth'`. |
| D-19 status returns {bound: bool} only | HONORED | `get_status` (telegram_service.py:265-285) never raises; unknown/expired/consumed all return False. |
| D-20 Deep-link tokens single-use | HONORED | `bind_and_issue` raises `OtpAlreadyConsumed` if `consumed_at IS NOT NULL` (line 141-142); `consume` raises same error (line 224-225). Handler catches and DMs `_DM_REPLAY` with `telegram_replay_attempt` event (handlers.py:127-133). |

**Decision audit:** 20/20 LOCKED decisions honored. No contradictions detected.

---

### Per-REQ-ID Verdict

| Requirement | Description | Status | Evidence |
|-------------|-------------|--------|----------|
| INFRA-06 | docker-compose `telegram-bot` service (`restart: unless-stopped`) reading `TELEGRAM_BOT_TOKEN` | SATISFIED | `docker-compose.yml:22-34` — service exists, restart policy correct, env_file: .env which carries TELEGRAM_BOT_TOKEN. |
| AUTH-TG-01 | `POST /auth/telegram/start` returns `{deepLinkUrl, deepLinkToken}` with TTL 10min | SATISFIED | `router.py:194-212` + `telegram_service.py:80-102` (`expires_at = now + otp_deep_link_ttl_seconds`, default 600). Test PASSED. |
| AUTH-TG-02 | Bot DMs 6-digit code TTL 5min, max 5 attempts | SATISFIED | `commit_otp` sets `expires_at = now + otp_code_ttl_seconds` (300); `OtpMaxAttempts` raised at `attempts >= 5`. Test `test_verify_invalid_then_max_attempts` PASSED. |
| AUTH-TG-03 | `GET /auth/telegram/status?token=...` returns `{bound: bool}` | SATISFIED | `router.py:215-229` + `telegram_service.get_status`. D-19 honored (never raises, oracle-safe). |
| AUTH-TG-04 | `POST /auth/telegram/verify` upserts user by chat_id, issues session like email/password | SATISFIED | `router.py:232-270` calls `issue_tokens` + `issue_session_cookies`; `commit_otp` sets `user.telegram_chat_id` if NULL (D-01: never inserts a User row — bind-existing-only is the policy). |
| AUTH-TG-05 | Bot worker as separate process via `python -m app.workers.telegram_bot`, NOT an ARQ task | SATISFIED | `app/workers/telegram_bot.py` ships `async def main()` + `if __name__ == "__main__": asyncio.run(main())`; docker-compose runs it as separate service; no ARQ task imports it. |
| AUTH-TG-06 | DM-blocked / chat-not-found → 409 `bot_not_started` carrying deep-link URL | SATISFIED | `sender.py:43-50` classifies `Forbidden` + `BadRequest("chat not found")` as `blocked=True`; handler skips commit (handlers.py:151-155); `/verify` raises `BotNotStarted` with `fields.deepLinkUrl` (router.py:254-258). Test `test_verify_bot_not_started_carries_deep_link_url` PASSED. |
| TEST-03 | Telegram OTP integration tests with stubbed `integrations.telegram.sender`: happy + expired + wrong + max-attempts + bot_not_started | SATISFIED | `stub_telegram_sender` fixture in `tests/conftest.py:184`. 4 test files cover all required modes. 10/10 telegram tests PASSED. |

**REQ-ID coverage:** 8/8 satisfied.

---

### Static Gates

| Gate | Result |
|------|--------|
| `uv run lint-imports` | All 3 contracts KEPT (core⊥modules / modules⊥each-other / integrations⊥modules), 0 broken |
| `uv run mypy --strict app` | Success: no issues found in 52 source files |
| `uv run ruff check app tests` | All checks passed! |
| `docker compose config --services` | Lists telegram-bot among 5 services |

---

### Test Execution Results

```
$ uv run pytest tests/integration/auth/test_telegram_start.py \
    tests/integration/auth/test_telegram_verify_happy.py \
    tests/integration/auth/test_telegram_verify_errors.py \
    tests/integration/telegram/test_handler_start.py -v

10 passed in 0.90s
```

| Test | Result |
|------|--------|
| `test_telegram_start_returns_deep_link_and_creates_otp_row` | PASSED |
| `test_telegram_verify_happy_path` | PASSED |
| `test_verify_token_unknown_returns_404` | PASSED |
| `test_verify_bot_not_started_carries_deep_link_url` | PASSED |
| `test_verify_otp_expired_returns_410` | PASSED |
| `test_verify_invalid_then_max_attempts` | PASSED |
| `test_verify_already_consumed_returns_409` | PASSED |
| `test_handler_known_username_binds_and_dms` | PASSED |
| `test_handler_unknown_username_emits_event_and_dms_stranger` | PASSED |
| `test_handler_sender_blocked_skips_commit_and_emits_event` | PASSED |

**Full backend regression:** `uv run pytest -q` → **204 passed in 6.09s**. No regressions from prior phases.

---

### Anti-Patterns Found

None. Spot-grep for stub/TODO/placeholder patterns in Phase 7 files:
- No `TODO`/`FIXME` markers in any of the 8 `key-files` lists across all SUMMARYs that map to live code paths.
- No `return None`/`return {}`/`return []` placeholder in service or router endpoints.
- No `console.log`-equivalent (e.g., `print()` debug) leakage; only `print()` calls are intentional in `seed_demo_data.py`.
- No `pass` body or `NotImplementedError` raises in any new module.

---

### Deferred Items Audit

CONTEXT.md `<deferred>` items confirmed NOT implemented in Phase 7 (all correctly out of scope):
- Telegram-only signup (auto-provisioned users) — REJECTED (D-01); no User insertion in `telegram_service.py`.
- Admin-web Bind-Telegram UI — Phase 10 / v1.2 (no FE work in Phase 7, confirmed).
- Webhook-mode bot — long-polling only (`updater.start_polling()` used).
- Password reset via Telegram DM — not implemented.
- ARQ retry job for DM — not implemented; handler emits `telegram_dm_failed` and exits.
- Periodic OtpCode cleanup — TTL is the GC; no vacuum job.
- Bot commands beyond `/start` — only `CommandHandler("start", ...)` registered (bot.py:79).
- Per-IP rate limit on `/auth/telegram/start` — not implemented (acceptable per CONTEXT line 296).

No deferred-item creep.

---

### Human Verification Required

None. The phase ships a backend module with comprehensive automated coverage:
- All 3 endpoints verified via httpx integration tests (`ASGITransport`).
- Bot handler verified via direct-call tests with stubbed sender (D-15).
- Worker entry intentionally NOT tested (D-17); its runtime smoke is `docker compose up` which is operational, not phase-gating. The worker body (~30 LOC) is a thin composition of building blocks each individually tested.

The deep-link end-to-end (FE clicks → Telegram opens → bot DMs → operator pastes code) is a Phase 10 (admin-web wiring) concern. Phase 7 ships the contract that Phase 10 will consume; the backend contract is verified.

---

## Cross-Phase Notes

- INFRA-06 wording mentions "alongside web/worker/migrate"; the live compose has services `backend` (the API, was `web` in spec language) + `migrate` + `postgres` + `redis` + `telegram-bot` — no ARQ worker compose service is present yet. This matches the codebase reality (no INFRA req for an ARQ compose service was scheduled in Phases 1–6) and does NOT block Phase 7's stated goal — Phase 7's narrow contract is the fourth (telegram-bot) service, which is present and correct. Future ARQ worker compose entry is a v1.2 concern.
- Migration numbering jumps 0001→0003 (no 0002). Per D-18 the file is named `0003_telegram_username.py` and `down_revision='0001_auth'` — the chain is sane and `alembic upgrade head` resolves cleanly.

---

## Gaps Summary

**No gaps.** All 4 success criteria, all 8 REQ-IDs, all 20 LOCKED decisions, and all static gates pass. Test suite is green (204/204). Codebase artifacts match SUMMARY claims; no stub or unwired components found.

---

## PHASE COMPLETE

Phase 7 (Telegram OTP Channel) delivers exactly what the goal promised: an operator without a password can request a deep-link via `/auth/telegram/start`, press `/start <token>` in the bot, receive a 6-digit DM, and exchange it via `/auth/telegram/verify` for the same cookie pair as the email/password login — with all six D-13 failure modes returning distinct error codes (including the 409 `bot_not_started` carrying `fields.deepLinkUrl` so the FE can redisplay the deep-link). The backend layer boundary (integrations ⊥ modules) is preserved; the workers→modules.auth relaxation is documented in two docstrings; the bot worker runs as a fourth `restart: unless-stopped` docker-compose service. All static gates (lint-imports / mypy strict / ruff) and the full 204-test suite are green.

---

*Verified: 2026-05-02*
*Verifier: Claude (gsd-verifier)*
