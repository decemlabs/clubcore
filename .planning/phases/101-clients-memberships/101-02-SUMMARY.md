---
phase: 101-clients-memberships
plan: "02"
subsystem: frontend/plans
tags: [plans, pt-packages, zod, staffRequest, mock-to-http, RBAC, owner-only, 403-friendly-state]
dependency_graph:
  requires: [100-04, 101-01]
  provides:
    - features/plans/schemas.ts (MembershipPlanSchema, PlansListResponseSchema, Create/UpdateSchema)
    - features/plans/api.ts (plansKeys, usePlans, useCreatePlan, useUpdatePlan, useDeletePlan, ApiError)
    - features/plans/schemas.test.ts (26 schema assertions)
    - features/pt-packages/schemas.ts (PtPackagePlanSchema, PtPackageSchema, Sell/Cancel/Refund schemas)
    - features/pt-packages/api.ts (ptPackagesKeys, plan-CRUD hooks, ApiError)
    - pages/plans/PlansPage.tsx (wired tariffs + addons, owner-gated buttons, 403 EmptyState)
  affects:
    - 101-03 (sell/lifecycle hooks build on pt-packages schemas defined here)
    - 101-04 (client detail tabs — membership lifecycle modals use plans/pt-packages api hooks)

tech_stack:
  added: []
  patterns:
    - staffRequest + Schema.parse(raw).data for membership-plans and pt-package-plans CRUD
    - can(role,'edit'|'delete', resource) HIDES owner-only buttons (defense-in-depth; backend authoritative)
    - 403 query response → EmptyState icon=Lock «Недостаточно прав» (T-101-06-403QUERY)
    - 403 mutation response → Sonner toast.error (T-101-05-OWNERPLAN)
    - plansKeys / ptPackagesKeys key factory with lists()/list(filter)/detail(id) hierarchy
    - Immutable-field protection: MembershipPlanUpdateSchema.omit({durationDays}); PtPackagePlanUpdateSchema = {name} only

key_files:
  created:
    - apps/admin-app/src/features/plans/schemas.ts
    - apps/admin-app/src/features/plans/schemas.test.ts
    - apps/admin-app/src/features/pt-packages/schemas.ts
    - apps/admin-app/src/features/pt-packages/api.ts
  modified:
    - apps/admin-app/src/features/plans/api.ts
    - apps/admin-app/src/pages/plans/PlansPage.tsx

key_decisions:
  - "D-101-02-PLANPATH: Path param is plan_id not id: /membership-plans/{plan_id} and /pt-package-plans/{plan_id} per schema.d.ts"
  - "D-101-02-DURATIONIMMUTABLE: MembershipPlanUpdateSchema.omit({durationDays}) prevents client-side send; backend extra=forbid is authority"
  - "D-101-02-PTUPDATE-NAMEONLY: PtPackagePlanUpdateSchema = z.object({name}) — only name mutable per backend contract"
  - "D-101-02-MOCKSTUBS: Create/Edit plan modals are toast stubs per task instruction (do NOT add net-new modal family); Delete is wired"
  - "D-101-02-SALESPROMOS-MOCK: Sales chart + promos + KPIs sections remain on plansPageData mock (deferred to future wiring phase)"
  - "D-101-02-DUMBBELL-ICON: Used Dumbbell (available) instead of Package (not in icons re-export) for pt-package plan rows"

requirements_completed: [MEM-01]

duration: "~9 minutes"
completed: 2026-06-13
---

# Phase 101 Plan 02: Membership-Plans + PT-Package-Plans Zod Schemas + HTTP Wiring Summary

Membership-plans and pt-package-plans catalogs flipped from mock to real backend over staffRequest; owner-gated CRUD buttons hidden for reception; 403 query renders friendly «Недостаточно прав» EmptyState with Lock icon; full pt-packages schema set (including sell/cancel/refund) landed for 101-03 reuse.

## Performance

- **Duration:** ~9 min
- **Started:** 2026-06-13T11:33:13Z
- **Completed:** 2026-06-13T11:41:57Z
- **Tasks:** 2
- **Files created:** 4
- **Files modified:** 2
- **Tests added:** 26

## Accomplishments

- Zod contract layer for membership-plans (Create schema with durationDays 1-3650 range, Update schema omitting immutable durationDays) and pt-package-plans (Create schema, Update schema accepting only name)
- Full pt-packages schema set including PtPackageSchema instance, PtPackageSellSchema (amountKopecks required), PtPackageCancelSchema + PtPackageRefundSchema (reason required 1-200) — all ready for 101-03 sell/lifecycle wiring
- Both plans/api.ts and pt-packages/api.ts wired to real endpoints over staffRequest with onSettled key invalidation and ApiError re-export
- PlansPage tariffs section now renders real membership plans; addons section renders real pt-package plans; both with per-query loading/error/empty/403 states
- Owner-only CRUD buttons hidden for reception via can() (T-101-05-OWNERPLAN defense-in-depth); delete mutation wired with 403 → Sonner toast

## Task Commits

1. **Task 1 (TDD): Schemas + HTTP api.ts** - `bd5f9d02` (feat)
2. **Task 2: Wire PlansPage** - `033110b8` (feat)

## Files Created/Modified

- `apps/admin-app/src/features/plans/schemas.ts` — MembershipPlanSchema, PlansListResponseSchema, MembershipPlanCreateSchema (1-3650/0+/1-365), MembershipPlanUpdateSchema (durationDays omitted)
- `apps/admin-app/src/features/plans/schemas.test.ts` — 26 pure-Zod assertions covering all boundary cases
- `apps/admin-app/src/features/plans/api.ts` — Rewrote from mock; plansKeys, usePlans, useCreatePlan, useUpdatePlan, useDeletePlan; path fixed to /{plan_id}; ApiError re-export
- `apps/admin-app/src/features/pt-packages/schemas.ts` — Full schema set: PtPackagePlanSchema/Create/UpdateSchema, PtPackageSchema, PtPackageSellSchema, PtPackageCancelSchema, PtPackageRefundSchema
- `apps/admin-app/src/features/pt-packages/api.ts` — ptPackagesKeys + plan-CRUD hooks (usePtPackagePlans with includeArchived, useCreatePtPackagePlan, useUpdatePtPackagePlan, useDeletePtPackagePlan); 101-03 section comment
- `apps/admin-app/src/pages/plans/PlansPage.tsx` — Wired tariffs (usePlans) + addons (usePtPackagePlans); MembershipPlanCard + PtPackagePlanRow sub-components; owner-gated buttons; 403 EmptyState; PageLoading/PageError

## Decisions Made

- Path param is `plan_id` (not `id`) per schema.d.ts — confirmed for both `/membership-plans/{plan_id}` and `/pt-package-plans/{plan_id}`
- durationDays immutability enforced client-side via `MembershipPlanCreateSchema.omit({durationDays}).partial()`; 422 surfaces «Длительность тарифа нельзя изменить после создания»
- pt-package plan PATCH sends only `{name}` (sessionCount/priceKopecks/validityDays immutable per backend)
- Create/Edit plan modals are toast stubs per plan task instruction ("do NOT add net-new modal family here") — delete is fully wired
- Sales chart + promos + KPIs sections remain on plansPageData mock; these are not in MEM-01 scope
- Used `Dumbbell` icon (available in icons re-export) instead of `Package` (not exported) for pt-package plan rows

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Incorrect path param names in api.ts**
- **Found during:** Task 1 typecheck
- **Issue:** Plan patterns used `{id}` for path params but schema.d.ts defines `/membership-plans/{plan_id}` and `/pt-package-plans/{plan_id}`
- **Fix:** Changed params from `{ id }` to `{ plan_id: id }` in useUpdatePlan, useDeletePlan, useUpdatePtPackagePlan, useDeletePtPackagePlan
- **Files modified:** `features/plans/api.ts`, `features/pt-packages/api.ts`
- **Commit:** bd5f9d02

**2. [Rule 3 - Blocking] Package icon not in icons re-export**
- **Found during:** Task 2 typecheck
- **Issue:** Used `Package` from `@/components/icons` but it's not exported; icons/index.tsx re-exports a curated subset of lucide-react
- **Fix:** Replaced with `Dumbbell` (already available, semantically appropriate for PT-packages)
- **Files modified:** `pages/plans/PlansPage.tsx`
- **Commit:** 033110b8

---

**Total deviations:** 2 auto-fixed (2 blocking path/icon errors)
**Impact on plan:** Both fixes required for compile; no scope creep.

## Known Stubs

**PlansPage — create/edit plan actions:**
- `apps/admin-app/src/pages/plans/PlansPage.tsx` — `handleCreatePlan`, `handleEditPlan`, `handleCreatePtPlan`, `handleEditPtPlan` show toast stubs
- Per plan task instruction: "do NOT add a net-new modal family here (keep scope to wiring)"
- Delete is fully wired; create/edit modals are deferred to a future plan
- This does NOT prevent MEM-01 (real catalogs listed, owner-only gated)

**PlansPage — sales chart + promos + KPIs sections:**
- Still use `plansPageData` mock data (real endpoints for these sections not in scope)
- Not part of MEM-01 requirement

## Threat Surface Scan

No new security surface beyond what the threat model covers:
- T-101-05-OWNERPLAN: can() HIDES owner-only buttons; backend is real authority (403 → toast)
- T-101-06-403QUERY: 403 on GET renders neutral EmptyState (no backend detail leaked)
- T-101-07-IMMUTABLE: Update schemas omit immutable fields client-side; backend extra='forbid' is authority

## Test Results

- `schemas.test.ts`: 26 tests green (NEW — TDD RED→GREEN)
- Full test suite: 153 tests passed (all pre-existing + 26 new)
- Typecheck: green
- Lint: green
- Build: green (2.52s)

## Self-Check: PASSED

All created files verified on disk. Both commits verified in git log:
- bd5f9d02: feat(101-02): membership-plans + pt-package-plans zod schemas + http api.ts
- 033110b8: feat(101-02): wire PlansPage — real catalogs, owner-gated mutations, 403 EmptyState
