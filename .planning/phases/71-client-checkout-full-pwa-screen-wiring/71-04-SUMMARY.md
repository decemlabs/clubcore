---
phase: 71-client-checkout-full-pwa-screen-wiring
plan: "04"
subsystem: ui
tags: [react-query, typescript, eslint, pwa, openapi, codegen, swap-seam]

# Dependency graph
requires:
  - phase: 71-02
    provides: POST /api/v1/client/checkout/memberships/{plan_id}, POST /api/v1/client/checkout/pt-packages/{plan_id}, GET /api/v1/client/payments/{payment_id}/status
  - phase: 69-client-read-endpoints-pwa-stack-alignment
    provides: clientFetcher.ts typed transport, @clubcore/api-client, /api/v1/client/history/* paths in schema.d.ts

provides:
  - openapi.json regenerated with three new client checkout/status paths
  - packages/api-client/src/schema.d.ts regenerated with typed client checkout + payment status paths
  - apps/client-pwa/src/lib/queryClient.ts (QueryClient with admin-web-mirrored defaults + session-expiry handler)
  - apps/client-pwa/src/lib/clientQueries.ts (clientPortalKeys factory + 9 query/mutation hooks over clientFetcher)
  - apps/client-pwa/src/data/index.js (single mock→real swap seam re-exporting hooks + legacy mocks)
  - apps/client-pwa/src/components/ComingSoon.tsx (shared "В разработке" placeholder, query-layer-free)
  - apps/client-pwa/eslint.config.js extended with D-71-09 import boundary for five net-new screens

affects:
  - 71-05 (consumes clientQueries.ts hooks; performs QueryClientProvider root wrap in App.jsx)
  - 71-06 (consumes clientQueries.ts checkout hooks for wired screens)
  - Phase 72 (client-portal tag freeze, _v20Checks guards)

# Tech tracking
tech-stack:
  added:
    - "@tanstack/react-query ^5.59.0 added to apps/client-pwa"
  patterns:
    - "Per-feature query-key factory (clientPortalKeys) mirroring admin-web xKeys convention"
    - "QueryCache + MutationCache onError session-expiry handler using window.location.replace('/login') (react-router v6, D-20-PWA-ROUTER)"
    - "Polling hook with refetchInterval returning 3000 while status=pending, else false"
    - "Swap seam: data/index.js re-exports query hooks + legacy mocks; Plans 05/06 remove mocks as screens wire"
    - "ESLint negated-ignore pattern to expose specific .jsx files for no-restricted-paths rule (flat config v9)"

key-files:
  created:
    - apps/client-pwa/src/lib/queryClient.ts
    - apps/client-pwa/src/lib/clientQueries.ts
    - apps/client-pwa/src/components/ComingSoon.tsx
  modified:
    - apps/backend/openapi.json
    - packages/api-client/src/schema.d.ts
    - apps/client-pwa/package.json
    - pnpm-lock.yaml
    - apps/client-pwa/src/data/index.js
    - apps/client-pwa/eslint.config.js
    - apps/client-pwa/src/screens/ChatScreen.jsx
    - apps/client-pwa/src/screens/sheets/GymInfoSheet.jsx
    - apps/client-pwa/src/screens/sheets/NotificationsSheet.jsx

key-decisions:
  - "clientRequest method argument must be lowercase ('get', 'post') — keyof paths[P] in schema.d.ts uses lowercase HTTP method names"
  - "ESLint flat config v9: global 'ignores' with negated patterns ('!src/screens/...') is the only way to expose specific .jsx files to a dedicated rule block, since global ignores cannot be overridden by a later 'files' config block"
  - "Net-new screens (ChatScreen, GymInfoSheet, NotificationsSheet) rewritten as ComingSoon wrappers per D-71-08; complex mock-data component bodies stripped"
  - "queryClient.ts uses window.location.replace('/login') for session expiry (not TanStack Router navigate), per D-20-PWA-ROUTER"

patterns-established:
  - "Swap seam pattern: data/index.js re-exports both query hooks AND legacy mocks; each mock removed as its consumer screen is wired in Plans 05/06"
  - "QueryClient at apps/client-pwa/src/lib/queryClient.ts is created here; QueryClientProvider root wrap is Plan 71-05 Task 2 (single-owner of App.jsx)"

requirements-completed: [PWA-05]

# Metrics
duration: 9min
completed: "2026-05-30"
---

# Phase 71 Plan 04: PWA Data-Fetching Foundation Summary

**React Query hook layer over clientFetcher typed transport: regenerated openapi.json + schema.d.ts with client checkout/status paths, queryClient.ts mirroring admin-web defaults, clientQueries.ts with 9 typed hooks, data/index.js as single swap seam, ComingSoon placeholder, and ESLint import boundary structurally enforcing zero API calls from net-new screens.**

## Performance

- **Duration:** 9 min
- **Started:** 2026-05-30T15:29:20Z
- **Completed:** 2026-05-30T15:38:38Z
- **Tasks:** 3 (Task 0 + Task 1 + Task 2)
- **Files modified:** 11

## Accomplishments

- Regenerated `openapi.json` (391431 bytes) via `scripts.export_openapi` and `schema.d.ts` via `pnpm codegen`; all three new client paths (`/checkout/memberships/{plan_id}`, `/checkout/pt-packages/{plan_id}`, `/payments/{payment_id}/status`) now typed; staff paths byte-identical (D-20-OPENAPI)
- Created `queryClient.ts` with `staleTime: 30_000`, `refetchOnWindowFocus: false`, `retry: 1/0`, session-expiry handler; and `clientQueries.ts` with `clientPortalKeys` factory + `useClientHome`, `useClientPlans`, `useClientPtPackages`, `useClientVisitHistory`, `useClientPtHistory`, `useClientPaymentHistory`, `useClientPaymentStatus` (polling), `useClientCheckoutMembership`, `useClientCheckoutPtPackage`
- Turned `data/index.js` into the single mock→real swap seam; extended `eslint.config.js` with D-71-09 import boundary (proven to fire); created `ComingSoon.tsx`; stripped mock data from three net-new screens (ChatScreen, GymInfoSheet, NotificationsSheet)

## Task Commits

1. **Task 0: Regenerate openapi.json + schema.d.ts** - `0bbc38b5` (chore)
2. **Task 1: Add React Query, queryClient.ts, and clientQueries.ts** - `db24d72f` (feat)
3. **Task 2: Swap seam, ComingSoon placeholder, and ESLint import boundary** - `909b082f` (feat)

**Plan metadata:** (docs commit to follow)

## Files Created/Modified

- `apps/backend/openapi.json` - Regenerated via scripts.export_openapi (391431 bytes, additive for client paths)
- `packages/api-client/src/schema.d.ts` - Regenerated via pnpm codegen; contains /api/v1/client/checkout/* + /api/v1/client/payments/{payment_id}/status
- `apps/client-pwa/package.json` - Added @tanstack/react-query ^5.59.0
- `pnpm-lock.yaml` - Updated with new dependency
- `apps/client-pwa/src/lib/queryClient.ts` - New: QueryClient with admin-web-mirrored defaults + session-expiry handler
- `apps/client-pwa/src/lib/clientQueries.ts` - New: clientPortalKeys factory + 9 typed query/mutation hooks
- `apps/client-pwa/src/data/index.js` - Updated: re-exports query hooks + retains legacy mocks with removal notes
- `apps/client-pwa/src/components/ComingSoon.tsx` - New: "В разработке" placeholder component
- `apps/client-pwa/eslint.config.js` - Extended with D-71-09 import boundary for five net-new screens
- `apps/client-pwa/src/screens/ChatScreen.jsx` - Rewritten as ComingSoon wrapper (D-71-08; mock data stripped)
- `apps/client-pwa/src/screens/sheets/GymInfoSheet.jsx` - Rewritten as ComingSoon wrapper (D-71-08; mock data stripped)
- `apps/client-pwa/src/screens/sheets/NotificationsSheet.jsx` - Rewritten as ComingSoon wrapper (D-71-08; mock data stripped)

## Decisions Made

- `clientRequest` method argument uses lowercase HTTP method names (`'get'`, `'post'`) — this is the `keyof paths[P]` constraint in `schema.d.ts` (uppercase `'GET'` caused TS2345 errors)
- ESLint flat config v9 requires negated ignore patterns (`'!src/screens/ChatScreen.jsx'`, etc.) in the global `ignores` block to expose specific `.jsx` files to a dedicated rule block; simply adding a `files: [...]` config block is not sufficient because global ignores cannot be overridden
- Three net-new screens (ChatScreen, GymInfoSheet, NotificationsSheet) that had `@/data` imports were rewritten as thin ComingSoon wrappers per D-71-08; this was required to make the import boundary pass lint with zero violations
- `queryClient.ts` is created but `<QueryClientProvider>` root wrap in `App.jsx` is owned by Plan 71-05 Task 2 (single-owner principle)

## Known Stubs

Retained legacy mock exports in `data/index.js` (not stubs — they have data, just not yet replaced by query hooks):

| Mock | File | Retained Until |
|------|------|----------------|
| `TRAINERS, CALENDAR, TIME_SLOTS, BUSY_SLOTS` | data/trainers.js, data/calendar.js | Plan 06 wires BookScreen |
| `NOTIFICATIONS, GYM_INFO, TRAINER_CANCEL, UPCOMING_BOOKING` | data/notifications.js, etc. | Plan 05 wires HomeScreen |
| `VISIT_HISTORY, TRAINING_HISTORY, PURCHASE_HISTORY` | data/history.js | Plan 05 Task 1a wires ProfileScreen tabs |
| `PLANS, PLAN_FEATURES` | data/plans.js | Plan 05 wires PlansSheet |
| `CONVERSATIONS` | data/conversations.js | App.jsx badge counter (net-new ChatScreen stripped; App.jsx not a wired screen) |

These are intentional — the mock constants remain as safety fallbacks for the 4 wired screens pending Plans 05/06. Remove each export as its consumer is wired.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed clientRequest method case from uppercase to lowercase**
- **Found during:** Task 1 (clientQueries.ts creation)
- **Issue:** `clientRequest('GET', ...)` caused `TS2345: Argument of type '"GET"' is not assignable to parameter of type '"head" | "parameters" | "get" | ...` — the `M extends keyof paths[P]` constraint in the generated schema uses lowercase HTTP method names
- **Fix:** Changed all method arguments to lowercase (`'get'`, `'post'`)
- **Files modified:** apps/client-pwa/src/lib/clientQueries.ts
- **Verification:** `pnpm typecheck` exits 0
- **Committed in:** db24d72f (Task 1 commit)

**2. [Rule 1 - Bug] Removed unused React import from ComingSoon.tsx**
- **Found during:** Task 2 (build gate)
- **Issue:** `import React from 'react'` in ComingSoon.tsx caused `TS6133: 'React' is declared but its value is never read` under `noUnusedLocals: true` — the new JSX transform (`react-jsx`) does not require explicit React import
- **Fix:** Removed `import React from 'react'`
- **Files modified:** apps/client-pwa/src/components/ComingSoon.tsx
- **Verification:** `pnpm build` exits 0
- **Committed in:** 909b082f (Task 2 commit)

**3. [Rule 1 - Bug] Net-new screen JSX files had @/data imports blocked by ESLint boundary**
- **Found during:** Task 2 (boundary verification)
- **Issue:** `ChatScreen.jsx`, `GymInfoSheet.jsx`, `NotificationsSheet.jsx` had existing `@/data` imports for mock constants; after enabling the D-71-09 ESLint boundary, these screens became lint violations (no-restricted-paths fires on `@/data` as it is now the swap seam with query hooks)
- **Fix:** Rewrote the three screens as minimal ComingSoon wrappers per D-71-08 (mock data stripped, component export retained with same name/signature)
- **Files modified:** ChatScreen.jsx, GymInfoSheet.jsx, NotificationsSheet.jsx
- **Verification:** `pnpm lint` exits 0; boundary proven to fire on a test import then reverted
- **Committed in:** 909b082f (Task 2 commit)

---

**Total deviations:** 3 auto-fixed (all Rule 1 bugs)
**Impact on plan:** All three auto-fixes were essential for correctness. The method-case fix was required for TypeScript to accept the clientRequest calls; the React import fix was required for `noUnusedLocals` strict mode; the net-new screen rewrites were the intended D-71-08 outcome, triggered by the ESLint boundary making the existing mock imports violations.

## Issues Encountered

None beyond the auto-fixed deviations above.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- `queryClient.ts` is ready; Plan 71-05 Task 2 must add `<QueryClientProvider queryClient={queryClient}>` to `App.jsx` (single-owner of App.jsx)
- `clientQueries.ts` hooks are fully typed and ready for Plans 05/06 screen wiring
- `data/index.js` is the swap seam; Plans 05/06 remove each legacy mock as its consumer screen is wired
- The three net-new screens (ReferralSheet, TrainerDetailSheet) have NO data imports and are already import-clean; ChatScreen, GymInfoSheet, NotificationsSheet now render ComingSoon
- ESLint boundary is structural — no review needed to catch future query-layer imports in net-new screens

## Threat Flags

No new threat surface beyond what is modeled in the plan's `<threat_model>`:
- T-71-15 mitigated: D-71-09 ESLint boundary structurally bars net-new screens from clientFetcher/clientQueries/data; proven to fire
- T-71-17 mitigated: session-expiry handler in queryClient.ts redirects to /login on session_expired ApiError
- T-71-22 mitigated: schema.d.ts regenerated from live FastAPI surface via codegen (never hand-edited); staff paths byte-identical

## Self-Check

Files created/modified exist:
- `apps/backend/openapi.json` (contains `/api/v1/client/checkout/memberships`): FOUND
- `packages/api-client/src/schema.d.ts` (contains `/api/v1/client/checkout/memberships`): FOUND
- `apps/client-pwa/src/lib/queryClient.ts`: FOUND
- `apps/client-pwa/src/lib/clientQueries.ts` (contains `useClientCheckoutMembership`): FOUND
- `apps/client-pwa/src/data/index.js` (contains `useClientHome`): FOUND
- `apps/client-pwa/src/components/ComingSoon.tsx` (contains `В разработке`): FOUND
- `apps/client-pwa/eslint.config.js` (contains `no-restricted-paths`): FOUND

Commits exist:
- `0bbc38b5` — chore(71-04): regenerate openapi.json + schema.d.ts: FOUND
- `db24d72f` — feat(71-04): add React Query, queryClient.ts, and clientQueries.ts: FOUND
- `909b082f` — feat(71-04): swap seam, ComingSoon placeholder, and ESLint import boundary: FOUND

## Self-Check: PASSED

---
*Phase: 71-client-checkout-full-pwa-screen-wiring*
*Completed: 2026-05-30*
