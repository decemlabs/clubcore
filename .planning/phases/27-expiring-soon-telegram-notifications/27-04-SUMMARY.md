---
phase: 27-expiring-soon-telegram-notifications
plan: 04
subsystem: workers
tags: [phase-27, arq-cron, worker, owner-signoff, key-decisions, ntf-02, ntf-03, ntf-copy-01]
requirements: [NTF-02, NTF-03, NTF-COPY-01]
dependency-graph:
  requires:
    - 27-02 (memberships service _send_expiring_notifications helper)
    - 27-03 (telegram copy module with 6 Russian DM templates)
  provides:
    - apps/backend/app/integrations/telegram/bot.py::build_bot
    - apps/backend/app/workers/scheduled/send_expiring_notifications.py::send_expiring_notifications
    - WorkerSettings 2-cron contract (06:05 expire_memberships → 06:15 send_expiring_notifications)
    - PROJECT.md row D-27-OWNER-COPY-LOCK (NTF-COPY-01 lock)
  affects:
    - tests/unit/workers/test_worker_settings.py (Phase 18 tests adjusted from 1-cron to 2-cron contract)
tech-stack:
  added:
    - python-telegram-bot Bot factory helper (build_bot)
    - ARQ cron registration for daily 06:15 Europe/Moscow tick
  patterns:
    - Option B (D-27-06): bot factory in integrations/telegram/bot.py — no inline Bot construction in worker
    - Multi-session pattern (D-27-07 b): worker passes session_factory to helper; helper opens per-send write sessions
    - Locked summary log convention: "<job_name>_complete count=N" (Phase 18 specifics line 195)
key-files:
  created:
    - apps/backend/app/workers/scheduled/send_expiring_notifications.py
  modified:
    - apps/backend/app/integrations/telegram/bot.py
    - apps/backend/app/workers/__init__.py
    - .planning/PROJECT.md
    - apps/backend/tests/unit/workers/test_worker_settings.py
decisions:
  - D-27-06 — Bot construction via build_bot helper (Option B); inline Bot(token=...) in worker rejected
  - D-27-OWNER-COPY-LOCK — 6 Russian DM templates (NTF-COPY-01) auto-approved under workflow.auto_advance 2026-05-09
  - D-27-16 — cron ordering 06:05 (expire_memberships) → 06:15 (send_expiring_notifications) with 10-min buffer + unique=True
metrics:
  duration: ~25 minutes
  completed: 2026-05-09
  tasks: 3
  files: 4 (modified) + 1 (created)
  commits: 4 (3 task + 1 deviation)
---

# Phase 27 Plan 04: ARQ wiring + owner sign-off Summary

ARQ scheduled job `send_expiring_notifications` wired (06:15 Europe/Moscow) using a new `build_bot` factory in `bot.py`; 6 locked Russian DM templates auto-approved as `D-27-OWNER-COPY-LOCK` in PROJECT.md Key Decisions table.

## Deliverables

### 1. `build_bot` helper added to `apps/backend/app/integrations/telegram/bot.py`

Appended after `build_application` (Option B locked per D-27-06):

```python
def build_bot(*, token: str) -> Bot:
    """Construct a bare Bot for outbound DM use (no long-polling Application).

    Phase 27 cron worker uses this — it only sends DMs and does NOT need
    Application's update-loop / handler dispatch. The Bot instance is
    lightweight (lazy aiohttp session) so per-tick instantiation is fine
    at pet-project scale (D-27-06 / CONTEXT Risks/Watchpoints).

    Returns a FRESH Bot per call (no caching) — keeps the helper pure and
    avoids cross-tick session leak risks.
    """
    return Bot(token=token)
```

Import block extended: `from telegram import Bot, Update`.

### 2. New worker file `apps/backend/app/workers/scheduled/send_expiring_notifications.py`

Mirrors `expire_memberships.py` analog. Key differences vs Phase 18 worker:
- Imports `build_bot`, `telegram_sender`, `telegram_copy`, `memberships_service`.
- Constructs `Bot` via `build_bot(token=settings.telegram_bot_token.get_secret_value())`.
- Multi-session pattern (D-27-07 b): passes `ctx["sessionmaker"]` to helper; helper opens per-send write sessions internally.
- Calls `memberships_service._send_expiring_notifications(session_factory, bot=bot, sender=telegram_sender, copy_module=telegram_copy)`.
- Emits locked summary log `send_expiring_notifications_complete count=N` after helper returns.
- Returns int count to ARQ result store.

```python
async def send_expiring_notifications(ctx: dict[str, Any]) -> int:
    session_factory = ctx["sessionmaker"]
    settings = get_settings()
    bot = build_bot(token=settings.telegram_bot_token.get_secret_value())

    count = await memberships_service._send_expiring_notifications(
        session_factory,
        bot=bot,
        sender=telegram_sender,
        copy_module=telegram_copy,
    )

    _log.info("send_expiring_notifications_complete", count=count)
    return count
```

### 3. WorkerSettings extension — 2-cron contract

**Before:**
```python
from app.workers.scheduled.expire_memberships import expire_memberships
...
functions: ClassVar[list[Any]] = [expire_memberships]
cron_jobs: ClassVar[list[Any]] = [
    cron(expire_memberships, hour=3, minute=5, unique=True, keep_result=60),
]
```

**After:**
```python
from app.workers.scheduled.expire_memberships import expire_memberships
from app.workers.scheduled.send_expiring_notifications import send_expiring_notifications
...
functions: ClassVar[list[Any]] = [expire_memberships, send_expiring_notifications]
cron_jobs: ClassVar[list[Any]] = [
    cron(expire_memberships, hour=3, minute=5, unique=True, keep_result=60),
    cron(send_expiring_notifications, hour=3, minute=15, unique=True, keep_result=60),
]
```

`on_startup` cron-resolution invariant (Pitfall 4 step 6) auto-passes — both cron coroutine names appear in `functions`.

ARQ boot smoke (verified): `len(WorkerSettings.cron_jobs) == 2`, `cron_names = ['expire_memberships', 'send_expiring_notifications']`, ordering preserved.

### 4. Owner sign-off — 6 locked Russian DM templates (auto-approved under `--auto`)

Auto-mode is active (`workflow.auto_advance = true`); the human-verify checkpoint was auto-approved per orchestrator policy. The 6 templates from plan 27-03 (rendered with `end_date = "16 мая 2026 г."`):

1. **EXPIRING_7D_VARIANT_A**: "Привет! Ваш абонемент истекает 16 мая 2026 г. Самое время продлить — обратитесь к администратору."
2. **EXPIRING_7D_VARIANT_B**: "Напоминаем: ваш абонемент действует до 16 мая 2026 г. Продление через администратора."
3. **EXPIRING_3D_VARIANT_A**: "Через 3 дня заканчивается ваш абонемент (16 мая 2026 г.). Подойдите к стойке для продления."
4. **EXPIRING_3D_VARIANT_B**: "Ваш абонемент действителен до 16 мая 2026 г. Не забудьте продлить!"
5. **EXPIRING_1D_VARIANT_A**: "Завтра (16 мая 2026 г.) — последний день вашего абонемента. Заходите продлевать."
6. **EXPIRING_1D_VARIANT_B**: "Внимание: ваш абонемент истекает завтра, 16 мая 2026 г. Зайдите к нам, чтобы продлить."

Per anti-oracle policy (D-5 / Phase 20): per-client A/B variant via `client_id.bytes[0] & 1`; `{end_date}` formatted via Russian long form. Templates were not edited; `apps/backend/app/integrations/telegram/copy.py` constants are byte-identical to plan 27-03 output.

**PROJECT.md Key Decisions row appended** (verbatim):

```
| D-27-OWNER-COPY-LOCK | Phase 27 owner sign-off — 6 locked Russian DM templates (NTF-COPY-01); per-client A/B variant via `client_id.bytes[0] & 1` (anti-oracle); placeholder `{end_date}` formatted via Russian long form (e.g. `16 мая 2026 г.`). Mirrors v1.2 Phase 20 D-20-9 / D-5 sign-off mechanism — locked Russian copy must be owner-signed; modification requires new sign-off row. | ✓ Auto-approved — v1.3 (Phase 27) — auto-approved under `workflow.auto_advance` 2026-05-09 |
```

`grep -c "D-27-OWNER-COPY-LOCK" .planning/PROJECT.md` = 1.

> Note: Sign-off was auto-approved under the `--auto` chain. A human reviewer can re-check post-hoc by reading the 6 templates above (or `apps/backend/app/integrations/telegram/copy.py`) and amending `copy.py` + appending a fresh sign-off row if any string needs editing.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 — Bug] Phase 18 worker settings tests broken by 2-cron contract**
- **Found during:** Final pytest run (post-Task 3)
- **Issue:** `tests/unit/workers/test_worker_settings.py::test_worker_settings_cron_resolves_to_registered_function` asserted `len(WorkerSettings.cron_jobs) == 1`; `test_worker_settings_functions_registered` asserted `len(WorkerSettings.functions) == 1`. Both were stale Phase 18 invariants directly broken by Task 2's intentional list extension.
- **Fix:** Updated both literal counts to `== 2`; preserved the index-0 expire_memberships invariant (06:05 stays first per D-27-16 ordering); added Phase 27 docstring rationale to both tests.
- **Files modified:** `apps/backend/tests/unit/workers/test_worker_settings.py`
- **Commit:** 96ce6c8

## Threat Surface Scan

No new security-relevant surface introduced beyond the threat model in plan 27-04. Bot token unwrap via `.get_secret_value()` happens only at the `build_bot(token=...)` call site (T-27-04-01 mitigation); structlog never receives the unwrapped token; `unique=True` cron guard (T-27-04-02 mitigation) preserved on both cron entries; `on_startup` cron-resolution invariant (T-27-04-03 mitigation) auto-passes.

## Verification

- ✅ `cd apps/backend && uv run lint-imports` → 3 contracts KEPT, 0 broken (152 deps analysed; +1 over baseline = the new worker→memberships.service edge documented in workers/__init__.py D-09 narrative)
- ✅ `cd apps/backend && uv run mypy app/workers/__init__.py app/workers/scheduled/send_expiring_notifications.py app/integrations/telegram/bot.py` → 0 issues across 3 files
- ✅ `cd apps/backend && uv run ruff check app/workers/ app/integrations/telegram/` → All checks passed
- ✅ `cd apps/backend && uv run pytest -x` → **709 passed in 45.51s** (was 703 + 1 stale failure → now 709 passing including 7 worker-settings tests)
- ✅ `grep -c "D-27-OWNER-COPY-LOCK" .planning/PROJECT.md` = 1
- ✅ `grep -c 'Bot(token=' apps/backend/app/workers/scheduled/send_expiring_notifications.py` = 0 (Option A rejected)
- ✅ `cron_function_names ⊆ function_names` invariant — `{"expire_memberships", "send_expiring_notifications"} ⊆ {"expire_memberships", "send_expiring_notifications"}`
- ✅ Cron ordering preserved — index 0 = expire_memberships (06:05), index 1 = send_expiring_notifications (06:15)

## Commits

| Task | Commit | Description |
|------|--------|-------------|
| 1 | 1129bff | feat(27-04): add build_bot helper + send_expiring_notifications worker |
| 2 | aca0d93 | feat(27-04): register send_expiring_notifications in WorkerSettings |
| 3 | ca6ce8a | docs(27-04): owner sign-off for 6 locked Russian DM templates (D-27-OWNER-COPY-LOCK) |
| Rule 1 | 96ce6c8 | test(27-04): align Phase 18 worker settings tests with 2-cron contract |

## Self-Check: PASSED

- ✅ `apps/backend/app/integrations/telegram/bot.py::build_bot` — FOUND (`grep -c '^def build_bot' apps/backend/app/integrations/telegram/bot.py` = 1)
- ✅ `apps/backend/app/workers/scheduled/send_expiring_notifications.py` — FOUND
- ✅ `apps/backend/app/workers/scheduled/send_expiring_notifications.py::send_expiring_notifications` coroutine — FOUND, async, takes `ctx: dict[str, Any]`, returns `int`
- ✅ `apps/backend/app/workers/__init__.py` extends functions + cron_jobs — VERIFIED at runtime (len(cron_jobs)==2, len(functions)==2, ordering preserved)
- ✅ `.planning/PROJECT.md` D-27-OWNER-COPY-LOCK row — FOUND (grep returns 1)
- ✅ Commits 1129bff, aca0d93, ca6ce8a, 96ce6c8 — FOUND in git log
