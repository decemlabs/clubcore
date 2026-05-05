---
phase: 05-user-schema-email-password-auth
plan: 01
subsystem: backend-config
tags: [config, dependencies, env, settings]
requirements-completed: [AUTH-06, AUTH-EP-04]
dependency_graph:
  requires: []
  provides:
    - "Pinned redis>=5,<6 dependency (D-08)"
    - "Settings.refresh_reuse_window_seconds field (D-13, AUTH-06)"
    - "Documented Phase 5 env vars: REFRESH_REUSE_WINDOW_SECONDS, SEED_OWNER_EMAIL, SEED_OWNER_PASSWORD"
  affects:
    - "All subsequent Phase 5 plans (05-02..05-08) consume Settings.refresh_reuse_window_seconds"
    - "Seed script (D-25) consumes SEED_OWNER_EMAIL/SEED_OWNER_PASSWORD"
tech_stack:
  added: []
  patterns:
    - "pydantic-settings env var loading with default value"
    - "Phase-tagged comment block in Settings class for grouping additions"
key_files:
  created: []
  modified:
    - "apps/backend/pyproject.toml — narrowed redis>=5,<6"
    - "apps/backend/uv.lock — regenerated against narrowed pin"
    - "apps/backend/.env.example — added REFRESH_REUSE_WINDOW_SECONDS, SEED_OWNER_EMAIL, SEED_OWNER_PASSWORD"
    - "apps/backend/app/core/config.py — added refresh_reuse_window_seconds: int = 5"
decisions:
  - "Strict adherence to plan's `<action>` text — no validators, no model_config touch, exact placement after cookie_secure"
  - "uv.lock regenerated via `uv lock` (resolves 59 packages, redis stays in 5.x)"
metrics:
  duration: "1m 34s"
  completed_date: "2026-05-02"
  tasks_completed: 2
  files_modified: 4
---

# Phase 5 Plan 01: Phase 5 Config & Deps Foundation Summary

Расширил config + dep pins для Phase 5: сузил `redis` до `>=5,<6`, добавил `Settings.refresh_reuse_window_seconds: int = 5` и задокументировал три новые env-переменные (`REFRESH_REUSE_WINDOW_SECONDS`, `SEED_OWNER_EMAIL`, `SEED_OWNER_PASSWORD`).

## What Was Built

### Task 1: Narrow redis pin and document Phase 5 env vars
**Commit:** `f2c8f71`

- `apps/backend/pyproject.toml`: заменён `"redis>=5.0",` на `"redis>=5,<6",` (D-08 — блокирует случайный major-апгрейд redis-py).
- `apps/backend/uv.lock`: регенерирован через `uv lock` (resolved 59 packages, без изменений в фактической версии redis).
- `apps/backend/.env.example`: добавлены три блока в конец файла (после `COOKIE_SECURE`):
  - `REFRESH_REUSE_WINDOW_SECONDS=5` с комментарием по D-13/AUTH-06
  - `SEED_OWNER_EMAIL=` (пустое значение, заполняется в operator shell)
  - `SEED_OWNER_PASSWORD=` (пустое значение)

**Verification:**
- `grep -F 'redis>=5,<6' pyproject.toml` ✓
- `grep -F 'REFRESH_REUSE_WINDOW_SECONDS=5' .env.example` ✓
- `grep -F 'SEED_OWNER_EMAIL=' .env.example` ✓
- `grep -F 'SEED_OWNER_PASSWORD=' .env.example` ✓
- `uv lock --check` exit 0 ✓
- `grep -F 'redis>=5.0' pyproject.toml` exit 1 (старый пин удалён) ✓

### Task 2: Add refresh_reuse_window_seconds to Settings
**Commit:** `4b0b637`

- `apps/backend/app/core/config.py`: добавлено единственное поле `refresh_reuse_window_seconds: int = 5` непосредственно после `cookie_secure: bool = False`, с комментарием-блоком по D-13/AUTH-06. `model_config` и существующие Phase 4 поля не тронуты.

**Verification:**
- `grep -n 'refresh_reuse_window_seconds: int = 5' app/core/config.py` ✓ (line 34)
- `uv run python -c "... assert get_settings().refresh_reuse_window_seconds == 5"` prints `5` ✓
- Env var override (`REFRESH_REUSE_WINDOW_SECONDS=42`) → реально читается как 42 ✓
- `uv run ruff check app/core/config.py` — All checks passed ✓
- `uv run mypy app/core/config.py` — Success: no issues found ✓

## Verification

Plan-level verification suite полностью зелёный:

```
Resolved 59 packages in 3ms                # uv lock --check
settings_ok                                 # refresh_reuse_window_seconds == 5
All checks passed!                          # ruff
Success: no issues found in 1 source file   # mypy strict
FINAL VERIFICATION OK
```

## Deviations from Plan

None — plan executed exactly as written.

**Notes (not deviations):**

- В `.env` файле в worktree отсутствует (только `.env.example`), поэтому при запуске verification-команды нужны были inline env-переменные `DATABASE_URL`, `REDIS_URL`, `SECRET_KEY` для прохождения Pydantic Settings валидации обязательных полей. Это не требует правки кода — это локальное состояние worktree (нормальная ситуация: `.env` создаётся оператором). Plan's `<verify>` команда сработала бы один-в-один в окружении с `.env` (которое есть локально у разработчика).

## Decisions Made

- **Strict adherence to plan's `<action>` text.** План был очень конкретным (узкий патч в Settings класс, точная позиция, точный комментарий). Никаких добавлений/обобщений вне ТЗ.
- **`uv lock` (а не `uv lock --upgrade`).** План просит регенерировать lockfile под новый constraint, не апгрейдить пакеты. `uv lock` корректно проверяет совместимость существующих pinned versions с новым constraint и ничего не двигает, если уже всё в диапазоне.

## Threat Model Compliance

Все три задокументированных threats из плана `<threat_model>` покрыты:

- **T-05.01-01 (Tampering, uv.lock):** Mitigated — `redis>=5,<6` блокирует major-bump; `uv lock --check` остаётся зелёным.
- **T-05.01-02 (Information disclosure, .env.example):** Accepted — `SEED_OWNER_*` оставлены как placeholders без значений.
- **T-05.01-03 (Repudiation, refresh_reuse_window_seconds):** Accepted — non-secret env-driven config, audit через git history.

## Threat Flags

None — изменения чисто конфигурационные, не вводят новой security surface.

## Known Stubs

None — все добавленные поля несут реальные default-значения и подключены к pydantic-settings env loading.

## Tasks Completed

| Task | Name                                                  | Commit  | Files                                           |
|------|-------------------------------------------------------|---------|-------------------------------------------------|
| 1    | Narrow redis pin and document Phase 5 env vars        | f2c8f71 | pyproject.toml, uv.lock, .env.example           |
| 2    | Add refresh_reuse_window_seconds to Settings          | 4b0b637 | app/core/config.py                              |

## Self-Check: PASSED

- [x] `apps/backend/pyproject.toml` exists and contains `redis>=5,<6`
- [x] `apps/backend/uv.lock` exists and `uv lock --check` exits 0
- [x] `apps/backend/.env.example` exists with three new env var lines
- [x] `apps/backend/app/core/config.py` exists with `refresh_reuse_window_seconds: int = 5`
- [x] Commit `f2c8f71` exists in git log
- [x] Commit `4b0b637` exists in git log
