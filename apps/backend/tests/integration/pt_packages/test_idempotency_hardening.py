"""Phase 66 Plan 66-05 — IDM-03 integration tests for pt_packages category-A endpoints.

Asserts the hardened idempotency behavior (real Postgres + real Redis) for:
  - POST /api/v1/pt-packages          (create_pt_package, A)
  - POST /api/v1/pt-packages/{id}/cancel (cancel_pt_package, A)
  - POST /api/v1/pt-packages/{id}/refund (refund_pt_package, A)

Assertions per endpoint:
  1. Replay (same key + same body) returns byte-identical cached response.
  2. Replay does NOT re-emit AuditLog rows for the subject (pt_package_id / payment_id).
  3. Same key + different body → 422 idempotency_key_reuse.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from uuid import UUID, uuid4

from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit_models import AuditLog
from app.modules.clients.models import Client
from app.modules.pt_packages.models import PtPackage, PtPackagePlan

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _csrf_header(client: AsyncClient) -> str:
    return client.cookies.get("clubcore_csrf") or ""


def _headers(client: AsyncClient, *, key: str) -> dict[str, str]:
    return {
        "X-CSRF-Token": _csrf_header(client),
        "Idempotency-Key": key,
    }


async def _audit_count(session: AsyncSession, resource_id: UUID) -> int:
    """Count AuditLog rows for a given resource_id."""
    result = await session.execute(
        select(func.count()).select_from(AuditLog).where(AuditLog.resource_id == resource_id)
    )
    return int(result.scalar_one())


async def _sell_pt_package(
    authed: AsyncClient,
    *,
    client_id: UUID,
    plan: PtPackagePlan,
) -> UUID:
    """Sell a PT-package via HTTP; return the pt_package_id."""
    r = await authed.post(
        "/api/v1/pt-packages",
        json={
            "clientId": str(client_id),
            "planId": str(plan.id),
            "amountKopecks": plan.price_kopecks,
        },
        headers=_headers(authed, key=uuid4().hex),
    )
    assert r.status_code == 201, r.text
    return UUID(r.json()["data"]["id"])


# ===========================================================================
# create_pt_package — double-submit + no-re-emit-audit + reuse-422
# ===========================================================================


async def test_create_pt_package_double_submit_byte_identical(
    authed_client_owner: AsyncClient,
    db_session: AsyncSession,
    make_client: Callable[..., Awaitable[Client]],
    make_pt_package_plan: Callable[..., Awaitable[PtPackagePlan]],
) -> None:
    """Replay of create_pt_package returns byte-identical cached response."""
    plan = await make_pt_package_plan()
    client_row = await make_client()
    key = uuid4().hex  # 32 chars, passes {16,128}

    body_json = {
        "clientId": str(client_row.id),
        "planId": str(plan.id),
        "amountKopecks": plan.price_kopecks,
    }
    headers = _headers(authed_client_owner, key=key)

    r1 = await authed_client_owner.post("/api/v1/pt-packages", json=body_json, headers=headers)
    assert r1.status_code == 201, r1.text

    r2 = await authed_client_owner.post("/api/v1/pt-packages", json=body_json, headers=headers)
    assert r2.status_code == 201, r2.text
    assert r2.content == r1.content, "Replay must return byte-identical content"


async def test_create_pt_package_replay_no_re_emit_audit(
    authed_client_owner: AsyncClient,
    db_session: AsyncSession,
    make_client: Callable[..., Awaitable[Client]],
    make_pt_package_plan: Callable[..., Awaitable[PtPackagePlan]],
) -> None:
    """Replay of create_pt_package does NOT re-emit AuditLog rows."""
    plan = await make_pt_package_plan()
    client_row = await make_client()
    key = uuid4().hex

    body_json = {
        "clientId": str(client_row.id),
        "planId": str(plan.id),
        "amountKopecks": plan.price_kopecks,
    }
    headers = _headers(authed_client_owner, key=key)

    r1 = await authed_client_owner.post("/api/v1/pt-packages", json=body_json, headers=headers)
    assert r1.status_code == 201, r1.text
    pt_package_id = UUID(r1.json()["data"]["id"])

    count_before = await _audit_count(db_session, pt_package_id)
    assert count_before >= 1, "At least one audit row expected after first submit"

    r2 = await authed_client_owner.post("/api/v1/pt-packages", json=body_json, headers=headers)
    assert r2.status_code == 201, r2.text

    count_after = await _audit_count(db_session, pt_package_id)
    assert count_after == count_before, (
        f"Replay must NOT re-emit audit: before={count_before}, after={count_after}"
    )


async def test_create_pt_package_same_key_different_body_422(
    authed_client_owner: AsyncClient,
    db_session: AsyncSession,
    make_client: Callable[..., Awaitable[Client]],
    make_pt_package_plan: Callable[..., Awaitable[PtPackagePlan]],
) -> None:
    """Same key + different body → 422 idempotency_key_reuse."""
    plan_a = await make_pt_package_plan(name="PT-IDM-A")
    plan_b = await make_pt_package_plan(name="PT-IDM-B")
    client_row = await make_client()
    key = uuid4().hex

    headers = _headers(authed_client_owner, key=key)

    r1 = await authed_client_owner.post(
        "/api/v1/pt-packages",
        json={
            "clientId": str(client_row.id),
            "planId": str(plan_a.id),
            "amountKopecks": plan_a.price_kopecks,
        },
        headers=headers,
    )
    assert r1.status_code == 201, r1.text

    r2 = await authed_client_owner.post(
        "/api/v1/pt-packages",
        json={
            "clientId": str(client_row.id),
            "planId": str(plan_b.id),  # different plan → different body
            "amountKopecks": plan_b.price_kopecks,
        },
        headers=headers,
    )
    assert r2.status_code == 422, r2.text
    body = r2.json()
    assert body["code"] == "validation_error"
    assert body["message"] == "idempotency_key_reuse"


# ===========================================================================
# cancel_pt_package — double-submit + no-re-emit-audit + reuse-422
# ===========================================================================


async def test_cancel_pt_package_double_submit_byte_identical(
    authed_client_owner: AsyncClient,
    db_session: AsyncSession,
    make_client: Callable[..., Awaitable[Client]],
    make_pt_package_plan: Callable[..., Awaitable[PtPackagePlan]],
    make_pt_package: Callable[..., Awaitable[PtPackage]],
) -> None:
    """Replay of cancel_pt_package returns byte-identical cached response."""
    plan = await make_pt_package_plan()
    client_row = await make_client()
    pkg = await make_pt_package(client_id=client_row.id, plan=plan, status="active")
    key = uuid4().hex

    body_json = {"reason": "client_request_idm_test"}
    headers = _headers(authed_client_owner, key=key)

    r1 = await authed_client_owner.post(
        f"/api/v1/pt-packages/{pkg.id}/cancel",
        json=body_json,
        headers=headers,
    )
    assert r1.status_code == 200, r1.text

    r2 = await authed_client_owner.post(
        f"/api/v1/pt-packages/{pkg.id}/cancel",
        json=body_json,
        headers=headers,
    )
    assert r2.status_code == 200, r2.text
    assert r2.content == r1.content, "Replay must return byte-identical content"


async def test_cancel_pt_package_replay_no_re_emit_audit(
    authed_client_owner: AsyncClient,
    db_session: AsyncSession,
    make_client: Callable[..., Awaitable[Client]],
    make_pt_package_plan: Callable[..., Awaitable[PtPackagePlan]],
    make_pt_package: Callable[..., Awaitable[PtPackage]],
) -> None:
    """Replay of cancel_pt_package does NOT re-emit AuditLog row."""
    plan = await make_pt_package_plan()
    client_row = await make_client()
    pkg = await make_pt_package(client_id=client_row.id, plan=plan, status="active")
    key = uuid4().hex

    body_json = {"reason": "audit_count_check"}
    headers = _headers(authed_client_owner, key=key)

    r1 = await authed_client_owner.post(
        f"/api/v1/pt-packages/{pkg.id}/cancel",
        json=body_json,
        headers=headers,
    )
    assert r1.status_code == 200, r1.text

    count_before = await _audit_count(db_session, pkg.id)
    assert count_before >= 1

    r2 = await authed_client_owner.post(
        f"/api/v1/pt-packages/{pkg.id}/cancel",
        json=body_json,
        headers=headers,
    )
    assert r2.status_code == 200, r2.text

    count_after = await _audit_count(db_session, pkg.id)
    assert count_after == count_before, (
        f"Replay must NOT re-emit audit: before={count_before}, after={count_after}"
    )


async def test_cancel_pt_package_same_key_different_body_422(
    authed_client_owner: AsyncClient,
    db_session: AsyncSession,
    make_client: Callable[..., Awaitable[Client]],
    make_pt_package_plan: Callable[..., Awaitable[PtPackagePlan]],
    make_pt_package: Callable[..., Awaitable[PtPackage]],
) -> None:
    """Same key + different cancel body → 422 idempotency_key_reuse."""
    plan = await make_pt_package_plan()
    client_row = await make_client()
    pkg = await make_pt_package(client_id=client_row.id, plan=plan, status="active")
    key = uuid4().hex

    headers = _headers(authed_client_owner, key=key)

    r1 = await authed_client_owner.post(
        f"/api/v1/pt-packages/{pkg.id}/cancel",
        json={"reason": "reason_alpha"},
        headers=headers,
    )
    assert r1.status_code == 200, r1.text

    r2 = await authed_client_owner.post(
        f"/api/v1/pt-packages/{pkg.id}/cancel",
        json={"reason": "reason_beta"},  # different body
        headers=headers,
    )
    assert r2.status_code == 422, r2.text
    body = r2.json()
    assert body["code"] == "validation_error"
    assert body["message"] == "idempotency_key_reuse"


# ===========================================================================
# refund_pt_package — double-submit + no-re-emit-audit + reuse-422
# ===========================================================================


async def test_refund_pt_package_double_submit_byte_identical(
    authed_client_owner: AsyncClient,
    db_session: AsyncSession,
    make_client: Callable[..., Awaitable[Client]],
    make_pt_package_plan: Callable[..., Awaitable[PtPackagePlan]],
) -> None:
    """Replay of refund_pt_package returns byte-identical cached response."""
    plan = await make_pt_package_plan()
    client_row = await make_client()
    # Sell first via HTTP (creates payment row + audit)
    pt_package_id = await _sell_pt_package(authed_client_owner, client_id=client_row.id, plan=plan)

    key = uuid4().hex
    body_json = {"reason": "refund_idem_test"}
    headers = _headers(authed_client_owner, key=key)

    r1 = await authed_client_owner.post(
        f"/api/v1/pt-packages/{pt_package_id}/refund",
        json=body_json,
        headers=headers,
    )
    assert r1.status_code == 200, r1.text

    r2 = await authed_client_owner.post(
        f"/api/v1/pt-packages/{pt_package_id}/refund",
        json=body_json,
        headers=headers,
    )
    assert r2.status_code == 200, r2.text
    assert r2.content == r1.content, "Replay must return byte-identical content"


async def test_refund_pt_package_replay_no_re_emit_audit(
    authed_client_owner: AsyncClient,
    db_session: AsyncSession,
    make_client: Callable[..., Awaitable[Client]],
    make_pt_package_plan: Callable[..., Awaitable[PtPackagePlan]],
) -> None:
    """Replay of refund_pt_package does NOT re-emit AuditLog row for the package."""
    plan = await make_pt_package_plan()
    client_row = await make_client()
    pt_package_id = await _sell_pt_package(authed_client_owner, client_id=client_row.id, plan=plan)

    key = uuid4().hex
    body_json = {"reason": "refund_audit_count"}
    headers = _headers(authed_client_owner, key=key)

    r1 = await authed_client_owner.post(
        f"/api/v1/pt-packages/{pt_package_id}/refund",
        json=body_json,
        headers=headers,
    )
    assert r1.status_code == 200, r1.text

    count_before = await _audit_count(db_session, pt_package_id)
    assert count_before >= 1

    r2 = await authed_client_owner.post(
        f"/api/v1/pt-packages/{pt_package_id}/refund",
        json=body_json,
        headers=headers,
    )
    assert r2.status_code == 200, r2.text

    count_after = await _audit_count(db_session, pt_package_id)
    assert count_after == count_before, (
        f"Replay must NOT re-emit audit: before={count_before}, after={count_after}"
    )


async def test_refund_pt_package_same_key_different_body_422(
    authed_client_owner: AsyncClient,
    db_session: AsyncSession,
    make_client: Callable[..., Awaitable[Client]],
    make_pt_package_plan: Callable[..., Awaitable[PtPackagePlan]],
) -> None:
    """Same key + different refund body → 422 idempotency_key_reuse."""
    plan = await make_pt_package_plan()
    client_row = await make_client()
    pt_package_id = await _sell_pt_package(authed_client_owner, client_id=client_row.id, plan=plan)

    key = uuid4().hex
    headers = _headers(authed_client_owner, key=key)

    r1 = await authed_client_owner.post(
        f"/api/v1/pt-packages/{pt_package_id}/refund",
        json={"reason": "refund_reason_a"},
        headers=headers,
    )
    assert r1.status_code == 200, r1.text

    r2 = await authed_client_owner.post(
        f"/api/v1/pt-packages/{pt_package_id}/refund",
        json={"reason": "refund_reason_b"},  # different body
        headers=headers,
    )
    assert r2.status_code == 422, r2.text
    body = r2.json()
    assert body["code"] == "validation_error"
    assert body["message"] == "idempotency_key_reuse"
