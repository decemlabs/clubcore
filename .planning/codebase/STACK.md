# Technology Stack

**Analysis Date:** 2026-04-30

## Languages

**Primary:**
- TypeScript ~5.7.2 - Application source code (`src/**/*.ts`, `src/**/*.tsx`), strict mode enabled
- JavaScript - Build and tooling scripts (`vite.config.ts`, `eslint.config.js`, Prettier config)

**Secondary:**
- HTML5 - Entry point and theme bootstrap (`index.html`)
- CSS - Tailwind CSS v4 via Vite plugin (CSS-first `@theme` syntax, no explicit CSS files)

## Runtime

**Environment:**
- Node.js ≥20.0.0 (specified in `package.json` engines field)

**Package Manager:**
- pnpm ≥9.0.0 (v9.15.9 in lockfile `pnpm-lock.yaml`)
- Lockfile: `pnpm-lock.yaml` present

## Frameworks

**Core:**
- React 19.2.5 - UI library (`react`, `react-dom` in dependencies)
- TanStack Router 1.95.0 - File-based routing with typed search (`@tanstack/react-router`, routed from `src/routes/`)
- TanStack Query (React Query) 5.59.0 - Server state & caching (`@tanstack/react-query` with devtools `@tanstack/react-query-devtools@5.99.2`)
- TanStack Table (React Table) 8.20.0 - Data table abstraction (`@tanstack/react-table`)
- Vite 6.0.7 - Build tool & dev server with React plugin (`@vitejs/plugin-react@4.3.4`)

**UI & Styling:**
- Tailwind CSS v4.0.0 - Utility-first CSS via `@tailwindcss/vite@4.0.0` plugin
- shadcn/ui - Copy-paste primitive components (new-york style, neutral base color)
  - Registry: components.json aliases `@/shared/ui` + `@reui` registry for reui.io extras
  - Manual copies to `src/shared/ui/` (not installed via package)
- Radix UI primitives (headless) - Underlying components for shadcn
  - `@radix-ui/react-avatar@1.1.2`
  - `@radix-ui/react-dialog@1.1.4`
  - `@radix-ui/react-dropdown-menu@2.1.4`
  - `@radix-ui/react-separator@1.1.1`
  - `@radix-ui/react-slot@1.1.1`
  - `@radix-ui/react-tooltip@1.1.6`
- Lucide React 0.469.0 - Icon library
- Sonner 1.7.4 - Toast/notification UI

**Forms & Validation:**
- react-hook-form 7.54.0 - Form state management
- Zod 3.24.1 - Schema validation library (TypeScript-first)
- @hookform/resolvers 3.9.1 - Zod integration for react-hook-form

**Utilities:**
- class-variance-authority 0.7.1 - Type-safe CSS class composition
- clsx 2.1.1 - Conditional className utility
- tailwind-merge 2.6.0 - Smart Tailwind class merging
- tw-animate-css 1.2.4 - Custom animation utilities for Tailwind
- date-fns 4.1.0 - Date manipulation (Russian locale `ru` available)
- next-themes 0.4.6 - Theme persistence and switching (light/dark)
- Zustand 5.0.2 - Lightweight state management with persistence middleware
  - Session store uses `zustand/middleware` for localStorage persistence
  - UI prefs store for theme preference

**Testing:**
- Vitest 2.1.8 - Fast unit test runner (config: `vitest.config.ts`)
  - Environment: jsdom (browser emulation)
  - Setup file: `src/test/setup.ts`
  - Includes: `@testing-library/react@16.1.0`, `@testing-library/user-event@14.5.2`, `@testing-library/jest-dom@6.6.3`
- jsdom 25.0.1 - DOM implementation for tests

**Dev Tooling:**
- ESLint 9.17.0 (flat config) - Linting with custom rules in `eslint.config.js`
  - Plugins: `typescript-eslint@8.19.0`, `eslint-plugin-import@2.32.0`, `eslint-plugin-react-hooks@5.1.0`, `eslint-plugin-react-refresh@0.4.16`
  - Enforces: no direct mock/http service imports, no raw palette colors, VITE_API_MODE chokepoint
- Prettier 3.8.3 - Code formatting with `prettier-plugin-tailwindcss@0.7.2` for class sorting
  - Config: `.prettierrc.json` (no semicolons, single quotes, 100 char width, all trailing commas)
- TypeScript 5.7.2 - Type checking (strict mode, noUncheckedIndexedAccess, noUnusedLocals)
  - Compiled with tsc before Vite build (see `scripts.build`)
  - Configuration: `tsconfig.json` (references app/node configs), `tsconfig.app.json` (strict), `tsconfig.node.json` (build tools)

**Seeding & Mocking:**
- @faker-js/faker 9.3.0 - Seeded (seed=42) mock data generation for development and mock services

## Configuration

**Environment:**
- Vite env vars (imported via `import.meta.env`)
  - `VITE_API_MODE` ('mock'|'http') - Switches between mock services and HTTP layer (enforced via ESLint chokepoint `src/shared/api/config/env.ts`)
- Configuration files: `.env.example` and `.env.development`
- localStorage keys (versioned):
  - `sportzal:session:v1` - Session state (role persistence, Zustand)
  - `sportzal:ui:v1` - UI prefs (theme, Zustand)
  - `sportzal:mock:v1` - Mock DB (versioned for backward compatibility)

**Build:**
- Vite config: `vite.config.ts` (plugins: tanstackRouter with autoCodeSplitting, react, tailwindcss; port 5173)
- TanStack Router config: routes directory at `src/routes/`, auto-generated tree at `src/routeTree.gen.ts`
- TypeScript build: `tsc -b` before Vite (composite project with app + node configs)
- Target: ES2022 (esbuild target for modern browsers)

**Plugin Order (Critical):**
1. `tanstackRouter` (must be first for file-based route generation)
2. `react` (React JSX transformation)
3. `tailwindcss` (CSS-first Tailwind)

## Platform Requirements

**Development:**
- Node.js ≥20.0.0
- pnpm ≥9.0.0
- Tested on macOS (zsh shell)
- Dev server port: 5173

**Production:**
- Static SPA (frontend-only v1)
- Browser target: ES2022 (modern Chrome, Firefox, Safari, Edge)
- Build output: `dist/` (Vite default)
- No server-side rendering (React CSR)

---

*Stack analysis: 2026-04-30*
