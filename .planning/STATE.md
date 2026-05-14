---
gsd_state_version: 1.0
milestone: v1.4
milestone_name: Cash Sales + PT Packages
status: planning
last_updated: "2026-05-14T10:26:25.353Z"
last_activity: 2026-05-14
progress:
  total_phases: 0
  completed_phases: 0
  total_plans: 0
  completed_plans: 0
  percent: 0
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-05-14)

**Core value:** Соло backend-разработчик с AI-агентами должен уметь поэтапно наращивать бизнес-фичи зала на стабильном, архитектурно ограниченном каркасе — без переписывания структуры по мере роста.
**Current focus:** Planning v1.4 — run `/gsd-new-milestone` to begin questioning → research → requirements → roadmap. Carry-over candidates listed in PROJECT.md under "Next Milestone Goals" (Billing, owner notification config, paid freeze, audit log read API, visit-count plans, admin-web housekeeping).

## Current Position

Phase: Not started (defining requirements)
Plan: —
Status: Defining requirements
Last activity: 2026-05-14 — Milestone v1.4 started

## v1.3 Milestone Summary

**Shipped:** 2026-05-14 (6 days, 199 commits, 45 feat)
**Phases:** 24 (Foundations & Tech-Debt) → 25 (Freeze) → 26 (Renewal) → 27 (Expiring-soon Telegram) → 28 (OpenAPI drift gate + admin-web wiring) → 29 (Milestone verification)
**Plans / tasks:** 33 / 29
**Tests:** backend 729 (95 files), admin-web 233 (41 files) — all green; 6/6 CI gates green
**Verification:** Phase 29 acted as the milestone audit — passed (7/7 human-verification scenarios + cross-phase smoke; 3 production-blocker regressions REG-29-01/03/04 found and fixed inline; 1 minor UX gap deferred to v1.4); operator sign-off in `.planning/milestones/v1.3-VERIFICATION-LOG.md`.
**Archive:** `.planning/milestones/v1.3-ROADMAP.md`, `.planning/milestones/v1.3-REQUIREMENTS.md`, `.planning/milestones/v1.3-VERIFICATION-LOG.md`.
**Tag:** `v1.3` (annotated; to be created during close sequence).

## Accumulated Context

### Decisions

Full decisions log lives in PROJECT.md Key Decisions table. v1.3 added 12 new locked decisions covering status taxonomy guard, resolver defence-in-depth filter, mock/http parity for `?expiring=`/`?within=`, freeze concurrency / day accounting, renewal date strategy + pricing + tiebreak, expiring-soon idempotency + cron ordering, `LOCKED_AUDIT_EVENTS` pre-registration discipline, and Phase 29 as milestone-verification-as-audit.

Locked v1.0–v1.2 invariants still hold (modular monolith with `core ⊥ modules` import-linter contract, Python package `app`, frontend integrity, inclusive `end_date`, `gym_date STORED + UNIQUE`, mandatory snapshot pricing, ARQ container `TZ=UTC` + `cron(unique=True, keep_result=60)`, cross-module Protocol callbacks via composition root, Telegram as separate long-polling worker, backend wire format camelCase via `BackendSchemaBase`, pagination `{items, total, page, pageSize}`).

### Pending Todos

None at milestone-close time. The next `/gsd-new-milestone` will surface v1.4 candidates.

### Blockers/Concerns

None blocking v1.4 start. Open watch-items:

- v1.1 `06-HUMAN-UAT.md` and `08-HUMAN-UAT.md` advisory scenarios were not exercised in Phase 29 sweep — re-evaluate at v1.4 scoping if any touch user-facing flows.
- The `260501-ndi` orphan directory in `.planning/quick/` should be archived during a future `/gsd-cleanup` run.

### Quick Tasks Completed

| # | Description | Date | Commit | Directory |
|---|-------------|------|--------|-----------|
| 260501-ndi | Migrate uv dev deps from `[tool.uv].dev-dependencies` to `[dependency-groups].dev` (PEP 735) | 2026-05-01 | 71f28de | [260501-ndi-fix-pyproject-toml-migrate-dev-deps-from](./quick/260501-ndi-fix-pyproject-toml-migrate-dev-deps-from/) |
| 260504-uws | Add root `.gitignore` (DS_Store/node_modules/.claude) + exclude `*.test.tsx` from TanStack Router scan | 2026-05-04 | 40a2b3c, 064b35e | [260504-uws-adminweb-cleanup](./quick/260504-uws-adminweb-cleanup/) |
| 260504-fst | Phase 12.1 fix: `await session.commit()` in clients/service.py write paths + persistence regression test; resolves Phase 11 SC #4 | 2026-05-04 | ba14aba | (inline /gsd-fast) |

## Deferred Items

Items carried into v1.3 from v1.1/v1.2 close (all resolved during v1.3):

| Category | Item | Status | Source | Resolution |
|----------|------|--------|--------|-----------|
| tech_debt | MEM-04 D-13: resolver `end_date >= today` filter | ✅ closed | v1.2 close | Phase 24 / DEBT-01 |
| tech_debt | WR-07: backend `?expiring=` query parity | ✅ closed | v1.2 close | Phase 24 / DEBT-02 |
| tech_debt | SVC001 walker scope → auth/service.py | ✅ closed | v1.2 close | Phase 24 / DEBT-03 |
| uat_gap | 22-VERIFICATION 6 human_verification smoke tests | ✅ closed | v1.2 close | Phase 29 / DEBT-04 (7/7 passed against live stack) |
| uat_gap | Phase 06 06-HUMAN-UAT.md (2 pending scenarios) | partial | v1.1 close | not exercised in Phase 29 sweep — re-evaluate if user-facing |
| uat_gap | Phase 08 08-HUMAN-UAT.md (2 pending scenarios) | partial | v1.1 close | not exercised in Phase 29 sweep — re-evaluate if user-facing |
| quick_task | 260501-ndi (status metadata missing; commit shipped) | missing-meta | v1.1 close | informational only |

### Items acknowledged and deferred at milestone close on 2026-05-14

| Category | Item | Status | Notes |
|----------|------|--------|-------|
| verification_gap | Phase 28 — `apps/admin-web/src/shared/api/services/mock/memberships.ts` `list()` does not filter by `query.status`; «Заморожен» filter pill on `/memberships` is a no-op under `VITE_API_MODE=mock` | deferred-to-v1.4 | Mock-only; `http` (production) path forwards `status` correctly. One-line fix recorded in `.planning/phases/28-openapi-drift-gate-refresh-admin-web-wiring/28-VERIFICATION.md` gap block. Will fold into v1.4 admin-web housekeeping. |
| quick_task | `260501-ndi` orphan in `.planning/quick/` from v1.0 era | acknowledged | Task itself completed 2026-05-01 (commits `71f28de`, `efdb7cc`); only the directory listing remains. Defer to `/gsd-cleanup`. |

## Session Continuity

Last session: 2026-05-14T10:05:00Z
Stopped at: v1.3 milestone close and archive complete
Resume: Run `/gsd-new-milestone` to scope v1.4.
