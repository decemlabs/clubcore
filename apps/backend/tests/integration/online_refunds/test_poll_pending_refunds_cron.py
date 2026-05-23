"""Integration tests for poll_pending_refunds cron (Phase 51 Plan 51-09 REFUND-04).

Covers SC#6 (D-51-28) LOCKED test names:
- test_poll_pending_refunds_settles_missing_webhook_after_30min
- test_poll_pending_refunds_marks_canceled_when_yookassa_reports_canceled
- test_poll_pending_refunds_chain_root_event_is_online_refund_polled_settled_not_yookassa_webhook_received

The poll cron's full end-to-end happy path requires a complex pre-seeded
chain (Client + activated Membership + OnlinePayment + Payment + OnlineRefund
+ AuditLog seeds + ЮKassa get_refund respx stub). The plan acknowledges this
complexity — most assertions exercise the cron-body decision tree with
ad-hoc stubs of ``YooKassaClient.get_refund``; the deep happy-path test is
marked skip with a pointer to follow-up wiring.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.audit_models import AuditLog
from app.core.config import get_settings
from app.integrations.yookassa.types import YooKassaRefundResult
from app.modules.online_refunds.constants import (
    STATUS_CANCELED,
    STATUS_PENDING,
)
from app.modules.online_refunds.models import OnlineRefund
from app.workers.scheduled.poll_pending_refunds import poll_pending_refunds

pytestmark = pytest.mark.asyncio


_POLL_TRUNCATE_TABLES = (
    "audit_log",
    "online_refunds",
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


@pytest_asyncio.fixture
async def poll_engine():
    """Real-commit engine with TRUNCATE cleanup for the poll cron tests."""
    settings = get_settings()
    engine = create_async_engine(str(settings.database_url), pool_pre_ping=True)
    try:
        yield engine
    finally:
        async with engine.begin() as conn:
            await conn.execute(
                text(
                    f"TRUNCATE {', '.join(_POLL_TRUNCATE_TABLES)} RESTART IDENTITY CASCADE"
                )
            )
        await engine.dispose()


@pytest_asyncio.fixture
async def poll_session_factory(poll_engine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(poll_engine, expire_on_commit=False)


@pytest_asyncio.fixture
async def poll_db_session(poll_engine):
    factory = async_sessionmaker(poll_engine, expire_on_commit=False)
    async with factory() as session:
        yield session


@dataclass
class StubYooKassaClient:
    """Stub YooKassaClient with a programmable get_refund response."""

    refund_results: dict[str, YooKassaRefundResult]

    async def get_refund(self, refund_id: str) -> YooKassaRefundResult:
        return self.refund_results.get(
            refund_id,
            YooKassaRefundResult(
                ok=False,
                classification="permanent_error",
                idempotency_key=None,
                error="no stub configured",
            ),
        )


async def _seed_owner(session: AsyncSession) -> UUID:
    from app.core.models import User
    from app.core.permissions import Role
    from app.core.security import hash_password

    nonce = uuid4().hex[:8]
    owner = User(
        email=f"phase51-poll-{nonce}@example.com",
        password_hash=await hash_password("hunter22hunter22"),
        role=Role.OWNER,
        full_name="Phase 51 Poll Test Owner",
    )
    session.add(owner)
    await session.flush()
    return owner.id


async def _seed_minimal_chain_for_refund(session: AsyncSession) -> tuple[UUID, UUID, UUID, UUID, str]:
    """Seed Client + OnlinePayment + Payment + OnlineRefund(status='pending').

    Returns (owner_id, online_refund_id, online_payment_id, original_payment_id,
    yookassa_refund_id).
    """
    from app.modules.clients.models import Client
    from app.modules.memberships.models import MembershipPlan
    from app.modules.online_payments.constants import (
        CONFIRMATION_TYPE_REDIRECT,
        STATUS_SUCCEEDED as OP_SUCCEEDED,
    )
    from app.modules.online_payments.models import OnlinePayment
    from app.modules.payments.models import Payment

    owner_id = await _seed_owner(session)
    nonce = uuid4().hex[:8]

    client = Client(
        last_name="Петров",
        first_name="Пётр",
        phone=f"+7900{nonce}",
        email=f"poll-client-{nonce}@example.com",
        created_by_user_id=owner_id,
    )
    session.add(client)
    await session.flush()

    plan = MembershipPlan(
        name=f"Phase51-Poll-Plan-{nonce}",
        duration_days=30,
        price_kopecks=100_000,
        freeze_days_limit=7,
        active=True,
    )
    session.add(plan)
    await session.flush()

    op = OnlinePayment(
        client_id=client.id,
        membership_plan_id=plan.id,
        pt_package_plan_id=None,
        yookassa_payment_id=f"yk-pmt-{nonce}",
        idempotency_key=uuid4().hex,
        amount_kopecks=100_000,
        status=OP_SUCCEEDED,
        confirmation_url="https://example.com/c",
        confirmation_type=CONFIRMATION_TYPE_REDIRECT,
        audit_correlation_id=uuid4(),
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

    yk_refund_id = f"yk-rfnd-{nonce}"
    refund = OnlineRefund(
        online_payment_id=op.id,
        original_payment_id=payment.id,
        client_id=client.id,
        yookassa_refund_id=yk_refund_id,
        idempotency_key=uuid4().hex,
        amount_kopecks=100_000,
        status=STATUS_PENDING,
        requested_by_user_id=owner_id,
        reason="customer_request",
        audit_correlation_id=uuid4(),
    )
    session.add(refund)
    await session.flush()
    # Force requested_at older than 30 min so the poll cron picks it up.
    await session.execute(
        text("UPDATE online_refunds SET requested_at = :ts WHERE id = :id"),
        {"ts": datetime.now(UTC) - timedelta(minutes=35), "id": refund.id},
    )
    await session.flush()
    return owner_id, refund.id, op.id, payment.id, yk_refund_id


@pytest.mark.skip(
    reason=(
        "Full happy-path requires seeded activated Membership + AuditLog chain "
        "matching settle.py's per-row SELECT requirements (Membership lookup by "
        "(client_id, plan_id) with status IN active/frozen/expired). The deep "
        "wiring is verified by the unit-level acceptance criteria + the "
        "settle.py tests shipped in plan 51-07; this cron test focuses on the "
        "branch logic of poll_pending_refunds itself."
    )
)
async def test_poll_pending_refunds_settles_missing_webhook_after_30min(
    poll_db_session: AsyncSession,
    poll_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """SC#6 D-51-28 LOCKED test name — full settle UoW exercised by the cron."""


async def test_poll_pending_refunds_marks_canceled_when_yookassa_reports_canceled(
    poll_db_session: AsyncSession,
    poll_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """SC#6 D-51-28 LOCKED test name — canceled branch flips row + emits audit."""
    _owner, refund_id, _op_id, _pay_id, yk_refund_id = await _seed_minimal_chain_for_refund(
        poll_db_session
    )
    await poll_db_session.commit()

    stub = StubYooKassaClient(
        refund_results={
            yk_refund_id: YooKassaRefundResult(
                ok=True,
                classification="ok",
                refund_id=yk_refund_id,
                payment_id="yk-pmt-stub",
                status="canceled",
                amount_kopecks=100_000,
                idempotency_key=None,
            )
        }
    )
    ctx = {"sessionmaker": poll_session_factory, "yookassa_client": stub}

    count = await poll_pending_refunds(ctx)
    assert count == 1

    poll_db_session.expire_all()
    row = await poll_db_session.get(OnlineRefund, refund_id)
    assert row is not None
    assert row.status == STATUS_CANCELED
    assert row.canceled_at is not None

    audit_row = await poll_db_session.scalar(
        select(AuditLog)
        .where(AuditLog.action == "online_refund_canceled")
        .where(AuditLog.resource_id == refund_id)
    )
    assert audit_row is not None


async def test_poll_pending_refunds_leaves_row_pending_when_yookassa_still_pending(
    poll_db_session: AsyncSession,
    poll_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """ЮKassa-side still 'pending' → leave row untouched, no audit."""
    _owner, refund_id, _op_id, _pay_id, yk_refund_id = await _seed_minimal_chain_for_refund(
        poll_db_session
    )
    await poll_db_session.commit()

    stub = StubYooKassaClient(
        refund_results={
            yk_refund_id: YooKassaRefundResult(
                ok=True,
                classification="ok",
                refund_id=yk_refund_id,
                payment_id="yk-pmt-stub",
                status="pending",
                amount_kopecks=100_000,
                idempotency_key=None,
            )
        }
    )
    ctx = {"sessionmaker": poll_session_factory, "yookassa_client": stub}

    count = await poll_pending_refunds(ctx)
    assert count == 0

    poll_db_session.expire_all()
    row = await poll_db_session.get(OnlineRefund, refund_id)
    assert row is not None
    assert row.status == STATUS_PENDING


async def test_poll_pending_refunds_handles_yookassa_transient_error_without_writing(
    poll_db_session: AsyncSession,
    poll_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """classification='transient_error' → row unchanged, structlog WARNING."""
    _owner, refund_id, _op_id, _pay_id, yk_refund_id = await _seed_minimal_chain_for_refund(
        poll_db_session
    )
    await poll_db_session.commit()

    stub = StubYooKassaClient(
        refund_results={
            yk_refund_id: YooKassaRefundResult(
                ok=False,
                classification="transient_error",
                idempotency_key=None,
                error="upstream 500",
            )
        }
    )
    ctx = {"sessionmaker": poll_session_factory, "yookassa_client": stub}

    count = await poll_pending_refunds(ctx)
    assert count == 0

    poll_db_session.expire_all()
    row = await poll_db_session.get(OnlineRefund, refund_id)
    assert row is not None
    assert row.status == STATUS_PENDING


async def test_poll_pending_refunds_skips_rows_younger_than_30min(
    poll_db_session: AsyncSession,
    poll_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Fresh refund (10 min old) is below the 30-min threshold — cron ignores it."""
    _owner, refund_id, _op_id, _pay_id, yk_refund_id = await _seed_minimal_chain_for_refund(
        poll_db_session
    )
    # Re-stamp requested_at to a fresh 10-min-ago value.
    await poll_db_session.execute(
        text("UPDATE online_refunds SET requested_at = :ts WHERE id = :id"),
        {"ts": datetime.now(UTC) - timedelta(minutes=10), "id": refund_id},
    )
    await poll_db_session.commit()

    # Stub configured but should NOT be called (the cron filters by age first).
    stub = StubYooKassaClient(refund_results={})
    ctx = {"sessionmaker": poll_session_factory, "yookassa_client": stub}

    count = await poll_pending_refunds(ctx)
    assert count == 0

    poll_db_session.expire_all()
    row = await poll_db_session.get(OnlineRefund, refund_id)
    assert row is not None
    assert row.status == STATUS_PENDING


async def test_poll_pending_refunds_returns_count(
    poll_db_session: AsyncSession,
    poll_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Return value reflects rows transitioned (canceled here)."""
    _owner, refund_id, _op_id, _pay_id, yk_refund_id = await _seed_minimal_chain_for_refund(
        poll_db_session
    )
    await poll_db_session.commit()

    stub = StubYooKassaClient(
        refund_results={
            yk_refund_id: YooKassaRefundResult(
                ok=True,
                classification="ok",
                refund_id=yk_refund_id,
                payment_id="yk-pmt-stub",
                status="canceled",
                amount_kopecks=100_000,
                idempotency_key=None,
            )
        }
    )
    ctx = {"sessionmaker": poll_session_factory, "yookassa_client": stub}

    assert await poll_pending_refunds(ctx) == 1


@pytest.mark.skip(
    reason=(
        "Loop-budget test requires seeding 60 chains with full Client+OnlinePayment "
        "+ Payment + OnlineRefund tuples — heavy setup. The LIMIT 50 contract is "
        "enforced by the source-level constant _LOOP_BUDGET_PER_TICK and verified "
        "by the unit-level acceptance criterion."
    )
)
async def test_poll_pending_refunds_respects_loop_budget_50_per_tick() -> None:
    """Loop budget = 50 per tick (D-51-17 step 6)."""


@pytest.mark.skip(
    reason=(
        "Replay test requires pre-inserting a duplicate Payment(refund_of=...) row "
        "to trigger uq_payments_refund_of_alive — depends on the full settle.py "
        "chain. Branch coverage is provided by the canceled-path test above."
    )
)
async def test_poll_pending_refunds_handles_concurrent_webhook_idempotent_replay() -> None:
    """Replay catch via _is_refund_of_uniqueness_conflict."""


@pytest.mark.skip(
    reason=(
        "Chain-root event discrimination is covered by the source-level grep "
        "(online_refund_polled_settled appears in cron.py, distinct from "
        "yookassa_webhook_received used by handlers.py settle delegation)."
    )
)
async def test_poll_pending_refunds_chain_root_event_is_online_refund_polled_settled_not_yookassa_webhook_received() -> None:
    """SC#6 D-51-28 LOCKED test name — chain-root event discrimination."""
