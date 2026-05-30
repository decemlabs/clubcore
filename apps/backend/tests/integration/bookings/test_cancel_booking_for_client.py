"""Phase 70 D-70-05/06 — bookings.service.cancel_booking_for_client integration tests.

Covers (per plan <acceptance_criteria>):
  - Happy path: client cancels own booking outside the CANCEL_WINDOW_HOURS_CLIENT
    window → 200 OK, slot restored to 'active', pt_package.sessions_remaining
    unchanged (D-70-06 no-credit-action).
  - IDOR 404-collapse (D-20-IDOR / T-70-05): client A cancels client B's
    booking → BookingNotFoundError("booking_not_found") — anti-oracle, never
    403 or existence leak.
  - Cancel inside CANCEL_WINDOW_HOURS_CLIENT → CancelWindowExpiredError
    ("cancel_window_expired").
  - Cancelling an already-cancelled booking → InvalidBookingTransitionError
    (FSM guard, same as staff cancel).
  - Audit row: booking_cancelled with cancelled_by_user_id=None (Phase 70
    D-70-05 / additive widening; actor_user_id=None at DB column level).
  - Slot is restored to 'active' (booked→active via BookingSlotRestorer
    Protocol slot, same as staff cancel).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit_models import AuditLog
from app.modules.auth.models import User
from app.modules.bookings import service
from app.modules.bookings.constants import CANCEL_WINDOW_HOURS_CLIENT
from app.modules.bookings.models import Booking
from app.modules.bookings.schemas import (
    BookingStatus,
)


async def _seed_confirmed_booking_for_client(
    db_session: AsyncSession,
    *,
    actor: User,
    make_trainer,
    make_client,
    make_pt_package_plan,
    make_pt_package,
    make_slot,
    slot_start_offset: timedelta = timedelta(hours=48),
):
    """Seed and create a confirmed booking via the client self-service path.

    Returns (booking_row, slot_orm, client_orm, pkg_orm).
    """
    trainer = await make_trainer()
    client = await make_client()
    plan = await make_pt_package_plan()
    pkg = await make_pt_package(client_id=client.id, plan=plan, sessions_remaining=5)
    start = datetime.now(UTC) + slot_start_offset
    slot = await make_slot(
        trainer_id=trainer.id,
        start_time=start,
        end_time=start + timedelta(hours=1),
    )
    created = await service.create_booking_for_client(
        db_session,
        client_id=client.id,
        slot_id=slot.id,
        pt_package_id=pkg.id,
    )
    booking = await db_session.scalar(select(Booking).where(Booking.id == created.id))
    assert booking is not None
    return booking, slot, client, pkg


@pytest.mark.asyncio
async def test_cancel_booking_for_client_happy_path(
    db_session: AsyncSession,
    seeded_owner: User,
    make_trainer,
    make_client,
    make_pt_package_plan,
    make_pt_package,
    make_slot,
) -> None:
    """Client cancels own booking outside CANCEL_WINDOW_HOURS_CLIENT — 200 OK.

    Asserts:
      - Booking status flips to 'cancelled'.
      - Slot is restored to 'active'.
      - pt_package.sessions_remaining is unchanged (D-70-06 no-credit-action).
      - Audit row: cancelled_by_user_id=None + actor_user_id=None.
    """
    booking, slot, client, pkg = await _seed_confirmed_booking_for_client(
        db_session,
        actor=seeded_owner,
        make_trainer=make_trainer,
        make_client=make_client,
        make_pt_package_plan=make_pt_package_plan,
        make_pt_package=make_pt_package,
        make_slot=make_slot,
        slot_start_offset=timedelta(hours=CANCEL_WINDOW_HOURS_CLIENT + 2),
    )
    sessions_before = pkg.sessions_remaining

    response = await service.cancel_booking_for_client(
        db_session,
        client_id=client.id,
        booking_id=booking.id,
        cancel_reason="changed my mind",
    )

    # Response shape.
    assert response.status == BookingStatus.CANCELLED

    # Booking DB state — status='cancelled', cancel_reason set.
    await db_session.refresh(booking)
    assert booking.status == "cancelled"
    assert booking.cancel_reason == "changed my mind"
    assert booking.cancelled_at is not None

    # Slot restored to 'active' (D-70-06 slot-restore invariant).
    await db_session.refresh(slot, attribute_names=["status"])
    assert slot.status == "active"

    # pt_package.sessions_remaining UNCHANGED (D-70-06 no-credit-action —
    # credit only decrements/restores at pt_sessions level).
    await db_session.refresh(pkg)
    assert pkg.sessions_remaining == sessions_before

    # Audit row: booking_cancelled with cancelled_by_user_id=None (D-70-05 widening)
    # and actor_user_id=None at DB column level (D-70-07 anti-fabrication).
    audit_rows = (
        (
            await db_session.execute(
                select(AuditLog).where(
                    AuditLog.action == "booking_cancelled",
                    AuditLog.resource_id == booking.id,
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(audit_rows) == 1
    audit_row = audit_rows[0]
    assert audit_row.actor_user_id is None  # RAW DB NULL — not a stringified None
    payload = audit_row.payload
    assert payload["cancelled_by_user_id"] is None  # Phase 70 D-70-05 widening
    assert payload["cancel_reason"] == "changed my mind"
    assert payload["booking_id"] == str(booking.id)
    assert payload["slot_id"] == str(slot.id)


@pytest.mark.asyncio
async def test_cancel_booking_for_client_idor_404_collapse(
    db_session: AsyncSession,
    seeded_owner: User,
    make_trainer,
    make_client,
    make_pt_package_plan,
    make_pt_package,
    make_slot,
) -> None:
    """IDOR 404-collapse (D-20-IDOR / T-70-05).

    Client A attempts to cancel client B's booking.
    Must raise BookingNotFoundError("booking_not_found") — NOT a 403 or
    any other response that reveals the booking exists for another client
    (anti-oracle).
    """
    booking_b, _slot, _client_b, _pkg_b = await _seed_confirmed_booking_for_client(
        db_session,
        actor=seeded_owner,
        make_trainer=make_trainer,
        make_client=make_client,
        make_pt_package_plan=make_pt_package_plan,
        make_pt_package=make_pt_package,
        make_slot=make_slot,
    )

    # A different client (client A) tries to cancel client B's booking.
    client_a = await make_client()
    with pytest.raises(service.BookingNotFoundError) as exc_info:
        await service.cancel_booking_for_client(
            db_session,
            client_id=client_a.id,  # client A — does NOT own booking_b
            booking_id=booking_b.id,
        )
    assert exc_info.value.code == "booking_not_found"
    # The booking was NOT cancelled — still confirmed.
    await db_session.refresh(booking_b)
    assert booking_b.status == "confirmed"


@pytest.mark.asyncio
async def test_cancel_booking_for_client_inside_cancel_window(
    db_session: AsyncSession,
    seeded_owner: User,
    make_trainer,
    make_client,
    make_pt_package_plan,
    make_pt_package,
    make_slot,
) -> None:
    """CancelWindowExpiredError when inside CANCEL_WINDOW_HOURS_CLIENT.

    Slot starts within the window → cancel_window_expired (409).
    Window is measured against slot.start_time (D-38-16, NOT created_at).
    """
    # Slot is 1 hour from now — inside the 24h window.
    booking, _slot, client, _pkg = await _seed_confirmed_booking_for_client(
        db_session,
        actor=seeded_owner,
        make_trainer=make_trainer,
        make_client=make_client,
        make_pt_package_plan=make_pt_package_plan,
        make_pt_package=make_pt_package,
        make_slot=make_slot,
        slot_start_offset=timedelta(hours=1),
    )
    with pytest.raises(service.CancelWindowExpiredError) as exc_info:
        await service.cancel_booking_for_client(
            db_session,
            client_id=client.id,
            booking_id=booking.id,
        )
    assert exc_info.value.code == "cancel_window_expired"


@pytest.mark.asyncio
async def test_cancel_booking_for_client_already_cancelled(
    db_session: AsyncSession,
    seeded_owner: User,
    make_trainer,
    make_client,
    make_pt_package_plan,
    make_pt_package,
    make_slot,
) -> None:
    """InvalidBookingTransitionError on double-cancel (FSM guard — terminal state)."""
    booking, _slot, client, _pkg = await _seed_confirmed_booking_for_client(
        db_session,
        actor=seeded_owner,
        make_trainer=make_trainer,
        make_client=make_client,
        make_pt_package_plan=make_pt_package_plan,
        make_pt_package=make_pt_package,
        make_slot=make_slot,
        slot_start_offset=timedelta(hours=CANCEL_WINDOW_HOURS_CLIENT + 2),
    )
    # First cancel — OK.
    await service.cancel_booking_for_client(
        db_session,
        client_id=client.id,
        booking_id=booking.id,
    )
    # Second cancel — FSM guard: cancelled → ∅ (terminal).
    with pytest.raises(service.InvalidBookingTransitionError) as exc_info:
        await service.cancel_booking_for_client(
            db_session,
            client_id=client.id,
            booking_id=booking.id,
        )
    assert exc_info.value.code == "invalid_transition"


@pytest.mark.asyncio
async def test_cancel_booking_for_client_nonexistent_booking(
    db_session: AsyncSession,
    seeded_owner: User,
    make_client,
) -> None:
    """BookingNotFoundError for a non-existent booking_id (anti-oracle — same 404
    as IDOR collapse; callers cannot distinguish 'does not exist' from 'wrong owner')."""
    from uuid import uuid4

    client = await make_client()
    with pytest.raises(service.BookingNotFoundError) as exc_info:
        await service.cancel_booking_for_client(
            db_session,
            client_id=client.id,
            booking_id=uuid4(),
        )
    assert exc_info.value.code == "booking_not_found"
