"""Integration tests for POST /api/v1/pt-sessions with booking_id (Plan 38-05).

Plan 38-05 — Phase 38 PKG-04 / PKG-05 / PKG-06 coverage:

  - Happy path: record session with booking_id pointing at confirmed booking →
    201; booking row transitions to status='completed'; pt_sessions row has
    booking_id set; audit_log pt_session_recorded payload includes
    booking_id=<UUID-string>.
  - Walk-in path (no booking_id): existing v1.4 flow unchanged → 201; audit
    payload has booking_id=None.
  - 409 booking_not_confirmed: booking.status='cancelled' (defensive — and
    also 'completed' for replay-attack defence).
  - 409 booking_mismatch: request.pt_package_id != booking.pt_package_id.
  - 409 booking_mismatch: slot.trainer_id != request.trainer_id.
  - 404 booking_not_found: booking_id points at non-existent UUID.
  - PKG-06 NO-revert (lock-in): record session with booking_id → booking
    'completed' → cancel that pt_session → booking REMAINS 'completed'
    (FSM forward-only, no automatic revert).

Cross-module seeding discipline: bookings + trainer_availability_slots rows are
inserted via direct SQL in this file (NOT via HTTP) because the booking-create
flow has its own validation path that doesn't fit the test fixtures here; the
schedule/bookings ORM imports stay outside pt_sessions module code per the
modules-independent contract (test code is exempt from the contract per
``.importlinter`` source_modules scope).
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit_models import AuditLog
from app.modules.auth.models import User
from app.modules.bookings.models import Booking
from app.modules.clients.models import Client
from app.modules.pt_packages.models import PtPackage, PtPackagePlan
from app.modules.pt_sessions.models import PtSession
from app.modules.schedule.models import TrainerAvailabilitySlot
from app.modules.trainers.models import Trainer


def _csrf_headers(
    client: AsyncClient,
    *,
    idempotency_key: str | None = None,
) -> dict[str, str]:
    headers: dict[str, str] = {
        "X-CSRF-Token": client.cookies.get("sportzal_csrf", "") or ""
    }
    if idempotency_key is not None:
        headers["Idempotency-Key"] = idempotency_key
    return headers


def _record_body(
    pt_package_id: UUID,
    trainer_id: UUID,
    *,
    booking_id: UUID | None = None,
    performed_at: datetime | None = None,
    notes: str | None = None,
) -> dict[str, Any]:
    body: dict[str, Any] = {
        "ptPackageId": str(pt_package_id),
        "trainerId": str(trainer_id),
        "performedAt": (
            performed_at or datetime.now(UTC) - timedelta(minutes=10)
        ).isoformat(),
    }
    if booking_id is not None:
        body["bookingId"] = str(booking_id)
    if notes is not None:
        body["notes"] = notes
    return body


async def _seed_slot(
    db_session: AsyncSession,
    *,
    trainer_id: UUID,
    created_by_user_id: UUID,
    start_time: datetime | None = None,
    status: str = "booked",
) -> TrainerAvailabilitySlot:
    """Insert a TrainerAvailabilitySlot row directly via the ORM.

    Default ``status='booked'`` reflects that the slot is already associated
    with a confirmed booking (the test sets up the post-booking state and
    exercises the PT-session record + completion path).
    """
    start = start_time or (datetime.now(UTC) + timedelta(hours=2))
    slot = TrainerAvailabilitySlot(
        trainer_id=trainer_id,
        start_time=start,
        end_time=start + timedelta(hours=1),
        status=status,
        created_by_user_id=created_by_user_id,
    )
    db_session.add(slot)
    await db_session.commit()
    await db_session.refresh(slot)
    return slot


async def _seed_booking(
    db_session: AsyncSession,
    *,
    slot_id: UUID,
    client_id: UUID,
    pt_package_id: UUID,
    created_by_user_id: UUID,
    status: str = "confirmed",
) -> Booking:
    """Insert a Booking row directly via the ORM (bypasses HTTP create flow)."""
    booking = Booking(
        slot_id=slot_id,
        client_id=client_id,
        pt_package_id=pt_package_id,
        status=status,
        created_by_user_id=created_by_user_id,
    )
    db_session.add(booking)
    await db_session.commit()
    await db_session.refresh(booking)
    return booking


# ---------------------------------------------------------------------------
# Happy paths.
# ---------------------------------------------------------------------------


async def test_record_with_booking_id_completes_booking(
    authed_client_reception: AsyncClient,
    db_session: AsyncSession,
    seeded_reception: User,
    make_client: Callable[..., Awaitable[Client]],
    make_pt_package_plan: Callable[..., Awaitable[PtPackagePlan]],
    make_pt_package: Callable[..., Awaitable[PtPackage]],
    make_trainer: Callable[..., Awaitable[Trainer]],
) -> None:
    """PKG-04 / PKG-05 happy path: 201 + booking transitions to 'completed' +
    pt_sessions row carries booking_id + audit payload includes booking_id."""
    plan = await make_pt_package_plan(session_count=5)
    client_row = await make_client()
    pkg = await make_pt_package(
        client_id=client_row.id, plan=plan, sessions_remaining=5
    )
    trainer = await make_trainer(full_name="Иван Петрович")
    slot = await _seed_slot(
        db_session,
        trainer_id=trainer.id,
        created_by_user_id=seeded_reception.id,
        status="booked",
    )
    booking = await _seed_booking(
        db_session,
        slot_id=slot.id,
        client_id=client_row.id,
        pt_package_id=pkg.id,
        created_by_user_id=seeded_reception.id,
        status="confirmed",
    )

    r = await authed_client_reception.post(
        "/api/v1/pt-sessions",
        json=_record_body(pkg.id, trainer.id, booking_id=booking.id),
        headers=_csrf_headers(
            authed_client_reception, idempotency_key=uuid4().hex
        ),
    )
    assert r.status_code == 201, r.text
    data = r.json()["data"]
    assert data["bookingId"] == str(booking.id)

    # Booking row transitioned to 'completed' (force a fresh read — the
    # bookings.service.complete_booking uses a raw text UPDATE that
    # bypasses the ORM identity-map cache).
    await db_session.refresh(booking, attribute_names=["status", "completed_at"])
    assert booking.status == "completed"
    assert booking.completed_at is not None

    # pt_sessions row carries booking_id.
    pt_session = await db_session.scalar(
        select(PtSession).where(PtSession.id == UUID(data["id"]))
    )
    assert pt_session is not None
    assert pt_session.booking_id == booking.id

    # audit_log pt_session_recorded payload includes booking_id stringified.
    recorded = (
        await db_session.scalars(
            select(AuditLog).where(
                AuditLog.action == "pt_session_recorded",
                AuditLog.resource_id == UUID(data["id"]),
            )
        )
    ).all()
    assert len(recorded) == 1
    payload = recorded[0].payload
    assert payload["booking_id"] == str(booking.id)


async def test_record_without_booking_id_unchanged_walk_in_flow(
    authed_client_reception: AsyncClient,
    db_session: AsyncSession,
    make_client: Callable[..., Awaitable[Client]],
    make_pt_package_plan: Callable[..., Awaitable[PtPackagePlan]],
    make_pt_package: Callable[..., Awaitable[PtPackage]],
    make_trainer: Callable[..., Awaitable[Trainer]],
) -> None:
    """Walk-in path (no booking_id): existing v1.4 flow unchanged → 201;
    audit payload has booking_id=None; pt_sessions.booking_id IS NULL."""
    plan = await make_pt_package_plan(session_count=5)
    client_row = await make_client()
    pkg = await make_pt_package(
        client_id=client_row.id, plan=plan, sessions_remaining=5
    )
    trainer = await make_trainer()

    r = await authed_client_reception.post(
        "/api/v1/pt-sessions",
        json=_record_body(pkg.id, trainer.id),
        headers=_csrf_headers(
            authed_client_reception, idempotency_key=uuid4().hex
        ),
    )
    assert r.status_code == 201, r.text
    data = r.json()["data"]
    assert data["bookingId"] is None

    pt_session = await db_session.scalar(
        select(PtSession).where(PtSession.id == UUID(data["id"]))
    )
    assert pt_session is not None
    assert pt_session.booking_id is None

    recorded = (
        await db_session.scalars(
            select(AuditLog).where(
                AuditLog.action == "pt_session_recorded",
                AuditLog.resource_id == UUID(data["id"]),
            )
        )
    ).all()
    assert len(recorded) == 1
    assert recorded[0].payload["booking_id"] is None


# ---------------------------------------------------------------------------
# Negative paths.
# ---------------------------------------------------------------------------


async def test_record_with_unknown_booking_returns_404(
    authed_client_reception: AsyncClient,
    make_client: Callable[..., Awaitable[Client]],
    make_pt_package_plan: Callable[..., Awaitable[PtPackagePlan]],
    make_pt_package: Callable[..., Awaitable[PtPackage]],
    make_trainer: Callable[..., Awaitable[Trainer]],
) -> None:
    """PKG-04: booking_id pointing at non-existent UUID → 404 booking_not_found."""
    plan = await make_pt_package_plan()
    client_row = await make_client()
    pkg = await make_pt_package(client_id=client_row.id, plan=plan)
    trainer = await make_trainer()

    r = await authed_client_reception.post(
        "/api/v1/pt-sessions",
        json=_record_body(pkg.id, trainer.id, booking_id=uuid4()),
        headers=_csrf_headers(
            authed_client_reception, idempotency_key=uuid4().hex
        ),
    )
    assert r.status_code == 404, r.text
    assert r.json()["code"] == "booking_not_found"


async def test_record_with_cancelled_booking_returns_409(
    authed_client_reception: AsyncClient,
    db_session: AsyncSession,
    seeded_reception: User,
    make_client: Callable[..., Awaitable[Client]],
    make_pt_package_plan: Callable[..., Awaitable[PtPackagePlan]],
    make_pt_package: Callable[..., Awaitable[PtPackage]],
    make_trainer: Callable[..., Awaitable[Trainer]],
) -> None:
    """PKG-04 / T-38-05-02: booking.status='cancelled' → 409 booking_not_confirmed."""
    plan = await make_pt_package_plan()
    client_row = await make_client()
    pkg = await make_pt_package(client_id=client_row.id, plan=plan)
    trainer = await make_trainer()
    slot = await _seed_slot(
        db_session,
        trainer_id=trainer.id,
        created_by_user_id=seeded_reception.id,
        status="cancelled",
    )
    booking = await _seed_booking(
        db_session,
        slot_id=slot.id,
        client_id=client_row.id,
        pt_package_id=pkg.id,
        created_by_user_id=seeded_reception.id,
        status="cancelled",
    )

    r = await authed_client_reception.post(
        "/api/v1/pt-sessions",
        json=_record_body(pkg.id, trainer.id, booking_id=booking.id),
        headers=_csrf_headers(
            authed_client_reception, idempotency_key=uuid4().hex
        ),
    )
    assert r.status_code == 409, r.text
    assert r.json()["code"] == "booking_not_confirmed"


async def test_record_with_already_completed_booking_returns_409(
    authed_client_reception: AsyncClient,
    db_session: AsyncSession,
    seeded_reception: User,
    make_client: Callable[..., Awaitable[Client]],
    make_pt_package_plan: Callable[..., Awaitable[PtPackagePlan]],
    make_pt_package: Callable[..., Awaitable[PtPackage]],
    make_trainer: Callable[..., Awaitable[Trainer]],
) -> None:
    """PKG-04 / T-38-05-02 defensive: booking.status='completed' → 409
    booking_not_confirmed (a completed booking should not accept another
    session — replay-attack defence)."""
    plan = await make_pt_package_plan()
    client_row = await make_client()
    pkg = await make_pt_package(client_id=client_row.id, plan=plan)
    trainer = await make_trainer()
    slot = await _seed_slot(
        db_session,
        trainer_id=trainer.id,
        created_by_user_id=seeded_reception.id,
    )
    booking = await _seed_booking(
        db_session,
        slot_id=slot.id,
        client_id=client_row.id,
        pt_package_id=pkg.id,
        created_by_user_id=seeded_reception.id,
        status="completed",
    )

    r = await authed_client_reception.post(
        "/api/v1/pt-sessions",
        json=_record_body(pkg.id, trainer.id, booking_id=booking.id),
        headers=_csrf_headers(
            authed_client_reception, idempotency_key=uuid4().hex
        ),
    )
    assert r.status_code == 409, r.text
    assert r.json()["code"] == "booking_not_confirmed"


async def test_record_with_pt_package_mismatch_returns_409(
    authed_client_reception: AsyncClient,
    db_session: AsyncSession,
    seeded_reception: User,
    make_client: Callable[..., Awaitable[Client]],
    make_pt_package_plan: Callable[..., Awaitable[PtPackagePlan]],
    make_pt_package: Callable[..., Awaitable[PtPackage]],
    make_trainer: Callable[..., Awaitable[Trainer]],
) -> None:
    """PKG-04 / T-38-05-03: request.pt_package_id != booking.pt_package_id →
    409 booking_mismatch. Server is the arbiter; client cannot spoof.

    The active-per-client partial UNIQUE constraint means only one
    pt_package per client can be active at a time; we work around this by
    seeding two different clients (one per package) — the booking owns the
    second client's package, but the request points at the first client's
    package. The mismatch surfaces server-side as 409."""
    plan = await make_pt_package_plan()
    client_a = await make_client(phone="+79059000001")
    client_b = await make_client(phone="+79059000002")
    pkg_a = await make_pt_package(client_id=client_a.id, plan=plan)
    pkg_b = await make_pt_package(client_id=client_b.id, plan=plan)
    trainer = await make_trainer()
    slot = await _seed_slot(
        db_session,
        trainer_id=trainer.id,
        created_by_user_id=seeded_reception.id,
    )
    # Booking is owned by pkg_b.
    booking = await _seed_booking(
        db_session,
        slot_id=slot.id,
        client_id=client_b.id,
        pt_package_id=pkg_b.id,
        created_by_user_id=seeded_reception.id,
    )

    # Request points at pkg_a → mismatch.
    r = await authed_client_reception.post(
        "/api/v1/pt-sessions",
        json=_record_body(pkg_a.id, trainer.id, booking_id=booking.id),
        headers=_csrf_headers(
            authed_client_reception, idempotency_key=uuid4().hex
        ),
    )
    assert r.status_code == 409, r.text
    assert r.json()["code"] == "booking_mismatch"


async def test_record_with_trainer_mismatch_returns_409(
    authed_client_reception: AsyncClient,
    db_session: AsyncSession,
    seeded_reception: User,
    make_client: Callable[..., Awaitable[Client]],
    make_pt_package_plan: Callable[..., Awaitable[PtPackagePlan]],
    make_pt_package: Callable[..., Awaitable[PtPackage]],
    make_trainer: Callable[..., Awaitable[Trainer]],
) -> None:
    """PKG-04 / T-38-05-03: slot.trainer_id != request.trainer_id → 409
    booking_mismatch (a session cannot be recorded against a trainer who
    is not the one whose slot was booked)."""
    plan = await make_pt_package_plan()
    client_row = await make_client()
    pkg = await make_pt_package(client_id=client_row.id, plan=plan)
    trainer_owning_slot = await make_trainer(full_name="Тренер слота")
    trainer_in_request = await make_trainer(full_name="Тренер запроса")
    slot = await _seed_slot(
        db_session,
        trainer_id=trainer_owning_slot.id,
        created_by_user_id=seeded_reception.id,
    )
    booking = await _seed_booking(
        db_session,
        slot_id=slot.id,
        client_id=client_row.id,
        pt_package_id=pkg.id,
        created_by_user_id=seeded_reception.id,
    )

    r = await authed_client_reception.post(
        "/api/v1/pt-sessions",
        json=_record_body(pkg.id, trainer_in_request.id, booking_id=booking.id),
        headers=_csrf_headers(
            authed_client_reception, idempotency_key=uuid4().hex
        ),
    )
    assert r.status_code == 409, r.text
    assert r.json()["code"] == "booking_mismatch"


# ---------------------------------------------------------------------------
# PKG-06 lock-in test: NO automatic revert on session cancel.
# ---------------------------------------------------------------------------


async def test_cancel_pt_session_does_not_revert_completed_booking(
    authed_client_reception: AsyncClient,
    db_session: AsyncSession,
    seeded_reception: User,
    make_client: Callable[..., Awaitable[Client]],
    make_pt_package_plan: Callable[..., Awaitable[PtPackagePlan]],
    make_pt_package: Callable[..., Awaitable[PtPackage]],
    make_trainer: Callable[..., Awaitable[Trainer]],
) -> None:
    """PKG-06 / D-38-13 / T-38-05-07 LOCK-IN TEST: record pt_session with
    booking_id → booking 'completed' → cancel that pt_session → booking
    REMAINS 'completed'. FSM forward-only (constants.BOOKING_STATUS_TRANSITIONS
    locks `completed → ∅`). No automatic revert."""
    plan = await make_pt_package_plan(session_count=5)
    client_row = await make_client()
    pkg = await make_pt_package(
        client_id=client_row.id, plan=plan, sessions_remaining=5
    )
    trainer = await make_trainer()
    slot = await _seed_slot(
        db_session,
        trainer_id=trainer.id,
        created_by_user_id=seeded_reception.id,
    )
    booking = await _seed_booking(
        db_session,
        slot_id=slot.id,
        client_id=client_row.id,
        pt_package_id=pkg.id,
        created_by_user_id=seeded_reception.id,
    )

    # Step 1: record pt_session → booking transitions to completed.
    r = await authed_client_reception.post(
        "/api/v1/pt-sessions",
        json=_record_body(pkg.id, trainer.id, booking_id=booking.id),
        headers=_csrf_headers(
            authed_client_reception, idempotency_key=uuid4().hex
        ),
    )
    assert r.status_code == 201, r.text
    pt_session_id = UUID(r.json()["data"]["id"])
    await db_session.refresh(booking, attribute_names=["status"])
    assert booking.status == "completed"

    # Step 2: cancel the pt_session.
    cancel = await authed_client_reception.post(
        f"/api/v1/pt-sessions/{pt_session_id}/cancel",
        json={"cancelReason": "Тестовая отмена PKG-06"},
        headers=_csrf_headers(
            authed_client_reception, idempotency_key=uuid4().hex
        ),
    )
    assert cancel.status_code == 200, cancel.text

    # Step 3: PKG-06 LOCK-IN — booking REMAINS 'completed'. No automatic revert.
    await db_session.refresh(booking, attribute_names=["status"])
    assert booking.status == "completed"

    # Audit chain shows the forensic trail (operator can reconstruct what
    # happened) — exactly one booking_created (seeded directly, no audit)
    # but pt_session_recorded + pt_session_cancelled rows for the session.
    recorded_count = await db_session.scalar(
        select(func.count())
        .select_from(AuditLog)
        .where(
            AuditLog.action == "pt_session_recorded",
            AuditLog.resource_id == pt_session_id,
        )
    )
    assert recorded_count == 1
    cancelled_count = await db_session.scalar(
        select(func.count())
        .select_from(AuditLog)
        .where(
            AuditLog.action == "pt_session_cancelled",
            AuditLog.resource_id == pt_session_id,
        )
    )
    assert cancelled_count == 1


# ---------------------------------------------------------------------------
# Defence-in-depth: importlinter modules-independent contract proof.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "module_path",
    [
        "app.modules.pt_sessions.service",
        "app.modules.pt_sessions.repository",
    ],
)
def test_pt_sessions_does_not_import_bookings_or_schedule(module_path: str) -> None:
    """T-38-05-04 mitigation proof: pt_sessions never imports bookings or
    schedule ORM. Cross-module reads go through raw sa.text() (with the
    canonical TABLE_REF noqa marker); cross-module writes go through the
    Phase 37 Protocol slots in app.core.dependencies."""
    import importlib

    mod = importlib.import_module(module_path)
    # Inspect the module's source to assert no `from app.modules.bookings`
    # or `from app.modules.schedule` import line is present.
    import inspect

    source = inspect.getsource(mod)
    forbidden = ["from app.modules.bookings", "from app.modules.schedule"]
    for needle in forbidden:
        assert needle not in source, (
            f"{module_path} contains forbidden import `{needle}` — "
            "use raw sa.text() with TABLE_REF noqa or a Protocol slot instead."
        )


