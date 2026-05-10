---
phase: 28
plan: "05"
subsystem: admin-web/features/memberships
tags: [hooks, mutations, optimistic, tests, tanstack-query]
dependency_graph:
  requires: [28-03, 28-04]
  provides: [useFreezeMembership, useUnfreezeMembership, useRenewMembership]
  affects: [28-06, 28-07, 28-08]
tech_stack:
  added: []
  patterns:
    - Optimistic mutation with snapshot rollback (freeze/unfreeze)
    - Non-optimistic resource-creating mutation with navigate-on-success (renew)
    - DomainError.code → i18n key via t() + Sonner toast
key_files:
  created:
    - apps/admin-web/src/features/memberships/api/hooks.freeze.test.ts
    - apps/admin-web/src/features/memberships/api/hooks.renew.test.ts
  modified:
    - apps/admin-web/src/features/memberships/api/hooks.ts
decisions:
  - Navigate call for useRenewMembership cast via `(navigate as (opts: any) => void)` until 28-06 registers the /memberships/$membershipId route; cast removed when route exists
metrics:
  duration: ~5 minutes
  completed_date: "2026-05-10"
  tasks_completed: 3
  files_modified: 1
  files_created: 2
---

# Phase 28 Plan 05: Membership Mutation Hooks Summary

Three TanStack Query mutation hooks for freeze, unfreeze, and renew membership operations with optimistic cache updates and Vitest unit tests.

## What Was Built

**useFreezeMembership** (optimistic): snapshots list + detail caches, patches both to `status='frozen'` with an optimistic `currentFreezePeriod` placeholder (`id='optimistic'`). On error: restores snapshots + Sonner toast via `t('memberships.freeze.errors.{code}')`. On settle: invalidates lists, detail, and byClient.

**useUnfreezeMembership** (optimistic): mirrors freeze, patches `status='active'` and clears `currentFreezePeriod=null`. Same rollback + toast + invalidation pattern.

**useRenewMembership** (non-optimistic): server assigns the new membership UUID. On success: `toast.success(t('memberships.renew.success'))` + navigates to the new membership detail. On error: `toast.error(t('memberships.renew.errors.{code}'))`. On settle: invalidates lists, byClient, and source detail.

## Test Coverage

- `hooks.freeze.test.ts`: 4 tests — optimistic detail patch, rollback on DomainError, settle invalidation (lists+detail+byClient), unfreeze optimistic patch to active
- `hooks.renew.test.ts`: 4 tests — success toast+navigate, DomainError `cannot_renew_cancelled`, DomainError `plan_archived`, settle invalidation
- Full suite: 215 tests pass, 37 test files, no regressions

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Type Error] Navigate call for unregistered route**
- **Found during:** Task 1 typecheck
- **Issue:** `/memberships/$membershipId` route is not yet registered (added in 28-06). TanStack Router's typed `navigate()` rejected the path at compile time.
- **Fix:** Cast `navigate as (opts: any) => void` with an ESLint disable comment explaining the TODO for Phase 28-06. The route navigation string is preserved verbatim so 28-06 can simply remove the cast.
- **Files modified:** `apps/admin-web/src/features/memberships/api/hooks.ts`
- **Commit:** f8047d0

**2. [Rule 3 - Blocking Setup] Worktree missing routeTree.gen.ts + node_modules**
- **Found during:** Task 1 verification
- **Issue:** The worktree lacked the auto-generated `routeTree.gen.ts` and had empty `node_modules`, causing typecheck to fail with route resolution errors.
- **Fix:** Symlinked `node_modules` from the main repo and copied `routeTree.gen.ts` into the worktree for typecheck/test tooling.
- **Impact:** Infrastructure only; no source files changed.

## Known Stubs

None. All three hooks are fully wired to `services.memberships.{freeze|unfreeze|renew}` via the swap seam.

## Threat Flags

None. No new network endpoints or auth paths introduced. Trust boundaries unchanged from plan (T-28-05-01 mitigated by `onSettled` invalidation; T-28-05-02 accepted; T-28-05-03 accepted).

## Self-Check

**Files created/modified:**
- `apps/admin-web/src/features/memberships/api/hooks.ts` — modified (Task 1)
- `apps/admin-web/src/features/memberships/api/hooks.freeze.test.ts` — created (Task 2)
- `apps/admin-web/src/features/memberships/api/hooks.renew.test.ts` — created (Task 3)

**Commits:**
- f8047d0: feat(28-05): add useFreezeMembership, useUnfreezeMembership, useRenewMembership hooks
- 3950320: test(28-05): add freeze + unfreeze hook tests (optimistic patch, rollback, invalidation)
- 98a45db: test(28-05): add renew hook tests (success navigate, error toast, settle invalidation)
