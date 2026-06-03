---
phase: 80-booking-reschedule
plan: "01"
subsystem: backend
tags: [migration, audit, notifications, schemas, booking-reschedule]
dependency_graph:
  requires: [phase-79]
  provides: [migration-0053, booking-rescheduled-audit-event, reschedule-dm-template, reschedule-request-schema]
  affects: [booking_notifications, audit_log, client_portal]
tech_stack:
  added: []
  patterns: [alembic-check-widen, audit-payload-registration, owner-copy-lock-dm, backendschemabase-forbid]
key_files:
  created:
    - apps/backend/alembic/versions/0053_booking_notifications_widen_kind.py
    - apps/backend/tests/integration/test_alembic_0053_booking_notif_rescheduled.py
  modified:
    - apps/backend/app/core/audit.py
    - apps/backend/app/core/audit_payloads.py
    - apps/backend/app/modules/bookings/notifications.py
    - apps/backend/app/modules/client_portal/schemas.py
    - apps/backend/tests/unit/test_booking_notifications_copy.py
decisions:
  - ClientRescheduleBookingRequest uses BackendSchemaBase (extra=forbid) not ResponseData (extra=ignore); ResponseData.extra is 'ignore' — the docstring comment in ClientCreateBookingRequest claiming 'extra=forbid' is incorrect, but the reschedule schema is correctly strict
metrics:
  duration_minutes: 7
  completed_date: "2026-06-03"
  tasks_completed: 3
  tasks_total: 3
  files_created: 2
  files_modified: 5
---

# Phase 80 Plan 01: Reschedule Foundation Summary

Migration 0053 widens the booking_notifications.kind CHECK to admit 'rescheduled', registers the booking_rescheduled audit event with a typed forensic payload, adds the locked Russian reschedule DM template with OWNER-COPY-LOCK annotation, and provides the ClientRescheduleBookingRequest schema with extra='forbid' for IDOR safety.

## Tasks Completed

| # | Task | Commit | Files |
|---|------|--------|-------|
| 1 | Migration 0053 — widen booking_notifications.kind CHECK for 'rescheduled' | ce018434 | 0053_booking_notifications_widen_kind.py, test_alembic_0053_booking_notif_rescheduled.py |
| 2 | Register booking_rescheduled audit event + typed payload | e9636de4 | audit.py, audit_payloads.py |
| 3 | Reschedule DM template + reschedule request schema | 8a4ef7f7 | notifications.py, schemas.py, test_booking_notifications_copy.py |

## Verification Results

- `uv run alembic upgrade head`: 0053_booking_notif_widen_kind_rescheduled at head
- `uv run alembic current`: 0053_booking_notif_widen_kind_rescheduled (head)
- `uv run pytest tests/integration/test_alembic_0053_booking_notif_rescheduled.py tests/unit/test_booking_notifications_copy.py -q`: 12 passed
- `uv run mypy --strict app`: Success: no issues found in 229 source files
- `uv run ruff check` on modified files: All checks passed
- `uv run lint-imports`: Contracts: 3 kept, 0 broken

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] ClientRescheduleBookingRequest uses BackendSchemaBase not ResponseData**
- **Found during:** Task 3
- **Issue:** The plan specifies `class ClientRescheduleBookingRequest(ResponseData)` with `extra='forbid'`. However, `ResponseData` inherits from `ContractModel` which has `extra="ignore"` — not `extra="forbid"`. The existing `ClientCreateBookingRequest` uses `ResponseData` but its docstring claim of `extra='forbid'` is factually incorrect (extra fields are silently ignored). The T-80-03 acceptance criterion "extra `client_id` rejected" would fail with `ResponseData`.
- **Fix:** Used `BackendSchemaBase` (which has `extra="forbid"`) instead of `ResponseData`. This is the correct base for inbound request body schemas per the codebase design. `BackendSchemaBase` is already imported in `schemas.py`.
- **Files modified:** apps/backend/app/modules/client_portal/schemas.py
- **Commit:** 8a4ef7f7

### Seeding Fix in Integration Test

**2. [Rule 1 - Bug] bookings table requires pt_package_id (NOT NULL)**
- **Found during:** Task 1 (integration test)
- **Issue:** Initial test seeding omitted `pt_package_id` from bookings INSERT, causing `NotNullViolationError`. Also `pt_package_plans.active` column doesn't exist (it uses soft-delete via `deleted_at`).
- **Fix:** Added `pt_package_plans` and `pt_packages` rows to the seeding chain; corrected the INSERT column list for `pt_package_plans`.
- **Files modified:** apps/backend/tests/integration/test_alembic_0053_booking_notif_rescheduled.py
- **Commit:** ce018434

## Known Stubs

None — all functionality is fully implemented. No placeholder data, no TODO stubs.

## Threat Flags

No new threat surface introduced beyond what the plan's threat model covers.

## Self-Check: PASSED

Files verified to exist:
- apps/backend/alembic/versions/0053_booking_notifications_widen_kind.py: FOUND
- apps/backend/tests/integration/test_alembic_0053_booking_notif_rescheduled.py: FOUND

Commits verified to exist:
- ce018434: FOUND
- e9636de4: FOUND
- 8a4ef7f7: FOUND
