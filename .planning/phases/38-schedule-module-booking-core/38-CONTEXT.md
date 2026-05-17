# Phase 38: Schedule Module + Booking Core - Context

**Gathered:** 2026-05-17
**Status:** Ready for planning
**Mode:** `--auto` (Claude auto-selected recommended defaults for all gray areas; user may override any D-38-NN before `/gsd-plan-phase 38` consumes this file)

<domain>
## Phase Boundary

Phase 38 is the **main implementation phase** for v1.5 Schedule + Bookings — it lands the 4 new Alembic migrations and the full router/service/repository stacks for both modules plus the PT-package + PT-session integration glue. The bedrock (audit taxonomy, RBAC matrix, FSM constants, Protocol slots) is already locked by Phase 37; Phase 38 wires real implementations into the existing Protocol slot bodies and exposes 9 new HTTP endpoints. Deliverable scope is exactly the 25 v1.5 requirements `SLOT-01..09 + BOOK-01..10 + PKG-01..06`.

**What ships:**
1. **Alembic 0016** — `trainer_availability_slots` table (TIMESTAMPTZ start/end, status enum, 2 indexes per SLOT-01).
2. **Alembic 0017** — `bookings` table with the partial UNIQUE `(slot_id) WHERE status='confirmed'` race guard (BOOK-01 / C-02).
3. **Alembic 0018** — `pt_packages.trainer_id` nullable FK ADD COLUMN (PKG-01 / C-08).
4. **Alembic 0019** — `pt_sessions.booking_id` nullable FK ADD COLUMN (PKG-04 / C-14).
5. **`app/modules/schedule/`** — full stack: `models.py`, `repository.py`, `schemas.py`, `router.py`, `service.py` (replacing the Phase 37 stub) implementing publish / list / get / cancel slot (SLOT-01..09).
6. **`app/modules/bookings/`** — full stack: `models.py`, `repository.py`, `schemas.py`, `router.py`, `service.py` (replacing the Phase 37 stub) implementing create / cancel / list / get-one booking + race-translation (BOOK-01..10).
7. **`app/modules/pt_packages/`** — extend `models.py` (trainer_id col), `schemas.py` (optional `trainer_id` request field), `service.py` (sale-time trainer validation + refund-guard cross-module count via `sa.text()`) — PKG-01..03.
8. **`app/modules/pt_sessions/`** — extend `models.py` (booking_id col), `schemas.py` (optional `booking_id` request field), `service.py` (validation + atomic completion of parent booking via `register_booking_completer` slot in the same UoW), `audit_payloads.py:PtSessionRecordedPayload.booking_id` callsite stringify (PKG-04..06).
9. **Tests** — race `BOOK-TEST-01` (real Postgres parallel asyncio.gather), FSM unit tests, all 409 negative-path tests, refund-guard test, pt-session-completes-booking test.

**Explicitly out of scope for Phase 38** (lands in Phase 39+):
- Any Telegram DM template or send (Phase 39 NOTIFY-01..05).
- Any ARQ cron (`mark_no_show_bookings`, `send_booking_reminders` — Phase 39 CRON-01/02).
- `booking_notifications` table (Alembic 0020 — Phase 39 NOTIFY-05).
- Telegram bot `/book` handler / InlineKeyboard (Phase 40 BOT-01..05).
- OpenAPI byte-stable regen + admin-web wiring (Phase 40 HANDOFF-01/02).
- 11 remaining DEFER-36-04-A pytest failures (handle as a parallel sweep if cheap; otherwise defer to Phase 38 verification step or to v1.5 close).

</domain>

<decisions>
## Implementation Decisions

All C-01..C-15 milestone-level decisions are locked in `.planning/REQUIREMENTS.md` and are NOT re-decided here. All D-37-NN Phase 37 bedrock decisions are locked in `.planning/phases/37-foundations-bedrock/37-CONTEXT.md`. The decisions below are Phase 38 implementation-level choices made during this auto-discuss pass.

### Module & Plan Structure

#### D-38-01 — Plan breakdown: 6 atomic plans grouped by table/module boundary
Phase 38 ships as **6 commit-sized plans** (mirroring v1.4 Phase 32/33 cadence). The breakdown is goal-back from the 5 ROADMAP success criteria:

1. **38-01 schedule-module** — Alembic 0016 + `schedule/{models,repository,schemas,router}.py` + replace `schedule/service.py` stub with real `publish_slot` (overlap + buffer + trainer-active + future-only guards) + `list_slots` + `cancel_slot_only` (the active→cancelled path; `booked→cancelled` cascade lives in the bookings cancellation cascade which is plan 38-03). Audit events `slot_published`. Owner-only RBAC. Covers SLOT-01..06, SLOT-08, SLOT-09 (publish part).
2. **38-02 booking-core-create** — Alembic 0017 (partial UNIQUE race guard) + `bookings/{models,repository,schemas,router}.py` + replace `bookings/service.py` stub: real `create_booking` UoW (slot-active check → PT-package validation via existing `register_active_pt_package_resolver` → `trainer_mismatch` check → `pt_package_expired_before_slot` validity-window check (Pitfall 18) → slot UPDATE active→booked → booking INSERT + emit → IntegrityError translation to 409 `slot_already_booked`) + `Idempotency-Key` via `Depends(verify_idempotency)`. Race test `BOOK-TEST-01` (real Postgres `asyncio.gather`). Covers BOOK-01..05, BOOK-10.
3. **38-03 booking-cancel-and-list** — `bookings.service.cancel_booking` (24h reception window via `datetime.now(UTC)` + `slot.start_time` comparison; owner-anytime; FSM `_assert_can_transition`; calls `get_booking_slot_restorer()` to flip slot booked→active in same UoW; emits `booking_cancelled`) + `schedule.service.cancel_slot` extended to handle the booked→cancelled cascade (atomically cancel the linked confirmed booking + emit both `slot_cancelled` and `booking_cancelled`) + `list_bookings` + `get_booking_by_id` + `list_bookings_for_client`. Owner+reception RBAC. DM-queueing is a no-op stub in 38 (Phase 39 lights it up). Covers SLOT-07, BOOK-06..09.
4. **38-04 pt-package-trainer-and-refund-guard** — Alembic 0018 (`pt_packages.trainer_id` nullable FK) + extend `pt_packages/schemas.py:PtPackageCreateRequest` with optional `trainer_id` + extend `pt_packages/service.create_pt_package` to validate trainer-active (409 `trainer_inactive`) + extend `pt_packages/service.refund_pt_package` with cross-module raw-`sa.text()` count of `bookings WHERE pt_package_id=:id AND status='confirmed'` → 409 `outstanding_bookings_exist` (PKG-03 / C-09 / Pitfall 4 Option A). Tests for both error paths. Covers PKG-01..03.
5. **38-05 pt-session-booking-completion** — Alembic 0019 (`pt_sessions.booking_id` nullable FK) + extend `pt_sessions/schemas.py:PtSessionCreateRequest` with optional `booking_id` + extend `pt_sessions/service.record_pt_session`: if `booking_id` provided, (a) load booking via raw `sa.text()` `SELECT ... FOR UPDATE` (Pitfall 12 — defeats no-show cron race), (b) validate `status='confirmed'` AND `pt_package_id = :req_pkg_id` AND `slot.trainer_id = :session_trainer_id` (else 409 `booking_mismatch` / `booking_not_confirmed`), (c) call `get_booking_completer()(session, booking_id)` to atomically flip booking confirmed→completed in the same UoW, (d) `pt_session_recorded` audit payload `.booking_id = str(booking_id)`. Test: record session with booking → booking is `completed`. Covers PKG-04..06 (PKG-06 NO-revert policy is the constants comment locked in Phase 37 — no code change here).
6. **38-06 svc001-and-importlinter-greens** — Confirm SVC001 walker catches the 2 new `service.py` files (already extended in Phase 37 plan 37-05), `modules-independent` contract green with real (not negative-fixture) implementation, ruff + mypy strict green. Includes the parallel sweep of remaining DEFER-36-04-A pytest failures (7 pt_sessions MissingGreenlet + 3 pt_packages envelope drift + 1 test_revert_predicate) if the surface is being touched anyway — otherwise carries forward to Phase 40 verification.

**Why 6 plans (not 4):** plans 38-04 + 38-05 touch existing v1.4 modules (`pt_packages`, `pt_sessions`) and have different test-surface ownership than the new module plans 38-01..38-03. Splitting keeps each commit reviewable and bisectable — mirrors v1.4 Phase 33 (3 plans for sale + refund) + Phase 34 (3 plans for session-record) discipline rather than v1.4 Phase 32's 3-plan condensed style.

**Parallel-eligibility (REVISED 2026-05-17 per plan-checker BLOCKER on 38-04 dependency_correctness — see 38-04 Task 1 'Decision' block for rationale):** 38-04 was originally placed in Wave 1 parallel with 38-01 on the assumption that pt_packages-module work was independent of the bookings table. The checker correctly identified that 38-04's Alembic 0018 migration has `down_revision = "0017_bookings"` (created by 38-02 in Wave 2), so 38-04 cannot `alembic upgrade head` until 38-02 lands. Additionally, 38-04 Task 3's refund-guard test seeds rows into the bookings table (via raw SQL — preserves modules-independent contract). Both reasons force 38-04 into Wave 3. Recommended wave layout for `/gsd-execute-phase`:
- Wave 1 (alone): 38-01 *(was 38-01 + 38-04)*
- Wave 2 (depends on 38-01): 38-02
- Wave 3 (parallel after 38-02): 38-03, 38-04, 38-05 *(was 38-03 + 38-05; 38-04 moved here)*
- Wave 4 (serial after all): 38-06 *(unchanged)*

All three Wave-3 plans share the dependency on 38-02 having shipped the `bookings` table + 0017 alembic revision. They have zero `files_modified` overlap with each other (38-03 = bookings+schedule modules; 38-04 = pt_packages module; 38-05 = pt_sessions module + Alembic 0019) so parallel execution is safe.

**Why this matters for `/gsd-plan-phase`:** the planner must respect the `bookings → schedule` Protocol slot direction (bookings consumes slot resolver + slot restorer; schedule provides them) when ordering 38-01 before 38-02. 38-05 depends on 38-02 + 38-03 (booking-completer slot consumes booking FSM transition which only exists after 38-02; safe to surface FSM via 38-02 alone, but the test that record_pt_session completes a booking needs both the booking-creation path and the completion-slot to be live).

#### D-38-02 — `bookings` table FK to `pt_packages` is NOT NULL
Per REQUIREMENTS BOOK-01 the `pt_package_id` is `NOT NULL FK pt_packages(id) ON DELETE RESTRICT`. PITFALLS Tech-debt row "Storing pt_package_id as nullable FK" lists nullable as acceptable for future non-PT bookings — **rejected for v1.5**. Every Phase 38 booking is a PT-session reservation by definition (group classes are anti-scope per ROADMAP). Keeping NOT NULL:
- Simplifies the refund-guard query (no `IS NOT NULL` filter needed).
- Enforces the C-08 invariant at the DB layer (every booking references a real PT-package).
- Future non-PT bookings (drop-in classes, gym tours) get their own table in v1.7+ — they have different cancellation, payment, and capacity semantics anyway.

### Slot Model

#### D-38-03 — Slot `status` values: `active / booked / cancelled` (no `available`)
REQUIREMENTS SLOT-01 specifies `active / booked / cancelled`. The Phase 37 `SLOT_STATUS_TRANSITIONS` constant in `app/modules/schedule/constants.py` already uses `active`. Research ARCHITECTURE.md drafted `available / booked / cancelled` — **rejected** (research is older than REQUIREMENTS lock). Phase 38 must use `active` everywhere — model CHECK constraint, schema enum, service code, audit-event `had_booking: bool` (computed from `status == 'booked'` at cancel time).

**No `completed` slot status.** Slot completion is a booking-side concept (`booking.status = completed` set via `register_booking_completer`). The slot stays `booked` after its associated booking is `completed` — terminal-by-implication, no further transitions. This matches the FSM matrix: `booked → {active, cancelled}` (no `completed` target). Audit / display reads the booking status, not the slot status, for "did this slot get used."

#### D-38-04 — No `deleted_at` / soft-delete on `trainer_availability_slots`
Research ARCHITECTURE.md drafted `SoftDeleteMixin` + `WHERE deleted_at IS NULL` indexes — **rejected for v1.5**. REQUIREMENTS SLOT-01 does NOT list `deleted_at`. Decommissioning is via status flip to `cancelled` (SLOT-02: "NO DELETE — cancelled slots stay for audit + booking history"). Avoiding the soft-delete column also avoids a partial-index pattern proliferation and keeps the model under the simplest viable surface.

**Implication for indexes:** the partial indexes per SLOT-01 are:
- `ix_trainer_availability_slots_trainer_start_time` on `(trainer_id, start_time)` — full btree, no WHERE
- `ix_trainer_availability_slots_active_start_time` on `(status, start_time)` partial WHERE `status = 'active'` (per SLOT-01 partial-for-active-discovery)

#### D-38-05 — No `recurrence_rule` column in v1.5
Research ARCHITECTURE.md drafted `recurrence_rule TEXT NULL` for RRULE storage — **rejected for v1.5**. REQUIREMENTS SLOT-02 specifies `POST /api/v1/trainer-slots` "publish one-off slot" — single slot per POST. RRULE expansion + horizon-window are explicit anti-features for v1.5 (deferred to v1.8 reports milestone alongside `.ics` export). One trainer publishes one slot at a time via reception or owner UI; bulk-publish is future scope.

**Implication for the request schema:** `SlotCreateRequest = {trainer_id: UUID, start_time: datetime, end_time: datetime}` — three fields, no recurrence.

#### D-38-06 — Slot overlap detection: app-layer query (NOT Postgres EXCLUDE constraint)
PITFALLS Pitfall 2 + Tech-debt row both recommend app-layer overlap for v1.5 (vs `EXCLUDE USING gist` which requires `btree_gist` extension). **Auto-select app-layer.** Implementation in `schedule.service.publish_slot`:

```python
existing = await session.execute(
    sa.select(TrainerAvailabilitySlot.id)
    .where(
        TrainerAvailabilitySlot.trainer_id == req.trainer_id,
        TrainerAvailabilitySlot.status != "cancelled",
        sa.func.tstzrange(TrainerAvailabilitySlot.start_time, TrainerAvailabilitySlot.end_time, "[)").op("&&")(
            sa.func.tstzrange(req.start_time, req.end_time, "[)")
        ),
    )
    .with_for_update()
)
```

(Equivalent to `WHERE trainer_id=:tid AND status!='cancelled' AND tstzrange(start_time,end_time,'[)') && tstzrange(:new_start,:new_end,'[)')` per SLOT-03.)

**Why `with_for_update()` is sufficient:** single-zal single-owner-publishing usage pattern — concurrent slot publishes by the same trainer are not a hot path. The row-level lock on the trainer's existing non-cancelled slots prevents two simultaneous publishes from both passing the overlap check. Migration to `EXCLUDE USING gist` deferred to v2.0 if trainers self-publish at scale (anti-feature today).

#### D-38-07 — 10-minute buffer (SLOT-04) computed in the same overlap query
SLOT-04 `slot_too_close` is detected by widening the candidate range by 10 minutes on each edge for the buffer check:

```python
buffer_candidate_range = sa.func.tstzrange(
    req.start_time - timedelta(minutes=10),
    req.end_time + timedelta(minutes=10),
    "[)"
)
```

If the buffer-widened candidate range overlaps another non-cancelled slot (and the unwidened candidate range does NOT), return 409 `slot_too_close` (discriminated from `slot_overlap`). Two separate executes (overlap-check first, then buffer-check on miss) is acceptable — both rows hold the same row lock.

**Constant:** `SLOT_BUFFER_MINUTES = 10` in `app/modules/schedule/constants.py` alongside `SLOT_STATUS_TRANSITIONS`. C-15 hardcodes 10 for v1.5; configurable buffer deferred to v1.8.

### Booking Model

#### D-38-08 — No `*_snapshot` columns on `bookings` (use `joinedload`)
Research ARCHITECTURE.md drafted `trainer_name_snapshot`, `slot_start_time_snapshot`, `slot_end_time_snapshot` columns — **rejected for v1.5**. REQUIREMENTS BOOK-01 does NOT list snapshot columns. Display payloads (BOOK-09 `GET /bookings/{id}` "returns full booking + denormalized slot + trainer + pt_package snapshot for display") are built via `joinedload(Booking.slot).joinedload(TrainerAvailabilitySlot.trainer)` + `joinedload(Booking.pt_package)` in the repository layer, returned as nested Pydantic response models in `bookings/schemas.py`.

**Why this is safe:**
- Trainers are soft-deleted via `is_active = false` (v1.4 Phase 31 TRN-04 lock); the FK is `ON DELETE RESTRICT` so the trainer row always exists for read-back.
- Slots are status-flipped to `cancelled`, never hard-deleted (per SLOT-02 / D-38-04); FK is `ON DELETE RESTRICT`; row always exists.
- The display-integrity requirement (research's stated reason for snapshot fields) is solved structurally by the no-hard-delete invariant, not by data duplication.

**Implication for N+1 (Pitfall 19):** every list query in `bookings/repository.py` and `schedule/repository.py` uses `options(joinedload(...))` explicitly. Add a query-count assertion in one repository test per module: "list of 20 items emits ≤ 2 DB queries."

#### D-38-09 — Booking cancellation authorization: reception or owner can cancel any booking
PITFALLS Security row "Booking cancellation does not verify booking ownership" lists two options: (a) check `booking.created_by_user_id == current_user.id OR owner`, (b) accept "reception = trusted" gym-staff context. **Auto-select Option B** (reception+owner can cancel any booking, no ownership check). Justification:
- v1.4 precedent: `pt_sessions` cancel (B-12) has the same model — any reception user can cancel any session within the 24h window. Audit trail records `cancelled_by_user_id` for post-hoc accountability.
- Single-zal MVP — there are 1–2 reception users at most. The "rogue reception cancels other reception's booking" threat is not credible at this scale.
- Adding ownership check creates UX friction for the typical scenario where reception #2 covers for reception #1.

**Implementation:** RBAC requires `(CANCEL, BOOKINGS)` (reception holds this per OWNER_ONLY map). Service enforces the 24h window for reception (BOOK-06 / C-05). No `created_by_user_id` ownership check. `cancelled_by_user_id` recorded in audit payload (Phase 39's audit consumers can use it).

#### D-38-10 — Booking FSM guard placement: `_assert_can_transition` helper lives in `bookings/service.py`
Phase 37 D-37-04 already locked "per-module guard alongside the constant" — but the `_assert_can_transition` function itself was deferred to Phase 38 (the constants module is pure data per the v1.3/v1.4 precedent; the helper sits in `service.py` next to the consumer). Implementation mirrors `apps/backend/app/modules/pt_packages/service.py:184-197`:

```python
def _assert_can_transition(current: str, target: str) -> None:
    if target not in BOOKING_STATUS_TRANSITIONS.get(current, frozenset()):
        raise InvalidBookingTransitionError(
            f"booking cannot transition {current!r} → {target!r}"
        )
```

`InvalidBookingTransitionError(ConflictError)` with `code = "invalid_transition"`, `status_code = 409`. Same shape for slots in `schedule/service.py` (`InvalidSlotTransitionError`).

### PT-Package + PT-Session Integration

#### D-38-11 — Cross-module SQL discipline for booking-completion + refund-guard
Both cross-module reach-throughs use raw `sa.text()` with named parameters (D-34-04a discipline from v1.4) to preserve the `modules-independent` import-linter contract:

1. **`pt_packages/service.refund_pt_package`** (PKG-03):
   ```python
   row = await session.execute(
       sa.text("SELECT count(*) FROM bookings WHERE pt_package_id = :pkg_id AND status = 'confirmed'"),
       {"pkg_id": str(pt_package_id)},
   )
   if row.scalar_one() > 0:
       raise OutstandingBookingsExistError(...)  # 409 outstanding_bookings_exist
   ```
   Comment `# noqa: TABLE_REF cross-module SQL per D-34-04a / Phase 38 D-38-11`. No `Booking` ORM import.

2. **`pt_sessions/service.record_pt_session`** when `booking_id` provided (PKG-05):
   - Loading the booking row uses `sa.text("SELECT id, status, pt_package_id, slot_id FROM bookings WHERE id = :bid FOR UPDATE")` (Pitfall 12 — row-level lock defeats no-show cron race).
   - Validating slot trainer for `trainer_mismatch` check: `sa.text("SELECT trainer_id FROM trainer_availability_slots WHERE id = :sid")`.
   - Flipping booking confirmed→completed: **does NOT use raw SQL** — calls `get_booking_completer()(session, booking_id)` instead. The Protocol slot resolves to `bookings.service.complete_booking` which owns the FSM-guarded UPDATE in its own module. This preserves the `modules-independent` contract — `pt_sessions` reaches the bookings module only via the composition-root slot, never via direct import.

**Why hybrid (raw SQL for reads, Protocol slot for writes):** reads are cheap and the FK + status check needs to happen inside the existing `record_pt_session` UoW before the package decrement; switching to a Protocol slot for the read would add a round-trip-through-the-slot-registry without correctness benefit. Writes (the FSM transition) MUST go through the slot so the bookings module owns its own FSM enforcement (`_assert_can_transition` lives there).

#### D-38-12 — Validity-window guard (Pitfall 18) lands in `bookings.service.create_booking`
PITFALLS Pitfall 18 + REQUIREMENTS BOOK-04 ("`pt_package_expired_before_slot` when `pt_package.end_date < slot.start_time::date`") agree. Implementation in `create_booking` after the active-PT-package check passes:

```python
# Pitfall 18: validity-window guard
if pt_package.end_date is not None and pt_package.end_date < slot.start_time.astimezone(MOSCOW_TZ).date():
    raise PtPackageExpiredBeforeSlotError(...)  # 409 pt_package_expired_before_slot
```

**Why `astimezone(MOSCOW_TZ).date()` not `.date()` on the UTC value:** business TZ is Europe/Moscow (C-07). A slot at 2026-07-01 01:00 Moscow is 2026-06-30 22:00 UTC. Comparing `.date()` on the UTC value would mis-classify the slot as belonging to 2026-06-30 — a package with `end_date = 2026-06-30` would incorrectly accept a slot meant for 2026-07-01. The comparison MUST happen in Moscow time.

#### D-38-13 — PKG-06 reverse-transition policy: NO automatic revert
REQUIREMENTS PKG-06 explicitly states "the booking does NOT automatically revert from `completed` back to `confirmed`" when the pt_session with `booking_id` is cancelled. Locked here as **D-38-13**. The FSM constant in `BOOKING_STATUS_TRANSITIONS` already enforces this (`completed → ∅`). Operator behavior: if a session is cancelled, the operator creates a new booking (and a new pt_session record at delivery). Audit trail shows the chain: `booking_created → pt_session_recorded → pt_session_cancelled` — operator can reconstruct what happened.

**Test coverage:** Plan 38-05 includes a test "record pt_session against booking → cancel pt_session → booking remains `completed`" to lock the no-revert behavior.

### Idempotency & Error Mapping

#### D-38-14 — `POST /api/v1/bookings` uses `Depends(verify_idempotency)` (Pitfall 14)
REQUIREMENTS BOOK-02 + Pitfall 14 + C-13 agree. Implementation mirrors `apps/backend/app/modules/pt_sessions/router.py:84`:

```python
idempotency_key: Annotated[str, Depends(verify_idempotency)],
```

NO manual `request.headers.get("idempotency-key")`. The route-bound key prevents cross-route replay between `/bookings` and `/pt-sessions`.

#### D-38-15 — `IntegrityError` → 409 translation discriminated by constraint name
The partial UNIQUE `(slot_id) WHERE status='confirmed'` constraint is named `uq_bookings_slot_confirmed` (matches v1.4 `uq_pt_packages_active_per_client` naming convention). Service catches `IntegrityError` and dispatches by `__cause__.diag.constraint_name`:

```python
try:
    await session.flush()
except IntegrityError as e:
    if _is_constraint(e, "uq_bookings_slot_confirmed"):
        raise SlotAlreadyBookedError(...)  # 409 slot_already_booked
    raise
```

Mirrors `apps/backend/app/modules/pt_packages/service.py:_is_pt_package_plan_name_conflict` discipline. Catch-and-re-raise pattern is canonical.

### Cancel-Window & Time Handling

#### D-38-16 — `datetime.now(UTC)` discipline (Pitfall 7), `CANCEL_WINDOW_HOURS_RECEPTION = 24` constant
Mirror `apps/backend/app/modules/pt_sessions/constants.py:18`:

```python
CANCEL_WINDOW_HOURS_RECEPTION = 24  # C-05 / BOOK-06
```

in `app/modules/bookings/constants.py`. Service uses `datetime.now(UTC)` (timezone-aware, Python 3.12 idiom):

```python
from datetime import UTC, datetime, timedelta
now_utc = datetime.now(UTC)
if current_user.role == "reception":
    if booking.slot.start_time - now_utc < timedelta(hours=CANCEL_WINDOW_HOURS_RECEPTION):
        raise CancelWindowExpiredError(...)  # 409 cancel_window_expired
```

mypy strict will flag any `datetime.utcnow()` usage in CI.

### Audit & Compliance

#### D-38-17 — Audit emit kwargs are stringified at callsite (Pitfall 13 / REG-36-03)
Every UUID-typed audit payload field is passed as `str(uuid)` at the callsite. Phase 37 already locked the schemas (`SlotPublishedPayload`, `SlotCancelledPayload`, `BookingCreatedPayload`, `BookingCancelledPayload`) with `booking_id: str` (not `UUID`) and `extra='forbid'`. Phase 38's callsites in `schedule.service.publish_slot` / `schedule.service.cancel_slot` / `bookings.service.create_booking` / `bookings.service.cancel_booking` all pass `slot_id=str(slot.id)`, `booking_id=str(booking.id)`, `client_id=str(client.id)`, etc.

For `pt_session_recorded` extension in plan 38-05: `pt_sessions.service.record_pt_session` audit emit gains `booking_id=str(booking_id) if booking_id is not None else None` — the field is `Optional[str]` per Phase 37 D-37-05.

#### D-38-18 — B-10 regression guard verified, no new code
PITFALLS Pitfall 20: PT-package alone does NOT grant gym-floor access. Phase 38 changes nothing in `visits/service.py`. Plan 38-06 (`svc001-and-importlinter-greens`) includes a one-line verification step: run the existing B-10 regression test (`test_visits.py::test_pt_package_only_client_blocked_from_check_in`) and confirm green after all Phase 38 commits land. No new code needed.

### No-Show Cron Race (Phase 39 forward-link)

#### D-38-19 — `SELECT FOR UPDATE` in `record_pt_session` is the v1.5 race guard against the future no-show cron
PITFALLS Pitfall 12: the no-show cron (Phase 39 CRON-01) will batch-`UPDATE bookings SET status='no_show' WHERE status='confirmed' AND slot.end_time < now()`. The PT-session-recording path competes. **The lock discipline is established in Phase 38** so Phase 39 doesn't need to retrofit: `pt_sessions.service.record_pt_session` issues `SELECT ... FOR UPDATE` on the booking row (via the raw `sa.text(... FOR UPDATE)` per D-38-11) **before** any INSERT or UPDATE in the UoW. The cron's competing UPDATE blocks on the row lock until commit. Clean serialization.

**No code in Phase 38 references the cron** — but the test in plan 38-05 includes a comment block noting the future cron interaction so Phase 39's planner finds the guarantee.

### Claude's Discretion
None — `--auto` mode picked every default with rationale logged above. The user can audit and override any D-38-NN before `gsd-plan-phase 38` consumes this file.

### Folded Todos
None — `gsd-sdk query todo.match-phase 38` was not invoked in `--auto` mode for this discussion (no pending todos detected at session start per STATE.md; the only pending todo "Run `/gsd-plan-phase 37`" was already actioned and is now obsolete).

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents (researcher, planner, executor) MUST read these before planning or implementing.**

### Milestone Decisions & Requirements (PRIMARY)
- `.planning/REQUIREMENTS.md` §C-01..C-15 — locked milestone bedrock decisions (source of truth for v1.5 architecture; C-02/C-04/C-05/C-07/C-08/C-09/C-13/C-14/C-15 are the most load-bearing for Phase 38)
- `.planning/REQUIREMENTS.md` §SLOT-01..09 — 9 slot requirements (Phase 38 scope)
- `.planning/REQUIREMENTS.md` §BOOK-01..10 — 10 booking requirements (Phase 38 scope)
- `.planning/REQUIREMENTS.md` §PKG-01..06 — 6 PT-package/session integration requirements (Phase 38 scope)
- `.planning/PROJECT.md` "Current Milestone: v1.5" + Key Decisions table — accumulated business-domain context (B-10 PT-package-vs-floor-access invariant is critical)
- `.planning/STATE.md` "v1.5 bedrock decisions" — C-01..C-15 summary + Phase 37 done-state

### Phase 37 Bedrock (LOCKED — do NOT re-decide)
- `.planning/phases/37-foundations-bedrock/37-CONTEXT.md` — D-37-01..D-37-09 implementation decisions (RBAC, Action.LIST, OWNER_ONLY deltas, FSM constant location, Protocol slot semantics, audit payload UUID-as-str)
- `.planning/phases/37-foundations-bedrock/37-VERIFICATION.md` — confirmed acceptance of all 5 success criteria
- `.planning/phases/37-foundations-bedrock/37-PATTERNS.md` — code patterns surveyed before Phase 37 planning (the pattern-mapper output that informed Phase 37 structure also applies to Phase 38)

### Research Outputs (still authoritative for Phase 38)
- `.planning/research/SUMMARY.md` — 4-dimension research synthesis (read first if unfamiliar with v1.5)
- `.planning/research/PITFALLS.md` §Pitfalls 1, 2, 4, 5, 7, 8, 12, 13, 14, 18, 19, 20 — the 12 pitfalls Phase 38 must defuse (Pitfalls 3, 6, 17 already defused in Phase 37; 9, 10, 11, 15, 16 are Phase 39/40)
- `.planning/research/PITFALLS.md` §"Looks Done But Isn't" Checklist + §Pitfall-to-Phase Mapping — Phase 38 verification matrix
- `.planning/research/ARCHITECTURE.md` — module-split + 3 Protocol slots (NOTE: ARCHITECTURE drafted some details — `available` status, soft-delete, recurrence_rule, snapshot fields — that REQUIREMENTS later overrode; see D-38-03..05, D-38-08 above)
- `.planning/research/FEATURES.md` — feature inventory + scope guard (anti-features list — Phase 38 must not creep into them)
- `.planning/research/STACK.md` — Python 3.12, FastAPI 0.115+, SQLAlchemy 2.0 async, Alembic async, asyncpg, Postgres 16 idioms

### Roadmap & Milestone Plans
- `.planning/ROADMAP.md` §Phase 38 — goal + 5 success criteria (the goal-backward anchor for plan-checker)
- `.planning/MILESTONES.md` — REG-29-03, REG-29-04, REG-36-03 incidents (institutional memory; all three relevant to Phase 38 patterns)

### Codebase Maps
- `.planning/codebase/ARCHITECTURE.md` — modular-monolith conventions
- `.planning/codebase/STRUCTURE.md` — directory + module layout
- `.planning/codebase/STACK.md` — Python/FastAPI/SQLAlchemy stack baseline
- `.planning/codebase/CONVENTIONS.md` — naming, ruff/mypy rules, commit conventions (Conventional Commits per project)
- `.planning/codebase/CONCERNS.md` — known cross-cutting concerns
- `.planning/codebase/TESTING.md` — pytest + httpx ASGITransport conventions + real-Postgres race-test conventions
- `.planning/codebase/INTEGRATIONS.md` — external boundaries (ARQ, Redis, Telegram — none of which Phase 38 touches directly)

### Source Files Phase 38 Will MODIFY (existing files)
- `apps/backend/app/modules/schedule/service.py` — REPLACE the Phase 37 stub functions `resolve_slot_by_id` + `restore_slot_to_active` with real bodies (preserve signatures; SVC001 walker already targets this file)
- `apps/backend/app/modules/schedule/constants.py` — APPEND `SLOT_BUFFER_MINUTES = 10` constant (locked from C-15)
- `apps/backend/app/modules/bookings/service.py` — REPLACE the Phase 37 stub function `complete_booking` with real body (preserve signature; SVC001 walker already targets this file)
- `apps/backend/app/modules/bookings/constants.py` — APPEND `CANCEL_WINDOW_HOURS_RECEPTION = 24` constant
- `apps/backend/app/modules/pt_packages/models.py` — ADD `trainer_id: Mapped[UUID | None]` column (FK trainers.id ON DELETE RESTRICT)
- `apps/backend/app/modules/pt_packages/schemas.py` — extend `PtPackageCreateRequest` with optional `trainer_id`; extend response schemas to surface `trainer_id`
- `apps/backend/app/modules/pt_packages/service.py` — `create_pt_package` validates trainer-active when `trainer_id` provided; `refund_pt_package` adds outstanding-bookings count guard via raw `sa.text()` (D-38-11)
- `apps/backend/app/modules/pt_sessions/models.py` — ADD `booking_id: Mapped[UUID | None]` column (FK bookings.id ON DELETE RESTRICT)
- `apps/backend/app/modules/pt_sessions/schemas.py` — extend `PtSessionCreateRequest` with optional `booking_id`
- `apps/backend/app/modules/pt_sessions/service.py` — `record_pt_session` validates and completes booking when `booking_id` provided (D-38-11); audit emit gains `booking_id=str(...)` per D-37-05

### Source Files Phase 38 Will CREATE (new files)
- `apps/backend/alembic/versions/0016_trainer_availability_slots.py` — Alembic migration for SLOT-01
- `apps/backend/alembic/versions/0017_bookings.py` — Alembic migration for BOOK-01 (includes the partial UNIQUE)
- `apps/backend/alembic/versions/0018_pt_packages_trainer_id.py` — Alembic ALTER for PKG-01
- `apps/backend/alembic/versions/0019_pt_sessions_booking_id.py` — Alembic ALTER for PKG-04
- `apps/backend/app/modules/schedule/models.py` — `TrainerAvailabilitySlot` ORM model
- `apps/backend/app/modules/schedule/repository.py` — async repository functions
- `apps/backend/app/modules/schedule/schemas.py` — Pydantic v2 request/response models
- `apps/backend/app/modules/schedule/router.py` — FastAPI APIRouter for `/trainer-slots`
- `apps/backend/app/modules/bookings/models.py` — `Booking` ORM model (with named partial UNIQUE `uq_bookings_slot_confirmed`)
- `apps/backend/app/modules/bookings/repository.py` — async repository functions
- `apps/backend/app/modules/bookings/schemas.py` — Pydantic v2 request/response models
- `apps/backend/app/modules/bookings/router.py` — FastAPI APIRouter for `/bookings`
- `apps/backend/tests/test_schedule_service.py` (or split per-endpoint following pt_packages pattern)
- `apps/backend/tests/test_bookings_service.py`
- `apps/backend/tests/test_booking_race.py` — `BOOK-TEST-01` real-Postgres `asyncio.gather` race test (BOOK-10)
- `apps/backend/tests/test_pt_packages_refund_guard.py` — extend existing pt_packages refund tests for PKG-03
- `apps/backend/tests/test_pt_sessions_booking_completion.py` — PKG-05 happy path + no-revert (PKG-06) coverage

### Existing patterns to mirror (READ before writing)
- `apps/backend/app/modules/pt_packages/service.py` — service.py shape: error classes, `_assert_can_transition`, `_is_*_conflict` discriminators, `register_active_pt_package_resolver` exposure (mirror this exactly for `bookings` and `schedule`)
- `apps/backend/app/modules/pt_packages/router.py` — router.py shape: `Depends(verify_idempotency)`, RBAC `require_permission`, response model, `status_code=201` (mirror exactly)
- `apps/backend/app/modules/pt_sessions/service.py:record_pt_session` — atomic UoW with partial UNIQUE race translation + `register_payment_recorder` cross-module slot use (closest analog to `create_booking`)
- `apps/backend/app/modules/pt_sessions/service.py:cancel_pt_session` — 24h window logic via `CANCEL_WINDOW_HOURS_RECEPTION` (mirror for `cancel_booking`)
- `apps/backend/app/modules/visits/repository.py` partial UNIQUE handling + race test (`tests/test_visits_race.py` if present — verify exact filename during plan-phase)
- `apps/backend/alembic/versions/0014_pt_packages.py` — closest precedent for the new tables (partial UNIQUE + status CHECK + TIMESTAMPTZ defaults)

### Architectural Contracts (CI-enforced; must stay green)
- `.importlinter` — `modules-independent` contract already lists `app.modules.schedule` and `app.modules.bookings` from Phase 37; Phase 38's real implementations must not cross-import (use Protocol slots from `app.core.dependencies`)
- `apps/backend/scripts/svc001_check.py` (or equivalent walker) — already targets `app/modules/schedule/service.py` and `app/modules/bookings/service.py` from Phase 37; every state-mutating service function MUST end with `await session.commit()`
- `apps/backend/tests/test_audit_taxonomy.py` — already locked at 58 events from Phase 37; Phase 38 emit callsites MUST use exactly those event names
- `apps/backend/tests/test_audit_payloads.py` — schemas are locked; Phase 38 emit kwargs MUST match the per-event Pydantic schema exactly (`extra='forbid'`)
- `apps/backend/tests/test_rbac_parity.py` (TEST-06) — backend ↔ frontend RBAC mirror; Phase 38 must NOT touch RBAC (already locked in Phase 37 D-37-02/03)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **Phase 37 Protocol slot stubs** in `app/modules/schedule/service.py` + `app/modules/bookings/service.py` — Phase 38 REPLACES the bodies; signatures are pinned and the composition-root wiring is already live. No changes needed to `app/core/dependencies.py` or `app/main.py:create_app()` for the slot wiring (Phase 37 INFRA-32/33 already shipped).
- **`get_payment_recorder()` / `get_payment_refunder()` slots** (`app/core/dependencies.py:386-422`) — pattern reference for "consume a slot in service.create" — `bookings.service.create_booking` calls `get_active_pt_package_resolver()` exactly the same way (existing slot from Phase 33).
- **`verify_idempotency` dependency** (`app/core/idempotency.py:60`) — Phase 38 router uses `Annotated[str, Depends(verify_idempotency)]` for `POST /bookings` (D-38-14 / Pitfall 14).
- **`CANCEL_WINDOW_HOURS_RECEPTION` constant pattern** (`pt_sessions/constants.py:18`) — copy to `bookings/constants.py` with the same value (24h per C-05).
- **`PtPackagePlanCreatedPayload` / `RefundIssuedPayload` audit payload schemas** (`app/core/audit_payloads.py`) — already locked for Phase 38 (`SlotPublishedPayload`, `BookingCreatedPayload`, etc. added in Phase 37). Emit callsite shape is identical to the v1.4 examples.
- **Module repository pattern** (`pt_packages/repository.py`, `pt_sessions/repository.py`) — async functions, single-statement SELECTs with explicit `options(joinedload(...))`, `with_for_update()` where row-lock is needed. Copy structure for `schedule/repository.py` + `bookings/repository.py`.
- **Module router pattern** (`pt_packages/router.py`, `pt_sessions/router.py`) — FastAPI router with `require_permission((Action.X, Resource.Y))` dependency, `Annotated[AsyncSession, Depends(get_db)]`, `Annotated[CurrentUser, Depends(...)]`, response models always paginated `PaginatedResponse[T]` for list endpoints.

### Established Patterns
- **Modular monolith with composition-root carve-outs** — every cross-module reach goes through `app/core/dependencies.py` (Protocol + register_* + get_*). Phase 38 has zero new slots (Phase 37 already shipped all 3). Reuse via `get_slot_by_id_resolver`, `get_booking_slot_restorer`, `get_booking_completer`, `get_active_pt_package_resolver`.
- **Per-module FSM constant + `_assert_can_transition` guard** — `MEMBERSHIP_STATUS_TRANSITIONS` (v1.3) + `PT_PACKAGE_STATUS_TRANSITIONS` (v1.4) + `BOOKING_STATUS_TRANSITIONS` + `SLOT_STATUS_TRANSITIONS` (Phase 37). Phase 38 adds the `_assert_can_transition` helper in each new module's `service.py` (D-38-10).
- **Partial UNIQUE + named constraint + IntegrityError discriminator** — every v1.2..v1.4 race guard uses this trio. `uq_bookings_slot_confirmed` (Phase 38) is the next instance; service translates by constraint name.
- **Caller-owns-UoW (SVC001)** — every service mutator ends `await session.commit()`. Private helpers may `# noqa: SVC001 caller-owns-txn`. Phase 38 follows the pattern.
- **Audit `extra='forbid'` payload schemas + emit-time validation hook** — payload kwargs must match the schema; any drift raises at emit time. Phase 37 locked the schemas; Phase 38 callsites must match exactly (every UUID is `str(...)` per Pitfall 13).
- **TIMESTAMPTZ via `DateTime(timezone=True)`** — Pitfall 6. Slot times + booking timestamps + `cancelled_at` + `no_show_at` + `completed_at` all use this. Migration uses raw `sa.DateTime(timezone=True)` or `sa.TIMESTAMP(timezone=True)`.
- **Real-Postgres race test pattern** — `tests/test_pt_packages_race.py` / `tests/test_pt_sessions_race.py` (verify exact names during plan-phase) use `asyncio.gather` against a docker-compose Postgres instance, not a mock. `BOOK-TEST-01` follows this template.

### Integration Points
- **`app/main.py:create_app()`** — Phase 37 already registers all 3 new Protocol slots in deterministic order BEFORE `api.include_router`. Phase 38 ALSO needs `api.include_router(schedule.router.router, prefix="/api/v1")` and `api.include_router(bookings.router.router, prefix="/api/v1")` — append in the same numbered-step block as the existing module routers. Update the docstring numbered-steps list.
- **`app/workers/telegram_bot.py:main()`** — Phase 37 already defensively wires `register_slot_by_id_resolver(schedule_service.resolve_slot_by_id)` (currently the stub) and `register_active_pt_package_resolver`. Phase 38's real `resolve_slot_by_id` replaces the stub body without changing the wiring (signature-compatible). No bot-worker edit needed in Phase 38.
- **Existing v1.4 modules touched by Phase 38** — `pt_packages` (sale + refund flows) and `pt_sessions` (record flow) gain optional fields and one cross-module check each. Risk surface: the 11 remaining DEFER-36-04-A failures live in these modules; plan 38-06 includes a parallel sweep to clear them while the surface is being touched (cheap if cheap, defer otherwise).
- **Existing `bookings/_negative_importlinter_fixture.py`** — Phase 37 fixture (one-line bad import guarded by `if False:`). Phase 38 plan must verify this file still exists after the real `bookings/router.py` etc. land, and is still ignored by import-linter (or moved out of the production codebase).

</code_context>

<specifics>
## Specific Ideas

- **Plan ordering and execution waves** (D-38-01 above): 38-01 + 38-04 in Wave 1 (parallel; different modules), 38-02 in Wave 2 (depends on 38-01's slot model + repo), 38-03 + 38-05 in Wave 3 (parallel; depend on 38-02), 38-06 in Wave 4 (serial last). This shape supports `/gsd-execute-phase` wave-based parallelization out of the box.

- **Migration naming convention** is `NNNN_<lowercase_snake>` matching the existing series (last is `0015_pt_sessions.py`). Phase 38 adds 4 sequential migrations in numerical order: `0016_trainer_availability_slots.py`, `0017_bookings.py`, `0018_pt_packages_trainer_id.py`, `0019_pt_sessions_booking_id.py`. Each migration's `down_revision` is the previous numbered migration. Plan-phase should set explicit ordering even though they target different tables (alembic linear-history discipline from v1.2 Phase 16).

- **Constraint naming** follows the established pattern: `uq_<table>_<scope>` for unique constraints, `ix_<table>_<columns>` for indexes, `ck_<table>_<short>` for check constraints. Specifically:
  - `uq_bookings_slot_confirmed` (partial UNIQUE) — the IntegrityError discriminator
  - `ix_trainer_availability_slots_trainer_start_time` and `ix_trainer_availability_slots_active_start_time`
  - `ix_bookings_client_status` and `ix_bookings_slot_status`
  - `ck_trainer_availability_slots_status` and `ck_bookings_status`

- **Pagination response envelope** is the locked `{items, total, page, pageSize}` shape via `PaginatedResponse[T]` from `app/core/pagination.py`. Phase 38 list endpoints (3 of them per SC #5) MUST use this envelope, never bare arrays.

- **Default date windows for list queries** (SLOT-08, BOOK-07): slot list defaults `now → now+14d Europe/Moscow`; booking list defaults `now-30d → now+30d Europe/Moscow`. Implementation in `schemas.py` field defaults using `Field(default_factory=...)` with the Moscow-TZ-aware now value, NOT in the router signature (testability — defaults computed at request time, not at module import time).

- **Cross-module SQL comments** must include the `# noqa: TABLE_REF cross-module SQL per D-34-04a / Phase 38 D-38-11` marker so the import-linter / future maintainers see the deliberate boundary crossing.

- **Race-test acceptance** for `BOOK-TEST-01` (BOOK-10) requires the test pass `--exit-code 0` against a real Postgres 16 via `docker compose up -d db` in CI. The test file MUST NOT use the `pytest-asyncio` mock event loop — `asyncio.gather` with two concrete `httpx.AsyncClient` requests is the established pattern (see `test_pt_sessions_race.py` / `test_pt_packages_race.py` for the exact recipe).

</specifics>

<deferred>
## Deferred Ideas

### To Phase 39 (Notifications + Cron)
- All Telegram DM templates (`BOOKING_CONFIRMED_DM`, `BOOKING_CANCELLED_BY_*_DM`, `BOOKING_REMINDER_24H_DM`) (NOTIFY-01..04)
- `_BOT_BOOK_DENIED_DM` anti-oracle constant (NOTIFY-02)
- Send-through factory `build_bot` reuse for booking-confirmed DM emission (NOTIFY-03)
- `booking_notifications` table (Alembic 0020) (NOTIFY-05)
- `mark_no_show_bookings` ARQ cron at 23:10 MSK (CRON-01)
- `send_booking_reminders` ARQ cron at 06:35 MSK (CRON-02)
- `WorkerSettings.cron_jobs` registration + `on_job_start/end` structlog (CRON-03)
- One-shot operator runners `run_no_show_cron_once.py` + `run_booking_reminders_once.py` (CRON-04/05)
- The DM-queue side-effect on `cancel_booking` is a no-op stub in Phase 38; Phase 39 wires the real Telegram send.

### To Phase 40 (Telegram /book + OpenAPI + Verification)
- `/book` command handler + `CallbackQueryHandler` + InlineKeyboard with `BK:{slot_uuid}` callback_data (BOT-01..03)
- `HandlerContext.bookings_service` field (BOT-05)
- Redis update_id dedup `sz:bot:update:{update_id}` (BOT-04)
- OpenAPI byte-stable regen for v1.5 paths (HANDOFF-01)
- `schema.contract.test.ts` `AssertNonNever` forward-guards (HANDOFF-02)
- 6 operator curl scenarios + 2 bot scenarios + cron scenarios (VER-05..07)
- Milestone verification log entries (VER-08)

### To Phase 38 verification step (or carries to Phase 40 verification)
- **DEFER-36-04-A pytest sweep** (11 remaining failures: 7 pt_sessions MissingGreenlet + 3 pt_packages validation_error envelope drift + 1 test_revert_predicate logic bug). Plan 38-06 attempts a cheap sweep while the test surface is being touched anyway; remaining failures defer to Phase 40 milestone verification. Tracked in `.planning/STATE.md` Deferred Items table.

### To v1.5.1 / future patches
- Manual `POST /bookings/{id}/no_show` endpoint — v1.5.1 only if real operational need surfaces (C-10 says cron-only for v1.5; do not anticipate).
- Reverse transition `no_show → confirmed` reopen flow (Pitfall 9 Option A) — defer to v1.6 if late-arrival reversals become a request.

### To Future Milestones
- Postgres EXCLUDE USING gist constraint for slot-overlap (D-38-06 deferred to v2.0 if trainers self-publish at scale)
- Slot snapshot columns (D-38-08 deferred — re-evaluate only if hard-delete is ever introduced; not anticipated)
- `recurrence_rule` / RRULE expansion (D-38-05 deferred to v1.8 reports milestone)
- `pt_package_id` nullable on bookings for non-PT bookings (D-38-02 deferred to v1.7+ when drop-in / group classes are scoped)
- Group classes (capacity > 1) — TBD milestone
- Online payment at booking time — v1.7 ЮKassa
- Trainer Telegram DMs — v1.6
- Configurable slot buffer — v1.8 Reports
- iCal `.ics` export — v1.8 Reports
- DEFER-36-04-B (ruff format 123 files) — v1.9 doc-debt sweep

### Reviewed Todos (not folded)
None — no todos surfaced for Phase 38 in `--auto` mode (no `gsd-sdk query todo.match-phase 38` results applicable; the only STATE.md pending todo "Run `/gsd-plan-phase 37`" is obsolete after Phase 37 completion 2026-05-17).

</deferred>

---

*Phase: 38-schedule-module-booking-core*
*Context gathered: 2026-05-17*
*Mode: --auto (single-pass; downstream agents may override any D-38-NN before plan-phase)*
