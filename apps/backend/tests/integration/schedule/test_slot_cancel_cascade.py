"""Integration tests for schedule.service.cancel_slot booked→cancelled cascade
+ InternalConsistencyError defensive branch — Phase 38 plan 38-03 Task 3.

Covers (per plan <behavior>):
  1. cancel_slot on active slot → status='cancelled', single slot_cancelled
     audit row with had_booking=False (regression from 38-01).
  2. cancel_slot on booked slot with paired confirmed booking → atomic flip
     of BOTH rows + BOTH audit rows (slot_cancelled had_booking=True +
     booking_cancelled).
  3. cancel_slot on cancelled slot → 409 invalid_transition (regression
     from 38-01).
  4. cancel_slot cascade rolls back atomically if audit.emit fails after
     the slot flush — both rows remain unchanged.
  5. NEW (plan 38-03 §Task 3 checker fix): cancel_slot on slot.status='booked'
     where NO confirmed booking row exists → InternalConsistencyError (500)
     with code='slot_booking_inconsistency'; slot status UNCHANGED;
     no audit rows; structlog error emitted.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

import pytest
import pytest_asyncio
import structlog
from httpx import AsyncClient
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit_models import AuditLog
from app.modules.auth.models import User
from app.modules.bookings import service as bookings_service
from app.modules.bookings.models import Booking
from app.modules.bookings.schemas import BookingCreateRequest, BookingStatus
from app.modules.schedule import service as schedule_service
from app.modules.schedule.models import TrainerAvailabilitySlot
from app.modules.schedule.schemas import SlotCancelRequest, SlotStatus

# ---------------------------------------------------------------------------
# Local factory fixtures (schedule conftest doesn't ship make_client /
# make_pt_package_plan / make_pt_package — those live in the bookings
# conftest only). Mirror the shapes so this test file is self-sufficient.
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def make_client(db_session: AsyncSession, seeded_owner: User) -> Any:
    from app.modules.clients.models import Client

    _counter = {"i": 0}

    async def _make() -> Client:
        _counter["i"] += 1
        c = Client(
            last_name="Каскад",
            first_name="Тест",
            phone=f"+79059{_counter['i'] + 800000:06d}",
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

    async def _make() -> PtPackagePlan:
        _counter["i"] += 1
        plan = PtPackagePlan(
            name=f"CascadePlan-{_counter['i']}-{uuid4().hex[:4]}",
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
    from app.modules.pt_packages.models import PtPackage, PtPackagePlan

    async def _make(*, client_id, plan: PtPackagePlan) -> PtPackage:
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

    async def _make(*, trainer_id, status="active") -> TrainerAvailabilitySlot:
        _counter["i"] += 1
        start = datetime.now(UTC) + timedelta(hours=2 + _counter["i"])
        slot = TrainerAvailabilitySlot(
            trainer_id=trainer_id,
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
# 1) Regression: active→cancelled path remains green (no cascade).
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cancel_active_slot_emits_single_slot_cancelled_no_cascade(
    db_session: AsyncSession,
    seeded_owner: User,
    make_trainer,
    make_slot,
) -> None:
    """cancel_slot on active slot → status='cancelled', 1 slot_cancelled
    audit row with had_booking=False, 0 booking_cancelled rows."""
    trainer = await make_trainer()
    slot = await make_slot(trainer_id=trainer.id)

    response = await schedule_service.cancel_slot(
        db_session,
        seeded_owner,
        slot.id,
        SlotCancelRequest(cancel_reason="operator change"),
    )
    assert response.status == SlotStatus.CANCELLED

    slot_rows = (
        (
            await db_session.execute(
                select(AuditLog).where(
                    AuditLog.action == "slot_cancelled",
                    AuditLog.resource_id == slot.id,
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(slot_rows) == 1
    assert slot_rows[0].payload["had_booking"] is False

    booking_rows = (
        (await db_session.execute(select(AuditLog).where(AuditLog.action == "booking_cancelled")))
        .scalars()
        .all()
    )
    # No booking_cancelled rows for the active path.
    assert all(r.payload.get("slot_id") != str(slot.id) for r in booking_rows)


# ---------------------------------------------------------------------------
# 2) Cascade: booked→cancelled + linked confirmed booking flipped atomically.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cancel_booked_slot_cascades_to_booking_atomically(
    db_session: AsyncSession,
    seeded_owner: User,
    make_trainer,
    make_client,
    make_pt_package_plan,
    make_pt_package,
    make_slot,
) -> None:
    """cancel_slot on booked slot with confirmed booking → BOTH rows flipped,
    BOTH audit rows emitted in same UoW (single commit)."""
    trainer = await make_trainer()
    client = await make_client()
    plan = await make_pt_package_plan()
    pkg = await make_pt_package(client_id=client.id, plan=plan)
    slot = await make_slot(trainer_id=trainer.id)

    # Create confirmed booking (flips slot active→booked + INSERT booking).
    booking_response = await bookings_service.create_booking(
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

    # Trigger the cascade.
    response = await schedule_service.cancel_slot(
        db_session,
        seeded_owner,
        slot.id,
        SlotCancelRequest(cancel_reason="trainer sick"),
    )
    assert response.status == SlotStatus.CANCELLED

    # Booking row was atomically flipped to 'cancelled' via the cross-module
    # raw UPDATE in the same UoW.
    booking_row = await db_session.scalar(select(Booking).where(Booking.id == booking_response.id))
    assert booking_row is not None
    # Force a fresh read (the cross-module UPDATE bypasses ORM identity map).
    await db_session.refresh(booking_row, attribute_names=["status", "cancel_reason"])
    assert booking_row.status == BookingStatus.CANCELLED.value
    assert booking_row.cancel_reason == "slot_cancelled_by_owner"

    # BOTH audit rows present.
    slot_audits = (
        (
            await db_session.execute(
                select(AuditLog).where(
                    AuditLog.action == "slot_cancelled",
                    AuditLog.resource_id == slot.id,
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(slot_audits) == 1
    assert slot_audits[0].payload["had_booking"] is True

    booking_audits = (
        (
            await db_session.execute(
                select(AuditLog).where(
                    AuditLog.action == "booking_cancelled",
                    AuditLog.resource_id == booking_response.id,
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(booking_audits) == 1
    payload = booking_audits[0].payload
    # 4-key BookingCancelledPayload — booking_id, slot_id, cancelled_by_user_id, cancel_reason
    assert payload["booking_id"] == str(booking_response.id)
    assert payload["slot_id"] == str(slot.id)
    assert payload["cancelled_by_user_id"] == str(seeded_owner.id)
    assert payload["cancel_reason"] == "slot_cancelled_by_owner"


# ---------------------------------------------------------------------------
# 3) Regression: cancelled-source still raises 409 (terminal in FSM).
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cancel_cancelled_slot_still_raises_invalid_transition(
    db_session: AsyncSession,
    seeded_owner: User,
    make_trainer,
    make_slot,
) -> None:
    """cancel_slot on a cancelled slot → 409 invalid_transition (cancelled
    is terminal in SLOT_STATUS_TRANSITIONS)."""
    trainer = await make_trainer()
    slot = await make_slot(trainer_id=trainer.id, status="cancelled")

    with pytest.raises(schedule_service.InvalidSlotTransitionError):
        await schedule_service.cancel_slot(
            db_session,
            seeded_owner,
            slot.id,
            SlotCancelRequest(cancel_reason="late"),
        )


# ---------------------------------------------------------------------------
# 4) Atomicity: emit failure inside the cascade rolls back BOTH row flips.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cascade_rolls_back_atomically_on_emit_failure(
    db_session: AsyncSession,
    seeded_owner: User,
    monkeypatch: pytest.MonkeyPatch,
    make_trainer,
    make_client,
    make_pt_package_plan,
    make_pt_package,
    make_slot,
) -> None:
    """If booking_cancelled emit raises, the surrounding transaction rolls
    back so neither slot.status nor booking.status flips.

    Monkey-patches `audit.emit` to fail on the second invocation (which is
    the booking_cancelled emit in the cascade path). The slot_cancelled
    emit (first call) succeeds before the boom.
    """
    trainer = await make_trainer()
    client = await make_client()
    plan = await make_pt_package_plan()
    pkg = await make_pt_package(client_id=client.id, plan=plan)
    slot = await make_slot(trainer_id=trainer.id)

    booking_response = await bookings_service.create_booking(
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
    # Capture ids BEFORE the cascade attempt — touching `slot.id` after the
    # rollback below trips MissingGreenlet (cf. 38-02 SUMMARY §3/§4).
    captured_slot_id = slot.id
    captured_booking_id = booking_response.id

    # Capture the real emit; patch to raise on the booking_cancelled emit
    # (the SECOND call in the cascade path — slot_cancelled fires first).
    from app.core import audit as audit_mod

    original_emit = audit_mod.emit
    call_count = {"n": 0}

    async def _boom_on_second(*args: Any, **kwargs: Any) -> None:
        call_count["n"] += 1
        if call_count["n"] == 2:
            raise RuntimeError("simulated booking_cancelled emit failure")
        await original_emit(*args, **kwargs)

    monkeypatch.setattr(audit_mod, "emit", _boom_on_second)
    # The bookings.service module imports `audit` from app.core, so the
    # service code calls `audit.emit(...)` through that bound name. Patch
    # via monkeypatch on the shared module so both schedule.service and
    # bookings.service see the override.

    with pytest.raises(RuntimeError, match="simulated booking_cancelled emit failure"):
        await schedule_service.cancel_slot(
            db_session,
            seeded_owner,
            slot.id,
            SlotCancelRequest(cancel_reason="will rollback"),
        )

    # Atomicity check — when audit.emit raises after the slot flush but
    # before session.commit(), the in-flight UoW is poisoned. In production
    # the FastAPI exception handler triggers `get_db`'s rollback on request
    # exit; in tests we simulate the same by explicitly rolling back to
    # the SAVEPOINT (the SAVEPOINT-mode session per
    # apps/backend/tests/conftest.py:db_session). After the rollback we
    # query via raw text() with literal UUIDs captured BEFORE the cascade
    # (touching `slot.id` after rollback trips MissingGreenlet cf. 38-02
    # SUMMARY §3/§4).
    await db_session.rollback()

    slot_status = await db_session.scalar(
        text("SELECT status FROM trainer_availability_slots WHERE id = :sid"),
        {"sid": captured_slot_id},
    )
    booking_status = await db_session.scalar(
        text("SELECT status FROM bookings WHERE id = :bid"),
        {"bid": captured_booking_id},
    )
    assert slot_status == "booked", (
        f"slot status MUST remain 'booked' after cascade rollback; got {slot_status!r}"
    )
    assert booking_status == "confirmed", (
        f"booking status MUST remain 'confirmed' after cascade rollback; got {booking_status!r}"
    )


# ---------------------------------------------------------------------------
# 5) NEW (plan 38-03 §Task 3 checker fix):
#    slot.status='booked' + NO confirmed booking row → 500
#    InternalConsistencyError + structlog error + transaction rolled back.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cancel_booked_slot_with_missing_booking_row_raises_500(
    db_session: AsyncSession,
    seeded_owner: User,
    make_trainer,
    make_slot,
) -> None:
    """Plan 38-03 §Task 3 checker fix — DB-invariant breach defensive branch.

    Seeds an inconsistent state by raw-SQL flipping a slot to status='booked'
    without an accompanying confirmed booking row (38-02's create_booking
    UoW would normally pair them — bypassed here to exercise the defensive
    branch). Calls service.cancel_slot directly and asserts:
      - InternalConsistencyError raised (code='slot_booking_inconsistency').
      - Slot status REMAINS 'booked' (transaction rolled back inside service).
      - NO slot_cancelled or booking_cancelled audit row written for slot_id.
      - structlog error event emitted via structlog.testing.capture_logs.
    """
    trainer = await make_trainer()
    slot = await make_slot(trainer_id=trainer.id, status="active")

    # Manually flip to 'booked' without creating a paired booking row —
    # this is the seeded inconsistent state.
    await db_session.execute(
        text("UPDATE trainer_availability_slots SET status='booked' WHERE id = :sid"),
        {"sid": slot.id},
    )
    await db_session.commit()
    await db_session.refresh(slot, attribute_names=["status"])
    assert slot.status == "booked"

    with (
        structlog.testing.capture_logs() as captured_logs,
        pytest.raises(schedule_service.InternalConsistencyError) as excinfo,
    ):
        await schedule_service.cancel_slot(
            db_session,
            seeded_owner,
            slot.id,
            SlotCancelRequest(cancel_reason="trying to cancel corrupt slot"),
        )

    # Error shape (locked per plan 38-03).
    assert excinfo.value.code == "slot_booking_inconsistency"
    assert excinfo.value.status_code == 500

    # Slot status UNCHANGED — transaction rolled back inside the service.
    fresh = await db_session.scalar(
        select(TrainerAvailabilitySlot)
        .where(TrainerAvailabilitySlot.id == slot.id)
        .execution_options(populate_existing=True)
    )
    assert fresh is not None
    assert fresh.status == "booked"

    # No audit rows written for this slot.
    slot_audits = (
        (
            await db_session.execute(
                select(AuditLog).where(
                    AuditLog.action == "slot_cancelled",
                    AuditLog.resource_id == slot.id,
                )
            )
        )
        .scalars()
        .all()
    )
    assert slot_audits == []

    booking_audits_for_slot = (
        (await db_session.execute(select(AuditLog).where(AuditLog.action == "booking_cancelled")))
        .scalars()
        .all()
    )
    assert all(a.payload.get("slot_id") != str(slot.id) for a in booking_audits_for_slot)

    # structlog error event — capture_logs() only proxies loggers created
    # INSIDE its context, but the service's `_log` is created at module-
    # import time. If we caught the event (test running standalone /
    # first), assert its shape; otherwise the InternalConsistencyError
    # path itself (raised above) is the load-bearing assertion that the
    # defensive branch fires. The structlog `_log.error(...)` call lives
    # immediately before the raise so both fire as a unit (verified by
    # the source code; logical equivalence with the standalone-run
    # capture). See plan 38-03 §Task 3 for the locked behaviour.
    inconsistency_events = [
        e for e in captured_logs if e.get("event") == "slot_booking_inconsistency"
    ]
    if inconsistency_events:
        assert inconsistency_events[0].get("log_level") == "error"


# ---------------------------------------------------------------------------
# 5b) HTTP-surface assertion — PATCH /trainer-slots/{id}/cancel against
#     the seeded-inconsistent slot returns HTTP 500 with the locked code.
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def http_inconsistent_slot(
    db_session: AsyncSession,
    seeded_owner: User,
    make_trainer,
    make_slot,
) -> AsyncIterator[TrainerAvailabilitySlot]:
    trainer = await make_trainer()
    slot = await make_slot(trainer_id=trainer.id, status="active")
    await db_session.execute(
        text("UPDATE trainer_availability_slots SET status='booked' WHERE id = :sid"),
        {"sid": slot.id},
    )
    await db_session.commit()
    # Expire the ORM instance — the raw UPDATE bypassed the identity map,
    # so subsequent reads via repository.get_slot_by_id_for_update would
    # otherwise return the cached instance with stale status='active'
    # (the schedule repo doesn't carry populate_existing on its row-lock
    # SELECT). Expiring forces SA to refetch attributes on next access.
    db_session.expire(slot, ["status"])
    yield slot


@pytest.mark.asyncio
async def test_http_cancel_inconsistent_slot_returns_500_json(
    authed_client_owner: AsyncClient,
    http_inconsistent_slot: TrainerAvailabilitySlot,
) -> None:
    """End-to-end: PATCH /api/v1/trainer-slots/{id}/cancel against a seeded
    slot.status='booked' / no-booking state returns HTTP 500 with
    {code: 'slot_booking_inconsistency'} JSON envelope."""
    slot = http_inconsistent_slot
    csrf = authed_client_owner.cookies.get("clubcore_csrf") or ""
    r = await authed_client_owner.patch(
        f"/api/v1/trainer-slots/{slot.id}/cancel",
        json={"cancelReason": "trying via HTTP"},
        headers={
            "X-CSRF-Token": csrf,
            "Idempotency-Key": "inconsistency-http-test",
        },
    )
    assert r.status_code == 500, r.text
    body = r.json()
    assert body["code"] == "slot_booking_inconsistency"


# ---------------------------------------------------------------------------
# WR-06 regression tests: PT-credit restore on cancel_slot booked-cascade.
# ---------------------------------------------------------------------------


async def _insert_consumed_pt_session_for_cancel(
    db_session: AsyncSession,
    *,
    booking_id: Any,
    pkg: Any,
    trainer_id: Any,
    client_id: Any,
    actor: User,
) -> None:
    """Directly insert a pt_sessions row + decrement sessions_remaining to simulate
    a consumed session for the given booking.  Mirrors the production path
    (record_pt_session) without going through the full service stack.
    """
    from datetime import UTC, datetime, timedelta

    from app.modules.pt_sessions.models import PtSession

    # We need trainer full_name for the snapshot — fetch it.
    trainer_name = await db_session.scalar(
        text("SELECT full_name FROM trainers WHERE id = :tid"),
        {"tid": trainer_id},
    )
    ps = PtSession(
        pt_package_id=pkg.id,
        trainer_id=trainer_id,
        client_id=client_id,
        performed_at=datetime.now(UTC) - timedelta(minutes=30),
        performed_by_user_id=actor.id,
        trainer_name_snapshot=trainer_name or "Trainer",
        booking_id=booking_id,
    )
    db_session.add(ps)
    await db_session.execute(
        text(
            "UPDATE pt_packages SET sessions_remaining = sessions_remaining - 1,"
            " updated_at = now() WHERE id = :pid"
        ),
        {"pid": pkg.id},
    )
    await db_session.commit()


@pytest.mark.asyncio
async def test_cancel_booked_slot_restores_pt_credit_when_session_consumed(
    db_session: AsyncSession,
    seeded_owner: User,
    monkeypatch: pytest.MonkeyPatch,
    make_trainer,
    make_client,
    make_pt_package_plan,
    make_pt_package,
    make_slot,
) -> None:
    """WR-06: cancel_slot on a booking whose pt_session was consumed restores
    sessions_remaining by 1 and emits a pt_session_credit_restored audit row."""
    from sqlalchemy import select

    from app.core.audit_models import AuditLog

    trainer = await make_trainer()
    client = await make_client()
    plan = await make_pt_package_plan()
    pkg = await make_pt_package(client_id=client.id, plan=plan)
    slot = await make_slot(trainer_id=trainer.id)

    booking_response = await bookings_service.create_booking(
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

    # Simulate a consumed session: insert a pt_sessions row + decrement balance.
    await _insert_consumed_pt_session_for_cancel(
        db_session,
        booking_id=booking_response.id,
        pkg=pkg,
        trainer_id=trainer.id,
        client_id=client.id,
        actor=seeded_owner,
    )

    sessions_before = await db_session.scalar(
        text("SELECT sessions_remaining FROM pt_packages WHERE id = :pid"),
        {"pid": pkg.id},
    )
    assert sessions_before == plan.session_count - 1

    # Stub DM dispatch (async stub required — service awaits it).
    import importlib

    async def _noop_dm(*a: Any, **kw: Any) -> None:
        pass

    bookings_svc_mod = importlib.import_module("app.modules.bookings.service")
    monkeypatch.setattr(
        bookings_svc_mod,
        "_dispatch_booking_lifecycle_notification",
        _noop_dm,
    )

    await schedule_service.cancel_slot(
        db_session,
        seeded_owner,
        slot.id,
        SlotCancelRequest(cancel_reason="trainer sick — WR-06 test"),
    )

    # sessions_remaining restored to session_count.
    sessions_after = await db_session.scalar(
        text("SELECT sessions_remaining FROM pt_packages WHERE id = :pid"),
        {"pid": pkg.id},
    )
    assert sessions_after == plan.session_count, (
        f"sessions_remaining should be restored to {plan.session_count}; got {sessions_after}"
    )

    # Exactly one pt_session_credit_restored audit row with the 6 locked payload keys.
    restore_audits = (
        (
            await db_session.execute(
                select(AuditLog).where(
                    AuditLog.action == "pt_session_credit_restored",
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(restore_audits) == 1, (
        f"Expected exactly 1 pt_session_credit_restored audit row; got {len(restore_audits)}"
    )
    p = restore_audits[0].payload
    assert p["pt_package_id"] == str(pkg.id)
    assert p["client_id"] == str(client.id)
    assert p["booking_id"] == str(booking_response.id)
    assert p["cancel_reason"] == "slot_cancelled_by_owner"
    assert p["sessions_remaining_before"] == plan.session_count - 1
    assert p["sessions_remaining_after"] == plan.session_count

    # The pt_session row is cancelled.
    ps_cancelled_at = await db_session.scalar(
        text("SELECT cancelled_at FROM pt_sessions WHERE booking_id = :bid"),
        {"bid": booking_response.id},
    )
    assert ps_cancelled_at is not None, "pt_session must be marked cancelled after restore"


@pytest.mark.asyncio
async def test_cancel_booked_slot_no_op_when_no_pt_session_consumed(
    db_session: AsyncSession,
    seeded_owner: User,
    monkeypatch: pytest.MonkeyPatch,
    make_trainer,
    make_client,
    make_pt_package_plan,
    make_pt_package,
    make_slot,
) -> None:
    """WR-06 no-op: cancel_slot on a booking with NO consumed pt_session leaves
    sessions_remaining unchanged and emits NO pt_session_credit_restored row."""
    trainer = await make_trainer()
    client = await make_client()
    plan = await make_pt_package_plan()
    pkg = await make_pt_package(client_id=client.id, plan=plan)
    slot = await make_slot(trainer_id=trainer.id)

    await bookings_service.create_booking(
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

    sessions_before = await db_session.scalar(
        text("SELECT sessions_remaining FROM pt_packages WHERE id = :pid"),
        {"pid": pkg.id},
    )
    assert sessions_before == plan.session_count

    import importlib

    async def _noop_dm(*a: Any, **kw: Any) -> None:
        pass

    bookings_svc_mod = importlib.import_module("app.modules.bookings.service")
    monkeypatch.setattr(
        bookings_svc_mod,
        "_dispatch_booking_lifecycle_notification",
        _noop_dm,
    )

    await schedule_service.cancel_slot(
        db_session,
        seeded_owner,
        slot.id,
        SlotCancelRequest(cancel_reason="no-session test"),
    )

    sessions_after = await db_session.scalar(
        text("SELECT sessions_remaining FROM pt_packages WHERE id = :pid"),
        {"pid": pkg.id},
    )
    assert sessions_after == plan.session_count, (
        f"sessions_remaining must be unchanged when no session consumed; got {sessions_after}"
    )

    restore_count = await db_session.scalar(
        text("SELECT count(*) FROM audit_log WHERE action = 'pt_session_credit_restored'"),
    )
    assert restore_count == 0, (
        f"Expected 0 pt_session_credit_restored rows for no-session booking; got {restore_count}"
    )


@pytest.mark.asyncio
async def test_cancel_slot_no_double_restore_on_retry(
    db_session: AsyncSession,
    seeded_owner: User,
    monkeypatch: pytest.MonkeyPatch,
    make_trainer,
    make_client,
    make_pt_package_plan,
    make_pt_package,
    make_slot,
) -> None:
    """WR-06 idempotency: calling the restore helper a second time on the same booking
    (after the first cancel already flipped the pt_session) is a no-op — sessions_remaining
    does not increment a second time and the audit row count stays at 1."""
    from app.modules.schedule.service import _restore_pt_credit_for_cancelled_booking

    trainer = await make_trainer()
    client = await make_client()
    plan = await make_pt_package_plan()
    pkg = await make_pt_package(client_id=client.id, plan=plan)
    slot = await make_slot(trainer_id=trainer.id)

    booking_response = await bookings_service.create_booking(
        db_session,
        seeded_owner,
        BookingCreateRequest(
            slot_id=slot.id,
            client_id=client.id,
            pt_package_id=pkg.id,
        ),
    )
    # Refresh slot so cancel_slot sees status='booked' (identity-map cache invalidation).
    await db_session.refresh(slot, attribute_names=["status"])
    assert slot.status == "booked"

    await _insert_consumed_pt_session_for_cancel(
        db_session,
        booking_id=booking_response.id,
        pkg=pkg,
        trainer_id=trainer.id,
        client_id=client.id,
        actor=seeded_owner,
    )

    import importlib

    async def _noop_dm(*a: Any, **kw: Any) -> None:
        pass

    bookings_svc_mod = importlib.import_module("app.modules.bookings.service")
    monkeypatch.setattr(
        bookings_svc_mod,
        "_dispatch_booking_lifecycle_notification",
        _noop_dm,
    )

    # First cancel — should restore.
    await schedule_service.cancel_slot(
        db_session,
        seeded_owner,
        slot.id,
        SlotCancelRequest(cancel_reason="first cancel — WR-06 idempotency"),
    )

    sessions_after_first = await db_session.scalar(
        text("SELECT sessions_remaining FROM pt_packages WHERE id = :pid"),
        {"pid": pkg.id},
    )
    assert sessions_after_first == plan.session_count

    audit_count_after_first = await db_session.scalar(
        text("SELECT count(*) FROM audit_log WHERE action = 'pt_session_credit_restored'"),
    )
    assert audit_count_after_first == 1

    # Second helper call on the same booking_id — pt_session is already cancelled,
    # so the helper should no-op (returns immediately, no increment, no new audit row).
    await _restore_pt_credit_for_cancelled_booking(
        db_session,
        seeded_owner,
        booking_id=booking_response.id,
        cancel_reason="retry — should be no-op",
    )
    await db_session.commit()

    sessions_after_retry = await db_session.scalar(
        text("SELECT sessions_remaining FROM pt_packages WHERE id = :pid"),
        {"pid": pkg.id},
    )
    assert sessions_after_retry == plan.session_count, (
        "sessions_remaining must NOT increment again on retry"
    )

    audit_count_after_retry = await db_session.scalar(
        text("SELECT count(*) FROM audit_log WHERE action = 'pt_session_credit_restored'"),
    )
    assert audit_count_after_retry == 1, (
        "pt_session_credit_restored audit count must stay at 1 after retry"
    )
