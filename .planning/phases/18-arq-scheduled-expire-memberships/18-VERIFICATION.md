---
phase: 18-arq-scheduled-expire-memberships
verified: 2026-05-07T00:00:00Z
status: human_needed
score: 5/5 success criteria verified; 1 documentation reconciliation pending human decision
overrides_applied: 0
human_verification:
  - test: "Decide ARQ 0.28 reconciliation: REQUIREMENTS.md ARQ-03 still names `keep_cronjob_progress=60` but shipped code uses `keep_result=60` (the API rename in arq 0.28.0)"
    expected: "Either (a) edit REQUIREMENTS.md ARQ-03 to read `keep_result=60` (preferred — semantics preserved by SQL-level idempotency gate, defence-in-depth maintained) and pin `arq>=0.28` in `apps/backend/pyproject.toml`, OR (b) pin `arq>=0.26,<0.27` and revert the worker code to `keep_cronjob_progress=60`."
    why_human: "REQUIREMENTS.md prose is locked text; the verifier must not silently rewrite locked specs. The deviation is documented in `apps/backend/app/workers/__init__.py:78-86` and SUMMARY 18-03; the user owns the choice."
---

# Phase 18: ARQ scheduled `expire_memberships` Verification Report

**Phase Goal:** Active memberships transition to `expired` automatically when their `end_date` passes — without manual intervention or duplicate audit events on worker restart.

**Verified:** 2026-05-07
**Status:** human_needed (5/5 SCs technically verified; 1 documentation-vs-code prose mismatch requires user decision)

---

## Goal Achievement

### Observable Truths (ROADMAP Success Criteria)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| SC#1 | `app/workers/scheduled/expire_memberships.py` exists, exposes `async def expire_memberships(ctx) -> int`, single-transaction UPDATE … RETURNING flips due rows and returns count | VERIFIED | File present (`apps/backend/app/workers/scheduled/expire_memberships.py:41`); signature `async def expire_memberships(ctx: dict[str, Any]) -> int`; calls `_expire_due_memberships` which uses `update(Membership).where(end_date<today, status='active').values(status='expired').returning(Membership.id, Membership.client_id)` (`apps/backend/app/modules/memberships/repository.py:342-348`); returns `len(rows)` (service line 556); worker returns `count` (worker line 72). |
| SC#2 | Calling `expire_memberships(ctx)` twice returns 0 the second time and produces no duplicate audit events; idempotency proven at SQL level | VERIFIED | SQL gate `WHERE status='active'` is the real defence; `tests/integration/workers/test_expire_memberships_idempotent.py:30-80` runs the function twice, asserts `second_count == 0`, audit row count stays at 1, and a `count=0` summary line is emitted on the second tick. Test passed (1 of 499 in pytest run). |
| SC#3 | `WorkerSettings` registers cron at hour=3, minute=5, unique=True (06:05 MSK / `TZ=UTC`); `on_startup`/`on_shutdown` open + close DB lifespan and expose `sessionmaker` in ctx | VERIFIED | `apps/backend/app/workers/__init__.py:87-95` defines `cron(expire_memberships, hour=3, minute=5, unique=True, keep_result=60)`; `on_startup` (lines 97-124) opens `db_lifespan_manager` via `AsyncExitStack`, stashes `engine`/`sessionmaker` into `ctx`, runs cron-resolution invariant; `on_shutdown` (lines 126-132) closes the stack. `redis_settings = RedisSettings.from_dsn(str(get_settings().redis_url))` (line 74). NOTE: The literal `keep_cronjob_progress=60` named in ROADMAP SC#3 + ARQ-03 is a stale parameter name — ARQ 0.28 dropped it; see Deviation D1 below. |
| SC#4 | `apps/backend/docker-compose.yml` runs a 5th `arq-worker` service (correct command + restart + deps); `app/workers/scheduler.py` deleted | VERIFIED | `apps/backend/docker-compose.yml:36-49` defines `arq-worker` service with `command: uv run arq app.workers.WorkerSettings`, `restart: unless-stopped`, `env_file: .env`, `environment: { TZ: UTC, DATABASE_URL, REDIS_URL }`, `depends_on: { migrate: service_completed_successfully, redis: service_started }`. `docker compose config` exits 0 (validated). `app/workers/scheduler.py` and `app/workers/arq_app.py` both deleted (CD-01 + ARQ-04). |
| SC#5 | `on_job_start`/`on_job_end` bind `job_id`/`job_name` into structlog contextvars (mirror of `RequestIdMiddleware`) | VERIFIED | `apps/backend/app/workers/__init__.py:134-151` — `on_job_start` calls `clear_contextvars()` then `bind_contextvars(job_id=str(ctx['job_id']), job_name=ctx['function_name'])`; `on_job_end` clears contextvars. Same shape as `RequestIdMiddleware` in `app/core/middleware.py`. `merge_contextvars` is in `app/core/logging.py:12`, so bound vars flow into all log lines emitted during the job. Tests `tests/unit/workers/test_arq_contextvars.py:35-56` assert bind + clear behaviour. |

**Score:** 5/5 ROADMAP success criteria verified.

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `apps/backend/app/workers/scheduled/__init__.py` | Namespace marker (D-09 docstring) | VERIFIED | Present, documents D-09 worker→module exception, lists current + future I/O fanout files. |
| `apps/backend/app/workers/scheduled/expire_memberships.py` | Worker entry `async def expire_memberships(ctx) -> int`; transaction owner | VERIFIED | Signature correct; opens session from `ctx['sessionmaker']`; calls `memberships_service._expire_due_memberships(session)`; commits; emits CD-03 summary `expire_memberships_complete count=N`; returns int. |
| `apps/backend/app/workers/__init__.py` | Real `WorkerSettings` class (replaces placeholder) | VERIFIED | Replaces former placeholder docstring with class implementing all 4 lifecycle hooks; preserves D-06/D-09 narrative docstring. |
| `apps/backend/app/modules/memberships/service.py:_expire_due_memberships` | Bulk service helper, private (`_` prefix), `# noqa: SVC001 caller-owns-txn` | VERIFIED | Function at line 497; underscore prefix per INFRA-13 opt-out; `# noqa: SVC001 caller-owns-txn` on def line; emits literal-string `audit.emit("membership_expired", actor_user_id=None, resource_type="membership", resource_id=..., client_id=...)`. AST commit gate passes (`tests/unit/test_service_commit_gate.py` 7/7 green). |
| `apps/backend/app/modules/memberships/repository.py:expire_due_rows` | Bulk SQL helper returning `Sequence[Row[(UUID, UUID)]]` | VERIFIED | At line 313; uses SQLAlchemy Core `update(Membership)…returning(Membership.id, Membership.client_id)`; D-04 wording verbatim in docstring. |
| `apps/backend/docker-compose.yml` (5th service) | `arq-worker` per CD-02 | VERIFIED | See SC#4. |
| `apps/backend/app/workers/scheduler.py` | DELETED per ARQ-04 | VERIFIED | File does not exist. |
| `apps/backend/app/workers/arq_app.py` | DELETED per CD-01 | VERIFIED | File does not exist. |
| Tests `tests/integration/workers/{test_expire_memberships,test_expire_memberships_idempotent}.py` | ARQ-TEST-01 + ARQ-TEST-02 | VERIFIED | Both files exist; both pass. |
| Tests `tests/unit/workers/{test_worker_settings,test_arq_contextvars}.py` | CD-04 invariants | VERIFIED | Both files exist; 7+4 tests pass. |

### Key Link Verification

| From | To | Via | Status | Details |
|------|-----|-----|--------|---------|
| `WorkerSettings.cron_jobs` | `expire_memberships` callable | `cron(expire_memberships, …)` | WIRED | Direct function reference; `cron_jobs[0].coroutine is expire_memberships` (asserted in `test_worker_settings.py:54`). |
| `WorkerSettings.on_startup` | `db_lifespan_manager` | `AsyncExitStack.enter_async_context(db_lifespan_manager())` | WIRED | Mirror of `app/workers/telegram_bot.py:55-59` pattern. |
| `expire_memberships(ctx)` worker | `memberships_service._expire_due_memberships` | `from app.modules.memberships import service as memberships_service` | WIRED | Import legal under D-09 (no `workers ⊥ modules` import-linter contract; 3 contracts kept, 0 broken). |
| `_expire_due_memberships` service | `repository.expire_due_rows` | direct call | WIRED | Service iterates `result.all()` Rows and emits per-row audit. |
| `audit.emit("membership_expired", ...)` | `LOCKED_AUDIT_EVENTS` | literal-string AST gate | WIRED | `("membership_expired", "membership")` at `app/core/audit.py:110`; AST taxonomy walker `tests/unit/test_audit_taxonomy.py` passes 3/3. |
| `on_job_start` → structlog → log lines | `merge_contextvars` processor | `app/core/logging.py:12` | WIRED | Bound `job_id`/`job_name` flow into both audit rows and the `expire_memberships_complete` summary line. |
| `arq-worker` compose service | `WorkerSettings` | `command: uv run arq app.workers.WorkerSettings` | WIRED | Import path matches the canonical class location post-CD-01 cleanup. |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Module imports cleanly | `uv run python -c "from app.workers import WorkerSettings; from app.workers.scheduled.expire_memberships import expire_memberships"` | (covered by `test_worker_settings.py::test_worker_settings_class_importable`, passed) | PASS |
| Cron coroutine wired | unit test asserts `cron_jobs[0].coroutine is expire_memberships` | passed | PASS |
| Cron parameters locked | unit test asserts `hour==3`, `minute==5`, `keep_result_s==60` | passed | PASS |
| 3-row fixture flips only overdue row, count==1 | `test_expire_memberships.py::test_expire_memberships_flips_only_overdue_active_rows` | passed | PASS |
| Idempotent: 2nd call returns 0, no duplicate audit | `test_expire_memberships_idempotent.py::test_expire_memberships_idempotent` | passed | PASS |
| `on_job_start` binds `job_id`+`job_name` | `test_arq_contextvars.py::test_on_job_start_binds_job_id_and_job_name` | passed | PASS |
| `on_job_end` clears contextvars | `test_arq_contextvars.py::test_on_job_end_clears_contextvars` | passed | PASS |
| docker-compose validates | `docker compose -f apps/backend/docker-compose.yml config` | exit 0 | PASS |
| Full pytest suite | `cd apps/backend && uv run pytest tests/ -x` | 499 passed in 27.62s | PASS |
| mypy strict | `cd apps/backend && uv run mypy app/` | "Success: no issues found in 65 source files" | PASS |
| import-linter | `cd apps/backend && uv run lint-imports` | "Contracts: 3 kept, 0 broken." | PASS |
| ruff | `cd apps/backend && uv run ruff check app/` | "All checks passed!" | PASS |

### Requirements Coverage

| Requirement | Source Plan | Description (abbrev.) | Status | Evidence |
|-------------|-------------|----------------------|--------|----------|
| ARQ-01 | 18-01, 18-02 | Namespace + worker entry exists; D-09 docstring | SATISFIED | Files + docstrings present (see Artifacts). |
| ARQ-02 | 18-01 | Idempotent single-transaction UPDATE…RETURNING with literal `audit.emit("membership_expired", actor_user_id=None, …)` per row | SATISFIED | Implementation at `service.py:497-556` + `repository.py:313-349`; ARQ-TEST-02 passes. NOTE: SQL uses parameterized `< :today` rather than `CURRENT_DATE` per D-05 (TZ-safety; ROADMAP wording is informal). |
| ARQ-03 | 18-03 | `WorkerSettings` class with redis_settings, on_startup/on_shutdown, functions, cron_jobs at hour=3 minute=5 unique=True keep_cronjob_progress=60 | PARTIALLY SATISFIED — see Deviation D1 | Class is present and correctly structured; `keep_cronjob_progress=60` was renamed `keep_result=60` in ARQ 0.28 (parameter dropped from `cron(...)` upstream). REQUIREMENTS.md prose is now stale; user must reconcile. |
| ARQ-04 | 18-04 | docker-compose `arq-worker` service + `scheduler.py` deletion | SATISFIED | `docker-compose.yml:36-49`; both legacy files deleted. |
| ARQ-05 | 18-03 | `on_job_start`/`on_job_end` bind `job_id`/`job_name` to structlog contextvars | SATISFIED | Hooks present + tested. |
| ARQ-TEST-01 | 18-05 | 3-row fixture, exactly 1 expired, exactly 1 audit, exactly 1 summary log | SATISFIED | `test_expire_memberships.py`; passed. |
| ARQ-TEST-02 | 18-05 | Two-call idempotency: 2nd returns 0, no duplicate audit | SATISFIED | `test_expire_memberships_idempotent.py`; passed. |

No orphaned requirements detected (all ARQ-* IDs claimed by Phase 18 plans are addressed in shipped code).

### Locked Decisions Audit

| Decision | Status | Evidence |
|----------|--------|----------|
| D-01: Worker is txn owner; service emits, worker commits | HONORED | `worker.expire_memberships` lines 64-66 (`async with…commit`); service has `# noqa: SVC001 caller-owns-txn`. |
| D-02: Service returns `int` count | HONORED | `service._expire_due_memberships` returns `len(rows)` (line 556); worker returns `count` (line 72). |
| D-03: No `_assert_can_expire` in bulk path | HONORED | Bulk path does not call `_assert_can_expire`; SQL `WHERE status='active'` is the gate. |
| D-04: `UPDATE … RETURNING id, client_id` | HONORED | `repository.py:346` `.returning(Membership.id, Membership.client_id)`. |
| D-05: `today: date` Python-side (not `CURRENT_DATE`) | HONORED | Service computes `datetime.now(ZoneInfo("Europe/Moscow")).date()` if `today is None` (line 542); strict `<` comparison; documented departure from ROADMAP informal wording. |
| D-09: Worker → owning-module service exception | HONORED | `expire_memberships.py:36` `from app.modules.memberships import service as memberships_service`; documented in `__init__.py:12-16` + `scheduled/__init__.py`. import-linter green (3/3 contracts). |
| CD-01: `arq_app.py` deleted | HONORED | File does not exist. |
| CD-02: compose at `apps/backend/`, not `infra/` | HONORED | Service added to existing `apps/backend/docker-compose.yml`. |
| CD-03: Summary log line `expire_memberships_complete count=N` after commit | HONORED | `worker.py:71` emits `_log.info("expire_memberships_complete", count=count)` AFTER `await session.commit()`. |
| CD-04: cron-resolution invariant in `on_startup` | HONORED | `__init__.py:110-117` asserts `unresolved == set()`. |
| CD-06: `_assert_can_expire` retained | HONORED | Helper still in service.py:118. |

### Anti-Patterns Found

None blocking. The deviations enumerated below are documented (in code comments + SUMMARYs) and intentional.

---

## Deviations Evaluated

### D1 (WARNING, not blocker): `keep_cronjob_progress=60` → `keep_result=60` rename

**Location:** `apps/backend/app/workers/__init__.py:78-95`; documented inline.

**Cause:** `arq>=0.26` pin in pyproject resolves to installed `arq==0.28.0` (uv.lock); ARQ 0.28 dropped the `keep_cronjob_progress` parameter from `cron(...)` and the per-tick progress key now flows through the `keep_result` retention TTL.

**Impact assessment:**
- Phase goal preservation: **fully preserved**. SC#2 (no duplicate audit on worker restart) is satisfied by the SQL-level `WHERE status='active'` gate, which is the real idempotency defence per PITFALLS Pitfall 4. ARQ `unique=True` + result-retention is a defence-in-depth layer; the rename does not weaken the SQL gate.
- ROADMAP SC#3 prose match: **stale**. ROADMAP says "`unique=True`" only and does not name `keep_cronjob_progress`. ARQ-03 prose in REQUIREMENTS.md DOES name `keep_cronjob_progress=60` — that line is now historically locked but technically out-of-date.
- Test coverage: ARQ-TEST-02 proves idempotency at the user-observable level (no duplicate audit rows on second call). Test passes.
- Observability: `keep_result_s == 60` is asserted in `tests/unit/workers/test_worker_settings.py:72`; the code shape is exercised.

**Recommendation: WARNING, accept rename.** The semantics are equivalent for this phase's idempotency goal. The user should:
1. Edit `.planning/REQUIREMENTS.md` ARQ-03 prose to read `keep_result=60` instead of `keep_cronjob_progress=60`, with a note "(ARQ 0.28 API rename; same retention-TTL purpose)".
2. Optionally tighten `apps/backend/pyproject.toml` arq pin from `arq>=0.26` to `arq>=0.28,<0.29` to lock the API surface.

**Alternative (not recommended): downgrade.** Pin `arq>=0.26,<0.27`, revert worker to `keep_cronjob_progress=60`. Costs: stale dependency for a non-goal-blocking parameter; loses 0.27/0.28 bug fixes.

### D2 (NOTE, no action needed): SVC prefix added to `ruff.toml` `lint.external`

**Location:** `apps/backend/ruff.toml:29` (`external = ["SVC"]`).

**Cause:** First production callsite of `# noqa: SVC001 caller-owns-txn` (Phase 15 INFRA-13 opt-out); RUF102 would otherwise warn that `SVC001` is an unrecognised rule code.

**Impact:** None — addition is mechanically required for the documented INFRA-13 opt-out path to compile cleanly. Documented in 18-01 SUMMARY.

### D3 (NOTE, no action needed): `seeded_client` fixture corrected to canonical `Client` schema

**Location:** Test fixtures only; documented in 18-05 SUMMARY.

**Impact:** None — fixture now matches the production model (`last_name`/`first_name`/`created_by_user_id`); tests pass.

### D4 (NOTE, no action needed): `capture_logs` autouse invalidation fixture

**Location:** `tests/integration/workers/conftest.py` (autouse fixture); commit `28bc2da`.

**Cause:** Module-level cached BoundLogger held a stale processor list reference after a mid-suite `create_app()` call reconfigured logging; `capture_logs` therefore missed events on the second test in a run.

**Impact:** None — fixture invalidates `_log.__dict__['bind']` before each test; ARQ-TEST-01 + ARQ-TEST-02 both green.

### D5 (NOTE, no action needed): ARQ 0.28 unit-test assertion shape changes

**Location:** `tests/unit/workers/test_worker_settings.py`.

- `cron_jobs[0].name` returns `"cron:expire_memberships"` in 0.28 — assertions use `.coroutine.__name__` instead.
- `.keep_cronjob_progress` attribute removed — assertions use `.keep_result_s == 60`.
- One RUF005 list-concat rewritten with unpacking.

**Impact:** None — assertions exercise the same invariants via the 0.28 API surface.

---

## Summary

All five ROADMAP success criteria are observable in shipped code. All seven Phase 18 requirements (ARQ-01..05, ARQ-TEST-01..02) are functionally satisfied. The 499-test suite is green; mypy strict is clean; import-linter contracts are 3/3 kept; ruff is clean; docker-compose validates.

The only outstanding item is a **prose reconciliation** between `.planning/REQUIREMENTS.md` (which still names the ARQ 0.26 parameter `keep_cronjob_progress=60`) and the shipped code (which uses the equivalent ARQ 0.28 `keep_result=60`). The phase goal — "Active memberships transition to expired automatically without duplicate audit events on worker restart" — is **achieved** and proven by ARQ-TEST-02; the deviation is documented inline and in SUMMARY 18-03 and is semantically equivalent for the goal at hand.

**Recommended status: PHASE COMPLETE pending human decision on D1.** The author of REQUIREMENTS.md (the user) should accept the rename in REQUIREMENTS.md prose and optionally tighten the arq pin. Reverting to `arq<0.27` is available but not recommended.

---

_Verified: 2026-05-07_
_Verifier: Claude (gsd-verifier, Opus 4.7)_
