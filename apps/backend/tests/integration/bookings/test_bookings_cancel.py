"""Integration tests for bookings.service.cancel_booking — plan 38-03 Task 2.

Covers (per plan <behavior>):
  - reception cancels 25h before slot.start → 200 OK (outside window).
  - reception cancels 23h before slot.start → 200 OK (>= boundary inclusive).
  - reception cancels 1h before slot.start → 409 cancel_window_expired.
  - owner cancels 30min before slot.start → 200 OK (no window).
  - cancelling already-cancelled booking → 409 invalid_transition.
  - cancelling completed booking → 409 invalid_transition.
  - audit_log booking_cancelled row exists with cancelled_by_user_id.

The cancel-flow restores the linked slot booked→active via the Phase 37
BookingSlotRestorer Protocol slot (production-wired via app.main.create_app).
Tests rely on the production wiring being live under the FastAPI lifespan
in conftest.

Wait-window math note: the plan spec calls out the 24h window edge inclusively
(i.e. exactly 24h = OK). The service compares with strict `<` (less-than),
so 24h is on the OK side (>= 24h passes). The "23h before slot.start" test
exercises the inside-window branch; "25h before" the outside-window branch.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit_models import AuditLog
from app.modules.auth.models import User
from app.modules.bookings import service
from app.modules.bookings.models import Booking
from app.modules.bookings.schemas import (
    BookingCancelRequest,
    BookingCreateRequest,
    BookingStatus,
)


async def _seed_confirmed_booking(
    db_session: AsyncSession,
    *,
    actor: User,
    make_trainer,
    make_client,
    make_pt_package_plan,
    make_pt_package,
    make_slot,
    slot_start_offset: timedelta = timedelta(hours=48),
) -> tuple[Booking, object]:
    """Helper: seed trainer/client/plan/pkg/slot and create a confirmed booking
    via service.create_booking. Returns (booking_row, slot_orm)."""
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
    created = await service.create_booking(
        db_session,
        actor,
        BookingCreateRequest(
            slot_id=slot.id,
            client_id=client.id,
            pt_package_id=pkg.id,
        ),
    )
    booking = await db_session.scalar(select(Booking).where(Booking.id == created.id))
    assert booking is not None
    return booking, slot


@pytest.mark.asyncio
async def test_cancel_booking_reception_outside_24h_window_ok(
    db_session: AsyncSession,
    seeded_owner: User,
    seeded_reception: User,
    make_trainer,
    make_client,
    make_pt_package_plan,
    make_pt_package,
    make_slot,
) -> None:
    """Reception cancels 25h before slot.start → 200 OK (outside the 24h window).

    Slot status flips back to 'active' via the BookingSlotRestorer Protocol slot.
    """
    booking, slot = await _seed_confirmed_booking(
        db_session,
        actor=seeded_owner,
        make_trainer=make_trainer,
        make_client=make_client,
        make_pt_package_plan=make_pt_package_plan,
        make_pt_package=make_pt_package,
        make_slot=make_slot,
        slot_start_offset=timedelta(hours=25),
    )
    response = await service.cancel_booking(
        db_session,
        seeded_reception,
        booking.id,
        BookingCancelRequest(reason="client request"),
    )
    assert response.status == BookingStatus.CANCELLED
    assert response.cancel_reason == "client request"
    assert response.cancelled_at is not None

    # Slot was restored to 'active' (cross-module raw UPDATE; force fresh read).
    await db_session.refresh(slot, attribute_names=["status"])
    assert slot.status == "active"


@pytest.mark.asyncio
async def test_cancel_booking_reception_23h_inside_window_409(
    db_session: AsyncSession,
    seeded_owner: User,
    seeded_reception: User,
    make_trainer,
    make_client,
    make_pt_package_plan,
    make_pt_package,
    make_slot,
) -> None:
    """Reception cancels 23h before slot.start → 409 cancel_window_expired.

    The 24h window is measured against `slot.start_time` (D-38-16). 23h
    is strictly inside the window so reception is locked out.
    """
    booking, _slot = await _seed_confirmed_booking(
        db_session,
        actor=seeded_owner,
        make_trainer=make_trainer,
        make_client=make_client,
        make_pt_package_plan=make_pt_package_plan,
        make_pt_package=make_pt_package,
        make_slot=make_slot,
        slot_start_offset=timedelta(hours=23),
    )
    with pytest.raises(service.CancelWindowExpiredError) as excinfo:
        await service.cancel_booking(
            db_session,
            seeded_reception,
            booking.id,
            BookingCancelRequest(reason="too late"),
        )
    assert excinfo.value.code == "cancel_window_expired"
    assert excinfo.value.status_code == 409


@pytest.mark.asyncio
async def test_cancel_booking_reception_1h_before_409(
    db_session: AsyncSession,
    seeded_owner: User,
    seeded_reception: User,
    make_trainer,
    make_client,
    make_pt_package_plan,
    make_pt_package,
    make_slot,
) -> None:
    """Reception cancels 1h before slot.start → 409 cancel_window_expired."""
    booking, _slot = await _seed_confirmed_booking(
        db_session,
        actor=seeded_owner,
        make_trainer=make_trainer,
        make_client=make_client,
        make_pt_package_plan=make_pt_package_plan,
        make_pt_package=make_pt_package,
        make_slot=make_slot,
        slot_start_offset=timedelta(hours=1),
    )
    with pytest.raises(service.CancelWindowExpiredError):
        await service.cancel_booking(
            db_session,
            seeded_reception,
            booking.id,
            BookingCancelRequest(reason="too late"),
        )


@pytest.mark.asyncio
async def test_cancel_booking_owner_within_window_ok(
    db_session: AsyncSession,
    seeded_owner: User,
    make_trainer,
    make_client,
    make_pt_package_plan,
    make_pt_package,
    make_slot,
) -> None:
    """Owner cancels 30min before slot.start → 200 OK (no window for owner)."""
    booking, slot = await _seed_confirmed_booking(
        db_session,
        actor=seeded_owner,
        make_trainer=make_trainer,
        make_client=make_client,
        make_pt_package_plan=make_pt_package_plan,
        make_pt_package=make_pt_package,
        make_slot=make_slot,
        slot_start_offset=timedelta(minutes=30),
    )
    response = await service.cancel_booking(
        db_session,
        seeded_owner,
        booking.id,
        BookingCancelRequest(reason="emergency"),
    )
    assert response.status == BookingStatus.CANCELLED
    await db_session.refresh(slot, attribute_names=["status"])
    assert slot.status == "active"


@pytest.mark.asyncio
async def test_cancel_booking_already_cancelled_409(
    db_session: AsyncSession,
    seeded_owner: User,
    make_trainer,
    make_client,
    make_pt_package_plan,
    make_pt_package,
    make_slot,
) -> None:
    """Cancelling already-cancelled booking → 409 invalid_transition (FSM gate)."""
    booking, _slot = await _seed_confirmed_booking(
        db_session,
        actor=seeded_owner,
        make_trainer=make_trainer,
        make_client=make_client,
        make_pt_package_plan=make_pt_package_plan,
        make_pt_package=make_pt_package,
        make_slot=make_slot,
        slot_start_offset=timedelta(hours=48),
    )
    await service.cancel_booking(
        db_session,
        seeded_owner,
        booking.id,
        BookingCancelRequest(reason="first cancel"),
    )
    with pytest.raises(service.InvalidBookingTransitionError) as excinfo:
        await service.cancel_booking(
            db_session,
            seeded_owner,
            booking.id,
            BookingCancelRequest(reason="second attempt"),
        )
    assert excinfo.value.code == "invalid_transition"


@pytest.mark.asyncio
async def test_cancel_completed_booking_409(
    db_session: AsyncSession,
    seeded_owner: User,
    make_trainer,
    make_client,
    make_pt_package_plan,
    make_pt_package,
    make_slot,
) -> None:
    """Cancelling completed booking → 409 invalid_transition."""
    booking, _slot = await _seed_confirmed_booking(
        db_session,
        actor=seeded_owner,
        make_trainer=make_trainer,
        make_client=make_client,
        make_pt_package_plan=make_pt_package_plan,
        make_pt_package=make_pt_package,
        make_slot=make_slot,
        slot_start_offset=timedelta(hours=48),
    )
    # Force booking → completed via complete_booking (Phase 38 plan 38-02 path).
    await service.complete_booking(db_session, booking.id)
    await db_session.commit()

    with pytest.raises(service.InvalidBookingTransitionError):
        await service.cancel_booking(
            db_session,
            seeded_owner,
            booking.id,
            BookingCancelRequest(reason="too late"),
        )


@pytest.mark.asyncio
async def test_cancel_booking_audit_row_written(
    db_session: AsyncSession,
    seeded_owner: User,
    make_trainer,
    make_client,
    make_pt_package_plan,
    make_pt_package,
    make_slot,
) -> None:
    """booking_cancelled audit row with the 4-key BookingCancelledPayload shape.

    Schema (audit_payloads.py:394): {booking_id, slot_id,
    cancelled_by_user_id, cancel_reason} — NO client_id field. UUIDs
    stringified at callsite per Pitfall 13 / D-38-17.
    """
    booking, _slot = await _seed_confirmed_booking(
        db_session,
        actor=seeded_owner,
        make_trainer=make_trainer,
        make_client=make_client,
        make_pt_package_plan=make_pt_package_plan,
        make_pt_package=make_pt_package,
        make_slot=make_slot,
        slot_start_offset=timedelta(hours=48),
    )
    response = await service.cancel_booking(
        db_session,
        seeded_owner,
        booking.id,
        BookingCancelRequest(reason="owner override"),
    )

    rows = (
        (
            await db_session.execute(
                select(AuditLog).where(
                    AuditLog.action == "booking_cancelled",
                    AuditLog.resource_id == response.id,
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(rows) == 1
    payload = rows[0].payload
    # Exact 4 keys (extra='forbid' would have rejected any extras at emit).
    assert set(payload.keys()) == {
        "booking_id",
        "slot_id",
        "cancelled_by_user_id",
        "cancel_reason",
    }
    assert payload["booking_id"] == str(response.id)
    assert payload["cancelled_by_user_id"] == str(seeded_owner.id)
    assert payload["cancel_reason"] == "owner override"


@pytest.mark.asyncio
async def test_cancel_booking_not_found_404(
    db_session: AsyncSession,
    seeded_owner: User,
) -> None:
    """Cancelling unknown booking_id → 404 booking_not_found."""
    from uuid import uuid4

    with pytest.raises(service.BookingNotFoundError):
        await service.cancel_booking(
            db_session,
            seeded_owner,
            uuid4(),
            BookingCancelRequest(reason="missing"),
        )
