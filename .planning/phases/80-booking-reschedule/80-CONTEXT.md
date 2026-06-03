# Phase 80: Booking Reschedule - Context

**Gathered:** 2026-06-03
**Status:** Ready for planning

<domain>
## Phase Boundary

A client can reschedule a confirmed booking to another slot **of the same trainer**. Scope:
a new `POST /client/booking/{id}/reschedule` endpoint that atomically cancels the old slot and
creates a new booking on the new slot in **one** transaction (via a new composition-root
`reschedule_booking_for_client` Protocol slot — NOT an in-place `slot_id` UPDATE); migration 0053
widening the `booking_notifications.kind` CHECK (+ unique constraint) for a new `'rescheduled'`
kind; a `booking_rescheduled` audit event; a reschedule DM template; and PWA wiring of the existing
`BookingManageSheet` to real available slots + the new endpoint (mock calendar removed). Staff
contract frozen; everything under `require_client()`. RESCH-01..03.

</domain>

<decisions>
## Implementation Decisions

### Endpoint Contract & Semantics
- `POST /client/booking/{id}/reschedule`, body `{ new_slot_id }`; returns 200 + the resulting booking (new slot time).
- Reschedule window: reuse `CANCEL_WINDOW_HOURS_CLIENT = 24` (`app/modules/bookings/constants.py`) — block when <24h before the **original** slot start → 409 `reschedule_window_expired`.
- Same-trainer constraint: the new slot must belong to the same trainer as the original booking; cross-trainer → 409 `slot_trainer_mismatch`.
- Idempotency: mirror `client_create_booking` exactly — RBAC-04 ordering `require_client()` → `verify_client_csrf` → `verify_client_idempotency` (Idempotency-Key required, D-70-02).
- IDOR: a non-owned booking id → 404 (anti-oracle), `client_id` from principal only.

### Atomicity, Races & PT-Session Credit
- Single new `reschedule_booking_for_client` Protocol slot performing atomic cancel-old + create-new in **one** UoW (slot implementation owns commit, SVC001).
- Race at flip (new slot taken concurrently) → catch the slot unique/capacity violation → 409 `slot_already_booked` (same pattern as `client_create_booking` D-70-02).
- **PT-session credit is PRESERVED** on reschedule — it is a slot move, not a cancel+rebook. No decrement, no restore; any linked `pt_session`/credit transfers to the new booking row. (Contrast with the WR-06 owner-force-cancel restore path, which is a genuine cancellation.)
- New booking row is created on the new slot (fresh `booking_notifications` slots); the old booking row is marked `cancelled`/rescheduled. The audit event links old→new.

### Notifications, Audit & PWA Wiring
- Emit `booking_rescheduled` audit event with `{ old_slot_id, new_slot_id, old_start, new_start }` (single event, not separate cancelled+created).
- New `render_booking_rescheduled_dm` (in `app/modules/bookings/notifications.py`) carrying the new time; delivered via `booking_notifications` kind `'rescheduled'` (migration 0053 widens the CHECK + the unique constraint already keys on (booking, kind, channel)).
- The old booking's pending 24h reminder lapses naturally (cancelled bookings skip reminders); the new booking gets its own reminder slot. No explicit reminder-row deletion needed.
- PWA: wire the existing `apps/client-pwa/src/screens/sheets/BookingManageSheet.jsx` to real available slots (existing `client_list_slots` GET, filtered to the booking's trainer) + the new reschedule endpoint; remove the mock calendar; optimistic update + toast (mirror the existing cancel-flow wiring + its test).

### Claude's Discretion
- Exact Pydantic schema field names, the Protocol slot signature, audit payload dataclass naming, and PWA component-internal state, following existing `bookings/`, `client_portal/`, and PWA cancel-flow conventions.

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `app/modules/client_portal/router.py` — `client_create_booking` (Idempotency-Key + CSRF + RBAC-04), `client_cancel_booking`, `client_list_slots` are the direct analogs for the new endpoint.
- `app/modules/client_portal/service.py` — `create_booking_for_client_request`, `cancel_booking_for_client` delegates (Phase 70 CBOOK) show the Protocol-slot write pattern; add `reschedule_booking_for_client`.
- `app/modules/bookings/` — `service.py` (slot implementations own commit), `constants.py` (`CANCEL_WINDOW_HOURS_CLIENT=24`), `notifications.py` (DM render fns, e.g. `render_booking_reminder_24h_dm`).
- `booking_notifications` kind CHECK-widening precedent: `alembic/versions/0020_booking_notifications.py` (created), `0032_booking_notifications_widen_kind.py` (widened). Migration 0053 follows this pattern. Unique constraint `uq_booking_notifications_booking_kind_channel` (0024).
- PWA: `apps/client-pwa/src/screens/sheets/BookingManageSheet.jsx` (+ `BookingManageSheet.cancel.test.jsx` as the wiring/test template), `src/data/booking.js`.

### Established Patterns
- Client writes go through composition-root Protocol slots only (D-20-MODULE); zero new `ignore_imports`.
- Slot-booking race → 409 `slot_already_booked` (D-70-02); category-A writes require Idempotency-Key.
- Audit events via `app/core/audit*` with typed payloads; webhook/state changes emit child/root audit rows.

### Integration Points
- New endpoint registered in `client_portal/router.py`; Protocol slot wired at the composition root (`app/core/dependencies.py`) and implemented in `bookings/service.py`.
- Migration 0053 chains from 0052.
- PWA `BookingManageSheet` consumes `client_list_slots` + the new reschedule endpoint via `src/data/booking.js`.

</code_context>

<specifics>
## Specific Ideas

- Reschedule is economically a *move*, not cancel+rebook — PT credit must NOT change (success criteria + explicit user decision). This is the load-bearing correctness rule.
- Same-trainer only (success criterion 1 wording "того же тренера").
- 24h window measured against the ORIGINAL slot start.
- Atomic single transaction; race → 409 `slot_already_booked`; window → 409 `reschedule_window_expired`; cross-trainer → 409 `slot_trainer_mismatch`; non-owned → 404.

</specifics>

<deferred>
## Deferred Ideas

- A formal UI-SPEC design contract was intentionally skipped: `BookingManageSheet` already exists with an established cancel-flow layout + test; Phase 80 is incremental data-wiring (real slot picker + reschedule call + mock-calendar removal), not new visual design. Plan carries concrete PWA acceptance criteria instead.
- `weeklyActivity` / `linkedCard` PWA flag flips + `CardSheet` wiring → Phase 81.
- Multi-trainer reschedule (different trainer) → out of scope (same-trainer only).

</deferred>
