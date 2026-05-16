"""Integration tests for the PT-session read endpoints (Plan 34-03).

PT-19 read tier — covers BOTH:

  - GET /api/v1/pt-sessions/{id} (single)
  - GET /api/v1/pt-packages/{id}/sessions (paginated by-package; D-34-08)

Scenarios:
  - GET single happy path — 200, full envelope shape with
    trainer_name_snapshot.
  - GET single missing → 404 pt_session_not_found.
  - List paginated DESC — 25 sessions, pageSize=10, page=1/2/3 returns
    10/10/5 ordered performed_at DESC.
  - includeCancelled filter — 5 cancelled + 5 active rows, default
    (true) returns all 10; false returns active 5.
  - Unknown pt_package_id → 200 + empty page (no 404 — package
    existence check out of scope for list endpoints; pt_packages list
    precedent).
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.clients.models import Client
from app.modules.pt_packages.models import PtPackage, PtPackagePlan
from app.modules.trainers.models import Trainer


def _csrf_headers(
    client: AsyncClient,
    *,
    idempotency_key: str | None = None,
) -> dict[str, str]:
    headers: dict[str, str] = {
        "X-CSRF-Token": client.cookies.get("sportzal_csrf", "") or ""
    }
    if idempotency_key is not None:
        headers["Idempotency-Key"] = idempotency_key
    return headers


async def _seed_pt_session(
    db_session: AsyncSession,
    *,
    pt_package_id: UUID,
    trainer_id: UUID,
    client_id: UUID,
    performed_by_user_id: UUID,
    trainer_name_snapshot: str,
    performed_at: datetime,
    created_at: datetime | None = None,
    cancelled_at: datetime | None = None,
    cancel_reason: str | None = None,
) -> UUID:
    """Insert a pt_sessions row directly. cancelled_at / cancel_reason can
    pre-mark the row as cancelled for filter tests."""
    pt_session_id = uuid4()
    ts = created_at or performed_at
    await db_session.execute(
        text(
            "INSERT INTO pt_sessions (id, pt_package_id, trainer_id, "
            "client_id, performed_at, performed_by_user_id, "
            "trainer_name_snapshot, notes, cancelled_at, cancel_reason, "
            "created_at, updated_at) VALUES "
            "(:id, :pkg, :trn, :cli, :perf, :uid, :name, NULL, "
            ":canc_at, :canc_rsn, :created, :created)"
        ),
        {
            "id": pt_session_id,
            "pkg": pt_package_id,
            "trn": trainer_id,
            "cli": client_id,
            "perf": performed_at,
            "uid": performed_by_user_id,
            "name": trainer_name_snapshot,
            "canc_at": cancelled_at,
            "canc_rsn": cancel_reason,
            "created": ts,
        },
    )
    await db_session.flush()
    return pt_session_id


async def test_get_pt_session_happy_path(
    authed_client_reception: AsyncClient,
    db_session: AsyncSession,
    make_client: Callable[..., Awaitable[Client]],
    make_pt_package_plan: Callable[..., Awaitable[PtPackagePlan]],
    make_pt_package: Callable[..., Awaitable[PtPackage]],
    make_trainer: Callable[..., Awaitable[Trainer]],
) -> None:
    """PT-19: GET /pt-sessions/{id} returns the row envelope with trainer_name_snapshot."""
    plan = await make_pt_package_plan(session_count=5)
    client = await make_client()
    pkg = await make_pt_package(client_id=client.id, plan=plan, sessions_remaining=5)
    trainer = await make_trainer(full_name="Сергей Петров")

    r_rec = await authed_client_reception.post(
        "/api/v1/pt-sessions",
        json={
            "ptPackageId": str(pkg.id),
            "trainerId": str(trainer.id),
            "performedAt": (datetime.now(UTC) - timedelta(minutes=10)).isoformat(),
        },
        headers=_csrf_headers(authed_client_reception, idempotency_key=uuid4().hex),
    )
    assert r_rec.status_code == 201
    pt_session_id = r_rec.json()["data"]["id"]

    r = await authed_client_reception.get(f"/api/v1/pt-sessions/{pt_session_id}")
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert data["id"] == pt_session_id
    assert data["ptPackageId"] == str(pkg.id)
    assert data["trainerId"] == str(trainer.id)
    assert data["clientId"] == str(client.id)
    assert data["trainerNameSnapshot"] == "Сергей Петров"
    assert data["cancelledAt"] is None
    assert data["cancelReason"] is None


async def test_get_pt_session_missing_returns_404(
    authed_client_reception: AsyncClient,
) -> None:
    """404 pt_session_not_found for unknown id."""
    r = await authed_client_reception.get(f"/api/v1/pt-sessions/{uuid4()}")
    assert r.status_code == 404, r.text
    assert r.json()["code"] == "pt_session_not_found"


async def test_list_sessions_by_pt_package_paginated(
    authed_client_reception: AsyncClient,
    db_session: AsyncSession,
    make_client: Callable[..., Awaitable[Client]],
    make_pt_package_plan: Callable[..., Awaitable[PtPackagePlan]],
    make_pt_package: Callable[..., Awaitable[PtPackage]],
    make_trainer: Callable[..., Awaitable[Trainer]],
    make_user: Callable[..., Awaitable[object]],
) -> None:
    """D-34-08: paginated history ordered performed_at DESC, pageSize=10."""
    plan = await make_pt_package_plan(session_count=50)
    client = await make_client()
    pkg = await make_pt_package(client_id=client.id, plan=plan, sessions_remaining=50)
    trainer = await make_trainer()
    operator = await make_user(role="reception")

    base = datetime.now(UTC) - timedelta(days=30)
    for i in range(25):
        await _seed_pt_session(
            db_session,
            pt_package_id=pkg.id,
            trainer_id=trainer.id,
            client_id=client.id,
            performed_by_user_id=operator.id,  # type: ignore[attr-defined]
            trainer_name_snapshot=trainer.full_name,
            performed_at=base + timedelta(hours=i),
            created_at=base + timedelta(hours=i),
        )

    # Page 1.
    r1 = await authed_client_reception.get(
        f"/api/v1/pt-packages/{pkg.id}/sessions",
        params={"page": 1, "pageSize": 10},
    )
    assert r1.status_code == 200, r1.text
    body1 = r1.json()["data"]
    assert body1["total"] == 25
    assert body1["page"] == 1
    assert body1["pageSize"] == 10
    assert len(body1["items"]) == 10
    # DESC by performed_at — first item should have the LATEST timestamp.
    performed_ts = [item["performedAt"] for item in body1["items"]]
    assert performed_ts == sorted(performed_ts, reverse=True)

    # Page 2 → 10 more.
    r2 = await authed_client_reception.get(
        f"/api/v1/pt-packages/{pkg.id}/sessions",
        params={"page": 2, "pageSize": 10},
    )
    assert r2.status_code == 200
    assert len(r2.json()["data"]["items"]) == 10

    # Page 3 → remaining 5.
    r3 = await authed_client_reception.get(
        f"/api/v1/pt-packages/{pkg.id}/sessions",
        params={"page": 3, "pageSize": 10},
    )
    assert r3.status_code == 200
    body3 = r3.json()["data"]
    assert len(body3["items"]) == 5
    assert body3["total"] == 25


async def test_list_sessions_include_cancelled_filter(
    authed_client_reception: AsyncClient,
    db_session: AsyncSession,
    make_client: Callable[..., Awaitable[Client]],
    make_pt_package_plan: Callable[..., Awaitable[PtPackagePlan]],
    make_pt_package: Callable[..., Awaitable[PtPackage]],
    make_trainer: Callable[..., Awaitable[Trainer]],
    make_user: Callable[..., Awaitable[object]],
) -> None:
    """includeCancelled=false yields ACTIVE rows only; default (true) yields all."""
    plan = await make_pt_package_plan(session_count=20)
    client = await make_client()
    pkg = await make_pt_package(client_id=client.id, plan=plan, sessions_remaining=20)
    trainer = await make_trainer()
    operator = await make_user(role="reception")

    base = datetime.now(UTC) - timedelta(days=10)
    # 5 active.
    for i in range(5):
        await _seed_pt_session(
            db_session,
            pt_package_id=pkg.id,
            trainer_id=trainer.id,
            client_id=client.id,
            performed_by_user_id=operator.id,  # type: ignore[attr-defined]
            trainer_name_snapshot=trainer.full_name,
            performed_at=base + timedelta(hours=i),
            created_at=base + timedelta(hours=i),
        )
    # 5 cancelled.
    for i in range(5, 10):
        await _seed_pt_session(
            db_session,
            pt_package_id=pkg.id,
            trainer_id=trainer.id,
            client_id=client.id,
            performed_by_user_id=operator.id,  # type: ignore[attr-defined]
            trainer_name_snapshot=trainer.full_name,
            performed_at=base + timedelta(hours=i),
            created_at=base + timedelta(hours=i),
            cancelled_at=base + timedelta(hours=i, minutes=30),
            cancel_reason="seeded as cancelled",
        )

    # Default (no param) → include_cancelled=True → 10.
    r_all = await authed_client_reception.get(
        f"/api/v1/pt-packages/{pkg.id}/sessions",
        params={"pageSize": 20},
    )
    assert r_all.status_code == 200, r_all.text
    assert r_all.json()["data"]["total"] == 10
    assert len(r_all.json()["data"]["items"]) == 10

    # includeCancelled=false → 5 active only.
    r_active = await authed_client_reception.get(
        f"/api/v1/pt-packages/{pkg.id}/sessions",
        params={"pageSize": 20, "includeCancelled": "false"},
    )
    assert r_active.status_code == 200, r_active.text
    body = r_active.json()["data"]
    assert body["total"] == 5
    assert len(body["items"]) == 5
    assert all(item["cancelledAt"] is None for item in body["items"])


async def test_list_sessions_unknown_pt_package_returns_empty_page(
    authed_client_reception: AsyncClient,
) -> None:
    """Unknown pt_package_id → 200 + items=[], total=0 (no 404)."""
    r = await authed_client_reception.get(
        f"/api/v1/pt-packages/{uuid4()}/sessions",
        params={"page": 1, "pageSize": 10},
    )
    assert r.status_code == 200, r.text
    body = r.json()["data"]
    assert body["items"] == []
    assert body["total"] == 0
    assert body["page"] == 1
    assert body["pageSize"] == 10
