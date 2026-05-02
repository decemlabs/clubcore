"""Integration tests for /api/v1/auth/login + /me (TEST-02, AUTH-EP-01..03, AUTH-LO-04).

Each test seeds an owner via the SAVEPOINT-rolled-back db_session fixture, then
exercises the endpoint via the ASGITransport-backed async_client. Cookie
attribute assertions match the helpers in app/core/security.py (Phase 4 D-25).
"""

from __future__ import annotations

import pytest_asyncio
from fastapi import FastAPI
from httpx import AsyncClient
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permissions import Role
from app.core.security import hash_password
from app.modules.auth.models import User

OWNER_EMAIL = "owner-login@example.com"
OWNER_PASSWORD = "hunter22hunter22"  # noqa: S105 — test password literal (16 chars >= AUTH-EP-05 floor of 12)
BAD_PASSWORD = "hunter22wrong-pw"  # noqa: S105 — test password literal


@pytest_asyncio.fixture
async def redis_clean(app: FastAPI) -> Redis:
    """Flush Redis between tests so rate-limit + session keys don't bleed."""
    client: Redis = app.state.redis
    await client.flushdb()
    return client


@pytest_asyncio.fixture
async def seeded_owner(db_session: AsyncSession, redis_clean: Redis) -> User:
    """Insert a seeded owner via the SAVEPOINT-rolled-back session."""
    user = User(
        email=OWNER_EMAIL,
        password_hash=await hash_password(OWNER_PASSWORD),
        role=Role.OWNER,
        full_name="Login Owner",
    )
    db_session.add(user)
    await db_session.commit()
    return user


async def test_login_happy_returns_envelope_and_three_cookies(
    async_client: AsyncClient,
    seeded_owner: User,
) -> None:
    response = await async_client.post(
        "/api/v1/auth/login",
        json={"email": OWNER_EMAIL, "password": OWNER_PASSWORD},
    )
    assert response.status_code == 200, response.text

    body = response.json()
    assert "data" in body
    assert body["data"]["user"]["fullName"] == "Login Owner"
    assert body["data"]["user"]["role"] == "owner"

    set_cookies = response.headers.get_list("set-cookie")
    joined = "\n".join(set_cookies)
    assert "sz_access=" in joined
    assert "sz_refresh=" in joined
    assert "sportzal_csrf=" in joined

    # sz_access — Path=/, HttpOnly, SameSite=Lax
    sz_access = next(c for c in set_cookies if c.startswith("sz_access="))
    assert "Path=/" in sz_access
    assert "HttpOnly" in sz_access
    assert "samesite=lax" in sz_access.lower()

    # sz_refresh — Path=/api/v1/auth, HttpOnly
    sz_refresh = next(c for c in set_cookies if c.startswith("sz_refresh="))
    assert "Path=/api/v1/auth" in sz_refresh
    assert "HttpOnly" in sz_refresh

    # sportzal_csrf — Path=/, NOT HttpOnly (frontend reads it for X-CSRF-Token)
    sz_csrf = next(c for c in set_cookies if c.startswith("sportzal_csrf="))
    assert "Path=/" in sz_csrf
    assert "HttpOnly" not in sz_csrf


async def test_login_invalid_password_returns_401(
    async_client: AsyncClient,
    seeded_owner: User,
) -> None:
    response = await async_client.post(
        "/api/v1/auth/login",
        json={"email": OWNER_EMAIL, "password": BAD_PASSWORD},
    )
    assert response.status_code == 401
    body = response.json()
    assert body["code"] == "invalid_credentials"


async def test_login_unknown_email_returns_401(
    async_client: AsyncClient,
    redis_clean: Redis,
) -> None:
    """User-not-found is timing-equivalent to wrong-password (AUTH-EP-02)."""
    response = await async_client.post(
        "/api/v1/auth/login",
        json={"email": "ghost@example.com", "password": "hunter22hunter22"},
    )
    assert response.status_code == 401
    assert response.json()["code"] == "invalid_credentials"


async def test_login_429_after_5_failures(
    async_client: AsyncClient,
    seeded_owner: User,
) -> None:
    """5 failed attempts within window → 6th returns 429 (AUTH-EP-03 / D-18)."""
    for _ in range(5):
        r = await async_client.post(
            "/api/v1/auth/login",
            json={"email": OWNER_EMAIL, "password": BAD_PASSWORD},
        )
        assert r.status_code == 401, r.text

    # 6th — counter is now at 5 → check_login_rate raises 429 before verify
    r6 = await async_client.post(
        "/api/v1/auth/login",
        json={"email": OWNER_EMAIL, "password": OWNER_PASSWORD},  # right pw, but rate-limited
    )
    assert r6.status_code == 429
    assert r6.json()["code"] == "rate_limited"


async def test_me_unauthenticated_returns_401(
    async_client: AsyncClient,
) -> None:
    """GET /me without sz_access cookie → 401 (AUTH-LO-04)."""
    response = await async_client.get("/api/v1/auth/me")
    assert response.status_code == 401


async def test_me_authenticated_returns_user(
    async_client: AsyncClient,
    seeded_owner: User,
) -> None:
    """Login → /me returns {id, role, fullName, email, hasTelegram} (AUTH-LO-04)."""
    login = await async_client.post(
        "/api/v1/auth/login",
        json={"email": OWNER_EMAIL, "password": OWNER_PASSWORD},
    )
    assert login.status_code == 200

    # AsyncClient preserves cookies; /me uses sz_access automatically
    me = await async_client.get("/api/v1/auth/me")
    assert me.status_code == 200, me.text
    body = me.json()
    assert body["data"]["email"] == OWNER_EMAIL
    assert body["data"]["fullName"] == "Login Owner"
    assert body["data"]["role"] == "owner"
    assert body["data"]["hasTelegram"] is False
