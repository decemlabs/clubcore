# Phase 100: Foundation + Authentication — Pattern Map

**Mapped:** 2026-06-13
**Files analyzed:** 14 new/modified files
**Analogs found:** 14 / 14

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `apps/admin-app/package.json` | config | — | `apps/client-pwa/package.json` | exact |
| `apps/admin-app/vite.config.ts` | config | request-response | `apps/client-pwa/vite.config.ts` (+ admin-app existing) | role-match |
| `apps/admin-app/eslint.config.js` | config | — | `apps/admin-web/eslint.config.js` | exact |
| `.github/workflows/ci.yml` (add job) | config | — | existing `client-pwa` job in `ci.yml` lines 169–201 | exact |
| `apps/admin-app/src/api/client.ts` (extend) | utility | request-response | `apps/client-pwa/src/lib/clientFetcher.ts` | exact |
| `apps/admin-app/src/api/query-client.ts` (extend) | utility | event-driven | `apps/client-pwa/src/lib/queryClient.ts` | exact |
| `apps/admin-app/src/lib/authBus.ts` (new) | utility | event-driven | `apps/client-pwa/src/lib/authBus.ts` | exact |
| `apps/admin-app/src/features/auth/schemas.ts` (new) | model | CRUD | `apps/client-pwa/src/lib/clientQueries.ts` (Zod shapes inline) | role-match |
| `apps/admin-app/src/features/auth/api.ts` (new) | service | request-response | `apps/client-pwa/src/lib/clientQueries.ts` + `apps/admin-app/src/features/clients/api.ts` | exact |
| `apps/admin-app/src/shared/session/can.ts` (new) | utility | — | `apps/admin-web/src/shared/session/can.ts` | exact (port) |
| `apps/admin-app/src/shared/session/registry.ts` (new) | utility | — | `apps/admin-web/src/shared/session/registry.ts` | exact (port) |
| `apps/admin-app/src/components/feedback/ComingSoon.tsx` (new) | component | — | `apps/client-pwa/src/components/ComingSoon.tsx` + admin-app `auth-ui.tsx` `ScreenIcon` | role-match |
| `apps/admin-app/src/layouts/AppLayout/AppSidebar.tsx` (modify) | component | request-response | `apps/admin-app/src/layouts/AppLayout/AppSidebar.tsx` (self, extend) | self |
| `apps/admin-app/src/pages/login/components/LoginForm.tsx` (modify) | component | request-response | `apps/admin-app/src/pages/login/components/LoginForm.tsx` (self, extend) | self |

---

## Pattern Assignments

### `apps/admin-app/package.json` (config — workspace absorption)

**Analog:** `apps/client-pwa/package.json`

**Name + packageManager pattern:**
```json
{
  "name": "@clubcore/admin-app",
  "private": true,
  "version": "0.0.1",
  "type": "module",
  "packageManager": "pnpm@9.15.9",
  "engines": {
    "node": ">=20.0.0",
    "pnpm": ">=9.0.0"
  }
}
```

**Workspace dependency pattern** (client-pwa `package.json` lines 19-20):
```json
"dependencies": {
  "@clubcore/api-client": "workspace:*",
  ...
}
```

**Scripts pattern** (client-pwa `package.json` lines 11-17):
```json
"scripts": {
  "dev": "vite",
  "build": "tsc -b && vite build",
  "preview": "vite preview",
  "lint": "eslint .",
  "test": "vitest run",
  "typecheck": "tsc -b --noEmit"
}
```

Drop: `bun.lock`, `"check"` script (not in client-pwa pattern). Drop `"format"` from scripts but keep prettier in devDependencies. Drop `@typescript-eslint/eslint-plugin` + `@typescript-eslint/parser` (use `typescript-eslint` monolith as in client-pwa). TypeScript pin: `~5.7.2` (match workspace constraint). Add `eslint-plugin-import` + `eslint-import-resolver-typescript` (needed for `import/no-restricted-paths`).

---

### `apps/admin-app/vite.config.ts` (config — add dev proxy)

**Analog:** existing `apps/admin-app/vite.config.ts` (lines 1-23) + client-pwa pattern

**Add `server.proxy` block to existing config:**
```typescript
server: {
  port: 5173,
  host: true,
  proxy: {
    '/api': {
      target: process.env['VITE_API_PROXY_TARGET'] ?? 'http://localhost:8000',
      changeOrigin: true,
    },
  },
},
```

Keep existing `plugins`, `resolve.alias`, `resolve.dedupe`, `optimizeDeps` untouched.

---

### `.github/workflows/ci.yml` (add `admin-app` parallel job)

**Analog:** `client-pwa` job in `.github/workflows/ci.yml` lines 169–201

**New job block — copy client-pwa job verbatim, change filter and name:**
```yaml
admin-app:
  name: Admin App (typecheck + lint + test + build)
  runs-on: ubuntu-latest
  steps:
    - name: Checkout
      uses: actions/checkout@v4

    - name: Set up pnpm
      uses: pnpm/action-setup@v3
      with:
        version: 9

    - name: Set up Node 20
      uses: actions/setup-node@v4
      with:
        node-version: "20"
        cache: "pnpm"

    - name: pnpm install
      run: pnpm install --frozen-lockfile

    - name: Typecheck
      run: pnpm -F @clubcore/admin-app typecheck

    - name: Lint
      run: pnpm -F @clubcore/admin-app lint

    - name: Test
      run: pnpm -F @clubcore/admin-app test

    - name: Build
      run: pnpm -F @clubcore/admin-app build
```

**Also update `frontend` job recursive filter** (lines 138-145) to also exclude `@clubcore/admin-app`:
```yaml
- name: Lint (workspaces)
  run: pnpm -r --filter '!@clubcore/client-pwa' --filter '!@clubcore/admin-app' lint

- name: Typecheck (workspaces)
  run: pnpm -r --filter '!@clubcore/client-pwa' --filter '!@clubcore/admin-app' typecheck

- name: Test (workspaces)
  run: pnpm -r --filter '!@clubcore/client-pwa' --filter '!@clubcore/api-client' --filter '!@clubcore/admin-app' test
```

---

### `apps/admin-app/src/api/client.ts` (extend — CSRF + credentials + 401 handling)

**Analog:** `apps/client-pwa/src/lib/clientFetcher.ts` (full file)

**Replace the thin `api()` wrapper with a staff-scoped transport. Key patterns to copy:**

**CSRF cookie reader** (clientFetcher.ts lines 52-60, adapted for staff cookie name):
```typescript
const STAFF_CSRF_COOKIE = 'clubcore_csrf'

export function readStaffCsrfCookie(): string | undefined {
  const prefix = `${STAFF_CSRF_COOKIE}=`
  const cookies = document.cookie.split(';')
  for (const raw of cookies) {
    const c = raw.trim()
    if (c.startsWith(prefix)) return c.slice(prefix.length)
  }
  return undefined
}
```

**Safe-methods check** (clientFetcher.ts lines 44-46):
```typescript
function isMutating(method: string): boolean {
  return method !== 'GET' && method !== 'HEAD' && method !== 'OPTIONS' && method !== 'TRACE'
}
```

**Refresh-exempt paths** (clientFetcher.ts lines 31-36, adapted for staff paths):
```typescript
export const STAFF_AUTH_EXEMPT_PATHS: readonly string[] = [
  '/api/v1/auth/login',
  '/api/v1/auth/refresh',
  '/api/v1/auth/logout',
  '/api/v1/auth/password-reset/request',
  '/api/v1/auth/password-reset/confirm',
]
```

**Single-flight refresh** (clientFetcher.ts lines 64-81, adapted to `/api/v1/auth/refresh`):
```typescript
let inFlightStaffRefresh: Promise<Response> | null = null

export function staffRefreshOnce(): Promise<Response> {
  if (inFlightStaffRefresh) return inFlightStaffRefresh
  inFlightStaffRefresh = fetch('/api/v1/auth/refresh', {
    method: 'POST',
    credentials: 'include',
  }).finally(() => {
    queueMicrotask(() => { inFlightStaffRefresh = null })
  })
  return inFlightStaffRefresh
}
```

**Error body parser** (clientFetcher.ts lines 83-103) — copy verbatim.

**Request function with credentials + CSRF injection + 401 → refresh → retry** (clientFetcher.ts lines 163-264):
```typescript
export async function staffRequest<
  P extends keyof paths,
  M extends keyof paths[P] & string,
>(method: M, path: P, init?: StaffRequestInit): Promise<unknown> {
  // ...build url, headers...
  if (isMutating(upper)) {
    const csrf = readStaffCsrfCookie()
    if (csrf) headers.set('X-CSRF-Token', csrf)
  }
  const baseInit: RequestInit = {
    ...restInit,
    method: upper,
    credentials: 'include',  // key: send cc_access / cc_refresh cookies
    headers,
    body: bodyPayload,
  }
  // ...fetch → if 401 and not exempt → staffRefreshOnce() → retry → if still 401 throw session_expired...
}
```

Keep existing `ApiError` class and `mockResponse()` helper — they are still used by non-auth domains in Phase 100. Rename `ApiError` to use `code: string` (string code, not `status: number`) to match the backend error envelope and `@clubcore/api-client` convention.

---

### `apps/admin-app/src/api/query-client.ts` (extend — session expiry handler)

**Analog:** `apps/client-pwa/src/lib/queryClient.ts` (full file, 52 lines)

**Replace singleton with QueryCache + MutationCache onError pattern:**
```typescript
import { MutationCache, QueryCache, QueryClient } from '@tanstack/react-query'
import { ApiError } from '@/api/client'
import { publishSessionExpired } from '@/lib/authBus'

let _redirecting = false

function handleSessionExpired(error: unknown): void {
  if (!(error instanceof ApiError)) return
  if (error.code !== 'session_expired') return
  if (_redirecting) return
  _redirecting = true
  publishSessionExpired()
  setTimeout(() => { _redirecting = false }, 5000)
}

export const queryClient = new QueryClient({
  queryCache: new QueryCache({ onError: handleSessionExpired }),
  mutationCache: new MutationCache({ onError: handleSessionExpired }),
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

`ApiError.code` is a string field (matches backend error envelope), not `status: number`. The import path changes: `@clubcore/api-client` is the source in client-pwa; in admin-app use `@/api/client` (local wrapper re-exports or re-implements `ApiError`).

---

### `apps/admin-app/src/lib/authBus.ts` (new)

**Analog:** `apps/client-pwa/src/lib/authBus.ts` (full file, 37 lines)

**Copy verbatim** — pure pub/sub, no React, no router imports. Only the file path changes.

```typescript
type SessionExpiredCallback = () => void
const _subscribers = new Set<SessionExpiredCallback>()

export function subscribeSessionExpired(cb: SessionExpiredCallback): () => void {
  _subscribers.add(cb)
  return () => { _subscribers.delete(cb) }
}

export function publishSessionExpired(): void {
  for (const cb of _subscribers) { cb() }
}
```

---

### `apps/admin-app/src/features/auth/schemas.ts` (new — Zod contract)

**Analog:** inline Zod usage in admin-app domain hooks + admin-web entity schemas pattern

**Login request schema** (matching backend `LoginRequest`: email, password `min_length=12`):
```typescript
import { z } from 'zod'

export const LoginRequestSchema = z.object({
  email: z.string().email('Введите корректный адрес почты'),
  password: z.string().min(12, 'Пароль должен содержать не менее 12 символов'),
})
export type LoginRequest = z.infer<typeof LoginRequestSchema>
```

**Login response schema** (verified backend shape `{data:{user:{id,role,fullName}}}`):
```typescript
export const LoginResponseSchema = z.object({
  data: z.object({
    user: z.object({
      id: z.string(),
      role: z.enum(['owner', 'reception']),
      fullName: z.string(),
    }),
  }),
})
```

**MeResponse schema** (verified `GET /auth/me` → `{data:{id,role,fullName,email,hasTelegram}}`):
```typescript
export const MeResponseSchema = z.object({
  data: z.object({
    id: z.string(),
    role: z.enum(['owner', 'reception']),
    fullName: z.string(),
    email: z.string(),
    hasTelegram: z.boolean(),
  }),
})
export type MeResponse = z.infer<typeof MeResponseSchema>
```

**Error envelope schema** (top-level, NOT wrapped in `data`):
```typescript
export const ApiErrorEnvelopeSchema = z.object({
  code: z.string(),
  message: z.string(),
  fields: z.record(z.string()).optional(),
})
```

**PasswordReset schemas:**
```typescript
export const PasswordResetRequestSchema = z.object({
  email: z.string().email(),
})
export const PasswordResetConfirmSchema = z.object({
  token: z.string(),
  password: z.string().min(12),
})
```

---

### `apps/admin-app/src/features/auth/api.ts` (new — TanStack Query hooks)

**Analog:** `apps/admin-app/src/features/clients/api.ts` (structure) + `apps/client-pwa/src/lib/clientQueries.ts` (mutation + query pattern)

**Keys factory pattern** (clients/api.ts lines 9-13):
```typescript
export const authKeys = {
  me: ['auth', 'me'] as const,
}
```

**`useSession()` query hook** — single source of truth for role/fullName/email:
```typescript
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { staffRequest } from '@/api/client'
import { MeResponseSchema } from './schemas'

export function useSession() {
  return useQuery({
    queryKey: authKeys.me,
    queryFn: async () => {
      const raw = await staffRequest('get', '/api/v1/auth/me')
      return MeResponseSchema.parse(raw).data
    },
    retry: false,   // 401 on /me is handled by global session_expired, not retried
  })
}
```

**`useLogin()` mutation:**
```typescript
export function useLogin() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (body: LoginRequest) => {
      const raw = await staffRequest('post', '/api/v1/auth/login', { body })
      return LoginResponseSchema.parse(raw).data.user
    },
    onSuccess: (user) => {
      qc.setQueryData(authKeys.me, user)
    },
  })
}
```

**`useLogout()` mutation:**
```typescript
export function useLogout() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: () => staffRequest('post', '/api/v1/auth/logout'),
    onSettled: () => {
      qc.removeQueries({ queryKey: authKeys.me })
    },
  })
}
```

**`VITE_API_MODE` chokepoint** — auth domain always uses `http` in Phase 100; no mock path needed. Other domains (`features/clients/api.ts`, etc.) stay on `mockResponse()` and are not changed in Phase 100.

---

### `apps/admin-app/src/shared/session/can.ts` (new — RBAC port)

**Analog:** `apps/admin-web/src/shared/session/can.ts` (full file, 85 lines)

**Port verbatim** from `apps/admin-web/src/shared/session/can.ts`. This is the CISO-01 byte-parity target. All 41 `OWNER_ONLY` entries must be preserved exactly. Only the import path for `Action`/`Resource` changes (from `./registry` — same relative path).

```typescript
import type { Action, Resource } from './registry'
import type { Role } from './types'

export const OWNER_ONLY: ReadonlyArray<{ action: Action; resource: Resource }> = [
  // ... all 41 entries verbatim from admin-web/src/shared/session/can.ts lines 12-79 ...
]

export function can(role: Role, action: Action, resource: Resource): boolean {
  if (role === 'owner') return true
  return !OWNER_ONLY.some((entry) => entry.action === action && entry.resource === resource)
}
```

Also create `apps/admin-app/src/shared/session/types.ts`:
```typescript
export type Role = 'owner' | 'reception'
```

---

### `apps/admin-app/src/shared/session/registry.ts` (new — route registry port)

**Analog:** `apps/admin-web/src/shared/session/registry.ts` (full file, 93 lines)

Port `Resource`, `Action`, `RouteEntry` type definitions verbatim. The `routeRegistry` entries must be adapted to admin-app's actual routes (different from admin-web). Use `apps/admin-app/src/app/routes.ts` `ROUTES` constants as path values. Resource strings must match `can.ts` OWNER_ONLY matrix exactly.

**Type definitions to port verbatim** (registry.ts lines 1-57 — Resource union, Action union, RouteEntry interface).

**routeRegistry adapted for admin-app routes:**
```typescript
export const routeRegistry: readonly RouteEntry[] = [
  { path: ROUTES.dashboard, resource: 'dashboard', label: 'Дашборд', icon: 'LayoutDashboard', navKey: 'home' },
  { path: ROUTES.clients,   resource: 'clients',   label: 'Клиенты',  icon: 'Users',          navKey: 'clients' },
  // ... map admin-app ROUTES entries to Resource values from can.ts ...
  { path: ROUTES.finance,   resource: 'finance',   label: 'Финансы',  icon: 'Banknote',       navKey: 'finance' },
  { path: ROUTES.reports,   resource: 'reports',   label: 'Отчёты',   icon: 'BarChart3',      navKey: 'reports' },
  // ... etc.
]
```

---

### `apps/admin-app/src/components/feedback/ComingSoon.tsx` (new)

**Analogs:** `apps/client-pwa/src/components/ComingSoon.tsx` (concept) + `apps/admin-app/src/pages/login/components/auth-ui.tsx` `ScreenIcon` (lines 22-33, icon tile anatomy) + `PageState.tsx` (feedback component file pattern)

**Full component using admin-app design tokens** per UI-SPEC.md Surface 1:
```typescript
import { Clock } from '@/components/icons'
import { ScreenIcon } from '@/pages/login/components/auth-ui'

/**
 * Placeholder for deferred (hide-for-future) routes.
 * FND-04: "not broken, not wired".
 */
export function ComingSoon() {
  return (
    <div className="flex flex-1 flex-col items-center justify-center px-6 text-center animate-in fade-in-0 duration-300">
      <div className="max-w-[400px]">
        <ScreenIcon icon={Clock} tone="accent" />
        <h2 className="text-[20px] font-bold tracking-[-0.4px] text-fg">
          Раздел в разработке
        </h2>
        <p className="mt-2 max-w-[320px] text-[14px] leading-[1.55] text-fg-muted">
          Этот раздел будет доступен в следующем обновлении.{'\n'}
          Пока продолжайте работать в текущих разделах.
        </p>
      </div>
    </div>
  )
}
```

No props, no action button (per UI-SPEC.md). `ScreenIcon` is imported from auth-ui (same 52×52px, rounded-[15px], accent tone = `bg-primary-soft text-primary-deep`).

---

### `apps/admin-app/src/layouts/AppLayout/AppSidebar.tsx` (modify — wire session + role gating)

**Analog:** existing `apps/admin-app/src/layouts/AppLayout/AppSidebar.tsx` (self, lines 1-112)

**Key modifications:**

1. **Import `useSession` + `can` + `Skeleton`:**
```typescript
import { Skeleton } from '@/components/ui/skeleton'
import { useSession } from '@/features/auth/api'
import { can } from '@/shared/session/can'
```

2. **Replace static `APP_ROLE_LABEL` pill** (line 40-42) with dynamic role pill per UI-SPEC.md:
```typescript
// In SidebarHeader, replace static pill:
{session.data && (
  <span className={cn(
    'ml-auto rounded-full px-[7px] py-0.5 text-[10px] font-bold tracking-[0.4px]',
    session.data.role === 'owner'
      ? 'bg-primary-soft text-primary-deep'
      : 'bg-surface-3 text-fg-subtle',
  )}>
    {session.data.role === 'owner' ? 'Владелец' : 'Ресепшн'}
  </span>
)}
```

3. **Filter NAV_SECTIONS at render time** using `can()` + hide-for-future removal:
```typescript
const HIDE_FOR_FUTURE = new Set([ROUTES.messages, ROUTES.notifications, ROUTES.branches])

// In render:
const role = session.data?.role ?? 'reception'
const visibleSections = NAV_SECTIONS.map(section => ({
  ...section,
  items: section.items.filter(item =>
    !HIDE_FOR_FUTURE.has(item.to) && can(role, 'view', itemToResource(item.to))
  ),
})).filter(section => section.items.length > 0)
```

4. **Replace hardcoded footer card** (lines 93-107) with session-driven card + Skeleton loading:
```typescript
// Footer card:
{session.isPending ? (
  <div className="flex items-center gap-2.5 rounded-[12px] border-[0.5px] border-border bg-surface p-2">
    <div className="size-8 rounded-full bg-surface-3" />
    <div className="flex flex-col gap-1.5">
      <Skeleton className="h-3 w-24" />
      <Skeleton className="h-2.5 w-16" />
    </div>
  </div>
) : session.data ? (
  <div className="flex items-center gap-2.5 rounded-[12px] border-[0.5px] border-border bg-surface p-2">
    <div className="grid size-8 shrink-0 place-items-center rounded-full bg-gradient-to-br from-[#f59e0b] to-[#f97316] text-[12px] font-bold text-white">
      {getInitials(session.data.fullName)}
    </div>
    <div className="min-w-0 flex-1">
      <div className="truncate text-[13px] font-semibold text-fg">{session.data.fullName}</div>
      <div className="truncate text-[11.5px] text-fg-subtle">
        {session.data.role === 'owner' ? 'Владелец' : 'Ресепшн'}
      </div>
    </div>
    {/* existing ChevronRight button unchanged */}
  </div>
) : null}
```

`getInitials(fullName)` helper: split on space, take first char of each word, max 2, uppercase.

---

### `apps/admin-app/src/pages/login/components/LoginForm.tsx` (modify — wire to real backend)

**Analog:** existing `apps/admin-app/src/pages/login/components/LoginForm.tsx` (self, 94 lines)

**Key modifications:**

1. **Replace `useState` form simulation with `useLogin()` mutation:**
```typescript
import { useLogin } from '@/features/auth/api'
import { LoginRequestSchema } from '@/features/auth/schemas'
import { AlertCircle } from '@/components/icons'
import { toast } from 'sonner'

const { mutate: login, isPending } = useLogin()
```

2. **Zod validation on submit** (replace regex + manual check):
```typescript
const handleSubmit = (event: FormEvent) => {
  event.preventDefault()
  setCredentialError(null)   // clear banner on each attempt
  const result = LoginRequestSchema.safeParse({ email, password })
  if (!result.success) {
    const fe = result.error.flatten().fieldErrors
    setErrors({ email: fe.email?.[0], password: fe.password?.[0] })
    return
  }
  login(result.data, {
    onSuccess: onSuccess,
    onError: (err) => {
      if (err instanceof ApiError) {
        if (err.code === 'invalid_credentials') {
          setCredentialError('Неверный email или пароль.')
        } else if (err.code === 'validation_error' && err.fields) {
          setErrors({ email: err.fields['email'], password: err.fields['password'] })
        } else {
          toast.error('Не удалось выполнить вход', {
            description: 'Проверьте соединение и попробуйте ещё раз.',
          })
        }
      }
    },
  })
}
```

3. **Inline credential error banner** (above email field, per UI-SPEC.md Surface 3):
```typescript
{credentialError && (
  <div className="mb-[18px] flex items-center gap-2 rounded-[10px] bg-danger-soft px-[14px] py-[11px] text-[13px] text-danger">
    <AlertCircle className="size-4 shrink-0" />
    {credentialError}
  </div>
)}
```

4. **Pending state** — pass `loading={isPending}` to `PrimaryButton` and `disabled={isPending}` to `Field`/`PasswordField`.

5. **Remember-me no-op callout** — add `Callout` with `tone='default'` below checkbox (import `Callout` from auth-ui):
```typescript
<Callout tone="default" icon={TriangleAlert}>
  Сессия действует 7 дней независимо от этого параметра.
</Callout>
```

6. **Google button no-op toast** (replace current `onClick={onSuccess}`):
```typescript
<GoogleButton onClick={() => toast('Google Workspace вход будет доступен позже.')} />
```

---

### `apps/admin-app/src/pages/login/LoginPage.tsx` (modify — hide twofa, wire session expiry nav)

**Analog:** existing `apps/admin-app/src/pages/login/LoginPage.tsx` (self, 100 lines)

**Key modifications:**

1. **Remove `twofa` from `DEEP_LINKABLE`** (line 14):
```typescript
// Before:
const DEEP_LINKABLE: AuthView[] = ['twofa', 'expired', 'logout']
// After:
const DEEP_LINKABLE: AuthView[] = ['expired', 'logout']
```

2. **Remove `twofa` case from `renderScreen()`** (line 66) — let it fall through to default `'login'`.

3. **Remove `TwoFactorScreen` import** (line 9). Keep the file `TwoFactorScreen.tsx` unmodified and un-imported.

4. **Wire session expiry redirect** — subscribe to `authBus` in a `useEffect`, navigate to `/login?state=expired` and invalidate session query on `session_expired`:
```typescript
import { subscribeSessionExpired } from '@/lib/authBus'
import { queryClient } from '@/api/query-client'
import { authKeys } from '@/features/auth/api'

useEffect(() => {
  return subscribeSessionExpired(() => {
    queryClient.removeQueries({ queryKey: authKeys.me })
    navigate(`${ROUTES.login}?state=expired`, { replace: true })
  })
}, [navigate])
```

---

### `apps/admin-app/src/app/router.tsx` (modify — swap deferred routes to ComingSoon)

**Analog:** existing `apps/admin-app/src/app/router.tsx` (self, 181 lines)

**Pattern for ComingSoon route registration** (replace `lazy:` import with inline element):
```typescript
import { ComingSoon } from '@/components/feedback/ComingSoon'

// Deferred routes — replace lazy page import with static ComingSoon element:
{ path: ROUTES.branches,      element: <ComingSoon /> },
{ path: ROUTES.messages,      element: <ComingSoon /> },
{ path: ROUTES.notifications, element: <ComingSoon /> },
{ path: ROUTES.roles,         element: <ComingSoon />, handle: { breadcrumb: ['Настройки', 'Роли и права'] } },
{ path: ROUTES.importExport,  element: <ComingSoon />, handle: { breadcrumb: ['Настройки', 'Импорт / экспорт'] } },
{ path: ROUTES.trash,         element: <ComingSoon />, handle: { breadcrumb: ['Настройки', 'Корзина'] } },
{ path: ROUTES.systemSettings, element: <ComingSoon />, handle: { breadcrumb: ['Настройки', 'Система'] } },
```

Keep `lazy:` for all active routes (`clients`, `schedule`, `dashboard`, etc.) — no change.

---

### `apps/admin-app/eslint.config.js` (update — add VITE_API_MODE chokepoint + boundary zones)

**Analog:** `apps/admin-web/eslint.config.js` (full file, 167 lines)

**Add `import/no-restricted-paths` zone** for the admin-app layer boundary (mirrors admin-web lines 48-76):
```javascript
'import/no-restricted-paths': [
  'error',
  {
    zones: [
      {
        // Pages/features/components must not import staffRequest / api/client directly
        target: [
          './src/features/**',
          './src/pages/**',
          './src/layouts/**',
          './src/components/**',
        ],
        from: ['./src/api/client.ts'],
        except: ['./src/features/auth/**'],
        message: 'Use TanStack Query hooks from features/*/api.ts, not staffRequest directly.',
      },
    ],
  },
],
```

**Add `VITE_API_MODE` chokepoint rule** (mirrors admin-web eslint.config.js lines 96-108):
```javascript
{
  files: ['src/**/*.{ts,tsx}'],
  ignores: ['src/features/auth/**'],
  rules: {
    'no-restricted-syntax': [
      'error',
      {
        selector: "MemberExpression[property.name='VITE_API_MODE']",
        message: 'Read VITE_API_MODE only inside src/features/*/api.ts swap-seam files.',
      },
    ],
  },
},
```

Add `eslint-plugin-import` (already in package.json devDeps after absorption) and `eslint-import-resolver-typescript` to support the path zones.

---

## Shared Patterns

### CSRF double-submit (apply to `staffRequest` in `api/client.ts`)

**Source:** `apps/client-pwa/src/lib/clientFetcher.ts` lines 52-60 + 193-196

Cookie name for staff: `clubcore_csrf` (NOT `clubcore_client_csrf`).
Inject on every mutating request (POST/PUT/PATCH/DELETE), read fresh after refresh:
```typescript
if (isMutating(upper)) {
  const csrf = readStaffCsrfCookie()
  if (csrf) headers.set('X-CSRF-Token', csrf)
}
```
After refresh + retry, re-read cookie (rotation may have changed value):
```typescript
const retryHeaders = new Headers(headers)
if (isMutating(upper)) {
  const csrf = readStaffCsrfCookie()
  if (csrf) retryHeaders.set('X-CSRF-Token', csrf)
  else retryHeaders.delete('X-CSRF-Token')
}
```

### 401 → session_expired propagation chain

**Source:** `apps/client-pwa/src/lib/queryClient.ts` + `apps/client-pwa/src/lib/authBus.ts`

Full chain:
1. `staffRequest` throws `ApiError('session_expired', ...)` after refresh also 401s.
2. `QueryCache.onError` / `MutationCache.onError` in `query-client.ts` catches it.
3. Calls `publishSessionExpired()` via `authBus.ts`.
4. `LoginPage.tsx` `useEffect` subscribes → navigates to `/login?state=expired` + clears session query.
5. Existing `ExpiredScreen` renders.

### Skeleton loading pattern for session-pending UI

**Source:** `apps/admin-app/src/components/feedback/PageState.tsx` lines 6-17 + UI-SPEC.md

```typescript
import { Skeleton } from '@/components/ui/skeleton'
// Pending: render Skeleton placeholders at exact dimensions from UI-SPEC
<Skeleton className="h-3 w-24" />   // fullName placeholder
<Skeleton className="h-2.5 w-16" /> // role label placeholder
```

### Mock swap-seam — do NOT change non-auth domains

**Source:** `apps/admin-app/src/features/clients/api.ts` lines 1-35

All non-auth feature hooks continue to use `mockResponse()`. The `VITE_API_MODE` chokepoint pattern is established in Phase 100 but only auth uses `http` mode. Each domain flips independently in its own phase (101–104). The `mockResponse()` helper in `api/client.ts` must be preserved even as the file gains real transport.

---

## No Analog Found

All files have close analogs. No entries in this section.

---

## Metadata

**Analog search scope:** `apps/client-pwa/src/lib/`, `apps/admin-web/src/shared/session/`, `apps/admin-app/src/` (api/, features/, layouts/, pages/, components/feedback/), `.github/workflows/ci.yml`
**Files scanned:** 18
**Pattern extraction date:** 2026-06-13
