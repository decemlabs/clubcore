"""Phase 999.5 Plan 07 — Alembic 0049 makes fiscal_receipts phone-aware.

Gap-closure for Issue 2 (UAT test 12, PAY-03 / FISCAL-05). The migration:

- ADDs ``customer_phone`` (nullable Text).
- RELAXes ``customer_email`` to nullable (was NOT NULL since 0035).
- ADDs CHECK ``ck_fiscal_receipts_contact_present`` enforcing at least one of
  (customer_email, customer_phone) is non-NULL (T-999.5-G2-01 mitigation).

Schema-shape assertions run against ``alembic upgrade head`` (the db_session
fixture brings the schema up via Base.metadata + the migration runner is
exercised by the plan's ``alembic upgrade head`` shell step). Row-level
constraint tests run inside their own SAVEPOINT so an IntegrityError on a
guarded write does not poison the outer rollback. Seeding mirrors the locked
W-3 shape from ``tests/integration/test_alembic_0035_fiscal_receipts.py``.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import pytest
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models import User
from app.core.permissions import Role
from app.modules.fiscal_receipts.models import FiscalReceipt
from app.modules.payments.constants import SUBJECT_KIND_MEMBERSHIP
from app.modules.payments.models import Payment


async def _seed_payments_row(session: AsyncSession) -> UUID:
    """W-3 locked seeding shape (mirrors test_alembic_0035_fiscal_receipts)."""
    owner = User(
        email=f"fiscal-0049-{uuid4()}@example.com",
        password_hash=None,
        role=Role.OWNER,
        full_name="Fiscal 0049 Test Owner",
    )
    session.add(owner)
    await session.flush()

    payment = Payment(
        subject_kind=SUBJECT_KIND_MEMBERSHIP,
        subject_id=uuid4(),
        amount_kopecks=250_000,
        method="cash",
        received_by_user_id=owner.id,
        received_at=datetime.now(tz=UTC),
        refund_of=None,
    )
    session.add(payment)
    await session.flush()
    return payment.id


# ---------------------------------------------------------------------------
# Schema-shape assertions (after `alembic upgrade head`)
# ---------------------------------------------------------------------------


async def test_0049_customer_phone_column_exists_and_nullable(
    db_session: AsyncSession,
) -> None:
    """ADD COLUMN customer_phone (nullable Text)."""

    def _columns(sync_conn: Any) -> dict[str, dict[str, Any]]:
        inspector = inspect(sync_conn)
        return {c["name"]: c for c in inspector.get_columns("fiscal_receipts")}

    conn = await db_session.connection()
    cols = await conn.run_sync(_columns)
    assert "customer_phone" in cols
    assert cols["customer_phone"]["nullable"] is True


async def test_0049_customer_email_is_now_nullable(
    db_session: AsyncSession,
) -> None:
    """ALTER customer_email → nullable (was NOT NULL in 0035)."""

    def _columns(sync_conn: Any) -> dict[str, dict[str, Any]]:
        inspector = inspect(sync_conn)
        return {c["name"]: c for c in inspector.get_columns("fiscal_receipts")}

    conn = await db_session.connection()
    cols = await conn.run_sync(_columns)
    assert cols["customer_email"]["nullable"] is True


async def test_0049_contact_present_check_exists(
    db_session: AsyncSession,
) -> None:
    """ADD CHECK ck_fiscal_receipts_contact_present (T-999.5-G2-01)."""

    def _checks(sync_conn: Any) -> set[str | None]:
        inspector = inspect(sync_conn)
        return {cc["name"] for cc in inspector.get_check_constraints("fiscal_receipts")}

    conn = await db_session.connection()
    check_names = await conn.run_sync(_checks)
    assert "ck_fiscal_receipts_contact_present" in check_names


# ---------------------------------------------------------------------------
# Row-level constraint enforcement
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_0049_phone_only_row_persists(db_session: AsyncSession) -> None:
    """A phone-only fiscal receipt (email NULL, phone set) survives the CHECK."""
    payment_id = await _seed_payments_row(db_session)

    db_session.add(
        FiscalReceipt(
            payment_id=payment_id,
            kind="payment",
            status="sent",
            customer_email=None,
            customer_phone="+79991234567",
        )
    )
    await db_session.flush()

    count = await db_session.scalar(
        text(
            "SELECT COUNT(*) FROM fiscal_receipts "
            "WHERE payment_id = :pid AND customer_email IS NULL "
            "AND customer_phone = '+79991234567'"
        ).bindparams(pid=payment_id)
    )
    assert count == 1


@pytest.mark.asyncio
async def test_0049_email_only_row_still_persists(db_session: AsyncSession) -> None:
    """The pre-existing email-only path is unchanged (phone NULL, email set)."""
    payment_id = await _seed_payments_row(db_session)

    db_session.add(
        FiscalReceipt(
            payment_id=payment_id,
            kind="payment",
            status="sent",
            customer_email="client@example.ru",
            customer_phone=None,
        )
    )
    await db_session.flush()

    count = await db_session.scalar(
        text(
            "SELECT COUNT(*) FROM fiscal_receipts "
            "WHERE payment_id = :pid AND customer_phone IS NULL "
            "AND customer_email = 'client@example.ru'"
        ).bindparams(pid=payment_id)
    )
    assert count == 1


@pytest.mark.asyncio
async def test_0049_both_null_contact_rejected(db_session: AsyncSession) -> None:
    """CHECK ck_fiscal_receipts_contact_present rejects an email+phone both-NULL row."""
    payment_id = await _seed_payments_row(db_session)

    with pytest.raises(IntegrityError):
        async with db_session.begin_nested():
            db_session.add(
                FiscalReceipt(
                    payment_id=payment_id,
                    kind="payment",
                    status="sent",
                    customer_email=None,
                    customer_phone=None,
                )
            )
            await db_session.flush()
