---
phase: 59-recurring-schedule-time-off
plan: "01"
subsystem: backend-infra
tags: [audit, config, constants, infra-15, locked-events, phase-59]
dependency_graph:
  requires: [58-payroll-foundations-ledger]
  provides: [4 new LOCKED_AUDIT_EVENTS for Phase 59 callsites, recurring_slot_horizon_days config, TIME_OFF_CANCEL_REASON constant]
  affects: [app/core/audit.py, app/core/config.py, app/modules/schedule/constants.py, tests/unit/test_audit_taxonomy.py]
tech_stack:
  added: []
  patterns: [INFRA-15 pre-registration discipline, frozenset taxonomy gate, pydantic-settings env field]
key_files:
  created: []
  modified:
    - apps/backend/app/core/audit.py
    - apps/backend/app/core/config.py
    - apps/backend/app/modules/schedule/constants.py
    - apps/backend/tests/unit/test_audit_taxonomy.py
decisions:
  - "4 new LOCKED_AUDIT_EVENTS pre-registered before any callsite per INFRA-15 / D-59-09 (frozenset grows 89 → 93)"
  - "recurring_slot_horizon_days: int = 56 added to Settings — raw env var RECURRING_SLOT_HORIZON_DAYS"
  - "TIME_OFF_CANCEL_REASON = 'trainer_time_off' and TIME_OFF_BOOKED_CONFLICT_CODE = 'time_off_booked_conflict' added to schedule/constants.py"
metrics:
  duration: ~4 minutes
  completed: "2026-05-25T13:53:54Z"
  tasks_completed: 2
  files_modified: 4
---

# Phase 59 Plan 01: INFRA-15 Bedrock Pre-registration Summary

**One-liner:** Pre-register 4 recurring/time-off audit events in LOCKED_AUDIT_EVENTS frozenset (89→93) + add RECURRING_SLOT_HORIZON_DAYS=56 config field + TIME_OFF_CANCEL_REASON/TIME_OFF_BOOKED_CONFLICT_CODE schedule constants before any Wave 2-4 callsite.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Pre-register 4 new LOCKED_AUDIT_EVENTS | `cec7c3cc` | `app/core/audit.py`, `tests/unit/test_audit_taxonomy.py` |
| 2 | Add RECURRING_SLOT_HORIZON_DAYS config field + schedule constants | `1899a696` | `app/core/config.py`, `app/modules/schedule/constants.py` |

## What Was Done

### Task 1: LOCKED_AUDIT_EVENTS pre-registration (INFRA-15 / D-59-09)

Added a new Phase 59 block to the `LOCKED_AUDIT_EVENTS` frozenset in `app/core/audit.py`, exactly mirroring the Phase 58 payroll block style:

```python
# v1.9 (Phase 59 lock — INFRA-15; emitted in Phase 59 service body)
# Recurring-schedule + time-off lifecycle (REC-01..04 / D-59-09):
("recurring_slot_template_created", "schedule_slot"),
("recurring_slot_template_cancelled", "schedule_slot"),
("trainer_time_off_created", "trainer"),
("trainer_time_off_cancelled", "trainer"),
```

No new events added for the active-slot-cancel leg (reuses existing `slot_cancelled`) or the force-cascade booking leg (reuses existing `booking_cancelled`) per D-59-09.

The human-readable doc comment block at the top of `audit.py` was updated with a new `## v1.9 (Phase 59 lock...)` section documenting payload shapes.

The taxonomy count assertion in `tests/unit/test_audit_taxonomy.py` was updated from 89 → 93 with the Phase 59 narrative comment explaining the growth path (85→89 via Phase 58, 89→93 via Phase 59).

All 7 audit taxonomy tests pass.

### Task 2: Config field + schedule constants

**`app/core/config.py`** — added `recurring_slot_horizon_days: int = 56` to the `Settings` class, following the `gym_hours_start` field pattern (env var `RECURRING_SLOT_HORIZON_DAYS`, `extra="ignore"`, no prefix). Comment references D-59-04 / REC-02.

**`app/modules/schedule/constants.py`** — added:
- `TIME_OFF_CANCEL_REASON = "trainer_time_off"` — the cancel_reason literal shared by both the active-slot cancel leg and the force-cascade booking UPDATE (REC-03 / D-59-06)
- `TIME_OFF_BOOKED_CONFLICT_CODE = "time_off_booked_conflict"` — the 409 error_code snake_case string shared between service raise site and test assertions
- Both constants exported in `__all__`

## Verification

- `python -c "from app.core.audit import LOCKED_AUDIT_EVENTS as L; assert ('recurring_slot_template_created','schedule_slot') in L; ..."` → OK 93
- `python -c "from app.core.config import get_settings; assert get_settings().recurring_slot_horizon_days == 56; ..."` → OK
- `uv run pytest tests/unit/test_audit_taxonomy.py -q` → 7 passed
- `uv run mypy app/core/config.py app/modules/schedule/constants.py` → Success: no issues found in 2 source files
- `uv run mypy app/core/audit.py` → Success: no issues found in 1 source file
- `uv run ruff check app/core/config.py app/modules/schedule/constants.py app/core/audit.py` → All checks passed!

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Updated taxonomy test count assertion from 89 to 93**
- **Found during:** Task 1 verification
- **Issue:** `test_locked_audit_events_has_expected_count` hardcodes the expected count (89); adding 4 new events caused it to fail (got 93). The count gate is the exact enforcement mechanism for INFRA-15 — it must be updated atomically with every pre-registration.
- **Fix:** Updated the `assert len(LOCKED_AUDIT_EVENTS) == 89` to `== 93`, updated the format string, and added a Phase 59 narrative comment below the assertion.
- **Files modified:** `apps/backend/tests/unit/test_audit_taxonomy.py`
- **Commit:** `cec7c3cc` (included in Task 1 commit)

## Known Stubs

None — this plan adds only infra-level constants and registrations. No data flow or UI stubs.

## Threat Surface Scan

T-59-01 (Tampering / LOCKED_AUDIT_EVENTS): mitigated — the frozenset + AST gate is itself the control; pre-registration here closes the forward-reference gap.

T-59-02 (DoS / recurring_slot_horizon_days): accepted — value is operator-set env var only; no untrusted-user path touches it.

No new network endpoints, auth paths, file access patterns, or schema changes introduced in this plan.

## Self-Check: PASSED

Files exist:
- `apps/backend/app/core/audit.py` — FOUND (modified)
- `apps/backend/app/core/config.py` — FOUND (modified)
- `apps/backend/app/modules/schedule/constants.py` — FOUND (modified)
- `apps/backend/tests/unit/test_audit_taxonomy.py` — FOUND (modified)

Commits exist:
- `cec7c3cc` — FOUND (Task 1)
- `1899a696` — FOUND (Task 2)
