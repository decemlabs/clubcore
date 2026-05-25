---
phase: 59-recurring-schedule-time-off
plan: "03"
subsystem: schedule
tags: [orm-models, pydantic-dtos, audit-payloads, nullable-author, recurring-slots, time-off]
dependency_graph:
  requires: ["59-02"]
  provides: ["59-04", "59-05"]
  affects: ["schedule.models", "schedule.schemas", "schedule.service", "core.audit_payloads"]
tech_stack:
  added: []
  patterns:
    - "UUID | None widening on nullable FK columns (mirrors BookingCreatedPayload Phase 40 precedent)"
    - "Pydantic model_validator + field_validator for mirroring DB CHECK constraints at DTO layer"
key_files:
  created: []
  modified:
    - apps/backend/app/modules/schedule/models.py
    - apps/backend/app/modules/schedule/schemas.py
    - apps/backend/app/modules/schedule/service.py
    - apps/backend/app/core/audit_payloads.py
decisions:
  - "SlotCancelledPayload.cancelled_by_user_id intentionally left as UUID (non-nullable) — every slot_cancelled emit goes through cancel_slot(actor: CurrentUser), always a real human actor; no cron or system-actor cancel path exists"
  - "SlotPublishedPayload.created_by_user_id widened to UUID | None = None following exact BookingCreatedPayload Phase 40 D-40-05 precedent"
  - "Task 1 (ORM models) was pre-completed by 59-02 executor (alembic check required models alongside migration 0042); no re-commit needed"
metrics:
  duration: "~20 minutes"
  completed: "2026-05-25T14:09:25Z"
  tasks_completed: 2
  files_changed: 3
---

# Phase 59 Plan 03: ORM Models + DTOs + Nullable Author Summary

One-liner: Added recurring-template and time-off Pydantic DTOs with CHECK-mirroring validators, widened nullable author through SlotResponse + SlotPublishedPayload + service audit emit, closing the cron-author crash gate (T-59-09).

## Tasks Completed

| Task | Name | Status | Commit |
|------|------|--------|--------|
| 1 | Add RecurringSlotTemplate + TrainerTimeOff ORM models | Pre-completed by 59-02 wave | 76f9131c (upstream) |
| 2 | Widen nullable author + add recurring/time-off DTOs | Complete | c2edca56 |

## What Was Built

### Task 1 — ORM Models (pre-completed by 59-02 executor)

The 59-02 executor added `RecurringSlotTemplate` and `TrainerTimeOff` ORM model classes to `apps/backend/app/modules/schedule/models.py`, along with the `TrainerAvailabilitySlot.created_by_user_id` nullable widening, because `alembic check` requires model metadata to match DDL before the migration can be verified. These are byte-identical to the 0042 migration — same constraint name tails (`ck_recurring_slot_templates_day_of_week`, `ck_recurring_slot_templates_end_after_start`, `ck_recurring_slot_templates_valid_window`, `ck_trainer_time_off_block_end_after_start`) and same index names (`uq_recurring_slot_templates_trainer_id`, `ix_trainer_time_off_trainer_id`, `uq_trainer_availability_slots_trainer_id_start_time`).

Verification: `python -c "from app.modules.schedule.models import RecurringSlotTemplate, TrainerTimeOff; print(RecurringSlotTemplate.__tablename__, TrainerTimeOff.__tablename__)"` → `recurring_slot_templates trainer_time_off`. `mypy app/modules/schedule/models.py` → Success.

### Task 2 — Nullable Author Widening + New DTOs (commit c2edca56)

**`apps/backend/app/modules/schedule/schemas.py`:**

- `SlotResponse.created_by_user_id` widened from `UUID` to `UUID | None` — cron-generated recurring slots carry no human author (D-59-05 / 0042 nullable ALTER). The docstring is updated to explain the None path.
- Added `RecurringSlotTemplateCreate` (BackendSchemaBase input) with:
  - `day_of_week: int = Field(ge=0, le=6)` — mirrors `ck_recurring_slot_templates_day_of_week`
  - `model_validator` enforcing `end_time > start_time` — mirrors `ck_recurring_slot_templates_end_after_start`
  - `model_validator` enforcing `valid_until >= valid_from` when set — mirrors `ck_recurring_slot_templates_valid_window`
- Added `RecurringSlotTemplateResponse` (ResponseData) with all template fields
- Added `TimeOffCreate` (BackendSchemaBase input) with:
  - `field_validator` requiring timezone-aware `block_start` / `block_end`
  - `model_validator` enforcing `block_end > block_start` — mirrors `ck_trainer_time_off_block_end_after_start`
- Added `TimeOffResponse` (ResponseData) with all time-off fields
- Added `TimeOffConflictDetail` (ResponseData) — 409 body for the REC-03 booked-slot guard: `conflicting_slot_ids: list[UUID]`, `conflicting_booking_ids: list[UUID]`

**`apps/backend/app/core/audit_payloads.py`:**

- `SlotPublishedPayload.created_by_user_id` widened from `UUID` to `UUID | None = None` (T-59-09 blocker fix). Mirrors the exact pattern of `BookingCreatedPayload.created_by_user_id: UUID | None = None` (Phase 40 D-40-05). `model_config = ConfigDict(extra="forbid")` and `AUDIT_PAYLOAD_SCHEMAS` registration unchanged — additive model-body widening only.

**`apps/backend/app/modules/schedule/service.py`:**

- `publish_slot` audit emit now uses a conditional `str(slot.created_by_user_id) if slot.created_by_user_id is not None else None` guard so the widened `SlotPublishedPayload` receives `None` (not the string `"None"`) when a cron-generated slot has no author.

## Deviations from Plan

### Pre-completion by 59-02 executor

**[Rule 2 — Pre-existing]** Task 1 (ORM models) was completed by the 59-02 wave executor as a required deviation — `alembic check` during migration verification requires model metadata to be present before the migration can be tested. The models were added as part of the 59-02 commit set and merged at `76f9131c`. This plan's Task 1 therefore required only verification, no additional code.

No other deviations. Plan executed exactly as specified for Task 2.

## SlotCancelledPayload Disposition

**Decision: `SlotCancelledPayload.cancelled_by_user_id` intentionally left as `UUID` (non-nullable).**

Rationale: Every `slot_cancelled` audit emit goes through `cancel_slot(session, actor: CurrentUser, ...)`. The `actor` parameter is always a resolved `CurrentUser` — a real authenticated human operator (owner or reception). There is no cron or system-actor path that emits `slot_cancelled`. The Plan 04 time-off service will also invoke `cancel_slot` within an owner request path (not a background task). Therefore, `cancelled_by_user_id` is always populated with a real UUID and `SlotCancelledPayload` does not need widening. This is in contrast with `SlotPublishedPayload`, which will be emitted by the Plan 05 ARQ cron (a system process without a human actor).

## Verification Results

| Check | Result |
|-------|--------|
| `mypy app/modules/schedule/models.py` | Success (0 issues) |
| `mypy app/modules/schedule/schemas.py` | Success (0 issues) |
| `mypy app/modules/schedule/service.py` | Success (0 issues) |
| `mypy app/core/audit_payloads.py` | Success (0 issues) |
| `ruff check schemas.py + service.py` | All checks passed |
| `ruff check audit_payloads.py` | 1 pre-existing E501 at L549 (out-of-scope, pre-dates this plan) |
| `lint-imports` | 3 kept, 0 broken (same as pre-plan) |
| `SlotPublishedPayload.model_validate({..., created_by_user_id: None})` | null-author OK (no ValidationError) |
| `SlotResponse(created_by_user_id=None, ...)` | OK (field is UUID | None) |
| Pydantic validators: day_of_week 7 rejected | OK |
| Pydantic validators: end_time <= start_time rejected | OK |
| Pydantic validators: valid_until < valid_from rejected | OK |
| Pydantic validators: block_end == block_start rejected | OK |
| 902 unit tests | All passed |
| Integration tests | Require Docker Compose (no running DB in worktree) — infrastructure limitation, not code regression |

## Known Stubs

None. All new DTOs are fully defined and wired for Plan 04 (router) + Plan 05 (cron) consumption. No placeholder values.

## Threat Surface Scan

No new network endpoints or auth paths introduced in this plan. DTOs provide the double-gate validation layer (T-59-06, T-59-07, T-59-08, T-59-09) as specified in the threat model. No additional threat flags beyond those already registered in the plan's `<threat_model>`.

## Self-Check: PASSED

Files confirmed present:
- `apps/backend/app/modules/schedule/models.py` — contains `RecurringSlotTemplate` and `TrainerTimeOff`
- `apps/backend/app/modules/schedule/schemas.py` — contains `TimeOff` (TimeOffCreate, TimeOffResponse, TimeOffConflictDetail) and `RecurringSlotTemplateCreate`/`RecurringSlotTemplateResponse`; `SlotResponse.created_by_user_id` is `UUID | None`
- `apps/backend/app/core/audit_payloads.py` — `SlotPublishedPayload.created_by_user_id: UUID | None = None`
- `apps/backend/app/modules/schedule/service.py` — audit emit stringify None-safe

Commits confirmed:
- `76f9131c` — upstream (Task 1 pre-completion, models.py)
- `c2edca56` — Task 2 (schemas.py + audit_payloads.py + service.py)
