"""Integration tests for /api/v1/memberships RBAC gates.

Phase 17 RBAC matrix (CONTEXT.md domain line 19):
  - (VIEW, MEMBERSHIPS)   — reception+owner   (NOT in OWNER_ONLY)
  - (CREATE, MEMBERSHIPS) — reception+owner   (NOT in OWNER_ONLY)
  - (CANCEL, MEMBERSHIPS) — owner-only        (IN OWNER_ONLY)

Unauth canary: bare async_client (no cookies) hits 401 first per RBAC-04
ordering (auth fires before RBAC).
"""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from httpx import AsyncClient


def _csrf_headers(client: AsyncClient) -> dict[str, str]:
    return {"X-CSRF-Token": client.cookies.get("sportzal_csrf") or ""}


VALID_PLAN: dict[str, Any] = {
    "name": "Базовый",
    "durationDays": 30,
    "priceKopecks": 250000,
    "active": True,
}

VALID_CLIENT: dict[str, Any] = {
    "lastName": "Иванов",
    "firstName": "Иван",
    "phone": "+79991234567",
}


async def _create_plan(authed: AsyncClient, **overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {**VALID_PLAN, **overrides}
    r = await authed.post(
        "/api/v1/membership-plans",
        json=payload,
        headers=_csrf_headers(authed),
    )
    assert r.status_code == 201, r.text
    data: dict[str, Any] = r.json()["data"]
    return data


async def _create_client(authed: AsyncClient, **overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {**VALID_CLIENT, **overrides}
    r = await authed.post(
        "/api/v1/clients",
        json=payload,
        headers=_csrf_headers(authed),
    )
    assert r.status_code == 201, r.text
    data: dict[str, Any] = r.json()["data"]
    return data


# --- Reception authorised paths --------------------------------------------


async def test_reception_can_post_sale(
    authed_client_owner: AsyncClient,
    authed_client_reception: AsyncClient,
) -> None:
    """(CREATE, MEMBERSHIPS) is NOT in OWNER_ONLY -> reception 201 on sale."""
    plan = await _create_plan(authed_client_owner)
    client = await _create_client(authed_client_owner)

    r = await authed_client_reception.post(
        "/api/v1/memberships",
        json={"clientId": client["id"], "planId": plan["id"]},
        headers=_csrf_headers(authed_client_reception),
    )
    assert r.status_code == 201, r.text


async def test_reception_can_get_list(
    authed_client_reception: AsyncClient,
) -> None:
    """(VIEW, MEMBERSHIPS) is NOT in OWNER_ONLY -> reception 200 on GET list."""
    r = await authed_client_reception.get("/api/v1/memberships")
    assert r.status_code == 200, r.text


async def test_reception_can_get_single(
    authed_client_owner: AsyncClient,
    authed_client_reception: AsyncClient,
) -> None:
    """(VIEW, MEMBERSHIPS) -> reception 200 on GET /{id} (or 404 for unknown)."""
    plan = await _create_plan(authed_client_owner)
    client = await _create_client(authed_client_owner)
    sale = await authed_client_owner.post(
        "/api/v1/memberships",
        json={"clientId": client["id"], "planId": plan["id"]},
        headers=_csrf_headers(authed_client_owner),
    )
    assert sale.status_code == 201
    membership_id = sale.json()["data"]["id"]

    r = await authed_client_reception.get(f"/api/v1/memberships/{membership_id}")
    assert r.status_code == 200, r.text


# --- Reception denied paths ------------------------------------------------


async def test_reception_cannot_post_cancel(
    authed_client_owner: AsyncClient,
    authed_client_reception: AsyncClient,
) -> None:
    """(CANCEL, MEMBERSHIPS) is in OWNER_ONLY -> reception 403."""
    plan = await _create_plan(authed_client_owner)
    client = await _create_client(authed_client_owner)
    sale = await authed_client_owner.post(
        "/api/v1/memberships",
        json={"clientId": client["id"], "planId": plan["id"]},
        headers=_csrf_headers(authed_client_owner),
    )
    assert sale.status_code == 201
    membership_id = sale.json()["data"]["id"]

    r = await authed_client_reception.post(
        f"/api/v1/memberships/{membership_id}/cancel",
        json={"reason": "test"},
        headers=_csrf_headers(authed_client_reception),
    )
    assert r.status_code == 403, r.text
    assert r.json()["code"] == "forbidden"


async def test_owner_can_post_cancel(
    authed_client_owner: AsyncClient,
) -> None:
    """Owner POST cancel on active membership -> 200."""
    plan = await _create_plan(authed_client_owner)
    client = await _create_client(authed_client_owner)
    sale = await authed_client_owner.post(
        "/api/v1/memberships",
        json={"clientId": client["id"], "planId": plan["id"]},
        headers=_csrf_headers(authed_client_owner),
    )
    assert sale.status_code == 201
    membership_id = sale.json()["data"]["id"]

    r = await authed_client_owner.post(
        f"/api/v1/memberships/{membership_id}/cancel",
        json={"reason": "owner cancel"},
        headers=_csrf_headers(authed_client_owner),
    )
    assert r.status_code == 200, r.text


# --- Unauthenticated 401 canaries (RBAC-04 ordering) -----------------------


async def test_unauth_get_list(async_client: AsyncClient) -> None:
    """RBAC-04: unauth GET /memberships -> 401, not 403."""
    r = await async_client.get("/api/v1/memberships")
    assert r.status_code == 401, r.text


async def test_unauth_post_sale(async_client: AsyncClient) -> None:
    """RBAC-04: unauth POST /memberships -> 401 (auth fires before CSRF/RBAC)."""
    r = await async_client.post(
        "/api/v1/memberships",
        json={"clientId": str(uuid4()), "planId": str(uuid4())},
    )
    assert r.status_code == 401, r.text


async def test_unauth_post_cancel(async_client: AsyncClient) -> None:
    """RBAC-04: unauth POST cancel -> 401 (auth fires before CSRF/RBAC)."""
    r = await async_client.post(
        f"/api/v1/memberships/{uuid4()}/cancel",
        json={},
    )
    assert r.status_code == 401, r.text


