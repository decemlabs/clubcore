---
phase: 22-admin-web-wiring-memberships-visits-active-sessions-ui
fixed_at: 2026-05-08T00:00:00Z
review_path: .planning/phases/22-admin-web-wiring-memberships-visits-active-sessions-ui/22-REVIEW.md
iteration: 2
findings_in_scope: 10
fixed: 10
skipped: 0
status: all_fixed
---

# Phase 22: Code Review Fix Report (Round 2)

**Fixed at:** 2026-05-08
**Source review:** `.planning/phases/22-admin-web-wiring-memberships-visits-active-sessions-ui/22-REVIEW.md`
**Iteration:** 2

**Summary:**
- Findings in scope: 10 (BLK-05, BLK-06, WR-12 through WR-19)
- Fixed: 10
- Skipped: 0
- Info findings (IN-08..IN-12) not in scope and deferred per `fix_scope=critical_warning`.

All round-2 BLOCKER and WARNING findings were applied. Each fix is its own commit. Full vitest suite (185 tests across 32 files) passes after the changes; ESLint reports zero errors on the touched files.

## Fixed Issues

### BLK-05: `MembershipPlansPage` pagination is wired up visually but not functionally

**Files modified:** `apps/admin-web/src/features/memberships/api/hooks.ts`, `apps/admin-web/src/features/memberships/api/keys.ts`, `apps/admin-web/src/routes/_protected/membership-plans.tsx`, `apps/admin-web/src/features/memberships/components/MembershipPlansPage.tsx`
**Commit:** 0399340
**Applied fix:** Promoted `/membership-plans` to `validateSearch` (`page` + `pageSize`), threaded the search params through `useMembershipPlans({ page, pageSize })`, extended `membershipsKeys.plansList(active, page?, pageSize?)` so the loader and the hook share the cache slice, and wired `useReactTable.onPaginationChange` to `navigate({ search })` (modeled on `MembershipsListPage`). Pagination now actually moves between pages and prefetch is no longer wasted.

### BLK-06: HTTP and mock `memberships.list` semantically diverge on `total` when `expiring=true`

**Files modified:** `apps/admin-web/src/shared/api/services/http/memberships.ts`, `apps/admin-web/src/shared/api/services/mock/memberships.ts`, `apps/admin-web/src/features/memberships/components/MembershipsListPage.tsx`
**Commit:** 0a54fe6
**Applied fix:** Collapsed both impls to a single unpaginated page when `expiring=true` (`{ items, total: items.length, page: 1, pageSize: Math.max(1, items.length) }`). HTTP no longer leaks the unfiltered backend `total`; mock no longer paginates the filtered set. UI hides `<DataGridPagination>` while `search.expiring === true`, matching the contract. Backend `?expiring=true&within=7` is the proper long-term fix and is called out in adapter comments.

### WR-12: Hardcoded Russian fallback in `CheckInPage` bypasses the `t()` dictionary

**Files modified:** `apps/admin-web/src/features/visits/components/CheckInPage.tsx`
**Commit:** b854ada
**Applied fix:** Replaced inline `'Ошибка соединения.'` with `t('common.errors.network')` in the non-`DomainError` error branch.

### WR-13: `ClientProfileCard` aria-label/title hardcoded — same i18n discipline violation

**Files modified:** `apps/admin-web/src/features/clients/components/ClientProfileCard.tsx`
**Commit:** 7393132
**Applied fix:** Extracted `editLabel = t('clients.actions.edit')` and used it for both `aria-label` and `title` on the Pencil button.

### WR-14: `ClientsTable` table headers and empty/error UI still bypass `t()`

**Files modified:** `apps/admin-web/src/features/clients/components/ClientsTable.tsx`, `apps/admin-web/src/shared/i18n/ru.ts`
**Commit:** 053f81c
**Applied fix:** Added `clients.columns.{fullName,phone,email,createdAt}` keys to the dictionary, imported `t`, and replaced every literal in `ClientsTable.tsx` (column headers, error/empty/no-results headings/bodies/buttons, edit/delete aria-labels). Tests still pass — `aria-label='Удалить клиента'` and `aria-label='Редактировать клиента'` remain identical to existing `clients.actions.{edit,delete}` values.

### WR-15: `useMembershipStatusForClient` and `useMembershipsByClient` issue parallel duplicate fetches

**Files modified:** `apps/admin-web/src/features/visits/api/hooks.ts`
**Commit:** df15ed3
**Applied fix:** Aligned `useMembershipStatusForClient`'s queryKey to the same tuple `['memberships', 'byClient', clientId]` used by `useMembershipsByClient` so React Query dedupes the fetch when both hooks are active in the same render. The tuple is hardcoded (not imported from `features/memberships`) to respect the "features must not import other features" architecture rule. Existing test (`hooks.test.tsx`) still passes — it asserts service calls, not the queryKey.

### WR-16: `MembershipsListPage` does not protect against the `expiring=true` total inflation

**Files modified:** `apps/admin-web/src/features/memberships/components/MembershipsListPage.tsx`, `apps/admin-web/src/shared/i18n/ru.ts`
**Commit:** 2c3e85d
**Applied fix:** Added `memberships.filterNotice.expiringSubsetOfPage` dictionary entry and rendered an `<Alert>` above the grid when `search.expiring === true`. Pairs with BLK-06's pagination-hide so the operator understands why pagination disappears and what subset is visible.

### WR-17: `useMembershipsByClient` still hardcodes pageSize=100 with silent truncation

**Files modified:** `apps/admin-web/src/shared/api/services/http/memberships.ts`
**Commit:** 5ff2a46 (cleanup of unused eslint-disable in 360577e)
**Applied fix:** Added `console.warn` when `raw.total > raw.items.length` so a long-lived gym member's truncated history surfaces in dev tools instead of being completely silent. Proper fix (pagination UI on `MembershipsBlock` or backend cursor support) is documented in the comment as a follow-up.

### WR-18: `_visitsAdapter.ts` casts `r.channel as VisitChannel` without runtime narrowing

**Files modified:** `apps/admin-web/src/shared/api/services/http/_visitsAdapter.ts`
**Commit:** e7df705 (cleanup of unused eslint-disable in 360577e)
**Applied fix:** Added `KNOWN_CHANNELS` set and `narrowChannel(c: string): VisitChannel` helper that gates against the union and `console.warn`s + defaults to `'reception'` on unknown values. Replaces the unsafe `as VisitChannel` cast in `responseToVisit`. Future backend channels (e.g. NFC turnstile) will be visible in the console rather than silently mis-classified.

### WR-19: `MembershipsListPage` clientId column shows hex slice instead of client name

**Files modified:** `apps/admin-web/src/features/memberships/components/MembershipsListPage.tsx`
**Commit:** 3fddb5d
**Applied fix:** Used `useQueries` to fetch the unique client IDs on the visible page via `services.clients.get(id)` and rendered `client.fullName` when available, with the hex slice as a graceful fallback during loading or fetch failure. Cache key matches `clientsKeys.detail()` shape so cache is shared with `/clients/$clientId`. Services-container access (not a `features/clients` import) respects the architecture rule. Backend `MembershipResponse.clientName` snapshot remains the proper long-term fix and is documented in the comment.

---

_Fixed: 2026-05-08_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 2_
