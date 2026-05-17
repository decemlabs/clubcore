# Pitfalls Research

**Domain:** PT-slot booking added to existing gym CRM (Sportzal v1.5)
**Researched:** 2026-05-17
**Confidence:** HIGH — derived from codebase archaeology of v1.2..v1.4 patterns and
the specific REG-*/DEFER-* incidents recorded in MILESTONES.md and PROJECT.md.

---

## Critical Pitfalls

### Pitfall 1: Double-Booking Race — Missing Partial UNIQUE on `bookings`

**What goes wrong:**
Two clients (or the same client from two devices/requests) POST to `POST /bookings` for
the same slot at the same time. Without a DB-level guard the first INSERT from both
transactions passes the app-layer `status='confirmed'` check before either commits.
Both rows land. The trainer now has two confirmed bookings for the same time window.

**Why it happens:**
Developers add an app-layer guard (`SELECT ... WHERE status='confirmed'`) but rely on
Python-level serialisation that does not exist under `asyncio` + `asyncpg`. The v1.2
visits race (VIS-TEST-01) and v1.3 freeze-period race proved the app-layer check is
always the second wall, never the first.

**How to avoid:**
Add a partial UNIQUE index on `bookings (slot_id) WHERE status='confirmed'` in the
Alembic migration. This is the literal mirror of:
- v1.2: `UNIQUE (client_id, gym_date)` on `visits`
- v1.3: partial UNIQUE `(membership_id) WHERE ended_at IS NULL` on `membership_freeze_periods`
- v1.4: partial UNIQUE `(client_id) WHERE status='active'` on `pt_packages`

The booking service's INSERT will raise `IntegrityError` on the loser; the service
translates the discriminated constraint name to `409 slot_already_booked`. A concurrent
race test analogous to VIS-TEST-01 must pass against a real Postgres 16 instance
(not a mock) as part of Phase 37 acceptance.

**Warning signs:**
- Migration file has `UNIQUE(slot_id)` (unconditional) — that forbids ANY second
  booking for a slot, even after cancellation. The partial `WHERE status='confirmed'`
  is essential.
- Service code checks `sessions_remaining > 0` at app-layer without the DB constraint
  as backup.

**Phase to address:** Phase 37 (DB schema + booking creation endpoint).

---

### Pitfall 2: Slot-Overlap at Publish Time Not Caught

**What goes wrong:**
A trainer publishes slot A at 14:00–15:00 on a given day. Later publishes slot B at
14:30–15:30 on the same day. The system accepts both. Now a client books slot A. The
trainer's calendar appears double-booked. Worse: a second client books slot B; both
bookings are confirmed but physically impossible to fulfil.

**Why it happens:**
The publish endpoint checks only uniqueness of `(trainer_id, start_time)` not temporal
overlap. Overlap queries (`start_time < other.end_time AND end_time > other.start_time`)
require an explicit overlap guard or an exclusion constraint.

**How to avoid:**
At slot-publish time add an overlap check using `SELECT ... FOR UPDATE` on the trainer's
existing non-cancelled slots for the same day, or add a Postgres exclusion constraint
`EXCLUDE USING gist (trainer_id WITH =, tstzrange(start_time, end_time, '[)') WITH &&)` —
requires `btree_gist` extension. The simpler app-layer overlap check is acceptable for a
single-zal MVP where concurrent slot publishing is not a hot path:
`SELECT ... WHERE trainer_id=:tid AND start_time < :new_end AND end_time > :new_start AND status != 'cancelled'`
Return `409 overlapping_slot` with the conflicting `slot_id` in the payload.

For trainer-published overlaps BEFORE any booking: catch at publish time (pre-validate
in `schedule.service.publish_slot`). If two overlapping slots were somehow published
before any booking, the `bookings` partial UNIQUE only guards one booking per slot, not
cross-slot booking conflicts. The overlap guard at publish time is the correct place.

**Warning signs:**
- `POST /schedule/slots` has no overlap query; it only checks `start_time != existing`.
- No test for "trainer publishes overlapping window, system rejects."

**Phase to address:** Phase 37 (slot publish endpoint + overlap guard).

---

### Pitfall 3: Audit Events Not Pre-Registered Before First Callsite Commit

**What goes wrong:**
Phase 37 lands `booking_created` emit in `bookings/service.py`. But `LOCKED_AUDIT_EVENTS`
in `app/core/audit.py` still contains only the 51 v1.4 entries. The first request to
`POST /bookings` raises `AuditEventNotLockedError` at runtime. If CI only runs the
unit-test suite (not integration), this surfaces only in the verification gate.

**Why it happens:**
The pattern requires adding all new events to `LOCKED_AUDIT_EVENTS` in Phase 37's
foundation plan BEFORE any callsite lands. v1.3 Phase 24 and v1.4 Phase 30 both did
this correctly — the events were locked in the foundations plan, then emitted in
subsequent plans. The temptation is to add the event and its callsite in the same plan.

**How to avoid:**
The v1.5 foundation plan (first plan of Phase 37) must extend `LOCKED_AUDIT_EVENTS`
with all 5 new pairs before any booking/schedule service code is written:

```python
("slot_published",    "slot"),
("booking_created",   "booking"),
("booking_cancelled", "booking"),
("booking_no_show",   "booking"),
("booking_completed", "booking"),
```

The taxonomy test `tests/unit/test_audit_taxonomy.py` count must be bumped from 51 to 56
in the same commit. The AST literal-string gate catches ad-hoc strings at CI time;
failing to pre-register means the AST gate passes (no unlocked string in code yet) but
the runtime `emit()` call fails on first POST — harder to spot in unit tests that mock
`audit.emit`.

**Warning signs:**
- Phase 37 plan for "booking creation" references `audit.emit("booking_created", ...)`
  without a prior plan that extends the frozenset.
- Taxonomy test count is still 51 when Phase 37 plans 37-02+ land callsites.

**Phase to address:** Phase 37, first plan (foundations/infra bedrock, before any
service implementation plan).

---

### Pitfall 4: PT-Package Refunded With Outstanding Confirmed Bookings

**What goes wrong:**
Client has 3 sessions remaining. They book next Friday. On Wednesday, reception issues
a refund for the PT-package. The PT-package transitions to `cancelled`. The booking is
now orphaned — `confirmed` status but its backing package is gone. The trainer shows up
on Friday; the client either shows up expecting a free session or doesn't; either way
the system is inconsistent.

**Why it happens:**
The v1.4 refund flow (`POST /pt-packages/{id}/refund`) only checks `must_unfreeze_first`
(B-08) and `cannot_refund_renewed_source` (B-09). It has no guard for outstanding
bookings because bookings did not exist in v1.4.

**How to avoid:**
Two acceptable strategies; pick one and document as a Key Decision:

Option A — **Block refund if outstanding bookings exist:**
Before issuing the refund in `pt_packages.service.refund_pt_package`, run a cross-module
raw-SQL count (via `sa.text()`, same D-34-04a discipline to preserve `modules-independent`
contract) against `bookings WHERE pt_package_id=:id AND status='confirmed'`. If count > 0
return `409 outstanding_bookings_exist`. Reception must cancel all bookings first.

Option B — **Auto-cancel bookings on refund:**
The refund service bulk-updates bookings to `cancelled` + emits `booking_cancelled` per
row before or in the same transaction as the refund.

Recommendation: Option A for v1.5. It matches the existing "block-then-explain" pattern
(B-08 `must_unfreeze_first`) and avoids silent auto-cancellations the client might not
notice until the trainer's Friday no-show.

The `bookings` table must expose a `pt_package_id` FK column so this count is trivial.

**Warning signs:**
- `refund_pt_package` in `pt_packages/service.py` has no reference to `bookings` table.
- No test: "refund with outstanding booking → 409".
- No test: "refund after cancelling all bookings → 200".

**Phase to address:** Phase 38 (PT-package linkage + booking-refund interaction guards).

---

### Pitfall 5: Session Returns on Trainer-Cancelled Booking — Causality Inversion

**What goes wrong:**
Client books slot. Trainer gets sick and reception cancels the booking. The booking
transitions to `cancelled`. The PT-package still has `sessions_remaining = N` unchanged
(session was never decremented — decrement is at delivery time, not booking time). No
problem there.

BUT: if the path incorrectly triggers a `pt_session` record first (to "mark it done")
and THEN cancels the booking, the decrement has already fired. The session is consumed
but never delivered. Client loses a session.

The inverse bug: reception records a `pt_session` against a booking, then separately
cancels the booking. Now `sessions_remaining` is decremented AND the booking is
`cancelled`, not `completed`. The booking FSM and the package balance are inconsistent.

**Why it happens:**
The v1.5 design requires that `booking.status = 'completed'` is set AS A CONSEQUENCE of
a `pt_session` being recorded with `booking_id`. If that causality is inverted (booking
cancelled independently after session recorded), the session stands but the booking does
not reflect delivery.

**How to avoid:**
Enforce the FSM causality in `pt_sessions.service.record_pt_session`: when `booking_id`
is provided, the service must atomically set `bookings.status = 'completed'` (via raw
`sa.text()` cross-module SQL, D-34-04a discipline) in the same transaction as the PT-
session INSERT and the package decrement. The booking must be in `confirmed` status at
the time — if it is already `cancelled`, reject with `409 booking_not_confirmed`.

For trainer cancellation: `POST /bookings/{id}/cancel` must check that no `pt_session`
row references this booking (raw SQL count: `SELECT COUNT(*) FROM pt_sessions WHERE
booking_id=:id AND cancelled_at IS NULL`). If one exists: reject with
`409 session_already_recorded`.

**Warning signs:**
- `record_pt_session` in Phase 34 does not reference the `bookings` table (booking_id
  FK on `pt_sessions` does not yet exist in v1.4).
- No test: "cancel booking after session recorded → 409".
- No test: "record session with cancelled booking_id → 409".

**Phase to address:** Phase 38 (PT-package + PT-session + booking causality).

---

### Pitfall 6: `timestamptz` vs `timestamp without time zone` for Slot Times

**What goes wrong:**
Slot start/end times are stored as `TIMESTAMP WITHOUT TIME ZONE` (SQLAlchemy default
`DateTime` without `timezone=True`). The container runs `TZ=UTC`. A slot published as
"18:00 Moscow" is stored as `18:00` with no TZ. When queried from a context that
interprets the bare timestamp as UTC, the slot appears at 21:00 Moscow local (UTC+3).
The no-show cron that marks `no_show` at `slot_end_time + 5min` fires 3 hours late.

**Why it happens:**
SQLAlchemy's `DateTime` column type maps to `TIMESTAMP WITHOUT TIME ZONE` by default.
New developers copy the `DateTime` type without adding `timezone=True`.

**How to avoid:**
Use `DateTime(timezone=True)` in the `trainer_availability_slots` model for `start_time`
and `end_time`. This maps to `TIMESTAMPTZ` in Postgres. The container stores and returns
UTC; the display layer converts to `Europe/Moscow`. Add a CHECK constraint
`end_time > start_time` in the migration.

```python
# Correct:
start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
end_time:   Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

# Wrong (SQLAlchemy default):
start_time: Mapped[datetime] = mapped_column(DateTime(), nullable=False)
```

Note: Moscow has not observed DST since 2014 (UTC+3 year-round), so there are no
DST-transition edge cases. Recurring weekly slots crossing the year boundary are safe
as long as times are stored as TIMESTAMPTZ — the materialised UTC value is unambiguous.

**Warning signs:**
- Migration `0016_trainer_availability_slots` uses bare `TIMESTAMP` not `TIMESTAMPTZ`.
- Slot times look correct in dev but break after a docker-timezone change or psql query.

**Phase to address:** Phase 37 (migration authoring). Non-recoverable post-data-entry
without a data migration.

---

### Pitfall 7: "Within 24h Cancel Window" Computed With Naive Datetime

**What goes wrong:**
`datetime.utcnow()` (naive UTC) compared with `slot.start_time` (TIMESTAMPTZ — asyncpg
returns timezone-aware). In Python 3.12 this raises a `TypeError: can't compare
offset-naive and offset-aware datetimes` at runtime on the first cancel attempt.
Developers "fix" this by stripping `tzinfo` — breaking correctness silently.

**Why it happens:**
`datetime.utcnow()` is deprecated in Python 3.12 precisely because it produces naive
datetimes. The v1.4 `record_pt_session` backdating window correctly uses
`datetime.now(UTC)` (aware). New code in bookings may not follow this discipline.

**How to avoid:**
Use `datetime.now(UTC)` throughout the bookings service. The 24h window check:

```python
from datetime import UTC, datetime, timedelta

now_utc = datetime.now(UTC)
if slot.start_time - now_utc < timedelta(hours=24):
    raise ConflictError("cancellation_window_exceeded")
```

This mirrors v1.4 `CANCEL_WINDOW_HOURS_RECEPTION = 24` constant in
`app/modules/pt_sessions/constants.py`. Add the same constant to
`app/modules/bookings/constants.py`.

**Warning signs:**
- `datetime.utcnow()` anywhere in bookings/schedule service.
- Tests use naive `datetime(2026, 5, 17, 14, 0)` rather than
  `datetime(2026, 5, 17, 14, 0, tzinfo=UTC)`.

**Phase to address:** Phase 38 (booking cancel endpoint). Enforce via mypy strict.

---

### Pitfall 8: FSM Illegal Transition `cancelled → completed` Without Guard

**What goes wrong:**
A booking is cancelled. The trainer records a PT-session for that booking by mistake.
`pt_sessions.service` receives the "set completed" callback for the booking. Without a
WHERE predicate guard, the booking transitions from `cancelled → completed` — an illegal
FSM move. The booking now appears "completed" and the PT-package was decremented for an
undelivered session.

**Why it happens:**
The `completed` transition is triggered by an external event (PT-session creation), not
by a direct API call. Without a pre-condition check that the booking is `confirmed`, the
trigger fires regardless of current status.

**How to avoid:**
Declare `BOOKING_STATUS_TRANSITIONS` (mirror of `MEMBERSHIP_STATUS_TRANSITIONS` from
v1.3 Phase 24 and `PT_PACKAGE_STATUS_TRANSITIONS` from v1.4 Phase 33) in
`app/modules/bookings/constants.py`:

```python
BOOKING_STATUS_TRANSITIONS: dict[str, frozenset[str]] = {
    "confirmed":  frozenset({"cancelled", "no_show", "completed"}),
    "cancelled":  frozenset(),   # terminal
    "no_show":    frozenset(),   # terminal (see Pitfall 9 for review exception)
    "completed":  frozenset(),   # terminal
}
```

Add a central `_assert_can_transition(current, target)` guard in
`app/modules/bookings/service.py` that raises `409 invalid_transition`. The PT-session
service's "set completed" SQL path uses `WHERE booking_id=:id AND status='confirmed'`
predicate — 0 rows updated means `409 booking_not_confirmed`. The guard applies to BOTH
the direct API path and the PT-session-triggered path.

Idempotent cancel: second `cancel(booking)` call should return `409 already_cancelled`
to be explicit, matching `must_unfreeze_first` and `invalid_transition` patterns.

**Warning signs:**
- No `BOOKING_STATUS_TRANSITIONS` constant.
- `UPDATE bookings SET status='completed'` SQL has no `WHERE status='confirmed'` predicate.
- No state-machine matrix test (the v1.3 16-cell matrix for memberships is the template).

**Phase to address:** Phase 37 (booking FSM constants must land before any transition
callsite in Phase 38).

---

### Pitfall 9: `no_show` Reverse-Transition Policy Undefined Before Cron Ships

**What goes wrong:**
The no-show cron marks all overdue `confirmed` bookings as `no_show`. At 23:10 the
trainer says "actually the client arrived late." Reception tries to record a PT-session
against the now-`no_show` booking. The service rejects with `booking_not_confirmed`.
The session cannot be recorded, the client loses a session, and the trainer is angry.

**Why it happens:**
`no_show` is defined as terminal without a documented policy for late-arrival reversals.
The v1.4 precedent `exhausted → active` (D-34-11a in `cancel_pt_session`) shows that
reverse transitions can be justified but must be predicate-gated and explicitly logged.

**How to avoid:**
Before the cron ships, lock the policy as a Key Decision:

- Option A: Allow `no_show → confirmed` reverse transition (owner+reception) within a
  configurable window (e.g. 4h after `slot_end_time`). Add `POST /bookings/{id}/reopen`
  endpoint. This mirrors D-34-11a.
- Option B: Allow PT-session recording against a `no_show` booking as an implicit
  `no_show → completed` transition (one-way; reception acknowledges it was delivered
  late). Simpler API surface.
- Option C: No reverse transition in v1.5 (acceptable for MVP). Document explicitly in
  `bookings/constants.py` with a comment directing future developer to a Key Decision.

Whatever is chosen, add a test for the chosen policy before Phase 39 ships.

**Warning signs:**
- No explicit policy decision in PROJECT.md.
- No test for "record PT-session against no_show booking."

**Phase to address:** Phase 37 (define policy in constants) + Phase 39 (cron ships;
policy must be in place first).

---

### Pitfall 10: Telegram Bot Missing `register_active_pt_package_resolver` (REG-29-03 Repeat)

**What goes wrong:**
The Telegram bot worker's `main()` does not call `register_active_pt_package_resolver(...)`
(and possibly also misses any new `register_booking_slot_resolver`). The bot's `/book`
command calls `get_active_pt_package(session, client_id)` which returns `None` because
the slot is empty. The service raises `409 no_active_pt_package`. In sandbox testing the
bot silently fails with no DM to the user.

**Why it happens:**
This is literally REG-29-03 repeated: in v1.3 the bot worker was missing
`register_active_membership_resolver` registration. The fix (`f3cd01f`) double-wired
all resolver registrations from BOTH `app.main.create_app()` AND
`app.workers.telegram_bot.main()`. In v1.4 Phase 31, `register_trainer_by_id_resolver`
was added defensively to both even though the bot wasn't a trainer-consumer. In v1.5
the bot IS a booking consumer.

**How to avoid:**
After adding any resolver registration to `app.main.create_app()`, immediately add the
same registration to `app.workers.telegram_bot.main()`. For v1.5 this means:
- `register_active_pt_package_resolver` (already in `app.main` since Phase 33, must be
  confirmed present in `telegram_bot.py:main()` — it is not currently there; check line
  count against `app.main`)
- Any new booking/slot resolver needed by the bot `/book` flow

The milestone verification phase must exercise `/book` via a real Telegram sandbox, not
just the HTTP API (same discipline as Phase 29 REG-29-03 discovery).

**Warning signs:**
- `telegram_bot.py:main()` registers fewer resolvers than `main.py:create_app()`.
- Milestone verification phase does not test `/book` via Telegram sandbox.

**Phase to address:** Phase 40 (Telegram `/book`) — verify both registration sites.
Add defensive comment in `telegram_bot.py` naming all v1.5 required resolvers.

---

### Pitfall 11: One-Shot CLI Runner Missing Eager ORM Model Import (REG-29-04 Repeat)

**What goes wrong:**
`scripts/run_no_show_cron_once.py` runs the `mark_no_show_bookings` ARQ job in isolation
for operator verification. The first invocation processes 0 rows. The operator assumes
no overdue bookings exist. In fact the SQLAlchemy mapper for `Booking` was never imported
before the query ran — no mapper registration, query returns empty result, no error.

**Why it happens:**
This is REG-29-04 repeated: the v1.3 `run_expiring_cron_once.py` had the same bug
(fix `1dfc7a8`). SQLAlchemy's class mapper registry is populated lazily when the model
module is imported. A standalone script that imports only the ARQ job function never
triggers the mapper import; ORM-level operations silently return no rows.

**How to avoid:**
Add an explicit `import app.modules.bookings.models  # noqa: F401 — eager mapper` at
the top of every one-shot runner script that touches the `bookings` table. Mirror the
existing fix in `run_expiring_cron_once.py`. Add a test that runs the one-shot script
against an in-memory test DB and asserts non-zero processing when bookings are present.

**Warning signs:**
- `scripts/run_no_show_cron_once.py` has no model import before calling the cron function.
- One-shot runner returns `count=0` on first run against a seeded DB.

**Phase to address:** Phase 39 (no-show cron one-shot runner creation).

---

### Pitfall 12: No-Show Cron Race With Concurrent PT-Session Recording

**What goes wrong:**
The no-show cron fires at 23:00. In the same moment reception records a PT-session
against the same booking. Two concurrent transactions:

- Cron: `UPDATE bookings SET status='no_show' WHERE status='confirmed' AND end_time < now()`
- Reception: `UPDATE bookings SET status='completed' WHERE id=:id AND status='confirmed'`

The cron wins the row lock. Reception's UPDATE sees 0 rows (booking is now `no_show`).
Service raises `409 booking_not_confirmed`. The PT-session INSERT has already fired.
The decrement has already fired. The booking is `no_show` but a `pt_sessions` row exists.

**Why it happens:**
Both the cron and the reception endpoint can simultaneously UPDATE the same booking row.
The cron's batch `WHERE status='confirmed' AND end_time < now()` holds a row lock only
for the duration of the single UPDATE statement — long enough to win the race against
the concurrent session-record transaction.

**How to avoid:**
The PT-session creation path must use `SELECT ... FOR UPDATE` on the booking row first
(acquires a row-level lock), verify `status='confirmed'`, INSERT the session, THEN
`UPDATE bookings SET status='completed'`. The cron's competing `UPDATE bookings WHERE
status='confirmed'` will block on the row lock until the session transaction commits.
One wins cleanly.

The cron is already idempotent by the predicate: a booking set to `completed` will not
match `WHERE status='confirmed'` on a re-run. No additional cron logic needed.

**Warning signs:**
- `record_pt_session` does not `SELECT ... FOR UPDATE` the booking row before INSERT.
- No concurrent race test: "cron + PT-session record same booking simultaneously."

**Phase to address:** Phase 38 (booking completion causality) + Phase 39 (no-show cron).

---

### Pitfall 13: Audit UUID Stringify Bug (REG-36-03 Repeat)

**What goes wrong:**
`audit.emit("booking_created", ..., booking_id=booking.id, slot_id=slot.id, ...)` — the
values are Python `UUID` objects, not strings. The Pydantic `BookingCreatedPayload`
schema has `booking_id: str` but the callsite passes `UUID`. Depending on Pydantic v2
coercion config this either raises a `ValidationError` → 500 or stores the UUID repr
`UUID('...')` string in the `jsonb` column — breaking read-back.

This is REG-36-03 verbatim: `pt_sessions/service.py` had `pt_session_id=pt_session.id`
(raw UUID) instead of `pt_session_id=str(pt_session.id)`. Fix was immediate stringify.

**How to avoid:**
Define `SlotPublishedPayload`, `BookingCreatedPayload`, `BookingCancelledPayload`,
`BookingNoShowPayload`, `BookingCompletedPayload` in `app/core/audit_payloads.py`
(extending the v1.4 registry) with all `id` fields typed as `str`. At callsite stringify
UUID values explicitly:

```python
await audit.emit(
    session, "booking_created",
    actor_user_id=current_user.id,
    resource_type="booking",
    resource_id=booking.id,
    booking_id=str(booking.id),      # <-- stringify
    slot_id=str(slot.id),
    client_id=str(client_id),
    pt_package_id=str(pt_package_id),
)
```

Add a test that calls `emit()` with all 5 new event types using the exact kwargs and
asserts no exception is raised (mirrors the existing `test_audit_taxonomy.py` pattern).

**Warning signs:**
- `audit_payloads.py` does not have entries for the 5 new booking/slot events.
- Callsites pass `UUID` objects directly without `str(...)`.

**Phase to address:** Phase 37 (foundation plan: add payload schemas to `audit_payloads.py`
at the same time as extending `LOCKED_AUDIT_EVENTS`).

---

### Pitfall 14: Idempotency Key Not Route-Bound for Booking Creation

**What goes wrong:**
The `POST /bookings` endpoint manually reads `request.headers.get("idempotency-key")`
instead of using `Depends(verify_idempotency)`. The raw header value is used as the
Redis key: `sz:idem:{raw_value}`. A client sends key `"abc123"` to `POST /bookings`,
gets a network error, and retries with `"abc123"` to `POST /pt-sessions`. Because both
routes share the same flat namespace, the cached booking response is replayed for the
PT-session request. The PT-session record is never created; the PT-package is not
decremented.

This is the CR-01 carry-over from Phase 33: `verify_idempotency` returns
`f"{method}:{path}:{key}"` — the route-binding was added specifically to prevent
cross-route replay. Bypassing `Depends(verify_idempotency)` loses this guarantee.

**How to avoid:**
The `POST /bookings` router must use:
```python
idempotency_key: Annotated[str, Depends(verify_idempotency)],
```
exactly as `pt_sessions/router.py` does. No manual header access.

**Warning signs:**
- `bookings/router.py` uses `request.headers.get("idempotency-key")` directly.
- Test reuses the same `Idempotency-Key` across `/bookings` and `/pt-sessions` and does
  not verify independence.

**Phase to address:** Phase 38 (booking creation endpoint).

---

### Pitfall 15: Telegram Bot `/book` callback_data Length Overflow

**What goes wrong:**
Telegram Bot API inline keyboard `callback_data` has a hard limit of 64 bytes. A slot
UUID is 36 characters. `"book:{slot_uuid}"` = 41 bytes (safe). But
`"book:{slot_uuid}:{pt_package_uuid}"` = 78 bytes — exceeds the limit. The inline
keyboard button exists but clicking it produces no callback event.

**Why it happens:**
Developers compose `callback_data` naively from business IDs without checking the limit.
The Bot API does not reject the `sendMessage` call; oversized `callback_data` is silently
truncated or the button fires no event.

**How to avoid:**
Use a compact prefix + single UUID: `"BK:{slot_uuid}"` = 39 bytes — within limit.
The booking service resolves the client's active PT-package at callback time via the
existing `get_active_pt_package` resolver (the client identity comes from
`telegram_user_id`, the package is resolved server-side — it does not need to be in
the `callback_data`).

Assert `len(callback_data.encode("utf-8")) <= 64` in a unit test for every inline
keyboard builder function in the bot.

**Warning signs:**
- `callback_data` contains two or more UUIDs.
- No unit test asserting byte length of all keyboard `callback_data` strings.

**Phase to address:** Phase 40 (Telegram `/book` implementation).

---

### Pitfall 16: Telegram Bot Anti-Oracle Leak for "No Active PT-Package"

**What goes wrong:**
Client sends `/book` without an active PT-package. Bot responds:
"У вас нет активного пакета ПТ. Приобретите у рецепции."
Client sends `/book` with a valid package but no available slots. Bot responds:
"Нет доступных слотов."

These are different messages. A non-client who has linked their Telegram account can now
distinguish "linked but no package" from "linked with package, no slots" — enabling
inference about the gym's PT-package inventory and client status. This mirrors the
v1.2 D-20-9 oracle that was deliberately closed: same DM for stranger and
expired-membership in `/checkin`.

**How to avoid:**
Use a single locked Russian DM constant for all negative booking outcomes:

```python
_DM_NO_BOOKING_AVAILABLE = "Нет доступных слотов для записи."
```

This DM fires for: no PT-package, no sessions remaining, no available slots, package
expired. The absence of detail prevents enumeration. The copy must be a locked constant
(not an f-string or inline literal) and must be owner-signed in a `D-40-OWNER-COPY-LOCK`
Key Decision entry before Phase 40 merges.

**Warning signs:**
- Different DM strings for different negative outcomes in `/book` handler.
- DM copy is an inline string literal instead of a named constant.
- No owner sign-off row in PROJECT.md for bot copy.

**Phase to address:** Phase 40. Copy must be locked before PR merges.

---

### Pitfall 17: Composition Root Resolver Registered After Router Mounts

**What goes wrong:**
`app.main.create_app()` calls `include_router(api)` before registering the new
`register_booking_slot_resolver(...)`. The first request to `GET /schedule/slots`
triggers a resolver call; the slot is `None` — `NotImplementedError` (or silent `None`
return, which is worse — returns empty results with no error).

**Why it happens:**
`include_router` is registration at `create_app()` time; resolver slots are plain module-
level globals. The convention in every prior milestone is to register resolvers BEFORE
`include_router`. The numbered-step docstring in `app/main.py` enforces this but only
if it is updated.

**How to avoid:**
Add resolver registrations for Schedule and Bookings modules BEFORE `api.include_router`
in `create_app()`. Update the `app/main.py` docstring numbered step list to include the
new slots. Add a startup integration test that calls `create_app()` and asserts all
resolver slots are non-None after the factory returns.

**Warning signs:**
- `create_app()` docstring numbered steps do not include new booking/schedule resolvers.
- `NotImplementedError` on first request to any Schedule or Bookings endpoint.

**Phase to address:** Phase 37 (Protocol slot definition + composition root wiring,
before any router is written).

---

### Pitfall 18: PT-Package Validity Expiry Between Booking and Slot Time

**What goes wrong:**
Client has a PT-package with `validity_days=30`, `end_date = 2026-06-15`. They book a
slot for `2026-06-20`. On the slot day the package is `expired` (ARQ cron ran on
June 16). `record_pt_session` fails with `409 pt_package_not_active`. The client shows
up; the trainer is there; nothing can be recorded.

**Why it happens:**
Booking validation checks `sessions_remaining > 0` and `status='active'` at booking
creation time. It does not compare the slot date against the package's validity window.

**How to avoid:**
At booking creation time, if the package has a non-NULL `end_date`, validate:
`slot.start_time.date() <= pt_package.end_date` (Europe/Moscow date comparison).
If the slot is outside the validity window reject with `422 slot_outside_package_validity`.
Reject at booking time, not at delivery time — better UX, same principle as the v1.3
`plan_archived` check at renewal time rather than at check-in time.

**Warning signs:**
- `bookings/service.py` only checks `sessions_remaining > 0` and `status='active'`.
- No test: "book slot beyond package `end_date` → 422."

**Phase to address:** Phase 38 (booking creation validation).

---

### Pitfall 19: N+1 on "Trainer's Upcoming Slots + Bookings" Query

**What goes wrong:**
`GET /schedule/slots?trainer_id=X` returns 20 slots. The response includes each slot's
current booking (client name, status). The service iterates 20 slots and for each
calls `session.get(Booking, slot_id=slot.id)` — 20 additional SELECTs. Under any
load this is a predictable performance problem.

**Why it happens:**
SQLAlchemy lazy-load default: accessing `slot.booking` on an ORM object triggers an
additional SELECT per object.

**How to avoid:**
Use `joinedload(TrainerAvailabilitySlot.booking)` in the repository list query, or
write a single JOIN that returns slot + booking data in one round-trip. The v1.4
`list_memberships` with `joinedload` is the template. Assert in a repository unit test
that fetching 20 slots emits exactly 1 (or 2) DB queries, not 21.

**Warning signs:**
- `repository.list_slots` uses bare `select(TrainerAvailabilitySlot)` without
  `options(joinedload(...))`.
- Response time grows linearly with slot count in load tests.

**Phase to address:** Phase 37 (slot list query design).

---

### Pitfall 20: B-10 Regression — Booking Must Not Grant Floor Access

**What goes wrong:**
A client has a PT-package but no active membership. They book a PT-slot. A developer
adds a "check for active PT-package" fallback to the visits resolver so PT-package
holders can enter the gym. B-10 is violated: PT-package alone does NOT grant floor
access. The constraint is maintained by ABSENCE — `visits/service.py` only calls
`resolve_active_membership_by_client`, never the PT-package resolver.

**Why it happens:**
Reception reports that a client "has a PT booking for today" and the developer interprets
this as justification to allow floor access. The rule is that PT-session recording (which
happens in the training room) is separate from gym-floor access (controlled by memberships).

**How to avoid:**
Keep `visits/service.py` touching only the membership resolver — no reference to
`pt_packages` table or the PT-package resolver. Add a comment in `visits/service.py`:
`# B-10 (PROJECT.md): PT-package alone does NOT grant gym floor access. Do NOT add PT-package resolver here.`

Verify the B-10 test still passes after every Phase 37–40 change: "client with active
PT-package but no membership → `POST /visits` → 409 no_active_membership."

**Warning signs:**
- `visits/service.py` references `pt_packages` or `get_active_pt_package`.
- The B-10 regression test is absent or commented out.

**Phase to address:** Phase 37 (foundation audit confirm B-10 test exists and passes).

---

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|---|---|---|---|
| App-layer overlap check at slot publish (not Postgres exclusion constraint) | No `btree_gist` extension setup needed | Race between two simultaneous publishes by the same trainer possible | Acceptable for v1.5 single-gym low-concurrency; add exclusion constraint in v2.0 if trainers self-publish at scale |
| Raw `sa.text()` for cross-module booking updates in `pt_sessions.service` | Preserves `modules-independent` import-linter contract | Schema drift if `bookings` table is renamed; no ORM type safety | Acceptable per D-34-04a precedent — document with `# noqa: TABLE_REF cross-module SQL` comment |
| No-show cron batch UPDATE without per-row `SELECT FOR UPDATE` | Simple batch UPDATE | Race with concurrent PT-session recording (Pitfall 12) | Never — use row-level lock in the session-record path |
| Skipping `Idempotency-Key` requirement on `POST /bookings` | Simpler endpoint | Duplicate booking on network retry | Never — booking is a mutation |
| Storing `pt_package_id` as nullable FK on bookings (future: bookings without packages) | Allows future non-PT bookings | Refund guard count query requires `IS NOT NULL` filter | Acceptable for v1.5 if documented; make NOT NULL now if all v1.5 bookings require a package |

---

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|---|---|---|
| `pt_sessions.service` ↔ `bookings` | Import `Booking` ORM from bookings module | Use raw `sa.text()` with `WHERE booking_id=:id` (D-34-04a discipline — no cross-module ORM import) |
| `pt_packages.service` ↔ `bookings` | Check outstanding bookings via ORM cross-import | `SELECT COUNT(*) FROM bookings WHERE pt_package_id=:id AND status='confirmed'` via `sa.text()` |
| ARQ no-show cron ↔ app state | Pass wrong key from ARQ `ctx` | Use `ctx['sessionmaker']` same as `expire_pt_packages` cron in Phase 33 |
| Telegram `/book` ↔ bookings service | Import `bookings.service` directly in `telegram_bot.py` | Wire via Protocol slot + composition root; bot calls through `HandlerContext` (same D-06/D-10 pattern) |
| Idempotency key ↔ booking + pt_session creation | Share one key across both endpoints | Two separate keys: one for `POST /bookings`, one for `POST /pt-sessions` when delivering the booked session |

---

## Performance Traps

| Trap | Symptoms | Prevention | When It Breaks |
|---|---|---|---|
| N+1 on slot list + bookings | Slow `GET /schedule/slots?trainer_id=X` | `joinedload(slot.booking)` or single JOIN query | > 10 slots per trainer per query |
| N+1 on "owner dashboard all bookings today" | Slow dashboard load | `joinedload(booking.slot, booking.client)` | > 20 bookings per day |
| No-show cron UPDATE without index on `(status, end_time)` | Full table scan at cron time | Add `ix_bookings_status_end_time` composite index in migration | > 500 bookings in table |
| Counting confirmed bookings for refund guard on every refund | Slow if large booking history | Index `(pt_package_id, status)` on bookings table | > 50 bookings per package |

---

## Security Mistakes

| Mistake | Risk | Prevention |
|---|---|---|
| Different DM for "no PT-package" vs "no slots" in Telegram `/book` | Account enumeration: attacker learns client's package status | Single anti-oracle DM for all negative booking outcomes (Pitfall 16) |
| Returning `client_id` in public slot list | Exposes which clients have booked future sessions | Slot list returns `is_available: bool` only; booking details are RBAC-gated (owner/reception) |
| Missing `require_permission` on `POST /bookings` | Any authenticated user can book without package validation | RBAC: `(CREATE, BOOKINGS)` required; validation in service (not only RBAC) |
| Booking cancellation does not verify booking ownership | Any reception user can cancel any client's booking | Check `booking.created_by_user_id == current_user.id OR current_user.role == owner`; or accept this for gym-staff context (reception = trusted) |

---

## "Looks Done But Isn't" Checklist

- [ ] **Partial UNIQUE on bookings:** Migration has `WHERE status='confirmed'` — run concurrent booking race test (real Postgres 16, not mock).
- [ ] **LOCKED_AUDIT_EVENTS extended to 56:** Count in `test_audit_taxonomy.py` bumped before any callsite lands.
- [ ] **5 audit payload schemas in `audit_payloads.py`:** `SlotPublishedPayload`, `BookingCreatedPayload`, `BookingCancelledPayload`, `BookingNoShowPayload`, `BookingCompletedPayload` — all with `extra='forbid'` + UUID fields typed as `str`.
- [ ] **Telegram bot resolver double-wiring:** `telegram_bot.py:main()` registers `register_active_pt_package_resolver` AND any new booking resolver — count matches `main.py:create_app()`.
- [ ] **No-show cron one-shot runner:** `scripts/run_no_show_cron_once.py` imports `app.modules.bookings.models` before first query.
- [ ] **`timestamptz` in migration:** `trainer_availability_slots.start_time` and `end_time` are `TIMESTAMPTZ` in raw Alembic SQL.
- [ ] **B-10 test still passes:** `POST /visits` for client with active PT-package but no membership returns `409 no_active_membership`.
- [ ] **`Idempotency-Key` required on `POST /bookings`:** Router uses `Depends(verify_idempotency)` not manual header access.
- [ ] **Telegram `callback_data` <= 64 bytes:** Unit test asserts `len("BK:{uuid}".encode()) <= 64` for all bot keyboard builders.
- [ ] **`bookings` has `pt_package_id` FK column:** Required for refund guard and validity-expiry validation.
- [ ] **`BOOKING_STATUS_TRANSITIONS` constant defined before any service uses it:** Same discipline as v1.3 Phase 24 / v1.4 Phase 30.
- [ ] **Composition root docstring updated:** `app/main.py` numbered steps include new Schedule and Bookings resolver registrations.
- [ ] **Owner DM copy locked:** Anti-oracle Telegram DM constant is a named constant with `D-40-OWNER-COPY-LOCK` sign-off in PROJECT.md.

---

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---|---|---|
| Missing partial UNIQUE discovered post-data-entry | MEDIUM | Write migration adding the constraint; deduplicate existing `confirmed` duplicates manually first; add concurrent race test |
| `timestamp without time zone` slots discovered in prod | HIGH | Migration: `ALTER COLUMN start_time TYPE TIMESTAMPTZ USING start_time AT TIME ZONE 'Europe/Moscow'`; verify offset correctness on all rows |
| REG-29-03 repeat (bot missing resolver) | LOW | Add resolver registration in `telegram_bot.py:main()`, redeploy bot worker container only |
| REG-29-04 repeat (cron runner 0-row) | LOW | Add `import app.modules.bookings.models` to one-shot script; no DB migration needed |
| REG-36-03 repeat (UUID stringify in audit) | LOW | Add `str(...)` at callsite; hotfix commit; confirm `test_audit_taxonomy.py` green |
| Illegal FSM transition in prod data | MEDIUM | Write one-time SQL correction; add transition guard; add regression test |
| Double-booking in prod (missing partial UNIQUE) | HIGH | Identify duplicate confirmed bookings; cancel the later one; contact affected trainer and client; add constraint migration |
| PT-package refunded with orphaned bookings | MEDIUM | Manually cancel orphaned bookings via SQL; add refund guard; document policy |

---

## Pitfall-to-Phase Mapping

| Pitfall | Prevention Phase | Verification |
|---|---|---|
| P1: Double-booking race — missing partial UNIQUE | Phase 37 (migration) | Concurrent race test against real Postgres 16 (mirrors VIS-TEST-01) |
| P2: Slot overlap at publish time | Phase 37 (slot publish endpoint) | Test: publish overlapping slot → 409 overlapping_slot |
| P3: Audit events not pre-registered | Phase 37 (foundations plan, first plan) | `test_audit_taxonomy.py` count == 56 from first commit |
| P4: PT-package refunded with outstanding bookings | Phase 38 (refund guard) | Test: refund with confirmed booking → 409 outstanding_bookings_exist |
| P5: Session/booking causality inversion | Phase 38 (PT-session + booking completion) | Test: cancel booking with existing session → 409; record session with cancelled booking → 409 |
| P6: `timestamp without time zone` for slots | Phase 37 (migration authoring) | `psql \d trainer_availability_slots` shows `timestamp with time zone` |
| P7: 24h cancel window naive datetime | Phase 38 (cancel endpoint) | Test: cancel at exactly 24h boundary using `datetime.now(UTC)` |
| P8: FSM illegal transition without guard | Phase 37 (BOOKING_STATUS_TRANSITIONS constant) | State-machine matrix test; UPDATE SQL has `WHERE status='confirmed'` predicate |
| P9: `no_show` reverse-transition policy undefined | Phase 37 (policy decision) + Phase 39 (cron) | Key Decision row in PROJECT.md; test for chosen policy |
| P10: Bot missing resolver (REG-29-03 repeat) | Phase 40 (Telegram `/book`) | Milestone verification: `/book` works end-to-end in Telegram sandbox |
| P11: One-shot runner missing import (REG-29-04 repeat) | Phase 39 (cron runner) | Run one-shot against seeded DB: `count > 0` |
| P12: No-show cron race with PT-session recording | Phase 38 (session lock) + Phase 39 (cron) | Concurrent test: cron + session record same booking simultaneously |
| P13: UUID stringify in audit (REG-36-03 repeat) | Phase 37 (audit_payloads.py) | Emit test for all 5 new event types with UUID-typed `resource_id` values |
| P14: Idempotency key not route-bound | Phase 38 (booking creation endpoint) | Test: same key reused across `/bookings` + `/pt-sessions` → independent responses |
| P15: Telegram callback_data length overflow | Phase 40 (bot inline keyboards) | Unit test: `len(callback_data.encode()) <= 64` for all keyboard builders |
| P16: Anti-oracle leak in `/book` | Phase 40 (bot DM copy) | Owner sign-off `D-40-OWNER-COPY-LOCK` in PROJECT.md before Phase 40 merges |
| P17: Composition root resolver registered after router | Phase 37 (Protocol slot wiring) | `create_app()` integration test: all resolver slots non-None after factory returns |
| P18: PT-package validity expiry between booking and slot | Phase 38 (booking creation validation) | Test: book slot beyond package `end_date` → 422 slot_outside_package_validity |
| P19: N+1 on slot list query | Phase 37 (repository design) | Query count assertion: list of 20 slots emits ≤ 2 DB queries |
| P20: B-10 regression | Phase 37 (foundation audit) | Existing B-10 test: PT-package only → check-in → 409 still passes |

---

## Sources

- PROJECT.md Key Decisions table — v1.2..v1.4 patterns, B-01..B-12 decisions (codebase)
- MILESTONES.md — REG-29-03, REG-29-04, REG-36-03 incident reports (verbatim)
- `apps/backend/app/core/audit.py` — LOCKED_AUDIT_EVENTS frozenset (51 entries confirmed at read time)
- `apps/backend/app/core/idempotency.py` — CR-01 route-binding fix (lines 70–89 confirmed)
- `apps/backend/app/core/dependencies.py` — Protocol slot registry, resolver registration patterns
- `apps/backend/app/main.py` — Composition root numbered wiring order (confirmed)
- `apps/backend/app/workers/telegram_bot.py` — Double-wiring pattern (confirmed; `register_active_pt_package_resolver` NOT yet present in bot worker — gap to close in Phase 40)
- `apps/backend/app/modules/pt_sessions/repository.py` — D-34-04a cross-module raw SQL pattern
- `apps/backend/app/modules/pt_sessions/models.py` — Booking FK not yet present (v1.4 baseline)
- `apps/backend/app/modules/visits/models.py` — STORED GENERATED `gym_date` pattern
- `apps/backend/app/modules/payments/models.py` — Append-only invariant pattern
- `apps/backend/app/modules/pt_packages/models.py` — Partial UNIQUE + FSM patterns

---
*Pitfalls research for: PT-slot booking added to Sportzal gym CRM (v1.5 Schedule + Bookings)*
*Researched: 2026-05-17*
