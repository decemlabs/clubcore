# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-04-21)

**Core value:** Gym owner and reception see one coherent, daily-work-ready admin UI — a frontend foundation that can be demoed as an MVP today and swapped onto a real API later without UI rework.
**Current focus:** Phase 2 — Data Layer Contracts + Mock Infrastructure

## Current Position

Phase: 2 of 7 (Data Layer Contracts + Mock Infrastructure)
Plan: 0 of TBD in current phase — not yet planned
Status: Phase 2 context gathered — run `/gsd-research-phase 2` (MEDIUM flag) or `/gsd-plan-phase 2`
Last activity: 2026-04-21 — Phase 2 discuss complete: 02-CONTEXT.md + DISCUSSION-LOG.md written; 29 decisions across 9 areas (entity scope, mock DB shape, seeds, pagination, DomainError, latency/chaos, canonical templates, xKeys, URL search, dev toolbar, minor OQs)

Progress: [██░░░░░░░░] 14%

## Performance Metrics

**Velocity:**
- Total plans completed: 1
- Average duration: 1 session
- Total execution time: 1 session

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| Phase 1 | 1 | 1 session | 1 session |

**Recent Trend:**
- Last 5 plans: PLAN-P1 ✓
- Trend: on-track

*Updated after each plan completion.*

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table. Key pre-roadmap decisions relevant to current work:

- Frontend-only, mock data only for v1 (no backend calls)
- shadcn/ui + reui.io stack fixed by user
- Role switcher replaces login; roles via `zustand/middleware#persist`
- RU-only UI, no i18n framework
- Light + Dark theme with toggle (blocking script in `index.html` against FOUC)
- Mocks via plain service-layer (OQ#1 resolved — not MSW)
- Kids area deferred to v2 (OQ#9)

### Phase 1 Deliverables (shipped)

- 69 files in `src/` scaffolded (FSD-lite layout: app/, routes/, shared/)
- Swap seam `shared/api/services/index.ts` eager-imports `mock` | `http` via `VITE_API_MODE`
- RBAC: `routeRegistry` + `can()` + `OWNER_ONLY` consumed by sidebar, router beforeLoad, `<RoleGate>`
- Zustand stores with 3 separate persist keys: `sportzal:session:v1`, `sportzal:ui:v1`, `sportzal:mock:v1` (skipHydration + manual rehydrate before render)
- Theme bootstrap: blocking IIFE in `index.html` applies class before React mounts (no FOUC)
- ESLint flat config with 4 enforcement rules (services boundary, raw palette ban, VITE_API_MODE chokepoint, `react/no-danger`); fixtures verify rules fire
- 8 test files / 33 tests passing; build 538 KB main chunk (code-split per route)

### Pending Todos

None.

### Blockers/Concerns

- Phase 2 pre-start: confirm URL filter/search contract (OQ#3), avatar source (OQ#16), notifications poll staleTime (OQ#13), pagination envelope shape
- Phase 4 (Schedule) flagged HIGH research need — plan a react-big-calendar spike early in that phase
- Bundle main chunk 538 KB triggers Vite warning; route-level code-splitting budget to be revisited in Phase 7 (OQ#14)

## Deferred Items

| Category | Item | Status | Deferred At |
|----------|------|--------|-------------|
| Security | CSP hardening (tighten `unsafe-inline` used by theme-bootstrap IIFE) | Tracked | 2026-04-21 (Phase 1) |
| UX | Notifications / profile dropdown content beyond shell scaffolding | Tracked | 2026-04-21 (Phase 1) |

## Session Continuity

Last session: 2026-04-21
Stopped at: Phase 1 complete — all 14 requirements (FOUND-01..07, ROLE-01..05, UI-03, UI-04) marked Done in REQUIREMENTS.md; ROADMAP Phase 1 marked Done (1/1)
Resume file: `/gsd-plan-phase 2` — begin planning Data Layer Contracts + Mock Infrastructure
