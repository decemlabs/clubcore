---
phase: 20-telegram-bot-checkin-self-check-in
plan: 02
subsystem: integrations
tags:
  - telegram
  - bot
  - worker
  - importlinter
  - dedup
  - redis

# Dependency graph
requires:
  - phase: 07-telegram-otp-channel
    provides: HandlerContext NamedTuple shape, build_application factory, redis_lifespan_manager, D-06 workers->modules.auth.telegram_service relaxation precedent
  - phase: 19-visits-db-reception-check-in-backend
    provides: app.modules.visits.service.create_visit_self_checkin (consumed via D-10 import in worker process boot)
  - phase: 20-telegram-bot-checkin-self-check-in/01
    provides: HandlerContext extension (visits_service + redis fields), checkin_handler symbol — wired by THIS plan into the worker boot
provides:
  - Wave-1 worker-side wiring of /checkin
  - D-10 narrative addendum in app/workers/telegram_bot.py module docstring (workers MAY import owning modules — auth.telegram_service AND visits.service)
  - Verified .importlinter still passes (3/3 contracts kept) with the new D-10 edge live
affects:
  - 20-03 (tests rely on the worker registering both ('start', start_handler) and ('checkin', checkin_handler))
  - any future phase adding a third bot command (will copy this 5-field HandlerContext + handlers.append shape)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "D-10: worker imports a second owning module's service layer (visits.service) parallel to the existing D-06 auth.telegram_service edge — narrative addendum in module docstring, no .importlinter contract change required because no `workers ⊥ modules` contract exists"
    - "Renaming a held-resource variable (_redis -> redis) once it stops being purely a lifecycle handle and starts being a consumed dependency — keeps Python `_`-prefix-as-private-marker convention honest"

key-files:
  created: []
  modified:
    - apps/backend/app/workers/telegram_bot.py

key-decisions:
  - "No `workers ⊥ modules` import-linter contract exists in the project (Phase 7 D-06 precedent); the new D-10 edge needs ZERO contract change — verified by running `lint-imports` after the source change"
  - "The redis client yielded from `redis_lifespan_manager()` is now passed into HandlerContext.redis (rename _redis -> redis), enabling the in-handler `sz:bot:update:{update_id}` SET-NX-EX dedup that 20-01 implements"

patterns-established:
  - "Worker boot wires N handlers via build_application(handlers=[(name, fn), ...]) — extending the list is a 1-line change; no factory churn"
  - "Cross-worktree wave-1 coordination: 20-01 ships handlers.py extension symbols; 20-02 imports them at the worker; both worktrees are merged together by the orchestrator before CI sees a consistent state"

requirements-completed:
  - AUTH-TG-09
  - AUTH-TG-10

# Metrics
duration: 7min
completed: 2026-05-08
---

# Phase 20 Plan 02: Wire D-10 visits.service + checkin_handler into bot worker — Summary

**Bot worker now registers both `/start` and `/checkin` ptb command handlers; D-10 visits.service relaxation imported parallel to D-06 auth.telegram_service; HandlerContext constructed with all 5 kwargs; lint-imports stays at 3/3 kept with no contract change.**

## Performance

- **Duration:** ~7 min
- **Started:** 2026-05-08T00:00:00Z (executor agent spawn)
- **Completed:** 2026-05-08T00:07:00Z
- **Tasks:** 2 (1 source-modify + 1 verification)
- **Files modified:** 1

## Accomplishments

- `apps/backend/app/workers/telegram_bot.py` extended:
  - Module docstring rewritten to cover BOTH D-06 (`auth.telegram_service`) and D-10 (`visits.service`) workers→modules relaxations.
  - Handlers import block rewritten as a multi-name import: `from app.integrations.telegram.handlers import (HandlerContext, checkin_handler, start_handler)`.
  - New D-10 import line added directly under the existing D-06 line: `from app.modules.visits import service as visits_service  # D-10 relaxation`.
  - The held-open redis variable renamed `_redis` → `redis` (it's no longer purely a lifecycle handle — it now flows into `HandlerContext.redis`).
  - `HandlerContext(...)` constructed with all 5 kwargs: `session_factory`, `telegram_service`, `sender`, `visits_service`, `redis`.
  - `build_application(handlers=[("start", start_handler), ("checkin", checkin_handler)], ...)` registers the second command.
- `apps/backend/.importlinter` was NOT modified — `lint-imports` continues to pass at `3 kept, 0 broken` with the new D-10 edge live, exactly as predicted by 20-CONTEXT.md (no `workers ⊥ modules` contract exists in the project).

## Task Commits

Each task was committed atomically with `--no-verify` (parallel-worktree execution):

1. **Task 1: Wire D-10 import + 5-field HandlerContext + checkin handler in telegram_bot.py** — `e2c8b6a` (feat)
2. **Task 2: Verify .importlinter passes with the D-10 edge — extend only if needed** — verification-only; no file change, no commit. Documented inline in this SUMMARY.

## Files Created/Modified

- `apps/backend/app/workers/telegram_bot.py` (MODIFIED, +15 / −6 lines):
  - L1–13: docstring rewrite
  - L30–34: multi-name import of handlers
  - L36: D-10 visits.service import
  - L63: rename `_redis` → `redis`
  - L65–71: 5-kwarg HandlerContext
  - L74: handlers list extension

## Decisions Made

- **No `.importlinter` modification.** Confirmed empirically by running `lint-imports` after the source change: `Contracts: 3 kept, 0 broken`. The plan's "default expected case" held — no `workers ⊥ modules` contract exists, so the D-10 edge needs no contract relaxation. The narrative documentation of D-10 lives in the worker module's docstring (Task 1).

## Deviations from Plan

None — plan executed exactly as written.

The only execution-time observation worth flagging is a documented wave-coordination artifact (NOT a deviation):

- **mypy fails in this worktree alone, by design.** Running `cd apps/backend && uv run mypy app/workers/telegram_bot.py` reports 3 errors:
  - `Module "app.integrations.telegram.handlers" has no attribute "checkin_handler"`
  - `Unexpected keyword argument "visits_service" for "HandlerContext"`
  - `Unexpected keyword argument "redis" for "HandlerContext"`

  These three errors are EXPECTED in this worktree alone because the symbols and HandlerContext fields they reference are created by sibling plan **20-01** (which extends `apps/backend/app/integrations/telegram/handlers.py`) running in a parallel worktree. The plan's `<wave_coordination_note>` (lines 114–120) explicitly anticipates this: "20-01 and 20-02 are both Wave 1 with NO file overlap... they can be executed in parallel by `/gsd-execute-phase`. However, 20-02 imports the symbols (`checkin_handler`, the new HandlerContext fields) that 20-01 creates." The orchestrator's worktree merge restores a consistent state before CI runs phase-level mypy.

  The acceptance criterion `cd apps/backend && uv run python -c "from app.workers.telegram_bot import main; print('importable')"` likewise depends on 20-01 merging first; it is intentionally verified at the post-merge phase-verification step (20-VERIFICATION.md), not here.

  **`ruff check app/workers/telegram_bot.py` passes cleanly** (no false positives that worry about a sibling worktree's symbols).

## Acceptance Criteria — Evidence

Task 1:

```
$ grep -F 'from app.modules.visits import service as visits_service  # D-10 relaxation' apps/backend/app/workers/telegram_bot.py
from app.modules.visits import service as visits_service  # D-10 relaxation

$ grep -F 'checkin_handler,' apps/backend/app/workers/telegram_bot.py
    checkin_handler,

$ grep -F 'visits_service=visits_service' apps/backend/app/workers/telegram_bot.py
            visits_service=visits_service,

$ grep -F 'redis=redis' apps/backend/app/workers/telegram_bot.py
            redis=redis,

$ grep -Pzo '\("start",\s*start_handler\)\s*,\s*\("checkin",\s*checkin_handler\)' apps/backend/app/workers/telegram_bot.py
("start", start_handler), ("checkin", checkin_handler)

$ grep -cE '_redis = await stack\.enter_async_context\(redis_lifespan_manager' apps/backend/app/workers/telegram_bot.py
0   # rename complete

$ grep -E 'redis = await stack\.enter_async_context\(redis_lifespan_manager' apps/backend/app/workers/telegram_bot.py
        redis = await stack.enter_async_context(redis_lifespan_manager())

$ cd apps/backend && uv run ruff check app/workers/telegram_bot.py
All checks passed!
```

Task 2 (literal `lint-imports` stdout):

```
$ cd apps/backend && uv run lint-imports
---------
Contracts
---------

Analyzed 70 files, 139 dependencies.
------------------------------------

core must not import modules KEPT
modules cannot import each other KEPT
integrations must not import modules KEPT

Contracts: 3 kept, 0 broken.

$ grep -c '^name = ' apps/backend/.importlinter
3
$ git diff --stat apps/backend/.importlinter
(no diff — file byte-identical to pre-Phase-20 state)
```

## Issues Encountered

None.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- The bot worker boot is now complete on the wiring side. Once 20-01's handlers.py extension lands in the same merge, `python -m app.workers.telegram_bot` will register both `/start` and `/checkin` and pass the runtime `HandlerContext` (with `visits_service` + `redis`) into both adapters.
- 20-03 (tests) can rely on:
  - `HandlerContext._fields` containing `visits_service` and `redis` (regression guard).
  - `build_application(handlers=[("start", start_handler), ("checkin", checkin_handler)], ctx=...)` producing an `Application` whose `.handlers` exposes both `CommandHandler`s.
- No blockers for 20-03; no architectural changes needed.

## Self-Check: PASSED

- File `apps/backend/app/workers/telegram_bot.py` exists and contains all D-10 / HandlerContext / handlers-list edits — verified via `grep` output above.
- File `apps/backend/.importlinter` exists and is byte-identical to its pre-Phase-20 state (3 contracts, no diff) — verified via `grep -c '^name = '` and `git status --short`.
- Commit `e2c8b6a` exists in `git log` — verified.
- `lint-imports` exits 0 with `Contracts: 3 kept, 0 broken` — verified.
- `ruff check app/workers/telegram_bot.py` exits 0 — verified.
- Documented wave-coordination artifact (mypy errors due to 20-01 living in a sibling worktree) is captured under "Deviations from Plan" with explicit reference to the plan's `<wave_coordination_note>`.

---
*Phase: 20-telegram-bot-checkin-self-check-in*
*Plan: 02*
*Completed: 2026-05-08*
