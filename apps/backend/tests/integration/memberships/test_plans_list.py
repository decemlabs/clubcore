"""Integration tests for GET /api/v1/membership-plans list (MEM-PLAN-EP-01).

Covers active filter / sort / pagination semantics from the PLAN, end-to-end
via httpx ASGITransport. All tests use the `authed_client_owner` fixture —
the entire MEMBERSHIP_PLANS resource is owner-only (Phase 15 OWNER_ONLY).
"""

from __future__ import annotations

from typing import Any

from httpx import AsyncClient


def _csrf_headers(client: AsyncClient) -> dict[str, str]:
    """Return X-CSRF-Token header echoing the sportzal_csrf cookie value."""
    return {"X-CSRF-Token": client.cookies.get("sportzal_csrf", "")}


VALID_PLAN: dict[str, Any] = {
    "name": "Базовый",
    "durationDays": 30,
    "priceKopecks": 250000,
    "active": True,
}


async def _create(
    authed_client_owner: AsyncClient,
    **overrides: Any,
) -> dict[str, Any]:
    """POST a plan and return its response data (asserts 201)."""
    payload: dict[str, Any] = {**VALID_PLAN, **overrides}
    r = await authed_client_owner.post(
        "/api/v1/membership-plans",
        json=payload,
        headers=_csrf_headers(authed_client_owner),
    )
    assert r.status_code == 201, r.text
    data: dict[str, Any] = r.json()["data"]
    return data


async def test_list_default_envelope(
    authed_client_owner: AsyncClient,
) -> None:
    """List response wraps items + total + page + pageSize (MEM-PLAN-EP-01)."""
    r = await authed_client_owner.get("/api/v1/membership-plans")
    assert r.status_code == 200, r.text
    body = r.json()
    assert "data" in body
    data = body["data"]
    assert isinstance(data["items"], list)
    assert data["total"] == 0
    assert data["page"] == 1
    assert data["pageSize"] == 20


async def test_list_returns_alive_plans_only(
    authed_client_owner: AsyncClient,
) -> None:
    """Soft-deleted plans are excluded from the default list view."""
    p1 = await _create(authed_client_owner, name="Первый план")
    await _create(authed_client_owner, name="Второй план")
    p3 = await _create(authed_client_owner, name="Третий план")

    # Delete one plan
    await authed_client_owner.delete(
        f"/api/v1/membership-plans/{p3['id']}",
        headers=_csrf_headers(authed_client_owner),
    )

    r = await authed_client_owner.get("/api/v1/membership-plans")
    data = r.json()["data"]
    assert data["total"] == 2
    ids = {item["id"] for item in data["items"]}
    assert p1["id"] in ids
    assert p3["id"] not in ids


async def test_list_filter_active_true(
    authed_client_owner: AsyncClient,
) -> None:
    """`?active=true` returns only active alive plans."""
    await _create(authed_client_owner, name="Активный план 1", active=True)
    await _create(authed_client_owner, name="Активный план 2", active=True)
    p3 = await _create(authed_client_owner, name="Неактивный план", active=True)

    # Deactivate p3 via PATCH
    await authed_client_owner.patch(
        f"/api/v1/membership-plans/{p3['id']}",
        json={"active": False},
        headers=_csrf_headers(authed_client_owner),
    )

    r = await authed_client_owner.get(
        "/api/v1/membership-plans", params={"active": "true"}
    )
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert data["total"] == 2


async def test_list_filter_active_false(
    authed_client_owner: AsyncClient,
) -> None:
    """`?active=false` returns only inactive alive plans."""
    await _create(authed_client_owner, name="Активный план 1", active=True)
    await _create(authed_client_owner, name="Активный план 2", active=True)
    p3 = await _create(authed_client_owner, name="Неактивный план", active=True)

    # Deactivate p3 via PATCH
    await authed_client_owner.patch(
        f"/api/v1/membership-plans/{p3['id']}",
        json={"active": False},
        headers=_csrf_headers(authed_client_owner),
    )

    r = await authed_client_owner.get(
        "/api/v1/membership-plans", params={"active": "false"}
    )
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert data["total"] == 1
    assert data["items"][0]["id"] == p3["id"]


async def test_list_filter_active_omitted_returns_both(
    authed_client_owner: AsyncClient,
) -> None:
    """No `?active` param -> both active and inactive alive plans returned."""
    await _create(authed_client_owner, name="Активный план 1", active=True)
    await _create(authed_client_owner, name="Активный план 2", active=True)
    p3 = await _create(authed_client_owner, name="Неактивный план", active=True)

    # Deactivate p3 via PATCH
    await authed_client_owner.patch(
        f"/api/v1/membership-plans/{p3['id']}",
        json={"active": False},
        headers=_csrf_headers(authed_client_owner),
    )

    r = await authed_client_owner.get("/api/v1/membership-plans")
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert data["total"] == 3


async def test_list_sort_name_asc_case_insensitive(
    authed_client_owner: AsyncClient,
) -> None:
    """`?sort=name_asc` orders by lower(name) ascending (case-insensitive)."""
    await _create(authed_client_owner, name="Beta")
    await _create(authed_client_owner, name="GAMMA")
    await _create(authed_client_owner, name="alpha")

    r = await authed_client_owner.get(
        "/api/v1/membership-plans", params={"sort": "name_asc"}
    )
    assert r.status_code == 200, r.text
    items = r.json()["data"]["items"]
    assert len(items) == 3
    names = [item["name"] for item in items]
    assert names == ["alpha", "Beta", "GAMMA"]


async def test_list_sort_default_created_at_desc(
    authed_client_owner: AsyncClient,
) -> None:
    """Default sort is created_at DESC, id DESC.

    Within a SAVEPOINT transaction, func.now() is constant so two
    INSERT rows may share the same created_at. The id DESC tie-breaker
    then determines order — we assert the last-inserted id comes first.
    """
    a = await _create(authed_client_owner, name="Первый план")
    b = await _create(authed_client_owner, name="Второй план")
    c = await _create(authed_client_owner, name="Третий план")

    r = await authed_client_owner.get("/api/v1/membership-plans")
    items = r.json()["data"]["items"]
    assert len(items) == 3
    # When created_at is equal (SAVEPOINT tx), largest UUID string comes first
    ids = [item["id"] for item in items]
    sorted_ids = sorted([a["id"], b["id"], c["id"]], reverse=True)
    assert ids == sorted_ids


async def test_list_pagination_boundary(
    authed_client_owner: AsyncClient,
) -> None:
    """POST 21 plans -> GET ?page=2 -> total=21, items has length 1."""
    for i in range(21):
        await _create(
            authed_client_owner,
            name=f"Тест {i:02d}",
        )

    r = await authed_client_owner.get(
        "/api/v1/membership-plans", params={"page": 2}
    )
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert data["total"] == 21
    assert data["page"] == 2
    assert len(data["items"]) == 1


async def test_list_invalid_active_value_returns_422(
    authed_client_owner: AsyncClient,
) -> None:
    """`?active=maybe` fails Pydantic bool parse -> 422."""
    r = await authed_client_owner.get(
        "/api/v1/membership-plans", params={"active": "maybe"}
    )
    assert r.status_code == 422, r.text
