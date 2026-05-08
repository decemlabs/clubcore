---
gsd_state_version: 1.0
milestone: v1.2
milestone_name: Memberships + Visits
status: planning
stopped_at: Phase 21 context gathered
last_updated: "2026-05-08T08:12:15.799Z"
last_activity: 2026-05-08
progress:
  total_phases: 9
  completed_phases: 6
  total_plans: 29
  completed_plans: 29
  percent: 100
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-05-07)

**Core value:** Соло backend-разработчик с AI-агентами должен уметь поэтапно наращивать бизнес-фичи зала на стабильном, архитектурно ограниченном каркасе — без переписывания структуры по мере роста.
**Current focus:** Phase 20 — telegram-bot-checkin-self-check-in

## Current Position

Phase: 21
Plan: Not started
Status: Ready to plan
Last activity: 2026-05-08

## Performance Metrics

**Velocity:**

- Total plans completed: 3 (this milestone)
- Average duration: —
- Total execution time: 0.0 hours

**By Phase (v1.2):**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 15. Foundations — RBAC + audit taxonomy + helper hoisting | 0/TBD | — | — |
| 16. Membership Plans Catalog (backend) | 0/TBD | — | — |
| 17. Membership Instances + Resolver (backend) | 0/TBD | — | — |
| 18. ARQ scheduled `expire_memberships` | 0/TBD | — | — |
| 19. Visits — DB + reception check-in (backend) | 0/TBD | — | — |
| 20. Telegram bot `/checkin` self check-in | 0/TBD | — | — |
| 21. OpenAPI drift gate refresh + api-client codegen | 0/TBD | — | — |
| 22. admin-web wiring — memberships + visits + active sessions UI | 0/TBD | — | — |
| 23. Hygiene + active sessions backend | 0/TBD | — | — |
| 20 | 3 | - | - |

**Recent Trend:**

- Last 5 plans: none yet (this milestone)
- Trend: —

*Updated after each plan completion.*
| Phase 18 P01 | 6 min | 2 tasks | 5 files |
| Phase 18 P04 | 2min | 2 tasks | 2 files |
| Phase 18 P02 | 1min | 2 tasks | 2 files |
| Phase 18 P03 | 5min | 2 tasks | 4 files (1 source, 2 docs, 2 deletions) |
| Phase 18-arq-scheduled-expire-memberships P05 | 5min | 3 tasks | 4 files |
| Phase 18 P06 | 5min | 3 tasks | 3 files |

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work (carried into v1.2 + new):

- Modular monolith (`core` / `modules` / `integrations` / `workers` / `api`) — locked
- Python package named `app` (not `sportzal`) — locked
- `frontend/` → `apps/admin-web/` without rewriting internals — locked
- `import-linter` enforced from Phase A onward — locked
- v1.2 phase numbering continues from v1.1 (last phase was 14 → v1.2 starts at 15); no `--reset-phase-numbers`
- v1.2 build order (from research): 15 → 16 → 17 → {18 ∥ 19} → 20 → 21 → 22; 23 parallel-eligible with anything after 15
- RBAC primitives stay in `core` (extended with `Action.{CREATE, CANCEL, CHECK_IN}` + `Resource.{MEMBERSHIPS, MEMBERSHIP_PLANS, VISITS}` in Phase 15)
- Cross-module callbacks (visits → memberships) use Protocol `ActiveMembershipResolver` in `core/dependencies.py`, registered from `app/main.py` — direct mirror of v1.1 `register_user_loader`
- ARQ `expire_memberships` placed in `app/workers/scheduled/` importing `app.modules.memberships.service` — documented as **D-09** (no `workers ⊥ modules` contract exists)
- Telegram `/checkin` handler receives `visits_service` via `HandlerContext` (NOT direct import) — documented as **D-10** parallel to D-06
- Membership `end_date` is **inclusive** (last valid check-in day = `end_date`); ARQ filter uses strict `<` against `CURRENT_DATE` — locked in Phase 15 Key Decisions
- `gym_date` defined as `(checked_in_at AT TIME ZONE 'Europe/Moscow')::date` and materialized as a `GENERATED ALWAYS AS … STORED` Postgres column; `UNIQUE (client_id, gym_date)` enforces 1/day at DB level (not app-layer) — locked in Phase 15
- Membership snapshot pricing is mandatory: `plan_name_snapshot`, `duration_days_snapshot`, `price_kopecks_snapshot` NOT NULL at insert + `ON DELETE RESTRICT` FK to plan
- ARQ cron tick: container `TZ=UTC` + `cron(hour=3, minute=5, unique=True)` (06:05 Europe/Moscow)
- Reception still has `(CREATE, MEMBERSHIPS)` and `(CHECK_IN, VISITS)`; ONLY plan-catalog mutations + membership cancel + plan delete are owner-only (extends v1.1 `OWNER_ONLY` frozenset by 6 entries)
- Telegram `/checkin` rejection DMs are LOCKED constants (single generic string per branch, no client name / end_date / hours / membership status oracle leak); Russian copy signed off by owner before Phase 20 merge
- Accepted residual friend-fraud risk for v1.2 single-zal scope — recorded in PROJECT.md Key Decisions in Phase 15
- [Phase ?]: Phase 18 Plan 01: SVC prefix added to ruff lint.external for first production SVC001 callsite
- [Phase ?]: Phase 18 Plan 04: arq-worker compose service shipped at apps/backend/docker-compose.yml (CD-02 honoured); REQUIREMENTS.md ARQ-04 + ARQ-TEST-01 wording reconciled with Phase 15 inclusive-end_date Key Decision (W-3 closed)
- [Phase 18]: Plan 18-02: Worker entry owns session.commit (D-01) — async with session_factory() as session block scopes the transaction; commit happens in the worker after _expire_due_memberships returns. Service helper carries SVC001 caller-owns-txn marker.
- [Phase 18]: Plan 18-02: Summary log shape <job_name>_complete count=N AFTER commit (CD-03) — Single structlog INFO emitted after session.commit() returns successfully — proves the cron tick booted, the connection worked, and the SQL resolved. Locks the convention for all future scheduled jobs (v1.3+ expire_otps_complete, aggregate_visits_daily_complete).
- [Phase ?]: Phase 18 Plan 18-03 — WorkerSettings cron-resolution invariant in on_startup (CD-04, Pitfall 4 step 6)
- [Phase ?]: Phase 18 Plan 18-03 — WorkerSettings on_job_start mirrors RequestIdMiddleware shape (Pitfall 14): clear_contextvars() then bind_contextvars(job_id, job_name); on_job_end clears. Locks structlog correlation pattern for all future ARQ scheduled jobs.
- [Phase ?]: Phase 18 Plan 18-03 Rule 4 deviation — arq>=0.26 floor pin resolved to 0.28.0 which removed cron(keep_cronjob_progress=...). Implementation uses keep_result=60 (closest 0.28 semantic). User to confirm at 18-VERIFICATION whether to (a) update REQUIREMENTS.md ARQ-03 to the 0.28 API or (b) pin arq<0.27. Recommended (a).
- [Phase ?]: Phase 18 Plan 18-03 — app/workers/arq_app.py + app/workers/scheduler.py DELETED (CD-01 + ARQ-04). Single canonical ARQ entrypoint at app.workers.WorkerSettings; matches docker-compose command from Plan 18-04.
- [Phase ?]: Phase 18 W-2 SAVEPOINT auto-restart resolved via Branch A — outer db_session fixture's join_transaction_mode='create_savepoint' suffices (Plan 18-05)
- [Phase ?]: Phase 18 W-3 (Plan 18-05): structlog cached-logger invalidation autouse fixture required for any test scope mixing module-level loggers with capture_logs and per-test create_app() reconfigure
- [Phase ?]: Phase 18-06: W-1 probe locked Form B (bare ints) — ARQ 0.28 cron stores hour/minute as int, not set
- [Phase ?]: Phase 18-06: Rule 1 fix — unit tests assert on cron_jobs[0].coroutine.__name__ + .keep_result_s instead of .name + .keep_cronjob_progress (ARQ 0.28 attribute reality)

### Pending Todos

None yet (roadmap just created).

### Blockers/Concerns

- Phase 18 (first real ARQ cron) flagged in SUMMARY.md for plan-time research: validate `unique=True` on docker restart, `keep_cronjob_progress=60` semantics, `on_startup` cron resolution assertion, `job_id` contextvars binding design.
- Phase 20 flagged: Russian DM copy needs explicit owner sign-off; Redis `update_id` dedup key-prefix discipline alongside `arq:*` and `sz:session:*`; residual-risk Key Decisions entry must land in PROJECT.md during Phase 15 (not Phase 20).
- Phase 22 flagged: confirm `eslint.config.js` `import/no-restricted-paths` rules support Pattern α (route composes features, `features/clients` does not import `features/memberships`/`features/visits`).

### Quick Tasks Completed

| # | Description | Date | Commit | Directory |
|---|-------------|------|--------|-----------|
| 260501-ndi | Migrate uv dev deps from `[tool.uv].dev-dependencies` to `[dependency-groups].dev` (PEP 735) | 2026-05-01 | 71f28de | [260501-ndi-fix-pyproject-toml-migrate-dev-deps-from](./quick/260501-ndi-fix-pyproject-toml-migrate-dev-deps-from/) |
| 260504-uws | Add root `.gitignore` (DS_Store/node_modules/.claude) + exclude `*.test.tsx` from TanStack Router scan | 2026-05-04 | 40a2b3c, 064b35e | [260504-uws-adminweb-cleanup](./quick/260504-uws-adminweb-cleanup/) |
| 260504-fst | Phase 12.1 fix: `await session.commit()` in clients/service.py write paths + persistence regression test; resolves Phase 11 SC #4 | 2026-05-04 | ba14aba | (inline /gsd-fast) |

## Deferred Items

Items acknowledged and deferred at v1.1 milestone close on 2026-05-07 (carried into v1.2 retrospective view, NOT v1.2 scope):

| Category | Item | Status | Deferred At |
|----------|------|--------|-------------|
| uat_gap | Phase 06 06-HUMAN-UAT.md (2 pending scenarios) | partial | 2026-05-07 (v1.1 close) |
| uat_gap | Phase 08 08-HUMAN-UAT.md (2 pending scenarios) | partial | 2026-05-07 (v1.1 close) |
| uat_gap | Phase 11 11-HUMAN-UAT.md (0 pending — flagged by audit-open metadata only; resolved in body) | resolved | 2026-05-07 (v1.1 close) |
| quick_task | 260501-ndi (status metadata missing; commit 71f28de shipped 2026-05-01) | missing-meta | 2026-05-07 (v1.1 close) |

## Session Continuity

Last session: 2026-05-08T08:12:15.795Z
Stopped at: Phase 21 context gathered
Resume file: .planning/phases/21-openapi-drift-gate-refresh-api-client-codegen/21-CONTEXT.md
