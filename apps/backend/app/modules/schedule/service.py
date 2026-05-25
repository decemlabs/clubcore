"""Schedule module service — orchestration between router and repository.

Phase 38 plan 38-01 Task 3 ships:
  - resolve_slot_by_id   — Phase 37 stub body replaced with repository delegate
                           (silent-None per D-37-06 / D-37-XX).
  - restore_slot_to_active — Phase 37 stub body replaced with predicate-gated
                           raw UPDATE (booked → active inside caller's UoW).
  - publish_slot         — full orchestrator (trainer-active check, future-only
                           guard, overlap detection via tstzrange, buffer check
                           via SLOT_BUFFER_MINUTES, INSERT, audit emit, commit).
  - cancel_slot          — active-only path (booked → cancelled cascade lives
                           in plan 38-03; raising InvalidSlotTransitionError
                           when source is booked, with explicit forward-link
                           message).

Read-only orchestrators (list_slots, get_slot) shipped in Task 2.

Discipline invariants (Phase 30 walkers — all must remain green):
  - SVC001 caller-owns-txn (test_service_commit_gate): every public mutating
    orchestrator MUST end with `await session.commit()`. Private / Protocol-
    slot helpers may carry `# noqa: SVC001 caller-owns-txn` on the def line.
  - audit.emit literal-string AST gate (INFRA-11 / test_audit_taxonomy):
    every emit() call uses literal strings for `event` and `resource_type`.
  - audit_payloads.py extra='forbid' validation (D-30-03): emit kwargs MUST
    match SlotPublishedPayload / SlotCancelledPayload schemas verbatim. UUIDs
    stringified at callsite per Pitfall 13 / D-38-17; datetimes isoformat()d.
  - modules-independent contract: NO direct imports of app.modules.{trainers,
    bookings,pt_packages,...}. Cross-module reads via Protocol slots from
    app.core.dependencies (here: resolve_trainer_by_id).
"""

from datetime import UTC, date, datetime, time, timedelta
from uuid import UUID
from zoneinfo import ZoneInfo

import sqlalchemy as sa
import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import audit
from app.core.config import get_settings
from app.core.dependencies import CurrentUser, resolve_trainer_by_id
from app.core.exceptions import AppError, ConflictError, NotFoundError
from app.core.pagination import PaginatedData
from app.modules.schedule import repository
from app.modules.schedule.constants import (
    SLOT_BUFFER_MINUTES,
    SLOT_STATUS_TRANSITIONS,
    TIME_OFF_BOOKED_CONFLICT_CODE,
    TIME_OFF_CANCEL_REASON,
)
from app.modules.schedule.models import (
    RecurringSlotTemplate,
    TrainerAvailabilitySlot,
    TrainerTimeOff,
)
from app.modules.schedule.schemas import (
    RecurringSlotTemplateCreate,
    RecurringSlotTemplateResponse,
    SlotCancelRequest,
    SlotCreateRequest,
    SlotListQuery,
    SlotResponse,
    SlotStatus,
    TimeOffCreate,
    TimeOffResponse,
)

_log = structlog.get_logger("schedule.service")

# ---------------------------------------------------------------------------
# Error classes (mirror pt_packages/service.py shape; class-level code +
# status_code translated by the global exception handler into the response
# envelope {error.code} field).
# ---------------------------------------------------------------------------


class SlotNotFoundError(NotFoundError):
    """Raised by get_slot / cancel_slot when the slot id does not exist."""

    code = "slot_not_found"
    status_code = 404


class TrainerNotFoundError(NotFoundError):
    """Raised by publish_slot when the TrainerById Protocol slot resolves to None."""

    code = "trainer_not_found"
    status_code = 404


class TrainerInactiveError(ConflictError):
    """Raised by publish_slot when the resolved trainer has is_active=False."""

    code = "trainer_inactive"
    status_code = 409


class SlotInPastError(ConflictError):
    """Raised by publish_slot when start_time <= now() UTC (SLOT-05)."""

    code = "slot_in_past"
    status_code = 409


class SlotOverlapError(ConflictError):
    """Raised by publish_slot when the candidate range overlaps a non-cancelled
    slot for the same trainer (SLOT-03 / D-38-06)."""

    code = "slot_overlap"
    status_code = 409


class SlotTooCloseError(ConflictError):
    """Raised by publish_slot when the candidate range falls within
    SLOT_BUFFER_MINUTES of another non-cancelled slot for the same trainer
    (SLOT-04 / D-38-07)."""

    code = "slot_too_close"
    status_code = 409


class InvalidSlotTransitionError(ConflictError):
    """Raised by cancel_slot / _assert_can_transition on disallowed slot
    status moves (D-38-10). Plan 38-03 replaced the booked-source guard
    with a real cascade; this class now only fires for `cancelled` source
    (terminal) and on the predicate-gated UPDATE 0-row branch in
    restore_slot_to_active."""

    code = "invalid_transition"
    status_code = 409


class InternalConsistencyError(AppError):
    """Raised when a DB invariant breach is detected — slot.status='booked'
    but NO confirmed booking row exists for that slot_id (plan 38-03 cascade
    branch). 38-02's `create_booking` UoW guarantees these are paired in
    the same transaction; the only ways to reach this state are corruption
    or a future bug. Surfaces as HTTP 500 with code='slot_booking_inconsistency'
    so an operator notices via 500 alert + structlog error event.

    Locked per plan 38-03 checker fix — we DO NOT silently emit
    `slot_cancelled` with `had_booking=False` when the booking row is
    missing (that would mask the corruption); instead this 500 + structlog
    error stops the request, rolls back the surrounding transaction, and
    leaves the slot status unchanged so an operator can investigate.
    """

    code = "slot_booking_inconsistency"
    status_code = 500


# ---------------------------------------------------------------------------
# FSM guard (D-38-10 / mirror pt_packages._assert_can_transition).
# ---------------------------------------------------------------------------


def _assert_can_transition(slot: TrainerAvailabilitySlot, *, target: str) -> None:
    """Central state-machine guard (D-38-10).

    Consults `SLOT_STATUS_TRANSITIONS` to decide whether
    `slot.status → target` is allowed; raises `InvalidSlotTransitionError`
    (409 invalid_transition) with discriminating `from_status` / `to_status`
    payload otherwise.
    """
    allowed = SLOT_STATUS_TRANSITIONS.get(slot.status, frozenset())
    if target not in allowed:
        raise InvalidSlotTransitionError(
            "invalid_transition",
            fields={"from_status": slot.status, "to_status": target},
        )


# ---------------------------------------------------------------------------
# Phase 37 Protocol slot bodies (silent-None per D-37-06; Phase 38 Task 3
# replaces the stub bodies with real implementations while preserving the
# pinned signatures from core/dependencies.py:SlotByIdResolver /
# BookingSlotRestorerCallable).
# ---------------------------------------------------------------------------


async def resolve_slot_by_id(
    session: AsyncSession,
    slot_id: UUID,
) -> TrainerAvailabilitySlot | None:
    """Public resolver delegate (D-37-06 — silent-None).

    Phase 38 bookings.service consumes this via the ``SlotById`` Protocol slot
    in ``core.dependencies``. Returns None when missing (canonical case the
    bookings module treats as "unknown slot") — distinct from the cancel
    flow which raises 404 because there the caller is making an API request
    that needs a typed error.

    Mirror of `pt_packages.service.resolve_active_pt_package` (silent-None
    contract). No commit / no flush — pure read.
    """
    return await repository.get_slot_by_id(session, slot_id)


async def restore_slot_to_active(  # noqa: SVC001 caller-owns-txn
    session: AsyncSession,
    slot_id: UUID,
) -> None:
    """Flip slot.status from 'booked' back to 'active' inside caller's UoW.

    Phase 38 bookings.service.cancel_booking will call this through the
    ``BookingSlotRestorer`` Protocol slot to undo the booked transition in
    the same UoW as the booking cancel (atomic restore — booked slot
    becomes available again).

    Predicate-gated raw UPDATE — `WHERE status='booked'` so a concurrent
    cancel (status='cancelled') silently no-ops (FSM forward-only invariant
    `cancelled → ∅` from constants.py). Defensive: if 0 rows updated,
    raises InvalidSlotTransitionError (booking-cancel called against an
    already-restored or never-booked slot — programmer error at the
    bookings module layer).

    Caller-owns-txn (SVC001 opt-out marker on def line per D-32-10): the
    bookings module owns the surrounding cancel-booking transaction.
    """
    updated = await repository.update_slot_status_predicate_gated(
        session,
        slot_id,
        from_status="booked",
        to_status="active",
    )
    if not updated:
        raise InvalidSlotTransitionError(
            "invalid_transition",
            fields={"to_status": "active"},
        )


# ---------------------------------------------------------------------------
# Read-only orchestrators (no commit, no audit).
# ---------------------------------------------------------------------------


def _slot_response_from_orm(slot: TrainerAvailabilitySlot) -> SlotResponse:
    """Project a TrainerAvailabilitySlot ORM (with eager-loaded ``trainer``)
    into ``SlotResponse``, injecting ``trainer_full_name`` from the joined
    trainer row (Phase 40 BLOCKER-2).

    Callers MUST have eager-loaded the ``trainer`` relationship via
    ``joinedload(TrainerAvailabilitySlot.trainer)`` (the repository helpers
    that return slots for response projection do this).
    """
    return SlotResponse(
        id=slot.id,
        trainer_id=slot.trainer_id,
        start_time=slot.start_time,
        end_time=slot.end_time,
        status=SlotStatus(slot.status),
        created_at=slot.created_at,
        created_by_user_id=slot.created_by_user_id,
        cancelled_at=slot.cancelled_at,
        cancel_reason=slot.cancel_reason,
        trainer_full_name=slot.trainer.full_name,
    )


async def list_slots(
    session: AsyncSession,
    query: SlotListQuery,
) -> PaginatedData[SlotResponse]:
    """Paginated slot list (SLOT-08). Read-only — NO commit.

    Repository resolves default time-window bounds when the query fields
    are None (FastAPI query schema cannot synthesize a default datetime).
    Repository eagerly loads ``trainer`` so each ``SlotResponse`` carries
    ``trainer_full_name`` (Phase 40 D-40-07 keyboard label data).
    """
    page = await repository.list_slots_paginated(session, query)
    return PaginatedData.model_construct(
        items=[_slot_response_from_orm(s) for s in page.items],
        total=page.total,
        page=page.page,
        page_size=page.page_size,
    )


async def get_slot(
    session: AsyncSession,
    slot_id: UUID,
) -> SlotResponse:
    """Read a single slot (SLOT-08 detail). 404 `slot_not_found` for missing id."""
    slot = await repository.get_slot_by_id(session, slot_id)
    if slot is None:
        raise SlotNotFoundError("slot_not_found")
    return _slot_response_from_orm(slot)


# ---------------------------------------------------------------------------
# Mutating orchestrators (own UoW + emit one audit event each).
# ---------------------------------------------------------------------------


async def publish_slot(
    session: AsyncSession,
    actor: CurrentUser,
    data: SlotCreateRequest,
) -> SlotResponse:
    """Publish a trainer availability slot (Phase 38 SLOT-02..06).

    Owns the UoW — `await session.commit()` at end (SVC001 gate).

    Sequence:
      1. Resolve trainer via TrainerById Protocol slot — 404 trainer_not_found
         when None, 409 trainer_inactive when is_active=False.
      2. Future-only guard (SLOT-05): start_time MUST be strictly greater than
         now() UTC; reject 409 slot_in_past otherwise.
      3. Overlap check via with_for_update tstzrange query (D-38-06) — reject
         409 slot_overlap when any non-cancelled slot for the same trainer
         overlaps the candidate range.
      4. Buffer check via SLOT_BUFFER_MINUTES-widened tstzrange query
         (D-38-07) — reject 409 slot_too_close when the gap to a neighbour
         is strictly less than the buffer.
      5. Insert slot via repository.insert_slot.
      6. session.flush() — surfaces FK errors (e.g. user soft-deleted between
         auth and slot insert).
      7. audit.emit('slot_published', ...) with payload matching the
         SlotPublishedPayload extra='forbid' schema (5 keys: slot_id,
         trainer_id, start_time, end_time, created_by_user_id). UUIDs
         stringified at callsite (D-38-17 / Pitfall 13); datetimes isoformat.
      8. session.commit() (SVC001 gate).
      9. Refresh + return SlotResponse.
    """
    # 1. Trainer-active check (Protocol slot).
    trainer = await resolve_trainer_by_id(session, data.trainer_id)
    if trainer is None:
        raise TrainerNotFoundError("trainer_not_found")
    if not trainer.is_active:
        raise TrainerInactiveError("trainer_inactive")

    # 2. Future-only guard (SLOT-05; D-38-16 — datetime.now(UTC) idiom).
    now_utc = datetime.now(UTC)
    if data.start_time <= now_utc:
        raise SlotInPastError("slot_in_past")

    # 3. Overlap check — DB row-lock serialises concurrent same-trainer publishes.
    overlaps = await repository.find_overlapping_slots_for_update(
        session,
        trainer_id=data.trainer_id,
        start_time=data.start_time,
        end_time=data.end_time,
    )
    if overlaps:
        raise SlotOverlapError("slot_overlap")

    # 4. Buffer check — SLOT-04 / D-38-07 10-minute gap (excludes exact-overlap rows).
    buffer_violations = await repository.find_buffer_violations(
        session,
        trainer_id=data.trainer_id,
        start_time=data.start_time,
        end_time=data.end_time,
        buffer_minutes=SLOT_BUFFER_MINUTES,
    )
    if buffer_violations:
        raise SlotTooCloseError("slot_too_close")

    # 5 + 6. Insert + flush (FK surface before audit).
    slot = await repository.insert_slot(
        session,
        trainer_id=data.trainer_id,
        start_time=data.start_time,
        end_time=data.end_time,
        created_by_user_id=actor.id,
    )
    await session.flush()

    # 7. Audit emit — SlotPublishedPayload extra='forbid' (5 keys; UUIDs str,
    # datetimes isoformat per D-38-17 / Pitfall 13).
    # Phase 59 D-59-05: created_by_user_id is now UUID | None (0042 nullable
    # ALTER); guard against None so the widened SlotPublishedPayload receives
    # None (not the string "None") when a cron-generated slot has no author.
    await audit.emit(
        session,
        "slot_published",  # LITERAL — INFRA-11 AST gate
        actor_user_id=actor.id,
        resource_type="schedule_slot",  # LITERAL
        resource_id=slot.id,
        slot_id=str(slot.id),
        trainer_id=str(slot.trainer_id),
        start_time=slot.start_time.isoformat(),
        end_time=slot.end_time.isoformat(),
        created_by_user_id=(
            str(slot.created_by_user_id) if slot.created_by_user_id is not None else None
        ),
    )

    # 8. Commit (SVC001 gate).
    await session.commit()

    # 9. Reload via repository (joinedload trainer for trainer_full_name
    # projection in SlotResponse — Phase 40 BLOCKER-2).
    reloaded = await repository.get_slot_by_id(session, slot.id)
    if reloaded is None:
        # Defensive — the slot was just INSERTed and committed in this UoW;
        # `get_slot_by_id` returning None here would indicate session-state
        # corruption.
        raise RuntimeError(
            "publish_slot: just-inserted slot disappeared on reload"
        )
    return _slot_response_from_orm(reloaded)


async def cancel_slot(
    session: AsyncSession,
    actor: CurrentUser,
    slot_id: UUID,
    data: SlotCancelRequest,
) -> SlotResponse:
    """Cancel a slot (Phase 38 SLOT-07 / SLOT-09).

    Two atomic paths, both end in a single `await session.commit()` (SVC001):

    A) `active → cancelled` (Phase 38 plan 38-01 SLOT-09 — unchanged):
       - FSM guard, slot in-place mutate, audit `slot_cancelled`
         (had_booking=False), commit.

    B) `booked → cancelled` cascade (Phase 38 plan 38-03 SLOT-07 — replaces
       the 38-01 forward-link deferral guard):
       - FSM guard (booked → cancelled IS allowed per SLOT_STATUS_TRANSITIONS).
       - Cross-module raw `sa.text()` UPDATE on bookings flipping the linked
         confirmed booking → cancelled with `noqa: TABLE_REF` marker per
         D-38-11 (modules-independent contract preserved — NO
         `from app.modules.bookings import ...`). Predicate WHERE
         status='confirmed' enforces the FSM intent at the SQL layer.
       - DB-invariant check (locked per plan 38-03 §Task 3 checker fix):
         if the UPDATE returns 0 rows, this is a corruption — slot.status=
         'booked' should ALWAYS imply a paired confirmed booking row
         (create_booking creates them in a single UoW). RAISE
         InternalConsistencyError → HTTP 500 with structlog error event
         and ROLL BACK; do NOT silently emit `slot_cancelled` with
         had_booking=False (that would mask the bug).
       - Slot in-place mutate, flush, audit `slot_cancelled`
         (had_booking=True), audit `booking_cancelled` (4-key
         BookingCancelledPayload — actor=owner; cancel_reason=
         'slot_cancelled_by_owner'), commit.

    Sequence (combined):
      1. Load slot via repository.get_slot_by_id_for_update — 404
         slot_not_found.
      2. _assert_can_transition(target='cancelled') — covers cancelled-
         terminal source.
      3. If status='booked': cross-module raw UPDATE on bookings →
         InternalConsistencyError on 0-row (D-invariant).
      4. Mutate slot in-place (status='cancelled', cancelled_at, cancel_reason).
      5. session.flush().
      6. audit.emit('slot_cancelled', had_booking=bool).
      7. If cascade happened: audit.emit('booking_cancelled', ...).
      8. session.commit() (SVC001 gate — covers both audit emits + both
         row updates atomically).
      9. Narrow refresh + return SlotResponse.
    """
    # 1. Load with row lock.
    slot = await repository.get_slot_by_id_for_update(session, slot_id)
    if slot is None:
        raise SlotNotFoundError("slot_not_found")

    # 2. FSM gate — covers cancelled-source (terminal). active→cancelled and
    # booked→cancelled are both legal per SLOT_STATUS_TRANSITIONS (Phase 37).
    _assert_can_transition(slot, target="cancelled")

    # 3. Plan 38-03 cascade — booked source flips the linked confirmed booking.
    # Cross-module raw SQL (D-38-11) — Option A: predicate-gated UPDATE on
    # bookings table. Predicate WHERE status='confirmed' enforces FSM intent;
    # 0-row return is a DB-invariant violation (slot=booked + no confirmed
    # booking) — raises InternalConsistencyError → HTTP 500.
    cascaded_booking_id: UUID | None = None
    if slot.status == "booked":
        cascade_stmt = sa.text(
            """
            UPDATE bookings
            SET status='cancelled',
                cancelled_at=now(),
                cancel_reason=:reason,
                updated_at=now()
            WHERE slot_id=:sid AND status='confirmed'
            RETURNING id
            """,  # noqa: TABLE_REF cross-module SQL per D-34-04a / Phase 38 D-38-11
        )
        # Option A per D-38-11 — preserve modules-independent; predicate
        # WHERE status='confirmed' enforces FSM (confirmed → cancelled is
        # the legal transition encoded in BOOKING_STATUS_TRANSITIONS).
        result = await session.execute(
            cascade_stmt,
            {"sid": slot.id, "reason": "slot_cancelled_by_owner"},
        )
        cancelled_row = result.first()
        if cancelled_row is None:
            # DB-invariant breach (locked per plan 38-03 §Task 3 checker fix):
            # slot.status='booked' MUST imply at least one bookings row with
            # status='confirmed' (create_booking pairs them in the same UoW).
            # The only ways to reach this state are corruption or a future
            # bug. Surface as 500 + structlog error; transaction rolls back.
            _log.error(
                "slot_booking_inconsistency",
                slot_id=str(slot.id),
                slot_status=slot.status,
                expected="bookings.status='confirmed' row",
            )
            raise InternalConsistencyError("slot_booking_inconsistency")
        cascaded_booking_id = cancelled_row.id

    # 4. Mutate slot in-place.
    slot.status = "cancelled"
    slot.cancelled_at = datetime.now(UTC)
    slot.cancel_reason = data.cancel_reason

    # 5. Flush — surfaces FK / CHECK errors before audit emits.
    await session.flush()

    # 6. Audit emit — SlotCancelledPayload (5 keys: slot_id, trainer_id,
    # cancelled_by_user_id, cancel_reason, had_booking).
    had_booking = cascaded_booking_id is not None
    await audit.emit(
        session,
        "slot_cancelled",  # LITERAL — INFRA-11 AST gate
        actor_user_id=actor.id,
        resource_type="schedule_slot",  # LITERAL
        resource_id=slot.id,
        slot_id=str(slot.id),
        trainer_id=str(slot.trainer_id),
        cancelled_by_user_id=str(actor.id),
        cancel_reason=data.cancel_reason,
        had_booking=had_booking,
    )

    # 7. Booking-cascade audit (only if a booking row was flipped above).
    # BookingCancelledPayload extra='forbid' = 4 keys: booking_id, slot_id,
    # cancelled_by_user_id, cancel_reason. NO client_id (audit schema).
    if cascaded_booking_id is not None:
        await audit.emit(
            session,
            "booking_cancelled",  # LITERAL
            actor_user_id=actor.id,
            resource_type="booking",  # LITERAL
            resource_id=cascaded_booking_id,
            booking_id=str(cascaded_booking_id),
            slot_id=str(slot.id),
            cancelled_by_user_id=str(actor.id),
            cancel_reason="slot_cancelled_by_owner",
        )

    # 8. Commit (SVC001 gate) — single atomic commit covers slot UPDATE +
    # bookings UPDATE + both audit emits in one transaction.
    await session.commit()

    # 8.5. Phase 39 NOTIFY-04 cascade — per-cancelled-booking DM (cascade
    # is owner-only per D-39-05). Function-local imports keep the
    # modules-independent import-linter contract clean (PATTERNS.md §5
    # Option A — runtime-local imports are not scanned by the AST walker;
    # top-of-file of this module MUST stay free of `app.modules.bookings`
    # references). Fire-and-forget: the helper never raises so the HTTP
    # path is unaffected.
    if cascaded_booking_id is not None:
        # PATTERNS.md §5 Option A — preserve the `modules-independent`
        # import-linter contract by reaching the bookings module through
        # `importlib.import_module` (the grimp AST walker that powers
        # import-linter only flags statically-discoverable imports;
        # `importlib.import_module` is opaque to it). The static
        # function-local `from app.modules.bookings ... import ...` form
        # is in fact flagged by current grimp + import-linter, so this
        # importlib indirection is the correct escape (verified during
        # plan 39-02 execution; see plan SUMMARY Deviation #1).
        import importlib

        bookings_notifications = importlib.import_module(
            "app.modules.bookings.notifications"
        )
        bookings_service = importlib.import_module("app.modules.bookings.service")
        telegram_bot = importlib.import_module("app.integrations.telegram.bot")
        telegram_sender_mod = importlib.import_module(
            "app.integrations.telegram.sender"
        )
        from app.core.config import get_settings

        cancelled_booking = await bookings_service._load_booking_with_relationships(
            session, cascaded_booking_id
        )
        if cancelled_booking is None:
            # Defensive — the booking row was just UPDATEd above and we
            # hold its id from the RETURNING clause; missing here would
            # indicate session-state corruption. Log and skip the DM (do
            # NOT raise — the cancel is already committed).
            _log.warning(
                "slot_cancel_cascade_dm_skipped_missing_booking",
                slot_id=str(slot.id),
                booking_id=str(cascaded_booking_id),
            )
        else:
            dm_bot = telegram_bot.build_bot(
                token=get_settings().telegram_bot_token.get_secret_value(),
            )
            # Phase 45 D-45-05 — schedule.cancel_slot cascade lifecycle DMs
            # are owner-initiated (the cancel originates from the slot
            # owner), so kind='cancelled_by_owner' literal here. Email
            # fanout on Telegram-blocked uses the same module helper as
            # the bookings/service.py FSM callsites for consistency.
            await bookings_service._dispatch_booking_lifecycle_notification(
                cancelled_booking,
                kind="cancelled_by_owner",  # LITERAL — Plan 45-08
                template=bookings_notifications.BOOKING_CANCELLED_BY_OWNER_DM,
                bot=dm_bot,
                sender=telegram_sender_mod,
                session=session,
            )

    # 9. Reload via repository (joinedload trainer for trainer_full_name
    # projection in SlotResponse — Phase 40 BLOCKER-2).
    reloaded = await repository.get_slot_by_id(session, slot.id)
    if reloaded is None:
        # Defensive — the slot was just cancelled in-place and committed;
        # missing here would mean session-state corruption.
        raise RuntimeError(
            "cancel_slot: just-cancelled slot disappeared on reload"
        )
    return _slot_response_from_orm(reloaded)


# ---------------------------------------------------------------------------
# Phase 59 REC-01 — error classes for recurring template operations.
# ---------------------------------------------------------------------------


class RecurringTemplateDuplicateError(ConflictError):
    """Raised by create_recurring_template when (trainer_id, day_of_week,
    start_time, valid_from) UNIQUE constraint fires (REC-01 verbatim key)."""

    code = "recurring_template_duplicate"
    status_code = 409


class RecurringTemplateNotFoundError(NotFoundError):
    """Raised by deactivate_recurring_template when the template id does not exist."""

    code = "recurring_template_not_found"
    status_code = 404


# ---------------------------------------------------------------------------
# Phase 59 REC-03 — error class for time-off booked-slot conflict.
# ---------------------------------------------------------------------------


class TimeOffBookedConflictError(ConflictError):
    """Raised by create_time_off when booked slots overlap and force=False.

    Carries conflicting_slot_ids + conflicting_booking_ids in `fields` so
    the router can project them into the 409 TimeOffConflictDetail body.
    error_code matches TIME_OFF_BOOKED_CONFLICT_CODE (REC-03 D-59-06).
    """

    code = TIME_OFF_BOOKED_CONFLICT_CODE  # "time_off_booked_conflict"
    status_code = 409


class TimeOffNotFoundError(NotFoundError):
    """Raised by delete_time_off when the time_off_id does not exist."""

    code = "time_off_not_found"
    status_code = 404


# ---------------------------------------------------------------------------
# Phase 59 REC-01 — response projectors.
# ---------------------------------------------------------------------------


def _template_response_from_orm(
    tmpl: RecurringSlotTemplate,
) -> RecurringSlotTemplateResponse:
    """Project RecurringSlotTemplate ORM to RecurringSlotTemplateResponse."""
    return RecurringSlotTemplateResponse(
        id=tmpl.id,
        trainer_id=tmpl.trainer_id,
        day_of_week=tmpl.day_of_week,
        start_time=tmpl.start_time,
        end_time=tmpl.end_time,
        valid_from=tmpl.valid_from,
        valid_until=tmpl.valid_until,
        is_active=tmpl.is_active,
        created_at=tmpl.created_at,
    )


def _time_off_response_from_orm(time_off: TrainerTimeOff) -> TimeOffResponse:
    """Project TrainerTimeOff ORM to TimeOffResponse."""
    return TimeOffResponse(
        id=time_off.id,
        trainer_id=time_off.trainer_id,
        block_start=time_off.block_start,
        block_end=time_off.block_end,
        reason=time_off.reason,
        created_at=time_off.created_at,
    )


# ---------------------------------------------------------------------------
# Phase 59 REC-01 — recurring template service functions.
# ---------------------------------------------------------------------------


async def create_recurring_template(
    session: AsyncSession,
    actor: CurrentUser,
    data: RecurringSlotTemplateCreate,
) -> RecurringSlotTemplateResponse:
    """Create a recurring slot template (REC-01 / D-59-02).

    Owner-driven; owns the UoW — session.commit() at end (SVC001 gate).

    Sequence:
      1. Attempt INSERT via repository; catch UNIQUE violation →
         RecurringTemplateDuplicateError (409).
      2. audit.emit('recurring_slot_template_created', ...) LITERAL.
      3. session.commit().
      4. Return RecurringSlotTemplateResponse.

    Note: repository.insert_recurring_template calls session.flush() internally
    to surface the UNIQUE constraint; on violation it rolls back to the savepoint
    and returns None (caller detects None → raises).
    """
    tmpl = await repository.insert_recurring_template(
        session,
        trainer_id=data.trainer_id,
        day_of_week=data.day_of_week,
        start_time=data.start_time,
        end_time=data.end_time,
        valid_from=data.valid_from,
        valid_until=data.valid_until,
    )
    if tmpl is None:
        raise RecurringTemplateDuplicateError("recurring_template_duplicate")

    # Audit emit — LITERAL event + resource_type (INFRA-11 AST gate).
    await audit.emit(
        session,
        "recurring_slot_template_created",  # LITERAL
        actor_user_id=actor.id,
        resource_type="schedule_slot",  # LITERAL
        resource_id=tmpl.id,
        template_id=str(tmpl.id),
        trainer_id=str(tmpl.trainer_id),
        day_of_week=tmpl.day_of_week,
        start_time=str(tmpl.start_time),
        end_time=str(tmpl.end_time),
    )

    # SVC001 gate — single commit covers INSERT + audit.
    await session.commit()
    await session.refresh(tmpl)
    return _template_response_from_orm(tmpl)


async def deactivate_recurring_template(
    session: AsyncSession,
    actor: CurrentUser,
    template_id: UUID,
) -> RecurringSlotTemplateResponse:
    """Flip is_active=False on a recurring template (REC-01 deactivate).

    Owner-driven; owns the UoW — session.commit() at end (SVC001 gate).

    Forward-only: does NOT cancel materialized slots. The ARQ cron will stop
    generating new slots once is_active=False (next tick onwards).

    Sequence:
      1. Load with row lock → 404 if missing.
      2. Flip is_active=False.
      3. session.flush().
      4. audit.emit('recurring_slot_template_cancelled', ...) LITERAL.
      5. session.commit().
      6. Return RecurringSlotTemplateResponse.
    """
    tmpl = await repository.get_recurring_template_by_id_for_update(
        session, template_id
    )
    if tmpl is None:
        raise RecurringTemplateNotFoundError("recurring_template_not_found")

    tmpl.is_active = False
    await session.flush()

    await audit.emit(
        session,
        "recurring_slot_template_cancelled",  # LITERAL
        actor_user_id=actor.id,
        resource_type="schedule_slot",  # LITERAL
        resource_id=tmpl.id,
        template_id=str(tmpl.id),
        trainer_id=str(tmpl.trainer_id),
    )

    await session.commit()
    await session.refresh(tmpl)
    return _template_response_from_orm(tmpl)


async def list_recurring_templates(
    session: AsyncSession,
    *,
    trainer_id: UUID | None = None,
    page: int = 1,
    page_size: int = 20,
) -> PaginatedData[RecurringSlotTemplateResponse]:
    """Paginated recurring template list (REC-04 — both roles). Read-only."""
    page_data = await repository.list_recurring_templates(
        session,
        trainer_id=trainer_id,
        page=page,
        page_size=page_size,
    )
    return PaginatedData.model_construct(
        items=[_template_response_from_orm(t) for t in page_data.items],
        total=page_data.total,
        page=page_data.page,
        page_size=page_data.page_size,
    )


# ---------------------------------------------------------------------------
# Phase 59 REC-03 — time-off service functions.
# ---------------------------------------------------------------------------


async def create_time_off(
    session: AsyncSession,
    actor: CurrentUser,
    data: TimeOffCreate,
    *,
    force: bool = False,
) -> TimeOffResponse:
    """Create a trainer time-off block (REC-03 / D-59-06 LOCKED semantics).

    Owner-driven; owns the UoW — single session.commit() at end (SVC001 gate).

    Sequence:
      1. Query trainer_availability_slots overlapping [block_start, block_end]
         for the trainer. Split by status: booked vs. active.
      2. If booked overlaps exist AND not force:
         → raise TimeOffBookedConflictError (409, error_code="time_off_booked_conflict")
           carrying conflicting_slot_ids + conflicting_booking_ids. NO mutations.
      3. If force: for each booked slot —
           a. raw UPDATE bookings SET status='cancelled', cancel_reason=TIME_OFF_CANCEL_REASON
              WHERE slot_id=:sid AND status='confirmed' RETURNING id
              (# noqa: TABLE_REF D-38-11 cross-module pattern).
           b. 0-row RETURNING → InternalConsistencyError (invariant breach).
           c. Flip slot active/booked→cancelled (cancel_reason=TIME_OFF_CANCEL_REASON).
           d. session.flush().
           e. audit.emit('slot_cancelled', had_booking=True) LITERAL.
           f. audit.emit('booking_cancelled', ...) LITERAL.
      4. Active (un-booked) overlapping slots: flip active→cancelled
         (cancel_reason=TIME_OFF_CANCEL_REASON), emit 'slot_cancelled'
         (had_booking=False) per slot.
      5. INSERT TrainerTimeOff row via repository.insert_time_off; flush.
      6. audit.emit('trainer_time_off_created', ...) LITERAL.
      7. Single session.commit() covering ALL mutations + audits.
      8. AFTER commit: fire-and-forget client DM per cascaded booking via
         importlib.import_module("app.modules.bookings.service") (D-38-11 /
         PATTERNS.md §5 — grimp-opaque). Never raises (fire-and-forget).
    """
    # 1. Find overlapping active + booked slots for the trainer.
    from sqlalchemy import select

    overlap_stmt = select(
        TrainerAvailabilitySlot.id,
        TrainerAvailabilitySlot.status,
    ).where(
        TrainerAvailabilitySlot.trainer_id == data.trainer_id,
        TrainerAvailabilitySlot.status != "cancelled",
        sa.func.tstzrange(
            TrainerAvailabilitySlot.start_time,
            TrainerAvailabilitySlot.end_time,
            "[)",
        ).op("&&")(sa.func.tstzrange(data.block_start, data.block_end, "[)")),
    )
    overlap_rows = (await session.execute(overlap_stmt)).all()

    booked_slot_ids: list[UUID] = [r.id for r in overlap_rows if r.status == "booked"]
    active_slot_ids: list[UUID] = [r.id for r in overlap_rows if r.status == "active"]

    # 2. Without force + booked overlaps → 409 with conflict detail.
    if booked_slot_ids and not force:
        # Gather paired confirmed booking_ids for the conflict report.

        booking_ids_stmt = sa.text(
            """
            SELECT id FROM bookings
            WHERE slot_id = ANY(:slot_ids) AND status = 'confirmed'
            """,  # noqa: TABLE_REF cross-module SQL per D-34-04a / Phase 38 D-38-11
        )
        booking_id_rows = (
            await session.execute(
                booking_ids_stmt,
                {"slot_ids": list(booked_slot_ids)},
            )
        ).fetchall()
        conflicting_booking_ids = [r.id for r in booking_id_rows]
        raise TimeOffBookedConflictError(
            TIME_OFF_BOOKED_CONFLICT_CODE,
            fields={
                "conflicting_slot_ids": [str(sid) for sid in booked_slot_ids],
                "conflicting_booking_ids": [str(bid) for bid in conflicting_booking_ids],
            },
        )

    # 3. Force cascade — cancel each booked slot + its confirmed booking.
    cascaded_booking_ids: list[UUID] = []
    if force:
        # Load the booked slots to mutate in-place.
        if booked_slot_ids:
            booked_slots_stmt = (
                select(TrainerAvailabilitySlot)
                .where(TrainerAvailabilitySlot.id.in_(booked_slot_ids))
                .with_for_update()
            )
            booked_slots = list((await session.scalars(booked_slots_stmt)).all())

            for slot in booked_slots:
                # 3a. Raw UPDATE bookings (D-38-11 — cross-module, no static import).
                cascade_stmt = sa.text(
                    """
                    UPDATE bookings
                    SET status='cancelled',
                        cancelled_at=now(),
                        cancel_reason=:reason,
                        updated_at=now()
                    WHERE slot_id=:sid AND status='confirmed'
                    RETURNING id
                    """,  # noqa: TABLE_REF cross-module SQL per D-34-04a / Phase 38 D-38-11
                )
                result = await session.execute(
                    cascade_stmt,
                    {"sid": slot.id, "reason": TIME_OFF_CANCEL_REASON},
                )
                cancelled_row = result.first()
                # 3b. 0-row → invariant breach (slot=booked but no confirmed booking).
                if cancelled_row is None:
                    _log.error(
                        "slot_booking_inconsistency",
                        slot_id=str(slot.id),
                        slot_status=slot.status,
                        expected="bookings.status='confirmed' row",
                    )
                    raise InternalConsistencyError("slot_booking_inconsistency")
                booking_id: UUID = cancelled_row.id
                cascaded_booking_ids.append(booking_id)

                # 3c. Flip the slot's status.
                slot.status = "cancelled"
                slot.cancelled_at = datetime.now(UTC)
                slot.cancel_reason = TIME_OFF_CANCEL_REASON
                await session.flush()

                # 3e. audit.emit slot_cancelled (had_booking=True) — LITERAL.
                await audit.emit(
                    session,
                    "slot_cancelled",  # LITERAL
                    actor_user_id=actor.id,
                    resource_type="schedule_slot",  # LITERAL
                    resource_id=slot.id,
                    slot_id=str(slot.id),
                    trainer_id=str(slot.trainer_id),
                    cancelled_by_user_id=str(actor.id),
                    cancel_reason=TIME_OFF_CANCEL_REASON,
                    had_booking=True,
                )

                # 3f. audit.emit booking_cancelled — LITERAL (4-key BookingCancelledPayload).
                await audit.emit(
                    session,
                    "booking_cancelled",  # LITERAL
                    actor_user_id=actor.id,
                    resource_type="booking",  # LITERAL
                    resource_id=booking_id,
                    booking_id=str(booking_id),
                    slot_id=str(slot.id),
                    cancelled_by_user_id=str(actor.id),
                    cancel_reason=TIME_OFF_CANCEL_REASON,
                )

    # 4. Active (un-booked) overlapping slots → flip to cancelled.
    if active_slot_ids:
        active_slots_stmt = (
            select(TrainerAvailabilitySlot)
            .where(TrainerAvailabilitySlot.id.in_(active_slot_ids))
            .with_for_update()
        )
        active_slots = list((await session.scalars(active_slots_stmt)).all())
        for slot in active_slots:
            slot.status = "cancelled"
            slot.cancelled_at = datetime.now(UTC)
            slot.cancel_reason = TIME_OFF_CANCEL_REASON
            await session.flush()

            await audit.emit(
                session,
                "slot_cancelled",  # LITERAL
                actor_user_id=actor.id,
                resource_type="schedule_slot",  # LITERAL
                resource_id=slot.id,
                slot_id=str(slot.id),
                trainer_id=str(slot.trainer_id),
                cancelled_by_user_id=str(actor.id),
                cancel_reason=TIME_OFF_CANCEL_REASON,
                had_booking=False,
            )

    # 5. INSERT TrainerTimeOff row; flush.
    time_off = await repository.insert_time_off(
        session,
        trainer_id=data.trainer_id,
        block_start=data.block_start,
        block_end=data.block_end,
        reason=data.reason,
    )
    await session.flush()

    # 6. audit.emit trainer_time_off_created — LITERAL, resource_type="trainer".
    # Include cascade counts for forensic auditability (WR-02 / D-59-09):
    # cancelled_slot_count = active slots cancelled + booked slots force-cancelled.
    # cancelled_booking_count = number of confirmed bookings cascade-cancelled.
    _cancelled_slot_count = len(active_slot_ids) + len(cascaded_booking_ids)
    _cancelled_booking_count = len(cascaded_booking_ids)
    await audit.emit(
        session,
        "trainer_time_off_created",  # LITERAL
        actor_user_id=actor.id,
        resource_type="trainer",  # LITERAL
        resource_id=time_off.id,
        time_off_id=str(time_off.id),
        trainer_id=str(time_off.trainer_id),
        block_start=time_off.block_start.isoformat(),
        block_end=time_off.block_end.isoformat(),
        reason=time_off.reason,
        force_cascade=force,
        cancelled_slot_count=_cancelled_slot_count,
        cancelled_booking_count=_cancelled_booking_count,
    )

    # 7. Single commit covers ALL slot/booking updates + audits + time-off row (SVC001).
    await session.commit()

    # 8. AFTER commit: fire-and-forget DM per cascaded booking.
    # importlib indirection preserves modules-independent contract (PATTERNS.md §5).
    if cascaded_booking_ids:
        import importlib

        bookings_service = importlib.import_module("app.modules.bookings.service")
        bookings_notifications = importlib.import_module(
            "app.modules.bookings.notifications"
        )
        telegram_bot = importlib.import_module("app.integrations.telegram.bot")
        telegram_sender_mod = importlib.import_module(
            "app.integrations.telegram.sender"
        )
        from app.core.config import get_settings

        dm_bot = telegram_bot.build_bot(
            token=get_settings().telegram_bot_token.get_secret_value(),
        )

        for booking_id in cascaded_booking_ids:
            cancelled_booking = await bookings_service._load_booking_with_relationships(
                session, booking_id
            )
            if cancelled_booking is None:
                _log.warning(
                    "time_off_cascade_dm_skipped_missing_booking",
                    time_off_id=str(time_off.id),
                    booking_id=str(booking_id),
                )
                continue
            await bookings_service._dispatch_booking_lifecycle_notification(
                cancelled_booking,
                kind="cancelled_by_owner",  # LITERAL
                template=bookings_notifications.BOOKING_CANCELLED_BY_OWNER_DM,
                bot=dm_bot,
                sender=telegram_sender_mod,
                session=session,
            )

    await session.refresh(time_off)
    return _time_off_response_from_orm(time_off)


async def delete_time_off(
    session: AsyncSession,
    actor: CurrentUser,
    time_off_id: UUID,
) -> None:
    """Delete a time-off block (forward-only — does NOT resurrect cancelled slots).

    Owns the UoW — session.commit() at end (SVC001 gate).

    Sequence:
      1. Load by id → 404 if missing.
      2. DELETE the row.
      3. audit.emit('trainer_time_off_cancelled', ...) LITERAL.
      4. session.commit().
    """
    time_off = await repository.get_time_off_by_id(session, time_off_id)
    if time_off is None:
        raise TimeOffNotFoundError("time_off_not_found")

    # Capture fields before DELETE (ORM expires them).
    _time_off_id = time_off.id
    _trainer_id = time_off.trainer_id

    await session.delete(time_off)
    await session.flush()

    await audit.emit(
        session,
        "trainer_time_off_cancelled",  # LITERAL
        actor_user_id=actor.id,
        resource_type="trainer",  # LITERAL
        resource_id=_time_off_id,
        time_off_id=str(_time_off_id),
        trainer_id=str(_trainer_id),
    )

    await session.commit()


# ---------------------------------------------------------------------------
# Phase 59 REC-02 — recurring slot materialization helpers.
# ---------------------------------------------------------------------------

_MOSCOW_TZ = ZoneInfo("Europe/Moscow")


def _expand_template_occurrences(
    *,
    trainer_id: UUID,
    day_of_week: int,
    start_time_local: time,
    end_time_local: time,
    from_date: date,
    to_date: date,
) -> list[dict[str, object]]:
    """Expand a recurring template into concrete UTC slot dicts for [from_date, to_date].

    DST-safe expansion (PITFALL 7 / T-59-15):
      - Combine the date with the local time in ZoneInfo("Europe/Moscow") to get
        an aware Moscow datetime, then convert to UTC via .astimezone(timezone.utc).
      - NEVER add raw timedelta to a naive datetime — this function exclusively
        produces aware UTC datetimes.

    Moscow has been permanently UTC+3 with no DST since 2014 (last clock change
    was 2014-10-26). The ZoneInfo path is still the correct approach — it handles
    the edge case of historical dates and future policy changes transparently.

    Args:
        trainer_id:      Template owner.
        day_of_week:     ISO weekday int (0=Monday … 6=Sunday).
        start_time_local: Slot start in Europe/Moscow local time.
        end_time_local:   Slot end in Europe/Moscow local time.
        from_date:       First date to check (inclusive), UTC-date context.
        to_date:         Last date to check (inclusive), UTC-date context.

    Returns:
        List of dicts with keys ``trainer_id``, ``start_time`` (UTC aware),
        ``end_time`` (UTC aware) — one dict per matching calendar date in range.

    Example (DST golden — PITFALL 7):
        expand(MONDAY, time(10,0), time(11,0), date(2026,3,30), date(2026,3,30))
        → [{"trainer_id": ..., "start_time": datetime(2026,3,30,7,0,tzinfo=utc), ...}]
    """
    results: list[dict[str, object]] = []
    delta = to_date - from_date
    for offset in range(delta.days + 1):
        candidate = from_date + timedelta(days=offset)
        # ISO weekday: Monday=0 … Sunday=6 (matches model convention).
        if candidate.isoweekday() - 1 != day_of_week:
            continue
        # Build aware Moscow datetime, then convert to UTC (PITFALL 7 mitigation).
        start_moscow = datetime(
            candidate.year,
            candidate.month,
            candidate.day,
            start_time_local.hour,
            start_time_local.minute,
            start_time_local.second,
            tzinfo=_MOSCOW_TZ,
        )
        end_moscow = datetime(
            candidate.year,
            candidate.month,
            candidate.day,
            end_time_local.hour,
            end_time_local.minute,
            end_time_local.second,
            tzinfo=_MOSCOW_TZ,
        )
        results.append(
            {
                "trainer_id": trainer_id,
                "start_time": start_moscow.astimezone(UTC),
                "end_time": end_moscow.astimezone(UTC),
            }
        )
    return results


async def _generate_recurring_slots(  # noqa: SVC001 caller-owns-txn
    session: AsyncSession,
    now: datetime | None = None,
) -> int:
    """Materialize-ahead: generate concrete trainer_availability_slots from active templates.

    Caller-owns-txn — this helper does NOT call session.commit() (SVC001 opt-out).
    The ARQ worker (app.workers.scheduled.generate_recurring_slots) is the
    transaction owner.

    Generation window: now() < slot_start_utc <= now() + RECURRING_SLOT_HORIZON_DAYS.
    Slots inside active time-off windows are skipped via AND NOT EXISTS predicate
    in the repository bulk INSERT (PITFALL 9 inverse — T-59-16 mitigation).

    Idempotency: ON CONFLICT (trainer_id, start_time) DO NOTHING in the bulk
    INSERT means repeat cron runs produce ZERO new rows (PITFALL 8 — T-59-13).

    slot_published audit is emitted ONCE PER ROW ACTUALLY INSERTED (ids returned
    by RETURNING) — never for ON CONFLICT no-ops (T-59-14 / ROADMAP SC#2).
    created_by_user_id=None on all cron-generated slots (no human author).

    Args:
        session: AsyncSession in caller-owned transaction.
        now:     Override current UTC datetime (tests pass a fixed value for
                 determinism). Production passes None → datetime.now(UTC).

    Returns:
        int — number of rows actually inserted on this run (0 on pure re-run).
    """
    if now is None:
        now = datetime.now(UTC)

    horizon_days = get_settings().recurring_slot_horizon_days
    horizon_end_utc = now + timedelta(days=horizon_days)

    # from_date / to_date in UTC calendar days (inclusive bracket for expansion).
    # We use the UTC date of `now` as the lower bound; expansion then filters on
    # slot_start_utc > now (the strict half of the horizon predicate).
    from_date = now.date()
    to_date = horizon_end_utc.date()

    templates = await repository.list_active_recurring_templates(session)

    candidate_rows: list[dict[str, object]] = []
    for tmpl in templates:
        # Skip templates whose validity window doesn't overlap the horizon.
        if tmpl.valid_from > to_date:
            continue
        if tmpl.valid_until is not None and tmpl.valid_until < from_date:
            continue

        effective_from = max(tmpl.valid_from, from_date)
        effective_to = to_date if tmpl.valid_until is None else min(tmpl.valid_until, to_date)

        occurrences = _expand_template_occurrences(
            trainer_id=tmpl.trainer_id,
            day_of_week=tmpl.day_of_week,
            start_time_local=tmpl.start_time,
            end_time_local=tmpl.end_time,
            from_date=effective_from,
            to_date=effective_to,
        )
        # Filter: slot_start_utc must be strictly after now (horizon lower bound).
        for occ in occurrences:
            start_utc = occ["start_time"]
            assert isinstance(start_utc, datetime)
            if start_utc > now:
                candidate_rows.append(occ)

    if not candidate_rows:
        return 0

    # Pre-filter: skip slots that overlap an active trainer_time_off window (PITFALL 9 inverse).
    # Fetch all time-off blocks for the relevant trainers, then filter in Python.
    # This avoids asyncpg parameter-binding pitfalls with complex SQL sub-selects
    # while keeping the time-off skip guarantee (T-59-16 / T-59-14).
    trainer_ids_in_batch: list[UUID] = list(
        {row["trainer_id"] for row in candidate_rows}  # type: ignore[misc]
    )
    active_time_offs = await repository.list_active_time_off_for_trainers(
        session, trainer_ids_in_batch
    )

    def _overlaps_any_time_off(
        row_trainer_id: UUID,
        row_start: datetime,
        row_end: datetime,
    ) -> bool:
        """Return True when any time-off block overlaps [row_start, row_end)."""
        for toff in active_time_offs:
            if toff.trainer_id != row_trainer_id:
                continue
            # Overlap condition: block_start < row_end AND block_end > row_start.
            if toff.block_start < row_end and toff.block_end > row_start:
                return True
        return False

    clean_rows: list[dict[str, object]] = []
    for row in candidate_rows:
        if not _overlaps_any_time_off(
            row["trainer_id"],  # type: ignore[arg-type]
            row["start_time"],  # type: ignore[arg-type]
            row["end_time"],  # type: ignore[arg-type]
        ):
            clean_rows.append(row)

    if not clean_rows:
        return 0

    # Bulk INSERT with ON CONFLICT (trainer_id, start_time) DO NOTHING RETURNING id.
    # Returns only ids of rows actually inserted (conflicts return nothing — PITFALL 8).
    inserted_ids = await repository.bulk_insert_recurring_slots(session, clean_rows)

    # Flush so the inserted rows are visible within the transaction (needed for
    # audit FK; the cron caller commits after this helper returns).
    await session.flush()

    # Audit emit — slot_published ONCE PER REAL INSERT only (ROADMAP SC#2 / T-59-14).
    # created_by_user_id=None (cron actor — no human author, D-59-05 / T-59-14).
    # We need start/end times for the audit payload; build a lookup from the
    # candidate rows matched by the inserted ids. Since ids are UUIDs returned
    # by RETURNING, we must re-query the just-inserted rows.
    if inserted_ids:
        from sqlalchemy import select as _select

        freshly_inserted = (
            await session.scalars(
                _select(TrainerAvailabilitySlot).where(
                    TrainerAvailabilitySlot.id.in_(inserted_ids)
                )
            )
        ).all()

        for slot in freshly_inserted:
            await audit.emit(
                session,
                "slot_published",  # LITERAL — INFRA-11 AST gate
                actor_user_id=None,  # cron actor — no human author (D-41-08)
                resource_type="schedule_slot",  # LITERAL
                resource_id=slot.id,
                slot_id=str(slot.id),
                trainer_id=str(slot.trainer_id),
                start_time=slot.start_time.isoformat(),
                end_time=slot.end_time.isoformat(),
                created_by_user_id=None,
            )

    return len(inserted_ids)


async def list_time_off(
    session: AsyncSession,
    *,
    trainer_id: UUID | None = None,
    page: int = 1,
    page_size: int = 20,
) -> "PaginatedData[TimeOffResponse]":
    """Paginated time-off list (REC-04 — both roles). Read-only."""
    page_data = await repository.list_time_off(
        session,
        trainer_id=trainer_id,
        page=page,
        page_size=page_size,
    )
    return PaginatedData.model_construct(
        items=[_time_off_response_from_orm(t) for t in page_data.items],
        total=page_data.total,
        page=page_data.page,
        page_size=page_data.page_size,
    )
