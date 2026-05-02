# Phase 7: Telegram OTP Channel - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-02
**Phase:** 07-telegram-otp-channel
**Areas discussed:** User upsert policy, Bot worker architecture & layer boundaries, OTP issuance timing
**Areas skipped:** TEST-03 testing surface (resolved via Claude discretion in CONTEXT.md D-15..D-17)

---

## Gray-Area Selection

| Option | Description | Selected |
|--------|-------------|----------|
| User upsert policy | Phase 5 D-02 left a migration on Phase 7's plate if Telegram-only signup is desired | ✓ |
| Bot worker architecture & layer boundaries | INFRA-06 fourth service + importlinter implications | ✓ |
| OTP issuance timing | Whose responsibility is it to write `code_hash` to OtpCode? | ✓ |
| TEST-03 test surface for the bot worker | How to test handlers without a live ptb runtime |  |

**Selected by user:** Bot worker architecture, OTP issuance timing, User upsert policy

---

## User upsert policy

| Option | Description | Selected |
|--------|-------------|----------|
| Bind-existing only — no migration | TG OTP only logs in users already created with email/password; bot rejects unknown chat_id; AUTH-TG-04 'upsert' reinterpreted as 'upsert telegram_chat_id onto an existing user' | ✓ |
| Pure upsert + migration to nullable email/password_hash/full_name | Faithful to AUTH-TG-04 wording; bot creates Users on first /start with role=reception default | |
| Pure upsert with telegram-username allowlist (env var) | Same migration as option 2, but bot only auto-creates allowlisted usernames | |

**User's choice:** Bind-existing only.
**Rationale:** 1-2-user gym; owner already has email/password from seed; auto-provisioning a public bot is a permission-policy hole.

---

## First-bind UX (sub-question of upsert)

| Option | Description | Selected |
|--------|-------------|----------|
| Bot self-claim via TELEGRAM_OWNER_USERNAME env var | Seed script writes username; bot binds chat_id on first /start of that username | ✓ |
| Manual DB seed with explicit chat_id env var | Owner has to discover their numeric chat_id via @userinfobot | |
| Defer binding to Phase 10 — Phase 7 ships login flow only | Phase 7 unusable end-to-end until Phase 10 lands | |

**User's choice:** Bot self-claim via username env var.

---

## Claim model (sub-question of upsert)

| Option | Description | Selected |
|--------|-------------|----------|
| Per-user `telegram_username` column + claim if matches | Migration adds nullable unique column; generalizes to multiple operators | ✓ |
| Env-var allowlist of `username:email` pairs | No schema migration; claim policy lives in env config | |
| Single-owner shortcut: TELEGRAM_OWNER_USERNAME claims THE owner row | No new column; hard-wired to one owner | |

**User's choice:** Per-user `telegram_username` column. Drives migration `0003_telegram_username.py` (D-02, D-18).

---

## Migration & seed-script behavior (sub-question of upsert)

| Option | Description | Selected |
|--------|-------------|----------|
| Seed script idempotent: backfills owner row if env var set | `seed_demo_data.py` reads `TELEGRAM_OWNER_USERNAME`; idempotent on rerun | ✓ |
| Migration only + manual ops | Migration adds column; operator inserts via psql | |

**User's choice:** Seed script extension (D-03).

---

## Stranger /start handler behavior

| Option | Description | Selected |
|--------|-------------|----------|
| DM error + leave OtpCode untouched + structlog warning | code_hash stays NULL → /verify returns 409 `bot_not_started` (same path as 'never started') | ✓ |
| Distinct API error code `unknown_telegram` separate from `bot_not_started` | Needs sentinel column or extra OtpCode state | |
| Drop the deep-link token + force restart | Bot deletes OtpCode; /verify returns 404 | |

**User's choice:** Reuse `bot_not_started` (D-04). Single FE branch.

---

## Bot worker logic placement

| Option | Description | Selected |
|--------|-------------|----------|
| New `app/modules/auth/telegram_service.py` + workers calls it | Bind/issue/upsert in auth module; relax workers→modules.auth convention | ✓ |
| Raw ORM in `app/workers/telegram_bot.py` | Bot writes its own SQL/ORM; preserves convention; duplicates patterns | |
| HTTP callback: bot calls back into FastAPI | Strictest isolation; extra moving part, internal HTTP surface | |

**User's choice:** Three-layer split with relaxed workers→modules.auth import (D-05, D-06).

---

## DB / Redis lifecycle for the bot worker

| Option | Description | Selected |
|--------|-------------|----------|
| Standalone async-context manager extracted from `app/core/database.py` + `app/core/redis.py` | Reusable `db_lifespan_manager()` / `redis_lifespan_manager()`; FastAPI lifespan becomes thin adapter | ✓ |
| Bot creates its own engine/sessionmaker inline | Engine config drift between API and bot | |
| Embed bot inside FastAPI lifespan as a background task | Contradicts INFRA-06 (fourth Docker service) | |

**User's choice:** Reusable async context managers (D-08).

---

## Bot module placement

| Option | Description | Selected |
|--------|-------------|----------|
| Split: integrations/telegram/* = ptb wiring; workers/telegram_bot.py = entry+lifespan; modules/auth/telegram_service.py = business logic | Three-layer split; clean test seams; integrations⊥modules preserved | ✓ |
| All in workers/telegram_bot.py | Single file ~150 LOC; harder to test handlers in isolation | |
| Everything in integrations/telegram/ | Integrations layer would own DB/Redis lifecycle | |

**User's choice:** Three-layer split (D-05).

---

## Sender stub seam (TEST-03)

| Option | Description | Selected |
|--------|-------------|----------|
| `integrations/telegram/sender.py` is the SOLE outbound boundary; tests stub it | Single function `send_otp_dm` returning typed `SendResult`; ptb `Bot.send_message` never called outside this file | ✓ |
| Stub the entire `Bot` instance via ptb's `tg.ext.testing` helpers | Heavier setup; ptb 22 testing surface in flux | |

**User's choice:** Sender as sole boundary (D-07).

---

## OTP issuance timing

| Option | Description | Selected |
|--------|-------------|----------|
| At bot /start handler — code generated AFTER DM sender succeeds | code_hash written only after user confirmed-received DM; no orphan codes | ✓ |
| At bot /start handler — code generated BEFORE DM sender | Simpler retry semantics; possible orphan code_hash if DM fails | |
| At API /auth/telegram/start | Raw code lives in Redis before user proves chat ownership | |

**User's choice:** Atomic-after-DM (D-11).

---

## ARQ retry policy

| Option | Description | Selected |
|--------|-------------|----------|
| Skip ARQ retry entirely — direct synchronous DM in bot handler | Reinterpret AUTH-TG-05 'send-OTP retry' as 'reserved for future SMS/email channels' | ✓ |
| ARQ enqueue for the DM send | Doubles moving parts; raw code lives in two places | |
| Synchronous send + ARQ job for failure ALERTING only | Premature observability for 1-2-user gym | |

**User's choice:** Skip ARQ retry (D-12).

---

## Verify endpoint error codes

| Option | Description | Selected |
|--------|-------------|----------|
| Distinct codes per failure mode | `bot_not_started` / `otp_expired` / `otp_invalid` / `otp_max_attempts` / `otp_consumed` / `token_unknown` | ✓ |
| Single `otp_invalid` code with sub-message | FE has to parse message strings | |

**User's choice:** Distinct codes (D-13).

---

## Verify success — audit emit names

| Option | Description | Selected |
|--------|-------------|----------|
| Distinct event names: otp_issued, otp_consumed, telegram_login_success | login_success carries `channel='telegram'` (or `'email_password'`); shared with Phase 5 | ✓ |
| One unified login_success event | Drops the issued/consumed observability ratio | |

**User's choice:** Distinct names + `channel` field (D-14).

---

## Claude's Discretion

The user explicitly said "I'm ready for context" before exhausting derivative gray areas. Claude resolved the following in CONTEXT.md without further questions:

- **D-15:** Handler tests run handler functions directly with hand-built `Update` objects. No live ptb event loop in tests.
- **D-16:** `stub_telegram_sender` pytest fixture in `tests/conftest.py`; bot worker process never started in tests.
- **D-17:** No bot worker entry-point tests; ~30 LOC of lifespan + Application build is exercised only by `docker compose up` smoke.
- **D-19:** `/auth/telegram/status` returns `{bound: bool}` only — no rate limit in Phase 7; FE polling cadence is a Phase 10 concern.
- **D-20:** Deep-link tokens are single-use (`consumed_at IS NOT NULL`); replay attempts get a fixed Russian DM and `event=telegram_replay_attempt`.

## Deferred Ideas

Captured in CONTEXT.md `<deferred>` section. Highlights:

- Telegram-only signup with auto-provisioned User rows (rejected, not deferred).
- Admin-web "Bind Telegram" UI (Phase 10 / v1.2).
- Webhook-mode bot for production (v1.2 — AUTH-V12-04).
- Password reset via Telegram (v1.2 — AUTH-V12-02).
- ARQ job for DM retry (revisit if telemetry shows >5% transient failures).
- Bot commands beyond `/start` (`/help`, `/unbind`, `/whoami`).
- Periodic cleanup of expired OtpCode rows (v1.2 ARQ vacuum).
- `Bot.get_me()` username discovery as self-check at lifespan startup.
- Per-IP rate limit on `/auth/telegram/start` (v1.2).
- HMAC-bound deep-link tokens (v2+).
- Active-sessions UI with channel field (v1.2 — AUTH-V12-01).
