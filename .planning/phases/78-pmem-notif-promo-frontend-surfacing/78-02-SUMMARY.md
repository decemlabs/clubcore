---
phase: 78-pmem-notif-promo-frontend-surfacing
plan: "02"
subsystem: ui
tags: [react, tanstack-query, vitest, optimistic-update, notification-prefs, client-pwa]

# Dependency graph
requires:
  - phase: 78-pmem-notif-promo-frontend-surfacing
    provides: "Phase 75 backend NOTIF-01: PATCH /client/me notifPrefs accepted server-side"
provides:
  - "notifPrefs field in useUpdateClientProfile mutation payload type (clientQueries.ts)"
  - "SettingsScreen notification toggles hydrating from GET /client/me and persisting via PATCH /client/me"
  - "Optimistic-flip + revert-on-error pattern for notification toggle saves"
  - "Vitest coverage: hydration, full-replace PATCH, optimistic flip, revert+toast on error"
affects:
  - "Any future plan touching SettingsScreen or notification prefs"
  - "NOTIF-01 requirement closure"

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Optimistic toggle with full-key replace: setNotif(next) → mutateAsync({notifPrefs: next}) → revert on catch"
    - "Local in-sheet toast for save errors (no global Sonner in PWA)"
    - "useEffect re-sync from authoritative server value (me?.notifPrefs) on data arrival"

key-files:
  created:
    - apps/client-pwa/src/screens/SettingsScreen.notif.test.jsx
  modified:
    - apps/client-pwa/src/lib/clientQueries.ts
    - apps/client-pwa/src/screens/SettingsScreen.jsx

key-decisions:
  - "D-78-05: NOTIF_STORAGE_KEY localStorage read/write removed entirely; server is sole persistence store"
  - "D-78-06: Toggle sends full 4-key notifPrefs object (not partial) to backend — matches extra=forbid schema"
  - "D-78-07: notifPrefs added as optional field to useUpdateClientProfile payload type"
  - "D-78-08: useEffect re-syncs local notif state from me.notifPrefs on arrival, surviving full reload"

patterns-established:
  - "Optimistic full-replace mutation: capture prior state → setLocal(next) → await mutateAsync → catch reverts to prior"
  - "Local toast pattern for non-global-Sonner screens: useState(null) + useRef timer + 2600ms auto-dismiss"

requirements-completed: [NOTIF-01]

# Metrics
duration: 25min
completed: 2026-06-02
---

# Phase 78 Plan 02: NOTIF-01 Frontend Surfacing Summary

**Settings notification toggles made server-backed: hydrate from GET /client/me notifPrefs, persist via PATCH /client/me full 4-key replace, localStorage dropped as persistence store**

## Performance

- **Duration:** 25 min
- **Started:** 2026-06-02T19:46:00Z
- **Completed:** 2026-06-02T20:11:01Z
- **Tasks:** 3
- **Files modified:** 3 (1 created, 2 modified)

## Accomplishments
- Extended `useUpdateClientProfile` mutation payload type with optional `notifPrefs` (4 boolean keys matching backend strict schema)
- Rewired SettingsScreen's 4 notification toggles to hydrate from `useClientMe().notifPrefs` and save via `mutateAsync` with full 4-key replace + optimistic flip + revert-on-error
- Removed all `NOTIF_STORAGE_KEY` localStorage read/write — server is now the sole persistence store (closes D-78-05)
- Added `SettingsScreen.notif.test.jsx` with 6 Vitest cases covering hydration, optimistic flip, full-replace PATCH, and revert+toast on rejection

## Task Commits

Each task was committed atomically:

1. **Task 1: Add notifPrefs to useUpdateClientProfile payload type** - `e7d6d163` (feat)
2. **Task 2: Rewire SettingsScreen toggles to server-backed optimistic save** - `5a4b942d` (feat)
3. **Task 3: Add SettingsScreen notif Vitest coverage** - `9061551b` (test)

## Files Created/Modified
- `apps/client-pwa/src/lib/clientQueries.ts` — Added `notifPrefs?: { promo: boolean; schedule: boolean; trainer: boolean; sound: boolean }` to `useUpdateClientProfile` mutationFn payload type
- `apps/client-pwa/src/screens/SettingsScreen.jsx` — Dropped localStorage notif persistence; wired toggles to `useClientMe().notifPrefs` + `useUpdateClientProfile().mutateAsync`; added local in-sheet toast for errors
- `apps/client-pwa/src/screens/SettingsScreen.notif.test.jsx` — New: 6 Vitest tests covering all NOTIF-01 behaviors

## Decisions Made
- Installed pnpm dependencies in the worktree (`pnpm install --frozen-lockfile`) since the worktree lacks node_modules — gates ran successfully against worktree files
- Used `NOTIF_DEFAULTS` only as a render-only fallback (not removed) so the UI has a sensible state before the first `me()` response arrives; server value takes over via `useEffect`
- Toast error copy: "Не удалось сохранить настройки. Попробуйте ещё раз." (mirrors ProfileExtraSheets pattern)

## Deviations from Plan

None — plan executed exactly as written. pnpm install in the worktree was a setup prerequisite, not a plan deviation.

## Issues Encountered
- Worktree lacked `node_modules` — ran `pnpm install --frozen-lockfile` at worktree root before first tsc/lint gate. All subsequent gates ran cleanly.

## Known Stubs
None — notification prefs are fully wired to the server; no placeholder data.

## Threat Flags
No new security surface introduced. The PATCH sends exactly 4 validated booleans for the authenticated principal (per T-78-03 disposition: mitigate — backend extra=forbid enforces strict schema). Dropping localStorage reduces local persistence surface (T-78-05 disposition: accept).

## Self-Check: PASSED

- FOUND: apps/client-pwa/src/lib/clientQueries.ts
- FOUND: apps/client-pwa/src/screens/SettingsScreen.jsx
- FOUND: apps/client-pwa/src/screens/SettingsScreen.notif.test.jsx
- FOUND: .planning/phases/78-pmem-notif-promo-frontend-surfacing/78-02-SUMMARY.md
- FOUND commit e7d6d163 (Task 1: notifPrefs type)
- FOUND commit 5a4b942d (Task 2: SettingsScreen rewrite)
- FOUND commit 9061551b (Task 3: notif tests)
- NOTIF_STORAGE_KEY count in SettingsScreen.jsx: 0 (acceptance criteria met)
- localStorage count in SettingsScreen.jsx: 0 (acceptance criteria met)
