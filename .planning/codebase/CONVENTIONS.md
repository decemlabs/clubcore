# Coding Conventions

**Analysis Date:** 2026-04-30

## Formatting (Prettier)

Configured in `frontend/.prettierrc.json`:

```json
{
  "semi": false,
  "singleQuote": true,
  "printWidth": 100,
  "trailingComma": "all",
  "plugins": ["prettier-plugin-tailwindcss"]
}
```

- No semicolons (ASI relied on).
- Single quotes for strings; backticks for templates.
- 100-char line width.
- Trailing commas everywhere (cleaner diffs).
- Tailwind classes auto-sorted by `prettier-plugin-tailwindcss`.

`.prettierignore` excludes `dist`, `node_modules`, generated files, and `.planning/`.

## Linting (ESLint 9 flat config)

Configured in `frontend/eslint.config.js`. Beyond the recommended JS + TypeScript + React Hooks + React Refresh sets, the project enforces three project-specific rules:

### 1. Layered import boundary (`import/no-restricted-paths`)

UI code (`features/`, `routes/`, `entities/`, `shared/ui/`, `app/`) **cannot import** from `shared/api/services/mock/**` or `shared/api/services/http/**`. Always go through the swap seam (`@/shared/api/services`) or a TanStack Query hook. See `eslint.config.js:48-69`.

### 2. `VITE_API_MODE` chokepoint

Reading `import.meta.env.VITE_API_MODE` is allowed only inside `src/shared/api/**`. Everywhere else, import `API_MODE` from `@/shared/api/config/env`. See `eslint.config.js:88-101`.

### 3. Raw Tailwind palette ban

`className` strings/templates cannot contain raw color utilities (`bg-white`, `text-slate-900`, `border-blue-500`, etc.). Use semantic shadcn tokens (`bg-background`, `text-muted-foreground`, `border-border`). Regex at `eslint.config.js:8-9`; rule at `eslint.config.js:71-83`.

### Negative-test fixtures

`src/__fixtures/` contains files that **must fail lint**. `pnpm lint:fixtures` runs `scripts/assert-eslint-fixtures.mjs` to verify the rules still trigger. Examples:
- `api-mode-leak.ts` — illegal `VITE_API_MODE` access.
- `features/illegal-mock-import.ts` — imports `services/mock` directly.
- `raw-palette.tsx` — uses `bg-slate-900`.

Fixtures are excluded from the main lint pass (`eslint.config.js:14-23`).

## TypeScript

Strict mode + extras enabled in `tsconfig.app.json`:

- `strict: true`
- `noUncheckedIndexedAccess: true` — array/record access is `T | undefined`.
- `noUnusedLocals: true`
- `noUnusedParameters: true`
- `target: ES2022`
- Path alias `@/* → src/*`.

`tsc -b --noEmit` runs as the standalone `typecheck` script and ahead of every Vite build (`build: tsc -b && vite build`).

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

Import order (Prettier + manual; no enforced sort plugin):

1. External packages (`react`, `@tanstack/*`, `zustand`, `zod`, ...).
2. Type-only imports (`import type { ... } from '...'`) — explicit `type` keyword preferred where possible.
3. Internal aliased imports via `@/` (rooted at `src/`).
4. Relative imports (`./`, `../`) — only inside the same folder.

Example (`src/app/main.tsx:1-11`):

```ts
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
```

`type` imports flagged with the keyword (`src/routes/__root.tsx:4`):

```ts
import type { RouterContext } from '@/app/router'
```

## Component Patterns

### Function components only

No class components. Component declared as a named `function`, not `const` arrow, when it serves as the route's `component`:

```tsx
// src/routes/index.tsx
export const Route = createFileRoute('/')({
  validateSearch: searchSchema,
  component: IndexPage,
})

function IndexPage() {
  const search = Route.useSearch()
  // ...
}
```

### Props typed via `interface` (or `type` when union/mapped)

```ts
// src/test/utils.tsx
interface ProvidersProps {
  children: ReactNode
  client: QueryClient
}
```

### Early-return guards

Throw or short-circuit on invalid state instead of nesting:

```ts
// src/app/main.tsx
const rootEl = document.getElementById('root')
if (!rootEl) throw new Error('#root element not found')
```

```ts
// src/routes/clients.tsx
beforeLoad: ({ context, location }) => {
  const { role } = context.getSession()
  if (!can(role, 'view', 'clients')) {
    throw redirect({ to: '/', search: { forbidden: location.href } })
  }
}
```

### Shadcn primitives are not hand-edited

Files in `src/shared/ui/*.tsx` (button, input, dialog, sidebar, …) come from shadcn `new-york`. Customizations go in **wrappers**, not in those files. If divergence is unavoidable, mark with `// SHADCN-DIVERGENCE: <reason>` so future updates from the registry can be re-applied carefully. ESLint disables `react-refresh/only-export-components` for these primitives only (`eslint.config.js:110-127`) because they co-export variant tables (e.g. `buttonVariants`).

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
  - `bg-background`, `bg-card`, `bg-muted`, `bg-popover`, `bg-primary`, `bg-destructive`
  - `text-foreground`, `text-muted-foreground`, `text-destructive`
  - `border-border`, `border-input`, `ring-ring`
- Class composition via `cn()` (`src/shared/lib/cn.ts`) which wraps `clsx` + `tailwind-merge`.

Example (`src/routes/index.tsx:21-25`):

```tsx
<div
  role="alert"
  className="border-destructive/50 bg-destructive/10 text-destructive rounded-md border p-3 text-sm"
>
```

## Comments / JSDoc

- Sparse comments. Prefer self-explanatory names over commentary.
- JSDoc for public APIs and non-obvious helpers, with `@example`:

  ```ts
  /**
   * Format an integer in minor units (kopecks) as a Russian RUB currency string.
   * @example formatMoney(123456) // "1 234,56 ₽"
   */
  export function formatMoney(minor: number): string { ... }
  ```

- Long-form rationale lives in module top-doc blocks (e.g. `src/shared/api/services/index.ts:1-13` explains the swap seam philosophy).
- Phase-deferred work tagged with `// TODO Phase N:` (e.g. `index.html` line 7 for CSP nonce work in Phase 7).

## Error Handling Patterns

- `try/catch` only at boundaries that can fail (localStorage shim, JSON.parse during theme bootstrap, network calls).
- Defensive `try/catch` swallows in non-critical paths use a `_e` parameter and `/* noop */` comment so the silence is intentional (e.g. `frontend/index.html` theme bootstrap).
- Domain errors are typed (`DomainError { code, message, fields? }`) — not raw `Error`.

## Testing Conventions

See `TESTING.md` for full details. Highlights:

- Vitest + jsdom; `src/test/setup.ts` installs an in-memory localStorage shim and resets state per test.
- `renderWithProviders(ui, { role })` from `src/test/utils.tsx` is the standard component test entry point.
- Tests live next to source (`*.test.ts(x)` siblings).
- `describe` blocks group by concern; `it` names read as sentences.

---

*Conventions analysis: 2026-04-30*
