"""Phase 112 TEAM-01 — PATCH /api/v1/users/{user_id}/role integration tests.

Covers:
  - Owner promotes reception → owner (204, role persisted).
  - Owner demotes owner → reception when another owner survives (204, role persisted).
  - Reception PATCH → 403 (UPDATE, USERS is OWNER_ONLY).
  - Owner changes own role → 409 cannot_change_own_role.
  - Owner demotes last remaining active owner → 409 cannot_change_last_owner_role
    (or cannot_change_own_role when the only owner targets themselves — accept both).
  - Owner PATCH without X-CSRF-Token → 403 csrf_mismatch.
  - Successful role change writes a user_role_changed audit row.

Fixture surface (all from tests/integration/users/conftest.py — NOT redefined here):
  - authed_client_owner     — owner cookies + CSRF in jar.
  - authed_client_reception — reception cookies + CSRF in jar.
  - current_owner_user_id   — UUID of the seeded owner.
  - single_active_owner_id  — UUID of the only active owner (forces last-owner precondition).
  - db_session              — SAVEPOINT-rolled AsyncSession (from root conftest.py).

Error-body convention: global AppError handler returns {code, message, fields} at the
TOP level (not under detail). All assertions use r.json()["code"].
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit_models import AuditLog
from app.core.models import User
from app.core.permissions import Role
from app.core.security import hash_password

from .conftest import OWNER_EMAIL, _csrf_headers

pytestmark = pytest.mark.asyncio

# Placeholder argon2id hash for test users seeded outside the _seed_user helper.
_PLACEHOLDER_PWD_HASH = "$argon2id$" + "placeholder"


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _csrf(client: AsyncClient) -> dict[str, str]:
    """Return {X-CSRF-Token: <cookie>} for CSRF-protected mutating routes.

    Mirrors the _csrf helper in test_users_guards.py — inlined for readability.
    """
    return {"X-CSRF-Token": client.cookies.get("clubcore_csrf") or ""}


async def _seed_reception(db_session: AsyncSession, *, email: str = "role-test-reception@example.com") -> User:
    """Insert an active reception user; return the ORM row."""
    user = User(
        email=email,
        password_hash=_PLACEHOLDER_PWD_HASH,
        role=Role.RECEPTION,
        full_name="Role Test Reception",
        email_verified=True,
        status="active",
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


async def _seed_inactive_reception(
    db_session: AsyncSession, *, email: str = "role-test-inactive@example.com"
) -> User:
    """Insert a deactivated reception user; return the ORM row.

    Mirrors real deactivation: ``is_active=False`` while ``status`` stays
    'active' (the CHECK ck_users_status only permits 'active' /
    'pending_invitation'; deactivation flips is_active, not status). The
    ck_users_lifecycle_consistency CHECK requires ``deactivated_at IS NOT NULL``
    whenever ``is_active=False``, so it is set here.
    """
    user = User(
        email=email,
        password_hash=_PLACEHOLDER_PWD_HASH,
        role=Role.RECEPTION,
        full_name="Role Test Inactive",
        email_verified=True,
        status="active",
        is_active=False,
        deactivated_at=datetime.now(tz=UTC),
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


async def _seed_second_owner(db_session: AsyncSession) -> User:
    """Insert an active owner user distinct from the session owner; return the ORM row."""
    user = User(
        email="role-test-second-owner@example.com",
        password_hash=_PLACEHOLDER_PWD_HASH,
        role=Role.OWNER,
        full_name="Role Test Second Owner",
        email_verified=True,
        status="active",
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


# ---------------------------------------------------------------------------
# Happy-path tests
# ---------------------------------------------------------------------------


async def test_owner_can_promote_reception_to_owner(
    authed_client_owner: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Owner PATCH reception → owner returns 204 and persists the new role."""
    target = await _seed_reception(db_session)

    r = await authed_client_owner.patch(
        f"/api/v1/users/{target.id}/role",
        json={"role": "owner"},
        headers=_csrf(authed_client_owner),
    )
    assert r.status_code == 204, r.text

    # Verify persistence.
    await db_session.refresh(target)
    assert target.role == Role.OWNER, f"Expected OWNER, got {target.role}"


async def test_owner_can_demote_non_last_owner_to_reception(
    authed_client_owner: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Owner demotes a second owner (not the last one) to reception — 204, persisted."""
    second_owner = await _seed_second_owner(db_session)

    r = await authed_client_owner.patch(
        f"/api/v1/users/{second_owner.id}/role",
        json={"role": "reception"},
        headers=_csrf(authed_client_owner),
    )
    assert r.status_code == 204, r.text

    await db_session.refresh(second_owner)
    assert second_owner.role == Role.RECEPTION, f"Expected RECEPTION, got {second_owner.role}"


async def test_role_change_persists_after_commit(
    authed_client_owner: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Verify the role update committed to the DB (read-back after PATCH 204)."""
    target = await _seed_reception(db_session, email="role-persist-check@example.com")
    target_id: UUID = target.id

    r = await authed_client_owner.patch(
        f"/api/v1/users/{target_id}/role",
        json={"role": "owner"},
        headers=_csrf(authed_client_owner),
    )
    assert r.status_code == 204, r.text

    # Re-fetch from the session to confirm the commit took effect.
    row = await db_session.scalar(select(User).where(User.id == target_id))
    assert row is not None
    assert row.role == Role.OWNER


# ---------------------------------------------------------------------------
# RBAC + CSRF guard tests
# ---------------------------------------------------------------------------


async def test_reception_cannot_change_role_returns_403(
    authed_client_reception: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Reception PATCH /users/{id}/role → 403 forbidden (UPDATE, USERS is OWNER_ONLY)."""
    target = await _seed_reception(db_session, email="rbac-target@example.com")

    r = await authed_client_reception.patch(
        f"/api/v1/users/{target.id}/role",
        json={"role": "owner"},
        headers=_csrf(authed_client_reception),
    )
    assert r.status_code == 403, r.text
    assert r.json()["code"] == "forbidden"


async def test_owner_patch_without_csrf_returns_403(
    authed_client_owner: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Owner PATCH /{user_id}/role without X-CSRF-Token header → 403 csrf_mismatch."""
    target = await _seed_reception(db_session, email="csrf-target@example.com")

    r = await authed_client_owner.patch(
        f"/api/v1/users/{target.id}/role",
        json={"role": "owner"},
        # Deliberately omit _csrf() headers — verify_csrf must fire.
    )
    assert r.status_code == 403, r.text
    assert r.json()["code"] == "csrf_mismatch"


# ---------------------------------------------------------------------------
# Self-guard test
# ---------------------------------------------------------------------------


async def test_owner_cannot_change_own_role_returns_409(
    authed_client_owner: AsyncClient,
    current_owner_user_id: UUID,
) -> None:
    """Owner attempting to change their own role → 409 cannot_change_own_role."""
    r = await authed_client_owner.patch(
        f"/api/v1/users/{current_owner_user_id}/role",
        json={"role": "reception"},
        headers=_csrf(authed_client_owner),
    )
    assert r.status_code == 409, r.text
    assert r.json()["code"] == "cannot_change_own_role"


# ---------------------------------------------------------------------------
# Last-owner guard test
# ---------------------------------------------------------------------------


async def test_owner_cannot_demote_last_owner_returns_409(
    authed_client_owner: AsyncClient,
    single_active_owner_id: UUID,
    current_owner_user_id: UUID,
) -> None:
    """Demoting the last remaining active owner → 409 (last-owner guard or self-guard).

    The single_active_owner_id fixture deactivates every extra owner so the
    last-owner guard precondition holds. In the seeded configuration
    single_active_owner_id == current_owner_user_id, so the self-guard fires
    BEFORE the last-owner branch (mirrors deactivate_user behaviour — accept
    either code per the plan-text fallback).
    """
    r = await authed_client_owner.patch(
        f"/api/v1/users/{single_active_owner_id}/role",
        json={"role": "reception"},
        headers=_csrf(authed_client_owner),
    )
    assert r.status_code == 409, r.text
    code = r.json()["code"]
    assert code in ("cannot_change_last_owner_role", "cannot_change_own_role"), code


# ---------------------------------------------------------------------------
# Audit row assertion
# ---------------------------------------------------------------------------


async def test_successful_role_change_writes_audit_row(
    authed_client_owner: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """A successful role change emits a user_role_changed audit row in the same UoW.

    Asserts that audit_log has exactly one row with:
      - action = 'user_role_changed'
      - resource_type = 'user'
      - resource_id = target.id
      - payload includes old_role and new_role
    """
    target = await _seed_reception(db_session, email="audit-role-check@example.com")
    target_id: UUID = target.id

    r = await authed_client_owner.patch(
        f"/api/v1/users/{target_id}/role",
        json={"role": "owner"},
        headers=_csrf(authed_client_owner),
    )
    assert r.status_code == 204, r.text

    audit_rows = (
        await db_session.execute(
            select(AuditLog).where(
                AuditLog.action == "user_role_changed",
                AuditLog.resource_id == target_id,
            )
        )
    ).scalars().all()

    assert len(audit_rows) == 1, (
        f"Expected 1 user_role_changed audit row for target {target_id}, "
        f"found {len(audit_rows)}"
    )

    row = audit_rows[0]
    assert row.resource_type == "user", f"Unexpected resource_type: {row.resource_type}"
    assert row.payload["old_role"] == "reception", f"old_role wrong: {row.payload}"
    assert row.payload["new_role"] == "owner", f"new_role wrong: {row.payload}"
    assert row.payload["changed_user_id"] == str(target_id), (
        f"changed_user_id wrong: {row.payload}"
    )


# ---------------------------------------------------------------------------
# WR-03 — role change on inactive user is rejected
# ---------------------------------------------------------------------------


async def test_role_change_on_inactive_user_returns_409(
    authed_client_owner: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """PATCH role on a deactivated user → 409 cannot_change_inactive_user_role.

    WR-03 — the endpoint is the security boundary; a deactivated user's role
    must not be silently mutated even though the FE hides the action.
    """
    target = await _seed_inactive_reception(db_session)

    r = await authed_client_owner.patch(
        f"/api/v1/users/{target.id}/role",
        json={"role": "owner"},
        headers=_csrf(authed_client_owner),
    )
    assert r.status_code == 409, r.text
    assert r.json()["code"] == "cannot_change_inactive_user_role"

    # Role unchanged in the DB.
    await db_session.refresh(target)
    assert target.role == Role.RECEPTION


# ---------------------------------------------------------------------------
# WR-04 — no-op role change is rejected and emits NO audit row
# ---------------------------------------------------------------------------


async def test_noop_role_change_returns_409_and_writes_no_audit(
    authed_client_owner: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """PATCH role == current role → 409 role_unchanged, NO user_role_changed audit.

    WR-04 — the no-op is rejected BEFORE mutate/emit so no phantom audit row
    (old_role == new_role) pollutes the forensic trail.
    """
    target = await _seed_reception(db_session, email="noop-role-check@example.com")
    target_id: UUID = target.id

    r = await authed_client_owner.patch(
        f"/api/v1/users/{target_id}/role",
        json={"role": "reception"},  # same as current role
        headers=_csrf(authed_client_owner),
    )
    assert r.status_code == 409, r.text
    assert r.json()["code"] == "role_unchanged"

    # No user_role_changed audit row was written for this target.
    audit_rows = (
        (
            await db_session.execute(
                select(AuditLog).where(
                    AuditLog.action == "user_role_changed",
                    AuditLog.resource_id == target_id,
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(audit_rows) == 0, (
        f"Expected NO user_role_changed audit row for no-op on {target_id}, "
        f"found {len(audit_rows)}"
    )
