# Plan 004: Split the 1.44 MB bundle by route with the router's native lazy loading

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update the status row for this plan
> in `plans/README.md`.
>
> **Drift check (run first)**: `git diff --stat <baseline SHA from plans/README.md>..HEAD -- src/app/router.tsx vite.config.ts src/app/router-smoke.test.tsx`
> If `router.tsx` changed since baseline (plan 002 exports `routeConfig` from it
> — that change is expected and assumed here), re-read it fully before editing;
> if the route tree itself differs from the excerpt below, STOP.

## Status

- **Priority**: P1
- **Effort**: M
- **Risk**: MED
- **Depends on**: plans/002-vitest-baseline.md (route smoke tests are the regression gate; it also exports `routeConfig` this plan edits)
- **Category**: perf
- **Planned at**: 2026-06-12 (pre-git; baseline SHA in plans/README.md)

## Why this matters

The production build is a single 1,510,376-byte JS chunk (`dist/assets/index-*.js`, measured 2026-06-12) plus 306 KB CSS, because `src/app/router.tsx` statically imports all ~25 page components. Every visitor — including someone opening only `/login` — downloads recharts, cmdk, the full modal set, and every page. Route-level lazy loading lets Vite split each page (and shared heavy deps like recharts) into on-demand chunks, cutting the entry chunk by roughly half or more. React Router v6's data-router `lazy` route property is the right mechanism here: no `<Suspense>` plumbing, and during client-side navigation the current page stays visible while the next chunk loads.

## Current state

- `src/app/router.tsx` — after plan 002 it exports `routeConfig: RouteObject[]` and `router = createBrowserRouter(routeConfig)`. The file begins with ~25 static page imports (verbatim, first lines):

  ```tsx
  import { createBrowserRouter, Navigate } from 'react-router-dom';
  import { AppLayout } from '@/layouts/AppLayout/AppLayout';
  import { ROUTES } from './routes';
  import { DashboardPage } from '@/pages/dashboard/DashboardPage';
  import { ClientsPage } from '@/pages/clients/ClientsPage';
  // ... ~20 more page imports ...
  import { LoginPage } from '@/pages/login/LoginPage';
  import { ErrorPage } from '@/components/feedback/ErrorPage';
  import { RouteErrorBoundary } from '@/components/feedback/RouteErrorBoundary';
  ```

  and routes shaped like:

  ```tsx
  { path: ROUTES.dashboard, element: <DashboardPage /> },
  { path: ROUTES.client(), element: <ClientPage /> },
  {
    path: ROUTES.roles,
    element: <RolesPage />,
    handle: { breadcrumb: ['Настройки', 'Роли и права'] },
  },
  ```

- **Every page component is a named export** (e.g. `export function DashboardPage`), so dynamic imports must map the name to `Component`.
- `vite.config.ts` — no `build` section at all today (only plugins/resolve/optimizeDeps/server). React 18.3, Vite 5.4.
- The router mounts via `<RouterProvider router={router} />` in `src/App.tsx`.
- Routes that must stay EAGER (small, or needed before any chunk loads): `AppLayout`, `RouteErrorBoundary`, `ErrorPage` (it's the 404/500 fallback inside and outside the layout), the `/index.html` → `Navigate` redirect. `LoginPage` may be lazy like the rest.

## Commands you will need

| Purpose    | Command             | Expected on success                |
|------------|---------------------|------------------------------------|
| Typecheck  | `bun run typecheck` | exit 0                             |
| Lint       | `bun run lint`      | exit 0                             |
| Tests      | `bun run test`      | all pass (incl. 20 route smokes)   |
| Build      | `bun run build`     | exit 0, multiple JS chunks emitted |
| Entry size | see Step 4          | entry chunk < 900,000 bytes        |

## Scope

**In scope**:
- `src/app/router.tsx`
- `vite.config.ts` (ONLY if the Step 4 size gate fails — see Step 5)
- `src/app/router-smoke.test.tsx` (assertion timing tweaks only, if needed)
- `plans/README.md` (status row)

**Out of scope** (do NOT touch):
- Page components themselves — no default-export rewrites; the `lazy` mapping handles named exports.
- `src/layouts/AppLayout/**` — no Suspense insertion needed with route-level `lazy`.
- `src/App.tsx` / `src/main.tsx`.
- `index.html`, `dist/` contents (build output only via `bun run build`).

## Git workflow

- Branch: `advisor/004-route-splitting` off `main`.
- Commits: (1) lazy conversion of routes, (2) optional vite manualChunks if Step 5 was needed. Messages: `perf: lazy-load route pages`, `perf: split recharts into a manual chunk`.
- Do NOT push.

## Steps

### Step 1: Convert page routes to `lazy`

In `src/app/router.tsx`:

1. Delete the static imports of all page components (every `import { XxxPage } from '@/pages/...'` line). KEEP the imports of `AppLayout`, `ROUTES`, `ErrorPage`, `RouteErrorBoundary`, `Navigate`, `createBrowserRouter`, `RouteObject`.
2. Replace each `element: <XxxPage />` with the data-router `lazy` property, preserving `path` and `handle` untouched. Pattern (apply to every page route, ~22 of them):

   ```tsx
   // БЫЛО:
   { path: ROUTES.dashboard, element: <DashboardPage /> },
   // СТАЛО:
   {
     path: ROUTES.dashboard,
     lazy: async () => ({
       Component: (await import('@/pages/dashboard/DashboardPage')).DashboardPage,
     }),
   },
   ```

   Routes with `handle` keep it as a sibling of `lazy`:

   ```tsx
   {
     path: ROUTES.roles,
     lazy: async () => ({
       Component: (await import('@/pages/roles/RolesPage')).RolesPage,
     }),
     handle: { breadcrumb: ['Настройки', 'Роли и права'] },
   },
   ```

3. Keep eager: the `AppLayout` wrapper route (`element: <AppLayout />`, `errorElement: <RouteErrorBoundary />`), both `ErrorPage` usages (`/error` and the `'*'` 404), and the `/index.html` Navigate redirect. Convert `LoginPage` to lazy like the rest.

**Verify**: `bun run typecheck` → exit 0; `grep -c "from '@/pages/" src/app/router.tsx` → **0**; `grep -c "lazy: async" src/app/router.tsx` → ≥ 20.

### Step 2: Lint and fix import-shape fallout

`bun run lint` → exit 0. (Likely clean; if `consistent-type-imports` flags the `RouteObject` import, use `import { createBrowserRouter, Navigate, type RouteObject } from 'react-router-dom';`.)

### Step 3: Run the route smoke tests

`bun run test` → the 20-route smoke suite must pass unchanged. The `findBy*` queries already await lazy resolution. If a smoke test times out, raise that single test's timeout to 10s (`it(path, async () => {...}, 10_000)`) rather than weakening the assertion.

**Verify**: `bun run test` → exit 0.

### Step 4: Build and measure

```
bun run build
ENTRY=$(grep -o 'assets/index-[^"]*\.js' dist/index.html | head -1)
stat -f%z "dist/$ENTRY"
ls dist/assets/*.js | wc -l
```

**Verify**: build exits 0; JS chunk count ≥ 8; entry chunk size **< 900,000 bytes** (baseline was 1,510,376). Record both numbers in your summary.

### Step 5 (conditional): manualChunks for recharts

ONLY if the entry chunk is still ≥ 900,000 bytes: add to `vite.config.ts`:

```ts
build: {
  rollupOptions: {
    output: {
      manualChunks: {
        recharts: ['recharts'],
      },
    },
  },
},
```

Rebuild and re-measure (Step 4 commands). If the gate STILL fails, STOP and report the chunk breakdown (`ls -laS dist/assets/*.js | head`) — something else dominates the entry and needs a human decision.

## Test plan

- Regression: the plan-002 smoke suite (every route renders through real providers) — this is the primary gate; lazy mistakes (wrong export name in a mapping) fail the exact route's smoke test with a clear error.
- Build-output assertions in Step 4 are the perf acceptance test.
- Optional manual check if a preview is available: `bun run preview`, navigate `/` → `/clients` → `/reports`; the Network tab should show per-route chunks loading on first visit and no full-page flash on navigation.

## Done criteria

ALL must hold:

- [ ] `grep -c "from '@/pages/" src/app/router.tsx` → 0
- [ ] `bun run typecheck` → exit 0
- [ ] `bun run lint` → exit 0
- [ ] `bun run test` → exit 0 (all smoke routes)
- [ ] `bun run build` → exit 0; ≥ 8 JS chunks in `dist/assets/`
- [ ] Entry chunk (the one referenced by `dist/index.html`) < 900,000 bytes
- [ ] `git status --porcelain` shows only in-scope files
- [ ] `plans/README.md` row updated (include before/after entry sizes in the status note)

## STOP conditions

Stop and report back (do not improvise) if:

- `router.tsx` does not export `routeConfig` (plan 002 not executed) — this plan assumes it; report the dependency violation.
- Any page module turns out to have side effects relied on at startup (e.g. something imports a page for a type/constant) — `grep -rn "from '@/pages/" src --include='*.ts*'` should return only page-internal imports; if a non-page file imports a page module, report it.
- A smoke route fails after conversion and the fix isn't an obvious export-name typo in the `lazy` mapping.
- The Step 5 fallback still can't get the entry under 900 KB.

## Maintenance notes

- Future routes (e.g. plan 011's archive/duplicates pages) must use the same `lazy:` pattern — plan 008 documents it in CLAUDE.md.
- `optimizeDeps.include: ['sonner', 'vaul']` in `vite.config.ts` is dev-server-only; unrelated to build chunking — don't "clean it up".
- Reviewer focus: each `lazy` mapping's export name matches the page's actual named export (a typo here compiles if the page has multiple exports, then 404s at runtime — the smoke suite catches it, so make sure it ran).
- Deferred: prefetching chunks on nav-link hover; `fallbackElement` on `RouterProvider` for the initial load (currently a brief blank before the first chunk — acceptable; revisit with product input).
