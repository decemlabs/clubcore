---
phase: 28
plan: "02"
subsystem: admin-web
tags: [types, contracts, i18n, foundation, freeze, renew]
dependency_graph:
  requires: [28-01]
  provides: [freeze-types, freeze-contract, i18n-keys]
  affects: [28-03, 28-04, 28-05, 28-06, 28-07, 28-08]
tech_stack:
  added: []
  patterns:
    - FreezePeriod nested type in entities/membership
    - MembershipsService.freeze/unfreeze/renew contract methods
    - freezeDaysLimit in MembershipPlan entity type (matches backend PlanResponse)
    - i18n namespace extension pattern for freeze/unfreeze/renew/frozen-badge surfaces
key_files:
  created: []
  modified:
    - apps/admin-web/src/entities/membership/types.ts
    - apps/admin-web/src/entities/membership/index.ts
    - apps/admin-web/src/shared/api/contracts/memberships.ts
    - apps/admin-web/src/shared/i18n/ru.ts
    - apps/admin-web/src/shared/api/services/http/_membershipsAdapter.ts
    - apps/admin-web/src/shared/api/services/http/memberships.ts
    - apps/admin-web/src/shared/api/services/mock/_db.ts
    - apps/admin-web/src/shared/api/services/mock/memberships.ts
    - apps/admin-web/src/shared/api/services/mock/memberships.read.test.ts
    - apps/admin-web/src/features/memberships/api/hooks.test.ts
    - apps/admin-web/src/features/memberships/components/MembershipsBlock.test.tsx
    - apps/admin-web/src/features/memberships/components/MembershipPlanFormDialog.tsx
    - apps/admin-web/src/features/memberships/components/SellMembershipDialog.tsx
    - apps/admin-web/src/features/visits/api/hooks.test.tsx
    - apps/admin-web/src/features/visits/components/CheckInPage.test.tsx
    - apps/admin-web/src/features/visits/components/RecentVisitsBlock.test.tsx
decisions:
  - "freezeDaysLimit added to MembershipPlan entity type to match backend MembershipPlanResponse (Phase 25)"
  - "freezeDaysLimit added to MembershipPlanCreateInput + planCreateInputToRequest (backend now requires it)"
  - "http freeze/unfreeze/renew methods fully implemented (3 lines each; trivial given existing pattern)"
  - "mock freeze/unfreeze/renew stubs throw mock_not_implemented (real impl deferred to 28-03)"
  - "MembershipPlanFormDialog computes freezeDaysLimit as durationDays/7 (sensible default; form field deferred to later phase)"
metrics:
  duration: "~45 minutes"
  completed: "2026-05-10"
  tasks_completed: 3
  files_changed: 16
---

# Phase 28 Plan 02: Domain Types + Contract + i18n Foundation Summary

Extended the FE membership domain surface to match Phase 25/26/27 backend shape — frozen status, freeze fields, freeze period, renewal chain — plus locked 24 Russian i18n strings for all Phase-28 user-facing surfaces.

## Tasks Completed

| Task | Name | Commit | Key Files |
|------|------|--------|-----------|
| 1 | Extend Membership domain types | a3eab01 | types.ts, index.ts |
| 2 | Extend MembershipsService contract | d5f256d | contracts/memberships.ts |
| 3 | Lock Russian i18n keys + fix typecheck cascade | 7a7bcda | ru.ts + 13 files |

## Outcomes

### Task 1: Membership Domain Types

- `MembershipStatus` union extended from 3 to 4 values: `'active' | 'expired' | 'cancelled' | 'frozen'`
- New `FreezePeriod` interface exported from `entities/membership/index.ts`
- `Membership` interface gained 5 new fields: `freezeDaysLimitSnapshot`, `freezeDaysUsed`, `freezeDaysRemaining`, `currentFreezePeriod`, `previousMembershipId`
- `MembershipPlan` gained `freezeDaysLimit` (Rule 3 fix — backend PlanResponse now requires it)

### Task 2: Contract Extension

- `MembershipsService` interface: `freeze()`, `unfreeze()`, `renew()` methods added (all `Promise<Membership>`)
- `MembershipsListQuery` extended with `status?: MembershipStatus`
- `MembershipPlanCreateInput` extended with `freezeDaysLimit: number` (Rule 3 fix)

### Task 3: Russian i18n Keys

All 24 keys locked under `memberships.*` namespace:
- `memberships.status.frozen`
- `memberships.freeze.{button, no_days_remaining, success, errors.{freeze_limit_exceeded, already_frozen, invalid_transition}}`
- `memberships.unfreeze.{button, success}`
- `memberships.frozen.{badge, period_dates}`
- `memberships.renew.{button, success, confirm.{title, body, cta, cancel}, errors.{cannot_renew_cancelled, plan_archived}}`
- `memberships.list.expiringWithin.{label, option_days}`
- `memberships.detail.{title, section.{freeze, renewal}, previousMembership}`

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Add freezeDaysLimit to MembershipPlan entity type**
- **Found during:** Task 3 typecheck run
- **Issue:** Backend `MembershipPlanResponse` schema (regenerated in 28-01) now includes `freezeDaysLimit: number` as a required field. `responseToMembershipPlan` failed TS2739.
- **Fix:** Added `freezeDaysLimit: number` to `MembershipPlan` entity type, `MembershipPlanCreateInput` contract, `planCreateInputToRequest` adapter, `generatePlan()` mock DB seed.
- **Files modified:** `types.ts`, `contracts/memberships.ts`, `_membershipsAdapter.ts`, `_db.ts`
- **Commit:** 7a7bcda

**2. [Rule 3 - Blocking] Fix typecheck cascade in http/mock service impls**
- **Found during:** Task 3 typecheck run
- **Issue:** The plan assumed impls (28-03/04) didn't exist yet — they do. Existing `http/memberships.ts` and `mock/memberships.ts` failed because `MembershipsService` interface now has 3 new required methods.
- **Fix:** http adapter: implemented real `freeze()`, `unfreeze()`, `renew()` methods (trivial — same pattern as `cancel()`). Mock: added stubs throwing `mock_not_implemented` (28-03 will replace with real freeze semantics).
- **Files modified:** `http/memberships.ts`, `mock/memberships.ts`
- **Commit:** 7a7bcda

**3. [Rule 3 - Blocking] Fix responseToMembership to map new fields**
- **Found during:** Task 3 typecheck run
- **Issue:** `responseToMembership` in `_membershipsAdapter.ts` returned `Membership` without the 5 new required fields.
- **Fix:** Added full mapping including `FreezePeriod` extraction from `currentFreezePeriod` (backend uses same field name via `BackendSchemaBase` camelization).
- **Files modified:** `_membershipsAdapter.ts`
- **Commit:** 7a7bcda

**4. [Rule 3 - Blocking] Fix mock DB seed to include new required fields**
- **Found during:** Task 3 typecheck run
- **Issue:** `generateMembership()` in `_db.ts` was missing `freezeDaysLimitSnapshot`, `freezeDaysUsed`, `freezeDaysRemaining`, `currentFreezePeriod`, `previousMembershipId`.
- **Fix:** Added all new fields with sensible defaults (no freeze in seed data, `freezeDaysLimitSnapshot = plan.freezeDaysLimit`).
- **Files modified:** `_db.ts`
- **Commit:** 7a7bcda

**5. [Rule 3 - Blocking] Fix 10 test files with incomplete Membership mock objects**
- **Found during:** Task 3 typecheck run
- **Issue:** Inline `Membership` object literals in 5 test files were missing the 5 new required fields.
- **Fix:** Added `freezeDaysLimitSnapshot: 4, freezeDaysUsed: 0, freezeDaysRemaining: 4, currentFreezePeriod: null, previousMembershipId: null` to all mock objects.
- **Files modified:** `hooks.test.ts`, `MembershipsBlock.test.tsx`, `visits/api/hooks.test.tsx`, `CheckInPage.test.tsx`, `memberships.read.test.ts`
- **Commit:** 7a7bcda

**6. [Rule 3 - Blocking] Fix MembershipPlanFormDialog to pass freezeDaysLimit**
- **Found during:** Task 3 typecheck run
- **Issue:** `createPlan.mutate({ ... })` call did not include `freezeDaysLimit` now required by `MembershipPlanCreateInput`.
- **Fix:** Compute `freezeDaysLimit = Math.round(durationDays / 7)` as a default (form field can be added in a later phase; D-28-05 mentions form UX).
- **Files modified:** `MembershipPlanFormDialog.tsx`
- **Commit:** 7a7bcda

**7. [Rule 3 - Blocking] Fix SellMembershipDialog null guard for Select onValueChange**
- **Found during:** Task 3 typecheck run
- **Issue:** `@base-ui/react/select` `Select.Root.onValueChange` passes `string | null`, but `form.setValue` expects `string`. Type mismatch triggered when the Select was now strictly typed.
- **Fix:** Added `v !== null &&` guard before calling `form.setValue`.
- **Files modified:** `SellMembershipDialog.tsx`
- **Commit:** 7a7bcda

**8. [Rule 3 - Blocking] Fix RecentVisitsBlock.test.tsx empty array type**
- **Found during:** Task 3 typecheck run
- **Issue:** `data: []` inferred as `never[]` when cast to `UseQueryResult<Visit[], Error>`.
- **Fix:** Cast to `[] as Visit[]` and update import to use `UseQueryResult` directly.
- **Files modified:** `RecentVisitsBlock.test.tsx`
- **Commit:** 7a7bcda

## Known Stubs

| File | Line | Stub | Reason |
|------|------|------|--------|
| `mock/memberships.ts` | freeze/unfreeze/renew | Throws `mock_not_implemented` | Full mock semantics (freeze period tracking, counter update, renewal chain) implemented in 28-03 |

## Threat Flags

None — this plan is types, contracts, and i18n strings only. No new network endpoints, auth paths, file access patterns, or schema changes at trust boundaries. (The http impl stubs added in deviation Rule 3 reuse existing `request()` infrastructure with existing CSRF handling.)

## Self-Check: PASSED

| Item | Status |
|------|--------|
| `apps/admin-web/src/entities/membership/types.ts` | FOUND |
| `apps/admin-web/src/entities/membership/index.ts` | FOUND |
| `apps/admin-web/src/shared/api/contracts/memberships.ts` | FOUND |
| `apps/admin-web/src/shared/i18n/ru.ts` | FOUND |
| commit a3eab01 (Task 1) | FOUND |
| commit d5f256d (Task 2) | FOUND |
| commit 7a7bcda (Task 3 + deviations) | FOUND |
| `pnpm typecheck` exit 0 | PASSED |
