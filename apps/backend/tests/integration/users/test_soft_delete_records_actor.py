"""Phase 43 WR-03 regression — soft_delete_user populates deactivated_by_user_id.

Pre-fix: repository.soft_delete_user UPDATE did not touch
deactivated_by_user_id, so the pure-delete-without-deactivate path left:
  is_active=false, deactivated_at=now, deactivated_by_user_id=NULL
breaking the forensic chain "which owner ended this account?".

Fix: COALESCE(User.deactivated_by_user_id, actor_user_id) — preserves the
existing value (delete-after-deactivate path) and fills NULL slots
(pure-delete path).
"""

from __future__ import annotations

from uuid import UUID

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models import User
from app.core.permissions import Role

from .conftest import OWNER_EMAIL, _csrf_headers

pytestmark = pytest.mark.asyncio


async def test_soft_delete_pure_delete_populates_deactivated_by_user_id(
    authed_client_owner: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Pure-delete path: DELETE on an active user must populate deactivated_by_user_id.

    WR-03 regression — pre-fix code left deactivated_by_user_id=NULL on this path.
    """
    # Resolve the seeded owner's id.
    owner_row = await db_session.scalar(
        select(User).where(User.email == OWNER_EMAIL, User.deleted_at.is_(None))
    )
    assert owner_row is not None
    owner_id: UUID = owner_row.id

    # Seed a reception user (no prior deactivation).
    target = User(
        email="pure-delete-wr03@example.com",
        email_verified=True,
        password_hash="$argon2id$placeholder",
        role=Role.RECEPTION,
        full_name="Pure Delete Target",
        is_active=True,
        status="active",
    )
    db_session.add(target)
    await db_session.commit()
    await db_session.refresh(target)
    target_id: UUID = target.id

    # Baseline: deactivated_by_user_id is NULL before any action.
    assert target.deactivated_by_user_id is None, (
        "Baseline failed: deactivated_by_user_id should be NULL on a fresh active user"
    )

    # DELETE without a prior deactivate (pure-delete-without-deactivate path).
    response = await authed_client_owner.delete(
        f"/api/v1/users/{target_id}",
        headers=_csrf_headers(authed_client_owner),
    )
    assert response.status_code == 204, response.text

    await db_session.refresh(target)
    assert target.deleted_at is not None, "deleted_at must be set after DELETE"
    assert target.is_active is False, "is_active must be False after DELETE"
    assert target.deactivated_at is not None, "deactivated_at must be set via COALESCE"
    assert target.deactivated_by_user_id == owner_id, (
        f"WR-03 regression — pure-delete path left deactivated_by_user_id="
        f"{target.deactivated_by_user_id} (expected {owner_id}). "
        "soft_delete_user must COALESCE in actor_user_id when the existing "
        "value is NULL."
    )


async def test_soft_delete_after_deactivate_preserves_original_deactivator(
    authed_client_owner: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Delete-after-deactivate path: COALESCE preserves the existing value.

    When a user is deactivated first (deactivated_by_user_id is set) and then
    deleted, the soft-delete UPDATE must NOT overwrite the existing
    deactivated_by_user_id value (COALESCE only fills NULLs).
    """
    # Resolve the seeded owner's id.
    owner_row = await db_session.scalar(
        select(User).where(User.email == OWNER_EMAIL, User.deleted_at.is_(None))
    )
    assert owner_row is not None
    owner_id: UUID = owner_row.id

    # Seed a reception user.
    target = User(
        email="post-deact-delete-wr03@example.com",
        email_verified=True,
        password_hash="$argon2id$placeholder",
        role=Role.RECEPTION,
        full_name="Post Deactivate Delete",
        is_active=True,
        status="active",
    )
    db_session.add(target)
    await db_session.commit()
    await db_session.refresh(target)
    target_id: UUID = target.id

    # Step 1 — deactivate (sets deactivated_by_user_id = owner_id).
    deactivate_resp = await authed_client_owner.patch(
        f"/api/v1/users/{target_id}/deactivate",
        headers=_csrf_headers(authed_client_owner),
    )
    assert deactivate_resp.status_code == 204, deactivate_resp.text
    await db_session.refresh(target)
    assert target.deactivated_by_user_id == owner_id, (
        "Deactivate step should have set deactivated_by_user_id to owner_id"
    )
    deactivated_at_first = target.deactivated_at

    # Step 2 — delete. The COALESCE must preserve the existing value.
    delete_resp = await authed_client_owner.delete(
        f"/api/v1/users/{target_id}",
        headers=_csrf_headers(authed_client_owner),
    )
    assert delete_resp.status_code == 204, delete_resp.text

    await db_session.refresh(target)
    assert target.deleted_at is not None, "deleted_at must be set after DELETE"
    assert target.deactivated_by_user_id == owner_id, (
        f"WR-03 regression — deactivated_by_user_id changed after delete "
        f"(expected {owner_id}, got {target.deactivated_by_user_id}). "
        "COALESCE must preserve the existing value from the deactivate step."
    )
    assert target.deactivated_at == deactivated_at_first, (
        "deactivated_at should be preserved by COALESCE (the deactivate value), "
        f"not re-stamped. Before: {deactivated_at_first}, After: {target.deactivated_at}"
    )
