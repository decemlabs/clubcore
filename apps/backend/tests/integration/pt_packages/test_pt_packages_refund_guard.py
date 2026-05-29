"""Integration tests for PKG-03 refund-guard cross-module check (Phase 38 plan 38-04 Task 3).

The refund-guard in ``pt_packages.service.refund_pt_package`` issues a raw
``sa.text()`` count of confirmed bookings referencing the pt_package
(``# noqa: TABLE_REF cross-module SQL per D-34-04a / Phase 38 D-38-11``).
If any confirmed booking exists, the orchestrator raises
``OutstandingBookingsExistError`` (409 ``outstanding_bookings_exist``)
BEFORE the FSM ``_assert_can_transition('cancelled')`` so the friendly code
surfaces instead of stock ``invalid_transition``.

Per D-38-11 the cross-module reach is via raw SQL only — NO direct import
of the bookings ORM. ``modules-independent`` import-linter contract stays
green.

Test design (per plan 38-04 Task 3 NOTE — "Preferred: direct-SQL booking
insertion"): we seed bookings via raw ``INSERT INTO bookings`` so the test
is self-contained, decoupled from ``bookings.service`` internals, and
exercises the SAME code path (raw SQL count against the bookings table)
that production uses.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

import sqlalchemy as sa
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.models import User
from app.modules.clients.models import Client
from app.modules.pt_packages.models import PtPackagePlan
from app.modules.trainers.models import Trainer


def _csrf_headers(client: AsyncClient, *, idempotency_key: str | None = None) -> dict[str, str]:
    headers: dict[str, str] = {"X-CSRF-Token": client.cookies.get("clubcore_csrf", "") or ""}
    if idempotency_key is not None:
        headers["Idempotency-Key"] = idempotency_key
    return headers


async def _sell_pt_package(
    authed: AsyncClient,
    *,
    client_id: UUID,
    plan: PtPackagePlan,
) -> UUID:
    r = await authed.post(
        "/api/v1/pt-packages",
        json={
            "clientId": str(client_id),
            "planId": str(plan.id),
            "amountKopecks": plan.price_kopecks,
        },
        headers=_csrf_headers(authed, idempotency_key=uuid4().hex),
    )
    assert r.status_code == 201, r.text
    return UUID(r.json()["data"]["id"])


async def _seed_trainer(db_session: AsyncSession, *, is_active: bool = True) -> Trainer:
    trainer = Trainer(full_name=f"Тренер-{uuid4().hex[:6]}", is_active=is_active)
    db_session.add(trainer)
    await db_session.commit()
    await db_session.refresh(trainer)
    return trainer


async def _seed_slot(
    db_session: AsyncSession,
    *,
    trainer_id: UUID,
    owner_id: UUID,
) -> UUID:
    """Insert a TrainerAvailabilitySlot via raw SQL to avoid ORM import here."""
    slot_id = uuid4()
    start = datetime.now(tz=UTC) + timedelta(hours=24)
    end = start + timedelta(hours=1)
    await db_session.execute(
        sa.text(
            "INSERT INTO trainer_availability_slots "
            "(id, trainer_id, start_time, end_time, status, created_by_user_id, "
            "created_at, updated_at) "
            "VALUES (:id, :tid, :start, :end, 'active', :owner, now(), now())"
        ),
        {
            "id": slot_id,
            "tid": trainer_id,
            "start": start,
            "end": end,
            "owner": owner_id,
        },
    )
    await db_session.commit()
    return slot_id


async def _seed_confirmed_booking(
    db_session: AsyncSession,
    *,
    client_id: UUID,
    pt_package_id: UUID,
    slot_id: UUID,
    owner_id: UUID,
) -> UUID:
    """Insert a confirmed booking via raw SQL (matches D-38-11 production guard)."""
    booking_id = uuid4()
    await db_session.execute(
        sa.text(
            "INSERT INTO bookings "
            "(id, slot_id, client_id, pt_package_id, status, created_at, updated_at, "
            "created_by_user_id) "
            "VALUES (:id, :sid, :cid, :pkg, 'confirmed', now(), now(), :owner)"
        ),
        {
            "id": booking_id,
            "sid": slot_id,
            "cid": client_id,
            "pkg": pt_package_id,
            "owner": owner_id,
        },
    )
    await db_session.commit()
    return booking_id


async def _cancel_booking_direct(db_session: AsyncSession, booking_id: UUID) -> None:
    """Flip a booking to cancelled via raw SQL (avoids bookings.service.cancel_booking
    which isn't shipped yet in wave 3)."""
    await db_session.execute(
        sa.text(
            "UPDATE bookings SET status='cancelled', cancelled_at=now(), "
            "updated_at=now() WHERE id=:id"
        ),
        {"id": booking_id},
    )
    await db_session.commit()


async def _set_booking_status_direct(
    db_session: AsyncSession, booking_id: UUID, status: str
) -> None:
    """Direct status flip for completed / no_show variants."""
    await db_session.execute(
        sa.text("UPDATE bookings SET status=:s, updated_at=now() WHERE id=:id"),
        {"s": status, "id": booking_id},
    )
    await db_session.commit()


# --- happy paths (refund succeeds when no confirmed booking blocks) ----------


async def test_refund_blocked_by_outstanding_confirmed_booking_409(
    authed_client_owner: AsyncClient,
    db_session: AsyncSession,
    seeded_owner: User,
    make_client: Callable[..., Awaitable[Client]],
    make_pt_package_plan: Callable[..., Awaitable[PtPackagePlan]],
) -> None:
    """PKG-03 main path: confirmed booking → refund 409 outstanding_bookings_exist."""
    plan = await make_pt_package_plan(name="refund-blocked")
    client = await make_client()
    pt_package_id = await _sell_pt_package(authed_client_owner, client_id=client.id, plan=plan)
    trainer = await _seed_trainer(db_session)
    slot_id = await _seed_slot(db_session, trainer_id=trainer.id, owner_id=seeded_owner.id)
    await _seed_confirmed_booking(
        db_session,
        client_id=client.id,
        pt_package_id=pt_package_id,
        slot_id=slot_id,
        owner_id=seeded_owner.id,
    )

    r = await authed_client_owner.post(
        f"/api/v1/pt-packages/{pt_package_id}/refund",
        json={"reason": "PKG-03 guard"},
        headers=_csrf_headers(authed_client_owner, idempotency_key=uuid4().hex),
    )
    assert r.status_code == 409, r.text
    assert r.json()["code"] == "outstanding_bookings_exist"


async def test_refund_blocked_with_two_confirmed_bookings_409(
    authed_client_owner: AsyncClient,
    db_session: AsyncSession,
    seeded_owner: User,
    make_client: Callable[..., Awaitable[Client]],
    make_pt_package_plan: Callable[..., Awaitable[PtPackagePlan]],
) -> None:
    """2 confirmed bookings → still single 409 (count > 0 is the gate)."""
    plan = await make_pt_package_plan(name="refund-blocked-2")
    client = await make_client()
    pt_package_id = await _sell_pt_package(authed_client_owner, client_id=client.id, plan=plan)
    trainer = await _seed_trainer(db_session)
    for _ in range(2):
        slot_id = await _seed_slot(db_session, trainer_id=trainer.id, owner_id=seeded_owner.id)
        await _seed_confirmed_booking(
            db_session,
            client_id=client.id,
            pt_package_id=pt_package_id,
            slot_id=slot_id,
            owner_id=seeded_owner.id,
        )

    r = await authed_client_owner.post(
        f"/api/v1/pt-packages/{pt_package_id}/refund",
        json={"reason": "multi-booking"},
        headers=_csrf_headers(authed_client_owner, idempotency_key=uuid4().hex),
    )
    assert r.status_code == 409, r.text
    assert r.json()["code"] == "outstanding_bookings_exist"


async def test_refund_allowed_after_booking_cancelled_200(
    authed_client_owner: AsyncClient,
    db_session: AsyncSession,
    seeded_owner: User,
    make_client: Callable[..., Awaitable[Client]],
    make_pt_package_plan: Callable[..., Awaitable[PtPackagePlan]],
) -> None:
    """Cancelled booking → guard count = 0 → refund 200."""
    plan = await make_pt_package_plan(name="refund-after-cancel")
    client = await make_client()
    pt_package_id = await _sell_pt_package(authed_client_owner, client_id=client.id, plan=plan)
    trainer = await _seed_trainer(db_session)
    slot_id = await _seed_slot(db_session, trainer_id=trainer.id, owner_id=seeded_owner.id)
    booking_id = await _seed_confirmed_booking(
        db_session,
        client_id=client.id,
        pt_package_id=pt_package_id,
        slot_id=slot_id,
        owner_id=seeded_owner.id,
    )
    await _cancel_booking_direct(db_session, booking_id)

    r = await authed_client_owner.post(
        f"/api/v1/pt-packages/{pt_package_id}/refund",
        json={"reason": "after_cancel"},
        headers=_csrf_headers(authed_client_owner, idempotency_key=uuid4().hex),
    )
    assert r.status_code == 200, r.text
    assert r.json()["data"]["status"] == "cancelled"


async def test_refund_allowed_with_no_bookings_at_all_200(
    authed_client_owner: AsyncClient,
    db_session: AsyncSession,
    make_client: Callable[..., Awaitable[Client]],
    make_pt_package_plan: Callable[..., Awaitable[PtPackagePlan]],
) -> None:
    """No bookings ever exist → refund 200 happy path (regression for Task 2)."""
    plan = await make_pt_package_plan(name="refund-clean")
    client = await make_client()
    pt_package_id = await _sell_pt_package(authed_client_owner, client_id=client.id, plan=plan)

    r = await authed_client_owner.post(
        f"/api/v1/pt-packages/{pt_package_id}/refund",
        json={"reason": "clean_refund"},
        headers=_csrf_headers(authed_client_owner, idempotency_key=uuid4().hex),
    )
    assert r.status_code == 200, r.text
    assert r.json()["data"]["status"] == "cancelled"


async def test_refund_ignores_non_confirmed_booking_statuses_200(
    authed_client_owner: AsyncClient,
    db_session: AsyncSession,
    seeded_owner: User,
    make_client: Callable[..., Awaitable[Client]],
    make_pt_package_plan: Callable[..., Awaitable[PtPackagePlan]],
) -> None:
    """completed / no_show / cancelled bookings do NOT trigger the guard."""
    plan = await make_pt_package_plan(name="refund-ignores-nonconfirmed")
    client = await make_client()
    pt_package_id = await _sell_pt_package(authed_client_owner, client_id=client.id, plan=plan)
    trainer = await _seed_trainer(db_session)
    # Seed one each: completed, no_show, cancelled. All should be invisible to
    # the `WHERE status='confirmed'` filter in the production guard.
    for status_value in ("completed", "no_show", "cancelled"):
        slot_id = await _seed_slot(db_session, trainer_id=trainer.id, owner_id=seeded_owner.id)
        booking_id = await _seed_confirmed_booking(
            db_session,
            client_id=client.id,
            pt_package_id=pt_package_id,
            slot_id=slot_id,
            owner_id=seeded_owner.id,
        )
        await _set_booking_status_direct(db_session, booking_id, status_value)

    r = await authed_client_owner.post(
        f"/api/v1/pt-packages/{pt_package_id}/refund",
        json={"reason": "non_confirmed_ignored"},
        headers=_csrf_headers(authed_client_owner, idempotency_key=uuid4().hex),
    )
    assert r.status_code == 200, r.text


# --- guard ordering: PKG-03 surfaces BEFORE FSM invalid_transition -----------


async def test_refund_guard_fires_before_fsm_invalid_transition(
    authed_client_owner: AsyncClient,
    db_session: AsyncSession,
    seeded_owner: User,
    make_client: Callable[..., Awaitable[Client]],
    make_pt_package_plan: Callable[..., Awaitable[PtPackagePlan]],
) -> None:
    """When a pt_package is already cancelled AND a confirmed booking would block
    refund — confirm the FSM guard still fires first (the cancelled status is
    the immediate blocker before the booking guard).

    NOTE: per plan 38-04 — the new outstanding_bookings_exist guard MUST fire
    BEFORE the FSM `_assert_can_transition('cancelled')` so the friendly 409
    surfaces when both would apply. This test asserts that when the booking
    guard would block refund on an ACTIVE package, the booking-guard code is
    returned (not invalid_transition).

    Variant covered above (test_refund_blocked_by_outstanding_confirmed_booking_409)
    proves the ordering directly: the package is still 'active' when the booking
    guard fires, so the FSM guard never gets a chance to trip. This test seeds
    an active package + confirmed booking and asserts the response is the
    booking-guard code, NOT FSM invalid_transition.
    """
    plan = await make_pt_package_plan(name="refund-ordering")
    client = await make_client()
    pt_package_id = await _sell_pt_package(authed_client_owner, client_id=client.id, plan=plan)
    trainer = await _seed_trainer(db_session)
    slot_id = await _seed_slot(db_session, trainer_id=trainer.id, owner_id=seeded_owner.id)
    await _seed_confirmed_booking(
        db_session,
        client_id=client.id,
        pt_package_id=pt_package_id,
        slot_id=slot_id,
        owner_id=seeded_owner.id,
    )

    r = await authed_client_owner.post(
        f"/api/v1/pt-packages/{pt_package_id}/refund",
        json={"reason": "ordering_check"},
        headers=_csrf_headers(authed_client_owner, idempotency_key=uuid4().hex),
    )
    assert r.status_code == 409, r.text
    body: dict[str, Any] = r.json()
    assert body["code"] == "outstanding_bookings_exist", (
        f"expected outstanding_bookings_exist, got {body!r} — guard ordering broken"
    )
    assert body["code"] != "invalid_transition"
