---
phase: 59-recurring-schedule-time-off
plan: "02"
subsystem: backend-schema
tags: [alembic, migration, schema, schedule, recurring-slots, time-off]
dependency_graph:
  requires: ["59-01"]
  provides: ["recurring_slot_templates table", "trainer_time_off table", "trainer_availability_slots ALTER"]
  affects: ["59-03", "59-04", "59-05"]
tech_stack:
  added: []
  patterns: ["Alembic two-tables-one-revision (0041 precedent)", "op.f() named constraints", "op.alter_column nullable", "downgrade guard (0021 precedent)"]
key_files:
  created:
    - apps/backend/alembic/versions/0042_recurring_schedule_time_off.py
  modified:
    - apps/backend/app/modules/schedule/models.py
decisions:
  - "Single combined revision 0042 (0041 two-tables-one-revision precedent)"
  - "Added RecurringSlotTemplate + TrainerTimeOff ORM models in models.py (required for alembic check to be clean — Plan 03 was deferred but alembic check runs against current models)"
  - "Downgrade guard mirrors 0021: refuses to run if NULL created_by_user_id rows exist"
  - "Constraint name tails (not full names) used in model __table_args__ so NAMING_CONVENTION expansion matches migration op.f() output"
metrics:
  duration: "~15 minutes"
  completed: "2026-05-25"
  tasks: 1
  files: 2
---

# Phase 59 Plan 02: Alembic 0042 — Recurring Schedule + Time-Off Schema Summary

Alembic migration 0042 delivering the full Phase 59 DDL substrate in one atomic revision: two new tables (`recurring_slot_templates`, `trainer_time_off`) and a cron-idempotency ALTER on `trainer_availability_slots` (nullable `created_by_user_id` + UNIQUE (trainer_id, start_time)).

## What Was Built

**Migration 0042** (`apps/backend/alembic/versions/0042_recurring_schedule_time_off.py`):

- **`recurring_slot_templates`** — REC-01 recurring availability patterns per trainer. Columns: `id` UUID PK, `trainer_id` FK RESTRICT, `day_of_week SMALLINT`, `start_time TIME`, `end_time TIME`, `valid_from DATE`, `valid_until DATE NULL`, `is_active BOOL DEFAULT true`, `created_at/updated_at TIMESTAMPTZ`. CHECKs: `day_of_week BETWEEN 0 AND 6`, `end_time > start_time`, `valid_until IS NULL OR valid_until >= valid_from`. **UNIQUE (trainer_id, day_of_week, start_time, valid_from)** — REC-01 verbatim idempotency key.

- **`trainer_time_off`** — REC-03 time-off blocks. Columns: `id` UUID PK, `trainer_id` FK RESTRICT, `block_start/block_end TIMESTAMPTZ`, `reason TEXT NULL`, `created_at/updated_at TIMESTAMPTZ`. CHECK: `block_end > block_start`. btree index on `(trainer_id, block_start)` for overlap queries (PITFALL 9 support).

- **ALTER `trainer_availability_slots`**: `created_by_user_id` → NULLABLE (D-59-05/REC-02 — cron-generated slots have no human author). UNIQUE `(trainer_id, start_time)` added (PITFALL 8 — backs `ON CONFLICT DO NOTHING` in cron).

**ORM models** added to `apps/backend/app/modules/schedule/models.py`:
- `RecurringSlotTemplate` + `TrainerTimeOff` model classes with correct `__table_args__` (constraint name tails matching NAMING_CONVENTION expansion)
- `TrainerAvailabilitySlot.created_by_user_id` made `nullable=True` + new UNIQUE index registered

## Verification Results

- `alembic upgrade head` → applied cleanly (0041 → 0042)
- `alembic check` → `No new upgrade operations detected` (clean)
- `alembic downgrade -1` → reversed cleanly (0042 → 0041)
- `alembic upgrade head` → re-applied cleanly
- Single head confirmed at `0042_recurring_schedule_time_off`

## Deviations from Plan

### Auto-added Missing Critical Functionality

**1. [Rule 2 - Missing Critical] Added ORM models for new tables (RecurringSlotTemplate, TrainerTimeOff)**
- **Found during:** Running `alembic check` after upgrade
- **Issue:** The plan stated ORM models would be added in Plan 03, but `alembic check` immediately flagged the two new DB tables as "detected removed table" (wanting to drop them) because they had no ORM registration. This made `alembic check` fail — violating the plan's primary success criterion.
- **Fix:** Added `RecurringSlotTemplate` and `TrainerTimeOff` as proper ORM models in `schedule/models.py`. Also added the slot UNIQUE index to the existing `TrainerAvailabilitySlot.__table_args__` and made `created_by_user_id` nullable in the model.
- **Files modified:** `apps/backend/app/modules/schedule/models.py`
- **Commit:** 3d309432

## Known Stubs

None. This plan delivers pure DDL — no service logic, no endpoints, no data paths.

## Threat Flags

| Flag | File | Description |
|------|------|-------------|
| threat_flag: schema_extension | `apps/backend/alembic/versions/0042_recurring_schedule_time_off.py` | ALTER on `trainer_availability_slots.created_by_user_id` relaxes a NOT NULL on a production table used by booking FK; existing rows retain their UUID value; only future cron rows will carry NULL — covered by T-59-03 in plan threat model |

## Self-Check: PASSED

- FOUND: `apps/backend/alembic/versions/0042_recurring_schedule_time_off.py`
- FOUND: `apps/backend/app/modules/schedule/models.py` (modified)
- FOUND: commit `3d309432`
- FOUND: `59-02-SUMMARY.md`
