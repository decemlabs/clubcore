# Testing

**Analysis Date:** 2026-04-30

## Framework

- **Vitest 2.1.8** as the runner.
- **jsdom 25.0.1** as the DOM environment.
- **@testing-library/react 16.1.0** + **@testing-library/jest-dom 6.6.3** + **@testing-library/user-event 14.5.2** for component-level assertions and interactions.

Configuration: `frontend/vitest.config.ts`.

```ts
test: {
  environment: 'jsdom',
  setupFiles: ['./src/test/setup.ts'],
  globals: true,
  css: false,
  include: ['src/**/*.{test,spec}.{ts,tsx}'],
  exclude: ['node_modules', 'dist', '.planning', '.claude', '.omc', 'src/__fixtures/**'],
}
```

`globals: true` exposes `describe/it/expect/beforeEach/afterEach` without imports. The `@` → `src/` path alias is duplicated under `resolve.alias` so tests pick it up.

## Scripts

From `frontend/package.json`:

| Script | Command | Purpose |
|---|---|---|
| `pnpm test` | `vitest run` | One-shot, used in CI / before commit |
| `pnpm test:watch` | `vitest` | Watch mode for local dev |
| `pnpm typecheck` | `tsc -b --noEmit` | Type-check across composite projects |
| `pnpm lint` | `eslint .` | Lint everything not ignored |
| `pnpm lint:fixtures` | `node scripts/assert-eslint-fixtures.mjs` | Verifies the negative-test fixtures still trigger their rules |

There is **no `test:coverage` script** wired and no `@vitest/coverage-*` provider installed. Coverage is not currently measured.

## Setup (`src/test/setup.ts`)

Two responsibilities:

1. **Replace `window.localStorage` with an in-memory shim.** Some jsdom builds expose a Storage object whose prototype methods are unreachable from code that captures the instance at module load time (the Zustand `persist` middleware does exactly that). The shim is a `Map<string,string>` wrapped in a `Storage` interface and assigned via `Object.defineProperty(window, 'localStorage', { ... })`.
2. **Reset between tests.**
   - `beforeEach`: `window.localStorage.clear()` and `document.documentElement.className = ''` (clears the `.dark` theme class).
   - `afterEach`: `cleanup()` from `@testing-library/react` to unmount React trees.

## Render Helper (`src/test/utils.tsx`)

```ts
export function renderWithProviders(ui: ReactElement, opts: RenderOptions = {}) {
  if (opts.role) {
    useSessionStore.setState({ role: opts.role })
  }
  const client = makeTestQueryClient()
  return {
    client,
    ...render(<Providers client={client}>{ui}</Providers>),
  }
}
```

- `makeTestQueryClient()` returns a fresh `QueryClient` with `retry: false`, `staleTime: 0`, `gcTime: 0` — disables retry timing flakes.
- The optional `role` option seeds the Zustand session store so role-gated components can be tested in either state.
- Returned object includes the `client` so tests can prefetch or inspect cache.

The helper is the canonical entry point for component tests; routes/components should not call `render()` directly.

## Test Layout

Tests live **next to their source** with the `.test.ts(x)` suffix. Current test files (8 total):

| Test file | What it covers |
|---|---|
| `src/shared/api/services/session-swap.test.ts` | Verifies `services` resolves to the right impl based on `VITE_API_MODE` |
| `src/shared/lib/money.test.ts` | `formatMoney` ru-RU formatting + NBSPs |
| `src/shared/i18n/date.test.ts` | Russian date formatting / `Europe/Moscow` TZ |
| `src/shared/i18n/plural.test.ts` | 3-form Russian pluralization |
| `src/shared/session/can.test.ts` | Owner short-circuit + reception denials in `OWNER_ONLY` matrix |
| `src/shared/session/store.test.ts` | Persistence shape, `partialize` selector, hydration |
| `src/shared/theme/theme-bootstrap.test.ts` | `index.html` script applies `.dark` from stored prefs |
| `src/shared/ui/components-json.test.ts` | `components.json` registry + alias contract |

## Conventions

### Structure

`describe` per module, nested by concern; `it` names read as sentences.

```ts
// src/shared/session/can.test.ts (illustrative)
describe('can(role, action, resource)', () => {
  describe('owner', () => {
    it('is allowed every action × resource', () => { ... })
  })
  describe('reception', () => {
    it.each(OWNER_ONLY)('is denied %s on %s', ({ action, resource }) => { ... })
  })
})
```

### Per-test isolation

The shared `beforeEach` in `setup.ts` clears localStorage and resets the `<html>` class — individual tests should not duplicate that work. Tests that touch the session store should reset it explicitly via `useSessionStore.setState({ role: 'owner' })` or use `renderWithProviders(..., { role })`.

### No mocking framework convention yet

There is no MSW (decision: explicitly **not** used). Vitest's `vi.mock()` and `vi.spyOn()` are available but used sparingly. The mock service container itself is the standard test seam — tests at the hook/component level read from `services.*` which already resolves to mocks.

### Async patterns

Use `await waitFor(() => ...)` from Testing Library when assertions depend on Query state. Use `userEvent.setup()` (created per test) for interactions:

```ts
const user = userEvent.setup()
await user.click(screen.getByRole('button', { name: /сохранить/i }))
```

## Coverage Posture

| Area | Coverage |
|---|---|
| Pure helpers (`money`, `plural`, `date`, `can`) | Solid |
| Stores (`session.store`) | Solid |
| Swap seam | Spot-checked (`session-swap.test.ts`) |
| Theme bootstrap | Spot-checked |
| Routes | None |
| AppShell + Header/Sidebar/ProfileMenu | None |
| Features (none yet) | N/A |
| Mock services (none yet) | N/A |
| Integration / E2E | None |

8 unit tests against ~3 K LOC of `src/`. Coverage tracking is not configured. Most application UI (routes, app shell, role gates as integrated components) is currently uncovered — flagged in `CONCERNS.md`.

## Negative-Test ESLint Fixtures

A separate quality net lives at `src/__fixtures/`. Files here are **not** Vitest tests; they are intentionally broken code that ESLint must reject. `pnpm lint:fixtures` runs `scripts/assert-eslint-fixtures.mjs`, which lints each fixture and asserts the expected rule fired. Today's fixtures:

- `api-mode-leak.ts` → `no-restricted-syntax` (VITE_API_MODE chokepoint).
- `features/illegal-mock-import.ts` → `import/no-restricted-paths` (services/mock direct import).
- `raw-palette.tsx` → `no-restricted-syntax` (raw Tailwind palette).

This locks the architectural ESLint rules against silent regressions.

## Recommended Additions (per `CONCERNS.md`)

- Coverage provider (`@vitest/coverage-v8`) + `pnpm test:coverage` script.
- Component tests for `AppShell`, `Sidebar`, `ProfileMenu`, `RoleGate` integration.
- Route-level tests using `createMemoryHistory()` from TanStack Router to verify `beforeLoad` redirects.
- A future Playwright (or similar) E2E layer when the first real feature lands.

---

*Testing analysis: 2026-04-30*
