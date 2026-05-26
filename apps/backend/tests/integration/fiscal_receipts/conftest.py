"""Phase 51 Plan 51-05 — integration test fixtures for dispatch_fiscal_receipt.

Mirrors the Phase 50 ``tests/integration/webhook_yookassa/conftest.py``
real-commit engine pattern (D-13) because the dispatch task opens its own
sessions via the ``session_factory`` in ``ctx`` and commits inside each;
that cannot compose with the root ``db_session`` SAVEPOINT pattern.

Re-exports the Phase 51-03 respx fixtures from
``tests/integrations/yookassa/conftest.py``:
  - ``yookassa_create_receipt_ok``     — POST /receipts → 200 (ok)
  - ``yookassa_create_receipt_429``    — POST /receipts → 429 (permanent_error)
  - ``yookassa_create_receipt_500``    — POST /receipts → 500 (transient_error)

Fixtures defined here:
  - ``fiscal_engine`` — real-commit AsyncEngine with TRUNCATE cleanup.
  - ``fiscal_session_factory`` — async_sessionmaker bound to fiscal_engine,
    yielded to the dispatch task as ``ctx["sessionmaker"]``.
  - ``arq_ctx`` — minimal ARQ ctx dict shape: sessionmaker / yookassa_client /
    redis / job_try (defaulting to 1).
  - ``seeded_dispatch_scenario`` — seeds a complete chain ready for the
    dispatch task to consume: Client + MembershipPlan + OnlinePayment +
    Payment + AuditLog(online_payment_succeeded) + FiscalReceipt(status='sent').
  - ``redis_circuit_cleaner`` — flushes the sliding-window + open-marker
    keys for the ``receipts`` provider between tests.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass
from typing import Any
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from fastapi import FastAPI
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.audit_models import AuditLog
from app.core.config import get_settings
from app.integrations.yookassa.client import YooKassaClient
from app.integrations.yookassa.factory import build_yookassa_client
from app.integrations.yookassa.settings import YooKassaSettings
from app.modules.clients.models import Client
from app.modules.fiscal_receipts.constants import KIND_PAYMENT, STATUS_SENT
from app.modules.fiscal_receipts.models import FiscalReceipt
from app.modules.memberships.models import MembershipPlan
from app.modules.online_payments.constants import (
    CONFIRMATION_TYPE_REDIRECT,
    STATUS_SUCCEEDED,
)
from app.modules.online_payments.models import OnlinePayment
from app.modules.payments.models import Payment

# Re-export Phase 51-03 respx fixtures.
from tests.integrations.yookassa.conftest import (  # noqa: F401
    yookassa_create_receipt_429,
    yookassa_create_receipt_500,
    yookassa_create_receipt_ok,
)

_TRUNCATE_TABLES = (
    "audit_log",
    "fiscal_receipts",
    "payments",
    "memberships",
    "pt_packages",
    "online_payments",
    "membership_plans",
    "pt_package_plans",
    "clients",
    "users",
)


@dataclass
class SeededDispatchScenario:
    """Carrier for the rows the dispatch task needs to consume."""

    fiscal_receipt_id: UUID
    payment_id: UUID
    online_payment_id: UUID
    yookassa_payment_id: str
    customer_email: str
    audit_correlation_id: UUID
    amount_kopecks: int


@pytest_asyncio.fixture
async def fiscal_engine() -> AsyncIterator[Any]:
    """Real-commit engine; TRUNCATEs all touched tables on teardown."""
    settings = get_settings()
    engine = create_async_engine(str(settings.database_url), pool_pre_ping=True)
    try:
        yield engine
    finally:
        async with engine.begin() as conn:
            await conn.execute(
                text(f"TRUNCATE {', '.join(_TRUNCATE_TABLES)} RESTART IDENTITY CASCADE")
            )
        await engine.dispose()


@pytest_asyncio.fixture
async def fiscal_session_factory(
    fiscal_engine: Any,
) -> async_sessionmaker[AsyncSession]:
    """Session factory the dispatch task receives as ``ctx['sessionmaker']``."""
    return async_sessionmaker(fiscal_engine, expire_on_commit=False)


@pytest_asyncio.fixture
async def fiscal_db_session(
    fiscal_engine: Any,
) -> AsyncIterator[AsyncSession]:
    """Real-commit session for test setup (seeding)."""
    session_factory = async_sessionmaker(fiscal_engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session


@pytest_asyncio.fixture
async def fiscal_yookassa_client() -> AsyncIterator[YooKassaClient]:
    """Real YooKassaClient backed by httpx; respx intercepts the actual call."""
    settings = YooKassaSettings()
    client = await build_yookassa_client(settings=settings)
    try:
        yield client
    finally:
        await client.aclose()


@pytest_asyncio.fixture
async def fiscal_redis(app: FastAPI) -> AsyncIterator[Redis]:
    """Lifespan-bound Redis singleton; flushes the receipts circuit keys."""
    client: Redis = app.state.redis
    for prefix in ("cc:yookassa:circuit:receipts", "cc:yookassa:circuit_window:receipts"):
        await client.delete(prefix)
    yield client
    for prefix in ("cc:yookassa:circuit:receipts", "cc:yookassa:circuit_window:receipts"):
        await client.delete(prefix)


@pytest.fixture
def arq_ctx(
    fiscal_session_factory: async_sessionmaker[AsyncSession],
    fiscal_yookassa_client: YooKassaClient,
    fiscal_redis: Redis,
) -> dict[str, Any]:
    """ARQ-shape ctx dict the dispatch task body reads from.

    ``job_try`` defaults to 1; tests that exercise the retry-exhaustion
    branch mutate ``ctx["job_try"]`` before invoking the task.

    Phase 52 (52-05): the dispatch task's failure path enqueues a best-effort
    ``dispatch_payment_notification`` owner alert via ``ctx['redis']``. In the
    real ARQ worker ``ctx['redis']`` is an ``ArqRedis`` (has ``enqueue_job``);
    the test's lifespan redis is a plain ``Redis``. Wrap it so circuit-breaker
    ops still hit the real redis while ``enqueue_job`` is a no-op AsyncMock.
    """

    class _ArqRedisProxy:
        def __init__(self, redis: Redis) -> None:
            self._redis = redis
            self.enqueue_job = AsyncMock()

        def __getattr__(self, name: str) -> Any:
            return getattr(self._redis, name)

    return {
        "sessionmaker": fiscal_session_factory,
        "yookassa_client": fiscal_yookassa_client,
        "redis": _ArqRedisProxy(fiscal_redis),
        "job_try": 1,
    }


async def _seed_owner_client_plan(
    session: AsyncSession,
) -> tuple[UUID, Client, MembershipPlan]:
    """Seed an Owner + Client + MembershipPlan; returns owner_id + ORM rows."""
    from app.core.models import User
    from app.core.permissions import Role
    from app.core.security import hash_password

    nonce = uuid4().hex[:8]
    owner = User(
        email=f"phase51-fiscal-owner-{nonce}@example.com",
        password_hash=await hash_password("hunter22hunter22"),
        role=Role.OWNER,
        full_name="Phase 51 Fiscal Test Owner",
    )
    session.add(owner)
    await session.flush()

    client = Client(
        last_name="Иванов",
        first_name="Иван",
        phone=f"+7999{nonce}",
        email=f"phase51-fiscal-client-{nonce}@example.com",
        created_by_user_id=owner.id,
    )
    session.add(client)
    await session.flush()

    plan = MembershipPlan(
        name=f"Phase51-Fiscal-Plan-{uuid4().hex[:6]}",
        duration_days=30,
        price_kopecks=100_000,
        freeze_days_limit=7,
        active=True,
    )
    session.add(plan)
    await session.flush()
    return owner.id, client, plan


@pytest_asyncio.fixture
async def seeded_dispatch_scenario(
    fiscal_db_session: AsyncSession,
) -> SeededDispatchScenario:
    """Seed the full chain through to ``FiscalReceipt(status='sent')``.

    Chain: Client → OnlinePayment → Payment → AuditLog(online_payment_succeeded)
    → FiscalReceipt(status='sent').

    Mirrors the Phase 50 webhook UoW post-state: the inbound webhook has
    been processed, the OnlinePayment is succeeded, the Payment ledger row
    is written, the online_payment_succeeded audit row carries the
    audit_correlation_id + yookassa_payment_id, and the fiscal_receipt
    row sits at status='sent' ready for the dispatch task.
    """
    session = fiscal_db_session

    _owner_id, client, plan = await _seed_owner_client_plan(session)

    yk_payment_id = f"yk-{uuid4().hex[:24]}"
    corr = uuid4()
    op = OnlinePayment(
        client_id=client.id,
        membership_plan_id=plan.id,
        pt_package_plan_id=None,
        yookassa_payment_id=yk_payment_id,
        idempotency_key=uuid4().hex,
        amount_kopecks=100_000,
        status=STATUS_SUCCEEDED,
        confirmation_url="https://example.com/confirm",
        confirmation_type=CONFIRMATION_TYPE_REDIRECT,
        audit_correlation_id=corr,
    )
    session.add(op)
    await session.flush()

    payment = Payment(
        subject_kind="membership",
        subject_id=plan.id,
        amount_kopecks=100_000,
        method="online",
        received_by_user_id=None,
    )
    session.add(payment)
    await session.flush()

    # The dispatch task resolves the yookassa_payment_id by looking up an
    # AuditLog row with action='online_payment_succeeded' and a JSONB
    # payload audit_correlation_id matching the fiscal_receipt's value.
    audit_row = AuditLog(
        actor_user_id=None,
        actor_email_snapshot=None,
        action="online_payment_succeeded",
        resource_type="online_payment",
        resource_id=op.id,
        payload={
            "audit_correlation_id": str(corr),
            "online_payment_id": str(op.id),
            "yookassa_payment_id": yk_payment_id,
            "amount_kopecks": 100_000,
            "payment_id": str(payment.id),
        },
    )
    session.add(audit_row)
    await session.flush()

    fr = FiscalReceipt(
        payment_id=payment.id,
        kind=KIND_PAYMENT,
        status=STATUS_SENT,
        customer_email=client.email or "",
        yookassa_receipt_id=None,
        audit_correlation_id=corr,
        sent_at=None,
    )
    session.add(fr)
    await session.flush()
    await session.commit()

    return SeededDispatchScenario(
        fiscal_receipt_id=fr.id,
        payment_id=payment.id,
        online_payment_id=op.id,
        yookassa_payment_id=yk_payment_id,
        customer_email=client.email or "",
        audit_correlation_id=corr,
        amount_kopecks=100_000,
    )


@pytest_asyncio.fixture
async def seeded_dispatch_scenario_succeeded(
    fiscal_db_session: AsyncSession,
) -> SeededDispatchScenario:
    """Variant of ``seeded_dispatch_scenario`` with FiscalReceipt.status='succeeded'.

    Used by the skip-nonactive test to verify the dispatch task returns
    'skipped' without touching ЮKassa or the audit log.
    """
    from app.modules.fiscal_receipts.constants import STATUS_SUCCEEDED as FR_SUCCEEDED

    session = fiscal_db_session

    _owner_id, client, plan = await _seed_owner_client_plan(session)

    payment = Payment(
        subject_kind="membership",
        subject_id=plan.id,
        amount_kopecks=100_000,
        method="online",
        received_by_user_id=None,
    )
    session.add(payment)
    await session.flush()

    fr = FiscalReceipt(
        payment_id=payment.id,
        kind=KIND_PAYMENT,
        status=FR_SUCCEEDED,
        customer_email=client.email or "",
        yookassa_receipt_id="prev_rcpt",
        audit_correlation_id=uuid4(),
        sent_at=None,
    )
    session.add(fr)
    await session.flush()
    await session.commit()

    return SeededDispatchScenario(
        fiscal_receipt_id=fr.id,
        payment_id=payment.id,
        online_payment_id=uuid4(),
        yookassa_payment_id="unused",
        customer_email=client.email or "",
        audit_correlation_id=fr.audit_correlation_id or uuid4(),
        amount_kopecks=100_000,
    )


@pytest.fixture
def settings_factory(monkeypatch: pytest.MonkeyPatch) -> Callable[..., None]:
    """Helper to monkey-patch YooKassaSettings field defaults at the module level.

    Used by the FISCAL-07 test to assert ``tax_system_code`` flows from
    settings (not hardcoded) by replacing the YooKassaSettings class with
    a stub that returns specific values.
    """

    def _apply(*, tax_system_code: int | None = None, default_vat_code: int | None = None) -> None:
        if tax_system_code is not None:
            monkeypatch.setenv("YOOKASSA_TAX_SYSTEM_CODE", str(tax_system_code))
        if default_vat_code is not None:
            monkeypatch.setenv("YOOKASSA_DEFAULT_VAT_CODE", str(default_vat_code))

    return _apply
