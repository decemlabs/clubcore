"""Integration tests for GET /api/v1/memberships list (MEM-EP-01, D-09, D-10).

Covers default-returns-all-statuses, status filter, clientId filter, sort axes,
pagination boundaries, and the D-10 snapshot fields exposed in the response.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

from httpx import AsyncClient


def _csrf_headers(client: AsyncClient) -> dict[str, str]:
    # Phase 32 PAY-09: POST /api/v1/memberships now requires Idempotency-Key.
    return {
        "X-CSRF-Token": client.cookies.get("sportzal_csrf") or "",
        "Idempotency-Key": uuid4().hex,
    }


VALID_CLIENT: dict[str, Any] = {
    "lastName": "Иванов",
    "firstName": "Иван",
    "phone": "+79991234567",
}


async def _create_client(
    authed_client_owner: AsyncClient,
    **overrides: Any,
) -> dict[str, Any]:
    payload: dict[str, Any] = {**VALID_CLIENT, **overrides}
    r = await authed_client_owner.post(
        "/api/v1/clients",
        json=payload,
        headers=_csrf_headers(authed_client_owner),
    )
    assert r.status_code == 201, r.text
    data: dict[str, Any] = r.json()["data"]
    return data


# --- Default + envelope ------------------------------------------------------


async def test_list_default_returns_all_statuses(
    authed_client_owner: AsyncClient,
    make_plan: Any,
    make_membership: Any,
) -> None:
    """D-09: default GET (no filters) returns all statuses (active + expired + cancelled)."""
    plan = await make_plan(name="List All Plan")
    client = await _create_client(authed_client_owner, phone="+79990001001")
    client_uuid = UUID(client["id"])

    await make_membership(client_id=client_uuid, plan=plan, status="active")
    await make_membership(client_id=client_uuid, plan=plan, status="expired")
    await make_membership(client_id=client_uuid, plan=plan, status="cancelled")

    r = await authed_client_owner.get(
        "/api/v1/memberships",
        params={"clientId": str(client_uuid)},
    )
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    # Envelope shape (D-09 + v1.1 contract)
    assert isinstance(data["items"], list)
    assert "total" in data
    assert "page" in data
    assert "pageSize" in data
    assert data["total"] == 3
    statuses = {item["status"] for item in data["items"]}
    assert statuses == {"active", "expired", "cancelled"}


async def test_list_filter_status_active(
    authed_client_owner: AsyncClient,
    make_plan: Any,
    make_membership: Any,
) -> None:
    """?status=active filters to only active rows."""
    plan = await make_plan(name="Filter Active")
    client = await _create_client(authed_client_owner, phone="+79990001002")
    client_uuid = UUID(client["id"])

    await make_membership(client_id=client_uuid, plan=plan, status="active")
    await make_membership(client_id=client_uuid, plan=plan, status="cancelled")

    r = await authed_client_owner.get(
        "/api/v1/memberships",
        params={"clientId": str(client_uuid), "status": "active"},
    )
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert data["total"] == 1
    assert data["items"][0]["status"] == "active"


async def test_list_filter_status_cancelled(
    authed_client_owner: AsyncClient,
    make_plan: Any,
    make_membership: Any,
) -> None:
    """?status=cancelled filters to only cancelled rows."""
    plan = await make_plan(name="Filter Cancelled")
    client = await _create_client(authed_client_owner, phone="+79990001003")
    client_uuid = UUID(client["id"])

    await make_membership(client_id=client_uuid, plan=plan, status="active")
    await make_membership(client_id=client_uuid, plan=plan, status="cancelled")
    await make_membership(client_id=client_uuid, plan=plan, status="cancelled")

    r = await authed_client_owner.get(
        "/api/v1/memberships",
        params={"clientId": str(client_uuid), "status": "cancelled"},
    )
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert data["total"] == 2
    for item in data["items"]:
        assert item["status"] == "cancelled"


async def test_list_filter_client_id(
    authed_client_owner: AsyncClient,
    make_plan: Any,
    make_membership: Any,
) -> None:
    """?clientId=<uuid> returns only that client's rows."""
    plan = await make_plan(name="Filter Client")
    c1 = await _create_client(authed_client_owner, phone="+79990001004")
    c2 = await _create_client(authed_client_owner, phone="+79990001005")
    c1_uuid = UUID(c1["id"])
    c2_uuid = UUID(c2["id"])

    await make_membership(client_id=c1_uuid, plan=plan)
    await make_membership(client_id=c1_uuid, plan=plan)
    await make_membership(client_id=c2_uuid, plan=plan)

    r = await authed_client_owner.get(
        "/api/v1/memberships",
        params={"clientId": str(c1_uuid)},
    )
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert data["total"] == 2
    for item in data["items"]:
        assert item["clientId"] == str(c1_uuid)


# --- Sort axes (D-09) -------------------------------------------------------


async def test_list_sort_end_date_desc(
    authed_client_owner: AsyncClient,
    make_plan: Any,
    make_membership: Any,
) -> None:
    """?sort=end_date_desc orders by end_date DESC."""
    plan = await make_plan(name="Sort End")
    client = await _create_client(authed_client_owner, phone="+79990001006")
    client_uuid = UUID(client["id"])

    today = datetime.now(tz=UTC).date()
    await make_membership(
        client_id=client_uuid,
        plan=plan,
        start_date=today,
        end_date=today + timedelta(days=29),
    )
    await make_membership(
        client_id=client_uuid,
        plan=plan,
        start_date=today,
        end_date=today + timedelta(days=89),
    )
    await make_membership(
        client_id=client_uuid,
        plan=plan,
        start_date=today,
        end_date=today + timedelta(days=179),
    )

    r = await authed_client_owner.get(
        "/api/v1/memberships",
        params={"clientId": str(client_uuid), "sort": "end_date_desc"},
    )
    assert r.status_code == 200, r.text
    items = r.json()["data"]["items"]
    assert len(items) == 3
    end_dates = [item["endDate"] for item in items]
    # Descending order
    assert end_dates == sorted(end_dates, reverse=True)


async def test_list_sort_start_date_desc(
    authed_client_owner: AsyncClient,
    make_plan: Any,
    make_membership: Any,
) -> None:
    """?sort=start_date_desc orders by start_date DESC."""
    plan = await make_plan(name="Sort Start")
    client = await _create_client(authed_client_owner, phone="+79990001007")
    client_uuid = UUID(client["id"])

    today = datetime.now(tz=UTC).date()
    await make_membership(
        client_id=client_uuid,
        plan=plan,
        start_date=today - timedelta(days=10),
    )
    await make_membership(
        client_id=client_uuid,
        plan=plan,
        start_date=today,
    )
    await make_membership(
        client_id=client_uuid,
        plan=plan,
        start_date=today - timedelta(days=5),
    )

    r = await authed_client_owner.get(
        "/api/v1/memberships",
        params={"clientId": str(client_uuid), "sort": "start_date_desc"},
    )
    assert r.status_code == 200, r.text
    items = r.json()["data"]["items"]
    assert len(items) == 3
    start_dates = [item["startDate"] for item in items]
    assert start_dates == sorted(start_dates, reverse=True)


async def test_list_sort_default_created_at_desc(
    authed_client_owner: AsyncClient,
    make_plan: Any,
    make_membership: Any,
) -> None:
    """No sort param -> default created_at DESC, id DESC tiebreak (Phase 16 pattern)."""
    plan = await make_plan(name="Sort Default")
    client = await _create_client(authed_client_owner, phone="+79990001008")
    client_uuid = UUID(client["id"])

    a = await make_membership(client_id=client_uuid, plan=plan)
    b = await make_membership(client_id=client_uuid, plan=plan)
    c = await make_membership(client_id=client_uuid, plan=plan)

    r = await authed_client_owner.get(
        "/api/v1/memberships",
        params={"clientId": str(client_uuid)},
    )
    assert r.status_code == 200, r.text
    items = r.json()["data"]["items"]
    assert len(items) == 3
    # Within a single SAVEPOINT tx, func.now() is constant so created_at is
    # equal across rows. The id DESC tiebreak then determines order.
    ids = [item["id"] for item in items]
    expected = sorted([str(a.id), str(b.id), str(c.id)], reverse=True)
    assert ids == expected


# --- Pagination ------------------------------------------------------------


async def test_list_pagination(
    authed_client_owner: AsyncClient,
    make_plan: Any,
    make_membership: Any,
) -> None:
    """page=2&pageSize=20 with 21 rows -> 1 item, total=21, page=2, pageSize=20."""
    plan = await make_plan(name="Pagination")
    client = await _create_client(authed_client_owner, phone="+79990001009")
    client_uuid = UUID(client["id"])

    # Seed 21 rows. Use sequential awaits — async fixture ensures DB ordering.
    for _ in range(21):
        await make_membership(client_id=client_uuid, plan=plan)

    r = await authed_client_owner.get(
        "/api/v1/memberships",
        params={"clientId": str(client_uuid), "page": 2, "pageSize": 20},
    )
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert data["total"] == 21
    assert data["page"] == 2
    assert data["pageSize"] == 20
    assert len(data["items"]) == 1


async def test_list_pagination_max_page_size(
    authed_client_owner: AsyncClient,
) -> None:
    """pageSize=101 -> 422 (PageQuery max=100, locked v1.1)."""
    r = await authed_client_owner.get(
        "/api/v1/memberships",
        params={"pageSize": 101},
    )
    assert r.status_code == 422, r.text


# --- D-10 snapshot fields exposed in response ------------------------------


async def test_list_response_includes_all_snapshot_fields(
    authed_client_owner: AsyncClient,
    make_plan: Any,
    make_membership: Any,
) -> None:
    """D-10: response includes ALL snapshot fields and lifecycle timestamps."""
    plan = await make_plan(name="Snapshot Fields", duration_days=60, price_kopecks=420000)
    client = await _create_client(authed_client_owner, phone="+79990001010")
    client_uuid = UUID(client["id"])

    await make_membership(client_id=client_uuid, plan=plan)

    r = await authed_client_owner.get(
        "/api/v1/memberships",
        params={"clientId": str(client_uuid)},
    )
    assert r.status_code == 200, r.text
    items = r.json()["data"]["items"]
    assert len(items) == 1
    item = items[0]

    # D-10: all snapshot fields exposed in camelCase
    assert "planNameSnapshot" in item
    assert "durationDaysSnapshot" in item
    assert "priceKopecksSnapshot" in item
    assert item["planNameSnapshot"] == "Snapshot Fields"
    assert item["durationDaysSnapshot"] == 60
    assert item["priceKopecksSnapshot"] == 420000

    # All lifecycle + audit fields
    for key in (
        "id",
        "clientId",
        "planId",
        "startDate",
        "endDate",
        "status",
        "cancelledAt",
        "cancelReason",
        "paidAt",
        "notes",
        "createdAt",
        "updatedAt",
    ):
        assert key in item, f"missing {key} in response item"
