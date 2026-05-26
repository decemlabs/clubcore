"""Integration tests for GET /api/v1/visits and GET /api/v1/visits/{id} (VIS-EP-01..02).

Covers:
- Paginated envelope shape {items, total, page, pageSize}
- Filter by clientId
- Filter by from/to (inclusive date bounds — CD-08)
- Default sort checked_in_at DESC (D-09)
- 404 visit_not_found for unknown id
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any
from uuid import uuid4
from zoneinfo import ZoneInfo

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.visits.models import Visit

_MSK = ZoneInfo("Europe/Moscow")


def _csrf(client: AsyncClient) -> dict[str, str]:
    return {"X-CSRF-Token": client.cookies.get("sportzal_csrf") or ""}


async def test_list_visits_no_filter_returns_paginated(
    authed_client_reception: AsyncClient,
    seeded_reception: Any,
) -> None:
    """VIS-EP-01: GET /api/v1/visits returns paginated envelope {items, total, page, pageSize}."""
    r = await authed_client_reception.get("/api/v1/visits")
    assert r.status_code == 200, r.text
    body = r.json()
    assert "data" in body
    data = body["data"]
    assert "items" in data
    assert "total" in data
    assert "page" in data
    assert "pageSize" in data
    assert isinstance(data["items"], list)
    assert isinstance(data["total"], int)


async def test_list_visits_filter_by_client_id(
    authed_client_owner: AsyncClient,
    db_session: AsyncSession,
    seeded_owner: Any,
    make_visit_setup: Any,
) -> None:
    """GET ?clientId=... returns only that client's visits."""
    client_a, membership_a = await make_visit_setup()
    client_b, membership_b = await make_visit_setup()

    now_msk = datetime.now(_MSK)
    # yesterday for client_b so we don't collide with today's gym_date for client_a
    yesterday = now_msk - timedelta(days=1)

    visit_a = Visit(
        client_id=client_a.id,
        membership_id=membership_a.id,
        channel="reception",
        checked_in_at=now_msk,
        checked_in_by=seeded_owner.id,
    )
    visit_b = Visit(
        client_id=client_b.id,
        membership_id=membership_b.id,
        channel="reception",
        checked_in_at=yesterday,
        checked_in_by=seeded_owner.id,
    )
    db_session.add_all([visit_a, visit_b])
    await db_session.commit()

    r = await authed_client_owner.get(
        "/api/v1/visits",
        params={"clientId": str(client_a.id)},
    )
    assert r.status_code == 200, r.text
    items = r.json()["data"]["items"]
    assert len(items) >= 1
    assert all(item["clientId"] == str(client_a.id) for item in items)


async def test_list_visits_from_to_inclusive(
    authed_client_owner: AsyncClient,
    db_session: AsyncSession,
    seeded_owner: Any,
    make_visit_setup: Any,
) -> None:
    """CD-08: from <= gym_date <= to (inclusive on both bounds)."""
    client_obj, membership = await make_visit_setup()

    # Insert a visit with checked_in_at at noon MSK today (gym_date = today_msk)
    now_msk = datetime.now(_MSK)
    today_msk = now_msk.date()
    noon_today = now_msk.replace(hour=12, minute=0, second=0, microsecond=0)

    visit = Visit(
        client_id=client_obj.id,
        membership_id=membership.id,
        channel="reception",
        checked_in_at=noon_today,
        checked_in_by=seeded_owner.id,
    )
    db_session.add(visit)
    await db_session.commit()

    # Filter with from=today, to=today — must include our visit
    r = await authed_client_owner.get(
        "/api/v1/visits",
        params={
            "clientId": str(client_obj.id),
            "from": today_msk.isoformat(),
            "to": today_msk.isoformat(),
        },
    )
    assert r.status_code == 200, r.text
    items = r.json()["data"]["items"]
    assert len(items) >= 1
    assert all(today_msk.isoformat() <= item["gymDate"] <= today_msk.isoformat() for item in items)


async def test_list_visits_default_sort_checked_in_at_desc(
    authed_client_owner: AsyncClient,
    db_session: AsyncSession,
    seeded_owner: Any,
    make_visit_setup: Any,
) -> None:
    """D-09: default sort is checked_in_at DESC — most recent visit first."""
    client_obj, membership = await make_visit_setup()

    now_msk = datetime.now(_MSK)
    # Two visits on different days so gym_date differs (avoids UNIQUE violation)
    earlier = now_msk - timedelta(days=2)
    later = now_msk - timedelta(days=1)

    visit_early = Visit(
        client_id=client_obj.id,
        membership_id=membership.id,
        channel="reception",
        checked_in_at=earlier,
        checked_in_by=seeded_owner.id,
    )
    visit_late = Visit(
        client_id=client_obj.id,
        membership_id=membership.id,
        channel="reception",
        checked_in_at=later,
        checked_in_by=seeded_owner.id,
    )
    db_session.add_all([visit_early, visit_late])
    await db_session.commit()

    r = await authed_client_owner.get(
        "/api/v1/visits",
        params={"clientId": str(client_obj.id)},
    )
    assert r.status_code == 200, r.text
    items = r.json()["data"]["items"]
    assert len(items) >= 2

    # Verify descending order by checked_in_at
    timestamps = [item["checkedInAt"] for item in items]
    assert timestamps == sorted(timestamps, reverse=True), f"Expected DESC order, got: {timestamps}"


async def test_get_visit_404_visit_not_found(
    authed_client_owner: AsyncClient,
    seeded_owner: Any,
) -> None:
    """VIS-EP-02: GET /api/v1/visits/{random_uuid} → 404 visit_not_found."""
    r = await authed_client_owner.get(f"/api/v1/visits/{uuid4()}")
    assert r.status_code == 404, r.text
    assert r.json()["code"] == "visit_not_found"


async def test_get_visit_200_returns_visit(
    authed_client_owner: AsyncClient,
    db_session: AsyncSession,
    seeded_owner: Any,
    make_visit_setup: Any,
) -> None:
    """VIS-EP-02: GET /api/v1/visits/{id} returns the visit row."""
    client_obj, membership = await make_visit_setup()

    now_msk = datetime.now(_MSK)
    visit = Visit(
        client_id=client_obj.id,
        membership_id=membership.id,
        channel="reception",
        checked_in_at=now_msk,
        checked_in_by=seeded_owner.id,
    )
    db_session.add(visit)
    await db_session.commit()
    await db_session.refresh(visit)

    r = await authed_client_owner.get(f"/api/v1/visits/{visit.id}")
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert data["id"] == str(visit.id)
    assert data["clientId"] == str(client_obj.id)
    assert data["channel"] == "reception"
