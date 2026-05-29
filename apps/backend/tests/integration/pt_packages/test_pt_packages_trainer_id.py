"""Integration tests for POST /api/v1/pt-packages with trainer_id (Phase 38 PKG-01 / PKG-02).

Plan 38-04 Task 2:
- Sale with valid active trainer → 201; pt_package row has trainer_id set.
- Sale with inactive trainer → 422 trainer_inactive (mirrors pt_sessions
  convention from Phase 34 D-34-12a).
- Sale with non-existent trainer → 404 trainer_not_found.
- Sale without trainer_id → 201; trainer_id stored as NULL (back-compat).

Trainer-active validation lands in pt_packages.service.create_pt_package
between the snapshot-symmetry guard and the insert_pt_package call. Uses
the existing TrainerById Protocol slot (resolve_trainer_by_id) — NO direct
import of trainers ORM (modules-independent contract).
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any
from uuid import UUID, uuid4

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.clients.models import Client
from app.modules.pt_packages.models import PtPackage, PtPackagePlan
from app.modules.trainers.models import Trainer


def _csrf_headers(client: AsyncClient, *, idempotency_key: str | None = None) -> dict[str, str]:
    headers: dict[str, str] = {"X-CSRF-Token": client.cookies.get("clubcore_csrf", "") or ""}
    if idempotency_key is not None:
        headers["Idempotency-Key"] = idempotency_key
    return headers


def _sale_body(
    client_id: UUID,
    plan_id: UUID,
    amount_kopecks: int,
    *,
    trainer_id: UUID | None = None,
) -> dict[str, Any]:
    body: dict[str, Any] = {
        "clientId": str(client_id),
        "planId": str(plan_id),
        "amountKopecks": amount_kopecks,
    }
    if trainer_id is not None:
        body["trainerId"] = str(trainer_id)
    return body


async def _seed_trainer(
    db_session: AsyncSession, *, is_active: bool = True, full_name: str = "Тренер"
) -> Trainer:
    trainer = Trainer(full_name=full_name, is_active=is_active)
    db_session.add(trainer)
    await db_session.commit()
    await db_session.refresh(trainer)
    return trainer


# --- happy paths -------------------------------------------------------------


async def test_create_pt_package_with_active_trainer_id_sets_column(
    authed_client_owner: AsyncClient,
    db_session: AsyncSession,
    make_client: Callable[..., Awaitable[Client]],
    make_pt_package_plan: Callable[..., Awaitable[PtPackagePlan]],
) -> None:
    """PKG-01 happy path: active trainer accepted; column persisted."""
    plan = await make_pt_package_plan(name="trainer-happy")
    client = await make_client()
    trainer = await _seed_trainer(db_session, full_name="Active Trainer")

    r = await authed_client_owner.post(
        "/api/v1/pt-packages",
        json=_sale_body(client.id, plan.id, plan.price_kopecks, trainer_id=trainer.id),
        headers=_csrf_headers(authed_client_owner, idempotency_key=uuid4().hex),
    )
    assert r.status_code == 201, r.text
    data = r.json()["data"]
    assert data["trainerId"] == str(trainer.id)

    # DB-level confirmation.
    pkg = await db_session.scalar(select(PtPackage).where(PtPackage.id == UUID(data["id"])))
    assert pkg is not None
    assert pkg.trainer_id == trainer.id


async def test_create_pt_package_without_trainer_id_stores_null(
    authed_client_owner: AsyncClient,
    db_session: AsyncSession,
    make_client: Callable[..., Awaitable[Client]],
    make_pt_package_plan: Callable[..., Awaitable[PtPackagePlan]],
) -> None:
    """PKG-01 back-compat: omitting trainer_id → 201; trainer_id IS NULL."""
    plan = await make_pt_package_plan(name="trainer-omit")
    client = await make_client()

    r = await authed_client_owner.post(
        "/api/v1/pt-packages",
        json=_sale_body(client.id, plan.id, plan.price_kopecks),
        headers=_csrf_headers(authed_client_owner, idempotency_key=uuid4().hex),
    )
    assert r.status_code == 201, r.text
    data = r.json()["data"]
    assert data["trainerId"] is None

    pkg = await db_session.scalar(select(PtPackage).where(PtPackage.id == UUID(data["id"])))
    assert pkg is not None
    assert pkg.trainer_id is None


# --- error paths -------------------------------------------------------------


async def test_create_pt_package_with_inactive_trainer_409_or_422(
    authed_client_owner: AsyncClient,
    db_session: AsyncSession,
    make_client: Callable[..., Awaitable[Client]],
    make_pt_package_plan: Callable[..., Awaitable[PtPackagePlan]],
) -> None:
    """PKG-02: inactive trainer → trainer_inactive code (mirrors pt_sessions)."""
    plan = await make_pt_package_plan(name="trainer-inactive")
    client = await make_client()
    trainer = await _seed_trainer(db_session, is_active=False, full_name="Inactive Trainer")

    r = await authed_client_owner.post(
        "/api/v1/pt-packages",
        json=_sale_body(client.id, plan.id, plan.price_kopecks, trainer_id=trainer.id),
        headers=_csrf_headers(authed_client_owner, idempotency_key=uuid4().hex),
    )
    # pt_sessions sets status 422 for trainer_inactive (D-34-12a). Mirror that.
    assert r.status_code == 422, r.text
    assert r.json()["code"] == "trainer_inactive"

    # No pt_package row should have been created.
    count = await db_session.scalar(select(PtPackage).where(PtPackage.client_id == client.id))
    assert count is None


async def test_create_pt_package_with_unknown_trainer_404(
    authed_client_owner: AsyncClient,
    db_session: AsyncSession,
    make_client: Callable[..., Awaitable[Client]],
    make_pt_package_plan: Callable[..., Awaitable[PtPackagePlan]],
) -> None:
    """Unknown trainer_id → 404 trainer_not_found (mirrors pt_sessions D-34-12a)."""
    plan = await make_pt_package_plan(name="trainer-unknown")
    client = await make_client()

    r = await authed_client_owner.post(
        "/api/v1/pt-packages",
        json=_sale_body(client.id, plan.id, plan.price_kopecks, trainer_id=uuid4()),
        headers=_csrf_headers(authed_client_owner, idempotency_key=uuid4().hex),
    )
    assert r.status_code == 404, r.text
    assert r.json()["code"] == "trainer_not_found"

    # No pt_package row should exist.
    count = await db_session.scalar(select(PtPackage).where(PtPackage.client_id == client.id))
    assert count is None
