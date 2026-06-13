---
phase: 104-dashboard-reports-settings
plan: "01"
subsystem: admin-app/api + features/reports + features/audit
tags: [reports, audit, csv, tdd, api-layer]
dependency_graph:
  requires: []
  provides:
    - downloadCsv(endpoint, filename, query) — blob-download helper
    - useClientsReport + useTrainersReport — owner-gated hooks
    - ClientsReportSchema + TrainersReportSchema — Zod schemas
    - reportsQueryKeys.clients + reportsQueryKeys.trainers — key factories
    - useAuditLog(filter, role) — owner-gated paginated hook
    - AuditEventSchema + AuditLogResponseSchema + AuditFilter — Zod schemas
    - auditKeys factory
  affects:
    - apps/admin-app/src/api/client.ts (export widened)
    - apps/admin-app/src/features/reports/* (extended)
    - apps/admin-app/src/features/audit/* (rewritten)
    - apps/admin-app/src/pages/audit/AuditPage.tsx (stub updated)
tech_stack:
  added: []
  patterns:
    - staffRequest + Schema.parse(raw).data
    - owner-gated enabled:can(role, 'view', resource)
    - TDD RED/GREEN per task (schemas + key factory)
    - blob-download via anchor + URL.revokeObjectURL
key_files:
  created:
    - apps/admin-app/src/api/csv.ts
    - apps/admin-app/src/features/audit/schemas.ts
    - apps/admin-app/src/features/reports/schemas.test.ts
    - apps/admin-app/src/features/audit/schemas.test.ts
  modified:
    - apps/admin-app/src/api/client.ts
    - apps/admin-app/src/features/reports/schemas.ts
    - apps/admin-app/src/features/reports/keys.ts
    - apps/admin-app/src/features/reports/api.ts
    - apps/admin-app/src/features/audit/api.ts
    - apps/admin-app/src/pages/audit/AuditPage.tsx
decisions:
  - "D-104-01-CSVLAYER: csv.ts lives in api/ layer (not features/) to allow same-layer import of appendQuery/parseErrorBody from client.ts without ESLint boundary violation"
  - "D-104-01-EXPORT-APPEND: appendQuery + parseErrorBody exported from client.ts by adding export keyword only — no signature/body changes"
  - "D-104-01-AUDITPAGE-STUB: AuditPage.tsx updated minimally to compile with 2-arg useAuditLog; renders EmptyState stub; Wave 2 (104-02) will wire full data rendering"
metrics:
  duration: "~6 minutes"
  completed: "2026-06-13"
  tasks: 3
  files_created: 4
  files_modified: 6
---

# Phase 104 Plan 01: Foundation (downloadCsv + reports + audit domain layer) Summary

**One-liner:** Blob-download CSV helper + owner-gated clients/trainers report hooks + real paginated audit-log hook with nullable JSONB payload schema.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | downloadCsv helper + export client.ts internals | d0022f34 | api/client.ts, api/csv.ts |
| 2 RED | Failing tests for ClientsReportSchema + TrainersReportSchema | 124d0e00 | reports/schemas.test.ts |
| 2 GREEN | Extend features/reports with useClientsReport + useTrainersReport | 27afc134 | reports/schemas.ts, reports/keys.ts, reports/api.ts |
| 3 RED | Failing tests for AuditEventSchema + AuditLogResponseSchema | 883c841c | audit/schemas.test.ts |
| 3 GREEN | Audit domain layer — schemas + real useAuditLog | 3832a1bd | audit/schemas.ts, audit/api.ts, pages/audit/AuditPage.tsx |

## Verification

Full admin-app gate result:
- `typecheck`: PASS
- `lint`: PASS
- `test`: PASS (329/329 tests, 25 test files)
- `build`: PASS (2.65s, no errors)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] AuditPage.tsx typecheck failure after api.ts rewrite**

- **Found during:** Task 3 typecheck gate
- **Issue:** Rewriting `audit/api.ts` to remove the mock branch changed `useAuditLog()` signature from 0 args to `(filter: AuditFilter, role: Role)`. `AuditPage.tsx` called the 0-arg version and accessed `data.groups` (mock-era shape) — TypeScript reported 5 errors.
- **Fix:** Updated `AuditPage.tsx` minimally: added `useSession()` to get the role, passes `({}, role)` to `useAuditLog`, replaced `data.groups` rendering with an `EmptyState` stub. All void-suppressed unused state vars preserved for Wave 2 to wire. Legacy `AuditEvent` from `types.ts` still imported for `AuditDetailModal` compatibility.
- **Files modified:** `apps/admin-app/src/pages/audit/AuditPage.tsx`
- **Commit:** 3832a1bd

## Known Stubs

| Stub | File | Reason |
|------|------|--------|
| AuditPage renders EmptyState instead of real audit items | `pages/audit/AuditPage.tsx` | Wave 2 (104-02) will wire full data.items rendering, filters, pagination, CSV export, RBAC Lock-EmptyState for reception |

This stub is intentional — Wave 2 (plan 104-02) will flip the AuditPage to full wiring.

## Threat Flags

No new threat surface beyond what the plan's threat model covers (T-104-01, T-104-02, T-104-03).

## TDD Gate Compliance

- Task 2: RED commit 124d0e00 → GREEN commit 27afc134 ✓
- Task 3: RED commit 883c841c → GREEN commit 3832a1bd ✓

## Self-Check: PASSED

All created files exist on disk. All task commits verified in git log.
