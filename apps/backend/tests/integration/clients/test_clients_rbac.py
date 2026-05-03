"""Integration tests for /api/v1/clients RBAC gates (CLIENTS-08, RBAC-05).

DELETE,CLIENTS is in `OWNER_ONLY` (Phase 6 D-11), so reception must be
denied with 403 forbidden. POST and GET sit on the EDIT/VIEW actions
which are NOT in OWNER_ONLY — reception passes those (D-21).

Unauth canary: bare async_client (no cookies) DELETE -> 401, not 403,
preserving the RBAC-04 ordering invariant from Phase 6 (auth fires
before RBAC).
"""

from __future__ import annotations

from typing import Any

from httpx import AsyncClient


def _csrf_headers(client: AsyncClient) -> dict[str, str]:
    return {"X-CSRF-Token": client.cookies.get("sportzal_csrf", "")}


VALID_CLIENT: dict[str, Any] = {
    "lastName": "Иванов",
    "firstName": "Иван",
    "phone": "+79991234567",
}


async def _create(authed: AsyncClient, **overrides: Any) -> dict[str, Any]:
    payload = {**VALID_CLIENT, **overrides}
    r = await authed.post(
        "/api/v1/clients",
        json=payload,
        headers=_csrf_headers(authed),
    )
    assert r.status_code == 201, r.text
    data: dict[str, Any] = r.json()["data"]
    return data


async def test_delete_owner_returns_204(
    authed_client_owner: AsyncClient,
) -> None:
    """CLIENTS-08: owner can soft-delete (204)."""
    created = await _create(authed_client_owner, phone="+79990001001")
    r = await authed_client_owner.delete(
        f"/api/v1/clients/{created['id']}",
        headers=_csrf_headers(authed_client_owner),
    )
    assert r.status_code == 204, r.text


async def test_delete_reception_returns_403_forbidden(
    authed_client_owner: AsyncClient,
    authed_client_reception: AsyncClient,
) -> None:
    """RBAC-05: (DELETE, CLIENTS) is in OWNER_ONLY -> reception 403 forbidden."""
    created = await _create(authed_client_owner, phone="+79990001002")
    r = await authed_client_reception.delete(
        f"/api/v1/clients/{created['id']}",
        headers=_csrf_headers(authed_client_reception),
    )
    assert r.status_code == 403, r.text
    assert r.json()["code"] == "forbidden"


async def test_delete_unauthenticated_returns_401(
    authed_client_owner: AsyncClient,
    async_client: AsyncClient,
) -> None:
    """RBAC-04 ordering: unauth DELETE -> 401, not 403."""
    created = await _create(authed_client_owner, phone="+79990001003")
    r = await async_client.delete(f"/api/v1/clients/{created['id']}")
    assert r.status_code == 401, r.text


async def test_create_reception_returns_201(
    authed_client_reception: AsyncClient,
) -> None:
    """D-21: (EDIT, CLIENTS) is NOT in OWNER_ONLY -> reception can POST."""
    r = await authed_client_reception.post(
        "/api/v1/clients",
        json={**VALID_CLIENT, "phone": "+79990001004"},
        headers=_csrf_headers(authed_client_reception),
    )
    assert r.status_code == 201, r.text


async def test_view_reception_returns_200(
    authed_client_owner: AsyncClient,
    authed_client_reception: AsyncClient,
) -> None:
    """(VIEW, CLIENTS) is NOT in OWNER_ONLY -> reception can list + read-one."""
    created = await _create(authed_client_owner, phone="+79990001005")

    r_list = await authed_client_reception.get("/api/v1/clients")
    assert r_list.status_code == 200

    r_one = await authed_client_reception.get(f"/api/v1/clients/{created['id']}")
    assert r_one.status_code == 200
    assert r_one.json()["data"]["id"] == created["id"]
