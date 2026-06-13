---
phase: 104-dashboard-reports-settings
plan: "03"
subsystem: admin-app/pages/reports + admin-app/pages/audit + admin-app/layouts/nav
tags: [reports, audit, csv, rbac, owner-only, pagination, xss-guard]
dependency_graph:
  requires:
    - 104-01 (downloadCsv, useClientsReport, useTrainersReport, useAuditLog — domain layer)
  provides:
    - ReportsPage.tsx — 4-tab real-data reports + per-tab CSV export
    - AuditPage.tsx — real audit log + server filters + keyset pagination + CSV
    - AuditDetailModal.tsx — payload rendered as escaped JSON (T-104-07)
    - nav-items.ts — «Журнал действий» owner-only nav entry
  affects:
    - apps/admin-app/src/pages/reports/ReportsPage.tsx (full rewrite)
    - apps/admin-app/src/pages/audit/AuditPage.tsx (full rewrite)
    - apps/admin-app/src/pages/audit/components/AuditDetailModal.tsx (rewritten)
    - apps/admin-app/src/pages/audit/components/parts.tsx (extended with RealAuditRow)
    - apps/admin-app/src/layouts/AppLayout/nav-items.ts (nav entry added)
tech_stack:
  added: []
  patterns:
    - owner RBAC Lock-EmptyState early-return before any hook (T-104-06)
    - downloadCsv idle/downloading/error button states
    - 4-tab layout (TabsGroup) + shared DateRangePicker
    - server-side filter + keyset pagination (page+pageSize=25)
    - JSON.stringify into <pre> for JSONB payload (never innerHTML, T-104-07)
key_files:
  created: []
  modified:
    - apps/admin-app/src/pages/reports/ReportsPage.tsx
    - apps/admin-app/src/pages/audit/AuditPage.tsx
    - apps/admin-app/src/pages/audit/components/AuditDetailModal.tsx
    - apps/admin-app/src/pages/audit/components/parts.tsx
    - apps/admin-app/src/layouts/AppLayout/nav-items.ts
decisions:
  - "D-104-03-TABSGROUP: Inline TabsGroup component (not imported from FinancePage parts) — avoids cross-page import and keeps Reports self-contained"
  - "D-104-03-VISITS-REUSE: VisitsTab reuses LoadHeatmapCard directly (same data shape) — no new component needed"
  - "D-104-03-CLIENTS-INLINE-KPI: ClientsTab uses inline KpiCard instead of existing KpiTile — clients data (3 scalars) doesn't match KpiTile's icon+delta contract"
  - "D-104-03-PARTS-COMPAT: Legacy AuditRow kept in parts.tsx (no usages but preserved for type safety); new RealAuditRow added for real API shape"
  - "D-104-03-MODAL-REWRITE: AuditDetailModal rewritten to use real AuditEvent from schemas.ts; old diff/ip/actor fields removed"
  - "D-104-03-ACTIVITY-ICON-REUSE: «Журнал действий» nav entry reuses already-imported Activity icon (consistent with Посещаемость)"
metrics:
  duration: "~25 minutes"
  completed: "2026-06-13"
  tasks: 3
  files_created: 0
  files_modified: 5
---

# Phase 104 Plan 03: Reports + Audit Pages + Nav Summary

**One-liner:** Owner-only 4-tab Reports page with per-report CSV export, wired Audit page with server-side filters/keyset pagination/CSV + XSS-safe payload render, and «Журнал действий» nav entry.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Reports page — 4 real-data tabs + per-tab CSV export | 664ae22d | pages/reports/ReportsPage.tsx |
| 2 | Audit page wiring — filters, keyset pagination, CSV, safe payload | 756864aa | pages/audit/AuditPage.tsx, components/AuditDetailModal.tsx, components/parts.tsx |
| 3 | Add «Журнал действий» owner-only nav entry + fix import types | 09921175 | layouts/AppLayout/nav-items.ts, ReportsPage.tsx (lint fix) |

## Verification

Full admin-app gate result:
- `typecheck`: PASS
- `lint`: PASS (0 errors, 0 warnings after fixing inline import() types in task 3)
- `test`: PASS (337/337 tests, 26 test files)
- `build`: PASS (2.55s, no errors)

Verified checks:
- `downloadCsv` present in ReportsPage.tsx ✓
- `reports/(revenue|clients|visits|trainers)\.csv` patterns present ✓
- `useClientsReport` + `useTrainersReport` imported ✓
- `useReports(` mock removed ✓
- `useAuditLog` wired in AuditPage.tsx ✓
- `audit-log.csv` endpoint referenced ✓
- `can(role, 'view', 'audit-log')` gate present ✓
- No `dangerouslySetInnerHTML` in AuditDetailModal.tsx ✓ (T-104-07 guard)
- `Журнал действий` nav entry present ✓
- `ownerResource: 'audit-log'` present ✓

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Lint] Inline import() type annotations in ReportsPage.tsx**
- **Found during:** Task 3 lint gate
- **Issue:** Three inline `import('@/features/reports/schemas').TypeName` annotations in function parameter types caused `@typescript-eslint/consistent-type-imports` lint warnings.
- **Fix:** Moved `RevenueBucket`, `VisitsReportDailyBucket`, `VisitsReportHourlyBucket` to the top-level named import block.
- **Files modified:** `apps/admin-app/src/pages/reports/ReportsPage.tsx`
- **Commit:** 09921175

**2. [Rule 2 - XSS guard] AuditDetailModal comment contained the banned word**
- **Found during:** Task 2 verify check
- **Issue:** JSDoc comment `NEVER dangerouslySetInnerHTML` caused `! grep -q "dangerouslySetInnerHTML"` verify check to fail (word appeared in comment text).
- **Fix:** Rephrased comment to `Never uses innerHTML (XSS guard T-104-07)` — preserves the security intent without tripping the grep check.
- **Files modified:** `apps/admin-app/src/pages/audit/components/AuditDetailModal.tsx`
- **Commit:** 756864aa

### Design Decisions

**TabsGroup inline component:** The 4-tab layout uses an inline `TabsGroup` component rather than importing from `FinancePage`'s `FinanceTabs` — the finance tabs have a `badge` prop and different import path that would create a cross-page dependency. The inline implementation is identical in visual output.

**ClientsTab KpiCard:** The clients report (3 scalars: activeCount/expiringCount/newClientsCount) doesn't fit the existing `KpiTile` contract (which requires icon + delta objects). An inline `KpiCard` component provides the same visual result without forcing artificial deltas.

**Legacy AuditRow preserved:** The old mock-era `AuditRow` component in `parts.tsx` is preserved for type compatibility (it imports from `features/audit/types.ts` which still exists). It's not called by any production code but avoids breaking changes if other components exist in the future.

## Known Stubs

None — all plan goals achieved. The payload `(нет данных)` text when `payload === null` is correct behavior (not a stub) per the schema definition.

## Threat Flags

T-104-06 mitigated: Reception Lock-EmptyState early-return fires before any hook call in both ReportsPage and AuditPage. Both hooks also have `enabled: can(role, 'view', resource)` as a double guard.

T-104-07 mitigated: `AuditDetailModal` renders `event.payload` exclusively via `JSON.stringify(event.payload, null, 2)` into a `<pre>` text node. No `innerHTML`, `dangerouslySetInnerHTML`, or DOM injection of any kind. Grep-verified in task 2 automated check.

T-104-08 mitigated: `downloadCsv` uses `credentials: 'include'` (cookie auth), no token/secret in URL, GET method is CSRF-exempt. Owner-only endpoints — reception cannot trigger (gated at page level and hook level).

## Self-Check: PASSED

All modified files verified:
- `apps/admin-app/src/pages/reports/ReportsPage.tsx` — exists, 4 tabs wired
- `apps/admin-app/src/pages/audit/AuditPage.tsx` — exists, full wiring
- `apps/admin-app/src/pages/audit/components/AuditDetailModal.tsx` — exists, payload as JSON.stringify
- `apps/admin-app/src/pages/audit/components/parts.tsx` — exists, RealAuditRow added
- `apps/admin-app/src/layouts/AppLayout/nav-items.ts` — exists, «Журнал действий» entry present

Commits verified in git log:
- 664ae22d feat(104-03): reports page ✓
- 756864aa feat(104-03): audit page wiring ✓
- 09921175 feat(104-03): nav entry + lint fix ✓
