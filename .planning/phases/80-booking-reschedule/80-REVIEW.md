---
phase: 80-booking-reschedule
reviewed: 2026-06-03T00:00:00Z
depth: standard
files_reviewed: 12
files_reviewed_list:
  - apps/backend/alembic/versions/0053_booking_notifications_widen_kind.py
  - apps/backend/app/core/audit_payloads.py
  - apps/backend/app/core/dependencies.py
  - apps/backend/app/modules/bookings/notifications.py
  - apps/backend/app/modules/bookings/service.py
  - apps/backend/app/modules/client_portal/router.py
  - apps/backend/app/modules/client_portal/schemas.py
  - apps/backend/app/modules/client_portal/service.py
  - apps/backend/tests/integration/bookings/test_reschedule_booking_for_client.py
  - apps/client-pwa/src/lib/clientQueries.ts
  - apps/client-pwa/src/screens/sheets/BookingManageSheet.jsx
  - apps/client-pwa/src/screens/sheets/BookingManageSheet.reschedule.test.jsx
findings:
  critical: 2
  warning: 6
  info: 4
  total: 12
status: issues_found
---

# Phase 80: Code Review Report

**Reviewed:** 2026-06-03T00:00:00Z
**Depth:** standard
**Files Reviewed:** 12
**Status:** issues_found

## Summary

Reviewed the v2.2 booking-reschedule slice: the atomic `reschedule_booking_for_client`
orchestrator, its Protocol-slot delegate in `client_portal`, the new `/reschedule`
endpoint, the `booking_rescheduled` audit payload, the reschedule DM renderer, the
`booking_notifications` CHECK-widen migration 0053, and the PWA wiring
(`useRescheduleBooking` + `BookingManageSheet`).

Core atomicity is well-constructed: the cancel-old + create-new sequence runs in one
UoW with a single `session.commit()` (Step 11), the slot-race maps to the partial-UNIQUE
`uq_bookings_slot_confirmed` IntegrityError → 409 `slot_already_booked` (not a TOCTOU
pre-check), and PT-session credit is genuinely preserved (the new row reuses
`booking.pt_package_id` with no `sessions_remaining` mutation). IDOR 404-collapse,
the 24h window guard, and the cross-trainer guard are all present and tested.

However, the post-commit DM/notification block contains a **transaction-state bug** that
can roll back the durable notification commit boundary and surface a 500 on a path the
DM is supposed to make best-effort, and the **idempotency replay contract is broken**
because the response body is materialised AFTER a second commit whose failure mode is
swallowed inconsistently. Several robustness and consistency gaps are noted below.

## Critical Issues

### CR-01: Reschedule DM/notification commit can resurrect a rolled-back session and re-emit / corrupt state

**File:** `apps/backend/app/modules/bookings/service.py:1846-1888`
**Issue:**
After the authoritative reschedule commits at Step 11 (line 1797), the function performs
a SECOND `session.commit()` at Step 14 (line 1863) to persist the `booking_notifications`
evidence row. The `except IntegrityError` branch calls `await session.rollback()`
(line 1865). That rollback is scoped only to the notification INSERT, which is correct —
**but the subsequent Step 15 reload (`get_booking_by_id`, line 1883) and the returned
response then run on a session whose last action was a rollback of a transaction that was
opened lazily AFTER the Step 11 commit.** More importantly, the DM is sent (network I/O,
line 1844) while the DB connection from `get_db` is still checked out and the prior
transaction has committed; the evidence INSERT + commit then runs on the same connection
after an unbounded Telegram round-trip. The reminder-cron path this is "mirroring"
deliberately opens a FRESH session per send (D-39-06b) precisely to avoid holding the
connection across HTTPS I/O and to keep the evidence commit isolated. Reusing the request
session here means:
  1. A transient DB error during the Step 14 commit raises out of the endpoint as a 500
     **even though the reschedule already succeeded and was committed** — the client sees
     a failure for an operation that durably happened (double-submit / duplicate-booking
     risk on retry).
  2. The `except IntegrityError` only catches IntegrityError; any other commit-time error
     (connection reset after the long Telegram I/O, serialization failure) propagates and
     poisons the already-successful response.

**Fix:** Open a fresh session for the post-send evidence INSERT exactly like
`_send_booking_reminders` (D-39-06b), and wrap the whole post-commit DM+evidence block so
no exception can escape the endpoint after the Step 11 commit:
```python
# after Step 11 commit — best-effort, never raises out of the endpoint
try:
    reloaded = await _load_booking_with_relationships(session, new_booking.id)
    ...
    if send_result.ok:
        async with session_factory() as evidence_session:
            try:
                evidence_session.add(BookingNotification(
                    booking_id=new_booking.id, kind="rescheduled", channel="telegram"))
                await evidence_session.commit()
            except IntegrityError:
                await evidence_session.rollback()
                _log.info("booking_reschedule_idempotency_collision", ...)
except Exception as exc:  # fire-and-forget envelope (D-39-09)
    _log.warning("booking_reschedule_dm_post_commit_failed", booking_id=str(new_booking.id),
                 error_msg=str(exc))
```
This requires threading a `session_factory` into the function (or moving the DM dispatch
to the router after the response is built). Either way the durable reschedule must not be
able to fail the HTTP response.

### CR-02: Idempotency replay can store a 500/error envelope for a reschedule that actually succeeded

**File:** `apps/backend/app/modules/client_portal/router.py:481-495` + `service.py:1797-1888`
**Issue:**
The endpoint runs the whole `reschedule_client_booking` call inside `idempotent_execute`'s
`_runner`. `idempotent_execute` stores a SUCCESS envelope only when the runner returns
normally, and on `AppError` stores a replayable error envelope, and on any other
`Exception` deletes the placeholder (router idempotency.py:327-355). Because the
authoritative reschedule commits at Step 11 but the function can still raise AFTER that
commit (see CR-01 — the Step 14 commit or any post-commit reload error), a retry with the
same Idempotency-Key will either:
  - replay a stored error envelope (if the post-commit failure were an AppError — it is
    not today, but the unknown-`Exception` branch deletes the placeholder), or
  - on the unknown-exception branch, delete the placeholder so the NEXT retry RE-RUNS the
    full reschedule against a booking that is already cancelled+rescheduled — Step 2's
    `_assert_can_transition(target="cancelled")` on the now-`cancelled` old booking raises
    `InvalidBookingTransitionError` (409 `invalid_transition`), a code the PWA does not map
    (BookingManageSheet.jsx:317-326 only maps window/slot/trainer codes) → generic
    "Не удалось перенести запись" shown to a user whose reschedule actually succeeded.
The post-commit work MUST NOT be able to raise; otherwise the idempotency envelope does
not reflect the committed state.
**Fix:** Same root remedy as CR-01 — make all work after the Step 11 commit strictly
best-effort (no exception escapes). Then `idempotent_execute` always observes a clean
return and stores the correct success envelope, so retries replay the 200 verbatim. Add a
regression test: call reschedule, force the post-send INSERT to raise, assert the endpoint
still returns 200 and the idempotency replay returns the same 200.

## Warnings

### WR-01: Same-slot reschedule surfaces a misleading `slot_not_available` instead of a no-op / clear error

**File:** `apps/backend/app/modules/bookings/service.py:1724-1730`
**Issue:** When `new_slot_id == booking.slot_id`, Step 4 resolves the old slot, which is
currently `"booked"` (the old booking holds it), so the guard raises
`SlotNotAvailableError("slot_not_available")`. The PWA does not map `slot_not_available`
(BookingManageSheet.jsx:317-326), so the user gets the generic failure copy for what is
really "you picked your current slot." No data corruption, but confusing UX and an
unmapped error code.
**Fix:** Short-circuit `if new_slot_id == booking.slot_id: return <current booking
response>` (idempotent no-op) early, or raise a distinct mapped code.

### WR-02: Post-commit DM holds the DB connection across a Telegram HTTPS round-trip

**File:** `apps/backend/app/modules/bookings/service.py:1843-1863`
**Issue:** `build_bot(...)` + `send_text_dm(...)` (network I/O) run while the request's
`get_db` session/connection is checked out, then the evidence INSERT commits on that same
connection. The cron path it claims to mirror deliberately avoids this (D-39-06b: fresh
session per send to free the connection across I/O). Under load this ties up a pooled
connection for the full Telegram latency on every reschedule.
**Fix:** Send the DM and write evidence on a fresh session (see CR-01), or move DM dispatch
out of the request transaction entirely (post-response / background task).

### WR-03: `_load_booking_with_relationships` is then discarded and a second full reload is issued

**File:** `apps/backend/app/modules/bookings/service.py:1805 + 1883`
**Issue:** Step 12 loads the booking with `client + slot + slot.trainer` joinedloaded
(needed for the DM), then Step 15 issues ANOTHER full SELECT via `get_booking_by_id` just
to build the response (`reloaded` from Step 12 already carries `slot.trainer.full_name`
and `slot.start_time`, which is exactly what `_booking_response_from_orm` needs). This is a
redundant query on every reschedule.
**Fix:** Reuse the Step 12 `reloaded` instance for `_booking_response_from_orm(reloaded)`
and drop the Step 15 reload (`_load_booking_with_relationships` already eager-loads
`slot.trainer`, satisfying the projection contract in `_booking_response_from_orm`).

### WR-04: `BOOKING_RESCHEDULED_DM` ships with an unsatisfied OWNER-COPY-LOCK sign-off marker

**File:** `apps/backend/app/modules/bookings/notifications.py:49-52`
**Issue:** The locked-copy convention (module docstring + every other template) requires a
recorded owner sign-off before merge; this template's comment says
`# OWNER-COPY-LOCK — requires owner sign-off before merge` and the section header says
"(pending owner sign-off before merge)". Per the module's own discipline this should not
merge unsigned. This is a process/quality gate, not a functional defect, but it is an
explicit unmet precondition in the changed code.
**Fix:** Obtain + record the owner sign-off (mirror the `signed-off 2026-05-17 — see
39-01-SUMMARY.md` marker) and update the comment, or hold the merge.

### WR-05: Reschedule gives Telegram-unlinked clients no notification and no email fallback

**File:** `apps/backend/app/modules/bookings/service.py:1820-1825`
**Issue:** When `client.telegram_user_id is None` the function only emits an INFO log and
sends nothing. The lifecycle helper (`_dispatch_booking_lifecycle_notification`) would have
fanned out to email for unlinked-but-email-present clients, but it is deliberately bypassed
because its `enqueue_booking_email_fallback` Literal kind set excludes `'rescheduled'`. The
ROADMAP success criterion is "the reschedule DM is actually sent"; for an email-only client
the move silently produces zero notifications. Whether this is acceptable depends on the
phase contract, but it is an asymmetry versus confirm/cancel that should be deliberate, not
incidental.
**Fix:** If unlinked clients must be notified, extend `enqueue_booking_email_fallback`'s
Literal + add a `'rescheduled'` branch and an `EMAIL_BOOKING_RESCHEDULED` template; else
document the no-fallback decision explicitly at the call site.

### WR-06: PWA same-trainer slot filter keys off a field the booking prop may not carry

**File:** `apps/client-pwa/src/screens/sheets/BookingManageSheet.jsx:28-33`
**Issue:** `candidateSlots` filters `s.trainerName === b.trainerName`, but the fallback
`UPCOMING_BOOKING` mock (and likely the real `booking` prop, which the label code reads via
`b.trainer || b.trainerName` on line 214) exposes `trainer`, not `trainerName`. When `b`
lacks `trainerName`, the filter compares against `undefined` and returns an EMPTY slot list,
showing "Нет доступных слотов" even when same-trainer slots exist. The test passes only
because its fixture sets BOTH `trainer` and `trainerName`. Server-side
`slot_trainer_mismatch` is the real guard, so this is UX-only, but it can fully block the
reschedule UI for real bookings shaped with `trainer` only.
**Fix:** Normalise the comparison: `const bookingTrainer = b.trainerName ?? b.trainer` and
filter `s.trainerName === bookingTrainer`, or match on a stable `trainerId` if the booking
prop carries one.

## Info

### IN-01: `now` captured via `Date.now()` and placed in a `useMemo` dependency array

**File:** `apps/client-pwa/src/screens/sheets/BookingManageSheet.jsx:27-33`
**Issue:** `const now = Date.now()` is computed every render and used as a `useMemo` dep, so
the memo recomputes on every render anyway (the value changes each render). Harmless here
(small list) but the memo provides no benefit and the dependency is misleading.
**Fix:** Drop `now` from deps and compute it inside the memo, or remove the memo.

### IN-02: Migration 0053 issues a no-op `alter_column` (same type → same type)

**File:** `apps/backend/alembic/versions/0053_booking_notifications_widen_kind.py:68-74`
**Issue:** `op.alter_column(... type_=sa.String(32), existing_type=sa.String(32) ...)` is an
intentional no-op kept "for symmetry with 0032." It generates a redundant `ALTER COLUMN
TYPE` that rewrites/validates the column needlessly. The CHECK drop+recreate is the only
required operation. Down-revision chaining (`0052_client_payment_methods`) and the
op.f()-wrapped constraint name are correct.
**Fix:** Remove the no-op `alter_column` (the comment can stay to document that no width
change is needed), or accept the documented symmetry.

### IN-03: Reschedule never re-validates PT-package liveness for the new (later) slot

**File:** `apps/backend/app/modules/bookings/service.py:1757-1766`
**Issue:** Create-paths guard `pt_package.end_date < slot.start_time` (PtPackageExpired-
BeforeSlot) and `sessions_remaining <= 0`. Reschedule reuses `booking.pt_package_id`
without re-checking these against the NEW slot's start_time. A client can reschedule a
confirmed booking to a slot AFTER their PT-package's `end_date`, producing a confirmed
booking the create-path would have rejected. Likely acceptable (credit already committed to
this session), but it is an unstated divergence from the create invariants.
**Fix:** If the expiry invariant must hold on the new slot, re-run the Moscow-TZ
end_date guard against `new_slot.start_time`; else document the intentional skip.

### IN-04: Reschedule audit emits `actor_user_id=None` with no `actor_email_snapshot` for an authenticated client action

**File:** `apps/backend/app/modules/bookings/service.py:1780-1794`
**Issue:** Consistent with the client create/cancel paths (no staff user), `actor_user_id`
is None. There is no client-identity column on `audit_log`, so the only client linkage in
the forensic row is the `client_id` payload field — which is present, so this is acceptable.
Noting for completeness that reschedule, like client create/cancel, has no operator-side
actor attribution by design (D-70-07 parity).
**Fix:** None required; documented for audit-trail expectations.

---

_Reviewed: 2026-06-03T00:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
