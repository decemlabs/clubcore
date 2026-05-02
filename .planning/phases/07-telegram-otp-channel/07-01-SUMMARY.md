---
phase: 07-telegram-otp-channel
plan: 01
subsystem: infra

tags: [pydantic-settings, secretstr, asynccontextmanager, sqlalchemy-async, redis-asyncio, fastapi-lifespan, importlinter]

requires:
  - phase: 04-auth-foundations-cookie-rbac-primitives
    provides: Settings base shape (SecretStr / TTL fields convention)
  - phase: 05-user-schema-email-password-auth
    provides: db_lifespan + redis_lifespan FastAPI integration shape (now refactored)

provides:
  - Five new Settings fields for Telegram OTP channel (telegram_bot_token, telegram_bot_username, otp_deep_link_ttl_seconds=600, otp_code_ttl_seconds=300, otp_max_attempts=5)
  - Six documented env vars in .env.example (5 Telegram OTP + 1 optional TELEGRAM_OWNER_USERNAME for seed script)
  - app.core.database.db_lifespan_manager() — framework-agnostic async-context manager yielding (engine, sessionmaker)
  - app.core.redis.redis_lifespan_manager() — framework-agnostic async-context manager yielding Redis client
  - db_lifespan(app) / redis_lifespan(app) preserved as thin FastAPI adapters (back-compat for app.state.engine / app.state.sessionmaker / app.state.redis readers)

affects: [07-04 telegram_service (reads new TTLs/secrets), 07-07 worker entry (opens both managers under AsyncExitStack), 07 verify route (uses telegram_bot_username for deep-link URL)]

tech-stack:
  added: []
  patterns:
    - "Two-tier lifespan: framework-agnostic *_manager() yields resource(s); FastAPI adapter wraps and writes to app.state"
    - "SecretStr for new Telegram bot token (mirrors existing secret_key convention)"

key-files:
  created: []
  modified:
    - apps/backend/app/core/config.py
    - apps/backend/.env.example
    - apps/backend/app/core/database.py
    - apps/backend/app/core/redis.py
    - apps/backend/app/main.py

key-decisions:
  - "D-08 implementation: db_lifespan_manager() yields tuple (engine, sessionmaker); redis_lifespan_manager() yields Redis client. FastAPI adapters wrap them — back-compat preserved."
  - "D-10 implementation: telegram_bot_username stored as Settings str (no leading @); telegram_bot_token as SecretStr."

patterns-established:
  - "Reusable lifespan manager pattern: any future worker process opens app.core.* managers via async with — no FastAPI app.state coupling required"
  - "core ⊥ modules invariant survives the refactor (importlinter `core-not-depend-on-modules` KEPT)"

requirements-completed: [INFRA-06, AUTH-TG-01, AUTH-TG-02]

duration: ~6min
completed: 2026-05-02
---

# Phase 7 Plan 01: Settings + Reusable Lifespan Managers Summary

**Five Telegram OTP Settings fields landed and `db_lifespan` / `redis_lifespan` split into framework-agnostic managers + thin FastAPI adapters — bot worker (07-07) can now share engine/pool config without app.state coupling.**

## Performance

- **Duration:** ~6 min
- **Started:** 2026-05-02T19:20:00Z (approx)
- **Completed:** 2026-05-02T19:26:26Z
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments

- `Settings` exposes `telegram_bot_token: SecretStr`, `telegram_bot_username: str`, `otp_deep_link_ttl_seconds=600`, `otp_code_ttl_seconds=300`, `otp_max_attempts=5` per D-10 / AUTH-TG-01 / AUTH-TG-02.
- `.env.example` documents all five Phase 7 vars plus optional `TELEGRAM_OWNER_USERNAME` (D-03 seed script binding) — block appended after seed-owner block, no existing keys touched.
- `app.core.database.db_lifespan_manager()` and `app.core.redis.redis_lifespan_manager()` are exported, framework-agnostic async-context managers usable by API process and the future bot worker (07-07).
- Existing `db_lifespan(app)` / `redis_lifespan(app)` reduced to ~4-line adapters that open the manager and bind to `app.state` — `tests/conftest.py:db_session` (which reads `app.state.engine`) is unaffected.
- `combined_lifespan` in `app/main.py` body unchanged (only docstring updated to point at the new managers + bot-worker reuse intent).

## Task Commits

Each task was committed atomically with `--no-verify` (parallel worktree):

1. **Task 1: Extend Settings + .env.example with Phase 7 Telegram vars (D-10, D-03)** — `f690f53` (feat)
2. **Task 2: Extract db_lifespan_manager + redis_lifespan_manager reusable managers (D-08)** — `831eb42` (refactor)

## Files Created/Modified

- `apps/backend/app/core/config.py` — Added five Phase 7 Settings fields after `refresh_reuse_window_seconds`. `SecretStr` already imported.
- `apps/backend/.env.example` — Appended Phase 7 block: `TELEGRAM_BOT_TOKEN`, `TELEGRAM_BOT_USERNAME`, `OTP_DEEP_LINK_TTL_SECONDS=600`, `OTP_CODE_TTL_SECONDS=300`, `OTP_MAX_ATTEMPTS=5`, `TELEGRAM_OWNER_USERNAME`.
- `apps/backend/app/core/database.py` — Added `db_lifespan_manager()` (yields `tuple[AsyncEngine, async_sessionmaker[AsyncSession]]`); rewrote `db_lifespan(app)` as adapter. Added `AsyncEngine` to `sqlalchemy.ext.asyncio` import.
- `apps/backend/app/core/redis.py` — Added `redis_lifespan_manager()` (yields `Redis`); rewrote `redis_lifespan(app)` as adapter.
- `apps/backend/app/main.py` — Updated `combined_lifespan` docstring to document the new manager reuse pattern; body unchanged.

## Decisions Made

None new — both tasks executed exactly as specified by the plan and locked Phase 7 decisions (D-08, D-10, D-03). Type annotation on `db_lifespan_manager` uses `tuple[AsyncEngine, async_sessionmaker[AsyncSession]]` exactly as the PATTERNS.md target shape (lines 78-90) prescribes.

## Deviations from Plan

None — plan executed exactly as written.

## Verification

| Check | Result |
|---|---|
| `Settings()` instantiation with min env produces correct field values | PASS |
| `grep telegram_bot_token: SecretStr` in `app/core/config.py` | PASS |
| `grep TELEGRAM_BOT_TOKEN=` and `TELEGRAM_OWNER_USERNAME=` in `.env.example` | PASS |
| `mypy --strict app/core/config.py` | Success: no issues found in 1 source file |
| `grep async def db_lifespan_manager` in `app/core/database.py` | PASS |
| `grep async def redis_lifespan_manager` in `app/core/redis.py` | PASS |
| `grep "async with db_lifespan_manager() as (engine, session_factory):"` | PASS |
| `grep "async with redis_lifespan_manager() as client:"` | PASS |
| `lint-imports` (3 importlinter contracts) | All 3 KEPT, 0 broken |
| `mypy --strict app/core/database.py app/core/redis.py app/main.py` | Success: no issues found in 3 source files |
| `mypy --strict app` (whole package, sanity) | Success: no issues found in 49 source files |
| `pytest tests/integration/test_healthz.py -x` | 2 skipped (DATABASE_URL not reachable in worktree — expected; same Phase 5 SAVEPOINT skip path; lifespan loaded without error before skip) |

## Issues Encountered

None. The PLAN's specified `tests/test_healthz.py` path was actually `tests/integration/test_healthz.py` (one-liner correction, no behavioral change). Tests skip cleanly because the worktree has no Docker Postgres reachable — same skip path Phase 5 D-22 conftest established. Lifespan path is exercised before the skip, confirming the refactor did not break startup.

## Threat Flags

None — no new network endpoints, auth paths, file access, or schema changes introduced. All Phase 7 STRIDE entries (T-07-01..T-07-04) remain inside the threat model boundary defined by the plan; `SecretStr` redaction (T-07-01) and `core ⊥ modules` contract (T-07-02) are both honored by this plan.

## Next Phase Readiness

- Plan 07-04 (`telegram_service`) can now read `settings.telegram_bot_token`, `settings.telegram_bot_username`, `settings.otp_deep_link_ttl_seconds`, `settings.otp_code_ttl_seconds`, `settings.otp_max_attempts` directly from the cached `get_settings()` instance.
- Plan 07-07 (worker entry) can `from app.core.database import db_lifespan_manager` and `from app.core.redis import redis_lifespan_manager` — open both under `contextlib.AsyncExitStack` exactly as PATTERNS.md prescribes (lines 178-211). `core ⊥ modules` invariant guarantees these manager imports do not pull in any `app.modules.*` code.
- Plan 07 router (verify endpoint, Phase 7 D-14) can build deep-link URL via `f"https://t.me/{settings.telegram_bot_username}?start={token}"` without needing a `Bot.get_me()` call (D-10).

## Self-Check: PASSED

- `apps/backend/app/core/config.py` — FOUND, contains five new fields (verified by grep + Settings smoke instantiation).
- `apps/backend/.env.example` — FOUND, contains all six Phase 7 keys (verified by grep).
- `apps/backend/app/core/database.py` — FOUND, contains `db_lifespan_manager` + adapter (verified by grep).
- `apps/backend/app/core/redis.py` — FOUND, contains `redis_lifespan_manager` + adapter (verified by grep).
- `apps/backend/app/main.py` — FOUND, docstring updated.
- Commit `f690f53` — FOUND in `git log`.
- Commit `831eb42` — FOUND in `git log`.

---

*Phase: 07-telegram-otp-channel*
*Plan: 01 of 8*
*Completed: 2026-05-02*
