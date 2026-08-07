"""Integration tests for POST /api/v1/auth/change-password (PROF-02).

Covers (Phase 109 Task 3):
  1. Happy + revoke-others-keeps-current — two separate clients (A and B) share
     the same user session; Client A changes the password; Client B's refresh
     family is revoked; Client A's family stays alive; Client A GET /me still 200.
  2. Wrong current password → 401 invalid_credentials; no families revoked;
     password_hash unchanged.
  3. New password too short (< 12 chars) → 422 (Pydantic min_length floor).
  4. CSRF required → 403 csrf_mismatch.
  5. Auth required → 401 invalid_token (RBAC-04: auth dep fires before csrf dep).
  6. Audit row — password_changed_revokes_sessions with family_count = others-
     revoked; payload contains no password/hash.
  7. Old password no longer logs in; new password succeeds.

Harness: SAVEPOINT rollback + ASGITransport async_client from root conftest.py.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit_models import AuditLog
from app.core.database import get_db
from app.core.permissions import Role
from app.core.redis import get_redis
from app.core.security import hash_password
from app.modules.auth.models import RefreshToken, User

pytestmark = pytest.mark.asyncio

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CHPW_OWNER_EMAIL = "chpw-owner@example.com"
CHPW_OWNER_PASSWORD = "original22password"  # noqa: S105 — test password
CHPW_NEW_PASSWORD = "brandnewpass12"  # noqa: S105 — test password, 12-char floor met


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def redis_clean(app: FastAPI) -> Redis:
    """Flush Redis between tests so session keys don't bleed."""
    client: Redis = app.state.redis
    await client.flushdb()
    return client


@pytest_asyncio.fixture
async def seeded_owner(db_session: AsyncSession, redis_clean: Redis) -> User:
    """Insert an owner user with known credentials."""
    _ = redis_clean
    user = User(
        email=CHPW_OWNER_EMAIL,
        password_hash=await hash_password(CHPW_OWNER_PASSWORD),
        role=Role.OWNER,
        full_name="ChPw Owner",
    )
    db_session.add(user)
    await db_session.commit()
    return user


async def _login_with_client(client: AsyncClient) -> None:
    """Login seeded owner via a given AsyncClient."""
    r = await client.post(
        "/api/v1/auth/login",
        json={"email": CHPW_OWNER_EMAIL, "password": CHPW_OWNER_PASSWORD},
    )
    assert r.status_code == 200, f"Login failed: {r.text}"


def _make_client(app: FastAPI, db_session: AsyncSession) -> AsyncClient:
    """Build a fresh ASGITransport AsyncClient sharing the SAVEPOINT session."""

    async def _override_get_db() -> AsyncIterator[AsyncSession]:
        yield db_session

    def _override_get_redis() -> Any:
        return app.state.redis

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_redis] = _override_get_redis

    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test")


# ---------------------------------------------------------------------------
# Test 1: revoke-others-keeps-current
# ---------------------------------------------------------------------------


async def test_change_password_revokes_others_keeps_current(
    app: FastAPI,
    db_session: AsyncSession,
    seeded_owner: User,
) -> None:
    """PROF-02 core: change-password from Client A revokes Client B's family;
    Client A's family stays alive and GET /me still returns 200 for Client A.
    """
    async with _make_client(app, db_session) as client_a, _make_client(app, db_session) as client_b:
        # Login from two independent clients — two distinct refresh families.
        await _login_with_client(client_a)
        await _login_with_client(client_b)

        # Snapshot Client B's refresh family from DB before the password change.
        b_refresh_cookie = client_b.cookies.get("cc_refresh")
        assert b_refresh_cookie is not None, "Client B must have a cc_refresh cookie"

        # Client A changes the password.
        r = await client_a.post(
            "/api/v1/auth/change-password",
            json={
                "currentPassword": CHPW_OWNER_PASSWORD,
                "newPassword": CHPW_NEW_PASSWORD,
            },
            headers={"X-CSRF-Token": client_a.cookies["clubcore_csrf"]},
        )
        assert r.status_code == 204, f"Expected 204, got {r.status_code}: {r.text}"
        assert r.content == b"", "204 response must have empty body"

        # ---- DB assertions ----
        # Client B's refresh family must be revoked.
        import hashlib as _hl

        b_hash = _hl.sha256(b_refresh_cookie.encode()).hexdigest()
        b_row = await db_session.scalar(
            select(RefreshToken).where(RefreshToken.token_hash == b_hash)
        )
        assert b_row is not None, "Client B's RefreshToken row must still exist"
        assert b_row.revoked_at is not None, (
            "Client B's refresh family must be revoked after change-password"
        )

        # Client A's refresh family must be ALIVE.
        a_refresh_cookie = client_a.cookies.get("cc_refresh")
        assert a_refresh_cookie is not None, "Client A must still have a cc_refresh cookie"
        a_hash = _hl.sha256(a_refresh_cookie.encode()).hexdigest()
        a_row = await db_session.scalar(
            select(RefreshToken).where(RefreshToken.token_hash == a_hash)
        )
        assert a_row is not None, "Client A's RefreshToken row must exist"
        assert a_row.revoked_at is None, (
            "Client A's refresh family must remain alive after change-password"
        )

        # Client A's GET /me still returns 200 — current session preserved.
        me_r = await client_a.get("/api/v1/auth/me")
        assert me_r.status_code == 200, (
            f"Client A GET /me must still succeed after change-password: {me_r.text}"
        )


# ---------------------------------------------------------------------------
# Test 2: wrong current password → 401, no revocation, hash unchanged
# ---------------------------------------------------------------------------


async def test_change_password_wrong_current_password(
    async_client: AsyncClient,
    db_session: AsyncSession,
    seeded_owner: User,
) -> None:
    """Wrong currentPassword → 401 invalid_credentials; no families revoked; hash unchanged."""
    await _login_with_client(async_client)

    # Count alive families before the call.
    alive_before = (
        await db_session.scalars(
            select(RefreshToken).where(
                RefreshToken.user_id == seeded_owner.id,
                RefreshToken.revoked_at.is_(None),
            )
        )
    ).all()

    r = await async_client.post(
        "/api/v1/auth/change-password",
        json={"currentPassword": "definitelywrong22", "newPassword": CHPW_NEW_PASSWORD},
        headers={"X-CSRF-Token": async_client.cookies["clubcore_csrf"]},
    )
    assert r.status_code == 401, (
        f"Wrong current password must return 401, got {r.status_code}: {r.text}"
    )
    body = r.json()
    assert body.get("code") == "invalid_credentials", f"Expected code='invalid_credentials': {body}"

    # No families must have been revoked.
    alive_after = (
        await db_session.scalars(
            select(RefreshToken).where(
                RefreshToken.user_id == seeded_owner.id,
                RefreshToken.revoked_at.is_(None),
            )
        )
    ).all()
    assert len(alive_after) == len(alive_before), (
        "Wrong-password attempt must not revoke any session families"
    )

    # DB User hash must be unchanged — confirm the original password still logs in.
    login_check = await async_client.post(
        "/api/v1/auth/login",
        json={"email": CHPW_OWNER_EMAIL, "password": CHPW_OWNER_PASSWORD},
    )
    assert login_check.status_code == 200, "Original password must still work after rejected change"


# ---------------------------------------------------------------------------
# Test 3: new password too short → 422
# ---------------------------------------------------------------------------


async def test_change_password_new_password_too_short(
    async_client: AsyncClient,
    seeded_owner: User,
) -> None:
    """newPassword shorter than 12 chars → 422 (Pydantic min_length floor)."""
    await _login_with_client(async_client)

    r = await async_client.post(
        "/api/v1/auth/change-password",
        json={"currentPassword": CHPW_OWNER_PASSWORD, "newPassword": "short"},
        headers={"X-CSRF-Token": async_client.cookies["clubcore_csrf"]},
    )
    assert r.status_code == 422, (
        f"Password shorter than 12 chars must return 422, got {r.status_code}: {r.text}"
    )


# ---------------------------------------------------------------------------
# Test 4: CSRF required → 403
# ---------------------------------------------------------------------------


async def test_change_password_without_csrf_returns_403(
    async_client: AsyncClient,
    seeded_owner: User,
) -> None:
    """Authenticated POST /change-password without X-CSRF-Token → 403 csrf_mismatch."""
    await _login_with_client(async_client)

    r = await async_client.post(
        "/api/v1/auth/change-password",
        json={"currentPassword": CHPW_OWNER_PASSWORD, "newPassword": CHPW_NEW_PASSWORD},
        # Deliberately omit the X-CSRF-Token header.
    )
    assert r.status_code == 403, f"Expected 403, got {r.status_code}: {r.text}"
    assert r.json()["code"] == "csrf_mismatch"


# ---------------------------------------------------------------------------
# Test 5: auth required → 401 (RBAC-04)
# ---------------------------------------------------------------------------


async def test_change_password_without_auth_returns_401(
    async_client: AsyncClient,
) -> None:
    """No session cookies → 401 (auth dep fires before csrf dep, RBAC-04 D-22)."""
    # No _login call — empty cookie jar.
    r = await async_client.post(
        "/api/v1/auth/change-password",
        json={"currentPassword": CHPW_OWNER_PASSWORD, "newPassword": CHPW_NEW_PASSWORD},
    )
    assert r.status_code == 401, f"Expected 401, got {r.status_code}: {r.text}"
    assert r.json()["code"] == "invalid_token"


# ---------------------------------------------------------------------------
# Test 6: audit row — password_changed_revokes_sessions with family_count
# ---------------------------------------------------------------------------


async def test_change_password_writes_audit_row(
    app: FastAPI,
    db_session: AsyncSession,
    seeded_owner: User,
) -> None:
    """Successful change-password writes a password_changed_revokes_sessions audit row.

    Payload must carry family_count = number of OTHER families revoked, and
    must not contain any password or hash values.
    """
    async with _make_client(app, db_session) as client_a, _make_client(app, db_session) as client_b:
        # Two logins → two families so "others" count is 1.
        await _login_with_client(client_a)
        await _login_with_client(client_b)

        r = await client_a.post(
            "/api/v1/auth/change-password",
            json={
                "currentPassword": CHPW_OWNER_PASSWORD,
                "newPassword": CHPW_NEW_PASSWORD,
            },
            headers={"X-CSRF-Token": client_a.cookies["clubcore_csrf"]},
        )
        assert r.status_code == 204, r.text

        rows = (
            await db_session.scalars(
                select(AuditLog).where(
                    AuditLog.action == "password_changed_revokes_sessions",
                    AuditLog.actor_user_id == seeded_owner.id,
                )
            )
        ).all()
        assert len(rows) >= 1, "Audit row must be committed atomically (Pitfall 2)"

        row = rows[0]
        assert row.resource_type == "user"
        assert row.resource_id == seeded_owner.id

        payload = row.payload
        # family_count must equal the number of OTHER families revoked (1).
        assert "family_count" in payload, f"Audit payload missing family_count: {payload}"
        assert payload["family_count"] == 1, (
            f"family_count must equal 1 (one other family revoked): {payload}"
        )

        # No password/hash values in the payload.
        payload_str = str(payload)
        assert "password" not in payload_str.lower(), (
            f"Audit payload must not leak password: {payload}"
        )
        assert "hash" not in payload_str.lower(), f"Audit payload must not leak hash: {payload}"


# ---------------------------------------------------------------------------
# Test 7: new password works; old password fails
# ---------------------------------------------------------------------------


async def test_change_password_new_pw_logs_in_old_pw_does_not(
    app: FastAPI,
    db_session: AsyncSession,
    seeded_owner: User,
) -> None:
    """After a successful change-password: new password → 200 login; old → 401."""
    async with _make_client(app, db_session) as client_a:
        await _login_with_client(client_a)

        r = await client_a.post(
            "/api/v1/auth/change-password",
            json={
                "currentPassword": CHPW_OWNER_PASSWORD,
                "newPassword": CHPW_NEW_PASSWORD,
            },
            headers={"X-CSRF-Token": client_a.cookies["clubcore_csrf"]},
        )
        assert r.status_code == 204, r.text

    # Independent fresh client — no cookie jar from previous sessions.
    async with _make_client(app, db_session) as fresh_client:
        # Old password must fail.
        old_login = await fresh_client.post(
            "/api/v1/auth/login",
            json={"email": CHPW_OWNER_EMAIL, "password": CHPW_OWNER_PASSWORD},
        )
        assert old_login.status_code == 401, (
            f"Old password must not work after change-password: {old_login.text}"
        )

        # New password must succeed.
        new_login = await fresh_client.post(
            "/api/v1/auth/login",
            json={"email": CHPW_OWNER_EMAIL, "password": CHPW_NEW_PASSWORD},
        )
        assert new_login.status_code == 200, (
            f"New password must log in after change-password: {new_login.text}"
        )
