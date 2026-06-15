---
phase: 115-live-advanced-analytics
plan: "04"
subsystem: frontend-dashboard
tags: [dashboard, activity-feed, audit-log, tdd, real-data-wiring]
dependency_graph:
  requires:
    - "115-01 (audit-log + reports backend endpoints already exist)"
  provides:
    - "ANL-04: real ActivityFeed render in DashboardPage"
    - "audit→ActivityFeed pure mapper + unit tests"
    - "useActivityFeed owner-gated hook"
  affects:
    - apps/admin-app/src/features/dashboard/
    - apps/admin-app/src/pages/dashboard/DashboardPage.tsx
tech_stack:
  added: []
  patterns:
    - "TDD RED/GREEN/REFACTOR for pure mapper function"
    - "Owner-gated TanStack Query hook with enabled:can(role,'view','audit-log')"
    - "Action-prefix switch with 'alert' fallback (never-throw pattern T-115-D2)"
    - "Skeleton→ActivityFeed→EmptyState render triptych per UI-SPEC"
key_files:
  created:
    - apps/admin-app/src/features/dashboard/audit-activity.ts
    - apps/admin-app/src/features/dashboard/audit-activity.test.ts
  modified:
    - apps/admin-app/src/features/dashboard/api.ts
    - apps/admin-app/src/pages/dashboard/DashboardPage.tsx
decisions:
  - "Import boundary: features/dashboard → features/audit is permitted by ESLint config (only pages/layouts/components → api/client.ts is blocked); useActivityFeed lives in features/dashboard/api.ts (not inlined in DashboardPage)"
  - "ACTION_TYPE_MAP removed in favor of direct switch in mapSingleEvent — cleaner, no unused-var suppression needed under noUnusedLocals:true"
  - "Null actorEmailSnapshot falls back to event.resourceType as subLead; no client names invented (T-115-D3)"
metrics:
  duration: "~15 minutes"
  completed: "2026-06-15"
  tasks_completed: 2
  files_changed: 4
---

# Phase 115 Plan 04: Dashboard Real-Data ActivityFeed Summary

Satisfies ANL-04: wires the dashboard activity feed to real `GET /api/v1/audit-log` data, replacing the EmptyState+Link stub. TopTrainers and RevenueChart were already wired to real hooks; confirmed no mock imports feed any of the three widgets.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| TDD RED | Failing tests for mapAuditToActivityFeed | 85600d8c | audit-activity.test.ts |
| TDD GREEN | audit-activity.ts + useActivityFeed hook | a17ecdf5 | audit-activity.ts, api.ts |
| Task 2 | Wire real ActivityFeed in DashboardPage | 658d041e | DashboardPage.tsx |

## Action → ActivityType Mapping Implemented

| Audit action | ActivityType | Title pattern |
|---|---|---|
| `visit.*` (starts with "visit") | `checkin` | `{name} · чек-ин` |
| `payment.*` (starts with "payment") | `payment` | `{name} · оплата` |
| `booking.confirmed` | `training` | `{name} · запись подтверждена` |
| `booking.cancelled` | `cancel` | `{name} · отмена записи` |
| `membership.expired` | `expire` | `{name} · абонемент истёк` |
| `client.registered` | `signup` | `{name} · новый клиент` |
| any other / unrecognized | `alert` | raw action string (never throws) |

Display name resolution priority: `payload.clientName` → `payload.name` → actor email local-part → `"Событие"`.

## Import Boundary Outcome

`features/dashboard → features/audit` is **allowed** — ESLint's `import/no-restricted-paths` only blocks `pages/layouts/components → api/client.ts`. Therefore `useActivityFeed` lives in `features/dashboard/api.ts` (not inlined in DashboardPage), keeping the hook in the correct domain layer.

## Mock Removal Confirmed

Grep confirms no mock import feeds ActivityFeed, TopTrainers, or RevenueChart:
- No `from '@/mocks/dashboard'` in DashboardPage.tsx
- TopTrainers: already wired to `useTrainersReport` (Phase 104-02)
- RevenueChart: already wired to `useRevenueReport` (Phase 104-02)
- ActivityFeed: now wired to `useActivityFeed` (this plan)

## Deviations from Plan

None — plan executed exactly as written.

## Threat Model Compliance

| Threat | Status |
|--------|--------|
| T-115-D1 (reception must not fetch audit-log) | Mitigated: `enabled: can(role,'view','audit-log')` in useActivityFeed; hook declared inside DashboardOwnerSection (mounts only when isOwner === true — double gate) |
| T-115-D2 (unrecognized audit action crashes dashboard) | Mitigated: switch default branch → type 'alert', uses raw action string as title, never throws |
| T-115-D3 (PII display) | Accepted: shows same data owner sees in full audit-log; no new surface |

## Verification Results

- `pnpm -F @clubcore/admin-app typecheck`: clean
- `pnpm -F @clubcore/admin-app lint` (all modified files): clean
- `pnpm -F @clubcore/admin-app test`: 405/405 passed (30 test files), including:
  - `audit-activity.test.ts`: 15 tests (6 known actions + unknown fallback + empty + timeLabel + actor fallback)
  - `router-smoke.test.tsx`: 20 routes render without error (owner + reception dashboard included)
- `pnpm -F @clubcore/admin-app build`: succeeded

## Known Stubs

None — ActivityFeed, TopTrainers, and RevenueChart all render real backend data with proper loading states.

## Self-Check: PASSED
