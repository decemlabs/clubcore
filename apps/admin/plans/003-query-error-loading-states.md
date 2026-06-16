# Plan 003: Give every data-driven page real loading and error states

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update the status row for this plan
> in `plans/README.md`.
>
> **Drift check (run first)**: `git diff --stat <baseline SHA from plans/README.md>..HEAD -- src/pages src/components/feedback src/api`
> If files changed since baseline, compare the "Current state" excerpts
> against the live code; on a mismatch, treat it as a STOP condition.

## Status

- **Priority**: P1
- **Effort**: M
- **Risk**: LOW
- **Depends on**: plans/001-init-git-baseline.md (recommended: plans/002-vitest-baseline.md for the smoke-test gate)
- **Category**: bug
- **Planned at**: 2026-06-12 (pre-git; baseline SHA in plans/README.md)

## Why this matters

Every page consumes data through TanStack Query hooks, but pages only handle the success branch: they destructure `{ data }` and `if (!data) return null`. Today this is invisible — the hooks resolve local mocks that never fail and resolve in ~0ms. The moment the real backend lands (the project's explicit plan: "only the hook's queryFn changes; pages stay untouched"), every failed or slow request becomes a permanently blank page: TanStack Query does not throw to the router's `errorElement` by default, so `RouteErrorBoundary` never fires. This plan adds a shared loading skeleton and a shared error state with retry, and sweeps every page to use them — so the backend swap doesn't silently break UX on ~20 routes.

## Current state

- **The pattern to replace** — `src/pages/clients/ClientsPage.tsx:46` and `:91` (verbatim):

  ```tsx
  const { data } = useClients();
  // ...
  if (!data) return null;
  ```

  The same shape exists across pages (dashboard, schedule, cashbox, attendance, plans, trainers, finance, …). Step 1 discovers the authoritative list with grep — do not trust a hardcoded list.

- **Hooks**: defined in `src/features/<domain>/api.ts`, all `useQuery` (TanStack v5 — the pending flag is `isPending`; `refetch` is available on the result). Example — `src/features/clients/api.ts:19-24`:

  ```ts
  export function useClients() {
    return useQuery({
      queryKey: clientsKeys.list,
      queryFn: () => mockResponse<ClientsPageData>(clientsPageData),
    });
  }
  ```

- **Existing building blocks** (reuse, do not duplicate):
  - `src/components/ui/skeleton.tsx` — `Skeleton` div with `animate-pulse rounded-md bg-accent`.
  - `src/components/feedback/EmptyState.tsx` — icon-in-circle + title + message + action slot; props `{ icon?: LucideIcon; title; message?; action?; className? }`. This is the visual language for the error state.
  - `src/components/ui/button.tsx` — shadcn Button with a `ghost` variant.
  - `src/components/icons/` re-exports lucide-react icons (e.g. `RefreshCw`, `CircleAlert` — verify exact names exported there; if an icon isn't re-exported yet, add the re-export to `src/components/icons` rather than importing lucide directly in a page).
- **Conventions**: all user-facing strings are Russian, inline. Semantic Tailwind classes only (`bg-surface`, `text-fg-muted`); compose with `cn()` from `@/lib/cn`. Query client defaults (`src/api/query-client.ts`): `staleTime: 30_000, refetchOnWindowFocus: false, retry: 1`.

## Commands you will need

| Purpose   | Command             | Expected on success |
|-----------|---------------------|---------------------|
| Typecheck | `bun run typecheck` | exit 0              |
| Lint      | `bun run lint`      | exit 0              |
| Tests     | `bun run test`      | all pass (if plan 002 landed) |
| Discovery | greps in Step 1     | see step            |

## Scope

**In scope**:
- `src/components/feedback/PageState.tsx` (create — `PageLoading` + `PageError`)
- `src/components/feedback/PageState.test.tsx` (create, only if plan 002 landed)
- Every `src/pages/**/<Name>Page.tsx` that consumes a `features/*/api.ts` hook (discovered in Step 1)
- `plans/README.md` (status row)

**Out of scope** (do NOT touch):
- `src/features/*/api.ts` hooks and `src/api/*` — no `throwOnError`, no global error handling changes; this plan is presentation-layer only.
- `src/layouts/AppLayout/**` (GlobalSearch/CommandPalette/ClubProvider) — chrome has its own UX rules; sweep pages only.
- Widgets *inside* pages that receive data via props — only the page-level query consumption changes.
- `RouteErrorBoundary` / `ErrorPage` — they handle render/route errors, a different layer; leave as is.

## Git workflow

- Branch: `advisor/003-query-states` off `main`.
- Commits: one for `PageState.tsx` (+test), then one commit per 3–5 pages swept (reviewable chunks). Conventional messages: `feat: add PageLoading/PageError feedback components`, `refactor: handle query states on <pages>`.
- Do NOT push.

## Steps

### Step 1: Build the authoritative page list

Run:

```
grep -rn "if (!data) return null" src/pages
grep -rln "from '@/features/[a-z-]*/api'" src/pages
```

Union the two lists (a page may destructure differently or have multiple hooks). Record the list in your final summary. Expected: roughly 15–22 page files.

**Verify**: list is non-empty and includes `src/pages/clients/ClientsPage.tsx` and `src/pages/dashboard/DashboardPage.tsx` (known consumers; if either is missing, your grep is wrong).

### Step 2: Create `src/components/feedback/PageState.tsx`

Two exports, matching the repo's visual language:

```tsx
import { RefreshCw } from '@/components/icons';
import { Skeleton } from '@/components/ui/skeleton';
import { EmptyState } from './EmptyState';

/** Скелет страницы на время первичной загрузки данных. */
export function PageLoading() {
  return (
    <div className="mx-auto flex w-full max-w-[1440px] flex-col gap-4 px-4 pb-10 pt-5 sm:px-6 sm:pt-6 lg:px-7" aria-busy="true">
      <Skeleton className="h-8 w-56" />
      <Skeleton className="h-24 w-full" />
      <Skeleton className="h-[420px] w-full" />
    </div>
  );
}

/** Ошибка загрузки данных страницы + повтор запроса. */
export function PageError({ onRetry }: { onRetry: () => void }) {
  return (
    <EmptyState
      className="py-24"
      title="Не удалось загрузить данные"
      message="Проверьте соединение и попробуйте ещё раз."
      action={
        <button
          type="button"
          onClick={onRetry}
          className="inline-flex h-9 items-center gap-1.5 rounded-[10px] border-[0.5px] border-border-strong bg-surface px-3.5 text-[13px] font-semibold transition-colors hover:bg-surface-3 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          <RefreshCw className="size-3.5" />
          Повторить
        </button>
      }
    />
  );
}
```

If `RefreshCw` is not re-exported from `@/components/icons`, add the re-export there (one line, matching the file's existing style). If `EmptyState`'s actual props differ from the excerpt in "Current state", STOP (drift).

**Verify**: `bun run typecheck` && `bun run lint` → exit 0.

### Step 3: Sweep the pages

For each page from Step 1, transform the query consumption:

```tsx
// БЫЛО:
const { data } = useClients();
// ...
if (!data) return null;

// СТАЛО:
const { data, isPending, isError, refetch } = useClients();
// ...
if (isPending) return <PageLoading />;
if (isError || !data) return <PageError onRetry={() => void refetch()} />;
```

Rules:
- Place the two guard returns where `if (!data) return null` was (after hooks — never between hook calls, that breaks the Rules of Hooks; all `useState`/`useMemo` calls must stay above the guards exactly as they are today).
- Pages with **multiple** hooks: `isPending` if ANY primary hook is pending; `isError` if ANY is error; retry refetches the erroring one(s). Keep it simple and explicit per page.
- After the guards, `data` is non-null — if TypeScript still complains downstream because code used `data?.x`, leave existing optional chaining alone (no drive-by cleanups).
- Do not redesign pages; the only change per page is the destructuring line and the guard block.

**Verify after every 3–5 pages**: `bun run typecheck` && `bun run lint` → exit 0; if plan 002 landed: `bun run test` → smoke suite still green.

### Step 4: Component test (only if plan 002 landed)

`src/components/feedback/PageState.test.tsx`: render `PageError` with a `vi.fn()`; assert the title text renders and clicking «Повторить» calls the handler once. Render `PageLoading`; assert `aria-busy` element present. Model structure after `src/lib/format.test.ts`.

**Verify**: `bun run test` → all pass.

## Test plan

- New: `PageState.test.tsx` (2 cases, Step 4).
- Regression gate: plan 002's route smoke test renders every page through real providers — it fails if a guard was misplaced between hooks (React hook-order error) or a page now returns nothing.
- Manual spot-check (optional, if a preview server is available): `bun run dev`, open `/clients` — page renders identically to before (mocks resolve instantly; you should never see the skeleton for more than a flash).

## Done criteria

ALL must hold:

- [ ] `grep -rn "if (!data) return null" src/pages` → **0 matches**
- [ ] `grep -rln "PageError" src/pages | wc -l` → ≥ 15
- [ ] `bun run typecheck` → exit 0
- [ ] `bun run lint` → exit 0
- [ ] `bun run test` → exit 0 (if tests exist)
- [ ] `git status --porcelain` shows only in-scope files
- [ ] `plans/README.md` row updated

## STOP conditions

Stop and report back (do not improvise) if:

- `EmptyState`, `Skeleton`, or the icons re-export don't match the descriptions here (drift).
- A page's hooks are called conditionally or after early returns *today* (pre-existing hook-order hazard) — report the file instead of restructuring it.
- A page consumes a hook whose result is NOT a `useQuery` result (no `isPending`/`refetch`) — report it; do not invent an adapter.
- The sweep balloons past ~25 files — the grep matched something unexpected; report the list before continuing.

## Maintenance notes

- New pages must follow this pattern from day one; plan 008 adds it to the docs. When the real backend lands, error states become reachable — QA should force a failure (dev-tools offline mode) per page.
- `PageError` deliberately doesn't render error details (no `error.message` — could leak backend internals); revisit when a real API error contract exists (see plan 010's spike).
- Reviewer focus: guards placed after ALL hook calls in every page; no page lost its `useMemo`/`useState` ordering.
- Deferred: per-widget (sub-page) error granularity; Suspense-based loading; global `QueryErrorResetBoundary`.
