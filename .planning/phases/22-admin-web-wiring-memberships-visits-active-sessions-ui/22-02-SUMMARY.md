---
phase: 22-admin-web-wiring-memberships-visits-active-sessions-ui
plan: 02
subsystem: ui
tags: [react, tanstack-router, tanstack-query, zod, react-hook-form, shadcn, faker, mock-service, swap-seam]

requires:
  - phase: 22-admin-web-wiring-memberships-visits-active-sessions-ui-01
    provides: OpenAPI schema refresh + api-client codegen (schema.d.ts with /api/v1/memberships* paths)

provides:
  - features/memberships feature dir end-to-end (entities, contracts, mock+http services, hooks, 6 components, 2 routes)
  - MembershipsBlock block component for /clients/$clientId inline composition (22-04)
  - /memberships list page with D-22-10 expiring filter (?expiring=true)
  - /membership-plans owner-only CRUD page
  - shadcn badge/alert/card/textarea primitives installed
  - ru.ts extended with memberships.* and membershipPlans.* keys
  - sidebar registry extended with Ticket (/memberships, both roles) and LayoutGrid (/membership-plans, owner-only)

affects:
  - 22-04 (composes MembershipsBlock + SellMembershipDialog on /clients/$clientId)
  - 22-03 (adds /visits sidebar entry after this plan's registry groundwork)

tech-stack:
  added: [shadcn badge, shadcn alert, shadcn card, shadcn textarea]
  patterns:
    - "Swap-seam: services.memberships.* via VITE_API_MODE mock|http identical to clients pattern"
    - "D-22-7 read-only mock: write stubs throw DomainError(mock_not_implemented) with no parameters to satisfy no-unused-vars"
    - "D-22-10 client-side expiring filter in HTTP service (expiringWithinDays not in backend schema)"
    - "Route ensureQueryData loader keyed identically to consuming hook query key"
    - "optimistic cancel mutation with onMutate/onError/onSettled mirroring useDeleteClient pattern"

key-files:
  created:
    - apps/admin-web/src/entities/membership/types.ts
    - apps/admin-web/src/entities/membership/schema.ts
    - apps/admin-web/src/entities/membership/index.ts
    - apps/admin-web/src/shared/api/contracts/memberships.ts
    - apps/admin-web/src/shared/api/services/mock/memberships.ts
    - apps/admin-web/src/shared/api/services/mock/memberships.read.test.ts
    - apps/admin-web/src/shared/api/services/http/_membershipsAdapter.ts
    - apps/admin-web/src/shared/api/services/http/memberships.ts
    - apps/admin-web/src/features/memberships/api/keys.ts
    - apps/admin-web/src/features/memberships/api/hooks.ts
    - apps/admin-web/src/features/memberships/api/hooks.test.ts
    - apps/admin-web/src/features/memberships/model/schema.ts
    - apps/admin-web/src/features/memberships/index.ts
    - apps/admin-web/src/features/memberships/components/MembershipsBlock.tsx
    - apps/admin-web/src/features/memberships/components/SellMembershipDialog.tsx
    - apps/admin-web/src/features/memberships/components/CancelMembershipDialog.tsx
    - apps/admin-web/src/features/memberships/components/MembershipsListPage.tsx
    - apps/admin-web/src/features/memberships/components/MembershipPlansPage.tsx
    - apps/admin-web/src/features/memberships/components/MembershipPlanFormDialog.tsx
    - apps/admin-web/src/routes/_protected/memberships.tsx
    - apps/admin-web/src/routes/_protected/membership-plans.tsx
    - apps/admin-web/src/shared/ui/badge.tsx
    - apps/admin-web/src/shared/ui/alert.tsx
    - apps/admin-web/src/shared/ui/card.tsx
    - apps/admin-web/src/shared/ui/textarea.tsx
  modified:
    - apps/admin-web/src/shared/api/contracts/index.ts
    - apps/admin-web/src/shared/api/services/mock/_db.ts
    - apps/admin-web/src/shared/api/services/mock/index.ts
    - apps/admin-web/src/shared/api/services/http/index.ts
    - apps/admin-web/src/shared/session/registry.ts
    - apps/admin-web/src/shared/ui/app-shell/Sidebar.tsx
    - apps/admin-web/src/shared/i18n/ru.ts
    - apps/admin-web/src/shared/i18n/date.ts
    - apps/admin-web/eslint.config.js

key-decisions:
  - "D-22-7 mock writes throw DomainError(mock_not_implemented) — stubs have no parameters (TypeScript subtype satisfaction without unused-var lint violations)"
  - "D-22-10 expiringWithinDays absent from backend schema — client-side filter in HTTP service using date comparison against today + 7 days"
  - "D-22-4 /visits sidebar entry deferred to 22-03 — execution directive overrides plan Task 2 acceptance criteria grep check for /visits"
  - "membershipPlanFormSchema uses priceRoubles (UI) converted to kopecks at submit — domain type stays in kopecks"
  - "MembershipPlanFormDialog: durationDays input disabled on edit (immutable after creation per business rule)"

patterns-established:
  - "Mock write stubs: omit parameter names entirely to avoid no-unused-vars ESLint violation while satisfying TypeScript interface (fewer params = valid subtype)"
  - "i18n key structure: domain.dialog.* for AlertDialog/Dialog titles, domain.form.* for labels/validation, domain.toast.* for sonner messages"
  - "Route tree regeneration: run `pnpm exec vite build` (not `pnpm build`) when tsc -b fails before Vite runs — routeTree.gen.ts is gitignored and auto-generated"

requirements-completed: [FE-04, FE-06, FE-10]

duration: 90min
completed: 2026-05-08
---

# Phase 22 Plan 02: Memberships Feature End-to-End Summary

**Full memberships feature slice: branded entities + swap-seam services (read-only mock + HTTP adapter) + 6 components (Block/List/Plans/SellDialog/CancelDialog/PlanFormDialog) + 2 routes (/memberships, /membership-plans) wired into TanStack Router with role guards and ensureQueryData loaders**

## Performance

- **Duration:** ~90 min
- **Started:** 2026-05-08T13:00:00Z
- **Completed:** 2026-05-08T13:57:00Z
- **Tasks:** 3
- **Files modified:** 34

## Accomplishments

- Full `features/memberships` feature dir built end-to-end following the clients feature analog
- Mock service delivers seeded read fixtures (faker.seed(42), 8 plans + 40 memberships) and correctly throws `DomainError('mock_not_implemented')` on all write paths with RBAC enforced
- HTTP service implements D-22-10 client-side expiring filter (backend has no `expiringWithinDays` query param)
- All 127 tests pass after implementation; tsc --noEmit clean; ESLint 0 errors

## Task Commits

1. **Task 1: Entities + contracts + mock service + tests** - `7463a2e` (feat)
2. **Task 2: HTTP service + hooks + sidebar + i18n** - `25e1f63` (feat)
3. **Task 3: Components + routes + ru.ts extensions** - `114165b` (feat)

## Files Created/Modified

**Entities:**
- `apps/admin-web/src/entities/membership/types.ts` - Branded MembershipId/MembershipPlanId + domain interfaces
- `apps/admin-web/src/entities/membership/schema.ts` - Zod schemas for sell/cancel/list/plan forms
- `apps/admin-web/src/entities/membership/index.ts` - Barrel

**Contracts + Services:**
- `apps/admin-web/src/shared/api/contracts/memberships.ts` - MembershipsService TypeScript interface
- `apps/admin-web/src/shared/api/services/mock/memberships.ts` - Read-only mock (D-22-7)
- `apps/admin-web/src/shared/api/services/mock/memberships.read.test.ts` - 15 tests (RBAC + shape + latency)
- `apps/admin-web/src/shared/api/services/http/_membershipsAdapter.ts` - Pure mappers (brand IDs, narrow unions)
- `apps/admin-web/src/shared/api/services/http/memberships.ts` - HTTP impl with D-22-10 client-side filter

**Hooks + Models:**
- `apps/admin-web/src/features/memberships/api/keys.ts` - membershipsKeys factory
- `apps/admin-web/src/features/memberships/api/hooks.ts` - 7 hooks incl. optimistic useCancelMembership
- `apps/admin-web/src/features/memberships/model/schema.ts` - Re-export from entities

**Components:**
- `apps/admin-web/src/features/memberships/components/MembershipsBlock.tsx` - Block for client profile
- `apps/admin-web/src/features/memberships/components/SellMembershipDialog.tsx` - Dialog + RHF + Zod
- `apps/admin-web/src/features/memberships/components/CancelMembershipDialog.tsx` - AlertDialog + inline error
- `apps/admin-web/src/features/memberships/components/MembershipsListPage.tsx` - List + expiring toggle
- `apps/admin-web/src/features/memberships/components/MembershipPlansPage.tsx` - CRUD DataGrid
- `apps/admin-web/src/features/memberships/components/MembershipPlanFormDialog.tsx` - Create/edit dialog

**Routes:**
- `apps/admin-web/src/routes/_protected/memberships.tsx` - validateSearch(expiring) + ensureQueryData
- `apps/admin-web/src/routes/_protected/membership-plans.tsx` - owner-only beforeLoad + ensureQueryData

**Modified:**
- `apps/admin-web/src/shared/session/registry.ts` - navKey union + Ticket + LayoutGrid entries
- `apps/admin-web/src/shared/ui/app-shell/Sidebar.tsx` - LogIn/Ticket/LayoutGrid icon imports
- `apps/admin-web/src/shared/i18n/ru.ts` - memberships.* (29 keys) + membershipPlans.* (extended) + clientProfile.*
- `apps/admin-web/src/shared/i18n/date.ts` - todayMSK() helper

## Decisions Made

- **Mock write stub parameters omitted entirely:** TypeScript allows methods with fewer parameters than the interface specifies (subtype compatibility). Removing parameter names avoids `@typescript-eslint/no-unused-vars` violations while satisfying the interface contract.
- **D-22-10 client-side expiring filter confirmed:** Checked `schema.d.ts` — `/api/v1/memberships` GET has no `expiringWithinDays` query param. Filter implemented in HTTP service via date comparison (today + 7 days, MSK timezone).
- **membershipPlanFormSchema uses priceRoubles:** UI field collects whole roubles (integer), converted `* 100` at submit. Domain types maintain kopecks throughout.
- **durationDays immutable on plan edit:** `<Input disabled={isEdit}>` with explanatory caption per business rule (existing memberships have snapshot of duration).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] Extended membershipPlans i18n with missing keys**
- **Found during:** Task 3 (MembershipPlansPage + MembershipPlanFormDialog creation)
- **Issue:** Original `ru.ts` had `membershipPlans.form.price` but components needed `priceRoubles`; missing `columns.*`, `dialog.*`, `toast.*`, `error.*`, `daysUnit` keys
- **Fix:** Restructured `membershipPlans` section in `ru.ts` — added columns/dialog/toast/error/daysUnit, renamed price → priceRoubles, added `submitting` key
- **Files modified:** `apps/admin-web/src/shared/i18n/ru.ts`
- **Committed in:** `114165b` (Task 3 commit)

**2. [Execution directive override] /visits sidebar entry NOT added in Task 2**
- **Found during:** Task 2 (registry.ts extension)
- **Context:** Plan Task 2 acceptance criteria included `grep -q "/visits.*Отметки"` check. Execution directive explicitly said "DO NOT add the /visits entry yet (22-03 owns that)".
- **Resolution:** Followed execution directive (overrides plan). Added only /memberships and /membership-plans entries. /visits TODO comment left in registry.ts. Will be resolved in 22-03.
- **Impact:** Non-blocking. 22-03 will add the /visits entry.

---

**Total deviations:** 2 (1 auto-fix Rule 2, 1 execution directive override)
**Impact on plan:** i18n fix was necessary for correct rendering; /visits deferral is per plan orchestration decision with no user-facing impact until 22-03.

## Issues Encountered

- **routeTree.gen.ts regeneration:** Running `pnpm build` (which runs `tsc -b && vite build`) failed on `tsc -b` before Vite could regenerate the route tree. Fixed by running `pnpm exec vite build` directly first to generate `routeTree.gen.ts`, then confirming `tsc --noEmit` clean. Gitignored file, not committed.

## Known Stubs

- `MembershipsBlock.tsx` line 85: `{/* TODO 22-04 D-3: insert <Badge variant="destructive">истёк сегодня</Badge> when endDate === todayMSK() && status==='active' */}` — intentional stub per plan (badge wiring lives in 22-04)

## Next Phase Readiness

- `<MembershipsBlock clientId={...}>` is ready to be composed on `/clients/$clientId` in 22-04
- Mock service is read-only (D-22-7): sells and cancels will return `mock_not_implemented` in mock mode until backend is wired
- `/memberships` and `/membership-plans` routes are live and navigable in dev (sidebar entries present)
- 22-03 can safely add the /visits sidebar entry — registry.ts groundwork (navKey union, `visits` in nav.* ru.ts) is in place

## Self-Check

**Files exist:**
- `apps/admin-web/src/entities/membership/types.ts` - FOUND
- `apps/admin-web/src/features/memberships/api/hooks.ts` - FOUND
- `apps/admin-web/src/features/memberships/components/MembershipsBlock.tsx` - FOUND
- `apps/admin-web/src/routes/_protected/memberships.tsx` - FOUND
- `apps/admin-web/src/routes/_protected/membership-plans.tsx` - FOUND

**Commits exist:**
- `7463a2e` - FOUND (Task 1)
- `25e1f63` - FOUND (Task 2)
- `114165b` - FOUND (Task 3)

## Self-Check: PASSED

---
*Phase: 22-admin-web-wiring-memberships-visits-active-sessions-ui*
*Completed: 2026-05-08*
