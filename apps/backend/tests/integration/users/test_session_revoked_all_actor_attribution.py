"""Phase 43 WR-01 regression — session_revoked_all attributes to the initiator.

Pre-fix: revoke_all_sessions emitted session_revoked_all with
actor_user_id=user_id, where user_id was the TARGET being deactivated. The
audit row therefore looked like the target self-deactivated their own
sessions — exactly the "self-deactivate" path Phase 43 forbids via
CannotDeactivateSelfError. Compliance review of the audit log would draw the
wrong conclusion about who initiated the action.

Fix: actor_user_id is plumbed through UserSessionInvalidator Protocol and
into the session_revoked_all emit, sourced from the initiating owner.
"""

from __future__ import annotations

from uuid import UUID

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit_models import AuditLog
from app.core.models import User
from app.core.permissions import Role

from .conftest import OWNER_EMAIL, _csrf_headers

pytestmark = pytest.mark.asyncio


async def test_session_revoked_all_actor_is_owner_not_target(
    authed_client_owner: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """WR-01 invariant: session_revoked_all.actor_user_id == owner.id, NOT target.id."""
    # Resolve the seeded owner's id from the DB.
    owner_row = await db_session.scalar(
        select(User).where(User.email == OWNER_EMAIL, User.deleted_at.is_(None))
    )
    assert owner_row is not None, f"Seeded owner not found for {OWNER_EMAIL}"
    owner_id: UUID = owner_row.id

    # Seed a reception user to deactivate.
    target = User(
        email="attribution-target-wr01@example.com",
        email_verified=True,
        password_hash="$argon2id$placeholder",
        role=Role.RECEPTION,
        full_name="Attribution Target",
        is_active=True,
        status="active",
    )
    db_session.add(target)
    await db_session.commit()
    await db_session.refresh(target)
    target_id: UUID = target.id

    # Owner deactivates target.
    response = await authed_client_owner.patch(
        f"/api/v1/users/{target_id}/deactivate",
        headers=_csrf_headers(authed_client_owner),
    )
    assert response.status_code == 204, response.text

    # Locate the session_revoked_all audit row for this target.
    session_revoked_rows = (
        (
            await db_session.execute(
                select(AuditLog).where(
                    AuditLog.action == "session_revoked_all",
                    AuditLog.resource_id == target_id,
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(session_revoked_rows) == 1, (
        f"Expected exactly 1 session_revoked_all row for target {target_id}, "
        f"got {len(session_revoked_rows)}"
    )
    row = session_revoked_rows[0]

    # WR-01 invariant: actor IS the owner, not the target.
    assert row.actor_user_id == owner_id, (
        f"WR-01 regression — session_revoked_all actor_user_id={row.actor_user_id} "
        f"but should be the initiating owner ({owner_id}). The TARGET ({target_id}) "
        "must appear in resource_id, NOT actor_user_id."
    )
    assert row.actor_user_id != target_id, (
        "WR-01 regression — session_revoked_all attributed to the target as if "
        "they self-deactivated. The Phase 43 CannotDeactivateSelfError path "
        "explicitly forbids self-deactivate; the audit attribution must agree."
    )
    assert row.resource_id == target_id, (
        f"resource_id should be the target's id ({target_id}), got {row.resource_id}"
    )
