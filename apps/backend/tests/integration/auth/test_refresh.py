"""Integration tests for /api/v1/auth/refresh (TEST-04 / AUTH-05 / AUTH-06).

Three scenarios:
  1. Happy rotation: login → refresh → row gets replaced_by_id + replaced_at;
     new refresh cookie value differs from the old.
  2. Race-window same-pair return: two refresh calls with the SAME old refresh
     cookie within 5s → both return the same new pair (D-13 branch B via the
     auth:rotate:{old_hash} cache).
  3. Family reuse outside the window: present an old token AFTER its rotation
     chain has been mutated such that the cache is gone → family revoked,
     structlog event=family_reuse_detected emitted, response is 401.
"""

from __future__ import annotations

import hashlib

import pytest_asyncio
from fastapi import FastAPI
from httpx import AsyncClient
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from structlog.testing import capture_logs

from app.core.audit_models import AuditLog
from app.core.permissions import Role
from app.core.security import hash_password
from app.modules.auth.models import RefreshToken, User

OWNER_EMAIL = "owner-refresh@example.com"
OWNER_PASSWORD = "hunter22hunter22"  # noqa: S105 — test password literal


@pytest_asyncio.fixture
async def redis_clean(app: FastAPI) -> Redis:
    client: Redis = app.state.redis
    await client.flushdb()
    return client


@pytest_asyncio.fixture
async def seeded_owner(db_session: AsyncSession, redis_clean: Redis) -> User:
    user = User(
        email=OWNER_EMAIL,
        password_hash=await hash_password(OWNER_PASSWORD),
        role=Role.OWNER,
        full_name="Refresh Owner",
    )
    db_session.add(user)
    await db_session.commit()
    return user


async def _login(client: AsyncClient) -> str:
    """Log in and return the raw sz_refresh cookie value."""
    r = await client.post(
        "/api/v1/auth/login",
        json={"email": OWNER_EMAIL, "password": OWNER_PASSWORD},
    )
    assert r.status_code == 200, r.text
    return client.cookies["sz_refresh"]


def _sha256_hex(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


async def test_refresh_happy_rotates_token(
    async_client: AsyncClient,
    db_session: AsyncSession,
    seeded_owner: User,
) -> None:
    old_refresh = await _login(async_client)
    old_hash = _sha256_hex(old_refresh)

    r = await async_client.post("/api/v1/auth/refresh")
    assert r.status_code == 200, r.text
    new_refresh = async_client.cookies["sz_refresh"]
    assert new_refresh != old_refresh

    # Verify the old row got replaced_by_id + replaced_at populated.
    # NOTE: the auth router commits via service; the SAVEPOINT outer-tx still
    # sees the data via the same connection (Plan 07 fixture).
    old_row = await db_session.scalar(
        select(RefreshToken).where(RefreshToken.token_hash == old_hash)
    )
    assert old_row is not None
    assert old_row.replaced_by_id is not None
    assert old_row.replaced_at is not None


async def test_refresh_race_window_returns_same_pair(
    async_client: AsyncClient,
    seeded_owner: User,
) -> None:
    """Replay the SAME old sz_refresh cookie twice within 5s → same new pair (D-13)."""
    await _login(async_client)
    old_refresh = async_client.cookies["sz_refresh"]

    # First refresh — rotates and caches the new pair at auth:rotate:{old_hash}.
    r1 = await async_client.post("/api/v1/auth/refresh")
    assert r1.status_code == 200, r1.text
    new_refresh_1 = async_client.cookies["sz_refresh"]
    assert new_refresh_1 != old_refresh

    # Replay the OLD sz_refresh by overriding only this request's cookie jar.
    # We replace the NEW sz_refresh in the client jar with the OLD value so the
    # outgoing request carries old_refresh (httpx merges request `cookies=` with
    # the jar; managing the jar directly avoids ambiguous duplicates).
    async_client.cookies.delete("sz_refresh")
    async_client.cookies.set("sz_refresh", old_refresh, path="/api/v1/auth")

    # Second refresh — should hit branch B (replaced-within-window) and return
    # the same new pair from cache. We read the new value off the response (jar
    # contents may end up with multi-domain duplicates after the round-trip,
    # which makes `async_client.cookies['sz_refresh']` ambiguous).
    r2 = await async_client.post("/api/v1/auth/refresh")
    assert r2.status_code == 200, r2.text
    new_refresh_2 = r2.cookies["sz_refresh"]
    assert new_refresh_2 == new_refresh_1, "Same cached new pair must be returned"


async def test_refresh_reuse_revokes_family(
    async_client: AsyncClient,
    db_session: AsyncSession,
    redis_clean: Redis,
    seeded_owner: User,
) -> None:
    """Replay after cache expiry → family revoked + family_reuse_detected (D-13 branch C)."""
    await _login(async_client)
    old_refresh = async_client.cookies["sz_refresh"]
    old_hash = _sha256_hex(old_refresh)

    # First refresh — rotation chain established.
    r1 = await async_client.post("/api/v1/auth/refresh")
    assert r1.status_code == 200

    # Drop the race-window cache so branch B falls through to branch C.
    await redis_clean.delete(f"auth:rotate:{old_hash}")

    # Restore the old refresh cookie and try to use it again.
    async_client.cookies.delete("sz_refresh")
    async_client.cookies.set("sz_refresh", old_refresh, path="/api/v1/auth")

    with capture_logs() as captured:
        r2 = await async_client.post("/api/v1/auth/refresh")

    assert r2.status_code == 401, r2.text
    assert r2.json()["code"] == "invalid_token"

    # Audit log assertion — event=family_reuse_detected emitted (D-20).
    events = [c.get("event") for c in captured]
    assert "family_reuse_detected" in events

    # DB assertion — every alive refresh-token row for this user is now revoked.
    rows = (
        await db_session.scalars(
            select(RefreshToken).where(RefreshToken.user_id == seeded_owner.id)
        )
    ).all()
    assert len(rows) >= 2  # original + first rotation
    for row in rows:
        assert row.revoked_at is not None, f"row {row.id} should be revoked"


async def test_refresh_without_cookie_returns_401(
    async_client: AsyncClient,
    redis_clean: Redis,
) -> None:
    r = await async_client.post("/api/v1/auth/refresh")
    assert r.status_code == 401
    assert r.json()["code"] == "invalid_token"


async def test_refresh_reuse_writes_family_reuse_detected_audit_row(
    async_client: AsyncClient,
    db_session: AsyncSession,
    redis_clean: Redis,
    seeded_owner: User,
) -> None:
    """AUDIT-02: refresh-token reuse outside the race window writes
    family_reuse_detected audit row (D-04 row 5)."""
    await _login(async_client)
    old_refresh = async_client.cookies["sz_refresh"]
    old_hash = _sha256_hex(old_refresh)

    r1 = await async_client.post("/api/v1/auth/refresh")
    assert r1.status_code == 200

    # Drop the race-window cache so branch B falls through to branch C.
    await redis_clean.delete(f"auth:rotate:{old_hash}")

    async_client.cookies.delete("sz_refresh")
    async_client.cookies.set("sz_refresh", old_refresh, path="/api/v1/auth")

    r2 = await async_client.post("/api/v1/auth/refresh")
    assert r2.status_code == 401, r2.text

    rows = (
        await db_session.scalars(
            select(AuditLog).where(AuditLog.action == "family_reuse_detected")
        )
    ).all()
    assert len(rows) >= 1
    row = rows[-1]
    assert row.actor_user_id == seeded_owner.id
    assert row.resource_type == "session"
    assert row.resource_id is not None  # family_id
