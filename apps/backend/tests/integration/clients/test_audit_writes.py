"""Integration tests asserting audit_log DB rows for clients events (AUDIT-02/03).

Each test exercises a clients route via the authed httpx client, then
queries the SAVEPOINT-rolled `db_session` for the corresponding
`AuditLog` rows. Assertions cover D-08 payload shapes (PII-aware) and
D-04 mapping table (resource_type, actor_user_id nullability).

AUDIT-03 is verified by `test_audit_log_endpoint_requires_auth` — the
Phase 56 audit-log read endpoint exists but is owner-only; it must never be
readable by unauthenticated callers or non-owner roles (clients/reception).
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit_models import AuditLog
from app.modules.auth.models import User


def _csrf_headers(client: AsyncClient) -> dict[str, str]:
    return {"X-CSRF-Token": client.cookies.get("clubcore_csrf", "")}


VALID_CLIENT: dict[str, Any] = {
    "lastName": "Иванов",
    "firstName": "Иван",
    "phone": "+79991234567",
}


async def _create(authed: AsyncClient, **overrides: Any) -> dict[str, Any]:
    payload = {**VALID_CLIENT, **overrides}
    r = await authed.post(
        "/api/v1/clients",
        json=payload,
        headers=_csrf_headers(authed),
    )
    assert r.status_code == 201, r.text
    data: dict[str, Any] = r.json()["data"]
    return data


async def test_client_created_writes_audit_row(
    authed_client_owner: AsyncClient,
    db_session: AsyncSession,
    seeded_owner: User,
) -> None:
    """AUDIT-02 + D-08: client_created row carries the locked PII-safe shape."""
    created = await _create(authed_client_owner, phone="+79990002001")
    client_id = UUID(created["id"])

    rows = (
        await db_session.scalars(
            select(AuditLog).where(
                AuditLog.action == "client_created",
                AuditLog.resource_id == client_id,
            )
        )
    ).all()
    assert len(rows) == 1, f"expected exactly 1 row, got {len(rows)}"
    row = rows[0]
    assert row.actor_user_id == seeded_owner.id
    assert row.resource_type == "client"
    assert row.resource_id == client_id

    payload = row.payload
    # D-08: required keys
    assert isinstance(payload["full_name"], str) and payload["full_name"]
    assert payload["phone"] == "+79990002001"
    assert isinstance(payload["has_email"], bool)
    assert isinstance(payload["has_telegram"], bool)
    # D-08: PII-protected — must NOT be in payload
    assert "notes" not in payload
    assert "birthday" not in payload
    assert "emergency_contact" not in payload


async def test_client_updated_writes_audit_row_with_changed_fields(
    authed_client_owner: AsyncClient,
    db_session: AsyncSession,
    seeded_owner: User,
) -> None:
    """D-08: client_updated payload reports changed_fields (sorted) and no
    previous_phone when phone was not changed."""
    created = await _create(authed_client_owner, phone="+79990002002")
    client_id = UUID(created["id"])

    r = await authed_client_owner.patch(
        f"/api/v1/clients/{client_id}",
        json={"firstName": "Other"},
        headers=_csrf_headers(authed_client_owner),
    )
    assert r.status_code == 200, r.text

    rows = (
        await db_session.scalars(
            select(AuditLog).where(
                AuditLog.action == "client_updated",
                AuditLog.resource_id == client_id,
            )
        )
    ).all()
    assert len(rows) == 1
    row = rows[0]
    assert row.actor_user_id == seeded_owner.id
    assert row.resource_type == "client"
    assert row.payload["changed_fields"] == ["first_name"]
    assert "previous_phone" not in row.payload


async def test_client_updated_with_phone_change_includes_previous_phone(
    authed_client_owner: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """D-08: phone change records previous_phone for audit reconstruction."""
    created = await _create(authed_client_owner, phone="+79991111111")
    client_id = UUID(created["id"])

    r = await authed_client_owner.patch(
        f"/api/v1/clients/{client_id}",
        json={"phone": "+79992222222"},
        headers=_csrf_headers(authed_client_owner),
    )
    assert r.status_code == 200, r.text

    rows = (
        await db_session.scalars(
            select(AuditLog).where(
                AuditLog.action == "client_updated",
                AuditLog.resource_id == client_id,
            )
        )
    ).all()
    assert len(rows) == 1
    payload = rows[0].payload
    assert "phone" in payload["changed_fields"]
    assert payload["previous_phone"] == "+79991111111"


async def test_client_soft_deleted_writes_audit_row_with_phone_and_full_name(
    authed_client_owner: AsyncClient,
    db_session: AsyncSession,
    seeded_owner: User,
) -> None:
    """D-08: client_soft_deleted payload captures pre-deletion full_name + phone."""
    created = await _create(authed_client_owner, phone="+79990002004")
    client_id = UUID(created["id"])

    r = await authed_client_owner.delete(
        f"/api/v1/clients/{client_id}",
        headers=_csrf_headers(authed_client_owner),
    )
    assert r.status_code == 204, r.text

    rows = (
        await db_session.scalars(
            select(AuditLog).where(
                AuditLog.action == "client_soft_deleted",
                AuditLog.resource_id == client_id,
            )
        )
    ).all()
    assert len(rows) == 1
    row = rows[0]
    assert row.actor_user_id == seeded_owner.id
    assert row.resource_type == "client"
    assert row.payload["phone"] == "+79990002004"
    assert isinstance(row.payload["full_name"], str)
    assert row.payload["full_name"]


async def test_audit_log_endpoint_requires_auth(
    async_client: AsyncClient,
) -> None:
    """AUDIT-03: the audit log is never readable without authentication.

    Phase 56 (AUD-01) introduced the owner-only ``GET /api/v1/audit-log``
    read endpoint. The earlier route-absence guard is obsolete: the route
    now exists but is gated by ``require_permission(LIST, AUDIT_LOG)``.
    An unauthenticated GET must be rejected with 401 (auth required), never
    served — confirming audit_log is not openly exposed. Reception-role
    denial (403) is covered by the Phase 56 reports integration suite.
    """
    r = await async_client.get("/api/v1/audit-log")
    assert r.status_code == 401, f"audit-log unexpectedly returned {r.status_code}"

    # A genuinely unknown audit path still 404s — guards against typo'd routes.
    r = await async_client.get("/api/v1/auditlog")
    assert r.status_code == 404, f"/api/v1/auditlog unexpectedly returned {r.status_code}"
