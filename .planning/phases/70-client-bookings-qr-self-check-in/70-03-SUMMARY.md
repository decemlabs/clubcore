---
phase: 70-client-bookings-qr-self-check-in
plan: "03"
subsystem: client-portal + bookings-write-surface
tags:
  - bookings
  - client-portal
  - idor
  - idempotency
  - race-test
  - protocol-slots
dependency_graph:
  requires:
    - "70-02 (create_booking_for_client / cancel_booking_for_client Protocol slots)"
    - "70-01 (CANCEL_WINDOW_HOURS_CLIENT constant)"
    - "Phase 68 (ClientPrincipal + require_client + verify_client_csrf)"
    - "Phase 69 (existing client_portal router/service base)"
  provides:
    - "POST /client/booking (idempotent, 201/422/409)"
    - "POST /client/booking/{id}/cancel (IDOR 404-collapse)"
    - "GET /client/slots (trainer-filtered, paginated)"
    - "verify_client_idempotency in app.core.idempotency"
    - "NoActivePtPackageError (422) in app.core.exceptions"
  affects:
    - "Plan 71-06 (PWA Book screen wired to these endpoints)"
tech_stack:
  added: []
  patterns:
    - "Protocol-slot write delegation: client_portal -> core.dependencies -> bookings (D-20-MODULE)"
    - "Client-scoped idempotency: verify_client_idempotency mirrors verify_idempotency with ClientPrincipal"
    - "IDOR 404-collapse: non-owned booking cancel -> 404 booking_not_found (anti-oracle)"
    - "Race test with db_session_real_commit (criterion #1): partial UNIQUE arbiter"
    - "Error code remapping: PtPackageNotActiveError (409) -> NoActivePtPackageError (422) at service boundary"
key_files:
  created:
    - "apps/backend/tests/integration/client_portal/test_client_booking.py"
    - "apps/backend/tests/integration/client_portal/test_client_booking_race.py"
    - "apps/backend/tests/integration/client_portal/test_client_booking_idor.py"
  modified:
    - "apps/backend/app/modules/client_portal/schemas.py"
    - "apps/backend/app/modules/client_portal/repository.py"
    - "apps/backend/app/modules/client_portal/service.py"
    - "apps/backend/app/modules/client_portal/router.py"
    - "apps/backend/app/core/idempotency.py"
    - "apps/backend/app/core/exceptions.py"
decisions:
  - "D-70-03-REMAP: PtPackageNotActiveError (409 ConflictError from bookings domain) caught at service layer and re-raised as NoActivePtPackageError (422 ValidationAppError, code='no_active_pt_package') — client_portal never imports app.modules.bookings (D-20-MODULE)"
  - "D-70-03-IDEM: verify_client_idempotency added to app.core.idempotency — client-scoped variant of verify_idempotency using ClientPrincipal instead of CurrentUser staff principal"
  - "D-70-03-SQL: fetch_available_slots uses conditional trainer_filter string (CAST(:trainer_id AS UUID) or '') rather than IS NULL check — avoids asyncpg `::uuid` cast syntax conflict with :name bind params"
metrics:
  duration: "~19m"
  completed: "2026-05-30"
  tasks: 3
  files: 9
---

# Phase 70 Plan 03: Client Booking Write Surface + Tests Summary

**One-liner:** Client booking POST (idempotent, 422 on no-PT-package, 409 on race), cancel (IDOR 404-collapse, cancel-window), and GET slots (trainer-filtered, paginated) exposed in `client_portal` via Protocol-slot delegates, with concurrency race and IDOR 404-collapse integration tests proving criteria #1 and #3.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Booking/cancel/slots schemas + available-slots raw-SQL reader | 8701a269 | schemas.py, repository.py |
| 2 | Service delegates + router endpoints + idempotency + error mapping | 4bf2c0c9 | service.py, router.py, idempotency.py, exceptions.py, test_client_booking.py |
| 3 | Race + IDOR 404-collapse integration tests | 5078939d | test_client_booking_race.py, test_client_booking_idor.py |

## What Was Built

### Schemas (`client_portal/schemas.py`)

Three new Phase 70 schemas added:
- `ClientCreateBookingRequest`: `slot_id + pt_package_id` — NO `client_id` field (T-70-11 structural mitigation)
- `ClientBookingResponse`: client-safe booking projection (`id, slot_id, status, start_time, trainer_name`) — declared here so `client_portal` never imports `app.modules.bookings`
- `ClientAvailableSlotItem`: `slot_id, trainer_id, trainer_name, start_time, end_time` — no owner-only economics (T-70-13 / D-69-05)

### Repository (`client_portal/repository.py`)

Added `fetch_available_slots(session, *, trainer_id, limit, offset) -> (rows, total)`:
- Raw SQL `text()` only — NO `from app.modules.schedule` ORM import (D-20-MODULE)
- Conditional `CAST(:trainer_id AS UUID)` filter (avoids asyncpg `::name::type` parse conflict)
- Joins `trainer_availability_slots` + `trainers`, filters `status='active' AND start_time > now()` + alive trainers
- Returns `(list[dict], int)` — rows and total count

### Service (`client_portal/service.py`)

Three write delegates via Protocol slots:
1. `create_booking_for_client_request` — calls `dependencies.create_booking_for_client`; catches `ConflictError` with `code='pt_package_not_active'` and re-raises as `NoActivePtPackageError` (422, CBOOK-04)
2. `cancel_client_booking` — calls `dependencies.cancel_booking_for_client`; `BookingNotFoundError` bubbles as 404
3. `list_available_slots` — calls `get_active_pt_package` → extracts `trainer_id` via `getattr` (Protocol-narrow pattern mirrors bookings/service.py:990) → calls repository

### Router (`client_portal/router.py`)

Three new endpoints on `APIRouter(tags=["Client-Portal"])`:
- `POST /booking` (`operation_id="client_create_booking"`) — RBAC-04: `require_client → verify_client_csrf → verify_client_idempotency → get_db`; 201 on success; `idempotent_execute` runner
- `POST /booking/{booking_id}/cancel` (`operation_id="client_cancel_booking"`) — RBAC-04: `require_client → verify_client_csrf → get_db`; `client.id` is the ONLY ownership source (T-70-09)
- `GET /slots` (`operation_id="client_list_slots"`) — behind `require_client()` only (safe GET); paginated

### `app/core/idempotency.py`

Added `verify_client_idempotency`: client-scoped variant of `verify_idempotency` that uses `get_current_client` (ClientPrincipal) instead of `get_current_user` (CurrentUser staff). Key shape: `{client.id}:{method}:{path}:{header_value}`.

### `app/core/exceptions.py`

Added `NoActivePtPackageError(ValidationAppError)` with `code = "no_active_pt_package"`, `status_code = 422`. Routes PWA to Plans/Checkout (D-70-03).

### Tests

- `test_client_booking.py` (6 tests): happy path, idempotency replay, 422 no_active_pt_package, own-cancel + slot-restore, GET /slots with and without PT-package
- `test_client_booking_race.py` (1 test): `db_session_real_commit` + 2 parallel POSTs DISTINCT keys → `[201, 409]` slot_already_booked + 1 confirmed booking + 1 audit row
- `test_client_booking_idor.py` (3 tests): client A → 404 on B's booking (anti-oracle), cancel within window → cancel_window_expired, outside window → success + slot restored

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing critical functionality] Added `verify_client_idempotency` to `app.core.idempotency`**
- **Found during:** Task 2 implementation
- **Issue:** `verify_idempotency` requires `get_current_user` (staff auth dep), which would 401 on every client request. No client-scoped variant existed.
- **Fix:** Added `verify_client_idempotency` to `app.core.idempotency` mirroring `verify_idempotency` but using `get_current_client` (ClientPrincipal)
- **Files modified:** `app/core/idempotency.py`
- **Commit:** 4bf2c0c9

**2. [Rule 2 - Missing critical functionality] Added `NoActivePtPackageError` to `app.core.exceptions`**
- **Found during:** Task 2 — `PtPackageNotActiveError` has `status_code=409` but CBOOK-04 requires `422`. `ValidationAppError` base class has `code="validation_error"`, not `"no_active_pt_package"`.
- **Fix:** Added `NoActivePtPackageError(ValidationAppError)` with `code="no_active_pt_package"`, `status_code=422`. Service catches `ConflictError` by `.code` attribute (avoids `app.modules.bookings` import) and re-raises the new typed error.
- **Files modified:** `app/core/exceptions.py`, `app/modules/client_portal/service.py`
- **Commit:** 4bf2c0c9

**3. [Rule 1 - Bug] SQL `::uuid` cast syntax conflict with asyncpg**
- **Found during:** Task 2 test run — `PostgresSyntaxError: syntax error at or near ":"`
- **Issue:** `text()` SQL used `:trainer_id::uuid` — asyncpg parser sees `:trainer_id` as a bind parameter and `::uuid` as postgres double-colon cast, creating a parse error.
- **Fix:** Changed conditional SQL approach: when `trainer_id` is not None, build `CAST(:trainer_id AS UUID)` filter string; no filter when None. Mirrors `fetch_client_payments_page` owned_sql discipline.
- **Files modified:** `app/modules/client_portal/repository.py`
- **Commit:** 4bf2c0c9

## Verification Results

- `cd apps/backend && uv run pytest tests/integration/client_portal/ -q`: 33 passed (23 pre-existing + 10 new)
- `cd apps/backend && uv run pytest tests/integration/bookings/ -q`: 90 passed (unchanged)
- `cd apps/backend && uv run lint-imports`: 3 contracts kept, 0 broken, 0 new `ignore_imports`
- `cd apps/backend && uv run mypy app/modules/client_portal/ app/core/idempotency.py app/core/exceptions.py`: no issues
- `cd apps/backend && uv run ruff check app/modules/client_portal/ app/core/idempotency.py app/core/exceptions.py`: all checks passed
- POST /client/booking with exhausted package → 422 `no_active_pt_package` ✓
- Concurrent same-slot POSTs → [201, 409] `slot_already_booked` + 1 confirmed booking + 1 audit row ✓
- Client A cancel client B's booking → 404 `booking_not_found` (anti-oracle) ✓
- `client_portal` imports `app.modules.bookings`: 0 (verified by lint-imports) ✓

## Success Criteria Achieved

- [x] CBOOK-02: GET /client/slots returns bookable, trainer-filtered, client-safe active future slots, paginated `{items, total, page, pageSize}`
- [x] CBOOK-03: client booking POST is idempotent and race-safe (409 `slot_already_booked` from partial UNIQUE, not idempotency cache)
- [x] CBOOK-04: no-active-PT-package → 422 `no_active_pt_package` (routes PWA to Plans/Checkout)
- [x] CBOOK-05: client cancel windowed + 404-collapse on non-owned booking + slot restore, no credit action
- [x] CBOOK-01: confirmed served by the existing Phase-69 GET /client/bookings (no new work; this plan adds write surface only)

## Known Stubs

None. All implemented functions are fully wired and functional.

## Threat Flags

No new threat surfaces beyond what the threat model defines. All T-70-09..T-70-13 mitigations implemented:
- T-70-09 (IDOR cancel): `client.id` only source; non-owned → 404 `booking_not_found`
- T-70-10 (race): `uq_bookings_slot_confirmed` partial UNIQUE arbiter; loser → 409 `slot_already_booked`
- T-70-11 (body spoofing): `ClientCreateBookingRequest` has no `client_id` field
- T-70-12 (idempotency): `verify_client_idempotency` + `idempotent_execute`; same key replays, distinct keys race at DB
- T-70-13 (slots projection): `ClientAvailableSlotItem` has no owner-only economics

## Self-Check: PASSED
