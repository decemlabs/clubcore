"""Shared fixtures for schedule integration tests (Phase 38 plan 38-01).

Mirrors tests/integration/pt_packages/conftest.py verbatim with role-specific
email constants (so schedule tests can run in parallel without collision on
the auth fixtures' seeded emails). Adds a `make_trainer` factory so Task 3
publish_slot tests can seed an active trainer row directly via the SAVEPOINT
session.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable, Callable
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
from app.modules.trainers.models import Trainer

OWNER_EMAIL = "sched-owner@example.com"
OWNER_PASSWORD = "hunter22hunter22"  # noqa: S105 -- test password literal (>=12 chars)
RECEPTION_EMAIL = "sched-reception@example.com"
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
    return await _seed_user(
        db_session,
        role=Role.OWNER,
        email=OWNER_EMAIL,
        password=OWNER_PASSWORD,
        full_name="Schedule Owner",
    )


@pytest_asyncio.fixture
async def seeded_reception(
    db_session: AsyncSession,
    redis_clean: Redis,
) -> User:
    return await _seed_user(
        db_session,
        role=Role.RECEPTION,
        email=RECEPTION_EMAIL,
        password=RECEPTION_PASSWORD,
        full_name="Schedule Reception",
    )


@pytest_asyncio.fixture
async def _client_app_overrides(
    app: FastAPI,
    db_session: AsyncSession,
) -> AsyncIterator[FastAPI]:
    """Install dependency overrides on `app` so route handlers see the
    SAVEPOINT-rolled session and the lifespan-bound Redis singleton.
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
    transport = ASGITransport(app=_client_app_overrides)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        await _login(client, email=OWNER_EMAIL, password=OWNER_PASSWORD)
        yield client


@pytest_asyncio.fixture
async def authed_client_reception(
    _client_app_overrides: FastAPI,
    seeded_reception: User,
) -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=_client_app_overrides)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        await _login(client, email=RECEPTION_EMAIL, password=RECEPTION_PASSWORD)
        yield client


@pytest_asyncio.fixture
async def anon_client(
    _client_app_overrides: FastAPI,
) -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=_client_app_overrides)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client


# ---------------------------------------------------------------------------
# DB-direct factories (Task 3 consumers).
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def make_trainer(
    db_session: AsyncSession,
) -> Callable[..., Awaitable[Trainer]]:
    """Insert a Trainer row directly via the SAVEPOINT-mode session."""

    _counter = {"i": 0}

    async def _make(
        *,
        full_name: str | None = None,
        is_active: bool = True,
        phone: str | None = None,
    ) -> Trainer:
        _counter["i"] += 1
        trainer = Trainer(
            full_name=full_name or f"Trainer {_counter['i']}",
            phone=phone,
            is_active=is_active,
        )
        db_session.add(trainer)
        await db_session.commit()
        await db_session.refresh(trainer)
        return trainer

    return _make
