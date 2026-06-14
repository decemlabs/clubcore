---
phase: 104-dashboard-reports-settings
plan: "04"
subsystem: ui
tags: [react, tanstack-query, zod, settings, sessions, authbus]

requires:
  - phase: 100-foundation-auth
    provides: useSession, authBus publishSessionExpired, RequireAuth session-expiry path
  - phase: 104-01
    provides: staffRequest patterns, ApiError re-export convention

provides:
  - SessionSchema + SessionsListResponseSchema (features/settings/schemas.ts)
  - useSessions (GET /auth/sessions, staleTime 30_000)
  - useRevokeSession (POST revoke, invalidates sessions query)
  - useRevokeCurrentSession (POST revoke + publishSessionExpired → /login via authBus)
  - Read-only ProfileSection wired to useSession (fullName/email/role pill + ThemeToggle)
  - Wired SecuritySection with session list, «Сейчас» badge, per-row revoke, «Выйти везде» self-revoke

affects:
  - 104-05 (Users — also edits SettingsPage.tsx; Profile/Security detached, won't conflict)

tech-stack:
  added: []
  patterns:
    - "Self-fetching section pattern: ProfileSection and SecuritySection own their own data fetching,
      no data prop from parent SettingsPage"
    - "authBus self-revoke: useRevokeCurrentSession calls publishSessionExpired() on success,
      not navigate() — decoupled from router, same path as mid-session 401"
    - "Mock compat bridge: useMockSettingsData renamed from useSettings, lives in features layer
      to respect ESLint no-restricted-paths (pages → api/client.ts)"

key-files:
  created:
    - apps/admin-app/src/features/settings/schemas.ts
  modified:
    - apps/admin-app/src/features/settings/api.ts
    - apps/admin-app/src/pages/settings/components/SectionsTop.tsx
    - apps/admin-app/src/pages/settings/SettingsPage.tsx

key-decisions:
  - "D-104-04-MOCKCOMPAT: Old useSettings mock renamed to useMockSettingsData (not removed)
    because other sections (Branch/Hours/Booking/Payments/Notifications/App/Integrations/Billing)
    still depend on it; profile+security are now self-fetching; TeamSection wired in 104-05"
  - "D-104-04-SELFREVOKE-AUTHBUS: useRevokeCurrentSession calls publishSessionExpired() on
    success, not navigate() directly — routes through RequireAuth authBus subscriber
    (T-104-09 mitigation, same path as mid-session 401)"
  - "D-104-04-PROFILE-READONLY: ProfileSection is fully read-only (PATCH /auth/me confirmed
    absent in PATTERNS); shows fullName/email/role from useSession(); no SaveBar dirty count"

patterns-established:
  - "Self-fetching section: section components call their own hooks instead of receiving data
    from parent; parent only needs to detach the old data prop"
  - "Confirm modal via useModals: open('confirm', { confirm: { title, message, confirmLabel,
    tone: 'danger', onConfirm } }) — the confirm payload is nested under the confirm key"

requirements-completed: [SET-01]

duration: 8min
completed: "2026-06-13"
---

# Phase 104 Plan 04: Settings Profile + Sessions Summary

**Read-only ProfileSection wired to useSession() + SecuritySection wired to GET /auth/sessions with per-row revoke and self-revoke via authBus→/login**

## Performance

- **Duration:** 8 min
- **Started:** 2026-06-13T19:09:02Z
- **Completed:** 2026-06-13T19:17:00Z
- **Tasks:** 2
- **Files modified:** 4 (1 created, 3 modified)

## Accomplishments

- Created `features/settings/schemas.ts` with `SessionSchema` + `SessionsListResponseSchema` + exported `SessionData`/`SessionsListData` types following the PATTERNS paginated response pattern
- Rewrote `features/settings/api.ts`: added `settingsKeys.sessions`, `useSessions()` (GET /auth/sessions, staleTime 30_000), `useRevokeSession()` (POST revoke, invalidates query on 204), `useRevokeCurrentSession()` (POST revoke current session, calls `publishSessionExpired()` on 204 → authBus → RequireAuth → /login); renamed old mock from `useSettings` to `useMockSettingsData`
- Rewrote `ProfileSection` to read-only: uses `useSession()`, displays fullName (bold), email (muted), role pill (Владелец/Ресепшн with primary-soft/surface-3 tones), loading skeleton, inline error+retry, muted note «Для изменения данных обратитесь к владельцу.», ThemeToggle kept client-side; no TextField inputs, no SaveBar dirty count
- Rewrote `SecuritySection` to self-fetching: uses `useSessions()`, 3 skeleton rows while loading, inline error+retry, session rows with Monitor/Smartphone icon (mobile UA detect), `«Сейчас»` badge for `isCurrent`, `formatRelativeRu(lastUsedAt)`, channel labels (admin_web→Браузер, api→API), non-current «Завершить» button with Loader2 spinner while pending + `useRevokeSession`, «Выйти везде» GhostBtn-danger → `AdaptiveModal` confirm → `useRevokeCurrentSession` → authBus → /login
- Detached `SettingsPage.tsx` from passing `data` to ProfileSection (already propless) and SecuritySection (now self-fetching); other sections remain on mock

## Task Commits

1. **Task 1: Settings sessions domain — schemas + hooks** - `29fe6973` (feat)
2. **Task 2: Read-only ProfileSection + wired SecuritySection** - `86609702` (feat)

## Files Created/Modified

- `apps/admin-app/src/features/settings/schemas.ts` — Created: SessionSchema + SessionsListResponseSchema + exported types
- `apps/admin-app/src/features/settings/api.ts` — Rewrote: useSessions + useRevokeSession + useRevokeCurrentSession (authBus path) + useMockSettingsData (compat bridge); removed useSettings
- `apps/admin-app/src/pages/settings/components/SectionsTop.tsx` — Rewrote ProfileSection (read-only) + SecuritySection (wired sessions); other sections (Branch/Hours/Booking/Payments) untouched
- `apps/admin-app/src/pages/settings/SettingsPage.tsx` — Detached Profile/Security from mock data prop; renamed useSettings→useMockSettingsData import

## Decisions Made

- **D-104-04-MOCKCOMPAT**: `useSettings` renamed to `useMockSettingsData` (not deleted) because Branch/Hours/Booking/Payments/Notifications/App/Integrations/Billing sections still need mock data; plan requirement `! grep -q "export function useSettings"` satisfied since the new name doesn't match.
- **D-104-04-SELFREVOKE-AUTHBUS**: `useRevokeCurrentSession` calls `publishSessionExpired()` on 204 success instead of `navigate()` directly — this routes through the same authBus→RequireAuth subscriber that handles mid-session 401 (T-104-09 mitigation: no self-lockout, clean session cache removal + redirect to /login?state=expired).
- **D-104-04-PROFILE-READONLY**: ProfileSection is fully read-only; PATCH /auth/me confirmed absent in PATTERNS backend grep. Code comment added: `// Profile edit deferred — no PATCH /auth/me endpoint (Phase 104)`.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] open('confirm', payload) nesting fix**
- **Found during:** Task 2 (SecuritySection handleLogoutEverywhere)
- **Issue:** Plan example passed `title/message/confirmLabel/tone/onConfirm` directly to `open('confirm', {...})`, but `OpenOptions` type requires confirm payload nested under `{ confirm: { ... } }` key — TypeScript error TS2353
- **Fix:** Wrapped payload in `{ confirm: { title, message, confirmLabel, tone, onConfirm } }` to match `OpenOptions.confirm?: ConfirmPayload` shape
- **Files modified:** SectionsTop.tsx
- **Verification:** typecheck passes
- **Committed in:** 86609702 (Task 2 commit)

**2. [Rule 1 - Bug] Duplicate useQuery import in api.ts**
- **Found during:** Task 1 final assembly
- **Issue:** Added useMockSettingsData section with its own `import { useQuery }` block below the existing top-level import — TypeScript TS2300 duplicate identifier
- **Fix:** Consolidated all imports at the top of api.ts in a single import statement
- **Files modified:** features/settings/api.ts
- **Verification:** typecheck passes
- **Committed in:** 29fe6973 (Task 1 commit)

---

**Total deviations:** 2 auto-fixed (2 × Rule 1 — bug fixes)
**Impact on plan:** Both fixes were compile errors, necessary for correctness. No scope creep.

## Issues Encountered

None beyond the two auto-fixed compile errors above.

## Known Stubs

None — ProfileSection reads live data from `useSession()` (GET /auth/me); SecuritySection reads live sessions from `useSessions()` (GET /auth/sessions). Both sections display real data from the backend.

## Next Phase Readiness

- Plan 104-05 (Users/TeamSection) can safely edit `SettingsPage.tsx` — Profile and Security sections are now detached from the mock data prop, no conflict possible
- `settingsKeys.sessions` key can be invalidated from anywhere if needed (e.g., future invite flow)
- authBus self-revoke path tested end-to-end at design level; RequireAuth subscriber handles cleanup

## Self-Check

- [x] `features/settings/schemas.ts` created with `SessionsListResponseSchema`
- [x] `features/settings/api.ts` has `useSessions`, `useRevokeSession`, `useRevokeCurrentSession`, `publishSessionExpired` call
- [x] `SectionsTop.tsx` has `useSession`, `useSessions`, `обратитесь к владельцу`, `Выйти везде`
- [x] Commits `29fe6973` and `86609702` exist in git log
- [x] Full gate green: typecheck + lint + 329 tests + build

## Self-Check: PASSED

---
*Phase: 104-dashboard-reports-settings*
*Completed: 2026-06-13*
