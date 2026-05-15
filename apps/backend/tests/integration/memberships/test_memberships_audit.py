"""Integration tests for membership audit_log writes (MEM-AUDIT-01, D-14).

Pattern: exercise a /memberships route, then query AuditLog rows directly via
the SAVEPOINT-rolled db_session.

Critical D-14 assertion: cancel WITHOUT reason emits a `membership_cancelled`
audit row whose payload OMITS the `reason` key entirely (NOT `reason: None`).
The grep canary `"reason" not in audit_row.payload` catches a regression
where a refactor accidentally writes `reason=None` into the JSONB blob.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID, uuid4

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit_models import AuditLog
from app.modules.auth.models import User


def _csrf_headers(client: AsyncClient) -> dict[str, str]:
    # Phase 32 PAY-09: POST /api/v1/memberships now requires Idempotency-Key.
    return {
        "X-CSRF-Token": client.cookies.get("sportzal_csrf") or "",
        "Idempotency-Key": uuid4().hex,
    }


VALID_PLAN: dict[str, Any] = {
    "name": "Базовый",
    "durationDays": 30,
    "priceKopecks": 250000,
    "freezeDaysLimit": 14,
    "active": True,
}


VALID_CLIENT: dict[str, Any] = {
    "lastName": "Иванов",
    "firstName": "Иван",
    "phone": "+79991234567",
}


async def _create_plan(authed: AsyncClient, **overrides: Any) -> dict[str, Any]:
    payload = {**VALID_PLAN, **overrides}
    r = await authed.post(
        "/api/v1/membership-plans",
        json=payload,
        headers=_csrf_headers(authed),
    )
    assert r.status_code == 201, r.text
    data: dict[str, Any] = r.json()["data"]
    return data


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


async def _sell_membership(
    authed: AsyncClient,
    *,
    client_id: str,
    plan_id: str,
) -> dict[str, Any]:
    r = await authed.post(
        "/api/v1/memberships",
        json={"clientId": client_id, "planId": plan_id},
        headers=_csrf_headers(authed),
    )
    assert r.status_code == 201, r.text
    data: dict[str, Any] = r.json()["data"]
    return data


# --- membership_created shape (MEM-AUDIT-01) ------------------------------


async def test_membership_created_payload_shape(
    authed_client_owner: AsyncClient,
    db_session: AsyncSession,
    seeded_owner: User,
) -> None:
    """MEM-AUDIT-01: membership_created payload has client_id, plan_id, end_date."""
    plan = await _create_plan(authed_client_owner)
    client = await _create_client(authed_client_owner)
    membership = await _sell_membership(
        authed_client_owner,
        client_id=client["id"],
        plan_id=plan["id"],
    )
    membership_id = UUID(membership["id"])

    rows = (
        await db_session.scalars(
            select(AuditLog).where(
                AuditLog.action == "membership_created",
                AuditLog.resource_id == membership_id,
            )
        )
    ).all()
    assert len(rows) == 1, f"expected exactly 1 row, got {len(rows)}"
    row = rows[0]
    assert row.actor_user_id == seeded_owner.id
    assert row.resource_type == "membership"
    assert row.resource_id == membership_id

    payload = row.payload
    assert payload["client_id"] == client["id"]
    assert payload["plan_id"] == plan["id"]
    assert payload["end_date"] == membership["endDate"]
    # Phase 32 PAY-05: membership_created payload extended with payment_id field
    # linking the sale-side payment row written in the same UoW (free-form
    # payload — D-30-02 — no AUDIT_PAYLOAD_SCHEMAS entry to update).
    assert "payment_id" in payload
    UUID(payload["payment_id"])  # well-formed UUID string
    # Defensive: only the 4 documented keys (membership_id is in resource_id).
    assert set(payload.keys()) == {"client_id", "plan_id", "end_date", "payment_id"}


async def test_audit_actor_user_id_matches_authenticated_user(
    authed_client_owner: AsyncClient,
    db_session: AsyncSession,
    seeded_owner: User,
) -> None:
    """Actor user_id on audit row equals the authenticated owner's id."""
    plan = await _create_plan(authed_client_owner)
    client = await _create_client(authed_client_owner)
    membership = await _sell_membership(
        authed_client_owner,
        client_id=client["id"],
        plan_id=plan["id"],
    )
    membership_id = UUID(membership["id"])

    row = await db_session.scalar(
        select(AuditLog).where(
            AuditLog.action == "membership_created",
            AuditLog.resource_id == membership_id,
        )
    )
    assert row is not None
    assert row.actor_user_id == seeded_owner.id


# --- membership_cancelled shape — D-14 critical reason-key omission --------


async def test_membership_cancelled_with_reason(
    authed_client_owner: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """D-14: cancel with reason -> audit payload includes {client_id, reason}."""
    plan = await _create_plan(authed_client_owner)
    client = await _create_client(authed_client_owner)
    membership = await _sell_membership(
        authed_client_owner,
        client_id=client["id"],
        plan_id=plan["id"],
    )
    membership_id = UUID(membership["id"])

    r = await authed_client_owner.post(
        f"/api/v1/memberships/{membership_id}/cancel",
        json={"reason": "data error"},
        headers=_csrf_headers(authed_client_owner),
    )
    assert r.status_code == 200, r.text

    rows = (
        await db_session.scalars(
            select(AuditLog).where(
                AuditLog.action == "membership_cancelled",
                AuditLog.resource_id == membership_id,
            )
        )
    ).all()
    assert len(rows) == 1
    payload = rows[0].payload
    assert payload["client_id"] == client["id"]
    assert payload["reason"] == "data error"


async def test_membership_cancelled_without_reason_omits_key(
    authed_client_owner: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """D-14 (critical): cancel WITHOUT reason -> payload OMITS the reason key.

    The assertion shape MUST be `"reason" not in payload`, NOT
    `payload.get("reason") is None` — the latter would silently pass even
    if a refactor accidentally serialised `reason: None`.
    """
    plan = await _create_plan(authed_client_owner)
    client = await _create_client(authed_client_owner)
    membership = await _sell_membership(
        authed_client_owner,
        client_id=client["id"],
        plan_id=plan["id"],
    )
    membership_id = UUID(membership["id"])

    r = await authed_client_owner.post(
        f"/api/v1/memberships/{membership_id}/cancel",
        json={},
        headers=_csrf_headers(authed_client_owner),
    )
    assert r.status_code == 200, r.text

    rows = (
        await db_session.scalars(
            select(AuditLog).where(
                AuditLog.action == "membership_cancelled",
                AuditLog.resource_id == membership_id,
            )
        )
    ).all()
    assert len(rows) == 1
    payload = rows[0].payload
    assert payload["client_id"] == client["id"]
    # D-14 critical assertion: the key must be absent, not present-with-null.
    assert "reason" not in payload
    # Defensive: only client_id should be in payload when no reason.
    assert set(payload.keys()) == {"client_id"}


# --- Co-transactional rollback canaries (Phase 16 D-14) ---------------------


async def test_no_audit_on_failed_sale(
    authed_client_owner: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Failed sale (409 plan_inactive) writes ZERO membership_created audit rows.

    Co-transactional rollback per Phase 16 D-14 — but actually for Phase 17 the
    409 path raises BEFORE any audit emit (the inactive-plan check is step 2 in
    the service, before the membership row is inserted), so the assertion is
    that the failed POST never even attempted an emit.
    """
    plan = await _create_plan(authed_client_owner)
    # Deactivate
    r_patch = await authed_client_owner.patch(
        f"/api/v1/membership-plans/{plan['id']}",
        json={"active": False},
        headers=_csrf_headers(authed_client_owner),
    )
    assert r_patch.status_code == 200

    client = await _create_client(authed_client_owner)
    r = await authed_client_owner.post(
        "/api/v1/memberships",
        json={"clientId": client["id"], "planId": plan["id"]},
        headers=_csrf_headers(authed_client_owner),
    )
    assert r.status_code == 409
    assert r.json()["code"] == "plan_inactive"

    # Zero membership_created rows for this client (no membership row was inserted).
    rows = (
        await db_session.scalars(
            select(AuditLog).where(AuditLog.action == "membership_created")
        )
    ).all()
    # Filter to rows for this specific client (other tests may have run in same
    # SAVEPOINT — but each test gets its own SAVEPOINT, so this is total count).
    assert len(rows) == 0


async def test_no_audit_on_failed_cancel(
    authed_client_owner: AsyncClient,
    db_session: AsyncSession,
    make_plan: Any,
    make_membership: Any,
) -> None:
    """Failed cancel (409 invalid_transition on expired) writes ZERO cancel audit.

    The transition guard (`_assert_can_cancel`) fires BEFORE any mutation per
    D-15, so the membership_cancelled audit emit never runs.
    """
    plan = await make_plan(name="No Audit On Fail")
    client = await _create_client(authed_client_owner, phone="+79991230099")
    membership = await make_membership(
        client_id=UUID(client["id"]),
        plan=plan,
        status="expired",
    )

    r = await authed_client_owner.post(
        f"/api/v1/memberships/{membership.id}/cancel",
        json={"reason": "n/a"},
        headers=_csrf_headers(authed_client_owner),
    )
    assert r.status_code == 409
    assert r.json()["code"] == "invalid_transition"

    rows = (
        await db_session.scalars(
            select(AuditLog).where(
                AuditLog.action == "membership_cancelled",
                AuditLog.resource_id == membership.id,
            )
        )
    ).all()
    assert len(rows) == 0
