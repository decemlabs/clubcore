"""Integration tests for freeze_limit_exceeded path (MEM-FRZ-TEST-02).

Pre-seeds closed freeze periods directly via db_session, then attempts a new
freeze. Asserts D-25-07 step 3 preventive guard fires:
    if days_used >= membership.freeze_days_limit_snapshot:
        raise FreezeLimitExceededError(
            "freeze_limit_exceeded",
            fields={"limit": snapshot, "used": days_used},
        )

Boundaries tested:
  - days_used > limit (10 closed days against limit=14 — passes; new freeze succeeds).
  - days_used == limit (exactly 14 days closed; new freeze blocked with 409).
  - days_used > limit (15 days closed; same 409, used reflects DB count).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.memberships.models import MembershipFreezePeriod


def _csrf_headers(client: AsyncClient) -> dict[str, str]:
    return {"X-CSRF-Token": client.cookies.get("sportzal_csrf") or ""}


VALID_CLIENT: dict[str, Any] = {
    "lastName": "Иванов",
    "firstName": "Иван",
    "phone": "+79991234060",
}


async def _create_client(authed: AsyncClient, **overrides: Any) -> dict[str, Any]:
    payload = {**VALID_CLIENT, **overrides}
    r = await authed.post(
        "/api/v1/clients",
        json=payload,
        headers=_csrf_headers(authed),
    )
    assert r.status_code == 201, r.text
    data: dict[str, Any] = r.json()["data"]
    return data


async def _seed_closed_period(
    db_session: AsyncSession,
    *,
    membership_id: UUID,
    actor_id: UUID,
    days: int,
) -> MembershipFreezePeriod:
    """Insert a closed freeze period spanning `days` days into the past."""
    started = datetime.now(tz=UTC) - timedelta(days=days + 5)
    ended = started + timedelta(days=days)
    period = MembershipFreezePeriod(
        membership_id=membership_id,
        started_by=actor_id,
        started_at=started,
        ended_at=ended,
        ended_by=actor_id,
    )
    db_session.add(period)
    await db_session.flush()
    return period


async def test_freeze_limit_exceeded_returns_409(
    authed_client_reception: AsyncClient,
    db_session: AsyncSession,
    seeded_reception: Any,
    make_plan: Any,
    make_membership: Any,
) -> None:
    """MEM-FRZ-TEST-02 boundary: exactly at limit (14 days closed) blocks new freeze.

    D-25-07 step 3: `if days_used >= snapshot_limit: raise`. So 14 == 14 blocks.
    """
    plan = await make_plan(name="Limit Plan At", freeze_days_limit=14)
    client = await _create_client(authed_client_reception, phone="+79991234061")
    client_uuid = UUID(client["id"])
    membership = await make_membership(client_id=client_uuid, plan=plan, status="active")

    # Pre-seed a closed period of EXACTLY 14 days
    await _seed_closed_period(
        db_session,
        membership_id=membership.id,
        actor_id=seeded_reception.id,
        days=14,
    )
    await db_session.commit()

    r = await authed_client_reception.post(
        f"/api/v1/memberships/{membership.id}/freeze",
        headers=_csrf_headers(authed_client_reception),
    )
    assert r.status_code == 409, r.text
    body = r.json()
    assert body["code"] == "freeze_limit_exceeded"
    assert body["fields"]["limit"] == 14
    assert body["fields"]["used"] == 14


async def test_freeze_limit_exceeded_above_limit_returns_409(
    authed_client_reception: AsyncClient,
    db_session: AsyncSession,
    seeded_reception: Any,
    make_plan: Any,
    make_membership: Any,
) -> None:
    """Above-limit (15 days closed) blocks new freeze; used reflects DB sum."""
    plan = await make_plan(name="Limit Plan Over", freeze_days_limit=14)
    client = await _create_client(authed_client_reception, phone="+79991234062")
    client_uuid = UUID(client["id"])
    membership = await make_membership(client_id=client_uuid, plan=plan, status="active")

    await _seed_closed_period(
        db_session,
        membership_id=membership.id,
        actor_id=seeded_reception.id,
        days=15,
    )
    await db_session.commit()

    r = await authed_client_reception.post(
        f"/api/v1/memberships/{membership.id}/freeze",
        headers=_csrf_headers(authed_client_reception),
    )
    assert r.status_code == 409, r.text
    body = r.json()
    assert body["code"] == "freeze_limit_exceeded"
    assert body["fields"]["limit"] == 14
    assert body["fields"]["used"] >= 15


async def test_freeze_limit_below_limit_succeeds(
    authed_client_reception: AsyncClient,
    db_session: AsyncSession,
    seeded_reception: Any,
    make_plan: Any,
    make_membership: Any,
) -> None:
    """Below-limit (10 days closed against limit=14) → freeze succeeds (200)."""
    plan = await make_plan(name="Limit Plan Under", freeze_days_limit=14)
    client = await _create_client(authed_client_reception, phone="+79991234063")
    client_uuid = UUID(client["id"])
    membership = await make_membership(client_id=client_uuid, plan=plan, status="active")

    await _seed_closed_period(
        db_session,
        membership_id=membership.id,
        actor_id=seeded_reception.id,
        days=10,
    )
    await db_session.commit()

    r = await authed_client_reception.post(
        f"/api/v1/memberships/{membership.id}/freeze",
        headers=_csrf_headers(authed_client_reception),
    )
    assert r.status_code == 200, r.text
    body = r.json()["data"]
    assert body["status"] == "frozen"
    # Used reflects the existing 10-day closed period sum (ongoing 0).
    assert body["freezeDaysUsed"] >= 10
    assert body["freezeDaysLimitSnapshot"] == 14
