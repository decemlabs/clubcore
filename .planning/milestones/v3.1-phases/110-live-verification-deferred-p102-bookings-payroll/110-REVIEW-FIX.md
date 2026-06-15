---
phase: 110-live-verification-deferred-p102-bookings-payroll
fixed_at: 2026-06-14T23:35:00Z
review_path: .planning/phases/110-live-verification-deferred-p102-bookings-payroll/110-REVIEW.md
iteration: 1
findings_in_scope: 8
fixed: 8
skipped: 0
status: all_fixed
---

# Phase 110: Code Review Fix Report

**Fixed at:** 2026-06-14T23:35:00Z
**Source review:** `.planning/phases/110-live-verification-deferred-p102-bookings-payroll/110-REVIEW.md`
**Iteration:** 1

**Summary:**
- Findings in scope: 8 (CR-01, CR-02, WR-01, WR-02, WR-03, WR-04, IN-01, IN-02)
- Fixed: 8
- Skipped: 0

## Fixed Issues

### CR-01: Seed script seeds Payment without PtSession — payroll revenue will be 0

**Files modified:** `apps/backend/scripts/seed_p102_walkthrough.py`
**Commit:** `26d57d65`
**Applied fix:** Added entity #8 `PtSession` (deterministic `PT_SESSION_ID = uuid.uuid5(_NS, "p102-walkthrough:pt-session")`) with `performed_at=_PAYMENT_AT` (2026-04-15 10:00 UTC, inside the payroll window), `trainer_id=TRAINER_ID`, `pt_package_id=PACKAGE_ID`, `client_id=CLIENT_ID`, and `ON CONFLICT (id) DO NOTHING` for idempotency. Added `PtSession` import and `PT_SESSION_ID` to the summary print block. Updated the module docstring entity list. This fixes the false-positive walkthrough: the payroll `fetch_trainer_session_revenue` EXISTS subquery now finds a non-cancelled pt_session in the period and returns non-zero revenue.

---

### CR-02: Shell script JSON-injects raw env vars — malformed JSON on special characters

**Files modified:** `apps/backend/scripts/verify/p102_walkthrough.sh`
**Commit:** `479240df`
**Applied fix:** Replaced the raw shell interpolation `"{\"email\":\"$SEED_OWNER_EMAIL\",\"password\":\"$SEED_OWNER_PASSWORD\"}"` with a Python-built payload via `json.dumps()` using `os.environ`. The `LOGIN_BODY` variable is now constructed via `python3 -c "import json, os; print(json.dumps({...}))"` and passed as `-d "$LOGIN_BODY"` to curl. Correctly escapes `"`, `\`, and newlines in credentials.

---

### WR-01: Printed slot_start in seed summary is recomputed — wrong on idempotent re-run

**Files modified:** `apps/backend/scripts/seed_p102_walkthrough.py`
**Commit:** `26d57d65`
**Applied fix:** Added a comment block above the `slot_start` print clarifying that the value is recomputed each run and may differ from the stored DB value on idempotent re-runs. Operators are directed to use `SLOT_ID` (deterministic uuid5) as the canonical reference. Also split the long print line to fix ruff E501 (follow-up commit `daf6f88f`).

---

### WR-02: Seed script silently accepts any owner if email doesn't match

**Files modified:** `apps/backend/scripts/seed_p102_walkthrough.py`
**Commit:** `26d57d65`
**Applied fix:** Removed the silent fallback that picked the first owner found when `SEED_OWNER_EMAIL` did not match any user. Now fails immediately with `"ERROR: no owner with email '{email}' found. Run uv run python -m scripts.seed_demo_data first."` printed to stderr and returns 1. The second `if owner is None` guard (for when no owners exist at all) was merged into the single check.

---

### WR-03: Race-test TRUNCATE wipes ALL users/trainers — destructively broad

**Files modified:** `apps/backend/tests/integration/bookings/test_p102_booking_lifecycle.py`
**Commits:** `dc9d4740` (initial fix), `1a3582ad` (corrected FK chain)
**Applied fix:** Replaced the global `TRUNCATE ... RESTART IDENTITY CASCADE` with targeted `DELETE` statements scoped to rows seeded by this test only. Identified by the constant `_RACE_OWNER_EMAIL_P102` for the user root, and by name prefix patterns (`P102RacePlan-%`, `P102RaceTrainer-%`) for plans and trainers. The delete chain handles the full FK graph in leaf-to-root order:
1. `booking_notifications` (FK → bookings via slot)
2. `pt_sessions` (FK → clients)
3. `audit_log` (by `actor_user_id`)
4. `bookings` (by slot)
5. `in_app_notifications`, `client_push_tokens`, `client_refresh_tokens`, `client_payment_methods` (all FK → clients; triggered by HTTP booking side-effects)
6. `trainer_availability_slots` (by `created_by_user_id`)
7. `pt_packages` (by client)
8. `clients` (by `created_by_user_id`)
9. `pt_package_plans` (by name prefix)
10. `trainers` (by name prefix)
11. `users` (by email)

Verified against real Postgres: all 5 tests pass including the race test teardown.

---

### WR-04: Audit_log count assertion in race test is not scoped to the test's slot

**Files modified:** `apps/backend/tests/integration/bookings/test_p102_booking_lifecycle.py`
**Commit:** `10ff01e6`
**Applied fix:** The REVIEW suggested filtering by `AuditLog.resource_id == slot_id` but the actual booking_created event stores `resource_id = booking.id` (not slot_id). The correct fix uses a subquery: `AuditLog.resource_id.in_(select(Booking.id).where(Booking.slot_id == slot_id))`. This correctly scopes the count to only the booking_created audit rows belonging to this test's slot, excluding stale rows from prior runs or other tests. Test verified passing.

---

### IN-01: `@pytest.mark.asyncio` on race test is redundant with `asyncio_mode = "auto"`

**Files modified:** `apps/backend/tests/integration/bookings/test_p102_booking_lifecycle.py`
**Commit:** `dc9d4740`
**Applied fix:** Removed the `@pytest.mark.asyncio` decorator from `test_concurrent_create_booking_slot_already_booked_clear_409`. The `asyncio_mode = "auto"` setting in `pyproject.toml` makes it redundant; sibling lifecycle tests (Test A, Test B) have no such mark.

---

### IN-02: Walkthrough step 4 soft-accepts slot re-booking failure — masks FSM regression

**Files modified:** `apps/backend/scripts/verify/p102_walkthrough.sh`
**Commit:** `479240df`
**Applied fix:** Replaced the `INFO` + `BOOKING2_ID=""` soft-accept branch with a hard `FAIL` + `exit 1`. The message now reads `"FAIL: slot not restored to 'active' after cancel (got $CREATE2_STATUS) — FSM regression"`. The summary echo at the end was updated from `"${BOOKING2_ID:-n/a (slot not re-bookable)}"` to `"${BOOKING2_ID:-n/a}"` since the fallback code path no longer exists.

---

## Verification Results

**ruff check** (changed .py files): All checks passed.

**mypy** (changed .py files): Success: no issues found in 2 source files.

**bash -n** (shell syntax check): syntax OK.

**pytest** (integration tests):
```
5 passed in 2.05s
tests/integration/bookings/test_p102_booking_lifecycle.py  (3 tests)
tests/integration/payroll/test_p102_payroll_lifecycle.py   (2 tests)
```

---

_Fixed: 2026-06-14T23:35:00Z_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
