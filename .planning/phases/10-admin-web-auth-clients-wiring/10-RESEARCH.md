# Phase 10: admin-web Auth + Clients Wiring — Research

**Researched:** 2026-05-03
**Domain:** React 19 SPA wiring — auth (login/session/refresh redirect) + clients CRUD against real HTTP backend, riding the existing `apps/admin-web` swap-seam.
**Confidence:** HIGH (architecture, library APIs, mock parity), MEDIUM (ReUI base-nova styling specifics, ReUI InputOTP exact props), LOW (none — all open questions surfaced and addressed).

## Summary

Phase 10 is a wiring phase, not a research phase: every load-bearing decision was already made in CONTEXT.md (D-01..D-17), and every cross-phase contract — `request<P,M>` + `ApiError` (Phase 9), backend wire format + `OWNER_ONLY` parity (Phase 4), `/auth/*` + `/clients` endpoints (Phases 5/7/8), `sportzal_csrf` cookie + single-flight refresh (Phases 4/9) — already exists. The planner's job is to execute these decisions correctly inside `apps/admin-web` without introducing drift.

The critical execution risks are: (1) wiring TanStack Router pathless layout-routes correctly so `/login` truly renders without `AppShell`; (2) attaching `QueryCache` + `MutationCache` `onError` hooks at the right level so `session_expired` is caught exactly once; (3) the `getSession()` API_MODE branch in `router.ts` not creating a stale read against TanStack Query cache; (4) optimistic mutation `onMutate`/`onError`/`onSettled` patterns rolling back correctly when paginated list state interacts with creates/deletes; (5) ReUI install commands hitting the right registry style (`base-nova`) without breaking the existing primitives that AppShell depends on.

**Primary recommendation:** Plan in this dependency order — (Wave 0) ReUI registry switch + theme-token revision; (Wave 1) `shared/api/contracts/{auth,clients}.ts` + branded `ClientId` + Zod schemas; (Wave 2) mock services (FE-03 — gives `/login` and `/clients` working in mock immediately, validating the contracts); (Wave 3) http services + global `session_expired` handler + `getSession()` API_MODE branch; (Wave 4) routes (`_public/login`, `_protected/clients` replacement) + features (`features/auth`, `features/clients`); (Wave 5) ESLint rule + fixtures + ProfileMenu logout + RoleSwitcher guard + verification suite. Mock-first is non-negotiable: it converts the SC#3 "no regression in mock-mode" criterion from a wish into a checkable property at every wave.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Pathless layout-route split (`_public` / `_protected`) | Routing (`src/routes/`) | — | TanStack Router file-based; file naming literally controls URL structure (D-01) |
| Splash before first `/auth/me` | Composition root (`src/app/main.tsx`) | Browser (index.html for FOUC-free first paint) | Bootstrap-time decision must precede `<RouterProvider>` mount (D-06) |
| Global `session_expired` handler | App composition (`src/app/queryClient.ts` + `features/auth/redirect-on-session-expired.ts`) | — | `QueryCache`/`MutationCache` are constructed once and own all error edges (D-07) |
| User SoT in http-mode | TanStack Query cache (`authKeys.me`) | — | One cache, one invalidation seam — Zustand session-store is mock-only branch (D-05) |
| User SoT in mock-mode | Zustand `useSessionStore` | — | Persists `role` for `RoleSwitcher`; pre-existing semantics unchanged (D-05, D-12) |
| URL-driven search/pagination state | Routing (TanStack Router `validateSearch` + `loaderDeps`) | — | URL is the canonical input; loader subscribes via deps (D-10) |
| Optimistic mutation orchestration | Feature query hooks (`features/clients/api/hooks.ts`) | TanStack Query cache | Per-feature `xKeys` factory + `onMutate`/`onError`/`onSettled` |
| Server-side RBAC mirror | `shared/session/can.ts` (existing) | RoleGate (`shared/session/RoleGate.tsx`) | Already byte-parity with backend (Phase 4 SC#1); Phase 10 consumes, never modifies |
| Transport (HTTP) | `packages/api-client` (`request`, `ApiError`) | `shared/api/services/http/{auth,clients}.ts` (thin wrappers) | Phase 9 sealed transport contract; Phase 10 only marshals |
| Mock transport | `shared/api/services/mock/{auth,clients}.ts` | Central localStorage DB key `sportzal:mock:v1` | Faker-seeded determinism + RBAC + DomainError (CLAUDE.md mock-realism) |
| ESLint enforcement | Project config (`eslint.config.js`) + fixture | `scripts/assert-eslint-fixtures.mjs` | Mirrors existing `api-mode-leak.ts` / `illegal-mock-import.ts` pattern |

## Standard Stack

### Core (already in `apps/admin-web/package.json` — no install needed)
| Library | Version (verified 2026-05-03) | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `@tanstack/react-router` | 1.169.1 (project: ^1.95.0) | File-based routing with typed search + pathless layouts | Already locked; idiomatic pathless-layout for auth boundary [VERIFIED: ctx7 /tanstack/router] |
| `@tanstack/react-query` | 5.100.9 (project: ^5.59.0) | Server state, cache `onError`, optimistic mutations | Already locked; v5 `QueryCache`/`MutationCache` is the global-error seam [VERIFIED: ctx7 /tanstack/query] |
| `@tanstack/react-table` | 8.21.3 (project: ^8.20.0) | Underpins ReUI `DataGrid` | ReUI DataGrid is a wrapper — keys factory + URL-driven pagination remain in admin-web [VERIFIED: ctx7 /keenthemes/reui] |
| `react-hook-form` | 7.66.0+ (project: ^7.54.0) | Form state | Locked; pairs with Zod via `@hookform/resolvers` [VERIFIED: ctx7 /react-hook-form/react-hook-form] |
| `@hookform/resolvers` | 5.2.2 (project: ^3.9.1) | Zod resolver bridge | Project version is 3.x — current registry is 5.x; **do NOT bump in this phase** (out of scope; the 3.x API for `zodResolver` is identical for our use). [VERIFIED: npm view] |
| `zod` | 4.4.2 (project: ^3.24.1) | Schema validation | Project on Zod 3 — DO NOT migrate to Zod 4 in Phase 10 (breaking). All examples below assume Zod 3 syntax which is what's installed. [VERIFIED: package.json] |
| `@sportzal/api-client` | workspace:* | `request<P,M>` + `ApiError` | Phase 9 product; Phase 10 consumer |
| `lucide-react` | ^0.469.0 | Icons | UI-SPEC references `Loader2`, `LogOut`, `Trash2`, `Pencil`, `Eye`/`EyeOff`, `MessageCircle` |
| `sonner` | ^1.7.4 | Toaster (existing) | UI-SPEC keeps it; D-16 leaves Toaster as Claude discretion |

### Supporting (decisions delegated by D-16/Discretion)
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `react-phone-number-input` | 3.4.16 | E.164 phone input + country dropdown | If `pnpm dlx shadcn add @reui/phone-input` is used (recommended) — it pulls this as a dep. [VERIFIED: ctx7 /keenthemes/reui] |
| `input-otp` | 1.4.2 | Underpins shadcn / ReUI `InputOTP` primitive | Pulled in transitively by `pnpm dlx shadcn add @reui/input-otp` |

**Installation commands (verified against ReUI registry mechanics, [VERIFIED: ctx7 /keenthemes/reui get-started.mdx]):**

```bash
# From apps/admin-web/, after components.json switches style→base-nova
pnpm dlx shadcn@latest add @reui/button
pnpm dlx shadcn@latest add @reui/input
pnpm dlx shadcn@latest add @reui/form
pnpm dlx shadcn@latest add @reui/label
pnpm dlx shadcn@latest add @reui/dropdown-menu
pnpm dlx shadcn@latest add @reui/dialog
pnpm dlx shadcn@latest add @reui/alert-dialog
pnpm dlx shadcn@latest add @reui/data-grid
pnpm dlx shadcn@latest add @reui/input-otp
pnpm dlx shadcn@latest add @reui/phone-input  # only if PhoneInput chosen for the form
```

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `_public.tsx` / `_protected.tsx` pathless | Conditional render in `__root.tsx` | Worse — `__root` always renders; pathless route's `beforeLoad` is the idiomatic auth boundary [CITED: tanstack/router auth-and-guards SKILL] |
| `QueryCache`/`MutationCache` global `onError` | Per-query `onError` for every hook | Catastrophic duplication; v5 deprecated per-query `onError` precisely because it doesn't fire after first observer mounts. Cache-level fires every time. [VERIFIED: ctx7 /tanstack/query] |
| ReUI `PhoneInput` (react-phone-number-input) | `react-imask` | ReUI variant gives country dropdown + E.164 normalization for free; matches D-16 "use ReUI primitive when available" |
| Suspense + `useSuspenseQuery` for clients list | `useQuery` + manual loading state | Suspense couples nicely with `ensureQueryData` loader — DataGrid renders directly with data (no `.isLoading` ladder). Recommended for `/clients`. [CITED: tanstack/router router-query SKILL] |
| Module-scoped `let redirecting = false` | React state in error boundary | Module flag is idempotent across mount cycles + survives `queryClient.clear()`; matches D-A4 single-flight-refresh pattern (Phase 9) |

## Architecture Patterns

### System Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                        Browser (admin-web SPA)                  │
└─────────────────────────────────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│  src/app/main.tsx — bootstrap                                   │
│   • await rehydrate(session, uiPrefs)                           │
│   • IF http-mode: render <Splash/> + await ensureQueryData(me)  │
│   • render <QueryClientProvider><ThemeProvider><RouterProvider> │
└─────────────────────────────────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│  TanStack Router tree                                           │
│   __root.tsx (no AppShell — only providers + devtools)          │
│     ├─ _public.tsx (no AppShell — Outlet only)                  │
│     │    └─ _public/login.tsx (beforeLoad: silent redirect      │
│     │       if me() succeeds; component: <LoginPage/>)          │
│     └─ _protected.tsx (beforeLoad: throw redirect if 401;       │
│           component: <AppShell><Outlet/></AppShell>)            │
│           ├─ _protected/index.tsx                               │
│           ├─ _protected/clients.tsx (validateSearch + loader)   │
│           ├─ _protected/schedule.tsx … (placeholders, untouched)│
└─────────────────────────────────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│  Route component → useQuery / useMutation hook                  │
│   features/auth/api/hooks.ts (authKeys.me, login, telegram*)    │
│   features/clients/api/hooks.ts (clientsKeys.list/detail/CRUD)  │
└─────────────────────────────────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│  TanStack Query — QueryCache + MutationCache                    │
│   onError(error) → if error instanceof ApiError &&              │
│                       error.code === 'session_expired'          │
│                    → redirectOnSessionExpired() (one-shot flag) │
└─────────────────────────────────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│  shared/api/services/index.ts — swap seam                       │
│   API_MODE === 'http' ? services.http : services.mock           │
└─────────────────────────────────────────────────────────────────┘
              │                                        │
              ▼ http                                    ▼ mock
┌──────────────────────────────┐  ┌──────────────────────────────┐
│ http/{auth,clients}.ts        │  │ mock/{auth,clients}.ts       │
│ → @sportzal/api-client request│  │ → faker.seed(42)             │
│   throws ApiError             │  │   localStorage sportzal:mock:│
│   single-flight refresh on 401│  │   v1                         │
│                               │  │   throws DomainError         │
│                               │  │   enforces RBAC via can()    │
└──────────────────────────────┘  └──────────────────────────────┘
              │                                        │
              ▼                                        ▼
       FastAPI backend                          (no network)
       (Phase 4-9 product)
```

### Recommended Project Structure

```
apps/admin-web/src/
├── app/                                        # composition (existing — extend)
│   ├── main.tsx                                # ADD: splash + ensureQueryData(me) gate
│   ├── queryClient.ts                          # ADD: queryCache + mutationCache onError
│   ├── router.ts                               # MODIFY: getSession() API_MODE branch
│   └── providers/
│       └── ThemeProvider.tsx                   # untouched
├── routes/                                     # TanStack Router file tree
│   ├── __root.tsx                              # MODIFY: drop AppShell from here
│   ├── _public.tsx                             # NEW: pathless layout, Outlet only
│   ├── _public.login.tsx                       # NEW: /login (D-01..D-04)
│   ├── _protected.tsx                          # NEW: pathless layout, AppShell + auth gate
│   ├── _protected.index.tsx                    # MOVE: from routes/index.tsx
│   ├── _protected.clients.tsx                  # REPLACE: real route w/ validateSearch + loader
│   ├── _protected.schedule.tsx                 # MOVE: untouched placeholder
│   ├── _protected.staff.tsx                    # MOVE
│   ├── _protected.finance.tsx                  # MOVE
│   └── _protected.settings.tsx                 # MOVE
├── features/                                   # NEW directory
│   ├── auth/
│   │   ├── api/
│   │   │   ├── keys.ts                         # authKeys factory
│   │   │   ├── hooks.ts                        # useMe, useLogin, useLogout, useTelegram*
│   │   │   └── redirect-on-session-expired.ts  # module-flag handler (D-07)
│   │   ├── components/
│   │   │   ├── LoginPage.tsx                   # tabs container
│   │   │   ├── EmailLoginForm.tsx
│   │   │   └── TelegramLoginTab.tsx            # poll → InputOTP
│   │   ├── model/
│   │   │   └── schema.ts                       # Zod (email/password, OTP)
│   │   └── index.ts
│   └── clients/
│       ├── api/
│       │   ├── keys.ts                         # clientsKeys factory (TkDodo)
│       │   └── hooks.ts                        # useClientsList, useCreate/Update/DeleteClient
│       ├── components/
│       │   ├── ClientsTable.tsx                # ReUI DataGrid wrapper
│       │   ├── ClientForm.tsx                  # create + edit (mode prop)
│       │   ├── ClientFormDialog.tsx            # Dialog wrapper
│       │   └── ClientDeleteDialog.tsx          # AlertDialog
│       ├── model/
│       │   └── schema.ts                       # Zod ClientCreate/Update/Search
│       └── index.ts
├── entities/                                   # NEW directory
│   └── client/
│       ├── types.ts                            # branded ClientId, Client, Pagination<T>
│       └── index.ts
├── shared/                                     # existing — extend
│   ├── api/
│   │   ├── contracts/
│   │   │   ├── auth.ts                         # NEW: AuthService, Session, etc.
│   │   │   ├── clients.ts                      # NEW: ClientsService
│   │   │   └── index.ts                        # MODIFY: re-export
│   │   └── services/
│   │       ├── http/
│   │       │   ├── auth.ts                     # NEW: implements AuthService via request()
│   │       │   ├── clients.ts                  # NEW: implements ClientsService
│   │       │   ├── error-mapping.ts            # NEW: ApiError → DomainError? (see below)
│   │       │   └── index.ts                    # MODIFY: export {auth, clients} as const
│   │       └── mock/
│   │           ├── _db.ts                      # NEW: central localStorage shim, seed
│   │           ├── _latency.ts                 # NEW: 120-300ms randomizer
│   │           ├── auth.ts                     # NEW: implements AuthService
│   │           ├── clients.ts                  # NEW: implements ClientsService
│   │           └── index.ts                    # MODIFY
│   └── ui/
│       ├── splash.tsx                          # NEW (D-06)
│       ├── button.tsx                          # REPLACE via @reui
│       ├── input.tsx                           # REPLACE via @reui
│       ├── form.tsx                            # NEW via @reui
│       ├── label.tsx                           # NEW via @reui
│       ├── dropdown-menu.tsx                   # REPLACE via @reui
│       ├── dialog.tsx                          # NEW via @reui
│       ├── alert-dialog.tsx                    # NEW via @reui
│       ├── data-grid.tsx                       # NEW via @reui
│       ├── input-otp.tsx                       # NEW via @reui
│       └── app-shell/
│           ├── ProfileMenu.tsx                 # MODIFY: enable Logout (D-08)
│           └── RoleSwitcher.tsx                # MODIFY: API_MODE !== 'mock' return null
└── __fixtures/
    └── raw-fetch-leak.ts                       # NEW (FE-07)
```

> Note on TanStack Router file naming: pathless layout routes use the leading underscore convention. The TanStack auto-router accepts both flat (`_public.login.tsx`) and nested (`_public/login.tsx`) directory conventions. **Recommendation: nested directory form** (`_public/login.tsx`, `_protected/clients.tsx`) — better for `loaderDeps` co-location and clearer at a glance. Both forms produce equivalent `routeTree.gen.ts`.

### Pattern 1: Pathless Layout Routes for Auth Boundary

**What:** Two siblings under `__root` — `_public` (Outlet only) and `_protected` (AppShell + auth gate). The leading `_` means the path segment doesn't appear in URLs.
**When to use:** Whenever a subset of routes needs different layout/guards, especially `/login` vs the rest.
**Example:**

```tsx
// src/routes/__root.tsx — strip AppShell out
import { createRootRouteWithContext, Outlet, ScrollRestoration } from '@tanstack/react-router'
// ...
export const Route = createRootRouteWithContext<RouterContext>()({
  component: () => (
    <>
      <Outlet />
      <ScrollRestoration />
      {/* devtools (existing) */}
    </>
  ),
})

// src/routes/_public.tsx — public branch (no AppShell, no auth)
import { createFileRoute, Outlet } from '@tanstack/react-router'
export const Route = createFileRoute('/_public')({
  component: () => <Outlet />,
})

// src/routes/_protected.tsx — protected branch (AppShell + auth gate)
import { AppShell } from '@/shared/ui/app-shell'
import { createFileRoute, Outlet, redirect } from '@tanstack/react-router'
import { authKeys } from '@/features/auth/api/keys'
import { services } from '@/shared/api/services'
import { API_MODE } from '@/shared/api/config/env'

export const Route = createFileRoute('/_protected')({
  beforeLoad: async ({ context, location }) => {
    if (API_MODE === 'mock') return  // mock has no real auth
    try {
      await context.queryClient.ensureQueryData({
        queryKey: authKeys.me,
        queryFn: () => services.auth.me(),
        retry: false,
      })
    } catch {
      throw redirect({ to: '/login', search: { next: location.href } })
    }
  },
  component: () => (
    <AppShell>
      <Outlet />
    </AppShell>
  ),
})

// src/routes/_public/login.tsx — D-03 silent redirect when already auth'd
import { createFileRoute, redirect } from '@tanstack/react-router'
import { z } from 'zod'

export const Route = createFileRoute('/_public/login')({
  validateSearch: z.object({ next: z.string().optional() }),
  beforeLoad: async ({ context, search }) => {
    if (API_MODE === 'mock') return
    try {
      await context.queryClient.ensureQueryData({
        queryKey: authKeys.me,
        queryFn: () => services.auth.me(),
        retry: false,
      })
      throw redirect({ to: search.next ?? '/', replace: true })
    } catch (e) {
      // isRedirect re-throw — don't swallow
      const { isRedirect } = await import('@tanstack/react-router')
      if (isRedirect(e)) throw e
      // 401 from /auth/me → render the login page (continue)
    }
  },
  component: LoginPage,
})
```

> Source: TanStack Router routing-concepts.md + auth-and-guards SKILL.md (verified via Context7 `/tanstack/router`).

### Pattern 2: Global `session_expired` Handler — `QueryCache` + `MutationCache` `onError`

**What:** Construct `QueryClient` with explicit `queryCache` and `mutationCache`, both wired with the same `onError` handler. The handler checks `error instanceof ApiError && error.code === 'session_expired'` and redirects exactly once via a module flag.
**When to use:** Any centralized session-lifecycle handling. Per-query `onError` is observer-scoped and unreliable — cache-level is global.
**Example:**

```ts
// src/features/auth/api/redirect-on-session-expired.ts
import { ApiError } from '@sportzal/api-client'
import { router } from '@/app/router'
import { queryClient } from '@/app/queryClient'

let redirecting = false  // module-scoped one-shot flag

export function redirectOnSessionExpired(error: unknown): void {
  if (!(error instanceof ApiError) || error.code !== 'session_expired') return
  if (redirecting) return
  redirecting = true
  queryClient.clear()
  const next = encodeURIComponent(router.state.location.href)
  router.navigate({ to: '/login', search: { next }, replace: true })
    .finally(() => { redirecting = false })
}

// TEST hook (not exported in barrel):
export function __resetRedirectingFlagForTests(): void {
  redirecting = false
}
```

```ts
// src/app/queryClient.ts
import { QueryClient, QueryCache, MutationCache } from '@tanstack/react-query'
import { redirectOnSessionExpired } from '@/features/auth/api/redirect-on-session-expired'

export const queryClient = new QueryClient({
  queryCache: new QueryCache({ onError: redirectOnSessionExpired }),
  mutationCache: new MutationCache({ onError: redirectOnSessionExpired }),
  defaultOptions: {
    queries: { staleTime: 30_000, refetchOnWindowFocus: false, retry: 1 },
    mutations: { retry: 0 },
  },
})
```

> Note on circular import: `queryClient` imports `redirectOnSessionExpired` which imports `router` which imports `queryClient` — break the cycle by deferring the `router` reference inside `redirectOnSessionExpired` via a lazy module read OR by exporting `router` and `queryClient` from a shared module that doesn't statically import the redirect helper. Recommended: move `redirecting` flag + handler into `app/session-error-handler.ts` and have `app/router.ts` import it lazily; OR use `globalThis.__sportzal_redirecting__` (less clean). **Planner: address this in the wave that wires `app/queryClient.ts`.**

> Sources: ctx7 `/tanstack/query` `QueryCache.md` and `MutationCache.md` — confirmed `new QueryCache({ onError })` + `new MutationCache({ onError })` is the v5 API; passed verbatim into `new QueryClient({ queryCache, mutationCache })`.

### Pattern 3: `ensureQueryData` in Loader + `useSuspenseQuery` in Component

**What:** The route loader pre-warms the cache with the same key the component reads. `useSuspenseQuery` then renders directly with data, no `.isLoading` ladder.
**When to use:** Every list/detail route. The double-keyed pattern is the canonical TanStack Router + Query bridge.
**Example:**

```ts
// src/features/clients/api/keys.ts (TkDodo factory)
import type { ClientsListQuery } from '@/shared/api/contracts/clients'

export const clientsKeys = {
  all: ['clients'] as const,
  lists: () => [...clientsKeys.all, 'list'] as const,
  list: (filter: ClientsListQuery) => [...clientsKeys.lists(), filter] as const,
  details: () => [...clientsKeys.all, 'detail'] as const,
  detail: (id: string) => [...clientsKeys.details(), id] as const,
}
```

```tsx
// src/routes/_protected/clients.tsx
import { createFileRoute } from '@tanstack/react-router'
import { z } from 'zod'
import { clientsKeys } from '@/features/clients/api/keys'
import { services } from '@/shared/api/services'

const searchSchema = z.object({
  q: z.string().optional(),
  page: z.coerce.number().int().min(1).default(1),
  pageSize: z.coerce.number().int().min(10).max(100).default(20),
})

export const Route = createFileRoute('/_protected/clients')({
  validateSearch: searchSchema,
  loaderDeps: ({ search }) => ({ search }),
  loader: ({ context, deps: { search } }) =>
    context.queryClient.ensureQueryData({
      queryKey: clientsKeys.list(search),
      queryFn: () => services.clients.list(search),
    }),
  component: ClientsPage,
})
```

```tsx
// src/features/clients/components/ClientsTable.tsx
import { useSuspenseQuery } from '@tanstack/react-query'
import { Route } from '@/routes/_protected/clients'

function ClientsTable() {
  const search = Route.useSearch()
  const { data } = useSuspenseQuery({
    queryKey: clientsKeys.list(search),
    queryFn: () => services.clients.list(search),
  })
  // data is { items, total, page, pageSize }
  // ...DataGrid here
}
```

> Sources: ctx7 `/tanstack/router` data-loading.md + router-query SKILL.md — `validateSearch` accepts a Zod schema directly (`schema.parse` is implicit in v1.95+), `loaderDeps` makes the loader subscribe to search-param changes.

### Pattern 4: Optimistic Mutations with Rollback (CRUD)

**What:** `onMutate` cancels in-flight refetches, snapshots cache, applies optimistic patch. `onError` rolls back from snapshot. `onSettled` invalidates.
**When to use:** Every mutation against a list users see live. Critical for `/clients` create/edit/delete.
**Example:**

```ts
// src/features/clients/api/hooks.ts
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { clientsKeys } from './keys'
import { services } from '@/shared/api/services'
import type { Client, Pagination } from '@/shared/api/contracts/clients'

export function useDeleteClient() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => services.clients.delete(id),
    onMutate: async (id) => {
      // Cancel all in-flight clients lists so they can't overwrite our patch
      await qc.cancelQueries({ queryKey: clientsKeys.lists() })
      // Snapshot every cached list (different filter combos = different keys)
      const snapshots = qc.getQueriesData<Pagination<Client>>({
        queryKey: clientsKeys.lists(),
      })
      // Optimistically remove from each snapshot
      for (const [key, data] of snapshots) {
        if (!data) continue
        qc.setQueryData<Pagination<Client>>(key, {
          ...data,
          items: data.items.filter((c) => c.id !== id),
          total: Math.max(0, data.total - 1),
        })
      }
      return { snapshots }
    },
    onError: (_err, _id, ctx) => {
      // Rollback every snapshot on any error
      if (!ctx) return
      for (const [key, data] of ctx.snapshots) qc.setQueryData(key, data)
    },
    onSettled: () => {
      // Invalidate so server-truth wins (handles pagination drift after delete)
      void qc.invalidateQueries({ queryKey: clientsKeys.lists() })
    },
  })
}
```

> Source: ctx7 `/tanstack/query` optimistic-updates.md — `getQueriesData` + iterate is the right primitive when filter combos produce many cached lists.

### Pattern 5: ReUI `DataGrid` + URL-driven pagination

**What:** ReUI `DataGrid` is a thin shell over `@tanstack/react-table`. Pagination state is driven by URL via `validateSearch`, NOT by the table's internal state. Pass a controlled `state.pagination` to `useReactTable` and update via `navigate({ search: ... })`.
**When to use:** `/clients` list, every other list later.
**Example:**

```tsx
import {
  DataGrid,
  DataGridContainer,
  DataGridPagination,
  DataGridTable,
  DataGridColumnHeader,
} from '@/shared/ui/data-grid'
import { useReactTable, getCoreRowModel, type ColumnDef } from '@tanstack/react-table'
import { Route } from '@/routes/_protected/clients'

const columns: ColumnDef<Client>[] = [
  {
    accessorKey: 'fullName',
    header: ({ column }) => <DataGridColumnHeader column={column} title="ФИО" />,
  },
  // …
]

function ClientsTable() {
  const search = Route.useSearch()
  const navigate = Route.useNavigate()
  const { data } = useSuspenseQuery({ /* … */ })

  const table = useReactTable({
    data: data.items,
    columns,
    getCoreRowModel: getCoreRowModel(),
    pageCount: Math.ceil(data.total / data.pageSize),
    state: {
      pagination: { pageIndex: search.page - 1, pageSize: search.pageSize },
    },
    manualPagination: true,
    onPaginationChange: (updater) => {
      const next = typeof updater === 'function'
        ? updater({ pageIndex: search.page - 1, pageSize: search.pageSize })
        : updater
      void navigate({
        search: (prev) => ({
          ...prev,
          page: next.pageIndex + 1,
          pageSize: next.pageSize,
        }),
      })
    },
  })

  return (
    <DataGrid table={table} recordCount={data.total} tableLayout={{ headerSticky: true }}>
      <DataGridContainer>
        <DataGridTable />
      </DataGridContainer>
      <DataGridPagination sizes={[20, 50, 100]} />
    </DataGrid>
  )
}
```

> Sources: ctx7 `/keenthemes/reui` data-grid.mdx (verified DataGrid API) + ctx7 `/tanstack/router` search-params SKILL (verified `navigate({ search: prev => … })` is the v1 idiom).

### Pattern 6: Splash Before First Mount (D-06)

**What:** In http-mode, render a splash element directly into `#root` before React mounts the router. After `ensureQueryData(authKeys.me)` resolves (success or failure — fall through), render the React tree.
**When to use:** Once, in `apps/admin-web/src/app/main.tsx`. In mock-mode, skip the splash (boot is synchronous).

**Example:**

```tsx
// src/app/main.tsx
import '@/app/index.css'
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { QueryClientProvider } from '@tanstack/react-query'
import { RouterProvider } from '@tanstack/react-router'
import { Toaster } from 'sonner'
import { queryClient } from './queryClient'
import { router } from './router'
import { ThemeProvider } from './providers/ThemeProvider'
import { useSessionStore } from '@/shared/session/store'
import { useUiPrefsStore } from '@/shared/theme/uiPrefsStore'
import { API_MODE } from '@/shared/api/config/env'
import { authKeys } from '@/features/auth/api/keys'
import { services } from '@/shared/api/services'
import { Splash } from '@/shared/ui/splash'

await Promise.all([
  useSessionStore.persist.rehydrate(),
  useUiPrefsStore.persist.rehydrate(),
])

const rootEl = document.getElementById('root')
if (!rootEl) throw new Error('#root element not found')
const root = createRoot(rootEl)

// http-mode: render splash, await /auth/me, then mount real tree
if (API_MODE === 'http') {
  root.render(<Splash />)
  try {
    await queryClient.ensureQueryData({
      queryKey: authKeys.me,
      queryFn: () => services.auth.me(),
      retry: false,
    })
  } catch {
    // 401 (or any failure) — router /login route will render
  }
}

root.render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <ThemeProvider>
        <RouterProvider router={router} />
      </ThemeProvider>
      <Toaster position="top-right" richColors closeButton />
    </QueryClientProvider>
  </StrictMode>,
)
```

> Alternative considered: hardcode splash HTML in `index.html` and remove via DOM call before `createRoot`. Rejected — mixing manual DOM with React reconciliation is fragile; React-rendered splash is one render cheap.

### Pattern 7: `getSession()` API_MODE Branch

**What:** The router context's `getSession` adapter returns the canonical `{role}` from whichever store is active in the current API_MODE.
**When to use:** Once, in `src/app/router.ts`. Read by `RoleGate`, route `beforeLoad`, `can()` callers — all must see the same answer regardless of mode.

```ts
// src/app/router.ts (excerpt)
import { createRouter } from '@tanstack/react-router'
import { routeTree } from '@/routeTree.gen'
import { queryClient } from './queryClient'
import { useSessionStore } from '@/shared/session/store'
import type { Role } from '@/shared/session/types'
import { API_MODE } from '@/shared/api/config/env'
import { authKeys } from '@/features/auth/api/keys'

export interface SessionView { role: Role }
export interface RouterContext {
  queryClient: QueryClient
  getSession: () => SessionView
}

function getSession(): SessionView {
  if (API_MODE === 'mock') {
    return { role: useSessionStore.getState().role }
  }
  // http-mode: cache-backed
  const me = queryClient.getQueryData<{ role: Role }>(authKeys.me)
  // Fallback to 'reception' (least-privileged) if cache empty —
  // /_protected beforeLoad will redirect to /login long before any RoleGate runs,
  // so this fallback is never user-visible. NEVER fall back to 'owner'.
  return { role: me?.role ?? 'reception' }
}

export const router = createRouter({
  routeTree,
  defaultPreload: 'intent',
  defaultPreloadStaleTime: 0,
  context: { queryClient, getSession } satisfies RouterContext,
})
```

> Note: `RoleGate` currently reads `useSessionStore` directly (see `src/shared/session/RoleGate.tsx` line 15). Phase 10 must re-route `RoleGate` to read via the router context's `getSession()` adapter (or wrap it in a hook that branches on `API_MODE`). **This is a meaningful refactor — flag in the planner.** Recommended approach: introduce `useCurrentRole()` in `shared/session/useCurrentRole.ts` that branches on `API_MODE`, and have `RoleGate` consume it.

### Pattern 8: react-hook-form + Zod (shared schema, server error mapping)

**What:** One Zod schema validates the form (via `zodResolver`) AND the mock service input. On http-mode failure, map `ApiError.fields` → `setError(fieldName, …)`. Form-level errors → `setError('root', …)`.
**When to use:** `EmailLoginForm`, `TelegramLoginTab` (OTP step), `ClientForm`.
**Example:**

```tsx
// src/features/clients/model/schema.ts
import { z } from 'zod'

export const clientCreateSchema = z.object({
  lastName: z.string().min(1, 'Укажите фамилию'),
  firstName: z.string().min(1, 'Укажите имя'),
  middleName: z.string().optional(),
  phone: z.string().regex(/^\+\d{10,15}$/, 'Введите телефон в формате +7…'),
  email: z.string().email('Введите корректный email').optional().or(z.literal('')),
  birthday: z.string().optional(),
  notes: z.string().optional(),
})
export type ClientCreateInput = z.infer<typeof clientCreateSchema>
```

```tsx
// src/features/clients/components/ClientForm.tsx
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { ApiError } from '@sportzal/api-client'
import { isDomainError } from '@/shared/api/services/mock/errors'  // see Pattern 9

export function ClientForm({ mode, initial, onClose }: Props) {
  const form = useForm<ClientCreateInput>({
    resolver: zodResolver(clientCreateSchema),
    defaultValues: initial,
  })
  const { mutate, isPending } = useCreateClient()

  const onSubmit = form.handleSubmit((values) => {
    mutate(values, {
      onError: (err) => {
        // Unified error mapping
        const code = isDomainError(err) || err instanceof ApiError ? err.code : 'unknown'
        const fields = isDomainError(err) || err instanceof ApiError ? err.fields : undefined
        if (fields) {
          for (const [k, v] of Object.entries(fields)) {
            form.setError(k as keyof ClientCreateInput, { type: 'server', message: String(v) })
          }
        } else {
          form.setError('root', { type: 'server', message: err.message ?? 'Ошибка' })
        }
      },
      onSuccess: () => onClose(),
    })
  })
  // …
}
```

> Source: ctx7 `/react-hook-form/react-hook-form` — `setError(name, {type, message})` and `setError('root', …)` for form-level errors. `zodResolver` API is unchanged across resolvers v3 and v5.

### Pattern 9: DomainError ↔ ApiError Unification

**What:** Two error classes with identical shape but different identity. Provide a single type guard that succeeds for both, plus an optional unifier helper.
**When to use:** Every UI-side error handling site (form `setError`, toast trigger, etc.).

```ts
// src/shared/api/services/mock/errors.ts
export class DomainError extends Error {
  constructor(
    public code: string,
    message: string,
    public fields?: Record<string, string>,
  ) {
    super(message)
    this.name = 'DomainError'
  }
}

export function isDomainError(e: unknown): e is DomainError {
  return e instanceof DomainError
}
```

```ts
// src/shared/api/services/error.ts (lives outside mock/ + http/ — shared seam)
import { ApiError } from '@sportzal/api-client'
import { isDomainError, DomainError } from './mock/errors'

export type AppError = ApiError | DomainError

export function isAppError(e: unknown): e is AppError {
  return e instanceof ApiError || isDomainError(e)
}

export function appErrorCode(e: unknown): string | undefined {
  return isAppError(e) ? e.code : undefined
}
```

> The `error.ts` file lives at `src/shared/api/services/error.ts` (NOT inside `mock/` or `http/` so the layered ESLint rule allows UI/features/routes to import it). The ESLint rule bans imports from `services/mock/**` and `services/http/**` — `services/error.ts` is sibling, allowed.

### Pattern 10: Mock Service with localStorage + Faker + RBAC

**What:** Faker-seeded initial data, persisted via the central `_db.ts` shim under `sportzal:mock:v1`, every method enforces `can(role, action, resource)` and throws `DomainError`.
**Example skeleton:**

```ts
// src/shared/api/services/mock/_db.ts
const STORAGE_KEY = 'sportzal:mock:v1'
type DB = { clients: Client[] /* ; future domains */ }

export function loadDB(): DB {
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY)
    if (!raw) return seed()
    return JSON.parse(raw) as DB
  } catch {
    return seed()
  }
}
export function saveDB(db: DB): void {
  window.localStorage.setItem(STORAGE_KEY, JSON.stringify(db))
}
function seed(): DB { /* faker.seed(42); generate ~30 clients … */ }
```

```ts
// src/shared/api/services/mock/clients.ts
import { faker } from '@faker-js/faker'
import { can } from '@/shared/session/can'
import { useSessionStore } from '@/shared/session/store'
import { DomainError } from './errors'
import { loadDB, saveDB } from './_db'
import { delay } from './_latency'

export const clients: ClientsService = {
  async list(query) {
    await delay()
    const role = useSessionStore.getState().role
    if (!can(role, 'view', 'clients')) throw new DomainError('forbidden', 'Доступ запрещён')
    const db = loadDB()
    const filtered = db.clients.filter(c =>
      !query.q ||
      `${c.lastName} ${c.firstName} ${c.phone}`.toLowerCase().includes(query.q.toLowerCase())
    )
    const total = filtered.length
    const page = query.page
    const pageSize = query.pageSize
    return { items: filtered.slice((page - 1) * pageSize, page * pageSize), total, page, pageSize }
  },
  async delete(id) {
    await delay()
    const role = useSessionStore.getState().role
    if (!can(role, 'delete', 'clients')) throw new DomainError('forbidden', 'Доступ запрещён')
    const db = loadDB()
    const idx = db.clients.findIndex(c => c.id === id)
    if (idx < 0) throw new DomainError('not_found', 'Клиент не найден')
    db.clients.splice(idx, 1)
    saveDB(db)
  },
  // … create / update / get
}
```

> `useSessionStore.getState()` (NOT a hook) is correct here — services are not React-rendered.

### Anti-Patterns to Avoid

- **Conditional render of `<AppShell>` in `__root.tsx`.** Root always renders; the `if (auth) <AppShell>` pattern leaks AppShell flicker before redirect. Use `_protected` pathless route. [CITED: tanstack/router auth-and-guards SKILL]
- **Per-query `onError` for session_expired.** Doesn't fire for cache hits, doesn't fire for already-mounted observers. Cache-level `onError` is the only correct seam. [VERIFIED: ctx7 /tanstack/query]
- **Reading `useSessionStore` inside http-mode UI.** Stale role after server-side role change → RBAC bypass risk. Always go through `getSession()` adapter (D-05).
- **Caching `sportzal_csrf` in JS module state.** The cookie is rotated on login/refresh/OTP-verify (Phase 4 D-26). Read from `document.cookie` per-request (Phase 9 D-11 — already enforced in `packages/api-client`).
- **`new Date(dateOnlyString)` for client birthdays.** DST hazard. Use `parse(value, 'yyyy-MM-dd', new Date())` from date-fns (CLAUDE.md domain conventions).
- **Throwing `Error` (not `DomainError`) from mock services.** Breaks the unified handling pattern; `setError` won't get `fields`.
- **Re-fetching `/auth/me` on every navigation.** `staleTime: 30_000` + cache key + `ensureQueryData` make navigation cheap — DO NOT call `services.auth.me()` directly in components.
- **Cleared cache before `router.navigate('/login')`.** If you `queryClient.clear()` THEN navigate, the `/_public/login` `beforeLoad` will fire `ensureQueryData(me)` which (in mock) returns the seeded user → infinite redirect. Order: in mock-mode the `beforeLoad` is no-op (we early-return); in http-mode `me()` will 401 and the catch falls through to render. Verified order matches D-03.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| HTTP transport, CSRF injection, single-flight refresh, `ApiError` | Hand-rolled fetch wrappers in `http/auth.ts` | `@sportzal/api-client.request<P,M>` (Phase 9) | Phase 9 product; refactor risk if duplicated |
| Phone E.164 input + country | Regex-driven `<Input>` | ReUI `PhoneInput` (`pnpm dlx shadcn add @reui/phone-input`) — internally `react-phone-number-input` | Country dropdown, E.164 normalization, paste handling for free [CITED: reui.io phone-input.mdx] |
| 6-digit OTP UI | Manual 6 `<Input>`s with index management | ReUI `InputOTP` (`pnpm dlx shadcn add @reui/input-otp`) — internally the `input-otp` npm package by guilhermerodz | Battle-tested paste handling, autofocus chain, accessibility [VERIFIED: shadcn input-otp registry; npm view input-otp = 1.4.2] |
| Pagination UI + page size selector | Custom `<button>` row | ReUI `DataGridPagination` | Built-in `sizes`, `info` template, ellipsis [VERIFIED: ctx7 /keenthemes/reui data-grid.mdx] |
| Form state + dirty tracking + field validation | useState + manual validate | react-hook-form + zodResolver | Already in stack; same Zod schema mock and form |
| Toast notifications | Custom toast | sonner (existing) | Already wired in `main.tsx` |
| Date formatting (RU locale, Europe/Moscow) | `Intl.DateTimeFormat` ad-hoc | date-fns + `ru` locale + `src/shared/i18n/date.ts` (existing) | Project convention; DST-safe |
| Money display | Manual format | `formatMoney(minor)` from `src/shared/lib/money.ts` (existing) | NBSP, RUB, ru-RU |
| Branded ID type | Plain `string` | `type ClientId = Brand<string, 'ClientId'>` | CLAUDE.md domain convention; compile-time guard against passing raw strings |
| Random debounce | setTimeout in `useEffect` | `useDebounceValue` from `usehooks-ts` OR a tiny custom hook in `shared/lib/hooks/` | Search input typing → URL update needs ~300ms debounce; existing project doesn't bundle a debounce — Claude's discretion (CONTEXT D-10 mentions debounce). **Recommended: 30-LOC custom hook** to avoid a new dep. |

**Key insight:** Phase 10 adds zero new transport, zero new auth primitives, zero new CSRF handling. Every "complex" piece was sealed in earlier phases. The phase is mostly composition + ReUI registry adoption + correctness wiring.

## Runtime State Inventory

> This phase introduces real backend + new mock data. The localStorage key `sportzal:mock:v1` is a runtime data surface — not just a code change.

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data (localStorage) | `sportzal:session:v1` (existing — Zustand session-store, holds `role`); `sportzal:ui:v1` (existing — theme prefs); `sportzal:mock:v1` (NEW — central mock DB seeded from faker, holds clients) | Code edit only — Phase 10 creates the new key fresh; no migration of old data needed (no v0). For `sportzal:session:v1`: leave untouched, mock-mode continues using it. |
| Live service config | None — phase touches only frontend code | None |
| OS-registered state | None | None |
| Secrets/env vars | `VITE_API_MODE` becomes runtime-valid as `'http'` (was already type-checked); `VITE_API_BASE_URL` (used by `packages/api-client` fetcher) — must be set in `.env.development` | Update `.env.example` and `.env.development` to document `VITE_API_MODE=http` and `VITE_API_BASE_URL=http://localhost:8000` (or compose-network address). No secret material. |
| Build artifacts / installed packages | `packages/api-client/src/schema.d.ts` (committed per Phase 9 D-07) — admin-web depends on it via workspace. If schema regenerated by backend changes, admin-web must rebuild. | The `predev` hook (`pnpm --filter @sportzal/api-client codegen`) already in `apps/admin-web/package.json` line 13 handles this — verified. |

## Common Pitfalls

### Pitfall 1: TanStack Router pathless layout doesn't strip parent layout
**What goes wrong:** Engineer creates `_public.tsx` and `_public/login.tsx` but `__root.tsx` still wraps `<Outlet/>` in `<AppShell>` — login renders inside AppShell.
**Why it happens:** Pathless layouts compose ON TOP of parents, they don't replace them. `_public` is a child of root.
**How to avoid:** Move AppShell OUT of `__root.tsx` and INTO `_protected.tsx` exclusively. `__root.tsx` only contains providers + ScrollRestoration + devtools.
**Warning signs:** Login page shows sidebar / header / RoleSwitcher — symptom that AppShell is still in `__root`.

### Pitfall 2: `RoleGate` reads `useSessionStore` directly → wrong role in http-mode
**What goes wrong:** In http-mode, `useSessionStore.role` is the dev-default `'owner'` (since `RoleSwitcher` is hidden) — `RoleGate` happily renders owner-only buttons even when the actual user is `reception`.
**Why it happens:** The current `RoleGate.tsx` line 15 (`const role = useSessionStore((s) => s.role)`) was correct for mock-only world; Phase 10 didn't get the API_MODE branch.
**How to avoid:** Introduce `useCurrentRole()` (branches on API_MODE) and refactor `RoleGate` + every direct consumer (`ProfileMenu` line 15, `RoleSwitcher` line 21–22, `AppShell` if any) to read through it.
**Warning signs:** Reception logged in via http-mode sees the delete-trash icon; CONTEXT.md D-11 promises that's impossible.

### Pitfall 3: Circular import between `queryClient` ↔ `router` ↔ `redirect-on-session-expired`
**What goes wrong:** `app/queryClient.ts` imports `redirectOnSessionExpired`; that file imports `router`; `router.ts` imports `queryClient`. Vite blows up at dev start with "cannot access before initialization".
**Why it happens:** ES module cycles are static and unforgiving when initialization order matters.
**How to avoid:** Make `redirectOnSessionExpired` look up the router lazily — either (a) import dynamically inside the function (`const { router } = await import('./router')` — async, but `redirectOnSessionExpired` returns void anyway), or (b) keep router lookup behind a getter that runs after module init. Recommended: option (a).
**Warning signs:** Dev server fails to start with `ReferenceError: Cannot access 'queryClient' before initialization`.

### Pitfall 4: Optimistic delete with paginated lists — total count off by one
**What goes wrong:** Optimistic delete decrements `total` on the current page snapshot. After server confirms, `invalidateQueries` refetches; if user is on page N and deleted item was the last item on page N-1, the snapshot showed N items, now there are N-1 — refetch shifts everything.
**Why it happens:** Pagination state can't be reconciled optimistically without server.
**How to avoid:** Snapshot, optimistic patch, accept transient flicker on `onSettled` invalidate. DO NOT try to recompute pagination locally. The example in Pattern 4 does the right thing (simple decrement; invalidate corrects).
**Warning signs:** "Total: 30" displayed but page only shows 29 rows for a beat.

### Pitfall 5: `redirecting` flag never reset after navigation throws
**What goes wrong:** `router.navigate(...)` rejects (rare — e.g., during teardown), `.finally()` runs but a subsequent `session_expired` should redirect again. If the flag is set and never cleared, the user gets stuck.
**Why it happens:** The `.finally()` clears the flag, but if multiple errors fire in the same tick the flag is still `true` for the second one (which is what we want — debounced single-flight). Subtle: a second redirect attempt within the same redirect cycle is correctly suppressed.
**How to avoid:** Verify with a unit test: simulate two `session_expired` errors in quick succession, assert `router.navigate` was called exactly once. Reset the flag manually in test teardown via the `__resetRedirectingFlagForTests` export (NOT in `index.ts` barrel).
**Warning signs:** Test for "two simultaneous failed mutations" fails with `expect(navigate).toHaveBeenCalledTimes(1)` getting 2.

### Pitfall 6: `validateSearch` + Zod 3 vs Zod 4 syntax drift
**What goes wrong:** TanStack Router docs use Zod v4 syntax (`fallback(z.number(), 1).default(1)`); project is on Zod v3. The v4 `fallback` helper doesn't exist in v3.
**Why it happens:** Zod 3 → 4 migration is mid-flight ecosystem-wide.
**How to avoid:** Use Zod 3 idioms: `z.number().int().min(1).default(1)`. For coerced URL params (which are strings before parse): `z.coerce.number().int().min(1).default(1)`. Verify with type-check, not just runtime.
**Warning signs:** `import('zod').fallback is not a function`.

### Pitfall 7: `services.mock.auth.me()` doesn't return the cached user immediately on RoleSwitcher change
**What goes wrong:** Owner switches to reception via `RoleSwitcher`; `RoleGate` correctly hides owner-only buttons (reads Zustand directly in mock-mode), but TanStack Query cache for `authKeys.me` is stale.
**Why it happens:** D-05 says http-mode reads cache, mock-mode reads Zustand — but if both stores can coexist in dev, behavior diverges.
**How to avoid:** `RoleSwitcher` `onSelect` should ALSO `queryClient.invalidateQueries({queryKey: authKeys.me})` so the next render sees consistent data, even though `useCurrentRole` only reads Zustand in mock mode. Belt and suspenders.
**Warning signs:** Hard-to-reproduce visual glitch when toggling role in dev.

### Pitfall 8: `next=` URL leaking sensitive search params into login screen
**What goes wrong:** `router.state.location.href` includes `?searchToken=...` from some hypothetical future feature; that's now in `?next=` of `/login` and shareable.
**Why it happens:** Naive serialization of full URL.
**How to avoid:** For Phase 10, `clients?q=...` is the only search-param-bearing protected route, and search query is non-sensitive. Use `encodeURIComponent(router.state.location.href)` as planned. Add a code comment flagging this for v1.2 if other sensitive search-params land.
**Warning signs:** N/A in Phase 10 scope.

## Code Examples

### Login form (email/password) — verified pattern

```tsx
// src/features/auth/model/schema.ts
import { z } from 'zod'

export const emailLoginSchema = z.object({
  email: z.string().email('Введите корректный email'),
  password: z.string().min(1, 'Введите пароль'),
})
export type EmailLoginInput = z.infer<typeof emailLoginSchema>

// src/features/auth/components/EmailLoginForm.tsx
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { useNavigate } from '@tanstack/react-router'
import { ApiError } from '@sportzal/api-client'
import { Button } from '@/shared/ui/button'
import { Input } from '@/shared/ui/input'
import { useLogin } from '../api/hooks'
import { emailLoginSchema, type EmailLoginInput } from '../model/schema'

export function EmailLoginForm({ next }: { next?: string }) {
  const navigate = useNavigate()
  const form = useForm<EmailLoginInput>({ resolver: zodResolver(emailLoginSchema) })
  const { mutate, isPending } = useLogin()

  const onSubmit = form.handleSubmit((values) => {
    mutate(values, {
      onSuccess: () => navigate({ to: next ?? '/', replace: true }),
      onError: (err) => {
        if (err instanceof ApiError && err.code === 'invalid_credentials') {
          form.setError('root', { type: 'server', message: 'Неверный email или пароль.' })
        } else if (err instanceof ApiError && err.code === 'rate_limited') {
          form.setError('root', { type: 'server', message: 'Слишком много попыток. Попробуйте через несколько минут.' })
        } else {
          form.setError('root', { type: 'server', message: 'Ошибка соединения.' })
        }
      },
    })
  })

  return (
    <form onSubmit={onSubmit} className="space-y-4">
      <Input type="email" autoComplete="username" {...form.register('email')} />
      <Input type="password" autoComplete="current-password" {...form.register('password')} />
      {form.formState.errors.root && (
        <p className="text-destructive text-sm">{form.formState.errors.root.message}</p>
      )}
      <Button type="submit" disabled={isPending} className="w-full">
        {isPending ? 'Вход…' : 'Войти'}
      </Button>
    </form>
  )
}
```

### Telegram poll — D-04 cadence + 5min timeout

```tsx
// src/features/auth/components/TelegramLoginTab.tsx (skeleton)
import { useQuery, useMutation } from '@tanstack/react-query'
import { useEffect, useRef, useState } from 'react'
import { authKeys } from '../api/keys'
import { services } from '@/shared/api/services'

const POLL_INTERVAL_MS = 3_000
const TIMEOUT_MS = 5 * 60 * 1_000

export function TelegramLoginTab() {
  const [token, setToken] = useState<string | null>(null)
  const [deepLink, setDeepLink] = useState<string | null>(null)
  const [timedOut, setTimedOut] = useState(false)
  const startedAtRef = useRef<number | null>(null)

  const start = useMutation({
    mutationFn: () => services.auth.telegramStart(),
    onSuccess: (r) => {
      setToken(r.deepLinkToken)
      setDeepLink(r.deepLinkUrl)
      setTimedOut(false)
      startedAtRef.current = Date.now()
    },
  })

  const status = useQuery({
    queryKey: token ? authKeys.telegramStatus(token) : ['idle'],
    queryFn: () => services.auth.telegramStatus(token!),
    enabled: !!token && !timedOut,
    refetchInterval: POLL_INTERVAL_MS,
  })

  // Track elapsed against startedAtRef (NOT a fresh timer per render)
  useEffect(() => {
    if (!startedAtRef.current || timedOut || status.data?.bound) return
    const id = setInterval(() => {
      if (Date.now() - startedAtRef.current! > TIMEOUT_MS) {
        setTimedOut(true)
      }
    }, 1_000)
    return () => clearInterval(id)
  }, [token, timedOut, status.data?.bound])

  // Three-state UI: not-started → polling → bound (show OTP) | timed-out
}
```

### Logout in `ProfileMenu` (D-08)

```tsx
// src/shared/ui/app-shell/ProfileMenu.tsx (modify line 36)
import { useNavigate } from '@tanstack/react-router'
import { useMutation } from '@tanstack/react-query'
import { LogOut } from 'lucide-react'
import { services } from '@/shared/api/services'
import { queryClient } from '@/app/queryClient'

const navigate = useNavigate()
const logout = useMutation({
  mutationFn: () => services.auth.logout(),
  onSuccess: () => {
    queryClient.clear()
    void navigate({ to: '/login', replace: true })
  },
})
// …
<DropdownMenuItem onSelect={() => logout.mutate()} disabled={logout.isPending}>
  <LogOut className="mr-2 size-4" />
  {t('shell.profile.logout')}
</DropdownMenuItem>
```

### ESLint rule banning raw `fetch(` (FE-07)

```js
// apps/admin-web/eslint.config.js — additional config block
{
  files: ['src/**/*.{ts,tsx}'],
  ignores: [
    // explicit allow-list — only these may call raw fetch():
    //   the package itself lives outside this app; the allow-list here
    //   is only for admin-web src/. packages/api-client/src/ is a SEPARATE
    //   eslint config in a sibling workspace — not affected by this rule.
    'src/shared/api/services/http/**',
  ],
  rules: {
    'no-restricted-syntax': [
      'error',
      {
        selector: "CallExpression[callee.name='fetch']",
        message: 'Use @sportzal/api-client request() — never raw fetch outside http/.',
      },
      // …keep existing VITE_API_MODE rule entries here too (combine carefully — see Pitfall 9)
    ],
  },
},
```

> Pitfall 9: ESLint flat config combines rule arrays per-file via "last config wins per rule". The existing `no-restricted-syntax` rule for `VITE_API_MODE` (lines 92-101) and palette ban (lines 71-83) must be preserved — appending a new selector to the same array, not creating a new rule entry that nukes the others. Use file-targeted config blocks; the planner must inspect the existing `eslint.config.js` and merge selectors carefully.

```ts
// src/__fixtures/raw-fetch-leak.ts — proves the rule fires
// FIXTURE: must trigger no-restricted-syntax —
// raw fetch is forbidden outside packages/api-client/src/
// and src/shared/api/services/http/.
export const leaked = await fetch('/api/v1/clients')
```

```js
// scripts/assert-eslint-fixtures.mjs (add line 22 entry)
{ file: 'src/__fixtures/raw-fetch-leak.ts', rule: 'no-restricted-syntax' },
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Per-query `onError` for global handlers | `QueryCache` + `MutationCache` `onError` | TanStack Query v4 | Phase 10 must use cache-level (D-07) |
| `validateSearch: (s) => schema.parse(s)` | `validateSearch: schema` (auto-applies `.parse`) | TanStack Router v1.95+ | Cleaner; either form works in 1.95+ |
| `useSessionStore` as universal SoT | Cache-as-SoT in http-mode + adapter | This phase (D-05) | Refactor `RoleGate` consumers (Pitfall 2) |
| `new-york` shadcn style | `base-nova` ReUI style | This phase (D-14) | Visual diff in primitives; AppShell internals unchanged (D-15) |
| Manual `<Table>` + react-table layout | ReUI `DataGrid` (wraps react-table) | This phase (D-16) | Less code; URL-driven pagination via `manualPagination: true` |

**Deprecated/outdated:**
- Zod v4 `fallback` helper — DON'T use; project on Zod 3.
- TanStack Query v4 mutation callback signature `(error, vars, context)` — v5 is `(error, vars, onMutateResult, context)` — verify hooks against the v5 signature [VERIFIED: ctx7 /tanstack/query optimistic-updates.md].

## Project Constraints (from CLAUDE.md + apps/admin-web/CLAUDE.md)

These are non-negotiable directives the planner MUST honor — they are at the same authority level as locked CONTEXT.md decisions.

- **pnpm 9 + Node 20** (project root CLAUDE.md). All install commands use `pnpm dlx`, never `npx`.
- **Frontend integrity**: `apps/admin-web` is a port of `./frontend`; structural / mock changes require explicit phase decisions. Phase 10 has them (D-12 explicitly authorizes mock additions for auth + clients only — other domains untouched).
- **Russian-only UI**, semantic shadcn tokens (raw palette banned by ESLint), branded UUIDv4 IDs, ISO date strings, money in minor units (`Money` type), `Intl.NumberFormat('ru-RU', {currency:'RUB'})` for display.
- **No semicolons** (Prettier ASI), single quotes, 100-char line width, trailing commas.
- **`strict: true` + `noUncheckedIndexedAccess`** — every array/record access yields `T | undefined`. Defensive: `data.items[0]?.id`, never `data.items[0].id`.
- **Layered import boundary** (`apps/admin-web/eslint.config.js` lines 47-69): UI/features/routes/entities/`shared/ui`/app cannot import from `services/mock` or `services/http` directly. Always go through `services` swap seam OR `services/error.ts` (NEW Pattern 9 module — sibling, allowed).
- **`VITE_API_MODE` chokepoint**: only `src/shared/api/**` reads it. `main.tsx` already imports `API_MODE` indirectly through services or env.ts re-export — verify.
- **shadcn customization**: don't hand-edit `components/ui/*`; mark divergence with `// SHADCN-DIVERGENCE: …`. ReUI replacement is a clean install via CLI, not a hand-edit.
- **NIST 800-63B password rules** (mostly server concern): no complexity rules, no rotation, no lockout — just min-length 12 (server-enforced; FE form validation matches).
- **Russian copy in i18n dictionary** `src/shared/i18n/ru.ts` only. No inline RU strings except inside `t('key')` callsites or one-off hardcoded labels mirrored to dict entries (UI-SPEC has the full list — planner expands `ru.ts` accordingly).
- **`VITE_API_MODE=mock` continues to work** — SC#3 of Phase 10. Mock parity is a hard checkpoint, not a "nice to have."

## Validation Architecture

> `workflow.nyquist_validation` config not explicitly disabled — section included.

### Test Framework

| Property | Value |
|----------|-------|
| Framework | Vitest 2.1.8 (project ^2.1.8) + @testing-library/react 16.1.0 + jsdom 25 |
| Config file | `apps/admin-web/vitest.config.ts` (existing) |
| Quick run command | `pnpm --filter sportzal-adminka test` (runs once) |
| Full suite command | `pnpm --filter sportzal-adminka test && pnpm --filter sportzal-adminka lint && pnpm --filter sportzal-adminka lint:fixtures && pnpm --filter sportzal-adminka typecheck` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| FE-01 | http/auth + http/clients implement contract via `request()` | unit (mock fetch via MSW-less stub) | `pnpm test src/shared/api/services/http/auth.test.ts` | ❌ Wave 0 |
| FE-01 | http/clients passes `q/page/pageSize` correctly | unit | `pnpm test src/shared/api/services/http/clients.test.ts` | ❌ Wave 0 |
| FE-02 | `/login` renders email + telegram tabs | component | `pnpm test src/features/auth/components/LoginPage.test.tsx` | ❌ Wave 0 |
| FE-02 | Telegram polling stops after 5min, refresh button appears | component (vi.useFakeTimers) | `pnpm test src/features/auth/components/TelegramLoginTab.test.tsx` | ❌ Wave 0 |
| FE-03 | mock-mode `/login` works against `services.mock.auth` | component (renderWithProviders mock-mode) | `pnpm test src/features/auth/components/LoginPage.mock.test.tsx` | ❌ Wave 0 |
| FE-03 | mock-mode `/clients` lists/searches/CRUDs | component | `pnpm test src/features/clients/components/ClientsTable.mock.test.tsx` | ❌ Wave 0 |
| FE-04 | `clientsKeys` factory produces stable keys | unit | `pnpm test src/features/clients/api/keys.test.ts` | ❌ Wave 0 |
| FE-04 | route loader uses `ensureQueryData` with same key as hook | component (assert query cache after navigation) | `pnpm test src/routes/_protected/clients.test.tsx` | ❌ Wave 0 |
| FE-04 | optimistic delete rolls back on error | unit (hook test) | `pnpm test src/features/clients/api/hooks.delete.test.ts` | ❌ Wave 0 |
| FE-05 | `session_expired` triggers single redirect; second concurrent error suppressed | unit | `pnpm test src/features/auth/api/redirect-on-session-expired.test.ts` | ❌ Wave 0 |
| FE-05 | next= URL is encoded; login success navigates back | component | (covered by FE-02 + integration) | ❌ Wave 0 |
| FE-06 | logout clears query cache + navigates `/login` | component | `pnpm test src/shared/ui/app-shell/ProfileMenu.test.tsx` | ❌ Wave 0 (extend existing) |
| FE-07 | ESLint negative-test fixture trips `no-restricted-syntax` | lint:fixtures | `pnpm --filter sportzal-adminka lint:fixtures` | ❌ Wave 0 (add fixture) |
| D-12 | mock RBAC: reception + delete-clients → DomainError forbidden | unit | `pnpm test src/shared/api/services/mock/clients.rbac.test.ts` | ❌ Wave 0 |
| D-11 | RoleGate hides delete for reception in DOM | component | `pnpm test src/features/clients/components/ClientsTable.rbac.test.tsx` | ❌ Wave 0 |

### Sampling Rate

- **Per task commit:** `pnpm --filter sportzal-adminka test path/to/changed.test.ts -x` (single test file)
- **Per wave merge:** `pnpm --filter sportzal-adminka test && pnpm --filter sportzal-adminka lint:fixtures`
- **Phase gate:** `pnpm install && pnpm -r lint && pnpm -r typecheck && pnpm -r test && pnpm --filter sportzal-adminka lint:fixtures` (the same battery CI runs per Phase 9 D-02)

### Wave 0 Gaps

- [ ] `src/__fixtures/raw-fetch-leak.ts` — covers FE-07
- [ ] `src/features/auth/api/redirect-on-session-expired.test.ts` — covers FE-05 single-flight
- [ ] `src/features/clients/api/keys.test.ts` — covers FE-04 keys-factory invariants
- [ ] `src/features/clients/api/hooks.delete.test.ts` — covers FE-04 optimistic rollback
- [ ] `src/shared/api/services/mock/clients.rbac.test.ts` — covers D-12 RBAC mock parity
- [ ] `src/test/fixtures/clients.ts` — shared faker.seed(42) factories for tests
- [ ] No new framework install needed; Vitest + RTL already set up (verified `vitest.config.ts` exists per file listing)

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | yes (consumer) | Phase 5 server-side; FE only consumes — DO NOT cache password / OTP locally [VERIFIED: REQUIREMENTS] |
| V3 Session Management | yes (consumer) | httpOnly cookies — FE never reads them; `getSession` reads cache, not cookies |
| V4 Access Control | yes | `can(role, action, resource)` + `RoleGate` (existing); reception cannot view delete button (D-11) |
| V5 Input Validation | yes | Zod schemas on every form; same schema validates mock service input (CLAUDE.md domain rules) |
| V6 Cryptography | no | All crypto is server-side (Phase 4-5 Argon2/JWT/CSRF) |

### Known Threat Patterns for React 19 + admin SPA

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Open redirect via `next=` query param | Tampering | Validate `next` is same-origin path before navigating. After login `navigate({to: search.next ?? '/'})` — TanStack `to` doesn't accept absolute URLs by default, mitigating; still: planner adds explicit `if (next?.startsWith('http')) next = '/'` guard. |
| `localStorage` poisoning leaks role to attacker | Information Disclosure | Already non-sensitive (only role + theme stored). Phase 10 adds mock client data (only present in mock-mode where there's no real auth). Document explicitly. |
| `dangerouslySetInnerHTML` XSS | Tampering | None used in Phase 10. ESLint `react/no-danger` is intentionally OFF (eslint.config.js line 84) — be paranoid in code review. |
| CSRF on mutating requests | Tampering | Server-enforced (Phase 6); client auto-injects via `request()` (Phase 9 D-11) — Phase 10 changes nothing here |
| Click-jacking on /login | Tampering | `X-Frame-Options` / CSP `frame-ancestors` — server header, out of Phase 10 scope (CLAUDE.md TODO Phase 7 nonce) |
| Session-fixation via copied cookies | Tampering | Backend rotates refresh-token family (Phase 5); FE has no role |

## Sources

### Primary (HIGH confidence)
- ctx7 `/tanstack/router` — pathless layout-routes (`_authenticated.tsx` SKILL), `validateSearch` + Zod, `loaderDeps`, `ensureQueryData` from loader, `useNavigate({search: prev => …})`, `isRedirect` re-throw idiom
- ctx7 `/tanstack/query` — `new QueryCache({onError})`, `new MutationCache({onError})`, optimistic update with `getQueriesData` snapshot + rollback, v5 mutation callback signature `(err, vars, onMutateResult, context)`
- ctx7 `/keenthemes/reui` — DataGrid full API (`table`, `recordCount`, `tableLayout`, `DataGridContainer`, `DataGridPagination` with `sizes`/`info`/`more`), PhoneInput (E.164, country selector, react-phone-number-input wrapper), components.json `registries: {"@reui": ...}` mechanics, `pnpm dlx shadcn add @reui/<name>` install command, get-started.mdx
- ctx7 `/react-hook-form/react-hook-form` — `setError(name, {type, message})`, `setError('root', …)`, zodResolver pattern
- npm registry — verified versions 2026-05-03: `@tanstack/react-router@1.169.1`, `@tanstack/react-query@5.100.9`, `@tanstack/react-table@8.21.3`, `react-phone-number-input@3.4.16`, `input-otp@1.4.2`, `zod@4.4.2`, `openapi-typescript@7.13.0`, `@hookform/resolvers@5.2.2`
- Repo files (read this session): `apps/admin-web/CLAUDE.md`, `eslint.config.js`, `package.json`, `components.json`, `src/app/{main,router,queryClient}.ts(x)`, `src/routes/__root.tsx`, `src/routes/clients.tsx`, `src/shared/api/{services/index.ts,config/env.ts,contracts/index.ts}`, `src/shared/session/{can.ts,RoleGate.tsx,store.ts,types.ts}`, `src/shared/ui/app-shell/{ProfileMenu.tsx,RoleSwitcher.tsx}`, `src/shared/i18n/ru.ts`, `src/__fixtures/api-mode-leak.ts`, `scripts/assert-eslint-fixtures.mjs`

### Secondary (MEDIUM confidence)
- ReUI `base-nova` style URL behavior — UI-SPEC reports 404 for primitive components at `https://reui.io/r/base-nova/{name}.json` (verified 2026-05-03 by ui-researcher); registry mechanism falls back to shadcn standard. Means: `pnpm dlx shadcn add @reui/button` after style switch may produce identical-to-shadcn-official output for primitives. Test post-install — visual diff is real for `data-grid` and `phone-input` (in-house ReUI components), trivial for primitives that re-export shadcn.
- ReUI `InputOTP` — by ReUI registry mechanics, this resolves to shadcn's official `input-otp` primitive (npm `input-otp@1.4.2`). API: `<InputOTP maxLength={6} value onChange><InputOTPGroup><InputOTPSlot index={0}/>…</InputOTPGroup></InputOTP>`. Paste handling and accessibility built-in.

### Tertiary (LOW confidence)
- (none — every claim resolved to HIGH or MEDIUM)

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | ReUI registry returns ≈identical-to-shadcn primitives for `@reui/button|input|form|label|dropdown-menu|dialog|alert-dialog` after style switch to `base-nova` (per UI-SPEC ui-researcher note: 404 → falls back to shadcn standard) | Standard Stack / Pitfalls | Visual diff larger than expected; planner can mitigate by reviewing PR diff after first install and adjusting CSS tokens in `app/index.css` |
| A2 | `src/__fixtures/` is ignored by app eslint config but linted by `scripts/assert-eslint-fixtures.mjs` (verified existing fixtures pattern at lines 13-23 of `eslint.config.js`); new fixture file works the same way | Code Examples / Wave 0 Gaps | If fixtures dir convention differs, fixture won't trip the rule — discovered immediately by `pnpm lint:fixtures` |
| A3 | TanStack Router v1.95+ accepts `validateSearch: schema` directly (without explicit `.parse`); v1.169.1 confirmed compatible | Pattern 3 | Falls back to `validateSearch: (s) => schema.parse(s)` — cosmetic |
| A4 | `useSuspenseQuery` is acceptable for the clients route despite `<Suspense>` boundary configuration not yet existing in `__root.tsx` — the loader's `ensureQueryData` warms the cache, so `useSuspenseQuery` resolves synchronously on first render | Pattern 3 | If cache misses (race / direct URL load), the `<Suspense>` boundary in `_protected.tsx` (planner adds) catches it; alternative: `useQuery` + manual loading state |
| A5 | `pnpm dlx shadcn add @reui/<name>` correctly writes into `apps/admin-web/src/shared/ui/` per `components.json.aliases.components` (`@/shared/ui` → `apps/admin-web/src/shared/ui`) | Standard Stack | Wrong path → manual move post-install (cheap to fix) |
| A6 | The existing `predev` hook in `apps/admin-web/package.json` line 13 is sufficient — no `postinstall`, no `prebuild` needed for Phase 10 | Runtime State Inventory | If schema.d.ts missing on first clone, dev throws — `pnpm install && pnpm dev` from root regenerates (predev runs) — verified Phase 9 D-08 |
| A7 | The mock-mode `/login` route is reachable in dev by URL (existing routes don't have a /login). After Phase 10's pathless restructure, `_public/login.tsx` is the only `/login` — works in both modes | Pattern 1 | None — confirmed by reading current `routes/` listing (no `login.tsx` exists) |

> Risk levels are LOW for all assumptions — each has a cheap mitigation. None warrant blocking the plan; surface to discuss-phase if uncertainty grows during execution.

## Open Questions (RESOLVED)

> All open questions from the additional_context (research focus areas 1-20) are answered above. Resolutions for the three uncertainties below are folded back into Plan 06 (WARNING #9 fix) and confirmed for Plan 04/06 (Toaster behavior).

1. **PhoneInput vs raw masked input — final choice.**
   - What we know: ReUI offers `@reui/phone-input` (react-phone-number-input wrapper, E.164 + country dropdown). UI-SPEC says "Claude's discretion." Default country `RU` makes sense for РФ/СНГ market.
   - What's unclear: Bundle-size cost (`react-phone-number-input` ships ~30 KB gz — comparable to date-fns base, acceptable) vs feature value of country dropdown for RU-only project (low — but enables future BY/KZ/UZ tenants).
   - Recommendation: Use `@reui/phone-input` with `defaultCountry="RU"`. Tradeoff is in the phase budget; switching later to a hand-rolled mask is trivial.
   - **RESOLVED: DEFER** — Phase 10 ships a raw `<Input type="tel" placeholder="+7 (XXX) XXX-XX-XX">` (Plan 06 Task 3). Phone-input mask via `@reui/phone-input` (or `react-imask`) is deferred to v1.2+. Per CONTEXT D-16 ("Phone input — if ReUI has PhoneInput, use; otherwise remains Claude's Discretion") this is within the locked discretion area; backend Phase 8 validates E.164 server-side, and the Zod regex on `clientCreateSchema.phone` rejects malformed input client-side. Rationale: scope-control — Phase 10 is already large.

2. **Toaster for non-blocking acks during Phase 10.**
   - What we know: `<Toaster>` already mounted in `main.tsx`. CONTEXT D-12 says reception delete is RoleGate-hidden, so no "denied" toast. Optimistic mutation rollback should "feel" silent unless server fails.
   - What's unclear: Whether to fire a sonner toast on successful create/update/delete ("Клиент добавлен" etc.) or only on error.
   - Recommendation: silent on success (the optimistic update IS the feedback); toast only on `onError` rollback to surface the failure. Per CLAUDE.md "non-blocking acks via Sonner toast" guidance.
   - **RESOLVED: ADOPTED** — silent on success; toast only on error. Confirmed in Plan 04 (login form: inline error mapping, no success toast — navigation IS the feedback) and Plan 06 (`ClientDeleteDialog` fires `toast.error(...)` only on rollback; create/update/delete success paths close the dialog silently and let the optimistic-cache update speak for itself).

3. **Suspense boundary placement.**
   - What we know: `useSuspenseQuery` in `ClientsTable` requires a `<Suspense>` ancestor. TanStack Router has built-in `pendingComponent` per-route which acts as the suspense fallback.
   - What's unclear: Whether to use TanStack's `pendingComponent` (declarative, route-level) or wrap the table in a manual `<Suspense fallback={<Skeleton/>}>`.
   - Recommendation: TanStack `pendingComponent: () => <ClientsTableSkeleton />` on `/clients` route — co-located with route, matches "DataGrid skeleton rows" per UI-SPEC.
   - **RESOLVED: ADOPTED** — Plan 06 ships `apps/admin-web/src/features/clients/components/ClientsTableSkeleton.tsx` (8 fake rows using existing `<Skeleton>` primitive at `apps/admin-web/src/shared/ui/skeleton.tsx`). `ClientsPage` renders it whenever `query.isPending && !query.data`. We do NOT use TanStack's `pendingComponent` because the route loader already prefetches via `ensureQueryData` (FE-04 same-key invariant), so initial render has data on the cache-hit path; the skeleton covers cache-miss / refetch paths only. This satisfies CLAUDE.md canonical List template (empty / loading / error) and the WARNING #9 fix from the Phase 10 review.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all libraries already in package.json or installed via verified ReUI registry mechanism
- Architecture patterns: HIGH — every major pattern verified against official docs via Context7
- Pitfalls: HIGH for cataloged ones (each backed by code reading or doc study); MEDIUM for "ReUI base-nova primitive 404 fallback" (relies on UI-SPEC's prior verification)
- Validation architecture: HIGH — vitest + RTL already configured; Wave 0 gaps are concrete files
- Security domain: HIGH — V4/V5 are FE concerns and already covered by `can()` + Zod patterns

**Research date:** 2026-05-03
**Valid until:** 2026-06-03 (30 days — TanStack libs and ReUI move at moderate pace; verify versions if execution slips past this)

## RESEARCH COMPLETE
