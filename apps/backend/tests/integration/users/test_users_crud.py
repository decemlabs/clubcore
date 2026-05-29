"""Phase 43 USERS-01/02/03/05 integration tests — D-43-33.

CRUD + invitation lifecycle for POST/GET /api/v1/users. Uses real
audit.emit + real audit_log query (Phase 42 CR-01 lesson, D-43-34); no
ContextVar patching; authenticated httpx.AsyncClient with cookies.

Plan: ``.planning/phases/43-multi-user-admin-module/43-08-PLAN.md``.

Shared fixtures (authed_client_owner, seeded_active_reception_email,
db_session, ...) live in ``tests/integration/users/conftest.py`` (43-07b)
— never redefined here.

Rule-1 fix vs plan text (43-08-SUMMARY.md):
  - Plan text referenced ``AuditLog.event`` and ``r.json()["detail"]["error"]``;
    the actual ORM column is ``AuditLog.action`` (see ``app/core/audit_models.py``)
    and the AppError handler emits ``{"code", "message", "fields"}`` (see
    ``app/core/exceptions.register_exception_handlers``). Tests align with the
    real surface — drift documented in 43-08-SUMMARY.md.
"""

from __future__ import annotations

from uuid import UUID

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit_models import AuditLog
from app.core.models import User

pytestmark = pytest.mark.asyncio


def _csrf_headers(client: AsyncClient) -> dict[str, str]:
    return {"X-CSRF-Token": client.cookies.get("clubcore_csrf") or ""}


async def test_create_happy_returns_201_and_emits_user_invited(
    db_session: AsyncSession,
    authed_client_owner: AsyncClient,
) -> None:
    """USERS-03 / D-43-13 branch A — no existing row → INSERT pending_invitation + emit + 201."""
    r = await authed_client_owner.post(
        "/api/v1/users",
        json={
            "email": "new-reception@example.com",
            "fullName": "Алла Алексеева",
            "role": "reception",
        },
        headers=_csrf_headers(authed_client_owner),
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert "data" in body
    user_id = UUID(body["data"]["id"])
    assert body["data"]["email"] == "new-reception@example.com"
    assert body["data"]["role"] == "reception"
    assert "invitationExpiresAt" in body["data"]
    # When include_invite_link is not requested, the URL must be absent or null.
    assert body["data"].get("inviteLinkUrl") in (None,)

    # User row exists with pending_invitation status.
    user = await db_session.scalar(select(User).where(User.id == user_id))
    assert user is not None
    assert user.status == "pending_invitation"
    assert user.password_hash is None
    assert user.is_active is True
    assert user.email_verified is False

    # Audit row exists with FLAT payload kwargs (D-43-04).
    audit_rows = (
        (
            await db_session.execute(
                select(AuditLog).where(
                    AuditLog.action == "user_invited",
                    AuditLog.resource_id == user_id,
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(audit_rows) == 1
    assert audit_rows[0].payload["invited_email"] == "new-reception@example.com"
    assert audit_rows[0].payload["link_copied"] is False


async def test_create_with_include_invite_link_returns_url_and_audit_link_copied_true(
    db_session: AsyncSession,
    authed_client_owner: AsyncClient,
) -> None:
    """USERS-03 / D-43-14 — ?include_invite_link=true returns inviteLinkUrl + link_copied=true."""
    r = await authed_client_owner.post(
        "/api/v1/users?include_invite_link=true",
        json={
            "email": "with-link@example.com",
            "fullName": "Borya B.",
            "role": "reception",
        },
        headers=_csrf_headers(authed_client_owner),
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["data"]["inviteLinkUrl"] is not None
    assert "/auth/accept-invite#token=" in body["data"]["inviteLinkUrl"]

    user_id = UUID(body["data"]["id"])
    audit_row = (
        await db_session.execute(
            select(AuditLog).where(
                AuditLog.action == "user_invited",
                AuditLog.resource_id == user_id,
            )
        )
    ).scalar_one()
    assert audit_row.payload["link_copied"] is True
    # Raw URL must NOT live in the payload (Pitfall 4 / D-43-14 anti-oracle for link bleed).
    payload_str = str(audit_row.payload)
    assert "/auth/accept-invite#token=" not in payload_str


async def test_create_pending_user_idempotent_re_invite(
    db_session: AsyncSession,
    authed_client_owner: AsyncClient,
) -> None:
    """USERS-03 / D-43-13 branch B — POST on pending email re-issues token (idempotent)."""
    json_body = {
        "email": "re-invite@example.com",
        "fullName": "Re Invitee",
        "role": "reception",
    }
    r1 = await authed_client_owner.post(
        "/api/v1/users",
        json=json_body,
        headers=_csrf_headers(authed_client_owner),
    )
    assert r1.status_code == 201, r1.text
    first_id = UUID(r1.json()["data"]["id"])

    r2 = await authed_client_owner.post(
        "/api/v1/users",
        json=json_body,
        headers=_csrf_headers(authed_client_owner),
    )
    assert r2.status_code in (200, 201), r2.text  # idempotent — accepts both
    second_id = UUID(r2.json()["data"]["id"])
    assert first_id == second_id, "re-invite must reuse same user_id (branch B)"

    # Two user_invited audit rows exist for the same user (re-issue trail).
    audit_rows = (
        (
            await db_session.execute(
                select(AuditLog).where(
                    AuditLog.action == "user_invited",
                    AuditLog.resource_id == first_id,
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(audit_rows) == 2


async def test_create_email_already_active_returns_409(
    db_session: AsyncSession,
    authed_client_owner: AsyncClient,
    seeded_active_reception_email: str,
) -> None:
    """USERS-03 / D-43-13 branch C — existing active row → 409 email_already_active."""
    r = await authed_client_owner.post(
        "/api/v1/users",
        json={
            "email": seeded_active_reception_email,
            "fullName": "Dup",
            "role": "reception",
        },
        headers=_csrf_headers(authed_client_owner),
    )
    assert r.status_code == 409, r.text
    # AppError handler shape: {"code", "message", "fields"} — see app/core/exceptions.py.
    assert r.json()["code"] == "email_already_active"


async def test_soft_deleted_email_can_be_re_invited_with_new_id(
    db_session: AsyncSession,
    authed_client_owner: AsyncClient,
) -> None:
    """USERS-05 / D-43-13 branch D — soft-deleted email INSERT new user (partial-UNIQUE permits)."""
    json_body = {
        "email": "recycled@example.com",
        "fullName": "First Owner",
        "role": "reception",
    }
    r1 = await authed_client_owner.post(
        "/api/v1/users",
        json=json_body,
        headers=_csrf_headers(authed_client_owner),
    )
    assert r1.status_code == 201, r1.text
    first_id = UUID(r1.json()["data"]["id"])

    # Owner soft-deletes.
    rd = await authed_client_owner.delete(
        f"/api/v1/users/{first_id}",
        headers=_csrf_headers(authed_client_owner),
    )
    assert rd.status_code == 204, rd.text

    # Re-invite same email for a different person.
    r2 = await authed_client_owner.post(
        "/api/v1/users",
        json={
            "email": "recycled@example.com",
            "fullName": "Second Owner",
            "role": "reception",
        },
        headers=_csrf_headers(authed_client_owner),
    )
    assert r2.status_code == 201, r2.text
    second_id = UUID(r2.json()["data"]["id"])
    assert second_id != first_id, "must INSERT new row, never reactivate soft-deleted"

    # Old row's audit history still resolves to old user.id.
    old_audits = (
        (
            await db_session.execute(
                select(AuditLog).where(
                    AuditLog.resource_id == first_id,
                    AuditLog.action == "user_invited",
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(old_audits) >= 1


async def test_list_users_paginated_envelope_no_password_leak(
    db_session: AsyncSession,
    authed_client_owner: AsyncClient,
) -> None:
    """USERS-02 / D-43-10 — paginated envelope + denylisted-field check."""
    r = await authed_client_owner.get(
        "/api/v1/users?page=1&pageSize=20&active=true",
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert "data" in body
    data = body["data"]
    assert {"items", "total", "page", "pageSize"}.issubset(data.keys())
    # Denylist (D-43-10): NO password_hash, telegram_chat_id, email_verified, raw tokens.
    for item in data["items"]:
        for forbidden in (
            "passwordHash",
            "password_hash",
            "telegramChatId",
            "telegram_chat_id",
            "emailVerified",
            "email_verified",
            "passwordChangedAt",
        ):
            assert forbidden not in item, f"denylist leak: {forbidden} in {item}"
        # Expected fields per D-43-10.
        for required in (
            "id",
            "email",
            "fullName",
            "role",
            "isActive",
            "status",
            "createdAt",
            "isDeactivated",
        ):
            assert required in item, f"missing required field: {required}"
