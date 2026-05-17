"""Bookings service — orchestration between router and repository (Phase 38).

Phase 38 plan 38-02 Task 3 ships:
  - create_booking — 10-step atomic UoW that creates a confirmed booking
    (resolve slot → validate pt_package + trainer + Moscow-TZ validity
    window → flip slot active→booked via cross-module raw UPDATE → INSERT
    booking → flush + translate IntegrityError on uq_bookings_slot_confirmed
    → emit booking_created → commit).
  - complete_booking — Phase 37 stub body replaced with predicate-gated
    raw UPDATE (confirmed → completed) inside caller's UoW (D-38-13 /
    PKG-05; pt_sessions.service.record_pt_session is the future caller).

Discipline invariants (Phase 30 walkers — all must remain green):
  - SVC001 caller-owns-txn (test_service_commit_gate): every public mutating
    orchestrator MUST end with `await session.commit()`. Private / Protocol-
    slot helpers may carry `# noqa: SVC001 caller-owns-txn` on the def line.
  - audit.emit literal-string AST gate (INFRA-11 / test_audit_taxonomy):
    every emit() call uses literal strings for `event` and `resource_type`.
  - audit_payloads.py extra='forbid' validation (D-30-03): emit kwargs MUST
    match BookingCreatedPayload schema verbatim (5 keys — booking_id,
    slot_id, client_id, pt_package_id, created_by_user_id). UUIDs
    stringified at callsite per Pitfall 13 / D-38-17.
  - modules-independent contract: NO direct imports of
    app.modules.{schedule,pt_packages,...}. Cross-module reads via Protocol
    slots from app.core.dependencies (here: resolve_slot_by_id +
    get_active_pt_package). Cross-module slot UPDATE goes through the
    bookings.repository raw `sa.text()` helper (D-38-11 carve-out).

Cross-module behaviours used in this module:
  - resolve_slot_by_id (Protocol slot, Phase 37 D-37-06; Phase 38 plan
    38-01 replaced body with real schedule resolver) — returns SlotById
    structurally typed read of TrainerAvailabilitySlot.
  - get_active_pt_package (Phase 33 ActivePtPackageResolver) — returns
    the client's single active PT-package, silent-None if none.
  - bookings.repository.update_slot_status_predicate_gated — flips the
    schedule slot's status via raw cross-module UPDATE with the
    `noqa: TABLE_REF` marker (modules-independent contract preserved).
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID
from zoneinfo import ZoneInfo

import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import audit
from app.core.dependencies import (
    CurrentUser,
    get_active_pt_package,
    resolve_slot_by_id,
)
from app.core.exceptions import ConflictError, NotFoundError
from app.modules.bookings import repository
from app.modules.bookings.constants import BOOKING_STATUS_TRANSITIONS
from app.modules.bookings.models import Booking
from app.modules.bookings.schemas import BookingCreateRequest, BookingResponse

# Business TZ pin (C-07 / D-38-12). Validity-window comparison MUST happen
# in Moscow time — a slot at 01:00 Moscow is 22:00 UTC the previous day;
# `.date()` on the UTC value mis-classifies the slot.
MOSCOW_TZ = ZoneInfo("Europe/Moscow")


# ---------------------------------------------------------------------------
# Error classes (mirror pt_sessions/service.py shape; class-level code +
# status_code translated by the global exception handler into the response
# envelope {error.code} field).
# ---------------------------------------------------------------------------


class BookingNotFoundError(NotFoundError):
    """Raised when a booking id lookup misses (plan 38-03 read/cancel)."""

    code = "booking_not_found"
    status_code = 404


class SlotNotFoundError(NotFoundError):
    """Raised by create_booking when the slot id does not exist."""

    code = "slot_not_found"
    status_code = 404


class SlotNotAvailableError(ConflictError):
    """Raised by create_booking when the slot exists but status != 'active'
    (cancelled, booked, etc.). Pre-INSERT app-layer guard mirrors the
    SLOT_STATUS_TRANSITIONS forward-only FSM (D-38-10)."""

    code = "slot_not_available"
    status_code = 409


class SlotAlreadyBookedError(ConflictError):
    """Raised by create_booking when the partial UNIQUE
    `uq_bookings_slot_confirmed` IntegrityError fires (D-38-15 / BOOK-10
    race-loser path). Translated via the `_is_slot_confirmed_conflict`
    constraint-name discriminator."""

    code = "slot_already_booked"
    status_code = 409


class TrainerMismatchError(ConflictError):
    """Raised by create_booking when `pt_package.trainer_id is not None`
    and does not match `slot.trainer_id` (C-08 / PKG-02). A NULL
    `pt_package.trainer_id` explicitly means "any trainer" and skips
    this guard."""

    code = "trainer_mismatch"
    status_code = 409


class PtPackageExhaustedError(ConflictError):
    """Raised by create_booking when the resolved active pt_package has
    sessions_remaining <= 0. Defence-in-depth at booking creation time;
    the package consumption logic itself lives in pt_sessions/service."""

    code = "pt_package_exhausted"
    status_code = 409


class PtPackageNotActiveError(ConflictError):
    """Raised by create_booking when the client has no active pt_package,
    or when the supplied pt_package_id does not match the client's active
    package. Defensive guard against id-spoofing — server is the arbiter
    of which package owns the booking."""

    code = "pt_package_not_active"
    status_code = 409


class PtPackageExpiredBeforeSlotError(ConflictError):
    """Raised by create_booking when the pt_package end_date is strictly
    less than the slot's start_time (compared in Moscow TZ per D-38-12 /
    Pitfall 18 / BOOK-04). NULL `pt_package.end_date` (бессрочный
    package) skips this guard."""

    code = "pt_package_expired_before_slot"
    status_code = 409


class InvalidBookingTransitionError(ConflictError):
    """Raised by complete_booking / FSM gate on disallowed booking status
    moves (D-38-10). Mirrors InvalidSlotTransitionError from schedule."""

    code = "invalid_transition"
    status_code = 409


# ---------------------------------------------------------------------------
# FSM guard (D-38-10 / mirror pt_packages._assert_can_transition).
# ---------------------------------------------------------------------------


def _assert_can_transition(  # noqa: SVC001 caller-owns-txn
    booking: Booking,
    *,
    target: str,
) -> None:
    """Central state-machine guard (D-38-10).

    Consults `BOOKING_STATUS_TRANSITIONS` to decide whether
    `booking.status → target` is allowed; raises
    `InvalidBookingTransitionError` (409 invalid_transition) with
    discriminating `from_status` / `to_status` payload otherwise.

    Pure function — no DB writes; SVC001 noqa marker documents the
    discipline even though no commit is required here.
    """
    allowed = BOOKING_STATUS_TRANSITIONS.get(booking.status, frozenset())
    if target not in allowed:
        raise InvalidBookingTransitionError(
            "invalid_transition",
            fields={"from_status": booking.status, "to_status": target},
        )


# ---------------------------------------------------------------------------
# IntegrityError discriminator (D-38-15 / mirror
# pt_packages._is_active_pt_package_conflict).
# ---------------------------------------------------------------------------


def _is_slot_confirmed_conflict(exc: IntegrityError) -> bool:
    """Return True iff `exc` was caused by `uq_bookings_slot_confirmed` (D-38-15).

    asyncpg surfaces the constraint name via `exc.orig.constraint_name` on
    Postgres; string-fallback matches the literal embedded in the error
    message for drivers that omit the attribute. The literal MUST match
    the migration 0017 `op.create_index` name letter-for-letter.
    """
    constraint = getattr(exc.orig, "constraint_name", None) or ""
    if constraint == "uq_bookings_slot_confirmed":
        return True
    return "uq_bookings_slot_confirmed" in str(exc.orig)


# ---------------------------------------------------------------------------
# Phase 37 Protocol slot body (D-37-06 — preserve signature
# `async def complete_booking(session: AsyncSession, booking_id: UUID) -> None`;
# Phase 38 replaces the stub body with the predicate-gated raw UPDATE).
# ---------------------------------------------------------------------------


async def complete_booking(  # noqa: SVC001 caller-owns-txn
    session: AsyncSession,
    booking_id: UUID,
) -> None:
    """Transition booking confirmed→completed inside caller's UoW (D-38-13 / PKG-05).

    Caller (`pt_sessions.service.record_pt_session` — plan 38-05) owns the
    surrounding transaction. We issue a predicate-gated UPDATE so a
    concurrent cancel (status='cancelled') silently no-ops (FSM
    forward-only invariant `cancelled → ∅` from constants.py); 0-row
    UPDATE raises InvalidBookingTransitionError → 409 (defensive — the
    pt_sessions service already validated status='confirmed' under
    SELECT FOR UPDATE earlier in its UoW per D-38-19, but we still gate
    here to surface the contract breach if a future caller drops the
    pre-check).

    NO audit emit here — `pt_session_recorded` carries the `booking_id`
    field per D-37-05, so the booking-completion is observable via the
    pt_session_recorded audit row (C-06 / D-37-05).

    Caller-owns-txn (SVC001 opt-out marker on def line per D-32-10).
    """
    stmt = sa.text(
        """
        UPDATE bookings
        SET status = 'completed',
            completed_at = now(),
            updated_at = now()
        WHERE id = :booking_id AND status = 'confirmed'
        RETURNING id
        """,
    )
    result = await session.execute(stmt, {"booking_id": booking_id})
    if result.first() is None:
        raise InvalidBookingTransitionError(
            "invalid_transition",
            fields={"to_status": "completed"},
        )


# ---------------------------------------------------------------------------
# Public mutating orchestrator — create_booking (BOOK-02).
# ---------------------------------------------------------------------------


async def create_booking(
    session: AsyncSession,
    actor: CurrentUser,
    data: BookingCreateRequest,
) -> BookingResponse:
    """Create a confirmed booking (Phase 38 BOOK-02).

    Owns the UoW — `await session.commit()` at end (SVC001 gate).

    10-step recipe (mirror pt_sessions.record_pt_session shape):
      1. Resolve slot via SlotById Protocol slot (D-37-06) — 404
         slot_not_found / 409 slot_not_available if status != 'active'.
      2. Resolve client's active pt_package via the existing Phase 33
         ActivePtPackageResolver slot — 409 pt_package_not_active when
         silent-None, when the id doesn't match (defensive against
         id-spoofing), or when sessions_remaining <= 0 (then 409
         pt_package_exhausted).
      3. Trainer-mismatch guard (PKG-02 / C-08): if
         `pt_package.trainer_id is not None` and != `slot.trainer_id`,
         raise TrainerMismatchError. NULL trainer_id means "any".
      4. Moscow-TZ validity-window guard (Pitfall 18 / D-38-12 /
         BOOK-04): if `pt_package.end_date < slot.start_time.astimezone(
         MOSCOW_TZ).date()`, raise PtPackageExpiredBeforeSlotError. NULL
         end_date (бессрочный package) skips this check.
      5. Flip slot active→booked via the cross-module raw UPDATE
         (bookings.repository — modules-independent contract preserved
         via raw sa.text() with TABLE_REF noqa). 0 rows updated → 409
         slot_not_available (concurrent winner already took it pre-INSERT).
      6. Insert booking row via bookings.repository.insert_booking.
      7. session.flush() — surfaces the partial UNIQUE
         uq_bookings_slot_confirmed IntegrityError when a concurrent
         winner already INSERTed a confirmed row for the same slot in
         the gap between our active→booked UPDATE and our INSERT (the
         load-bearing race guard per BOOK-10). Translate via
         _is_slot_confirmed_conflict → 409 slot_already_booked.
      8. audit.emit('booking_created', ...) — payload matches
         BookingCreatedPayload (extra='forbid') verbatim; UUIDs
         stringified at callsite per Pitfall 13 / D-38-17.
      9. session.commit() (SVC001 gate).
     10. Narrow refresh on created_at/updated_at + return BookingResponse.
    """
    # Defensive request-time pin (Pitfall 7 / D-38-16 — datetime.now(UTC)
    # idiom; never datetime.utcnow which is deprecated in 3.12). Used by
    # the Moscow-TZ validity-window guard below and by the slot-not-available
    # defensive freshness check (if the slot's start_time has slipped into
    # the past since publish, surface as slot_not_available — the schedule
    # service guarantees future-only at publish time but time drifts).
    now_utc = datetime.now(UTC)

    # Step 1 — slot resolve + status guard.
    slot = await resolve_slot_by_id(session, data.slot_id)
    if slot is None:
        raise SlotNotFoundError("slot_not_found")
    if slot.status != "active":
        raise SlotNotAvailableError("slot_not_available")
    if slot.start_time <= now_utc:
        # Defensive freshness — the schedule-service publish-time guard
        # (D-38-16) means a newly-published slot can never start in the
        # past, but between publish and booking the clock advances. We
        # surface as slot_not_available to match the unified error code
        # set (no separate slot_in_past code at the booking layer; the
        # slot is simply not bookable).
        raise SlotNotAvailableError("slot_not_available")

    # Step 2 — active pt_package resolve + id-match + exhausted guard.
    pt_package = await get_active_pt_package(session, data.client_id)
    if pt_package is None:
        raise PtPackageNotActiveError("pt_package_not_active")
    if pt_package.id != data.pt_package_id:
        # Defensive — reception/owner cannot book against an unrelated
        # package id (server is the arbiter of which package owns the
        # booking; mirrors pt_sessions/service.py:217-222 client_id
        # sourced-from-package discipline per D-34-13a).
        raise PtPackageNotActiveError("pt_package_not_active")
    if pt_package.sessions_remaining <= 0:
        raise PtPackageExhaustedError("pt_package_exhausted")

    # Step 3 — Trainer-mismatch guard (PKG-02 / C-08).
    # pt_package.trainer_id is added by plan 38-04 (Alembic 0018); until
    # then the column does not exist on the ActivePtPackage Protocol and
    # `getattr` returns None (NULL = "any trainer" by C-08 spec).
    pkg_trainer_id = getattr(pt_package, "trainer_id", None)
    if pkg_trainer_id is not None and pkg_trainer_id != slot.trainer_id:
        raise TrainerMismatchError("trainer_mismatch")

    # Step 4 — Moscow-TZ validity-window guard (Pitfall 18 / D-38-12 / BOOK-04).
    # CRITICAL: convert slot.start_time to Moscow TZ before extracting .date()
    # — a slot at 01:00 Moscow is 22:00 UTC the prior day; .date() on the
    # UTC value would mis-classify and incorrectly accept an expired package.
    if (
        pt_package.end_date is not None
        and pt_package.end_date < slot.start_time.astimezone(MOSCOW_TZ).date()
    ):
        raise PtPackageExpiredBeforeSlotError("pt_package_expired_before_slot")

    # Step 5 — Cross-module raw UPDATE flipping slot active→booked.
    # 0-row return: concurrent winner already took it pre-INSERT (or the
    # slot status changed between Step 1's read and now). Re-fetch to
    # discriminate `slot_already_booked` (someone else booked it) from
    # `slot_not_available` (slot was cancelled / otherwise unbookable).
    # This matches BOOK-TEST-01 / D-38-15 expectation that the race-loser
    # surfaces as `slot_already_booked` consistently.
    slot_flipped = await repository.update_slot_status_predicate_gated(
        session,
        data.slot_id,
        from_status="active",
        to_status="booked",
    )
    if not slot_flipped:
        # Force a fresh read bypassing the ORM identity-map cache (the
        # cross-module raw UPDATE in another transaction bypassed our
        # ORM tracking, so a normal `session.scalar(select(...))` could
        # return a cached pre-UPDATE instance).
        await session.refresh(slot, attribute_names=["status"])
        if slot.status == "booked":
            raise SlotAlreadyBookedError("slot_already_booked")
        raise SlotNotAvailableError("slot_not_available")

    # Step 6 — INSERT booking row.
    booking = await repository.insert_booking(
        session,
        slot_id=data.slot_id,
        client_id=data.client_id,
        pt_package_id=data.pt_package_id,
        created_by_user_id=actor.id,
    )

    # Step 7 — Flush + race-translation. The partial UNIQUE
    # uq_bookings_slot_confirmed is the load-bearing race guard (BOOK-01 /
    # C-02 / Pitfall 1 / D-38-15). On 2 concurrent POSTs to the same slot:
    # both may pass Step 5 (their UPDATEs serialise but the loser sees 0
    # rows only when the winner committed; in real Postgres async write
    # interleavings the loser observes 1 row from its own UPDATE then
    # blocks on the row-lock, ultimately attempting the INSERT and hitting
    # the partial UNIQUE here). We rollback the broken UoW and translate
    # to 409 slot_already_booked.
    try:
        await session.flush()
    except IntegrityError as exc:
        await session.rollback()
        if _is_slot_confirmed_conflict(exc):
            raise SlotAlreadyBookedError("slot_already_booked") from exc
        raise

    # Step 8 — Emit booking_created (LITERAL strings for INFRA-11 AST gate).
    # Payload matches BookingCreatedPayload (extra='forbid') verbatim; UUIDs
    # stringified at callsite per D-38-17 / Pitfall 13.
    await audit.emit(
        session,
        "booking_created",  # LITERAL — INFRA-11 AST gate
        actor_user_id=actor.id,
        resource_type="booking",  # LITERAL
        resource_id=booking.id,
        booking_id=str(booking.id),
        slot_id=str(booking.slot_id),
        client_id=str(booking.client_id),
        pt_package_id=str(booking.pt_package_id),
        created_by_user_id=str(booking.created_by_user_id),
    )

    # Step 9 — Commit (SVC001 gate).
    await session.commit()

    # Step 10 — Narrow refresh + response (WR-04 lesson — populate the
    # server-generated created_at / updated_at into the loaded ORM
    # instance for the response envelope).
    await session.refresh(booking, attribute_names=["created_at", "updated_at"])
    return BookingResponse.model_validate(booking, from_attributes=True)
