# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project purpose

Admin panel for a chain of fitness clubs (ClubCore). The UI is in Russian. The project is built by **incrementally integrating standalone HTML design templates** (Dashboard, Clients, Schedule, Plans/Абонементы, Trainers, Cashbox, Messages, Reports, Attendance, Load, Settings + a client detail page) into this React SPA.

**Integration philosophy (governing).** Treat each reference as a **design specification, not a literal copy**. Reproduce its visual identity closely — spacing, sizes, proportions, hierarchy, colors, typography, and interaction states — but write clean, production-ready, **responsive** React; never port the source HTML/CSS verbatim. Tasteful improvements (accessibility, responsiveness, modern patterns) are encouraged; don't degrade the design for technical convenience. Prefer existing shadcn/ui components where they fit naturally, and build clean custom components (Tailwind + theme tokens) where fidelity needs it — whichever is the better-engineered result while preserving visual identity. Design every breakpoint deliberately (mobile/tablet/desktop): no horizontal scroll, overlap, or clipped content. (This supersedes any earlier "pixel-for-pixel 1:1, change nothing" or "theme-only generic components" framing.)

## Commands

This package is now part of the clubcore pnpm workspace (`@clubcore/admin-app`). Run all commands from the **repo root** using pnpm workspace filters.

```bash
# Install deps (run from repo root — generates root pnpm-lock.yaml)
pnpm install

# Dev server on http://localhost:5173
pnpm -F @clubcore/admin-app dev

# Production build → ./apps/admin-app/dist
pnpm -F @clubcore/admin-app build

# Preview production build
pnpm -F @clubcore/admin-app preview

# TypeScript check
pnpm -F @clubcore/admin-app typecheck

# ESLint
pnpm -F @clubcore/admin-app lint

# Vitest unit + smoke tests
pnpm -F @clubcore/admin-app test

# Vitest in watch mode
pnpm -F @clubcore/admin-app test:watch
```

Tests run on **vitest** (`pnpm -F @clubcore/admin-app test`): unit tests for pure logic (`src/lib/format.test.ts`, `src/features/clients/sort.test.ts`) plus a route smoke suite (`src/app/router-smoke.test.tsx`) that renders every registered route.

To add shadcn/ui components: `pnpm dlx shadcn@latest add button card dialog select …` (run from the `apps/admin-app/` directory or pass `--cwd apps/admin-app` from the root).

## Architecture

React 18 + TypeScript (strict) SPA. Vite 5 bundler, Bun runtime/package manager. Path alias `@/*` → `src/*`.

Entry flow: `src/main.tsx` → `App.tsx` → `app/providers.tsx` (wraps `QueryClientProvider` + Radix `TooltipProvider`) → `RouterProvider` with `app/router.tsx`.

**Routing.** All routes are children of a single `AppLayout` element (`app/router.tsx`), so Sidebar/Header never remount on navigation. Route paths live ONLY in `app/routes.ts` as the `ROUTES` constant — reference these constants, never hardcode path strings. `ROUTES.client(id)` is a function that also doubles as the route pattern (`ROUTES.client()` → `/clients/:clientId`). Page routes load lazily via the data-router `lazy:` property (`app/router.tsx`); new page routes MUST follow the same `lazy: async () => ({ Component: (await import('…')).XxxPage })` shape so the route stays code-split.

**Layered component model** (this is the core convention — every integrated template gets decomposed across these layers):
- `layouts/AppLayout/` — the shell: Sidebar (driven by `nav-items.ts`), Header (breadcrumb derived from current route + global search). Shared chrome lives here.
- `components/ui/` — base shadcn primitives (Button, Card, Badge, Avatar, ToggleGroup, etc.). `PagePlaceholder` is a temporary stand-in until a page's reference arrives.
- `components/{data,charts,icons}/` — shared tables/lists, Recharts wrappers, and icon re-exports (`components/icons` re-exports **lucide-react**, the project icon set — don't inline template SVGs). Bespoke chart markup is rebuilt with Recharts (the shadcn `Chart`), not ported as raw CSS/SVG.
- `components/layout/` — shared page-composition pieces: `Card.tsx` (+`CardHeader`/`CardLink`), `PageHeader.tsx`, `SectionHead.tsx`, `StatStrip.tsx`.
- `components/modals/` — the app-wide modal system: `ModalsProvider` + `modals-context.ts` + one file per dialog + shared `fields.tsx`.
- `components/feedback/` — `EmptyState.tsx`, `ErrorPage.tsx`, `RouteErrorBoundary.tsx`.
- `components/settings/` — settings-page controls (`controls.tsx`, `ScrollspyNav.tsx`), shared by settings/system-settings/branch-settings pages.
- `features/<domain>/` — domain logic reused across pages: `types.ts`, `api.ts` (TanStack Query hooks), `components/`.
- `pages/<route>/` — one folder per route; page-specific composition goes in `pages/<route>/components/`.

**Data layer.** Pages must consume data through TanStack Query hooks (e.g. `useClients()`) defined in `features/<domain>/api.ts` — even while the backend is absent. There is no real API yet: hooks resolve mock data from `src/mocks/` via `mockResponse()` in `api/client.ts`. When the backend lands, only the hook's `queryFn` changes; pages stay untouched. `api/client.ts` already reads `VITE_API_BASE_URL`. Pages render `<PageLoading />` while `isPending` and `<PageError onRetry={…} />` on `isError` (both from `components/feedback/PageState.tsx`) — new data-driven pages must handle these states, not just the success branch.

**Styling.** Tailwind **v4** (CSS-first via the `@tailwindcss/vite` plugin — there is no `tailwind.config.ts`). Raw color values live in `src/styles/tokens.css` (`:root` + `[data-theme="dark"]`); `src/styles/globals.css` maps them to utilities via `@theme inline { --color-*: var(--raw) }`, including the full shadcn semantic set (`--color-primary`, `--color-accent`, `--color-sidebar`, …). Brand emerald = `primary`; shadcn's `accent` = neutral hover. Use semantic classes (`bg-surface`, `text-fg-muted`, `bg-primary`), NOT raw values. Compose conditional classes with `cn()` from `lib/cn.ts` (clsx + tailwind-merge); use `class-variance-authority` for component variants. Token values come from the reference's palette/radii/typography (treated as the design system). The theme also defines a chart palette (`--chart-1..5`) for the shadcn `Chart`. **Dark theme** works by redefining the same `--color-*` vars under `[data-theme="dark"]` in `tokens.css`, so semantic classes switch automatically — no `dark:` variant needed for the project's own colors. `globals.css` declares `@custom-variant dark` bound to `[data-theme="dark"]`, so explicit `dark:` utilities key off the same attribute; toggle by setting `data-theme` on `<html>`.

**Formatting/i18n.** All user-facing strings are Russian. Use the helpers in `lib/format.ts` (`formatRub`, `formatInt`, `formatDateRu`, `formatWeekdayLongRu`, `formatRelativeRu`, `formatTime`) — they wrap `Intl` and `date-fns` with the `ru` locale. There is no i18n framework; strings are inline.

## Component library (shadcn/ui)

shadcn/ui is wired through `components.json` + `.mcp.json` (the shadcn MCP server). Add primitives with `bunx shadcn@latest add button card dialog select …` → they land in `components/ui/`. (ReUI was evaluated and removed — use base shadcn/ui + clean custom components only.)

- **Do NOT run `shadcn init`** — it rewrites the Tailwind config + `globals.css` and clobbers the curated tokens. The setup is hand-maintained. `aliases.utils` → `@/lib/cn` (not the default `@/lib/utils`); `cssVariables: true`; no `tailwind.config.ts` (v4); `@` resolves from the **root** `tsconfig.json`.
- `bun` is on PATH here, so the CLI installs deps with bun (which tolerates the `@eslint/js`↔`eslint` peer-dep conflict). The "move `bun.lock` aside + add `.npmrc legacy-peer-deps`" npm-fallback is only needed when bun is absent.
- `--yes` does NOT suppress the per-file "overwrite?" prompt, and the CLI hangs on it in a non-TTY shell. Pipe **`yes N | bunx shadcn@latest add …`** to auto-decline overwrites and keep curated/existing files.
- After an add, the CLI may append CSS vars / a `.dark {…}` block to `globals.css`. Reconcile them into the curated structure (raw values → `tokens.css` `:root`/`[data-theme="dark"]`, `@theme inline` mappings → `globals.css`); **delete any `.dark {…}` block** (this project keys dark off `[data-theme="dark"]`, not `.dark`) and never let it override brand tokens (e.g. `--success`).
- Vendored components trip `react-refresh/only-export-components`; `eslint.config.js` disables that rule for `components/ui/**`. React is 18 — freshly generated components may need small strict-TS fixes (`import type` under `verbatimModuleSyntax`; react-day-picker v10 uses `month_grid`, not `table`).
- Radix is imported ONLY from the `radix-ui` monolith (e.g. `import { Tooltip as TooltipPrimitive } from 'radix-ui'`), never from individual `@radix-ui/react-*` packages. After any `shadcn add`, check `package.json` and convert any individual `@radix-ui/*` the CLI pinned back to the monolith.

## Template integration workflow

When a new screen reference is provided (apply the integration philosophy under **Project purpose** — faithful visual, clean responsive code, not a literal HTML copy):
1. Map it to its route (`app/router.tsx` / `app/routes.ts`).
2. Extract any new design tokens into `tokens.css` (raw values) + `globals.css` (`@theme inline`) before building.
3. Decompose across the layer model (shared chrome → `AppLayout`; primitives → `components/ui`; domain widgets → `features/*/components`; page composition → `pages/<route>/components`). `pages/dashboard` + `features/dashboard` are the worked reference for this structure.
4. Put seed data in `mocks/<entity>.ts`, types in `features/<entity>/types.ts`, expose via a TanStack Query hook the page calls, and register the mock in `mocks/index.ts`.
5. Implement all interaction states (hover/active/focus/disabled) and design each breakpoint (no horizontal scroll/overlap/clipping). Verify with the preview server against the reference in **light and dark**; keep `typecheck` + `lint` green.

When a component reappears in a second screen, promote it from page-local to `components/ui` / `features/*`.
