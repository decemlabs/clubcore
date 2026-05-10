---
phase: 28
plan: "07"
subsystem: admin-web
tags: [memberships, badge, filter, integration, test]
dependency_graph:
  requires: [28-06]
  provides: [FE-11]
  affects: [MembershipsListPage, MembershipsBlock, memberships-route]
tech_stack:
  added: []
  patterns:
    - Shared StatusBadge component imported in two sibling components (eliminates duplicate inline definitions)
    - Mutually-exclusive filter pills pattern (frozen clears expiring; expiring clears status)
    - Route search schema extended with optional enum field (z.enum + .optional())
key_files:
  created:
    - apps/admin-web/src/features/memberships/components/MembershipsListPage.frozen.test.tsx
  modified:
    - apps/admin-web/src/features/memberships/components/MembershipsListPage.tsx
    - apps/admin-web/src/features/memberships/components/MembershipsBlock.tsx
    - apps/admin-web/src/routes/_protected/memberships.tsx
decisions:
  - Mocked useMembershipsList hook directly (rather than services.memberships.list) to avoid going through useQuery internals in the test
  - Mocked useQueries as returning [] to suppress client-name parallel queries without affecting behaviour under test
  - Added explicit SearchState type annotation to fix TS error where status:'frozen' was not assignable to status:undefined (inferred type too narrow)
metrics:
  duration: "~18 minutes"
  completed: "2026-05-10"
  tasks_completed: 3
  files_created: 1
  files_modified: 3
---

# Phase 28 Plan 07: StatusBadge consolidation + frozen filter pill (FE-11)

Shared StatusBadge wired into both list page and client overview block; "Заморожен" filter pill added to list page toolbar with mutual exclusion against expiring toggle; route schema extended with `status?: MembershipStatus`; 4-test integration suite verifying pill toggle and badge rendering.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Replace inline StatusBadge in MembershipsListPage + add frozen pill | e2c850a | MembershipsListPage.tsx, memberships.tsx (route) |
| 2 | Replace inline StatusBadge in MembershipsBlock | 5ef807f | MembershipsBlock.tsx |
| 3 | Vitest integration test for frozen pill + badge | 8bc73fa | MembershipsListPage.frozen.test.tsx |
| fix | TS type annotation fix in test (Rule 1) | 8708460 | MembershipsListPage.frozen.test.tsx |

## Verification Results

- `pnpm --filter sportzal-adminka typecheck` — exits 0
- `pnpm --filter sportzal-adminka lint` — 0 errors (2 pre-existing warnings in unrelated files)
- `pnpm --filter sportzal-adminka test -- --run MembershipsListPage.frozen` — 4/4 pass
- Full test suite — 228 tests pass (40 test files)
- `git diff --exit-code apps/backend/openapi.json packages/api-client/src/schema.d.ts` — drift-gate untouched

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Stale routeTree caused typecheck cascade**
- **Found during:** Task 1 verification
- **Issue:** Fresh worktree node_modules required `pnpm install` + `vite build` to regenerate `routeTree.gen.ts` (same as 28-06 pattern)
- **Fix:** `pnpm install --frozen-lockfile` then `vite build --mode development` in worktree
- **Files modified:** None (routeTree is auto-generated, not tracked changes)

**2. [Rule 1 - Bug] Unused `Membership` type import after inline deletion (MembershipsBlock)**
- **Found during:** Task 2 typecheck
- **Issue:** `import type { Membership, MembershipId }` — `Membership` was only used in the inline `StatusBadge` prop type; removing the inline function left it unused (noUnusedLocals error)
- **Fix:** Changed import to `import type { MembershipId }` (dropped `Membership`)
- **Files modified:** `apps/admin-web/src/features/memberships/components/MembershipsBlock.tsx`
- **Commit:** 5ef807f (included in Task 2 commit)

**3. [Rule 1 - Bug] TS type inference too narrow for useSearchMock**
- **Found during:** Task 3 typecheck
- **Issue:** `vi.fn(() => ({ ..., status: undefined }))` inferred return type as `{ status: undefined }`, making `status: 'frozen'` in `mockReturnValue` unassignable
- **Fix:** Added explicit `SearchState = { page: number; pageSize: number; expiring: boolean; status?: string }` return type annotation
- **Files modified:** `apps/admin-web/src/features/memberships/components/MembershipsListPage.frozen.test.tsx`
- **Commit:** 8708460

## Known Stubs

None — all four status values render correctly via the shared StatusBadge component; filter pill wires to real route search params.

## Threat Flags

None — only client-side UI state mutation and search-param validation (covered by Zod enum schema per T-28-07-01 in plan threat model).

## Self-Check: PASSED

All created files verified present. All task commits verified in git history.
- FOUND: MembershipsListPage.frozen.test.tsx
- FOUND: MembershipsListPage.tsx (modified)
- FOUND: MembershipsBlock.tsx (modified)
- FOUND: routes/_protected/memberships.tsx (modified)
- FOUND commit e2c850a (Task 1)
- FOUND commit 5ef807f (Task 2)
- FOUND commit 8bc73fa (Task 3)
- FOUND commit 8708460 (Rule 1 fix)
