---
phase: 22-admin-web-wiring-memberships-visits-active-sessions-ui
reviewed: 2026-05-08T14:23:00Z
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
  - apps/backend/tests/integration/telegram_bot/test_checkin_dm_days_remaining.py
  - apps/backend/tests/integration/telegram_bot/test_checkin_handler.py
  - apps/backend/tests/integration/test_visits_meta.py
  - packages/api-client/src/schema.contract.test.ts
  - packages/api-client/src/schema.d.ts
findings:
  blocker: 4
  warning: 11
  info: 7
  total: 22
status: issues_found
---

# Phase 22: Code Review Report

**Reviewed:** 2026-05-08T14:23:00Z
**Depth:** standard
**Files Reviewed:** 83
**Status:** issues_found

## Summary

Phase 22 wires the admin-web frontend to the FastAPI backend through the typed `@sportzal/api-client` schema, and adds the `/profile` route consuming the active-sessions endpoints. The HTTP transport layer, contracts, mock services, and Phase 23 D-22-11 days-remaining DM logic are well-architected. Tests are thorough and the architecture rules (Pattern α, swap seam, role gates) are respected at module boundaries.

However, the review found **4 BLOCKER findings** that affect data correctness, RBAC coverage, and feature behavior, plus **11 WARNINGS** primarily around i18n discipline (16+ hardcoded Russian strings violating the `t()`-only rule in CLAUDE.md), and **7 INFO** items.

The most serious issues are:
- **`/visits` route lacks the `beforeLoad` RBAC guard** every other phase-22 route has (BLOCKER 1).
- **Membership-plans page loader prefetches a different cache key than the hook reads**, so the loader is wasted and the page does an extra round-trip with different filter semantics (BLOCKER 2).
- **`MembershipsBlock` uses the wrong i18n key (`expirestoday` "истёк сегодня" / "expired today") in a code path that fires when status is still `active`** — the badge tells the operator the membership has already expired when in fact it expires later today (BLOCKER 3).
- **Plan-edit form lossily round-trips `priceKopecks` through whole-roubles**, silently truncating sub-rouble precision on every edit (BLOCKER 4).

## Blocker Issues

### BLK-01: `/visits` route is missing the `beforeLoad` role guard

**File:** `apps/admin-web/src/routes/_protected/visits.tsx:6-13`
**Issue:** Every other Phase 22 protected route (`memberships`, `membership-plans`, `clients.$clientId`, `profile`) defines a `beforeLoad` that calls `can(role, 'view', resource)` and throws `redirect(...)` on deny. `visits.tsx` has no `beforeLoad` at all. Today reception+owner are both allowed, so the omission is not exploitable, but the moment a future requirement narrows `(view, visits)` (e.g. to a sub-role, or to a permission-checked staff scope) the guard rule is silently bypassed and unauthorised users land on the check-in surface. This is exactly the regression the architecture rule "every protected route declares its `beforeLoad`" exists to prevent (CLAUDE.md Architecture Rule 4 / `routeRegistry` invariant).
**Fix:**
```ts
export const Route = createFileRoute('/_protected/visits')({
  beforeLoad: ({ context, location }) => {
    const { role } = context.getSession()
    if (!can(role, 'view', 'visits')) {
      throw redirect({
        to: '/',
        search: { forbidden: location.pathname + (location.searchStr ?? '') },
      })
    }
  },
  loader: ({ context }) =>
    context.queryClient.ensureQueryData({
      queryKey: visitsKeys.gymMeta,
      queryFn: () => services.visits.gymMeta(),
    }),
  component: CheckInPage,
})
```

### BLK-02: `MembershipPlansPage` loader prefetches a key the hook never reads

**File:** `apps/admin-web/src/routes/_protected/membership-plans.tsx:17-22` + `apps/admin-web/src/features/memberships/components/MembershipPlansPage.tsx:40` + `apps/admin-web/src/features/memberships/api/hooks.ts:29-35`
**Issue:** Three layers disagree:
- Loader caches `[...membershipsKeys.plans, { active: undefined }]` calling `services.memberships.listPlans({})`.
- Page calls `useMembershipPlans({ active: undefined as unknown as boolean })`.
- Hook signature is `useMembershipPlans({ active = true } = {})`. The destructuring **default** kicks in when the property is `undefined`, so `active` becomes `true`. The hook then uses queryKey `[...plans, { active: true }]` and calls `listPlans({ active: true })`.

Result: the loader prefetch is a cache miss (different key), and the hook fetches **only active** plans — but the page renders an `ActiveBadge active={p.active}` column with both "Активен" and "Архивирован" variants, i.e. it expects archived plans too. Operators will never see archived plans on this screen, and every navigation to `/membership-plans` does a wasted prefetch + a real fetch with the wrong filter. The `as unknown as boolean` cast is the visible smell of the type system telling the truth about a real bug.
**Fix:** Decide what the page is for and align all three sites. To show all plans (active + archived):
```ts
// hooks.ts — accept undefined explicitly
export function useMembershipPlans(opts?: { active?: boolean }) {
  const active = opts?.active // undefined OR boolean
  return useQuery({
    queryKey: [...membershipsKeys.plans, { active }],
    queryFn: () => services.memberships.listPlans(active === undefined ? {} : { active }),
    staleTime: 30_000,
  })
}

// MembershipPlansPage.tsx — drop the cast
const query = useMembershipPlans()
```
And in the loader call `services.memberships.listPlans({})` with the matching `{ active: undefined }` key — keep them in sync via a single keys helper, e.g. `membershipsKeys.plansList(active)`.

### BLK-03: Wrong i18n key on the "expires today" badge — says "expired today" instead

**File:** `apps/admin-web/src/features/memberships/components/MembershipsBlock.tsx:85-89` and `apps/admin-web/src/shared/i18n/ru.ts:141-144`
**Issue:** The dictionary defines two near-identical keys:
```ts
badge: {
  expirestoday: 'истёк сегодня',          // "already expired today"
  expiresToday: 'Абонемент истекает сегодня', // "expires today"
}
```
`MembershipsBlock` uses `t('memberships.badge.expirestoday')` (the lowercase variant) in a branch guarded by `m.status === 'active' && m.endDate === todayMSK()`. With INCLUSIVE `endDate` semantics (Phase 15 Key Decision documented in `_membershipsAdapter.ts:42` and confirmed in the bot DM logic), the membership is still **valid today** when `endDate === today` — so the operator-facing label must say "expires today", not "already expired today". The `CheckInPage` correctly uses `expiresToday` ("Абонемент истекает сегодня") for the same predicate. The unit test `MembershipsBlock.test.tsx:67` actively asserts the WRONG string ("истёк сегодня"), so this regression has been frozen in.
**Fix:**
```tsx
// MembershipsBlock.tsx:87
<Badge variant="destructive" className="ml-2 text-xs">
  {t('memberships.badge.expiresToday')}
</Badge>
```
Also delete the `expirestoday` key from `ru.ts` (no other consumer) and update `MembershipsBlock.test.tsx` to assert `'Абонемент истекает сегодня'`. While here, decide whether the `destructive` variant is right for "expires today, but still valid" — `outline`/`secondary` matches the CheckInPage choice better.

### BLK-04: `MembershipPlanFormDialog` lossily round-trips `priceKopecks` through whole roubles

**File:** `apps/admin-web/src/features/memberships/components/MembershipPlanFormDialog.tsx:38, 48, 60`
**Issue:** On open in edit mode the form initialises `priceRoubles = Math.round(plan.priceKopecks / 100)` (lines 38, 48). On submit it ships back `priceKopecks = values.priceRoubles * 100` (line 60). Any existing plan whose `priceKopecks` is not a multiple of 100 (e.g. 250050 → 2500.50 ₽) is silently snapped to the nearest 100 kopecks on the next save — a real money-correctness bug per the CLAUDE.md money convention ("Money: integer minor units (kopecks)"). The Zod schema (`membershipPlanFormSchema.priceRoubles: z.number().int()`) enforces the rouble integer on input, but does not protect existing data on edit. The same conversion does not exist for `MembershipPlanCreateInput.priceKopecks` — that path is fine.
**Fix:** Either (a) keep the form in kopecks (display roubles via `formatMoney`, edit kopecks directly) or (b) initialise `priceRoubles` from the kopecks value and *block submit* if the loaded plan has sub-rouble precision. Minimal patch:
```tsx
defaultValues: {
  priceRoubles: plan ? plan.priceKopecks / 100 : 0,
  // ...
},
// schema allows fractional roubles to round-trip
priceRoubles: z.number().min(0),
// submit rounds explicitly so kopecks <= 99 are preserved
const priceKopecks = Math.round(values.priceRoubles * 100)
```
Best fix is (a) — keep the wire format and FE state in kopecks, format roubles only in the display layer.

## Warnings

### WR-01: Hardcoded Russian strings throughout new components — violates the `t()`-only convention

**Files:**
- `apps/admin-web/src/features/auth/components/SessionsList.tsx:30`
- `apps/admin-web/src/features/auth/components/LogoutAllDialog.tsx:41`
- `apps/admin-web/src/features/memberships/components/CancelMembershipDialog.tsx:44`
- `apps/admin-web/src/features/memberships/components/SellMembershipDialog.tsx:65, 156`
- `apps/admin-web/src/features/memberships/components/MembershipPlanFormDialog.tsx:78, 96, 113, 179`
- `apps/admin-web/src/features/memberships/components/MembershipPlansPage.tsx:115`
- `apps/admin-web/src/features/memberships/components/MembershipsBlock.tsx:73-75`
- `apps/admin-web/src/features/memberships/components/MembershipsListPage.tsx:45, 52, 55, 67, 72, 148`
- `apps/admin-web/src/features/visits/components/RecentVisitsBlock.tsx:49, 63-65`

**Issue:** CLAUDE.md mandates: "Single `src/shared/i18n/ru.ts` dictionary. No runtime locale switching." All operator-facing strings must come from `t()`. Phase 22 introduces ~16 inlined Russian literals (table headers "Тариф", "Период", "Статус", "Цена", "Клиент", "Дата", "Время", "Канал"; toast/error texts "Ошибка соединения.", "Ошибка при сохранении тарифа.", "Ошибка при удалении тарифа.", "Не удалось загрузить посещения", "Повторить загрузку"; sr-only descriptions "Редактирование тарифа", "Создание нового тарифа", "Форма продажи абонемента клиенту"). These bypass the central dictionary, harming consistency and any future glossary/proofreading pass.
**Fix:** Add the missing keys (e.g. `memberships.columns.{client,plan,period,price,status}`, `memberships.error.retry`, `common.errors.{network,saveTariff,deleteTariff}`, `visits.recentBlock.error`, `visits.columns.{date,time,channel}`, `memberships.dialog.{editDescription,createDescription,sellDescription}`) to `src/shared/i18n/ru.ts` and replace every literal with `t(…)`. Consider adding an ESLint rule that bans Cyrillic literals in `*.tsx` outside `i18n/ru.ts`.

### WR-02: `as unknown as boolean` lies to the type system

**File:** `apps/admin-web/src/features/memberships/components/MembershipPlansPage.tsx:40`
**Issue:** `useMembershipPlans({ active: undefined as unknown as boolean })` is the root cause of BLK-02. The double cast hides the fact that the call site is sending an invalid value to a parameter typed `boolean`. CLAUDE.md mandates strict TS — type lies of this form should never ship.
**Fix:** Once BLK-02 is fixed (`active?: boolean | undefined` is honest), the cast disappears. If the contract truly is "send `undefined` to mean both", encode that in the type, not in a cast.

### WR-03: HTTP `memberships.list` "expiring" filter is applied client-side AFTER pagination

**File:** `apps/admin-web/src/shared/api/services/http/memberships.ts:42-64`
**Issue:** The `expiring` flag filters items already returned by the backend page, then preserves the original `total` and pageSize. Two problems: (1) the page can return mostly-non-expiring items, leaving the user with an empty list while `total` still says "20 results"; (2) DST/TZ correctness — `today` and `cutoff` use the runtime local TZ via `Date()` and `setDate`, but membership `endDate` is MSK-pinned (`todayMSK()` is the canonical helper). Adjacent code (`CheckInPage`, `RecentVisitsBlock`, `useMembershipStatusForClient`) all pin to MSK; this site silently drifts.
**Fix:** Either push the filter into the backend (negotiate a `?expiring=true&within=7` query) or, at minimum, use the MSK helper:
```ts
import { todayMSK } from '@/shared/i18n/date'
// ...
const todayStr = todayMSK()
const cutoff = new Date(todayStr) // YYYY-MM-DD parses as UTC midnight
cutoff.setUTCDate(cutoff.getUTCDate() + EXPIRING_DAYS)
const cutoffStr = cutoff.toISOString().slice(0, 10)
```
Document that pagination is meaningless while `expiring=true` (or disable it).

### WR-04: `LogoutAllDialog` and `SessionsList` swallow non-DomainError into a generic Russian literal

**File:** `apps/admin-web/src/features/auth/components/LogoutAllDialog.tsx:41` + `apps/admin-web/src/features/auth/components/SessionsList.tsx:30`
**Issue:** When the error is not a `DomainError` (e.g. transport failure, 5xx), the user sees "Ошибка соединения." — but the real `ApiError` thrown by `@sportzal/api-client` may carry a richer `code`/`message` that the auth-feature dictionary already covers (`auth.errors.network`). The literal ignores it and is also untranslatable.
**Fix:** Use `t('auth.errors.network')` (already in dictionary) and pass through `ApiError.message` when present:
```ts
const fallback = t('auth.errors.network')
toast.error(isDomainError(err) ? err.message : err instanceof ApiError ? err.message : fallback)
```

### WR-05: `MembershipPlanFormDialog` mixes `register('active')` with `defaultChecked`

**File:** `apps/admin-web/src/features/memberships/components/MembershipPlanFormDialog.tsx:163-170`
**Issue:** `react-hook-form`'s `register` already controls the checkbox's checked state via `defaultValues`/`reset`. Adding `defaultChecked={plan?.active ?? true}` sets the underlying DOM defaultChecked attribute too. When the dialog re-opens with a different `plan`, the `useEffect` `form.reset(...)` correctly updates the form state, but the DOM defaultChecked attribute is stale (it only applies on initial mount, not subsequent renders). For a single uncontrolled checkbox the practical impact is small, but the mix is a source of bug-of-the-week — the convention is "register OR defaultChecked, not both".
**Fix:** Drop `defaultChecked` — `defaultValues.active` + `form.reset({ active: plan?.active ?? true })` already drives the input correctly.

### WR-06: `useMembershipsByClient` returns up to 100 memberships in a single non-paginated call

**File:** `apps/admin-web/src/shared/api/services/http/memberships.ts:66-71`
**Issue:** `byClient` hardcodes `pageSize: 100` to fetch "all" memberships for a client. For a long-lived gym member the cap is silently truncating history with no UI signal. The mock `byClient` returns ALL items regardless of pagination, so the FE/backend behaviours diverge — the mock test cannot exercise the truncation.
**Fix:** Either (a) add pagination UI to `MembershipsBlock`, or (b) document the cap in code + add a follow-up issue. Backend should also expose a sort order so the most recent N are returned.

### WR-07: `MembershipsListPage` `expiring` filter is wired to a boolean toggle but ignored by the backend (D-22-10)

**File:** `apps/admin-web/src/features/memberships/components/MembershipsListPage.tsx:131-141` + `apps/admin-web/src/shared/api/services/http/memberships.ts:53-62`
**Issue:** The toggle flips a search-param that the http adapter applies in-memory after pagination (see WR-03). On the mock service path, `memberships.list` ignores the `expiring` flag entirely (mock/memberships.ts:25-34 — no filter), so the filter is silently a no-op in dev mode. Operators training in mock mode will see a working button that does nothing.
**Fix:** Either implement the filter symmetrically in the mock service or hide the toggle in mock mode (`API_MODE === 'mock'`). Document the limitation in a UI tooltip if the backend filter is deferred.

### WR-08: Backend `_DM_CHECKIN_OK_LAST_DAY` is reachable only when `days_remaining == 0`, but the guard accepts `<= 0`

**File:** `apps/backend/app/integrations/telegram/handlers.py:330-333`
**Issue:** `if days_remaining <= 0` covers the negative case which "shouldn't" happen (the anti-fraud chain would have rejected with `no_active_membership`). If a future bug ever lets a past-end membership resolve as active, the bot will tell the user "today is the last day" — incorrect for a membership that ended yesterday. Better to make the impossible case observable rather than silently mis-message.
**Fix:**
```python
if days_remaining == 0:
    dm_text = _DM_CHECKIN_OK_LAST_DAY
elif days_remaining > 0:
    dm_text = _DM_CHECKIN_OK_WITH_DAYS.format(days_remaining=days_remaining)
else:
    logger.error(
        "checkin_negative_days_remaining",
        membership_end_date=str(membership_end_date),
        chat_id=chat_id,
    )
    dm_text = _DM_CHECKIN_OK_LAST_DAY  # safe fallback, but log so we can find the bug
```

### WR-09: `_db.ts` "additive migration" branch regenerates with mismatched referential integrity

**File:** `apps/admin-web/src/shared/api/services/mock/_db.ts:151-188`
**Issue:** When `parsed.memberships` is missing but `parsed.clients` is present, the code calls `faker.seed(42)` and regenerates `clients`, `plans`, `memberships`, `visits` — but then keeps the **stored** `parsed.clients` while using the **freshly generated** `memberships` (which reference fresh client IDs). Result: the membership rows reference client UUIDs that no longer exist in `parsed.clients`, breaking joins in the byClient/recent-visits views. Same issue in the visits-only branch (lines 172-188).
**Fix:** Either (a) when migrating, regenerate from the stored `parsed.clients` (i.e. only generate plans/memberships/visits from those clients), or (b) blow the whole DB away and seed fresh. (b) is simpler; it's a mock dev-mode store.

### WR-10: `verify-pattern-alpha.sh` leaves the temp file behind on Ctrl-C / SIGINT

**File:** `apps/admin-web/scripts/verify-pattern-alpha.sh:13-22`
**Issue:** `set -e` aborts the script on the first ESLint failure if the user runs it interactively, but the cleanup `rm -f "$TMP_FILE"` is not in a `trap`. A killed run leaves `src/features/clients/__test__/illegal-pattern-alpha.ts` in the tree — which then triggers the rule on every subsequent ESLint run.
**Fix:**
```bash
trap 'rm -f "$TMP_FILE"; rmdir "$TMP_DIR" 2>/dev/null || true' EXIT INT TERM
```

### WR-11: HTTP `auth.login`/`auth.telegramVerify` cast `envelope.user as MeResponse` instead of validating

**File:** `apps/admin-web/src/shared/api/services/http/auth.ts:40, 60`
**Issue:** Both endpoints unwrap `{user: UserPublic}` and cast `.user` to `MeResponse`. If the backend ever drops `hasTelegram` or renames a field, this cast happily passes a half-built object to the rest of the FE. The mock equivalent (`mock/auth.ts:currentMe`) constructs a `MeResponse` literally, so the two paths diverge in safety.
**Fix:** Define a Zod schema for `MeResponse` (already informally described by the contract) and `parse()` the unwrapped value. Or rely on the generated `components['schemas']['UserPublic']` + a small adapter that forces required fields.

## Info

### IN-01: `services.visits.gymMeta` mock skips RBAC `ensure(...)`

**File:** `apps/admin-web/src/shared/api/services/mock/visits.ts:65-69`
**Issue:** The comment says "no RBAC ensure needed — endpoint is reception+owner viewable; current FE roles satisfy". Mock services SHOULD enforce role access (CLAUDE.md "Mock services enforce role access"). Even when the answer is "all current roles pass", calling `ensure('view', 'visits')` documents the policy and protects against silent regressions when a new role is added.
**Fix:** Add `ensure('view', 'visits')` for parity with `list`/`recentByClient`/`get`.

### IN-02: `useCancelMembership` optimistic snapshot is rebuilt as `Pagination<Membership>` but `byClient` keys aren't included

**File:** `apps/admin-web/src/features/memberships/api/hooks.ts:64-87`
**Issue:** Optimistic update mutates entries under `membershipsKeys.lists()` only. A `MembershipsBlock` rendering the same membership via `byClient` will not flip to "cancelled" until invalidation completes (no optimistic UI on the client-detail screen). Minor UX gap, not a correctness issue.
**Fix:** Extend the snapshot loop to also patch `membershipsKeys.byClient(...)` entries, or accept the small async lag.

### IN-03: `mock/_db.ts` regenerates a faker-seeded DB on every `loadDB()` call when local storage is empty

**File:** `apps/admin-web/src/shared/api/services/mock/_db.ts:145-193`
**Issue:** `loadDB()` with no stored value calls `seed()` which regenerates 30 + 8 + 40 + 150 entities. Multiple cold reads in the same tick (e.g. parallel `Promise.all([list, byClient, recent])` from a route loader) can each call `loadDB()`, each regenerate, each `saveDB`. Not a correctness bug — `faker.seed(42)` makes them deterministic — but it duplicates work.
**Fix:** Memoise the in-memory DB at module scope and treat `loadDB()` as a getter; only call `saveDB` from explicit mutations.

### IN-04: `MembershipsListPage` clientId column uses `clientId.slice(0, 8)` instead of resolving the name

**File:** `apps/admin-web/src/features/memberships/components/MembershipsListPage.tsx:46-50`
**Issue:** The list shows the first 8 hex chars of a UUID instead of the client's name. Operators have no way to identify the membership owner from this surface. The route loader fetches `memberships.list` only — no clients prefetch.
**Fix:** Either (a) add a `clientName` field to `MembershipResponse` server-side, or (b) batch-prefetch clients by id in the loader and join in the page. Tracking issue.

### IN-05: Schema types pass `pageSize: filtered.length` (which can be `0`) for the mock byClient response

**File:** `apps/admin-web/src/shared/api/services/mock/memberships.ts:36-42`
**Issue:** When a client has no memberships, `pageSize: 0` is returned — semantically odd (page size is a request constant, not a result count). Consumers handle it because the items are empty, but `Math.ceil(total / pageSize)` would `Infinity` for any consumer that tries to paginate.
**Fix:** Default to `Math.max(1, filtered.length)` or to a sensible page size constant (20).

### IN-06: `Pagination` is re-exported from both `entities/membership` and `shared/api/contracts/visits`

**File:** `apps/admin-web/src/shared/api/contracts/visits.ts:2, 25`
**Issue:** Visits contracts import `Pagination` from `entities/membership` and re-export it. The type is generic and belongs to `shared/api/contracts/clients.ts` originally. Three exports of the same generic risks drift if any of them ever specialises.
**Fix:** Move `Pagination<T>` to `shared/api/contracts/_pagination.ts` and import from there everywhere.

### IN-07: `_visitsAdapter.ts` casts `r.channel as VisitChannel` without narrowing

**File:** `apps/admin-web/src/shared/api/services/http/_visitsAdapter.ts:32`
**Issue:** Backend `VisitResponse.channel: str` is unrestricted; FE narrows to `'reception' | 'telegram_bot'` via cast. If a third channel ever lands (NFC turnstile is hinted in the service docstring), components matching on the union will silently drop the unknown value.
**Fix:** Add a runtime guard: `const channel = (r.channel === 'telegram_bot' ? 'telegram_bot' : 'reception') as VisitChannel` (or expand the union when the third value lands and add an `assertNever` fallthrough).

---

_Reviewed: 2026-05-08T14:23:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
