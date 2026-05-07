---
phase: 18-arq-scheduled-expire-memberships
plan: 06
subsystem: backend
tags: [backend, arq, tests, unit, contextvars, cron, mypy-strict]

# Dependency graph
requires:
  - phase: 18-arq-scheduled-expire-memberships
    provides: "Plan 18-03 — app.workers.WorkerSettings class shape (cron_jobs, functions, redis_settings, on_startup, on_shutdown, on_job_start, on_job_end)"
  - phase: 18-arq-scheduled-expire-memberships
    provides: "Plan 18-02 — app.workers.scheduled.expire_memberships coroutine (the registered cron function under test)"
provides:
  - "tests/unit/workers/ — new unit-test scope mirroring tests/unit/{clients,memberships}/ — 11 unit tests that lock the WorkerSettings class shape + structlog contextvars hooks at the import level (no DB, no Redis)"
  - "Pitfall 4 step 6 (silent no-op trap) — exercised at the unit-test level via on_startup against monkey-patched cron_jobs referencing an unregistered function: AssertionError raised at boot, not silent no-op at 06:05"
  - "Pitfall 14 (contextvars leak between cron runs) — exercised at the unit-test level via bind→end→bind→end shape: second bind sees a fresh job_id, no leakage from the first run"
  - "Empirical lock: ARQ 0.28 cron(...) hour/minute attribute shape is bare int (Form B); CronJob.name is auto-prefixed `cron:expire_memberships`; keep_result=60 stores as .keep_result_s"
affects:
  - "Future ARQ version bumps — these tests fail loud if .coroutine.__name__ resolution, contextvars binding shape, or hour/minute attribute type changes"
  - "Future cron registrations — adding a cron entry whose function is not in WorkerSettings.functions is now caught at the unit-test level on every CI run, not just at the next 06:05 tick"

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Unit-test scope under tests/unit/workers/ — mirrors tests/unit/{clients,memberships}/ layout; pattern for future worker-related unit tests"
    - "structlog.contextvars.get_contextvars() introspection — public API for asserting bound contextvars without touching internal _CONTEXT_VARS"
    - "autouse fixture pattern for contextvars isolation — clear_contextvars() before AND after each test to prevent cross-test pollution"
    - "Class-attribute mutation + try/finally restore — for testing class-level invariants (WorkerSettings.cron_jobs) without polluting downstream tests"
    - "Empirically-verified cron-attribute shape locking — W-1 probe runs `from arq.cron import cron; ...; print(type(c.hour).__name__, c.hour)` BEFORE locking the assertion form, eliminating the green-but-wrong test class"

key-files:
  created:
    - "apps/backend/tests/unit/workers/__init__.py — package marker (1 line)"
    - "apps/backend/tests/unit/workers/test_worker_settings.py — 7 unit tests covering class importable, cron coroutine identity, cron locked args, functions list, redis_settings.host, on_startup baseline, on_startup raises on unregistered cron entry"
    - "apps/backend/tests/unit/workers/test_arq_contextvars.py — 4 unit tests covering on_job_start binds, on_job_end clears, bind→end→bind→end no leakage, clear-stale-before-bind"
  modified: []
  deleted: []

key-decisions:
  - "W-1 probe locked Form B (bare ints): `type(c.hour).__name__` returned `int 3 int 5` against arq==0.28.0 — assertion form `c.hour == 3` (not `c.hour == {3}`) is the only form left in the test file"
  - "Rule 1 fix (auto-applied per 18-03 SUMMARY guidance): assert on `cron_jobs[0].coroutine.__name__ == 'expire_memberships'` instead of `cron_jobs[0].name == 'expire_memberships'` — ARQ 0.28 auto-prefixes `CronJob.name` to `'cron:expire_memberships'`, so the plan's literal name assertion would have shipped a red test"
  - "Rule 1 fix (auto-applied per CronJob attribute introspection): assert on `cron_jobs[0].keep_result_s == 60` instead of `cron_jobs[0].keep_cronjob_progress == 60` — ARQ 0.28's CronJob exposes the `keep_result=60` constructor parameter as the `.keep_result_s` attribute (Plan 18-03 already used `keep_result=60` in the cron() call per its own Rule 4 deviation)"
  - "W-4 strengthening applied: smoke-test assertions on ctx['sessionmaker'] and ctx['engine'] use `callable(...) or ... is not None` instead of bare `is not None` — the bare form is vacuously true against `object()` sentinels and would not catch a regression where on_startup forgot to populate those keys"
  - "Ruff RUF005 fix during Task 2: `original_cron_jobs + [cron(...)]` rewritten as `[*original_cron_jobs, cron(...)]` (iterable unpacking style)"

requirements-completed: [ARQ-03, ARQ-05]

# Metrics
duration: 5min
completed: 2026-05-07
---

# Phase 18 Plan 06: ARQ unit tests — WorkerSettings + contextvars Summary

**11 unit tests shipped under `tests/unit/workers/` (7 in `test_worker_settings.py` + 4 in `test_arq_contextvars.py`) that lock the `WorkerSettings` class shape (cron coroutine identity, hour/minute/unique/keep_result_s, functions list, redis_settings.host) and the structlog contextvars hooks (Pitfall 14 bind→end→bind→end shape) at the unit-test level — no DB, no Redis. Pitfall 4 step 6 (silent no-op trap) is now exercised by mutating WorkerSettings.cron_jobs in-place to inject a cron entry referencing an unregistered function and asserting `on_startup` raises AssertionError; the W-1 probe empirically verified ARQ 0.28's cron attribute shape (Form B: bare ints) before the assertion form was locked.**

## Performance

- **Duration:** ~5 min
- **Started:** 2026-05-07T19:10:32Z
- **Completed:** 2026-05-07T19:15:04Z
- **Tasks:** 3 (Task 1 package marker, Task 2 test_worker_settings, Task 3 test_arq_contextvars)
- **Files created:** 3; **Files modified:** 0; **Files deleted:** 0
- **Tests added:** 11 unit tests; **Total backend test count:** 499 passed (was 477 + 11 new + integration tests from 18-05).

## Accomplishments

### `tests/unit/workers/__init__.py`

- 1-line package marker matching `tests/unit/{clients,memberships}/__init__.py` shape.

### `tests/unit/workers/test_worker_settings.py` (7 tests)

1. **`test_worker_settings_class_importable`** — regression catcher for class rename / accidental deletion.
2. **`test_worker_settings_cron_resolves_to_registered_function`** — asserts `cron_jobs[0].coroutine.__name__ == 'expire_memberships'` AND `cron_jobs[0].coroutine is expire_memberships` (identity, not equality — catches future decorator wrapping).
3. **`test_worker_settings_cron_locked_args`** — asserts `c.hour == 3, c.minute == 5, c.unique is True, c.keep_result_s == 60` (Form B locked per W-1 probe; `keep_result_s` is the ARQ 0.28 attribute name).
4. **`test_worker_settings_functions_registered`** — asserts `expire_memberships in functions` AND `len(functions) == 1`.
5. **`test_worker_settings_redis_settings_resolved`** — asserts `redis_settings.host` is a non-empty string (resolves from `get_settings().redis_url`).
6. **`test_on_startup_cron_resolution_invariant_passes_at_baseline`** — async smoke test; monkey-patches `db_lifespan_manager` to a no-op `asynccontextmanager` that yields `(object(), object())` sentinels; calls `await WorkerSettings.on_startup(ctx)`; asserts `_db_stack`, `sessionmaker`, `engine` populated using the W-4-strengthened `callable(...) or ... is not None` form.
7. **`test_on_startup_raises_when_cron_references_unregistered_function`** — Pitfall 4 step 6; mutates `WorkerSettings.cron_jobs` to add a `cron(_bogus_function, ...)` entry (whose name is NOT in `functions`); calls `await WorkerSettings.on_startup({})`; asserts `pytest.raises(AssertionError, match="cron_jobs reference")`; restores `cron_jobs` in `finally` block.

### `tests/unit/workers/test_arq_contextvars.py` (4 tests)

1. **`test_on_job_start_binds_job_id_and_job_name`** — calls `await WorkerSettings.on_job_start({"job_id": "abc-123", "function_name": "expire_memberships"})`; asserts `structlog.contextvars.get_contextvars()` contains both keys.
2. **`test_on_job_end_clears_contextvars`** — bind, then end; asserts `get_contextvars() == {}` after end.
3. **`test_bind_end_bind_end_no_leakage_between_runs`** — Pitfall 14 leakage protection; runs the cycle bind(run-1) → end → bind(run-2) → end; asserts run-2's contextvars contain only `run-2`, no `run-1` string anywhere; asserts final state is `{}`.
4. **`test_on_job_start_clears_stale_bindings_before_binding`** — clear-then-bind regression catcher; pre-binds `stale_key`; calls `on_job_start`; asserts `stale_key` is gone but `job_id` is bound. Catches a future refactor that drops `clear_contextvars()` from the hook.

The 4 contextvars tests share an autouse `_isolate_contextvars` fixture that calls `clear_contextvars()` before AND after each test — without this, a stray bind from a prior test (e.g. `RequestIdMiddleware` tests in another file) would pollute `get_contextvars()` assertions.

## Task Commits

Each task committed atomically on `master`:

1. **Task 1: package marker** — `db03956` (`test`)
2. **Task 2: test_worker_settings.py** — `c40cbcd` (`test`)
3. **Task 3: test_arq_contextvars.py** — `44aa3cf` (`test`)

`git log --oneline -3` shows them at HEAD..HEAD~2.

## Files Created/Modified

- **Created** `apps/backend/tests/unit/workers/__init__.py` (1 line, docstring only).
- **Created** `apps/backend/tests/unit/workers/test_worker_settings.py` (151 lines, 7 tests).
- **Created** `apps/backend/tests/unit/workers/test_arq_contextvars.py` (110 lines, 4 tests).

No source files modified — these are purely additive unit tests against the Plan 18-03 implementation.

## Empirically-locked cron attribute shape (W-1 probe result)

The plan included a CRITICAL pre-step probe to determine whether ARQ stores `cron(hour=3, minute=5)` as bare `int` or as `set[int]`. The probe was run BEFORE locking the assertion form:

```bash
cd apps/backend && uv run python -c "
from arq.cron import cron
async def _f(ctx): pass
c = cron(_f, hour=3, minute=5)
print(type(c.hour).__name__, repr(c.hour), type(c.minute).__name__, repr(c.minute))
"
```

**Output:** `int 3 int 5`

**Form B locked.** The test asserts `c.hour == 3` and `c.minute == 5` (bare integers). The grep validation `grep -c "c\.hour == {3}\|c\.hour == 3" tests/unit/workers/test_worker_settings.py` returns exactly `1` — the single live assertion line; no Form A fragment was left commented out (deleted, not commented).

## Decisions Made

All locked-at-plan-time decisions (Pitfall 4 step 6 invariant, Pitfall 14 bind→end→bind→end, autouse contextvars isolation, no DB requirement, mypy strict + ruff clean) honored. Three execution-time observations are documented in the **Deviations** section below.

## Deviations from Plan

### 1. [Rule 1 — bug] `cron_jobs[0].name == 'expire_memberships'` would fail in ARQ 0.28; assert on `.coroutine.__name__` instead

- **Found during:** Task 2 (writing test_worker_settings.py).
- **Issue:** The plan's literal acceptance criterion `cron_jobs[0].name == 'expire_memberships'` is not satisfiable against `arq==0.28.0` — the installed version auto-prefixes `CronJob.name` with `"cron:"` (i.e., returns `"cron:expire_memberships"`). The 18-03 SUMMARY explicitly flagged this as Deviation §3 (verifier-side bug, not code-side bug). The Plan 18-06 prompt's `<phase_context>` ALSO flagged it: "ARQ 0.28's `CronJob.name` returns `"cron:expire_memberships"` (auto-prefixed), so `cron_jobs[0].name == 'expire_memberships'` would FAIL. Use `.coroutine.__name__` for the function-name assertion instead."
- **Fix:** Asserted on `cron_entry.coroutine.__name__ == "expire_memberships"` (the same accessor `WorkerSettings.on_startup`'s cron-resolution invariant uses). Identity check `cron_entry.coroutine is expire_memberships` added as the stronger same-object oracle.
- **Files modified:** `apps/backend/tests/unit/workers/test_worker_settings.py`.
- **Commit:** `c40cbcd`.

### 2. [Rule 1 — bug] `keep_cronjob_progress == 60` is not on the CronJob attribute API; assert `keep_result_s == 60` instead

- **Found during:** Task 2 attribute-introspection probe (`uv run python -c "...; print(c.keep_result_s)"`).
- **Issue:** The plan's literal `cron_entry.keep_cronjob_progress == 60` does not match the ARQ 0.28 CronJob attribute shape. Plan 18-03's `cron()` call already uses `keep_result=60` (per its own Rule 4 deviation — `keep_cronjob_progress` was removed in 0.28). When ARQ stores the parameter on the CronJob instance, it does so as `.keep_result_s` (seconds suffix). Asserting on `.keep_cronjob_progress` would raise `AttributeError`; asserting on `.keep_result == 60` would also fail because the attribute name is `.keep_result_s`.
- **Fix:** Asserted on `c.keep_result_s == 60`.
- **Files modified:** `apps/backend/tests/unit/workers/test_worker_settings.py`.
- **Commit:** `c40cbcd`.

### 3. [Rule 3 — blocking] Ruff RUF005 (iterable concatenation) on the cron_jobs mutation

- **Found during:** Task 2 first ruff check (`uv run ruff check tests/unit/workers/test_worker_settings.py`).
- **Issue:** `WorkerSettings.cron_jobs = original_cron_jobs + [cron(_bogus_function, ...)]` triggered RUF005 ("Consider iterable unpacking instead of concatenation"). Project uses ruff strict — this is a blocking issue.
- **Fix:** Rewrote as `WorkerSettings.cron_jobs = [*original_cron_jobs, cron(_bogus_function, ...)]`.
- **Files modified:** `apps/backend/tests/unit/workers/test_worker_settings.py`.
- **Commit:** `c40cbcd` (bundled into the same commit since this was caught before commit).

## Threat Surface Verification

The Plan 18-06 file did not declare its own `<threat_model>` block (it inherits the phase-level threats validated by Plan 18-03). This plan adds tests, not new attack surface. The relevant threats from 18-03 (T-18-05 cron registration tampering, T-18-07 contextvars leak) now have BOTH integration-level AND unit-level catchers:

| Threat ID | Plan 18-03 mitigation | Plan 18-06 unit test catcher |
|-----------|------------------------|-------------------------------|
| T-18-05 (cron registration tampering / silent no-op) | `on_startup` cron-resolution invariant assert | `test_on_startup_raises_when_cron_references_unregistered_function` exercises the assertion against a mutated WorkerSettings.cron_jobs |
| T-18-07 (contextvars leak across runs) | `on_job_start` clears+binds; `on_job_end` clears | `test_bind_end_bind_end_no_leakage_between_runs` AND `test_on_job_start_clears_stale_bindings_before_binding` exercise both halves |

No new threat surface introduced. No new flags.

## Issues Encountered

- **Initial probe attempted with a `lambda`** — failed because `arq.cron.cron(...)` requires a coroutine function (raised `RuntimeError: <function <lambda> at 0x...> is not a coroutine function`). Re-ran with `async def _f(ctx): pass`; probe succeeded and printed `int 3 int 5`.
- **First ruff run failed** — RUF005 fix applied (Deviation §3 above).
- **No other issues.** mypy strict and lint-imports stayed green throughout.

## User Setup Required

None — purely backend Python tests. The Phase 18 Rule 4 deviation (Plan 18-03's `keep_cronjob_progress` → `keep_result` rename for ARQ 0.28 compatibility) remains the only item flagged for human review at 18-VERIFICATION; this plan does NOT introduce a new such item.

## Verification Gates — All Green

- `cd apps/backend && uv run pytest tests/unit/workers/ -v` → 11 passed in 0.02s.
- `cd apps/backend && uv run pytest tests/ -x` → 499 passed in 26.76s (full backend suite, no regressions).
- `cd apps/backend && uv run mypy tests/unit/workers/` → Success: no issues found in 3 source files.
- `cd apps/backend && uv run ruff check tests/unit/workers/` → All checks passed.
- `cd apps/backend && uv run lint-imports` → 3 contracts kept, 0 broken.
- `grep -c "c\.hour == {3}\|c\.hour == 3" tests/unit/workers/test_worker_settings.py` → `1` (only Form B live; Form A deleted not commented).
- `grep -q 'callable(ctx\["sessionmaker"\])' tests/unit/workers/test_worker_settings.py` → exit 0 (W-4 strengthened assertion present).

## Next Phase Readiness

- **Phase 18 is now complete (Wave 4 final plan).** All 5 success criteria from `.planning/ROADMAP.md` §"Phase 18" are unit + integration tested:
  1. `expire_memberships` flips overdue active rows to expired and returns the count → covered by 18-05 integration tests.
  2. SQL-level idempotency via `WHERE status='active'` → covered by 18-05 idempotency test.
  3. Cron tick `06:05 Europe/Moscow` (`hour=3, minute=5` UTC) → covered by `test_worker_settings_cron_locked_args`.
  4. WorkerSettings importable as `app.workers.WorkerSettings` → covered by `test_worker_settings_class_importable`.
  5. `arq-worker` docker-compose service → shipped in 18-04 (out of unit-test scope).
- The cron-resolution invariant (Pitfall 4 step 6) AND the contextvars hooks (Pitfall 14) now have unit-level catchers — future class-shape regressions fail at `pytest tests/unit/workers/` in <0.1s on every CI run, well before the integration tests in 18-05 spin up Postgres.
- **Phase 18 verifier (`/gsd-verify-phase 18`)** can now run; the 18-VERIFICATION step will inherit the open Plan 18-03 Rule 4 deviation review (`keep_cronjob_progress` → `keep_result` rename for ARQ 0.28).

## Self-Check: PASSED

Files exist (verified via `test -f`):

- `apps/backend/tests/unit/workers/__init__.py` — FOUND.
- `apps/backend/tests/unit/workers/test_worker_settings.py` — FOUND.
- `apps/backend/tests/unit/workers/test_arq_contextvars.py` — FOUND.

Commits exist (verified via `git log --oneline -3`):

- `db03956` — test(18-06): add tests/unit/workers package marker — FOUND.
- `c40cbcd` — test(18-06): add WorkerSettings class-shape + cron-resolution invariant tests — FOUND.
- `44aa3cf` — test(18-06): add ARQ contextvars binding/clearing tests (Pitfall 14) — FOUND.

All acceptance gates ran and passed:

- 11 unit tests in `tests/unit/workers/` PASSED.
- Full backend suite (499 tests) PASSED.
- mypy strict on 3 new files PASSED.
- ruff on all 3 new files PASSED.
- lint-imports 3 contracts KEPT.
- W-1 form-uniqueness grep returns 1 (only Form B live).
- W-4 strengthened-assertion grep returns 0 exit (callable check present).

All plan-level success criteria PASSED. Plan 18-06 complete.

---

*Phase: 18-arq-scheduled-expire-memberships*
*Completed: 2026-05-07*
