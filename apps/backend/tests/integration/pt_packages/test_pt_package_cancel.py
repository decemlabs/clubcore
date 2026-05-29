"""Integration tests for POST /api/v1/pt-packages/{id}/cancel (Phase 33 PT-08).

D-33-10 cancel-without-refund flow:
  - Owner-only via (CANCEL, PT_PACKAGES) in OWNER_ONLY (Phase 30 INFRA-19).
  - CSRF + Idempotency-Key required per D-33-16.
  - Free-text cancellation_reason (NOT 'refunded' sentinel — that is reserved
    for refund flow per D-33-08).
  - audit emit pt_package_cancelled with 4-key payload (prior_status added
    in Plan 33-03 additive PtPackageCancelledPayload extension).
  - NO payment ledger touch (distinct from refund per D-33-10).
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any
from uuid import uuid4

from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit_models import AuditLog
from app.modules.clients.models import Client
from app.modules.payments.models import Payment
from app.modules.pt_packages.models import PtPackage, PtPackagePlan


def _csrf_headers(client: AsyncClient, *, idempotency_key: str | None = None) -> dict[str, str]:
    headers: dict[str, str] = {"X-CSRF-Token": client.cookies.get("clubcore_csrf", "") or ""}
    if idempotency_key is not None:
        headers["Idempotency-Key"] = idempotency_key
    return headers


async def test_cancel_pt_package_active_owner_happy_path(
    authed_client_owner: AsyncClient,
    db_session: AsyncSession,
    make_client: Callable[..., Awaitable[Client]],
    make_pt_package_plan: Callable[..., Awaitable[PtPackagePlan]],
    make_pt_package: Callable[..., Awaitable[PtPackage]],
) -> None:
    """PT-08 happy path from active source → 200 cancelled + free-text reason + audit row."""
    plan = await make_pt_package_plan(name="cancel-active")
    client = await make_client()
    pkg = await make_pt_package(client_id=client.id, plan=plan, status="active")
    r = await authed_client_owner.post(
        f"/api/v1/pt-packages/{pkg.id}/cancel",
        json={"reason": "client_request"},
        headers=_csrf_headers(authed_client_owner, idempotency_key=uuid4().hex),
    )
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert data["status"] == "cancelled"
    assert data["cancellationReason"] == "client_request"  # NOT 'refunded'
    assert data["isActive"] is False

    # DB invariant.
    await db_session.refresh(pkg)
    assert pkg.status == "cancelled"
    assert pkg.cancellation_reason == "client_request"

    # Audit row.
    audit_rows = (
        await db_session.scalars(
            select(AuditLog).where(
                AuditLog.action == "pt_package_cancelled",
                AuditLog.resource_id == pkg.id,
            )
        )
    ).all()
    assert len(audit_rows) == 1
    payload = audit_rows[0].payload
    assert set(payload.keys()) == {
        "pt_package_id",
        "client_id",
        "cancellation_reason",
        "prior_status",
    }
    assert payload["cancellation_reason"] == "client_request"
    assert payload["prior_status"] == "active"

    # No payment ledger touch — cancel does NOT insert refund rows.
    refund_count = await db_session.scalar(
        select(func.count())
        .select_from(Payment)
        .where(
            Payment.subject_kind == "refund",
            Payment.subject_id == pkg.id,
        )
    )
    assert refund_count == 0


async def test_cancel_pt_package_exhausted_owner_happy_path(
    authed_client_owner: AsyncClient,
    db_session: AsyncSession,
    make_client: Callable[..., Awaitable[Client]],
    make_pt_package_plan: Callable[..., Awaitable[PtPackagePlan]],
    make_pt_package: Callable[..., Awaitable[PtPackage]],
) -> None:
    """D-33-04 exhausted → cancelled allowed; audit payload.prior_status='exhausted'."""
    plan = await make_pt_package_plan(name="cancel-exhausted")
    client = await make_client()
    pkg = await make_pt_package(
        client_id=client.id, plan=plan, status="exhausted", sessions_remaining=0
    )
    r = await authed_client_owner.post(
        f"/api/v1/pt-packages/{pkg.id}/cancel",
        json={"reason": "operator_correction"},
        headers=_csrf_headers(authed_client_owner, idempotency_key=uuid4().hex),
    )
    assert r.status_code == 200, r.text
    assert r.json()["data"]["status"] == "cancelled"

    audit_rows = (
        await db_session.scalars(
            select(AuditLog).where(
                AuditLog.action == "pt_package_cancelled",
                AuditLog.resource_id == pkg.id,
            )
        )
    ).all()
    assert len(audit_rows) == 1
    assert audit_rows[0].payload["prior_status"] == "exhausted"


async def test_cancel_pt_package_expired_owner_happy_path(
    authed_client_owner: AsyncClient,
    db_session: AsyncSession,
    make_client: Callable[..., Awaitable[Client]],
    make_pt_package_plan: Callable[..., Awaitable[PtPackagePlan]],
    make_pt_package: Callable[..., Awaitable[PtPackage]],
) -> None:
    """D-33-04 expired → cancelled allowed; audit payload.prior_status='expired'."""
    plan = await make_pt_package_plan(name="cancel-expired")
    client = await make_client()
    pkg = await make_pt_package(client_id=client.id, plan=plan, status="expired")
    r = await authed_client_owner.post(
        f"/api/v1/pt-packages/{pkg.id}/cancel",
        json={"reason": "lifecycle_complete"},
        headers=_csrf_headers(authed_client_owner, idempotency_key=uuid4().hex),
    )
    assert r.status_code == 200, r.text

    audit_rows = (
        await db_session.scalars(
            select(AuditLog).where(
                AuditLog.action == "pt_package_cancelled",
                AuditLog.resource_id == pkg.id,
            )
        )
    ).all()
    assert len(audit_rows) == 1
    assert audit_rows[0].payload["prior_status"] == "expired"


async def test_cancel_pt_package_reception_403(
    authed_client_reception: AsyncClient,
    db_session: AsyncSession,
    make_client: Callable[..., Awaitable[Client]],
    make_pt_package_plan: Callable[..., Awaitable[PtPackagePlan]],
    make_pt_package: Callable[..., Awaitable[PtPackage]],
) -> None:
    """(CANCEL, PT_PACKAGES) ∈ OWNER_ONLY → reception denied 403; no side effects."""
    plan = await make_pt_package_plan(name="cancel-reception")
    client = await make_client()
    pkg = await make_pt_package(client_id=client.id, plan=plan, status="active")
    r = await authed_client_reception.post(
        f"/api/v1/pt-packages/{pkg.id}/cancel",
        json={"reason": "should_not_succeed"},
        headers=_csrf_headers(authed_client_reception, idempotency_key=uuid4().hex),
    )
    assert r.status_code == 403, r.text

    # DB unchanged.
    await db_session.refresh(pkg)
    assert pkg.status == "active"
    assert pkg.cancellation_reason is None

    # No audit emit.
    audit_count = await db_session.scalar(
        select(func.count())
        .select_from(AuditLog)
        .where(
            AuditLog.action == "pt_package_cancelled",
            AuditLog.resource_id == pkg.id,
        )
    )
    assert audit_count == 0


async def test_cancel_pt_package_missing_404(
    authed_client_owner: AsyncClient,
) -> None:
    """Random UUID → 404 pt_package_not_found."""
    r = await authed_client_owner.post(
        f"/api/v1/pt-packages/{uuid4()}/cancel",
        json={"reason": "missing"},
        headers=_csrf_headers(authed_client_owner, idempotency_key=uuid4().hex),
    )
    assert r.status_code == 404, r.text
    assert r.json()["code"] == "pt_package_not_found"


async def test_cancel_pt_package_already_cancelled_409(
    authed_client_owner: AsyncClient,
    db_session: AsyncSession,
    make_client: Callable[..., Awaitable[Client]],
    make_pt_package_plan: Callable[..., Awaitable[PtPackagePlan]],
    make_pt_package: Callable[..., Awaitable[PtPackage]],
) -> None:
    """D-33-04: cancelled source → 409 invalid_transition with discriminator fields."""
    plan = await make_pt_package_plan(name="cancel-already")
    client = await make_client()
    pkg = await make_pt_package(
        client_id=client.id,
        plan=plan,
        status="cancelled",
    )
    r = await authed_client_owner.post(
        f"/api/v1/pt-packages/{pkg.id}/cancel",
        json={"reason": "second_attempt"},
        headers=_csrf_headers(authed_client_owner, idempotency_key=uuid4().hex),
    )
    assert r.status_code == 409, r.text
    body = r.json()
    assert body["code"] == "invalid_transition"
    assert body.get("fields") == {
        "from_status": "cancelled",
        "to_status": "cancelled",
    }


async def test_cancel_pt_package_no_csrf_403(
    authed_client_owner: AsyncClient,
    make_client: Callable[..., Awaitable[Client]],
    make_pt_package_plan: Callable[..., Awaitable[PtPackagePlan]],
    make_pt_package: Callable[..., Awaitable[PtPackage]],
) -> None:
    """Missing X-CSRF-Token → CSRF gate denial (verify_csrf middleware)."""
    plan = await make_pt_package_plan(name="cancel-no-csrf")
    client = await make_client()
    pkg = await make_pt_package(client_id=client.id, plan=plan, status="active")
    r = await authed_client_owner.post(
        f"/api/v1/pt-packages/{pkg.id}/cancel",
        json={"reason": "no_csrf"},
        headers={"Idempotency-Key": uuid4().hex},  # no X-CSRF-Token
    )
    # CSRF failures return 403 in Sportzal (Phase 4 RBAC-04).
    assert r.status_code == 403, r.text


async def test_cancel_pt_package_extra_field_422(
    authed_client_owner: AsyncClient,
    make_client: Callable[..., Awaitable[Client]],
    make_pt_package_plan: Callable[..., Awaitable[PtPackagePlan]],
    make_pt_package: Callable[..., Awaitable[PtPackage]],
) -> None:
    """BackendSchemaBase extra='forbid' → 422 on unknown body field."""
    plan = await make_pt_package_plan(name="cancel-extra")
    client = await make_client()
    pkg = await make_pt_package(client_id=client.id, plan=plan, status="active")
    r = await authed_client_owner.post(
        f"/api/v1/pt-packages/{pkg.id}/cancel",
        json={"reason": "ok", "foo": "bar"},
        headers=_csrf_headers(authed_client_owner, idempotency_key=uuid4().hex),
    )
    assert r.status_code == 422, r.text


async def test_cancel_pt_package_reason_empty_422(
    authed_client_owner: AsyncClient,
    make_client: Callable[..., Awaitable[Client]],
    make_pt_package_plan: Callable[..., Awaitable[PtPackagePlan]],
    make_pt_package: Callable[..., Awaitable[PtPackage]],
) -> None:
    """Field(min_length=1) → 422 on empty reason."""
    plan = await make_pt_package_plan(name="cancel-empty")
    client = await make_client()
    pkg = await make_pt_package(client_id=client.id, plan=plan, status="active")
    r = await authed_client_owner.post(
        f"/api/v1/pt-packages/{pkg.id}/cancel",
        json={"reason": ""},
        headers=_csrf_headers(authed_client_owner, idempotency_key=uuid4().hex),
    )
    assert r.status_code == 422, r.text


async def test_cancel_pt_package_reason_too_long_422(
    authed_client_owner: AsyncClient,
    make_client: Callable[..., Awaitable[Client]],
    make_pt_package_plan: Callable[..., Awaitable[PtPackagePlan]],
    make_pt_package: Callable[..., Awaitable[PtPackage]],
) -> None:
    """Field(max_length=200) → 422 on reason >200 chars."""
    plan = await make_pt_package_plan(name="cancel-long")
    client = await make_client()
    pkg = await make_pt_package(client_id=client.id, plan=plan, status="active")
    r = await authed_client_owner.post(
        f"/api/v1/pt-packages/{pkg.id}/cancel",
        json={"reason": "x" * 201},
        headers=_csrf_headers(authed_client_owner, idempotency_key=uuid4().hex),
    )
    assert r.status_code == 422, r.text


async def test_cancel_pt_package_idempotency_replay(
    authed_client_owner: AsyncClient,
    db_session: AsyncSession,
    make_client: Callable[..., Awaitable[Client]],
    make_pt_package_plan: Callable[..., Awaitable[PtPackagePlan]],
    make_pt_package: Callable[..., Awaitable[PtPackage]],
) -> None:
    """D-33-16 idempotency replay: same key + same body → cached envelope, NO duplicate audit."""
    plan = await make_pt_package_plan(name="cancel-idem")
    client = await make_client()
    pkg = await make_pt_package(client_id=client.id, plan=plan, status="active")
    idem = uuid4().hex
    body: dict[str, Any] = {"reason": "replay_test"}

    r1 = await authed_client_owner.post(
        f"/api/v1/pt-packages/{pkg.id}/cancel",
        json=body,
        headers=_csrf_headers(authed_client_owner, idempotency_key=idem),
    )
    assert r1.status_code == 200, r1.text

    # Same key + same body → cached envelope replay.
    r2 = await authed_client_owner.post(
        f"/api/v1/pt-packages/{pkg.id}/cancel",
        json=body,
        headers=_csrf_headers(authed_client_owner, idempotency_key=idem),
    )
    assert r2.status_code == 200, r2.text
    assert r1.json() == r2.json()

    # Exactly 1 audit emit (replay must NOT double-emit).
    audit_count = await db_session.scalar(
        select(func.count())
        .select_from(AuditLog)
        .where(
            AuditLog.action == "pt_package_cancelled",
            AuditLog.resource_id == pkg.id,
        )
    )
    assert audit_count == 1
