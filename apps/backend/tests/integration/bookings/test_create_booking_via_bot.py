"""Phase 40 D-40-04 — bookings.service.create_booking_via_bot integration tests.

Mirrors the structure of ``test_bookings_create.py`` (the Phase 38 ``create_booking``
test fleet) — 1 happy path + the 7 domain error classes the bot path can raise.
Adds the Phase 40-specific audit-row assertions:

  - ``audit_log.actor_user_id`` is DB-level NULL (raw None, not the string
    ``"None"``).
  - ``audit_log.payload.actor_role == "telegram_bot"`` (Literal — D-40-05).
  - ``audit_log.payload.created_by_user_id`` is None (D-40-05 / BLOCKER-4).
  - The inserted ``bookings`` row has ``created_by_user_id IS NULL``
    (BLOCKER-4 — Alembic 0021 / ORM model nullable).
  - The returned ``BookingResponse`` carries ``trainer_full_name`` +
    ``slot_start_time`` from the Phase 40 BLOCKER-2 JOIN projection.

These tests are placed in ``tests/integration/bookings/`` (not
``tests/unit/bookings/``) because the bot service entry-point needs a real
PostgreSQL session — the slot-flip ``sa.text()`` UPDATE, audit-row INSERT,
and partial-UNIQUE race translation cannot be exercised without it. CI runs
the suite against a live Postgres container; the worktree env skips cleanly
when ``127.0.0.1:5432`` is unreachable (shared autouse conftest fixture).

Plan-doc note: the original plan listed ``tests/unit/bookings/`` for these
cases. They are integration-grade by construction (real DB session, real
audit/registry wiring), so we keep them next to ``test_bookings_create.py``
where the existing fixtures + factories live. Logged in the SUMMARY as a
structural deviation (no behaviour change).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit_models import AuditLog
from app.modules.auth.models import User
from app.modules.bookings import service
from app.modules.bookings.models import Booking
from app.modules.bookings.schemas import BookingStatus


@pytest.mark.asyncio
async def test_create_booking_via_bot_happy_path(
    db_session: AsyncSession,
    seeded_owner: User,  # only used by factories below — no actor on the bot path
    make_trainer,
    make_client,
    make_pt_package_plan,
    make_pt_package,
    make_slot,
) -> None:
    """D-40-04 happy path — slot flips active→booked, booking lands with
    created_by_user_id IS NULL, audit row carries actor_role='telegram_bot'."""
    trainer = await make_trainer(full_name="Иван Тренеров")
    client = await make_client()
    plan = await make_pt_package_plan()
    pkg = await make_pt_package(
        client_id=client.id,
        plan=plan,
        sessions_remaining=5,
    )
    slot = await make_slot(trainer_id=trainer.id)

    response = await service.create_booking_via_bot(
        db_session,
        client_id=client.id,
        slot_id=slot.id,
        pt_package_id=pkg.id,
    )

    # Response shape — Phase 40 BLOCKER-2 fields present + D-40-05 None actor.
    assert response.status == BookingStatus.CONFIRMED
    assert response.slot_id == slot.id
    assert response.client_id == client.id
    assert response.pt_package_id == pkg.id
    assert response.created_by_user_id is None
    assert response.trainer_full_name == "Иван Тренеров"
    assert response.slot_start_time == slot.start_time

    # DB invariants — booking row exists with NULL actor; slot flipped to 'booked'.
    booking_row = await db_session.scalar(
        select(Booking).where(Booking.id == response.id)
    )
    assert booking_row is not None
    assert booking_row.status == "confirmed"
    assert booking_row.created_by_user_id is None
    await db_session.refresh(slot, attribute_names=["status"])
    assert slot.status == "booked"

    # Audit invariant — booking_created emitted with telegram_bot role and
    # NULL actor_user_id at the DB column level + NULL payload.created_by_user_id.
    audit_rows = (
        await db_session.execute(
            select(AuditLog).where(
                AuditLog.action == "booking_created",
                AuditLog.resource_id == response.id,
            )
        )
    ).scalars().all()
    assert len(audit_rows) == 1
    audit_row = audit_rows[0]
    assert audit_row.actor_user_id is None
    payload = audit_row.payload
    assert payload["actor_role"] == "telegram_bot"
    assert payload["created_by_user_id"] is None
    assert payload["booking_id"] == str(response.id)
    assert payload["slot_id"] == str(slot.id)
    assert payload["client_id"] == str(client.id)
    assert payload["pt_package_id"] == str(pkg.id)


@pytest.mark.asyncio
async def test_create_booking_via_bot_slot_not_found(
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
        await service.create_booking_via_bot(
            db_session,
            client_id=client.id,
            slot_id=uuid4(),
            pt_package_id=pkg.id,
        )
    assert exc_info.value.code == "slot_not_found"


@pytest.mark.asyncio
async def test_create_booking_via_bot_slot_not_available_cancelled(
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
        await service.create_booking_via_bot(
            db_session,
            client_id=client.id,
            slot_id=slot.id,
            pt_package_id=pkg.id,
        )


@pytest.mark.asyncio
async def test_create_booking_via_bot_slot_not_available_in_past(
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
        await service.create_booking_via_bot(
            db_session,
            client_id=client.id,
            slot_id=slot.id,
            pt_package_id=pkg.id,
        )


@pytest.mark.asyncio
async def test_create_booking_via_bot_pt_package_not_active_none(
    db_session: AsyncSession,
    seeded_owner: User,
    make_trainer,
    make_client,
    make_slot,
) -> None:
    """PtPackageNotActiveError when client has no active pt_package."""
    trainer = await make_trainer()
    client = await make_client()
    slot = await make_slot(trainer_id=trainer.id)
    with pytest.raises(service.PtPackageNotActiveError):
        await service.create_booking_via_bot(
            db_session,
            client_id=client.id,
            slot_id=slot.id,
            pt_package_id=uuid4(),
        )


@pytest.mark.asyncio
async def test_create_booking_via_bot_pt_package_id_mismatch(
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
        await service.create_booking_via_bot(
            db_session,
            client_id=client.id,
            slot_id=slot.id,
            pt_package_id=uuid4(),
        )


@pytest.mark.asyncio
async def test_create_booking_via_bot_pt_package_exhausted(
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
        await service.create_booking_via_bot(
            db_session,
            client_id=client.id,
            slot_id=slot.id,
            pt_package_id=pkg.id,
        )


@pytest.mark.asyncio
async def test_create_booking_via_bot_pt_package_expired_before_slot(
    db_session: AsyncSession,
    seeded_owner: User,
    make_trainer,
    make_client,
    make_pt_package_plan,
    make_pt_package,
    make_slot,
) -> None:
    """PtPackageExpiredBeforeSlotError — slot.start_time after pt_package.end_date.

    The package must still be ACTIVE today (``end_date >= today`` so the
    Step-2 ``get_active_pt_package`` filter returns it) yet expire BEFORE the
    future slot date (so the Step-4 Moscow-TZ validity-window guard fires).
    An ``end_date`` in the past would instead be excluded by the active-package
    query and raise ``PtPackageNotActiveError`` — never reaching Step 4.
    """
    from zoneinfo import ZoneInfo

    moscow_tz = ZoneInfo("Europe/Moscow")
    trainer = await make_trainer()
    client = await make_client()
    plan = await make_pt_package_plan()
    # Slot 3 days out; package expires tomorrow (Moscow business date) — still
    # active now, but strictly before the slot's Moscow date.
    slot_start = datetime.now(UTC) + timedelta(days=3)
    slot = await make_slot(trainer_id=trainer.id, start_time=slot_start)
    pkg = await make_pt_package(
        client_id=client.id,
        plan=plan,
        end_date=(datetime.now(moscow_tz) + timedelta(days=1)).date(),
    )
    with pytest.raises(service.PtPackageExpiredBeforeSlotError):
        await service.create_booking_via_bot(
            db_session,
            client_id=client.id,
            slot_id=slot.id,
            pt_package_id=pkg.id,
        )


@pytest.mark.asyncio
async def test_create_booking_via_bot_already_booked_race(
    db_session: AsyncSession,
    seeded_owner: User,
    make_trainer,
    make_client,
    make_pt_package_plan,
    make_pt_package,
    make_slot,
) -> None:
    """SlotAlreadyBookedError — slot pre-flipped to 'booked' before the bot
    UoW runs (mirrors the Phase 38 serial double-book scenario)."""
    trainer = await make_trainer()
    client = await make_client()
    plan = await make_pt_package_plan()
    pkg = await make_pt_package(client_id=client.id, plan=plan)
    slot = await make_slot(trainer_id=trainer.id, status="booked")
    # status='booked' falls through Step 1's status != 'active' guard — both
    # SlotNotAvailableError and SlotAlreadyBookedError surface as
    # _BOT_BOOK_DENIED_DM at the handler layer (anti-oracle).
    with pytest.raises(service.SlotNotAvailableError):
        await service.create_booking_via_bot(
            db_session,
            client_id=client.id,
            slot_id=slot.id,
            pt_package_id=pkg.id,
        )


@pytest.mark.asyncio
async def test_audit_row_for_bot_booking_has_null_actor_user_id(
    db_session: AsyncSession,
    seeded_owner: User,
    make_trainer,
    make_client,
    make_pt_package_plan,
    make_pt_package,
    make_slot,
) -> None:
    """DB-level forensic chain assertion — audit_log row's actor_user_id is
    a true SQL NULL after a bot booking lands (not the string 'None')."""
    trainer = await make_trainer()
    client = await make_client()
    plan = await make_pt_package_plan()
    pkg = await make_pt_package(client_id=client.id, plan=plan)
    slot = await make_slot(trainer_id=trainer.id)

    response = await service.create_booking_via_bot(
        db_session,
        client_id=client.id,
        slot_id=slot.id,
        pt_package_id=pkg.id,
    )

    raw = (
        await db_session.execute(
            text(
                "SELECT actor_user_id, payload "
                "FROM audit_log WHERE action = 'booking_created' "
                "  AND resource_id = :rid"
            ),
            {"rid": response.id},
        )
    ).first()
    assert raw is not None
    actor_user_id_col, payload = raw
    assert actor_user_id_col is None
    assert payload["actor_role"] == "telegram_bot"
    assert payload.get("created_by_user_id") is None
