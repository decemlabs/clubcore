---
phase: 22-admin-web-wiring-memberships-visits-active-sessions-ui
plan: 03
subsystem: ui
tags: [react, tanstack-query, vitest, visits, checkin, fe-08, architecture-rule-5, todayMSK]

requires:
  - phase: 22-01
    provides: api-client schema with /api/v1/visits and /api/v1/visits/_meta paths
  - phase: 22-02
    provides: memberships swap-seam wiring (services.memberships.byClient consumed by local hook)

provides:
  - features/visits end-to-end (entities + contracts + mock + http + hooks + components + route)
  - CheckInPage with all FE-08(a..d) edge cases hardened
  - RecentVisitsBlock component ready for 22-04 Pattern α client-detail composition
  - todayMSK() exported from shared/i18n/date.ts for 22-04 D-3 badge wiring
  - useMembershipStatusForClient local hook (Architecture Rule 5 compliant)
  - /visits route registered at position 2 in routeRegistry (D-22-4)
  - ru.ts visits domain keys

affects:
  - 22-04 (imports RecentVisitsBlock, todayMSK from this plan)
  - features/clients/components/ClientDetailPage (Pattern α consumes RecentVisitsBlock)

tech-stack:
  added: []
  patterns:
    - local-hook-pattern: "features/visits/api/hooks.useMembershipStatusForClient consumes services.memberships.byClient via swap-seam without importing features/memberships — Architecture Rule 5"
    - formatTimeMSK-pattern: "Intl.DateTimeFormat('ru-RU', {timeZone: 'Europe/Moscow'}) for TZ-safe time display; NOT date-fns formatTime() which uses runtime local zone"
    - disambiguation-listbox: "role=listbox + role=option for phone-prefix top-5 search (FE-08a)"

key-files:
  created:
    - apps/admin-web/src/entities/visit/types.ts
    - apps/admin-web/src/entities/visit/index.ts
    - apps/admin-web/src/shared/api/contracts/visits.ts
    - apps/admin-web/src/shared/api/services/mock/visits.ts
    - apps/admin-web/src/shared/api/services/mock/visits.read.test.ts
    - apps/admin-web/src/shared/api/services/http/_visitsAdapter.ts
    - apps/admin-web/src/shared/api/services/http/visits.ts
    - apps/admin-web/src/features/visits/api/keys.ts
    - apps/admin-web/src/features/visits/api/hooks.ts
    - apps/admin-web/src/features/visits/api/hooks.test.tsx
    - apps/admin-web/src/features/visits/model/schema.ts
    - apps/admin-web/src/features/visits/components/RecentVisitsBlock.tsx
    - apps/admin-web/src/features/visits/components/CheckInPage.tsx
    - apps/admin-web/src/features/visits/components/CheckInPage.test.tsx
    - apps/admin-web/src/features/visits/components/RecentVisitsBlock.test.tsx
    - apps/admin-web/src/features/visits/index.ts
    - apps/admin-web/src/routes/_protected/visits.tsx
  modified:
    - apps/admin-web/src/shared/api/contracts/index.ts
    - apps/admin-web/src/shared/api/services/mock/_db.ts
    - apps/admin-web/src/shared/api/services/mock/index.ts
    - apps/admin-web/src/shared/api/services/http/index.ts
    - apps/admin-web/src/shared/i18n/date.ts (todayMSK already present — partial work verified)
    - apps/admin-web/src/shared/i18n/date.test.ts
    - apps/admin-web/src/shared/i18n/index.ts (export todayMSK)
    - apps/admin-web/src/shared/i18n/ru.ts (visits domain keys)
    - apps/admin-web/src/shared/session/registry.ts (/visits entry at position 2)

key-decisions:
  - "D-22-7 enforced: mock.visits.checkIn throws DomainError('mock_not_implemented'); all read paths return seeded fixtures"
  - "Architecture Rule 5 (no cross-feature imports): useMembershipStatusForClient defined as local hook in features/visits/api/hooks.ts consuming services.memberships.byClient via swap-seam"
  - "formatTimeMSK defined inline in CheckInPage.tsx and RecentVisitsBlock.tsx using Intl.DateTimeFormat('ru-RU', {timeZone:'Europe/Moscow'}); NOT reusing date-fns formatTime() which does not TZ-convert"
  - "todayMSK was already added to shared/i18n/date.ts by the interrupted prior execution; verified correct implementation and exported from index.ts"
  - "hooks.test.tsx uses vi.mock('@/shared/i18n/date', ...) to freeze todayMSK at '2026-05-09' instead of vi.useFakeTimers() to avoid waitFor timeout issues with frozen timers"
  - "useDebounceValue from shared/lib/hooks/useDebounceValue.ts already existed; no new hook needed"
  - "visitsMeta.ts standalone file not created — GymMeta kept inline in visits.ts (plan allowed either approach)"

patterns-established:
  - "Local hook isolation: when a feature needs data from another domain, consume the SERVICE (swap-seam) directly, NOT the other feature's hook"
  - "TZ-safe time display: always use Intl.DateTimeFormat with timeZone:'Europe/Moscow' for visit timestamps in UI"
  - "Read-only mock with D-22-7: mock services for write-heavy domains implement reads from seeded DB, throws mock_not_implemented on mutations"

requirements-completed:
  - FE-05
  - FE-08

duration: 75min
completed: 2026-05-08
---

# Phase 22 Plan 03: visits feature end-to-end (entities + mock + http + hooks + CheckInPage FE-08 a..d + RecentVisitsBlock + route)

**visits feature end-to-end with CheckInPage covering all four FE-08 edge cases (disambiguation/already-checked-in/expiring-today/outside-hours) and Architecture Rule 5 compliant local membership hook**

## Performance

- **Duration:** ~75 min
- **Started:** 2026-05-08T14:45:00Z (resumed from interrupted prior execution)
- **Completed:** 2026-05-08T15:05:00Z
- **Tasks:** 3 (+ pre-existing partial work on Task 1 reconciled)
- **Files modified:** ~25

## Accomplishments

- Entities + contracts + mock service (D-22-7 read-only: checkIn throws mock_not_implemented) wired into swap-seam; 12 mock tests passing
- HTTP adapter + service + keys + hooks (useGymMeta staleTime:300_000, useMembershipStatusForClient local hook for Architecture Rule 5) + todayMSK exported; 7 hook tests passing
- CheckInPage with all FE-08(a-d) edge cases + RecentVisitsBlock (formatTimeMSK TZ-safe) + /visits route with gymMeta loader; 27 test files / 160 tests passing, tsc + lint clean

## Task Commits

Each task was committed atomically:

1. **Task 1: Entities + contracts + mock service + tests + seam wiring** — `0f4b54d` (feat)
2. **Task 2: HTTP service + hooks + todayMSK export + ru.ts visits keys** — `5050e30` (feat)
3. **Task 3: Components (RecentVisitsBlock + CheckInPage FE-08 a..d) + route + barrel** — `5da6952` (feat)

## Files Created/Modified

- `entities/visit/types.ts` — VisitId brand, VisitChannel, Visit interface
- `entities/visit/index.ts` — re-export barrel
- `shared/api/contracts/visits.ts` — VisitsService, VisitsListQuery, GymMeta (single-file; visitsMeta.ts not needed)
- `shared/api/services/mock/_db.ts` — DB.visits[], generateVisit(), migration guard
- `shared/api/services/mock/visits.ts` — D-22-7 read-only mock; checkIn throws mock_not_implemented
- `shared/api/services/mock/visits.read.test.ts` — 12 tests (RBAC, shape parity, D-22-7, latency)
- `shared/api/services/http/_visitsAdapter.ts` — responseToVisit + responseToGymMeta
- `shared/api/services/http/visits.ts` — HTTP impl consuming /api/v1/visits* paths
- `features/visits/api/keys.ts` — visitsKeys factory (all/lists/list/recentByClient/gymMeta)
- `features/visits/api/hooks.ts` — useRecentVisitsByClient + useGymMeta + useCheckIn + useMembershipStatusForClient
- `features/visits/api/hooks.test.tsx` — 7 tests
- `features/visits/model/schema.ts` — phoneSearchSchema Zod
- `features/visits/components/RecentVisitsBlock.tsx` — Card with skeleton/empty/data states; formatTimeMSK TZ-safe
- `features/visits/components/CheckInPage.tsx` — FE-08(a..d) complete; local hook, no cross-feature import
- `features/visits/components/CheckInPage.test.tsx` — 7 tests covering all FE-08 edge cases
- `features/visits/components/RecentVisitsBlock.test.tsx` — 3 tests
- `features/visits/index.ts` — barrel
- `routes/_protected/visits.tsx` — ensureQueryData(visitsKeys.gymMeta) loader; no beforeLoad
- `shared/i18n/date.ts` — todayMSK already present (partial execution); exported from index.ts
- `shared/i18n/ru.ts` — visits domain keys (20 entries)
- `shared/session/registry.ts` — /visits entry at position 2 (D-22-4, LogIn icon)
- `shared/api/services/mock/index.ts` — services.visits wired
- `shared/api/services/http/index.ts` — services.visits wired

## Decisions Made

- **visitsMeta.ts not created:** GymMeta kept inline in visits.ts (plan allowed either; single-file is acceptable).
- **todayMSK pre-existing:** The interrupted prior executor had added `todayMSK()` to date.ts with correct implementation. Verified, exported from index.ts, added boundary tests.
- **formatTimeMSK inline:** Defined in both CheckInPage.tsx and RecentVisitsBlock.tsx rather than in shared/i18n/date.ts. The plan spec explicitly placed it inline (Warning 3 mitigation pattern) with a code comment.
- **hooks.test.tsx mocks todayMSK:** Used `vi.mock('@/shared/i18n/date')` to freeze the return value rather than `vi.useFakeTimers()` to avoid waitFor timeout issues caused by frozen setTimeout.
- **useDebounceValue already existed:** Found at `shared/lib/hooks/useDebounceValue.ts` — no new hook required.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed unused parameter error in mock/visits.ts checkIn**
- **Found during:** Task 1 (lint check)
- **Issue:** `async checkIn(_clientId: string)` triggered `@typescript-eslint/no-unused-vars`
- **Fix:** Changed to `async checkIn()` (empty params, same as memberships.ts pattern for throw-only methods)
- **Files modified:** `apps/admin-web/src/shared/api/services/mock/visits.ts`
- **Committed in:** `0f4b54d` (Task 1 commit)

**2. [Rule 1 - Bug] Fixed hooks.test.ts extension — must be .tsx for JSX**
- **Found during:** Task 2 (test run)
- **Issue:** hooks.test.ts file used JSX (`<QueryClientProvider>`) but had `.ts` extension, causing esbuild transform error
- **Fix:** Renamed to hooks.test.tsx
- **Files modified:** `apps/admin-web/src/features/visits/api/hooks.test.tsx`
- **Committed in:** `5050e30` (Task 2 commit)

**3. [Rule 1 - Bug] Fixed useMembershipStatusForClient tests timing out with vi.useFakeTimers()**
- **Found during:** Task 2 (test run)
- **Issue:** `vi.useFakeTimers()` freezes `setTimeout`, causing `waitFor` to timeout in renderHook tests
- **Fix:** Used `vi.mock('@/shared/i18n/date')` to stub `todayMSK()` return value; removed fake timer usage from hooks tests
- **Files modified:** `apps/admin-web/src/features/visits/api/hooks.test.tsx`
- **Committed in:** `5050e30` (Task 2 commit)

---

**Total deviations:** 3 auto-fixed (all Rule 1 bugs)
**Impact on plan:** All auto-fixes were correctness issues. No scope creep.

## Implementation Notes

### useDebouncedValue
`useDebounceValue` already existed at `shared/lib/hooks/useDebounceValue.ts`. No new implementation required.

### Wall-clock comparison strategy for FE-08(d)
HH:MM string comparison via `formatTimeMSK` using `Intl.DateTimeFormat('ru-RU', {timeZone:'Europe/Moscow'})`. Lexicographic compare is correct for zero-padded HH:mm strings (e.g., "07:00" < "23:00"). `nowHHmmMSK()` wraps this to get the current wall-clock time in Moscow.

### /visits accessible by both roles
The route has no `beforeLoad` guard. `(check_in, visits)` is not in `OWNER_ONLY` in `can.ts`. Both owner and reception can access the page.

### 22-04 readiness
22-04 can cleanly `import { RecentVisitsBlock } from '@/features/visits'` for Pattern α composition on the `/clients/$clientId` route. `todayMSK` is exported from `@/shared/i18n/date` for the D-3 badge.

### Architecture Rule 5 confirmed
`grep -v '^[[:space:]]*//' features/visits/api/hooks.ts features/visits/components/*.tsx | grep "@/features/memberships"` — no matches. All membership data access goes through `services.memberships.byClient` via the swap-seam.

## Issues Encountered

- Prior interrupted execution had partially completed Task 1. Reconciliation: all pre-existing files matched the plan spec exactly; they were kept and built on top of.

## Next Phase Readiness

- 22-04 (client detail page Pattern α): `RecentVisitsBlock` + `todayMSK` ready for import
- `/visits` route live in mock mode; `checkIn` throws `mock_not_implemented` per D-22-7 (http mode needed for green-path mutation)
- All 27 test files + 160 tests passing; tsc + lint clean

---
*Phase: 22-admin-web-wiring-memberships-visits-active-sessions-ui*
*Completed: 2026-05-08*
