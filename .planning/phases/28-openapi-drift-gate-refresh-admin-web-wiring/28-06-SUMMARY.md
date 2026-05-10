---
phase: 28
plan: "06"
subsystem: admin-web
tags: [route, ui, freeze, renew, rbac, badge, tests, typescript]
dependency_graph:
  requires: [28-05]
  provides: [membership-detail-route, StatusBadge, FreezeSection, RenewSection, RenewConfirmDialog]
  affects: [memberships-list, client-detail-block]
tech_stack:
  added: []
  patterns:
    - flat-detail-route (memberships_ underscore convention mirrors clients_.$clientId)
    - semantic-warning-token for frozen badge (bg-warning not raw palette)
    - RoleGate(action=create, resource=memberships) for freeze/unfreeze/renew
    - useParams mock via vi.mock(@tanstack/react-router) for isolated component tests
key_files:
  created:
    - apps/admin-web/src/features/memberships/components/StatusBadge.tsx
    - apps/admin-web/src/features/memberships/components/StatusBadge.test.tsx
    - apps/admin-web/src/features/memberships/components/FreezeSection.tsx
    - apps/admin-web/src/features/memberships/components/RenewSection.tsx
    - apps/admin-web/src/features/memberships/components/RenewConfirmDialog.tsx
    - apps/admin-web/src/routes/_protected/memberships_.$membershipId.tsx
    - apps/admin-web/src/routes/_protected/memberships_.$membershipId.test.tsx
  modified:
    - apps/admin-web/src/features/memberships/api/hooks.ts
decisions:
  - "Mock @tanstack/react-router useParams via vi.mock to test MembershipDetailPage in isolation — avoids RouterProvider setup complexity while testing real component logic"
  - "StatusBadge uses bg-warning text-warning-foreground border-warning/50 (CSS variable aliases from reui-extras) — ESLint raw-palette ban does not trigger"
  - "MembershipDetailPage exported from route file to enable direct test import per plan spec"
  - "TODO cast removed from useRenewMembership.onSuccess — route now registered in routeTree.gen.ts"
metrics:
  duration: "8m"
  completed_date: "2026-05-10"
  tasks_completed: 3
  files_created: 7
  files_modified: 1
---

# Phase 28 Plan 06: Membership Detail Route + Freeze/Renew UI Summary

**One-liner:** Flat detail route `/memberships/$membershipId` with StatusBadge (4 statuses), FreezeSection (button states + tooltip + frozen badge), and RenewSection (AlertDialog with snapshot price + computed dates), all RBAC-gated via RoleGate.

## Tasks Completed

| # | Task | Commit | Status |
|---|------|--------|--------|
| 1 | Extract StatusBadge component + tests | fd6ed8b | Done |
| 2 | Build FreezeSection, RenewSection, RenewConfirmDialog | eaedf51 | Done |
| 3 | Create flat detail route + RBAC integration tests | 3247921 | Done |

## What Was Built

### StatusBadge (Task 1)
Single source of truth for all 4 membership status variants. Frozen badge uses `bg-warning text-warning-foreground border-warning/50` — CSS variable aliases from the reui-extras integration in `index.css`, not raw Tailwind palette colors (ESLint raw-palette ban does not trigger). 4 tests verify Russian labels and the frozen variant's className.

### FreezeSection (Task 2)
Shows `Заморозить` button when `status=active` + `freezeDaysRemaining>0`; disabled button with Radix Tooltip when `remaining=0`; spinner on `freeze.isPending`. When `status=frozen`, swaps to `Снять заморозку` + frozen badge showing start date. Hidden entirely for `expired` and `cancelled`. Gated via `<RoleGate action="create" resource="memberships">`.

### RenewConfirmDialog (Task 2)
shadcn AlertDialog showing plan name, `formatMoney(priceKopecksSnapshot)`, and computed dates (today if expired; `endDate + 1 day` otherwise). Date math uses `addDays(parseISO(...))` from date-fns per D-28-08 spec. Triggers `useRenewMembership.mutate` on confirm.

### RenewSection (Task 2)
Thin wrapper: hides for `cancelled` memberships; shows `Продлить` button gated by RoleGate; opens `RenewConfirmDialog`.

### Detail Route (Task 3)
Flat route `memberships_.$membershipId.tsx` (trailing underscore = not nested under `/memberships` list). `beforeLoad` checks `can(role, 'view', 'memberships')`. Loader uses `queryClient.ensureQueryData(membershipsKeys.detail(id))`. Page composes all sections in Cards. `MembershipDetailPage` exported for test import.

### TODO Cast Removed (Task 3)
`useRenewMembership.onSuccess` had a `(navigate as (opts: any) => void)` cast with a `// TODO Phase 28-06` comment. Route is now registered in `routeTree.gen.ts` — cast replaced with typed `navigate({ to: '/memberships/$membershipId', params: { membershipId: newMembership.id } })`.

## Verification Results

- `pnpm --filter sportzal-adminka typecheck` — exits 0
- `pnpm --filter sportzal-adminka lint` — 0 errors (2 pre-existing warnings in unrelated files)
- `pnpm --filter sportzal-adminka test -- --run StatusBadge` — 4/4 pass
- `pnpm --filter sportzal-adminka test -- --run memberships_` — 5/5 pass
- Full suite — 224 tests pass
- `git diff --exit-code apps/backend/openapi.json packages/api-client/src/schema.d.ts` — drift-gate untouched

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Added `API_MODE: 'mock'` to services mock in detail page test**
- **Found during:** Task 3 — first test run
- **Issue:** `vi.mock('@/shared/api/services', ...)` without `API_MODE: 'mock'` caused `RoleGate → useCurrentRole` to throw "No API_MODE export defined on mock"
- **Fix:** Added `API_MODE: 'mock'` to the vi.mock factory (pattern from `hooks.delete.test.tsx`)
- **Files modified:** `apps/admin-web/src/routes/_protected/memberships_.$membershipId.test.tsx`
- **Commit:** 3247921

**2. [Rule 3 - Blocking] Mocked `@tanstack/react-router` useParams for isolated component testing**
- **Found during:** Task 3 — `useParams` needs RouterProvider context
- **Issue:** `MembershipDetailPage` calls `useParams({ from: '...' })` which requires TanStack Router context unavailable in renderWithProviders
- **Fix:** Added `vi.mock('@tanstack/react-router', ...)` returning `{ ...actual, useParams: () => ({ membershipId: 'm-1' }), Link: ... }`
- **Files modified:** `apps/admin-web/src/routes/_protected/memberships_.$membershipId.test.tsx`
- **Commit:** 3247921

**3. [Rule 3 - Blocking] Ran `vite build` to regenerate routeTree.gen.ts**
- **Found during:** Task 1 — typecheck failed due to missing routeTree
- **Issue:** Worktree started with stale routeTree + missing node_modules; `pnpm install` + `npx vite build` needed
- **Fix:** Installed dependencies and ran vite build to generate routeTree (which already had the memberships_ route registered from prior wave planning)
- **Commit:** Not committed separately (routeTree was already tracked and unchanged)

## Known Stubs

None — all components receive real data from hooks/services.

## Self-Check: PASSED

- `apps/admin-web/src/features/memberships/components/StatusBadge.tsx` — EXISTS
- `apps/admin-web/src/features/memberships/components/FreezeSection.tsx` — EXISTS
- `apps/admin-web/src/features/memberships/components/RenewSection.tsx` — EXISTS
- `apps/admin-web/src/features/memberships/components/RenewConfirmDialog.tsx` — EXISTS
- `apps/admin-web/src/routes/_protected/memberships_.$membershipId.tsx` — EXISTS
- Commits fd6ed8b, eaedf51, 3247921 — FOUND in git log
