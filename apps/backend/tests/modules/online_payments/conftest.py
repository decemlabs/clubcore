"""Phase 49 PAY-03/04/05/06 service-layer test fixtures (D-49-27/28).

Provides:
- Phase-49-scoped respx 500/404 fixtures (PATTERNS.md lines 952-972).
- Local DB-direct factories for User/Client/MembershipPlan/PtPackagePlan
  bound to the SAVEPOINT-rolled ``db_session`` fixture (Phase 49 service tests
  are the first under ``tests/modules/`` so we don't piggyback on the
  ``tests/integration/memberships/`` cookie-jar / login machinery).
- ``yookassa_settings`` test-instance pulled from environment.

All factories commit via the SAVEPOINT-mode session — nested savepoints
release inside the outer per-test transaction which the root conftest
rolls back at teardown.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Generator
from uuid import UUID

import httpx
import pytest
import pytest_asyncio
import respx
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permissions import Role
from app.core.security import hash_password
from app.integrations.yookassa.settings import YooKassaSettings
from app.modules.auth.models import User
from app.modules.clients.models import Client
from app.modules.memberships.models import MembershipPlan
from app.modules.pt_packages.models import PtPackagePlan

# Reuse Phase 48 / 49-01 respx routes + base URL constant. These fixture
# imports are NOT picked up automatically by pytest (conftest discovery
# follows the directory tree only); re-exporting them here makes them
# available to tests under tests/modules/online_payments/.
from tests.integrations.yookassa.conftest import (  # noqa: F401
    _YOOKASSA_BASE_URL,
    yookassa_create_payment_422,
    yookassa_create_payment_qr_422,
    yookassa_create_payment_qr_success,
    yookassa_create_payment_success,
    yookassa_create_refund_success,
    yookassa_get_payment_pending,
    yookassa_get_payment_qr_pending,
    yookassa_get_payment_succeeded,
    yookassa_webhook_payload,
)

# ---------------------------------------------------------------------------
# Phase 49 D-49-27 / PATTERNS.md — respx 500 / 404 routes for
# transient_error / permanent_error coverage. yookassa_create_payment_success,
# _422, _qr_success, and yookassa_get_payment_qr_pending come from
# tests/integrations/yookassa/conftest.py (Plan 49-01 ships them).
# ---------------------------------------------------------------------------


@pytest.fixture
def yookassa_create_payment_500() -> Generator[respx.MockRouter, None, None]:
    """Phase 49 D-49-27 — POST /v3/payments → 500 (transient_error)."""
    with respx.mock(base_url=_YOOKASSA_BASE_URL, assert_all_called=False) as router:
        router.post("payments").mock(
            return_value=httpx.Response(
                500, json={"type": "error", "code": "internal_server_error"}
            )
        )
        yield router


@pytest.fixture
def yookassa_create_payment_404() -> Generator[respx.MockRouter, None, None]:
    """Phase 49 D-49-27 — POST /v3/payments → 404 (permanent_error)."""
    with respx.mock(base_url=_YOOKASSA_BASE_URL, assert_all_called=False) as router:
        router.post("payments").mock(
            return_value=httpx.Response(404, json={"type": "error", "code": "not_found"})
        )
        yield router


@pytest.fixture
def yookassa_settings() -> YooKassaSettings:
    """Test-instance reading from env (loaded from .env.example at conftest top)."""
    return YooKassaSettings()


# ---------------------------------------------------------------------------
# DB-direct factories — committed inside the SAVEPOINT-mode session so the
# outer per-test transaction rolls back on teardown.
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
        full_name: str = "Phase 49 Service Test User",
    ) -> User:
        _counter["i"] += 1
        resolved_email = email or f"phase49-svc-{_counter['i']}@example.com"
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
    """Return an awaitable that produces a reception user usable as CurrentUser."""

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
        resolved_phone = phone or f"+799912350{_counter['i']:02d}"
        resolved_email = email or f"phase49-client-{_counter['i']}@example.com"
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
        resolved_phone = phone or f"+799912360{_counter['i']:02d}"
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
        resolved_name = name or f"Phase49-Plan-{_counter['i']}"
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
        resolved_name = name or f"Phase49-PT-{_counter['i']}"
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


# Note: tests that need the YooKassaClient slot registered must depend on
# the root `app` fixture (which fires create_app() lifespan and calls
# register_yookassa_client_provider). Adding `app` to the parameter list
# is sufficient; do NOT call any method on it.
