"""RBAC integration test fixtures (Phase 6 D-11, D-12).

Provides a sibling FastAPI app fixture that mounts the test-only
`tests/_fixtures/owner_routes.py` router. Production `create_app()` is
UNCHANGED (D-12). Plus owner_client / reception_client fixtures backed by
real seeded users authenticated via the actual /api/v1/auth/login flow.

Topology:
  - `app_with_fixture_routes` is a SIBLING of the root `app` fixture, not a
    replacement. Phase 5 tests continue using the root `app`. Only RBAC tests
    opt into this variant.
  - `rbac_async_client` is bound to `app_with_fixture_routes` (the root
    `async_client` is bound to the root `app`).
  - `reception_client` uses a fresh AsyncClient so its cookies do not collide
    with `owner_client`'s cookie jar.
  - `db_session` is inherited from the root conftest (Phase 5 D-22 — SAVEPOINT
    rollback wipes seeded users at teardown).
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

import pytest_asyncio
from asgi_lifespan import LifespanManager
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.permissions import Role
from app.core.redis import get_redis
from app.core.security import hash_password
from app.main import create_app
from app.modules.auth.models import User
from tests._fixtures.owner_routes import router as _owner_routes_router

OWNER_EMAIL = "rbac-owner@example.com"
OWNER_PASSWORD = "hunter22hunter22"  # noqa: S105 — test password literal
RECEPTION_EMAIL = "rbac-reception@example.com"
RECEPTION_PASSWORD = "hunter22hunter22"  # noqa: S105 — test password literal


@pytest_asyncio.fixture
async def app_with_fixture_routes(
    db_session: AsyncSession,
) -> AsyncIterator[FastAPI]:
    """FastAPI instance with lifespan + the OWNER_ONLY stub router mounted (D-12 Option A).

    Mirrors the root `app` fixture (tests/conftest.py) but additionally
    mounts the test-only fixture router. Overrides `get_db` to use the
    SAVEPOINT-rolled session and `get_redis` to expose the lifespan-bound
    client — same pattern as the root `async_client` fixture.
    """
    _app = create_app()
    _app.include_router(_owner_routes_router)

    async with LifespanManager(_app):
        async def _override_get_db() -> AsyncIterator[AsyncSession]:
            yield db_session

        def _override_get_redis() -> Any:
            # Mirrors app.core.redis.get_redis: returns the process-singleton
            # client bound on app.state.redis (no per-request connection).
            return _app.state.redis

        _app.dependency_overrides[get_db] = _override_get_db
        _app.dependency_overrides[get_redis] = _override_get_redis
        try:
            yield _app
        finally:
            _app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def rbac_redis_clean(app_with_fixture_routes: FastAPI) -> Redis:
    """Flush Redis between tests so rate-limit + session keys don't bleed."""
    client: Redis = app_with_fixture_routes.state.redis
    await client.flushdb()
    return client


async def _seed_user(
    db_session: AsyncSession,
    *,
    role: Role,
    email: str,
    password: str,
) -> User:
    """Insert a User row in the SAVEPOINT-rolled session (Phase 5 D-22).

    The outer transaction rollback wipes the row at test teardown — no
    cross-test data leak.
    """
    user = User(
        email=email,
        password_hash=await hash_password(password),
        role=role,
        full_name=f"RBAC {role.value}",
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
async def rbac_async_client(
    app_with_fixture_routes: FastAPI,
) -> AsyncIterator[AsyncClient]:
    """Anonymous httpx client bound to the fixture-router-mounted app."""
    transport = ASGITransport(app=app_with_fixture_routes)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client


@pytest_asyncio.fixture
async def owner_client(
    app_with_fixture_routes: FastAPI,
    db_session: AsyncSession,
    rbac_redis_clean: Redis,
) -> AsyncIterator[AsyncClient]:
    """Authenticated client for a seeded OWNER user (cookies in jar).

    Uses a dedicated AsyncClient so its cookie jar does not collide with
    `reception_client` when both fixtures are pulled in by the same test.
    """
    await _seed_user(
        db_session, role=Role.OWNER, email=OWNER_EMAIL, password=OWNER_PASSWORD
    )
    transport = ASGITransport(app=app_with_fixture_routes)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        await _login(client, email=OWNER_EMAIL, password=OWNER_PASSWORD)
        yield client


@pytest_asyncio.fixture
async def reception_client(
    app_with_fixture_routes: FastAPI,
    db_session: AsyncSession,
    rbac_redis_clean: Redis,
) -> AsyncIterator[AsyncClient]:
    """Authenticated client for a seeded RECEPTION user (cookies in jar).

    Uses a SEPARATE httpx client (cannot share with `owner_client` because both
    mint cookies in the same jar — they would collide). Mounts a fresh
    ASGITransport against the same app instance.
    """
    await _seed_user(
        db_session,
        role=Role.RECEPTION,
        email=RECEPTION_EMAIL,
        password=RECEPTION_PASSWORD,
    )
    transport = ASGITransport(app=app_with_fixture_routes)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        await _login(client, email=RECEPTION_EMAIL, password=RECEPTION_PASSWORD)
        yield client
