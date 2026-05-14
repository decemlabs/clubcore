"""Shared fixtures for trainers integration tests (Phase 31 TRN-01..07).

Provides authed httpx clients for owner + reception roles backed by REAL
seeded users authenticated via the production /api/v1/auth/login flow.
The cookie jar carries `sz_access`, `sz_refresh`, `sportzal_csrf` after
login, so subsequent calls go through the full RBAC chain.

Mirrors the clients integration conftest pattern verbatim.
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

TRAINERS_OWNER_EMAIL = "trainers-owner@example.com"
TRAINERS_OWNER_PASSWORD = "hunter22hunter22"  # noqa: S105 -- test password literal
TRAINERS_RECEPTION_EMAIL = "trainers-reception@example.com"
TRAINERS_RECEPTION_PASSWORD = "hunter22hunter22"  # noqa: S105 -- test password literal

VALID_TRAINER: dict[str, Any] = {
    "fullName": "Иванов Иван",
    "phone": "+79991234567",
}


def _csrf_headers(client: AsyncClient) -> dict[str, str]:
    return {"X-CSRF-Token": client.cookies.get("sportzal_csrf", "")}


async def _create(
    authed: AsyncClient,
    *,
    phone: str | None = "+79991234567",
    full_name: str = "Тестовый Тренер",
) -> dict[str, Any]:
    """Helper to create a trainer and return the response data dict."""
    payload: dict[str, Any] = {"fullName": full_name}
    if phone is not None:
        payload["phone"] = phone
    r = await authed.post(
        "/api/v1/trainers",
        json=payload,
        headers=_csrf_headers(authed),
    )
    assert r.status_code == 201, r.text
    data: dict[str, Any] = r.json()["data"]
    return data


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
    """Insert a User row in the SAVEPOINT-rolled session."""
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
        email=TRAINERS_OWNER_EMAIL,
        password=TRAINERS_OWNER_PASSWORD,
        full_name="Trainers Owner",
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
        email=TRAINERS_RECEPTION_EMAIL,
        password=TRAINERS_RECEPTION_PASSWORD,
        full_name="Trainers Reception",
    )


@pytest_asyncio.fixture
async def _trainer_app_overrides(
    app: FastAPI,
    db_session: AsyncSession,
) -> AsyncIterator[FastAPI]:
    """Install dependency overrides on `app` so route handlers see the
    SAVEPOINT-rolled session and the lifespan-bound Redis singleton."""

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
    _trainer_app_overrides: FastAPI,
    seeded_owner: User,
) -> AsyncIterator[AsyncClient]:
    """Authenticated httpx client for the seeded owner (cookies in jar)."""
    transport = ASGITransport(app=_trainer_app_overrides)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        await _login(client, email=TRAINERS_OWNER_EMAIL, password=TRAINERS_OWNER_PASSWORD)
        yield client


@pytest_asyncio.fixture
async def authed_client_reception(
    _trainer_app_overrides: FastAPI,
    seeded_reception: User,
) -> AsyncIterator[AsyncClient]:
    """Authenticated httpx client for the seeded reception user."""
    transport = ASGITransport(app=_trainer_app_overrides)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        await _login(
            client, email=TRAINERS_RECEPTION_EMAIL, password=TRAINERS_RECEPTION_PASSWORD
        )
        yield client
