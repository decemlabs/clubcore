"""Shared fixtures for pt_packages integration tests (Phase 33 Plan 33-01).

Mirrors tests/integration/memberships/conftest.py verbatim with role-specific
email constants (so PT-package tests can run in parallel with memberships
tests within the same session without collision on the auth fixtures'
seeded emails).

Plan 33-03 addition: ``db_session_real_commit`` fixture for REF-TEST-02
(concurrent PT-package refund race) — mirrors the membership sibling
verbatim, TRUNCATE list extended with pt_package_plans + pt_packages.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Any
from uuid import UUID

import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import get_settings
from app.core.database import get_db
from app.core.permissions import Role
from app.core.redis import get_redis
from app.core.security import hash_password
from app.modules.auth.models import User
from app.modules.clients.models import Client
from app.modules.pt_packages.models import PtPackage, PtPackagePlan

OWNER_EMAIL = "ptpkg-owner@example.com"
OWNER_PASSWORD = "hunter22hunter22"  # noqa: S105 -- test password literal (>=12 chars)
RECEPTION_EMAIL = "ptpkg-reception@example.com"
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
        full_name="PT-Package Owner",
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
        full_name="PT-Package Reception",
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


# ---------------------------------------------------------------------------
# DB-direct factories for tests that need to seed plan / package / client
# without going through the HTTP create flow (which would emit an audit row).
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def make_user(
    db_session: AsyncSession,
) -> Callable[..., Awaitable[User]]:
    """Insert a User row directly via the SAVEPOINT-mode session."""

    _counter = {"i": 0}

    async def _make(
        *,
        role: str = "owner",
        email: str | None = None,
        password: str = "hunter22hunter22",  # noqa: S107 -- test password literal
        full_name: str = "Test User",
    ) -> User:
        _counter["i"] += 1
        resolved_email = email or f"ptpkg-factory-{_counter['i']}@example.com"
        user = User(
            email=resolved_email,
            password_hash=await hash_password(password),
            role=Role(role),
            full_name=full_name,
        )
        db_session.add(user)
        await db_session.commit()
        await db_session.refresh(user)
        return user

    return _make


@pytest_asyncio.fixture
async def make_client(
    db_session: AsyncSession,
    make_user: Callable[..., Awaitable[User]],
) -> Callable[..., Awaitable[Client]]:
    """Insert a Client row directly via the SAVEPOINT-mode session."""

    _counter = {"i": 0}

    async def _make(
        *,
        last_name: str = "Петров",
        first_name: str = "Пётр",
        phone: str | None = None,
        created_by_user_id: UUID | None = None,
    ) -> Client:
        _counter["i"] += 1
        resolved_phone = phone or f"+799988760{_counter['i']:02d}"
        if created_by_user_id is None:
            owner = await make_user(role="owner")
            created_by_user_id = owner.id
        client = Client(
            last_name=last_name,
            first_name=first_name,
            phone=resolved_phone,
            created_by_user_id=created_by_user_id,
        )
        db_session.add(client)
        await db_session.commit()
        await db_session.refresh(client)
        return client

    return _make


@pytest_asyncio.fixture
async def make_pt_package_plan(
    db_session: AsyncSession,
) -> Callable[..., Awaitable[PtPackagePlan]]:
    """Insert a PtPackagePlan row directly (bypasses HTTP create + audit emit)."""

    _counter = {"i": 0}

    async def _make(
        *,
        name: str | None = None,
        session_count: int = 10,
        price_kopecks: int = 500000,
        validity_days: int | None = 90,
    ) -> PtPackagePlan:
        _counter["i"] += 1
        resolved_name = name or f"PT-PKG-{_counter['i']}"
        plan = PtPackagePlan(
            name=resolved_name,
            session_count=session_count,
            price_kopecks=price_kopecks,
            validity_days=validity_days,
        )
        db_session.add(plan)
        await db_session.commit()
        await db_session.refresh(plan)
        return plan

    return _make


@pytest_asyncio.fixture
async def make_pt_package(
    db_session: AsyncSession,
) -> Callable[..., Awaitable[PtPackage]]:
    """Insert a PtPackage instance row directly with full snapshot suite.

    Used by the plan_in_use 409 integration test — seeds a pt_packages row
    referencing the plan so the DELETE endpoint surfaces the pre-flight
    409 ``plan_in_use`` branch.
    """

    async def _make(
        *,
        client_id: UUID,
        plan: PtPackagePlan,
        status: str = "active",
        sessions_remaining: int | None = None,
        start_date: Any = None,
        end_date: Any = None,
    ) -> PtPackage:
        from datetime import UTC, datetime, timedelta

        today = start_date or datetime.now(tz=UTC).date()
        if end_date is None and plan.validity_days is not None:
            end = today + timedelta(days=plan.validity_days - 1)
        else:
            end = end_date
        sessions = sessions_remaining if sessions_remaining is not None else plan.session_count
        pt_package = PtPackage(
            client_id=client_id,
            plan_id=plan.id,
            plan_name_snapshot=plan.name,
            session_count_snapshot=plan.session_count,
            price_kopecks_snapshot=plan.price_kopecks,
            validity_days_snapshot=plan.validity_days,
            sessions_remaining=sessions,
            status=status,
            start_date=today,
            end_date=end,
        )
        db_session.add(pt_package)
        await db_session.commit()
        await db_session.refresh(pt_package)
        return pt_package

    return _make


# ---------------------------------------------------------------------------
# Plan 33-03 — D-13 sibling fixture for REF-TEST-02 race test only.
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def db_session_real_commit() -> AsyncIterator[AsyncSession]:
    """Real BEGIN/COMMIT per request — used ONLY by test_pt_package_refund_race.py.

    The default ``db_session`` fixture wraps every test in a SAVEPOINT for
    per-test isolation; concurrent INSERTs against the partial UNIQUE
    ``uq_payments_refund_of_alive`` do NOT compose with nested savepoints
    (rollback on IntegrityError masks second-+ failures and breaks the
    serialisation guarantees REF-TEST-02 asserts). Mirrors the membership
    sibling at ``tests/integration/memberships/conftest.py:307`` verbatim
    with the TRUNCATE list extended for the PT-package tables (D-33-01 /
    D-33-03).
    """
    settings = get_settings()
    engine = create_async_engine(str(settings.database_url), pool_pre_ping=True)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with session_factory() as session:
        yield session

    # Cleanup: real-commit writes are NOT rolled back. TRUNCATE every table
    # the REF-TEST-02 test seeds: users + clients + pt_package_plans +
    # pt_packages + payments + audit_log. CASCADE handles the FK chain.
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "TRUNCATE users, clients, pt_package_plans, pt_packages, "
                "payments, audit_log "
                "RESTART IDENTITY CASCADE"
            )
        )
    await engine.dispose()
