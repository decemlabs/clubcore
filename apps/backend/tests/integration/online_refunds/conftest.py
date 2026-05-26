"""Phase 51 Plan 51-08 — integration test fixtures for the online_refunds suite.

Mirrors ``tests/integration/online_payments/conftest.py`` cookie-jar +
respx-fixture re-export pattern. Adds three seed-graph factories:

  - ``seeded_membership_with_succeeded_online_payment``: Client + active
    Membership + succeeded OnlinePayment + positive Payment ledger row
    (subject_kind='membership', subject_id=plan_id, method='online').
  - ``seeded_pt_package_with_succeeded_online_payment``: same shape for
    PT-packages (subject_kind='pt_package').
  - ``yookassa_create_refund_422`` / ``_500`` / ``_404``: respx routes
    driving the classification → AppError mapping branches of the
    initiate_online_refund service (mirror of the Phase 49
    yookassa_create_payment_* family).

The ЮKassa adapter is wired via ``register_yookassa_client_provider`` in
``app.main.create_app``; the respx mocks intercept the HTTP boundary.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable, Callable, Generator
from datetime import UTC, date, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

import httpx
import pytest
import pytest_asyncio
import respx
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
from app.modules.memberships.models import Membership, MembershipPlan
from app.modules.online_payments.models import OnlinePayment
from app.modules.payments.constants import (
    SUBJECT_KIND_MEMBERSHIP,
    SUBJECT_KIND_PT_PACKAGE,
)
from app.modules.payments.models import Payment
from app.modules.pt_packages.models import PtPackage, PtPackagePlan

# Re-export the canonical respx refund-success fixture so this directory's
# tests can pick it up via pytest collection (conftest discovery is directory-
# tree-only — explicit re-import is the documented Sportzal-internal pattern;
# see tests/integration/online_payments/conftest.py:49).
from tests.integrations.yookassa.conftest import (  # noqa: F401
    _YOOKASSA_BASE_URL,
    _reset_structlog_for_capture,
    yookassa_create_refund_success,
)

OWNER_EMAIL = "phase51-refund-owner@example.com"
OWNER_PASSWORD = "hunter22hunter22"  # noqa: S105 -- test password literal
RECEPTION_EMAIL = "phase51-refund-reception@example.com"
RECEPTION_PASSWORD = "hunter22hunter22"  # noqa: S105 -- test password literal


# ---------------------------------------------------------------------------
# Phase 51 — respx classification fixtures (mirror Phase 49 conftest).
# ---------------------------------------------------------------------------


@pytest.fixture
def yookassa_create_refund_422() -> Generator[respx.MockRouter, None, None]:
    """POST /v3/refunds → 422 validation error (ЮKassa shape)."""
    with respx.mock(base_url=_YOOKASSA_BASE_URL, assert_all_called=False) as router:
        router.post("refunds").mock(
            return_value=httpx.Response(
                422,
                json={
                    "type": "error",
                    "code": "invalid_request",
                    "description": "invalid",
                },
            )
        )
        yield router


@pytest.fixture
def yookassa_create_refund_500() -> Generator[respx.MockRouter, None, None]:
    """POST /v3/refunds → 500 → transient_error per _classify_http_status_error."""
    with respx.mock(base_url=_YOOKASSA_BASE_URL, assert_all_called=False) as router:
        router.post("refunds").mock(
            return_value=httpx.Response(
                500, json={"type": "error", "code": "internal_server_error"}
            )
        )
        yield router


@pytest.fixture
def yookassa_create_refund_404() -> Generator[respx.MockRouter, None, None]:
    """POST /v3/refunds → 404 → permanent_error per _classify_http_status_error."""
    with respx.mock(base_url=_YOOKASSA_BASE_URL, assert_all_called=False) as router:
        router.post("refunds").mock(
            return_value=httpx.Response(404, json={"type": "error", "code": "not_found"})
        )
        yield router


# ---------------------------------------------------------------------------
# Cookie-jar / login machinery — mirror of online_payments conftest.
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
        full_name="Phase 51 Refund Owner",
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
        full_name="Phase 51 Refund Reception",
    )


@pytest_asyncio.fixture
async def _client_app_overrides(
    app: FastAPI,
    db_session: AsyncSession,
) -> AsyncIterator[FastAPI]:
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
# DB-direct factories.
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def make_user(
    db_session: AsyncSession,
) -> Callable[..., Awaitable[User]]:
    _counter = {"i": 0}

    async def _make(
        *,
        role: str = "reception",
        email: str | None = None,
        password: str = "hunter22hunter22",  # noqa: S107 -- test password literal
        full_name: str = "Phase 51 Refund Aux User",
    ) -> User:
        _counter["i"] += 1
        resolved_email = email or f"phase51-refund-aux-{_counter['i']}@example.com"
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
    async def _make() -> User:
        return await make_user(role="reception")

    return _make


@pytest_asyncio.fixture
async def make_client_with_email(
    db_session: AsyncSession,
    make_user: Callable[..., Awaitable[User]],
) -> Callable[..., Awaitable[Client]]:
    _counter = {"i": 0}

    async def _make(
        *,
        email: str | None = None,
        phone: str | None = None,
    ) -> Client:
        _counter["i"] += 1
        owner = await make_user(role="owner")
        resolved_phone = phone or f"+799951130{_counter['i']:02d}"
        resolved_email = email or f"phase51-refund-client-{_counter['i']}@example.com"
        client = Client(
            last_name="Иванов",
            first_name="Иван",
            phone=resolved_phone,
            email=resolved_email,
            created_by_user_id=owner.id,
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
    _counter = {"i": 0}

    async def _make(
        *,
        name: str | None = None,
        duration_days: int = 30,
        price_kopecks: int = 199_00,  # 199.00 RUB (matches create_refund_success fixture)
        freeze_days_limit: int = 14,
    ) -> MembershipPlan:
        _counter["i"] += 1
        resolved_name = name or f"Phase51-Refund-Plan-{_counter['i']}"
        plan = MembershipPlan(
            name=resolved_name,
            duration_days=duration_days,
            price_kopecks=price_kopecks,
            freeze_days_limit=freeze_days_limit,
            active=True,
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
    _counter = {"i": 0}

    async def _make(
        *,
        name: str | None = None,
        session_count: int = 10,
        price_kopecks: int = 199_00,
        validity_days: int | None = 90,
    ) -> PtPackagePlan:
        _counter["i"] += 1
        resolved_name = name or f"Phase51-Refund-PT-{_counter['i']}"
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


# ---------------------------------------------------------------------------
# Seed-graph factories — combined Client + subject + OnlinePayment + Payment.
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def seeded_membership_with_succeeded_online_payment(
    db_session: AsyncSession,
    make_client_with_email: Callable[..., Awaitable[Client]],
    make_membership_plan: Callable[..., Awaitable[MembershipPlan]],
) -> Callable[..., Awaitable[tuple[Client, OnlinePayment, Payment, Membership]]]:
    """Seed the full graph (client + membership + OP + ledger row).

    Mirrors the post-Phase-50 webhook end-state: OnlinePayment row in
    status='succeeded' with a positive Payment ledger row carrying
    subject_kind='membership' AND subject_id=plan_id AND method='online'.
    """
    _counter = {"i": 0}

    async def _make(
        *,
        membership_status: str = "active",
    ) -> tuple[Client, OnlinePayment, Payment, Membership]:
        _counter["i"] += 1
        client = await make_client_with_email()
        plan = await make_membership_plan(name=f"refund-fixture-{_counter['i']}")

        today = datetime.now(tz=UTC).date()
        end = today + timedelta(days=plan.duration_days - 1)
        membership = Membership(
            client_id=client.id,
            plan_id=plan.id,
            plan_name_snapshot=plan.name,
            duration_days_snapshot=plan.duration_days,
            price_kopecks_snapshot=plan.price_kopecks,
            freeze_days_limit_snapshot=plan.freeze_days_limit,
            start_date=today,
            end_date=end,
            status=membership_status,
        )
        db_session.add(membership)

        op = OnlinePayment(
            client_id=client.id,
            membership_plan_id=plan.id,
            pt_package_plan_id=None,
            yookassa_payment_id=f"yk-pmt-{uuid4().hex[:12]}",
            idempotency_key=f"idem-{uuid4().hex[:12]}",
            amount_kopecks=plan.price_kopecks,
            status="succeeded",
            confirmation_url=None,
            confirmation_type="redirect",
            succeeded_at=datetime.now(tz=UTC),
            audit_correlation_id=uuid4(),
        )
        db_session.add(op)
        await db_session.flush()  # populate op.id for the Payment FK / log linkage

        payment = Payment(
            subject_kind=SUBJECT_KIND_MEMBERSHIP,
            subject_id=plan.id,  # Phase 50 webhook records subject_id=membership_plan_id
            amount_kopecks=plan.price_kopecks,
            method="online",
            received_by_user_id=None,  # anonymous webhook flow
        )
        db_session.add(payment)
        await db_session.commit()
        await db_session.refresh(client)
        await db_session.refresh(op)
        await db_session.refresh(payment)
        await db_session.refresh(membership)
        return client, op, payment, membership

    return _make


@pytest_asyncio.fixture
async def seeded_pt_package_with_succeeded_online_payment(
    db_session: AsyncSession,
    make_client_with_email: Callable[..., Awaitable[Client]],
    make_pt_package_plan: Callable[..., Awaitable[PtPackagePlan]],
    make_user: Callable[..., Awaitable[User]],
) -> Callable[..., Awaitable[tuple[Client, OnlinePayment, Payment, PtPackage]]]:
    """PT-package mirror of ``seeded_membership_with_succeeded_online_payment``."""
    _counter = {"i": 0}

    async def _make() -> tuple[Client, OnlinePayment, Payment, PtPackage]:
        _counter["i"] += 1
        client = await make_client_with_email()
        plan = await make_pt_package_plan(name=f"refund-pt-fixture-{_counter['i']}")
        today = datetime.now(tz=UTC).date()
        validity = plan.validity_days or 90
        end = today + timedelta(days=validity - 1)

        pt_package = PtPackage(
            client_id=client.id,
            plan_id=plan.id,
            trainer_id=None,
            plan_name_snapshot=plan.name,
            session_count_snapshot=plan.session_count,
            sessions_remaining=plan.session_count,
            price_kopecks_snapshot=plan.price_kopecks,
            validity_days_snapshot=validity,
            start_date=today,
            end_date=end,
            status="active",
        )
        db_session.add(pt_package)

        op = OnlinePayment(
            client_id=client.id,
            membership_plan_id=None,
            pt_package_plan_id=plan.id,
            yookassa_payment_id=f"yk-pmt-pt-{uuid4().hex[:12]}",
            idempotency_key=f"idem-pt-{uuid4().hex[:12]}",
            amount_kopecks=plan.price_kopecks,
            status="succeeded",
            confirmation_url=None,
            confirmation_type="redirect",
            succeeded_at=datetime.now(tz=UTC),
            audit_correlation_id=uuid4(),
        )
        db_session.add(op)
        await db_session.flush()

        payment = Payment(
            subject_kind=SUBJECT_KIND_PT_PACKAGE,
            subject_id=plan.id,
            amount_kopecks=plan.price_kopecks,
            method="online",
            received_by_user_id=None,
        )
        db_session.add(payment)
        await db_session.commit()
        await db_session.refresh(client)
        await db_session.refresh(op)
        await db_session.refresh(payment)
        await db_session.refresh(pt_package)
        return client, op, payment, pt_package

    return _make
