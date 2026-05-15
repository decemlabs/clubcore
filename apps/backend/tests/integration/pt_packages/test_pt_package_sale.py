"""Integration tests for POST /api/v1/pt-packages sale (Phase 33 PT-07).

Marquee paths (Plan 33-02 / D-33-09 / D-33-16 / D-33-17):
  - Happy path reception + owner (RBAC parity for sale: (CREATE, PT_PACKAGES)
    NOT in OWNER_ONLY per B-07).
  - validityDays=NULL plan → instance with end_date IS NULL (D-33-14).
  - 422 amount_mismatch (snapshot symmetry server-enforcement).
  - 404 pt_package_plan_not_found (archived plan; D-33-08 archive guard).
  - 409 active_pt_package_already_exists (defensive pre-check + DB partial
    UNIQUE final race gate).
  - Idempotency-Key replay (same body → same envelope); same key + different
    body → 422 idempotency_key_reuse (D-33-16 / D-32-10).
  - Missing X-CSRF-Token → 403 csrf_mismatch.
  - Missing Idempotency-Key → 422 idempotency_key_required.
  - Unauthenticated → 401.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any
from uuid import UUID, uuid4

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit_models import AuditLog
from app.modules.clients.models import Client
from app.modules.payments.models import Payment
from app.modules.pt_packages.models import PtPackage, PtPackagePlan


def _csrf_headers(client: AsyncClient, *, idempotency_key: str | None = None) -> dict[str, str]:
    headers: dict[str, str] = {
        "X-CSRF-Token": client.cookies.get("sportzal_csrf", "") or ""
    }
    if idempotency_key is not None:
        headers["Idempotency-Key"] = idempotency_key
    return headers


def _sale_body(client_id: UUID, plan_id: UUID, amount_kopecks: int) -> dict[str, Any]:
    return {
        "clientId": str(client_id),
        "planId": str(plan_id),
        "amountKopecks": amount_kopecks,
    }


async def test_create_pt_package_sale_happy_path_reception(
    authed_client_reception: AsyncClient,
    db_session: AsyncSession,
    make_client: Callable[..., Awaitable[Client]],
    make_pt_package_plan: Callable[..., Awaitable[PtPackagePlan]],
) -> None:
    """PT-07 happy path: 201 + envelope + pt_packages row + payments row + audit row."""
    plan = await make_pt_package_plan(
        name="reception-sale", session_count=10, price_kopecks=500000, validity_days=90
    )
    client = await make_client()

    idem = uuid4().hex
    r = await authed_client_reception.post(
        "/api/v1/pt-packages",
        json=_sale_body(client.id, plan.id, plan.price_kopecks),
        headers=_csrf_headers(authed_client_reception, idempotency_key=idem),
    )
    assert r.status_code == 201, r.text
    body = r.json()
    data = body["data"]

    new_id = UUID(data["id"])
    assert data["status"] == "active"
    assert data["sessionsRemaining"] == plan.session_count
    assert data["priceKopecksSnapshot"] == plan.price_kopecks
    assert data["planNameSnapshot"] == plan.name
    assert data["isActive"] is True
    assert data["startDate"] is not None
    assert data["endDate"] is not None

    # DB verification.
    pkg = await db_session.scalar(
        select(PtPackage).where(PtPackage.id == new_id)
    )
    assert pkg is not None
    assert pkg.status == "active"

    payments = (
        await db_session.scalars(
            select(Payment).where(
                Payment.subject_kind == "pt_package",
                Payment.subject_id == new_id,
                Payment.amount_kopecks > 0,
            )
        )
    ).all()
    assert len(payments) == 1
    assert payments[0].amount_kopecks == plan.price_kopecks

    audit_rows = (
        await db_session.scalars(
            select(AuditLog).where(
                AuditLog.action == "pt_package_sold",
                AuditLog.resource_id == new_id,
            )
        )
    ).all()
    assert len(audit_rows) == 1
    payload = audit_rows[0].payload
    assert set(payload.keys()) == {
        "pt_package_id",
        "client_id",
        "plan_id",
        "plan_name_snapshot",
        "session_count_snapshot",
        "price_kopecks_snapshot",
        "validity_days_snapshot",
        "start_date",
        "end_date",
        "payment_id",
    }
    assert payload["plan_name_snapshot"] == plan.name


async def test_create_pt_package_sale_happy_path_owner(
    authed_client_owner: AsyncClient,
    make_client: Callable[..., Awaitable[Client]],
    make_pt_package_plan: Callable[..., Awaitable[PtPackagePlan]],
) -> None:
    """Owner has equal access — (CREATE, PT_PACKAGES) NOT in OWNER_ONLY (B-07)."""
    plan = await make_pt_package_plan(name="owner-sale")
    client = await make_client()
    r = await authed_client_owner.post(
        "/api/v1/pt-packages",
        json=_sale_body(client.id, plan.id, plan.price_kopecks),
        headers=_csrf_headers(authed_client_owner, idempotency_key=uuid4().hex),
    )
    assert r.status_code == 201, r.text


async def test_create_pt_package_sale_validity_null_no_end_date(
    authed_client_owner: AsyncClient,
    make_client: Callable[..., Awaitable[Client]],
    make_pt_package_plan: Callable[..., Awaitable[PtPackagePlan]],
) -> None:
    """D-33-14: plan with validity_days NULL → instance with end_date NULL."""
    plan = await make_pt_package_plan(name="indef-pkg", validity_days=None)
    client = await make_client()
    r = await authed_client_owner.post(
        "/api/v1/pt-packages",
        json=_sale_body(client.id, plan.id, plan.price_kopecks),
        headers=_csrf_headers(authed_client_owner, idempotency_key=uuid4().hex),
    )
    assert r.status_code == 201, r.text
    assert r.json()["data"]["endDate"] is None
    assert r.json()["data"]["validityDaysSnapshot"] is None


async def test_create_pt_package_sale_amount_mismatch_422(
    authed_client_owner: AsyncClient,
    db_session: AsyncSession,
    make_client: Callable[..., Awaitable[Client]],
    make_pt_package_plan: Callable[..., Awaitable[PtPackagePlan]],
) -> None:
    """D-33-17: amountKopecks != plan.priceKopecks → 422 amount_mismatch (no side effects)."""
    plan = await make_pt_package_plan(name="mismatch", price_kopecks=500000)
    client = await make_client()
    r = await authed_client_owner.post(
        "/api/v1/pt-packages",
        json=_sale_body(client.id, plan.id, plan.price_kopecks + 1),
        headers=_csrf_headers(authed_client_owner, idempotency_key=uuid4().hex),
    )
    assert r.status_code == 422, r.text
    err = r.json()
    assert err["code"] == "amount_mismatch"

    # No pt_packages row, no payments row, no audit row.
    rows = (
        await db_session.scalars(
            select(PtPackage).where(PtPackage.client_id == client.id)
        )
    ).all()
    assert len(rows) == 0
    payment_rows = (
        await db_session.scalars(
            select(Payment).where(Payment.subject_kind == "pt_package")
        )
    ).all()
    assert len(payment_rows) == 0


async def test_create_pt_package_sale_archived_plan_404(
    authed_client_owner: AsyncClient,
    db_session: AsyncSession,
    make_client: Callable[..., Awaitable[Client]],
    make_pt_package_plan: Callable[..., Awaitable[PtPackagePlan]],
) -> None:
    """D-33-08 archive guard: sale on archived plan → 404 pt_package_plan_not_found."""
    plan = await make_pt_package_plan(name="archived-plan")
    # Soft-delete the plan directly via DB.
    from datetime import UTC, datetime
    plan.deleted_at = datetime.now(tz=UTC)
    db_session.add(plan)
    await db_session.commit()

    client = await make_client()
    r = await authed_client_owner.post(
        "/api/v1/pt-packages",
        json=_sale_body(client.id, plan.id, plan.price_kopecks),
        headers=_csrf_headers(authed_client_owner, idempotency_key=uuid4().hex),
    )
    assert r.status_code == 404, r.text
    assert r.json()["code"] == "pt_package_plan_not_found"


async def test_create_pt_package_sale_active_already_exists_pre_check_409(
    authed_client_owner: AsyncClient,
    make_client: Callable[..., Awaitable[Client]],
    make_pt_package_plan: Callable[..., Awaitable[PtPackagePlan]],
) -> None:
    """D-33-09 active-per-client invariant: 2nd sale for same client → 409 (pre-check)."""
    plan = await make_pt_package_plan(name="dup-sale")
    client = await make_client()

    r1 = await authed_client_owner.post(
        "/api/v1/pt-packages",
        json=_sale_body(client.id, plan.id, plan.price_kopecks),
        headers=_csrf_headers(authed_client_owner, idempotency_key=uuid4().hex),
    )
    assert r1.status_code == 201, r1.text

    r2 = await authed_client_owner.post(
        "/api/v1/pt-packages",
        json=_sale_body(client.id, plan.id, plan.price_kopecks),
        headers=_csrf_headers(authed_client_owner, idempotency_key=uuid4().hex),
    )
    assert r2.status_code == 409, r2.text
    assert r2.json()["code"] == "active_pt_package_already_exists"


async def test_create_pt_package_sale_idempotency_key_replay(
    authed_client_owner: AsyncClient,
    db_session: AsyncSession,
    make_client: Callable[..., Awaitable[Client]],
    make_pt_package_plan: Callable[..., Awaitable[PtPackagePlan]],
) -> None:
    """D-33-16 / D-32-10: same Idempotency-Key + same body → cached envelope replay.

    Same key + different body → 422 idempotency_key_reuse.
    """
    plan = await make_pt_package_plan(name="idem-replay")
    client = await make_client()
    idem = uuid4().hex

    body = _sale_body(client.id, plan.id, plan.price_kopecks)
    r1 = await authed_client_owner.post(
        "/api/v1/pt-packages",
        json=body,
        headers=_csrf_headers(authed_client_owner, idempotency_key=idem),
    )
    assert r1.status_code == 201, r1.text
    new_id = r1.json()["data"]["id"]

    # Replay with same key + same body → cached envelope (same id).
    r2 = await authed_client_owner.post(
        "/api/v1/pt-packages",
        json=body,
        headers=_csrf_headers(authed_client_owner, idempotency_key=idem),
    )
    assert r2.status_code == 201, r2.text
    assert r2.json()["data"]["id"] == new_id

    # Only 1 pt_packages row + 1 payments row.
    pkgs = (
        await db_session.scalars(
            select(PtPackage).where(PtPackage.client_id == client.id)
        )
    ).all()
    assert len(pkgs) == 1

    # Same key + DIFFERENT body → 422 idempotency_key_reuse.
    body_diff = {**body, "amountKopecks": body["amountKopecks"] + 1}
    r3 = await authed_client_owner.post(
        "/api/v1/pt-packages",
        json=body_diff,
        headers=_csrf_headers(authed_client_owner, idempotency_key=idem),
    )
    assert r3.status_code == 422, r3.text
    assert r3.json()["code"] == "idempotency_key_reuse"


async def test_create_pt_package_sale_missing_idempotency_key_422(
    authed_client_owner: AsyncClient,
    make_client: Callable[..., Awaitable[Client]],
    make_pt_package_plan: Callable[..., Awaitable[PtPackagePlan]],
) -> None:
    """D-33-16: missing Idempotency-Key header → 422 idempotency_key_required."""
    plan = await make_pt_package_plan(name="no-idem")
    client = await make_client()
    r = await authed_client_owner.post(
        "/api/v1/pt-packages",
        json=_sale_body(client.id, plan.id, plan.price_kopecks),
        headers=_csrf_headers(authed_client_owner, idempotency_key=None),
    )
    assert r.status_code == 422, r.text
    assert r.json()["code"] == "idempotency_key_required"


async def test_create_pt_package_sale_missing_csrf_403(
    authed_client_owner: AsyncClient,
    make_client: Callable[..., Awaitable[Client]],
    make_pt_package_plan: Callable[..., Awaitable[PtPackagePlan]],
) -> None:
    """Missing X-CSRF-Token → 403 csrf_mismatch (RBAC-04 ordering invariant)."""
    plan = await make_pt_package_plan(name="no-csrf")
    client = await make_client()
    r = await authed_client_owner.post(
        "/api/v1/pt-packages",
        json=_sale_body(client.id, plan.id, plan.price_kopecks),
        headers={"Idempotency-Key": uuid4().hex},  # NO X-CSRF-Token
    )
    assert r.status_code == 403, r.text
    assert r.json()["code"] == "csrf_mismatch"


async def test_create_pt_package_sale_unauthenticated_401(
    app: Any,
    make_pt_package_plan: Callable[..., Awaitable[PtPackagePlan]],
    make_client: Callable[..., Awaitable[Client]],
) -> None:
    """Unauthenticated POST → 401 (no sz_access cookie)."""
    from httpx import ASGITransport

    plan = await make_pt_package_plan(name="unauthed")
    client = await make_client()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as anon:
        r = await anon.post(
            "/api/v1/pt-packages",
            json=_sale_body(client.id, plan.id, plan.price_kopecks),
            headers={
                "Idempotency-Key": uuid4().hex,
                "X-CSRF-Token": "irrelevant",
            },
        )
    assert r.status_code == 401, r.text
