# Architecture

**Analysis Date:** 2026-04-30

## Top-Level Layout

Two-directory repo:
- `backend/` — empty placeholder (no code, no manifest). All API access in v1 happens via mock services in the frontend.
- `frontend/` — the entire shipping application (React 19 SPA, Vite, TypeScript strict).

Everything below describes `frontend/`.

## Architectural Pattern

**Single-page application** organized as **FSD-lite** (Feature-Sliced Design, light variant) on top of a **layered data flow** with a hard **swap seam** between UI and data.

```
UI (routes, components)
   ↓
TanStack Query hooks  ← per-feature `xKeys` factories (planned, not yet present)
   ↓
services container  → src/shared/api/services/index.ts  (THE swap seam)
   ↓
{ mock impl | http impl }  → src/shared/api/services/{mock,http}/
```

**Swap seam contract** (`src/shared/api/services/index.ts:18`):

```ts
export const services = API_MODE === 'http' ? httpServices : mockServices
```

`VITE_API_MODE` ('mock'|'http') is read **only** through `src/shared/api/config/env.ts` (single chokepoint, ESLint-enforced — see `eslint.config.js:88-101`). UI code that reaches `import.meta.env.VITE_API_MODE` directly fails the build.

Real-API migration = populate `services/http/*` and flip default. UI, hooks, schemas, routes do not change.

## Layers

| Layer | Folder | Responsibility |
|---|---|---|
| Composition | `src/app/` | Root render, providers, query client, router instance, global CSS |
| Routing | `src/routes/` | TanStack Router file-based tree; thin route components, role guards in `beforeLoad` |
| Features (planned) | `src/features/<domain>/` | `api/` (hooks + keys), `components/`, `model/`, `index.ts` — none present yet |
| Entities (planned) | `src/entities/<entity>/` | Domain types + Zod schemas + pure helpers — none present yet |
| Shared | `src/shared/` | Cross-cutting code: `ui/`, `api/`, `session/`, `lib/`, `theme/`, `i18n/` |

**Dependency rules** (enforced by ESLint `import/no-restricted-paths`, `eslint.config.js:48-69`):

- `features → entities + shared` ✅
- `features → other features` ❌ (cross-feature refs go through the central mock DB)
- `routes/features/entities/shared/ui/app → services/{mock,http}` ❌ (must go through swap seam or a Query hook)

## Entry Points

| File | Role |
|---|---|
| `index.html` | Static shell + theme bootstrap script (applies `dark` class before React mounts to avoid FOUC). Has a `TODO Phase 7` to remove `'unsafe-inline'` from CSP. |
| `src/app/main.tsx` | Top-level render. Awaits Zustand `persist.rehydrate()` for session + UI prefs **before** mounting React, then composes `QueryClientProvider → ThemeProvider → RouterProvider` and renders `<Toaster />`. |
| `src/app/router.ts` | Builds the TanStack Router instance, injects `RouterContext = { queryClient, getSession }` so route loaders/`beforeLoad` can read session state and prefetch via `queryClient.ensureQueryData`. |
| `src/app/queryClient.ts` | Single `QueryClient` with `staleTime: 30_000`, `refetchOnWindowFocus: false`, `retry: 1` for queries, `retry: 0` for mutations. |
| `src/routes/__root.tsx` | Wraps `<AppShell>` around `<Outlet/>`, lazy-loads dev tools (router devtools + react-query devtools) only in dev. |

## Core Abstractions

### Session & Authorization (`src/shared/session/`)

The single source of truth for who-can-do-what.

- `types.ts` — `Role = 'owner' | 'reception'`, `SessionState = { role; setRole }`
- `store.ts` — Zustand store, persisted to `localStorage['sportzal:session:v1']` with `version: 1`, `skipHydration: true` (manually rehydrated in `main.tsx:13`).
- `registry.ts` — `routeRegistry: readonly RouteEntry[]` — maps each top-level path to a `Resource`, sidebar label (Russian), Lucide icon name, and i18n key. Used by sidebar, router, and tests.
- `can.ts` — `can(role, action, resource): boolean`. Owner short-circuits to `true`; reception is denied any pair listed in `OWNER_ONLY` (finance/reports/payroll/compensation/settings/owner-area views, template edits, client deletes, refunds).
- `RoleGate.tsx` — declarative wrapper for in-page action gating.

When real auth ships, only `store.ts` + the http services change. The `SessionState` shape and `can()` API stay stable.

### Routing & Guards

TanStack Router with file-based routes. Each non-public route gates access in `beforeLoad`:

```ts
// src/routes/clients.tsx
beforeLoad: ({ context, location }) => {
  const { role } = context.getSession()
  if (!can(role, 'view', 'clients')) {
    throw redirect({ to: '/', search: { forbidden: location.href } })
  }
}
```

The forbidden path is round-tripped to `/` via `?forbidden=` and surfaced as an inline alert (`src/routes/index.tsx`). Search params are validated with `zod` (`validateSearch`). The auto-generated route tree lives at `src/routeTree.gen.ts` (do not hand-edit).

### Theming (`src/shared/theme/` + `src/app/providers/ThemeProvider.tsx`)

- UI prefs Zustand store at `localStorage['sportzal:ui:v1']` holds `{ theme: 'light' | 'dark' | 'system' }`.
- Inline blocking script in `index.html` reads that key and applies `.dark` to `<html>` before React mounts (no FOUC).
- `ThemeProvider` keeps the class in sync with store changes and `prefers-color-scheme`.
- All colors are semantic shadcn tokens (`bg-background`, `text-muted-foreground`); raw palette classes are banned by ESLint (`eslint.config.js:8-9, 71-83`).

### Mock Services Container

`src/shared/api/services/mock/index.ts` exports an empty `services` object in Phase 1 (just enough for the swap seam to type-check). Per-domain implementations are added in later phases. Mock contract (per CLAUDE.md):

- 120–300 ms simulated latency, configurable failure rate.
- Versioned localStorage DB key `sportzal:mock:v1`.
- `faker.seed(42)` for deterministic data.
- Mock services enforce role access (throw `DomainError` when `can(...)` is false).

## Data Flow Examples

**Component reading data (target pattern, not yet wired):**

```
<ClientsList/>
  → useClients()                    // src/features/clients/api/useClients.ts
      → services.clients.list()     // resolved via src/shared/api/services/index.ts
          → mock impl OR http impl  // selected by VITE_API_MODE at module load
```

**Route prefetch:**

```ts
loader: ({ context }) =>
  context.queryClient.ensureQueryData({ queryKey: clientsKeys.list(), queryFn: ... })
```

The same `queryKey` is used by the hook so the loader's data is reused on mount.

## State Management

| Concern | Mechanism | Where |
|---|---|---|
| Server/cached data | TanStack Query | `src/app/queryClient.ts` + per-feature hooks |
| Session (role) | Zustand + `persist` | `src/shared/session/store.ts` |
| UI prefs (theme) | Zustand + `persist` | `src/shared/theme/uiPrefsStore.ts` |
| Route search/params | TanStack Router + Zod `validateSearch` | per-route file |
| Local component state | React hooks (`useState`/`useReducer`) | inline |

No Redux. No Context for app data (Context is reserved for the React Query and Theme providers).

## Cross-Cutting Concerns

- **i18n:** Single Russian dictionary in `src/shared/i18n/ru.ts`, helpers `t()`, `formatDate`, `plural`. No runtime locale switching (Russian-only v1).
- **Money:** Integer minor units (kopecks); `formatMoney()` uses `Intl.NumberFormat('ru-RU', {currency:'RUB'})` — produces NBSPs.
- **IDs:** Branded UUIDv4 string types (e.g. `type ClientId = Brand<string, 'ClientId'>`).
- **Errors:** Mock services throw `DomainError { code, message, fields? }`. UI surfaces critical errors as inline alerts/dialogs, non-blocking confirmations as Sonner toasts.
- **Pagination:** Every list endpoint returns `{ items, total, page, pageSize }`. No bare arrays.

## Architectural Constraints (locked)

These are enforced either by code, ESLint rules, or by the canonical patterns in `frontend/CLAUDE.md`:

1. UI never imports `services/mock` or `services/http` directly.
2. `VITE_API_MODE` is read only inside `src/shared/api/`.
3. Raw Tailwind palette classes (`bg-slate-900`, `text-white`) are banned in `className` literals/template strings.
4. Shadcn primitives in `src/shared/ui/*.tsx` are not hand-edited; customizations go in wrappers (`// SHADCN-DIVERGENCE: …` if unavoidable).
5. Domain types use ISO date strings (never `Date`) and integer kopecks for money.
6. Features depend on entities + shared; never on other features.

## Build & Plugin Order

Vite plugins in `vite.config.ts` must run in this order:

1. `tanstackRouter` — generates `src/routeTree.gen.ts` from `src/routes/`.
2. `react` — JSX transform.
3. `tailwindcss` — CSS-first Tailwind v4.

Build pipeline: `tsc -b && vite build`. Type-check happens before bundling so a TS error fails the build.

---

*Architecture analysis: 2026-04-30*
