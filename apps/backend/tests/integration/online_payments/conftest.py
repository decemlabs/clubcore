"""Phase 49 Plan 49-07 — integration test fixtures for online_payments E2E suite.

Mirrors ``tests/integration/memberships/conftest.py``: cookie-jar + login
machinery on a per-role AsyncClient, sharing the SAVEPOINT-rolled
``db_session`` with the in-process FastAPI app.

Re-exports the Phase 49 module-scope DB factories (clients, plans, users)
and the Phase 48 + Plan 49-01 respx routes by importing them directly so
pytest collection picks them up.

Also re-installs the Plan 49-01 structlog autouse fixture so module-cached
loggers (e.g. ``app.integrations.yookassa.factory``) get re-bound to the
default config before each test — without it, ``capture_logs()`` in
Plan 49-03 / 49-04 service tests silently swallows events.
"""

from __future__ import annotations

import importlib
from collections.abc import AsyncIterator, Awaitable, Callable, Generator
from typing import Any
from uuid import UUID, uuid4

import httpx
import pytest
import pytest_asyncio
import respx
import structlog
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.permissions import Role
from app.core.redis import get_redis
from app.core.security import hash_password
from app.integrations.yookassa.settings import YooKassaSettings
from app.modules.auth.models import User
from app.modules.clients.models import Client
from app.modules.memberships.models import MembershipPlan
from app.modules.pt_packages.models import PtPackagePlan

# Re-export Phase 50 webhook fixtures needed by test_notify05_cancellation_regression.py
# (pytest conftest discovery is directory-tree-only — explicit re-export is required).
from tests.integration.webhook_yookassa.conftest import (  # noqa: F401
    seeded_online_payment_pending,
    webhook_client,
    webhook_db_session,
    webhook_engine,
    webhook_payment_canceled_body,
    yookassa_get_payment_canceled,
)

# Re-export respx fixtures from the Phase 48 / Plan 49-01 base conftest so
# they're available to tests in this directory (pytest conftest discovery
# is directory-tree-only; explicit re-import + ``# noqa: F401`` is the
# documented Sportzal-internal pattern, copied from
# ``tests/modules/online_payments/conftest.py``).
from tests.integrations.yookassa.conftest import (  # noqa: F401
    _YOOKASSA_BASE_URL,
    yookassa_create_payment_422,
    yookassa_create_payment_qr_422,
    yookassa_create_payment_qr_success,
    yookassa_create_payment_success,
)

OWNER_EMAIL = "phase49-e2e-owner@example.com"
OWNER_PASSWORD = "hunter22hunter22"  # noqa: S105 -- test password literal
RECEPTION_EMAIL = "phase49-e2e-reception@example.com"
RECEPTION_PASSWORD = "hunter22hunter22"  # noqa: S105 -- test password literal


# ---------------------------------------------------------------------------
# Plan 49-01 structlog reset (mirror of
# tests/integrations/yookassa/conftest.py:_reset_structlog_for_capture). The
# autouse fixture in that file does NOT cascade into this directory.
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _reset_structlog_for_capture_integration() -> Generator[None, None, None]:
    """Reset structlog defaults + re-bind the cached factory logger proxy."""
    structlog.reset_defaults()
    try:
        import app.integrations.yookassa.factory as _factory_mod

        importlib.reload(_factory_mod)
    except Exception:  # noqa: S110 -- best-effort isolation, do not fail tests
        pass
    yield


# ---------------------------------------------------------------------------
# Plan 49-07 — Phase-49-scoped respx 500 / 404 routes for transient_error /
# permanent_error coverage. Mirrors the Plan 49-03 fixtures from
# ``tests/modules/online_payments/conftest.py`` (they live there so the
# module-scope service tests can import them) — duplicated here so the
# integration E2E suite is self-contained and does not depend on parent-
# directory fixtures from a sibling test tree.
# ---------------------------------------------------------------------------


@pytest.fixture
def yookassa_create_payment_500() -> Generator[respx.MockRouter, None, None]:
    """Plan 49-07 D-49-27 — POST /v3/payments → 500 (transient_error)."""
    with respx.mock(base_url=_YOOKASSA_BASE_URL, assert_all_called=False) as router:
        router.post("payments").mock(
            return_value=httpx.Response(
                500, json={"type": "error", "code": "internal_server_error"}
            )
        )
        yield router


@pytest.fixture
def yookassa_create_payment_404() -> Generator[respx.MockRouter, None, None]:
    """Plan 49-07 D-49-27 — POST /v3/payments → 404 (permanent_error)."""
    with respx.mock(base_url=_YOOKASSA_BASE_URL, assert_all_called=False) as router:
        router.post("payments").mock(
            return_value=httpx.Response(
                404, json={"type": "error", "code": "not_found"}
            )
        )
        yield router


@pytest.fixture
def yookassa_settings() -> YooKassaSettings:
    """Test-instance reading from env (.env.example loaded in root conftest)."""
    return YooKassaSettings()


# ---------------------------------------------------------------------------
# Cookie-jar / login machinery — mirror of
# tests/integration/memberships/conftest.py:_client_app_overrides + the two
# authed_client_* fixtures, retargeted at Plan 49-07 E2E sell tests.
# ---------------------------------------------------------------------------


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
    """Owner user seeded via SAVEPOINT-rolled session."""
    return await _seed_user(
        db_session,
        role=Role.OWNER,
        email=OWNER_EMAIL,
        password=OWNER_PASSWORD,
        full_name="Phase 49 E2E Owner",
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
        full_name="Phase 49 E2E Reception",
    )


@pytest_asyncio.fixture
async def _client_app_overrides(
    app: FastAPI,
    db_session: AsyncSession,
) -> AsyncIterator[FastAPI]:
    """Install dependency overrides so route handlers see the SAVEPOINT-rolled
    session and the lifespan-bound Redis singleton (mirror of memberships
    conftest)."""

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
    """Authenticated AsyncClient for the seeded owner (cookies in jar)."""
    transport = ASGITransport(app=_client_app_overrides)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        await _login(client, email=OWNER_EMAIL, password=OWNER_PASSWORD)
        yield client


@pytest_asyncio.fixture
async def authed_client_reception(
    _client_app_overrides: FastAPI,
    seeded_reception: User,
) -> AsyncIterator[AsyncClient]:
    """Authenticated AsyncClient for the seeded reception user."""
    transport = ASGITransport(app=_client_app_overrides)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        await _login(client, email=RECEPTION_EMAIL, password=RECEPTION_PASSWORD)
        yield client


def sell_headers(client: AsyncClient) -> dict[str, str]:
    """CSRF + per-call Idempotency-Key headers required by every POST /sell*.

    Plan 49-04 router stack: ``require_permission → verify_csrf →
    verify_idempotency``. CSRF is read from the cookie jar populated by
    ``_login``; Idempotency-Key is fresh per call (D-49-16 outer layer).
    """
    return {
        "X-CSRF-Token": client.cookies.get("sportzal_csrf") or "",
        "Idempotency-Key": uuid4().hex,
    }


# ---------------------------------------------------------------------------
# DB-direct factories — committed inside the SAVEPOINT-mode session so the
# outer per-test transaction rolls back on teardown. Mirror of the Plan 49-03
# module-scope factories under ``tests/modules/online_payments/conftest.py``.
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def make_user(
    db_session: AsyncSession,
) -> Callable[..., Awaitable[User]]:
    """Insert a User row directly via the SAVEPOINT-mode session."""

    _counter = {"i": 0}

    async def _make(
        *,
        role: str = "reception",
        email: str | None = None,
        password: str = "hunter22hunter22",  # noqa: S107 -- test password literal
        full_name: str = "Phase 49 E2E Aux User",
    ) -> User:
        _counter["i"] += 1
        resolved_email = email or f"phase49-e2e-aux-{_counter['i']}@example.com"
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
async def make_actor(
    make_user: Callable[..., Awaitable[User]],
) -> Callable[..., Awaitable[User]]:
    """Return a reception user usable as CurrentUser / actor."""

    async def _make() -> User:
        return await make_user(role="reception")

    return _make


@pytest_asyncio.fixture
async def make_client_with_email(
    db_session: AsyncSession,
    make_user: Callable[..., Awaitable[User]],
) -> Callable[..., Awaitable[Client]]:
    """Insert a Client row with a non-NULL ``email`` for FIS-05 happy paths."""

    _counter = {"i": 0}

    async def _make(
        *,
        last_name: str = "Иванов",
        first_name: str = "Иван",
        email: str | None = None,
        phone: str | None = None,
        created_by_user_id: UUID | None = None,
    ) -> Client:
        _counter["i"] += 1
        if created_by_user_id is None:
            owner = await make_user(role="owner")
            created_by_user_id = owner.id
        resolved_phone = phone or f"+799912450{_counter['i']:02d}"
        resolved_email = email or f"phase49-e2e-client-{_counter['i']}@example.com"
        client = Client(
            last_name=last_name,
            first_name=first_name,
            phone=resolved_phone,
            email=resolved_email,
            created_by_user_id=created_by_user_id,
        )
        db_session.add(client)
        await db_session.commit()
        await db_session.refresh(client)
        return client

    return _make


@pytest_asyncio.fixture
async def make_client_no_email(
    db_session: AsyncSession,
    make_user: Callable[..., Awaitable[User]],
) -> Callable[..., Awaitable[Client]]:
    """Insert a Client row with ``email IS NULL`` for FIS-05 gate tests."""

    _counter = {"i": 0}

    async def _make(
        *,
        last_name: str = "Петров",
        first_name: str = "Пётр",
        phone: str | None = None,
        created_by_user_id: UUID | None = None,
    ) -> Client:
        _counter["i"] += 1
        if created_by_user_id is None:
            owner = await make_user(role="owner")
            created_by_user_id = owner.id
        resolved_phone = phone or f"+799912460{_counter['i']:02d}"
        client = Client(
            last_name=last_name,
            first_name=first_name,
            phone=resolved_phone,
            email=None,
            created_by_user_id=created_by_user_id,
        )
        db_session.add(client)
        await db_session.commit()
        await db_session.refresh(client)
        return client

    return _make


@pytest_asyncio.fixture
async def make_membership_plan(
    db_session: AsyncSession,
) -> Callable[..., Awaitable[MembershipPlan]]:
    """Insert a MembershipPlan row directly via the SAVEPOINT-mode session."""

    _counter = {"i": 0}

    async def _make(
        *,
        name: str | None = None,
        duration_days: int = 30,
        price_kopecks: int = 250000,
        freeze_days_limit: int = 14,
        active: bool = True,
    ) -> MembershipPlan:
        _counter["i"] += 1
        resolved_name = name or f"Phase49-E2E-Plan-{_counter['i']}"
        plan = MembershipPlan(
            name=resolved_name,
            duration_days=duration_days,
            price_kopecks=price_kopecks,
            freeze_days_limit=freeze_days_limit,
            active=active,
        )
        db_session.add(plan)
        await db_session.commit()
        await db_session.refresh(plan)
        return plan

    return _make


@pytest_asyncio.fixture
async def make_pt_package_plan(
    db_session: AsyncSession,
) -> Callable[..., Awaitable[PtPackagePlan]]:
    """Insert a PtPackagePlan row directly via the SAVEPOINT-mode session."""

    _counter = {"i": 0}

    async def _make(
        *,
        name: str | None = None,
        session_count: int = 10,
        price_kopecks: int = 500000,
        validity_days: int | None = 90,
    ) -> PtPackagePlan:
        _counter["i"] += 1
        resolved_name = name or f"Phase49-E2E-PT-{_counter['i']}"
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
