---
phase: 80-booking-reschedule
plan: 02
type: execute
wave: 2
depends_on: ["80-01"]
files_modified:
  - apps/backend/app/modules/bookings/service.py
  - apps/backend/app/core/dependencies.py
  - apps/backend/app/main.py
  - apps/backend/app/modules/client_portal/service.py
  - apps/backend/app/modules/client_portal/router.py
  - apps/backend/tests/integration/bookings/test_reschedule_booking_for_client.py
autonomous: true
requirements: [RESCH-01, RESCH-02]
must_haves:
  truths:
    - "POST /client/booking/{id}/reschedule atomically cancels the old slot and creates a new booking on the new slot in one transaction"
    - "Concurrent claim of the new slot returns 409 slot_already_booked (DB-constraint driven, not pre-check)"
    - "Reschedule <24h before the original slot start returns 409 reschedule_window_expired"
    - "A new slot belonging to a different trainer returns 409 slot_trainer_mismatch"
    - "A non-owned booking id returns 404 booking_not_found (IDOR anti-oracle)"
    - "PT-session credit is PRESERVED across the reschedule — no decrement, no restore, no double-charge"
    - "A booking_rescheduled audit event is emitted linking old→new booking ids"
    - "client_portal reaches bookings logic only via the composition-root Protocol slot (zero new ignore_imports)"
  artifacts:
    - path: "apps/backend/app/modules/bookings/service.py"
      provides: "reschedule_booking_for_client atomic implementation + RescheduleWindowExpiredError + SlotTrainerMismatchError"
      contains: "async def reschedule_booking_for_client"
    - path: "apps/backend/app/core/dependencies.py"
      provides: "BookingForClientRescheduler Protocol slot + register/accessor"
      contains: "register_booking_for_client_rescheduler"
    - path: "apps/backend/app/modules/client_portal/router.py"
      provides: "POST /booking/{booking_id}/reschedule endpoint"
      contains: "client_reschedule_booking"
    - path: "apps/backend/tests/integration/bookings/test_reschedule_booking_for_client.py"
      provides: "atomic flip, race→409, window→409, cross-trainer→409, IDOR 404, audit, PT-credit-unchanged tests"
      contains: "reschedule"
  key_links:
    - from: "apps/backend/app/modules/client_portal/service.py"
      to: "app.core.dependencies.reschedule_booking_for_client"
      via: "Protocol slot accessor (no direct bookings import)"
      pattern: "reschedule_booking_for_client"
    - from: "apps/backend/app/main.py create_app()"
      to: "bookings_service.reschedule_booking_for_client"
      via: "register_booking_for_client_rescheduler"
      pattern: "register_booking_for_client_rescheduler"
    - from: "apps/backend/app/modules/bookings/service.py audit.emit"
      to: "booking_rescheduled audit row"
      via: "literal event name (INFRA-11 gate)"
      pattern: "\"booking_rescheduled\""
---

<objective>
Implement the atomic reschedule flow end-to-end: the `reschedule_booking_for_client` slot
implementation in `bookings/service.py` (cancel-old + create-new in one UoW, PT-credit preserved),
the `BookingForClientRescheduler` Protocol slot in `dependencies.py` + `main.py` wiring, the
`client_portal/service.py` delegate, the `POST /client/booking/{id}/reschedule` endpoint, and the
full integration test suite.

Purpose: This is the load-bearing correctness work — atomicity, race→409, window/cross-trainer/IDOR
guards, audit emission, and the PRESERVED PT-session credit (a move, not cancel+rebook). Delivers
RESCH-01 + the backend half of RESCH-02.

Output: working endpoint + slot + delegate + tests proving all four error paths and credit preservation.
</objective>

<execution_context>
@/Users/andre/Workspace/Development/clubcore/.claude/get-shit-done/workflows/execute-plan.md
@/Users/andre/Workspace/Development/clubcore/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@.planning/STATE.md
@.planning/phases/80-booking-reschedule/80-CONTEXT.md
@.planning/phases/80-booking-reschedule/80-PATTERNS.md
@.planning/phases/80-booking-reschedule/80-01-SUMMARY.md

<interfaces>
<!-- Contracts from Plan 01 (already shipped in Wave 1) — use directly, no exploration. -->
From app/core/audit_payloads.py:
  BookingRescheduledPayload fields: old_booking_id, new_booking_id, old_slot_id, new_slot_id,
  old_start (str ISO-8601), new_start (str ISO-8601), client_id, actor_role: Literal["client"].
  Registered under ("booking_rescheduled","booking") in AUDIT_PAYLOAD_SCHEMAS + LOCKED_AUDIT_EVENTS.

From app/modules/client_portal/schemas.py:
  ClientRescheduleBookingRequest(ResponseData): new_slot_id: UUID  (extra='forbid', no client_id)
  ClientBookingResponse (reuse): id, slot_id, status, start_time, trainer_name

From app/modules/bookings/notifications.py:
  render_booking_rescheduled_dm(*, client_name, trainer_name, new_slot_start_msk) -> str
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Implement atomic reschedule_booking_for_client in bookings/service.py</name>
  <files>apps/backend/app/modules/bookings/service.py</files>
  <read_first>
    - apps/backend/app/modules/bookings/service.py — create_booking_for_client (~lines 1265-1384), cancel_booking_for_client (~lines 1552-1653), CancelWindowExpiredError + error classes (~lines 133-202), the confirmed/cancelled notification fan-out INSERT (~lines 775-838), `_is_slot_confirmed_conflict` helper, `_booking_response_from_orm`
    - apps/backend/app/modules/bookings/constants.py — CANCEL_WINDOW_HOURS_CLIENT (=24)
    - apps/backend/app/modules/bookings/notifications.py — render_booking_rescheduled_dm (from Plan 01)
    - apps/backend/app/core/audit_payloads.py — BookingRescheduledPayload (from Plan 01)
  </read_first>
  <behavior>
    - reschedule_booking_for_client cancels the old slot (restores it to active) and books the new slot, inserting a new booking row, in one committed UoW
    - <24h before original slot start raises RescheduleWindowExpiredError (code reschedule_window_expired)
    - new slot of a different trainer raises SlotTrainerMismatchError (code slot_trainer_mismatch)
    - new slot already booked at flip raises SlotAlreadyBookedError (code slot_already_booked)
    - non-owned or missing booking raises BookingNotFoundError (code booking_not_found)
    - the new booking row carries the same pt_package_id as the old booking (PT credit preserved — no decrement/restore)
    - audit.emit is called with LITERAL "booking_rescheduled" and "booking", payload linking old→new ids
  </behavior>
  <action>
    Add error classes `RescheduleWindowExpiredError(ConflictError)` (code `reschedule_window_expired`)
    and `SlotTrainerMismatchError(ConflictError)` (code `slot_trainer_mismatch`) near the other
    booking errors. Implement `async def reschedule_booking_for_client(session, *, client_id: UUID,
    booking_id: UUID, new_slot_id: UUID) -> BookingResponse` following the PATTERNS.md step sequence:
    (1) load old booking FOR UPDATE with slot via the existing locking repository fn; (2) IDOR
    404-collapse if None or `client_id` mismatch → `BookingNotFoundError`; (3) FSM guard (booking must
    be confirmed); (4) window guard: if `old_slot.start_time - now_utc < timedelta(hours=CANCEL_WINDOW_HOURS_CLIENT)`
    → `RescheduleWindowExpiredError`; (5) resolve new slot, guard not-found/not-active/in-past; (6)
    same-trainer guard: `new_slot.trainer_id != old_slot.trainer_id` → `SlotTrainerMismatchError`; (7)
    cancel old booking in-place (status cancelled, cancelled_at, cancel_reason="rescheduled") and
    restore old slot to active; (8) flip new slot active→booked via the predicate-gated update;
    (9) INSERT new booking row reusing `pt_package_id=booking.pt_package_id` (PT credit PRESERVED — NO
    sessions_remaining decrement, NO restore); (10) flush, translating IntegrityError via
    `_is_slot_confirmed_conflict` → `SlotAlreadyBookedError`; (11) insert a `booking_notifications`
    row `kind='rescheduled', channel='telegram'` for the new booking (DM via
    `render_booking_rescheduled_dm`, new_slot_start_msk = new_slot.start_time astimezone Moscow,
    strftime "%d.%m.%Y %H:%M"); (12) `audit.emit(session, "booking_rescheduled", actor_user_id=None,
    resource_type="booking", resource_id=new_booking.id, actor_role="client", old_booking_id=...,
    new_booking_id=..., old_slot_id=..., new_slot_id=..., old_start=..., new_start=..., client_id=...)`
    — ALL literal strings for INFRA-11; (13) `await session.commit()` (SVC001); (14) reload new booking
    with slot+trainer joinedload and return `_booking_response_from_orm`. No try/except around domain
    errors — let them bubble.
  </action>
  <verify>
    <automated>cd apps/backend && uv run mypy --strict app/modules/bookings/service.py && uv run ruff check app/modules/bookings/service.py</automated>
  </verify>
  <acceptance_criteria>
    - `reschedule_booking_for_client` exists with the documented signature returning BookingResponse
    - `RescheduleWindowExpiredError`, `SlotTrainerMismatchError` defined with the exact codes
    - `audit.emit` call uses literal `"booking_rescheduled"` and `"booking"` (INFRA-11)
    - new booking row reuses `booking.pt_package_id` (no credit math)
    - `uv run mypy --strict app/modules/bookings/service.py` + `uv run ruff check` exit 0
  </acceptance_criteria>
  <done>Atomic reschedule slot implementation compiles, types clean, PT credit preserved by construction.</done>
</task>

<task type="auto">
  <name>Task 2: Wire BookingForClientRescheduler Protocol slot + client_portal delegate + endpoint</name>
  <files>apps/backend/app/core/dependencies.py, apps/backend/app/main.py, apps/backend/app/modules/client_portal/service.py, apps/backend/app/modules/client_portal/router.py</files>
  <read_first>
    - apps/backend/app/core/dependencies.py — BookingForClientCanceller block (~lines 1521-1574), the full 3-part register/accessor pattern
    - apps/backend/app/main.py — create_app() registration of create/cancel slots (~after line 602)
    - apps/backend/app/modules/client_portal/service.py — create_booking_for_client_request (~lines 429-488), cancel_client_booking (~lines 491-521), the D-20-MODULE imports from app.core.dependencies (~lines 39-46)
    - apps/backend/app/modules/client_portal/router.py — client_create_booking (~lines 337-396), client_cancel_booking (~lines 399-434), idempotency/csrf imports (~lines 41-43)
  </read_first>
  <action>
    In dependencies.py copy the `BookingForClientCanceller` 3-part block verbatim renamed for reschedule:
    type alias `BookingForClientRescheduler = Callable[..., Awaitable[Any]]`, module global
    `_booking_for_client_rescheduler`, `register_booking_for_client_rescheduler(rescheduler)` setter,
    and async accessor `reschedule_booking_for_client(session, *, client_id, booking_id, new_slot_id)
    -> Any` that defensive-raises RuntimeError when the slot is unregistered. In main.py `create_app()`
    add `register_booking_for_client_rescheduler(bookings_service.reschedule_booking_for_client)` next
    to the create/cancel registrations. In client_portal/service.py add `reschedule_booking_for_client`
    to the imports from `app.core.dependencies` and add the delegate `async def
    reschedule_booking_for_client(session, *, client_id, booking_id, new_slot_id) -> ClientBookingResponse`
    that calls the accessor and maps the result onto `ClientBookingResponse` (NO direct
    app.modules.bookings import — D-20-MODULE). In client_portal/router.py add `client_reschedule_booking`
    handler: `POST /booking/{booking_id}/reschedule`, `operation_id="client_reschedule_booking"`,
    response_model `ResponseEnvelope[ClientBookingResponse]`, status 200; RBAC-04 ordering
    `require_client()` → `verify_client_csrf` → `verify_client_idempotency`; body
    `ClientRescheduleBookingRequest`; mirror `client_create_booking`'s `idempotent_execute` runner
    calling `service.reschedule_booking_for_client(session, client_id=client.id, booking_id=booking_id,
    new_slot_id=payload.new_slot_id)`. `client.id` is the only client_id source (no client_id in body).
    No try/except — AppError bubbles to the handler.
  </action>
  <verify>
    <automated>cd apps/backend && uv run mypy --strict app && uv run ruff check app/core/dependencies.py app/main.py app/modules/client_portal/service.py app/modules/client_portal/router.py && uv run lint-imports</automated>
  </verify>
  <acceptance_criteria>
    - `register_booking_for_client_rescheduler` + accessor present in dependencies.py
    - main.py registers the slot in create_app()
    - client_portal/service.py delegate present with NO `app.modules.bookings` import
    - `POST /booking/{booking_id}/reschedule` registered with RBAC-04 ordering + Idempotency-Key dep
    - `uv run lint-imports` exits 0 (zero new ignore_imports)
    - `uv run mypy --strict app` + `uv run ruff check` exit 0
  </acceptance_criteria>
  <done>Endpoint reachable through Protocol slot; import boundary intact; types clean.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 3: Integration tests — atomic flip, race, window, cross-trainer, IDOR, audit, PT-credit</name>
  <files>apps/backend/tests/integration/bookings/test_reschedule_booking_for_client.py</files>
  <read_first>
    - apps/backend/tests/integration/bookings/test_create_booking_for_client.py (happy-path + fixtures)
    - apps/backend/tests/integration/bookings/test_cancel_booking_for_client.py (cancel-flow assertions)
    - apps/backend/tests/integration/bookings/test_booking_race.py (concurrent-flip → slot_already_booked pattern)
    - apps/backend/tests/integration/bookings/test_cancel_sends_dm.py (DM-row assertion pattern)
    - apps/backend/tests/integration/bookings/conftest.py (httpx ASGITransport + client principal + seed fixtures)
  </read_first>
  <behavior>
    - happy path: reschedule returns 200, old booking cancelled, new booking confirmed on new slot, old slot restored to active, new slot booked
    - concurrent reschedule onto a slot another booking claims first → 409 slot_already_booked
    - reschedule when original slot starts in <24h → 409 reschedule_window_expired
    - new slot of a different trainer → 409 slot_trainer_mismatch
    - reschedule of another client's booking → 404 booking_not_found
    - audit_log gains exactly one booking_rescheduled row linking old→new ids
    - PT credit: pt_package sessions_remaining is IDENTICAL before and after reschedule
    - a booking_notifications row kind='rescheduled' exists for the new booking
  </behavior>
  <action>
    Create `test_reschedule_booking_for_client.py` using the bookings integration conftest (httpx
    ASGITransport, pytest-asyncio). Seed a client + trainer + two active slots of the SAME trainer +
    one slot of a DIFFERENT trainer + a PT-package-backed confirmed booking on the original slot.
    Write tests: (1) happy reschedule → 200; assert old booking status cancelled, new booking confirmed
    on new_slot_id, old slot active, new slot booked; (2) race: pre-book the target slot (or simulate
    the predicate-gate failing) → assert 409 `slot_already_booked`; (3) seed the original slot starting
    in <24h → assert 409 `reschedule_window_expired`; (4) target a different-trainer slot → 409
    `slot_trainer_mismatch`; (5) call as a different client principal → 404 `booking_not_found`;
    (6) assert exactly one `booking_rescheduled` audit row with old_booking_id/new_booking_id; (7)
    PT-credit: read `sessions_remaining` of the linked pt_package before and after → assert UNCHANGED;
    (8) assert a `booking_notifications` row with `kind='rescheduled'` for the new booking. Mirror the
    Idempotency-Key + CSRF header setup from test_create_booking_for_client.py.
  </action>
  <verify>
    <automated>cd apps/backend && uv run pytest tests/integration/bookings/test_reschedule_booking_for_client.py -q</automated>
  </verify>
  <acceptance_criteria>
    - All eight test cases pass; file exits 0
    - PT-credit test explicitly asserts sessions_remaining before == after
    - race test asserts HTTP 409 with body code `slot_already_booked`
    - window/cross-trainer/IDOR tests assert the exact codes `reschedule_window_expired` / `slot_trainer_mismatch` and HTTP 404 respectively
    - audit test asserts exactly one `booking_rescheduled` row
  </acceptance_criteria>
  <done>Full reschedule integration suite green, covering atomicity, all error paths, audit, and credit preservation.</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| client → POST /booking/{id}/reschedule | untrusted client supplies booking_id + new_slot_id; principal is the only trusted client_id |
| service → DB slot flip | concurrent clients race for the same target slot (TOCTOU) |
| client_portal → bookings | cross-module access must traverse the Protocol slot only |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-80-05 | Elevation/BOLA (IDOR) | reschedule_booking_for_client | mitigate | client_id sourced from require_client() only; non-owned booking → BookingNotFoundError (404 anti-oracle, never 403); test case 5 asserts |
| T-80-06 | Tampering (TOCTOU/race) | new-slot flip | mitigate | predicate-gated active→booked update + IntegrityError→SlotAlreadyBookedError (no pre-check); 409 slot_already_booked; test case 2 asserts |
| T-80-07 | Tampering (authz window) | original-slot start time | mitigate | <24h vs CANCEL_WINDOW_HOURS_CLIENT against ORIGINAL slot → 409 reschedule_window_expired; test case 3 |
| T-80-08 | Tampering (cross-trainer) | new_slot.trainer_id | mitigate | same-trainer guard → 409 slot_trainer_mismatch; test case 4 |
| T-80-09 | Tampering (replay) | Idempotency-Key | mitigate | verify_client_idempotency + idempotent_execute mirrors client_create_booking (D-70-02) |
| T-80-10 | Spoofing/CSRF | endpoint | mitigate | verify_client_csrf in RBAC-04 ordering |
| T-80-11 | Tampering (PT credit integrity) | pt_package sessions_remaining | mitigate | new booking reuses pt_package_id with NO credit math (move semantics); test case 7 asserts before==after — prevents double-charge AND spurious restore |
| T-80-12 | Repudiation | booking_rescheduled audit | mitigate | single audit event with old→new linkage; literal-string emit (INFRA-11); test case 6 |
| T-80-13 | Elevation (import boundary) | client_portal→bookings | mitigate | Protocol slot only; lint-imports gate, zero new ignore_imports |
| T-80-SC | Tampering | npm/pip/cargo installs | mitigate | no new packages; block on slopcheck human checkpoint if any install appears |

No HIGH-severity unmitigated threat remains.
</threat_model>

<verification>
- `uv run pytest tests/integration/bookings/test_reschedule_booking_for_client.py -q` exits 0
- `uv run mypy --strict app` exits 0
- `uv run ruff check` exits 0
- `uv run lint-imports` exits 0 (zero new ignore_imports — D-20-MODULE)
- ROADMAP success criteria 1, 2, 3 (backend half) satisfied: atomic flip + race 409; window 409 + IDOR 404; audit event + DM row
</verification>

<success_criteria>
RESCH-01 fully delivered (atomic same-trainer reschedule with window/race/cross-trainer/IDOR guards,
PT credit preserved); RESCH-02 backend half delivered (audit event emitted + 'rescheduled' DM row
inserted). ROADMAP success criteria 1-3 proven by the integration suite.
</success_criteria>

<output>
Create `.planning/phases/80-booking-reschedule/80-02-SUMMARY.md` when done.
</output>
