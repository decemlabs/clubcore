---
phase: 22-admin-web-wiring-memberships-visits-active-sessions-ui
fixed_at: 2026-05-08T17:55:00Z
review_path: .planning/phases/22-admin-web-wiring-memberships-visits-active-sessions-ui/22-REVIEW.md
iteration: 1
findings_in_scope: 15
fixed: 15
skipped: 0
status: all_fixed
---

# Phase 22: Code Review Fix Report

**Fixed at:** 2026-05-08T17:55:00Z
**Source review:** .planning/phases/22-admin-web-wiring-memberships-visits-active-sessions-ui/22-REVIEW.md
**Iteration:** 1

**Summary:**
- Findings in scope (BLK + WR): 15
- Fixed: 15
- Skipped: 0

All 4 blockers and all 11 warnings were addressed. Two warnings (WR-02, WR-04) were rolled into related commits (BLK-02 and WR-01 respectively) because the changes were inseparable from the parent fix. WR-06 was addressed with an in-code documentation comment marking the 100-row truncation cap as a tracking item — the suggested UI/backend remediation is deferred per the review's own option (b). 7 Info findings (IN-01 through IN-07) were out of scope for this iteration; IN-05 was opportunistically fixed inside the WR-03 commit.

**Verification performed:**
- `npx tsc --noEmit -p tsconfig.app.json` — only pre-existing errors remain (none introduced by these fixes).
- `npx vitest run` — 32/32 test files pass, 185/185 tests pass.
- `npx eslint src/` — clean (1 pre-existing warning unrelated to these changes).
- `python3 ast.parse` — backend handlers.py syntax-clean.
- `bash -n` — verify-pattern-alpha.sh syntax-clean.

## Fixed Issues

### BLK-01: `/visits` route is missing the `beforeLoad` role guard

**Files modified:** `apps/admin-web/src/routes/_protected/visits.tsx`
**Commit:** 18f0977
**Applied fix:** Added `beforeLoad` that calls `can(role, 'view', 'visits')` and throws `redirect({to: '/', search: {forbidden: ...}})` on deny, mirroring every other Phase 22 protected route.

### BLK-02: `MembershipPlansPage` loader prefetches a key the hook never reads

**Files modified:** `apps/admin-web/src/features/memberships/api/keys.ts`, `apps/admin-web/src/features/memberships/api/hooks.ts`, `apps/admin-web/src/features/memberships/api/hooks.test.ts`, `apps/admin-web/src/features/memberships/components/MembershipPlansPage.tsx`, `apps/admin-web/src/routes/_protected/membership-plans.tsx`
**Commit:** 186f836
**Applied fix:** Introduced `membershipsKeys.plansList(active: boolean | undefined)` as the single source of truth for the cache key. Reworked `useMembershipPlans` to default `active` to `undefined` (all plans) and forward an explicit boolean when supplied. Loader and page both call through the helper, dropping the divergent inline keys. The `as unknown as boolean` cast (WR-02) was removed at the same time. Test updated to assert the new default semantics. `SellMembershipDialog` continues to opt in to active-only via `useMembershipPlans({ active: true })`.

### BLK-03: Wrong i18n key on the "expires today" badge — says "expired today"

**Files modified:** `apps/admin-web/src/features/memberships/components/MembershipsBlock.tsx`, `apps/admin-web/src/features/memberships/components/MembershipsBlock.test.tsx`, `apps/admin-web/src/shared/i18n/ru.ts`
**Commit:** 704b6e9
**Applied fix:** Switched the badge to `t('memberships.badge.expiresToday')` ("Абонемент истекает сегодня"). Deleted the misleading `expirestoday` key from the dictionary (no other consumer). Changed the badge variant from `destructive` to `secondary` to match `CheckInPage`'s tone for the same predicate, since the membership is still valid today under inclusive `endDate` semantics. Updated the frozen-in test to assert the correct string.

### BLK-04: `MembershipPlanFormDialog` lossily round-trips `priceKopecks` through whole roubles

**Files modified:** `apps/admin-web/src/entities/membership/schema.ts`, `apps/admin-web/src/features/memberships/components/MembershipPlanFormDialog.tsx`
**Commit:** 00e4bf8
**Applied fix:** Allowed fractional roubles in the form schema (`z.number().min(0)` instead of `.int()`), removed the lossy `Math.round(plan.priceKopecks / 100)` on initialise so kopecks/100 is preserved exactly, stepped the input by 0.01, and rounded explicitly on submit (`Math.round(values.priceRoubles * 100)`) so any existing fractional rouble value round-trips back to its original kopecks. Money is still stored and transported as integer minor units throughout.

### WR-01: Hardcoded Russian strings throughout new components

**Files modified:** `apps/admin-web/src/shared/i18n/ru.ts`, `apps/admin-web/src/features/auth/components/SessionsList.tsx`, `apps/admin-web/src/features/auth/components/LogoutAllDialog.tsx`, `apps/admin-web/src/features/memberships/components/CancelMembershipDialog.tsx`, `apps/admin-web/src/features/memberships/components/SellMembershipDialog.tsx`, `apps/admin-web/src/features/memberships/components/MembershipPlanFormDialog.tsx`, `apps/admin-web/src/features/memberships/components/MembershipPlansPage.tsx`, `apps/admin-web/src/features/memberships/components/MembershipsBlock.tsx`, `apps/admin-web/src/features/memberships/components/MembershipsListPage.tsx`, `apps/admin-web/src/features/visits/components/RecentVisitsBlock.tsx`
**Commit:** 6b27198
**Applied fix:** Added `memberships.columns.{client,plan,period,price,status}`, `memberships.dialogDescription.{sell,edit,create}`, `visits.columns.{date,time,channel}`, `visits.recentBlock.error`, `common.errors.{network,saveTariff,createTariff,deleteTariff}`, and `common.retryLoad` to `ru.ts`. Replaced every Phase 22 inline Russian literal with its `t('...')` lookup. The "дн." units suffix in `SellMembershipDialog`'s plan select was routed through the existing `t('membershipPlans.daysUnit')`.

### WR-02: `as unknown as boolean` lies to the type system

**Files modified:** `apps/admin-web/src/features/memberships/components/MembershipPlansPage.tsx` (rolled into BLK-02)
**Commit:** 186f836
**Applied fix:** Resolved by BLK-02 — once `useMembershipPlans` honours an honest `opts?: { active?: boolean }` signature with `undefined` semantics, the cast disappears.

### WR-03: HTTP `memberships.list` "expiring" filter applied client-side AFTER pagination

**Files modified:** `apps/admin-web/src/shared/api/services/http/memberships.ts`
**Commit:** a33b984
**Applied fix:** Switched the filter window from runtime-TZ `new Date()/setDate` to `todayMSK()` + UTC arithmetic on the `YYYY-MM-DD` string (DST-safe). Documented in code that pagination is meaningless while `expiring=true` and that backend filter parity is a follow-up.

### WR-04: `LogoutAllDialog` and `SessionsList` swallow non-DomainError into a generic literal

**Files modified:** `apps/admin-web/src/features/auth/components/LogoutAllDialog.tsx`, `apps/admin-web/src/features/auth/components/SessionsList.tsx`, `apps/admin-web/src/features/memberships/components/CancelMembershipDialog.tsx` (rolled into WR-01)
**Commit:** 6b27198
**Applied fix:** Replaced the literal `'Ошибка соединения.'` toast fallback with a three-tier handler — `DomainError.message` first, then `ApiError.message`, then `t('auth.errors.network')` (or `t('common.errors.network')` for the memberships dialog) as the localized fallback. The user now gets the richer transport-layer message instead of a swallowed generic.

### WR-05: `MembershipPlanFormDialog` mixes `register('active')` with `defaultChecked`

**Files modified:** `apps/admin-web/src/features/memberships/components/MembershipPlanFormDialog.tsx`
**Commit:** bba79ab
**Applied fix:** Removed the `defaultChecked={plan?.active ?? true}` prop. `defaultValues` + the `useEffect` `form.reset` already control the checkbox correctly across reopens.

### WR-06: `useMembershipsByClient` returns up to 100 memberships in a single non-paginated call

**Files modified:** `apps/admin-web/src/shared/api/services/http/memberships.ts` (documentation comment, rolled into WR-03)
**Commit:** a33b984
**Applied fix:** Added an in-code TODO comment marking the 100-row hardcoded `pageSize` as a known truncation cap and naming the two follow-up options from the review (UI pagination on `MembershipsBlock` or backend cursor support). The functional change (UI pagination or backend support) is deferred per the review's own option (b) — "document the cap in code + add a follow-up issue". The mock divergence remains intentional for now (mock returns all rows; backend caps at 100).

### WR-07: `MembershipsListPage` `expiring` filter ignored by mock backend (D-22-10)

**Files modified:** `apps/admin-web/src/shared/api/services/mock/memberships.ts`
**Commit:** a33b984
**Applied fix:** Implemented the `expiring` filter symmetrically in the mock service using `todayMSK()` + UTC arithmetic, mirroring the http adapter. Also wired the previously-ignored `clientId` filter while there. Operators training in mock mode now see the toggle behave the same way as in http mode.

### WR-08: Backend `_DM_CHECKIN_OK_LAST_DAY` covers `<= 0` instead of `== 0`

**Files modified:** `apps/backend/app/integrations/telegram/handlers.py`
**Commit:** e4f86af
**Applied fix:** Split the `<= 0` guard into three explicit branches: `== 0` ("today is the last day"), `> 0` (uses `_DM_CHECKIN_OK_WITH_DAYS`), and `< 0` (logs `checkin_negative_days_remaining` with `chat_id`, `membership_end_date`, and the negative value, then falls back to the same last-day text). The impossible case is now observable while user-facing behaviour for the legitimate paths is unchanged.

### WR-09: `_db.ts` "additive migration" branch regenerates with mismatched referential integrity

**Files modified:** `apps/admin-web/src/shared/api/services/mock/_db.ts`
**Commit:** 47081b4
**Applied fix:** Replaced both additive-migration branches with a single `return seed()` when any of `clients`, `memberships`, `plans`, or `visits` is missing/non-array in storage. The previous branches kept stored `clients` while regenerating fresh memberships referencing fresh client UUIDs, breaking joins. Per the review's preferred option (b), full re-seed is simpler and correct for a dev-mode mock store.

### WR-10: `verify-pattern-alpha.sh` leaves the temp file behind on Ctrl-C / SIGINT

**Files modified:** `apps/admin-web/scripts/verify-pattern-alpha.sh`
**Commit:** 112b7fa
**Applied fix:** Moved the `rm -f "$TMP_FILE"` + `rmdir` cleanup into a `cleanup()` function and registered it via `trap cleanup EXIT INT TERM`. The script now self-heals on Ctrl-C and SIGTERM in addition to normal exit — no more stray fixture polluting `src/features/clients/__test__/`.

### WR-11: HTTP `auth.login`/`auth.telegramVerify` cast `envelope.user as MeResponse`

**Files modified:** `apps/admin-web/src/shared/api/contracts/auth.ts`, `apps/admin-web/src/shared/api/services/http/auth.ts`
**Commit:** 8b7d210
**Applied fix:** Added a Zod `meResponseSchema` mirroring the `MeResponse` interface. Both `login()` and `telegramVerify()` now `unwrap<{ user: unknown }>(...)` and run `meResponseSchema.parse(envelope.user)` instead of casting. A backend rename or dropped field surfaces as a clean Zod failure rather than silently flowing a half-built object into the FE.

---

_Fixed: 2026-05-08T17:55:00Z_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
