---
phase: 80-booking-reschedule
plan: "02"
subsystem: backend
tags: [booking, reschedule, atomic, pt-package, telegram, idempotency, audit, idor]
dependency_graph:
  requires:
    - phase: 80-01
      provides: migration-0053, booking-rescheduled-audit-event, reschedule-dm-template, reschedule-request-schema
  provides:
    - reschedule-booking-endpoint (POST /client/booking/{id}/reschedule)
    - atomic-reschedule-service-function
    - booking-for-client-rescheduler-protocol-slot
    - reschedule-integration-tests-9
  affects: [client_portal, bookings, dependencies, main]
tech_stack:
  added: []
  patterns:
    - cancel-old-plus-create-new-atomic-uow
    - fire-and-forget-post-commit-dm-send
    - protocol-slot-d20-module
    - idor-404-collapse
    - pt-credit-preserved-move-semantics
key_files:
  created:
    - apps/backend/tests/integration/bookings/test_reschedule_booking_for_client.py
  modified:
    - apps/backend/app/modules/bookings/service.py
    - apps/backend/app/core/dependencies.py
    - apps/backend/app/main.py
    - apps/backend/app/modules/client_portal/service.py
    - apps/backend/app/modules/client_portal/router.py
key_decisions:
  - "Evidence INSERT uses the same post-commit session (not fresh sessionmaker) to avoid sync/async engine wrapping complexity in the HTTP context"
  - "Race test simulates TOCTOU via existing confirmed booking against 'active' slot (partial UNIQUE fires on flush), matching SAVEPOINT-mode test limitations"
  - "reschedule_client_booking delegate name used in service.py (not reschedule_booking_for_client) to avoid name collision with the imported accessor"
requirements-completed: [RESCH-01, RESCH-02]
duration: 25min
completed: "2026-06-03"
---

# Phase 80 Plan 02: Reschedule Endpoint Summary

**Atomic client booking reschedule via cancel-old + create-new in one UoW; PT-credit preserved by move semantics; reschedule DM sent via send_text_dm; 9 integration tests prove all error paths, audit, credit, and DM delivery.**

## Performance

- **Duration:** ~25 min
- **Started:** 2026-06-03T17:30:00Z
- **Completed:** 2026-06-03T17:55:00Z
- **Tasks:** 3
- **Files modified:** 5
- **Files created:** 1

## Accomplishments

- `reschedule_booking_for_client` in bookings/service.py: atomic 15-step UoW with window/IDOR/cross-trainer/race guards, audit emit, fire-and-forget DM, post-send evidence row
- `BookingForClientRescheduler` Protocol slot in dependencies.py + main.py wiring + client_portal delegate + `POST /booking/{id}/reschedule` endpoint with RBAC-04 ordering and idempotent execution
- 9-test integration suite: happy path, race→409, window→409, cross-trainer→409, IDOR→404, audit linkage, PT-credit unchanged, DM-sent spy, notification row evidence

## Task Commits

1. **Task 1: Atomic reschedule_booking_for_client** — `47433eff` (feat)
2. **Task 2: Protocol slot + delegate + endpoint** — `e615d850` (feat)
3. **Task 3: Integration tests** — `833d922c` (test)

## Files Created/Modified

- `apps/backend/app/modules/bookings/service.py` — Added `RescheduleWindowExpiredError`, `SlotTrainerMismatchError`, `reschedule_booking_for_client` function; added `render_booking_rescheduled_dm` import
- `apps/backend/app/core/dependencies.py` — Added `BookingForClientRescheduler` type alias, `_booking_for_client_rescheduler` module global, `register_booking_for_client_rescheduler` setter, `reschedule_booking_for_client` accessor
- `apps/backend/app/main.py` — Added `register_booking_for_client_rescheduler` import; wired slot in `create_app()`
- `apps/backend/app/modules/client_portal/service.py` — Added `reschedule_booking_for_client` to dependency imports; added `reschedule_client_booking` delegate
- `apps/backend/app/modules/client_portal/router.py` — Added `ClientRescheduleBookingRequest` import; added `client_reschedule_booking` endpoint handler
- `apps/backend/tests/integration/bookings/test_reschedule_booking_for_client.py` — 9 integration tests (new file)

## Decisions Made

- **Post-commit evidence INSERT uses same session**: After `await session.commit()`, the session is clean and reusable. Using `async_sessionmaker(session.get_bind())` to create a fresh session would require wrapping the sync engine into `AsyncEngine`; reusing the committed session is simpler and correct in the HTTP context. The reminder_24h cron uses a true separate `session_factory` because it opens many write sessions across N sends.
- **Race test uses partial-UNIQUE approach**: The SAVEPOINT-mode session cannot demonstrate true concurrent races. Instead we seed a `confirmed` booking against an `active` slot; the predicate-gated UPDATE returns 1 row (succeeds) but the flush fires the partial UNIQUE `uq_bookings_slot_confirmed` IntegrityError. This correctly tests the `_is_slot_confirmed_conflict` path.
- **`reschedule_client_booking` delegate name**: client_portal/service.py already imports `reschedule_booking_for_client` from `app.core.dependencies` as the Protocol-slot accessor; the delegate function uses a different name `reschedule_client_booking` to avoid a name collision in the same namespace.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Race test used pre-booked (status='booked') slot — wrong test path**
- **Found during:** Task 3 (integration test execution)
- **Issue:** Initial race test set `new_slot.status = "booked"` before calling reschedule. The step-4 slot status guard (`new_slot.status != "active"`) fires before reaching the predicate-gated UPDATE/flush, raising `SlotNotAvailableError` instead of `SlotAlreadyBookedError`. This tested the wrong code path.
- **Fix:** Changed the race scenario to keep the slot `active` (so the status guard passes) but insert a `confirmed` booking row against it. The predicate-gated UPDATE still flips the slot (0 rows because the status guard fires first? No — actually the UPDATE succeeds because status is active). Actually: the UPDATE succeeds (slot was active → booked flip returns 1 row), but the INSERT of the new booking hits the partial UNIQUE `uq_bookings_slot_confirmed` at flush time. This is the correct TOCTOU BOOK-10 path.
- **Files modified:** tests/integration/bookings/test_reschedule_booking_for_client.py
- **Verification:** Test passes with `SlotAlreadyBookedError`
- **Committed in:** 833d922c

**2. [Rule 2 - Missing] Unused imports and style fixes in test file**
- **Found during:** Task 3 (ruff check)
- **Issue:** Test file had unused imports (`UTC`, `datetime`, `uuid4`, `TrainerAvailabilitySlot`), unsorted imports (I001), unpacked unused vars (RUF059), and Cyrillic ambiguous char warnings (RUF001).
- **Fix:** Removed unused imports, prefixed unused vars with `_`, added `# noqa: RUF001` where needed, ran `ruff --fix` for I001.
- **Files modified:** tests/integration/bookings/test_reschedule_booking_for_client.py
- **Verification:** `uv run ruff check` exits 0 on all modified files

---

**Total deviations:** 2 auto-fixed (1 bug, 1 style)
**Impact on plan:** Both fixes necessary for correctness and clean CI. No scope creep.

## Issues Encountered

None beyond the auto-fixed deviations above.

## Known Stubs

None — all functionality is fully implemented. No placeholder data, no TODO stubs.

## Threat Flags

No new threat surface introduced beyond what the plan's threat model covers (T-80-05 through T-80-14 all mitigated per acceptance criteria).

## Verification Results

- `uv run pytest tests/integration/bookings/test_reschedule_booking_for_client.py -q`: 9 passed
- `uv run mypy --strict app`: Success: no issues found in 229 source files
- `uv run ruff check` (modified files): All checks passed
- `uv run lint-imports`: Contracts: 3 kept, 0 broken (zero new ignore_imports)

## Next Phase Readiness

RESCH-01 and RESCH-02 backend fully delivered:
- Atomic reschedule endpoint with all four error paths
- PT-session credit preserved by construction (move semantics)
- Telegram DM delivered to client with new slot time
- booking_rescheduled audit event emitted
- Integration suite proves all correctness requirements

## Self-Check: PASSED

Files verified to exist:
- apps/backend/app/modules/bookings/service.py: FOUND (reschedule_booking_for_client present)
- apps/backend/app/core/dependencies.py: FOUND (register_booking_for_client_rescheduler present)
- apps/backend/app/modules/client_portal/router.py: FOUND (client_reschedule_booking present)
- apps/backend/tests/integration/bookings/test_reschedule_booking_for_client.py: FOUND

Commits verified:
- 47433eff: FOUND
- e615d850: FOUND
- 833d922c: FOUND

---
*Phase: 80-booking-reschedule*
*Completed: 2026-06-03*
