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
    - "The client RECEIVES a Telegram DM with the new slot time (send_text_dm called), and a booking_notifications row records the send as evidence"
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
      provides: "atomic flip, race→409, window→409, cross-trainer→409, IDOR 404, audit, PT-credit-unchanged, DM-sent tests"
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
guards, audit emission, the PRESERVED PT-session credit (a move, not cancel+rebook), and the client
RECEIVING the reschedule DM. Delivers RESCH-01 + the backend half of RESCH-02.

Output: working endpoint + slot + delegate + tests proving all four error paths, credit preservation,
and the reschedule DM actually being sent.
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

From app/modules/bookings/service.py (DM-send helpers — Phase 39/45):
  _dispatch_booking_dm(booking, *, template, bot, sender) -> None
    Fire-and-forget Telegram DM. NEVER raises. Renders `template` itself via str.format
    (client_name, trainer_name, slot_start_msk derived from booking.client / booking.slot.trainer).
    Skips when booking.client.telegram_user_id is None (logs booking_dm_skipped_unlinked).
    Requires client + slot.trainer joinedloaded. Inserts NO booking_notifications row.
  sender.send_text_dm(bot, chat_id, text_body) -> SendResult  (the low-level send; .ok / .blocked)
  NOTE: _dispatch_booking_lifecycle_notification CANNOT be reused — its email-fallback branch has
  NO 'rescheduled' case (enqueue_booking_email_fallback's Literal kind set excludes it) and would
  raise ValueError. Use the DM-only path + an explicit send-evidence INSERT instead.
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Implement atomic reschedule_booking_for_client in bookings/service.py</name>
  <files>apps/backend/app/modules/bookings/service.py</files>
  <read_first>
    - apps/backend/app/modules/bookings/service.py — create_booking_for_client (~lines 1265-1384), cancel_booking_for_client (~lines 1552-1653), CancelWindowExpiredError + error classes (~lines 133-202), `_dispatch_booking_dm` (~lines 346-402), the reminder_24h cron Telegram-success post-send INSERT of `BookingNotification(kind=..., channel='telegram')` (~lines 743-786), `_is_slot_confirmed_conflict` helper, `_booking_response_from_orm`, `MOSCOW_TZ`
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
    - when the new booking's client has telegram_user_id set, send_text_dm is called once with the rendered reschedule DM text (containing the new slot time), and a booking_notifications row kind='rescheduled', channel='telegram' is inserted as send-evidence
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
    `_is_slot_confirmed_conflict` → `SlotAlreadyBookedError`; (11) emit `audit.emit(session,
    "booking_rescheduled", actor_user_id=None, resource_type="booking", resource_id=new_booking.id,
    actor_role="client", old_booking_id=..., new_booking_id=..., old_slot_id=..., new_slot_id=...,
    old_start=..., new_start=..., client_id=...)` — ALL literal strings for INFRA-11; (12)
    `await session.commit()` (SVC001); (13) reload the NEW booking with client + slot.trainer
    joinedload (the same eager-load create_booking uses before its DM fan-out, NOT a bare
    get_booking_by_id) — this reloaded instance feeds both the DM and the response; (14) SEND the
    reschedule DM so the client actually RECEIVES it (ROADMAP success criterion 3): when the reloaded
    new booking's `client.telegram_user_id is not None`, build the bot and the telegram sender module
    the same way the lifecycle/reminder paths do, then dispatch the DM. Because `_dispatch_booking_dm`
    renders its own template via the `confirmed`-style placeholders (client_name/trainer_name/
    slot_start_msk) and `render_booking_rescheduled_dm` uses `new_slot_start_msk`, do NOT route through
    `_dispatch_booking_dm`; instead render the text directly with `render_booking_rescheduled_dm(
    client_name=new_booking.client.first_name, trainer_name=new_booking.slot.trainer.full_name,
    new_slot_start_msk=new_slot.start_time.astimezone(MOSCOW_TZ).strftime("%d.%m.%Y %H:%M"))` and
    call `await sender.send_text_dm(bot, new_booking.client.telegram_user_id, text_body)`. Fire-and-
    forget semantics (D-39-09): NEVER let a send failure raise out of the endpoint — on
    `result.ok is False` WARNING-log `booking_dm_send_failed` (reason bot_blocked/transient), mirroring
    `_dispatch_booking_dm`; on telegram_user_id None, INFO-log `booking_dm_skipped_unlinked` and skip
    the send. Do NOT reuse `_dispatch_booking_lifecycle_notification` — its email-fallback branch has no
    'rescheduled' case and would raise ValueError. (15) After a successful send (`result.ok is True`),
    INSERT a send-evidence row mirroring the reminder_24h cron Telegram-success branch (~lines 757-786):
    open a FRESH write session (or reuse the post-commit session shape used there) and
    `add(BookingNotification(booking_id=new_booking.id, kind="rescheduled", channel="telegram"))`,
    commit, and catch `IntegrityError` (duplicate via `uq_booking_notifications_booking_kind_channel`)
    with rollback + INFO-log `booking_reschedule_idempotency_collision` — this row is post-send
    EVIDENCE, not a pre-send intent marker. (16) Return `_booking_response_from_orm(new_booking)` from
    the reloaded instance. No try/except around the domain errors in steps 2-10 — let them bubble; the
    only swallowed failures are the fire-and-forget DM send and the evidence-row IntegrityError.
  </action>
  <verify>
    <automated>cd apps/backend && uv run mypy --strict app/modules/bookings/service.py && uv run ruff check app/modules/bookings/service.py</automated>
  </verify>
  <acceptance_criteria>
    - `reschedule_booking_for_client` exists with the documented signature returning BookingResponse
    - `RescheduleWindowExpiredError`, `SlotTrainerMismatchError` defined with the exact codes
    - `audit.emit` call uses literal `"booking_rescheduled"` and `"booking"` (INFRA-11)
    - new booking row reuses `booking.pt_package_id` (no credit math)
    - the DM is SENT via `sender.send_text_dm` (with text from `render_booking_rescheduled_dm`) when the client is Telegram-linked — NOT merely a tracking row inserted; the `booking_notifications` row is written only AFTER a successful send (post-send evidence)
    - DM send is fire-and-forget: a send failure WARNING-logs and never raises out of the function
    - `uv run mypy --strict app/modules/bookings/service.py` + `uv run ruff check` exit 0
  </acceptance_criteria>
  <done>Atomic reschedule slot implementation compiles, types clean, PT credit preserved by construction, client receives the reschedule DM with the new time.</done>
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
  <name>Task 3: Integration tests — atomic flip, race, window, cross-trainer, IDOR, audit, PT-credit, DM-sent</name>
  <files>apps/backend/tests/integration/bookings/test_reschedule_booking_for_client.py</files>
  <read_first>
    - apps/backend/tests/integration/bookings/test_create_booking_for_client.py (happy-path + fixtures)
    - apps/backend/tests/integration/bookings/test_cancel_booking_for_client.py (cancel-flow assertions)
    - apps/backend/tests/integration/bookings/test_booking_race.py (concurrent-flip → slot_already_booked pattern)
    - apps/backend/tests/integration/bookings/test_cancel_sends_dm.py (send_text_dm monkeypatch / spy + DM-row assertion pattern — mirror this for the reschedule DM)
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
    - DM sent: send_text_dm (the telegram sender) is called exactly once with the rendered reschedule DM text, and that text contains the NEW slot time — assert on the spy's call args, not just that a row exists
    - a booking_notifications row kind='rescheduled', channel='telegram' exists for the new booking as post-send evidence
  </behavior>
  <action>
    Create `test_reschedule_booking_for_client.py` using the bookings integration conftest (httpx
    ASGITransport, pytest-asyncio). Seed a client (WITH telegram_user_id set so the DM path fires) +
    trainer + two active slots of the SAME trainer + one slot of a DIFFERENT trainer + a
    PT-package-backed confirmed booking on the original slot. Monkeypatch / spy the telegram
    `sender.send_text_dm` exactly as test_cancel_sends_dm.py does (stub returning an ok SendResult,
    record call args). Write tests: (1) happy reschedule → 200; assert old booking status cancelled,
    new booking confirmed on new_slot_id, old slot active, new slot booked; (2) race: pre-book the
    target slot (or simulate the predicate-gate failing) → assert 409 `slot_already_booked`; (3) seed
    the original slot starting in <24h → assert 409 `reschedule_window_expired`; (4) target a
    different-trainer slot → 409 `slot_trainer_mismatch`; (5) call as a different client principal →
    404 `booking_not_found`; (6) assert exactly one `booking_rescheduled` audit row with
    old_booking_id/new_booking_id; (7) PT-credit: read `sessions_remaining` of the linked pt_package
    before and after → assert UNCHANGED; (8) DM-sent: assert `send_text_dm` was called exactly once and
    that the `text_body` argument equals `render_booking_rescheduled_dm(...)` for the new slot (assert
    the new slot's MSK time string is a substring of the sent text); (9) assert a `booking_notifications`
    row with `kind='rescheduled'`, `channel='telegram'` exists for the new booking (post-send evidence).
    Mirror the Idempotency-Key + CSRF header setup from test_create_booking_for_client.py.
  </action>
  <verify>
    <automated>cd apps/backend && uv run pytest tests/integration/bookings/test_reschedule_booking_for_client.py -q</automated>
  </verify>
  <acceptance_criteria>
    - All nine test cases pass; file exits 0
    - PT-credit test explicitly asserts sessions_remaining before == after
    - race test asserts HTTP 409 with body code `slot_already_booked`
    - window/cross-trainer/IDOR tests assert the exact codes `reschedule_window_expired` / `slot_trainer_mismatch` and HTTP 404 respectively
    - audit test asserts exactly one `booking_rescheduled` row
    - DM-sent test asserts `send_text_dm` was called once with the rendered reschedule DM text containing the new slot time — not merely that the booking_notifications row exists
  </acceptance_criteria>
  <done>Full reschedule integration suite green, covering atomicity, all error paths, audit, credit preservation, and the client actually receiving the reschedule DM.</done>
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
| T-80-14 | Repudiation (notification delivery) | reschedule DM send | mitigate | send_text_dm called with rendered reschedule text; post-send booking_notifications evidence row keyed by uq_booking_notifications_booking_kind_channel; test case 8 asserts the send (not just the row) |
| T-80-SC | Tampering | npm/pip/cargo installs | mitigate | no new packages; block on slopcheck human checkpoint if any install appears |

No HIGH-severity unmitigated threat remains.
</threat_model>

<verification>
- `uv run pytest tests/integration/bookings/test_reschedule_booking_for_client.py -q` exits 0
- `uv run mypy --strict app` exits 0
- `uv run ruff check` exits 0
- `uv run lint-imports` exits 0 (zero new ignore_imports — D-20-MODULE)
- ROADMAP success criteria 1, 2, 3 (backend half) satisfied: atomic flip + race 409; window 409 + IDOR 404; audit event + client RECEIVES the reschedule DM (send_text_dm called) + send-evidence row
</verification>

<success_criteria>
RESCH-01 fully delivered (atomic same-trainer reschedule with window/race/cross-trainer/IDOR guards,
PT credit preserved); RESCH-02 backend half delivered (audit event emitted + the client RECEIVES a
Telegram DM with the new time + 'rescheduled' send-evidence row inserted). ROADMAP success criteria
1-3 proven by the integration suite — including criterion 3 ("клиент получает DM-уведомление с новым
временем") asserted via the send_text_dm spy.
</success_criteria>

<output>
Create `.planning/phases/80-booking-reschedule/80-02-SUMMARY.md` when done.
</output>
</output>
