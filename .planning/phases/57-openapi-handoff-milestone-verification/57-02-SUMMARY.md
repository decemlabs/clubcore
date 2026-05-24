---
phase: 57-openapi-handoff-milestone-verification
plan: "02"
subsystem: backend-tests
tags: [reports, dst, timezone, msk, integration-tests, ver-02]
dependency_graph:
  requires: []
  provides: [VER-02-dst-golden-test]
  affects: [57-03-runbook]
tech_stack:
  added: []
  patterns: [savepoint-per-test, deterministic-utc-to-msk-timestamps, net-of-refund-arithmetic]
key_files:
  created:
    - apps/backend/tests/integration/reports/test_reports_dst.py
  modified: []
decisions:
  - "DST golden test written as a new file test_reports_dst.py (sibling to existing test_reports_revenue.py + test_reports_visits.py) rather than merging into those files, per D-141 (Claude's discretion) — keeps the named-constant module block clean and the VER-02 gap closure clearly isolated"
  - "Counter-anchor payment placed on the SAME MSK day as GOLDEN_DATE_MSK_NEXT (07:00 UTC = 10:00 MSK on 2026-01-02) to prove two-date window is non-trivial rather than spanning two distinct MSK days — simplifies assertion arithmetic while still validating bucketing correctness"
  - "Net-of-refund golden test uses a 2-day window (GOLDEN_DATE_MSK_NEXT only) to isolate only the boundary events — prevents ambient DB state from affecting the deterministic NET_KOPECKS assertion"
metrics:
  duration_minutes: 4
  completed_date: "2026-05-24"
  tasks_completed: 2
  files_created: 1
  files_modified: 0
---

# Phase 57 Plan 02: DST/MSK-Offset Golden Tests Summary

**One-liner:** DST midnight-boundary golden tests proving 21:30Z revenue/visits bucket to next MSK calendar day, with named kopeck constants for 57-03 runbook cross-reference (VER-02 closed).

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | DST/MSK-offset golden test for revenue + visits midnight bucketing | 4b67698 | apps/backend/tests/integration/reports/test_reports_dst.py (created, 299 lines) |
| 2 | Verify existing RBAC-403 + pagination-stability coverage satisfies VER-02 SC#3/SC#4 | (no code change — verification only) | — |

## What Was Built

### Task 1: test_reports_dst.py

Three integration tests covering the VER-02 correctness gap (D-07 / ROADMAP SC#3):

**`test_dst_revenue_boundary_payment_buckets_to_next_msk_day`**
- Inserts a payment at `datetime(2026, 1, 1, 21, 30, tzinfo=UTC)` (= 00:30 MSK on 2026-01-02)
- Inserts a partial refund at the same boundary timestamp
- Inserts a counter-anchor payment at `datetime(2026, 1, 2, 7, 0, tzinfo=UTC)` (= 10:00 MSK on 2026-01-02)
- Asserts `period == "2026-01-02"` bucket exists with `netKopecks == NET_KOPECKS + 10_000`
- Asserts NO `period == "2026-01-01"` bucket (boundary event must NOT appear on UTC date)

**`test_dst_revenue_net_of_refund_golden_amount`**
- Isolated membership — only boundary sale + partial refund in window
- Queries fromDate=toDate=GOLDEN_DATE_MSK_NEXT to pin deterministic NET_KOPECKS
- Asserts `netKopecks == 200_000` (GROSS 250k − REFUND 50k)
- This is the canonical golden number for 57-03 runbook eyeball-match

**`test_dst_visits_boundary_visit_buckets_to_next_msk_day`**
- Inserts a boundary visit at 21:30Z → asserts `daily[].date == "2026-01-02"` (not "2026-01-01")
- Inserts counter-anchor visit at 07:00Z on 2026-01-02 → both land on same MSK day, count=2
- `gym_date` is STORED GENERATED — never passed explicitly (only `checked_in_at` with tzinfo=UTC)

### Named constants at module top (for 57-03 runbook)

```python
GOLDEN_DATE_UTC_PREV = "2026-01-01"   # UTC calendar date of boundary event
GOLDEN_DATE_MSK_NEXT = "2026-01-02"   # MSK calendar date (next day, +03:00)
GROSS_KOPECKS: int = 250_000           # Gross sale (2 500,00 RUB)
REFUND_KOPECKS: int = 50_000           # Partial refund (500,00 RUB)
NET_KOPECKS: int = 200_000             # GROSS − REFUND deterministic golden amount
ANCHOR_DATE_MSK = "2026-01-02"         # Counter-anchor MSK date
```

### Task 2: Existing coverage verified (no code added)

Ran `uv run pytest tests/integration/reports/ -q -k "reception or pagination_stability or forbidden"` — **9 passed**.

Confirmed already covered (D-06 extend-don't-duplicate):
- `test_reports_revenue.py:43` — `test_reception_forbidden` → 403 + `code == "forbidden"` on revenue
- `test_audit_log.py:47` — `test_reception_forbidden` → 403 + `code == "forbidden"` on audit-log
- `test_audit_log.py:304` — `test_pagination_stability_under_concurrent_insert` → keyset stability
- `test_reports_visits.py:46` — `test_reception_forbidden_visits` → 403 on visits
- CSV reception-403 tests in `test_csv_export.py` (4 paths)

Full suite: **68 passed, 0 failed**.

## Verification Results

```
cd apps/backend && uv run pytest tests/integration/reports/test_reports_dst.py -x -q
→ 3 passed in 0.78s ✓

cd apps/backend && uv run pytest tests/integration/reports/ -q -k "reception or pagination_stability or forbidden"
→ 9 passed ✓

cd apps/backend && uv run pytest tests/integration/reports/ -q
→ 68 passed in 13.23s ✓
```

## Deviations from Plan

None — plan executed exactly as written.

- Task 1: new test file created with all 3 named tests. Named constants pinned at module top. No new factories added to conftest.py (git diff on conftest.py empty, confirmed).
- Task 2: verification-only. Existing RBAC-403 and pagination-stability tests confirmed present and passing. No code change.

## Known Stubs

None. All tests assert live API responses with real database data via SAVEPOINT-per-test fixtures.

## Threat Flags

No new network endpoints, auth paths, or schema changes introduced. This plan only creates integration tests. No threat flags.

## Self-Check: PASSED

- [x] `apps/backend/tests/integration/reports/test_reports_dst.py` exists (299 lines)
- [x] Commit 4b67698 exists in git log
- [x] 3 DST tests pass
- [x] 68 full reports suite tests pass
- [x] conftest.py diff empty (no new factories)
- [x] Named constants GOLDEN_DATE_UTC_PREV/GOLDEN_DATE_MSK_NEXT/GROSS_KOPECKS/REFUND_KOPECKS/NET_KOPECKS at module top
