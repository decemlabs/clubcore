"""Integration tests for schedule.service — Phase 38 plan 38-01 Task 3.

Covers:
  - publish_slot happy path → 201 + audit row.
  - 7 negative paths (trainer_not_found, trainer_inactive, slot_in_past,
    slot_overlap, slot_too_close, boundary OK, idempotent ish).
  - cancel_slot active path → status='cancelled', audit_log row.
  - cancel_slot booked source → 409 invalid_transition (plan 38-03 deferral).
  - list_slots envelope + window filter.
  - resolve_slot_by_id silent-None contract.
  - restore_slot_to_active booked→active + 0-row guard.
  - SlotPublishedPayload kwargs exactly match the 5-key locked schema.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permissions import Role
from app.modules.auth.models import User
from app.modules.schedule import service
from app.modules.schedule.models import TrainerAvailabilitySlot
from app.modules.schedule.schemas import (
    SlotCancelRequest,
    SlotCreateRequest,
    SlotListQuery,
    SlotStatus,
)
from app.modules.trainers.models import Trainer

# ---------------------------------------------------------------------------
# Task 1 import smoke (carries forward) — confirms model + constant remain
# importable after the Task 3 service rewrite.
# ---------------------------------------------------------------------------


def test_trainer_availability_slot_model_imports() -> None:
    """SLOT-01 — ORM model class is importable and exposes the locked tablename."""
    assert TrainerAvailabilitySlot.__tablename__ == "trainer_availability_slots"


def test_slot_buffer_minutes_constant() -> None:
    """SLOT-04 / C-15 — buffer constant hardcoded to 10 minutes for v1.5."""
    from app.modules.schedule.constants import SLOT_BUFFER_MINUTES

    assert SLOT_BUFFER_MINUTES == 10


# ---------------------------------------------------------------------------
# Task 3 — publish_slot happy + negative paths
# ---------------------------------------------------------------------------


def _future_window(
    *, offset_minutes: int = 60, duration_minutes: int = 60
) -> tuple[datetime, datetime]:
    """Return a (start, end) tuple a known offset in the future from now()."""
    start = datetime.now(UTC) + timedelta(minutes=offset_minutes)
    end = start + timedelta(minutes=duration_minutes)
    return start, end


@pytest.mark.asyncio
async def test_publish_slot_happy(
    db_session: AsyncSession,
    seeded_owner: User,
    make_trainer,
) -> None:
    """SLOT-02 — owner publishes a slot; audit row written; status='active'."""
    trainer = await make_trainer()
    start, end = _future_window()
    response = await service.publish_slot(
        db_session,
        seeded_owner,
        SlotCreateRequest(trainer_id=trainer.id, start_time=start, end_time=end),
    )
    assert response.status == SlotStatus.ACTIVE
    assert response.trainer_id == trainer.id
    assert response.created_by_user_id == seeded_owner.id

    # Audit row exists for slot_published with locked event name.
    rows = (
        (
            await db_session.execute(
                text(
                    "SELECT action, resource_type, resource_id, payload "
                    "FROM audit_log WHERE action = 'slot_published'"
                ),
            )
        )
        .mappings()
        .all()
    )
    matching = [r for r in rows if str(r["resource_id"]) == str(response.id)]
    assert len(matching) == 1, f"expected exactly one slot_published row, got {matching}"
    payload = matching[0]["payload"]
    # SlotPublishedPayload: exactly 5 keys, all stringified.
    assert set(payload.keys()) == {
        "slot_id",
        "trainer_id",
        "start_time",
        "end_time",
        "created_by_user_id",
    }
    assert payload["slot_id"] == str(response.id)
    assert payload["trainer_id"] == str(trainer.id)
    assert payload["created_by_user_id"] == str(seeded_owner.id)


@pytest.mark.asyncio
async def test_publish_slot_overlap_409(
    db_session: AsyncSession,
    seeded_owner: User,
    make_trainer,
) -> None:
    """SLOT-03 — second slot overlapping a non-cancelled slot for the same
    trainer raises SlotOverlapError."""
    trainer = await make_trainer()
    start, end = _future_window()
    await service.publish_slot(
        db_session,
        seeded_owner,
        SlotCreateRequest(trainer_id=trainer.id, start_time=start, end_time=end),
    )
    # 30 minutes into the first slot — strict overlap.
    overlap_start = start + timedelta(minutes=30)
    overlap_end = end + timedelta(minutes=30)
    with pytest.raises(service.SlotOverlapError):
        await service.publish_slot(
            db_session,
            seeded_owner,
            SlotCreateRequest(
                trainer_id=trainer.id,
                start_time=overlap_start,
                end_time=overlap_end,
            ),
        )


@pytest.mark.asyncio
async def test_publish_slot_too_close_409(
    db_session: AsyncSession,
    seeded_owner: User,
    make_trainer,
) -> None:
    """SLOT-04 — second slot within SLOT_BUFFER_MINUTES of the first edge
    raises SlotTooCloseError (discriminated from slot_overlap)."""
    trainer = await make_trainer()
    start, end = _future_window(offset_minutes=120, duration_minutes=60)
    await service.publish_slot(
        db_session,
        seeded_owner,
        SlotCreateRequest(trainer_id=trainer.id, start_time=start, end_time=end),
    )
    # 5 minutes after the first slot ends — within the 10-minute buffer.
    too_close_start = end + timedelta(minutes=5)
    too_close_end = too_close_start + timedelta(minutes=60)
    with pytest.raises(service.SlotTooCloseError):
        await service.publish_slot(
            db_session,
            seeded_owner,
            SlotCreateRequest(
                trainer_id=trainer.id,
                start_time=too_close_start,
                end_time=too_close_end,
            ),
        )


@pytest.mark.asyncio
async def test_publish_slot_buffer_boundary_ok(
    db_session: AsyncSession,
    seeded_owner: User,
    make_trainer,
) -> None:
    """SLOT-04 — slot exactly SLOT_BUFFER_MINUTES (10min) after another succeeds.

    Plan task 3 behaviour spec: "publish at 9:00-10:00 then 10:10-11:00 (exactly
    10min — >= boundary) → succeeds."
    """
    trainer = await make_trainer()
    start, end = _future_window(offset_minutes=120, duration_minutes=60)
    await service.publish_slot(
        db_session,
        seeded_owner,
        SlotCreateRequest(trainer_id=trainer.id, start_time=start, end_time=end),
    )
    boundary_start = end + timedelta(minutes=10)
    boundary_end = boundary_start + timedelta(minutes=60)
    second = await service.publish_slot(
        db_session,
        seeded_owner,
        SlotCreateRequest(
            trainer_id=trainer.id,
            start_time=boundary_start,
            end_time=boundary_end,
        ),
    )
    assert second.status == SlotStatus.ACTIVE


@pytest.mark.asyncio
async def test_publish_slot_in_past_409(
    db_session: AsyncSession,
    seeded_owner: User,
    make_trainer,
) -> None:
    """SLOT-05 — start_time <= now() UTC raises SlotInPastError."""
    trainer = await make_trainer()
    start = datetime.now(UTC) - timedelta(hours=1)
    end = start + timedelta(hours=1)
    with pytest.raises(service.SlotInPastError):
        await service.publish_slot(
            db_session,
            seeded_owner,
            SlotCreateRequest(trainer_id=trainer.id, start_time=start, end_time=end),
        )


@pytest.mark.asyncio
async def test_publish_slot_trainer_inactive_409(
    db_session: AsyncSession,
    seeded_owner: User,
    make_trainer,
) -> None:
    """SLOT-06 — publishing against an is_active=False trainer raises
    TrainerInactiveError."""
    trainer = await make_trainer(is_active=False)
    start, end = _future_window()
    with pytest.raises(service.TrainerInactiveError):
        await service.publish_slot(
            db_session,
            seeded_owner,
            SlotCreateRequest(trainer_id=trainer.id, start_time=start, end_time=end),
        )


@pytest.mark.asyncio
async def test_publish_slot_trainer_not_found_404(
    db_session: AsyncSession,
    seeded_owner: User,
) -> None:
    """SLOT-06 — publishing against an unknown trainer_id raises TrainerNotFoundError."""
    from uuid import uuid4

    start, end = _future_window()
    with pytest.raises(service.TrainerNotFoundError):
        await service.publish_slot(
            db_session,
            seeded_owner,
            SlotCreateRequest(trainer_id=uuid4(), start_time=start, end_time=end),
        )


# ---------------------------------------------------------------------------
# Task 3 — cancel_slot active-only path + booked-cascade deferral
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cancel_slot_active_to_cancelled(
    db_session: AsyncSession,
    seeded_owner: User,
    make_trainer,
) -> None:
    """SLOT-09 — owner cancels an active slot; status flips to 'cancelled',
    cancelled_at is set, audit row written with had_booking=False."""
    trainer = await make_trainer()
    start, end = _future_window()
    slot = await service.publish_slot(
        db_session,
        seeded_owner,
        SlotCreateRequest(trainer_id=trainer.id, start_time=start, end_time=end),
    )
    response = await service.cancel_slot(
        db_session,
        seeded_owner,
        slot.id,
        SlotCancelRequest(cancel_reason="operator change of plan"),
    )
    assert response.status == SlotStatus.CANCELLED
    assert response.cancelled_at is not None
    assert response.cancel_reason == "operator change of plan"

    rows = (
        (
            await db_session.execute(
                text(
                    "SELECT payload FROM audit_log WHERE action='slot_cancelled' "
                    "AND resource_id = :sid"
                ),
                {"sid": slot.id},
            )
        )
        .mappings()
        .all()
    )
    assert len(rows) == 1
    payload = rows[0]["payload"]
    assert payload["had_booking"] is False
    assert payload["cancel_reason"] == "operator change of plan"
    assert payload["cancelled_by_user_id"] == str(seeded_owner.id)


@pytest.mark.asyncio
async def test_cancel_slot_booked_source_no_booking_raises_inconsistency(
    db_session: AsyncSession,
    seeded_owner: User,
    make_trainer,
) -> None:
    """SLOT-07 / plan 38-03 — cancelling a `booked` slot with NO paired
    confirmed booking row raises InternalConsistencyError (500).

    This test was the plan 38-01 forward-link guard
    (`test_cancel_slot_booked_source_deferred_to_38_03`) — plan 38-03
    replaced the InvalidSlotTransitionError(`deferred='plan 38-03'`)
    branch with the real cascade. Seeding the slot as 'booked' WITHOUT
    a paired confirmed booking row triggers the DB-invariant defensive
    branch (slot=booked MUST imply confirmed booking exists per
    create_booking UoW guarantee). The cascade-happy-path coverage now
    lives in tests/integration/schedule/test_slot_cancel_cascade.py.
    """
    trainer = await make_trainer()
    start, end = _future_window()
    slot = await service.publish_slot(
        db_session,
        seeded_owner,
        SlotCreateRequest(trainer_id=trainer.id, start_time=start, end_time=end),
    )
    # Seed the inconsistent state: slot status='booked' WITHOUT a paired
    # confirmed booking row (bypasses create_booking's atomic UoW).
    await db_session.execute(
        text("UPDATE trainer_availability_slots SET status='booked' WHERE id = :sid"),
        {"sid": slot.id},
    )
    await db_session.commit()

    with pytest.raises(service.InternalConsistencyError) as excinfo:
        await service.cancel_slot(
            db_session,
            seeded_owner,
            slot.id,
            SlotCancelRequest(cancel_reason="operator change"),
        )
    assert excinfo.value.code == "slot_booking_inconsistency"
    assert excinfo.value.status_code == 500


@pytest.mark.asyncio
async def test_cancel_slot_already_cancelled_409(
    db_session: AsyncSession,
    seeded_owner: User,
    make_trainer,
) -> None:
    """SLOT-09 — cancelling an already-cancelled slot raises InvalidSlotTransitionError
    (cancelled → ∅ terminal in SLOT_STATUS_TRANSITIONS)."""
    trainer = await make_trainer()
    start, end = _future_window()
    slot = await service.publish_slot(
        db_session,
        seeded_owner,
        SlotCreateRequest(trainer_id=trainer.id, start_time=start, end_time=end),
    )
    await service.cancel_slot(
        db_session,
        seeded_owner,
        slot.id,
        SlotCancelRequest(cancel_reason="first"),
    )
    with pytest.raises(service.InvalidSlotTransitionError):
        await service.cancel_slot(
            db_session,
            seeded_owner,
            slot.id,
            SlotCancelRequest(cancel_reason="second"),
        )


@pytest.mark.asyncio
async def test_cancel_slot_not_found_404(
    db_session: AsyncSession,
    seeded_owner: User,
) -> None:
    """SLOT-09 — cancelling an unknown slot_id raises SlotNotFoundError."""
    from uuid import uuid4

    with pytest.raises(service.SlotNotFoundError):
        await service.cancel_slot(
            db_session,
            seeded_owner,
            uuid4(),
            SlotCancelRequest(cancel_reason="unknown id"),
        )


# ---------------------------------------------------------------------------
# Task 3 — list_slots window + envelope
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_slots_envelope_with_window(
    db_session: AsyncSession,
    seeded_owner: User,
    make_trainer,
) -> None:
    """SLOT-08 — list_slots returns PaginatedData envelope for slots in window."""
    trainer = await make_trainer()
    start, end = _future_window(offset_minutes=180, duration_minutes=60)
    slot = await service.publish_slot(
        db_session,
        seeded_owner,
        SlotCreateRequest(trainer_id=trainer.id, start_time=start, end_time=end),
    )
    page = await service.list_slots(
        db_session,
        SlotListQuery(trainer_id=trainer.id),
    )
    assert page.total >= 1
    matched = [item for item in page.items if item.id == slot.id]
    assert len(matched) == 1
    assert matched[0].status == SlotStatus.ACTIVE


# ---------------------------------------------------------------------------
# Task 3 — resolve_slot_by_id silent-None contract + restore_slot_to_active
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_resolve_slot_by_id_returns_orm_row(
    db_session: AsyncSession,
    seeded_owner: User,
    make_trainer,
) -> None:
    """D-37-06 — Phase 38 Task 3 replaces the stub body with a real delegate."""
    trainer = await make_trainer()
    start, end = _future_window()
    slot = await service.publish_slot(
        db_session,
        seeded_owner,
        SlotCreateRequest(trainer_id=trainer.id, start_time=start, end_time=end),
    )
    row = await service.resolve_slot_by_id(db_session, slot.id)
    assert row is not None
    assert row.id == slot.id
    assert row.status == "active"


@pytest.mark.asyncio
async def test_resolve_slot_by_id_missing_returns_none(
    db_session: AsyncSession,
) -> None:
    """D-37-06 silent-None — unknown slot id returns None (NOT 404)."""
    from uuid import uuid4

    row = await service.resolve_slot_by_id(db_session, uuid4())
    assert row is None


@pytest.mark.asyncio
async def test_restore_slot_to_active_from_booked(
    db_session: AsyncSession,
    seeded_owner: User,
    make_trainer,
) -> None:
    """Phase 38 Task 3 — booked → active flip works via predicate-gated UPDATE."""
    trainer = await make_trainer()
    start, end = _future_window()
    slot = await service.publish_slot(
        db_session,
        seeded_owner,
        SlotCreateRequest(trainer_id=trainer.id, start_time=start, end_time=end),
    )
    await db_session.execute(
        text("UPDATE trainer_availability_slots SET status='booked' WHERE id = :sid"),
        {"sid": slot.id},
    )
    await db_session.commit()

    await service.restore_slot_to_active(db_session, slot.id)
    await db_session.commit()

    row = await service.resolve_slot_by_id(db_session, slot.id)
    assert row is not None
    assert row.status == "active"
    assert row.cancelled_at is None


@pytest.mark.asyncio
async def test_restore_slot_to_active_wrong_status_raises(
    db_session: AsyncSession,
    seeded_owner: User,
    make_trainer,
) -> None:
    """Predicate-gated UPDATE: 0-row flip on non-booked source raises InvalidSlotTransitionError."""
    trainer = await make_trainer()
    start, end = _future_window()
    slot = await service.publish_slot(
        db_session,
        seeded_owner,
        SlotCreateRequest(trainer_id=trainer.id, start_time=start, end_time=end),
    )
    # Slot is 'active' — restoring a non-booked slot should be a programmer error.
    with pytest.raises(service.InvalidSlotTransitionError):
        await service.restore_slot_to_active(db_session, slot.id)


# Suppress unused-warning suppression — fixtures are pulled in via parameters.
_ = (Trainer, Role)
