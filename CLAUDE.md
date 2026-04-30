<!-- GSD:project-start source:PROJECT.md -->
## Project

**Sportzal**

Sportzal — CRM для тренажёрного зала. Сейчас пет-проект на один зал: управление клиентами, абонементами, посещениями, расписанием, бронированиями, тренерами, биллингом и уведомлениями. Под рынок РФ/СНГ. Frontend — admin-панель на React 19 (Vite + TanStack Router) с моками; backend сейчас отсутствует и будет построен в текущем milestone как модульный монолит на FastAPI.

**Core Value:** Соло backend-разработчик с AI-агентами должен уметь поэтапно наращивать бизнес-фичи зала на стабильном, архитектурно ограниченном каркасе — без переписывания структуры по мере роста.

### Constraints

- **Tech stack — Backend**: Python 3.12 + uv + FastAPI 0.115+ + SQLAlchemy 2.0 async + Alembic async + Pydantic v2 + Postgres 16 + Redis 7 + ARQ + structlog — закреплено пользователем; альтернативы не рассматриваются в Phase A
- **Tech stack — Frontend**: пакетный менеджер pnpm (workspaces); существующий frontend стек (React 19, Vite 6, TanStack) не трогаем
- **Region**: РФ/СНГ — Stripe запрещён; платежи только ЮKassa; Telegram как первичный канал
- **Tooling**: ruff + mypy strict + import-linter обязательны с Phase A — архитектурные правила должны быть выполнимы локально
- **Testing**: backend-тесты используют `httpx ASGITransport` (не реальный сетевой стек) и `pytest-asyncio`
- **Frontend integrity**: `apps/admin-web` — это перенос `./frontend`, никаких правок внутренней структуры или моков в Phase A
- **Placeholders only**: `packages/ui` и `packages/api-client` — только `package.json` + `README.md` в Phase A; никакого реального кода
<!-- GSD:project-end -->

<!-- GSD:stack-start source:codebase/STACK.md -->
## Technology Stack

## Languages
- TypeScript ~5.7.2 - Application source code (`src/**/*.ts`, `src/**/*.tsx`), strict mode enabled
- JavaScript - Build and tooling scripts (`vite.config.ts`, `eslint.config.js`, Prettier config)
- HTML5 - Entry point and theme bootstrap (`index.html`)
- CSS - Tailwind CSS v4 via Vite plugin (CSS-first `@theme` syntax, no explicit CSS files)
## Runtime
- Node.js ≥20.0.0 (specified in `package.json` engines field)
- pnpm ≥9.0.0 (v9.15.9 in lockfile `pnpm-lock.yaml`)
- Lockfile: `pnpm-lock.yaml` present
## Frameworks
- React 19.2.5 - UI library (`react`, `react-dom` in dependencies)
- TanStack Router 1.95.0 - File-based routing with typed search (`@tanstack/react-router`, routed from `src/routes/`)
- TanStack Query (React Query) 5.59.0 - Server state & caching (`@tanstack/react-query` with devtools `@tanstack/react-query-devtools@5.99.2`)
- TanStack Table (React Table) 8.20.0 - Data table abstraction (`@tanstack/react-table`)
- Vite 6.0.7 - Build tool & dev server with React plugin (`@vitejs/plugin-react@4.3.4`)
- Tailwind CSS v4.0.0 - Utility-first CSS via `@tailwindcss/vite@4.0.0` plugin
- shadcn/ui - Copy-paste primitive components (new-york style, neutral base color)
- Radix UI primitives (headless) - Underlying components for shadcn
- Lucide React 0.469.0 - Icon library
- Sonner 1.7.4 - Toast/notification UI
- react-hook-form 7.54.0 - Form state management
- Zod 3.24.1 - Schema validation library (TypeScript-first)
- @hookform/resolvers 3.9.1 - Zod integration for react-hook-form
- class-variance-authority 0.7.1 - Type-safe CSS class composition
- clsx 2.1.1 - Conditional className utility
- tailwind-merge 2.6.0 - Smart Tailwind class merging
- tw-animate-css 1.2.4 - Custom animation utilities for Tailwind
- date-fns 4.1.0 - Date manipulation (Russian locale `ru` available)
- next-themes 0.4.6 - Theme persistence and switching (light/dark)
- Zustand 5.0.2 - Lightweight state management with persistence middleware
- Vitest 2.1.8 - Fast unit test runner (config: `vitest.config.ts`)
- jsdom 25.0.1 - DOM implementation for tests
- ESLint 9.17.0 (flat config) - Linting with custom rules in `eslint.config.js`
- Prettier 3.8.3 - Code formatting with `prettier-plugin-tailwindcss@0.7.2` for class sorting
- TypeScript 5.7.2 - Type checking (strict mode, noUncheckedIndexedAccess, noUnusedLocals)
- @faker-js/faker 9.3.0 - Seeded (seed=42) mock data generation for development and mock services
## Configuration
- Vite env vars (imported via `import.meta.env`)
- Configuration files: `.env.example` and `.env.development`
- localStorage keys (versioned):
- Vite config: `vite.config.ts` (plugins: tanstackRouter with autoCodeSplitting, react, tailwindcss; port 5173)
- TanStack Router config: routes directory at `src/routes/`, auto-generated tree at `src/routeTree.gen.ts`
- TypeScript build: `tsc -b` before Vite (composite project with app + node configs)
- Target: ES2022 (esbuild target for modern browsers)
## Platform Requirements
- Node.js ≥20.0.0
- pnpm ≥9.0.0
- Tested on macOS (zsh shell)
- Dev server port: 5173
- Static SPA (frontend-only v1)
- Browser target: ES2022 (modern Chrome, Firefox, Safari, Edge)
- Build output: `dist/` (Vite default)
- No server-side rendering (React CSR)
<!-- GSD:stack-end -->

<!-- GSD:conventions-start source:CONVENTIONS.md -->
## Conventions

## Formatting (Prettier)
- No semicolons (ASI relied on).
- Single quotes for strings; backticks for templates.
- 100-char line width.
- Trailing commas everywhere (cleaner diffs).
- Tailwind classes auto-sorted by `prettier-plugin-tailwindcss`.
## Linting (ESLint 9 flat config)
### 1. Layered import boundary (`import/no-restricted-paths`)
### 2. `VITE_API_MODE` chokepoint
### 3. Raw Tailwind palette ban
### Negative-test fixtures
- `api-mode-leak.ts` — illegal `VITE_API_MODE` access.
- `features/illegal-mock-import.ts` — imports `services/mock` directly.
- `raw-palette.tsx` — uses `bg-slate-900`.
## TypeScript
- `strict: true`
- `noUncheckedIndexedAccess: true` — array/record access is `T | undefined`.
- `noUnusedLocals: true`
- `noUnusedParameters: true`
- `target: ES2022`
- Path alias `@/* → src/*`.
## Naming
| Kind | Convention | Example |
|---|---|---|
| React components | `PascalCase` | `AppShell`, `RoleGate`, `ProfileMenu` |
| Hooks | `useCamelCase` | `useSessionStore`, `useTheme` |
| Functions / variables | `camelCase` | `formatMoney`, `routeRegistry`, `queryClient` |
| Constants | `UPPER_SNAKE_CASE` | `OWNER_ONLY`, `STORAGE_KEY`, `SESSION_STORAGE_KEY` |
| Types / interfaces | `PascalCase` | `Role`, `SessionState`, `RouterContext`, `Resource` |
| Branded IDs (planned) | `PascalCase` ending in `Id` | `ClientId`, `SubscriptionId` (UUIDv4 brand) |
| Files: components | `PascalCase.tsx` | `RoleGate.tsx` |
| Files: hooks/libs | `camelCase.ts` (kebab-case for shadcn-derived) | `uiPrefsStore.ts`, `use-mobile.ts` |
| Files: tests | `<source>.test.ts(x)`, co-located | `money.test.ts` |
## Imports
## Component Patterns
### Function components only
### Props typed via `interface` (or `type` when union/mapped)
### Early-return guards
### Shadcn primitives are not hand-edited
## State & Data Conventions
### Zustand stores
- One store per concern (`session`, `uiPrefs`).
- Persisted state uses `persist` middleware with **versioned** storage keys (`sportzal:<name>:v1`) and a `partialize` selector.
- `skipHydration: true` + manual `persist.rehydrate()` in `src/app/main.tsx` so the bootstrap is awaited before React mounts (avoids flicker between roles/themes).
### TanStack Query (target conventions)
- Per-feature `xKeys` factory (e.g. `clientsKeys.list(filter) = ['clients', 'list', filter] as const`).
- `staleTime: 30_000`, `refetchOnWindowFocus: false` (set globally on the `QueryClient`, `src/app/queryClient.ts`).
- Mutations use `onMutate`/`onError`/`onSettled` for optimistic updates with rollback.
- Route `loader` calls `queryClient.ensureQueryData` with the **same key** the hook uses.
## Domain Conventions
| Concern | Convention | Reference |
|---|---|---|
| **Money** | Integer minor units (kopecks). Format with `formatMoney(minor)` → ru-RU RUB string with NBSPs. | `src/shared/lib/money.ts` |
| **Dates** | ISO strings in domain types. Display with date-fns + `ru` locale, TZ pinned to `Europe/Moscow`. Never `new Date(dateOnlyString)` (DST risk). | `src/shared/i18n/date.ts` |
| **IDs** | Branded UUIDv4 strings (`type ClientId = Brand<string, 'ClientId'>`). | (planned) |
| **Pagination** | Endpoints return `{ items, total, page, pageSize }` — never bare arrays. | (contract, planned) |
| **Errors** | Mock services throw `DomainError { code, message, fields? }`. UI shows critical errors as inline alerts/dialogs; non-blocking acks via Sonner toast. | (planned in services) |
| **Forms** | react-hook-form + Zod via `@hookform/resolvers`. Same Zod schema validates the form **and** the mock service input. | (planned) |
| **i18n** | Single `src/shared/i18n/ru.ts` dictionary. No runtime locale switching. Russian-only v1. | `src/shared/i18n/` |
## Styling
- Tailwind v4 CSS-first via `@theme` (in `src/app/index.css`).
- Single `:root` / `.dark` token block; no theme-aware `bg-blue-500` overrides.
- Use semantic shadcn tokens for all colors:
- Class composition via `cn()` (`src/shared/lib/cn.ts`) which wraps `clsx` + `tailwind-merge`.
## Comments / JSDoc
- Sparse comments. Prefer self-explanatory names over commentary.
- JSDoc for public APIs and non-obvious helpers, with `@example`:
- Long-form rationale lives in module top-doc blocks (e.g. `src/shared/api/services/index.ts:1-13` explains the swap seam philosophy).
- Phase-deferred work tagged with `// TODO Phase N:` (e.g. `index.html` line 7 for CSP nonce work in Phase 7).
## Error Handling Patterns
- `try/catch` only at boundaries that can fail (localStorage shim, JSON.parse during theme bootstrap, network calls).
- Defensive `try/catch` swallows in non-critical paths use a `_e` parameter and `/* noop */` comment so the silence is intentional (e.g. `frontend/index.html` theme bootstrap).
- Domain errors are typed (`DomainError { code, message, fields? }`) — not raw `Error`.
## Testing Conventions
- Vitest + jsdom; `src/test/setup.ts` installs an in-memory localStorage shim and resets state per test.
- `renderWithProviders(ui, { role })` from `src/test/utils.tsx` is the standard component test entry point.
- Tests live next to source (`*.test.ts(x)` siblings).
- `describe` blocks group by concern; `it` names read as sentences.
<!-- GSD:conventions-end -->

<!-- GSD:architecture-start source:ARCHITECTURE.md -->
## Architecture

## Top-Level Layout
- `backend/` — empty placeholder (no code, no manifest). All API access in v1 happens via mock services in the frontend.
- `frontend/` — the entire shipping application (React 19 SPA, Vite, TypeScript strict).
## Architectural Pattern
```
```
```ts
```
## Layers
| Layer | Folder | Responsibility |
|---|---|---|
| Composition | `src/app/` | Root render, providers, query client, router instance, global CSS |
| Routing | `src/routes/` | TanStack Router file-based tree; thin route components, role guards in `beforeLoad` |
| Features (planned) | `src/features/<domain>/` | `api/` (hooks + keys), `components/`, `model/`, `index.ts` — none present yet |
| Entities (planned) | `src/entities/<entity>/` | Domain types + Zod schemas + pure helpers — none present yet |
| Shared | `src/shared/` | Cross-cutting code: `ui/`, `api/`, `session/`, `lib/`, `theme/`, `i18n/` |
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
- `types.ts` — `Role = 'owner' | 'reception'`, `SessionState = { role; setRole }`
- `store.ts` — Zustand store, persisted to `localStorage['sportzal:session:v1']` with `version: 1`, `skipHydration: true` (manually rehydrated in `main.tsx:13`).
- `registry.ts` — `routeRegistry: readonly RouteEntry[]` — maps each top-level path to a `Resource`, sidebar label (Russian), Lucide icon name, and i18n key. Used by sidebar, router, and tests.
- `can.ts` — `can(role, action, resource): boolean`. Owner short-circuits to `true`; reception is denied any pair listed in `OWNER_ONLY` (finance/reports/payroll/compensation/settings/owner-area views, template edits, client deletes, refunds).
- `RoleGate.tsx` — declarative wrapper for in-page action gating.
### Routing & Guards
```ts
```
### Theming (`src/shared/theme/` + `src/app/providers/ThemeProvider.tsx`)
- UI prefs Zustand store at `localStorage['sportzal:ui:v1']` holds `{ theme: 'light' | 'dark' | 'system' }`.
- Inline blocking script in `index.html` reads that key and applies `.dark` to `<html>` before React mounts (no FOUC).
- `ThemeProvider` keeps the class in sync with store changes and `prefers-color-scheme`.
- All colors are semantic shadcn tokens (`bg-background`, `text-muted-foreground`); raw palette classes are banned by ESLint (`eslint.config.js:8-9, 71-83`).
### Mock Services Container
- 120–300 ms simulated latency, configurable failure rate.
- Versioned localStorage DB key `sportzal:mock:v1`.
- `faker.seed(42)` for deterministic data.
- Mock services enforce role access (throw `DomainError` when `can(...)` is false).
## Data Flow Examples
```
```
```ts
```
## State Management
| Concern | Mechanism | Where |
|---|---|---|
| Server/cached data | TanStack Query | `src/app/queryClient.ts` + per-feature hooks |
| Session (role) | Zustand + `persist` | `src/shared/session/store.ts` |
| UI prefs (theme) | Zustand + `persist` | `src/shared/theme/uiPrefsStore.ts` |
| Route search/params | TanStack Router + Zod `validateSearch` | per-route file |
| Local component state | React hooks (`useState`/`useReducer`) | inline |
## Cross-Cutting Concerns
- **i18n:** Single Russian dictionary in `src/shared/i18n/ru.ts`, helpers `t()`, `formatDate`, `plural`. No runtime locale switching (Russian-only v1).
- **Money:** Integer minor units (kopecks); `formatMoney()` uses `Intl.NumberFormat('ru-RU', {currency:'RUB'})` — produces NBSPs.
- **IDs:** Branded UUIDv4 string types (e.g. `type ClientId = Brand<string, 'ClientId'>`).
- **Errors:** Mock services throw `DomainError { code, message, fields? }`. UI surfaces critical errors as inline alerts/dialogs, non-blocking confirmations as Sonner toasts.
- **Pagination:** Every list endpoint returns `{ items, total, page, pageSize }`. No bare arrays.
## Architectural Constraints (locked)
## Build & Plugin Order
<!-- GSD:architecture-end -->

<!-- GSD:skills-start source:skills/ -->
## Project Skills

No project skills found. Add skills to any of: `.claude/skills/`, `.agents/skills/`, `.cursor/skills/`, `.github/skills/`, or `.codex/skills/` with a `SKILL.md` index file.
<!-- GSD:skills-end -->

<!-- GSD:workflow-start source:GSD defaults -->
## GSD Workflow Enforcement

Before using Edit, Write, or other file-changing tools, start work through a GSD command so planning artifacts and execution context stay in sync.

Use these entry points:
- `/gsd-quick` for small fixes, doc updates, and ad-hoc tasks
- `/gsd-debug` for investigation and bug fixing
- `/gsd-execute-phase` for planned phase work

Do not make direct repo edits outside a GSD workflow unless the user explicitly asks to bypass it.
<!-- GSD:workflow-end -->



<!-- GSD:profile-start -->
## Developer Profile

> Profile not yet configured. Run `/gsd-profile-user` to generate your developer profile.
> This section is managed by `generate-claude-profile` -- do not edit manually.
<!-- GSD:profile-end -->
