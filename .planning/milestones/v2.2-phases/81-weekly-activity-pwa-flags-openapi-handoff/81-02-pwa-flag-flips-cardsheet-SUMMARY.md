---
phase: 81-weekly-activity-pwa-flags-openapi-handoff
plan: "02"
subsystem: client-pwa
tags: [pwa, feature-flags, weekly-activity, payment-method, autopay, fz-376, openapi]
dependency_graph:
  requires: [81-01 GET /client/activity/weekly, Phase-79 GET/DELETE/PATCH /client/payment-method]
  provides: [useClientWeeklyActivity, useClientPaymentMethod, useUnlinkPaymentMethod, usePatchAutopay, CardSheet wiring, ФЗ-376 consent modal]
  affects:
    - apps/client-pwa/src/lib/clientQueries.ts
    - apps/client-pwa/src/screens/ProfileScreen.jsx
    - apps/client-pwa/src/screens/SettingsScreen.jsx
    - apps/client-pwa/src/screens/sheets/ProfileExtraSheets.jsx
    - apps/client-pwa/src/data/index.js
    - apps/backend/openapi.json
    - packages/api-client/src/schema.d.ts
tech_stack:
  added: []
  patterns: [TanStack Query hooks staleTime 30_000, onSettled invalidation, ФЗ-376 consent modal (bottom-sheet pattern), aria role=switch for testability]
key_files:
  created:
    - apps/client-pwa/src/lib/clientQueries.test.ts (16 wiring tests for 4 new hooks)
    - apps/client-pwa/src/screens/sheets/CardSheet.wiring.test.jsx (13 CardSheet wiring tests)
  modified:
    - apps/client-pwa/src/lib/clientQueries.ts (4 new hooks + 2 key factory entries)
    - apps/client-pwa/src/data/index.js (re-export 4 new hooks from @/data barrel)
    - apps/client-pwa/src/screens/ProfileScreen.jsx (flags flipped, bars wired, hook added)
    - apps/client-pwa/src/screens/SettingsScreen.jsx (flag flipped, card row wired, hook added)
    - apps/client-pwa/src/screens/sheets/ProfileExtraSheets.jsx (CardSheet fully wired)
    - apps/backend/openapi.json (regenerated — adds Phase 79+80+81 paths)
    - packages/api-client/src/schema.d.ts (regenerated — adds all new client paths)
decisions:
  - "Regenerated openapi.json + schema.d.ts in this plan (pre-existing build failures from Phase 79+80 missing schema entries fixed as Rule 1 bug)"
  - "AutopayToggleRow is a controlled component with role=switch, aria-label for test reliability"
  - "Bar heights: min 6px, max 40px, max-normalized; active days use var(--accent); guard divide-by-zero when all workouts=0"
  - "CardSheet drops ALEXANDRA Z. cardholder (no cardholder field in API); shows КАРТА CLUBCORE generic label"
metrics:
  duration: "649s (~11 min)"
  completed: "2026-06-03"
  tasks_completed: 3
  files_modified: 9
---

# Phase 81 Plan 02: PWA Flag Flips + CardSheet Wiring Summary

**One-liner:** Flip weeklyActivity + linkedCard PWA feature flags ON and wire ProfileScreen bars, SettingsScreen card row, and CardSheet to real Phase-79/81 backend endpoints with ФЗ-376 autopay consent modal.

## What Was Built

### Task 1: Four TanStack Query Hooks (clientQueries.ts)

Added to `clientPortalKeys` key factory:
- `weeklyActivity: () => [...clientPortalKeys.all, 'weekly-activity'] as const`
- `paymentMethod: () => [...clientPortalKeys.all, 'payment-method'] as const`

Four new hooks:
- **`useClientWeeklyActivity()`** — GET /api/v1/client/activity/weekly, 7-item Mon→Sun array, `staleTime: 30_000`
- **`useClientPaymentMethod()`** — GET /api/v1/client/payment-method, returns `PaymentMethodData | null`, `staleTime: 30_000`
- **`useUnlinkPaymentMethod()`** — DELETE /api/v1/client/payment-method, `onSettled` invalidates `paymentMethod()` key
- **`usePatchAutopay({ enabled, consentAcknowledged })`** — PATCH /api/v1/client/payment-method/autopay, `onSettled` invalidates `paymentMethod()` key

All four re-exported from `apps/client-pwa/src/data/index.js` via the `@/data` barrel.

Wiring test suite: `clientQueries.test.ts` with 16 tests (TDD RED→GREEN).

### Task 2: Feature Flag Flips + Screen Wiring

**ProfileScreen.jsx:**
- `PROFILE_FEATURE_FLAGS.weeklyActivity = true` (WACT-02)
- `PROFILE_FEATURE_FLAGS.linkedCard = true` (PAYM-05)
- Imported `useClientWeeklyActivity` from `@/data`; called at component top level
- Activity bars: data-driven heights from `weeklyActivity[i].workouts`, max-normalized (min 6px, max 40px), active days use `var(--accent)`, guard divide-by-zero when all workouts=0

**SettingsScreen.jsx:**
- `SETTINGS_FEATURE_FLAGS.linkedCard = true` (PAYM-05)
- Imported `useClientPaymentMethod` from `@/data`; called at component top level
- `NavRow` value: `paymentMethod ? '•••• ' + data.last4 : 'Добавить'` — no hardcoded "4821"

**OpenAPI schema regeneration** (pre-existing build failure fix, Rule 1):
- `apps/backend/openapi.json` regenerated — adds Phase 79+80+81 paths
- `packages/api-client/src/schema.d.ts` regenerated — fixes `clientRequest<keyof paths>` TS errors

Existing test mocks updated: `ProfileScreen.identity.test.jsx`, `ProfileScreen.membership.test.jsx`, `SettingsScreen.notif.test.jsx` — added missing hook stubs.

### Task 3: CardSheet Wiring + ФЗ-376 Consent + Anti-feature Removal

**ProfileExtraSheets.jsx — CardSheet:**
- Imported `useClientPaymentMethod`, `useUnlinkPaymentMethod`, `usePatchAutopay` from `@/data`
- **Card visual**: `•••• {data.last4}`, expiry `{String(expiryMonth).padStart(2,'0')} / {String(expiryYear).slice(-2)}`, `ALEXANDRA Z.` replaced with generic `КАРТА CLUBCORE` label (no cardholder field in API, T-81-07)
- **Removed**: `«Авто-оплата тренировок»` per-booking toggle — locked anti-feature (double-billing vs PT-package credit model)
- **Kept**: `«Авто-продление абонемента»` toggle, now controlled via `AutopayToggleRow` component
- **Autopay enable**: Opens ФЗ-376 consent disclosure bottom-sheet modal (amount + periodicity + cancellation) → `mutateAsync({ enabled: true, consentAcknowledged: true })` (T-81-06)
- **Autopay disable**: Directly calls `mutateAsync({ enabled: false, consentAcknowledged: false })` — no consent modal (T-81-06)
- **Unbind**: `unlinkCard.mutateAsync()` DELETE (PAYM-03) — replaces `setUnbound(true)` mock; error handling per BookingManageSheet pattern
- **`consent_required` error**: re-surfaces consent modal (T-81-08)

New `AutopayToggleRow` helper component: controlled, `role="switch"`, `aria-label` for reliable test targeting.

`CardSheet.wiring.test.jsx`: 13 tests covering all wiring assertions.

## Commits

| Task | Commit   | Description |
|------|----------|-------------|
| 1    | f045d636 | Add useClientWeeklyActivity, useClientPaymentMethod, useUnlinkPaymentMethod, usePatchAutopay hooks |
| 2    | 0575b11b | Flip WACT-02+PAYM-05 flags, wire ProfileScreen bars + SettingsScreen card row, regen OpenAPI schema |
| 3    | d9f17b5e | Wire CardSheet to real endpoints, ФЗ-376 consent modal, remove autopay-training toggle |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Pre-existing TS build failures from Phase 79+80 missing schema entries**
- **Found during:** Task 2 verification (build step)
- **Issue:** `clientRequest<keyof paths>` TS errors for `/api/v1/client/booking/{booking_id}/reschedule` (Phase 80), `/api/v1/client/payment-method` (Phase 79), and `/api/v1/client/payment-method/autopay` (Phase 79) — schema.d.ts had never been regenerated after those phases shipped. The build was already broken before this plan started.
- **Fix:** Ran `uv run python -m scripts.export_openapi` to regenerate openapi.json with all new paths, then `pnpm --filter @clubcore/api-client codegen` to regenerate schema.d.ts. Both committed in Task 2.
- **Files modified:** `apps/backend/openapi.json`, `packages/api-client/src/schema.d.ts`

**2. [Rule 1 - Bug] Existing test mocks broke when new hooks imported in components**
- **Found during:** Task 2 test run
- **Issue:** Vitest strict mock mode (`vi.mock('@/data', () => ({...}))`) threw "No useClientWeeklyActivity/useClientPaymentMethod export defined on mock" when screens imported the new hooks.
- **Fix:** Added stub entries to `ProfileScreen.identity.test.jsx`, `ProfileScreen.membership.test.jsx`, `SettingsScreen.notif.test.jsx`.

**3. [Rule 2 - Missing critical] AutopayToggleRow needs role=switch + aria-label**
- **Found during:** Task 3 test writing — querySelector('button') was unreliable in nested DOM
- **Fix:** Added `role="switch"` + `aria-label={label}` to `AutopayToggleRow` button — enables `getByRole('switch', { name })` test targeting and improves accessibility.

## Known Stubs

None. All wired paths use real hook data:
- Activity bars: real `workouts` from `useClientWeeklyActivity` (0 → flat bar)
- Card last4/expiry: real from `useClientPaymentMethod`
- Autopay state: `data?.autopayEnabled` from `useClientPaymentMethod`

The `minutes=null` field in `WeeklyActivityItem` is intentional per WACT-01 spec (deferred WACT-03), not a stub.

## Threat Flags

No new threat surface beyond the plan's threat model. All T-81-06 through T-81-10 mitigations implemented:
- T-81-06: ФЗ-376 consent modal shows amount+periodicity+cancellation before enable; `consentAcknowledged:true` sent only after confirm; backend rejects without it (409), mirrored client-side
- T-81-07: Only last4/expiryMonth/expiryYear displayed; no PAN/CVV/yookassa token
- T-81-08: `consent_required` error re-surfaces consent modal (no silent retry)
- T-81-09: No client_id sent in PWA mutations (accepted, cookie-scoped server-side)
- T-81-10: CSRF via `clientRequest` transparent cookie attachment (Phase-79 design)

## Self-Check: PASSED

Files created/exist:
- apps/client-pwa/src/lib/clientQueries.test.ts — FOUND (16 tests)
- apps/client-pwa/src/screens/sheets/CardSheet.wiring.test.jsx — FOUND (13 tests)
- apps/client-pwa/src/lib/clientQueries.ts — FOUND (useClientWeeklyActivity, usePatchAutopay exported)
- apps/client-pwa/src/screens/ProfileScreen.jsx — FOUND (PROFILE_FEATURE_FLAGS.weeklyActivity: true)
- apps/client-pwa/src/screens/SettingsScreen.jsx — FOUND (SETTINGS_FEATURE_FLAGS.linkedCard: true)
- apps/client-pwa/src/screens/sheets/ProfileExtraSheets.jsx — FOUND (consentAcknowledged:true in handler)
- apps/backend/openapi.json — FOUND (activity/weekly path present)
- packages/api-client/src/schema.d.ts — FOUND (activity/weekly, payment-method paths present)

Commits verified:
- f045d636 — FOUND
- 0575b11b — FOUND
- d9f17b5e — FOUND

Test suite: 127 tests, 19 test files — all pass.
Build: `pnpm --filter client-pwa build` — PASS.
