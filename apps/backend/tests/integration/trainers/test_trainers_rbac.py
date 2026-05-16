"""Integration tests for /api/v1/trainers RBAC gates (TRN-04/05, RBAC-04/05).

OWNER_ONLY contains (CREATE, TRAINERS), (EDIT, TRAINERS), (DELETE, TRAINERS).
(VIEW, TRAINERS) is NOT in OWNER_ONLY — reception can list + read-one (D-31-09).

RBAC-04 ordering: unauthenticated DELETE → 401, not 403 (auth fires before RBAC).
"""

from __future__ import annotations

import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from tests.integration.trainers.conftest import VALID_TRAINER, _create, _csrf_headers


@pytest_asyncio.fixture
async def unauthed_client(app: FastAPI) -> AsyncClient:
    """Non-authenticated httpx client (no cookies)."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client


async def test_create_reception_returns_403_forbidden(
    authed_client_reception: AsyncClient,
) -> None:
    """(CREATE, TRAINERS) is in OWNER_ONLY → reception 403."""
    r = await authed_client_reception.post(
        "/api/v1/trainers",
        json=VALID_TRAINER,
        headers=_csrf_headers(authed_client_reception),
    )
    assert r.status_code == 403, r.text
    assert r.json()["code"] == "forbidden"


async def test_patch_reception_returns_403_forbidden(
    authed_client_owner: AsyncClient,
    authed_client_reception: AsyncClient,
) -> None:
    """(EDIT, TRAINERS) is in OWNER_ONLY → reception PATCH 403."""
    created = await _create(authed_client_owner, phone="+79990001101")
    r = await authed_client_reception.patch(
        f"/api/v1/trainers/{created['id']}",
        json={"fullName": "X"},
        headers=_csrf_headers(authed_client_reception),
    )
    assert r.status_code == 403, r.text
    assert r.json()["code"] == "forbidden"


async def test_delete_reception_returns_403_forbidden(
    authed_client_owner: AsyncClient,
    authed_client_reception: AsyncClient,
) -> None:
    """(DELETE, TRAINERS) is in OWNER_ONLY → reception DELETE 403."""
    created = await _create(authed_client_owner, phone="+79990001102")
    r = await authed_client_reception.delete(
        f"/api/v1/trainers/{created['id']}",
        headers=_csrf_headers(authed_client_reception),
    )
    assert r.status_code == 403, r.text
    assert r.json()["code"] == "forbidden"


async def test_list_reception_active_true_returns_200(
    authed_client_reception: AsyncClient,
) -> None:
    """(VIEW, TRAINERS) NOT in OWNER_ONLY → reception can list active trainers."""
    r = await authed_client_reception.get("/api/v1/trainers?active=true")
    assert r.status_code == 200, r.text


async def test_list_reception_without_active_returns_200(
    authed_client_reception: AsyncClient,
) -> None:
    """(VIEW, TRAINERS) NOT in OWNER_ONLY → reception can list all trainers (D-31-09)."""
    r = await authed_client_reception.get("/api/v1/trainers")
    assert r.status_code == 200, r.text


async def test_get_reception_returns_200(
    authed_client_owner: AsyncClient,
    authed_client_reception: AsyncClient,
) -> None:
    """(VIEW, TRAINERS) NOT in OWNER_ONLY → reception can read single trainer."""
    created = await _create(authed_client_owner, phone="+79990001103")
    r = await authed_client_reception.get(f"/api/v1/trainers/{created['id']}")
    assert r.status_code == 200, r.text
    assert r.json()["data"]["id"] == created["id"]


async def test_delete_unauthed_returns_401_not_403(
    unauthed_client: AsyncClient,
) -> None:
    """RBAC-04: unauthenticated DELETE → 401 (auth fires before permission check)."""
    r = await unauthed_client.delete(
        "/api/v1/trainers/00000000-0000-0000-0000-000000000001",
        headers={"X-CSRF-Token": "fake"},
    )
    assert r.status_code == 401, r.text


async def test_post_without_csrf_returns_403(
    authed_client_owner: AsyncClient,
) -> None:
    """Owner POST without X-CSRF-Token header → 403 csrf_mismatch.

    Note: require_permission fires before verify_csrf (RBAC-04), so owner
    is authenticated + authorized first; then CSRF fails → 403.
    """
    r = await authed_client_owner.post(
        "/api/v1/trainers",
        json=VALID_TRAINER,
        # No X-CSRF-Token header
    )
    assert r.status_code == 403, r.text
