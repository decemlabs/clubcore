"""Phase 26 MEM-REN-TEST-03 — rejection paths (parts A + B).

Locks the two 409 rejection branches on POST /renew:

  Part A — archived plan: source's plan is soft-deleted (deleted_at IS NOT NULL).
    Service.renew_membership classifies via repository.get_plan_for_renewal
    returning (plan, is_archived=True) → raises PlanArchivedError → 409
    body code='plan_archived'. Operator must sell a NEW membership using a
    current alive plan instead.

  Part B — cancelled source: source.status == 'cancelled'. Service raises
    CannotRenewCancelledError → 409 body code='cannot_renew_cancelled'.
    Cancellation is terminal/intentional revocation; renewal would mask the
    cancellation intent.

Both rejection paths MUST be side-effect-free:
  - NO new membership row created (count_for_client unchanged).
  - NO `membership_renewed` audit row written.

Response body shape per `register_exception_handlers` contract:
    {"code": "<ErrorClass.code>", "message": "<error message>", "fields": ...}

Analog: tests/integration/memberships/test_freeze_endpoints.py (409 envelope
shape) + tests/integration/memberships/test_plan_in_use.py (plan archive
flow).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit_models import AuditLog
from app.modules.memberships.models import Membership


def _csrf_headers(client: AsyncClient) -> dict[str, str]:
    # Phase 66 IDM-07: renew_membership now requires Idempotency-Key.
    return {
        "X-CSRF-Token": client.cookies.get("sportzal_csrf") or "",
        "Idempotency-Key": uuid4().hex,
    }


VALID_CLIENT: dict[str, Any] = {
    "lastName": "Иванов",
    "firstName": "Иван",
    "phone": "+79991239030",
}


async def _create_client(authed: AsyncClient, **overrides: Any) -> dict[str, Any]:
    payload = {**VALID_CLIENT, **overrides}
    r = await authed.post(
        "/api/v1/clients",
        json=payload,
        headers=_csrf_headers(authed),
    )
    assert r.status_code == 201, r.text
    data: dict[str, Any] = r.json()["data"]
    return data


async def _count_memberships_for_client(db_session: AsyncSession, client_id: UUID) -> int:
    """Count memberships owned by client_id (used to prove no-side-effect on reject)."""
    return (
        await db_session.scalar(
            select(func.count()).select_from(Membership).where(Membership.client_id == client_id)
        )
    ) or 0


async def _count_renewal_audit_rows_for_source(db_session: AsyncSession, source_id: UUID) -> int:
    """Count `membership_renewed` audit rows whose payload references this source.

    Audit row's `resource_id` is the NEW membership id (D-26-15); the
    forensic back-pointer to source lives in `payload->>'source_membership_id'`.
    A successful POST /renew writes exactly one row matching this filter; a
    rejected POST writes zero.
    """
    rows = (
        await db_session.scalars(select(AuditLog).where(AuditLog.action == "membership_renewed"))
    ).all()
    return sum(1 for r in rows if r.payload.get("source_membership_id") == str(source_id))


async def test_renew_archived_plan_returns_plan_archived_409(
    authed_client_owner: AsyncClient,
    db_session: AsyncSession,
    make_plan: Any,
    make_membership: Any,
) -> None:
    """MEM-REN-TEST-03 part A: archived plan → 409 plan_archived; no side effects.

    The archive flow uses direct ORM mutation on `plan.deleted_at` (mirrors
    the established Wave-3 pattern in test_renewal_endpoint.py:206) so the
    test stays focused on the rejection path rather than the plans-soft-delete
    HTTP roundtrip (which itself emits its own audit rows and would pollute
    the no-side-effect assertion).
    """
    plan = await make_plan(name="Archive guard plan A")
    client = await _create_client(authed_client_owner, phone="+79991239031")
    client_uuid = UUID(client["id"])
    source = await make_membership(client_id=client_uuid, plan=plan, status="active")

    membership_count_before = await _count_memberships_for_client(db_session, client_uuid)
    audit_count_before = await _count_renewal_audit_rows_for_source(db_session, source.id)
    assert membership_count_before == 1
    assert audit_count_before == 0

    # Soft-delete the plan (sets deleted_at; the soft-delete column is what
    # repository.get_plan_for_renewal classifies as is_archived=True).
    plan.deleted_at = datetime.now(tz=UTC)
    await db_session.commit()
    await db_session.refresh(plan)
    assert plan.deleted_at is not None

    r = await authed_client_owner.post(
        f"/api/v1/memberships/{source.id}/renew",
        headers=_csrf_headers(authed_client_owner),
    )
    assert r.status_code == 409, r.text

    # Response body shape matches register_exception_handlers contract.
    body: dict[str, Any] = r.json()
    assert body["code"] == "plan_archived"
    assert body.get("fields") in (None, {})

    # NO new membership row created.
    membership_count_after = await _count_memberships_for_client(db_session, client_uuid)
    assert membership_count_after == membership_count_before

    # NO `membership_renewed` audit row written.
    audit_count_after = await _count_renewal_audit_rows_for_source(db_session, source.id)
    assert audit_count_after == audit_count_before


async def test_renew_cancelled_source_returns_cannot_renew_cancelled_409(
    authed_client_owner: AsyncClient,
    db_session: AsyncSession,
    make_plan: Any,
    make_membership: Any,
) -> None:
    """MEM-REN-TEST-03 part B: cancelled source → 409 cannot_renew_cancelled; no side effects.

    Source is seeded directly with status='cancelled' via make_membership
    (mirrors test_renewal_endpoint.py:184) — going through the cancel HTTP
    flow would emit a `membership_cancelled` audit row and skew the
    no-renewal-audit assertion.
    """
    plan = await make_plan(name="Cancel guard plan B")
    client = await _create_client(authed_client_owner, phone="+79991239032")
    client_uuid = UUID(client["id"])
    source = await make_membership(client_id=client_uuid, plan=plan, status="cancelled")
    assert source.status == "cancelled"

    membership_count_before = await _count_memberships_for_client(db_session, client_uuid)
    audit_count_before = await _count_renewal_audit_rows_for_source(db_session, source.id)
    assert membership_count_before == 1
    assert audit_count_before == 0

    r = await authed_client_owner.post(
        f"/api/v1/memberships/{source.id}/renew",
        headers=_csrf_headers(authed_client_owner),
    )
    assert r.status_code == 409, r.text

    body: dict[str, Any] = r.json()
    assert body["code"] == "cannot_renew_cancelled"
    assert body.get("fields") in (None, {})

    # NO new membership row created.
    membership_count_after = await _count_memberships_for_client(db_session, client_uuid)
    assert membership_count_after == membership_count_before

    # NO `membership_renewed` audit row written.
    audit_count_after = await _count_renewal_audit_rows_for_source(db_session, source.id)
    assert audit_count_after == audit_count_before
