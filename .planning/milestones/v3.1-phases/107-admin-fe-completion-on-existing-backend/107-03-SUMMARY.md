---
phase: 107-admin-fe-completion-on-existing-backend
plan: 03
subsystem: ui
tags: [react, tanstack-query, rbac, client-delete, toast, navigation]

# Dependency graph
requires:
  - phase: 101-admin-app-backend-wiring
    provides: useDeleteClient hook (DELETE /api/v1/clients/{client_id} → 204)
provides:
  - Owner-gated client soft-delete wired into ProfileHeroReal hero confirm (CLI-04)
affects: [107-04, client-page, rbac-gating]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "useDeleteClient + navigate on success — hero confirm pattern for destructive owner-gated actions"
    - "can(role,'delete','clients') conditional rendering of separator + danger DropdownMenuItem"

key-files:
  created: []
  modified:
    - apps/admin-app/src/pages/client/components/ProfileHeroReal.tsx

key-decisions:
  - "Plain danger confirm (NOT type-to-confirm) retained — owner-gated soft-delete with explicit warning is sufficient per D-107-CLI04"
  - "can() gate wraps separator + delete item together so separator disappears for reception too"
  - "role defaults to 'reception' when session.data is undefined (unauthenticated edge) — safe fail-closed"

patterns-established:
  - "Hero confirm onConfirm: mutate + onSuccess navigate + toast; onError toast only"

requirements-completed: [CLI-04]

# Metrics
duration: 2min
completed: 2026-06-14
---

# Phase 107 Plan 03: Client Delete Wiring (CLI-04) Summary

**Owner-gated `useDeleteClient` mutation replacing toast.info stub in ProfileHeroReal — 204 navigates to clients list, RBAC hides delete item for reception**

## Performance

- **Duration:** 2 min
- **Started:** 2026-06-14T14:05:52Z
- **Completed:** 2026-06-14T14:07:34Z
- **Tasks:** 1
- **Files modified:** 1

## Accomplishments
- Replaced `toast.info('Удаление доступно из карточки редактирования')` stub with real `useDeleteClient().mutate` call
- On 204 success: `navigate(ROUTES.clients)` + `toast.success('Клиент удалён')`
- On error: `toast.error('Не удалось удалить клиента')` (confirm modal closes)
- Added `useSession` + `can(role, 'delete', 'clients')` gate — «Удалить клиента» item (+ preceding separator) hidden for reception

## Task Commits

Each task was committed atomically:

1. **Task 1: Wire real delete + add owner-only gate in ProfileHeroReal** - `c30223db` (feat)

**Plan metadata:** (included in final metadata commit)

## Files Created/Modified
- `apps/admin-app/src/pages/client/components/ProfileHeroReal.tsx` — added `useDeleteClient`, `useSession`, `can` imports; derived `role`; replaced stub `onConfirm`; wrapped delete item in `can()` conditional

## Decisions Made
- Plain danger confirm retained (no type-to-confirm) — consistent with 107-CONTEXT.md CLI-04 decision
- Separator moved inside the `can()` wrapper so reception sees a clean dropdown with no orphaned separator

## Deviations from Plan

None — plan executed exactly as written.

## Issues Encountered
None — typecheck, lint, and all 340 tests passed on first attempt.

## User Setup Required
None — no external service configuration required.

## Next Phase Readiness
- CLI-04 complete; ProfileHeroReal now performs real soft-delete for owners
- Remaining Phase 107 plans (01, 02 — PlanFormModal; 04 — PTPKG sell/cancel/refund) are independent
- No blockers

---
*Phase: 107-admin-fe-completion-on-existing-backend*
*Completed: 2026-06-14*
