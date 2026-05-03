---
gsd_state_version: 1.0
milestone: v1.1
milestone_name: Auth + Clients
status: executing
stopped_at: Phase 8 context gathered
last_updated: "2026-05-03T08:38:15.371Z"
last_activity: 2026-05-03 -- Phase 08 planning complete
progress:
  total_phases: 7
  completed_phases: 4
  total_plans: 38
  completed_plans: 30
  percent: 79
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-05-01)

**Core value:** Соло backend-разработчик с AI-агентами должен уметь поэтапно наращивать бизнес-фичи зала на стабильном, архитектурно ограниченном каркасе — без переписывания структуры по мере роста.
**Current focus:** Phase 07 — Telegram OTP Channel

## Current Position

Phase: 07 (Telegram OTP Channel) — COMPLETE ✓
Plan: 8 of 8 (07-01..07-08 done)
Status: Ready to execute
Last activity: 2026-05-03 -- Phase 08 planning complete

## Performance Metrics

**Velocity:**

- Total plans completed: 22 (this milestone)
- Average duration: —
- Total execution time: 0.0 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 4. Auth Foundations & Cookie/RBAC Primitives | 0/TBD | — | — |
| 5. User Schema + Email/Password Auth | 0/TBD | — | — |
| 6. RBAC Wiring + Parity Tests | 0/TBD | — | — |
| 7. Telegram OTP Channel | 0/TBD | — | — |
| 8. Clients Module + Audit Log | 0/TBD | — | — |
| 9. OpenAPI Pipeline + packages/api-client | 0/TBD | — | — |
| 10. admin-web Auth + Clients Wiring | 0/TBD | — | — |
| 04 | 9 | - | - |
| 05 | 8 | - | - |
| 06 | 5 | - | - |

**Recent Trend:**

- Last 5 plans: none yet (this milestone)
- Trend: —

*Updated after each plan completion*

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- Modular monolith (`core` / `modules` / `integrations` / `workers` / `api`) — locked
- Python package named `app` (not `sportzal`) — locked
- `frontend/` → `apps/admin-web/` without rewriting internals — locked
- `import-linter` enforced from Phase A onward — locked
- v1.1 phase numbering continues from v1.0 (phase 03 → phase 04); no `--reset-phase-numbers`
- v1.1 build order follows SUMMARY.md merged ordering: Foundations → Email/Password → RBAC → Telegram → Clients+Audit → OpenAPI → FE wiring
- RBAC primitives live in `core` (not `modules/auth`) to satisfy `core ⊥ modules` while letting every module import `require_permission`
- Cross-module callbacks (auth ↔ telegram bot) use a Protocol registered by `app/main.py` (composition root) — preserves `modules-independent` contract
- Pagination contract flips backend to `{items, total, page, pageSize}` to match the frozen frontend; happens in Phase 4
- Backend wire format is camelCase via Pydantic `alias_generator=to_camel`; Python identifiers stay snake_case
- `app/modules/members/` is renamed to `app/modules/clients/` in Phase 4 (frontend term canonical)
- Telegram bot is a SEPARATE process (`python -m app.workers.telegram_bot`), NOT an ARQ task — long-polling is a wrong fit for ARQ
- New deps in Phase 4: `pyjwt>=2.12.1,<3`, `argon2-cffi>=25.1.0,<26`, `python-telegram-bot>=22.7,<23`; rejected: `passlib`, `python-jose`, `aiogram`, `fastapi-csrf-protect`, `Casbin/Oso/OPA`

### Pending Todos

None yet (roadmap just created).

### Blockers/Concerns

- Phase 7 (Telegram OTP) flagged in SUMMARY.md as needing deeper research at planning time: ptb 22.x deep-linking exact API, error class hierarchy, polling vs webhook toggle
- Phase 9 (OpenAPI + api-client) flagged: `openapi-typescript` 7.13 CLI flags + FastAPI `app.openapi()` lifespan-safety with Pydantic v2 alias generators
- Phase 10 (admin-web wiring) light flag: TanStack Query 5.x retry semantics + TanStack Router protected-route idiom

### Quick Tasks Completed

| # | Description | Date | Commit | Directory |
|---|-------------|------|--------|-----------|
| 260501-ndi | Migrate uv dev deps from `[tool.uv].dev-dependencies` to `[dependency-groups].dev` (PEP 735) | 2026-05-01 | 71f28de | [260501-ndi-fix-pyproject-toml-migrate-dev-deps-from](./quick/260501-ndi-fix-pyproject-toml-migrate-dev-deps-from/) |

## Deferred Items

Items acknowledged and carried forward from previous milestone close:

| Category | Item | Status | Deferred At |
|----------|------|--------|-------------|
| *(none — Phase A is the first milestone; v1.1 starts with empty deferred queue)* | | | |

## Session Continuity

Last session: 2026-05-03T07:58:02.401Z
Stopped at: Phase 8 context gathered
Resume file: .planning/phases/08-clients-module-audit-log/08-CONTEXT.md
