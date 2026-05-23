---
phase: 53-milestone-verification
plan: "03"
subsystem: backend-testing
tags: [verification, circuit-breaker, fiscal-receipts, defer-46-03, ver-05]
dependency_graph:
  requires:
    - "51-05 dispatch_fiscal_receipt FISCAL-05 implementation"
    - "51-04 app/integrations/yookassa/circuit_breaker.py D-51-14"
  provides:
    - "VER-05: DEFER-46-03 closed — FISCAL-05 open-state breaker parity confirmed"
  affects: []
tech_stack:
  added: []
  patterns:
    - "real-commit engine + fiscal_redis fixture from conftest.py"
    - "respx.mock(assert_all_called=False) for no-call assertions"
    - "arq_ctx dict from conftest.py arq fixture"
key_files:
  created:
    - apps/backend/tests/integration/fiscal_receipts/test_circuit_breaker_open_state_parity.py
  modified: []
decisions:
  - "D-05 (53-CONTEXT): expressed as integration test (not runner script) — deterministic and CI-runnable per planner N-note"
  - "Two test variants: 5 record_failure() calls (primary) + direct SET (parity variant)"
  - "Seeded fiscal_receipts(status='pending') row — pre-dispatch status confirms short-circuit fires before FSM"
metrics:
  duration: "~8 minutes"
  completed_date: "2026-05-23"
  tasks_completed: 1
  tasks_total: 1
  files_created: 1
  files_modified: 0
---

# Phase 53 Plan 03: VER-05 DEFER-46-03 Circuit-Breaker Open-State Parity Summary

**One-liner:** FISCAL-05 open-state circuit-breaker parity test closes DEFER-46-03: 5 `record_failure()` calls pre-open `sz:yookassa:circuit:receipts`, `dispatch_fiscal_receipt` raises `Retry(defer=300)` short-circuit with zero ЮKassa POSTs, seeded `pending` row unchanged.

## What Was Built

Created `apps/backend/tests/integration/fiscal_receipts/test_circuit_breaker_open_state_parity.py` — two integration tests that close DEFER-46-03 (v1.6 VER-09 scenario-08 PARTIAL) by re-running the open-state fixture against the FISCAL-05 circuit breaker.

### Test 1: `test_fiscal_receipt_dispatch_short_circuits_when_breaker_open_via_5_failures`

Primary parity assertion matching the v1.6 scenario-08 expectation:
1. Pre-opens `sz:yookassa:circuit:receipts` via exactly 5 `record_failure(redis, "receipts")` calls, crossing the D-51-14 locked threshold.
2. Seeds a `fiscal_receipts(status='pending')` row (minimal chain: Payment → FiscalReceipt, no online_payment chain needed).
3. Invokes `dispatch_fiscal_receipt(ctx, receipt_id)`.
4. Asserts `arq.Retry(defer=300)` is raised — the head-of-body `is_circuit_open` guard at tasks.py:276-278 short-circuits.
5. Asserts `respx` route call count == 0 (no ЮKassa `/v3/receipts` POST issued).
6. Asserts the seeded row remains `status='pending'`, `yookassa_receipt_id=None`, `succeeded_at=None`.

### Test 2: `test_fiscal_receipt_dispatch_short_circuits_when_breaker_open_via_direct_set`

Secondary parity variant confirming `is_circuit_open` is EXISTS-based (O(1)):
- Directly SETs the open-marker key via `await fiscal_redis.set("sz:yookassa:circuit:receipts", "1", ex=300)`.
- Same assertions as test 1 — same short-circuit, same no-call, same status-unchanged.
- Mirrors the unit-level assertion in `tests/unit/test_yookassa_circuit_breaker.py::test_is_circuit_open_returns_true_when_marker_set`.

## Deviations from Plan

None — plan executed exactly as written. The `arq_ctx` and `fiscal_redis` fixtures in `conftest.py` already provided the correct setup; no new fixtures were required. Both test variants used in the plan (5 record_failure + direct SET) were implemented as requested.

## Verification Results

```
pytest tests/integration/fiscal_receipts/test_circuit_breaker_open_state_parity.py -x -v
2 passed in 0.78s
```

## Known Stubs

None. This plan creates integration tests only; no application code was written.

## Threat Flags

None. The test harness touches only local test Redis and local Postgres; no new network endpoints or trust boundaries were introduced.

## Self-Check: PASSED

- [x] File created: `apps/backend/tests/integration/fiscal_receipts/test_circuit_breaker_open_state_parity.py`
- [x] Commit exists: `c8cdbf0`
- [x] Tests pass: 2/2
- [x] Module docstring records DEFER-46-03 / v1.6 VER-09 scenario-08 parity lineage
- [x] `sz:yookassa:circuit:receipts` key used (D-51-14 locked)
- [x] `is_circuit_open` guard verified via 5 record_failure() calls (threshold crossing)
- [x] No ЮKassa POST issued under open breaker (respx call_count == 0)
- [x] `fiscal_receipts` row status unchanged (remains 'pending')
