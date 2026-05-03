"""Shared fixtures for clients integration tests (Phase 8 Plan 08-08).

Provides authed httpx clients for owner + reception roles backed by REAL
seeded users authenticated via the production /api/v1/auth/login flow.
The cookie jar carries `sz_access`, `sz_refresh`, `sportzal_csrf` after
login, so subsequent calls go through the full RBAC chain (decode JWT
-> loader -> require_permission -> can()).

The `authed_client_*` fixtures pull the root `async_client` (which has
`get_db` overridden to share the SAVEPOINT-rolled `db_session`) and
re-issue cookies into a FRESH AsyncClient bound to the same app — so
the cookie jars are isolated per role but the underlying session
(visible to route handlers via the dependency override) is the same
one tests query directly.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.permissions import Role
from app.core.redis import get_redis
from app.core.security import hash_password
from app.modules.auth.models import User

OWNER_EMAIL = "clients-owner@example.com"
OWNER_PASSWORD = "hunter22hunter22"  # noqa: S105 -- test password literal (>=12 chars)
RECEPTION_EMAIL = "clients-reception@example.com"
RECEPTION_PASSWORD = "hunter22hunter22"  # noqa: S105 -- test password literal


@pytest_asyncio.fixture
async def redis_clean(app: FastAPI) -> Redis:
    """Flush Redis between tests so rate-limit + session keys don't bleed."""
    client: Redis = app.state.redis
    await client.flushdb()
    return client


async def _seed_user(
    db_session: AsyncSession,
    *,
    role: Role,
    email: str,
    password: str,
    full_name: str,
) -> User:
    """Insert a User row in the SAVEPOINT-rolled session (Phase 5 D-22)."""
    user = User(
        email=email,
        password_hash=await hash_password(password),
        role=role,
        full_name=full_name,
    )
    db_session.add(user)
    await db_session.commit()
    return user


async def _login(client: AsyncClient, *, email: str, password: str) -> None:
    r = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert r.status_code == 200, r.text


@pytest_asyncio.fixture
async def seeded_owner(
    db_session: AsyncSession,
    redis_clean: Redis,
) -> User:
    """Owner user seeded via SAVEPOINT-rolled session (rolls back at teardown)."""
    return await _seed_user(
        db_session,
        role=Role.OWNER,
        email=OWNER_EMAIL,
        password=OWNER_PASSWORD,
        full_name="Clients Owner",
    )


@pytest_asyncio.fixture
async def seeded_reception(
    db_session: AsyncSession,
    redis_clean: Redis,
) -> User:
    """Reception user seeded via SAVEPOINT-rolled session."""
    return await _seed_user(
        db_session,
        role=Role.RECEPTION,
        email=RECEPTION_EMAIL,
        password=RECEPTION_PASSWORD,
        full_name="Clients Reception",
    )


@pytest_asyncio.fixture
async def _client_app_overrides(
    app: FastAPI,
    db_session: AsyncSession,
) -> AsyncIterator[FastAPI]:
    """Install dependency overrides on `app` so route handlers see the
    SAVEPOINT-rolled session and the lifespan-bound Redis singleton.

    Mirrors the root `async_client` fixture (tests/conftest.py) — required
    because each `authed_client_*` fixture builds its own AsyncClient and
    must share the same overrides for routes to see seeded data and
    audit_log writes the test inspects directly.
    """

    async def _override_get_db() -> AsyncIterator[AsyncSession]:
        yield db_session

    def _override_get_redis() -> Any:
        return app.state.redis

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_redis] = _override_get_redis
    try:
        yield app
    finally:
        app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def authed_client_owner(
    _client_app_overrides: FastAPI,
    seeded_owner: User,
) -> AsyncIterator[AsyncClient]:
    """Authenticated httpx client for the seeded owner (cookies in jar).

    Uses a dedicated AsyncClient so the cookie jar is isolated from any
    other client fixture in the same test. The app passed in already has
    `get_db` / `get_redis` overrides installed by `_client_app_overrides`.
    """
    transport = ASGITransport(app=_client_app_overrides)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        await _login(client, email=OWNER_EMAIL, password=OWNER_PASSWORD)
        yield client


@pytest_asyncio.fixture
async def authed_client_reception(
    _client_app_overrides: FastAPI,
    seeded_reception: User,
) -> AsyncIterator[AsyncClient]:
    """Authenticated httpx client for the seeded reception user."""
    transport = ASGITransport(app=_client_app_overrides)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        await _login(client, email=RECEPTION_EMAIL, password=RECEPTION_PASSWORD)
        yield client
