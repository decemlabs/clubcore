---
phase: 22-admin-web-wiring-memberships-visits-active-sessions-ui
reviewed: 2026-05-08T00:00:00Z
depth: standard
files_reviewed: 83
files_reviewed_list:
  - apps/admin-web/eslint.config.js
  - apps/admin-web/scripts/verify-pattern-alpha.sh
  - apps/admin-web/src/__fixtures/features/illegal-cross-feature-import.ts
  - apps/admin-web/src/entities/membership/index.ts
  - apps/admin-web/src/entities/membership/schema.ts
  - apps/admin-web/src/entities/membership/types.ts
  - apps/admin-web/src/entities/visit/index.ts
  - apps/admin-web/src/entities/visit/types.ts
  - apps/admin-web/src/features/auth/api/keys.ts
  - apps/admin-web/src/features/auth/api/sessionsHooks.test.ts
  - apps/admin-web/src/features/auth/api/sessionsHooks.ts
  - apps/admin-web/src/features/auth/components/LogoutAllDialog.test.tsx
  - apps/admin-web/src/features/auth/components/LogoutAllDialog.tsx
  - apps/admin-web/src/features/auth/components/SessionsList.test.tsx
  - apps/admin-web/src/features/auth/components/SessionsList.tsx
  - apps/admin-web/src/features/auth/index.ts
  - apps/admin-web/src/features/clients/components/ClientProfileCard.tsx
  - apps/admin-web/src/features/clients/components/ClientsTable.rbac.test.tsx
  - apps/admin-web/src/features/clients/components/ClientsTable.tsx
  - apps/admin-web/src/features/memberships/api/hooks.test.ts
  - apps/admin-web/src/features/memberships/api/hooks.ts
  - apps/admin-web/src/features/memberships/api/keys.ts
  - apps/admin-web/src/features/memberships/components/CancelMembershipDialog.tsx
  - apps/admin-web/src/features/memberships/components/MembershipPlanFormDialog.tsx
  - apps/admin-web/src/features/memberships/components/MembershipPlansPage.tsx
  - apps/admin-web/src/features/memberships/components/MembershipsBlock.test.tsx
  - apps/admin-web/src/features/memberships/components/MembershipsBlock.tsx
  - apps/admin-web/src/features/memberships/components/MembershipsListPage.tsx
  - apps/admin-web/src/features/memberships/components/SellMembershipDialog.tsx
  - apps/admin-web/src/features/memberships/index.ts
  - apps/admin-web/src/features/memberships/model/schema.ts
  - apps/admin-web/src/features/visits/api/hooks.test.tsx
  - apps/admin-web/src/features/visits/api/hooks.ts
  - apps/admin-web/src/features/visits/api/keys.ts
  - apps/admin-web/src/features/visits/components/CheckInPage.test.tsx
  - apps/admin-web/src/features/visits/components/CheckInPage.tsx
  - apps/admin-web/src/features/visits/components/RecentVisitsBlock.test.tsx
  - apps/admin-web/src/features/visits/components/RecentVisitsBlock.tsx
  - apps/admin-web/src/features/visits/index.ts
  - apps/admin-web/src/features/visits/model/schema.ts
  - apps/admin-web/src/routes/_protected/clients.$clientId.tsx
  - apps/admin-web/src/routes/_protected/membership-plans.tsx
  - apps/admin-web/src/routes/_protected/memberships.tsx
  - apps/admin-web/src/routes/_protected/profile.test.tsx
  - apps/admin-web/src/routes/_protected/profile.tsx
  - apps/admin-web/src/routes/_protected/visits.tsx
  - apps/admin-web/src/shared/api/contracts/auth.ts
  - apps/admin-web/src/shared/api/contracts/index.ts
  - apps/admin-web/src/shared/api/contracts/memberships.ts
  - apps/admin-web/src/shared/api/contracts/visits.ts
  - apps/admin-web/src/shared/api/services/http/_membershipsAdapter.ts
  - apps/admin-web/src/shared/api/services/http/_visitsAdapter.ts
  - apps/admin-web/src/shared/api/services/http/auth.ts
  - apps/admin-web/src/shared/api/services/http/index.ts
  - apps/admin-web/src/shared/api/services/http/memberships.ts
  - apps/admin-web/src/shared/api/services/http/visits.ts
  - apps/admin-web/src/shared/api/services/mock/_db.ts
  - apps/admin-web/src/shared/api/services/mock/auth.ts
  - apps/admin-web/src/shared/api/services/mock/index.ts
  - apps/admin-web/src/shared/api/services/mock/memberships.read.test.ts
  - apps/admin-web/src/shared/api/services/mock/memberships.ts
  - apps/admin-web/src/shared/api/services/mock/visits.read.test.ts
  - apps/admin-web/src/shared/api/services/mock/visits.ts
  - apps/admin-web/src/shared/i18n/date.test.ts
  - apps/admin-web/src/shared/i18n/date.ts
  - apps/admin-web/src/shared/i18n/ru.ts
  - apps/admin-web/src/shared/session/can.test.ts
  - apps/admin-web/src/shared/session/registry.ts
  - apps/admin-web/src/shared/ui/alert.tsx
  - apps/admin-web/src/shared/ui/app-shell/ProfileMenu.tsx
  - apps/admin-web/src/shared/ui/app-shell/Sidebar.tsx
  - apps/admin-web/src/shared/ui/badge.tsx
  - apps/admin-web/src/shared/ui/card.tsx
  - apps/admin-web/src/shared/ui/textarea.tsx
  - apps/backend/app/integrations/telegram/handlers.py
  - apps/backend/app/modules/visits/router.py
  - apps/backend/app/modules/visits/schemas.py
  - apps/backend/app/modules/visits/service.py
  - apps/backend/openapi.json
  - apps/backend/tests/integration/telegram_bot/test_checkin_dm_days_remaining.py
  - apps/backend/tests/integration/telegram_bot/test_checkin_handler.py
  - apps/backend/tests/integration/test_visits_meta.py
  - packages/api-client/src/schema.contract.test.ts
  - packages/api-client/src/schema.d.ts
findings:
  blocker: 2
  warning: 8
  info: 5
  total: 15
status: issues_found
---

# Phase 22: Code Review Report (Round 2)

**Reviewed:** 2026-05-08
**Depth:** standard
**Files Reviewed:** 83
**Status:** issues_found

## Summary

Round 2 review of Phase 22 after the round-1 fixes (BLK-01..04 and WR-01/03/04/05/07/08/09/10/11). The fixes landed cleanly: `/visits` has its `beforeLoad` guard, the plan-list cache key is unified through `membershipsKeys.plansList(active)`, the "expires today" badge uses the right key, the price form keeps sub-rouble precision via `Math.round(roubles*100)`, the bot DM splits the `==0`/`>0`/`<0` cases, the Pattern α fixture now has an EXIT/INT/TERM trap, the auth envelope is Zod-validated, etc.

Round 2 surfaces **2 BLOCKER findings** that the round-1 review missed, **8 WARNING items** (most are residue from round-1 — hardcoded strings that escaped the WR-01 sweep, mock/HTTP semantic divergence flagged but not fully closed in WR-03/07, an architecture rule-of-thumb violation in `useReactTable`), and **5 INFO** items.

The two new BLOCKERs:

- **MembershipPlansPage pagination is non-functional**: `useReactTable` is configured with `manualPagination: true` but no `onPaginationChange` handler, AND `useMembershipPlans()` accepts no pagination params and never propagates page/pageSize to the service. The pagination footer renders, but clicking "next page" does nothing and any plan beyond the first 20 is unreachable. (BLK-05.)
- **HTTP `memberships.list` and mock `memberships.list` disagree on what `total` means when `expiring=true`**: HTTP keeps the unfiltered backend `total`, mock returns the filtered count. This is a hard divergence — every test exercising the filter against the mock validates a contract the HTTP path violates. The `MembershipsListPage` pagination UI is therefore broken in HTTP mode (page 2 may show 0 items while `total` says "20 results"); the round-1 WR-03/WR-07 fix mentions this caveat in a comment but never fixes the page-level UX. (BLK-06.)

## Blocker Issues

### BLK-05: `MembershipPlansPage` pagination is wired up visually but not functionally

**File:** `apps/admin-web/src/features/memberships/components/MembershipPlansPage.tsx:40, 93-105, 177` + `apps/admin-web/src/features/memberships/api/hooks.ts:29-36`

**Issue:** Three layers conspire to break pagination on `/membership-plans`:

1. `useMembershipPlans()` (line 40) is called with no arguments. The hook signature accepts `opts?: { active?: boolean }` only — there is no way to pass `page` / `pageSize`. The hook always calls `services.memberships.listPlans(active === undefined ? {} : { active })`, so the service receives no page/pageSize and applies the defaults (HTTP: `page=1`, `pageSize=20`; mock: `page=1`, `pageSize=50`).
2. `useReactTable` (line 93-105) is configured with `manualPagination: true`, `pageCount: Math.ceil(data.total / data.pageSize)`, and `state.pagination = { pageIndex: data.page - 1, pageSize: data.pageSize ?? 20 }`. Crucially there is **no `onPaginationChange` handler** — compare with `MembershipsListPage.tsx:111-124` which routes pagination through TanStack Router's `validateSearch`.
3. `<DataGridPagination sizes={[20, 50, 100]} />` (line 177) renders the next/prev/size controls, so the operator sees a working UI.

Result: the operator clicks "next page" → no state change → the same first page renders. Any plan past the first 20 (or 50 in mock) is unreachable. Worse, the empty-state branch (`data.total === 0`) silences the issue when the page is not 1: clicking forward to a non-existent page would show whatever stale data remains.

The same code path also lacks any way to pass `active` through, so the toggle "show archived only" doesn't exist either.

**Fix:** Decide what UX the page wants. Minimal patch to make pagination work, modeled on `MembershipsListPage`:

```ts
// 1) hooks.ts — accept page/pageSize
export function useMembershipPlans(opts?: { active?: boolean; page?: number; pageSize?: number }) {
  const { active, page = 1, pageSize = 20 } = opts ?? {}
  return useQuery({
    queryKey: [...membershipsKeys.plansList(active), { page, pageSize }] as const,
    queryFn: () => services.memberships.listPlans({ ...(active === undefined ? {} : { active }), page, pageSize }),
    staleTime: 30_000,
  })
}

// 2) routes/_protected/membership-plans.tsx — promote to validateSearch + loaderDeps
const searchSchema = z.object({
  page: z.coerce.number().int().min(1).default(1),
  pageSize: z.coerce.number().int().min(10).max(100).default(20),
})
// loaderDeps + ensureQueryData with the same key

// 3) MembershipPlansPage — read search, drive useReactTable.onPaginationChange via navigate({ search: ... })
```

Until the loader matches the hook key, every navigation to `/membership-plans` will also do a wasted prefetch + a real fetch.

### BLK-06: HTTP and mock `memberships.list` semantically diverge on `total` when `expiring=true`

**File:** `apps/admin-web/src/shared/api/services/http/memberships.ts:43-74` + `apps/admin-web/src/shared/api/services/mock/memberships.ts:29-52` + `apps/admin-web/src/features/memberships/components/MembershipsListPage.tsx:99-141`

**Issue:** The two implementations of the same `MembershipsService.list` contract return contradictory `total` values when `query.expiring === true`:

- **Mock** (mock/memberships.ts:33-51): filters `db.memberships` first, then computes `total = all.length`, then paginates the filtered slice. `total` is the count of actually-matching memberships. Pagination is consistent: `Math.ceil(total/pageSize)` pages each containing matching items.
- **HTTP** (http/memberships.ts:49-73): fetches a page from the backend, **then** filters the page client-side, **then** spreads `...raw` (which keeps the backend's unfiltered `total`) and returns the filtered `items`. `total` is the count of all memberships in the system, not the count of expiring ones.

The HTTP comment (lines 59-62) acknowledges this: "pagination is meaningless while expiring=true … UI should disable pagination on this toggle or hide the toggle until backend support lands". But the UI **does not** disable pagination on the toggle. `MembershipsListPage` (line 99-125) configures `useReactTable` with `manualPagination: true`, `pageCount: Math.ceil(data.total / data.pageSize)`, and `onPaginationChange` that updates router search. With HTTP `expiring=true`:

- `data.total` = count of all memberships (e.g. 200)
- `data.items.length` = filtered count for THIS page only (e.g. 0–20)
- `pageCount` = ceil(200 / 20) = 10 pages
- Operator clicks "page 2" → backend returns 20 NEW unfiltered rows → client filters → likely 0 expiring items → operator sees an empty page with the footer still saying "200 results, page 2/10".

Two consequences:

1. Real production UX bug in HTTP mode (the toggle is shipped, the toggle button is wired, the result is broken pagination operators will hit on day one).
2. Tests that exercise `expiring=true` against the mock cannot detect the HTTP misbehavior — `mock/memberships.read.test.ts` would assert `total === filtered.length`, which the HTTP impl violates. A future bug where someone "fixes" the mock to match the HTTP behavior would silently regress the contract.

This is a **contract violation**, not a TODO.

**Fix:** Pick one and enforce it:

(a) Fastest: hide the toggle behind `import.meta.env.VITE_API_MODE === 'mock'` until the backend supports `?expiring=true&within=7`. Add a follow-up issue for the backend filter.

(b) Make HTTP match mock by paging client-side after fetching ALL active memberships (bounded by some limit) — only safe for small datasets.

(c) Best: add the backend query parameter and change both impls to push the filter to the server. Keep the contract uniform.

In any case, the `MembershipsListPage` pagination footer must not lie. If the toggle stays without backend support, set `pageCount={1}` and don't render `<DataGridPagination>` while `search.expiring === true`.

## Warnings

### WR-12: Hardcoded Russian fallback in `CheckInPage` bypasses the `t()` dictionary

**File:** `apps/admin-web/src/features/visits/components/CheckInPage.tsx:87`

**Issue:** The non-`DomainError` branch sets `setServerError('Ошибка соединения.')` directly. CLAUDE.md mandates `t()` for every user-facing string and the dictionary already has `common.errors.network = 'Ошибка соединения.'`. The previous WR-01 sweep missed this site (the fix touched many components but not this one).

**Fix:**

```tsx
} else {
  setServerError(t('common.errors.network'))
}
```

### WR-13: `ClientProfileCard` aria-label/title hardcoded — same i18n discipline violation

**File:** `apps/admin-web/src/features/clients/components/ClientProfileCard.tsx:36-37`

**Issue:** `aria-label="Редактировать клиента"` and `title="Редактировать клиента"` are inlined Russian literals. The matching key already exists at `clients.actions.edit = 'Редактировать клиента'`. WR-01 corrected the same anti-pattern in `ClientsTable.tsx` but missed this newly-created Phase 22 file (the round-1 review listed it under WR-01 but the fix commit did not visit it).

**Fix:**

```tsx
const editLabel = t('clients.actions.edit')
// ...
<Button
  ...
  aria-label={editLabel}
  title={editLabel}
  onClick={() => setEditOpen(true)}
>
```

### WR-14: `ClientsTable` table headers and empty/error UI still bypass `t()`

**File:** `apps/admin-web/src/features/clients/components/ClientsTable.tsx:34, 35, 38, 47, 61, 62, 72, 73, 116-118, 132-134, 142-145`

**Issue:** This file pre-dates Phase 22 but was modified by Phase 22 (D-22-5 row-click). The pre-existing inlined strings (`'ФИО'`, `'Телефон'`, `'Email'`, `'Дата регистрации'`, `'Не удалось загрузить клиентов'`, `'Клиентов пока нет'`, `'Ничего не найдено'`, etc.) violate the i18n discipline rule — the matching `clients.errorState`, `clients.empty`, `clients.noResults` keys exist in `ru.ts`. CLAUDE.md does not grandfather pre-existing files, and the Phase 22 modification is a natural opportunity to clear technical debt that affects every operator-facing screen.

**Fix:** Replace each literal with the matching `t('clients.…')` key. Add column header keys (e.g. `clients.columns.fullName`, `clients.columns.phone`, `clients.columns.email`, `clients.columns.createdAt`).

### WR-15: `useMembershipStatusForClient` and `useMembershipsByClient` issue parallel duplicate fetches

**File:** `apps/admin-web/src/features/visits/api/hooks.ts:40-52` + `apps/admin-web/src/features/memberships/api/hooks.ts:12-19`

**Issue:** Both hooks call `services.memberships.byClient(clientId)` but with different cache keys (`['visits', 'membershipStatusForClient', clientId]` vs `['memberships', 'byClient', clientId]`). On any render where both are active for the same client (the architecture rule "features cannot import each other" forced this duplication), the same network request fires twice, returning the same data.

For Phase 22 the two are in disjoint route trees (`/visits` uses the visits hook; `/clients/$clientId` uses the memberships hook). But the moment a future feature wants both pieces of state in one render, the design will leak. The architectural rule is sound; the seam to share data is missing.

**Fix:** Promote the data fetcher to a shared hook in `shared/api/hooks/` (or factor a "current active membership" derivation onto a single key shared between features). Minimal change: pick ONE of the keys (e.g. `membershipsKeys.byClient`) and have both feature-local hooks call into it via `qc.fetchQuery` with the same key + queryFn so dedup kicks in. The wrapping `useMembershipStatusForClient` only needs to compute the derived state (`activeMembership`, `expiringToday`).

### WR-16: `MembershipsListPage` does not protect against the `expiring=true` total inflation (BLK-06 sibling)

**File:** `apps/admin-web/src/features/memberships/components/MembershipsListPage.tsx:99-141`

**Issue:** Even setting BLK-06 aside, the page never communicates to the operator that the toggle filters a subset of the page and the result count may differ from the visible row count. The button is just a toggle. There is no banner ("Показано X из Y абонементов на этой странице"), no disabled-pagination affordance, no warning tooltip. Until BLK-06 is fixed at the data layer, the page should at least not mislead the operator.

**Fix:** When `search.expiring === true`, display a small `<Alert variant="default">` above the grid:

```tsx
{search.expiring && (
  <Alert>
    <AlertDescription>{t('memberships.filterNotice.expiringSubsetOfPage')}</AlertDescription>
  </Alert>
)}
```

And add the i18n key. (Or fix BLK-06.)

### WR-17: `useMembershipsByClient` still hardcodes pageSize=100 with silent truncation (residual from WR-06)

**File:** `apps/admin-web/src/shared/api/services/http/memberships.ts:76-84`

**Issue:** WR-06 was acknowledged in a comment ("WR-06: pageSize is hardcoded to 100 — for long-lived members, history beyond the first 100 rows is silently truncated. Tracking issue …") but no tracking issue was filed (no follow-up commit, no `// TODO Phase N:` marker that ties to a roadmap entry). The "tracking issue" comment is the only artifact, and the mock implementation (`mock/memberships.ts:byClient`) returns ALL items regardless, so tests cannot detect the truncation.

**Fix:** Either file the follow-up issue and link it (`// TODO #ISSUE-NN: pagination UI on MembershipsBlock`), or implement pagination in `MembershipsBlock`. At minimum, log a `console.warn` when `total > items.length` so a long-lived gym member's truncation isn't completely silent in production.

### WR-18: `_visitsAdapter.ts` casts `r.channel as VisitChannel` without runtime narrowing (residual from IN-07)

**File:** `apps/admin-web/src/shared/api/services/http/_visitsAdapter.ts:32`

**Issue:** Backend `VisitResponse.channel: str` is a free-form string (`apps/backend/app/modules/visits/schemas.py:57`), constrained only by the DB CHECK constraint to `'reception' | 'telegram_bot'`. The adapter casts to the FE `VisitChannel` union with no runtime guard. If the backend ever adds a third channel (NFC turnstile is hinted in `service.py:14-15`), components rendering `channel === 'telegram_bot' ? ... : 'reception'` (e.g. `RecentVisitsBlock.tsx:78-80`, `ChannelBadge` in `SessionsList.tsx:14-19` for the same enum shape) will silently mis-classify the new value as "reception".

**Fix:**

```ts
const KNOWN_CHANNELS = new Set<VisitChannel>(['reception', 'telegram_bot'])
function narrowChannel(c: string): VisitChannel {
  return KNOWN_CHANNELS.has(c as VisitChannel) ? (c as VisitChannel) : 'reception' // safe default + log
}
// in responseToVisit:
channel: narrowChannel(r.channel),
```

(Or expand the union and add an `assertNever` fallthrough at every consumer site.)

### WR-19: `MembershipsListPage` clientId column shows hex slice instead of client name

**File:** `apps/admin-web/src/features/memberships/components/MembershipsListPage.tsx:43-51`

**Issue:** Column "Клиент" renders `row.original.clientId.slice(0, 8) + '…'`. Operators have no way to identify the membership owner from this surface. The route loader fetches `memberships.list` only — no clients prefetch. Clicking the row does nothing (no `onRowClick` handler is wired, unlike `ClientsTable`'s D-22-5 navigation). The screen is operationally near-useless: it answers "are there any active memberships?" but never "whose are they?".

**Fix:** Either (a) the backend `MembershipResponse` adds a `clientName` snapshot field, or (b) the route loader batch-prefetches `services.clients.list({ id__in: [...uniqueClientIds] })` and the page joins by id. (b) is FE-only; (a) is faster server-side.

## Info

### IN-08: `useLogoutAll`'s `qc.clear()` runs before the navigation in `LogoutAllDialog`

**File:** `apps/admin-web/src/features/auth/api/sessionsHooks.ts:30-39` + `apps/admin-web/src/features/auth/components/LogoutAllDialog.tsx:33-52`

**Issue:** Both the hook and the dialog register `onSuccess` callbacks. React Query runs the hook-level callback first (`qc.clear()`), then the per-mutation callback (toast + navigate). If any `useQuery` hook is mounted at the time `qc.clear()` fires, it will refetch in the gap before navigate, producing wasted requests against an authenticated cache that was just cleared.

In practice, the `/profile` page only renders `SessionsList`, whose query was just invalidated, so the wasted refetch is just one. Minor.

**Fix:** Move `qc.clear()` to AFTER `navigate({ to: '/login' })` — or rely on the `/login` route's expected unmount of authenticated queries.

### IN-09: Mock `auth.logoutAll` resolves silently in mock mode but UI behaves as if it succeeded

**File:** `apps/admin-web/src/shared/api/services/mock/auth.ts:64-67`

**Issue:** In mock mode `auth.logoutAll()` is a no-op (resolves successfully without clearing anything). `LogoutAllDialog` then calls `qc.clear()` and navigates to `/login`, but the Zustand role store is unaffected — the user "logs out" in UI but the role persists. They can navigate back into protected routes immediately. This deviates from the real HTTP behavior the dialog is designed to mirror.

**Fix:** Either also throw `mock_not_implemented` from `auth.logoutAll()` (parity with `auth.sessions()` / `auth.revokeSession()`) or genuinely clear the session store in mock mode. The first option is simpler and makes the limitation explicit.

### IN-10: `MembershipsListPage` row has no click handler — inconsistent with `ClientsTable` D-22-5

**File:** `apps/admin-web/src/features/memberships/components/MembershipsListPage.tsx:99-105`

**Issue:** Phase 22 D-22-5 added row-click navigation to `ClientsTable` (clicking a row routes to `/clients/$clientId`). The matching surface for memberships — clicking a membership row — does nothing. Operators have to scan the right-edge "Отменить" button to interact. Given WR-19 (clientId shown as hex slice), the row is effectively dead UI.

**Fix:** Either skip the column entirely until the backend supports name lookup, or wire `onRowClick` to navigate to `/clients/$clientId` of the membership's owner.

### IN-11: `Pagination` is re-exported from both `entities/membership` and `shared/api/contracts/visits` (residual from IN-06)

**File:** `apps/admin-web/src/shared/api/contracts/visits.ts:2, 25` + `apps/admin-web/src/entities/membership/types.ts:36-41`

**Issue:** Visits contracts import `Pagination<T>` from `entities/membership` and re-export it. Same generic type lives in two places. Three exports of the same generic risks drift if any of them ever specialises.

**Fix:** Move `Pagination<T>` to a dedicated module (`shared/api/contracts/_pagination.ts` or `shared/types/pagination.ts`) and import from there everywhere — entities, contracts, hooks.

### IN-12: `services.visits.gymMeta` mock skips RBAC `ensure(...)` (residual from IN-01)

**File:** `apps/admin-web/src/shared/api/services/mock/visits.ts:65-69`

**Issue:** Comment: "No RBAC ensure needed — endpoint is reception+owner viewable; current FE roles satisfy". Mock services SHOULD enforce role access (CLAUDE.md "Mock services enforce role access"). Even when the answer is "all current roles pass", calling `ensure('view', 'visits')` documents the policy and protects against silent regressions when a new role is added. Adjacent methods (`list`, `recentByClient`, `get`) all call `ensure(...)`.

**Fix:** Add `ensure('view', 'visits')` for parity.

---

_Reviewed: 2026-05-08_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
