"""Shared fixtures for memberships integration tests (Phase 16 Plan 16-05).

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

from collections.abc import AsyncIterator, Awaitable, Callable
from datetime import date, timedelta
from typing import Any
from uuid import UUID

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
from app.modules.memberships.models import Membership, MembershipPlan

OWNER_EMAIL = "plans-owner@example.com"
OWNER_PASSWORD = "hunter22hunter22"  # noqa: S105 -- test password literal (>=12 chars)
RECEPTION_EMAIL = "plans-reception@example.com"
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
        full_name="Plans Owner",
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
        full_name="Plans Reception",
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


# ---------------------------------------------------------------------------
# Phase 17 Plan 17-05 — DB-direct factories for memberships integration tests.
#
# Both factories run on the SAVEPOINT-mode `db_session` fixture. Inner
# `await db_session.commit()` becomes a nested SAVEPOINT release — the outer
# fixture rollback at teardown wipes the writes regardless.
#
# `make_plan` is provided here for the rare test that needs a plan but does
# NOT want to go through the HTTP create-plan endpoint (e.g. seeding a row
# with `active=False` or a deterministic name without firing the
# `membership_plan_created` audit row that would otherwise pollute the
# audit_log query in the same test).
#
# `make_membership` inserts a Membership row directly with overridable
# `status` / `start_date` / `end_date` so resolver and state-machine tests
# can craft expired/cancelled rows without going through the cancel HTTP
# flow (which itself emits `membership_cancelled` and would skew audit
# assertions).
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def make_plan(
    db_session: AsyncSession,
) -> Callable[..., Awaitable[MembershipPlan]]:
    """Insert a MembershipPlan row directly via the SAVEPOINT-mode session.

    Outer fixture rolls back at teardown, so the inner commit becomes a
    nested-transaction release (Phase 16 pattern).
    """

    async def _make(
        *,
        name: str = "Базовый",
        duration_days: int = 30,
        price_kopecks: int = 250000,
        active: bool = True,
    ) -> MembershipPlan:
        plan = MembershipPlan(
            name=name,
            duration_days=duration_days,
            price_kopecks=price_kopecks,
            active=active,
        )
        db_session.add(plan)
        await db_session.commit()
        await db_session.refresh(plan)
        return plan

    return _make


@pytest_asyncio.fixture
async def make_membership(
    db_session: AsyncSession,
) -> Callable[..., Awaitable[Membership]]:
    """Insert a Membership row directly via the SAVEPOINT-mode session.

    Snapshot fields are copied from the provided `plan` ref so the inserted
    row is shape-identical to what `service.create_membership` would write.
    `status`, `start_date`, and `end_date` may be overridden so resolver and
    state-machine tests can craft expired/cancelled scenarios without
    routing through the cancel HTTP flow (which emits its own audit row).
    """

    async def _make(
        *,
        client_id: UUID,
        plan: MembershipPlan,
        status: str = "active",
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> Membership:
        today = start_date or date.today()
        end = end_date or (today + timedelta(days=plan.duration_days - 1))
        membership = Membership(
            client_id=client_id,
            plan_id=plan.id,
            plan_name_snapshot=plan.name,
            duration_days_snapshot=plan.duration_days,
            price_kopecks_snapshot=plan.price_kopecks,
            start_date=today,
            end_date=end,
            status=status,
        )
        db_session.add(membership)
        await db_session.commit()
        await db_session.refresh(membership)
        return membership

    return _make
