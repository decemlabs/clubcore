"""Integration tests for bookings.service.create_booking — plan 38-02 Task 3.

Covers the 1 happy path + 9 negative paths from the plan <behavior> spec:
  - happy path → status='confirmed', slot flipped active→booked, audit row.
  - SlotNotFound (404 slot_not_found).
  - SlotNotAvailable (slot.status != 'active' before any concurrency).
  - PtPackageNotActive (no active package for client).
  - PtPackageNotActive (active package id doesn't match payload — defensive).
  - PtPackageExhausted (sessions_remaining=0).
  - TrainerMismatch — NOT testable in 38-02 because PtPackage.trainer_id
    is added by plan 38-04 (Alembic 0018); the field is not in the schema
    until then, so `getattr(pt_package, 'trainer_id', None)` returns None.
    A placeholder test asserts the safe-by-default behaviour (NULL trainer
    == "any trainer" per C-08).
  - PtPackageExpiredBeforeSlot (Moscow-TZ comparison — 01:00 Moscow = 22:00
    UTC prior day).
  - SlotNotAvailable (slot.status='cancelled').
  - InvalidBookingTransition (complete_booking on already-cancelled booking).

Race test (BOOK-TEST-01) lives in test_booking_race.py — uses
`db_session_real_commit` because SAVEPOINT isolation interferes with
concurrent UPDATE serialisation.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit_models import AuditLog
from app.modules.auth.models import User
from app.modules.bookings import service
from app.modules.bookings.models import Booking
from app.modules.bookings.schemas import BookingCreateRequest, BookingStatus


@pytest.mark.asyncio
async def test_create_booking_happy(
    db_session: AsyncSession,
    seeded_owner: User,
    make_trainer,
    make_client,
    make_pt_package_plan,
    make_pt_package,
    make_slot,
) -> None:
    """BOOK-02 happy path — owner creates booking; slot flips active→booked;
    booking_created audit row written; response status='confirmed'."""
    trainer = await make_trainer()
    client = await make_client()
    plan = await make_pt_package_plan()
    pkg = await make_pt_package(
        client_id=client.id,
        plan=plan,
        sessions_remaining=5,
    )
    slot = await make_slot(trainer_id=trainer.id)

    response = await service.create_booking(
        db_session,
        seeded_owner,
        BookingCreateRequest(
            slot_id=slot.id,
            client_id=client.id,
            pt_package_id=pkg.id,
        ),
    )

    assert response.status == BookingStatus.CONFIRMED
    assert response.slot_id == slot.id
    assert response.client_id == client.id
    assert response.pt_package_id == pkg.id
    assert response.created_by_user_id == seeded_owner.id

    # DB invariants — booking row exists; slot row flipped to 'booked'.
    booking_row = await db_session.scalar(select(Booking).where(Booking.id == response.id))
    assert booking_row is not None
    assert booking_row.status == "confirmed"
    # The slot status was flipped via raw cross-module sa.text() UPDATE
    # (bookings.repository.update_slot_status_predicate_gated), so the
    # ORM identity-map cache still holds the pre-UPDATE 'active' value
    # for the seeded `slot` instance. Expire it to force a fresh read.
    await db_session.refresh(slot, attribute_names=["status"])
    assert slot.status == "booked"

    # Audit invariant — booking_created emitted exactly once with the
    # locked payload shape (5 keys, UUIDs stringified per D-38-17).
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
    payload = audit_rows[0].payload
    assert payload["booking_id"] == str(response.id)
    assert payload["slot_id"] == str(slot.id)
    assert payload["client_id"] == str(client.id)
    assert payload["pt_package_id"] == str(pkg.id)
    assert payload["created_by_user_id"] == str(seeded_owner.id)


@pytest.mark.asyncio
async def test_create_booking_slot_not_found(
    db_session: AsyncSession,
    seeded_owner: User,
    make_client,
    make_pt_package_plan,
    make_pt_package,
) -> None:
    """SlotNotFound — non-existent slot id → 404 slot_not_found."""
    client = await make_client()
    plan = await make_pt_package_plan()
    pkg = await make_pt_package(client_id=client.id, plan=plan)

    with pytest.raises(service.SlotNotFoundError) as exc_info:
        await service.create_booking(
            db_session,
            seeded_owner,
            BookingCreateRequest(
                slot_id=uuid4(),
                client_id=client.id,
                pt_package_id=pkg.id,
            ),
        )
    assert exc_info.value.code == "slot_not_found"
    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_create_booking_slot_not_available_cancelled(
    db_session: AsyncSession,
    seeded_owner: User,
    make_trainer,
    make_client,
    make_pt_package_plan,
    make_pt_package,
    make_slot,
) -> None:
    """SlotNotAvailable — slot.status='cancelled' → 409 slot_not_available."""
    trainer = await make_trainer()
    client = await make_client()
    plan = await make_pt_package_plan()
    pkg = await make_pt_package(client_id=client.id, plan=plan)
    slot = await make_slot(trainer_id=trainer.id, status="cancelled")

    with pytest.raises(service.SlotNotAvailableError) as exc_info:
        await service.create_booking(
            db_session,
            seeded_owner,
            BookingCreateRequest(
                slot_id=slot.id,
                client_id=client.id,
                pt_package_id=pkg.id,
            ),
        )
    assert exc_info.value.code == "slot_not_available"


@pytest.mark.asyncio
async def test_create_booking_pt_package_not_active_none(
    db_session: AsyncSession,
    seeded_owner: User,
    make_trainer,
    make_client,
    make_slot,
) -> None:
    """PtPackageNotActive — client has no active pt_package → 409."""
    trainer = await make_trainer()
    client = await make_client()
    slot = await make_slot(trainer_id=trainer.id)

    with pytest.raises(service.PtPackageNotActiveError) as exc_info:
        await service.create_booking(
            db_session,
            seeded_owner,
            BookingCreateRequest(
                slot_id=slot.id,
                client_id=client.id,
                pt_package_id=uuid4(),
            ),
        )
    assert exc_info.value.code == "pt_package_not_active"


@pytest.mark.asyncio
async def test_create_booking_pt_package_not_active_id_mismatch(
    db_session: AsyncSession,
    seeded_owner: User,
    make_trainer,
    make_client,
    make_pt_package_plan,
    make_pt_package,
    make_slot,
) -> None:
    """PtPackageNotActive — payload pt_package_id != active package id → 409
    (defensive against id-spoofing — server is the arbiter)."""
    trainer = await make_trainer()
    client = await make_client()
    plan = await make_pt_package_plan()
    pkg = await make_pt_package(client_id=client.id, plan=plan)
    slot = await make_slot(trainer_id=trainer.id)
    # NOTE: pkg.id is the only active package for the client.
    bogus_pkg_id = uuid4()
    assert bogus_pkg_id != pkg.id

    with pytest.raises(service.PtPackageNotActiveError) as exc_info:
        await service.create_booking(
            db_session,
            seeded_owner,
            BookingCreateRequest(
                slot_id=slot.id,
                client_id=client.id,
                pt_package_id=bogus_pkg_id,
            ),
        )
    assert exc_info.value.code == "pt_package_not_active"


@pytest.mark.asyncio
async def test_create_booking_pt_package_exhausted(
    db_session: AsyncSession,
    seeded_owner: User,
    make_trainer,
    make_client,
    make_pt_package_plan,
    make_pt_package,
    make_slot,
) -> None:
    """PtPackageExhausted — sessions_remaining=0 → 409 pt_package_exhausted."""
    trainer = await make_trainer()
    client = await make_client()
    plan = await make_pt_package_plan()
    pkg = await make_pt_package(
        client_id=client.id,
        plan=plan,
        sessions_remaining=0,
    )
    slot = await make_slot(trainer_id=trainer.id)

    with pytest.raises(service.PtPackageExhaustedError) as exc_info:
        await service.create_booking(
            db_session,
            seeded_owner,
            BookingCreateRequest(
                slot_id=slot.id,
                client_id=client.id,
                pt_package_id=pkg.id,
            ),
        )
    assert exc_info.value.code == "pt_package_exhausted"


@pytest.mark.asyncio
async def test_create_booking_pt_package_expired_before_slot_moscow_tz(
    db_session: AsyncSession,
    seeded_owner: User,
    make_trainer,
    make_client,
    make_pt_package_plan,
    make_pt_package,
    make_slot,
) -> None:
    """PtPackageExpiredBeforeSlot (D-38-12 / Pitfall 18 / BOOK-04).

    Crucial assertion: the comparison happens in Moscow TZ. A slot at
    01:00 Moscow is 22:00 UTC on the prior day. A package whose end_date
    is that prior Moscow business date MUST reject the slot —
    naive .date() on the UTC datetime would mis-classify the slot as
    belonging to 2026-06-30 and incorrectly accept it.
    """
    from zoneinfo import ZoneInfo

    moscow_tz = ZoneInfo("Europe/Moscow")
    trainer = await make_trainer()
    client = await make_client()
    plan = await make_pt_package_plan()

    # Use a future date so this test cannot expire while preserving the
    # 01:00 Moscow -> 22:00 UTC on the previous day boundary condition.
    slot_date_moscow = datetime.now(tz=moscow_tz).date() + timedelta(days=1)
    slot_start_moscow = datetime.combine(
        slot_date_moscow,
        datetime.min.time().replace(hour=1),
        tzinfo=moscow_tz,
    )
    slot_end_moscow = slot_start_moscow + timedelta(hours=1)
    slot = await make_slot(
        trainer_id=trainer.id,
        start_time=slot_start_moscow.astimezone(UTC),
        end_time=slot_end_moscow.astimezone(UTC),
    )
    pkg = await make_pt_package(
        client_id=client.id,
        plan=plan,
        end_date=slot_date_moscow - timedelta(days=1),
    )

    with pytest.raises(service.PtPackageExpiredBeforeSlotError) as exc_info:
        await service.create_booking(
            db_session,
            seeded_owner,
            BookingCreateRequest(
                slot_id=slot.id,
                client_id=client.id,
                pt_package_id=pkg.id,
            ),
        )
    assert exc_info.value.code == "pt_package_expired_before_slot"


@pytest.mark.asyncio
async def test_create_booking_pt_package_null_end_date_skips_validity_guard(
    db_session: AsyncSession,
    seeded_owner: User,
    make_trainer,
    make_client,
    make_pt_package_plan,
    make_pt_package,
    make_slot,
) -> None:
    """Бессрочный package (end_date IS NULL) skips the validity-window guard
    even for far-future slots (D-38-12 / D-33-14)."""
    trainer = await make_trainer()
    client = await make_client()
    # validity_days=None → end_date=NULL on the pt_package.
    plan = await make_pt_package_plan(validity_days=None)
    pkg = await make_pt_package(
        client_id=client.id,
        plan=plan,
        end_date=None,
    )
    far_future_start = datetime.now(UTC) + timedelta(days=365)
    slot = await make_slot(
        trainer_id=trainer.id,
        start_time=far_future_start,
        end_time=far_future_start + timedelta(hours=1),
    )

    response = await service.create_booking(
        db_session,
        seeded_owner,
        BookingCreateRequest(
            slot_id=slot.id,
            client_id=client.id,
            pt_package_id=pkg.id,
        ),
    )
    assert response.status == BookingStatus.CONFIRMED


@pytest.mark.asyncio
async def test_create_booking_trainer_mismatch_skipped_when_pkg_trainer_null(
    db_session: AsyncSession,
    seeded_owner: User,
    make_trainer,
    make_client,
    make_pt_package_plan,
    make_pt_package,
    make_slot,
) -> None:
    """C-08 — NULL pt_package.trainer_id means "any trainer"; create_booking
    succeeds when slot.trainer_id is set and package trainer is unset/None.

    NOTE: PtPackage.trainer_id is added by plan 38-04 (Alembic 0018); until
    then the column does not exist on the ORM, so `getattr` returns None
    and the guard short-circuits via the `pkg_trainer_id is None` branch.
    This test pins the safe-by-default behaviour."""
    trainer = await make_trainer()
    client = await make_client()
    plan = await make_pt_package_plan()
    pkg = await make_pt_package(client_id=client.id, plan=plan)
    slot = await make_slot(trainer_id=trainer.id)

    response = await service.create_booking(
        db_session,
        seeded_owner,
        BookingCreateRequest(
            slot_id=slot.id,
            client_id=client.id,
            pt_package_id=pkg.id,
        ),
    )
    assert response.status == BookingStatus.CONFIRMED


@pytest.mark.asyncio
async def test_create_booking_double_book_serial_409(
    db_session: AsyncSession,
    seeded_owner: User,
    make_trainer,
    make_client,
    make_pt_package_plan,
    make_pt_package,
    make_slot,
) -> None:
    """Serial double-book — same slot booked twice in sequence:
    first call → 201; second call → 409 slot_not_available (the slot's
    status is now 'booked' so the pre-INSERT guard fires before the
    partial UNIQUE)."""
    trainer = await make_trainer()
    client = await make_client()
    plan = await make_pt_package_plan(session_count=10)
    pkg = await make_pt_package(client_id=client.id, plan=plan, sessions_remaining=10)
    slot = await make_slot(trainer_id=trainer.id)

    # First booking succeeds.
    response = await service.create_booking(
        db_session,
        seeded_owner,
        BookingCreateRequest(
            slot_id=slot.id,
            client_id=client.id,
            pt_package_id=pkg.id,
        ),
    )
    assert response.status == BookingStatus.CONFIRMED

    # Second booking — slot is now 'booked' → 409 slot_already_booked
    # (the predicate-gated UPDATE matches 0 rows; refresh shows status='booked'
    # so we surface SlotAlreadyBookedError rather than SlotNotAvailableError
    # per D-38-15 / BOOK-10 unified race-loser code).
    with pytest.raises(service.SlotAlreadyBookedError) as exc_info:
        await service.create_booking(
            db_session,
            seeded_owner,
            BookingCreateRequest(
                slot_id=slot.id,
                client_id=client.id,
                pt_package_id=pkg.id,
            ),
        )
    assert exc_info.value.code == "slot_already_booked"

    # DB invariant — exactly one confirmed booking for the slot.
    count = await db_session.scalar(
        select(func.count())
        .select_from(Booking)
        .where(
            Booking.slot_id == slot.id,
            Booking.status == "confirmed",
        )
    )
    assert count == 1


@pytest.mark.asyncio
async def test_complete_booking_happy(
    db_session: AsyncSession,
    seeded_owner: User,
    make_trainer,
    make_client,
    make_pt_package_plan,
    make_pt_package,
    make_slot,
) -> None:
    """complete_booking flips confirmed→completed and sets completed_at."""
    trainer = await make_trainer()
    client = await make_client()
    plan = await make_pt_package_plan()
    pkg = await make_pt_package(client_id=client.id, plan=plan)
    slot = await make_slot(trainer_id=trainer.id)
    created = await service.create_booking(
        db_session,
        seeded_owner,
        BookingCreateRequest(
            slot_id=slot.id,
            client_id=client.id,
            pt_package_id=pkg.id,
        ),
    )

    # Caller-owns-txn — we commit the surrounding transaction.
    await service.complete_booking(db_session, created.id)
    await db_session.commit()

    row = await db_session.scalar(select(Booking).where(Booking.id == created.id))
    assert row is not None
    assert row.status == "completed"
    assert row.completed_at is not None


@pytest.mark.asyncio
async def test_complete_booking_invalid_transition_when_not_confirmed(
    db_session: AsyncSession,
    seeded_owner: User,
    make_trainer,
    make_client,
    make_pt_package_plan,
    make_pt_package,
    make_slot,
) -> None:
    """complete_booking on a status='completed' (already-completed) booking
    → 409 invalid_transition (predicate-gated UPDATE returns 0 rows)."""
    trainer = await make_trainer()
    client = await make_client()
    plan = await make_pt_package_plan()
    pkg = await make_pt_package(client_id=client.id, plan=plan)
    slot = await make_slot(trainer_id=trainer.id)
    created = await service.create_booking(
        db_session,
        seeded_owner,
        BookingCreateRequest(
            slot_id=slot.id,
            client_id=client.id,
            pt_package_id=pkg.id,
        ),
    )
    await service.complete_booking(db_session, created.id)
    await db_session.commit()

    with pytest.raises(service.InvalidBookingTransitionError) as exc_info:
        await service.complete_booking(db_session, created.id)
    assert exc_info.value.code == "invalid_transition"
