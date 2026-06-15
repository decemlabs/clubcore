---
phase: "110"
plan: "03"
subsystem: backend-payroll-verification
tags: [payroll, integration-test, rbac, ver-02, p102-deferral-close]
dependency_graph:
  requires: ["110-01"]
  provides: [VER-02]
  affects: [payroll-lifecycle, rbac-verification]
tech_stack:
  added: []
  patterns: [httpx-asgi-transport, pytest-asyncio-auto, payroll-conftest-factories, csrf-helper, seed-pt-data]
key_files:
  created:
    - apps/backend/tests/integration/payroll/test_p102_payroll_lifecycle.py
  modified: []
decisions:
  - "Reused _csrf and _seed_pt_data helpers (copied from test_payroll_accruals.py) rather than importing — avoids cross-module test coupling; pattern matches all sibling payroll tests"
  - "Task 1 and Task 2 written in the same file (both target the same artifact per plan), committed as a single atomic commit after both verifications passed"
  - "revenueKopecks asserted in the accrual snapshot (field exists in the response envelope alongside accrualKopecks)"
metrics:
  duration_minutes: 3
  completed_date: "2026-06-14"
  tasks_completed: 2
  tasks_total: 2
  files_created: 1
  files_modified: 0
---

# Phase 110 Plan 03: Payroll Lifecycle E2E Verification Summary

End-to-end payroll lifecycle test (comp-config PUT → preview GET → accrual POST → mark-paid POST) with golden-math snapshot assertions and reception-403 RBAC negative on real seeded Postgres via httpx ASGITransport.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Payroll lifecycle E2E — comp-config → preview → run → mark-paid + snapshot assertions | 96300367 | apps/backend/tests/integration/payroll/test_p102_payroll_lifecycle.py |
| 2 | Payroll RBAC negative E2E — reception 403 on owner-only payroll endpoints | 96300367 | apps/backend/tests/integration/payroll/test_p102_payroll_lifecycle.py |

## What Was Built

Created `apps/backend/tests/integration/payroll/test_p102_payroll_lifecycle.py` (326 lines, 2 tests) closing the P102 `data-setup-blocked` payroll deferral:

**test_payroll_lifecycle_e2e (owner)**
Drives the full VER-02 lifecycle through HTTP:
1. PUT `/api/v1/payroll/trainer-configs/{trainer_id}` (commission_pct_bps=1000, session_fee_kopecks=50000, effective_from=2026-01-01) → 200, config_id captured
2. GET `/api/v1/payroll/preview?trainerId=...&periodStart=2026-04-01&periodEnd=2026-04-30` → 200, golden math: sessionCount=2, commissionKopecks=10000, fixedKopecks=100000, totalKopecks=110000
3. POST `/api/v1/payroll/accruals` → 201, status='pending', snapshot fields asserted (commissionPctBpsSnapshot=1000, sessionFeeKopecksSnapshot=50000, compConfigIdSnapshot=<config_id>, sessionsCount=2, accrualKopecks=110000, revenueKopecks=100000), paidAt/paidByUserId null
4. POST `/api/v1/payroll/accruals/{id}/mark-paid` → 200, status='paid', paidAt+paidByUserId set
5. Second mark-paid → 409, code='already_paid' (terminal transition verified)

**test_payroll_rbac_reception_forbidden_on_all_endpoints**
Asserts reception receives 403 (code='forbidden') on all four owner-only payroll endpoints:
- PUT `/api/v1/payroll/trainer-configs/{trainer_id}` → 403
- GET `/api/v1/payroll/preview` → 403
- POST `/api/v1/payroll/accruals` → 403
- POST `/api/v1/payroll/accruals/{random_uuid}/mark-paid` → 403 (RBAC fires before resource resolution)

## Verification Results

```
uv run ruff check tests/integration/payroll/test_p102_payroll_lifecycle.py
# → All checks passed!

uv run mypy --strict tests/integration/payroll/test_p102_payroll_lifecycle.py
# → Success: no issues found in 1 source file

uv run pytest tests/integration/payroll/test_p102_payroll_lifecycle.py -v
# → 2 passed in 0.78s
```

## Golden Math Verified

| Input | Value |
|-------|-------|
| revenue (sale_amount_kopecks) | 100,000 kopecks |
| commission_pct_bps | 1000 (10%) |
| sessions_count | 2 |
| session_fee_kopecks | 50,000 |
| commission = ceil(100000 × 1000 / 10000) | 10,000 kopecks |
| fixed = 50000 × 2 | 100,000 kopecks |
| total | 110,000 kopecks |

## Deviations from Plan

None — plan executed exactly as written.

The only minor addition beyond the plan spec: `revenueKopecks` was also asserted in the accrual snapshot (the field exists in the response envelope and is part of the snapshot record; asserting it makes the test more complete without expanding scope).

## VER-02 Deferral Closure

This plan closes the P102 `data-setup-blocked` payroll deferral from the v3.0 milestone close. The payroll router was confirmed mounted at `router.py:61` (prefix `/payroll`); the only blocker was the test prerequisite data (trainer + comp-config + completed pt-sessions + pt_package Payment for revenue). This plan provides repeatable self-contained test data via the `_seed_pt_data` helper and the `make_trainer` conftest factory.

## Threat Surface Scan

No new network endpoints, auth paths, file access patterns, or schema changes introduced — this plan adds only a test file exercising existing endpoints.

## Self-Check: PASSED

- FOUND: apps/backend/tests/integration/payroll/test_p102_payroll_lifecycle.py
- FOUND: commit 96300367
