# Phase 2: Data Layer Contracts + Mock Infrastructure — Context

**Gathered:** 2026-04-21
**Status:** Ready for planning

<domain>
## Phase Boundary

Production-shaped data layer and canonical UI templates — no feature UI. Delivers:

- Per-domain service contracts (`shared/api/contracts/<domain>.ts`) consumed by both mock and http impls.
- Central mock infrastructure (in-memory DB, Faker seeds, latency/failure simulation, localStorage persistence) behind the swap seam already in place from Phase 1.
- Canonical UI templates (`<ListTemplate>`, `<DetailTemplate>`, `<FormTemplate>`) composed by every future feature.
- Dev-only toolbar for API mode, chaos toggles, seed reset, and mock-DB inspection.

Requirements in scope: DATA-01..12, UI-01, UI-02, UI-06. Feature UI (Clients, Schedule, Staff…) belongs to Phases 3–7.

</domain>

<decisions>
## Implementation Decisions

### Entity scope (LOCKED by user)
- **D-01:** Scaffold the **full v1 domain** in Phase 2 — types + Zod schemas + empty repositories for all ~13 entities. Feature phases then only add hooks/UI.
- **D-02:** Entities to scaffold (from research/SUMMARY §Domain Model + REQUIREMENTS):
  `Client, Staff, Service, Visit, Subscription (abonement), Payment, Product, Order, Lead, StaffSchedule, Notification, AuditEvent, FiscalReceipt`.
- **D-03:** Each entity lives in `src/entities/<name>/` with `types.ts` (branded IDs, ISO strings, Money as kopecks, discriminated unions where applicable) and `schema.ts` (one Zod schema reused by forms and mock validation).

### Mock DB shape (LOCKED by user — accepted recommendation)
- **D-04:** **Central `MockDB`** object in `src/shared/api/services/mock/db/` — one `Map<Id, Entity>` per entity table. Services receive a shared `db` reference (dependency injection at module init), mutate in-memory, and persist the snapshot.
- **D-05:** Persist full snapshot to `localStorage` under key `sportzal:mock:v1` (versioned). Writes are **throttled** (debounced ~200ms) to avoid thrashing. Read at boot, hydrate into Maps; if version mismatch → reseed.
- **D-06:** Central `relations.ts` holds pure helpers for cross-entity lookups (e.g., `getClientVisits(db, clientId)`) so services don't duplicate join logic.
- **D-07:** `faker.seed(42)` set once at seed generation; UUIDv4 IDs produced via `faker.string.uuid()` cast to branded types.

### Seeds (LOCKED by user — accepted recommendation)
- **D-08:** **Two-tier seeds**:
  - `small` — ≤5 rows per entity, used by Vitest tests; fully deterministic, loaded explicitly in test setup.
  - `demo` — realistic graph (~200 Clients, ~12 Staff, ~20 Services, ~20 Subscriptions/plan types, ~800 Visits, ~500 Payments, ~50 Products, proportional Orders/Leads/Notifications). Default for `pnpm dev`.
- **D-09:** Active seed tier is a field in the Zustand `mock` store (persist key `sportzal:mock:v1`); switching tiers triggers a full reseed + page reload (simplest honest behavior).

### Contracts + pagination envelope
- **D-10:** Every list method returns `{ items, total, page, pageSize }` (no bare arrays, no cursors — v1 is offset pagination).
- **D-11:** List inputs are a single params object: `{ page?: number; pageSize?: number; sort?: { field: string; dir: 'asc'|'desc' }; filters?: Record<string, unknown>; q?: string }`. Per-domain type narrows `filters` and `sort.field` to allowed keys.
- **D-12:** Contract files are **types-only** — no runtime imports. Enforced by existing ESLint boundary rules + tree-shaking.

### DomainError taxonomy
- **D-13:** `class DomainError extends Error` with `{ code: DomainErrorCode; message: string; fields?: Record<string, string> }`. `DomainErrorCode` enum: `NOT_FOUND | FORBIDDEN | VALIDATION | CONFLICT | INVALID_STATE | RATE_LIMITED | UNKNOWN`.
- **D-14:** Mock services throw `FORBIDDEN` when role check fails (403-analog) — exact same shape a future HTTP impl will map 403 responses to.
- **D-15:** `VALIDATION` errors carry `fields` keyed by form-field path; react-hook-form `resolver` maps them back via `setError`.

### Latency + chaos
- **D-16:** Default latency 120–300ms (uniform random) per call — matches CLAUDE.md.
- **D-17:** Default failure rate 0% in dev, but `chaos` mode in dev toolbar toggles a 10% random `UNKNOWN` error rate + latency multiplier ×3. Persisted in Zustand `mock` store (NOT in `localStorage:sportzal:mock:v1` data key — separate UI-state key).
- **D-18:** All latency/chaos injection lives in **one wrapper** `withMockEffects(fn)` at `shared/api/services/mock/_runtime.ts`. Services wrap every public method with it — no ad-hoc `setTimeout` in services.

### Canonical UI templates
- **D-19:** Three templates in `src/shared/ui/templates/`:
  - `<ListTemplate>` — toolbar slot + filters slot + DataTable slot + pagination slot. Three-state (empty / loading / error) rendered by template, NOT by feature. Virtualization via TanStack Table + `@tanstack/react-virtual` when `items.length > 100`.
  - `<DetailTemplate>` — breadcrumb + header slot + tabs slot + side-panel slot.
  - `<FormTemplate>` — grouped-sections slot + sticky submit bar + dirty-guard via `useBlocker` (TanStack Router). Accepts a single `form` prop (the RHF `UseFormReturn`) so dirty state is read off it.
- **D-20:** Templates are **composition-heavy** (children slots), not prop-soup. Feature composes; template renders layout + states.

### Query keys + loader sharing
- **D-21:** Each feature exports an `xKeys` factory (`clientKeys = { all: ['clients'] as const, list: (params) => [...clientKeys.all, 'list', params], detail: (id) => [...clientKeys.all, 'detail', id] }`). Phase 2 scaffolds the convention + one exemplar (`clientKeys`) so planner has a template.
- **D-22:** Route `loader` uses the **same** `xKeys` + `queryClient.ensureQueryData`. Scaffold the pattern in Phase 2 on a single example route (clients list) so Phase 3 copies it.
- **D-23:** Default QueryClient options: `staleTime: 30_000`, `refetchOnWindowFocus: false`, `retry: 1` — set once in `app/queryClient.ts` (already exists from Phase 1, confirm values).

### URL filter/search/sort contract
- **D-24:** Each list route declares a **typed search schema** (TanStack Router `validateSearch: zodValidator(schema)`) with fields: `page, pageSize, q, sort, dir, ...domain-specific filters`. The `routes/<entity>.index.tsx` file owns its schema.
- **D-25:** Service receives the parsed search as its params object directly (1:1 mapping) — no adapter layer. Boundary enforced by test.

### Dev toolbar (UI-06 + UI-02 helpers)
- **D-26:** Floating button → panel at `src/shared/ui/dev-toolbar/`, mounted in `app/providers.tsx` behind `import.meta.env.DEV`. Controls:
  - API mode badge (read-only in v1 — swap needs reload).
  - Chaos toggle + failure-rate slider.
  - Seed tier switch (small/demo) → reseed + reload.
  - "Reset mock DB" → clears `localStorage:sportzal:mock:v1` + reseed.
  - Role switcher (already exists in app shell; toolbar just deep-links).
  - Mock DB inspector (read-only JSON tree per table, collapsed by default).

### Minor open questions
- **D-27:** **Avatar source (OQ#16 resolved):** DiceBear `initials` style via `https://api.dicebear.com/9.x/initials/svg?seed=<name>` — no dependency, deterministic per client. Fallback to local SVG generator if offline; cached in `<img>` only (no prefetch).
- **D-28:** **Notifications poll (OQ#13 resolved):** `staleTime: 60_000`, `refetchInterval: 60_000`, `refetchOnWindowFocus: true` for the notifications query only. All other queries keep 30_000 default.
- **D-29:** **Seed volume (UI-06):** numbers fixed in D-08.

### Claude's Discretion
- Exact file layout within `entities/` (split vs single-file) — planner decides per entity size.
- Exact Zod schema composition (shared primitives vs inline) — standard conventions.
- Dev toolbar styling (use shadcn `Sheet` + `Tabs`) — designer/executor.
- Virtualization threshold exact number (D-19 says 100 as anchor).
- Internal helper names within `_runtime.ts`.

</decisions>

<specifics>
## Specific Ideas

- Money display must include NBSP (`1 234,56 ₽`) per CLAUDE.md.
- Dates stay as ISO strings in domain types; display layer applies `date-fns` + `ru` locale + `Europe/Moscow` TZ.
- 3-form Russian pluralization via `Intl.PluralRules('ru-RU')` — already scaffolded in `shared/i18n/plural.ts`.
- `FormTemplate` dirty-guard follows TanStack Router's `useBlocker` pattern (per-route), not window `beforeunload`.
- Mock DB inspector should visually hint at relations (e.g., hover `clientId` field → highlight client row) — nice-to-have, not gate.

</specifics>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Product & requirements
- `.planning/PROJECT.md` — Product context, roles, daily flows (RU).
- `.planning/REQUIREMENTS.md` — §Data Layer (DATA-01..12), §UI System (UI-01, UI-02, UI-06). Full Phase 2 coverage.
- `.planning/ROADMAP.md` §Phase 2 — Goal, deliverables, 5 success criteria, MEDIUM research flag.

### Architecture & conventions
- `CLAUDE.md` — Stack (locked), Architecture non-negotiables (1–8), Conventions (Money, Dates, IDs, Pagination, Forms, Errors, Russian locale), Anti-features.
- `.planning/research/SUMMARY.md` — TL;DR + Domain model + Architecture principles + Do's/Don'ts + open questions (OQ#1/#3/#13/#16 resolved here).
- `.planning/research/ARCHITECTURE.md` — Layered data flow, swap seam, FSD-lite layout detail.
- `.planning/research/PITFALLS.md` — Mock realism, date TZ pitfalls, form/validation dual-use.
- `.planning/research/STACK.md` — shadcn + reui setup, TanStack Table virtualization notes.

### Phase 1 deliverables (already on disk)
- `src/shared/api/services/index.ts` — Swap seam. Do not modify in Phase 2 (consumes new impls automatically).
- `src/shared/api/config/env.ts` — `VITE_API_MODE` chokepoint.
- `src/shared/api/contracts/index.ts` — Current stub; Phase 2 replaces with per-domain re-exports.
- `src/shared/api/services/mock/index.ts`, `http/index.ts` — Empty scaffolds; Phase 2 populates `mock/`.
- `src/app/queryClient.ts` — QueryClient defaults (verify `staleTime: 30_000`, `refetchOnWindowFocus: false`).
- `src/shared/session/{store,can,registry,RoleGate}.ts` — Role source consumed by mock services for 403-analog checks.
- `eslint.config.js` — 4 enforcement rules (services boundary, raw palette ban, `VITE_API_MODE` chokepoint, `react/no-danger`); tests in `eslint-fixtures/`.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `shared/session/store.ts` + `can.ts` + `registry.ts` — Mock services will import `can()` to enforce role-based 403-analog; no duplication.
- `shared/lib/money.ts` — Money primitives already present; entities use it directly.
- `shared/i18n/{ru,date,plural}.ts` — Display helpers; templates wire them into columns.
- `shared/theme/` — CSS tokens only; templates use shadcn semantic classes exclusively (raw palette already banned).

### Established Patterns
- Swap seam is eager-import — any service added in `mock/` must have a matching no-op stub in `http/` (returns `Promise.reject(new DomainError({ code: 'UNKNOWN', message: 'http impl not available in v1' }))`) so both sides type-check identically.
- Persist stores use `skipHydration + manual rehydrate before render` (Phase 1 pattern) — mock-settings store must follow same pattern to avoid FOUC/flash.
- Each shared module has `_README.md`; Phase 2 extends pattern into `entities/<name>/_README.md` and `services/mock/db/_README.md`.

### Integration Points
- Contracts are consumed by both `mock` and `http` via structural typing — no shared abstract class.
- Dev toolbar mounts at `app/providers.tsx` (has ThemeProvider, QueryClientProvider, RouterProvider); add after RouterProvider, behind `import.meta.env.DEV`.
- Canonical templates sit in `shared/ui/templates/` and are imported by feature routes (Phase 3+). In Phase 2 we ship them **plus** one thin demo route at `/_dev/templates` (DEV-only) to prove three-state rendering without needing real feature code.

</code_context>

<deferred>
## Deferred Ideas

- HTTP impls for services — Phase 7 (real API migration).
- Cursor/infinite pagination — not in v1; current envelope is offset-only.
- Real-time updates (websockets) — anti-feature per CLAUDE.md.
- Optimistic mutation scaffolding beyond conventions doc — applied per-feature in Phases 3–7.
- Mock DB inspector relation-hover highlight — nice-to-have, revisit if time in Phase 2 wave tail.
- CSP hardening of theme bootstrap (tracked deferred from Phase 1) — unrelated to data layer.
- Kids area entities (OQ#9 deferred to v2).
- CSV import / bulk actions / command palette — anti-features for v1.

</deferred>

---

*Phase: 02-data-layer-contracts-mock-infrastructure*
*Context gathered: 2026-04-21*
