---
phase: 110-live-verification-deferred-p102-bookings-payroll
reviewed: 2026-06-14T00:00:00Z
depth: standard
files_reviewed: 4
files_reviewed_list:
  - apps/backend/scripts/seed_p102_walkthrough.py
  - apps/backend/scripts/verify/p102_walkthrough.sh
  - apps/backend/tests/integration/bookings/test_p102_booking_lifecycle.py
  - apps/backend/tests/integration/payroll/test_p102_payroll_lifecycle.py
findings:
  critical: 2
  warning: 4
  info: 2
  total: 8
status: issues_found
---

# Phase 110: Code Review Report

**Reviewed:** 2026-06-14T00:00:00Z
**Depth:** standard
**Files Reviewed:** 4
**Status:** issues_found

## Summary

Reviewed the idempotent seed script, bash live-HTTP walkthrough, and two E2E verification
tests for the P102 bookings + payroll lifecycle. The test assertion coverage is generally
strong — FSM states, accrual snapshot fields, RBAC 403, and the 409 race path are all
verified. Two blockers were found: the seed script seeds a `Payment` without any
`PtSession` rows, which causes the payroll `fetch_trainer_session_revenue` revenue query to
return 0 (the EXISTS guard requires a pt_session in-period), meaning the walkthrough script's
Step 5 payroll preview will show `revenueKopecks=0` and Step 6 accrual will produce an
incorrect `accrual_kopecks=0`; and the bash script injects raw env-var values directly into
a JSON string, making it vulnerable to JSON-injection if credentials contain `"` or `\`
characters. Four warnings cover the misleading summary output, an unsafe owner fallback, the
destructively broad TRUNCATE in the race-test teardown, and the missing `@pytest.mark.asyncio`
parity on lifecycle tests.

## Critical Issues

### CR-01: Seed script seeds Payment without PtSession — payroll revenue will be 0

**File:** `apps/backend/scripts/seed_p102_walkthrough.py:257-275`

**Issue:** The payroll revenue query in `app/modules/payroll/repository.py:fetch_trainer_session_revenue`
attributes commission revenue only to pt_packages that have **at least one non-cancelled
PtSession in the period** (lines 103-109: `AND EXISTS (SELECT 1 FROM pt_sessions s WHERE
s.pt_package_id = pkg.id AND s.cancelled_at IS NULL AND ... BETWEEN :period_start AND
:period_end)`). The seed script seeds a `Payment` (`PAYMENT_ID`, `received_at=2026-04-15`)
and a `PtPackage` (`PACKAGE_ID`, `trainer_id=TRAINER_ID`) but seeds **zero PtSession rows**.

Consequence: when the walkthrough script runs Step 5 (payroll preview) and Step 6 (run
accrual), the EXISTS subquery returns no rows for `PACKAGE_ID`, so
`commission_revenue_kopecks` = 0. The accrual will show `revenueKopecks=0` and
`accrual_kopecks=0` regardless of the commission/session-fee config. The walkthrough
passes (HTTP 200/201) but verifies nothing meaningful — it is a false positive.

**Fix:** Add a PtSession seed row (entity #8) to the seed script, timed within the payroll
period (2026-04-01..2026-04-30), attributed to `TRAINER_ID` and `PACKAGE_ID`:

```python
from app.modules.pt_sessions.models import PtSession  # add to imports

PT_SESSION_ID = uuid.uuid5(_NS, "p102-walkthrough:pt-session")

# 8. PtSession — links the package to the period for payroll revenue attribution
sess_stmt = (
    pg_insert(PtSession)
    .values(
        id=PT_SESSION_ID,
        pt_package_id=PACKAGE_ID,
        trainer_id=TRAINER_ID,
        client_id=CLIENT_ID,
        performed_at=_PAYMENT_AT,          # 2026-04-15 10:00 UTC — inside period
        performed_by_user_id=owner.id,
        trainer_name_snapshot="P102 Walkthrough Trainer",
        cancelled_at=None,
    )
    .on_conflict_do_nothing(index_elements=["id"])
)
await session.execute(sess_stmt)
```

Also add `PT_SESSION_ID` to the summary print block and update the docstring entity list.

---

### CR-02: Shell script JSON-injects raw env vars — malformed JSON on special characters

**File:** `apps/backend/scripts/verify/p102_walkthrough.sh:74`

**Issue:** The login payload is constructed by embedding `$SEED_OWNER_EMAIL` and
`$SEED_OWNER_PASSWORD` directly into a double-quoted JSON string:

```bash
-d "{\"email\":\"$SEED_OWNER_EMAIL\",\"password\":\"$SEED_OWNER_PASSWORD\"}"
```

If either variable contains `"` (e.g., `pass"word`), `\`, or a newline, the result is
malformed JSON that `curl` sends as-is, causing a `422` from the server (or a parse error
that is silently treated as a bad login). The `set -euo pipefail` safety net does not catch
this because the curl command itself succeeds — the failure is in the login status check, but
only if `$SEED_OWNER_EMAIL` or `$SEED_OWNER_PASSWORD` is the attacker-controlled value
(CI secret injection or typo in an exported password).

**Fix:** Build the JSON body via Python (already present in the script environment) so
special characters are correctly escaped:

```bash
LOGIN_BODY=$(python3 -c "
import json, os
print(json.dumps({'email': os.environ['SEED_OWNER_EMAIL'],
                  'password': os.environ['SEED_OWNER_PASSWORD']}))")

LOGIN_RESPONSE=$(curl -si -X POST "$BASE_URL/api/v1/auth/login" \
  -H 'Content-Type: application/json' \
  -c "$COOKIE_JAR" \
  -d "$LOGIN_BODY")
```

Apply the same pattern to any future `-d` blocks that embed env vars in JSON strings
(Steps 2, 4a, 4b, 6 embed `$SLOT_ID`, `$CLIENT_ID`, `$PT_PACKAGE_ID`, `$TRAINER_ID` which
are UUIDs and do not contain special chars — they are lower-risk but the pattern is
still fragile).

---

## Warnings

### WR-01: Printed slot_start in seed summary is recomputed — wrong on idempotent re-run

**File:** `apps/backend/scripts/seed_p102_walkthrough.py:289`

**Issue:** `slot_start` is recomputed on every run via `_next_monday_10_msk()` (line 175),
but the actual DB row for `SLOT_ID` is written only on the first run (ON CONFLICT DO
NOTHING). On a re-run the print statement outputs the newly computed value:

```python
print(f"  slot_start (UTC) = {slot_start.isoformat()}")
```

This is the value computed *today*, not the value stored in the DB. If the operator copies
this value into `SLOT_ID` / `SLOT_START` env vars for the walkthrough, they have the right
UUID but a stale time printout. The discrepancy could be confusing when debugging.

**Fix:** Either (a) query the DB row after the insert and print the stored value, or (b)
add a comment clarifying that the printed time is the computed-this-run value and may differ
from the stored DB value on re-runs.

---

### WR-02: Seed script silently accepts any owner if email doesn't match

**File:** `apps/backend/scripts/seed_p102_walkthrough.py:148-158`

**Issue:** The fallback at lines 148-159 silently accepts the *first* owner found when the
provided `SEED_OWNER_EMAIL` does not match any user:

```python
if owner is None:
    # Fall back to any owner if the email doesn't match exactly
    owner = await session.scalar(
        select(User).where(User.role == Role.OWNER).order_by(User.created_at)
    )
```

This undermines the env-var validation performed earlier (lines 108-123). An operator who
mistyped `SEED_OWNER_EMAIL` will silently get rows seeded under a different owner's
`created_by_user_id`, without any warning. In a multi-owner staging environment this could
attribute data to the wrong user.

**Fix:** Remove the fallback and fail with a clear error if the exact-email lookup returns
nothing:

```python
if owner is None:
    print(
        f"ERROR: no owner with email '{email}' found. "
        "Run `uv run python -m scripts.seed_demo_data` first.",
        file=sys.stderr,
    )
    return 1
```

---

### WR-03: Race-test TRUNCATE wipes ALL users/trainers — destructively broad

**File:** `apps/backend/tests/integration/bookings/test_p102_booking_lifecycle.py:309-317`

**Issue:** The `db_session_real_commit_p102` teardown issues:

```sql
TRUNCATE users, clients, trainers, pt_package_plans,
         pt_packages, trainer_availability_slots, bookings, audit_log
RESTART IDENTITY CASCADE
```

This truncates **every row in every listed table**, not just the rows seeded by this test.
If the race test runs in the same pytest session as other integration tests that use a
shared Postgres instance (e.g., any test that does not use the SAVEPOINT-rolled fixture),
the teardown will silently wipe their data. The `RESTART IDENTITY CASCADE` is also
superfluous for UUID-keyed tables (no sequences to restart), and the CASCADE from `users`
will propagate to any table with a FK→users that is not listed here (e.g., payroll tables
seeded by payroll tests if they share the DB).

The pattern is copied from `test_booking_race.py` and is intentional for the race test
isolation model, but the scope is unnecessarily broad.

**Fix:** Scope the DELETE to only the rows inserted by this test. Using the deterministic
UUIDs (owner_id, slot_id, etc.) makes this safe:

```python
# After the test, delete only the rows this test inserted (by PK).
await conn.execute(
    text("DELETE FROM bookings WHERE slot_id = :sid"),
    {"sid": str(slot_id)},
)
await conn.execute(
    text("DELETE FROM trainer_availability_slots WHERE id = :sid"),
    {"sid": str(slot_id)},
)
# ... etc. for each seeded row, working outward from FK leaves to roots
await conn.execute(text("DELETE FROM users WHERE id = :uid"), {"uid": str(owner_id)})
```

---

### WR-04: Audit_log count assertion in race test is not scoped to the test's slot

**File:** `apps/backend/tests/integration/bookings/test_p102_booking_lifecycle.py:495-502`

**Issue:**

```python
created_count = await session.scalar(
    select(func.count())
    .select_from(AuditLog)
    .where(AuditLog.action == "booking_created")
)
assert created_count == 1, ...
```

The assertion counts ALL `booking_created` audit rows in the database, not only those for
the slot under test. If any prior test (in the same pytest session or a prior un-rolled
run) left a `booking_created` row in the audit log, this assertion fails with a count > 1,
producing a false negative. Conversely, if the audit log was previously truncated only
partially, this could produce a false positive. The race-test intent is to verify that
exactly one booking was committed, but the unscoped count cannot guarantee that.

**Fix:** Filter by `resource_id = slot_id` (or the booking id of the winning 201
response) to scope the audit assertion:

```python
created_count = await session.scalar(
    select(func.count())
    .select_from(AuditLog)
    .where(
        AuditLog.action == "booking_created",
        AuditLog.resource_id == slot_id,   # scope to this slot's bookings only
    )
)
assert created_count == 1, ...
```

---

## Info

### IN-01: `@pytest.mark.asyncio` on race test is redundant with `asyncio_mode = "auto"`

**File:** `apps/backend/tests/integration/bookings/test_p102_booking_lifecycle.py:335`

**Issue:** `pyproject.toml` sets `asyncio_mode = "auto"`, which means all `async def` test
functions are automatically treated as asyncio tests. The explicit `@pytest.mark.asyncio`
on the race test function at line 335 is redundant. The lifecycle tests (Test A, Test B) at
lines 104 and 189 have no mark and work correctly — the race test mark is inconsistent.

**Fix:** Remove the `@pytest.mark.asyncio` decorator from
`test_concurrent_create_booking_slot_already_booked_clear_409` for consistency.

---

### IN-02: Walkthrough step 4 soft-accepts slot re-booking failure — masks FSM regression

**File:** `apps/backend/scripts/verify/p102_walkthrough.sh:165-172`

**Issue:** If the second booking in step 4a returns a non-201 status, the script emits
`INFO` and continues with `BOOKING2_ID=""`, silently omitting the `bookingId` from the
pt-session payload:

```bash
echo "INFO: second booking returned $CREATE2_STATUS — recording PT-session without bookingId"
BOOKING2_ID=""
```

The stated purpose of step 4 is to exercise the "complete-via-pt-session" booking lifecycle
path. If the slot was not restored to `active` after the cancel (step 3), the complete leg
is never tested — but the script still prints `PASS` for step 4b and exits 0. A real FSM
regression (slot stuck in `booked` after cancel) would be silently swallowed.

**Fix:** Either fail hard if the slot cannot be re-booked (enforcing that cancel restores
the slot, which is the FSM guarantee being tested), or at minimum log a `WARN` that clearly
states the complete-via-booking path was not exercised:

```bash
if [ "$CREATE2_STATUS" = "201" ] && [ -n "$BOOKING2_ID" ]; then
  echo "PASS: second booking created, id=$BOOKING2_ID"
else
  echo "FAIL: slot not restored to 'active' after cancel (got $CREATE2_STATUS) — FSM regression"
  exit 1
fi
```

---

_Reviewed: 2026-06-14T00:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
