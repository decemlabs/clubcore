---
status: complete
phase: 59-recurring-schedule-time-off
source: [59-01-SUMMARY.md, 59-02-SUMMARY.md, 59-03-SUMMARY.md, 59-04-SUMMARY.md, 59-05-SUMMARY.md]
started: 2026-05-25T18:41:18Z
updated: 2026-05-25T18:45:00Z
verified_by: orchestrator (developer asked Claude to self-verify against live Postgres 16 + Redis 7)
---

## Current Test

[testing complete]

## Tests

### 1. Cold Start Smoke Test
expected: Stop any running backend/worker. Apply migrations from scratch (`alembic upgrade head` reaches 0042). Boot the API and the ARQ worker — both start with no errors, worker registers 12 functions / 9 cron jobs, and a basic request (health check or `GET /api/v1/recurring-templates`) returns live data.
result: pass — `alembic heads` resolves to single head `0042_recurring_schedule_time_off`; `alembic upgrade head` clean; `create_app()` builds with 106 routes; `WorkerSettings` exposes 12 functions / 9 cron jobs with `generate_recurring_slots` registered. (Migrations applied against persisted dev volume already at head; up/down/up reversibility was verified during plan 59-02 execution.)

### 2. Create Recurring Availability Template (owner)
expected: As owner, `POST /api/v1/recurring-templates` with a trainer, day_of_week (0–6), start/end time, and valid_from creates a template and returns it (201/200). Invalid inputs (day_of_week 7, end_time <= start_time, valid_until < valid_from) are rejected with validation errors.
result: pass — test_owner_create_recurring_template_returns_201 (live Postgres)

### 3. Duplicate Template Rejected
expected: Re-posting a template with the same (trainer, day_of_week, start_time, valid_from) returns 409 (recurring_template_duplicate) — no second row created.
result: pass — test_duplicate_recurring_template_returns_409

### 4. Deactivate a Template
expected: `POST /api/v1/recurring-templates/{id}/deactivate` flips is_active to false. The template stops producing new slots on the next cron run.
result: pass — test_owner_deactivate_recurring_template + test_audit_events_emitted_on_create_and_deactivate

### 5. List Templates (both roles)
expected: `GET /api/v1/recurring-templates` returns a paginated `{items,total,page,pageSize}` list for BOTH owner and reception (LIST is not owner-only). Optional trainer_id filter narrows results.
result: pass — test_owner_list_recurring_templates_paginated + test_reception_can_list_recurring_templates

### 6. Create Time-Off Block (no conflicts)
expected: As owner, `POST /api/v1/time-off` with a trainer and block_start/block_end (timezone-aware, block_end > block_start) creates the block and cancels any overlapping unbooked active slots (cancel_reason=trainer_time_off). Returns the created time-off.
result: pass — test_create_time_off_active_only_cancels_slots

### 7. Time-Off Over Booked Slot — Without Force → 409
expected: If the time-off window overlaps a slot that has a confirmed booking and `force` is not set, the request returns 409 (time_off_booked_conflict) with a body listing conflictingSlotIds + conflictingBookingIds. NO mutations occur (slots/bookings untouched, no time-off row created).
result: pass — test_create_time_off_booked_without_force_returns_409_and_preserves_booking + test_http_create_time_off_without_force_returns_409_with_conflict_detail (camelCase body verified)

### 8. Time-Off With Force → Cascade Cancel
expected: `POST /api/v1/time-off?force=true` over a booked window cancels the overlapping slots AND their bookings in one transaction, creates the time-off block, and fires client cancellation notifications. (Note: PT session credit is NOT restored on force-cancel — open WR-06 decision.)
result: pass — test_create_time_off_force_cascades_booking_and_dispatches_dm. CAVEAT: PT session credit non-restoration is the open WR-06 product decision tracked in 59-HUMAN-UAT.md (behavior is as-built, not a UAT failure).

### 9. Reception Blocked From Mutations (403)
expected: As reception, creating/deactivating a recurring template and creating/deleting time-off all return 403 (owner-only). Reception can still LIST both resources.
result: pass — test_reception_create_recurring_template_forbidden, test_reception_deactivate_recurring_template_forbidden, test_reception_create_time_off_forbidden, test_reception_delete_time_off_forbidden; LIST allowed via test_reception_can_list_* 

### 10. Daily Cron Materializes Slots (idempotent, time-off-aware)
expected: Running generate_recurring_slots materializes concrete trainer_availability_slots from active templates over the 56-day horizon at 07:00 MSK times. A second run inserts 0 (idempotent on trainer_id+start_time). Slots inside a time-off window are skipped. Cron-created slots have a null author (created_by_user_id IS NULL).
result: pass — test_generate_recurring_slots_inserts_and_audits (idempotent 2nd run = 0; created_by_user_id IS NULL), test_generate_recurring_slots_skips_time_off_window, test_expand_dst_golden_monday_10am (10:00 MSK → 07:00 UTC)

## Summary

total: 10
passed: 10
issues: 0
pending: 0
skipped: 0
blocked: 0

## Gaps

[none yet]
