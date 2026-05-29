"""Phase 66 Plan 66-05 — IDM-03 integration tests for bookings category-A endpoints.

Asserts the hardened idempotency behavior (real Postgres + real Redis) for:
  - POST /api/v1/bookings             (create_booking, A)
  - POST /api/v1/bookings/{id}/cancel (cancel_booking, A)

Assertions per endpoint:
  1. Replay (same key + same body) returns byte-identical cached response.
  2. Replay does NOT re-emit AuditLog rows for the booking id.
  3. Same key + different body → 422 idempotency_key_reuse.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit_models import AuditLog
from app.modules.clients.models import Client
from app.modules.pt_packages.models import PtPackage, PtPackagePlan
from app.modules.schedule.models import TrainerAvailabilitySlot
from app.modules.trainers.models import Trainer

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _csrf_header(client: AsyncClient) -> str:
    return client.cookies.get("sportzal_csrf") or ""


def _headers(client: AsyncClient, *, key: str) -> dict[str, str]:
    return {
        "X-CSRF-Token": _csrf_header(client),
        "Idempotency-Key": key,
    }


async def _audit_count(session: AsyncSession, resource_id: UUID) -> int:
    """Count AuditLog rows for a given resource_id."""
    result = await session.execute(
        select(func.count()).select_from(AuditLog).where(AuditLog.resource_id == resource_id)
    )
    return int(result.scalar_one())


async def _seed_booking_prerequisites(
    *,
    make_trainer: Callable[..., Awaitable[Trainer]],
    make_client: Callable[..., Awaitable[Client]],
    make_pt_package_plan: Callable[..., Awaitable[PtPackagePlan]],
    make_pt_package: Callable[..., Awaitable[PtPackage]],
    make_slot: Callable[..., Awaitable[TrainerAvailabilitySlot]],
) -> tuple[UUID, UUID, UUID, UUID]:
    """Seed trainer, client, pt_package, slot.

    Returns (slot_id, client_id, pt_package_id, trainer_id).
    """
    trainer = await make_trainer()
    client_row = await make_client()
    plan = await make_pt_package_plan()
    pkg = await make_pt_package(
        client_id=client_row.id,
        plan=plan,
        sessions_remaining=5,
    )
    start = datetime.now(tz=UTC) + timedelta(hours=48)
    slot = await make_slot(
        trainer_id=trainer.id,
        start_time=start,
        end_time=start + timedelta(hours=1),
    )
    return slot.id, client_row.id, pkg.id, trainer.id


# ===========================================================================
# create_booking — double-submit + no-re-emit-audit + reuse-422
# ===========================================================================


async def test_create_booking_double_submit_byte_identical(
    authed_client_owner: AsyncClient,
    db_session: AsyncSession,
    make_trainer: Callable[..., Awaitable[Trainer]],
    make_client: Callable[..., Awaitable[Client]],
    make_pt_package_plan: Callable[..., Awaitable[PtPackagePlan]],
    make_pt_package: Callable[..., Awaitable[PtPackage]],
    make_slot: Callable[..., Awaitable[TrainerAvailabilitySlot]],
) -> None:
    """Replay of create_booking returns byte-identical cached response."""
    slot_id, client_id, pkg_id, _ = await _seed_booking_prerequisites(
        make_trainer=make_trainer,
        make_client=make_client,
        make_pt_package_plan=make_pt_package_plan,
        make_pt_package=make_pt_package,
        make_slot=make_slot,
    )
    key = uuid4().hex  # 32 chars, passes {16,128}

    body_json = {
        "slotId": str(slot_id),
        "clientId": str(client_id),
        "ptPackageId": str(pkg_id),
    }
    headers = _headers(authed_client_owner, key=key)

    r1 = await authed_client_owner.post("/api/v1/bookings", json=body_json, headers=headers)
    assert r1.status_code == 201, r1.text

    r2 = await authed_client_owner.post("/api/v1/bookings", json=body_json, headers=headers)
    assert r2.status_code == 201, r2.text
    assert r2.content == r1.content, "Replay must return byte-identical content"


async def test_create_booking_replay_no_re_emit_audit(
    authed_client_owner: AsyncClient,
    db_session: AsyncSession,
    make_trainer: Callable[..., Awaitable[Trainer]],
    make_client: Callable[..., Awaitable[Client]],
    make_pt_package_plan: Callable[..., Awaitable[PtPackagePlan]],
    make_pt_package: Callable[..., Awaitable[PtPackage]],
    make_slot: Callable[..., Awaitable[TrainerAvailabilitySlot]],
) -> None:
    """Replay of create_booking does NOT re-emit AuditLog row."""
    slot_id, client_id, pkg_id, _ = await _seed_booking_prerequisites(
        make_trainer=make_trainer,
        make_client=make_client,
        make_pt_package_plan=make_pt_package_plan,
        make_pt_package=make_pt_package,
        make_slot=make_slot,
    )
    key = uuid4().hex

    body_json = {
        "slotId": str(slot_id),
        "clientId": str(client_id),
        "ptPackageId": str(pkg_id),
    }
    headers = _headers(authed_client_owner, key=key)

    r1 = await authed_client_owner.post("/api/v1/bookings", json=body_json, headers=headers)
    assert r1.status_code == 201, r1.text
    booking_id = UUID(r1.json()["data"]["id"])

    count_before = await _audit_count(db_session, booking_id)
    assert count_before >= 1, "At least one audit row expected after first submit"

    r2 = await authed_client_owner.post("/api/v1/bookings", json=body_json, headers=headers)
    assert r2.status_code == 201, r2.text

    count_after = await _audit_count(db_session, booking_id)
    assert count_after == count_before, (
        f"Replay must NOT re-emit audit: before={count_before}, after={count_after}"
    )


async def test_create_booking_same_key_different_body_422(
    authed_client_owner: AsyncClient,
    db_session: AsyncSession,
    make_trainer: Callable[..., Awaitable[Trainer]],
    make_client: Callable[..., Awaitable[Client]],
    make_pt_package_plan: Callable[..., Awaitable[PtPackagePlan]],
    make_pt_package: Callable[..., Awaitable[PtPackage]],
    make_slot: Callable[..., Awaitable[TrainerAvailabilitySlot]],
) -> None:
    """Same key + different body (different client) → 422 idempotency_key_reuse."""
    # Seed two independent slot/client/pkg sets
    slot_id_a, client_id_a, pkg_id_a, _ = await _seed_booking_prerequisites(
        make_trainer=make_trainer,
        make_client=make_client,
        make_pt_package_plan=make_pt_package_plan,
        make_pt_package=make_pt_package,
        make_slot=make_slot,
    )
    slot_id_b, client_id_b, pkg_id_b, _ = await _seed_booking_prerequisites(
        make_trainer=make_trainer,
        make_client=make_client,
        make_pt_package_plan=make_pt_package_plan,
        make_pt_package=make_pt_package,
        make_slot=make_slot,
    )
    key = uuid4().hex

    headers = _headers(authed_client_owner, key=key)

    r1 = await authed_client_owner.post(
        "/api/v1/bookings",
        json={
            "slotId": str(slot_id_a),
            "clientId": str(client_id_a),
            "ptPackageId": str(pkg_id_a),
        },
        headers=headers,
    )
    assert r1.status_code == 201, r1.text

    r2 = await authed_client_owner.post(
        "/api/v1/bookings",
        json={
            "slotId": str(slot_id_b),
            "clientId": str(client_id_b),
            "ptPackageId": str(pkg_id_b),
        },
        headers=headers,
    )
    assert r2.status_code == 422, r2.text
    body = r2.json()
    assert body["code"] == "validation_error"
    assert body["message"] == "idempotency_key_reuse"


# ===========================================================================
# cancel_booking — double-submit + no-re-emit-audit + reuse-422
# ===========================================================================


async def _seed_confirmed_booking(
    authed: AsyncClient,
    *,
    make_trainer: Callable[..., Awaitable[Trainer]],
    make_client: Callable[..., Awaitable[Client]],
    make_pt_package_plan: Callable[..., Awaitable[PtPackagePlan]],
    make_pt_package: Callable[..., Awaitable[PtPackage]],
    make_slot: Callable[..., Awaitable[TrainerAvailabilitySlot]],
) -> UUID:
    """Create a confirmed booking via HTTP; return booking_id."""
    slot_id, client_id, pkg_id, _ = await _seed_booking_prerequisites(
        make_trainer=make_trainer,
        make_client=make_client,
        make_pt_package_plan=make_pt_package_plan,
        make_pt_package=make_pt_package,
        make_slot=make_slot,
    )
    r = await authed.post(
        "/api/v1/bookings",
        json={
            "slotId": str(slot_id),
            "clientId": str(client_id),
            "ptPackageId": str(pkg_id),
        },
        headers=_headers(authed, key=uuid4().hex),
    )
    assert r.status_code == 201, r.text
    return UUID(r.json()["data"]["id"])


async def test_cancel_booking_double_submit_byte_identical(
    authed_client_owner: AsyncClient,
    db_session: AsyncSession,
    make_trainer: Callable[..., Awaitable[Trainer]],
    make_client: Callable[..., Awaitable[Client]],
    make_pt_package_plan: Callable[..., Awaitable[PtPackagePlan]],
    make_pt_package: Callable[..., Awaitable[PtPackage]],
    make_slot: Callable[..., Awaitable[TrainerAvailabilitySlot]],
) -> None:
    """Replay of cancel_booking returns byte-identical cached response."""
    booking_id = await _seed_confirmed_booking(
        authed_client_owner,
        make_trainer=make_trainer,
        make_client=make_client,
        make_pt_package_plan=make_pt_package_plan,
        make_pt_package=make_pt_package,
        make_slot=make_slot,
    )
    key = uuid4().hex
    body_json = {"reason": "owner_cancel_idem_test"}
    headers = _headers(authed_client_owner, key=key)

    r1 = await authed_client_owner.post(
        f"/api/v1/bookings/{booking_id}/cancel",
        json=body_json,
        headers=headers,
    )
    assert r1.status_code == 200, r1.text

    r2 = await authed_client_owner.post(
        f"/api/v1/bookings/{booking_id}/cancel",
        json=body_json,
        headers=headers,
    )
    assert r2.status_code == 200, r2.text
    assert r2.content == r1.content, "Replay must return byte-identical content"


async def test_cancel_booking_replay_no_re_emit_audit(
    authed_client_owner: AsyncClient,
    db_session: AsyncSession,
    make_trainer: Callable[..., Awaitable[Trainer]],
    make_client: Callable[..., Awaitable[Client]],
    make_pt_package_plan: Callable[..., Awaitable[PtPackagePlan]],
    make_pt_package: Callable[..., Awaitable[PtPackage]],
    make_slot: Callable[..., Awaitable[TrainerAvailabilitySlot]],
) -> None:
    """Replay of cancel_booking does NOT re-emit AuditLog row."""
    booking_id = await _seed_confirmed_booking(
        authed_client_owner,
        make_trainer=make_trainer,
        make_client=make_client,
        make_pt_package_plan=make_pt_package_plan,
        make_pt_package=make_pt_package,
        make_slot=make_slot,
    )
    key = uuid4().hex
    body_json = {"reason": "audit_count_check_cancel"}
    headers = _headers(authed_client_owner, key=key)

    r1 = await authed_client_owner.post(
        f"/api/v1/bookings/{booking_id}/cancel",
        json=body_json,
        headers=headers,
    )
    assert r1.status_code == 200, r1.text

    count_before = await _audit_count(db_session, booking_id)
    assert count_before >= 1

    r2 = await authed_client_owner.post(
        f"/api/v1/bookings/{booking_id}/cancel",
        json=body_json,
        headers=headers,
    )
    assert r2.status_code == 200, r2.text

    count_after = await _audit_count(db_session, booking_id)
    assert count_after == count_before, (
        f"Replay must NOT re-emit audit: before={count_before}, after={count_after}"
    )


async def test_cancel_booking_same_key_different_body_422(
    authed_client_owner: AsyncClient,
    db_session: AsyncSession,
    make_trainer: Callable[..., Awaitable[Trainer]],
    make_client: Callable[..., Awaitable[Client]],
    make_pt_package_plan: Callable[..., Awaitable[PtPackagePlan]],
    make_pt_package: Callable[..., Awaitable[PtPackage]],
    make_slot: Callable[..., Awaitable[TrainerAvailabilitySlot]],
) -> None:
    """Same key + different cancel body → 422 idempotency_key_reuse."""
    booking_id = await _seed_confirmed_booking(
        authed_client_owner,
        make_trainer=make_trainer,
        make_client=make_client,
        make_pt_package_plan=make_pt_package_plan,
        make_pt_package=make_pt_package,
        make_slot=make_slot,
    )
    key = uuid4().hex
    headers = _headers(authed_client_owner, key=key)

    r1 = await authed_client_owner.post(
        f"/api/v1/bookings/{booking_id}/cancel",
        json={"reason": "cancel_reason_a"},
        headers=headers,
    )
    assert r1.status_code == 200, r1.text

    r2 = await authed_client_owner.post(
        f"/api/v1/bookings/{booking_id}/cancel",
        json={"reason": "cancel_reason_b"},  # different body
        headers=headers,
    )
    assert r2.status_code == 422, r2.text
    body = r2.json()
    assert body["code"] == "validation_error"
    assert body["message"] == "idempotency_key_reuse"
