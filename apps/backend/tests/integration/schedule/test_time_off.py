"""Integration tests for trainer time-off CRUD (Phase 59 REC-03, REC-04).

Covers:
  1. active-only window: active slots cancelled (cancel_reason='trainer_time_off'),
     slot_cancelled audit (had_booking=False), time-off inserted, trainer_time_off_created
     emitted — 201.
  2. booked slot without ?force: 409 error_code='time_off_booked_conflict',
     body lists conflicting slot_ids + booking_ids; bookings REMAIN confirmed (no silent cancel).
  3. ?force=true: confirmed bookings flipped to 'cancelled' via raw UPDATE
     (cancel_reason='trainer_time_off'), booking_cancelled audit per booking,
     DM dispatch helper invoked per booking (spy stub) — 201.
  4. reception 403 on create (both force and non-force).
  5. reception 403 on delete.
  6. delete: emits trainer_time_off_cancelled, does NOT resurrect cancelled slots.
  7. reception can list time-off (200 — REC-04 both roles).
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit_models import AuditLog
from app.modules.auth.models import User
from app.modules.bookings import service as bookings_service
from app.modules.bookings.models import Booking
from app.modules.bookings.schemas import BookingCreateRequest, BookingStatus
from app.modules.schedule import service as schedule_service
from app.modules.schedule.models import TrainerAvailabilitySlot, TrainerTimeOff
from app.modules.schedule.schemas import TimeOffCreate
from app.modules.trainers.models import Trainer


# ---------------------------------------------------------------------------
# Local DB-direct factories (mirror test_slot_cancel_cascade.py style)
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def make_client(db_session: AsyncSession, seeded_owner: User) -> Any:
    from app.modules.clients.models import Client

    _counter = {"i": 0}

    async def _make(*, email: str | None = None) -> Any:
        _counter["i"] += 1
        c = Client(
            last_name="TimeOff",
            first_name="Тест",
            phone=f"+79041{_counter['i'] + 900000:06d}",
            email=email,
            created_by_user_id=seeded_owner.id,
        )
        db_session.add(c)
        await db_session.commit()
        await db_session.refresh(c)
        return c

    return _make


@pytest_asyncio.fixture
async def make_pt_package_plan(db_session: AsyncSession) -> Any:
    from app.modules.pt_packages.models import PtPackagePlan

    _counter = {"i": 0}

    async def _make() -> Any:
        _counter["i"] += 1
        plan = PtPackagePlan(
            name=f"TimeOffPlan-{_counter['i']}-{uuid4().hex[:4]}",
            session_count=10,
            price_kopecks=500000,
            validity_days=90,
        )
        db_session.add(plan)
        await db_session.commit()
        await db_session.refresh(plan)
        return plan

    return _make


@pytest_asyncio.fixture
async def make_pt_package(db_session: AsyncSession) -> Any:
    from app.modules.pt_packages.models import PtPackage

    async def _make(*, client_id: Any, plan: Any) -> Any:
        today = datetime.now(UTC).date()
        pkg = PtPackage(
            client_id=client_id,
            plan_id=plan.id,
            plan_name_snapshot=plan.name,
            session_count_snapshot=plan.session_count,
            price_kopecks_snapshot=plan.price_kopecks,
            validity_days_snapshot=plan.validity_days,
            sessions_remaining=plan.session_count,
            status="active",
            start_date=today,
            end_date=today + timedelta(days=plan.validity_days - 1),
        )
        db_session.add(pkg)
        await db_session.commit()
        await db_session.refresh(pkg)
        return pkg

    return _make


@pytest_asyncio.fixture
async def make_slot(db_session: AsyncSession, seeded_owner: User) -> Any:
    _counter = {"i": 0}

    async def _make(
        *,
        trainer: Trainer,
        hours_ahead: int = 2,
        status: str = "active",
    ) -> TrainerAvailabilitySlot:
        _counter["i"] += 1
        start = datetime.now(UTC) + timedelta(hours=hours_ahead + _counter["i"])
        slot = TrainerAvailabilitySlot(
            trainer_id=trainer.id,
            start_time=start,
            end_time=start + timedelta(hours=1),
            status=status,
            created_by_user_id=seeded_owner.id,
        )
        db_session.add(slot)
        await db_session.commit()
        await db_session.refresh(slot)
        return slot

    return _make


# ---------------------------------------------------------------------------
# Helper: build a TimeOffCreate that covers the given slots' window.
# ---------------------------------------------------------------------------


def _time_off_covering(trainer: Trainer, slots: list[Any]) -> TimeOffCreate:
    starts = [s.start_time for s in slots]
    ends = [s.end_time for s in slots]
    block_start = min(starts) - timedelta(minutes=5)
    block_end = max(ends) + timedelta(minutes=5)
    return TimeOffCreate(
        trainer_id=trainer.id,
        block_start=block_start,
        block_end=block_end,
        reason="integration test",
    )


# ---------------------------------------------------------------------------
# 1. Active-only window → active slots cancelled, time-off inserted.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_time_off_active_only_cancels_slots(
    db_session: AsyncSession,
    seeded_owner: User,
    make_trainer,
    make_slot,
) -> None:
    """Time-off over an active-only window: slots cancelled, time-off created."""
    trainer = await make_trainer()
    slot1 = await make_slot(trainer=trainer, hours_ahead=2)
    slot2 = await make_slot(trainer=trainer, hours_ahead=3)

    data = _time_off_covering(trainer, [slot1, slot2])
    time_off_resp = await schedule_service.create_time_off(
        db_session, seeded_owner, data
    )
    assert time_off_resp.trainer_id == trainer.id

    # Slots are cancelled.
    await db_session.refresh(slot1, attribute_names=["status", "cancel_reason"])
    await db_session.refresh(slot2, attribute_names=["status", "cancel_reason"])
    assert slot1.status == "cancelled"
    assert slot1.cancel_reason == "trainer_time_off"
    assert slot2.status == "cancelled"
    assert slot2.cancel_reason == "trainer_time_off"

    # slot_cancelled audit rows (had_booking=False).
    for slot in [slot1, slot2]:
        audits = (
            await db_session.execute(
                select(AuditLog).where(
                    AuditLog.action == "slot_cancelled",
                    AuditLog.resource_id == slot.id,
                )
            )
        ).scalars().all()
        assert len(audits) == 1
        assert audits[0].payload["had_booking"] is False
        assert audits[0].payload["cancel_reason"] == "trainer_time_off"

    # trainer_time_off_created audit row.
    time_off_audits = (
        await db_session.execute(
            select(AuditLog).where(
                AuditLog.action == "trainer_time_off_created",
            )
        )
    ).scalars().all()
    assert any(
        str(a.resource_id) == str(time_off_resp.id) for a in time_off_audits
    ), "trainer_time_off_created audit not found"


# ---------------------------------------------------------------------------
# 2. Booked slot + no force → 409, bookings remain confirmed.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_time_off_booked_without_force_returns_409_and_preserves_booking(
    db_session: AsyncSession,
    seeded_owner: User,
    make_trainer,
    make_client,
    make_pt_package_plan,
    make_pt_package,
    make_slot,
) -> None:
    """409 time_off_booked_conflict when force=False; bookings stay confirmed."""
    trainer = await make_trainer()
    client = await make_client()
    plan = await make_pt_package_plan()
    pkg = await make_pt_package(client_id=client.id, plan=plan)
    slot = await make_slot(trainer=trainer, hours_ahead=5)

    # Create a confirmed booking against the slot.
    booking_resp = await bookings_service.create_booking(
        db_session,
        seeded_owner,
        BookingCreateRequest(
            slot_id=slot.id,
            client_id=client.id,
            pt_package_id=pkg.id,
        ),
    )
    await db_session.refresh(slot, attribute_names=["status"])
    assert slot.status == "booked"

    data = _time_off_covering(trainer, [slot])
    with pytest.raises(schedule_service.TimeOffBookedConflictError) as excinfo:
        await schedule_service.create_time_off(
            db_session, seeded_owner, data, force=False
        )

    exc = excinfo.value
    assert exc.code == "time_off_booked_conflict"
    assert exc.fields is not None
    assert str(slot.id) in exc.fields["conflicting_slot_ids"]  # type: ignore[operator]
    assert str(booking_resp.id) in exc.fields["conflicting_booking_ids"]  # type: ignore[operator]

    # Roll back the in-flight transaction (mirrors test_slot_cancel_cascade.py §4).
    await db_session.rollback()

    # Booking MUST still be confirmed — no silent cancel (T-59-10).
    booking_row = await db_session.scalar(
        text("SELECT status FROM bookings WHERE id = :bid"),
        {"bid": booking_resp.id},
    )
    assert booking_row == "confirmed", (
        f"Booking must remain 'confirmed' after 409-without-force; got {booking_row!r}"
    )


# ---------------------------------------------------------------------------
# 3. Booked slot + force=True → booking cascade + DM + audit.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_time_off_force_cascades_booking_and_dispatches_dm(
    db_session: AsyncSession,
    seeded_owner: User,
    monkeypatch: pytest.MonkeyPatch,
    make_trainer,
    make_client,
    make_pt_package_plan,
    make_pt_package,
    make_slot,
) -> None:
    """force=True: booking cancelled via raw UPDATE + audit rows + DM dispatched."""
    trainer = await make_trainer()
    client = await make_client()
    plan = await make_pt_package_plan()
    pkg = await make_pt_package(client_id=client.id, plan=plan)
    slot = await make_slot(trainer=trainer, hours_ahead=10)

    booking_resp = await bookings_service.create_booking(
        db_session,
        seeded_owner,
        BookingCreateRequest(
            slot_id=slot.id,
            client_id=client.id,
            pt_package_id=pkg.id,
        ),
    )
    await db_session.refresh(slot, attribute_names=["status"])
    assert slot.status == "booked"
    captured_slot_id = slot.id
    captured_booking_id = booking_resp.id

    # Spy on DM dispatch — patch the module that schedule.service loads via importlib.
    dm_calls: list[dict[str, Any]] = []

    async def _dm_spy(booking: Any, *, kind: str, **kwargs: Any) -> None:
        dm_calls.append({"kind": kind, "booking": booking})

    import importlib

    bookings_svc_mod = importlib.import_module("app.modules.bookings.service")
    monkeypatch.setattr(
        bookings_svc_mod,
        "_dispatch_booking_lifecycle_notification",
        _dm_spy,
    )

    data = _time_off_covering(trainer, [slot])
    time_off_resp = await schedule_service.create_time_off(
        db_session, seeded_owner, data, force=True
    )
    assert time_off_resp.trainer_id == trainer.id

    # Booking is cancelled via the raw UPDATE.
    booking_status = await db_session.scalar(
        text("SELECT status FROM bookings WHERE id = :bid"),
        {"bid": captured_booking_id},
    )
    assert booking_status == "cancelled", (
        f"Booking must be 'cancelled' after force cascade; got {booking_status!r}"
    )
    booking_cancel_reason = await db_session.scalar(
        text("SELECT cancel_reason FROM bookings WHERE id = :bid"),
        {"bid": captured_booking_id},
    )
    assert booking_cancel_reason == "trainer_time_off"

    # slot_cancelled audit with had_booking=True.
    slot_audits = (
        await db_session.execute(
            select(AuditLog).where(
                AuditLog.action == "slot_cancelled",
                AuditLog.resource_id == captured_slot_id,
            )
        )
    ).scalars().all()
    assert len(slot_audits) == 1
    assert slot_audits[0].payload["had_booking"] is True
    assert slot_audits[0].payload["cancel_reason"] == "trainer_time_off"

    # booking_cancelled audit per cascaded booking.
    booking_audits = (
        await db_session.execute(
            select(AuditLog).where(
                AuditLog.action == "booking_cancelled",
                AuditLog.resource_id == captured_booking_id,
            )
        )
    ).scalars().all()
    assert len(booking_audits) == 1
    assert booking_audits[0].payload["cancel_reason"] == "trainer_time_off"
    assert booking_audits[0].payload["booking_id"] == str(captured_booking_id)

    # trainer_time_off_created audit row.
    time_off_audits = (
        await db_session.execute(
            select(AuditLog).where(
                AuditLog.action == "trainer_time_off_created",
            )
        )
    ).scalars().all()
    assert any(str(a.resource_id) == str(time_off_resp.id) for a in time_off_audits)

    # DM dispatch helper was called exactly once per cascaded booking.
    assert len(dm_calls) == 1
    assert dm_calls[0]["kind"] == "cancelled_by_owner"


# ---------------------------------------------------------------------------
# 4. Reception 403 on time-off create (force and non-force both 403).
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_reception_create_time_off_forbidden(
    authed_client_reception: AsyncClient,
    make_trainer,
) -> None:
    """Reception 403 on POST /time-off regardless of ?force flag (T-59-09)."""
    trainer = await make_trainer()
    now = datetime.now(UTC)
    csrf = authed_client_reception.cookies.get("sportzal_csrf") or ""

    body = {
        "trainerId": str(trainer.id),
        "blockStart": now.isoformat(),
        "blockEnd": (now + timedelta(hours=2)).isoformat(),
        "reason": "test",
    }

    for force_val in [False, True]:
        r = await authed_client_reception.post(
            "/api/v1/time-off",
            json=body,
            params={"force": str(force_val).lower()},
            headers={
                "X-CSRF-Token": csrf,
                "Idempotency-Key": f"time-off-recep-{uuid4()}",
            },
        )
        assert r.status_code == 403, (
            f"Reception must get 403 on time-off create (force={force_val}); got {r.status_code}"
        )


# ---------------------------------------------------------------------------
# 5. Reception 403 on time-off delete.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_reception_delete_time_off_forbidden(
    authed_client_reception: AsyncClient,
    db_session: AsyncSession,
    seeded_owner: User,
    make_trainer,
) -> None:
    """Reception 403 on DELETE /time-off/{id}."""
    trainer = await make_trainer()
    # Seed a time-off block directly via DB.
    now = datetime.now(UTC)
    time_off = TrainerTimeOff(
        trainer_id=trainer.id,
        block_start=now,
        block_end=now + timedelta(hours=2),
        reason=None,
    )
    db_session.add(time_off)
    await db_session.commit()
    await db_session.refresh(time_off)

    csrf = authed_client_reception.cookies.get("sportzal_csrf") or ""
    r = await authed_client_reception.delete(
        f"/api/v1/time-off/{time_off.id}",
        headers={
            "X-CSRF-Token": csrf,
            "Idempotency-Key": f"time-off-del-recep-{uuid4()}",
        },
    )
    assert r.status_code == 403, r.text


# ---------------------------------------------------------------------------
# 6. Delete emits trainer_time_off_cancelled; does NOT resurrect slots.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_delete_time_off_emits_cancelled_and_does_not_resurrect_slots(
    authed_client_owner: AsyncClient,
    db_session: AsyncSession,
    seeded_owner: User,
    make_trainer,
    make_slot,
) -> None:
    """DELETE /time-off/{id}: emits trainer_time_off_cancelled; cancelled slots stay cancelled."""
    trainer = await make_trainer()
    slot = await make_slot(trainer=trainer, hours_ahead=20)
    captured_slot_id = slot.id

    csrf = authed_client_owner.cookies.get("sportzal_csrf") or ""

    # Create time-off via HTTP (cancels the overlapping active slot).
    now = datetime.now(UTC)
    create_r = await authed_client_owner.post(
        "/api/v1/time-off",
        json={
            "trainerId": str(trainer.id),
            "blockStart": (slot.start_time - timedelta(minutes=5)).isoformat(),
            "blockEnd": (slot.end_time + timedelta(minutes=5)).isoformat(),
            "reason": "forward-only test",
        },
        headers={
            "X-CSRF-Token": csrf,
            "Idempotency-Key": f"time-off-fwd-create-{uuid4()}",
        },
    )
    assert create_r.status_code == 201, create_r.text
    time_off_id = create_r.json()["data"]["id"]

    # Slot is now cancelled.
    slot_status = await db_session.scalar(
        text("SELECT status FROM trainer_availability_slots WHERE id = :sid"),
        {"sid": captured_slot_id},
    )
    assert slot_status == "cancelled"

    # Delete the time-off block.
    delete_r = await authed_client_owner.delete(
        f"/api/v1/time-off/{time_off_id}",
        headers={
            "X-CSRF-Token": csrf,
            "Idempotency-Key": f"time-off-fwd-delete-{uuid4()}",
        },
    )
    assert delete_r.status_code == 204, delete_r.text

    # trainer_time_off_cancelled audit emitted.
    cancelled_audit = (
        await db_session.execute(
            select(AuditLog).where(
                AuditLog.action == "trainer_time_off_cancelled",
            )
        )
    ).scalars().all()
    assert any(
        str(a.resource_id) == time_off_id for a in cancelled_audit
    ), "trainer_time_off_cancelled audit not found"

    # Slot still cancelled (forward-only — no resurrection).
    slot_status_after = await db_session.scalar(
        text("SELECT status FROM trainer_availability_slots WHERE id = :sid"),
        {"sid": captured_slot_id},
    )
    assert slot_status_after == "cancelled", (
        "Cancelled slot must stay cancelled after time-off deletion (forward-only)"
    )


# ---------------------------------------------------------------------------
# 7. Reception can list time-off (REC-04 both roles).
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_reception_can_list_time_off(
    authed_client_reception: AsyncClient,
    make_trainer,
) -> None:
    """GET /time-off → 200 for reception (LIST SCHEDULE_SLOTS not in OWNER_ONLY)."""
    trainer = await make_trainer()
    r = await authed_client_reception.get(
        "/api/v1/time-off",
        params={"trainerId": str(trainer.id)},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert "total" in body["data"]
    assert isinstance(body["data"]["items"], list)


# ---------------------------------------------------------------------------
# 8. HTTP: POST /time-off without force → 409 with error_code + conflict IDs.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_http_create_time_off_without_force_returns_409_with_conflict_detail(
    authed_client_owner: AsyncClient,
    db_session: AsyncSession,
    seeded_owner: User,
    make_trainer,
    make_client,
    make_pt_package_plan,
    make_pt_package,
    make_slot,
) -> None:
    """POST /time-off (no force) when booked slot exists → 409 with conflict detail."""
    trainer = await make_trainer()
    client = await make_client()
    plan = await make_pt_package_plan()
    pkg = await make_pt_package(client_id=client.id, plan=plan)
    slot = await make_slot(trainer=trainer, hours_ahead=30)

    booking_resp = await bookings_service.create_booking(
        db_session,
        seeded_owner,
        BookingCreateRequest(
            slot_id=slot.id,
            client_id=client.id,
            pt_package_id=pkg.id,
        ),
    )
    await db_session.refresh(slot, attribute_names=["status"])
    assert slot.status == "booked"

    csrf = authed_client_owner.cookies.get("sportzal_csrf") or ""
    r = await authed_client_owner.post(
        "/api/v1/time-off",
        json={
            "trainerId": str(trainer.id),
            "blockStart": (slot.start_time - timedelta(minutes=5)).isoformat(),
            "blockEnd": (slot.end_time + timedelta(minutes=5)).isoformat(),
            "reason": "test 409",
        },
        headers={
            "X-CSRF-Token": csrf,
            "Idempotency-Key": f"time-off-409-{uuid4()}",
        },
    )
    assert r.status_code == 409, r.text
    body = r.json()
    assert body["code"] == "time_off_booked_conflict"

    # Conflict detail contains the slot and booking IDs.
    data = body.get("data", {})
    assert str(slot.id) in data["conflictingSlotIds"]
    assert str(booking_resp.id) in data["conflictingBookingIds"]

    # Booking still confirmed (post-409 safety — T-59-10).
    booking_status = await db_session.scalar(
        text("SELECT status FROM bookings WHERE id = :bid"),
        {"bid": booking_resp.id},
    )
    assert booking_status == "confirmed", (
        "Booking MUST remain confirmed after 409-without-force"
    )
