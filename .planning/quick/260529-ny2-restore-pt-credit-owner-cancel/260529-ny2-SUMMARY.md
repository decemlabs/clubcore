---
status: complete
phase: 999.1
plan: 01
subsystem: backend/schedule + backend/core
tags: [pt-sessions, schedule, audit, wr-06, credit-restore, idempotency]
dependency_graph:
  requires:
    - apps/backend/app/modules/schedule/service.py (cancel_slot, create_time_off)
    - apps/backend/app/core/audit.py (LOCKED_AUDIT_EVENTS)
    - apps/backend/app/core/audit_payloads.py (AUDIT_PAYLOAD_SCHEMAS)
  provides:
    - pt_session_credit_restored audit event + payload (registered, locked)
    - _restore_pt_credit_for_cancelled_booking helper (consumption-keyed, idempotent)
    - Credit restore wired into both owner-cancel cascades (cancel_slot, create_time_off)
  affects:
    - apps/backend/app/modules/schedule/service.py (two cascade paths extended)
    - apps/backend/tests/integration/schedule/test_time_off.py
    - apps/backend/tests/integration/schedule/test_slot_cancel_cascade.py
tech_stack:
  added:
    - PtSessionCreditRestoredPayload (Pydantic model, audit_payloads.py)
  patterns:
    - Raw sa.text() cross-module writes (D-38-11) — no static ORM import
    - Consumption-keyed restore with RETURNING idempotency gate (cancelled_at IS NULL)
    - LITERAL event/resource_type strings throughout (INFRA-11 AST gate)
key_files:
  created: []
  modified:
    - apps/backend/app/core/audit.py
    - apps/backend/app/core/audit_payloads.py
    - apps/backend/app/modules/schedule/service.py
    - apps/backend/tests/integration/schedule/test_time_off.py
    - apps/backend/tests/integration/schedule/test_slot_cancel_cascade.py
decisions:
  - D-999.1-01: Consumption-keyed restore (Option B) — restore +1 ONLY when a live
    pt_sessions row exists for the booking (booking_id=:bid AND cancelled_at IS NULL).
    Confirmed by owner 2026-05-29; blind +1 REJECTED (over-credit / CHECK breach).
  - D-999.1-02: No static ORM import — all cross-module writes are raw sa.text() per
    D-38-11; modules-independent import-linter contract preserved.
  - D-999.1-03: resource_type for pt_session_credit_restored is "pt_package" (the row
    being mutated), mirroring the pt_package_* event family.
metrics:
  duration: ~30min
  completed_date: "2026-05-29T14:33:00Z"
  tasks_completed: 3
  files_modified: 5
---

# Phase 999.1 Plan 01: PT-session credit restore on owner-cancel Summary

One-liner: Consumption-keyed PT-session credit restore on owner-initiated cancellation using idempotent raw-SQL helper wired into both cancel_slot and create_time_off force cascades, with pt_session_credit_restored audit event.

## What Was Built

Closes WR-06: when an owner force-cancels a confirmed PT booking that had already consumed a prepaid session (`pt_sessions` row with `booking_id=:bid AND cancelled_at IS NULL`), the client's `pt_packages.sessions_remaining` is restored by exactly 1 in the same atomic commit as the booking cancellation. A `pt_session_credit_restored` audit row with before/after balance is written atomically. For a confirmed booking with no consumed session, the restore is a correct no-op (nothing was deducted, nothing to give back).

### Task 1 — Register audit event + payload

- Added `("pt_session_credit_restored", "pt_package")` to `LOCKED_AUDIT_EVENTS` in `audit.py` immediately after the `pt_session_cancelled` pair (WR-06 Phase 999.1 comment tag).
- Added `PtSessionCreditRestoredPayload` to `audit_payloads.py` with `extra="forbid"` and 6 locked fields: `client_id`, `pt_package_id`, `booking_id`, `cancel_reason`, `sessions_remaining_before`, `sessions_remaining_after`.
- Registered in `AUDIT_PAYLOAD_SCHEMAS` near the PT-session cluster.

### Task 2 — Credit-restore helper + wire into both cascades

Added `_restore_pt_credit_for_cancelled_booking(session, actor, *, booking_id, cancel_reason)` in `schedule/service.py` using raw `sa.text()` per D-38-11:

1. SELECT the live consumed session with FOR UPDATE (no row → return immediately, no-op).
2. UPDATE pt_sessions SET cancelled_at=now() WHERE id=:psid AND cancelled_at IS NULL RETURNING id (0 rows = concurrent restore won → no-op, idempotent).
3. SELECT sessions_remaining FOR UPDATE (before value), then UPDATE pt_packages SET sessions_remaining+1 WHERE sessions_remaining < session_count_snapshot RETURNING (ceiling guard, raises InternalConsistencyError on breach).
4. audit.emit("pt_session_credit_restored", ...) with LITERAL strings (INFRA-11).

Wired into:
- `cancel_slot` booked-cascade: step 7.5 after `booking_cancelled` emit, before `session.commit()`.
- `create_time_off` force-cascade: step 3g inside the per-slot loop after `booking_cancelled` emit, inside the single end-of-function commit (SVC001).

Removed NOTE WR-06 limitation block (lines ~1049-1057 of original service.py).

### Task 3 — Regression tests

**test_time_off.py** (2 new tests):
- `test_force_cascade_restores_pt_credit_when_session_consumed` — booking with consumed pt_session: after force-cancel, `sessions_remaining == session_count`, exactly 1 `pt_session_credit_restored` audit row with all 6 payload keys, pt_session is cancelled.
- `test_force_cascade_no_op_when_no_pt_session_consumed` — booking with no session: `sessions_remaining` unchanged, 0 restore audit rows.

**test_slot_cancel_cascade.py** (3 new tests):
- `test_cancel_booked_slot_restores_pt_credit_when_session_consumed` — cancel_slot path mirrors time_off restore test.
- `test_cancel_booked_slot_no_op_when_no_pt_session_consumed` — cancel_slot path mirrors no-op test.
- `test_cancel_slot_no_double_restore_on_retry` — after first cancel (1 restore event), direct second helper call returns immediately (pt_session already cancelled), no second increment, audit count stays at 1.

## CI Results

- ruff check app: PASSED (0 errors; existing TABLE_REF noqa warnings unchanged)
- ruff format --check app: PASSED (210 files already formatted)
- mypy --strict app: PASSED (0 issues in 210 files)
- import-linter (modules-independent): PASSED (3 contracts kept, 0 broken)
- pytest tests/integration/schedule/test_time_off.py test_slot_cancel_cascade.py: PASSED (19/19)

## Deviations from Plan

**1. [Rule 1 - Bug] Async stub required for DM dispatch monkeypatch**
- **Found during:** Task 3 test execution
- **Issue:** Test stubs for `_dispatch_booking_lifecycle_notification` used sync `lambda *a, **kw: None`; the service `await`s the dispatch, so a sync lambda causes `TypeError: object NoneType can't be used in 'await' expression`.
- **Fix:** Replaced lambdas with `async def _noop_dm(*a, **kw): pass` stubs in all 3 new tests (plus idempotency test).
- **Files modified:** test_time_off.py, test_slot_cancel_cascade.py

**2. [Rule 1 - Bug] Identity-map cache in idempotency test needed explicit refresh**
- **Found during:** Task 3, test_cancel_slot_no_double_restore_on_retry
- **Issue:** After `create_booking` (which commits via SAVEPOINT), the `slot` ORM object remained in the SQLAlchemy identity map with `status='active'`. Without `db_session.refresh(slot)`, `cancel_slot` appeared to see the slot as active (no cascade triggered, `had_booking=False`).
- **Fix:** Added `await db_session.refresh(slot, attribute_names=["status"])` + assert after `create_booking` in the idempotency test, mirroring the pattern in all existing cascade tests.
- **Files modified:** test_slot_cancel_cascade.py

None of the deviations affect the implementation logic — both were test-layer fixes.

## Threat Surface Scan

No new network endpoints, auth paths, or schema changes introduced. All mutations are internal to the existing owner-cancel UoW (cross-module raw SQL per the existing D-38-11 pattern). Threat mitigations T-999.1-01 through T-999.1-04 are implemented as planned.

## Known Stubs

None — all 6 payload fields are wired to real runtime values; no placeholder text or empty defaults.

## Self-Check: PASSED

- apps/backend/app/core/audit.py modified: FOUND
- apps/backend/app/core/audit_payloads.py modified: FOUND
- apps/backend/app/modules/schedule/service.py modified: FOUND
- apps/backend/tests/integration/schedule/test_time_off.py modified: FOUND
- apps/backend/tests/integration/schedule/test_slot_cancel_cascade.py modified: FOUND
- Commit 058caad4 (Task 1): FOUND
- Commit d6d3f93a (Task 2): FOUND
- Commit e59ec464 (Task 3): FOUND
