"""Shared fixtures for bookings integration tests (Phase 38 plans 38-02 / 38-03).

Mirrors `tests/integration/schedule/conftest.py` with the role-specific
email constants swapped (``book-*`` prefix) so bookings tests can run in
parallel with schedule + pt_sessions tests without colliding on the auth
fixtures' seeded emails.

Includes:
  - ``redis_clean`` / ``seeded_owner`` / ``seeded_reception`` /
    ``authed_client_owner`` / ``authed_client_reception`` / ``anon_client``
    standard auth fixtures.
  - ``make_trainer`` / ``make_client`` / ``make_pt_package_plan`` /
    ``make_pt_package`` / ``make_slot`` factories for the service-layer
    create-booking integration test (plan 38-02 Task 3).
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable, Callable
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

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
from app.modules.clients.models import Client
from app.modules.pt_packages.models import PtPackage, PtPackagePlan
from app.modules.schedule.models import TrainerAvailabilitySlot
from app.modules.trainers.models import Trainer

OWNER_EMAIL = "book-owner@example.com"
OWNER_PASSWORD = "hunter22hunter22"  # noqa: S105 -- test password literal (>=12 chars)
RECEPTION_EMAIL = "book-reception@example.com"
RECEPTION_PASSWORD = "hunter22hunter22"  # noqa: S105 -- test password literal


@pytest_asyncio.fixture
async def redis_clean(app: FastAPI) -> Redis:
    """Flush Redis between tests so rate-limit + idempotency keys don't bleed."""
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
        full_name="Bookings Owner",
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
        full_name="Bookings Reception",
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
            full_name=full_name or f"BookTrainer-{_counter['i']}-{uuid4().hex[:4]}",
            phone=phone,
            is_active=is_active,
        )
        db_session.add(trainer)
        await db_session.commit()
        await db_session.refresh(trainer)
        return trainer

    return _make


@pytest_asyncio.fixture
async def make_client(
    db_session: AsyncSession,
    seeded_owner: User,
) -> Callable[..., Awaitable[Client]]:
    """Insert a Client row directly via the SAVEPOINT-mode session."""
    _counter = {"i": 0}

    async def _make(
        *,
        last_name: str = "Петров",
        first_name: str = "Пётр",
        phone: str | None = None,
    ) -> Client:
        _counter["i"] += 1
        client_obj = Client(
            last_name=last_name,
            first_name=first_name,
            phone=phone or f"+79059{_counter['i']:06d}",
            created_by_user_id=seeded_owner.id,
        )
        db_session.add(client_obj)
        await db_session.commit()
        await db_session.refresh(client_obj)
        return client_obj

    return _make


@pytest_asyncio.fixture
async def make_pt_package_plan(
    db_session: AsyncSession,
) -> Callable[..., Awaitable[PtPackagePlan]]:
    _counter = {"i": 0}

    async def _make(
        *,
        name: str | None = None,
        session_count: int = 10,
        price_kopecks: int = 500000,
        validity_days: int | None = 90,
    ) -> PtPackagePlan:
        _counter["i"] += 1
        plan = PtPackagePlan(
            name=name or f"BookPlan-{_counter['i']}-{uuid4().hex[:4]}",
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
    """Insert a PtPackage instance directly (bypasses HTTP sale flow + audit)."""

    async def _make(
        *,
        client_id: UUID,
        plan: PtPackagePlan,
        status: str = "active",
        sessions_remaining: int | None = None,
        start_date: Any = None,
        end_date: Any = None,
    ) -> PtPackage:
        today = start_date or datetime.now(tz=UTC).date()
        if end_date is None and plan.validity_days is not None:
            end = today + timedelta(days=plan.validity_days - 1)
        else:
            end = end_date
        sessions = (
            sessions_remaining
            if sessions_remaining is not None
            else plan.session_count
        )
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


@pytest_asyncio.fixture
async def make_slot(
    db_session: AsyncSession,
    seeded_owner: User,
) -> Callable[..., Awaitable[TrainerAvailabilitySlot]]:
    """Insert a TrainerAvailabilitySlot directly (bypasses HTTP publish flow)."""
    _counter = {"i": 0}

    async def _make(
        *,
        trainer_id: UUID,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        status: str = "active",
        created_by_user_id: UUID | None = None,
    ) -> TrainerAvailabilitySlot:
        _counter["i"] += 1
        start = start_time or (datetime.now(tz=UTC) + timedelta(hours=2 + _counter["i"]))
        end = end_time or (start + timedelta(hours=1))
        slot = TrainerAvailabilitySlot(
            trainer_id=trainer_id,
            start_time=start,
            end_time=end,
            status=status,
            created_by_user_id=created_by_user_id or seeded_owner.id,
        )
        db_session.add(slot)
        await db_session.commit()
        await db_session.refresh(slot)
        return slot

    return _make
