"""Phase 45 D-45-28 / NOTIFY-11 — concurrent receipt fanout UNIQUE race test.

Real-Postgres concurrent insert via ``asyncio.gather`` of two independent
session commits. The UNIQUE index ``uq_payment_receipts_payment_channel``
on ``payment_receipts (payment_id, channel)`` guarantees exactly one row
survives; the loser raises :class:`sqlalchemy.exc.IntegrityError` which
the orchestrator post-commit fanout swallows per D-45-08.

Mirrors Phase 22 VIS-TEST-01 + Phase 25 freeze-period race-test discipline
(``tests/integration/payments/test_payments_refund_race.py`` is the closest
in-tree analog). Uses a local real-commit session factory (NOT the default
SAVEPOINT-wrapped ``db_session``) because UNIQUE-INDEX serialisation fires
at COMMIT time across SEPARATE sessions — nested SAVEPOINTs mask the race.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import get_settings
from app.core.models import User
from app.core.permissions import Role
from app.modules.payments.constants import SUBJECT_KIND_MEMBERSHIP
from app.modules.payments.models import Payment, PaymentReceipt

_RACE_OWNER_EMAIL = "receipt-race-owner@example.com"


@pytest_asyncio.fixture
async def real_commit_engine() -> AsyncIterator[AsyncEngine]:
    """Standalone real-commit engine for the receipt UNIQUE race test.

    The default ``db_session`` SAVEPOINT pattern (tests/conftest.py:57)
    composes nested transactions; concurrent INSERTs from two separate
    sessions cannot race against a UNIQUE index inside a single outer
    SAVEPOINT, so we need a real engine that issues real COMMITs.

    Defensively probes Postgres at fixture entry — cleanly SKIPs on
    unreachable Postgres rather than erroring inside ``asyncio.gather``.
    Cleans up with TRUNCATE at teardown (real-commit writes are not
    rolled back); CASCADE handles the FK chain
    ``payment_receipts → payments → users``.
    """
    settings = get_settings()
    engine = create_async_engine(str(settings.database_url), pool_pre_ping=True)

    try:
        async with engine.connect() as probe:
            await probe.execute(text("select 1"))
    except Exception as exc:  # broad: skip on any connectivity failure
        await engine.dispose()
        pytest.skip(
            f"DATABASE_URL not reachable for D-45-28; "
            f"run `docker compose up postgres` first ({exc!r})"
        )

    try:
        yield engine
    finally:
        async with engine.begin() as conn:
            await conn.execute(
                text(
                    "TRUNCATE payment_receipts, payments, users "
                    "RESTART IDENTITY CASCADE"
                )
            )
        await engine.dispose()


@pytest.mark.asyncio
async def test_payment_receipt_concurrent_fanout_race(
    real_commit_engine: AsyncEngine,
) -> None:
    """Two concurrent receipt INSERTs for same (payment_id, channel='email') → 1 row.

    Race outcome (D-45-08): exactly one INSERT commits; the other receives
    :class:`IntegrityError` on ``uq_payment_receipts_payment_channel``.
    """
    session_factory = async_sessionmaker(real_commit_engine, expire_on_commit=False)

    # ── Seed owner + sale payment via a dedicated setup session ─────────
    async with session_factory() as setup_session:
        owner = User(
            email=_RACE_OWNER_EMAIL,
            password_hash=None,  # password is nullable per D-43-06/08
            role=Role.OWNER,
            full_name="Receipt Race Owner",
        )
        setup_session.add(owner)
        await setup_session.commit()
        await setup_session.refresh(owner)

        sale_payment = Payment(
            subject_kind=SUBJECT_KIND_MEMBERSHIP,
            subject_id=uuid4(),
            amount_kopecks=250000,
            method="cash",
            received_by_user_id=owner.id,
            received_at=datetime.now(tz=UTC),
            refund_of=None,
        )
        setup_session.add(sale_payment)
        await setup_session.commit()
        await setup_session.refresh(sale_payment)
        payment_id = sale_payment.id

    # ── Race: two concurrent INSERTs in independent sessions ────────────
    corr_a = uuid4()
    corr_b = uuid4()

    async def _insert_receipt(corr: UUID) -> None:
        async with session_factory() as session:
            session.add(
                PaymentReceipt(
                    payment_id=payment_id,
                    channel="email",
                    audit_correlation_id=corr,
                    to_address="receipt-race@example.com",
                )
            )
            await session.commit()

    results = await asyncio.gather(
        _insert_receipt(corr_a),
        _insert_receipt(corr_b),
        return_exceptions=True,
    )

    integrity_errors = [r for r in results if isinstance(r, IntegrityError)]
    successes = [r for r in results if r is None]
    assert len(integrity_errors) == 1, (
        f"expected exactly 1 IntegrityError on uq_payment_receipts_payment_channel, "
        f"got {results!r}"
    )
    assert len(successes) == 1, (
        f"expected exactly 1 successful commit, got {results!r}"
    )
    # The losing IntegrityError must reference our UNIQUE constraint.
    err_text = str(integrity_errors[0].orig)
    assert "uq_payment_receipts_payment_channel" in err_text, (
        f"IntegrityError not from the expected UNIQUE index: {err_text}"
    )

    # ── DB invariant: exactly one row, with one of the two correlation IDs ──
    async with session_factory() as verify_session:
        count = await verify_session.scalar(
            select(func.count())
            .select_from(PaymentReceipt)
            .where(
                PaymentReceipt.payment_id == payment_id,
                PaymentReceipt.channel == "email",
            )
        )
        assert count == 1, (
            f"expected exactly 1 payment_receipts row, got {count}"
        )

        surviving_corr = await verify_session.scalar(
            select(PaymentReceipt.audit_correlation_id).where(
                PaymentReceipt.payment_id == payment_id,
                PaymentReceipt.channel == "email",
            )
        )
        assert surviving_corr in (corr_a, corr_b), (
            f"surviving audit_correlation_id {surviving_corr!r} is neither "
            f"{corr_a!r} nor {corr_b!r}"
        )
