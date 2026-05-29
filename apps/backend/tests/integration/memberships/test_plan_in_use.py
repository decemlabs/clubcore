"""Integration tests for DELETE /api/v1/membership-plans plan_in_use closure.

Phase 16 D-15 forward-promised the FK conflict path; Phase 17 closes it via
the FK fk_memberships_plan_id_membership_plans ON DELETE RESTRICT and the
service-layer translation in soft_delete_plan.

D-05: any membership row blocks DELETE.
D-06: ANY status (active, expired, cancelled) blocks — cancelled rows keep
their FK reference for audit-trail integrity.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from httpx import AsyncClient
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit_models import AuditLog
from app.modules.memberships.models import Membership, MembershipPlan


def _csrf_headers(client: AsyncClient) -> dict[str, str]:
    return {"X-CSRF-Token": client.cookies.get("clubcore_csrf") or ""}


VALID_CLIENT: dict[str, Any] = {
    "lastName": "Иванов",
    "firstName": "Иван",
    "phone": "+79991234567",
}


async def _create_client(authed: AsyncClient, **overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {**VALID_CLIENT, **overrides}
    r = await authed.post(
        "/api/v1/clients",
        json=payload,
        headers=_csrf_headers(authed),
    )
    assert r.status_code == 201, r.text
    data: dict[str, Any] = r.json()["data"]
    return data


# --- D-05 / D-06 — all membership statuses block DELETE plan ---------------


async def test_delete_plan_with_active_membership_returns_409(
    authed_client_owner: AsyncClient,
    db_session: AsyncSession,
    make_plan: Any,
    make_membership: Any,
) -> None:
    """D-05: DELETE plan with at least one active membership row -> 409 plan_in_use."""
    plan = await make_plan(name="Active Block")
    client = await _create_client(authed_client_owner, phone="+79991231001")
    await make_membership(
        client_id=UUID(client["id"]),
        plan=plan,
        status="active",
    )

    r = await authed_client_owner.delete(
        f"/api/v1/membership-plans/{plan.id}",
        headers=_csrf_headers(authed_client_owner),
    )
    assert r.status_code == 409, r.text
    assert r.json()["code"] == "plan_in_use"

    # Plan row still alive — soft-delete was rolled back.
    plan_row = await db_session.scalar(select(MembershipPlan).where(MembershipPlan.id == plan.id))
    assert plan_row is not None
    assert plan_row.deleted_at is None


async def test_delete_plan_with_cancelled_membership_returns_409(
    authed_client_owner: AsyncClient,
    make_plan: Any,
    make_membership: Any,
) -> None:
    """D-06 (critical): cancelled membership rows ALSO block DELETE plan."""
    plan = await make_plan(name="Cancelled Block")
    client = await _create_client(authed_client_owner, phone="+79991231002")
    await make_membership(
        client_id=UUID(client["id"]),
        plan=plan,
        status="cancelled",
    )

    r = await authed_client_owner.delete(
        f"/api/v1/membership-plans/{plan.id}",
        headers=_csrf_headers(authed_client_owner),
    )
    assert r.status_code == 409, r.text
    assert r.json()["code"] == "plan_in_use"


async def test_delete_plan_with_expired_membership_returns_409(
    authed_client_owner: AsyncClient,
    make_plan: Any,
    make_membership: Any,
) -> None:
    """D-06: expired membership rows ALSO block DELETE plan."""
    plan = await make_plan(name="Expired Block")
    client = await _create_client(authed_client_owner, phone="+79991231003")
    await make_membership(
        client_id=UUID(client["id"]),
        plan=plan,
        status="expired",
    )

    r = await authed_client_owner.delete(
        f"/api/v1/membership-plans/{plan.id}",
        headers=_csrf_headers(authed_client_owner),
    )
    assert r.status_code == 409, r.text
    assert r.json()["code"] == "plan_in_use"


# --- Happy path: no memberships -> DELETE succeeds -------------------------


async def test_delete_plan_with_no_memberships_succeeds(
    authed_client_owner: AsyncClient,
    make_plan: Any,
) -> None:
    """No FK references -> DELETE plan returns 204 (Phase 16 happy path)."""
    plan = await make_plan(name="No Refs")
    r = await authed_client_owner.delete(
        f"/api/v1/membership-plans/{plan.id}",
        headers=_csrf_headers(authed_client_owner),
    )
    assert r.status_code == 204, r.text


async def test_delete_plan_after_hard_delete_membership_succeeds(
    authed_client_owner: AsyncClient,
    db_session: AsyncSession,
    make_plan: Any,
    make_membership: Any,
) -> None:
    """Hard-delete the membership row directly -> DELETE plan succeeds."""
    plan = await make_plan(name="Hard Delete Then DELETE")
    client = await _create_client(authed_client_owner, phone="+79991231004")
    membership = await make_membership(
        client_id=UUID(client["id"]),
        plan=plan,
        status="active",
    )

    # Hard-delete the membership row directly
    await db_session.execute(delete(Membership).where(Membership.id == membership.id))
    await db_session.commit()

    r = await authed_client_owner.delete(
        f"/api/v1/membership-plans/{plan.id}",
        headers=_csrf_headers(authed_client_owner),
    )
    assert r.status_code == 204, r.text


# --- Co-transactional rollback canary --------------------------------------


async def test_no_audit_row_on_409_plan_in_use(
    authed_client_owner: AsyncClient,
    db_session: AsyncSession,
    make_plan: Any,
    make_membership: Any,
) -> None:
    """Phase 16 D-14: on 409 plan_in_use, the membership_plan_archived audit row
    is rolled back with the soft-delete (audit emitted BEFORE flush so FK
    rejection masks both)."""
    plan = await make_plan(name="No Audit On 409")
    client = await _create_client(authed_client_owner, phone="+79991231005")
    await make_membership(
        client_id=UUID(client["id"]),
        plan=plan,
        status="active",
    )

    r = await authed_client_owner.delete(
        f"/api/v1/membership-plans/{plan.id}",
        headers=_csrf_headers(authed_client_owner),
    )
    assert r.status_code == 409, r.text

    rows = (
        await db_session.scalars(
            select(AuditLog).where(
                AuditLog.action == "membership_plan_archived",
                AuditLog.resource_id == plan.id,
            )
        )
    ).all()
    assert len(rows) == 0, (
        "co-transactional rollback should wipe the membership_plan_archived "
        "audit row when FK rejected the soft-delete"
    )
