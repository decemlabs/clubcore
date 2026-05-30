---
phase: 70-client-bookings-qr-self-check-in
plan: "02"
subsystem: bookings-service + core-dependencies + main-wiring
tags:
  - bookings
  - client-portal
  - protocol-slots
  - actor-agnostic
  - idor
dependency_graph:
  requires:
    - "70-01 (CANCEL_WINDOW_HOURS_CLIENT constant in bookings/constants.py)"
    - "Phase 40 (create_booking_via_bot precedent; created_by_user_id nullable)"
    - "Phase 68 (ClientPrincipal + client auth stack)"
  provides:
    - "create_booking_for_client (actor-agnostic booking core, client path)"
    - "cancel_booking_for_client (client cancel with IDOR 404-collapse)"
    - "register_booking_for_client_creator + accessor in core.dependencies"
    - "register_booking_for_client_canceller + accessor in core.dependencies"
    - "Wiring in main.py create_app()"
  affects:
    - "Plan 70-03 (client booking endpoints delegate through these slots)"
tech_stack:
  added: []
  patterns:
    - "Composition-root Protocol slot (D-20-MODULE) — value-returning Callable[..., Awaitable[Any]]"
    - "IDOR 404-collapse: booking.client_id ownership check → BookingNotFoundError (anti-oracle)"
    - "Additive Pydantic model widening: BookingCreatedPayload.actor_role += 'client'; BookingCancelledPayload.cancelled_by_user_id Optional"
key_files:
  created:
    - "apps/backend/tests/integration/bookings/test_create_booking_for_client.py"
    - "apps/backend/tests/integration/bookings/test_cancel_booking_for_client.py"
  modified:
    - "apps/backend/app/modules/bookings/service.py"
    - "apps/backend/app/core/audit_payloads.py"
    - "apps/backend/app/core/dependencies.py"
    - "apps/backend/app/main.py"
decisions:
  - "D-70-07: actor_role='client' literal added to BookingCreatedPayload.actor_role Literal union (additive widening; same pattern as Phase 40 D-40-05 adding 'telegram_bot')"
  - "D-70-05: BookingCancelledPayload.cancelled_by_user_id widened to UUID | None (additive; client self-cancel has no staff user; mirrors BookingCreatedPayload.created_by_user_id widening)"
  - "BookingForClientCreator/Canceller use Callable[..., Awaitable[Any]] return type in dependencies.py (BookingResponse from app.modules.bookings.schemas cannot be imported in app.core without violating core-not-depend-on-modules contract)"
  - "cancel_booking_for_client omits Telegram DM dispatch (out of scope for this plan; Plan 70-03 may add at router layer)"
metrics:
  duration: "~12m"
  completed: "2026-05-30"
  tasks: 3
  files: 6
---

# Phase 70 Plan 02: Actor-Agnostic Booking Core + Client Cancel + Protocol Slots Summary

**One-liner:** Actor-agnostic `create_booking_for_client` and `cancel_booking_for_client` added to bookings service with IDOR 404-collapse and client cancel window, exposed through composition-root Protocol slots in `core.dependencies`, wired in `main.py` — zero new `ignore_imports`, staff path byte-identical, 90 tests pass.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Extract actor-agnostic booking core + create_booking_for_client (D-70-01) | b716388a | service.py, audit_payloads.py, test_create_booking_for_client.py |
| 2 | Actor-agnostic client cancel core with client window + IDOR 404-collapse (D-70-05/06) | 8bae419b | service.py, audit_payloads.py, test_cancel_booking_for_client.py |
| 3 | Composition-root Protocol slots + main.py wiring (D-20-MODULE) | 1edcb217 | dependencies.py, main.py |

## What Was Built

### `create_booking_for_client` (service.py)

Mirrors `create_booking_via_bot`'s 10-step UoW exactly with:
- `created_by_user_id=None` (D-40-05 / D-70-07 anti-fabrication)
- `audit.emit("booking_created", ..., actor_role="client")` literal (INFRA-11 AST gate)
- `actor_user_id=None` at the DB column level
- Same 7 domain errors as the staff path (CBOOK-03: SlotAlreadyBookedError on race; CBOOK-04: PtPackageNotActiveError on no active package)

### `cancel_booking_for_client` (service.py)

Cancel path with the single divergence from staff cancel:
- IDOR 404-collapse (T-70-05): `booking is None OR booking.client_id != client_id → BookingNotFoundError("booking_not_found")` — anti-oracle, never reveals existence for another client
- Client window: `CANCEL_WINDOW_HOURS_CLIENT` measured against `booking.slot.start_time` (D-38-16, NOT `created_at`) → `CancelWindowExpiredError`
- Slot restored via `restore_booking_slot` Protocol slot (booked→active)
- NO `sessions_remaining` mutation (D-70-06: credit only at pt_sessions level)
- Audit: `cancelled_by_user_id=None` (Phase 70 widening of BookingCancelledPayload)

### Protocol slots in `core.dependencies`

- `register_booking_for_client_creator` + `create_booking_for_client` accessor (defensive-raise if unregistered)
- `register_booking_for_client_canceller` + `cancel_booking_for_client` accessor (defensive-raise if unregistered)
- Return type `Any` (avoids `core → modules` import violation; callers in `client_portal` import `BookingResponse` from their own scope)

### Wiring in `main.py`

Both slots wired in `create_app()` next to existing booking registrations. HTTP-only single-wire (no ARQ/bot entry path for client booking writes).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing critical functionality] Extended BookingCreatedPayload.actor_role to include "client"**
- **Found during:** Task 1 implementation
- **Issue:** `BookingCreatedPayload.actor_role` was `Literal["reception", "owner", "telegram_bot"]` — passing `actor_role="client"` would fail Pydantic `extra='forbid'` validation
- **Fix:** Added `"client"` to the Literal union (additive widening, same pattern as Phase 40 D-40-05)
- **Files modified:** `apps/backend/app/core/audit_payloads.py`
- **Commit:** b716388a

**2. [Rule 2 - Missing critical functionality] Extended BookingCancelledPayload.cancelled_by_user_id to UUID | None**
- **Found during:** Task 2 implementation
- **Issue:** `BookingCancelledPayload.cancelled_by_user_id: UUID` (non-Optional) with `extra='forbid'` — client cancel has no staff user UUID; passing `None` would fail validation
- **Fix:** Widened to `UUID | None = None` (additive widening, mirrors `BookingCreatedPayload.created_by_user_id` Phase 40 D-40-05 pattern)
- **Files modified:** `apps/backend/app/core/audit_payloads.py`
- **Commit:** 8bae419b

**3. [Rule 1 - Bug] Fixed expired-before-slot test setup**
- **Found during:** Task 1 test execution
- **Issue:** Test set `end_date=yesterday` — but the `get_active_pt_package` resolver filters `end_date >= today`, so the package was not found (PtPackageNotActiveError instead of PtPackageExpiredBeforeSlotError)
- **Fix:** Set `pkg_end_date` to 5 days from now (package still active), slot 30 days from now (slot after package expiry)
- **Files modified:** `tests/integration/bookings/test_create_booking_for_client.py`
- **Commit:** b716388a

## Verification Results

- `cd apps/backend && uv run pytest tests/integration/bookings/ -q`: 90 passed (76 original + 9 create_for_client + 5 cancel_for_client)
- `cd apps/backend && uv run lint-imports`: 3 contracts kept, 0 broken, 0 new ignore_imports
- `cd apps/backend && uv run mypy app/modules/bookings/service.py app/core/dependencies.py app/main.py`: no issues
- `cd apps/backend && uv run ruff check app/modules/bookings/service.py app/core/dependencies.py`: all checks passed
- `uv run python -c "from app.core.dependencies import create_booking_for_client, cancel_booking_for_client"`: OK

## Success Criteria Achieved

- [x] CBOOK-03: race-safe, actor-agnostic booking core callable by the client write-slot (409 slot_already_booked on the loser)
- [x] CBOOK-04: no-active-PT-package surfaces PtPackageNotActiveError (Plan 70-03 maps to 422 no_active_pt_package)
- [x] CBOOK-05: client cancel core enforces the client window + 404-collapses non-owned bookings + restores slot with no credit action
- [x] Staff contract byte-identical (76 original tests unchanged)
- [x] import-linter green, zero new ignore_imports (D-20-MODULE)
- [x] Protocol-slot writes only: client_portal will import only app.core.dependencies, never app.modules.bookings

## Known Stubs

None. All implemented functions are fully wired and functional.

## Threat Flags

None. All surfaces in this plan are internal service + core functions (no new network endpoints). The IDOR mitigation (T-70-05) and race guard (T-70-06) are implemented as required by the threat model.

## Self-Check: PASSED
