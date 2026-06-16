# Plan 002: Establish a vitest verification baseline (pure logic + route smoke tests)

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update the status row for this plan
> in `plans/README.md`.
>
> **Drift check (run first)**: `git diff --stat <baseline SHA from plans/README.md>..HEAD -- src/lib/format.ts src/pages/clients/ClientsPage.tsx src/app/router.tsx package.json`
> If any of these changed since the baseline, compare the "Current state"
> excerpts below against the live code before proceeding; on a mismatch,
> treat it as a STOP condition.

## Status

- **Priority**: P1
- **Effort**: M
- **Risk**: LOW
- **Depends on**: plans/001-init-git-baseline.md
- **Category**: tests
- **Planned at**: 2026-06-12 (pre-git; baseline SHA in plans/README.md)

## Why this matters

The repo has zero tests and no test runner — verification today is `typecheck` + `lint` + manual preview. That was a deliberate deferral, but plans 003–009 refactor the router, ~20 pages, and shared components; doing that without an automated safety net is gambling. This plan installs vitest and writes a small, high-value baseline: unit tests for the pure logic most likely to harbor real bugs (Russian pluralization, the client-list sort comparator), and a smoke test that renders every registered route. It is the prerequisite gate for plans 004 (router surgery) and 009 (component consolidation).

## Current state

- **No test infra**: `package.json` has no `test` script; no `vitest`/`@testing-library/*` in devDependencies; `find src -name '*.test.*'` returns nothing.
- **Stack**: React 18.3, TypeScript 5.7 strict, Vite 5.4, Bun as package manager. TanStack Query v5 hooks resolve mock data instantly (`mockResponse(value, delay = 0)` in `src/api/client.ts:34-36`), so rendered pages reach their data state after a microtask+timer tick — `findBy*` queries handle this.
- **Important**: `bun test` invokes Bun's OWN test runner, which will NOT pick up vitest config. Always use `bun run test` (the npm script, which runs vitest).

- `src/lib/format.ts:41-47` — Russian pluralization, the top unit-test target (verbatim):

  ```ts
  /** Русская плюрализация: forms = [один, два-четыре, пять]. */
  export function pluralRu(n: number, forms: [string, string, string]): string {
    const n10 = n % 10;
    const n100 = n % 100;
    if (n10 === 1 && n100 !== 11) return forms[0];
    if (n10 >= 2 && n10 <= 4 && (n100 < 10 || n100 >= 20)) return forms[1];
    return forms[2];
  }
  ```

  The same file exports `formatRub`, `formatInt`, `formatDateRu`, `formatWeekdayLongRu`, `formatRelativeRu`, `formatTime` — all wrap `Intl`/`date-fns` with the `ru` locale. **Locale gotcha**: `Intl` with `ru-RU` uses non-breaking spaces (` `, and in some ICU versions narrow NBSP ` `) as group separators. Assertions must normalize: `value.replace(/[  ]/g, ' ')`.

- `src/pages/clients/ClientsPage.tsx:17-43` — sort comparator currently module-private inside the page component (verbatim):

  ```ts
  const DEFAULT_DIR: Record<ClientSortKey, ClientSort['dir']> = {
    name: 'asc',
    expires: 'asc',
    visits: 'desc',
    last: 'desc',
  };

  function compare(a: Client, b: Client, sort: ClientSort): number {
    const m = sort.dir === 'asc' ? 1 : -1;
    switch (sort.key) {
      case 'name':
        return a.name.localeCompare(b.name, 'ru') * m;
      case 'visits':
        return (a.visits.month - b.visits.month) * m;
      case 'last':
        return (a.lastVisit.rank - b.lastVisit.rank) * m;
      case 'expires': {
        const av = a.expiry?.daysLeft;
        const bv = b.expiry?.daysLeft;
        // Лиды (без срока) — всегда в конце, независимо от направления.
        if (av == null && bv == null) return 0;
        if (av == null) return 1;
        if (bv == null) return -1;
        return (av - bv) * m;
      }
    }
  }
  ```

  To test it, this plan extracts it (unchanged) to `src/features/clients/sort.ts`. Types `Client`, `ClientSort`, `ClientSortKey` come from `src/features/clients/types.ts` (already imported by the page).

- `src/app/router.tsx:39-103` — `export const router = createBrowserRouter([...])` with the route tree inline. For the smoke test the route array must be exported separately (Step 4). Routes use path constants from `src/app/routes.ts` (`ROUTES`).
- `src/App.tsx` — `<Providers><RouterProvider router={router} /></Providers>`. `src/app/providers.tsx` wraps `QueryClientProvider` (client from `src/api/query-client.ts`) + Radix `TooltipProvider` + `ModalsProvider`.
- **jsdom stubs needed**: pages use Recharts (`ResizeObserver`), `src/components/settings/ScrollspyNav.tsx` (`IntersectionObserver`), `src/hooks/use-mobile.ts` (`matchMedia`), and smooth scrolling (`Element.prototype.scrollIntoView`). jsdom provides none of these — the setup file must stub all four or chart/settings pages will throw.
- **Convention**: path alias `@/*` → `src/*` (defined in root `tsconfig.json` and `vite.config.ts`). The vitest config must replicate the alias. TS uses `verbatimModuleSyntax` — type-only imports must be `import type`.

## Commands you will need

| Purpose   | Command                          | Expected on success |
|-----------|----------------------------------|---------------------|
| Install   | `bun install`                    | exit 0              |
| Add deps  | `bun add -d <pkgs>` (Step 1)     | exit 0              |
| Typecheck | `bun run typecheck`              | exit 0              |
| Lint      | `bun run lint`                   | exit 0              |
| Tests     | `bun run test`                   | all pass            |

## Scope

**In scope** (only these files):
- `package.json` (devDependencies + `test` / `test:watch` scripts)
- `bun.lock` (regenerated by bun)
- `vitest.config.ts` (create)
- `src/test/setup.ts` (create)
- `src/lib/format.test.ts` (create)
- `src/features/clients/sort.ts` (create — extraction target)
- `src/features/clients/sort.test.ts` (create)
- `src/pages/clients/ClientsPage.tsx` (remove the extracted comparator, import it instead)
- `src/app/router.tsx` (export the route array; no behavioral change)
- `src/app/router-smoke.test.tsx` (create)
- `plans/README.md` (status row)

**Out of scope** (do NOT touch):
- `tsconfig*.json` — the existing config already covers `src/` including test files; do not add a separate test tsconfig.
- Any page/component beyond the two named refactors. No "while I'm here" fixes.
- `eslint.config.js` — only touch if lint fails on test files for a rule reason; then add a minimal override for `**/*.test.*` and report it in your summary.
- CI configuration — none exists; do not create one.

## Git workflow

- Branch: `advisor/002-vitest-baseline` off `main`.
- Commit per step (5 commits): deps, config+setup, format tests, sort extraction+tests, router export+smoke.
- Message style: `test: <what>` / `refactor: <what>` (the repo has no history to match yet — use conventional commits).
- Do NOT push.

## Steps

### Step 1: Install test dependencies

Run:

```
bun add -d vitest@^3 @testing-library/react@^16 @testing-library/jest-dom@^6 @testing-library/user-event@^14 jsdom@^26
```

Note: vitest ships its own vite internally; pinning `vitest@^3` avoids peer friction with the project's Vite 5. Do NOT add `@vitejs/plugin-react` to the vitest config — vitest's esbuild handles TSX via the repo's `jsx: react-jsx` tsconfig setting; the plugin is only needed for HMR, which tests don't use.

Add scripts to `package.json` (keep existing ones untouched):

```json
"test": "vitest run",
"test:watch": "vitest"
```

**Verify**: `bun run test 2>&1 | tail -3` → vitest runs and reports "No test files found" (exit code may be 1 — that is expected at this step).

### Step 2: Create `vitest.config.ts` and `src/test/setup.ts`

`vitest.config.ts`:

```ts
import { defineConfig } from 'vitest/config';
import path from 'node:path';

export default defineConfig({
  resolve: {
    alias: { '@': path.resolve(__dirname, 'src') },
  },
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
    css: false,
  },
});
```

`src/test/setup.ts`:

```ts
import '@testing-library/jest-dom/vitest';

// jsdom не реализует эти API; страницы (Recharts, ScrollspyNav, use-mobile)
// требуют их при монтировании.
class ResizeObserverStub {
  observe() {}
  unobserve() {}
  disconnect() {}
}
class IntersectionObserverStub {
  observe() {}
  unobserve() {}
  disconnect() {}
  takeRecords() {
    return [];
  }
}
globalThis.ResizeObserver = ResizeObserverStub as unknown as typeof ResizeObserver;
globalThis.IntersectionObserver = IntersectionObserverStub as unknown as typeof IntersectionObserver;

if (!window.matchMedia) {
  window.matchMedia = ((query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: () => {},
    removeListener: () => {},
    addEventListener: () => {},
    removeEventListener: () => {},
    dispatchEvent: () => false,
  })) as unknown as typeof window.matchMedia;
}

Element.prototype.scrollIntoView = Element.prototype.scrollIntoView ?? (() => {});
```

(If `noUnusedParameters` complains about the stub signatures, prefix params with `_`.)

**Verify**: `bun run typecheck` → exit 0. `bun run lint` → exit 0.

### Step 3: Unit tests for `src/lib/format.ts`

Create `src/lib/format.test.ts`. Required cases:

- `pluralRu` — the full boundary matrix with forms `['клиент', 'клиента', 'клиентов']`:
  - 1 → `клиент`, 21 → `клиент`, 101 → `клиент`
  - 2 → `клиента`, 3 → `клиента`, 4 → `клиента`, 22 → `клиента`
  - 0 → `клиентов`, 5 → `клиентов`, 11 → `клиентов`, 12 → `клиентов`, 14 → `клиентов`, 111 → `клиентов`, 112 → `клиентов`
- `formatInt(1234567)` → groups with spaces; normalize NBSP before asserting: `expect(formatInt(1234567).replace(/[  ]/g, ' ')).toBe('1 234 567')`.
- `formatRub` — assert it contains the normalized digits and `₽`.
- `formatTime(new Date(2026, 5, 12, 9, 5))` → `09:05`.
- Do NOT test `formatRelativeRu` against wall-clock time without `vi.useFakeTimers()` + `vi.setSystemTime(...)`; either use fake timers or skip it (it's a thin `date-fns` wrapper).

**Verify**: `bun run test -- src/lib/format.test.ts` → all pass (≥ 18 assertions).

### Step 4: Extract and test the clients sort comparator

1. Create `src/features/clients/sort.ts` containing `DEFAULT_DIR` and `compare` moved **verbatim** from `src/pages/clients/ClientsPage.tsx:17-43` (excerpt in "Current state"), both `export`ed, with `import type { Client, ClientSort, ClientSortKey } from './types';`.
2. In `ClientsPage.tsx`: delete the moved block, add `import { compare, DEFAULT_DIR } from '@/features/clients/sort';`. No other edits.
3. Create `src/features/clients/sort.test.ts`. Build minimal `Client` fixtures (only fields the comparator touches: `name`, `visits.month`, `lastVisit.rank`, `expiry?.daysLeft` — check `src/features/clients/types.ts` for exact required fields and satisfy the type with realistic dummies, or use `as Client` casts on partial objects if the type demands many unrelated fields). Cases:
   - `name` asc/desc uses Russian collation: `'Анна' < 'Борис'`, and `'ё'`/`'е'` ordering doesn't throw.
   - `visits` asc/desc numeric.
   - `expires`: both null → 0; a-null → 1 regardless of direction; b-null → -1 regardless of direction; both present → numeric × direction. (This pins the "leads always sort last" behavior — the likeliest future regression.)

**Verify**: `bun run test` → format + sort suites pass. `bun run typecheck` → exit 0. `bun run lint` → exit 0.

### Step 5: Export the route array and add the route smoke test

1. In `src/app/router.tsx`, change the construction to (preserving the existing route objects byte-for-byte):

   ```ts
   import { createBrowserRouter, Navigate, type RouteObject } from 'react-router-dom';
   // ... existing imports unchanged

   export const routeConfig: RouteObject[] = [ /* the existing array, unchanged */ ];

   export const router = createBrowserRouter(routeConfig);
   ```

2. Create `src/app/router-smoke.test.tsx`:

   ```tsx
   import { describe, expect, it } from 'vitest';
   import { render, screen } from '@testing-library/react';
   import { RouterProvider, createMemoryRouter } from 'react-router-dom';
   import { Providers } from './providers';
   import { routeConfig } from './router';

   const PATHS = [
     '/', '/clients', '/schedule', '/plans', '/trainers', '/branches',
     '/cashbox', '/messages', '/notifications', '/reports', '/attendance',
     '/load', '/finance', '/settings', '/settings/system', '/settings/roles',
     '/settings/audit', '/settings/trash', '/settings/import-export', '/login',
   ];

   describe('маршруты рендерятся без падений', () => {
     for (const path of PATHS) {
       it(path, async () => {
         const router = createMemoryRouter(routeConfig, { initialEntries: [path] });
         const { unmount } = render(
           <Providers>
             <RouterProvider router={router} />
           </Providers>,
         );
         expect(await screen.findByRole('main')).toBeInTheDocument();
         unmount();
       });
     }
   });
   ```

   If `findByRole('main')` fails because `AppLayout` doesn't render a `<main>` landmark, check `src/layouts/AppLayout/AppLayout.tsx` for what wraps the `Outlet` and assert on that instead (e.g. `findByRole('navigation')` for the sidebar plus a non-empty `document.body`); for `/login` (outside AppLayout) assert on the login heading via `await screen.findByText(...)` with a string you confirm in `src/pages/login/LoginPage.tsx`. Adjust the assertion, not the app.

**Verify**: `bun run test` → all suites pass, 20 smoke cases green. `bun run typecheck` && `bun run lint` → exit 0.

## Test plan

This plan IS the test plan. Final state: 3 test files (`format.test.ts`, `sort.test.ts`, `router-smoke.test.tsx`), ≥ 35 passing assertions, `bun run test` exits 0 in under ~60s.

## Done criteria

ALL must hold:

- [ ] `bun run test` → exit 0, ≥ 3 test files, 0 failures, 0 skips (except an explicitly-reported jsdom-incompatible smoke path, see STOP #3)
- [ ] `bun run typecheck` → exit 0
- [ ] `bun run lint` → exit 0
- [ ] `grep -n "function compare" src/pages/clients/ClientsPage.tsx` → no matches (comparator lives in `features/clients/sort.ts`)
- [ ] `grep -n "export const routeConfig" src/app/router.tsx` → 1 match
- [ ] `git status --porcelain` shows only in-scope files modified
- [ ] `plans/README.md` row updated

## STOP conditions

Stop and report back (do not improvise) if:

- The comparator or route-array code does not match the excerpts (drift).
- `bun add -d vitest@^3 ...` fails to resolve (registry/peer problem) — report the exact error; do not force other major versions.
- More than 2 of the 20 smoke paths crash under jsdom for environment reasons (missing browser API beyond the four stubbed). One or two genuinely jsdom-incompatible pages may be excluded with an inline comment naming the missing API — more than two means the setup is wrong, not the pages.
- Extracting `compare` requires changing its logic or signature to satisfy types — extraction must be verbatim.

## Maintenance notes

- Plans 003–009 rely on `bun run test` as a gate; keep the smoke list in sync when routes are added (plan 011 will add archive/duplicates routes).
- The four jsdom stubs in `src/test/setup.ts` are the canonical place for future browser-API stubs — extend there, never per-test.
- Reviewer focus: the `ClientsPage.tsx` diff must be import-only (no logic change); `router.tsx` diff must be a pure re-shape (array extracted, `createBrowserRouter` argument identical).
- Deferred deliberately: component/integration tests for modals (see plan 006's maintenance notes), coverage thresholds, CI wiring (no CI exists yet).
