---
phase: 02-backend-skeleton-with-quality-tooling
plan: 05
subsystem: backend
tags: [backend, integrations, workers, arq, telegram, email, placeholders, python]

requires:
  - phase: 02-backend-skeleton-with-quality-tooling
    plan: 02
    provides: "apps/backend/.venv with arq + pydantic-settings importable"
provides:
  - "app.integrations namespace package + telegram/email subpackages (INT-01, INT-02)"
  - "app.integrations.telegram.{bot,handlers,sender} — docstring-only placeholders, no aiogram"
  - "app.integrations.email.client + email/templates/.gitkeep — docstring-only placeholder, no SMTP"
  - "app.workers namespace + real ARQ WorkerSettings (WORK-01) with empty functions list + RedisSettings.from_dsn"
  - "app.workers.scheduler + workers.tasks.{notifications,reminders,reports} — docstring-only placeholders (WORK-02, WORK-03)"
  - "Stable import target `app.workers.arq_app.WorkerSettings` for future `arq` CLI invocation"
affects:
  - "Plan 02-08 (import-linter `integrations-not-depend-on-modules` contract has a real namespace to enforce)"
  - "Future Phase B+ tasks plug into WorkerSettings.functions without restructuring the import path"

tech-stack:
  added: []
  patterns:
    - "Docstring-only placeholders for adapter modules — no business logic, no third-party imports (no aiogram, smtplib, aiosmtplib)"
    - "Real ARQ WorkerSettings as a class-level config (ARQ canonical pattern); functions typed as ClassVar[list[Any]] to satisfy ruff RUF012 + mypy strict"
    - "RedisSettings.from_dsn(str(get_settings().redis_url)) — str() cast required because pydantic v2 RedisDsn is not a plain string"
    - "get_settings() called at module import time in arq_app.py — fail-fast on missing REDIS_URL (intentional; ARQ worker process needs Redis to run anyway)"
    - ".gitkeep convention reused for empty integrations/email/templates/ (matches infra/docker/.gitkeep from Phase 1)"

key-files:
  created:
    - "apps/backend/app/integrations/__init__.py (D-03/D-04 namespace docstring; references integrations-not-depend-on-modules contract)"
    - "apps/backend/app/integrations/telegram/__init__.py (Phase X+ aiogram TODO marker)"
    - "apps/backend/app/integrations/telegram/bot.py (Phase X+ aiogram entry placeholder + RU/CIS region note)"
    - "apps/backend/app/integrations/telegram/handlers.py (Phase X+ /start, /link_account placeholder)"
    - "apps/backend/app/integrations/telegram/sender.py (Phase X+ outbound sender placeholder)"
    - "apps/backend/app/integrations/email/__init__.py (Phase X+ SMTP namespace placeholder)"
    - "apps/backend/app/integrations/email/client.py (Phase X+ aiosmtplib/transactional adapter placeholder)"
    - "apps/backend/app/integrations/email/templates/.gitkeep (zero-byte tracker for templates/ dir)"
    - "apps/backend/app/workers/__init__.py (D-03 namespace docstring; events bus deferred)"
    - "apps/backend/app/workers/arq_app.py (real ARQ WorkerSettings — only non-placeholder file in plan)"
    - "apps/backend/app/workers/scheduler.py (Phase B+ cron_jobs/APScheduler placeholder)"
    - "apps/backend/app/workers/tasks/__init__.py (Phase A: all empty placeholders)"
    - "apps/backend/app/workers/tasks/notifications.py (Phase B+ send_telegram_message/send_email placeholder)"
    - "apps/backend/app/workers/tasks/reminders.py (Phase B+ visit-reminder/expiry-alert placeholder)"
    - "apps/backend/app/workers/tasks/reports.py (Phase B+ daily/monthly report placeholder)"
  modified: []
  deleted: []

key-decisions:
  - "Wrapped functions attr in `ClassVar[list[Any]]` instead of plan-spec literal `list[Any] = []` — ruff RUF012 (mutable default class attribute) is enabled via the RUF rule family (locked in Plan 01 ruff.toml). ClassVar is the canonical fix per ruff's hint and is semantically correct: ARQ's WorkerSettings is a class-level config, not instance state."
  - "Evaluated `get_settings()` at module import time in arq_app.py — chose fail-fast over lazy. ARQ worker process needs REDIS_URL set anyway; surfacing config errors at import (rather than at first task dispatch) is preferable. Cost: importing app.workers.arq_app without env vars raises pydantic ValidationError. Plan 08's smoke checks need env vars set; mypy/ruff don't execute the module body so they're unaffected."
  - "All adapter modules are docstring-only — no `def`, no `class`, no third-party imports (aiogram, smtplib, aiosmtplib are NOT in pyproject dependencies; importing them would fail uv sync). This is the same convention from Plan 04 module placeholders, applied uniformly to integrations + worker tasks."

requirements-completed: [INT-01, INT-02, WORK-01, WORK-02, WORK-03]

duration: ~2m 21s
completed: 2026-04-30
---

# Phase 2 Plan 05: Integration & Worker Placeholders Summary

**Created the full `app.integrations.*` and `app.workers.*` namespaces (15 files): 7 docstring-only adapter placeholders (telegram bot/handlers/sender + email client + 2 namespace inits + .gitkeep), the only real code in the plan being a 3-line ARQ `WorkerSettings` skeleton in `app/workers/arq_app.py` that wires `RedisSettings.from_dsn(str(get_settings().redis_url))` and reserves an empty `ClassVar[list[Any]]` functions list — locking in import-linter's `integrations-not-depend-on-modules` contract surface and the ARQ worker entry path before any real adapter or task code lands in Phase B+.**

## Performance

- **Duration:** ~2m 21s
- **Started:** 2026-04-30T19:48:32Z
- **Completed:** 2026-04-30T19:50:53Z
- **Tasks:** 2
- **Files created:** 15
- **Quality-gate iterations:** 1 (ruff RUF012 fix on arq_app.py — added `ClassVar` wrapper)

## Accomplishments

- Created `apps/backend/app/integrations/__init__.py` with a docstring documenting D-03/D-04 (modules + workers may import integrations; integrations must not import from app.modules.*) and naming the import-linter contract that enforces it.
- Created the telegram subpackage (`telegram/__init__.py`, `bot.py`, `handlers.py`, `sender.py`) — every file is a pure docstring with `TODO Phase X+` markers. `bot.py` carries the RU/CIS region note from CLAUDE.md (Telegram = primary auth + notifications channel). `sender.py` documents the future call-site (`app.workers.tasks.notifications`).
- Created the email subpackage (`email/__init__.py`, `email/client.py`) with the same convention. `client.py` notes the choice between `aiosmtplib` and a transactional provider (TBD by region constraints).
- Tracked the empty `email/templates/` directory with a zero-byte `.gitkeep` — same convention as Phase 1's `infra/docker/.gitkeep`.
- Created `app/workers/arq_app.py` with the only non-placeholder code in the plan: a `WorkerSettings` class with `functions: ClassVar[list[Any]] = []` and `redis_settings = RedisSettings.from_dsn(str(get_settings().redis_url))`. The import path stabilizes so a future `arq app.workers.arq_app.WorkerSettings` invocation works once tasks land.
- Created `app/workers/scheduler.py` and 3 task module placeholders (`tasks/notifications.py`, `tasks/reminders.py`, `tasks/reports.py`) plus `tasks/__init__.py` — all docstring-only with `TODO Phase B+` markers naming the future task functions.
- Verified zero forbidden imports: `grep -rE '^(import|from)\s+(aiogram|smtplib|aiosmtplib|email\.mime)' app/integrations/` returns nothing.
- All 15 files pass `uv run ruff check app/`, `uv run ruff format --check app/`, and `uv run mypy app` (38 source files, was 31 after Plan 04).

## Task Commits

1. **Task 1: integrations namespace + telegram + email placeholders + .gitkeep (8 files)** — `55d9157` (feat)
2. **Task 2: workers namespace + ARQ WorkerSettings + scheduler + tasks placeholders (7 files)** — `42ca5fb` (feat)

**Plan metadata commit:** _to follow this SUMMARY (docs)_

## Quality Gate Results

| Gate | Command | Result |
|------|---------|--------|
| Smoke import (integrations) | `uv run python -c "from app.integrations import telegram, email; from app.integrations.telegram import bot, handlers, sender; from app.integrations.email import client"` | OK |
| Smoke import (arq_app, env-set) | `DATABASE_URL=… REDIS_URL=… SECRET_KEY=… uv run python -c "from app.workers.arq_app import WorkerSettings; assert WorkerSettings.functions == []"` | OK |
| Smoke import (worker placeholders, no env) | `uv run python -c "from app.workers import scheduler; from app.workers.tasks import notifications, reminders, reports"` | OK |
| Forbidden import scan | `grep -rE '^(import\|from)\s+(aiogram\|smtplib\|aiosmtplib\|email\.mime)' app/integrations/` | (none) |
| Spec-grep: WorkerSettings shape | `grep -q 'class WorkerSettings:' app/workers/arq_app.py && grep -q 'RedisSettings.from_dsn' …` | OK |
| Spec-grep: ClassVar typing | `grep -q 'functions: ClassVar\[list\[Any\]\] = \[\]' app/workers/arq_app.py` | OK |
| Spec-grep: typing imports | `grep -q 'from typing import Any, ClassVar' app/workers/arq_app.py` | OK |
| Spec-grep: no def/class in placeholders | `grep -lE '^(def \|class )' …integrations/{*.py,telegram/*.py,email/*.py} workers/scheduler.py workers/tasks/{__init__,notifications,reminders,reports}.py` | (none) |
| Ruff lint | `uv run ruff check app` | All checks passed! (after ClassVar fix) |
| Ruff format | `uv run ruff format --check app` | 38 files already formatted |
| mypy strict + pydantic plugin | `uv run mypy app` | Success: no issues found in 38 source files |
| .gitkeep is zero bytes | `wc -c < app/integrations/email/templates/.gitkeep` | `0` |

All plan-level `<verification>` block commands pass:
- 15 files exist — VERIFIED
- arq_app.py import succeeds with env set — VERIFIED
- Placeholder files import without env — VERIFIED
- No forbidden adapter imports under app/integrations/ — VERIFIED
- All files mypy-strict clean — VERIFIED (full mypy run)

All acceptance criteria from both tasks satisfied (modulo the documented ClassVar deviation, see below).

## Decisions Made

- **`ClassVar[list[Any]]` over plan-spec `list[Any]`** — The plan-spec literal `functions: list[Any] = []` triggered ruff `RUF012` (Mutable default value for class attribute). RUF is enabled via the `RUF` rule family in `apps/backend/ruff.toml` (locked in Plan 01). The canonical fix per ruff's own hint is `typing.ClassVar`, which is also semantically correct: ARQ's `WorkerSettings` is a class-level configuration container (the `arq` CLI introspects it as a class, not as an instance), so its attributes ARE class variables, not instance state. The acceptance-criteria literal regex `'functions: list\[Any\] = \[\]'` no longer matches, but the requirement intent (`functions` is an empty list, typed for mypy strict) is fully satisfied.
- **Module-import-time `get_settings()` evaluation in arq_app.py** — `redis_settings = RedisSettings.from_dsn(str(get_settings().redis_url))` runs at import time, meaning `app.workers.arq_app` cannot be imported without REDIS_URL/DATABASE_URL/SECRET_KEY in the environment. This is intentional: the ARQ worker process needs Redis to run anyway, and failing fast at import surfaces config errors before any task dispatch. Trade-offs: (a) Plan 08's import-linter / mypy / ruff smoke checks are unaffected (those tools don't execute module bodies), (b) a future runtime smoke test must set env vars or stub `get_settings`. Documented in arq_app.py's module docstring.
- **`str()` cast on `get_settings().redis_url`** — `Settings.redis_url: RedisDsn` is a pydantic v2 typed value, not a plain string; `RedisSettings.from_dsn` expects `str`. The cast is verified safe because Settings instantiation already validated the URL format. Without the cast, mypy strict would reject the call signature (RedisDsn → str mismatch).
- **All adapter modules docstring-only** — No `def`, no `class`, no third-party imports under `app/integrations/`. The relevant third-party packages (`aiogram`, `smtplib`, `aiosmtplib`) are NOT in `pyproject.toml`'s dependencies; an `import aiogram` would crash `uv sync` consumers. This matches Plan 04's module placeholder convention.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Linter] Added `ClassVar` wrapper to `WorkerSettings.functions` typing**
- **Found during:** Task 2, `uv run ruff check app/workers/`
- **Issue:** `RUF012 Mutable default value for class attribute` on `functions: list[Any] = []`. The RUF rule family is enabled in `ruff.toml`; this rule has been on since Plan 01 and was not anticipated by the plan author. The ruff hint suggests `Consider initializing in __init__ or annotating with typing.ClassVar`.
- **Fix:** Changed `from typing import Any` to `from typing import Any, ClassVar` and `functions: list[Any] = []` to `functions: ClassVar[list[Any]] = []`. ARQ's `WorkerSettings` IS a class-level config (the `arq` CLI introspects the class itself, not an instance), so `ClassVar` is semantically correct, not just a lint-suppression hack.
- **Files modified:** `apps/backend/app/workers/arq_app.py`
- **Commit:** `42ca5fb` (folded into Task 2's single commit since the fix happened before commit)
- **Acceptance-criteria impact:** The strict regex `'functions: list\[Any\] = \[\]'` from `<acceptance_criteria>` no longer matches. Replaced by the equivalent intent-check `'functions: ClassVar\[list\[Any\]\] = \[\]'` (verified above). No behavior change — `WorkerSettings.functions == []` and `WorkerSettings.functions` is still typed as a list of `Any`.

This is a linter-driven typing tightening, not a functional change. The plan-spec text predates RUF012's enablement awareness; the fix preserves WORK-01's intent (empty `functions` list, typed for mypy strict).

## Issues Encountered

None beyond the single RUF012 fix above. No surprises with `RedisSettings.from_dsn` (the Context7-verified API in RESEARCH.md Pattern 9), no surprises with pydantic v2 `RedisDsn` requiring a `str()` cast (RESEARCH.md mypy gotcha line 1049 anticipated bare-list issue but not RUF012). The fail-fast `get_settings()` at module import time is intentional and documented in-file.

## User Setup Required

None for plan execution. **For future smoke tests of `app.workers.arq_app`:** Set `DATABASE_URL`, `REDIS_URL`, `SECRET_KEY` env vars (any valid format strings — connectivity is not checked at import). This is already documented in `apps/backend/.env.example` from Plan 01.

## Threat Surface Scan

Plan-05 introduces no new runtime trust boundaries beyond what the threat model in 02-05-PLAN.md already covers:
- T-02-11 (Tampering: REDIS_URL injection at import time) — accept, mitigated: `RedisSettings.from_dsn` validates URL shape, no network call until tasks land. The `str()` cast on a pydantic-validated `RedisDsn` does not weaken validation.
- T-02-12 (Information Disclosure: telegram/email placeholders contain region notes) — accept: comments document RU/CIS region constraint per CLAUDE.md, no PII or secrets in any placeholder.

No new surface introduced. All 14 placeholder files are pure docstrings with no executable logic; only `arq_app.py` runs code at import time, and that code is bounded to URL parsing.

## Next Phase Readiness

- **Plan 02-06** can wire FastAPI router registration without colliding with workers/integrations imports.
- **Plan 02-07** (alembic) and **Plan 02-08** (import-linter) have a real `app.integrations` namespace to enforce contracts against (`integrations-not-depend-on-modules` from Plan 01's `importlinter.ini`).
- **Future Phase B+** tasks plug into `WorkerSettings.functions` without restructuring the worker import path. The `arq app.workers.arq_app.WorkerSettings` CLI command will work once any task is appended to the list.

## Self-Check

Verifying claims before final commit:

**Created files (all 15):**
- `apps/backend/app/integrations/__init__.py` — FOUND
- `apps/backend/app/integrations/telegram/__init__.py` — FOUND
- `apps/backend/app/integrations/telegram/bot.py` — FOUND
- `apps/backend/app/integrations/telegram/handlers.py` — FOUND
- `apps/backend/app/integrations/telegram/sender.py` — FOUND
- `apps/backend/app/integrations/email/__init__.py` — FOUND
- `apps/backend/app/integrations/email/client.py` — FOUND
- `apps/backend/app/integrations/email/templates/.gitkeep` — FOUND (0 bytes)
- `apps/backend/app/workers/__init__.py` — FOUND
- `apps/backend/app/workers/arq_app.py` — FOUND
- `apps/backend/app/workers/scheduler.py` — FOUND
- `apps/backend/app/workers/tasks/__init__.py` — FOUND
- `apps/backend/app/workers/tasks/notifications.py` — FOUND
- `apps/backend/app/workers/tasks/reminders.py` — FOUND
- `apps/backend/app/workers/tasks/reports.py` — FOUND

**Commits:**
- `55d9157` (Task 1 — integrations namespace + telegram/email placeholders + .gitkeep)
- `42ca5fb` (Task 2 — workers namespace + ARQ WorkerSettings + tasks/scheduler placeholders, RUF012 fix folded in)

**Quality gates:**
- `uv run ruff check app` — exit 0, "All checks passed!"
- `uv run ruff format --check app` — exit 0, "38 files already formatted"
- `uv run mypy app` — exit 0, "Success: no issues found in 38 source files"
- Forbidden import scan (`grep -rE '^(import|from)\s+(aiogram|smtplib|aiosmtplib|email\.mime)' app/integrations/`) — VERIFIED (none)
- WorkerSettings shape grep — VERIFIED (`class WorkerSettings:`, `RedisSettings.from_dsn`, `from typing import Any, ClassVar`, `functions: ClassVar[list[Any]] = []`)
- Smoke import with env — VERIFIED (`WorkerSettings.functions == []`)
- Smoke import without env (placeholders only) — VERIFIED

## Self-Check: PASSED

---

*Phase: 02-backend-skeleton-with-quality-tooling*
*Completed: 2026-04-30*
