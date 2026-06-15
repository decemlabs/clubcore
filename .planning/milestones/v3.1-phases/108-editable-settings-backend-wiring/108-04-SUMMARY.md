---
phase: 108-editable-settings-backend-wiring
plan: "04"
subsystem: frontend
tags: [settings, zod, tanstack-query, rbac, hooks, gym, hours, booking, notifications]
dependency_graph:
  requires:
    - "108-02 (settings endpoints: GET/PUT /api/v1/settings/{hours,booking,notifications} + staff GET /api/v1/gym)"
  provides:
    - "GymInfoSchema/GymInfoUpdateSchema + useGymInfo/useUpdateGymInfo (CFG-01)"
    - "WorkingHoursSchema/WorkingHoursUpdateSchema + useWorkingHours/useUpdateWorkingHours (CFG-02)"
    - "BookingConfigSchema/BookingConfigUpdateSchema + useBookingConfig/useUpdateBookingConfig (CFG-03)"
    - "NotificationPrefsSchema/NotificationPrefsUpdateSchema + useNotificationPrefs/useUpdateNotificationPrefs (CFG-04)"
    - "Extended settingsKeys factory (gymInfo/workingHours/bookingConfig/notificationPrefs)"
  affects:
    - apps/admin-app/src/features/settings/schemas.ts
    - apps/admin-app/src/features/settings/api.ts
    - apps/admin-app/src/shared/session/can.test.ts
tech_stack:
  added: []
  patterns:
    - "Zod seam: wire-response schema → ResponseSchema wrapper → inferred type → Update/form schema reused for react-hook-form resolver + PUT body"
    - "TanStack Query enabled gate: can(role,'edit',resource) blocks reception at query layer (zero requests)"
    - "staffRequest 'as never' path cast for Phase 111 schema regen (D-V31-CONTRACT-ADDITIVE)"
    - "onSuccess toast.success + invalidateQueries; onError ApiError.message fallback toast"
key_files:
  created: []
  modified:
    - apps/admin-app/src/features/settings/schemas.ts
    - apps/admin-app/src/features/settings/api.ts
    - apps/admin-app/src/shared/session/can.test.ts
decisions:
  - "D-108-04-PATH-CAST: /api/v1/settings/{hours,booking,notifications} paths cast 'as never' at staffRequest call sites — not yet in schema.d.ts; Phase 111 regenerates additively per D-V31-CONTRACT-ADDITIVE"
  - "D-108-04-KOPECKS-COMMENT: noShowPenaltyKopecks documented in both schemas.ts and api.ts as requiring ×100 multiply before submit and ÷100 for display — Plan 05 must implement"
  - "D-108-04-WORKING-HOURS-REFINE: WorkingHoursUpdateSchema uses typed ScheduleDaySchema for schedule array + .refine() for close>open; breaks/closures remain unknown[] passthrough per backend design"
  - "D-108-04-CAN-TEST-FIX: can.test.ts OWNER_ONLY count was stale at 41 — Phase 108-01 added entry but test was not updated; fixed as Rule 1 bug"
metrics:
  duration: "~6 minutes"
  completed: "2026-06-14"
  tasks_completed: 2
  tasks_total: 2
  files_created: 0
  files_modified: 3
---

# Phase 108 Plan 04: Settings Frontend Data Layer (Hooks + Schemas) Summary

Zod wire+form schemas and eight TanStack Query hooks for the four settings concerns (gym/hours/booking/notifications) — the data-layer contract Plan 05's section components consume directly.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Zod schemas for gym/hours/booking/notifications (wire + form validation) | 8ffa46e0 | schemas.ts |
| 2 | TanStack Query hooks for all four concerns | a14e8a78 | api.ts, can.test.ts |

## Hook Signatures

| Hook | Signature | Endpoint | Gate |
|------|-----------|----------|------|
| `useGymInfo` | `useGymInfo(role: Role)` | GET /api/v1/gym | `can(role,'edit','gym')` |
| `useUpdateGymInfo` | `useUpdateGymInfo()` | PUT /api/v1/gym | — |
| `useWorkingHours` | `useWorkingHours(role: Role)` | GET /api/v1/settings/hours | `can(role,'edit','settings')` |
| `useUpdateWorkingHours` | `useUpdateWorkingHours()` | PUT /api/v1/settings/hours | — |
| `useBookingConfig` | `useBookingConfig(role: Role)` | GET /api/v1/settings/booking | `can(role,'edit','settings')` |
| `useUpdateBookingConfig` | `useUpdateBookingConfig()` | PUT /api/v1/settings/booking | — |
| `useNotificationPrefs` | `useNotificationPrefs(role: Role)` | GET /api/v1/settings/notifications | `can(role,'edit','settings')` |
| `useUpdateNotificationPrefs` | `useUpdateNotificationPrefs()` | PUT /api/v1/settings/notifications | — |

## settingsKeys Factory Extensions

```typescript
export const settingsKeys = {
  sessions: ['auth', 'sessions'] as const,         // pre-existing
  gymInfo: ['settings', 'gym'] as const,           // CFG-01 (new)
  workingHours: ['settings', 'hours'] as const,    // CFG-02 (new)
  bookingConfig: ['settings', 'booking'] as const, // CFG-03 (new)
  notificationPrefs: ['settings', 'notifications'] as const, // CFG-04 (new)
}
```

## Kopecks ↔ Rubles Convention (for Plan 05)

`BookingConfigSchema.noShowPenaltyKopecks` is stored/transmitted as **integer kopecks**.

Plan 05 (BookingSection form) **must**:
- Display `noShowPenaltyKopecks / 100` in the MoneyField (rubles)
- Submit `formValueRubles * 100` as `noShowPenaltyKopecks` in the PUT body

This convention is documented in both `schemas.ts` (comment on `BookingConfigSchema`) and `api.ts` (comment on `useUpdateBookingConfig`).

## Schema Exports for Plan 05

```typescript
// schemas.ts exports for Plan 05 form wiring:
import {
  GymInfoUpdateSchema, type GymInfoUpdateInput,       // CFG-01 BranchSection form
  WorkingHoursUpdateSchema, type WorkingHoursUpdateInput, // CFG-02 HoursSection form
  BookingConfigUpdateSchema, type BookingConfigUpdateInput, // CFG-03 BookingSection form
  NotificationPrefsUpdateSchema, type NotificationPrefsUpdateInput, // CFG-04 NotificationsSection form
} from '@/features/settings/schemas'
```

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed stale OWNER_ONLY count in can.test.ts**
- **Found during:** Task 2 test run
- **Issue:** `can.test.ts` asserted exactly 41 OWNER_ONLY entries; Phase 108-01 added `{ action: 'edit', resource: 'settings' }` making it 42 entries but the test was not updated atomically
- **Fix:** Updated test description "all 41 OWNER_ONLY pairs" → "all 42 OWNER_ONLY pairs" and matrix count assertion 41 → 42
- **Files modified:** `apps/admin-app/src/shared/session/can.test.ts`
- **Commit:** a14e8a78

### Type Cast Deviation

**D-108-04-PATH-CAST:** `/api/v1/settings/{hours,booking,notifications}` endpoints were landed in Plan 02 but are not yet in `packages/api-client/src/schema.d.ts` (Phase 111 regenerates the schema additively). The `staffRequest` call sites for these three paths use `'get' as never` / `'put' as never` / `'/api/v1/settings/...' as never` casts until Phase 111. This is per `D-V31-CONTRACT-ADDITIVE` decision in STATE.md.

## Known Stubs

None — this is a data-layer plan (hooks + schemas). No UI rendering.

## Threat Flags

None — no new network endpoints or auth paths introduced. The hooks consume endpoints already landed and threat-modeled in Plan 02.

## Self-Check: PASSED

Files modified:
- apps/admin-app/src/features/settings/schemas.ts: FOUND
- apps/admin-app/src/features/settings/api.ts: FOUND
- apps/admin-app/src/shared/session/can.test.ts: FOUND

Commits:
- 8ffa46e0 (Task 1): FOUND
- a14e8a78 (Task 2): FOUND

Verification:
- typecheck: PASSED (0 errors)
- lint: PASSED (0 warnings)
- tests: PASSED (340/340, 26 test files)
- 8 hooks exported with correct can() gates
- Reception zero-calls discipline enforced (enabled: can(...))
- No package installs
