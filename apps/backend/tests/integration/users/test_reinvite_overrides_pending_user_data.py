"""Phase 43 WR-02 regression — re-invite overwrites full_name/role on the pending user.

Pre-fix: Branch B of create_user (existing pending_invitation user) silently
ignored data.full_name and data.role from the inbound POST body. An owner
fixing a typo would mint a fresh invitation token under the OLD name/role.

Fix: Branch B overwrites existing.full_name = data.full_name and
existing.role = data.role before the atomic-consume + new token INSERT.

Fixture conventions mirror test_users_crud.py exactly.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models import User
from app.modules.auth.password_reset_token_model import PasswordResetToken

from .conftest import _csrf_headers

pytestmark = pytest.mark.asyncio


async def test_reinvite_overwrites_full_name_and_role(
    db_session: AsyncSession,
    authed_client_owner: AsyncClient,
) -> None:
    """WR-02 — second POST /users for the same email overwrites full_name and role.

    Branch A: first invite inserts pending_invitation row with 'John Smith' /
    reception. Branch B: second invite with 'Jane Smith' / owner MUST overwrite
    the existing row (not silently keep the old values). A new active invitation
    token is present after the second POST.
    """
    email = "typo-fix@example.com"

    # Branch A — first invite.
    first = await authed_client_owner.post(
        "/api/v1/users",
        json={"email": email, "fullName": "John Smith", "role": "reception"},
        headers=_csrf_headers(authed_client_owner),
    )
    assert first.status_code == 201, first.text

    # Branch B — re-invite with corrected name + promoted role.
    second = await authed_client_owner.post(
        "/api/v1/users",
        json={"email": email, "fullName": "Jane Smith", "role": "owner"},
        headers=_csrf_headers(authed_client_owner),
    )
    assert second.status_code in (200, 201), second.text

    # Assert the users row carries the NEW values.
    user = await db_session.scalar(
        select(User).where(
            func.lower(User.email) == email.lower(),
            User.deleted_at.is_(None),
        )
    )
    assert user is not None, f"user row not found for {email!r}"
    assert user.full_name == "Jane Smith", (
        f"WR-02 regression — Branch B kept old full_name {user.full_name!r}; "
        "create_user must overwrite existing.full_name = data.full_name."
    )
    assert user.role.value == "owner", (
        f"WR-02 regression — Branch B kept old role {user.role.value!r}; "
        "create_user must overwrite existing.role = data.role."
    )
    assert user.status == "pending_invitation", (
        f"User status should remain 'pending_invitation' after re-invite; got {user.status!r}"
    )

    # New active invitation token exists (the previous one was atomic-consumed).
    active_tokens = (
        (
            await db_session.execute(
                select(PasswordResetToken).where(
                    PasswordResetToken.user_id == user.id,
                    PasswordResetToken.purpose == "invitation",
                    PasswordResetToken.consumed_at.is_(None),
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(active_tokens) == 1, (
        f"WR-02 regression — expected exactly 1 active invitation token after re-invite; "
        f"got {len(active_tokens)}. The prior token must be atomic-consumed and a fresh "
        "one inserted."
    )
