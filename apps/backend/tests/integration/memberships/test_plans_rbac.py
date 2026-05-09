"""Integration tests for /api/v1/membership-plans RBAC gates (RBAC-05).

The ENTIRE MEMBERSHIP_PLANS resource is in OWNER_ONLY (Phase 15), so
reception must be denied with 403 forbidden on ALL 4 endpoints:
GET list, GET single, POST, PATCH, DELETE.

Unauth canary: bare async_client (no cookies) GET/POST -> 401, not 403,
preserving the RBAC-04 ordering invariant from Phase 6 (auth fires
before RBAC).
"""

from __future__ import annotations

from typing import Any

from httpx import AsyncClient


def _csrf_headers(client: AsyncClient) -> dict[str, str]:
    return {"X-CSRF-Token": client.cookies.get("sportzal_csrf", "")}


VALID_PLAN: dict[str, Any] = {
    "name": "Базовый",
    "durationDays": 30,
    "priceKopecks": 250000,
    "freezeDaysLimit": 14,
    "active": True,
}


async def _create(authed: AsyncClient, **overrides: Any) -> dict[str, Any]:
    payload = {**VALID_PLAN, **overrides}
    r = await authed.post(
        "/api/v1/membership-plans",
        json=payload,
        headers=_csrf_headers(authed),
    )
    assert r.status_code == 201, r.text
    data: dict[str, Any] = r.json()["data"]
    return data


# --- Reception 403 matrix (whole resource is owner-only) ---


async def test_get_list_reception_returns_403(
    authed_client_owner: AsyncClient,
    authed_client_reception: AsyncClient,
) -> None:
    """(VIEW, MEMBERSHIP_PLANS) is in OWNER_ONLY -> reception 403 forbidden."""
    r = await authed_client_reception.get("/api/v1/membership-plans")
    assert r.status_code == 403, r.text
    assert r.json()["code"] == "forbidden"


async def test_get_single_reception_returns_403(
    authed_client_owner: AsyncClient,
    authed_client_reception: AsyncClient,
) -> None:
    """(VIEW, MEMBERSHIP_PLANS) is in OWNER_ONLY -> reception 403 on GET /{id}."""
    created = await _create(authed_client_owner)
    r = await authed_client_reception.get(
        f"/api/v1/membership-plans/{created['id']}"
    )
    assert r.status_code == 403, r.text
    assert r.json()["code"] == "forbidden"


async def test_post_reception_returns_403(
    authed_client_owner: AsyncClient,
    authed_client_reception: AsyncClient,
) -> None:
    """(CREATE, MEMBERSHIP_PLANS) is in OWNER_ONLY -> reception 403 on POST."""
    r = await authed_client_reception.post(
        "/api/v1/membership-plans",
        json=VALID_PLAN,
        headers=_csrf_headers(authed_client_reception),
    )
    assert r.status_code == 403, r.text
    assert r.json()["code"] == "forbidden"


async def test_patch_reception_returns_403(
    authed_client_owner: AsyncClient,
    authed_client_reception: AsyncClient,
) -> None:
    """(EDIT, MEMBERSHIP_PLANS) is in OWNER_ONLY -> reception 403 on PATCH."""
    created = await _create(authed_client_owner)
    r = await authed_client_reception.patch(
        f"/api/v1/membership-plans/{created['id']}",
        json={"name": "Другой"},
        headers=_csrf_headers(authed_client_reception),
    )
    assert r.status_code == 403, r.text
    assert r.json()["code"] == "forbidden"


async def test_delete_reception_returns_403(
    authed_client_owner: AsyncClient,
    authed_client_reception: AsyncClient,
) -> None:
    """(DELETE, MEMBERSHIP_PLANS) is in OWNER_ONLY -> reception 403 on DELETE."""
    created = await _create(authed_client_owner)
    r = await authed_client_reception.delete(
        f"/api/v1/membership-plans/{created['id']}",
        headers=_csrf_headers(authed_client_reception),
    )
    assert r.status_code == 403, r.text
    assert r.json()["code"] == "forbidden"


# --- Unauthenticated 401 canaries (RBAC-04 ordering: auth before RBAC) ---


async def test_get_list_unauth_returns_401(
    async_client: AsyncClient,
) -> None:
    """RBAC-04: unauth GET /membership-plans -> 401, not 403."""
    r = await async_client.get("/api/v1/membership-plans")
    assert r.status_code == 401, r.text


async def test_post_unauth_returns_401(
    async_client: AsyncClient,
) -> None:
    """RBAC-04: unauth POST -> 401 (auth check fires before CSRF, before RBAC)."""
    r = await async_client.post(
        "/api/v1/membership-plans",
        json=VALID_PLAN,
    )
    assert r.status_code == 401, r.text
