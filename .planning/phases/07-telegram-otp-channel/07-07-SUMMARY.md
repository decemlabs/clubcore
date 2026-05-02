---
phase: 07-telegram-otp-channel
plan: 07
subsystem: ops
tags: [worker, asyncio, asynccontextmanager, asyncexitstack, ptb22, docker-compose, seed-script, importlinter]

# Dependency graph
requires:
  - phase: 07-telegram-otp-channel
    plan: 01
    provides: db_lifespan_manager + redis_lifespan_manager reusable async-context managers; Settings.telegram_bot_token (SecretStr)
  - phase: 07-telegram-otp-channel
    plan: 04
    provides: app.modules.auth.telegram_service module (D-06 relaxation target)
  - phase: 07-telegram-otp-channel
    plan: 05
    provides: build_application factory + HandlerContext NamedTuple + start_handler + sender module

provides:
  - apps/backend/app/workers/telegram_bot.py:main — async entry composing AsyncExitStack(db_lifespan_manager + redis_lifespan_manager) + ptb 22 Application via build_application factory + SIGINT/SIGTERM graceful shutdown
  - apps/backend/app/workers/telegram_bot.py module guard `if __name__ == "__main__": asyncio.run(main())` — INFRA-06 entry
  - apps/backend/app/workers/__init__.py docstring documenting D-06 relaxation (workers MAY import a single owning module's service layer)
  - apps/backend/docker-compose.yml fourth `telegram-bot` service — INFRA-06; restart: unless-stopped; depends_on migrate (service_completed_successfully) + redis (service_started); no ports, no volumes mount
  - apps/backend/scripts/seed_demo_data.py optional TELEGRAM_OWNER_USERNAME binding — idempotent lower(value) write to seeded owner User.telegram_username (D-03)

affects:
  - 07-08 (integration tests, Wave 3 sibling) — worker entry is intentionally NOT exercised in tests per D-17; handler-level tests use the same HandlerContext shape this worker constructs
  - Phase 8 (audit log) — bot worker's structlog events from handlers (telegram_unknown_start / telegram_dm_blocked / telegram_dm_failed / telegram_replay_attempt / otp_issued) latch onto the future audit_log writer unchanged
  - Phase 10 (admin-web) — `docker compose up` now starts a 4th container so end-to-end testing of the deep-link flow works without manual bot worker startup

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "AsyncExitStack composition for multi-resource lifespan in non-FastAPI processes: opens db_lifespan_manager() + redis_lifespan_manager() under one stack so worker shutdown disposes both even if Application init fails"
    - "ptb 22 manual Application lifecycle (initialize/start/updater.start_polling/stop) instead of run_polling() — required when the surrounding event loop already manages signals"
    - "asyncio.Event-driven graceful shutdown: SIGINT/SIGTERM set the event; main loop awaits it; finally-block stops Application; suppress(NotImplementedError) on signal registration for platforms without POSIX signals"
    - "Docker compose service-as-process pattern: fourth service uses the same image but a different command, no port exposure, no volume mount — production-shape for an outbound-only worker"
    - "Idempotent seed extension via SELECT-then-conditional-UPDATE: `if user.telegram_username != tg_lower:` guards both the no-op (already set) and the rebind (different value) paths without duplicate INSERTs"

key-files:
  created:
    - apps/backend/app/workers/telegram_bot.py
  modified:
    - apps/backend/app/workers/__init__.py
    - apps/backend/docker-compose.yml
    - apps/backend/scripts/seed_demo_data.py

key-decisions:
  - "D-06 relaxation realised in a single import line: `from app.modules.auth import telegram_service` is the SOLE direct app.modules.* import across all of app/workers/. Documented inline in workers/telegram_bot.py docstring AND in workers/__init__.py docstring (ground truth + index)."
  - "D-09 honored: NO module-level Application — built inside main()'s scope via build_application factory; Application instance lifetime is bounded by the AsyncExitStack."
  - "D-08 honored: db_lifespan_manager() + redis_lifespan_manager() opened under contextlib.AsyncExitStack — pool config shared with API process; close-on-exit guaranteed even if Application init raises."
  - "Manual ptb 22 lifecycle (initialize/start/updater.start_polling/stop) chosen over run_polling() so SIGINT/SIGTERM shutdown is explicit and observable; matches the pattern other ptb v22 long-running deployments use when an external supervisor (docker restart: unless-stopped) is in play."
  - "INFRA-06 docker-compose service inserted RIGHT AFTER `backend:` (visual sibling) — preserves alphabetical/topological ordering migrate -> postgres -> redis at end. depends_on uses condition: service_completed_successfully on migrate (must wait for schema) + service_started on redis (long-poll loop tolerates brief Redis hiccups)."
  - "D-03 seed extension is gated by an optional env var (TELEGRAM_OWNER_USERNAME) AND a string-equality check — env var unset = no-op, env var unchanged = no-op (printed), env var changed = rebind. Three idempotent paths in one block."
  - "Ruff SIM105 fix at first run: replaced `try: ... except NotImplementedError: pass` with `with suppress(NotImplementedError):` — preserves Windows test platform fallback while satisfying the lint rule."

patterns-established:
  - "Worker-as-supervised-process: bot worker is structurally a sibling of the API uvicorn process (same image, different command, env_file: .env, no shared volume) — this is the template for any future channel worker (SMS, email-OTP) that needs its own ARQ-or-polling loop"
  - "Docstring-only architectural relaxation: when no importlinter contract enforces a boundary (here `workers ⊥ modules`), the relaxation lives in two docstrings (worker entry + package __init__) rather than a config-file comment — discoverable at import time"

requirements-completed:
  - INFRA-06
  - AUTH-TG-02
  - AUTH-TG-05

# Metrics
metrics:
  duration_minutes: 3
  completed_date: "2026-05-02"
  tasks_completed: 2
  files_changed: 4
  commits:
    - d949c86
    - c76c6ae
---

# Phase 7 Plan 07: Bot Worker Entry + Docker Service + Seed Extension Summary

**Ops-уровень Phase 7 закрыт: `app/workers/telegram_bot.py` собирает ptb 22 Application через AsyncExitStack + reusable lifespan managers (D-08/D-09), docker-compose поднимает четвёртый `telegram-bot` сервис (INFRA-06), seed-скрипт идемпотентно привязывает `telegram_username` владельцу при наличии `TELEGRAM_OWNER_USERNAME` env (D-03). Архитектурное исключение D-06 (workers→modules.auth.telegram_service) задокументировано в двух docstring-блоках. mypy --strict / ruff / lint-imports — зелёные на всём бэкенде (52 файла, 3 контракта KEPT).**

## Performance

- **Started:** 2026-05-02T19:49:40Z
- **Completed:** 2026-05-02T19:52:23Z
- **Duration:** ~3 min
- **Tasks:** 2 (both atomically committed)
- **Files changed:** 4 (1 created, 3 modified)

## Accomplishments

- `app/workers/telegram_bot.py` (NEW) — `async def main()` composes the entire bot worker process:
  1. `get_settings()` + `configure_logging(settings)` (logging-first, mirrors `app/main.py:create_app` order).
  2. `AsyncExitStack` opens `db_lifespan_manager()` (yields engine + sessionmaker) and `redis_lifespan_manager()` — both close on exit even if Application init fails.
  3. Constructs `HandlerContext(session_factory=sessionmaker, telegram_service=telegram_service, sender=telegram_sender)`.
  4. Calls `build_application(token=settings.telegram_bot_token.get_secret_value(), handlers=[("start", start_handler)], ctx=ctx)` — D-09 factory pattern, no module-level Application instance.
  5. Manual lifecycle: `application.initialize()` → `application.start()` → `application.updater.start_polling()`.
  6. Awaits `asyncio.Event` set by SIGINT/SIGTERM handlers (suppressed if signals unavailable on platform).
  7. `finally` block: `updater.stop()` → `application.stop()` → `application.shutdown()`.
  8. `if __name__ == "__main__": asyncio.run(main())` enables `python -m app.workers.telegram_bot` (INFRA-06 entry).
- `app/workers/__init__.py` — docstring extended with explicit Phase 7 D-06 EXCEPTION clause: workers MAY import a single owning module's service layer when the worker IS that module's I/O fanout. Cross-module imports inside workers stay forbidden. Documents that no importlinter contract change is needed because no contract currently enforces `workers ⊥ modules`.
- `docker-compose.yml` — fourth `telegram-bot` service inserted right after `backend:` (sibling visual pairing). Identical image (`build: .`), `command: python -m app.workers.telegram_bot`, `env_file: .env`, `DATABASE_URL`+`REDIS_URL` env, `restart: unless-stopped` (INFRA-06 explicit), `depends_on: migrate (service_completed_successfully) + redis (service_started)`. NO `ports:` (outbound-only), NO `volumes:` mount (production-shape; full image rebuild for code changes).
- `scripts/seed_demo_data.py` — added `from sqlalchemy import select` and a Phase 7 D-03 block after the existing owner upsert + commit. Reads `TELEGRAM_OWNER_USERNAME` env var; if set, lstrips leading `@`, lowercases, SELECTs the seeded owner User by `email_lower`, and:
  - sets `user.telegram_username = tg_lower` + commits + prints `Bound telegram_username=...` if currently NULL or different
  - prints `telegram_username for ... already set to ... (no-op).` if already matches
  - skips entire block if env var missing/empty
  Three idempotent paths, zero schema/data risk on re-runs.

## Task Commits

| # | Task | Commit | Type |
|---|---|---|---|
| 1 | Implement workers/telegram_bot.py + workers/__init__.py docstring (D-06, D-08, D-09) | `d949c86` | feat |
| 2 | Add telegram-bot docker service + extend seed_demo_data.py (INFRA-06, D-03) | `c76c6ae` | feat |

## Files Created/Modified

| File | Status | Role |
|---|---|---|
| `apps/backend/app/workers/telegram_bot.py` | created | Bot worker process entry — async main() with AsyncExitStack lifespan composition + ptb 22 Application + signal-driven graceful shutdown |
| `apps/backend/app/workers/__init__.py` | modified | Docstring documents D-06 relaxation (workers→modules.auth.telegram_service) |
| `apps/backend/docker-compose.yml` | modified | +13 lines: telegram-bot service after backend |
| `apps/backend/scripts/seed_demo_data.py` | modified | +14 lines (incl. import): D-03 idempotent telegram_username binding block |

## Decisions Made

- **Manual Application lifecycle over `run_polling()`** — `application.initialize()` → `application.start()` → `application.updater.start_polling()` → wait on asyncio.Event → `updater.stop()`/`application.stop()`/`application.shutdown()`. `run_polling()` blocks the calling coroutine and installs its own signal handlers, which would conflict with our explicit SIGINT/SIGTERM → asyncio.Event pattern. The manual lifecycle is the documented escape hatch in ptb 22 for processes managed by an external supervisor (docker `restart: unless-stopped`).
- **`# type: ignore[union-attr]` on `application.updater.{start_polling,stop}`** — ptb 22 types `Application.updater` as `Updater | None` (None when configured without an Updater). Our `Application.builder().token(...).build()` always produces an Updater, but the static type doesn't narrow. Two narrow ignores keep mypy --strict green without weakening the rest of the file.
- **`with suppress(NotImplementedError):` on signal registration** — `loop.add_signal_handler` raises `NotImplementedError` on Windows. The bot is dev-shipped on macOS/Linux but the test/CI matrix may include Windows callers; suppression is the canonical Python idiom for platform-conditional system-call fallbacks.
- **`_engine` and `_redis` as throwaway names** — the worker only needs the sessionmaker (passed into HandlerContext) and the AsyncExitStack-managed lifecycle of both resources; the engine handle and Redis client are not used directly. Underscore prefix signals deliberate non-use to readers + ruff.
- **Seed env block placed AFTER the existing commit** — keeps the upsert atomic on its own and the D-03 binding as a separate, idempotent commit. If the binding query/commit fails, the owner upsert stays intact.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 — Blocking] Ruff SIM105 on signal-handler try/except in workers/telegram_bot.py**
- **Found during:** Task 1 verify (`uv run ruff check app/workers/telegram_bot.py`).
- **Issue:** The plan's action block specified `try: loop.add_signal_handler(sig, _shutdown) except NotImplementedError: pass` for cross-platform safety. Ruff SIM105 flagged this as a candidate for `contextlib.suppress(NotImplementedError)`.
- **Fix:** Imported `suppress` alongside `AsyncExitStack` from `contextlib`; replaced the try/except block with `with suppress(NotImplementedError): loop.add_signal_handler(sig, _shutdown)`. Identical runtime semantics, satisfies SIM105.
- **Files modified:** `apps/backend/app/workers/telegram_bot.py` (rolled into Task 1 commit `d949c86`).
- **Commit:** `d949c86` (folded into Task 1 final commit).

---

**Total deviations:** 1 auto-fixed (1 blocking lint issue). Public contract (function name, signature, behaviour, signal handling) is identical to the plan. Plan's done criteria all met without contract drift.

## Verification

| Check | Result |
|---|---|
| `test -f apps/backend/app/workers/telegram_bot.py` | PASS |
| `grep -q "async def main" telegram_bot.py` | PASS |
| `grep -q 'if __name__ == "__main__":' telegram_bot.py` | PASS |
| `grep -q "asyncio.run(main())" telegram_bot.py` | PASS |
| `grep -q "from app.modules.auth import telegram_service" telegram_bot.py` | PASS (D-06 relaxation realised) |
| `grep -q "AsyncExitStack" telegram_bot.py` | PASS (D-08 lifespan composition) |
| `grep -q "EXCEPTION (Phase 7 D-06)" workers/__init__.py` | PASS (relaxation documented) |
| `grep -q "telegram_bot" workers/__init__.py` | PASS |
| `uv run mypy --strict app/workers/telegram_bot.py app/workers/__init__.py` | Success (2 source files) |
| `uv run ruff check app/workers/telegram_bot.py app/workers/__init__.py` | All checks passed! |
| `uv run python -c "import app.workers.telegram_bot; assert hasattr(app.workers.telegram_bot, 'main')"` | OK (smoke import) |
| `grep -A1 "^  telegram-bot:" docker-compose.yml \| grep "build: ."` | PASS |
| `grep -A12 "^  telegram-bot:" docker-compose.yml \| grep "command: python -m app.workers.telegram_bot"` | PASS |
| `grep -A12 "^  telegram-bot:" docker-compose.yml \| grep "restart: unless-stopped"` | PASS |
| `grep -A12 "^  telegram-bot:" docker-compose.yml \| grep "service_completed_successfully"` | PASS |
| `! grep -A12 "^  telegram-bot:" docker-compose.yml \| grep "ports:"` | PASS (no ports — outbound-only) |
| `docker compose config --services` lists telegram-bot | PASS (5 services: backend, migrate, postgres, redis, telegram-bot) |
| `uv run python -c "import yaml; ... 'telegram-bot' in data['services']"` | True |
| `grep -q "TELEGRAM_OWNER_USERNAME" scripts/seed_demo_data.py` | PASS |
| `grep -q "telegram_username" scripts/seed_demo_data.py` | PASS |
| `uv run mypy --strict scripts/seed_demo_data.py` | Success (1 source file) |
| `uv run ruff check scripts/seed_demo_data.py` | All checks passed! |
| `uv run mypy --strict app` (full sanity) | Success: no issues found in 52 source files |
| `uv run ruff check app` (full sanity) | All checks passed! |
| `uv run lint-imports` (3 importlinter contracts) | All 3 KEPT, 0 broken |

## Threat Mitigations Honored

- **T-07-33 (Information Disclosure — TELEGRAM_BOT_TOKEN in YAML):** Mitigated. docker-compose.yml uses `env_file: .env` (not literal token in YAML); .env is in .gitignore; SecretStr in Settings means `.get_secret_value()` is the explicit unwrap point — no accidental log leakage via Settings.__repr__.
- **T-07-34 (DoS — bot crash in polling loop):** Mitigated. `restart: unless-stopped` in compose service ensures docker restarts the worker on crash; ptb 22 global error handler (registered by build_application — Plan 07-05) catches handler exceptions inside the loop so most failures don't propagate; AsyncExitStack guarantees clean DB/Redis pool teardown on shutdown so restart cycles don't leak connections.
- **T-07-35 (EoP — seed script overwrites arbitrary telegram_username):** Accepted. Seed runs only at deploy with privileged DB user; ENV var is operator-controlled. Mitigation is operational (deploy gating) rather than code-level.
- **T-07-36 (Tampering — bot worker connects to wrong DB):** Accepted. DATABASE_URL is hardcoded to internal docker DNS in compose; production deploys override via env var; D-08 reusable manager guarantees same engine/pool config as the API process — drift impossible by construction.
- **T-07-37 (Repudiation — seed script silent on action):** Mitigated. Three explicit `print(...)` calls in the D-03 block: bound (new value), already-set (no-op), and the existing seeded-owner message. Output is captured in `docker compose logs migrate` (or stdout when run directly) for audit.

## Threat Flags

None — no new network surface, no new auth path, no new file access pattern, no schema change. The 4th docker service does NOT expose any port (outbound-only Telegram client connections); the seed extension reads/writes an existing column added by Wave 1 Plan 02.

## User Setup Required

To start the bot worker via docker compose:

1. Create `apps/backend/.env` (or copy `.env.example`) with at minimum:
   - `TELEGRAM_BOT_TOKEN=<your-bot-token-from-BotFather>` (required)
   - `TELEGRAM_BOT_USERNAME=<bot-username-without-@>` (required for deep-link URL — used by Plan 07-06 router)
   - `SECRET_KEY=<32+ char string>` (existing)
   - `DATABASE_URL=postgresql+asyncpg://app:app@postgres:5432/sportzal` (existing — internal compose DNS)
   - `REDIS_URL=redis://redis:6379/0` (existing)
2. (Optional) Set `TELEGRAM_OWNER_USERNAME=<your_telegram_username_lowercase>` to bind your Telegram account to the seeded owner during seeding.
3. `docker compose -f apps/backend/docker-compose.yml up` starts five services. Bot worker connects to Telegram and starts long-polling.
4. Run seed: `docker compose -f apps/backend/docker-compose.yml run --rm migrate uv run python -m scripts.seed_demo_data` (or run inside backend container) — D-03 block writes telegram_username when env var is present.

## Next Phase Readiness

- **Plan 07-06 (router, Wave 3 sibling)** will mount `/api/v1/auth/telegram/{start,status,verify}` endpoints. The deep-link URL it constructs (`f"https://t.me/{settings.telegram_bot_username}?start={token}"`) targets the bot username operators set in `.env`; the worker process this plan ships is what the deep-link clicks reach. End-to-end happy path: FE calls /start → router returns deepLinkUrl → user clicks → Telegram opens bot chat → user presses /start <token> → THIS WORKER's start_handler runs → bind_and_issue → DM → user pastes code → /verify.
- **Plan 07-08 (integration tests, Wave 3 sibling)** intentionally does NOT exercise this worker (D-17). Handler tests (`tests/integration/telegram/test_handler_start.py`) call `start_handler` directly with hand-built `Update` objects + the same `HandlerContext` shape this worker constructs. The worker's `python -m app.workers.telegram_bot` entry is exercised manually via `docker compose up` smoke.
- **Phase 8 (audit log)** — when the audit_log writer lands, the structlog events emitted by the handlers (running inside this worker process) will be captured by the same handler infrastructure that captures API events. No worker-side change needed.
- **Future channel workers (v1.2 SMS / email-OTP)** can copy this worker's pattern verbatim: add a 5th compose service with the same shape, write `app/workers/<channel>_bot.py` with AsyncExitStack composition, document the D-06-style relaxation if the worker calls a single module's service layer.

## Self-Check: PASSED

Files asserted to exist:
- FOUND: `/Users/andre/Workspace/Development/clubcore/.claude/worktrees/agent-a3f47a7725462bb1e/apps/backend/app/workers/telegram_bot.py`
- FOUND: `/Users/andre/Workspace/Development/clubcore/.claude/worktrees/agent-a3f47a7725462bb1e/apps/backend/app/workers/__init__.py`
- FOUND: `/Users/andre/Workspace/Development/clubcore/.claude/worktrees/agent-a3f47a7725462bb1e/apps/backend/docker-compose.yml`
- FOUND: `/Users/andre/Workspace/Development/clubcore/.claude/worktrees/agent-a3f47a7725462bb1e/apps/backend/scripts/seed_demo_data.py`

Commits asserted to exist on branch:
- FOUND: `d949c86` (Task 1)
- FOUND: `c76c6ae` (Task 2)

Verified via:
```
git log --oneline -3
c76c6ae feat(07-07): add telegram-bot compose service + seed telegram_username binding
d949c86 feat(07-07): add telegram bot worker entry + workers D-06 docstring
60bf28b docs(07): record Wave 2 completion in STATE.md (5/8 plans)
```

---

*Phase: 07-telegram-otp-channel*
*Plan: 07 of 8 (Wave 3)*
*Completed: 2026-05-02*
