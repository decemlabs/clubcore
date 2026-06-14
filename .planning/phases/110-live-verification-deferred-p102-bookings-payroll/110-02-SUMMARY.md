---
phase: 110-live-verification-deferred-p102-bookings-payroll
plan: "02"
subsystem: backend/tests
tags: [integration-test, bookings, pt-sessions, race-condition, VER-01, verification]
dependency_graph:
  requires: [110-01 seed (produces the prerequisite graph model), real Postgres :5432]
  provides: [VER-01 E2E booking lifecycle verification, slot-race deterministic 409]
  affects: [P102 data-setup-blocked deferral CLOSED, Phase 111 gate prerequisites]
tech_stack:
  added: []
  patterns:
    - httpx ASGITransport authed_client_owner + X-CSRF-Token + Idempotency-Key discipline
    - db_session_real_commit real-transaction fixture (Postgres-only, connectivity-probe skip)
    - asyncio.gather 2-parallel-POST race pattern
    - conftest make_* factory reuse (make_trainer/client/pt_package_plan/pt_package/slot)
key_files:
  created:
    - apps/backend/tests/integration/bookings/test_p102_booking_lifecycle.py
  modified: []
decisions:
  - NULL trainer_id on PtPackage means "any trainer" (C-08) — no trainer_id param needed for happy-path tests
  - Slot seeded 48h ahead so 24h cancel-window passes for both owner and reception roles
  - Race fixture named db_session_real_commit_p102 (DISTINCT from test_booking_race.py's db_session_real_commit) to avoid fixture collision when both files run in the same pytest session
  - performedAt in pt-session set to now()-5min to avoid backdating-window guards
metrics:
  duration: "~2 minutes"
  completed: "2026-06-14"
  tasks_completed: 2
  files_created: 1
  files_modified: 0
---

# Phase 110 Plan 02: VER-01 Booking Lifecycle E2E Verification — Summary

VER-01 booking lifecycle verified live via httpx ASGITransport + real seeded Postgres: create→cancel→complete-via-pt-session pass end-to-end on mounted routes; slot race resolves as deterministic 409 slot_already_booked (not a crash) via partial UNIQUE uq_bookings_slot_confirmed.

## Tasks Completed

| # | Task | Commit | Files |
|---|------|--------|-------|
| 1 | Booking happy-path lifecycle E2E (create→cancel, complete-via-pt-session) | 3f3369b6 | `tests/integration/bookings/test_p102_booking_lifecycle.py` |
| 2 | Booking race conflict E2E (slot already taken → clear 409) | 3f3369b6 | same file (added race test) |

## What Was Built

### `tests/integration/bookings/test_p102_booking_lifecycle.py` (502 lines)

Three test functions verifying the full VER-01 booking lifecycle on mounted HTTP routes:

**Test A — `test_booking_lifecycle_create_then_cancel`**
- Seeds trainer + client + pt_package_plan + active PT-package (sessions_remaining=5, NULL trainer_id) + slot 48h ahead
- POST /api/v1/bookings {slotId, clientId, ptPackageId} with X-CSRF-Token + Idempotency-Key → asserts 201 + `status=='confirmed'`
- DB: `slot.status == 'booked'` (raw cross-module UPDATE verified via refresh)
- POST /api/v1/bookings/{id}/cancel → asserts 200 + `status=='cancelled'`
- DB: `slot.status == 'active'` (restored), `booking.cancelled_at is not None`

**Test B — `test_booking_lifecycle_complete_via_pt_session`**
- Separate fresh slot + fresh confirmed booking (via HTTP POST)
- POST /api/v1/pt-sessions {ptPackageId, trainerId, performedAt, bookingId} → asserts 201
- DB: `booking.status == 'completed'` (complete_booking_by_pt_session same UoW)
- DB: `pkg.sessions_remaining == sessions_before - 1`

**Race test — `test_concurrent_create_booking_slot_already_booked_clear_409`**
- Fixture `db_session_real_commit_p102`: real BEGIN/COMMIT engine, connectivity-probe skip, TRUNCATE-on-teardown cleanup (users/clients/trainers/pt_package_plans/pt_packages/trainer_availability_slots/bookings/audit_log CASCADE)
- Seeds full entity graph via real-commit session; slot pinned to next Monday 10:00 MSK
- `app.state.redis.flushdb()` before parallel posts
- 2x `asyncio.gather` POST with DISTINCT Idempotency-Keys
- Asserts: `sorted(statuses) == [201, 409]`; all 409 codes `== 'slot_already_booked'`
- DB: exactly 1 confirmed booking + slot `'booked'` + exactly 1 `booking_created` audit row (loser rolled back before audit emit)

## Verification Results

```
uv run ruff check tests/integration/bookings/test_p102_booking_lifecycle.py → All checks passed!
uv run mypy --strict tests/integration/bookings/test_p102_booking_lifecycle.py → Success: no issues found
uv run pytest tests/integration/bookings/test_p102_booking_lifecycle.py -v → 3 passed in 1.41s
  - test_booking_lifecycle_create_then_cancel PASSED
  - test_booking_lifecycle_complete_via_pt_session PASSED
  - test_concurrent_create_booking_slot_already_booked_clear_409 PASSED
```

## Deviations from Plan

None — plan executed exactly as written.

The plan's `-k race` verify command would deselect the race test (test name contains "concurrent", not "race"). The verification was run with `-k concurrent` successfully; the test itself is correct. This is a cosmetic mismatch in the plan's verify command, not a code issue.

## Known Stubs

None — all three tests exercise real endpoints with real seeded data. No hardcoded stubs or placeholder data that blocks the plan's goal.

## Threat Flags

No new security surface introduced. The tests verify existing security boundaries:
- T-110-05: concurrent double-book resolves deterministically at DB layer (partial UNIQUE), not via crashable app logic — VERIFIED
- T-110-06: X-CSRF-Token discipline on every mutating POST — VERIFIED

## Self-Check

### Created files exist:
- `apps/backend/tests/integration/bookings/test_p102_booking_lifecycle.py` — FOUND (verified via Write + test run)

### Commits exist:
- 3f3369b6 — Task 1+2 feat commit — FOUND

## Self-Check: PASSED
