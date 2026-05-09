"""Visits test fixtures (Phase 19).

Two key additions over the memberships conftest:

1. `make_visit_setup` — convenience factory producing (client, membership)
   in a single call so per-test seeding is one line.

2. `db_session_real_commit` (D-13) — sibling fixture that uses real
   BEGIN/COMMIT per request and TRUNCATEs `visits` + `audit_log` at fixture
   exit. Used ONLY by `test_visits_concurrent.py` (VIS-TEST-01). Rationale:
   the default `db_session` fixture wraps each test in a SAVEPOINT for
   per-test isolation; concurrent INSERT serialisation against the UNIQUE
   index doesn't compose cleanly with nested savepoints (savepoint rollback
   on IntegrityError can mask second-+ failures or affect ordering).
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable, Callable
from datetime import date, timedelta
from typing import Any
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest
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
from app.modules.memberships.models import Membership, MembershipPlan

_MSK = ZoneInfo("Europe/Moscow")


def _today_msk() -> date:
    from datetime import datetime

    return datetime.now(_MSK).date()

OWNER_EMAIL = "visits-owner@example.com"
OWNER_PASSWORD = "hunter22hunter22"  # noqa: S105 -- test password literal (>=12 chars)
RECEPTION_EMAIL = "visits-reception@example.com"
RECEPTION_PASSWORD = "hunter22hunter22"  # noqa: S105 -- test password literal


def _csrf_headers(client: AsyncClient) -> dict[str, str]:
    return {"X-CSRF-Token": client.cookies.get("sportzal_csrf") or ""}


@pytest.fixture
def csrf_headers() -> Callable[[AsyncClient], dict[str, str]]:
    return _csrf_headers


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
        email=OWNER_EMAIL,
        password=OWNER_PASSWORD,
        full_name="Visits Owner",
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
        full_name="Visits Reception",
    )


@pytest_asyncio.fixture
async def _client_app_overrides(
    app: FastAPI,
    db_session: AsyncSession,
) -> AsyncIterator[FastAPI]:
    """Install dependency overrides so route handlers see the SAVEPOINT-rolled session."""

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
    """Authenticated httpx client for the seeded owner."""
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


@pytest_asyncio.fixture
async def make_visit_setup(
    db_session: AsyncSession,
) -> Callable[..., Awaitable[tuple[Client, Membership]]]:
    """Seed (client, plan, active-membership) tuple in one call.

    Internally seeds a system owner user for the required `created_by_user_id`
    FK (clients.created_by_user_id NOT NULL). The seeded user is unique per
    factory call (email based on uuid4) to avoid duplicate email conflicts.

    Usage:
        client, membership = await make_visit_setup()
        client, membership = await make_visit_setup(end_date=date.today())
        client, membership = await make_visit_setup(telegram_user_id=42)
    """

    async def _factory(
        *,
        end_date: date | None = None,
        telegram_user_id: int | None = None,
    ) -> tuple[Client, Membership]:
        # Seed a system owner user for created_by_user_id FK
        creator = User(
            email=f"setup-owner-{uuid4().hex[:8]}@example.com",
            password_hash="$argon2id$notreal",  # noqa: S106
            role=Role.OWNER,
            full_name="Setup Owner",
        )
        db_session.add(creator)
        await db_session.flush()

        plan = MembershipPlan(
            name=f"Plan-{uuid4().hex[:8]}",
            duration_days=30,
            price_kopecks=250000,
            freeze_days_limit=14,
            active=True,
        )
        db_session.add(plan)
        await db_session.flush()

        phone_suffix = uuid4().int % 10**7
        c = Client(
            last_name=f"Client-{uuid4().hex[:8]}",
            first_name="Test",
            phone=f"+7901{phone_suffix:07d}",
            telegram_user_id=telegram_user_id,
            created_by_user_id=creator.id,
        )
        db_session.add(c)
        await db_session.flush()

        m = Membership(
            client_id=c.id,
            plan_id=plan.id,
            duration_days_snapshot=plan.duration_days,
            price_kopecks_snapshot=plan.price_kopecks,
        freeze_days_limit_snapshot=plan.freeze_days_limit,
            plan_name_snapshot=plan.name,
            start_date=_today_msk() - timedelta(days=1),
            end_date=end_date or (_today_msk() + timedelta(days=29)),
            status="active",
            activation_policy="purchase_date",
        )
        db_session.add(m)
        await db_session.flush()
        return c, m

    return _factory


# ─── D-13 sibling fixture for VIS-TEST-01 only ────────────────────────────
@pytest_asyncio.fixture
async def db_session_real_commit() -> AsyncIterator[AsyncSession]:
    """Real BEGIN/COMMIT per request — used ONLY by test_visits_concurrent.py.

    The default `db_session` fixture (apps/backend/tests/conftest.py) wraps
    every test in a SAVEPOINT for per-test isolation. Concurrent INSERTs
    racing against the UNIQUE index do NOT compose with nested savepoints —
    savepoint rollback on IntegrityError can mask second-+ failures and
    interferes with the serialisation guarantees we need to prove
    VIS-TEST-01.

    This fixture issues TRUNCATE visits, audit_log RESTART IDENTITY CASCADE
    after the test so the next test starts clean.

    D-13: SAVEPOINT interferes with concurrent INSERT serialisation against
    the UNIQUE index. Real BEGIN/COMMIT per request + TRUNCATE `visits,
    audit_log` at fixture exit is required for VIS-TEST-01.
    """
    settings = get_settings()
    engine = create_async_engine(str(settings.database_url), pool_pre_ping=True)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with session_factory() as session:
        yield session

    # Cleanup: wipe everything VIS-TEST-01 inserts so the next test starts clean.
    # Real-commit writes are NOT rolled back (unlike SAVEPOINT-isolated tests),
    # so we must TRUNCATE every table the test seeds: users + plans + clients +
    # memberships + visits + audit_log. CASCADE handles the FK chain order.
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "TRUNCATE users, membership_plans, clients, memberships, "
                "visits, audit_log RESTART IDENTITY CASCADE"
            )
        )
    await engine.dispose()
