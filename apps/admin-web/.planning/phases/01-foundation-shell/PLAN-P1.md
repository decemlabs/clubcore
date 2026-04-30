---
phase: 01-foundation-shell
plan: P1
type: execute
granularity: fine
execution: auto-waves
language: en
goal: "Project boots; shell renders in Russian with role toggle and theme switcher; routing, providers, and role-based access wrappers work end-to-end on an empty data layer."
requirements: [FOUND-01, FOUND-02, FOUND-03, FOUND-04, FOUND-05, FOUND-06, FOUND-07, ROLE-01, ROLE-02, ROLE-03, ROLE-04, ROLE-05, UI-03, UI-04]
success_criteria:
  - SC1: Shell rendered in Russian with DD.MM.YYYY / 24h / Monday-week conventions
  - SC2: Role toggle survives hard reload (Zustand persist works)
  - SC3: Theme toggle light/dark/system with no FOUC via blocking script in index.html
  - SC4: ESLint boundary enforcement passes (services/{mock,http} import bans + raw palette bans)
  - SC5: Single routeRegistry + can(role, action, resource) helper consumed by sidebar, router beforeLoad, and RoleGate
waves: 7
depends_on: []
files_modified_summary: |
  Greenfield project scaffold: package.json, pnpm-lock.yaml, tsconfig*.json, vite.config.ts,
  eslint.config.js, prettier config, vitest.config.ts, components.json, index.html, .env.development,
  src/app/**, src/routes/**, src/shared/{ui,api,session,lib,i18n,theme,config}/**, src/test/**.
---

# Phase 1 — Foundation & Shell — Plan P1

## 0. Header

- **Phase:** 01 — Foundation & Shell
- **Goal:** A navigable app shell with role and theme toggles, a typed router, enforced architectural boundaries, and a single source of truth for role-based access — nothing feature-specific yet.
- **Requirements covered (14):** FOUND-01, FOUND-02, FOUND-03, FOUND-04, FOUND-05, FOUND-06, FOUND-07, ROLE-01, ROLE-02, ROLE-03, ROLE-04, ROLE-05, UI-03, UI-04
- **Success criteria (5):** see frontmatter `success_criteria`
- **Out-of-scope reminder:** no mock DB seeding, no entity Zod schemas, no real forms, no calendar, no reports — all start in Phase 2+.
- **Granularity:** fine (small atomic tasks per `.planning/config.json`)
- **Execution:** auto-waves; each wave merges only if `pnpm typecheck && pnpm lint && pnpm test --run` is green.

---

## 1. Assumptions

Carried forward from `RESEARCH.md` (A1–A6) plus plan-level additions (A7–A9).

| # | Claim | Risk if wrong |
|---|---|---|
| A1 | `tw-animate-css` is the current shadcn-recommended animation CSS import for Tailwind v4. | LOW — sourced from shadcn manual-install docs; package name has changed once before. |
| A2 | reui's `style: "base-nova"` is an override, not a required global style — a `new-york` project can consume reui via the `{style}` URL variable. | MEDIUM — verified inline at T2.2 via curl probe; if wrong, fall back to per-component `--style base-nova` invocation and document SHADCN-DIVERGENCE. |
| A3 | `pnpm dlx shadcn@latest add @reui/radix/<name>` is the exact CLI invocation. | LOW — verified at first reui install in Phase 2; Phase 1 only needs the registry entry, no reui components installed yet. |
| A4 | CSP `unsafe-inline` is acceptable for the pre-React theme bootstrap script in v1. | LOW — internal mock; nonce/hash hardening deferred to Phase 7. |
| A5 | `oklch(...)` color tokens render identically in evergreen browsers we target. | LOW — supported since 2023 in all Chromium/Firefox/Safari. |
| A6 | Node 20+ is the runtime the team uses. | LOW — required by Vite 6 + TanStack Router plugin. |
| A7 | `CLAUDE.md` version locks (Vite 6, ESLint 9, TS 5.6+) are authoritative; npm-latest drift (Vite 8, ESLint 10, TS 6) is **informational only** and NOT applied in Phase 1. | LOW — documented in RESEARCH §Summary; revisit only on explicit user request. |
| A8 | The placeholder routes at `/`, `/clients`, `/schedule`, `/staff`, `/finance`, `/settings` paint a Russian H1 + "Phase N" stub — they are page-level placeholders, not feature stubs. | LOW — they exist purely so the router tree compiles and the sidebar has something to navigate to. Phases 3–7 replace each. |
| A9 | Vitest + jsdom + `@testing-library/react` is the unit-test stack for Phase 1; Playwright is **not** introduced in this phase (UI-04 1366×768 verified by manual smoke + jsdom viewport assertion). | LOW — RESEARCH §Validation Architecture flags Playwright as optional / deferable. |

---

## 2. Decisions (resolves the 6 RESEARCH OQs)

| OQ | Decision | Rationale |
|---|---|---|
| **OQ1** reui `style` interop with shadcn `new-york` | Keep `components.json` `style: "new-york"`. At T2.2 run `curl -fsS https://reui.io/r/new-york/data-grid.json -o /dev/null` as a probe. If it returns 404, fall back to per-component install with `--style base-nova` and add `// SHADCN-DIVERGENCE: reui style override` to any reui-sourced wrapper. Phase 1 ships only the registry entry; no reui components installed yet, so the fallback cost is paid in Phase 2. | Honors `CLAUDE.md` lock (`new-york`). Defers actual reui surface to Phase 2 (UI templates) when we install Data Grid for the canonical List template. |
| **OQ2** Session-store rehydration timing | Use `skipHydration: true` + manual `useSessionStore.persist.rehydrate()` awaited before `createRoot(...).render(...)` in `main.tsx`. Theme is handled by the blocking script (FOUC-safe by construction). | Eliminates RBAC flash described in RESEARCH §Pitfall 2; small (one `await`) cost. |
| **OQ3** services/index.ts swap mechanism | **Eager imports** of both `./mock` and `./http` modules with a synchronous mode-branch picker. No top-level `await`. | Simpler, no ESM-target coupling, predictable bundle splitting. Both impls are empty stubs in Phase 1, so the dead-code is < 200 bytes. |
| **OQ4** Sidebar collapse breakpoint | Sidebar collapses below `1024px` (Tailwind `lg`) and is **collapsed by default at < 1536px** (`< 2xl`) at first paint. Full at 1366×768: shadcn `sidebar-07` with `defaultOpen={false}` + `<SidebarTrigger>` in header. | Matches RESEARCH §Pitfall 9 guidance for 1366-wide DataTables in Phase 3+. |
| **OQ5** Persist key naming | **Three separate keys**: `sportzal:session:v1` (role), `sportzal:ui:v1` (theme + sidebar collapsed), `sportzal:mock:v1` (mock DB — created in Phase 2). | Theme rehydrates synchronously in the blocking script; role rehydrates async in JS; mock DB loads on demand. Different lifetimes → different keys. |
| **OQ6** Path alias | `@/*` → `./src/*` (tsconfig + Vite `resolve.alias` + components.json aliases must match). | Standard shadcn convention; matches all canonical snippets in RESEARCH §Code Examples. |

Additional plan-level decisions:

| ID | Decision | Rationale |
|---|---|---|
| D-PKG | Pin `pnpm@9.x` in `package.json#packageManager`; require Node `>= 20`. | `CLAUDE.md` lock + Vite 6 minimum. |
| D-LANG | All UI strings in `src/shared/i18n/ru.ts`; component code never inlines literals — even placeholder pages call `t('home.title')` so the discipline lands from day one. | Enforces single-dictionary rule from `CLAUDE.md`; future-proofs against accidental i18n debt. |
| D-CSP | Add baseline `<meta http-equiv="Content-Security-Policy">` allowing `'self' 'unsafe-inline'` for the FOUC bootstrap script only — flagged TODO for Phase 7 nonce/hash hardening. | RESEARCH §Security A4. |
| D-ESLINT-VITE_API_MODE | ESLint flat config also forbids `import.meta.env.VITE_API_MODE` outside `src/shared/api/**` (RESEARCH §Pitfall 5). | Prevents mode-leakage into UI. |

---

## 3. Wave-by-Wave Task List

Each task: ID · Wave · Files · Action · Verify · Acceptance · Deps · Reqs.

> Path conventions: paths under `src/` are project-relative; everything else is repo-root.

### Wave 1 — Project Init (serial)

#### T1.1 — Scaffold Vite + React + TypeScript (strict)
- **Wave:** 1 · **Deps:** — · **Reqs:** FOUND-05 (foundational), supports all
- **Files:** `package.json`, `pnpm-lock.yaml`, `tsconfig.json`, `tsconfig.app.json`, `tsconfig.node.json`, `vite.config.ts`, `index.html`, `src/main.tsx` (temporary; replaced in Wave 3), `src/vite-env.d.ts`, `.gitignore`, `.nvmrc`, `.npmrc`
- **Action:**
  1. **Scaffold-and-merge** (the repo root is non-empty: contains `.git/`, `.claude/`, `.omc/`, `.planning/`, `CLAUDE.md` — `pnpm create vite@latest .` would refuse). Run in a sibling temp dir, then merge:
     ```sh
     mkdir -p /tmp/sportzal-init && cd /tmp/sportzal-init
     pnpm create vite@latest scaffold --template react-ts
     # merge: copy everything except node_modules + .git into the repo root, never overwriting existing files
     rsync -av --ignore-existing --exclude node_modules --exclude .git scaffold/ /Users/andre/Workspace/Development/SportZal/adminka/
     cd - && rm -rf /tmp/sportzal-init
     ```
     Verify the merge did not touch `.planning/`, `CLAUDE.md`, `.claude/`, or `.omc/`.
  2. Edit `package.json`:
     - `"name": "sportzal-adminka"`
     - `"packageManager": "pnpm@9.15.0"`
     - `"engines": { "node": ">=20" }`
     - Scripts: `"dev": "vite"`, `"build": "tsc -b && vite build"`, `"preview": "vite preview"`, `"typecheck": "tsc -b --noEmit"`, `"lint": "eslint ."`, `"format": "prettier --write ."`, `"test": "vitest"`.
  3. `tsconfig.json`: `"strict": true`, `"noUncheckedIndexedAccess": true`, `"exactOptionalPropertyTypes": true`, `"paths": { "@/*": ["./src/*"] }`, `"baseUrl": "."`. Apply same `paths` in `tsconfig.app.json`.
  4. `vite.config.ts`: minimal `defineConfig` with `react()` and `resolve.alias['@'] = path.resolve(__dirname, './src')` (TanStack Router plugin added in T3.1 — order critical).
  5. `.nvmrc`: `20`.
  6. `pnpm install`.
- **Verify:** `pnpm dev` starts without error; `pnpm typecheck` exits 0; `import x from '@/main'` resolves in TS.
- **Acceptance:** Dev server prints "Local: http://localhost:5173"; visiting renders the default Vite splash.

#### T1.2 — Install runtime + dev dependencies (single transaction)
- **Wave:** 1 · **Deps:** T1.1 · **Reqs:** all (sets up package set)
- **Files:** `package.json`, `pnpm-lock.yaml`
- **Action:** Install in one `pnpm add` per group (per RESEARCH §Installation sequence) — do **not** run `shadcn init` yet (T2.2 owns that):
  - Tailwind v4: `pnpm add tailwindcss@^4 @tailwindcss/vite@^4 tw-animate-css`
  - TanStack: `pnpm add @tanstack/react-router @tanstack/react-query` and `pnpm add -D @tanstack/router-plugin @tanstack/router-devtools @tanstack/react-query-devtools`
  - Runtime: `pnpm add zustand@^5 date-fns@^4 lucide-react sonner@^2 clsx tailwind-merge`
  - Dev tooling: `pnpm add -D eslint@^9 typescript-eslint eslint-plugin-import @eslint/js prettier prettier-plugin-tailwindcss vitest @vitest/ui jsdom @testing-library/react @testing-library/jest-dom @testing-library/user-event`
- **Verify:** `pnpm install` clean; `pnpm list --depth=0` shows all expected packages at `CLAUDE.md`-locked majors.
- **Acceptance:** Lockfile committed; no peer-dep warnings beyond known harmless ones.

---

### Wave 2 — Tooling Triplet (parallel: T2.1 ⫼ T2.2 ⫼ T2.3 ⫼ T2.4)

#### T2.1 — Tailwind v4 + shadcn token CSS
- **Wave:** 2 · **Deps:** T1.2 · **Reqs:** UI-03, FOUND-07
- **Files:** `src/app/index.css`
- **Action:** Create `src/app/index.css` per RESEARCH §Code Examples #3 verbatim (`@import "tailwindcss"`, `@import "tw-animate-css"`, `@custom-variant dark`, `@theme inline { … }`, full neutral oklch palette in `:root` and `.dark`, `@layer base` defaults). Append the **reui-extra tokens** in both `:root` and `.dark`: `--success`, `--success-foreground`, `--warning`, `--warning-foreground`, `--info`, `--info-foreground`, `--destructive-foreground`, `--invert`, `--invert-foreground` (use sensible neutral oklch values; document with `/* reui-extras */` comment block).
- **Verify:** `pnpm build` (after Wave 3 wires main.tsx) emits CSS containing both `:root` and `.dark` blocks; grep for `--success-foreground` finds it in built CSS.
- **Acceptance:** `index.css` valid Tailwind v4; both reui- and shadcn-required tokens present in single source.

#### T2.2 — shadcn init + components.json (with @reui registry probe)
- **Wave:** 2 · **Deps:** T1.2, T2.1 (CSS file must exist for shadcn to point at) · **Reqs:** UI-03
- **Files:** `components.json`
- **Action:**
  1. Probe reui style availability: `curl -fsSI https://reui.io/r/new-york/button.json | head -1` — record HTTP status in plan-runner notes.
  2. If 200: `style: "new-york"`. If 404: still set `style: "new-york"` for shadcn primitives, plan to use `--style base-nova` per-reui-component in Phase 2; tag in `components.json` with a JSON comment header.
  3. Write `components.json` per RESEARCH §Code Examples #7 verbatim (style new-york, baseColor neutral, cssVariables true, aliases pointing at `@/shared/ui`, `@/shared/lib/cn`, `@/shared/lib`, `@/shared/lib/hooks`, `iconLibrary lucide`, `registries.@reui` set to `https://reui.io/r/{style}/{name}.json`).
  4. Create empty alias targets so shadcn CLI doesn't error on first `add`: `mkdir -p src/shared/ui src/shared/lib/hooks` and create `src/shared/lib/cn.ts` (T4-3 fills it; for now `export const cn = (...args: any[]) => args.filter(Boolean).join(' ')` placeholder).
- **Verify:** `pnpm dlx shadcn@latest add button --yes` succeeds and writes `src/shared/ui/button.tsx`; `pnpm typecheck` still green.
- **Acceptance:** `components.json` exists with `@reui` registry entry; one shadcn primitive (`button`) installed as smoke test.

#### T2.3 — ESLint flat config (boundary + palette + VITE_API_MODE rules) + Prettier
- **Wave:** 2 · **Deps:** T1.2 · **Reqs:** FOUND-06, FOUND-07
- **Files:** `eslint.config.js`, `scripts/eslint.fixtures.config.js`, `.prettierrc.json`, `.prettierignore`, `.eslintignore` (or flat-config `ignores`)
- **Action:**
  1. `eslint.config.js`: per RESEARCH §Code Examples #8 with three rules:
     - `import/no-restricted-paths` zone blocking `src/{features,routes,entities,shared/ui,app}/**` from importing `src/shared/api/services/{mock,http}/**` (message: "Go through services container or a TanStack Query hook.").
     - `no-restricted-syntax` for raw palette `className` literals (regex from RESEARCH §Code Examples #8).
     - `no-restricted-syntax` for `import.meta.env.VITE_API_MODE` outside `src/shared/api/**` (selector: `MemberExpression[object.object.property.name='env'][property.name='VITE_API_MODE']`; configure `files`/`ignores` accordingly via flat-config layered objects).
     - `react/no-danger` (warn) for XSS hygiene per RESEARCH §Security.
  2. Prettier config: `{ semi: false, singleQuote: true, printWidth: 100, plugins: ["prettier-plugin-tailwindcss"] }`.
  3. `.prettierignore` + flat-config `ignores`: `dist`, `node_modules`, `src/routeTree.gen.ts`, `src/__fixtures/**`.
- **Verify:** `pnpm lint` passes on the empty src tree; lint fixture (T7.2) will assert violations are caught.
- **Acceptance:** Three custom rules registered; `pnpm format` reformats without errors.

#### T2.4 — Vitest + jsdom + Testing Library scaffold
- **Wave:** 2 · **Deps:** T1.2 · **Reqs:** all (per RESEARCH §Validation Architecture Wave-0 gap)
- **Files:** `vitest.config.ts`, `src/test/setup.ts`, `src/test/utils.tsx`
- **Action:**
  1. `vitest.config.ts`: `test: { environment: 'jsdom', setupFiles: ['./src/test/setup.ts'], globals: true, css: false }`; `resolve.alias['@'] = ./src`.
  2. `src/test/setup.ts`: `import '@testing-library/jest-dom/vitest'`; reset `localStorage` + `document.documentElement.className` in `beforeEach`.
  3. `src/test/utils.tsx`: `renderWithProviders(ui, { route?, role? })` helper that mounts inside `<QueryClientProvider>` with a fresh `QueryClient` and seeds `useSessionStore` (for tests added in Wave 7).
- **Verify:** `pnpm test --run` exits 0 (no tests yet, but framework boots).
- **Acceptance:** Vitest discovers 0 tests, prints "no test files found" without error.

---

### Wave 3 — Foundational stores + Providers + Router skeleton (depends on Wave 1 + Wave 2)

T4.1 (session store) and T4.5 (UI prefs store) are hoisted into Wave 3 because T3.2 (router context) and T3.4 (main.tsx rehydrate) import them. T4.1/T4.5 themselves have no T3.x dependencies, so the wave dep graph remains acyclic.

#### T3.1 — vite.config.ts plugin order + TanStack Router codegen wiring
- **Wave:** 3 · **Deps:** T1.2, T2.1 · **Reqs:** FOUND-05
- **Files:** `vite.config.ts`, `src/routeTree.gen.ts` (auto-generated; gitignore-ed initially, then committed once stable per TanStack convention)
- **Action:** Replace `vite.config.ts` per RESEARCH §Code Examples #1 — `tanstackRouter({ target: 'react', autoCodeSplitting: true })` MUST come BEFORE `react()`; then `tailwindcss()`. Add `routesDirectory: './src/routes'` and `generatedRouteTree: './src/routeTree.gen.ts'` to the plugin options. Keep `resolve.alias`. Add `routeTree.gen.ts` to ESLint `ignores`.
- **Verify:** `pnpm dev` starts; touching `src/routes/index.tsx` (created in T5.4) regenerates `routeTree.gen.ts`.
- **Acceptance:** Plugin order matches RESEARCH §Pitfall 8; HMR reloads on route file change.

#### T3.2 — QueryClient + Router instances
- **Wave:** 3 · **Deps:** T3.1, T4.1 · **Reqs:** FOUND-05
- **Files:** `src/app/queryClient.ts`, `src/app/router.ts`
- **Action:**
  - `queryClient.ts` per RESEARCH §Code Examples #4: `staleTime: 30_000`, `refetchOnWindowFocus: false`, `retry: 1`, `mutations.retry: 0`.
  - `router.ts` per RESEARCH §Code Examples (Pattern 1): `createRouter({ routeTree, context: { queryClient, getSession: () => useSessionStore.getState() }, defaultPreload: 'intent', defaultPreloadStaleTime: 0 })` + `declare module '@tanstack/react-router' { interface Register { router: typeof router } }`.
- **Verify:** `pnpm typecheck` green; router accepts the typed context.
- **Acceptance:** Router exposes typed `Register`; `router.options.defaultPreloadStaleTime === 0`.

#### T3.3 — index.html: blocking theme script + `lang="ru"` + CSP baseline
- **Wave:** 3 · **Deps:** T1.1 · **Reqs:** FOUND-03, FOUND-04, UI-03
- **Files:** `index.html`
- **Action:** Replace stock `index.html` per RESEARCH §Code Examples #2:
  - `<html lang="ru">`
  - `<title>SportZal</title>`
  - Add `<meta http-equiv="Content-Security-Policy" content="default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self';">` with `<!-- TODO Phase 7: replace 'unsafe-inline' with nonce/hash for the bootstrap script -->`.
  - Inline blocking `<script>` IIFE: reads `localStorage.getItem('sportzal:ui:v1')`, JSON-parses, picks `state.theme || 'system'`, resolves `system` via `matchMedia('(prefers-color-scheme: dark)')`, adds `dark` class to `<html>` if resolved=`'dark'`. Wrap in `try/catch`, < 800 bytes.
  - `<script type="module" src="/src/app/main.tsx">`.
- **Verify:** Manually set `localStorage.setItem('sportzal:ui:v1', JSON.stringify({state:{theme:'dark'}}))` in DevTools, hard reload — page paints dark immediately, no light flash. (Automated equivalent in T7.1 `theme-bootstrap.test.ts`.)
- **Acceptance:** No FOUC under DevTools "Slow 3G" throttle; `<html lang="ru">` present.

#### T3.4 — main.tsx: providers + rehydrate session before render
- **Wave:** 3 · **Deps:** T3.2, T3.3, T4.1, T4.5 · **Reqs:** FOUND-02, FOUND-03, FOUND-05
- **Files:** `src/app/main.tsx`
- **Action:** Per RESEARCH §Code Examples #5 + decision OQ2:
  ```tsx
  import { useSessionStore } from '@/shared/session/store'
  import { useUiPrefsStore } from '@/shared/theme/uiPrefsStore'

  await Promise.all([
    useSessionStore.persist.rehydrate(),
    useUiPrefsStore.persist.rehydrate(),
  ])

  createRoot(document.getElementById('root')!).render(
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
  Top-level `await` is acceptable here (single entry, ESM target).
- **Verify:** Hard reload as Reception → sidebar paints with Reception items only on first paint (no Owner flash).
- **Acceptance:** RESEARCH §Pitfall 2 demonstrably absent.

---

### Wave 4 — RBAC, i18n, RoleGate, env (parallel; depends on Wave 3 stores + Wave 1)

#### T4.1 — Zustand session store (with persist + skipHydration)
- **Wave:** 3 · **Deps:** T1.2 · **Reqs:** FOUND-02, ROLE-05
- **Files:** `src/shared/session/store.ts`, `src/shared/session/types.ts`
- **Action:** Per RESEARCH §Code Examples (Pattern 4):
  - `types.ts`: `export type Role = 'owner' | 'reception'`.
  - `store.ts`: `useSessionStore = create(persist(...))` with `name: 'sportzal:session:v1'`, `version: 1`, `partialize: s => ({ role: s.role })`, `migrate: (state, _from) => state`, `skipHydration: true` (per OQ2).
  - Default `role: 'owner'`.
  - Export `SessionState` type for router context typing.
- **Verify:** Unit test (T7.1 `store.test.ts`): set role, call `persist.rehydrate()`, read from `localStorage` directly — key is `sportzal:session:v1`, value contains only `role` (not `setRole`).
- **Acceptance:** No function serialization errors; `version: 1` recorded; key strictly versioned.

#### T4.2 — routeRegistry + can() RBAC helper
- **Wave:** 4 · **Deps:** T4.1 · **Reqs:** ROLE-01, ROLE-02, ROLE-03, ROLE-04
- **Files:** `src/shared/session/registry.ts`, `src/shared/session/can.ts`, `src/shared/session/README.md`
- **Action:** Per RESEARCH §Code Examples #9:
  - `registry.ts`: `Resource` union (`'dashboard' | 'clients' | 'schedule' | 'staff' | 'finance' | 'reports' | 'payroll' | 'compensation' | 'templates' | 'settings' | 'owner-area'`); `Action` union (`'view' | 'create' | 'edit' | 'delete' | 'refund'`); `RouteEntry { path, resource, label (RU), icon (lucide name) }`; `routeRegistry: RouteEntry[]` for the 6 placeholder routes (Главная, Клиенты, Расписание, Сотрудники, Финансы, Настройки).
  - `can.ts`: `OWNER_ONLY` table per snippet; `can(role, action, resource): boolean` returns `true` for owner; for reception returns `!OWNER_ONLY.some(...)`.
  - `README.md`: 1-page note: "**This is not auth.** Role is UI state. When real auth ships in v2, the session source flips from Zustand+localStorage to a JWT claim; `can()` and `routeRegistry` do not change." (RESEARCH §Security V3/V4.)
- **Verify:** Unit test (T7.1 `can.test.ts`): table-driven — owner allowed on all entries; reception blocked on `view/finance`, `view/payroll`, `delete/clients`, `refund/finance`, `edit/templates`; reception allowed on `view/clients`, `create/clients`, `view/schedule`.
- **Acceptance:** All ROLE-02/03/04 cases assert green; ROLE-05 satisfied by `README.md` contract + `getSession`-via-router-context indirection.

#### T4.3 — RoleGate component
- **Wave:** 4 · **Deps:** T4.2 · **Reqs:** ROLE-01
- **Files:** `src/shared/session/RoleGate.tsx`
- **Action:** Per RESEARCH §Code Examples #10. Subscribe with selector `s => s.role` to avoid extra re-renders. Re-export `Action`, `Resource` from `./can`.
- **Verify:** Render `<RoleGate action="refund" resource="finance">X</RoleGate>` as reception → no `X`; as owner → `X` visible (smoke unit test).
- **Acceptance:** Component < 25 LOC; pure.

#### T4.4 — i18n RU dictionary + Intl helpers (money, plural, date)
- **Wave:** 4 · **Deps:** T1.2 · **Reqs:** FOUND-04, UI-04
- **Files:** `src/shared/i18n/ru.ts`, `src/shared/i18n/plural.ts`, `src/shared/i18n/date.ts`, `src/shared/i18n/index.ts`, `src/shared/lib/money.ts`, `src/shared/lib/cn.ts` (replace placeholder from T2.2)
- **Action:**
  - `ru.ts`: nested object dictionary `{ shell: { roleSwitch: { owner: 'Владелец', reception: 'Ресепшн' }, theme: { light: 'Светлая', dark: 'Тёмная', system: 'Системная' }, nav: { home: 'Главная', clients: 'Клиенты', schedule: 'Расписание', staff: 'Сотрудники', finance: 'Финансы', settings: 'Настройки' }, notifications: 'Уведомления', profile: 'Профиль' }, common: { loading: 'Загрузка…', empty: 'Пусто', error: 'Ошибка' } }`. Export `t(path)` typed via template-literal types so consumers get autocomplete.
  - `plural.ts` per RESEARCH §Code Examples #11.
  - `date.ts` per RESEARCH: `DATE_FMT = 'dd.MM.yyyy'`, `TIME_FMT = 'HH:mm'`, `formatDate`, `formatDateTime`, `formatTime` — all `{ locale: ru, weekStartsOn: 1 }`. Export `MOSCOW_TZ = 'Europe/Moscow'` constant.
  - `money.ts` per RESEARCH: `formatMoney(minor: number)` using `Intl.NumberFormat('ru-RU', { style: 'currency', currency: 'RUB' })`.
  - `cn.ts`: `import { clsx, type ClassValue } from 'clsx'; import { twMerge } from 'tailwind-merge'; export const cn = (...inputs: ClassValue[]) => twMerge(clsx(inputs))`.
- **Verify:** Unit tests (T7.1):
  - `formatMoney(123456)` → `'1 234,56 ₽'` (with NBSP `\u00A0` between digits and currency symbol; assert via `.charCodeAt`).
  - `plural(2, { one: 'клиент', few: 'клиента', many: 'клиентов' })` → `'клиента'`; `plural(11, …)` → `'клиентов'`; `plural(21, …)` → `'клиент'`.
  - `formatDate('2026-04-21T00:00:00.000Z')` → `'21.04.2026'`.
  - `t('shell.nav.clients')` → `'Клиенты'`.
- **Acceptance:** All NBSP and 3-form plural edge cases (1, 2, 5, 11, 21, 101) covered.

#### T4.5 — UI prefs store (theme + sidebar collapsed) + ThemeProvider + useTheme
- **Wave:** 3 · **Deps:** T1.2 · **Reqs:** FOUND-03, UI-03
- **Files:** `src/shared/theme/uiPrefsStore.ts`, `src/app/providers/ThemeProvider.tsx`, `src/shared/theme/useTheme.ts`
- **Action:**
  - `uiPrefsStore.ts`: `useUiPrefsStore = create(persist(set => ({ theme: 'system' as 'light'|'dark'|'system', sidebarCollapsed: false, setTheme, setSidebarCollapsed }), { name: 'sportzal:ui:v1', version: 1, partialize: s => ({ theme: s.theme, sidebarCollapsed: s.sidebarCollapsed }), skipHydration: true }))`.
  - `ThemeProvider.tsx`: subscribes to `theme`, computes `resolved` via `matchMedia('(prefers-color-scheme: dark)')` (with `addEventListener('change')` cleanup), toggles `.dark` on `document.documentElement`. **No FOUC**: blocking script already set the class — provider only handles in-session changes.
  - `useTheme.ts`: thin re-export hook `() => { const { theme, setTheme } = useUiPrefsStore(...); return { theme, setTheme, resolved } }`.
- **Verify:** Click theme switcher → `<html>` toggles class without page reload. Reload while `theme: 'dark'` → no flash (asserted manually + by T7.1 `theme-bootstrap.test.ts`).
- **Acceptance:** Storage key matches blocking-script reader; provider does not duplicate work the script already did.

#### T4.6 — Typed env wrapper
- **Wave:** 4 · **Deps:** T1.1 · **Reqs:** FOUND-06 (supports), DATA-05 (foreshadow)
- **Files:** `src/shared/config/env.ts`, `src/vite-env.d.ts` (augment), `.env.development`, `.env.example`
- **Action:**
  - `vite-env.d.ts`: `interface ImportMetaEnv { readonly VITE_API_MODE: 'mock' | 'http' }; interface ImportMeta { readonly env: ImportMetaEnv }`.
  - `env.ts`: `export const API_MODE = (import.meta.env.VITE_API_MODE ?? 'mock') as 'mock' | 'http'` with runtime narrow + dev-only `console.warn` if value is unexpected. **This file lives under `src/shared/api/` for ESLint exemption — move it to `src/shared/api/config/env.ts`** (so the `VITE_API_MODE` ESLint rule does not flag it).
  - `.env.development`: `VITE_API_MODE=mock`.
  - `.env.example`: same with comment.
- **Verify:** `import { API_MODE } from '@/shared/api/config/env'` works; ESLint allows the env access here but blocks it elsewhere (proven by T7.2 fixture).
- **Acceptance:** Single chokepoint for env reads.

---

### Wave 5 — Shell layout + routes (depends Wave 3 + Wave 4)

#### T5.1 — Install required shadcn primitives
- **Wave:** 5 · **Deps:** T2.2, T2.1 · **Reqs:** FOUND-01, UI-04
- **Files:** auto-created under `src/shared/ui/` — `button.tsx` (already from T2.2), `sidebar.tsx`, `dropdown-menu.tsx`, `avatar.tsx`, `separator.tsx`, `tooltip.tsx`, `sheet.tsx`, `skeleton.tsx`, `sonner.tsx`
- **Action:** `pnpm dlx shadcn@latest add sidebar dropdown-menu avatar separator tooltip sheet skeleton sonner --yes`. Do NOT hand-edit. After install run `pnpm lint` immediately to confirm no raw-palette classes leaked (RESEARCH §Pitfall 6) — if any do, file a SHADCN-DIVERGENCE wrapper.
- **Verify:** `pnpm typecheck && pnpm lint` green.
- **Acceptance:** Primitives present; no raw-palette violations.

#### T5.2 — AppShell composition (Header + Sidebar + Content)
- **Wave:** 5 · **Deps:** T5.1, T4.2, T4.3, T4.4, T4.5 · **Reqs:** FOUND-01, FOUND-02, FOUND-03, FOUND-04, ROLE-01, ROLE-02, ROLE-03, UI-03, UI-04
- **Files:** `src/shared/ui/app-shell/AppShell.tsx`, `src/shared/ui/app-shell/Header.tsx`, `src/shared/ui/app-shell/Sidebar.tsx`, `src/shared/ui/app-shell/RoleSwitcher.tsx`, `src/shared/ui/app-shell/ThemeSwitcher.tsx`, `src/shared/ui/app-shell/NotificationsBell.tsx`, `src/shared/ui/app-shell/ProfileMenu.tsx`, `src/shared/ui/app-shell/index.ts`
- **Action:**
  - `AppShell.tsx`: shadcn `<SidebarProvider defaultOpen={false}>` + `<Sidebar>` + `<SidebarInset>` containing `<Header />` + `<main className="flex-1 p-6 bg-background text-foreground">{children}</main>`. Use `useUiPrefsStore` to bind `defaultOpen` to persisted `!sidebarCollapsed`.
  - `Sidebar.tsx`: maps `routeRegistry` filtered by `can(role, 'view', entry.resource)`; renders `<Link to={entry.path}>` (TanStack Router) with lucide icon + RU `label` from `t()`. Active link via router `useMatchRoute`.
  - `Header.tsx`: left = `<SidebarTrigger>`; right = `<RoleSwitcher>` `<ThemeSwitcher>` `<NotificationsBell>` (icon-only stub, `aria-label={t('shell.notifications')}`, no popover yet) `<ProfileMenu>` (avatar + dropdown stub showing the role label).
  - `RoleSwitcher.tsx`: shadcn `<DropdownMenu>` with two items "Владелец" / "Ресепшн" calling `useSessionStore.setRole`.
  - `ThemeSwitcher.tsx`: shadcn `<DropdownMenu>` with three items "Светлая" / "Тёмная" / "Системная" calling `useTheme().setTheme`.
  - All visual styling via semantic tokens **only** (`bg-background`, `text-foreground`, `text-muted-foreground`, `border-border`, etc.). No raw palette.
- **Verify:** `pnpm dev` and visit `/` — header + sidebar + content visible in Russian; toggle role → sidebar items count changes (Reception: no Финансы, no Настройки); toggle theme → instant; resize to 1366×768 → sidebar collapses to icon rail, content fills.
- **Acceptance:** SC1, SC2, SC3, SC5 all visually demonstrable; `pnpm lint` clean.

#### T5.3 — `__root.tsx` route with typed router context + devtools
- **Wave:** 5 · **Deps:** T3.2, T5.2 · **Reqs:** FOUND-05
- **Files:** `src/routes/__root.tsx`
- **Action:** Per RESEARCH §Code Examples #6 with `RouterContext { queryClient: QueryClient; getSession: () => SessionState }`. Render `<AppShell><Outlet /></AppShell>` plus `<TanStackRouterDevtools>` and `<ReactQueryDevtools>` gated by `import.meta.env.DEV`.
- **Verify:** `routeTree.gen.ts` regenerates including `__root`; typecheck green.
- **Acceptance:** Router context type matches what `router.ts` provides.

#### T5.4 — Placeholder routes (6) with RoleGate redirects
- **Wave:** 5 · **Deps:** T5.3, T4.2 · **Reqs:** FOUND-05, ROLE-01, ROLE-02, ROLE-03
- **Files:** `src/routes/index.tsx`, `src/routes/clients.tsx`, `src/routes/schedule.tsx`, `src/routes/staff.tsx`, `src/routes/finance.tsx`, `src/routes/settings.tsx`
- **Action:** Each file: `createFileRoute('/...')({ beforeLoad: ({ context, location }) => { const { role } = context.getSession(); const resource = '<matching resource from registry>'; if (!can(role, 'view', resource)) throw redirect({ to: '/', search: { forbidden: location.href } }) }, component: () => <h1 className="text-2xl font-semibold">{t('shell.nav.<key>')}</h1> })`. Use the typed-search `forbidden` param via a Zod-less `validateSearch: (s) => ({ forbidden: typeof s.forbidden === 'string' ? s.forbidden : undefined })` (Zod arrives in Phase 2; Phase 1 keeps it inline).
- **Verify:** As Reception, navigating to `/finance` redirects to `/?forbidden=...`; URL preserves the attempt; sidebar already hides the link, this is the second line of defense.
- **Acceptance:** Server-side guard parity with sidebar filter; six routes render.

#### T5.5 — `app/index.css` import wired into `main.tsx`
- **Wave:** 5 · **Deps:** T2.1, T3.4 · **Reqs:** UI-03
- **Files:** `src/app/main.tsx` (edit)
- **Action:** Add `import '@/app/index.css'` at the top of `main.tsx` (above provider imports). Delete the stock `src/index.css` and `src/App.css` if scaffolded by Vite.
- **Verify:** Built CSS contains shadcn tokens; `<body>` paints `bg-background`.
- **Acceptance:** Single CSS entry; Tailwind classes work everywhere.

---

### Wave 6 — Swap seam + contracts stubs (parallel with late Wave 5; depends Wave 1 + T4.6)

#### T6.1 — Empty service contracts
- **Wave:** 6 · **Deps:** T1.1 · **Reqs:** FOUND-06, ROLE-05 (foreshadow)
- **Files:** `src/shared/api/contracts/index.ts`, `src/shared/api/contracts/_README.md`
- **Action:** Empty `index.ts` exporting nothing yet (Phase 2 fills `ClientsService`, `ScheduleService`, etc.). `_README.md` documents the convention: "Each domain owns one TS interface here; both `services/mock/<domain>.ts` and `services/http/<domain>.ts` implement it."
- **Verify:** File compiles.
- **Acceptance:** Directory exists for ESLint zone targeting.

#### T6.2 — Empty mock + http impls
- **Wave:** 6 · **Deps:** T6.1 · **Reqs:** FOUND-06, DATA-05 (foreshadow), ROLE-05
- **Files:** `src/shared/api/services/mock/index.ts`, `src/shared/api/services/http/index.ts`
- **Action:** Each exports an empty object `export const services = {} as const` (no domain methods yet). Add `_README.md` in each subfolder reminding hand-rollers that **components must not import from these paths** (ESLint will block).
- **Verify:** `pnpm typecheck` green.
- **Acceptance:** Both impl folders exist as ESLint zone targets.

#### T6.3 — Swap seam (eager imports)
- **Wave:** 6 · **Deps:** T6.2, T4.6 · **Reqs:** FOUND-06, DATA-05 (foreshadow)
- **Files:** `src/shared/api/services/index.ts`
- **Action:** Per OQ3 (eager imports, no top-level await):
  ```ts
  import { API_MODE } from '@/shared/api/config/env'
  import { services as mockServices } from './mock'
  import { services as httpServices } from './http'

  export const services = API_MODE === 'http' ? httpServices : mockServices
  ```
  Add `// 403-analog hook lands in Phase 2 once contracts exist (ROLE-05).` comment.
- **Verify:** `pnpm typecheck && pnpm build` green; build output shows tree-shaking stripped the unused branch (inspect dist with `du -sh dist/assets`).
- **Acceptance:** Single seam; UI cannot reach `mock`/`http` directly thanks to T2.3 ESLint rule.

---

### Wave 7 — Verification (depends all)

#### T7.1 — Unit-test suite (RBAC, store, i18n, theme bootstrap, components.json)
- **Wave:** 7 · **Deps:** T4.1, T4.2, T4.4, T4.5, T2.4 · **Reqs:** FOUND-02, FOUND-03, FOUND-04, ROLE-01..ROLE-05, UI-03 (verifies SC1, SC2, SC5)
- **Files:** `src/shared/session/can.test.ts`, `src/shared/session/store.test.ts`, `src/shared/lib/money.test.ts`, `src/shared/i18n/plural.test.ts`, `src/shared/i18n/date.test.ts`, `src/app/providers/theme-bootstrap.test.ts`, `src/test/components-json.test.ts`, `src/shared/session/session-swap.test.ts`
- **Action:** Implement tests per RESEARCH §Validation Architecture mapping. `theme-bootstrap.test.ts` extracts the IIFE source from `index.html` (read via `fs`), `eval`s it inside jsdom with localStorage seeded, asserts `<html>` carries `dark`. `components-json.test.ts` JSON-parses `components.json`, asserts `style==='new-york'`, `tailwind.baseColor==='neutral'`, and `registries['@reui']` matches the URL. `session-swap.test.ts` substitutes a fake session source object and proves `can()` outputs are unchanged (ROLE-05 contract).
- **Verify:** `pnpm test --run` exits 0 with ≥ 25 passing assertions.
- **Acceptance:** Coverage of all listed reqs; CI-stable.

#### T7.2 — ESLint fixture + assert-violations script
- **Wave:** 7 · **Deps:** T2.3, T6.2, T4.6 · **Reqs:** FOUND-06, FOUND-07 (verifies SC4)
- **Files:** `src/__fixtures/eslint-violations/raw-palette.tsx`, `src/__fixtures/eslint-violations/mock-import.ts`, `src/__fixtures/eslint-violations/api-mode-leak.ts`, `scripts/assert-eslint-fixtures.mjs`, `package.json` (add `lint:fixtures` script)
- **Action:**
  - Three fixture files: one with `<div className="bg-white text-slate-900" />`, one importing `@/shared/api/services/mock`, one reading `import.meta.env.VITE_API_MODE` from outside `shared/api/**`.
  - `scripts/assert-eslint-fixtures.mjs`: runs `eslint --config scripts/eslint.fixtures.config.js src/__fixtures/eslint-violations` (dedicated fixtures config re-exports the main rules but drops the `ignores` for `src/__fixtures/**`), expects exit code 1 AND ≥ 3 errors (one per file). Exits 0 only if those conditions hold.
  - `package.json`: `"lint:fixtures": "node scripts/assert-eslint-fixtures.mjs"`.
  - Update flat-config `ignores` so the main `pnpm lint` does NOT pick fixtures (only the script does).
- **Verify:** `pnpm lint:fixtures` exits 0 (i.e. ESLint correctly errored on every fixture); `pnpm lint` (main) still green.
- **Acceptance:** SC4 demonstrably enforced.

#### T7.3 — Manual smoke checkpoint (SC1 + SC3 + UI-04 1366×768)
- **Wave:** 7 · **Deps:** all prior · **Reqs:** FOUND-01, FOUND-03, FOUND-04, UI-03, UI-04 (verifies SC1, SC3 visually, plus 1366×768)
- **Files:** `.planning/phases/01-foundation-shell/SMOKE-NOTES.md` (created during the checkpoint)
- **Action:** Human-in-the-loop checklist; runner records results into `SMOKE-NOTES.md`:
  1. `pnpm dev`; open in fresh incognito window at viewport **1366×768**.
  2. Confirm Russian shell strings, "Главная" highlighted, sidebar collapsed by default at this width.
  3. Throttle to "Slow 3G", set `localStorage['sportzal:ui:v1']` to `{state:{theme:'dark'},version:1}`, hard reload — assert **no light flash** (SC3).
  4. Toggle role to "Ресепшн" — sidebar drops Финансы + Настройки; navigate manually to `/finance` URL — verify redirect to `/?forbidden=...`.
  5. Hard reload — role still Ресепшн (SC2).
  6. Resize to desktop width (1920) — sidebar can be expanded via trigger; expanded state persists across reload via `sportzal:ui:v1`.
  7. Run gate suite: `pnpm typecheck && pnpm lint && pnpm lint:fixtures && pnpm test --run && pnpm build`.
- **Verify:** All seven steps pass; gate suite exits 0.
- **Acceptance:** All five SCs satisfied; `SMOKE-NOTES.md` committed.

---

## 4. Requirements Traceability Matrix

| Req | Description (short) | Task(s) |
|---|---|---|
| **FOUND-01** | App shell (header + sidebar + content) | T5.1, T5.2, T5.3 |
| **FOUND-02** | Role toggle persisted via Zustand `persist` | T4.1, T5.2 (RoleSwitcher), T3.4 (rehydrate), T7.1 (`store.test.ts`) |
| **FOUND-03** | Theme toggle + blocking script, no FOUC | T3.3 (index.html script), T4.5 (UI prefs store + ThemeProvider), T5.2 (ThemeSwitcher), T7.1 (`theme-bootstrap.test.ts`), T7.3 (manual) |
| **FOUND-04** | Russian shell, DD.MM.YYYY, 24h, Monday, NBSP money, 3-form plurals | T4.4 (i18n + helpers), T3.3 (`<html lang="ru">`), T5.2 (RU labels), T7.1 (i18n tests), T7.3 |
| **FOUND-05** | TanStack Router file-based + typed search + root layout | T3.1, T3.2, T5.3, T5.4 |
| **FOUND-06** | ESLint blocks `services/{mock,http}` imports + `VITE_API_MODE` leakage | T2.3, T6.1, T6.2, T6.3, T4.6, T7.2 |
| **FOUND-07** | Semantic tokens only; raw palette banned | T2.1 (CSS tokens), T2.3 (ESLint rule), T5.2 (compliant header/sidebar), T7.2 (fixture) |
| **ROLE-01** | Single `routeRegistry` + `can()` consumed by sidebar/router/RoleGate | T4.2, T4.3, T5.2 (sidebar filter), T5.4 (router beforeLoad), T7.1 (`can.test.ts`) |
| **ROLE-02** | Reception scope boundary | T4.2 (`OWNER_ONLY` table), T7.1 (table-driven test) |
| **ROLE-03** | Owner = superset of Reception | T4.2 (owner short-circuit), T7.1 |
| **ROLE-04** | Destructive actions Owner-only (refund, delete client, edit templates) | T4.2 (entries in `OWNER_ONLY`), T7.1 |
| **ROLE-05** | Replacing session source preserves ACL logic | T3.2 (router context `getSession` indirection), T4.2 README contract, T6.3 (403 hook stub), T7.1 (`session-swap.test.ts`) |
| **UI-03** | reui.io coexists with shadcn via `@reui` registry; both read same CSS vars | T2.1 (reui-extra tokens in `index.css`), T2.2 (`components.json` `@reui` entry), T7.1 (`components-json.test.ts`) |
| **UI-04** | Responsive at 1366×768 | T5.2 (sidebar `defaultOpen={false}` rule + `<SidebarTrigger>`), T7.3 (manual viewport check) |

**Coverage:** 14/14 requirements have at least one task; cross-task coverage on FOUND-02/03/04/06 and ROLE-01.

---

## 5. Success-Criteria Verification Plan

| SC | Criterion | Verifying task(s) | How |
|---|---|---|---|
| **SC1** | Shell rendered in Russian with DD.MM.YYYY / 24h / Monday-week | T7.1 (`date.test.ts`, dictionary spot-check), T7.3 step 2 | Unit asserts `formatDate(...)` → `'21.04.2026'`, `t('shell.nav.clients')` → `'Клиенты'`; manual confirms visible labels. |
| **SC2** | Role toggle survives hard reload | T7.1 (`store.test.ts`: rehydrate path), T7.3 step 5 | Test seeds `localStorage`, calls `persist.rehydrate()`, asserts `getState().role`. Manual reload confirms in-browser. |
| **SC3** | Theme toggle light/dark/system, no FOUC via blocking script | T7.1 (`theme-bootstrap.test.ts`), T7.3 step 3 | Test `eval`s the IIFE in jsdom with seeded localStorage, asserts `<html>` carries `dark`. Manual: Slow-3G reload shows no flash. |
| **SC4** | ESLint boundary enforcement (services + raw palette + VITE_API_MODE) | T7.2 (`assert-eslint-fixtures.mjs`) | Three fixture files; script confirms ESLint exits 1 with ≥ 3 errors. |
| **SC5** | Single `routeRegistry` + `can()` consumed by sidebar, router beforeLoad, RoleGate | T7.1 (`can.test.ts`, `session-swap.test.ts`), T7.3 step 4 | Tests cover full table; manual confirms sidebar filters AND `/finance` redirect both stem from the same `can()` call. |

Phase gate: **all five SCs green AND** `pnpm typecheck && pnpm lint && pnpm lint:fixtures && pnpm test --run && pnpm build` exits 0.

---

## 6. Risks & Mitigations

| # | Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|---|
| R1 | reui registry returns 404 for `new-york` style (OQ1) — would force per-component `--style base-nova` and a SHADCN-DIVERGENCE wrapper. | MEDIUM | LOW (Phase 1 ships only the registry entry, no reui components yet) | T2.2 step 1 probe; document outcome in `components.json` header. Real cost paid in Phase 2 when Data Grid is installed. |
| R2 | TanStack Router plugin order silently broken → routes don't HMR | LOW | MEDIUM (slows Phase 2+) | T3.1 explicitly orders `tanstackRouter()` BEFORE `react()`; T5.4 verifies HMR by editing a placeholder route during dev. |
| R3 | Persisted-store rehydration race (RESEARCH §Pitfall 2) → owner sidebar flash on Reception reload | LOW (mitigated) | LOW (UX only, not security) | T4.1 sets `skipHydration: true`; T3.4 awaits both stores before render. |
| R4 | ESLint flat-config palette regex misses obscure shadcn-block colors | MEDIUM | LOW | Run `pnpm lint` after every `shadcn add` (T5.1 enforces); refine regex if missed; T7.2 fixture hard-asserts the canonical case. |
| R5 | `tw-animate-css` package name churn (A1) | LOW | LOW | Pin in lockfile; if install fails, fall back to `tailwindcss-animate` and update import. |
| R6 | `oklch()` rendering inconsistency on older Safari (< 16.4) | LOW | LOW | Project targets evergreen browsers per RESEARCH §Environment; document baseline in README. |
| R7 | CSP `unsafe-inline` allows future XSS surface | LOW | MEDIUM (in v2) | D-CSP comment + Phase 7 hardening TODO; v1 is internal mock. |
| R8 | Phase commit becomes massive (auto-waves + many small tasks) | MEDIUM | LOW | `git: phase-commits` per config — single commit at phase close is the project convention; granular commits per wave are fine since `gsd-execute-phase` will batch. |

---

## 7. Out-of-Scope (explicit reminder)

The following are **explicitly NOT** part of Phase 1, even though they may seem related:

- **No mock DB seeding** with `@faker-js/faker` — Phase 2 (DATA-06).
- **No entity Zod schemas** (`Client`, `Membership`, `ClassOccurrence`, …) — Phase 2 (DATA-01, DATA-02).
- **No real forms** beyond the role/theme dropdowns — `react-hook-form`, `@hookform/resolvers`, `zod` are NOT installed in Phase 1; deferred to Phase 2 with the canonical Form template.
- **No calendar / `react-big-calendar`** — Phase 4 (SCHED-01).
- **No reports / Recharts** — Phase 6 (FIN-06) and Phase 7 (DASH-02).
- **No notifications popover content** — bell renders as an icon-only stub (Phase 7 NOTF-01 fills it).
- **No profile content** — profile menu shows the role label only.
- **No auth, no SMS, no fiscal, no payments, no websockets** — anti-features per `CLAUDE.md` and `REQUIREMENTS.md` "Out of Scope".
- **No List / Detail / Form templates** — Phase 2 (UI-01).
- **No reui components installed** (only the `@reui` registry entry) — Phase 2 installs Data Grid first.
- **No 403-analog mock-service implementation** — Phase 2; Phase 1 only ships the architectural seam (T6.3 stub) and the README contract (T4.2 README) so ROLE-05 holds at the design level.
- **No Playwright** — manual smoke at 1366×768 is sufficient for Phase 1 (per A9).

---

## 8. Ready-for-Execution Checklist

Execute-phase MUST confirm before starting:

- [ ] `RESEARCH.md` present in `.planning/phases/01-foundation-shell/`
- [ ] `PLAN-P1.md` (this file) present and validated by plan-checker
- [ ] `pnpm` v9 + Node v20+ available on the runner
- [ ] Git working tree clean (so phase commit is unambiguous)
- [ ] `.planning/config.json` confirms `execution: "auto-waves"` and `granularity: "fine"`
- [ ] No prior `package.json` exists at repo root (this is a greenfield init)
- [ ] User has been informed (in Russian per `language.user_communication`) that Phase 1 takes ~7 waves and ends with a manual 1366×768 smoke check
- [ ] Plan-checker has not flagged any ⚠ items in §3 task list
- [ ] OQ1 reui style probe scheduled inside T2.2 (no pre-flight required)

Phase 1 close: phase commit message `feat(phase-01): scaffold foundation & shell`; mark all 14 requirements as ✅ in `.planning/REQUIREMENTS.md` traceability table; advance `.planning/STATE.md` cursor to Phase 2; update `ROADMAP.md` Plans column from `TBD` to `1`.

---

*Plan authored: 2026-04-21 by `gsd-planner` (opus). Granularity: fine. Waves: 7. Tasks: 22. Reqs covered: 14/14.*
