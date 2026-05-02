# Phase 7: Telegram OTP Channel - Context

**Gathered:** 2026-05-02
**Status:** Ready for planning

<domain>
## Phase Boundary

Operator without a password can log in by tapping a deep-link to the bot, pressing `/start`, receiving a 6-digit DM, and pasting it into admin-web — with all DM-blocked / wrong-code / expired-code edges handled deterministically. A separate `telegram-bot` Docker service runs `python -m app.workers.telegram_bot` long-polling against the python-telegram-bot 22 Application; its sole outbound surface is `app.integrations.telegram.sender.send_otp_dm` so TEST-03 can stub one function.

**Phase 7 ships:**

1. **Settings additions** in `app/core/config.py` — `telegram_bot_token: SecretStr`, `telegram_bot_username: str` (without `@`), `otp_deep_link_ttl_seconds: int = 600` (10 min, AUTH-TG-01), `otp_code_ttl_seconds: int = 300` (5 min, AUTH-TG-02), `otp_max_attempts: int = 5` (AUTH-TG-02). `.env.example` updated.

2. **Migration `0003_telegram_username.py`** — adds `users.telegram_username TEXT NULL UNIQUE` (lowercased on write, no leading `@`). Single small column addition; no other schema churn (Phase 5 D-02 already shipped `telegram_chat_id` nullable + `otp_codes` table in final shape).

3. **`app/modules/auth/telegram_service.py`** (NEW) — sibling of `service.py`. Owns:
   - `start_deep_link()` — generates `(raw_deep_link_token, deep_link_token_hash)` via Phase 4 `generate_deep_link_token` + sha256, inserts an `OtpCode { deep_link_token_hash, expires_at = now + 10min, code_hash = NULL, user_id = NULL, telegram_chat_id = NULL }`, returns `{deepLinkUrl, deepLinkToken}`.
   - `bind_and_issue(deep_link_token, telegram_chat_id, telegram_username)` — called by bot handler. Looks up OtpCode by hash; matches a `User WHERE lower(telegram_username) = ?` whose `telegram_chat_id IS NULL OR telegram_chat_id = ?`; sets `users.telegram_chat_id` if NULL; generates `(raw_code, code_hash)` via Phase 4 `generate_otp_code`; updates OtpCode with `{code_hash, user_id, telegram_chat_id, expires_at = now + 5min, attempts = 0}`. Returns the raw_code (caller passes to sender). Raises `TelegramUnknownAccount` (no User match) so handler can DM error and emit `event=telegram_unknown_start`.
   - `consume(deep_link_token, raw_code)` — called by `/auth/telegram/verify`. Looks up OtpCode; checks `consumed_at`, `expires_at`, `code_hash`, `attempts`; raises `BotNotStarted` / `OtpExpired` / `OtpInvalid` / `OtpMaxAttempts` / `OtpAlreadyConsumed` / `TokenUnknown` accordingly; on success stamps `consumed_at = now`, returns the bound `User`.
   - `get_status(deep_link_token) -> {bound: bool}` — reads OtpCode by hash; `bound` = `code_hash IS NOT NULL` (i.e., bot has DM'd the code).

4. **`app/integrations/telegram/`** filled in:
   - `bot.py` — builds `python-telegram-bot 22` `Application`, registers `/start` handler + a global error handler, exposes `build_application(token, handlers, sender)` factory that takes injected callables (no module-level side effects).
   - `handlers.py` — `start_handler(update, context, ctx: HandlerContext)` where `HandlerContext = NamedTuple(session_factory, telegram_service, sender)`. Handler runs in transaction: validates `/start <token>`, calls `telegram_service.bind_and_issue(...)`, on success calls `sender.send_otp_dm(chat_id, code)`, on send failure rolls back the bind/issue commit (or doesn't commit; see D-12). Localized DM strings live in `handlers.py`.
   - `sender.py` — `async def send_otp_dm(bot: telegram.Bot, chat_id: int, code: str) -> SendResult` returning `SendResult(ok: bool, blocked: bool, error: str | None)`. Wraps `bot.send_message(chat_id, f"Ваш код: {code}\nДействителен 5 минут.")`. Catches `telegram.error.Forbidden` / `BadRequest("chat not found")` and returns `SendResult(ok=False, blocked=True)`. Other errors return `SendResult(ok=False, blocked=False, error=str(e))`. THIS IS THE SOLE OUTBOUND BOUNDARY for TEST-03 stubbing.

5. **`app/workers/telegram_bot.py`** (replacing the placeholder) — `async def main()` opens `db_lifespan_manager()` + `redis_lifespan_manager()` (extracted reusable async context managers — D-08), instantiates `Bot(token=settings.telegram_bot_token.get_secret_value())`, builds `Application` with handlers wired to `telegram_service` + `sender` closures, runs `application.run_polling()`. `if __name__ == "__main__": asyncio.run(main())` at bottom (so `python -m app.workers.telegram_bot` works).

6. **`app/core/database.py` + `app/core/redis.py` refactor** — extract framework-agnostic `@asynccontextmanager async def db_lifespan_manager()` and `redis_lifespan_manager()` so both the FastAPI lifespan in `app/main.py` and the bot worker share one source of truth for engine/pool config. `app/main.py` becomes a thin adapter calling these.

7. **Auth router** `app/modules/auth/router.py` extended with three endpoints (TEST-07 exclusion list already accommodates these per Phase 6 D-04):
   - `POST /api/v1/auth/telegram/start` — unauthenticated; calls `telegram_service.start_deep_link()`; returns `{deepLinkUrl, deepLinkToken}`.
   - `GET /api/v1/auth/telegram/status?token=<deep_link_token>` — unauthenticated; calls `telegram_service.get_status()`; returns `{bound: bool}`.
   - `POST /api/v1/auth/telegram/verify` — unauthenticated; calls `telegram_service.consume()`; on success calls Phase 5 `issue_tokens(user)` + Phase 4 `issue_session_cookies(...)`; emits `event=otp_consumed` + `event=login_success {channel='telegram'}`. None of the three has `verify_csrf` per Phase 6 D-09.

8. **`docker-compose.yml`** (apps/backend) — adds a fourth service `telegram-bot` per INFRA-06:
   ```yaml
   telegram-bot:
     build: .
     command: python -m app.workers.telegram_bot
     env_file: .env
     environment:
       DATABASE_URL: postgresql+asyncpg://app:app@postgres:5432/sportzal
       REDIS_URL: redis://redis:6379/0
     restart: unless-stopped
     depends_on:
       migrate:
         condition: service_completed_successfully
       redis:
         condition: service_started
   ```

9. **`scripts/seed_demo_data.py`** extended — if `TELEGRAM_OWNER_USERNAME` is in env, after upserting the seeded owner User by email, idempotently set `telegram_username = lower(env_value)` if currently NULL or different. No-op when env var missing. Phase 5 already establishes the seed-script pattern.

10. **`importlinter` contract update** — the Phase 1 docstring convention "workers MUST NOT import app.modules.*" is explicitly relaxed for `app.workers.telegram_bot → app.modules.auth`. Added as a documented exception in `app.workers.__init__.py` and the Phase 7 PLAN narrative. `integrations⊥modules` contract is preserved (integrations/telegram/* never imports modules.auth).

11. **Tests** (TEST-03):
    - `tests/integration/auth/test_telegram_start.py` — `POST /auth/telegram/start` returns 200 with `{deepLinkUrl: "https://t.me/<bot>?start=<token>", deepLinkToken}`; OtpCode row created with `code_hash IS NULL`.
    - `tests/integration/auth/test_telegram_verify_happy.py` — full happy path: call /start → simulate bot bind via direct call to `telegram_service.bind_and_issue()` with stubbed `sender` → /verify with code → 200 + cookies + `otp_consumed` audit + `login_success` audit.
    - `tests/integration/auth/test_telegram_verify_errors.py` — parametrized: expired OTP (410 `otp_expired`), wrong code 4 times (401 `otp_invalid`), wrong code 5th time (429 `otp_max_attempts`), already-consumed (409 `otp_consumed`), unknown token (404 `token_unknown`), bot_not_started — code_hash IS NULL (409 `bot_not_started` carrying `fields.deepLinkUrl`).
    - `tests/integration/telegram/test_handler_start.py` — calls `start_handler` with hand-built fake `Update` objects + `stub_telegram_sender` fixture; asserts: known username + chat_id NULL → bind + DM called; unknown username → no DM, structlog `telegram_unknown_start`, OtpCode untouched; sender returns `blocked=True` → no code_hash written, structlog `telegram_dm_blocked`.

**In scope (Phase 7 REQ-IDs):** INFRA-06, AUTH-TG-01, AUTH-TG-02, AUTH-TG-03, AUTH-TG-04, AUTH-TG-05, AUTH-TG-06, TEST-03.

**Out of scope (deferred):**
- Telegram-only signup with nullable email/password_hash — explicitly rejected; bind-existing-only flow chosen (D-01).
- Admin-web "Bind Telegram" UI for self-service binding — Phase 10 / v1.2.
- Webhook-mode bot for production — v1.2 (AUTH-V12-04). Phase 7 ships long-polling only.
- Password reset via Telegram bot DM — v1.2 (AUTH-V12-02).
- ARQ job for DM retry — D-13 explicitly drops it; bot handler sends synchronously.
- Multi-OTP-per-user / cleanup of expired OtpCode rows — TTL expiry is the GC; periodic vacuum is a v1.2 ARQ job concern.
- Bot commands beyond `/start` (e.g., `/help`, `/unbind`) — out of scope; stranger contact gets a fixed Russian DM.

</domain>

<decisions>
## Implementation Decisions

### User upsert policy & first-bind UX

- **D-01 [LOCKED]:** **Bind-existing-only login.** TG OTP only LOGS IN users already created with email/password (seeded owner + future invites). AUTH-TG-04's "user is upserted matched by `telegram_chat_id`" is reinterpreted as "the User row's `telegram_chat_id` is upserted (set on first claim) onto an existing email/password User; no User row is ever created by the bot." This avoids the Phase 5 D-02 NOT NULL invariants on `email`/`password_hash`/`full_name` and skips the role-defaulting permission hole that auto-provisioning would create on a publicly reachable bot.

- **D-02 [LOCKED]:** **First-bind via bot self-claim by Telegram username.** Phase 7 adds migration `0003_telegram_username.py` introducing `users.telegram_username TEXT NULL UNIQUE` (stored as `lower(username)`, no leading `@`). On bot `/start <token>`, if `update.effective_user.username` (lowercased) matches a User whose `telegram_chat_id IS NULL`, the bot writes `users.telegram_chat_id = update.effective_chat.id` and proceeds with OTP issuance. No admin-web UI required for the binding step. Generalizes cleanly to multiple operators when v1.2 invites land.

- **D-03 [LOCKED]:** **Seed script extension.** `scripts/seed_demo_data.py` reads `TELEGRAM_OWNER_USERNAME` env var (optional). After upserting the seeded owner User by email, if env var is set, idempotently writes `telegram_username = lower(env_value)` (only if current value is NULL or different). Re-runs are safe. The seeded owner workflow becomes: set `OWNER_EMAIL` + `OWNER_PASSWORD` + `TELEGRAM_OWNER_USERNAME`, run `seed_demo_data.py`, message the bot once → bot binds chat_id and sends OTP for that /start. Done.

- **D-04 [LOCKED]:** **Stranger /start handler — DM error + leave OtpCode untouched + structlog warning.** When `/start <token>` arrives from a Telegram username with no matching User (or matching User already has a different `telegram_chat_id`), the bot:
  1. DMs the user a fixed Russian message: "Этот Telegram не привязан к аккаунту Sportzal. Обратитесь к администратору."
  2. Does NOT write `code_hash`, does NOT bind `telegram_chat_id`, does NOT touch the OtpCode row.
  3. Emits `structlog.event=telegram_unknown_start` `{username, chat_id, deep_link_token_hash}`.
  4. Subsequent `/auth/telegram/verify` for that token returns 409 `bot_not_started` (because `code_hash IS NULL`) carrying `fields.deepLinkUrl` — same code path as "user never pressed /start at all". No new error code needed; FE messaging stays single-branch.

### Bot worker architecture & layer boundaries

- **D-05 [LOCKED]:** **Three-layer split.** `app/integrations/telegram/*` = ptb wiring (no DB knowledge); `app/workers/telegram_bot.py` = process entry + lifespan + DI wiring; `app/modules/auth/telegram_service.py` = business logic + DB access. Handlers receive a `HandlerContext = NamedTuple(session_factory, telegram_service, sender)` closure constructed in `workers/telegram_bot.py`'s `main()`. `integrations/telegram/handlers.py` only knows the closure interface; it never imports `app.modules.auth` directly so `integrations ⊥ modules` import-linter contract stays GREEN.

- **D-06 [LOCKED]:** **Workers → modules.auth import is explicitly allowed (relaxed convention).** Phase 1's `app.workers.__init__.py` docstring "workers MUST NOT import app.modules.* directly" is updated to: "workers MAY import a single module's service layer (e.g., `app.modules.auth.telegram_service`) when the worker's sole purpose is that module's I/O fanout. Cross-module imports inside workers are still forbidden." Phase 7 PLAN narrative documents the deviation. No importlinter rule change needed (no contract currently enforces workers→modules).

- **D-07 [LOCKED]:** **`sender.send_otp_dm` is the SOLE outbound `Bot` boundary.** TEST-03's "stubbed integrations.telegram.sender" maps to a single function. Returns a typed `SendResult(ok: bool, blocked: bool, error: str | None)` instead of raising on transport failures. Bot handler code NEVER calls `bot.send_message` directly. Test fixture `stub_telegram_sender` in `tests/conftest.py` monkey-patches the function and exposes a `.calls` list + `.next_result` setter.

- **D-08 [LOCKED]:** **Reusable async-context managers for DB and Redis.** `app/core/database.py` exports `@asynccontextmanager async def db_lifespan_manager()` (yields after engine init, closes pool on exit). `app/core/redis.py` exports `redis_lifespan_manager()` analogously. `app/main.py`'s FastAPI lifespan becomes a thin adapter calling both. `app/workers/telegram_bot.py`'s `main()` opens both managers under `contextlib.AsyncExitStack` and runs the ptb Application inside. Engine/pool config drift between API and bot is impossible by construction.

- **D-09 [LOCKED]:** **Bot Application is built per-process, no module-level singletons.** `bot.py:build_application(token, handlers, sender)` is a factory; the `Application` instance lives in `workers/telegram_bot.py:main()`'s scope. No `app = Application.builder()...build()` at module level. Tests can build a fresh Application or skip the Application entirely (call handlers directly per D-15).

- **D-10 [LOCKED]:** **Bot username is a Settings value, not a `getMe()` call.** `telegram_bot_username: str` lives in `Settings`, env-driven. Deep-link URL is f-string `f"https://t.me/{settings.telegram_bot_username}?start={token}"`. Pros: offline-friendly tests, no API call on /start latency budget, deterministic openapi.json output. Cons: ops must keep env in sync if bot is recreated under a new username — acceptable for 1-2-user gym.

### OTP issuance timing & retry policy

- **D-11 [LOCKED]:** **Code generated AFTER successful DM, not before.** Flow:
  1. API `/auth/telegram/start` writes `OtpCode { deep_link_token_hash, expires_at = now+10min, code_hash = NULL, user_id = NULL, telegram_chat_id = NULL, attempts = 0 }`. Emits `event=telegram_deep_link_issued`.
  2. Bot `/start <token>` handler validates token → matches user by username → calls `telegram_service.bind_and_issue()` which generates `(raw_code, code_hash)` in-memory.
  3. Bot handler calls `sender.send_otp_dm(chat_id, raw_code)`. **No DB commit yet** for the OTP issuance.
  4. **If `SendResult.ok`:** in a single transaction, set `users.telegram_chat_id` if previously NULL, update OtpCode row with `{code_hash, user_id, telegram_chat_id, expires_at = now+5min, attempts = 0}`, commit. Emit `event=otp_issued {user_id, chat_id}`.
  5. **If `SendResult.ok = False, blocked = True`:** rollback. Emit `event=telegram_dm_blocked {chat_id}`. OtpCode keeps `code_hash IS NULL`. `/auth/telegram/verify` will return 409 `bot_not_started`. No retry.
  6. **If `SendResult.ok = False, blocked = False`** (transient network): rollback. Emit `event=telegram_dm_failed {chat_id, error}`. Same outcome as blocked from FE perspective — user can re-press the deep-link. No automatic retry in Phase 7.

  Atomicity guarantee: a code is valid (code_hash present in DB) ONLY after the user has actually received the raw code via DM. No orphan codes.

- **D-12 [LOCKED]:** **No ARQ retry job for DM send.** AUTH-TG-05's "send-OTP retry" via ARQ is reinterpreted as "reserved for future SMS/email channels." Phase 7 sends synchronously inside the ptb handler coroutine (ptb already runs handlers in asyncio). Pros: zero new ARQ task code, no Redis-stored raw-code window, no ARQ→Bot client duplication. Cons: a transient network hiccup forces the user to re-press the deep-link — acceptable for 1-2-user gym; revisit if ops data shows >5% transient DM failure rate.

- **D-13 [LOCKED]:** **Verify endpoint distinct error codes per failure mode.** `/auth/telegram/verify` returns the standard `AppError` envelope `{code, message, fields?}`:
  | Failure | HTTP | code | fields |
  |---|---|---|---|
  | OtpCode found, `code_hash IS NULL` | 409 | `bot_not_started` | `{deepLinkUrl}` |
  | `expires_at < now` | 410 | `otp_expired` | — |
  | code_hash mismatch, `attempts < 5` (after increment) | 401 | `otp_invalid` | `{attemptsRemaining}` |
  | code_hash mismatch, `attempts >= 5` after this miss | 429 | `otp_max_attempts` | — |
  | `consumed_at IS NOT NULL` (replay) | 409 | `otp_consumed` | — |
  | `deep_link_token_hash` not found | 404 | `token_unknown` | — |

  All implemented as `AppError` subclasses in `app/modules/auth/exceptions.py` (or `app/core/exceptions.py` if narrowly module-local — planner's call). Each failure is a distinct exception class so structlog events can pick them up via class name.

- **D-14 [LOCKED]:** **Successful verify: same cookie issuance + audit shape as Phase 5 email/password login.**
  1. `telegram_service.consume()` returns the bound `User`.
  2. Router calls Phase 5 `issue_tokens(user)` (mints access JWT + refresh + family_id + Redis session) and Phase 4 `issue_session_cookies(response, ...)` (sets `sz_access`, `sz_refresh`, `sportzal_csrf` cookies).
  3. Emit `event=otp_consumed {user_id}` and `event=login_success {user_id, channel='telegram'}`. The shared `login_success` event with a `channel` field is the Phase 8 audit_log latch point. Phase 5's email/password login is updated to add `channel='email_password'` (one-line update; not a breaking change because no consumer reads `channel` yet).
  4. Response body mirrors `/auth/login`: `{user: {id, role, fullName}}`.

### Testing strategy (TEST-03)

- **D-15 (Discretion):** **Handler tests run handler functions directly with hand-built `Update` objects + stubbed sender.** No `Application.run_polling()` in tests, no live ptb event loop, no real Bot client. `tests/integration/telegram/test_handler_start.py` constructs `Update`/`Message`/`User`/`Chat` objects with the minimum fields the handler reads, builds a `Context` with stubbed sender + real db_session, awaits `start_handler(update, context, ctx)`, asserts on `stub_telegram_sender.calls` + DB state. ptb 22's testing surface is in flux; calling our handler directly is stable and fast.

- **D-16 (Discretion):** **TEST-03 "stub `integrations.telegram.sender`" implemented as a pytest fixture in `tests/conftest.py`.** The fixture monkeypatches `app.integrations.telegram.sender.send_otp_dm` to a recorder. All Phase 7 tests that touch the bot path consume this fixture; the bot worker process is never started in tests. API-level tests that need to simulate "the bot ran /start" call `telegram_service.bind_and_issue()` directly under the same db_session SAVEPOINT.

- **D-17 (Discretion):** **No bot worker process tests.** The `python -m app.workers.telegram_bot` entry point is exercised only by `docker compose up` smoke (manual). Its body is ~30 LOC — DB lifespan + Redis lifespan + Application build + run_polling — and each piece is tested separately (lifespans by Phase 5 fixtures, handlers by D-15 tests). A dedicated entry-point test would mock half the standard library to land.

### Migration strategy

- **D-18 [LOCKED]:** **Single migration `0003_telegram_username.py`** — adds nullable unique `users.telegram_username TEXT`. No data backfill in the migration body (seed script handles it). Migration name follows the Phase 4 D-19 naming convention. `alembic upgrade head` on a fresh DB after Phase 7 produces a clean autogenerate diff (TEST-08 still GREEN).

### Status polling endpoint

- **D-19 (Discretion):** **`GET /auth/telegram/status?token=<deep_link_token>` returns `{bound: bool}` only.** No deep-link-expired/consumed/unknown distinction here — the status endpoint is for the FE to know "may I prompt for the code now?". Polling cadence is a FE concern (Phase 10); server enforces no rate limit in Phase 7 (the deep-link token is opaque + 10-min TTL + bound to one OtpCode row, so polling is harmless). If `token` doesn't match any OtpCode, return `{bound: false}` (don't leak token validity); if `expires_at < now`, also `{bound: false}` (FE will see token-expired on /verify).

- **D-20 (Discretion):** **Deep-link tokens are single-use.** `consumed_at IS NOT NULL` means the token is dead; subsequent `/start` from the bot (e.g., user opens deep-link in a second device) finds the row and treats it as "expired" — DMs "Этот код уже использован, запросите новый." and emits `event=telegram_replay_attempt`. The OtpCode is not deleted (audit trail).

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Project specs
- `CLAUDE.md` — backend stack lock (Python 3.12 + uv + FastAPI + SQLAlchemy 2.0 async + Pydantic v2 + Postgres 16 + Redis 7 + structlog), `httpx ASGITransport` + `pytest-asyncio` testing rule, RU-locale strings.
- `apps/admin-web/CLAUDE.md` — frontend integration-side reference (Phase 10 will consume `/auth/telegram/*`); Phase 7 does NOT touch FE.
- `.planning/PROJECT.md` — milestone scope; "Telegram как первичный канал" (RU/CIS regional constraint); `core ⊥ modules` invariant.
- `.planning/REQUIREMENTS.md` — Phase 7 owns these REQ-IDs (every plan task must trace): `INFRA-06`, `AUTH-TG-01`, `AUTH-TG-02`, `AUTH-TG-03`, `AUTH-TG-04`, `AUTH-TG-05`, `AUTH-TG-06`, `TEST-03`.
- `.planning/ROADMAP.md` Phase 7 section — goal (deep-link → /start → 6-digit DM → paste flow with all edges) + four success criteria (deep-link endpoint shape; bot bind + DM + verify happy path; 409 `bot_not_started` carrying deep-link URL; fourth `telegram-bot` docker-compose service).

### Cross-phase context (load-bearing)
- `.planning/phases/04-auth-foundations-cookie-rbac-primitives/04-CONTEXT.md` — D-25 (`issue_session_cookies` reused verbatim on /verify success), D-26 (`generate_csrf_token` regenerated on OTP-verify per Phase 4), security helper inventory (`generate_otp_code`, `generate_deep_link_token`).
- `.planning/phases/05-user-schema-email-password-auth/05-CONTEXT.md` — D-02 (Phase 5 left `password_hash`/`email`/`full_name` NOT NULL and explicitly tagged Phase 7 to handle the relaxation IF Telegram-only signup were chosen — D-01 here declines that), D-03 (`OtpCode` final shape is already shipped; no schema churn in Phase 7), D-08 (Redis lifespan to be reused by D-08 here), D-15 (`register_user_loader` already wired — Phase 7 reuses), D-21 (audit `emit` helper + locked event names; Phase 7 adds `telegram_deep_link_issued` / `otp_issued` / `otp_consumed` / `telegram_unknown_start` / `telegram_dm_blocked` / `telegram_dm_failed` / `telegram_replay_attempt` / `login_success {channel}`).
- `.planning/phases/06-rbac-wiring-parity-tests/06-CONTEXT.md` — D-04 (`/api/v1/auth/telegram/*` is in TEST-07 exclusion list — three new routes land without introspection-test changes), D-09 (no `verify_csrf` on telegram routes — by omission, exempt list).

### Source files Phase 7 directly reads or mutates
- `apps/backend/app/core/config.py` — extend `Settings` with `telegram_bot_token` (SecretStr), `telegram_bot_username`, `otp_deep_link_ttl_seconds`, `otp_code_ttl_seconds`, `otp_max_attempts` (D-10).
- `apps/backend/.env.example` — add the five env vars + `TELEGRAM_OWNER_USERNAME` (consumed by seed script per D-03).
- `apps/backend/app/core/database.py` — extract `db_lifespan_manager()` async context manager (D-08).
- `apps/backend/app/core/redis.py` — extract `redis_lifespan_manager()` async context manager (D-08).
- `apps/backend/app/main.py` — refactor FastAPI lifespan to call the new managers; no behavioral change (D-08).
- `apps/backend/alembic/versions/0003_telegram_username.py` — NEW. `users.telegram_username TEXT NULL UNIQUE`, lowercased on write convention (D-02, D-18).
- `apps/backend/app/modules/auth/models.py` — add `User.telegram_username: Mapped[str | None]` column (D-02).
- `apps/backend/app/modules/auth/telegram_service.py` — NEW. `start_deep_link()` / `bind_and_issue()` / `consume()` / `get_status()` (D-05, D-11, D-13, D-14).
- `apps/backend/app/modules/auth/exceptions.py` — NEW (or extend existing). Subclasses for the 6 verify failure modes per D-13.
- `apps/backend/app/modules/auth/router.py` — add `POST /auth/telegram/start`, `GET /auth/telegram/status`, `POST /auth/telegram/verify` (D-13, D-14, D-19).
- `apps/backend/app/modules/auth/schemas.py` — add `TelegramStartResponse`, `TelegramStatusResponse`, `TelegramVerifyRequest` (extend Phase 4 contract bases).
- `apps/backend/app/modules/auth/service.py` — extend `login_success` audit emit to add `channel='email_password'` (D-14).
- `apps/backend/app/integrations/telegram/__init__.py` — replace placeholder docstring; no business code.
- `apps/backend/app/integrations/telegram/bot.py` — `build_application(token, handlers, sender) -> Application` factory (D-05, D-09).
- `apps/backend/app/integrations/telegram/handlers.py` — `start_handler(update, context, ctx: HandlerContext)` (D-04, D-05, D-11).
- `apps/backend/app/integrations/telegram/sender.py` — `async def send_otp_dm(bot, chat_id, code) -> SendResult` (D-07).
- `apps/backend/app/workers/__init__.py` — update docstring to document the workers→modules.auth relaxation (D-06).
- `apps/backend/app/workers/telegram_bot.py` — replace placeholder with `async def main()` + `if __name__ == "__main__":` entry (D-08, D-09).
- `apps/backend/docker-compose.yml` — add `telegram-bot` service (INFRA-06).
- `apps/backend/scripts/seed_demo_data.py` — extend to read `TELEGRAM_OWNER_USERNAME` env (D-03).
- `apps/backend/tests/conftest.py` — add `stub_telegram_sender` fixture (D-16).
- `apps/backend/tests/integration/auth/test_telegram_start.py` — NEW.
- `apps/backend/tests/integration/auth/test_telegram_verify_happy.py` — NEW.
- `apps/backend/tests/integration/auth/test_telegram_verify_errors.py` — NEW (parametrized over D-13 failure modes).
- `apps/backend/tests/integration/telegram/__init__.py` — NEW. Empty.
- `apps/backend/tests/integration/telegram/test_handler_start.py` — NEW (D-15, D-16).

### External docs (consulted)
- python-telegram-bot v22 docs — `Application` builder, long-polling `run_polling()`, `Update`/`Message`/`User`/`Chat` types, `telegram.error.Forbidden` / `BadRequest` exception classes (used in `sender.py` to detect blocked DM per D-07).
- Telegram Bot API §5.1 (deep-linking) — `https://t.me/<bot>?start=<param>` syntax; `<param>` is `[a-zA-Z0-9_-]{1,64}` which `secrets.token_urlsafe(32)` (43 chars) satisfies (D-10).
- python-telegram-bot v22 examples / migration notes (consulted by planner) — async-only API, no v13-style `Updater` shim, `Application.run_polling()` is the canonical entry.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets (Phase 4/5/6 outputs Phase 7 consumes verbatim)
- `app/core/security.py:generate_otp_code` — Phase 4 helper returning `(raw_6_digit, sha256_hex)`. Phase 7 calls inside `telegram_service.bind_and_issue` (D-11).
- `app/core/security.py:generate_deep_link_token` — Phase 4 helper. Phase 7 calls in `telegram_service.start_deep_link` (D-11 step 1).
- `app/core/security.py:_sha256_hex` (or equivalent) — used to hash the raw deep-link token before persisting (`deep_link_token_hash`).
- `app/core/security.py:issue_session_cookies` — Phase 4 helper. Verify endpoint reuses on success (D-14).
- `app/core/security.py:encode_access_token` / `generate_refresh_token` / `generate_csrf_token` — all consumed via Phase 5 `issue_tokens(user)` flow.
- `app/core/audit.py:emit` — Phase 5 structlog helper. Phase 7 emits new event names (D-04, D-11, D-14, D-20).
- `app/modules/auth/models.py:User` — extended with `telegram_username` column (D-02). `telegram_chat_id` already exists (Phase 5 D-02).
- `app/modules/auth/models.py:OtpCode` — final shape from Phase 5 D-03 (`deep_link_token_hash`, `code_hash NULL`, `expires_at`, `attempts`, `consumed_at`, `user_id NULL`, `telegram_chat_id NULL`). Phase 7 writes app code only against this schema.
- `app/modules/auth/service.py:issue_tokens` — Phase 5 helper. Verify endpoint calls on success (D-14).
- `app/modules/auth/service.py:authenticate` — Phase 5 helper for email/password. Reused only as a pattern reference (Phase 7 doesn't call it directly).
- `app/core/dependencies.py:require_authenticated` — Phase 6 D-01. Telegram routes do NOT use it (all three are in the exclusion list per Phase 6 D-04).
- `app/core/exceptions.py:AppError` — Phase 7's verify error subclasses (D-13) extend this; the Phase 2 D-12 `_app_error_handler` emits the right `{code, message, fields}` shape.
- `tests/conftest.py:db_session` (Phase 5 D-22 SAVEPOINT) — Phase 7 telegram tests reuse.
- `pyproject.toml` — `python-telegram-bot>=22.7,<23` already pinned in Phase 4 D-01 (INFRA-07). No new pyproject change needed.

### Established patterns to honor
- **Factory pattern, no module-level `app`** (Phase 2 main.py docstring) — `build_application` in `bot.py` is a factory; the live `Application` instance lives in worker `main()` (D-09).
- **`integrations ⊥ modules`** (importlinter `integrations-not-depend-on-modules` contract) — `app/integrations/telegram/*` MUST NOT import `app.modules.auth`. Handlers receive injected callables, never import the service directly (D-05).
- **`core ⊥ modules`** (importlinter `core-not-depend-on-modules`) — `app/core/database.py` and `app/core/redis.py` lifespan managers MUST NOT import any auth/telegram code (D-08).
- **Per-route `dependencies=[...]` for cross-cutting checks** (Phase 5/6 router pattern) — `/auth/telegram/*` routes declare NO `verify_csrf` dependency (Phase 6 D-09 exempt list).
- **AppError → JSONResponse handler** (Phase 2 D-12) — Phase 7 verify error classes ride this path (D-13).
- **SAVEPOINT-rolled `db_session`** (Phase 5 D-22) — telegram tests seed users and OtpCode rows inside the rolled-back transaction.
- **Russian-narrative + English-code docs style** (Phase 3 D-05) — PLAN.md / SUMMARY.md narrative in Russian, code in English; bot DM strings are Russian (D-04).
- **Audit emit + locked event names** (Phase 5 D-21) — every new event named in this CONTEXT becomes a Phase 8 audit_log latch point.

### Integration points
- **Phase 5 (already shipped) — Phase 7 reuses `issue_tokens(user)` + cookie issuance for the verify success path.** No retroactive change to Phase 5 routes; only `service.login_success` event gains a `channel` kwarg per D-14 (one-line, additive).
- **Phase 6 (already shipped) — `/auth/telegram/start|status|verify` are pre-listed in TEST-07's exclusion (D-04 there).** The route-introspection test continues to pass without edits when Phase 7 mounts the routes. No `verify_csrf` per Phase 6 D-09.
- **Phase 8 (Clients + Audit Log)** — `audit_log` DB table will write rows for every event Phase 7 emits via `app.core.audit.emit` (D-04, D-11, D-14, D-20). No Phase 7 change needed when Phase 8 lands; the emit names are LOCKED.
- **Phase 9 (OpenAPI export)** — adds `/auth/telegram/start|status|verify` request/response shapes to `openapi.json`. Phase 7 declares these via Pydantic schemas (`TelegramStartResponse` etc.) so Phase 9 codegen picks them up automatically.
- **Phase 10 (admin-web wiring)** — consumes `/auth/telegram/*` via `packages/api-client`. Phase 7 must produce response/error shapes that match the FE design contract (FE-02 says "the Telegram tab polls the status endpoint and prompts for the code once the chat is bound").

</code_context>

<specifics>
## Specific Ideas

- **The bot's outbound DM uses Russian copy.** Code message: "Ваш код: {code}\nДействителен 5 минут." Stranger error: "Этот Telegram не привязан к аккаунту Sportzal. Обратитесь к администратору." Replay attempt: "Этот код уже использован, запросите новый." All three are constants in `handlers.py`. No i18n framework in the bot — single-language by design (PROJECT.md RU/CIS).

- **The fourth docker-compose service is `telegram-bot`, not `bot` or `telegram`.** Naming is verbose-explicit so `docker compose logs telegram-bot` is unambiguous and the service can't be confused with a future SMS-channel worker.

- **`SendResult` dataclass with explicit `blocked: bool` is the architectural choice.** Don't conflate "user blocked the bot" with "transient network error" — the first means "give up, FE shows deep-link again," the second is the same outcome but observable via different structlog event names. Future ARQ retry (post-Phase-7) only retries the latter.

- **`code_hash IS NULL` is the load-bearing invariant for `bot_not_started`.** Don't add a parallel `OtpCode.status` enum or boolean — the NULL in `code_hash` is the single source of truth for "OTP not issued yet." `expires_at` covers the expiry case. `consumed_at` covers the replay case. Three NULL/timestamp columns, no enum.

- **Telegram username lookup is exact-match after lowercasing.** No fuzzy matching, no leading `@` tolerance in the column (callers strip `@` before write). If a user changes their Telegram username, owner re-runs the seed script with the new env value (or a future v1.2 admin UI handles it).

- **Bot worker is a separate process, not an in-API background task.** INFRA-06 is explicit. This protects API uvicorn workers from ptb's polling loop and lets us scale/restart the bot independently. `restart: unless-stopped` per the requirement.

- **`workers → modules.auth` is the ONLY relaxation of the workers convention.** D-06 is narrowly scoped: workers may import a single owning module's service layer when the worker IS that module's I/O fanout. Cross-module imports inside a worker (e.g., a worker importing both `modules.auth` and `modules.clients`) remain forbidden — those need an events bus, which is v1.2+ territory.

- **No bot commands beyond `/start <token>`.** No `/help`, no `/unbind`, no `/status`. Stranger contact gets the fixed Russian DM and structlog event; bot interaction outside `/start` is silently logged at debug level and otherwise ignored. Keeps the bot's surface minimal.

- **Atomic-after-DM pattern (D-11) is the chosen tradeoff over write-then-send.** A pre-DM-write design (option B in the discussion) is simpler retry-wise but creates orphan codes that the user never received — worse audit story. The user picked the atomic-after pattern explicitly.

</specifics>

<deferred>
## Deferred Ideas

- **Telegram-only signup with auto-provisioned User rows** — explicitly rejected in Phase 7 (D-01). Revisit only if multi-operator invitations need a self-service onboarding path that doesn't go through email; would require migration to nullable `email`/`password_hash`/`full_name` + a role-defaulting policy.

- **Admin-web "Bind Telegram" UI** for self-service binding (an existing logged-in user binds their Telegram from a profile page) — Phase 10 / v1.2. Would require an authenticated variant of `/auth/telegram/start` that pre-populates `OtpCode.user_id` from the current session, plus a TG tab in profile settings.

- **`telegram_username` column rename / migration** if a user changes their Telegram handle — v1.2 admin UI. Phase 7 covers it via re-running `seed_demo_data.py` with the updated env var.

- **Webhook-mode bot for production** — v1.2 (AUTH-V12-04). Phase 7 ships long-polling only. Webhook needs public HTTPS + nginx routing; out of scope for docker-compose-only dev.

- **Password reset via Telegram bot DM** — v1.2 (AUTH-V12-02). Different flow (proves identity via TG, then prompts new password). Phase 7 only does login.

- **ARQ job for DM retry** — D-12 explicitly drops it; bot handler sends synchronously. Revisit if production telemetry shows >5% transient DM failure rate.

- **Bot commands beyond `/start`** (`/help`, `/unbind`, `/whoami`, `/status`) — out of scope. Each adds attack surface and copy complexity. Add only when a concrete user need lands in v1.2.

- **Periodic cleanup of expired OtpCode rows** — TTL-based GC suffices for Phase 7 (`expires_at` filter at read time). A periodic ARQ vacuum job is v1.2.

- **`Bot.get_me()` username discovery** — D-10 picks env-var Settings instead. If we ever rotate the bot to a new username and forget to update env, deep-link URLs break silently. A `get_me()` self-check at lifespan startup (warn-only) is a small follow-up improvement; deferred.

- **Audit log DB rows** for `telegram_*` events — Phase 8 (INFRA-04, AUDIT-01..03) adds the DB writer; Phase 7 emits structlog events with locked names so the swap-in is mechanical.

- **Per-IP rate limit on `/auth/telegram/start`** — v1.2. The endpoint is unauthenticated and an attacker can mint deep-links endlessly, but each one is a single OtpCode row and a 10-min TTL. Aggregate cost is bounded; rate-limit is a noisy-neighbor mitigation.

- **HMAC-bound deep-link tokens** — v2+. Current 32-byte URL-safe tokens (Phase 4 D-26-style entropy) + sha256 storage are sufficient at gym scale.

- **Multi-OTP-per-user concurrent** — current shape allows one active OtpCode per `(user, deep_link_token)`; if a user clicks /start twice in two devices, the second `/start <token>` finds a `consumed_at IS NOT NULL` (D-20) and the bot DMs "уже использован." A "newest token wins" policy is a v1.2 ergonomics improvement.

- **Active-sessions UI / per-session revoke** — v1.2 (AUTH-V12-01). Telegram-channel sessions appear alongside email/password sessions via the shared `family_id` + `channel` audit field.

- **Telegram Login Widget** — out of scope (RU regional constraint requires public HTTPS; bot deep-link works in docker-compose dev without ngrok).

</deferred>

---

*Phase: 07-telegram-otp-channel*
*Context gathered: 2026-05-02*
