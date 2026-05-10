---
phase: 28-openapi-drift-gate-refresh-admin-web-wiring
plan: 03
subsystem: mock, testing
tags: [mock, vitest, memberships, freeze, renew, parity, localStorage]

requires:
  - phase: 28-02
    provides: "Membership type extensions (FreezePeriod, freezeDaysLimitSnapshot, previousMembershipId) + MembershipsService contract (freeze/unfreeze/renew signatures)"
  - phase: 28-01
    provides: "Regenerated OpenAPI spec + schema.d.ts drift-gate artifacts"
provides:
  - "mock/memberships.ts freeze/unfreeze/renew real implementations (DomainError parity with backend)"
  - "memberships.freeze.test.ts — 9 parity tests for freeze/unfreeze transitions and error codes"
  - "memberships.renew.test.ts — 8 parity tests for renew (new-row, previousMembershipId, date math, error codes)"
affects: [28-04, 28-05, 28-06, mock-mode developers]

tech-stack:
  added: []
  patterns:
    - "Mock mutation pattern: delay() + ensure('create', 'memberships') + loadDB() + mutation + saveDB()"
    - "injectMembership helper: spread seed[0] + partial override, push to db, saveDB — mirrors expiring.test.ts pattern"
    - "Error assertion pattern: expect(...).rejects.toMatchObject({ code: 'error_code' })"

key-files:
  created:
    - apps/admin-web/src/shared/api/services/mock/memberships.freeze.test.ts
    - apps/admin-web/src/shared/api/services/mock/memberships.renew.test.ts
  modified:
    - apps/admin-web/src/shared/api/services/mock/memberships.ts

key-decisions:
  - "freeze/unfreeze/renew all use ensure('create', 'memberships') — both roles (reception + owner) have this permission"
  - "unfreeze clears currentFreezePeriod to null after closing period (history-of-one not exposed in v1.3)"
  - "renew allows frozen source (only 'cancelled' triggers cannot_renew_cancelled)"
  - "daysFrozen uses Math.max(1, ceil(...)) to ensure minimum 1 day even for sub-second freeze-then-unfreeze"
  - "MembershipPlanId brand type required in renew test when manually constructing plan fixtures"

patterns-established:
  - "Mock write method pattern: delay + ensure + loadDB + findIndex + validation + mutation + saveDB + return"
  - "Test injectMembership helper spreads seed[0] to inherit all required fields, overrides only test-specific ones"
  - "Freeze test file: 9 tests covering both freeze and unfreeze transitions in same describe block"
  - "Renew test file: 8 tests covering new-row creation, date math, error codes, counter reset"

requirements-completed: [FE-10, FE-12]

duration: 18min
completed: 2026-05-10
---

# Phase 28 Plan 03: Mock Freeze/Unfreeze/Renew Implementation Summary

**Mock memberships service implements freeze/unfreeze/renew with backend-equivalent DomainError codes, backed by 17 parity tests covering all transitions, error paths, and RBAC**

## Performance

- **Duration:** ~18 min
- **Started:** 2026-05-10T15:15:00Z
- **Completed:** 2026-05-10T15:33:00Z
- **Tasks:** 3 (+ 1 auto-fix)
- **Files modified:** 3

## Accomplishments
- Replaced three `mock_not_implemented` TODO stubs with real freeze/unfreeze/renew implementations in `mock/memberships.ts`
- freeze: active + freezeDaysRemaining > 0 → frozen, allocates `currentFreezePeriod`; throws `already_frozen`, `invalid_transition`, `freeze_limit_exceeded`
- unfreeze: frozen → active, closes period (`endedAt/endedBy`), extends `endDate` by `ceil(daysFrozen)`, increments `freezeDaysUsed`, clears `currentFreezePeriod` to null
- renew: creates new membership row with `previousMembershipId = source.id`, resets freeze counters, computes dates per backend rule (`max(todayMSK, endDate+1)`); throws `cannot_renew_cancelled`, `plan_archived`
- RBAC enforced via `ensure('create', 'memberships')` on all three — both `owner` and `reception` roles can operate
- 9 freeze/unfreeze parity tests — all green
- 8 renew parity tests — all green
- No regression to existing 5 expiring parity tests

## Task Commits

1. **Task 1: Implement freeze/unfreeze/renew in mock memberships service** - `a32ea3e` (feat)
2. **Task 2: Vitest parity tests — memberships.freeze.test.ts** - `213305d` (test)
3. **Task 3: Vitest parity tests — memberships.renew.test.ts** - `7df03d3` (test)
4. **Auto-fix: MembershipPlanId brand type in renew test** - `1e096b9` (fix)

## Files Created/Modified
- `apps/admin-web/src/shared/api/services/mock/memberships.ts` - Added faker + saveDB imports; replaced 3 TODO stubs with real freeze/unfreeze/renew implementations
- `apps/admin-web/src/shared/api/services/mock/memberships.freeze.test.ts` - 9 parity tests for freeze/unfreeze transitions and error codes
- `apps/admin-web/src/shared/api/services/mock/memberships.renew.test.ts` - 8 parity tests for renew (new-row, previousMembershipId, date math, plan_archived, counter reset)

## Decisions Made
- `unfreeze` clears `currentFreezePeriod` to `null` after closing the period — consistent with CONTEXT "history-of-one is not exposed in v1.3"
- `renew` allows frozen source membership (only `cancelled` triggers `cannot_renew_cancelled`) — matches backend Phase 26 semantics
- `daysFrozen = Math.max(1, Math.ceil(...))` — minimum 1 day even for same-millisecond round-trip (consistent with backend `ceil` semantics)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] TypeScript brand type error in renew test fixture**
- **Found during:** Task 3 final typecheck pass
- **Issue:** `{ ...db.plans[0]!, id: 'archived-plan-id', active: false }` — the literal string `id` is `string`, not `MembershipPlanId` branded type; TypeScript strict mode rejected the spread
- **Fix:** Cast `id` as `'archived-plan-id' as MembershipPlanId`, import `MembershipPlanId` from `@/entities/membership`, cast `planId` in `injectMembership` call similarly
- **Files modified:** `apps/admin-web/src/shared/api/services/mock/memberships.renew.test.ts`
- **Verification:** `pnpm --filter sportzal-adminka typecheck` exits 0; all 8 renew tests still pass
- **Committed in:** `1e096b9` (separate fix commit after task commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 — type correctness)
**Impact on plan:** Necessary for TypeScript strict mode compliance. No scope creep. All tests pass.

## Issues Encountered
None beyond the branded type fix documented above.

## Known Stubs
None — all three methods implement real semantics. The `_db.ts` seed already populated all freeze fields (wave 2 completed this). No placeholder data flows to UI rendering.

## Threat Surface Scan
No new network endpoints, auth paths, or schema changes introduced. This plan only modifies mock service code (localStorage, browser-only, dev-mode gated by `VITE_API_MODE=mock`). Threat model from plan frontmatter applies; no new surfaces found.

## Next Phase Readiness
- Mock service is fully operational for freeze/unfreeze/renew — `VITE_API_MODE=mock` developers can exercise all transitions offline
- 28-04 (HTTP adapter) can now proceed — mock and http impls share the same `MembershipsService` contract
- 28-05 (hooks) can wire against both impls identically since DomainError codes match backend

---
*Phase: 28-openapi-drift-gate-refresh-admin-web-wiring*
*Completed: 2026-05-10*
