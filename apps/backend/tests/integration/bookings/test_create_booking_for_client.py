"""Phase 70 D-70-01 — bookings.service.create_booking_for_client integration tests.

Mirrors ``test_create_booking_via_bot.py`` (the Phase 40 D-40-04 bot-actor
test fleet) — 1 happy path + the 7 domain error classes the client path can
raise + the criterion-#1 race guard (slot_already_booked on concurrent duplicate).

Key Phase 70 D-70-01 assertions (differences vs. the bot path):
  - ``audit_log.actor_user_id`` is DB-level NULL (raw None — D-70-07 anti-fab).
  - ``audit_log.payload.actor_role == "client"`` (Literal — INFRA-11 AST gate /
    D-70-07; distinct from "telegram_bot").
  - ``audit_log.payload.created_by_user_id`` is None (D-40-05 / D-70-07 —
    do NOT fabricate a staff user).
  - The inserted ``bookings`` row has ``created_by_user_id IS NULL`` (D-40-05).
  - ``PtPackageNotActiveError`` surfaces on None active package (maps to 422
    ``no_active_pt_package`` in Plan 70-03; CBOOK-04).
  - ``SlotAlreadyBookedError`` on a second confirmed booking for the same slot
    (criterion #1 race guard; CBOOK-03).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit_models import AuditLog
from app.modules.auth.models import User
from app.modules.bookings import service
from app.modules.bookings.models import Booking
from app.modules.bookings.schemas import BookingStatus


@pytest.mark.asyncio
async def test_create_booking_for_client_happy_path(
    db_session: AsyncSession,
    seeded_owner: User,  # only used by factories below — no actor on the client path
    make_trainer,
    make_client,
    make_pt_package_plan,
    make_pt_package,
    make_slot,
) -> None:
    """D-70-01 happy path — slot flips active→booked, booking lands with
    created_by_user_id IS NULL, audit row carries actor_role='client' and
    NULL actor_user_id."""
    trainer = await make_trainer(full_name="Мария Тренерова")
    client = await make_client()
    plan = await make_pt_package_plan()
    pkg = await make_pt_package(
        client_id=client.id,
        plan=plan,
        sessions_remaining=5,
    )
    slot = await make_slot(trainer_id=trainer.id)

    response = await service.create_booking_for_client(
        db_session,
        client_id=client.id,
        slot_id=slot.id,
        pt_package_id=pkg.id,
    )

    # Response shape — Phase 40 BLOCKER-2 fields present + D-70-07 None actor.
    assert response.status == BookingStatus.CONFIRMED
    assert response.slot_id == slot.id
    assert response.client_id == client.id
    assert response.pt_package_id == pkg.id
    assert response.created_by_user_id is None  # D-40-05 / D-70-07 anti-fab
    assert response.trainer_full_name == "Мария Тренерова"
    assert response.slot_start_time == slot.start_time

    # DB invariants — booking row exists with NULL actor; slot flipped to 'booked'.
    booking_row = await db_session.scalar(select(Booking).where(Booking.id == response.id))
    assert booking_row is not None
    assert booking_row.status == "confirmed"
    assert booking_row.created_by_user_id is None  # D-70-07: NULL in DB, not a staff UUID
    await db_session.refresh(slot, attribute_names=["status"])
    assert slot.status == "booked"

    # Audit invariants — booking_created emitted with 'client' actor_role +
    # NULL actor_user_id at the DB column level + NULL payload.created_by_user_id
    # (D-70-07: anti-fabrication; do NOT invent a fake staff user).
    audit_rows = (
        (
            await db_session.execute(
                select(AuditLog).where(
                    AuditLog.action == "booking_created",
                    AuditLog.resource_id == response.id,
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
    assert payload["actor_role"] == "client"  # Literal — INFRA-11 / D-70-07
    assert payload["created_by_user_id"] is None  # D-40-05 / D-70-07
    assert payload["booking_id"] == str(response.id)
    assert payload["slot_id"] == str(slot.id)
    assert payload["client_id"] == str(client.id)
    assert payload["pt_package_id"] == str(pkg.id)


@pytest.mark.asyncio
async def test_create_booking_for_client_slot_not_found(
    db_session: AsyncSession,
    seeded_owner: User,
    make_client,
    make_pt_package_plan,
    make_pt_package,
) -> None:
    """SlotNotFoundError on unknown slot_id."""
    client = await make_client()
    plan = await make_pt_package_plan()
    pkg = await make_pt_package(client_id=client.id, plan=plan)
    with pytest.raises(service.SlotNotFoundError) as exc_info:
        await service.create_booking_for_client(
            db_session,
            client_id=client.id,
            slot_id=uuid4(),
            pt_package_id=pkg.id,
        )
    assert exc_info.value.code == "slot_not_found"


@pytest.mark.asyncio
async def test_create_booking_for_client_slot_not_available_cancelled(
    db_session: AsyncSession,
    seeded_owner: User,
    make_trainer,
    make_client,
    make_pt_package_plan,
    make_pt_package,
    make_slot,
) -> None:
    """SlotNotAvailableError on slot.status != 'active'."""
    trainer = await make_trainer()
    client = await make_client()
    plan = await make_pt_package_plan()
    pkg = await make_pt_package(client_id=client.id, plan=plan)
    slot = await make_slot(trainer_id=trainer.id, status="cancelled")
    with pytest.raises(service.SlotNotAvailableError):
        await service.create_booking_for_client(
            db_session,
            client_id=client.id,
            slot_id=slot.id,
            pt_package_id=pkg.id,
        )


@pytest.mark.asyncio
async def test_create_booking_for_client_slot_not_available_in_past(
    db_session: AsyncSession,
    seeded_owner: User,
    make_trainer,
    make_client,
    make_pt_package_plan,
    make_pt_package,
    make_slot,
) -> None:
    """SlotNotAvailableError defensive freshness — slot.start_time in the past."""
    trainer = await make_trainer()
    client = await make_client()
    plan = await make_pt_package_plan()
    pkg = await make_pt_package(client_id=client.id, plan=plan)
    past = datetime.now(UTC) - timedelta(hours=1)
    slot = await make_slot(
        trainer_id=trainer.id,
        start_time=past,
        end_time=past + timedelta(minutes=30),
    )
    with pytest.raises(service.SlotNotAvailableError):
        await service.create_booking_for_client(
            db_session,
            client_id=client.id,
            slot_id=slot.id,
            pt_package_id=pkg.id,
        )


@pytest.mark.asyncio
async def test_create_booking_for_client_no_active_pt_package(
    db_session: AsyncSession,
    seeded_owner: User,
    make_trainer,
    make_client,
    make_slot,
) -> None:
    """PtPackageNotActiveError when client has no active pt_package (CBOOK-04).

    Maps to HTTP 422 no_active_pt_package in Plan 70-03.
    """
    trainer = await make_trainer()
    client = await make_client()
    slot = await make_slot(trainer_id=trainer.id)
    with pytest.raises(service.PtPackageNotActiveError) as exc_info:
        await service.create_booking_for_client(
            db_session,
            client_id=client.id,
            slot_id=slot.id,
            pt_package_id=uuid4(),
        )
    assert exc_info.value.code == "pt_package_not_active"


@pytest.mark.asyncio
async def test_create_booking_for_client_pt_package_id_mismatch(
    db_session: AsyncSession,
    seeded_owner: User,
    make_trainer,
    make_client,
    make_pt_package_plan,
    make_pt_package,
    make_slot,
) -> None:
    """PtPackageNotActiveError — id-spoofing protection (resolved package's id
    differs from the supplied pt_package_id)."""
    trainer = await make_trainer()
    client = await make_client()
    plan = await make_pt_package_plan()
    await make_pt_package(client_id=client.id, plan=plan)
    slot = await make_slot(trainer_id=trainer.id)
    with pytest.raises(service.PtPackageNotActiveError):
        await service.create_booking_for_client(
            db_session,
            client_id=client.id,
            slot_id=slot.id,
            pt_package_id=uuid4(),
        )


@pytest.mark.asyncio
async def test_create_booking_for_client_pt_package_exhausted(
    db_session: AsyncSession,
    seeded_owner: User,
    make_trainer,
    make_client,
    make_pt_package_plan,
    make_pt_package,
    make_slot,
) -> None:
    """PtPackageExhaustedError on sessions_remaining=0."""
    trainer = await make_trainer()
    client = await make_client()
    plan = await make_pt_package_plan()
    pkg = await make_pt_package(
        client_id=client.id,
        plan=plan,
        sessions_remaining=0,
    )
    slot = await make_slot(trainer_id=trainer.id)
    with pytest.raises(service.PtPackageExhaustedError):
        await service.create_booking_for_client(
            db_session,
            client_id=client.id,
            slot_id=slot.id,
            pt_package_id=pkg.id,
        )


@pytest.mark.asyncio
async def test_create_booking_for_client_pt_package_expired_before_slot(
    db_session: AsyncSession,
    seeded_owner: User,
    make_trainer,
    make_client,
    make_pt_package_plan,
    make_pt_package,
    make_slot,
) -> None:
    """PtPackageExpiredBeforeSlotError — package end_date < slot start in Moscow TZ."""
    trainer = await make_trainer()
    client = await make_client()
    plan = await make_pt_package_plan()
    # Slot is 30 days from now (in the future).
    future = datetime.now(UTC) + timedelta(days=30)
    # Package end_date is 5 days from now — before the slot's start date (Moscow TZ).
    # The resolver query admits the package because end_date >= today; the service
    # then raises PtPackageExpiredBeforeSlotError because
    # end_date < slot.start_time.astimezone(MOSCOW_TZ).date() (30 days out vs 5 days).
    pkg_end_date = (datetime.now(UTC) + timedelta(days=5)).date()
    pkg = await make_pt_package(
        client_id=client.id,
        plan=plan,
        sessions_remaining=5,
        end_date=pkg_end_date,
    )
    slot = await make_slot(
        trainer_id=trainer.id,
        start_time=future,
        end_time=future + timedelta(hours=1),
    )
    with pytest.raises(service.PtPackageExpiredBeforeSlotError):
        await service.create_booking_for_client(
            db_session,
            client_id=client.id,
            slot_id=slot.id,
            pt_package_id=pkg.id,
        )


@pytest.mark.asyncio
async def test_create_booking_for_client_slot_already_booked_serial(
    db_session: AsyncSession,
    seeded_owner: User,
    make_trainer,
    make_client,
    make_pt_package_plan,
    make_pt_package,
    make_slot,
) -> None:
    """SlotAlreadyBookedError — criterion #1 race guard (CBOOK-03).

    A second confirmed booking on the same slot (serial path) raises
    SlotAlreadyBookedError via the 0-row UPDATE branch (slot is already
    'booked' after the first booking committed).
    """
    trainer = await make_trainer()
    client = await make_client()
    plan = await make_pt_package_plan()
    pkg = await make_pt_package(
        client_id=client.id,
        plan=plan,
        sessions_remaining=10,
    )
    slot = await make_slot(trainer_id=trainer.id)

    # First booking succeeds.
    response1 = await service.create_booking_for_client(
        db_session,
        client_id=client.id,
        slot_id=slot.id,
        pt_package_id=pkg.id,
    )
    assert response1.status == BookingStatus.CONFIRMED

    # Second booking on the same slot → SlotAlreadyBookedError (slot is 'booked').
    with pytest.raises(service.SlotAlreadyBookedError) as exc_info:
        await service.create_booking_for_client(
            db_session,
            client_id=client.id,
            slot_id=slot.id,
            pt_package_id=pkg.id,
        )
    assert exc_info.value.code == "slot_already_booked"
