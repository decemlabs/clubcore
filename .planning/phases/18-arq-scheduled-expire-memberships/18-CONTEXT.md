# Phase 18: ARQ scheduled `expire_memberships` - Context

**Gathered:** 2026-05-07
**Status:** Ready for planning

<domain>
## Phase Boundary

Phase 18 ships the **first production ARQ cron job** in the codebase: `expire_memberships` daily at 06:05 Europe/Moscow (`hour=3, minute=5` UTC, container `TZ=UTC`). Until this phase, ARQ has been an empty skeleton — `app/workers/arq_app.py` carries `functions: ClassVar[list[Any]] = []` and `app/workers/scheduler.py` is a one-line TODO. After this phase, the modular monolith has a real recurring job that flips `memberships.status` from `active → expired` once `end_date < CURRENT_DATE`, plus the WorkerSettings infrastructure that future v1.3+ jobs (notifications, reports) will plug into.

In scope:
- **NEW** `app/workers/scheduled/__init__.py` — empty namespace marker (ARQ-01).
- **NEW** `app/workers/scheduled/expire_memberships.py` exposing `async def expire_memberships(ctx) -> int` — thin worker entry: opens session from `ctx["sessionmaker"]`, calls `app.modules.memberships.service.expire_due_memberships(session, today=...)`, awaits `session.commit()`, returns the integer count from the service. D-09 docstring header documents the worker→module exception (parallel to D-06 in `app/workers/__init__.py`).
- **NEW** `app/modules/memberships/service.py:expire_due_memberships(session, today)` — owns the bulk `UPDATE memberships SET status='expired' WHERE end_date < CURRENT_DATE AND status='active' RETURNING id, client_id` (single transaction, no per-row SELECT pre-flight); iterates the returned rows in Python emitting one `audit.emit("membership_expired", actor_user_id=None, resource_type="membership", resource_id=mid, client_id=cid)` per row (LOCKED payload `{membership_id, client_id}` per `LOCKED_AUDIT_EVENTS` in `app/core/audit.py:104`); returns `int` count. Caller (worker) commits.
- **NEW** `app/modules/memberships/repository.py:expire_due_rows(session, today) -> Sequence[Row]` — narrow helper returning the result of the bulk `UPDATE … RETURNING id, client_id`; service consumes it. Mirrors Phase 17 repository pattern (`update_status` lives there too). The SQL is built with SQLAlchemy Core `update()` + `.returning(Membership.id, Membership.client_id)`.
- **REPLACE** `app/workers/__init__.py` — current placeholder docstring becomes a real `WorkerSettings` class (per ARQ-03, the import path `app.workers.WorkerSettings` is REQUIREMENTS-locked):
  - `redis_settings = RedisSettings.from_dsn(str(get_settings().redis_url))`
  - `functions = [expire_memberships]`
  - `cron_jobs = [cron(expire_memberships, hour=3, minute=5, unique=True, keep_cronjob_progress=60)]`
  - `on_startup(ctx)` — opens `db_lifespan_manager()` via `AsyncExitStack`, stores `(engine, sessionmaker)` in `ctx`; **also asserts every `cron_jobs` entry's coroutine name is in `functions`** (PITFALLS step 6 — silent no-op trap).
  - `on_shutdown(ctx)` — closes the exit stack (releases engine + sessionmaker).
  - `on_job_start(ctx)` — `structlog.contextvars.clear_contextvars()` then `bind_contextvars(job_id=str(ctx["job_id"]), job_name=ctx["function_name"])` (mirror of `RequestIdMiddleware` shape per Pitfall 14).
  - `on_job_end(ctx)` — `clear_contextvars()` (prevents leak across runs in the same asyncio task).
  - The narrative docstring documents D-09 (worker → owning-module service exception) and the `RequestIdMiddleware`-mirror rationale for the contextvars hooks.
- **DELETE** `app/workers/scheduler.py` (REQUIREMENTS-locked ARQ-04 cleanup; placeholder superseded by `cron_jobs` on `WorkerSettings`).
- **DELETE** `app/workers/arq_app.py` (Claude-discretion CD-01 — see decisions; placeholder duplicate of WorkerSettings now living in `__init__.py`; keeping both creates two import paths for the same class which is the kind of drift the OpenAPI gate exists to prevent at the boundary).
- **MODIFY** `apps/backend/docker-compose.yml` (CD-02 — REQ wording said `infra/docker-compose.yml` but the canonical compose file is at `apps/backend/`; we keep the existing location and add the 5th service):
  - `arq-worker:` `build: .`, `command: uv run arq app.workers.WorkerSettings`, `restart: unless-stopped`, `env_file: .env`, `environment: { TZ: UTC, DATABASE_URL: postgresql+asyncpg://app:app@postgres:5432/sportzal, REDIS_URL: redis://redis:6379/0 }`, `depends_on: { migrate: { condition: service_completed_successfully }, redis: { condition: service_started } }`. The `TZ: UTC` is critical — the `cron(hour=3)` pin assumes UTC + a documented MSK offset.
- **NEW** end-of-run structlog INFO `expire_memberships_complete count=N` emitted from `expire_memberships(ctx)` AFTER `session.commit()` returns successfully (CD-03 — defensive observability for the first cron). `audit_user_id` and `resource_*` fields are not on this log — it's an ops summary line, not an audit event. The `job_id`/`job_name` are already on the contextvars stack from `on_job_start` so the line carries them automatically.
- Tests:
  - `tests/integration/workers/test_expire_memberships.py` (ARQ-TEST-01) — fixture creates 3 memberships (1 expiring today / `end_date == today`, 1 expired yesterday / `end_date < today`, 1 future / `end_date > today`); call `await expire_memberships(ctx)` directly with a hand-built `ctx = {"sessionmaker": db_session_factory}`; assert returned count == 1 (only yesterday's row), exactly 1 `membership_expired` audit row inserted, exactly 1 structlog INFO `expire_memberships_complete count=1` line, and the today/future rows still `status='active'`. Inclusive `end_date` invariant proven (today's row is NOT expired by the strict `<` filter).
  - `tests/integration/workers/test_expire_memberships_idempotent.py` (ARQ-TEST-02) — same fixture; call twice in sequence; second call returns 0, no duplicate audit rows, no duplicate `expire_memberships_complete` summary with `count > 0`.
  - `tests/unit/workers/test_worker_settings.py` (CD-04) — imports `app.workers.WorkerSettings` and asserts: `cron_jobs[0].name == "expire_memberships"`, every cron entry's name is also in `[f.__name__ for f in functions]` (the on_startup invariant exercised at the import-time level too), `redis_settings.host` resolves from settings, the structlog binding hook is wired (call `on_job_start({"job_id": "x", "function_name": "expire_memberships"})` then assert `structlog.contextvars._CONTEXT_VARS` contains `job_id` / `job_name`).
  - `tests/unit/workers/test_arq_contextvars.py` (CD-04 cont.) — asserts `on_job_end({})` clears the contextvars set by `on_job_start`. Two-run shape per Pitfall 14: bind → end → bind → end; second bind sees a fresh `job_id`, no leakage from the first run.
- Audit taxonomy: no extension — `("membership_expired", "membership")` already in `LOCKED_AUDIT_EVENTS` since Phase 15. The AST gate (`tests/unit/test_audit_taxonomy.py`) catches typos at the new callsite.
- AST commit gate: `app.modules.memberships.service.expire_due_memberships` is a write path (it inserts audit rows via `audit.emit` and the bulk UPDATE is itself a mutation enrolled in the transaction), so it MUST `await session.commit()` per Phase 15 INFRA-13. **Exception: this phase deliberately moves the commit into the worker entry** (one transaction wraps "UPDATE + N audits"; the worker is the transaction owner, not the service function). The AST gate's signature pattern needs an explicit `# noqa: SVC001` opt-out in `expire_due_memberships` with a comment "commit owned by worker entry per Phase 18 D-04". Documented in plan; planner reviews whether the AST walker exempts service functions called only from `app.workers.*` automatically (Phase 15 INFRA-13 spec) or if the noqa is required.
- `.importlinter` contracts unchanged. `app.workers.scheduled.expire_memberships` imports `app.modules.memberships.service` — legal under the documented D-09 (no `workers ⊥ modules` contract). The `core ⊥ modules`, `modules independent`, and `integrations ⊥ modules` contracts all remain green.

Out of scope (locked to later phases):
- **Phase 19** `visits` table + reception check-in (parallel-eligible with this phase per ROADMAP).
- **Phase 20** Telegram bot `/checkin` (D-10 parallel, separate worker process).
- **Phase 21** OpenAPI drift gate refresh + api-client codegen — Phase 18 doesn't change `apps/backend/openapi.json` (cron jobs aren't HTTP routes; nothing OpenAPI-visible changes).
- **Phase 22** admin-web wiring — there is no UI surface for the cron job itself; "expired" memberships will be rendered by the Phase 22 memberships list view.
- **v1.3+** Expiring-soon Telegram notifications (would reuse the worker infra Phase 18 lays down, but the feature itself is in PROJECT.md "Перенесено в v1.3+ … Memberships extras: freeze, visit-count plans, expiring-soon notifications").
- **v1.3+** ЮKassa payment integration; the cron has nothing to do with payments.
- **v1.3+** Bulk-aggregate audit event for runs > 200 rows (per PITFALLS scaling note — not relevant at single-zal scale where active membership count is in the hundreds, daily expiries in single digits).

</domain>

<decisions>
## Implementation Decisions

### Service contract (interactively discussed)

- **D-01:** **Service owns the UPDATE + per-row audit emits; worker is a thin wrapper.** `app/modules/memberships/service.py:expire_due_memberships(session, today)` performs the bulk `UPDATE … RETURNING id, client_id`, iterates the returned rows in Python, and calls `audit.emit("membership_expired", …)` for each. The worker file (`app/workers/scheduled/expire_memberships.py:expire_memberships(ctx)`) is the transaction owner: opens the session from `ctx["sessionmaker"]`, calls the service, calls `session.commit()`, returns the count. Rationale: mirrors Phase 17's `cancel_membership` (service emits, caller commits), inherits the AST commit-gate's coverage of `app.modules.memberships.service` from Phase 16 (modulo the noqa described in scope above), and keeps `audit.emit` co-transactional with the bulk UPDATE — if any emit fails (e.g. an LOCKED_AUDIT_EVENTS regression), the whole transaction rolls back and the next run picks up the same rows again.
- **D-02:** **Service returns `int` (count of newly-expired rows).** `expire_due_memberships(session, today) -> int`. ARQ writes the integer into its result store automatically; Phase 22's UI doesn't surface this number. Internal IDs of the affected rows stay encapsulated inside the service — exposing them would only be useful for cross-phase coupling (e.g. a hypothetical "notify expired" step), and v1.2 ships no such consumer (expiring-soon notifications are v1.3+ Out of Scope). ROADMAP SC#1 wording ("flips due rows and returns the count") is verbatim satisfied.
- **D-03:** **No per-row state-machine guard inside `expire_due_memberships`.** Phase 17 D-19 shipped `_assert_can_expire(membership)` for the 9-cell TESTS-10 matrix; the bulk UPDATE deliberately does NOT call it. Rationale:
  - The SQL `WHERE status='active'` clause is the gate — Postgres MVCC isolates concurrent admin cancels (cancel's UPDATE filter `status='active'` and the cron's UPDATE filter `status='active'` race on the row lock; whichever commits first wins, the loser sees 0 rows and emits no event).
  - Calling `_assert_can_expire` per row would require a `SELECT id FOR UPDATE` pre-flight (N+1 reads); ROADMAP SC#1 explicitly mandates "single-transaction `UPDATE … RETURNING`".
  - `_assert_can_expire` stays in `service.py` for the unit-test matrix coverage, but it has no caller in production code in v1.2 (it would be invoked by a hypothetical "manually expire one row via API" endpoint, which doesn't exist and isn't planned).

### Bulk SQL shape (locked sub-decision of D-01)

- **D-04:** **`UPDATE … RETURNING id, client_id` (not just `id`).** The audit payload for `membership_expired` is locked at `{membership_id, client_id}` (LOCKED_AUDIT_EVENTS in `app/core/audit.py:104`). Returning both columns avoids a follow-up SELECT to look up `client_id`s by `id`s. Implementation: SQLAlchemy Core `update(Membership).where(Membership.end_date < today, Membership.status == "active").values(status="expired").returning(Membership.id, Membership.client_id)`. The query is in `app/modules/memberships/repository.py:expire_due_rows(session, today)` returning `Sequence[Row]` (tuples of (UUID, UUID)); service consumes the rows, iterates emitting audits, returns `len(rows)`. Single transaction; no flush between UPDATE and emit (audit_log INSERTs and the membership UPDATE all flow into the same `session.commit()` at the worker boundary).
- **D-05:** **`today` parameter is `datetime.date`, computed in the service from `datetime.now(ZoneInfo("Europe/Moscow")).date()` if not passed.** Tests pass an explicit `today` for determinism (the fixture fakes "yesterday" by inserting a row with `end_date = today - 1`). Production-path call from the worker passes `today=None` and the service computes it. Rationale: same shape as Phase 17 D-04 `start_date` computation (Python-side, testable); the strict `<` comparison + the SQL-side use of `CURRENT_DATE` are subtly different (Postgres `CURRENT_DATE` is server-clock, server-TZ — and we set container `TZ=UTC` for the worker, which would make `CURRENT_DATE` mean "UTC date" not "MSK date"). Using a Python-side `date` parameter compares against `Membership.end_date` as `< :today` literally, removing TZ ambiguity. ROADMAP SC#1 wording uses `CURRENT_DATE` informally — the planner translates to a parameterized comparison.

### Compose + worker placement (Claude's discretion; user did not select for discussion)

- **CD-01 (default applied):** **Delete `app/workers/arq_app.py`.** It is a placeholder with `functions=[]` from Phase A WORK-01; ARQ-03 locks the import path as `app.workers.WorkerSettings` (i.e., the class lives in `__init__.py`). Keeping `arq_app.py` as a re-export creates two import paths for the same class, which is the kind of drift the OpenAPI byte-stable gate exists to prevent at the API boundary. Cleaner to have one canonical location matching the docker-compose `command:` string. **User can override by saying "keep arq_app.py"** in the plan-phase review.
- **CD-02 (default applied):** **Add `arq-worker` service to the existing `apps/backend/docker-compose.yml`** rather than creating a new `infra/docker-compose.yml`. ARQ-04's wording (`infra/docker-compose.yml`) is research-vintage — when the v1.0 phase landed the compose file lived at `apps/backend/docker-compose.yml`, and the 4 current services (`backend`, `telegram-bot`, `migrate`, `postgres`, `redis`) all live there. Moving the file to `infra/` would touch CI workflow paths, dev `make` targets, and `.env` lookups for unrelated reasons. The REQUIREMENTS wording is reconciled by a small REQUIREMENTS.md edit in this phase (or a deviation note in `18-VERIFICATION.md`). **User can override by saying "actually relocate to `infra/`"** at plan time.

### Observability defaults (Claude's discretion)

- **CD-03 (default applied):** **Emit one structlog INFO `expire_memberships_complete count=N` from the worker entry after `session.commit()` returns.** PITFALLS Pitfall 14 mitigation step 1 explicitly recommends this for the first real cron. Cheap (one line), gives ops `count=0` lines on days when nothing expires (proves the cron ran and the connection worked), and the `job_id`/`job_name` are already bound by `on_job_start` so the line is correlatable to the run. Test (ARQ-TEST-01) asserts the line is emitted exactly once with the expected count.
- **CD-04 (default applied):** **`on_startup` cron-resolution assertion.** PITFALLS Pitfall 4 step 6: ARQ silently does nothing if `cron_jobs` points at a function name not in `functions`. The 3-line assertion (`assert all(c.coroutine.__name__ in {f.__name__ for f in functions} for c in cron_jobs)`) catches this at worker boot, not at 06:05 the next morning. Wired in `on_startup`; tested at the unit level by importing `WorkerSettings` and exercising the assertion against a mutated copy.
- **CD-05 (default applied):** **Test placement under `tests/integration/workers/` and `tests/unit/workers/`.** Mirrors clients/memberships test layout (`tests/{integration,unit}/<module>/`). The integration tests need a real DB (SAVEPOINT-based isolation per `db_session` fixture from Phase 4 D-26). The unit tests for WorkerSettings and contextvars do not need DB.

### `_assert_can_expire` retention (related to D-03)

- **CD-06 (default applied):** **Keep `_assert_can_expire` in `app/modules/memberships/service.py` even though the bulk path doesn't call it.** Phase 17 D-19 + TESTS-10 (9-cell state matrix) reference this helper for completeness. Removing it would shrink the matrix to 6 cells and undo Phase 17 verification. The helper has zero call-sites in production v1.2 code but earns its keep as the documented contract for "active is the only valid source state of an `expire` action".

### Locked-not-discussed (carried verbatim from REQUIREMENTS / Phase 15 / ROADMAP / research)

- **Cron tick** = `cron(expire_memberships, hour=3, minute=5, unique=True, keep_cronjob_progress=60)` → 06:05 Europe/Moscow with container `TZ=UTC`. Locked ARQ-03 + ROADMAP SC#3.
- **Audit payload shape** = `{membership_id, client_id}` exactly. Locked LOCKED_AUDIT_EVENTS (`app/core/audit.py:104`).
- **`actor_user_id=None`** for system-driven expiry. Locked ARQ-02 + research ARCHITECTURE.md `actor_kind = 'system'`.
- **Idempotency mechanism** = SQL-level (`WHERE status='active'`); ARQ `unique=True` is necessary-not-sufficient. Locked PITFALLS #4.
- **`scheduler.py` deletion** = mandated by ARQ-04. Locked.
- **`workers ⊥ modules` not enforced**, D-09 documents the targeted exception. Locked Phase 15 / SUMMARY.
- **Inclusive `end_date`**: a membership ending today stays `active` until tomorrow morning's tick (strict `<`). Locked Phase 15 PROJECT.md Key Decisions.
- **No new runtime deps**: ARQ 0.26 is already in `pyproject.toml`; `cron` import = `from arq.cron import cron`. Locked SUMMARY.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Project context (read first)
- `.planning/PROJECT.md` — project description, Constraints (РФ/СНГ), Key Decisions table (incl. inclusive `end_date`, `gym_date` Europe/Moscow STORED, accepted residual fraud risk, all v1.2 entries from Phase 15) and the explicit D-09 wording for "ARQ `expire_memberships` placed in `app/workers/scheduled/` importing `app.modules.memberships.service` — documented as **D-09**".
- `.planning/REQUIREMENTS.md` — Phase 18 owns ARQ-01..05, ARQ-TEST-01..02. ARQ-02 verbatim is the SQL contract; ARQ-03 verbatim is the WorkerSettings contract; ARQ-04 verbatim is the docker-compose contract (note CD-02 path reconciliation).
- `.planning/ROADMAP.md` §"Phase 18: ARQ scheduled `expire_memberships`" — phase goal + Success Criteria 1-5 + dependency note (depends on Phase 17, parallel-eligible with Phase 19).
- `.planning/STATE.md` §"Decisions" — accumulated v1.2 decisions including D-09 line item.

### Phase 17 outputs (direct precursor)
- `.planning/phases/17-membership-instances-resolver-backend/17-CONTEXT.md` — D-19 (9-cell state matrix + `_assert_can_expire`); Phase 17 BusinessService template + AST commit gate already cover `app.modules.memberships.service`.
- `.planning/phases/17-membership-instances-resolver-backend/17-VERIFICATION.md` — confirms Phase 17 SC: `Membership` model + service (sale + cancel + resolver) shipped; `update_status` repo helper exists; `_assert_can_expire` exists. Phase 18 builds on top.
- `apps/backend/app/modules/memberships/service.py` — patterns Phase 18 mirrors (commit ownership, `audit.emit` co-transactional, `BusinessService` template).
- `apps/backend/app/modules/memberships/repository.py` lines 260-279 — `update_status` narrow setter (Phase 18's bulk variant lives alongside it).

### Phase 15 outputs (foundation contract)
- `.planning/phases/15-foundations-rbac-audit-taxonomy-helper-hoisting/15-CONTEXT.md` — INFRA-11 audit taxonomy lock; INFRA-13 service-write commit gate (and the `# noqa: SVC001` documented opt-out path; planner verifies whether worker-only service functions are auto-exempt or require the noqa).
- `apps/backend/app/core/audit.py` — `LOCKED_AUDIT_EVENTS` line 104 declares `("membership_expired", "membership")` with payload `{membership_id, client_id}`. The AST taxonomy walker (`tests/unit/test_audit_taxonomy.py`) enforces literal-string callsite.
- `apps/backend/app/core/middleware.py` — `RequestIdMiddleware` lines 21-25 are the `clear_contextvars + bind_contextvars` shape Phase 18 mirrors in `on_job_start`/`on_job_end`.

### Research outputs (v1.2 — global)
- `.planning/research/SUMMARY.md` §"Phase 18 (first real ARQ cron)" — explicit task list + recommended file shape (the `async def expire_memberships(ctx) -> int` sketch is the canonical worker entry).
- `.planning/research/PITFALLS.md` Pitfall 4 ("ARQ `expire_memberships` job not idempotent") — full mitigation: single-transaction UPDATE + RETURNING, on_startup cron-resolution assertion, monkey-patched-clock test. Pitfall 14 ("ARQ job has no structlog request_id correlation") — `on_job_start`/`on_job_end` contextvars binding pattern.
- `.planning/research/ARCHITECTURE.md` §"D-09" — full rationale for placing the job under `workers/scheduled/` not `modules/memberships/jobs.py`.
- `.planning/research/STACK.md` — confirms zero new runtime deps; ARQ 0.26 cron API; container `TZ=UTC` policy.
- `.planning/research/FEATURES.md` M-4 ("ARQ daily expiry job") — feature contract; "expired" never appears without this; sequential vs bulk discussion.

### Backend codebase — direct templates
- `apps/backend/app/workers/__init__.py` — current placeholder docstring; Phase 18 replaces with real `WorkerSettings` class.
- `apps/backend/app/workers/arq_app.py` — current skeleton (functions=[], redis_settings only); deletion candidate per CD-01.
- `apps/backend/app/workers/scheduler.py` — placeholder; deletion mandated by ARQ-04.
- `apps/backend/app/workers/telegram_bot.py` — companion long-polling worker; lines 23-65 show the `db_lifespan_manager + AsyncExitStack` pattern Phase 18's `on_startup`/`on_shutdown` mirrors. Specifically lines 55-59 (`stack.enter_async_context(db_lifespan_manager())` + `session_factory=sessionmaker`).
- `apps/backend/app/core/database.py` lines 109-141 — `db_lifespan_manager()` returns `(engine, sessionmaker)`; this is what `on_startup` opens for the cron worker.
- `apps/backend/app/core/audit.py:emit()` lines 119-173 — the audit emit signature; the worker's per-row loop calls this with literal `event="membership_expired"`, literal `resource_type="membership"`, and `actor_user_id=None`.
- `apps/backend/app/core/logging.py` — structlog config with `merge_contextvars`; the `on_job_start` contextvars binding flows into all log lines emitted during the job (audit + summary).
- `apps/backend/app/core/middleware.py:RequestIdMiddleware` — exact `clear_contextvars` + `bind_contextvars` template.
- `apps/backend/app/core/config.py` — `get_settings().redis_url` for `RedisSettings.from_dsn(...)` in WorkerSettings.

### Backend codebase — wiring touch-points
- `apps/backend/docker-compose.yml` — current 4-service file (`backend`, `telegram-bot`, `migrate`, `postgres`, `redis`). Phase 18 adds 5th service `arq-worker` per CD-02 (NOT `infra/docker-compose.yml` despite ARQ-04 wording).
- `apps/backend/.importlinter` — three contracts unchanged. `app.workers.scheduled.expire_memberships → app.modules.memberships.service` is legal (no `workers ⊥ modules` contract). Confirm green via `uv run lint-imports` in CI.

### ARQ documentation (third-party)
- [ARQ docs index](https://arq-docs.helpmanual.io/) — `cron_jobs`, `unique=True`, `keep_cronjob_progress` semantics; `WorkerSettings` shape; `on_startup`/`on_shutdown`/`on_job_start`/`on_job_end` lifecycle hooks.
- [ARQ issue #193 — cron job scheduling behaviour](https://github.com/samuelcolvin/arq/issues/193) — `unique=True` does not protect against worker-restart re-runs; SQL-level idempotency is required. Cited in PITFALLS #4.

### Tests (Phase 18 adds; Phase 15 enforces)
- `apps/backend/tests/unit/test_audit_taxonomy.py` — Phase 15 INFRA-11 AST walker; the new `audit.emit("membership_expired", …)` callsite passes verbatim because the literal string is already in `LOCKED_AUDIT_EVENTS`.
- `apps/backend/tests/unit/test_service_commit_gate.py` — Phase 15 INFRA-13 AST commit gate. `app.modules.memberships.service.expire_due_memberships` is a write path; planner verifies whether the gate's auto-exemption for "service called only from `app.workers.*`" applies, or whether `# noqa: SVC001` is required (per Phase 15 INFRA-13 documented opt-out).
- `apps/backend/tests/integration/conftest.py` — `db_session` fixture (SAVEPOINT-based per-test isolation against real Postgres); the new `tests/integration/workers/conftest.py` extends with a `make_membership(end_date=...)` factory.

### Conventions (read for style consistency)
- `.planning/codebase/CONVENTIONS.md`, `STRUCTURE.md`, `TESTING.md`.
- `apps/backend/docs/conventions.md` — backend-specific (camelCase wire / snake_case Python; service-write commit discipline).
- `apps/backend/docs/architecture.md` — modular monolith doc; will gain a one-paragraph addendum on D-09 (workers→module exception) in this phase.
- `apps/backend/docs/adr/0001-modular-monolith.md` — ADR for the import-linter contracts; D-09 is documented as a narrative exception, NOT a contract relaxation, and the ADR text stays accurate.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets

- **`db_lifespan_manager` from `core/database.py`** (lines 109-141) — Phase 18 `on_startup` opens it via `AsyncExitStack` and stashes the resulting `(engine, sessionmaker)` in `ctx`. Exact mirror of `app/workers/telegram_bot.py:55-59`. The `engine` reference must survive `on_startup`'s return so that `on_shutdown` can close it; using `ctx["_db_stack"]` (an `AsyncExitStack` instance) is the natural carrier.
- **`audit.emit` co-transactional contract** (`app/core/audit.py:119-173`) — Phase 18's per-row emit calls slot in cleanly: same session, no flush/commit inside emit, AuditLog rows are part of the worker's single transaction. The locked-events guard fires before any structlog/DB write so a typo at the new callsite fails loud, not silent.
- **Phase 17 `_assert_can_expire`** (`app/modules/memberships/service.py:118-129`) — exists from Phase 17 D-19; Phase 18 deliberately does NOT call it (D-03), but the helper stays for the TESTS-10 9-cell matrix.
- **Phase 17 `update_status` repo setter** (`app/modules/memberships/repository.py:260-279`) — narrow lifecycle setter; Phase 18 adds a sibling `expire_due_rows(session, today)` for the bulk path. Both coexist (single-row cancel via `update_status`; bulk expire via `expire_due_rows`).
- **`structlog.contextvars.{clear,bind}_contextvars`** — already used by `RequestIdMiddleware` (`app/core/middleware.py:21-25`); Phase 18 binds `job_id` + `job_name` in the `on_job_start` hook with the same shape.
- **`AsyncExitStack` pattern** — `app/workers/telegram_bot.py:50-65` shows the canonical "open multiple lifespan managers, store the stack, close on shutdown" idiom.
- **PEP 735 dev dependency `pytest-asyncio` + `httpx ASGITransport`** — already in scope; Phase 18 tests use them (no real ARQ runtime; `await expire_memberships(ctx)` is just an async function call).

### Established Patterns

- **Service owns mutate + audit emit; caller owns commit** — Phase 17 cancel pattern; Phase 18 D-01 mirrors. The wrinkle is that Phase 17's caller is the FastAPI router (per-request transaction), Phase 18's caller is the worker (per-job transaction). The shape is the same; the lifecycle changes.
- **Literal-string `audit.emit` callsites** — Phase 15 INFRA-11 AST walker; Phase 18's `audit.emit("membership_expired", resource_type="membership", …)` uses literal strings.
- **Single-transaction co-transactional audit** — UPDATE + N audit INSERTs all flow into one `await session.commit()`. If any audit's locked-events check fails, the whole batch rolls back and the next run picks up the same rows (idempotent retry).
- **`_engine` is `_` because we don't reuse it** — `app/workers/telegram_bot.py:55` shows this convention; Phase 18 follows.
- **Container `TZ=UTC`** — locked Phase 15 Key Decisions; the worker reads MSK only via Python `ZoneInfo("Europe/Moscow")`, never via process env.
- **Tests under `tests/{unit,integration}/<scope>/`** — Phase 18 creates `tests/integration/workers/` and `tests/unit/workers/` (new top-level test scope; mirrors `clients/`, `memberships/`, `auth/`).
- **No `# noqa` unless documented** — the `# noqa: SVC001` in `expire_due_memberships` (if needed) carries a one-line comment explaining why ("commit owned by worker entry per Phase 18 D-04").

### Integration Points

- **`apps/backend/docker-compose.yml`** — Phase 18 adds 5th service `arq-worker`; depends on `migrate` (DB schema must be live) + `redis` (ARQ queue). No port exposure (worker doesn't accept HTTP).
- **`app/workers/__init__.py`** — replaces placeholder docstring with `WorkerSettings` class. The narrative docstring at module top stays (D-06 + D-09 documentation), but the file gains code.
- **`app/workers/arq_app.py`** — deletion candidate per CD-01. If the user vetoes deletion at plan time, the file becomes a 3-line re-export `from app.workers import WorkerSettings as _; WorkerSettings = _` — not done by default.
- **`app/workers/scheduler.py`** — deletion mandated by ARQ-04.
- **No OpenAPI changes** — `expire_memberships` is not an HTTP route. `apps/backend/openapi.json` byte-stable check stays green without intervention. Phase 21 still owns the next FE-facing OpenAPI refresh.
- **`.importlinter` contracts** — unchanged; Phase 18's worker→module edge is legal under D-09 (no contract enforces `workers ⊥ modules`).
- **`AGENTS.md` / `CLAUDE.md`** — no edit needed; project-instructions don't reference cron jobs.

</code_context>

<specifics>
## Specific Ideas

- The user wants the service-owned commit pattern even though the worker is the transaction owner — this is a deliberate inversion of "service commits" because the worker holds the session lifecycle. The planner must reconcile this with the AST commit-gate (Phase 15 INFRA-13) explicitly: either rely on the gate's documented worker-only-caller exemption, or apply `# noqa: SVC001` with the comment "commit owned by worker entry per Phase 18 D-04". Picking one and documenting in the plan + the function docstring is non-negotiable; both are acceptable, the choice should be explicit not silent.
- The end-of-run summary log line `expire_memberships_complete count=N` is keyed to the locked event-name pattern (`<event>_complete`) for future cron jobs — if v1.3+ adds `expire_otps`, `aggregate_visits_daily`, etc., they all log `<name>_complete count=N` with the same shape. Phase 18 establishes the convention.

</specifics>

<deferred>
## Deferred Ideas

- **Bulk-aggregated `membership_expired` audit event for runs > 200 rows** — PITFALLS scaling note. Not relevant at single-zal scale (active memberships in the hundreds; daily expiries in single digits). Revisit if/when the project grows past 10 zals.
- **Expiring-soon Telegram notifications** — would reuse the worker infra Phase 18 lays down (separate `cron_jobs` entry + new `app/workers/scheduled/notify_expiring.py`); explicitly v1.3+ per PROJECT.md.
- **APScheduler / pg_cron migration** — research SUMMARY rejected; ARQ 0.26 cron is sufficient.
- **`time-machine` dev dep** — research SUMMARY: "Defer until pain forces it". Phase 18 tests use parameterized `today` instead of clock-patching, which avoids the dep entirely.
- **`infra/docker-compose.yml` relocation** — CD-02 default keeps the file at `apps/backend/`. If a future phase consolidates infra files (terraform, k8s, etc.) under `infra/`, the compose move can come with that.
- **Multi-process ARQ workers (one per job class)** — single `arq-worker` process handles all `WorkerSettings.functions` for v1.2; horizontal scaling not relevant at single-zal scale.

</deferred>

<next_steps>
## Next Steps

1. Review this CONTEXT.md (especially CD-01..CD-05 if any default doesn't match your preference).
2. `/clear` then `/gsd-plan-phase 18` to draft `18-NN-PLAN.md` files.

</next_steps>
