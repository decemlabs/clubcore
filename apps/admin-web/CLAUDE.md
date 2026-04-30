# CLAUDE.md — SportZal Adminka

Project conventions for Claude Code. Read this before making changes.

## What this project is

React admin panel (CRM) for a single gym. Frontend-only v1 on mock data; real HTTP API plugs in later without touching UI. Two UI-toggled roles (Owner/Admin, Reception/Manager), Russian-only UI, light + dark themes.

See `.planning/PROJECT.md` for product context, `.planning/REQUIREMENTS.md` for the 79 v1 requirements, `.planning/ROADMAP.md` for the 7-phase delivery plan.

## Stack (locked)

React 19, Vite 6, TypeScript strict, Tailwind CSS v4 (CSS-first `@theme`), shadcn/ui (`new-york`, neutral) as base + reui.io via `@reui` registry entry in `components.json`, TanStack Router (file-based, typed search) + TanStack Query v5 + TanStack Table 8, Zustand 5 with `persist`, react-hook-form + zod + `@hookform/resolvers`, react-big-calendar + date-fns `ru` locale, Recharts via shadcn `<Chart>`, lucide-react, sonner. `@faker-js/faker` seeded with `faker.seed(42)`. pnpm 9, ESLint 9 flat, Vitest.

**No MSW.** Mock transport is plain service-layer functions (decision OQ#1).

## Architecture — non-negotiable

1. **Layered data flow:** `UI → TanStack Query hook → services.X → { mock | http } impl`. Components only import hooks. Enforce via ESLint `import/no-restricted-paths`.
2. **Swap seam:** `src/shared/api/services/index.ts` picks impl by `VITE_API_MODE=mock|http`. Contracts in `shared/api/contracts/`. Real-API migration = add http impls + flip default; UI/hooks/schemas/routes don't change.
3. **Domain types:** branded string UUIDv4 IDs, ISO date strings (never `Date` in domain types), money as integer minor units (kopecks) via `Money` type, discriminated unions for variant kinds, one Zod schema per resource reused by forms AND mock validation, uniform `DomainError { code, message, fields? }`.
4. **Role as session:** `useSession()` (Zustand + `persist`) exposes `{ role }`. Single `routeRegistry` + `can(role, action, resource)` is the source of truth — consumed by sidebar, router `beforeLoad`, `<RoleGate>` wrappers, and mock services (403-analog). When real auth ships, only the session source changes.
5. **Folder layout (FSD-lite):**
   ```
   src/
     app/                  # providers, queryClient, router, index.css
     routes/               # TanStack Router file tree (thin)
     features/<domain>/    # api/ (hooks + keys) · components/ · model/ · index.ts
     entities/<entity>/    # types + schemas + pure helpers
     shared/
       ui/                 # shadcn + reui primitives (copied)
       api/{contracts,services/{mock,http}}
       session/            # store + RoleGate
       lib/ config/ theme/ i18n/
   ```
   Features depend on entities + shared; features do not import other features. Mock DB is central (cross-feature refs).
6. **Query hygiene:** per-feature `xKeys` factory, `staleTime: 30_000`, `refetchOnWindowFocus: false`, optimistic mutations with `onMutate`/`onError`/`onSettled`, route `loader` uses `queryClient.ensureQueryData` with the same key as the hook.
7. **Canonical templates** in `shared/ui`: List (toolbar + filters + virtualized DataTable + pagination + three-state empty/loading/error), Detail (breadcrumb + header + tabs + side panel), Form/Wizard (grouped sections, sticky submit, dirty-guard). Every module composes these.
8. **Theming:** single `:root` / `.dark` block in `app/index.css` using shadcn tokens. Blocking `<script>` in `index.html` applies stored theme class before React mounts (no FOUC). reui reads the same CSS vars.

## Conventions

- **Money:** integer minor units (kopecks). Display via `Intl.NumberFormat('ru-RU', { style: 'currency', currency: 'RUB' })` (NBSP included).
- **Dates:** ISO strings in domain types. Display via date-fns + `ru` locale. TZ pinned to `Europe/Moscow`. Never `new Date(dateOnlyString)` — DST will bite.
- **IDs:** branded UUIDv4 string types (e.g. `type ClientId = Brand<string, 'ClientId'>`).
- **Pagination:** every list endpoint returns `{ items, total, page, pageSize }`. Never bare arrays.
- **Forms:** react-hook-form + the same Zod schema the service validates with.
- **Errors:** mock services throw `DomainError`; critical errors render as inline alerts or dialogs, not toasts. Toasts (sonner) for non-blocking acks and undo windows.
- **Russian locale:** DD.MM.YYYY, Monday week-start, 24h, `+7 (XXX) XXX-XX-XX` phone masks, `1 234,56 ₽` with NBSP, 3-form pluralization via `Intl.PluralRules('ru-RU')`. Single `src/shared/i18n/ru.ts` dictionary — no i18next.
- **Style tokens:** only semantic shadcn tokens (`bg-background`, `text-muted-foreground`, …). Raw palette colors (`bg-white`, `text-slate-900`) are banned via ESLint.
- **shadcn customization:** don't hand-edit `components/ui/*`. Put customizations in wrappers. If you must diverge, mark with `// SHADCN-DIVERGENCE: …`.
- **Mock realism:** 120–300ms latency, configurable failure rate, versioned localStorage key (`sportzal:mock:v1`), `faker.seed(42)`. Mock services enforce role access.

## Anti-features (do not build in v1)

Real auth, real SMS/email, real fiscal registrar (54-ФЗ), payment gateways, websockets/live push, audit log search, reports builder, CSV import, bulk table actions, drag-to-reschedule (unless rbc supports cleanly in Phase 4), command palette (Phase 7 budget-permitting), multi-club/multi-tenant, mobile portal, i18n runtime, kids module (OQ#9 deferred).

See `.planning/REQUIREMENTS.md` "Out of Scope" table for the full list with reasoning.

## GSD workflow

This project uses the get-shit-done (GSD) workflow (`.claude/get-shit-done/`). Key commands:

- `/gsd-plan-phase <N>` — plan a phase (produces PLAN-P{N}.md)
- `/gsd-discuss-phase <N>` — discuss/clarify before planning
- `/gsd-research-phase <N>` — deeper research for HIGH/MEDIUM-flagged phases
- `/gsd-execute-phase <N>` — execute the phase plan
- `/gsd-verify-phase <N>` — goal-backward verification

Config: `.planning/config.json` (interactive mode, fine granularity, auto-waves execution, phase commits, opus for planners). User-facing language: Russian. Docs: English.

## Where to look

- `.planning/PROJECT.md` — product context (RU)
- `.planning/REQUIREMENTS.md` — 79 v1 requirements with traceability to phases
- `.planning/ROADMAP.md` — 7 phases with goals, coverage, research flags
- `.planning/STATE.md` — project memory
- `.planning/research/SUMMARY.md` — synthesized research (TL;DR, stack, domain model, architecture principles, v1 module scope, do's and don'ts, 16 open questions)
- `.planning/research/{STACK,FEATURES,ARCHITECTURE,PITFALLS}.md` — full research docs
