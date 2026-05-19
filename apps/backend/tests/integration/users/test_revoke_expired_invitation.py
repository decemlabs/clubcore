"""Phase 43 WR-06 regression — revoke_invitation rejects expired tokens with 409.

Pre-fix: revoke_invitation pre-checked consumed_at IS NOT NULL but ignored
expires_at. An expired-but-unconsumed token would be silently "consumed" by
the UPDATE...RETURNING, the service emitted user_invitation_revoked, and the
owner UI saw a clean 204 — but the token was already useless. Worse, the
audit row muddied the forensic chain.

Fix: pre-check raises InvitationExpiredError (409 invitation_expired) AND
repository.atomic_consume_invitation_token_by_id filters on
expires_at > now() (defence-in-depth against the pre-check/UPDATE race).

Fixture conventions mirror test_users_invitation_flow.py exactly.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from httpx import AsyncClient
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit_models import AuditLog
from app.modules.auth.password_reset_token_model import PasswordResetToken

from .conftest import _csrf_headers

pytestmark = pytest.mark.asyncio


async def test_revoke_expired_invitation_returns_409(
    db_session: AsyncSession,
    authed_client_owner: AsyncClient,
) -> None:
    """WR-06 — revoking an expired token returns 409 invitation_expired.

    Also asserts that NO user_invitation_revoked audit row is emitted for
    the expired token (forensic chain protection — the token was already
    useless, audit muddying is prevented).
    """
    # Arrange — create an invitation via the normal service path.
    create_resp = await authed_client_owner.post(
        "/api/v1/users",
        json={
            "email": "soon-expired@example.com",
            "fullName": "Скоро Истечет",
            "role": "reception",
        },
        headers=_csrf_headers(authed_client_owner),
    )
    assert create_resp.status_code == 201, create_resp.text

    # Locate the invitation token row (consumed_at IS NULL — fresh from create).
    token_row = await db_session.scalar(
        select(PasswordResetToken)
        .where(
            PasswordResetToken.purpose == "invitation",
            PasswordResetToken.consumed_at.is_(None),
        )
        .order_by(PasswordResetToken.created_at.desc())
        .limit(1)
    )
    assert token_row is not None, "fresh invitation token row missing after POST /users"
    token_id: UUID = token_row.id

    # Back-date expires_at by 1 hour (direct UPDATE — bypass service layer).
    past = datetime.now(tz=UTC) - timedelta(hours=1)
    await db_session.execute(
        update(PasswordResetToken)
        .where(PasswordResetToken.id == token_id)
        .values(expires_at=past)
    )
    await db_session.commit()

    # Act — owner tries to revoke the now-expired token.
    revoke_resp = await authed_client_owner.post(
        f"/api/v1/users/invitations/{token_id}/revoke",
        json={"reason": "stale typo"},
        headers=_csrf_headers(authed_client_owner),
    )

    # Assert — 409 invitation_expired (NOT 204).
    assert revoke_resp.status_code == 409, revoke_resp.text
    body = revoke_resp.json()
    # AppError handler shape: {"code", "message", "fields"} at top level.
    assert body["code"] == "invitation_expired", (
        f"WR-06 regression — expected code 'invitation_expired'; got {body!r}"
    )

    # Audit log MUST NOT contain a user_invitation_revoked row for this token.
    audit_rows = (
        await db_session.execute(
            select(AuditLog).where(AuditLog.action == "user_invitation_revoked")
        )
    ).scalars().all()
    for row in audit_rows:
        # invitation_token_id is in payload as str(UUID) — JSONB roundtrip.
        assert str(token_id) not in str(row.payload), (
            "WR-06 regression — user_invitation_revoked audit row emitted "
            "for an expired token. The pre-check should have raised "
            "InvitationExpiredError before audit.emit."
        )


async def test_revoke_non_expired_invitation_succeeds(
    db_session: AsyncSession,
    authed_client_owner: AsyncClient,
) -> None:
    """Positive control — a non-expired invitation still revokes cleanly (204).

    Confirms the WR-06 fix did not break the happy path.
    """
    create_resp = await authed_client_owner.post(
        "/api/v1/users",
        json={
            "email": "still-fresh@example.com",
            "fullName": "Свежее Приглашение",
            "role": "reception",
        },
        headers=_csrf_headers(authed_client_owner),
    )
    assert create_resp.status_code == 201, create_resp.text

    # Locate the fresh invitation token.
    token_row = await db_session.scalar(
        select(PasswordResetToken)
        .where(
            PasswordResetToken.purpose == "invitation",
            PasswordResetToken.consumed_at.is_(None),
        )
        .order_by(PasswordResetToken.created_at.desc())
        .limit(1)
    )
    assert token_row is not None
    token_id: UUID = token_row.id

    revoke_resp = await authed_client_owner.post(
        f"/api/v1/users/invitations/{token_id}/revoke",
        json={"reason": "operator declined"},
        headers=_csrf_headers(authed_client_owner),
    )
    assert revoke_resp.status_code == 204, revoke_resp.text

    # Verify the token is now consumed.
    await db_session.refresh(token_row)
    assert token_row.consumed_at is not None, "token consumed_at should be set after revoke"
