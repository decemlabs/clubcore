---
phase: 18-arq-scheduled-expire-memberships
plan: 03
subsystem: backend
tags: [backend, arq, workers, settings, contextvars, mypy-strict]

# Dependency graph
requires:
  - phase: 18-arq-scheduled-expire-memberships
    provides: "Plan 18-02 — async def expire_memberships(ctx) -> int worker entry coroutine in app/workers/scheduled/expire_memberships.py"
  - phase: 7-telegram-bot-worker
    provides: "D-06 worker -> owning-module exception template + AsyncExitStack/db_lifespan_manager pattern in app/workers/telegram_bot.py"
  - phase: 4-foundations-db-mixins
    provides: "db_lifespan_manager() context manager yielding (engine, sessionmaker)"
provides:
  - "app/workers/__init__.py — real WorkerSettings class importable as app.workers.WorkerSettings (the path docker-compose `command: uv run arq app.workers.WorkerSettings` will use in Plan 18-04)"
  - "WorkerSettings.on_startup cron-resolution invariant (Pitfall 4 step 6) — fails LOUD at worker boot if any cron_jobs entry's coroutine name is missing from functions"
  - "WorkerSettings.on_job_start / on_job_end structlog contextvars binding (job_id, job_name) — direct mirror of RequestIdMiddleware shape (Pitfall 14)"
  - "Single canonical ARQ entrypoint (CD-01 + ARQ-04 cleanup): arq_app.py + scheduler.py placeholders DELETED; only one import path remains"
affects: [18-04 docker-compose arq-worker service references this WorkerSettings, 18-05 integration tests exercise expire_memberships through the same ctx shape on_startup populates, 18-06 verification asserts the cron-resolution invariant + contextvars hooks]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "ARQ WorkerSettings class — class-attribute-only, ARQ reads via introspection (never instantiates); ClassVar[list[Any]] annotations satisfy mypy strict against ARQ's untyped heterogeneous lists"
    - "Cron-resolution invariant in on_startup — `assert not (cron_function_names - function_names)` BEFORE opening DB lifespan so a typo at the registration site fails LOUD at boot rather than silently producing zero ticks at 06:05 (Pitfall 4 step 6)"
    - "AsyncExitStack stashed in ctx['_db_stack'] — survives on_startup return; on_shutdown defensively closes only if present (handles on_startup raising before stack creation)"
    - "structlog contextvars in worker hooks — clear_contextvars() THEN bind_contextvars(job_id, job_name) on_job_start (mirror of RequestIdMiddleware), clear_contextvars() on_job_end (prevents cross-run leak in same asyncio task)"
    - "Locked summary log shape `<job_name>_complete count=N` carries job_id+job_name automatically via merge_contextvars (proven downstream of on_job_start binding)"

key-files:
  created: []
  modified:
    - "apps/backend/app/workers/__init__.py — replaced 16-line placeholder docstring with 142-line module containing real WorkerSettings class + extended D-06/D-09 narrative + Pitfall 4 step 6 + Pitfall 14 rationale"
    - "apps/backend/docs/architecture.md — refreshed app.workers section: now documents app.workers.WorkerSettings as canonical entrypoint and notes scheduled/<job>.py layout (was: stale references to deleted arq_app.py)"
    - "apps/backend/docs/conventions.md — replaced arq_app.py snake_case example with expire_memberships.py (since arq_app.py was deleted)"
  deleted:
    - "apps/backend/app/workers/arq_app.py — placeholder duplicate (CD-01); ARQ-03 locks the canonical class to live in __init__.py"
    - "apps/backend/app/workers/scheduler.py — placeholder superseded by cron_jobs on WorkerSettings (REQUIREMENTS-locked ARQ-04)"

key-decisions:
  - "Rule 4 deviation: plan locked `keep_cronjob_progress=60` from ARQ 0.26 docs, but installed arq is 0.28.0 (uv.lock; pyproject pin `>=0.26`) which removed that parameter. Replaced with `keep_result=60` — the closest 0.28 semantic equivalent (Redis result-retention TTL bounding the per-tick tracking key lifetime that backs `unique=True`). Documented inline in WorkerSettings.cron_jobs comment + this SUMMARY's Deviations section. User should review at 18-VERIFICATION."
  - "WorkerSettings.cron_jobs[0].name in ARQ 0.28 returns `\"cron:expire_memberships\"` (prefixed) — NOT `\"expire_memberships\"`. The plan's own internal verify line `assert WorkerSettings.cron_jobs[0].name == 'expire_memberships'` would fail; the prompt's success criteria correctly use `.coroutine.__name__` (which DOES return `\"expire_memberships\"`). Used `.coroutine.__name__` everywhere — matches both the cron-resolution invariant and the prompt's locked check."
  - "Cron-resolution invariant runs BEFORE opening db_lifespan_manager — fail-fast saves a connection-pool leak on misconfigured WorkerSettings"
  - "on_shutdown defensively reads `ctx.get('_db_stack')` — handles the case where on_startup raises BEFORE stashing the stack (the assert-fail path)"

patterns-established:
  - "Pattern: Class-attribute-only WorkerSettings — ARQ never instantiates; ClassVar[...] satisfies mypy strict against the heterogeneous `functions`/`cron_jobs` lists"
  - "Pattern: structlog contextvars binding in worker job-lifecycle hooks (on_job_start/on_job_end) — direct shape-mirror of HTTP RequestIdMiddleware so audit + summary log lines carry job_id/job_name the same way request_id/path/method flow on the HTTP side"
  - "Pattern: import-path canonicalization — single class definition + zero-cost re-export OR deletion of the duplicate; no two paths to the same class (CD-01 default)"

requirements-completed: [ARQ-03, ARQ-04, ARQ-05]

# Metrics
duration: 5min
completed: 2026-05-07
---

# Phase 18 Plan 03: ARQ WorkerSettings + placeholder cleanup Summary

**Real `WorkerSettings` class shipped at `app.workers.WorkerSettings` — registers `expire_memberships` as both a callable AND a cron entry (06:05 Europe/Moscow with container `TZ=UTC`), opens DB lifespan via `AsyncExitStack`, asserts cron-resolution invariant at startup (Pitfall 4 step 6), binds/clears `job_id`+`job_name` on structlog contextvars per job (Pitfall 14 RequestIdMiddleware mirror); placeholder `arq_app.py` + `scheduler.py` deleted (CD-01 + ARQ-04) so there is exactly one canonical import path for the ARQ entrypoint.**

## Performance

- **Duration:** ~5 min
- **Started:** 2026-05-07T18:49:50Z
- **Completed:** 2026-05-07T18:54:43Z
- **Tasks:** 2 (Task 1 replace `__init__.py` + Task 2 delete placeholders)
- **Files modified:** 4 (1 source, 2 docs, 0 created); **Files deleted:** 2

## Accomplishments

- `apps/backend/app/workers/__init__.py` rewritten: 16-line placeholder docstring → 142-line module with real `WorkerSettings` class. Module docstring extended to document **D-06** (telegram_bot exception, preserved verbatim) + **D-09** (scheduled cron exception, NEW prose) + the `RequestIdMiddleware`-mirror rationale for the `on_job_start`/`on_job_end` hooks. Class implements:
  - `redis_settings = RedisSettings.from_dsn(str(get_settings().redis_url))` — class attribute (mypy infers `RedisSettings`).
  - `functions: ClassVar[list[Any]] = [expire_memberships]` — every callable ARQ may invoke.
  - `cron_jobs: ClassVar[list[Any]] = [cron(expire_memberships, hour=3, minute=5, unique=True, keep_result=60)]` — see Deviations §1 for the `keep_result` vs `keep_cronjob_progress` reconciliation.
  - `on_startup(ctx)` runs the cron-resolution invariant (`assert not unresolved`) BEFORE opening `db_lifespan_manager()` via `AsyncExitStack`; stashes the stack in `ctx['_db_stack']`; exposes `engine` + `sessionmaker` at the top of `ctx`; emits `worker_startup_complete` structlog INFO.
  - `on_shutdown(ctx)` defensively reads `ctx.get('_db_stack')` (handles assertion-failure path), calls `await stack.aclose()`, emits `worker_shutdown_complete`.
  - `on_job_start(ctx)` calls `structlog.contextvars.clear_contextvars()` THEN `bind_contextvars(job_id=str(ctx['job_id']), job_name=ctx['function_name'])` — direct shape-mirror of `RequestIdMiddleware`.
  - `on_job_end(ctx)` calls `structlog.contextvars.clear_contextvars()` (Pitfall 14 mitigation step 3 — prevents cross-run leak in the same asyncio task).
- `apps/backend/app/workers/arq_app.py` and `apps/backend/app/workers/scheduler.py` **deleted** — both were Phase A WORK-01 placeholders. Pre-deletion grep verified zero Python imports across `apps/backend/` and `tests/`. Stale prose references in `apps/backend/docs/architecture.md` + `apps/backend/docs/conventions.md` were also refreshed to remove the dangling pointer (Rule 1: stale doc reference to deleted file).
- All quality gates green: mypy strict (`app/workers/` 8 source files clean), ruff (no issues), import-linter (3 contracts kept, 0 broken — D-09 confirmed as documented exception, NOT a contract relaxation), 253 unit tests still pass.

## Task Commits

Each task was committed atomically:

1. **Task 1: Replace `app/workers/__init__.py` with real `WorkerSettings` class** — `c60a998` (feat)
2. **Task 2: Delete `app/workers/scheduler.py` + `app/workers/arq_app.py` placeholders + refresh stale docs** — `af71814` (chore)

Both commits are on `master`; `git log --oneline -3` shows them at HEAD and HEAD~1.

## Files Created/Modified

- **Modified** `apps/backend/app/workers/__init__.py` (16 → 142 lines) — full WorkerSettings class shipped per plan CONCRETE content; one Rule 4 surgical change (`keep_cronjob_progress` → `keep_result`) documented inline as a multi-line comment block above `cron_jobs`.
- **Modified** `apps/backend/docs/architecture.md` lines 33-35 — replaced "ARQ background tasks. `app/workers/arq_app.py` определяет `WorkerSettings` skeleton; `app/workers/tasks/*.py` …" with current Phase 18 state: `app.workers.WorkerSettings` is the canonical entrypoint; `app/workers/scheduled/<job>.py` is the per-job entry layout; placeholder removal noted with phase + plan reference.
- **Modified** `apps/backend/docs/conventions.md` line 7 — swapped `arq_app.py` for `expire_memberships.py` in the snake_case Python module example (since `arq_app.py` no longer exists).
- **Deleted** `apps/backend/app/workers/arq_app.py` (CD-01) — was 26-line placeholder with `functions=[]` skeleton.
- **Deleted** `apps/backend/app/workers/scheduler.py` (ARQ-04) — was 5-line TODO placeholder.

## Decisions Made

All locked-at-plan-time decisions (D-06, D-09, ARQ-03, ARQ-04, CD-01, CD-04, Pitfall 4 step 6, Pitfall 14) were honored verbatim. Two execution-time observations:

1. **Rule 4 deviation: `keep_cronjob_progress=60` → `keep_result=60`** — see Deviations §1 below. The plan's locked-arg list assumed ARQ 0.26 (the version cited in research/PITFALLS), but the installed library is 0.28.0 (uv.lock; pyproject pin is `>=0.26` — a floor, not a cap). 0.28 removed `keep_cronjob_progress`. Replaced with the closest semantic equivalent `keep_result=60` and documented inline at the call-site so a future agent reading the file understands the choice without re-deriving it.

2. **Stale doc cleanup is in-scope as Rule 1** — `apps/backend/docs/architecture.md` and `apps/backend/docs/conventions.md` referenced `arq_app.py` (a file we just deleted). The plan's `<verify>` block did not enumerate doc-grep checks, but leaving stale prose pointing at a deleted file is a Rule 1 issue (stale doc references a non-existent file). Bundled into the Task 2 commit.

## Deviations from Plan

### 1. [Rule 4 — Library version mismatch] `keep_cronjob_progress=60` → `keep_result=60`

- **Found during:** Task 1 (`uv run mypy app/workers/__init__.py` failed with `error: Unexpected keyword argument "keep_cronjob_progress" for "cron"`).
- **Issue:** The plan locks the cron call literal as `cron(expire_memberships, hour=3, minute=5, unique=True, keep_cronjob_progress=60)` per ARQ-03 (REQUIREMENTS-locked) and references "ARQ 0.26" throughout. The installed version per `uv.lock` is `arq==0.28.0` (pyproject pin is `>=0.26`, a floor). ARQ 0.28's `arq.cron.cron()` signature is:
  ```
  cron(coroutine, *, name, month, day, weekday, hour, minute, second, microsecond,
       run_at_startup, unique, job_id, timeout, keep_result, keep_result_forever, max_tries)
  ```
  No `keep_cronjob_progress` parameter. mypy strict rejects the call; runtime would also raise `TypeError`.
- **Fix:** Replaced with `keep_result=60`. Rationale: in ARQ 0.28 the `keep_result` parameter governs how long ARQ retains the cron tick's result data in Redis — which is the same Redis key whose presence ARQ uses to back `unique=True` dedup. The original `keep_cronjob_progress=60` intent (bound the lifetime of ARQ's per-tick tracking key so `unique=True` dedup is not unbounded) is preserved by `keep_result=60`. Inline comment block above `cron_jobs` documents the rename + the user's two follow-up options: (a) accept the rename permanently and update REQUIREMENTS.md ARQ-03 prose; (b) pin `arq` to `<0.27` in `pyproject.toml` and revert to `keep_cronjob_progress=60`. Recommendation: (a) — newer ARQ is forward-friendly, the semantics are equivalent, and downgrading is purely cosmetic.
- **Why Rule 4, not Rule 1/2/3:** This deviates from REQUIREMENTS-locked text (ARQ-03 verbatim per `18-CONTEXT.md` line 19). Per `<deviation_rules>`, that's a Rule 4 architectural-style decision because it changes a literal-locked contract surface. Auto-mode is active (`workflow.auto_advance: true`), so the executor proceeded with the most reasonable resolution and documented loudly here for verifier review (rather than blocking). The Plan 18-VERIFICATION step is the natural review point.
- **Files modified:** `apps/backend/app/workers/__init__.py` (cron call + docstring `cron_jobs` description).
- **Commit:** `c60a998`.

### 2. [Rule 1 — Stale doc references] `apps/backend/docs/architecture.md` + `apps/backend/docs/conventions.md`

- **Found during:** Task 2 pre-deletion grep (`grep -rn "arq_app" apps/backend/`).
- **Issue:** After deleting `apps/backend/app/workers/arq_app.py`, two doc files contained dangling prose references. The plan's `<verify>` clause `! grep -rn "from app.workers.arq_app" apps/backend/ tests/` only matches Python `from`-imports, not markdown prose, so the verify gate would not have caught this. Leaving the stale text would mislead future agents.
- **Fix:**
  - `apps/backend/docs/architecture.md` — rewrote the `app.workers` section to reflect Phase 18 reality (`app.workers.WorkerSettings` canonical, `app/workers/scheduled/<job>.py` layout, placeholder removal noted with phase+plan reference).
  - `apps/backend/docs/conventions.md` line 7 — replaced `arq_app.py` snake_case example with `expire_memberships.py`.
- **Files modified:** 2 (both `apps/backend/docs/`).
- **Commit:** `af71814` (bundled into Task 2 commit since they belong with the deletion).

### 3. [Internal plan inconsistency, non-blocking] `cron_jobs[0].name` returns `"cron:expire_memberships"` in ARQ 0.28

- **Found during:** Task 1 sanity inspection (`uv run python -c "...; print(WorkerSettings.cron_jobs[0].name)"`).
- **Issue:** The plan's `<verify>` line `assert WorkerSettings.cron_jobs[0].name == 'expire_memberships'` would FAIL — in ARQ 0.28, `CronJob.name` is auto-prefixed with `"cron:"`. The prompt's success criteria correctly use `.coroutine.__name__` (which DOES return `"expire_memberships"`). The plan's literal-acceptance criterion `assert WorkerSettings.cron_jobs[0].name == 'expire_memberships'` is a verifier-side bug, not a code-side bug.
- **Fix:** None on the code side — `.coroutine.__name__` is the correct accessor and is what the cron-resolution invariant uses. Reported here for the verifier to update the plan's `<verify>` block (or the verifier may simply skip that single line and use `.coroutine.__name__`).

## Threat Surface Verification

The plan's `<threat_model>` block enumerated 5 threats (T-18-05 through T-18-09). Implementation honors each `mitigate` disposition:

| Threat ID | Disposition | Where mitigated in 18-03 |
|-----------|-------------|--------------------------|
| T-18-05 (cron registration tampering) | mitigate | `on_startup` cron-resolution invariant (`assert not unresolved`) — fails LOUD at boot if cron_jobs references a function name not in `functions`. Verified literal `assert not unresolved` present. |
| T-18-06 (DB pool leak) | mitigate | `on_shutdown` defensively closes `ctx.get('_db_stack')`. ARQ SIGTERM → graceful shutdown → on_shutdown. Verified literal `await stack.aclose()` present. |
| T-18-07 (contextvars leak) | mitigate | `on_job_end` calls `clear_contextvars()`. `on_job_start` also clears BEFORE binding (defence-in-depth: even if a previous job's on_job_end never ran, the next on_job_start clears anyway). Verified literal `structlog.contextvars.clear_contextvars()` present in both hooks. |
| T-18-08 (container TZ drift) | accept-with-test | Compose env block (Plan 18-04 territory) sets `TZ: UTC`. Plan 18-03 deliberately does NOT touch compose; deferred to 18-04 per phase split. |
| T-18-09 (placeholder deletion impact) | mitigate | Pre-deletion grep verified zero references in `apps/backend/` and `tests/`. Post-deletion `import app.workers` + `lint-imports` + `mypy` all green. Stale doc references found and refreshed (Deviation §2). |

No new threat surfaces introduced. The cron-callsite reads `get_settings().redis_url` only at class-definition time (module import), so secret material is not re-read inside the hot loop; the same `redis_url` was already read by the existing FastAPI bootstrap.

## Issues Encountered

- **mypy: `keep_cronjob_progress` not in `cron(...)` signature** — resolved per Deviation §1 above.
- **No other issues.** ruff, lint-imports, and the 253-test unit suite all stayed green throughout.

## User Setup Required

None — purely backend internal Python code. The Rule 4 deviation (Deviation §1) is the only item that needs human review at 18-VERIFICATION time:

> **Reviewer prompt:** "The plan locked `keep_cronjob_progress=60` from ARQ 0.26 docs, but the installed `arq==0.28.0` removed that parameter and replaced it with `keep_result`. The implementation uses `keep_result=60`. Confirm: (a) accept the rename and update REQUIREMENTS.md ARQ-03 prose to reflect the 0.28 API; or (b) pin `arq<0.27` in `pyproject.toml` and revert to `keep_cronjob_progress=60`."

Plan 18-04 will add the `arq-worker` docker-compose service and wire `TZ: UTC` + `DATABASE_URL` + `REDIS_URL`; this plan only ships the Python entrypoint.

## Next Phase Readiness

- **Plan 18-04 (docker-compose `arq-worker` service)** can use `command: uv run arq app.workers.WorkerSettings` directly — the import path is now real and exercised. The `TZ: UTC` env requirement is unchanged.
- **Plan 18-05 (integration tests)** can build `ctx = {"sessionmaker": db_session_factory}` and call `await expire_memberships(ctx)` directly, bypassing ARQ runtime. They can ALSO exercise `WorkerSettings.on_startup({})` against a real DB to confirm the cron-resolution invariant + `(engine, sessionmaker)` population end-to-end.
- **Plan 18-06 (verification)** can grep for the literal `assert not unresolved` (cron-resolution invariant — Pitfall 4 step 6) and `structlog.contextvars.bind_contextvars` (Pitfall 14) — both present at the locations above.
- **No blockers** beyond the Deviation §1 review at 18-VERIFICATION.

## Confirmation: `ls app/workers/` post-deletion

```
$ ls apps/backend/app/workers/
__init__.py
scheduled/
telegram_bot.py
```

(Plus `__pycache__/` ignored.) `arq_app.py` and `scheduler.py` are absent. `__init__.py` is the new 142-line WorkerSettings module; `scheduled/` is Plan 18-02's namespace + `expire_memberships.py`; `telegram_bot.py` is unchanged.

## Self-Check: PASSED

Files exist (or are correctly absent):

- `apps/backend/app/workers/__init__.py` — verified via `test -f` (FOUND).
- `apps/backend/app/workers/scheduler.py` — verified via `test ! -f` (correctly MISSING).
- `apps/backend/app/workers/arq_app.py` — verified via `test ! -f` (correctly MISSING).
- `apps/backend/docs/architecture.md` — verified via `test -f` (FOUND, prose refreshed).
- `apps/backend/docs/conventions.md` — verified via `test -f` (FOUND, prose refreshed).

Commits exist (verified via `git log --oneline -3`):

- `c60a998` — feat(18-03): replace workers/__init__.py with real WorkerSettings — FOUND.
- `af71814` — chore(18-03): delete arq_app.py + scheduler.py placeholders, refresh docs — FOUND.

Acceptance gates run and passed:

- `cd apps/backend && uv run mypy app/workers/` → Success: no issues found in 8 source files.
- `cd apps/backend && uv run ruff check app/workers/__init__.py` → All checks passed!
- `cd apps/backend && uv run lint-imports` → 3 contracts kept, 0 broken.
- `cd apps/backend && uv run python -c "from app.workers import WorkerSettings; assert hasattr(WorkerSettings, 'on_startup') and hasattr(WorkerSettings, 'cron_jobs')"` → exit 0.
- `cd apps/backend && uv run python -c "from app.workers import WorkerSettings; assert WorkerSettings.cron_jobs[0].coroutine.__name__ == 'expire_memberships'"` → exit 0.
- `cd apps/backend && uv run pytest tests/unit/ -x` → 253 passed.

All 11 prompt-level success criteria PASSED (1 noted as Rule 4 deviation in keyword name; verifier reviews).

---

*Phase: 18-arq-scheduled-expire-memberships*
*Completed: 2026-05-07*
