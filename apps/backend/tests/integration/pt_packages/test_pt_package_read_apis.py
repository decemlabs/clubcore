"""Integration tests for GET /api/v1/pt-packages list + GET /pt-packages/{id} (Plan 33-02).

Phase 33 D-33-06 read-tier (reception+owner; (VIEW, PT_PACKAGES) NOT in
OWNER_ONLY — B-07 PT-session form prefill in Phase 35).

Coverage:
  - List paginated envelope (owner + reception RBAC parity).
  - Filter by client_id; filter by status.
  - Single GET returns full snapshot + computed is_active (D-33-10).
  - 404 pt_package_not_found.
  - Unauthenticated → 401.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from uuid import uuid4

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.clients.models import Client
from app.modules.pt_packages.models import PtPackage, PtPackagePlan


async def test_list_pt_packages_owner_returns_paginated_envelope(
    authed_client_owner: AsyncClient,
    make_client: Callable[..., Awaitable[Client]],
    make_pt_package_plan: Callable[..., Awaitable[PtPackagePlan]],
    make_pt_package: Callable[..., Awaitable[PtPackage]],
) -> None:
    """List returns envelope {items, total, page, pageSize}; owner sees all."""
    plan = await make_pt_package_plan(name="list-owner")
    c1 = await make_client(phone="+79991110001")
    c2 = await make_client(phone="+79991110002")
    c3 = await make_client(phone="+79991110003")
    await make_pt_package(client_id=c1.id, plan=plan)
    await make_pt_package(client_id=c2.id, plan=plan)
    await make_pt_package(client_id=c3.id, plan=plan)

    r = await authed_client_owner.get("/api/v1/pt-packages")
    assert r.status_code == 200, r.text
    body = r.json()
    assert "data" in body
    data = body["data"]
    assert "items" in data
    assert "total" in data
    assert "page" in data
    assert "pageSize" in data
    assert data["total"] >= 3
    assert len(data["items"]) >= 3


async def test_list_pt_packages_reception_rbac_parity(
    authed_client_reception: AsyncClient,
    make_client: Callable[..., Awaitable[Client]],
    make_pt_package_plan: Callable[..., Awaitable[PtPackagePlan]],
    make_pt_package: Callable[..., Awaitable[PtPackage]],
) -> None:
    """(VIEW, PT_PACKAGES) NOT in OWNER_ONLY — reception 200 same as owner."""
    plan = await make_pt_package_plan(name="list-reception")
    client = await make_client()
    await make_pt_package(client_id=client.id, plan=plan)

    r = await authed_client_reception.get("/api/v1/pt-packages")
    assert r.status_code == 200, r.text


async def test_list_pt_packages_filter_by_client_id(
    authed_client_owner: AsyncClient,
    make_client: Callable[..., Awaitable[Client]],
    make_pt_package_plan: Callable[..., Awaitable[PtPackagePlan]],
    make_pt_package: Callable[..., Awaitable[PtPackage]],
) -> None:
    """?clientId=A returns only packages for client A."""
    plan = await make_pt_package_plan(name="filter-client")
    c_a = await make_client(phone="+79991120001")
    c_b = await make_client(phone="+79991120002")
    await make_pt_package(client_id=c_a.id, plan=plan)
    await make_pt_package(client_id=c_b.id, plan=plan)

    r = await authed_client_owner.get(f"/api/v1/pt-packages?clientId={c_a.id}")
    assert r.status_code == 200, r.text
    items = r.json()["data"]["items"]
    assert all(it["clientId"] == str(c_a.id) for it in items)
    assert len(items) >= 1


async def test_list_pt_packages_filter_by_status(
    authed_client_owner: AsyncClient,
    db_session: AsyncSession,
    make_client: Callable[..., Awaitable[Client]],
    make_pt_package_plan: Callable[..., Awaitable[PtPackagePlan]],
    make_pt_package: Callable[..., Awaitable[PtPackage]],
) -> None:
    """?status=cancelled returns only cancelled packages."""
    plan = await make_pt_package_plan(name="filter-status")
    c_a = await make_client(phone="+79991130001")
    c_b = await make_client(phone="+79991130002")
    pkg_active = await make_pt_package(client_id=c_a.id, plan=plan)
    pkg_cancelled = await make_pt_package(client_id=c_b.id, plan=plan, status="cancelled")

    r = await authed_client_owner.get("/api/v1/pt-packages?status=cancelled")
    assert r.status_code == 200, r.text
    items = r.json()["data"]["items"]
    assert all(it["status"] == "cancelled" for it in items)
    cancelled_ids = {it["id"] for it in items}
    assert str(pkg_cancelled.id) in cancelled_ids
    assert str(pkg_active.id) not in cancelled_ids


async def test_get_pt_package_owner_returns_full_snapshot(
    authed_client_owner: AsyncClient,
    make_client: Callable[..., Awaitable[Client]],
    make_pt_package_plan: Callable[..., Awaitable[PtPackagePlan]],
    make_pt_package: Callable[..., Awaitable[PtPackage]],
) -> None:
    """Single GET returns full snapshot + computed is_active (D-33-10)."""
    plan = await make_pt_package_plan(name="get-owner")
    client = await make_client()
    pkg = await make_pt_package(client_id=client.id, plan=plan)

    r = await authed_client_owner.get(f"/api/v1/pt-packages/{pkg.id}")
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert data["id"] == str(pkg.id)
    assert data["planNameSnapshot"] == plan.name
    assert data["sessionCountSnapshot"] == plan.session_count
    assert data["priceKopecksSnapshot"] == plan.price_kopecks
    assert data["validityDaysSnapshot"] == plan.validity_days
    assert data["sessionsRemaining"] == pkg.sessions_remaining
    assert data["status"] == "active"
    assert data["isActive"] is True


async def test_get_pt_package_reception_rbac_parity(
    authed_client_reception: AsyncClient,
    make_client: Callable[..., Awaitable[Client]],
    make_pt_package_plan: Callable[..., Awaitable[PtPackagePlan]],
    make_pt_package: Callable[..., Awaitable[PtPackage]],
) -> None:
    """(VIEW, PT_PACKAGES) reception+owner — reception 200 on detail GET."""
    plan = await make_pt_package_plan(name="get-reception")
    client = await make_client()
    pkg = await make_pt_package(client_id=client.id, plan=plan)
    r = await authed_client_reception.get(f"/api/v1/pt-packages/{pkg.id}")
    assert r.status_code == 200, r.text


async def test_get_pt_package_not_found_404(
    authed_client_owner: AsyncClient,
) -> None:
    """Unknown id → 404 pt_package_not_found."""
    r = await authed_client_owner.get(f"/api/v1/pt-packages/{uuid4()}")
    assert r.status_code == 404, r.text
    assert r.json()["code"] == "pt_package_not_found"


async def test_get_pt_package_unauthenticated_401(app: FastAPI) -> None:
    """No auth → 401."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as anon:
        r = await anon.get(f"/api/v1/pt-packages/{uuid4()}")
    assert r.status_code == 401, r.text
