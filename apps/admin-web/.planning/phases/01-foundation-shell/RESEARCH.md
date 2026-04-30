# Phase 1: Foundation & Shell — Research

**Researched:** 2026-04-21
**Domain:** React 19 + Vite + Tailwind v4 + shadcn/ui + TanStack Router/Query + Zustand + ESLint flat config + Russian locale shell
**Confidence:** HIGH on core stack setup; MEDIUM on reui.io `style` interop; MEDIUM-HIGH on FOUC-safe theme bootstrap.
**Research flag (from ROADMAP):** LOW — stack is locked in `CLAUDE.md`. This pass confirms versions and locks down exact setup snippets.

---

## Summary

Phase 1 is a pure scaffolding phase: there is no product logic, only infrastructure. The biggest risks are *not* ecosystem churn — they are **project-global decisions that cost 3× if you undo them later**: folder layout, theme-token contract, import boundaries, router context plumbing, and persisted-store versioning. All eight items below are commodity patterns with one official flow each; the planner should treat them as fill-in-the-blanks, not as design problems.

**Version drift found (2026-04-21 npm registry check) [VERIFIED: npm view]:** several versions in `CLAUDE.md`'s locked stack have moved. `CLAUDE.md` is the source of truth for this project, so treat these as *informational only* — the planner should ask the user before bumping:

| Package | CLAUDE.md locks | npm latest (2026-04-21) | Delta |
|---|---|---|---|
| vite | 6 | **8.0.9** | two majors ahead |
| eslint | 9 flat | **10.2.1** | one major ahead |
| typescript | 5.6+ (strict) | **6.0.3** | one major ahead |
| react | 19 | 19.2.5 | ✓ in line |
| tailwindcss | v4 | 4.2.3 | ✓ in line |
| @tanstack/react-router | 1.x | 1.168.23 | ✓ in line |
| @tanstack/react-query | 5 | 5.99.2 | ✓ in line |
| zustand | 5 | 5.0.12 | ✓ in line |
| date-fns | 4 | 4.1.0 | ✓ in line |
| sonner | current | 2.0.7 | ✓ in line |
| @tanstack/router-plugin | — | 1.167.22 | needed for file-based routing |

**Primary recommendation:** Honor `CLAUDE.md`'s locked versions (Vite 6, ESLint 9, TS 5.6+) unless the user explicitly approves bumps — don't quietly modernize. For every other item, use the canonical snippets in §"Code Examples" verbatim.

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|---|---|---|---|
| App shell render (top bar, sidebar, content) | Browser / Client | — | SPA; no SSR in v1. |
| Theme bootstrap (no-FOUC) | Browser (pre-React blocking `<script>` in `index.html`) | Browser (React `ThemeProvider`) | Class must land on `<html>` before React paints. |
| Role session (`useSession`) | Browser (Zustand + `persist`) | — | Mock-only in v1; swap seam at `session/` when real auth ships. |
| Route tree + guards | Browser (TanStack Router, file-based) | — | SPA routing, `beforeLoad` reads session+query context. |
| Server-state cache | Browser (TanStack Query) | Router loader (`ensureQueryData`) | Single source for remote data. |
| Russian locale (dates/money/plurals) | Browser (`Intl.*` + date-fns `ru` + `i18n/ru.ts`) | — | No runtime i18n framework per `CLAUDE.md`. |
| Import-boundary enforcement | Build time (ESLint flat config) | — | Static; runs in IDE + CI. |
| `VITE_API_MODE` seam | Build time (Vite env) → Runtime (services container) | — | `services/index.ts` reads env once at module init. |

---

## User Constraints (from CLAUDE.md — no CONTEXT.md yet)

### Locked Decisions (non-negotiable, from `CLAUDE.md`)
- Stack versions listed in `CLAUDE.md` §Stack (locked). No MSW (decision OQ#1 closed — plain service-layer mocks).
- Layered data flow: `UI → TanStack Query hook → services.X → { mock | http } impl`. Enforced by ESLint `import/no-restricted-paths`.
- Swap seam at `src/shared/api/services/index.ts` gated by `VITE_API_MODE=mock|http`.
- Domain types: branded UUIDv4 string IDs, ISO date strings (never `Date`), integer minor-unit `Money`, discriminated unions for variant kinds, uniform `DomainError`.
- Role as session: `useSession()` Zustand+`persist` exposes `{ role }`. Single `routeRegistry` + `can(role, action, resource)` consumed by sidebar, router `beforeLoad`, `<RoleGate>`, and mock services.
- Folder layout FSD-lite as described in `CLAUDE.md` (verbatim — do not invent alternatives).
- Query defaults: `staleTime: 30_000`, `refetchOnWindowFocus: false`, route `loader` uses `queryClient.ensureQueryData` with the same key the hook uses.
- Theming: single `:root` / `.dark` block in `app/index.css` with shadcn tokens; blocking `<script>` in `index.html` applies stored theme class before React mounts.
- Russian locale: DD.MM.YYYY, Monday week start, 24h, `+7 (XXX) XXX-XX-XX`, `1 234,56 ₽` with NBSP, 3-form plurals via `Intl.PluralRules('ru-RU')`; TZ pinned to `Europe/Moscow`; one `src/shared/i18n/ru.ts` dictionary — no i18next.
- Style tokens: only semantic shadcn tokens (`bg-background`, `text-muted-foreground`, …). Raw palette (`bg-white`, `text-slate-*`) banned via ESLint.
- shadcn customization: don't hand-edit `components/ui/*`; customizations go in wrappers; mark intentional divergence `// SHADCN-DIVERGENCE: …`.
- pnpm 9; commit_docs=true; Vitest; user-facing language RU; docs EN.

### Claude's Discretion (planner may decide within these bounds)
- Exact ESLint flat-config layout (single vs split config files).
- Exact path aliases (`@/…`) in `tsconfig.json` + Vite `resolve.alias` (must match shadcn `components.json` aliases).
- Whether the FOUC script also pre-computes `system` via `matchMedia('(prefers-color-scheme: dark)')` at boot (strongly recommended).
- Whether `useSession()` persists both `role` and `theme` in one store or two (recommend two: session vs ui-prefs; different rehydration priorities).
- Where the `routeRegistry` lives: `shared/session/registry.ts` is the natural home.

### Deferred Ideas (OUT OF SCOPE for Phase 1)
- Any feature UI (clients, schedule, staff, finance) — Phases 3+.
- Actual mock DB seeding with `@faker-js/faker` — Phase 2.
- Canonical List/Detail/Form templates — Phase 2 (UI-01, UI-02).
- Real auth / SMS / fiscalization / command palette — anti-features per `CLAUDE.md`.

---

## Phase Requirements

| ID | Description | Research support |
|---|---|---|
| FOUND-01 | App shell top bar + collapsible sidebar + content | §Code Examples — sidebar-07 shadcn block; AppShell composition |
| FOUND-02 | Role switcher persisted via `zustand/middleware#persist` | §Code Examples — Zustand persist with version + partialize |
| FOUND-03 | Theme toggle w/ blocking script, no FOUC | §Code Examples — `index.html` blocking script + `ThemeProvider` |
| FOUND-04 | RU UI: DD.MM.YYYY, Monday, phone mask, `1 234,56 ₽` NBSP, 3-form plurals | §Russian Locale Shell |
| FOUND-05 | TanStack Router file-based, typed search, root layout | §Code Examples — `vite.config.ts` plugin order + root route |
| FOUND-06 | ESLint `import/no-restricted-paths` blocking `services/mock\|http` from UI | §Code Examples — flat-config rule |
| FOUND-07 | Semantic tokens only; raw palette banned | §Code Examples — `no-restricted-syntax`/custom regex rule |
| ROLE-01 | Single `routeRegistry` + `can()` helper, one source of truth | §Architecture — Role/ACL module |
| ROLE-02 | Reception scope boundary | §Architecture — `can()` returns false for owner-only resources |
| ROLE-03 | Owner is superset of Reception | §Architecture — `can()` table |
| ROLE-04 | Destructive actions Owner-only | §Architecture — `can()` table entries |
| ROLE-05 | Replacing session source preserves ACL logic | §Architecture — session seam |
| UI-03 | reui.io coexists with shadcn via `@reui` registry | §reui.io Integration |
| UI-04 | Responsive at 1366×768 | §Pitfalls — container queries, sidebar collapse breakpoint |

---

## Standard Stack

### Core (honor `CLAUDE.md` locks)

| Library | Target version | Purpose | Why standard |
|---|---|---|---|
| vite | `^6.0.0` [CITED: CLAUDE.md] | Dev server + build | Fast HMR, first-class Tailwind v4 plugin, TanStack Router plugin support |
| react / react-dom | `^19.0.0` [CITED: CLAUDE.md] | UI runtime | Stack lock |
| typescript | `^5.6.0` strict [CITED: CLAUDE.md] | Type system | `strict: true` required |
| tailwindcss + @tailwindcss/vite | `^4.0.0` [CITED: shadcn Vite install docs] | Styling | CSS-first `@theme`, no `tailwind.config.js` required |
| shadcn (CLI) | latest (`shadcn@latest`) [CITED: ui.shadcn.com] | Component scaffolder | Project-local copy-paste components |
| @tanstack/react-router | `^1.168.0` [VERIFIED: npm] | Routing | Typed routes, typed search, `beforeLoad`, loader context |
| @tanstack/router-plugin | `^1.167.0` [VERIFIED: npm, CITED: tanstack router docs] | File-based route codegen | Required for file-based routing with Vite |
| @tanstack/react-query | `^5.99.0` [VERIFIED: npm] | Server-state cache | `ensureQueryData` pairs with router loader |
| zustand | `^5.0.0` [CITED: CLAUDE.md] | UI/session state | Tiny, typed, `persist` middleware |
| lucide-react | latest | Icons | shadcn default icon set |
| sonner | `^2.0.0` [VERIFIED: npm] | Toasts | shadcn default toast provider |

### Supporting (Phase 1)

| Library | Purpose | Notes |
|---|---|---|
| date-fns | Date formatting + `ru` locale | `import { ru } from 'date-fns/locale'` |
| eslint + typescript-eslint + eslint-plugin-import | Linting + boundary enforcement | Flat config (`eslint.config.js`) |
| prettier + prettier-plugin-tailwindcss | Formatting | Sorts Tailwind classes |
| vitest | Unit tests (smoke-level in Phase 1) | Config added in Phase 1 scaffold, real tests in Phase 2+ |

### Installation sequence (canonical, Vite + shadcn + Tailwind v4)

```bash
# 1. Scaffold
pnpm create vite@latest sportzal-adminka --template react-ts
cd sportzal-adminka
pnpm install

# 2. Tailwind v4 [CITED: ui.shadcn.com/docs/installation/vite]
pnpm add tailwindcss @tailwindcss/vite

# 3. TanStack Router + Query [CITED: tanstack/router docs]
pnpm add @tanstack/react-router @tanstack/react-query
pnpm add -D @tanstack/router-plugin @tanstack/router-devtools @tanstack/react-query-devtools

# 4. State / forms / icons / toasts / dates
pnpm add zustand date-fns lucide-react sonner

# 5. shadcn init (interactive; choose: Vite, TS, new-york, neutral, CSS vars)
pnpm dlx shadcn@latest init

# 6. Dev tooling
pnpm add -D eslint typescript-eslint eslint-plugin-import prettier prettier-plugin-tailwindcss vitest
```

### Version verification (2026-04-21)

All versions in the table above were verified with `npm view <pkg> version`. See §Summary for the drift table against `CLAUDE.md`.

---

## Architecture Patterns

### System data flow

```
index.html
  └─ <script> (blocking, ~500 bytes)              ← reads localStorage('sportzal:theme'), adds 'dark' class to <html>
          │                                          (runs BEFORE React bundle parses)
          ▼
  <div id="root">
          │
          ▼
  main.tsx  ──▶  <QueryClientProvider>             ← QueryClient with staleTime 30s, refetchOnWindowFocus false
                    └─ <RouterProvider router>     ← router context.queryClient injected
                          └─ __root.tsx layout     ← AppShell (TopBar + Sidebar + <Outlet/>)
                                │                     TopBar reads useSession() (role) and useTheme()
                                │                     Sidebar filters routeRegistry by can(role, 'view', resource)
                                ▼
                          /index.tsx, /clients.tsx, …
                                │
                                │  beforeLoad({ context: { queryClient, session } }) ──▶ check can(); redirect if no
                                │  loader({ context: { queryClient } }) ──▶ queryClient.ensureQueryData({ queryKey, queryFn })
                                ▼
                          useClientsQuery()  ──▶  services.clients.list(params)
                                                       │
                                                       ▼
                                             VITE_API_MODE === 'mock'
                                                       ? mockClientsService
                                                       : httpClientsService
```

### Recommended folder layout (from `CLAUDE.md`, expanded for Phase 1 files)

```
src/
├── app/
│   ├── index.css                 # @import "tailwindcss"; @theme inline {...}; :root {...}; .dark {...}
│   ├── main.tsx                  # <QueryClientProvider> + <RouterProvider>
│   ├── queryClient.ts            # new QueryClient({ defaultOptions: { queries: { staleTime: 30_000, refetchOnWindowFocus: false } } })
│   ├── router.ts                 # createRouter({ routeTree, context: { queryClient, session } })
│   └── providers/
│       └── ThemeProvider.tsx     # reads/writes localStorage + toggles .dark on <html>
├── routes/                       # TanStack Router file tree (auto-generated routeTree.gen.ts sits here)
│   ├── __root.tsx                # AppShell layout + <Outlet/> + devtools
│   ├── index.tsx                 # placeholder "Главная"
│   ├── clients.tsx               # placeholder (Phase 3 fills in)
│   ├── schedule.tsx              # placeholder
│   ├── staff.tsx                 # placeholder
│   └── finance.tsx               # placeholder
├── features/                     # (empty in Phase 1 — reserved)
├── entities/                     # (empty in Phase 1 — reserved)
└── shared/
    ├── ui/                       # shadcn components land here via CLI: button, sidebar, dropdown-menu, ...
    ├── api/
    │   ├── contracts/            # (empty stubs in Phase 1; Phase 2 fills)
    │   └── services/
    │       ├── index.ts          # seam: reads import.meta.env.VITE_API_MODE, returns { clients, schedule, ... }
    │       ├── mock/             # (empty stubs — just placeholders so ESLint path rule has a target)
    │       └── http/             # (empty stubs)
    ├── session/
    │   ├── store.ts              # Zustand persist store { role, setRole }
    │   ├── RoleGate.tsx          # <RoleGate action="refund" resource="payment">...</RoleGate>
    │   ├── registry.ts           # routeRegistry: { path, resource, actions, label, icon }[]
    │   └── can.ts                # can(role, action, resource): boolean
    ├── lib/
    │   ├── cn.ts                 # clsx + tailwind-merge
    │   └── money.ts              # formatMoney(kopecks) → '1 234,56 ₽'
    ├── i18n/
    │   └── ru.ts                 # single dictionary + plural helper
    ├── theme/
    │   └── useTheme.ts           # thin hook over ThemeProvider
    └── config/
        └── env.ts                # typed import.meta.env wrapper
index.html                        # includes the blocking theme <script>
vite.config.ts                    # tanstackRouter() BEFORE react()
eslint.config.js                  # flat config with import/no-restricted-paths + semantic-token rule
tsconfig.json                     # strict + path alias @/* → ./src/*
components.json                   # style=new-york, baseColor=neutral, registries.@reui
.env.development                  # VITE_API_MODE=mock
```

### Pattern 1: TanStack Router + Query context injection [CITED: tanstack/query + tanstack/router docs]

Plumb `queryClient` and `session` into the router context so every `beforeLoad` and `loader` can reach them without singletons.

```ts
// src/app/router.ts
import { createRouter } from '@tanstack/react-router'
import { routeTree } from '@/routeTree.gen'
import { queryClient } from './queryClient'
import { useSessionStore } from '@/shared/session/store'

export const router = createRouter({
  routeTree,
  context: {
    queryClient,
    // session is looked up at guard time, not frozen at create time
    getSession: () => useSessionStore.getState(),
  },
  defaultPreload: 'intent',
  defaultPreloadStaleTime: 0, // let TanStack Query own the cache
})

declare module '@tanstack/react-router' {
  interface Register { router: typeof router }
}
```

### Pattern 2: Role guard via `beforeLoad` [CITED: tanstack/router auth-and-guards skill]

```tsx
// src/routes/_owner.tsx  (pathless layout route — wraps owner-only children)
import { createFileRoute, redirect } from '@tanstack/react-router'
import { can } from '@/shared/session/can'

export const Route = createFileRoute('/_owner')({
  beforeLoad: ({ context, location }) => {
    const { role } = context.getSession()
    if (!can(role, 'view', 'owner-area')) {
      throw redirect({ to: '/', search: { forbidden: location.href } })
    }
  },
})
```

### Pattern 3: Loader + hook share one query key [CITED: tanstack/query prefetching docs]

```ts
// src/features/clients/api/keys.ts (Phase 2 will populate; skeleton in Phase 1)
export const clientKeys = {
  all: ['clients'] as const,
  list: (params: ListParams) => ['clients', 'list', params] as const,
}

// Route:
loader: ({ context }) =>
  context.queryClient.ensureQueryData({
    queryKey: clientKeys.list(defaultParams),
    queryFn: () => services.clients.list(defaultParams),
  }),

// Hook (in component):
useQuery({ queryKey: clientKeys.list(params), queryFn: () => services.clients.list(params) })
```

### Pattern 4: Zustand `persist` with version + partialize [CITED: zustand persist middleware docs]

```ts
// src/shared/session/store.ts
import { create } from 'zustand'
import { persist, createJSONStorage } from 'zustand/middleware'

export type Role = 'owner' | 'reception'
interface SessionState {
  role: Role
  setRole: (r: Role) => void
}

export const useSessionStore = create<SessionState>()(
  persist(
    (set) => ({
      role: 'owner',
      setRole: (role) => set({ role }),
    }),
    {
      name: 'sportzal:session:v1',           // versioned key matches mock DB convention
      storage: createJSONStorage(() => localStorage),
      version: 1,
      partialize: (s) => ({ role: s.role }),  // never persist functions / derived
      migrate: (state, fromVersion) => state, // future-proof seam
    }
  )
)
```

### Anti-patterns to avoid

- **Creating `queryClient` inside a component** — it will be recreated on every render / HMR and blow the cache. Create once at module scope in `app/queryClient.ts`.
- **Plumbing `queryClient` via React Context to loaders** — the loader runs outside React. Put it on the router `context` instead.
- **Persisting the entire session store** without `partialize` — Zustand will try to JSON-serialize `setRole`, which is a function.
- **Putting `ThemeProvider` above `QueryClientProvider` and doing async work in it** — the FOUC script on `<html>` already handled paint; the provider is now a pure React concern.
- **Hand-editing `src/shared/ui/*` shadcn components** — `CLAUDE.md` bans it. Wrap instead.
- **Registering ESLint rules in `.eslintrc.cjs`** — ESLint 9+ is flat config only unless `ESLINT_USE_FLAT_CONFIG=false` is set (don't).

---

## Don't Hand-Roll

| Problem | Don't build | Use instead | Why |
|---|---|---|---|
| Theme toggle with no FOUC | React `useEffect` to add `.dark` | Blocking `<script>` in `index.html` **plus** shadcn-style `ThemeProvider` | `useEffect` runs after first paint — guarantees a flash |
| Persisting role across reload | `localStorage.setItem` + `useEffect` | `zustand/middleware#persist` + `createJSONStorage` + `version` | Rehydration race, missing migration seam |
| RBAC in 5 places | `{role === 'owner' && …}` scattered | Single `can(role, action, resource)` + `routeRegistry` | Role drift is the #1 bug in admin CRMs |
| Currency formatting | Hand-writing `str.replace(/\./, ',')` | `Intl.NumberFormat('ru-RU', { style: 'currency', currency: 'RUB' })` | Includes NBSP + minor-unit handling free |
| RU plural 3-form | `if (n === 1) … else if (…)` | `Intl.PluralRules('ru-RU').select(n)` → `one/few/many/other` | Russian has 3 forms (1 / 2-4 / 5+); edge cases at 11, 21, 101 |
| Phone mask `+7 (XXX) XXX-XX-XX` | regex on blur | Uses `imask` or phone component from reui (Phone Input) | Caret jumping, paste from `8…` |
| Router-Query integration | Manual prefetch + `useEffect` | `context.queryClient.ensureQueryData` inside `loader` | Dedups the fetch, keeps one cache |
| File-based routes | Manually wiring `createRootRoute`/`createRoute` | `@tanstack/router-plugin/vite` auto-generated `routeTree.gen.ts` | Codegen handles types; manual code bit-rots |
| Import boundary enforcement | Code review + PR comments | `eslint-plugin-import` `import/no-restricted-paths` | Static, runs on save |

**Key insight:** Phase 1 is a discipline installation phase. Everything above has exactly one right answer; let the tools enforce the rules so future phases can't accidentally skip them.

---

## Code Examples

All examples below are copy-ready. Sources are annotated.

### 1. `vite.config.ts` — plugin order matters [CITED: tanstack/router docs]

```ts
import { defineConfig } from 'vite'
import { tanstackRouter } from '@tanstack/router-plugin/vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import path from 'node:path'

export default defineConfig({
  plugins: [
    tanstackRouter({ target: 'react', autoCodeSplitting: true }), // MUST be before react()
    react(),
    tailwindcss(),
  ],
  resolve: {
    alias: { '@': path.resolve(__dirname, './src') },
  },
})
```

### 2. `index.html` — blocking theme script (no FOUC) [CITED: shadcn ThemeProvider pattern adapted for pre-React]

```html
<!DOCTYPE html>
<html lang="ru">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>SportZal</title>
    <script>
      // Runs synchronously before React bundle is parsed. Keep < 1 KB.
      (function () {
        try {
          var stored = localStorage.getItem('sportzal:ui:v1');
          var theme = 'system';
          if (stored) { try { theme = (JSON.parse(stored).state || {}).theme || 'system' } catch (_) {} }
          var resolved = theme === 'system'
            ? (window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light')
            : theme;
          if (resolved === 'dark') document.documentElement.classList.add('dark');
        } catch (_) { /* noop */ }
      })();
    </script>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/app/main.tsx"></script>
  </body>
</html>
```

### 3. `src/app/index.css` — Tailwind v4 + shadcn tokens (new-york, neutral) [CITED: ui.shadcn.com — Manual Install Tailwind v4]

> Base snippet from the shadcn manual-install doc; add reui extras (`--success`, `--warning`, `--info`, `--destructive-foreground`, `--invert`) — see §reui.io integration.

```css
@import "tailwindcss";
@import "tw-animate-css";

@custom-variant dark (&:is(.dark *));

@theme inline {
  --color-background: var(--background);
  --color-foreground: var(--foreground);
  --color-card: var(--card);
  /* ... full shadcn token set (see shadcn docs) ... */
  --color-sidebar: var(--sidebar);
  --radius-sm: calc(var(--radius) * 0.6);
  --radius-md: calc(var(--radius) * 0.8);
  --radius-lg: var(--radius);
  --radius-xl: calc(var(--radius) * 1.4);
}

:root {
  --radius: 0.625rem;
  --background: oklch(1 0 0);
  --foreground: oklch(0.145 0 0);
  /* ... neutral base palette (oklch) from shadcn default ... */
}

.dark {
  --background: oklch(0.145 0 0);
  --foreground: oklch(0.985 0 0);
  /* ... */
}

@layer base {
  * { @apply border-border outline-ring/50; }
  body { @apply bg-background text-foreground; }
}
```

### 4. `src/app/queryClient.ts` [CITED: tanstack/query v5 defaults]

```ts
import { QueryClient } from '@tanstack/react-query'

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      refetchOnWindowFocus: false,
      retry: 1,
    },
    mutations: { retry: 0 },
  },
})
```

### 5. `src/app/main.tsx`

```tsx
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { QueryClientProvider } from '@tanstack/react-query'
import { RouterProvider } from '@tanstack/react-router'
import { Toaster } from 'sonner'
import { queryClient } from './queryClient'
import { router } from './router'
import './index.css'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
      <Toaster position="top-right" richColors />
    </QueryClientProvider>
  </StrictMode>
)
```

### 6. `src/routes/__root.tsx` — AppShell layout

```tsx
import { createRootRouteWithContext, Outlet } from '@tanstack/react-router'
import type { QueryClient } from '@tanstack/react-query'
import type { SessionState } from '@/shared/session/store'
import { AppShell } from '@/shared/ui/app-shell'

interface RouterContext {
  queryClient: QueryClient
  getSession: () => SessionState
}

export const Route = createRootRouteWithContext<RouterContext>()({
  component: () => (
    <AppShell>
      <Outlet />
    </AppShell>
  ),
})
```

### 7. `components.json` (for shadcn CLI) [CITED: shadcn docs + reui.io/docs/get-started]

```json
{
  "$schema": "https://ui.shadcn.com/schema.json",
  "style": "new-york",
  "rsc": false,
  "tsx": true,
  "tailwind": {
    "css": "src/app/index.css",
    "baseColor": "neutral",
    "cssVariables": true
  },
  "aliases": {
    "components": "@/shared/ui",
    "utils": "@/shared/lib/cn",
    "ui": "@/shared/ui",
    "lib": "@/shared/lib",
    "hooks": "@/shared/lib/hooks"
  },
  "iconLibrary": "lucide",
  "registries": {
    "@reui": "https://reui.io/r/{style}/{name}.json"
  }
}
```

> ⚠️ See Open Question #1 below — reui documents `style: "base-nova"`. The planner must verify whether `new-york` resolves correctly against the reui registry, or whether reui-sourced components need a `style` override via the CLI.

### 8. `eslint.config.js` — flat config with boundary rules [CITED: eslint-plugin-import docs]

```js
import js from '@eslint/js'
import tseslint from 'typescript-eslint'
import importPlugin from 'eslint-plugin-import'

export default tseslint.config(
  js.configs.recommended,
  ...tseslint.configs.recommendedTypeChecked,
  importPlugin.flatConfigs.recommended,
  {
    languageOptions: {
      parserOptions: { projectService: true, tsconfigRootDir: import.meta.dirname },
    },
    settings: {
      'import/resolver': { typescript: true, node: true },
    },
    rules: {
      // FOUND-06: UI/features may not reach into mock/http impls directly.
      'import/no-restricted-paths': ['error', {
        zones: [
          {
            target: './src/{features,routes,entities,shared/ui}/**',
            from:   './src/shared/api/services/{mock,http}/**',
            message: 'Go through services container (shared/api/services/index.ts) or a TanStack Query hook.',
          },
          {
            target: './src/features/*/**',
            from:   './src/features/*/**',
            // allow same-feature imports only
            except: ['./src/features/{FEATURE}/**'],
            message: 'Features must not import other features; share via entities/ or shared/.',
          },
        ],
      }],
      // FOUND-07: ban raw palette classes in JSX className strings.
      'no-restricted-syntax': ['error', {
        selector: "JSXAttribute[name.name='className'] Literal[value=/\\b(bg|text|border|ring)-(white|black|slate|gray|zinc|neutral|stone|red|orange|amber|yellow|lime|green|emerald|teal|cyan|sky|blue|indigo|violet|purple|fuchsia|pink|rose)-\\d/]",
        message: 'Use semantic shadcn tokens (bg-background, text-muted-foreground, …) not raw Tailwind palette colors.',
      }],
    },
  },
)
```

### 9. `src/shared/session/registry.ts` + `can.ts`

```ts
// registry.ts
export type Resource =
  | 'dashboard' | 'clients' | 'schedule' | 'staff'
  | 'finance' | 'reports' | 'payroll' | 'compensation'
  | 'templates' | 'settings' | 'owner-area'
export type Action = 'view' | 'create' | 'edit' | 'delete' | 'refund'

export interface RouteEntry {
  path: string
  resource: Resource
  label: string           // Russian label for sidebar
  icon: string            // lucide icon name
}

export const routeRegistry: RouteEntry[] = [
  { path: '/',          resource: 'dashboard', label: 'Главная',     icon: 'LayoutDashboard' },
  { path: '/clients',   resource: 'clients',   label: 'Клиенты',     icon: 'Users' },
  { path: '/schedule',  resource: 'schedule',  label: 'Расписание',  icon: 'Calendar' },
  { path: '/staff',     resource: 'staff',     label: 'Сотрудники',  icon: 'UserCog' },
  { path: '/finance',   resource: 'finance',   label: 'Финансы',     icon: 'Wallet' },
  { path: '/settings',  resource: 'settings',  label: 'Настройки',   icon: 'Settings' },
]

// can.ts
import type { Role } from './store'
import type { Action, Resource } from './registry'

const OWNER_ONLY: Array<[Action, Resource]> = [
  ['view', 'finance'], ['view', 'reports'], ['view', 'payroll'],
  ['view', 'compensation'], ['view', 'templates'], ['view', 'settings'], ['view', 'owner-area'],
  ['delete', 'clients'], ['refund', 'finance'],
  ['edit', 'templates'], ['edit', 'compensation'],
]

export function can(role: Role, action: Action, resource: Resource): boolean {
  if (role === 'owner') return true
  // reception
  return !OWNER_ONLY.some(([a, r]) => a === action && r === resource)
}
```

### 10. `src/shared/session/RoleGate.tsx`

```tsx
import type { ReactNode } from 'react'
import { useSessionStore } from './store'
import { can, type Action, type Resource } from './can'

export function RoleGate({ action, resource, fallback = null, children }: {
  action: Action; resource: Resource; fallback?: ReactNode; children: ReactNode
}) {
  const role = useSessionStore((s) => s.role)
  return can(role, action, resource) ? <>{children}</> : <>{fallback}</>
}
```

### 11. Russian locale helpers `src/shared/i18n/ru.ts` + `src/shared/lib/money.ts`

```ts
// money.ts  —  kopecks → '1 234,56 ₽' with NBSP
const fmt = new Intl.NumberFormat('ru-RU', { style: 'currency', currency: 'RUB' })
export function formatMoney(minor: number): string {
  return fmt.format(minor / 100)
}

// date.ts  —  DD.MM.YYYY, 24h, Monday
import { format } from 'date-fns'
import { ru } from 'date-fns/locale'
export const DATE_FMT = 'dd.MM.yyyy'
export const TIME_FMT = 'HH:mm'
export function formatDate(iso: string): string {
  return format(new Date(iso), DATE_FMT, { locale: ru, weekStartsOn: 1 })
}

// plural.ts  —  3-form
const pr = new Intl.PluralRules('ru-RU')
export function plural(n: number, forms: { one: string; few: string; many: string }): string {
  const cat = pr.select(n) as 'one' | 'few' | 'many' | 'other'
  return forms[cat === 'other' ? 'many' : cat]
}
// usage: plural(n, { one: 'клиент', few: 'клиента', many: 'клиентов' })
```

### 12. `src/shared/api/services/index.ts` — swap seam (stub for Phase 1)

```ts
import type { ClientsService, ScheduleService, /* ... */ } from '../contracts'

const mode = (import.meta.env.VITE_API_MODE ?? 'mock') as 'mock' | 'http'

// Phase 1: both impls are empty stubs; Phase 2 fills mock, future flip adds http.
const impls =
  mode === 'http'
    ? await import('./http')
    : await import('./mock')

export const services = {
  clients: impls.clients as ClientsService,
  schedule: impls.schedule as ScheduleService,
  // ...
}
```

> Note: top-level `await` requires ESM target. Alternative: eager-import both and pick synchronously — pick one style and stick with it.

---

## reui.io Integration [CITED: reui.io/docs/get-started]

- **What reui is:** a first-class shadcn-compatible registry of enterprise components (Data Grid, Date Selector, Filters, Timeline, Stepper, Kanban, Phone Input, …), built for React 19 + Tailwind v4, shipped as both Base UI and Radix UI variants.
- **Registry entry (canonical):**
  ```json
  "registries": { "@reui": "https://reui.io/r/{style}/{name}.json" }
  ```
- **Install per component:** `pnpm dlx shadcn@latest add @reui/data-grid` (etc.)
- **Extra semantic tokens reui expects in your CSS (beyond shadcn defaults):**
  - `--destructive-foreground` (shadcn already ships `--destructive`; reui needs the paired foreground)
  - `--success` + `--success-foreground`
  - `--warning` + `--warning-foreground`
  - `--info` + `--info-foreground`
  - `--invert` + `--invert-foreground`
- **Dark mode:** reui reads the **same** `.dark` class + shared CSS vars as shadcn — no separate strategy.
- **Primitive choice:** reui ships Base UI **and** Radix UI variants for each component. Since shadcn (`new-york`) is Radix-based, **prefer the Radix variant** from reui for consistency (`@reui/radix/data-grid`, not `@reui/base/data-grid`). Verify exact namespace during install.

---

## Runtime State Inventory

*Not applicable.* Phase 1 is greenfield — no existing project-level runtime state to migrate or rename. (The only persisted state the phase *creates* is `localStorage['sportzal:session:v1']` and `localStorage['sportzal:ui:v1']`, which are intentional and versioned from day one.)

---

## Environment Availability

| Dependency | Required by | Available | Version policy | Fallback |
|---|---|---|---|---|
| Node.js | Vite build | ✓ (Node 20+ expected) | Vite 6 requires Node 18+; TanStack Router codegen works cleanly on 20+ | — |
| pnpm | Package manager | ✓ (pnpm 9 per CLAUDE.md) | — | npm/yarn would work but breaks lockfile consistency |
| Browser: modern evergreen | Runtime target | ✓ | `Intl.PluralRules`, `oklch()`, `matchMedia`, `localStorage`, container queries — all baseline since 2023 | None; IE/legacy are explicitly out |
| Git | Phase commits (commit_docs=true) | ✓ | — | — |

**Skip rationale:** Phase 1 has no external services (no DB, no backend, no Docker) — pure frontend scaffolding.

---

## Common Pitfalls

### Pitfall 1: Theme flash on reload
- **What goes wrong:** Dark-mode users see a bright flash for ~200 ms.
- **Why:** The React `ThemeProvider` only applies `.dark` inside a `useEffect` *after* first paint.
- **How to avoid:** Ship the blocking script in `index.html` (Example 2). The script reads localStorage + `matchMedia` and applies `.dark` to `<html>` **before** the bundle is parsed.
- **Warning sign:** Open DevTools → Network → "Slow 3G" → reload. If you see a flash, the script is broken or the `<script>` isn't in `<head>`.

### Pitfall 2: Persisted Zustand rehydration race
- **What goes wrong:** `useSessionStore` reads `role: 'owner'` on first render, then rehydrates to `role: 'reception'` on second render → router `beforeLoad` already ran with the wrong role, and the user sees a momentary owner sidebar.
- **Why:** `persist` rehydrates asynchronously by default.
- **How to avoid:** Two choices — (a) Accept the flash (fine for role; it's local demo, not security), or (b) use `skipHydration: true` + manually `useSessionStore.persist.rehydrate()` before mounting `<RouterProvider>`. Recommended (b) for production feel. [CITED: zustand docs]
- **Warning sign:** Refresh on a Reception-only route as Reception — if you momentarily see Owner nav, it's the race.

### Pitfall 3: Router + Query double-fetch
- **What goes wrong:** The route `loader` fetches, and the in-component `useQuery` also fetches → 2 requests.
- **Why:** Different query keys between `ensureQueryData` (loader) and `useQuery` (component).
- **How to avoid:** **Both** sides must use the **exact same** `queryKey` (hence the per-feature `xKeys` factory in `CLAUDE.md`). `defaultPreloadStaleTime: 0` on the router also defers freshness to TanStack Query. [CITED: tanstack/query prefetching docs]

### Pitfall 4: `components/ui/*` hand-edits
- **What goes wrong:** You tweak `components/ui/button.tsx`; next shadcn CLI update overwrites it silently.
- **Why:** shadcn re-writes files it recognizes as its own.
- **How to avoid:** Wrap in `shared/ui/Button.tsx`; add `// SHADCN-DIVERGENCE: …` comment if you must diverge.

### Pitfall 5: `VITE_API_MODE` branch leaking into components
- **What goes wrong:** Someone writes `if (import.meta.env.VITE_API_MODE === 'mock') …` inside a component.
- **Why:** It's easier than creating a service method.
- **How to avoid:** Add an ESLint rule: `no-restricted-syntax` for `MemberExpression[object.property.name='env'][property.name='VITE_API_MODE']` outside `shared/api/**`. Alternatively, `no-restricted-properties`.

### Pitfall 6: Raw palette classes slipping through
- **What goes wrong:** shadcn blocks you copy sometimes contain `bg-white` or `text-slate-900`.
- **Why:** shadcn docs examples use raw palette for brevity.
- **How to avoid:** The `no-restricted-syntax` rule in Example 8 flags them at install time. Run `pnpm lint` right after every `shadcn add`.

### Pitfall 7: `new Date('2026-04-21')` drift
- **What goes wrong:** Parsed as UTC; display date shifts one day in `Europe/Moscow` after DST boundaries are replaced by civilian confusion (MSK is UTC+3, no DST — but bugs hit anyway via server dates).
- **Why:** ISO date-only strings are UTC by spec.
- **How to avoid:** Never `new Date(dateOnlyString)` in domain code. Use `parseISO` from date-fns or a date-only wrapper. Pin TZ explicitly.

### Pitfall 8: TanStack Router plugin order
- **What goes wrong:** Routes don't hot-reload; `routeTree.gen.ts` is stale.
- **Why:** `@vitejs/plugin-react` runs before `@tanstack/router-plugin/vite` and eats the file-system event.
- **How to avoid:** `tanstackRouter()` **must** come **before** `react()` in `vite.config.ts`. [CITED: tanstack/router install docs]

### Pitfall 9: Responsive at 1366×768
- **What goes wrong:** The shadcn `sidebar-07` block defaults to `w-64` expanded — on 1366-wide screens this leaves ~1100 px for content, which is fine but feels cramped for DataTables.
- **How to avoid:** Default sidebar to collapsed at `< 1536 px` (shadcn `Sidebar` supports `defaultOpen={false}` + `<SidebarTrigger>`). Test key screens (Clients list, Schedule week) at exactly 1366×768.

---

## Validation Architecture

Phase 1 is scaffolding-heavy; most FOUND-* requirements are visual/structural. Per `.planning/config.json` nothing disables `nyquist_validation`, so include a lightweight test scaffold.

### Test Framework
| Property | Value |
|---|---|
| Framework | Vitest (latest); `jsdom` environment for DOM tests |
| Config file | `vitest.config.ts` (Wave 0 creates it) |
| Quick run | `pnpm test --run` |
| Full suite | `pnpm test --run && pnpm typecheck && pnpm lint` |

### Phase Requirements → Test Map

| Req | Behavior | Test type | Automated command | File exists? |
|---|---|---|---|---|
| FOUND-01 | AppShell renders top bar + sidebar + content | smoke (RTL) | `pnpm test -- app-shell` | ❌ Wave 0 |
| FOUND-02 | Role toggle persists to localStorage key `sportzal:session:v1` | unit | `pnpm test -- session-store` | ❌ Wave 0 |
| FOUND-03 | Blocking script adds `.dark` when stored theme='dark' | unit (jsdom mock) | `pnpm test -- theme-bootstrap` | ❌ Wave 0 |
| FOUND-04 | `formatMoney(123456)` → `'1 234,56 ₽'` (NBSP); `plural(2, …)` → `'клиента'` | unit | `pnpm test -- i18n` | ❌ Wave 0 |
| FOUND-05 | Typed `routeTree.gen.ts` generated; root route has AppShell layout | typecheck | `pnpm typecheck` | ✓ |
| FOUND-06 | ESLint flags a component importing from `services/mock/**` | lint fixture | `pnpm lint` against fixture | ❌ Wave 0 |
| FOUND-07 | ESLint flags `className="bg-white"` | lint fixture | `pnpm lint` against fixture | ❌ Wave 0 |
| ROLE-01 | `can('reception', 'view', 'finance')` is `false`; `can('owner', …)` is `true` | unit | `pnpm test -- can` | ❌ Wave 0 |
| ROLE-02/03 | table-driven `can()` coverage | unit (table test) | `pnpm test -- can` | ❌ Wave 0 |
| ROLE-04 | `can('reception', 'delete', 'clients')` false; `can('reception', 'refund', 'finance')` false | unit | `pnpm test -- can` | ❌ Wave 0 |
| ROLE-05 | Replacing session source (mocked) leaves `can()` outputs unchanged | unit | `pnpm test -- session-swap` | ❌ Wave 0 |
| UI-03 | `components.json` validates against JSON schema; `@reui` registry entry present | schema/unit | `pnpm test -- components-json` | ❌ Wave 0 |
| UI-04 | Playwright/Vitest jsdom viewport 1366×768: sidebar collapses and content fits | smoke | `pnpm test -- responsive-1366` | ❌ Wave 0 (or manual) |

### Sampling rate
- **Per task commit:** `pnpm test --run` (< 5 s with this scaffold).
- **Per wave merge:** `pnpm test --run && pnpm typecheck && pnpm lint`.
- **Phase gate:** full suite green + manual smoke at 1366×768 in both light and dark themes.

### Wave 0 gaps
- [ ] `vitest.config.ts` + `src/test/setup.ts` (jsdom, RTL matchers)
- [ ] `src/shared/session/can.test.ts`
- [ ] `src/shared/session/store.test.ts`
- [ ] `src/shared/lib/money.test.ts` + `src/shared/i18n/plural.test.ts`
- [ ] `src/app/providers/theme-bootstrap.test.ts` (simulate `localStorage` + run the blocking script snippet)
- [ ] ESLint fixture directory `src/__fixtures/eslint-violations/` with 2 files + a CI check that `pnpm lint` exits non-zero on them
- [ ] `components.json` schema-validation test
- [ ] (Optional) Playwright smoke for 1366×768 responsive layout; can be deferred to Phase 7 polish if time-boxed

---

## Security Domain

`.planning/config.json` does not set `security_enforcement: false`, so include ASVS mapping.

### Applicable ASVS categories (for a v1 frontend-only mock app)

| ASVS | Applies | Standard control |
|---|---|---|
| V2 Authentication | no | No real auth in v1; role is UI toggle. Flag: document `"this is not auth"` in README. |
| V3 Session Management | partial | The Zustand persisted store **is not a security boundary** — it's a UX preference. Phase 1 must not let it be mistaken for one. |
| V4 Access Control | yes (design) | `can()` is central; mock services also enforce (Phase 2+). **Client-side hiding alone is never security.** |
| V5 Input Validation | partial (Phase 2 territory) | Zod schemas land in Phase 2; Phase 1 only needs env var typing via `import.meta.env.VITE_API_MODE` narrowing. |
| V6 Cryptography | no | No secrets in v1. Never store tokens in localStorage even when http mode lands — plan for HttpOnly cookies. |

### Known threat patterns for this stack

| Pattern | STRIDE | Mitigation |
|---|---|---|
| XSS via dangerouslySetInnerHTML | Tampering | Ban via ESLint `react/no-danger`; document why. |
| localStorage tampering (user flips role to 'owner') | EoP | **Accepted risk in v1**: role is UX state. When real auth ships, role comes from the JWT claim, not localStorage. Document this contract in `shared/session/README.md`. |
| Supply-chain (malicious @reui package) | Tampering | Pin package versions via `pnpm-lock.yaml`; `pnpm audit` in CI. |
| CSP | Info disclosure | Phase 1: add a baseline `Content-Security-Policy` meta tag (or Vite plugin) allowing self + inline script for the FOUC bootstrapper (`'unsafe-inline'` for that one script, or use nonce). — [ASSUMED] baseline; revisit in Phase 7 polish. |

---

## State of the Art (for this stack slice)

| Old approach | Current (2026-04) | Changed | Impact |
|---|---|---|---|
| Tailwind v3 `tailwind.config.ts` + JIT | **Tailwind v4 `@theme` in CSS, zero JS config** | v4.0 (2025) | `tailwind.config.js` is optional; `components.json` no longer writes one |
| shadcn `globals.css` + `tailwind.config.ts` | **Single `index.css` with `@theme inline` + `:root`/`.dark`** | shadcn v2 (2024) → v3/v4 CLI (2025+) | One block to edit |
| `@tanstack/router` old `createRoute` manual tree | **File-based via `@tanstack/router-plugin`** | 2024 | Codegen generates `routeTree.gen.ts`; delete hand-written route modules |
| React Query `cacheTime` | **`gcTime`** (v5) | v5.0 | Rename if migrating from v4 |
| ESLint `.eslintrc.cjs` | **Flat `eslint.config.js`** | v9 default (2024), mandatory v10 | No more `extends:` strings; compose configs as arrays |
| Sonner `<Toaster richColors />` defaults | unchanged; sonner v2 raised peer-deps | 2025 | No migration needed |

### Deprecated / outdated
- `clsx` alone — pair with `tailwind-merge` (`cn()`).
- `class-variance-authority` is still current but shadcn `new-york` leans on simple variants in CSS now; use where helpful, not reflexively.
- `tailwindcss-animate` → now `tw-animate-css` per shadcn's v4 manual install [CITED: shadcn manual install Tailwind v4].

---

## Assumptions Log

| # | Claim | Section | Risk if wrong |
|---|---|---|---|
| A1 | `tw-animate-css` is the current shadcn-recommended animation CSS import (v4) | §Code Examples / §State of the Art | LOW — snippet sourced from shadcn manual-install docs [CITED], but the package name changed once already in v4 history |
| A2 | reui's `style: "base-nova"` is an **override**, not a required global style — a `new-york` project can still consume reui components via the `{style}` URL variable | §reui.io Integration / OQ#1 | MEDIUM — if wrong, we'd need to add per-component `--style` flag at install or maintain two styles. See OQ#1 |
| A3 | `pnpm dlx shadcn@latest add @reui/radix/data-grid` is the exact CLI invocation | §reui.io Integration | LOW — standard shadcn namespaced-registry syntax, but reui may use a different path (e.g. `@reui/data-grid-radix`). Verify with one real install in Phase 1 |
| A4 | CSP `unsafe-inline` is acceptable for the pre-React theme bootstrap script in v1 | §Security Domain | LOW — v1 is internal mock; can be replaced with nonce/hash in Phase 7 |
| A5 | `oklch(...)` color tokens render identically in all evergreen browsers the team targets | §Code Examples | LOW — supported since 2023 across Chromium/Firefox/Safari, safe for admin target |
| A6 | Node 20+ is the runtime the team will use (no Node 18-only constraint) | §Environment Availability | LOW — confirm with user; affects Vite/TanStack plugin compatibility |

---

## Open Questions (for planner + discuss-phase)

1. **reui.io `style` conflict with shadcn `new-york`.** The reui get-started doc shows `"style": "base-nova"` paired with `"registries": { "@reui": "https://reui.io/r/{style}/{name}.json" }`. Our project locks shadcn `style: "new-york"`. Under shadcn's namespaced-registry contract, the `{style}` URL variable interpolates the global `components.json` style. Two possible resolutions:
   - (a) reui publishes under multiple style paths, so `/r/new-york/data-grid.json` resolves. → verify by `curl https://reui.io/r/new-york/data-grid.json`.
   - (b) reui only publishes under `base-nova`, so we need to override at add-time: `pnpm dlx shadcn@latest add @reui/data-grid --style base-nova` (if the CLI supports it) or use a secondary components.json section.
   Decision needed before Phase 1 closes. **Tag:** DISCUSS-PHASE-1 — this is OQ#15 from the project-level research summary.
2. **Rehydration timing for `useSessionStore`.** Accept the tiny flash (default async rehydrate) or block mount (`skipHydration: true` + manual `persist.rehydrate()` before `<RouterProvider>`)? Recommend blocking for production feel; pick one.
3. **Top-level await in `services/index.ts`.** Cleaner pattern but couples to ESM target and can pessimize bundle splitting. Alternative: eager import both impls (both stubs in Phase 1, one full in Phase 2) and branch on `mode`. Both impls tree-shake only if completely unreferenced after dead-code elimination.
4. **Responsive QA at 1366×768.** Phase 1 ships the shell; UI-04 wants this working. Pick the default sidebar breakpoint (collapse below `2xl`?) and document it in `AppShell`.
5. **Theme persistence key naming.** `sportzal:ui:v1` for `{ theme }` or combine with session into one key? Recommend separate: theme rehydrates synchronously (via blocking script), role rehydrates async.
6. **Path alias style.** `@/…` is conventional but `~/…` avoids conflicts with npm org scopes. `CLAUDE.md` doesn't pin this; recommend `@/…`.

---

## Sources

### Primary (HIGH confidence)
- **Context7 `/websites/ui_shadcn`** — topics fetched: Vite install, Tailwind v4 `@theme inline`, components.json, dark mode, registries (`@reui` namespace), ThemeProvider pattern.
- **Context7 `/tanstack/router`** — topics fetched: Vite plugin setup, file-based routing, `beforeLoad`/`redirect` auth guard pattern, loader+query integration.
- **Context7 `/tanstack/query`** — topics fetched: `QueryClient` defaults (`staleTime`), `ensureQueryData` for route loaders, router integration.
- **Context7 `/pmndrs/zustand`** — topics fetched: `persist` + `createJSONStorage`, `partialize`, `version`+`migrate`, `skipHydration`.
- **Context7 `/eslint/eslint`** — topics fetched: flat config shape (v9/v10).
- **npm registry** (`npm view`) — latest versions as of 2026-04-21 for all core packages.
- **reui.io `llms.txt` + `/docs/get-started` (curl)** — components.json registry entry, extra semantic tokens, primitive-agnostic (Base UI + Radix UI).

### Secondary (MEDIUM)
- `.planning/research/{STACK,ARCHITECTURE,PITFALLS}.md` — prior synthesized research.
- `CLAUDE.md` — locked stack, architecture non-negotiables, conventions.

### Tertiary (LOW — flagged for validation)
- Exact reui.io CLI per-component path (`@reui/radix/...` vs `@reui/...`) — verify with a real install during Phase 1.

---

## Metadata

**Confidence breakdown:**
- Stack versions & install: **HIGH** — verified against Context7 and npm registry on research day.
- Router + Query integration: **HIGH** — official docs pattern.
- Theme bootstrap (no-FOUC): **HIGH** — standard blocking-script pattern adapted for shadcn.
- Zustand persist (versioned, partial): **HIGH** — directly from docs.
- ESLint flat config boundary rules: **MEDIUM-HIGH** — pattern is canonical; exact regex for palette classes may need refinement once real shadcn components land.
- Russian locale helpers: **HIGH** — built on `Intl.*` standard APIs.
- reui.io integration specifics: **MEDIUM** — registry entry confirmed, but `style` interop with shadcn `new-york` is OQ#1.
- RBAC module design: **HIGH** — plain functions, testable, easy to swap.

**Research date:** 2026-04-21
**Valid until:** ~2026-05-21 (30 days) for stable areas; reui.io specifics should be re-checked on the day of install (fast-moving, MEDIUM).
