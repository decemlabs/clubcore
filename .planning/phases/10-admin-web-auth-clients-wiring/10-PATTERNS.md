# Phase 10: admin-web Auth + Clients Wiring — Pattern Map

**Mapped:** 2026-05-03
**Files analyzed:** 30 files to create or modify
**Analogs found:** 27 / 30 (3 with no internal analog — see "No Analog Found")

> All file paths are relative to repo root unless otherwise stated. Phase 10 lives entirely under `apps/admin-web/` (frontend was migrated from `frontend/` in Phase 1). Backend is not touched.

---

## File Classification

### Routes & app-composition layer

| New / Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `apps/admin-web/src/app/main.tsx` (UPDATE) | composition / bootstrap | request-response (boot) | (self — extend existing) | self |
| `apps/admin-web/src/app/queryClient.ts` (UPDATE) | composition / config | event-driven (cache onError) | (self — extend existing) | self |
| `apps/admin-web/src/app/router.ts` (UPDATE) | composition / config | request-response | (self — extend existing) | self |
| `apps/admin-web/src/routes/__root.tsx` (UPDATE) | route / layout | request-response | (self — extend existing) | self |
| `apps/admin-web/src/routes/_public.tsx` (NEW) | route / pathless layout | request-response | `apps/admin-web/src/routes/__root.tsx` | role-match |
| `apps/admin-web/src/routes/_protected.tsx` (NEW) | route / pathless layout | request-response | `apps/admin-web/src/routes/__root.tsx` | role-match |
| `apps/admin-web/src/routes/_public/login.tsx` (NEW) | route / page | request-response | `apps/admin-web/src/routes/index.tsx` (validateSearch) + `apps/admin-web/src/routes/clients.tsx` (beforeLoad redirect) | composite |
| `apps/admin-web/src/routes/clients.tsx` (REPLACE) | route / page | CRUD | `apps/admin-web/src/routes/index.tsx` (validateSearch) + existing placeholder (beforeLoad RBAC) | composite |

### Features (FSD-lite)

| New / Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `apps/admin-web/src/features/auth/api/keys.ts` (NEW) | feature / query-keys factory | — | none in repo (first feature folder) | research-only |
| `apps/admin-web/src/features/auth/api/hooks.ts` (NEW) | feature / hooks (TanStack Query) | request-response | none in repo | research-only |
| `apps/admin-web/src/features/auth/api/redirect-on-session-expired.ts` (NEW) | feature / module-state helper | event-driven | `packages/api-client/src/fetcher.ts` lines 54-74 (module-scoped single-flight pattern) | role-match |
| `apps/admin-web/src/features/auth/components/EmailLoginForm.tsx` (NEW) | feature / component (form) | request-response | none — but copy from research (RHF + Zod resolver pattern) | research-only |
| `apps/admin-web/src/features/auth/components/TelegramLoginTab.tsx` (NEW) | feature / component (poll + OTP) | request-response (polling) | none — research-only (TanStack Query refetchInterval) | research-only |
| `apps/admin-web/src/features/auth/model/schema.ts` (NEW) | feature / Zod schema | — | none in repo | research-only |
| `apps/admin-web/src/features/auth/index.ts` (NEW) | feature / barrel | — | `apps/admin-web/src/shared/i18n/index.ts` | role-match |
| `apps/admin-web/src/features/clients/api/keys.ts` (NEW) | feature / query-keys factory | — | none in repo | research-only |
| `apps/admin-web/src/features/clients/api/hooks.ts` (NEW) | feature / hooks (CRUD + optimistic) | CRUD | none in repo (research-only — TkDodo optimistic pattern) | research-only |
| `apps/admin-web/src/features/clients/components/ClientsTable.tsx` (NEW) | feature / component (DataGrid) | CRUD list | none — ReUI DataGrid usage | research-only |
| `apps/admin-web/src/features/clients/components/ClientForm.tsx` (NEW) | feature / component (form, Dialog content) | request-response | (mirror EmailLoginForm RHF+Zod pattern) | sibling |
| `apps/admin-web/src/features/clients/components/ClientDeleteDialog.tsx` (NEW) | feature / component (AlertDialog) | request-response | none — research-only (shadcn AlertDialog) | research-only |
| `apps/admin-web/src/features/clients/model/schema.ts` (NEW) | feature / Zod schema | — | (mirror auth/model/schema.ts) | sibling |
| `apps/admin-web/src/features/clients/index.ts` (NEW) | feature / barrel | — | `apps/admin-web/src/shared/i18n/index.ts` | role-match |

### Entities

| New / Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `apps/admin-web/src/entities/client/types.ts` (NEW) | entity / domain types + branded ID | — | `apps/admin-web/src/shared/session/types.ts` (small types module) | role-match |
| `apps/admin-web/src/entities/client/index.ts` (NEW) | entity / barrel | — | `apps/admin-web/src/shared/i18n/index.ts` | role-match |

### Shared API layer (contracts + transports)

| New / Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `apps/admin-web/src/shared/api/contracts/auth.ts` (NEW) | contract / interface | — | `apps/admin-web/src/shared/api/contracts/index.ts` (current stub doc-block) | role-match |
| `apps/admin-web/src/shared/api/contracts/clients.ts` (NEW) | contract / interface | — | (mirror auth contract) | sibling |
| `apps/admin-web/src/shared/api/contracts/index.ts` (UPDATE) | contract / barrel | — | (self — current `Contracts = Record<string, never>` stub) | self |
| `apps/admin-web/src/shared/api/services/http/auth.ts` (NEW) | service / http transport | request-response | `packages/api-client/src/fetcher.ts` (consumer of `request<P,M>`) | role-match |
| `apps/admin-web/src/shared/api/services/http/clients.ts` (NEW) | service / http transport | CRUD | (mirror http/auth.ts) | sibling |
| `apps/admin-web/src/shared/api/services/http/index.ts` (UPDATE) | service / barrel | — | (self — extend `services = {} as const` stub) | self |
| `apps/admin-web/src/shared/api/services/mock/auth.ts` (NEW) | service / mock transport | request-response | none in repo (first mock impl) — research-only | research-only |
| `apps/admin-web/src/shared/api/services/mock/clients.ts` (NEW) | service / mock transport | CRUD | (mirror mock/auth.ts) | sibling |
| `apps/admin-web/src/shared/api/services/mock/index.ts` (UPDATE) | service / barrel | — | (self — extend `services = {} as const` stub) | self |

### Shared UI

| New / Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `apps/admin-web/src/shared/ui/app-shell/ProfileMenu.tsx` (UPDATE) | shared-ui / component | request-response | (self — current "Logout" disabled stub on line 36) | self |
| `apps/admin-web/src/shared/ui/app-shell/RoleSwitcher.tsx` (UPDATE) | shared-ui / component | — | (self — add API_MODE guard) | self |
| `apps/admin-web/src/shared/ui/splash.tsx` (NEW) | shared-ui / component | — | `apps/admin-web/src/shared/ui/skeleton.tsx` (small leaf component) | partial |
| `apps/admin-web/src/shared/ui/{button,input,form,label,dropdown-menu,dialog,alert-dialog}.tsx` (REPLACE via ReUI) | shared-ui / primitive | — | `apps/admin-web/src/shared/ui/button.tsx` (current shadcn shape) | self |
| `apps/admin-web/src/shared/ui/data-grid.tsx` (NEW via ReUI) | shared-ui / primitive | CRUD list | (ReUI install — no analog) | external |
| `apps/admin-web/src/shared/ui/input-otp.tsx` (NEW via ReUI) | shared-ui / primitive | request-response | (ReUI install — no analog) | external |

### Tooling / config / fixtures / i18n

| New / Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `apps/admin-web/eslint.config.js` (UPDATE — add fetch ban) | config / lint | — | (self — block at lines 87-102 is the existing `VITE_API_MODE` chokepoint pattern to mirror) | self |
| `apps/admin-web/src/__fixtures/raw-fetch-leak.ts` (NEW) | test / negative-test fixture | — | `apps/admin-web/src/__fixtures/api-mode-leak.ts` | exact |
| `apps/admin-web/scripts/assert-eslint-fixtures.mjs` (UPDATE — add new fixture) | tooling / script | — | (self — `EXPECTED` array on line 19) | self |
| `apps/admin-web/src/shared/i18n/ru.ts` (UPDATE — add login/clients keys) | i18n / dictionary | — | (self — extend existing `shell` block) | self |
| `apps/admin-web/components.json` (UPDATE) | config / shadcn | — | (self — already has `@reui` registry; switch `style`) | self |
| `apps/admin-web/src/app/index.css` (UPDATE — base-nova tokens) | config / theme tokens | — | (self) | self |
| `apps/admin-web/.env.example` / `.env.development` (UPDATE) | config / env docs | — | (self) | self |
| `apps/admin-web/package.json` (UPDATE) | config / deps | — | (self) | self |

---

## Pattern Assignments

### `apps/admin-web/src/routes/_public/login.tsx` (NEW route — beforeLoad redirect + validateSearch)

**Analog:** `apps/admin-web/src/routes/clients.tsx` (current placeholder — beforeLoad guard) + `apps/admin-web/src/routes/index.tsx` (validateSearch with Zod).

**Imports pattern** (from `apps/admin-web/src/routes/clients.tsx` lines 1-3 + `apps/admin-web/src/routes/index.tsx` lines 1-3):

```typescript
import { createFileRoute, redirect } from '@tanstack/react-router'
import { z } from 'zod'
import { t } from '@/shared/i18n'
```

**Route shape — `createFileRoute` with `validateSearch` + `beforeLoad`** (composite of `routes/index.tsx:9-12` and `routes/clients.tsx:5-13`):

```typescript
// routes/index.tsx:5-12 (validateSearch)
const searchSchema = z.object({
  forbidden: z.string().optional(),
})

export const Route = createFileRoute('/')({
  validateSearch: searchSchema,
  component: IndexPage,
})

// routes/clients.tsx:5-13 (beforeLoad with context.getSession + redirect)
export const Route = createFileRoute('/clients')({
  beforeLoad: ({ context, location }) => {
    const { role } = context.getSession()
    if (!can(role, 'view', 'clients')) {
      throw redirect({ to: '/', search: { forbidden: location.href } })
    }
  },
  component: ClientsPage,
})
```

**Key adaptation for `/login`:** D-03 requires `beforeLoad` to call `context.queryClient.ensureQueryData({queryKey: authKeys.me, queryFn: services.auth.me})` and on success `throw redirect({to: search.next ?? '/', replace: true})`. The pattern of `throw redirect()` from `beforeLoad` is established in `routes/clients.tsx:9`. Wrap the `ensureQueryData` call in try/catch — on 401 swallow and let the page render.

**Forbidden-search-param pattern (from `routes/index.tsx:14-29`):**

```typescript
function IndexPage() {
  const search = Route.useSearch()
  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-semibold">{t('shell.nav.home')}</h1>
      {search.forbidden && (
        <div role="alert" className="border-destructive/50 bg-destructive/10 text-destructive rounded-md border p-3 text-sm">
          {t('shell.forbidden')}: <code className="font-mono">{search.forbidden}</code>
        </div>
      )}
    </div>
  )
}
```

**Use this as the model for inline error alerts on the login page** (e.g. 401 invalid_credentials, 429 rate_limited per UI-SPEC). Same `border-destructive/50 bg-destructive/10 text-destructive rounded-md border p-3 text-sm` styling, same `role="alert"`.

---

### `apps/admin-web/src/routes/clients.tsx` (REPLACE — full route with validateSearch + loader + loaderDeps)

**Analog:** `apps/admin-web/src/routes/index.tsx` (validateSearch) + `apps/admin-web/src/routes/clients.tsx` current placeholder (RBAC pattern to preserve).

**Existing RBAC pattern to KEEP** (`routes/clients.tsx:5-13`):

```typescript
beforeLoad: ({ context, location }) => {
  const { role } = context.getSession()
  if (!can(role, 'view', 'clients')) {
    throw redirect({ to: '/', search: { forbidden: location.href } })
  }
},
```

**Extension required by D-10:** add `validateSearch`, `loader`, `loaderDeps`. Pattern composition:

```typescript
// from routes/index.tsx:5-8 — validateSearch with Zod
validateSearch: z.object({
  q: z.string().optional(),
  page: z.number().int().min(1).default(1),
  pageSize: z.number().int().min(10).max(100).default(20),
}).parse,

// new: loader + loaderDeps (research-only — TanStack Router docs)
loaderDeps: ({ search }) => ({ search }),
loader: ({ context, deps: { search } }) =>
  context.queryClient.ensureQueryData({
    queryKey: clientsKeys.list(search),
    queryFn: () => services.clients.list(search),
  }),
```

The `context.queryClient` is already available in `RouterContext` (`apps/admin-web/src/app/router.ts:8-11`).

---

### `apps/admin-web/src/app/main.tsx` (UPDATE — add ensureQueryData splash gate)

**Analog:** self (lines 1-30 below). D-06 requires inserting `ensureQueryData(authKeys.me)` between rehydrate and `createRoot`.

**Current bootstrap shape** (`apps/admin-web/src/app/main.tsx:1-30`):

```typescript
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

await Promise.all([
  useSessionStore.persist.rehydrate(),
  useUiPrefsStore.persist.rehydrate(),
])

const rootEl = document.getElementById('root')
if (!rootEl) throw new Error('#root element not found')

createRoot(rootEl).render(
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

**Phase 10 addition:** branch on `API_MODE === 'http'` (imported from `@/shared/api/services` swap seam), render Splash into `#root` immediately, then `await queryClient.ensureQueryData({queryKey: authKeys.me, queryFn: services.auth.me, retry: false})` inside try/catch (catch is a no-op — router `beforeLoad` resolves), then call `createRoot(...).render(...)`. In mock-mode skip the await entirely (instant boot).

The top-level `await` on line 13 already proves the project is configured for top-level await (Vite + esbuild target ES2022 per CLAUDE.md), so the additional `await ensureQueryData(...)` does not require any tsconfig/build changes.

---

### `apps/admin-web/src/app/queryClient.ts` (UPDATE — add QueryCache + MutationCache onError)

**Analog:** self.

**Current shape** (`apps/admin-web/src/app/queryClient.ts:1-14`):

```typescript
import { QueryClient } from '@tanstack/react-query'

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      refetchOnWindowFocus: false,
      retry: 1,
    },
    mutations: {
      retry: 0,
    },
  },
})
```

**Phase 10 D-07 extension:** add explicit `queryCache: new QueryCache({onError: handleApiError})` and `mutationCache: new MutationCache({onError: handleApiError})`. The `handleApiError` function lives in `apps/admin-web/src/features/auth/api/redirect-on-session-expired.ts` (NEW) — must be imported here. Keep `staleTime: 30_000`, `refetchOnWindowFocus: false` as-is (locked by CLAUDE.md).

---

### `apps/admin-web/src/app/router.ts` (UPDATE — getSession() branches on API_MODE)

**Analog:** self.

**Current shape** (`apps/admin-web/src/app/router.ts:1-21`):

```typescript
import { createRouter } from '@tanstack/react-router'
import type { QueryClient } from '@tanstack/react-query'
import { routeTree } from '@/routeTree.gen'
import { queryClient } from './queryClient'
import { useSessionStore } from '@/shared/session/store'
import type { SessionState } from '@/shared/session/types'

export interface RouterContext {
  queryClient: QueryClient
  getSession: () => SessionState
}

export const router = createRouter({
  routeTree,
  defaultPreload: 'intent',
  defaultPreloadStaleTime: 0,
  context: {
    queryClient,
    getSession: () => useSessionStore.getState(),
  } satisfies RouterContext,
})
```

**Phase 10 D-05 change:** `getSession` becomes a function that branches on `API_MODE`:
- mock → `useSessionStore.getState()` (preserve current behavior)
- http → derive `SessionState` shape from `queryClient.getQueryData(authKeys.me)`; map `me.role` into the `{role, setRole}` shape (`setRole` becomes a no-op in http-mode — RoleSwitcher is hidden by D-12 guard).

The `RouterContext` interface stays the same — only the `getSession` impl forks.

---

### `apps/admin-web/src/features/auth/api/redirect-on-session-expired.ts` (NEW — module-scoped flag)

**Analog:** `packages/api-client/src/fetcher.ts:54-74` (module-scoped single-flight Promise pattern).

**Pattern to copy** (`packages/api-client/src/fetcher.ts:54-74`):

```typescript
// D-A4: module-scoped single-flight promise. Concurrent awaiters share the
// same promise. The slot is cleared on the *next microtask* after settle so
// that a 401 storm arriving in the same tick latches onto the in-flight
// promise instead of triggering a second refresh (CR-02).
let inFlightRefresh: Promise<Response> | null = null

function refreshOnce(): Promise<Response> {
  if (inFlightRefresh) return inFlightRefresh
  inFlightRefresh = fetch('/api/v1/auth/refresh', {
    method: 'POST',
    credentials: 'include',
  }).finally(() => {
    queueMicrotask(() => {
      inFlightRefresh = null
    })
  })
  return inFlightRefresh
}
```

**Adapt for D-07:** module-scoped `let redirecting = false`. On first `ApiError` with `code === 'session_expired'`, set `redirecting = true`, call `queryClient.clear()`, then `router.navigate({to:'/login', search:{next: encodeURIComponent(router.state.location.href)}, replace: true})`, and reset the flag in `.finally()`. Discriminate on `error instanceof ApiError && error.code === 'session_expired'` — all other codes pass-through (D-A3).

**Critical:** `ApiError` import comes from `@sportzal/api-client` (`packages/api-client/src/errors.ts:16-26`):

```typescript
export class ApiError extends Error {
  constructor(
    public readonly code: string,
    message: string,
    public readonly fields?: Record<string, unknown>,
    options?: { cause?: unknown },
  ) {
    super(message, options)
    this.name = 'ApiError'
  }
}
```

---

### `apps/admin-web/src/shared/api/services/http/auth.ts` (NEW — http transport)

**Analog:** `packages/api-client/src/fetcher.ts` (consumer reference) + `apps/admin-web/src/shared/api/services/http/index.ts` doc-block.

**Imports pattern** (research-only — Phase 9 D-10 public surface):

```typescript
import { request, ApiError } from '@sportzal/api-client'
import type { paths } from '@sportzal/api-client'
import type { AuthService } from '@/shared/api/contracts/auth'
```

**Service shape — wraps `request<P,M>`** (per Phase 9 D-10 — no convenience wrappers, only `request`):

```typescript
export const auth: AuthService = {
  async login(input) {
    const { user } = await request<paths, 'post'>('post', '/api/v1/auth/login', {
      body: input,
    })
    return user
  },
  async me() {
    return await request<paths, 'get'>('get', '/api/v1/auth/me')
  },
  async logout() {
    await request<paths, 'post'>('post', '/api/v1/auth/logout')
  },
  // telegramStart, telegramStatus, telegramVerify follow same shape
}
```

**Doc-block convention** (mirror `apps/admin-web/src/shared/api/services/http/index.ts:1-12`):

```typescript
/**
 * HTTP service implementations (real-API).
 *
 * Rules:
 * - Must implement the same `Contracts` as `mock/`.
 * - No UI imports, no React — pure transport layer.
 * - Error mapping (HTTP → ApiError) lives in @sportzal/api-client; this layer
 *   re-throws ApiError unchanged. Callers discriminate on `error.code`.
 */
```

---

### `apps/admin-web/src/shared/api/services/http/clients.ts` (NEW — http CRUD transport)

**Analog:** sibling `http/auth.ts` (pattern above).

Same `import { request, ApiError } from '@sportzal/api-client'` shape. Operations: `list({q, page, pageSize})` → GET `/api/v1/clients`, `create(input)` → POST, `update(id, input)` → PATCH, `remove(id)` → DELETE. All return shapes per Phase 8 contract: `{items, total, page, pageSize}` for list, `Client` domain type for single, `void` for delete.

---

### `apps/admin-web/src/shared/api/services/mock/auth.ts` (NEW — full mock impl)

**Analog:** none in repo (mock containers are empty stubs). Pattern is research-only per `apps/admin-web/src/shared/api/services/mock/index.ts:1-12` rules:

```typescript
/**
 * Mock service implementations (Faker-backed, in-memory DB, localStorage-persisted).
 *
 * Rules:
 * - Simulate latency (120–300ms) and a configurable failure rate.
 * - Enforce role access (reject with DomainError when `can(role, ...)` is false).
 * - Validate inputs with the same Zod schema the UI form uses.
 */
```

**RBAC enforcement excerpt** (canonical signature from `apps/admin-web/src/shared/session/can.ts:24-28`):

```typescript
export function can(role: Role, action: Action, resource: Resource): boolean {
  if (role === 'owner') return true
  return !OWNER_ONLY.some((entry) => entry.action === action && entry.resource === resource)
}
```

**Mock-mode "current user" reads from `useSessionStore`** (per D-12):

```typescript
import { useSessionStore } from '@/shared/session/store'

const currentRole = useSessionStore.getState().role  // re-evaluated per call
```

**`DomainError` shape** (per CLAUDE.md "Errors" + D-12): `{code: 'forbidden' | 'invalid_credentials' | 'not_found' | 'validation_failed', message: string, fields?: Record<string, string[]>}`.

---

### `apps/admin-web/src/shared/api/services/mock/clients.ts` (NEW — full mock CRUD)

**Analog:** none in repo — research-only.

**Conventions to enforce** (per CLAUDE.md + D-12):
- `faker.seed(42)` once at module load, generate ~30 clients.
- localStorage key: `sportzal:mock:v1` (versioned — CLAUDE.md "Mock realism").
- Latency: random 120-300ms via `setTimeout` Promise wrapper.
- ILIKE search: `String.prototype.includes()` on lowercased `fullName + phone`.
- Pagination: always return `{items, total, page, pageSize}` — never bare arrays (CLAUDE.md "Pagination").
- RBAC: gate `delete` with `if (!can(currentRole, 'delete', 'clients')) throw new DomainError({code: 'forbidden'})`.

---

### `apps/admin-web/src/shared/ui/app-shell/ProfileMenu.tsx` (UPDATE — enable Logout)

**Analog:** self (lines 1-40).

**Current shape** (`apps/admin-web/src/shared/ui/app-shell/ProfileMenu.tsx:1-40`):

```typescript
import { useSessionStore } from '@/shared/session/store'
import { Avatar, AvatarFallback } from '@/shared/ui/avatar'
import { Button } from '@/shared/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/shared/ui/dropdown-menu'
import { t } from '@/shared/i18n'

export function ProfileMenu() {
  const role = useSessionStore((s) => s.role)
  const initials = role === 'owner' ? 'ВЛ' : 'РЦ'
  const label = role === 'owner' ? t('shell.roleSwitch.owner') : t('shell.roleSwitch.reception')

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" size="icon" className="rounded-full" aria-label={t('shell.profile.label')}>
          <Avatar className="size-8">
            <AvatarFallback>{initials}</AvatarFallback>
          </Avatar>
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-56">
        <DropdownMenuLabel>...</DropdownMenuLabel>
        <DropdownMenuSeparator />
        <DropdownMenuItem disabled>{t('shell.profile.logout')}</DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
```

**Phase 10 change (D-08):** line 36 `<DropdownMenuItem disabled>` → remove `disabled`, add `onSelect` handler that calls `await services.auth.logout()`, then `queryClient.clear()`, then `router.navigate({to:'/login', replace: true})`. Add `LogOut` icon from `lucide-react` per UI-SPEC. Existing `t('shell.profile.logout')` key already maps to `'Выйти'` in `apps/admin-web/src/shared/i18n/ru.ts:29`. Pull `services` from `@/shared/api/services` (swap seam — never `./mock` or `./http` directly per ESLint rule).

---

### `apps/admin-web/src/shared/ui/app-shell/RoleSwitcher.tsx` (UPDATE — API_MODE guard)

**Analog:** self (lines 20-48).

**Phase 10 change (D-12):** add early-return guard at the top of `RoleSwitcher()`:

```typescript
import { API_MODE } from '@/shared/api/services'  // swap seam re-exports API_MODE per services/index.ts:20

export function RoleSwitcher() {
  if (API_MODE !== 'mock') return null
  // ...existing body
}
```

Note: `apps/admin-web/src/shared/api/services/index.ts:20` already does `export { API_MODE }`, so the import path is correct and stays inside the swap-seam contract (no direct `@/shared/api/config/env` access from a `shared/ui/**` file — would otherwise trip the `VITE_API_MODE` chokepoint).

---

### `apps/admin-web/src/shared/ui/splash.tsx` (NEW — centered logo + spinner)

**Analog:** `apps/admin-web/src/shared/ui/skeleton.tsx` (small leaf shadcn-style component, no logic).

**Pattern (research-only since splash is novel):** `function Splash() { return <div className="bg-background fixed inset-0 flex flex-col items-center justify-center gap-12">...<Loader2 className="text-muted-foreground size-6 animate-spin" />...</div> }`. Use semantic shadcn tokens only (`bg-background`, `text-muted-foreground`) — raw palette banned (`eslint.config.js:8-9, 71-83`).

UI-SPEC § "Splash Screen" specifies: 28px display weight 600 logo, `Loader2` Lucide icon with `animate-spin`, no artificial minimum delay.

---

### `apps/admin-web/eslint.config.js` (UPDATE — add `fetch(` ban for FE-07)

**Analog:** self — mirror the existing `VITE_API_MODE` block (`apps/admin-web/eslint.config.js:87-102`).

**Existing chokepoint pattern to mirror exactly** (`apps/admin-web/eslint.config.js:87-102`):

```javascript
{
  // VITE_API_MODE access only allowed inside src/shared/api/**
  files: ['src/**/*.{ts,tsx}'],
  ignores: ['src/shared/api/**'],
  rules: {
    'no-restricted-syntax': [
      'error',
      {
        selector:
          "MemberExpression[property.name='VITE_API_MODE']",
        message:
          'Read VITE_API_MODE only via @/shared/api/config/env (single chokepoint).',
      },
    ],
  },
},
```

**Phase 10 FE-07 addition** — new block with:
- `files: ['src/**/*.{ts,tsx}']`
- `ignores: ['src/shared/api/services/http/**']` (allowed transport-impl path)
- selector: `"CallExpression[callee.name='fetch']"`
- message: `'Use @sportzal/api-client.request<P,M> instead of raw fetch(). Direct fetch is allowed only inside src/shared/api/services/http/**.'`

Note: `packages/api-client/src/fetcher.ts` is outside `apps/admin-web/eslint.config.js` jurisdiction (separate package, different lint config) — no exemption needed there. The existing test-file relaxation block (`apps/admin-web/eslint.config.js:103-108`) already turns `no-restricted-syntax` off for tests, so test files won't trip the new rule either.

---

### `apps/admin-web/src/__fixtures/raw-fetch-leak.ts` (NEW — negative-test fixture)

**Analog:** `apps/admin-web/src/__fixtures/api-mode-leak.ts` (exact match — same role, same flow).

**Pattern to copy verbatim with one substitution** (`apps/admin-web/src/__fixtures/api-mode-leak.ts:1-4`):

```typescript
// FIXTURE: must trigger the VITE_API_MODE chokepoint rule —
// VITE_API_MODE may only be read inside src/shared/api/**.
// Run via scripts/assert-eslint-fixtures.mjs.
export const leaked = import.meta.env.VITE_API_MODE
```

**Adapt for FE-07:**

```typescript
// FIXTURE: must trigger the no-raw-fetch rule —
// fetch() may only be called inside src/shared/api/services/http/**.
// Run via scripts/assert-eslint-fixtures.mjs.
export const leaked = fetch('/api/v1/clients')
```

**Companion update — `apps/admin-web/scripts/assert-eslint-fixtures.mjs`** (`scripts/assert-eslint-fixtures.mjs:18-23`): add a fourth entry to the `EXPECTED` array:

```javascript
const EXPECTED = [
  { file: 'src/__fixtures/raw-palette.tsx', rule: 'no-restricted-syntax' },
  { file: 'src/__fixtures/features/illegal-mock-import.ts', rule: 'import/no-restricted-paths' },
  { file: 'src/__fixtures/api-mode-leak.ts', rule: 'no-restricted-syntax' },
  { file: 'src/__fixtures/raw-fetch-leak.ts', rule: 'no-restricted-syntax' },  // NEW
]
```

---

### `apps/admin-web/src/shared/i18n/ru.ts` (UPDATE — extend dictionary)

**Analog:** self (lines 1-40).

**Existing dict shape** (`apps/admin-web/src/shared/i18n/ru.ts:1-40`):

```typescript
export const ru = {
  shell: {
    appName: 'SportZal',
    roleSwitch: { label: 'Роль', owner: 'Владелец', reception: 'Ресепшн' },
    nav: { home: 'Главная', clients: 'Клиенты', /* ... */ },
    profile: { label: 'Профиль', logout: 'Выйти', demoMode: 'Демо-режим' },
    forbidden: 'Доступ запрещён',
  },
  common: { loading: 'Загрузка…', empty: 'Пусто', error: 'Ошибка', retry: 'Повторить' },
} as const
```

**Phase 10 additions** (per UI-SPEC "Copywriting Contract"): add top-level `auth` and `clients` blocks (do NOT nest under `shell` — those are AppShell-specific). The auto-derived `TranslationKey` Paths<Dict> type (lines 44-50) means new keys are type-checked automatically — no manual type maintenance.

Suggested shape:
```typescript
auth: {
  login: { heading: 'Войти в систему', emailTab: 'Email / Пароль', /* ... */ },
  errors: { invalidCredentials: 'Неверный email или пароль.', /* ... */ },
  splash: 'Загрузка...',
},
clients: {
  heading: 'Клиенты',
  search: { placeholder: 'Поиск по имени или телефону...' },
  actions: { create: 'Новый клиент', edit: 'Редактировать клиента', delete: 'Удалить клиента' },
  empty: { heading: 'Клиентов пока нет', body: 'Добавьте первого клиента, нажав «Новый клиент».' },
  /* ... per UI-SPEC Copywriting Contract */
},
```

---

### `apps/admin-web/src/entities/client/types.ts` (NEW — branded ID + domain type)

**Analog:** `apps/admin-web/src/shared/session/types.ts` (small types module shape).

**Pattern to mirror** (`apps/admin-web/src/shared/session/types.ts:1-7`):

```typescript
export type Role = 'owner' | 'reception'

export interface SessionState {
  role: Role
  setRole: (role: Role) => void
}
```

**Phase 10 adaptation** — branded UUIDv4 ID per CLAUDE.md "IDs":

```typescript
declare const __brand: unique symbol
type Brand<T, B> = T & { readonly [__brand]: B }

export type ClientId = Brand<string, 'ClientId'>

export interface Client {
  id: ClientId
  fullName: string
  phone: string
  email?: string
  birthDate?: string  // ISO date string per CLAUDE.md "Dates"
  notes?: string
  createdAt: string  // ISO
  deletedAt?: string  // soft-delete per Phase 8 backend
}
```

(The exact `Brand<T, B>` helper may live in `apps/admin-web/src/shared/lib/brand.ts` — Claude's discretion per CONTEXT.md.)

---

### `apps/admin-web/src/features/auth/api/keys.ts` (NEW — authKeys factory)

**Analog:** none in repo. Research-only (TkDodo "Effective React Query Keys" per CONTEXT.md).

**Canonical TkDodo shape** (research):

```typescript
export const authKeys = {
  all: ['auth'] as const,
  me: () => [...authKeys.all, 'me'] as const,
  telegramStatus: (token: string) => [...authKeys.all, 'telegram-status', token] as const,
} as const
```

---

### `apps/admin-web/src/features/clients/api/keys.ts` (NEW — clientsKeys factory)

**Analog:** none in repo. Research-only (TkDodo).

**Canonical TkDodo shape** (per CONTEXT.md "Claude's Discretion"):

```typescript
export const clientsKeys = {
  all: ['clients'] as const,
  lists: () => [...clientsKeys.all, 'list'] as const,
  list: (filter: { q?: string; page: number; pageSize: number }) => [...clientsKeys.lists(), filter] as const,
  details: () => [...clientsKeys.all, 'detail'] as const,
  detail: (id: ClientId) => [...clientsKeys.details(), id] as const,
} as const
```

---

### Components — common shadcn primitive usage pattern

**Analog (shape):** `apps/admin-web/src/shared/ui/button.tsx` (current shadcn shape; will be REPLACED by ReUI per D-16, but shape stays — `cva` + variants + `data-slot` + `cn()`).

**Imports excerpt** (`apps/admin-web/src/shared/ui/button.tsx:1-5`):

```typescript
import * as React from "react"
import { cva, type VariantProps } from "class-variance-authority"
import { Slot } from "radix-ui"

import { cn } from "@/shared/lib/cn"
```

**`data-slot` attribute convention** (`button.tsx:54-58`, `dropdown-menu.tsx:8-19`): every primitive sets `data-slot="<name>"` — preserved by ReUI per D-13. Components consuming primitives (e.g. `ProfileMenu.tsx`) do NOT need to set this themselves; only the primitive author does.

**`cn()` helper** (`apps/admin-web/src/shared/lib/cn.ts:1-4`) — used everywhere class composition is needed:

```typescript
import { clsx, type ClassValue } from 'clsx'
import { twMerge } from 'tailwind-merge'

export const cn = (...inputs: ClassValue[]): string => twMerge(clsx(inputs))
```

---

## Shared Patterns

### Authorization (RBAC)

**Source:** `apps/admin-web/src/shared/session/can.ts` (function) + `apps/admin-web/src/shared/session/RoleGate.tsx` (declarative wrapper).

**Apply to:** All route `beforeLoad` guards, all action-gated UI elements (delete buttons, owner-only views), all mock service entry points.

**Excerpt — `can()` function** (`apps/admin-web/src/shared/session/can.ts:24-28`):

```typescript
export function can(role: Role, action: Action, resource: Resource): boolean {
  if (role === 'owner') return true
  return !OWNER_ONLY.some((entry) => entry.action === action && entry.resource === resource)
}
```

**Excerpt — `OWNER_ONLY` matrix** (`apps/admin-web/src/shared/session/can.ts:12-22`) — `{action: 'delete', resource: 'clients'}` is already in the list (line 20), so reception is auto-blocked from delete-clients with no Phase 10 changes to `can.ts`.

**Excerpt — `RoleGate` declarative wrapper** (`apps/admin-web/src/shared/session/RoleGate.tsx:14-17`):

```typescript
export function RoleGate({ action, resource, fallback = null, children }: RoleGateProps) {
  const role = useSessionStore((s) => s.role)
  return <>{can(role, action, resource) ? children : fallback}</>
}
```

**Phase 10 caveat (D-05):** in http-mode `useSessionStore` is no longer the source of truth. Either update `RoleGate` to read role from `getSession()` adapter (which forks per `API_MODE`), OR keep `RoleGate` as-is and ensure http-mode populates `useSessionStore.role` from `authKeys.me` cache as a side effect. **Planner decides.** Recommended: update `RoleGate` to call `getSession()` (single source) since the adapter already exists in `router.ts`.

---

### Route guard pattern (RBAC redirect)

**Source:** `apps/admin-web/src/routes/clients.tsx:5-13`, `apps/admin-web/src/routes/settings.tsx:5-13`, `apps/admin-web/src/routes/schedule.tsx:5-12`.

**Apply to:** Every protected route (i.e. children of `_protected` layout — D-01).

**Excerpt** (`apps/admin-web/src/routes/clients.tsx:5-13`):

```typescript
export const Route = createFileRoute('/clients')({
  beforeLoad: ({ context, location }) => {
    const { role } = context.getSession()
    if (!can(role, 'view', 'clients')) {
      throw redirect({ to: '/', search: { forbidden: location.href } })
    }
  },
  component: ClientsPage,
})
```

This pattern is already in use across `clients`, `settings`, `schedule`, `staff`, `finance`. Phase 10 keeps it; `_protected.tsx` layout-route can hoist the `getSession + can(...)` into one place (research recommends `_protected.tsx` does the AppShell render + a generic auth check; per-resource RBAC stays on the leaf route).

---

### Error handling (DomainError vs ApiError)

**Source — `ApiError`:** `packages/api-client/src/errors.ts:16-26` (above).

**Source — `DomainError`:** does not currently exist as a class in repo (mock containers are empty stubs). Phase 10 introduces it. Mirror `ApiError` shape exactly (CONTEXT.md "Code Insights — DomainError vs ApiError"):

```typescript
// suggested location: apps/admin-web/src/shared/api/errors.ts (NEW, Claude's discretion)
export class DomainError extends Error {
  constructor(
    public readonly code: string,
    message: string,
    public readonly fields?: Record<string, unknown>,
  ) {
    super(message)
    this.name = 'DomainError'
  }
}
```

**Apply to:** All mock service throws + all UI error rendering. UI must accept both `ApiError` (http-mode) and `DomainError` (mock-mode). Discriminate on `.code`.

**Inline alert UI pattern** (`apps/admin-web/src/routes/index.tsx:19-26`) — reuse for form errors:

```tsx
<div role="alert" className="border-destructive/50 bg-destructive/10 text-destructive rounded-md border p-3 text-sm">
  {message}
</div>
```

---

### Forms (react-hook-form + Zod)

**Source:** none in current repo (no form components yet). Pattern is research-only per CLAUDE.md "Forms":

> react-hook-form + the same Zod schema the service validates with.

**Apply to:** `EmailLoginForm.tsx`, `ClientForm.tsx`. Schema lives in `features/<domain>/model/schema.ts` and is imported by both the form (`zodResolver`) and the mock service (`schema.parse(input)` before mutating mock DB).

---

### Optimistic mutations

**Source:** none in current repo. Pattern is research-only per CLAUDE.md "Query hygiene":

> optimistic mutations with `onMutate`/`onError`/`onSettled`, route `loader` uses `queryClient.ensureQueryData` with the same key as the hook.

**Apply to:** `useCreateClient`, `useUpdateClient`, `useDeleteClient` in `features/clients/api/hooks.ts`. Pattern:
- `onMutate` → `queryClient.cancelQueries({queryKey: clientsKeys.lists()})`, snapshot `queryClient.getQueryData(...)`, optimistically update via `setQueryData`, return `{previous}` ctx.
- `onError(err, vars, ctx)` → restore `setQueryData(key, ctx.previous)`.
- `onSettled` → `queryClient.invalidateQueries({queryKey: clientsKeys.lists()})`.

---

### Layered import boundary (already enforced)

**Source:** `apps/admin-web/eslint.config.js:48-69` (`import/no-restricted-paths`).

**Apply to:** All Phase 10 features. Components must import via `@/shared/api/services` (the swap seam exporting `services` and `API_MODE`), never `@/shared/api/services/mock` or `@/shared/api/services/http`. Reading `import.meta.env.VITE_API_MODE` outside `src/shared/api/**` is also banned.

**Existing zone definition** (`eslint.config.js:48-69`):

```javascript
'import/no-restricted-paths': [
  'error',
  {
    zones: [
      {
        target: ['./src/features/**', './src/routes/**', './src/entities/**', './src/shared/ui/**', './src/app/**'],
        from: ['./src/shared/api/services/mock/**', './src/shared/api/services/http/**'],
        message: 'Go through services container or a TanStack Query hook (do not import mock/http impls directly).',
      },
    ],
  },
],
```

---

### Test conventions

**Source:** `apps/admin-web/src/test/utils.tsx:30-39`, `apps/admin-web/src/test/setup.ts:36-44`, `apps/admin-web/src/shared/session/can.test.ts:1-36` (sentence-style `it()` names; `describe` per concern).

**Excerpt — `renderWithProviders` entry point** (`apps/admin-web/src/test/utils.tsx:30-39`):

```typescript
export function renderWithProviders(ui: ReactElement, opts: RenderOptions = {}) {
  if (opts.role) {
    useSessionStore.setState({ role: opts.role })
  }
  const client = makeTestQueryClient()
  return {
    client,
    ...render(<Providers client={client}>{ui}</Providers>),
  }
}
```

**Apply to:** All Phase 10 component tests. Tests live next to source as `*.test.ts(x)` siblings (CLAUDE.md "Testing Conventions").

---

## No Analog Found

Files with no close internal match — planner should rely on RESEARCH.md and external library docs:

| File | Role | Data Flow | Reason |
|---|---|---|---|
| `apps/admin-web/src/features/auth/components/EmailLoginForm.tsx` | feature / RHF form | request-response | Repo has zero RHF+Zod usage today (Phase 10 introduces forms) |
| `apps/admin-web/src/features/auth/components/TelegramLoginTab.tsx` | feature / polling component | event-driven | Repo has zero TanStack Query polling (`refetchInterval`) usage today |
| `apps/admin-web/src/features/clients/components/ClientsTable.tsx` | feature / DataGrid wrapper | CRUD list | DataGrid (ReUI) install is novel; @tanstack/react-table also unused today |
| `apps/admin-web/src/features/clients/api/hooks.ts` (optimistic mutations) | feature / mutation hooks | CRUD | Repo has zero TanStack Query usage today; pattern is research-only |
| `apps/admin-web/src/shared/api/services/mock/clients.ts` (full mock CRUD) | service / mock | CRUD | All mock containers are empty stubs in current repo |
| `apps/admin-web/src/shared/ui/data-grid.tsx` | shared-ui / primitive | CRUD list | ReUI install — generated, not authored |
| `apps/admin-web/src/shared/ui/input-otp.tsx` | shared-ui / primitive | request-response | ReUI install — generated, not authored |

For these, planner references RESEARCH.md sections (TanStack Router pathless layouts, TanStack Query optimistic mutations, ReUI DataGrid props), and Phase 10 CLAUDE.md conventions (faker.seed=42, 120-300ms latency, RBAC enforcement, branded IDs, pagination shape).

---

## Metadata

**Analog search scope:**
- `apps/admin-web/src/{app,routes,shared,__fixtures,test}/**`
- `apps/admin-web/{eslint.config.js,components.json,scripts}`
- `packages/api-client/src/**`

**Files scanned:** ~60 source files in `apps/admin-web/src/` + 4 files in `packages/api-client/src/` + lint config + scripts.

**Pattern extraction date:** 2026-05-03

**Notes for the planner:**
- The swap-seam contract (`apps/admin-web/src/shared/api/services/index.ts:14-20`) is locked — Phase 10 must populate `./mock` and `./http` containers, never modify `index.ts` itself beyond what the existing `session-swap.test.ts` tolerates (the test asserts the exact branching shape).
- `RoleGate` currently reads `useSessionStore` directly (`RoleGate.tsx:15`). In http-mode this read becomes stale (D-05). Resolving this is a planner decision and crosses several files (`RoleGate.tsx` + `router.ts:getSession()` + maybe a `useCurrentRole()` hook). Recommend a single `useCurrentRole()` hook that internally branches on `API_MODE` — would require updating `RoleGate.tsx` only.
- ReUI primitives (D-16) overwrite existing files at `apps/admin-web/src/shared/ui/{button,input,form,label,dropdown-menu,dialog,alert-dialog}.tsx`. Existing consumers (`ProfileMenu`, `RoleSwitcher`, `Header`, etc.) import from `@/shared/ui/<name>` — those import paths stay stable. The consumers' code does not need to change unless the ReUI variant API differs from the current shadcn variant API; planner should diff post-install.
- `eslint.config.js:104-108` already turns `no-restricted-syntax` off for tests, so the new fetch-ban rule is automatically test-safe.
- The fixture-assertion script `apps/admin-web/scripts/assert-eslint-fixtures.mjs` is wired to `pnpm lint:fixtures` (per its top doc-block) — Phase 10 must add the new fixture entry to the `EXPECTED` array (line 19) for the guard-rail to be enforced.
