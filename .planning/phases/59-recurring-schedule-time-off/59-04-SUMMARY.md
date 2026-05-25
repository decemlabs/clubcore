---
phase: 59-recurring-schedule-time-off
plan: "04"
subsystem: schedule
tags: [recurring-templates, time-off, rbac, cascade, audit, importlib]
dependency_graph:
  requires: ["59-01", "59-03"]
  provides: [recurring-template-crud, time-off-crud, time-off-conflict-409, force-cascade, active-slot-cancel]
  affects: [schedule-module, bookings-module-via-raw-sql]
tech_stack:
  added: []
  patterns:
    - REC-01 recurring slot template CRUD (create/deactivate/list)
    - REC-03 time-off 409-without-force gate + force-cascade + DM via importlib
    - REC-04 both-role list endpoints (LIST SCHEDULE_SLOTS not in OWNER_ONLY)
    - D-38-11 cross-module raw sa.text() UPDATE on bookings (TABLE_REF noqa)
    - PATTERNS.md §5 importlib DM indirection (grimp-opaque)
    - SVC001 caller-owns-txn for all mutating orchestrators
key_files:
  created:
    - apps/backend/tests/integration/schedule/test_recurring_templates.py
    - apps/backend/tests/integration/schedule/test_time_off.py
  modified:
    - apps/backend/app/modules/schedule/repository.py
    - apps/backend/app/modules/schedule/service.py
    - apps/backend/app/modules/schedule/router.py
    - apps/backend/app/api/v1/router.py
decisions:
  - "Flat paths /recurring-templates + /time-off registered as separate routers in api/v1/router.py (schedule_router at /trainer-slots already fixed its prefix); trainer_id in body for creates, query param for lists — mirrors existing SlotCreateRequest pattern"
  - "TimeOffBookedConflictError carries conflicting_slot_ids + conflicting_booking_ids in exc.fields as string lists; router extracts + converts to UUID via typing.cast"
  - "Task 2 service implementation happened in Task 1 GREEN phase (both tasks share the same service file); Task 2 tests written after and confirmed all pass — minor TDD sequencing deviation"
metrics:
  duration_seconds: 599
  completed_date: "2026-05-25"
  tasks_completed: 2
  files_changed: 6
---

# Phase 59 Plan 04: Recurring Templates + Time-Off Endpoints Summary

JWT-style recurring slot template CRUD and trainer time-off block management with 409/force-cascade/DM semantics, zero new import-linter edges.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 RED | Failing recurring template tests | 6e327f0d | test_recurring_templates.py |
| 1 GREEN | Recurring template CRUD (REC-01, REC-04) | 1be4f160 | repository.py, service.py, router.py, api/v1/router.py |
| 2 RED | Failing time-off tests | fe6186e9 | test_time_off.py |
| 2 GREEN | Time-off router fix (by_alias camelCase) | 99cfc263 | router.py |

## What Was Built

### Recurring Slot Template CRUD (REC-01, REC-04)

**Repository (`schedule/repository.py`):**
- `insert_recurring_template`: INSERT with IntegrityError detection on UNIQUE (trainer_id, day_of_week, start_time, valid_from) — returns None on violation, caller raises ConflictError
- `get_recurring_template_by_id_for_update`: row-locked SELECT for deactivate FSM
- `list_recurring_templates`: paginated SELECT with optional trainer_id filter
- `insert_time_off`, `get_time_off_by_id`, `list_time_off`: analogous helpers for TrainerTimeOff

**Service (`schedule/service.py`):**
- `create_recurring_template`: UNIQUE-gate → 409 recurring_template_duplicate; emit `recurring_slot_template_created` (LITERAL); SVC001 commit
- `deactivate_recurring_template`: is_active=False flip; emit `recurring_slot_template_cancelled` (LITERAL); SVC001 commit
- `list_recurring_templates`: passthrough read-only

**Router (`schedule/router.py` + `api/v1/router.py`):**
- `POST /api/v1/recurring-templates` — (CREATE, SCHEDULE_SLOTS) owner-only + Idempotency-Key
- `POST /api/v1/recurring-templates/{id}/deactivate` — (CANCEL, SCHEDULE_SLOTS) owner-only + Idempotency-Key
- `GET /api/v1/recurring-templates` — (LIST, SCHEDULE_SLOTS) both roles
- Registered as `recurring_templates_router` in `api/v1/router.py`

### Time-Off Block Management (REC-03, REC-04)

**Service (`schedule/service.py`) — `create_time_off(session, actor, data, *, force=False)`:**

1. tstzrange '&&' overlap query against trainer_availability_slots → splits into booked vs active lists
2. If booked overlaps AND NOT force: raise `TimeOffBookedConflictError` (409, error_code=`time_off_booked_conflict`) with `conflicting_slot_ids` + `conflicting_booking_ids` in `exc.fields`; NO mutations
3. If force: for each booked slot — raw `sa.text()` UPDATE on `bookings` table (`# noqa: TABLE_REF D-38-11`), 0-row → InternalConsistencyError; slot.status='cancelled' + cancel_reason='trainer_time_off'; emit `slot_cancelled` (had_booking=True, LITERAL) + `booking_cancelled` (LITERAL) per booking
4. Active overlaps: slot.status='cancelled' + cancel_reason='trainer_time_off'; emit `slot_cancelled` (had_booking=False, LITERAL) per slot
5. INSERT TrainerTimeOff via repository; flush; emit `trainer_time_off_created` (resource_type="trainer", LITERAL)
6. Single `session.commit()` covering ALL mutations + audits (SVC001 gate)
7. AFTER commit: importlib.import_module("app.modules.bookings.service") indirection for DM fan-out via `_dispatch_booking_lifecycle_notification(kind="cancelled_by_owner", ...)` — grimp-opaque, fire-and-forget

**Service — `delete_time_off`:** DELETE → emit `trainer_time_off_cancelled` (LITERAL) → commit (forward-only)

**Router:**
- `POST /api/v1/time-off?force=False` — (CREATE, SCHEDULE_SLOTS) owner-only + Idempotency-Key; maps TimeOffBookedConflictError to 409 JSONResponse with camelCase conflict detail
- `DELETE /api/v1/time-off/{id}` — (DELETE, SCHEDULE_SLOTS) owner-only + Idempotency-Key
- `GET /api/v1/time-off` — (LIST, SCHEDULE_SLOTS) both roles

## Verification Results

- `test_recurring_templates.py`: 8/8 passed
- `test_time_off.py`: 8/8 passed
- All 46 schedule integration tests pass
- All 902 unit tests pass
- Route introspection test passes (RBAC-04 ordering verified)
- `uv run mypy app/modules/schedule/{repository,service,router}.py`: Success, no issues
- `uv run lint-imports`: 3 kept, 0 broken — zero new ignore edges

## Security (Threat Model)

| Threat | Mitigation | Verified |
|--------|-----------|---------|
| T-59-09: Elevation (force cascade) | require_permission(CREATE, SCHEDULE_SLOTS) is OWNER_ONLY; reception 403 on both force and non-force | test_reception_create_time_off_forbidden asserts both |
| T-59-10: Silent data loss (booked cancel) | 409-without-force is mandatory safety gate; only explicit force triggers cascade; every cascade emits booking_cancelled audit + DM | test_create_time_off_booked_without_force + test_http_*_409_with_conflict_detail |
| T-59-11: IDOR cross-trainer | Overlap query scoped WHERE trainer_id=:tid; FK RESTRICT ensures trainer exists | covered by tstzrange query scope |
| T-59-12: Tampering overlap | Single-UoW commit; InternalConsistencyError on 0-row RETURNING rolls back entire transaction | inherited from cancel_slot cascade pattern |

## Deviations from Plan

### Minor Sequencing: Task 2 Service in Task 1 GREEN

**Found during:** Task 1 implementation
**Issue:** The service.py changes for `create_time_off`, `delete_time_off`, and `list_time_off` were implemented in the Task 1 GREEN commit alongside the Task 1 scope, since both tasks modify the same `service.py` file. Task 2 tests were then written and confirmed all pass.
**Impact:** None — all required behaviors are implemented and tested. Task 2 GREEN commit captured the `by_alias=True` fix needed for the 409 camelCase response.
**Classification:** [Rule 1 - Deviation] Minor TDD sequencing — implementation preceded test writing for Task 2 scope

### Auto-fixed: camelCase in 409 Response Body

**Found during:** Task 2 test run
**Issue:** `TimeOffConflictDetail.model_dump(mode="json")` returned snake_case keys (`conflicting_slot_ids`) but the test expected camelCase (`conflictingSlotIds`) since `ResponseData` uses `alias_generator`.
**Fix:** Added `by_alias=True` to the `model_dump()` call in the conflict exception handler in `router.py`.
**Commit:** 99cfc263

## Known Stubs

None — all service functions are fully wired with real repository queries, audit emits, and DB mutations.

## Self-Check: PASSED

- `apps/backend/app/modules/schedule/service.py`: FOUND (contains create_time_off, create_recurring_template)
- `apps/backend/app/modules/schedule/router.py`: FOUND (contains time_off_router, recurring_templates_router)
- `apps/backend/tests/integration/schedule/test_recurring_templates.py`: FOUND
- `apps/backend/tests/integration/schedule/test_time_off.py`: FOUND
- Commit 6e327f0d (RED recurring templates): FOUND
- Commit 1be4f160 (GREEN recurring CRUD): FOUND
- Commit fe6186e9 (RED time-off): FOUND
- Commit 99cfc263 (GREEN time-off fix): FOUND
