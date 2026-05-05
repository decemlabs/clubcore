---
gsd_state_version: 1.0
milestone: v1.1
milestone_name: Auth + Clients
status: ready_to_plan
stopped_at: Phase 13 complete (v1.1 minor drift & hygiene cleanup — 7/7 SCs verified)
last_updated: "2026-05-05T14:15:00Z"
last_activity: 2026-05-05 -- Phase 13 execution complete
progress:
  total_phases: 12
  completed_phases: 10
  total_plans: 60
  completed_plans: 60
  percent: 100
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-05-01)

**Core value:** Соло backend-разработчик с AI-агентами должен уметь поэтапно наращивать бизнес-фичи зала на стабильном, архитектурно ограниченном каркасе — без переписывания структуры по мере роста.
**Current focus:** Phase 14 — clients-search-pii-hardening (next, ready to plan)

## Current Position

Phase: 14
Plan: Not started
Status: Ready to plan
Last activity: 2026-05-05 -- Phase 13 execution complete

## Performance Metrics

**Velocity:**

- Total plans completed: 35 (this milestone)
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
| 08 | 8 | - | - |
| 12 | 5 | - | - |

**Recent Trend:**

- Last 5 plans: none yet (this milestone)
- Trend: —

*Updated after each plan completion*
| Phase 10 P03 | 196 | 2 tasks | 7 files |
| Phase 10 P04 | 6 | 3 tasks | 12 files |
| Phase 10 P05 | 9 | 3 tasks | 23 files |
| Phase 10 P06 | 4 | 3 tasks | 12 files |
| Phase 10 P07 | 6 | 3 tasks | 11 files |
| Phase 10 P08 | 6 | 2 tasks | 7 files |

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
- [Phase ?]: HTTP methods lowercase for openapi paths type compliance; fetcher uppercases internally
- [Phase ?]: Lazy dynamic import in redirect-on-session-expired breaks queryClient<->router circular dep
- [Phase ?]: useCurrentRole hook unifies role source: mock=Zustand, http=TanStack Query cache, both branch on API_MODE
- [Phase 10 P05]: Tabs primitive: standard shadcn tabs installed as fallback — ReUI tabs 404'd from base-nova registry; uses @base-ui/react
- [Phase 10 P05]: base-ui tabs use aria-selected=true for active tab (not data-state=active like Radix); tests adapted
- [Phase 10 P05]: Test files need import/no-restricted-paths exemption for mock DB access in test setup
- [Phase ?]: useReactTable must be called before early returns (react-hooks/rules-of-hooks); vi.hoisted() for mock factories in vi.mock()
- [Phase 10 P07]: userEvent.setup() required for Radix DropdownMenu in tests — fireEvent.click does not dispatch pointer events
- [Phase 10 P07]: Hooks must be called before API_MODE early returns (react-hooks/rules-of-hooks applies to all early returns)
- [Phase 10 P07]: ESLint flat config fetch ban: separate file-targeted block per no-restricted-syntax selector — stacks additively with existing rules
- [Phase 10 P08]: TanStack Router ParsedLocation.search is the parsed object form; never concatenate with `+` (triggers Symbol.toPrimitive on the proxy → "Cannot convert object to primitive value"). Use ParsedLocation.searchStr (encoded string '' or '?...') in redirect-builders. Both are origin-free, so security guarantee of CR-01 (no scheme/host in forbidden/next) is preserved.

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
| 260504-uws | Add root `.gitignore` (DS_Store/node_modules/.claude) + exclude `*.test.tsx` from TanStack Router scan | 2026-05-04 | 40a2b3c, 064b35e | [260504-uws-adminweb-cleanup](./quick/260504-uws-adminweb-cleanup/) |
| 260504-fst | Phase 12.1 fix: `await session.commit()` in clients/service.py write paths + persistence regression test; resolves Phase 11 SC #4 | 2026-05-04 | ba14aba | (inline /gsd-fast) |

## Deferred Items

Items acknowledged and carried forward from previous milestone close:

| Category | Item | Status | Deferred At |
|----------|------|--------|-------------|
| *(none — Phase A is the first milestone; v1.1 starts with empty deferred queue)* | | | |

## Session Continuity

Last session: 2026-05-04T18:28:30.000Z
Stopped at: Completed 10-08-PLAN.md (UAT-08 gap closure — Phase 10 complete)
Resume file: None
