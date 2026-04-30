# Architecture: SportZal Adminka

**Domain:** Gym CRM admin panel (frontend-only, mock-first, API-later)
**Researched:** 2026-04-21
**Overall confidence:** HIGH

## 0. Executive Summary

SportZal Adminka is a React admin panel that must feel and behave like a real product
while running entirely on mock data, and must survive the eventual swap to a real HTTP
API as a localized change (new service implementation, nothing else). The architecture
below is designed around one load-bearing idea:

> **The UI must never know whether data came from memory, localStorage, or HTTP.**

Every other decision flows from that. We achieve it by layering:

```
  UI (React components, shadcn/ui, reui.io)
        │  uses only hooks
        ▼
  Query hooks (TanStack Query v5) — useClients(), useCreateClient(), ...
        │  call service methods by interface
        ▼
  Service interfaces (ClientsService, ScheduleService, ...)
        │  injected via a single services module
        ▼
  ┌──────────────────────┬───────────────────────┐
  │  MockServices        │  HttpServices         │
  │  in-memory + seeded  │  axios/fetch against  │
  │  faker, localStorage │  real backend (later) │
  └──────────────────────┴───────────────────────┘
```

**Stack at a glance:**

- React 19 + Vite + TypeScript (strict)
- TanStack Query v5 as the only data-access surface in UI
- TanStack Router (file-based, type-safe params and search)
- Zustand for client-only state (session/role, UI prefs)
- React Hook Form + Zod (schemas shared between UI and mock "backend")
- shadcn/ui + reui.io, themed via CSS variables and a `next-themes`-style toggle
- `@faker-js/faker` with a fixed seed for deterministic mock data
- MSW is **not** used in v1; direct service-layer mocks are simpler for our swap story
  (see §3.3). MSW remains the fallback if we ever need to mock at the network boundary
  (e.g. for Storybook or e2e).

**Target feel:** every list paginates, every create/edit hits a loading state and a
toast, every detail page can be deep-linked, every mutation updates the list without a
full refetch. When the real backend shows up, only `src/shared/api/services/http/*`
changes.

---

## 1. Data Layer Contract Pattern

### 1.1 Domain model as single source of truth

All domain entities live in `src/entities/*/model/types.ts` and are the only shape the
UI ever sees. They model **business reality**, not backend response shapes.

```ts
// src/entities/client/model/types.ts
export type ClientId = string & { readonly __brand: 'ClientId' }

export type MembershipStatus = 'active' | 'frozen' | 'expired' | 'pending'

export interface Client {
  id: ClientId
  firstName: string
  lastName: string
  phone: string
  email?: string
  birthday?: string          // ISO date, no time
  joinedAt: string           // ISO datetime
  activeMembershipId?: MembershipId
  note?: string
}

export interface Membership {
  id: MembershipId
  clientId: ClientId
  planId: PlanId
  status: MembershipStatus
  startsAt: string
  endsAt: string
  visitsUsed: number
  visitsTotal: number | null // null = unlimited
}
```

**Rules:**

- Domain types use **branded IDs** (`string & { __brand }`) so `ClientId` can't be
  accidentally passed where `MembershipId` is expected.
- ISO strings, not `Date` — `Date` pollutes serialization; convert at the edge.
- No backend-only fields (e.g. `_id`, `__v`, `created_at` snake_case). Mappers live
  in the HTTP impl (§11).
- No mock-only fields (e.g. `__mockSeed`). Ever.

### 1.2 Service interfaces

One interface per feature domain. The interface is the contract; implementations come
and go.

```ts
// src/shared/api/contracts/clients.ts
export interface ListParams {
  query?: string
  page?: number
  pageSize?: number
  status?: MembershipStatus
  sort?: 'name' | 'recent'
}

export interface Paginated<T> {
  items: T[]
  total: number
  page: number
  pageSize: number
}

export interface ClientsService {
  list(params: ListParams): Promise<Paginated<Client>>
  getById(id: ClientId): Promise<Client>
  create(input: CreateClientInput): Promise<Client>
  update(id: ClientId, patch: UpdateClientInput): Promise<Client>
  remove(id: ClientId): Promise<void>
}
```

Same pattern for `MembershipsService`, `ScheduleService`, `TrainersService`,
`PaymentsService`, `NotificationsService`, `DashboardService`.

### 1.3 The swap seam

One module decides which implementation is live. This is the only place that knows
about `mock` vs `http`.

```ts
// src/shared/api/services/index.ts
import type { ClientsService, ScheduleService, /* ... */ } from '../contracts'
import * as mock from './mock'
import * as http from './http' // stubs until backend lands

const mode = import.meta.env.VITE_API_MODE ?? 'mock' // 'mock' | 'http'

const impl = mode === 'http' ? http : mock

export const services = {
  clients:       impl.clientsService       as ClientsService,
  memberships:   impl.membershipsService   as MembershipsService,
  schedule:      impl.scheduleService      as ScheduleService,
  trainers:      impl.trainersService      as TrainersService,
  payments:      impl.paymentsService      as PaymentsService,
  notifications: impl.notificationsService as NotificationsService,
  dashboard:     impl.dashboardService     as DashboardService,
}
```

Why a plain object container rather than a DI framework (InversifyJS, tsyringe):

- Zero runtime cost, zero decorators, zero TS config gymnastics.
- Tree-shakable per implementation.
- Testing is a one-line override: `vi.mock('@/shared/api/services', ...)`.

### 1.4 Errors as domain shapes

```ts
// src/shared/api/contracts/errors.ts
export class DomainError extends Error {
  constructor(
    public code: 'NOT_FOUND' | 'VALIDATION' | 'CONFLICT' | 'UNKNOWN',
    message: string,
    public fields?: Record<string, string>,
  ) { super(message) }
}
```

Mock services **throw the same shape** HTTP services will throw. UI renders errors by
`code`, never by checking for "is this a mock?".

---

## 2. TanStack Query as the Only Data-Access Surface

**Rule:** React components never import from `src/shared/api/services`. They import
hooks. This is enforced by ESLint (`no-restricted-imports` banning `services` outside
`hooks` folders).

### 2.1 Query keys, typed and centralized

Per-feature key factory. Prevents typos and keeps invalidation surgical.

```ts
// src/features/clients/api/keys.ts
export const clientsKeys = {
  all:   ['clients'] as const,
  lists: () => [...clientsKeys.all, 'list'] as const,
  list:  (p: ListParams) => [...clientsKeys.lists(), p] as const,
  details: () => [...clientsKeys.all, 'detail'] as const,
  detail:  (id: ClientId) => [...clientsKeys.details(), id] as const,
}
```

### 2.2 Query hooks

```ts
// src/features/clients/api/useClients.ts
import { useQuery } from '@tanstack/react-query'
import { services } from '@/shared/api/services'
import { clientsKeys } from './keys'

export function useClients(params: ListParams = {}) {
  return useQuery({
    queryKey: clientsKeys.list(params),
    queryFn: () => services.clients.list(params),
    placeholderData: (prev) => prev, // keepPreviousData behavior in v5
    staleTime: 30_000,
  })
}

export function useClient(id: ClientId | undefined) {
  return useQuery({
    queryKey: id ? clientsKeys.detail(id) : ['clients', 'detail', 'none'],
    queryFn: () => services.clients.getById(id!),
    enabled: !!id,
  })
}
```

### 2.3 Mutation hooks with optimistic updates

Verified against TanStack Query v5 docs (Context7). The mock service returns Promises
with simulated latency (§3.4), so the same hook works identically against HTTP.

```ts
// src/features/clients/api/useCreateClient.ts
import { useMutation, useQueryClient } from '@tanstack/react-query'

export function useCreateClient() {
  const qc = useQueryClient()

  return useMutation({
    mutationFn: (input: CreateClientInput) => services.clients.create(input),

    onMutate: async (input) => {
      await qc.cancelQueries({ queryKey: clientsKeys.lists() })
      const previous = qc.getQueriesData<Paginated<Client>>({ queryKey: clientsKeys.lists() })
      const optimistic: Client = { ...input, id: tempId(), joinedAt: new Date().toISOString() }
      qc.setQueriesData<Paginated<Client>>(
        { queryKey: clientsKeys.lists() },
        (old) => old ? { ...old, items: [optimistic, ...old.items], total: old.total + 1 } : old,
      )
      return { previous, optimisticId: optimistic.id }
    },

    onError: (_err, _input, ctx) => {
      ctx?.previous.forEach(([key, data]) => qc.setQueryData(key, data))
    },

    onSettled: () => {
      qc.invalidateQueries({ queryKey: clientsKeys.lists() })
    },
  })
}
```

### 2.4 QueryClient defaults

```ts
// src/app/query-client.ts
export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      gcTime: 5 * 60_000,
      retry: (failureCount, err) =>
        err instanceof DomainError && err.code === 'VALIDATION' ? false : failureCount < 2,
      refetchOnWindowFocus: false, // admin panels: usually undesirable
    },
    mutations: {
      retry: false,
    },
  },
})
```

---

## 3. Mock Data Strategy

### 3.1 Deterministic seeded faker

```ts
// src/shared/api/services/mock/seed.ts
import { faker } from '@faker-js/faker/locale/ru'
faker.seed(42) // stable data every reload for the first boot
```

**Why faker over static JSON:**

- Realistic distributions (names, phones, addresses in ru-locale).
- Generates 2–3 months of schedule rows mechanically.
- Stable because of the fixed seed — reviews see the same data.

### 3.2 In-memory stores + localStorage persistence

```
src/shared/api/services/mock/
├── db/
│   ├── clients.store.ts      // { byId: Map<ClientId, Client>, ids: ClientId[] }
│   ├── memberships.store.ts
│   ├── schedule.store.ts
│   ├── payments.store.ts
│   ├── trainers.store.ts
│   └── index.ts              // createDb(), hydrate/persist via localStorage
├── seed.ts                   // populates empty stores on first boot
├── latency.ts                // sleep(150 + jitter) + rare 500 errors (toggleable)
├── clients.service.ts        // implements ClientsService
├── memberships.service.ts
├── ...
└── index.ts                  // exports *Service singletons
```

**Persistence policy:**

- Default: hydrate from `localStorage['sportzal:mock:v1']` on boot. If missing, seed
  from faker and persist.
- **Versioned key** (`:v1`) so bumping the schema invalidates stale mock state.
- Topbar has a hidden "Reset mock data" action (gated by dev build or Ctrl-Shift-R).
- IndexedDB is overkill for ~100 clients + ~300 sessions. localStorage is <5 MB and
  synchronous, which is actually easier for a mock layer.

**Write path goes through the store, not around it:**

```ts
// src/shared/api/services/mock/clients.service.ts
export const clientsService: ClientsService = {
  async list(p) {
    await latency()
    return paginate(filter(db.clients.all(), p), p)
  },
  async create(input) {
    await latency()
    const validation = CreateClientSchema.safeParse(input)       // shared with UI (§7)
    if (!validation.success) throw zodToDomainError(validation.error)
    const client: Client = { ...input, id: newId<ClientId>(), joinedAt: new Date().toISOString() }
    db.clients.insert(client)
    persist()
    return client
  },
  // ...
}
```

### 3.3 MSW vs service-layer mocks — decision

**Recommendation: direct service-layer mocks for v1. HIGH confidence.**

| Dimension | Service-layer mocks | MSW |
|---|---|---|
| Swap to real API | Change one import in `services/index.ts` | Keep axios code working, just disable worker |
| Build/run complexity | None; pure TS | Needs `public/mockServiceWorker.js`, Vite plugin, setup hooks |
| Realism (network tab, status codes) | Low — just rejected promises | High — real fetch, headers, status codes |
| Type-safety at the service boundary | Strong — impls conform to `ClientsService` | Typed per-handler, but request/response shape drift is possible |
| Testing | Same interface in unit tests | Same worker runs in browser + Vitest (nice bonus) |
| "Mock feels real for demos" | Fine with good latency sim | Marginally nicer |

**Tradeoff:** MSW's biggest win (same network-level mock for tests + dev + Storybook)
is what we don't need in v1 — we're not shipping e2e and we don't have real HTTP
endpoints to shadow. The service-layer approach makes the swap story **trivially
local**: implementing `HttpClientsService` doesn't require rewriting handlers; it just
fills a stub.

Leave MSW as a migration escape hatch: once we have the real backend, if we want to
write integration tests that exercise the HTTP impl without a live server, we add MSW
at that time — it doesn't invalidate today's architecture.

### 3.4 Simulated latency & failures

```ts
// src/shared/api/services/mock/latency.ts
const BASE = 120, JITTER = 180, FAIL_RATE = 0 // set to 0.05 in dev to stress UI
export async function latency() {
  await new Promise(r => setTimeout(r, BASE + Math.random() * JITTER))
  if (Math.random() < FAIL_RATE) throw new DomainError('UNKNOWN', 'Simulated outage')
}
```

Why it matters: TanStack Query's `isPending`, `isFetching`, and optimistic update
paths only light up when the promise takes measurable time. Instant mocks hide UX
bugs that will surface the day we plug in HTTP.

---

## 4. Role-Based UI

### 4.1 Session as the right abstraction

Role is stored under a **session** concept. When real auth arrives, only the session
source changes — gates and guards stay.

```ts
// src/shared/session/store.ts
import { create } from 'zustand'
import { persist } from 'zustand/middleware'

export type Role = 'owner' | 'manager'

interface SessionState {
  role: Role
  setRole: (r: Role) => void
}

export const useSession = create<SessionState>()(
  persist(
    (set) => ({ role: 'owner', setRole: (role) => set({ role }) }),
    { name: 'sportzal:session' },
  ),
)
```

Later, the real `useSession` will read from `AuthContext` (JWT, whatever) but expose
the same `{ role }` shape.

### 4.2 `<RoleGate>` component

```tsx
// src/shared/session/RoleGate.tsx
export function RoleGate({ role, fallback = null, children }: {
  role: Role | Role[]
  fallback?: ReactNode
  children: ReactNode
}) {
  const current = useSession((s) => s.role)
  const allowed = Array.isArray(role) ? role.includes(current) : role === current
  return allowed ? <>{children}</> : <>{fallback}</>
}
```

Usage:

```tsx
<RoleGate role="owner">
  <Button onClick={() => deleteClient(id)}>Удалить клиента</Button>
</RoleGate>
```

### 4.3 Route guards

Centralize in the route tree. With TanStack Router:

```tsx
// src/routes/_app/finances.tsx
export const Route = createFileRoute('/_app/finances')({
  beforeLoad: () => {
    const { role } = useSession.getState()
    if (role !== 'owner') throw redirect({ to: '/forbidden' })
  },
  component: FinancesLayout,
})
```

### 4.4 Menu filtering

The sidebar reads a static menu config annotated with roles and filters at render
time. No imperative show/hide logic sprinkled in layouts.

```ts
const menu = [
  { to: '/clients',   label: 'Клиенты',   roles: ['owner', 'manager'] },
  { to: '/schedule',  label: 'Расписание', roles: ['owner', 'manager'] },
  { to: '/finances',  label: 'Финансы',   roles: ['owner'] },
  { to: '/trainers',  label: 'Тренеры',   roles: ['owner'] },
]
```

---

## 5. Routing Structure

### 5.1 TanStack Router vs React Router 7

**Recommendation: TanStack Router. HIGH confidence for this project.**

| Concern | TanStack Router | React Router 7 |
|---|---|---|
| Type-safe params & search | Best-in-class; `validateSearch` with Zod | Typed IDs, search typing weaker |
| File-based routing | First-class, generated route tree | Opt-in via framework mode (Remix lineage) |
| Integration with TanStack Query | Native (`context: { queryClient }`, loaders call `ensureQueryData`) | Works, but no special coupling |
| Nested layouts | Via pathless `_layout` files | Via layout routes |
| SSR | Optional (Start); we don't need it | Built-in via framework mode |
| Learning curve | Higher at start, pays off on big apps | Familiar, lower |
| Bundle size | Slightly bigger | Slightly smaller |

For an admin panel with heavy search state (filters, sort, pagination in URL),
typed search params alone justify TanStack Router. The Query integration means
route loaders can prefetch into the same cache the hooks read from — no
duplicate request on page entry.

Fallback if the team prefers familiarity: React Router 7 in library (non-framework)
mode is a fine choice; none of the rest of this architecture changes.

### 5.2 Route tree shape

```
src/routes/
├── __root.tsx                 // <AppShell/>: providers, topbar, sidebar
├── index.tsx                  // → redirect to /dashboard
├── _app/                      // pathless layout, holds auth/role guard
│   ├── route.tsx
│   ├── dashboard.tsx
│   ├── clients/
│   │   ├── index.tsx          // list + filters (search params typed)
│   │   ├── new.tsx
│   │   └── $clientId.tsx      // detail with tabs
│   ├── schedule/
│   │   ├── index.tsx          // calendar
│   │   └── $sessionId.tsx
│   ├── trainers/
│   │   ├── index.tsx
│   │   └── $trainerId.tsx
│   ├── finances.tsx           // owner-only
│   └── notifications.tsx
└── forbidden.tsx
```

### 5.3 Loader-prefetch pattern

```tsx
export const Route = createFileRoute('/_app/clients/')({
  validateSearch: (s) => ClientsSearchSchema.parse(s),
  loaderDeps: ({ search }) => ({ search }),
  loader: ({ context: { queryClient }, deps: { search } }) =>
    queryClient.ensureQueryData({
      queryKey: clientsKeys.list(search),
      queryFn: () => services.clients.list(search),
    }),
  component: ClientsListPage,
})
```

The page component then calls `useClients(search)` and gets data synchronously from
the cache on first paint — no flash of loading state on direct navigation.

---

## 6. Folder Layout — Feature-First (FSD-lite)

We use a pragmatic subset of Feature-Sliced Design: the parts that help (clear
feature boundaries) without the parts that punish small teams (shared/entities/features
rigid six-layer dogma).

```
src/
├── app/                       # providers, query client, router, global styles entry
│   ├── providers.tsx
│   ├── query-client.ts
│   ├── router.tsx
│   └── index.css
├── routes/                    # TanStack Router file tree (thin: compose features)
├── features/                  # feature-first; one folder per business module
│   ├── clients/
│   │   ├── api/               # useClients, useClient, useCreateClient, keys
│   │   ├── components/        # ClientsTable, ClientForm, ClientCard
│   │   ├── model/             # feature-local schemas, selectors
│   │   └── index.ts           # public barrel
│   ├── memberships/
│   ├── schedule/
│   ├── trainers/
│   ├── payments/
│   ├── dashboard/
│   └── notifications/
├── entities/                  # domain types + pure helpers (no UI, no hooks)
│   ├── client/
│   ├── membership/
│   ├── session/
│   ├── trainer/
│   └── payment/
├── shared/
│   ├── ui/                    # shadcn/ui components (copied) + reui.io wrappers
│   ├── lib/                   # date, currency, ids, result-type helpers
│   ├── api/
│   │   ├── contracts/         # service interfaces, domain errors
│   │   └── services/
│   │       ├── index.ts       # swap point
│   │       ├── mock/
│   │       └── http/          # stubs for now
│   ├── session/               # session store, RoleGate
│   └── config/                # env, constants
└── main.tsx
```

**Rules of thumb:**

- Features may depend on `entities`, `shared`. Features may **not** import from other
  features (enforced by ESLint `import/no-restricted-paths`).
- `routes/` is thin: it wires features into the router, no business logic.
- Mocks live **centrally** in `shared/api/services/mock/` — not per feature.
  Rationale: the mock DB is cross-feature (memberships reference clients, payments
  reference memberships). Colocating mocks per feature creates a tangled import graph.

---

## 7. Forms & Validation

One Zod schema per resource, shared by UI and mock "backend".

```ts
// src/entities/client/model/schemas.ts
import { z } from 'zod'

export const CreateClientSchema = z.object({
  firstName: z.string().trim().min(1, 'Имя обязательно').max(60),
  lastName:  z.string().trim().min(1, 'Фамилия обязательна').max(60),
  phone:     z.string().regex(/^\+?[0-9\s\-()]{7,}$/, 'Некорректный телефон'),
  email:     z.string().email('Некорректный email').optional().or(z.literal('')),
  birthday:  z.string().date().optional(),
  note:      z.string().max(500).optional(),
})
export type CreateClientInput = z.infer<typeof CreateClientSchema>
```

**UI side:**

```tsx
const form = useForm<CreateClientInput>({
  resolver: zodResolver(CreateClientSchema),
  defaultValues: { firstName: '', lastName: '', phone: '' },
})
```

**Mock service side:** parses with the **same schema** and throws a `DomainError` with
the Zod `fieldErrors` mapped to `fields`. That way, the mock genuinely reproduces a
"server rejected my input" experience, and server-side errors show up in the form
identically to client-side ones.

When the real API arrives, UI validation stays; server validation is enforced by the
backend; we still ingest `fields` from the error response into `form.setError`.

---

## 8. Error, Loading, Empty States

Standardized per-route primitives in `shared/ui/states/`:

```
<PageError onRetry={...} />
<PageLoading />     // skeleton matching the page's layout
<EmptyState title icon action />
```

**Per-route error boundary:** TanStack Router's `errorComponent` catches loader errors;
component-level errors use React's `ErrorBoundary`. Both render the same `<PageError>`
with a retry that invalidates the relevant query.

**Loading:** shadcn `<Skeleton>` composed into page-shape skeletons. Tables render a
skeleton row per expected row count (from `pageSize` param) so layout doesn't jump.

**Empty:** every list returns a typed `Paginated<T>` whose `items.length === 0` case
is an `<EmptyState>` with a context-appropriate action (e.g. "Добавить клиента").

---

## 9. Theming

**Recommendation:** shadcn CSS variables + a small, in-house `ThemeProvider` that
mirrors `next-themes` semantics. No Next.js, no FOUC.

```tsx
// src/shared/theme/ThemeProvider.tsx
type Theme = 'light' | 'dark' | 'system'

const STORAGE_KEY = 'sportzal:theme'

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setTheme] = useState<Theme>(() =>
    (localStorage.getItem(STORAGE_KEY) as Theme) ?? 'system'
  )
  useEffect(() => {
    const root = document.documentElement
    const resolved = theme === 'system'
      ? (matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light')
      : theme
    root.classList.remove('light', 'dark')
    root.classList.add(resolved)
    localStorage.setItem(STORAGE_KEY, theme)
  }, [theme])
  return <ThemeContext.Provider value={{ theme, setTheme }}>{children}</ThemeContext.Provider>
}
```

Add a blocking `<script>` in `index.html` that reads localStorage and applies the
class before React mounts — eliminates the flash of wrong theme.

shadcn tokens (`--background`, `--foreground`, `--primary`, ...) are defined in
`app/index.css` under `:root` and `.dark`. reui.io components consume the same
variables via `tailwind.config.ts`, so both libraries stay visually unified.

---

## 10. Testing Posture for v1

- **Type-check on commit** (`tsc --noEmit`) — non-negotiable; this is our main safety net.
- **Vitest** smoke tests:
  - Each service (`ClientsService`) against the mock impl: list/create/update/remove
    round-trip, validation error shape.
  - Each query key factory: key stability, no accidental structural drift.
  - Two or three component tests on critical forms (ClientForm create flow).
- **No e2e, no Playwright** in v1. The mock app would test itself.
- **ESLint boundary rules** (import restrictions between layers) are treated as tests.

When the HTTP impl lands, the same service tests run against it with MSW shimming
the network, which gives us a cheap correctness harness for the swap.

---

## 11. Migration Path to Real API

### 11.1 What stays

- All React components, all routes, all forms, all Zod schemas.
- All query hooks, all query keys.
- Service **interfaces** in `shared/api/contracts/*`.
- The session store (role source gets repointed).

### 11.2 What changes

- `shared/api/services/http/*` gets real implementations.
- `services/index.ts` now default-picks `http`.
- `shared/session/store.ts` reads from an auth provider; `<RoleGate>` and guards
  don't care.
- Environment: `VITE_API_BASE_URL`, plus token refresh plumbing.
- Mappers from backend DTOs to domain types live in `http/mappers/*`.
- Optional: MSW added for integration tests against the HTTP impl.

### 11.3 Concrete diff — `clientsService.list`

**Before (mock):**

```ts
// src/shared/api/services/mock/clients.service.ts
import { db } from './db'
import { latency } from './latency'
import { filter, paginate } from './query-helpers'

export const clientsService: ClientsService = {
  async list(params) {
    await latency()
    return paginate(filter(db.clients.all(), params), params)
  },
  // ...
}
```

**After (http):**

```ts
// src/shared/api/services/http/clients.service.ts
import { http } from './http-client' // axios instance with baseURL + auth interceptor
import { toClient } from './mappers/client'
import type { ClientsService } from '@/shared/api/contracts'

export const clientsService: ClientsService = {
  async list(params) {
    const { data } = await http.get('/clients', { params })
    return {
      items: data.items.map(toClient),
      total: data.total,
      page: data.page,
      pageSize: data.pageSize,
    }
  },
  // ...
}
```

**And the single-line swap:**

```ts
// src/shared/api/services/index.ts
- const mode = import.meta.env.VITE_API_MODE ?? 'mock'
+ const mode = import.meta.env.VITE_API_MODE ?? 'http'
```

No React component, no hook, no query key, no schema, no route changes. That is
the point of the whole architecture, and it's the single acceptance criterion for
the mock era.

---

## 12. Pitfalls Already Flagged

1. **Instant mocks hide loading bugs.** Always keep a baseline latency in dev; don't
   set it to zero to "feel snappy".
2. **Stale localStorage across schema changes.** Always bump the `:v1` key, and show
   a one-time migration toast if desired.
3. **Backend response shapes leaking into components.** If anyone imports from
   `shared/api/services/http/*` outside the services folder, fail the lint.
4. **Role gate in UI ≠ security.** We know this is dev-only. Make sure the
   `HttpServices` era introduces actual server-side authorization; `<RoleGate>` is
   for UX, never for access control.
5. **Invalidation storms on big mutations.** Prefer `setQueriesData` for targeted
   cache updates; `invalidateQueries` only in `onSettled` as a safety net.
6. **Route-level loaders duplicating hook calls.** Always prefetch via
   `queryClient.ensureQueryData` with the **same key** the hook uses — otherwise you
   get two fetches on first paint.
7. **`Date` in domain types.** Don't. Serialize as ISO strings; parse at the edges.
8. **Faker without a seed.** You'll get a different demo every reload; reviewers
   will think data is broken.

---

## 13. Sources

- TanStack Query v5 — optimistic updates & invalidation. Context7: `/tanstack/query`,
  latest v5.90.3. HIGH confidence.
- TanStack Router — file-based routing, `validateSearch`, loader + `ensureQueryData`.
  Context7: `/websites/tanstack_router`. HIGH confidence.
- React Router v7.9.4 — alternative, library mode. Context7: `/remix-run/react-router`.
  HIGH confidence.
- MSW — browser + node handlers, Vite/Vitest integration. Context7:
  `/websites/mswjs_io`. HIGH confidence.
- React Hook Form v7.66 + `@hookform/resolvers` (zod). Context7:
  `/react-hook-form/react-hook-form`, `/react-hook-form/resolvers`. HIGH confidence.
- shadcn/ui — CSS variables for theming, copy-in components. Context7:
  `/websites/ui_shadcn`. HIGH confidence.
- Zustand v5 — store + `persist` middleware for session. Context7: `/pmndrs/zustand`.
  HIGH confidence.
- Feature-Sliced Design (feature-first layout as applied here is an FSD-lite adaptation).
  Community pattern widely adopted 2023–2026. MEDIUM confidence (conceptual guidance,
  not a strict version-bound spec).
