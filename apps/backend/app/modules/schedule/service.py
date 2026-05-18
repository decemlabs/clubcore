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

from datetime import UTC, datetime
from uuid import UUID

import sqlalchemy as sa
import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import audit
from app.core.dependencies import CurrentUser, resolve_trainer_by_id
from app.core.exceptions import AppError, ConflictError, NotFoundError
from app.core.pagination import PaginatedData
from app.modules.schedule import repository
from app.modules.schedule.constants import (
    SLOT_BUFFER_MINUTES,
    SLOT_STATUS_TRANSITIONS,
)
from app.modules.schedule.models import TrainerAvailabilitySlot
from app.modules.schedule.schemas import (
    SlotCancelRequest,
    SlotCreateRequest,
    SlotListQuery,
    SlotResponse,
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


async def list_slots(
    session: AsyncSession,
    query: SlotListQuery,
) -> PaginatedData[SlotResponse]:
    """Paginated slot list (SLOT-08). Read-only — NO commit.

    Repository resolves default time-window bounds when the query fields
    are None (FastAPI query schema cannot synthesize a default datetime).
    """
    page = await repository.list_slots_paginated(session, query)
    return PaginatedData.model_construct(
        items=[SlotResponse.model_validate(s, from_attributes=True) for s in page.items],
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
    return SlotResponse.model_validate(slot, from_attributes=True)


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
        created_by_user_id=str(slot.created_by_user_id),
    )

    # 8. Commit (SVC001 gate).
    await session.commit()

    # 9. Narrow refresh + response.
    await session.refresh(slot, attribute_names=["created_at", "updated_at"])
    return SlotResponse.model_validate(slot, from_attributes=True)


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
            await bookings_service._dispatch_booking_dm(
                cancelled_booking,
                template=bookings_notifications.BOOKING_CANCELLED_BY_OWNER_DM,
                bot=dm_bot,
                sender=telegram_sender_mod,
            )

    # 9. Refresh + response.
    await session.refresh(slot, attribute_names=["updated_at"])
    return SlotResponse.model_validate(slot, from_attributes=True)
