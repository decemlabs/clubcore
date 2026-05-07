---
gsd_state_version: 1.0
milestone: v1.2
milestone_name: Memberships + Visits
status: executing
stopped_at: Phase 18 context gathered
last_updated: "2026-05-07T18:42:43.379Z"
last_activity: 2026-05-07
progress:
  total_phases: 9
  completed_phases: 3
  total_plans: 21
  completed_plans: 17
  percent: 81
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-05-07)

**Core value:** Соло backend-разработчик с AI-агентами должен уметь поэтапно наращивать бизнес-фичи зала на стабильном, архитектурно ограниченном каркасе — без переписывания структуры по мере роста.
**Current focus:** Phase 18 — arq-scheduled-expire-memberships

## Current Position

Phase: 18 (arq-scheduled-expire-memberships) — EXECUTING
Plan: 3 of 6
Status: Ready to execute
Last activity: 2026-05-07

## Performance Metrics

**Velocity:**

- Total plans completed: 0 (this milestone)
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

**Recent Trend:**

- Last 5 plans: none yet (this milestone)
- Trend: —

*Updated after each plan completion.*
| Phase 18 P01 | 6 min | 2 tasks | 5 files |
| Phase 18 P04 | 2min | 2 tasks | 2 files |

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

Last session: 2026-05-07T18:42:27.601Z
Stopped at: Phase 18 context gathered
Resume file: None
