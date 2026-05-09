---
gsd_state_version: 1.0
milestone: v1.3
milestone_name: Memberships Extras + Tech-Debt
status: ready_to_plan
stopped_at: Phase 27 context gathered
last_updated: "2026-05-09T19:08:03.176Z"
last_activity: 2026-05-09 -- Phase 27 execution started
progress:
  total_phases: 6
  completed_phases: 4
  total_plans: 19
  completed_plans: 14
  percent: 67
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-05-08)

**Core value:** Соло backend-разработчик с AI-агентами должен уметь поэтапно наращивать бизнес-фичи зала на стабильном, архитектурно ограниченном каркасе — без переписывания структуры по мере роста.
**Current focus:** Phase 27 — expiring-soon-telegram-notifications

## Current Position

Phase: 28
Plan: Not started
Status: Ready to plan
Last activity: 2026-05-09

## Performance Metrics

**Velocity:**

- Total plans completed: 5 (this milestone)
- Average duration: —
- Total execution time: 0.0 hours

**By Phase (v1.3):**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 24. Foundations & Tech-Debt Bedrock | 0/TBD | — | — |
| 25. Memberships — Freeze (backend) | 0/TBD | — | — |
| 26. Memberships — Renewal (backend) | 0/TBD | — | — |
| 27. Expiring-soon Telegram Notifications | 0/TBD | — | — |
| 28. OpenAPI Drift-Gate Refresh + admin-web Wiring | 0/TBD | — | — |
| 29. Milestone Verification | 0/TBD | — | — |
| 27 | 5 | - | - |

**Recent Trend:**

- Last 5 plans: none yet (this milestone)
- Trend: —

*Updated after each plan completion.*
| Phase 24 P02 | 10min | 2 tasks | 7 files |

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting v1.3:

- v1.3 phase numbering continues from v1.2 (last phase 23 → v1.3 starts at Phase 24); no `--reset-phase-numbers`
- v1.3 build order: 24 → 25 → 26 → 27 → 28 → 29 (linear; 25/26 share migration `0007`, plan-time decision on combined-vs-extension revision)
- Phase 24 owns INFRA-15 + INFRA-16 + DEBT-01 + DEBT-02 + DEBT-03 (foundations + 3 of 4 tech-debt closures); DEBT-04 is human-verification, lives in Phase 29
- Resolver touch-points serialized: 24 ставит `end_date >= today` filter → 25 добавляет `status != 'frozen'` → 26 расширяет tiebreak — каждая phase оставляет резолвер в зелёном тесте
- Cron ordering 06:05 (`expire_memberships`) → 06:15 (`send_expiring_notifications`) с buffer ~10min; `unique=True` ловит docker-restart races (Phase 27)
- 6 locked Russian DM templates (NTF-COPY-01) требуют owner sign-off перед Phase 27 merge — pattern v1.2 D-5
- Phase 28 — единый drift-gate refresh после backend phases (мигрировано из v1.2 Phase 21)
- Carried-forward decisions from v1.2 close (still locked):
  - Modular monolith (`core` / `modules` / `integrations` / `workers` / `api`)
  - Python package `app`
  - `frontend/` → `apps/admin-web/` без правок internals
  - `import-linter` enforced
  - Membership `end_date` is **inclusive** (last valid check-in day)
  - `gym_date = (checked_in_at AT TIME ZONE 'Europe/Moscow')::date` STORED + `UNIQUE (client_id, gym_date)`
  - Membership snapshot pricing mandatory (`*_snapshot` columns NOT NULL + `ON DELETE RESTRICT` FK)
  - ARQ cron tick: container `TZ=UTC` + `cron(hour=H, minute=M, unique=True, keep_result=60)`
  - Cross-module callbacks via Protocol + `app/main.py` composition root
  - Telegram bot — отдельный процесс long-polling worker, НЕ ARQ task
  - Backend wire format = camelCase via `BackendSchemaBase`
  - Pagination envelope `{items, total, page, pageSize}`
- [Phase ?]: INFRA-16 Phase 24: status taxonomy locked — central _assert_can_transition guard + MEMBERSHIP_STATUS_TRANSITIONS read-only constant; Postgres CHECK admits 'frozen' as of migration 0007_status_taxonomy

### Pending Todos

None yet (roadmap just drafted; phase planning starts with `/gsd-plan-phase 24`).

### Blockers/Concerns

- **Phase 25/26 migration `0007`** — план-агент Phase 25 должен решить: единый combined revision (freeze + renewal columns) или extension hook для Phase 26. Не блокер для Phase 24.
- **Phase 27 NTF-COPY-01** — owner sign-off на 6 Russian DM strings нужен до merge; включить в Phase 27 plan-time clarification (mirror of v1.2 D-5 process).
- **Phase 27 cron ordering 06:05 → 06:15** — формализовать race-test или явно зафиксировать в Phase 27 Key Decisions, что 10-min gap + `unique=True` достаточны.
- **Phase 28 drift-gate refresh** — выполнить ровно один `git diff --exit-code` failure → regenerate → commit cycle, не больше; mirrors v1.2 Phase 21 discipline.
- **Phase 29 DEBT-04** — нужны live backend + Telegram sandbox для 6 smoke сценариев из `.planning/milestones/v1.2-phases/22-VERIFICATION.md`; ops session должна быть запланирована до старта Phase 29.

### Quick Tasks Completed

| # | Description | Date | Commit | Directory |
|---|-------------|------|--------|-----------|
| 260501-ndi | Migrate uv dev deps from `[tool.uv].dev-dependencies` to `[dependency-groups].dev` (PEP 735) | 2026-05-01 | 71f28de | [260501-ndi-fix-pyproject-toml-migrate-dev-deps-from](./quick/260501-ndi-fix-pyproject-toml-migrate-dev-deps-from/) |
| 260504-uws | Add root `.gitignore` (DS_Store/node_modules/.claude) + exclude `*.test.tsx` from TanStack Router scan | 2026-05-04 | 40a2b3c, 064b35e | [260504-uws-adminweb-cleanup](./quick/260504-uws-adminweb-cleanup/) |
| 260504-fst | Phase 12.1 fix: `await session.commit()` in clients/service.py write paths + persistence regression test; resolves Phase 11 SC #4 | 2026-05-04 | ba14aba | (inline /gsd-fast) |

## Deferred Items

Items carried into v1.3 from v1.1/v1.2 close:

| Category | Item | Status | Source | Resolution |
|----------|------|--------|--------|-----------|
| tech_debt | MEM-04 D-13: resolver `end_date >= today` filter | scheduled | v1.2 close | Phase 24 / DEBT-01 |
| tech_debt | WR-07: backend `?expiring=` query parity | scheduled | v1.2 close | Phase 24 / DEBT-02 |
| tech_debt | SVC001 walker scope → auth/service.py | scheduled | v1.2 close | Phase 24 / DEBT-03 |
| uat_gap | 22-VERIFICATION 6 human_verification smoke tests | scheduled | v1.2 close | Phase 29 / DEBT-04 |
| uat_gap | Phase 06 06-HUMAN-UAT.md (2 pending scenarios) | partial | v1.1 close | rolled into Phase 29 sweep if relevant |
| uat_gap | Phase 08 08-HUMAN-UAT.md (2 pending scenarios) | partial | v1.1 close | rolled into Phase 29 sweep if relevant |
| quick_task | 260501-ndi (status metadata missing; commit shipped) | missing-meta | v1.1 close | informational only |

## Session Continuity

Last session: 2026-05-09T18:26:59.934Z
Stopped at: Phase 27 context gathered
Resume: Next step is `/gsd-plan-phase 24` to break Phase 24 (Foundations & Tech-Debt Bedrock) into plans.
