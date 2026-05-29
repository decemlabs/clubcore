"""Integration tests for /api/v1/visits RBAC gates.

Phase 19 RBAC matrix:
  - (VIEW, VISITS)     — reception+owner  (NOT in OWNER_ONLY)
  - (CHECK_IN, VISITS) — reception+owner  (NOT in OWNER_ONLY)

3-cell matrix per endpoint: anon → 401, reception → 200/201, owner → 200/201.
"""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from httpx import AsyncClient


def _csrf(client: AsyncClient) -> dict[str, str]:
    return {"X-CSRF-Token": client.cookies.get("clubcore_csrf") or ""}


# ── Unauthenticated 401 canaries (RBAC-04 ordering) ───────────────────────────


async def test_anon_get_list_401(async_client: AsyncClient) -> None:
    """RBAC-04: unauth GET /visits → 401, not 403."""
    r = await async_client.get("/api/v1/visits")
    assert r.status_code == 401, r.text


async def test_anon_get_single_401(async_client: AsyncClient) -> None:
    """RBAC-04: unauth GET /visits/{id} → 401."""
    r = await async_client.get(f"/api/v1/visits/{uuid4()}")
    assert r.status_code == 401, r.text


async def test_anon_post_checkin_401(async_client: AsyncClient) -> None:
    """RBAC-04: unauth POST /visits → 401 (auth fires before CSRF/RBAC)."""
    r = await async_client.post(
        "/api/v1/visits",
        json={"clientId": str(uuid4())},
    )
    assert r.status_code == 401, r.text


# ── Reception authorised paths ────────────────────────────────────────────────


async def test_reception_can_get_visits_list(
    authed_client_reception: AsyncClient,
    seeded_reception: Any,
) -> None:
    """(VIEW, VISITS) is NOT in OWNER_ONLY → reception 200 on GET list."""
    r = await authed_client_reception.get("/api/v1/visits")
    assert r.status_code == 200, r.text


async def test_reception_can_get_visit_or_404(
    authed_client_reception: AsyncClient,
    seeded_reception: Any,
) -> None:
    """(VIEW, VISITS) → reception 404 (not 403) on random UUID."""
    r = await authed_client_reception.get(f"/api/v1/visits/{uuid4()}")
    # 404 means RBAC passed (403 would mean OWNER_ONLY blocked)
    assert r.status_code == 404, r.text


async def test_reception_can_post_checkin_409(
    authed_client_reception: AsyncClient,
    seeded_reception: Any,
) -> None:
    """(CHECK_IN, VISITS) is NOT in OWNER_ONLY → reception gets 409, not 403.

    Random client_id yields no_active_membership (409) — proves RBAC let reception through.
    """
    r = await authed_client_reception.post(
        "/api/v1/visits",
        json={"clientId": str(uuid4())},
        headers=_csrf(authed_client_reception),
    )
    # 409 means reception got past RBAC (403 would mean OWNER_ONLY blocked)
    assert r.status_code == 409, r.text


# ── Owner authorised paths ────────────────────────────────────────────────────


async def test_owner_can_get_visits_list(
    authed_client_owner: AsyncClient,
    seeded_owner: Any,
) -> None:
    """Owner GET /visits → 200."""
    r = await authed_client_owner.get("/api/v1/visits")
    assert r.status_code == 200, r.text


async def test_owner_can_get_visit_or_404(
    authed_client_owner: AsyncClient,
    seeded_owner: Any,
) -> None:
    """Owner GET /visits/{random} → 404 (not 403 = RBAC OK)."""
    r = await authed_client_owner.get(f"/api/v1/visits/{uuid4()}")
    assert r.status_code == 404, r.text


async def test_owner_can_post_checkin_409(
    authed_client_owner: AsyncClient,
    seeded_owner: Any,
) -> None:
    """Owner POST /visits with random clientId → 409 no_active_membership (RBAC OK)."""
    r = await authed_client_owner.post(
        "/api/v1/visits",
        json={"clientId": str(uuid4())},
        headers=_csrf(authed_client_owner),
    )
    assert r.status_code == 409, r.text
