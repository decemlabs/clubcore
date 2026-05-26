"""Phase 50 FISCAL-01 / FISCAL-02 — Alembic 0035 ships fiscal_receipts.

D-50-30 + D-50-31. The migration creates the ``fiscal_receipts`` FSM table with:

- 11 columns (id, payment_id, kind, status, yookassa_receipt_id,
  customer_email, failure_reason, sent_at, succeeded_at, failed_at,
  audit_correlation_id).
- 1 FK ``fk_fiscal_receipts_payment_id_payments`` ON DELETE RESTRICT
  pointing at ``payments.id`` (T-50-01-01 mitigation: NOT online_payments.id).
- 2 CHECK constraints (``ck_fiscal_receipts_kind`` enforcing
  ``IN ('payment','refund')``; ``ck_fiscal_receipts_status`` enforcing
  ``IN ('pending','sent','succeeded','failed')``).
- 1 UNIQUE constraint ``uq_fiscal_receipts_payment_id_kind`` —
  cross-channel-discriminator (FISCAL-02): at most one 'payment' + one
  'refund' receipt per Payment ledger row.

The ``db_session`` fixture brings the DB up to head via the FastAPI lifespan
that loads ``Base.metadata``; the migration runner is exercised by the
``alembic upgrade head`` / ``alembic downgrade`` shell invocations in the
plan's verify step.

W-3 LOCKED seeding analog: the row-level constraint tests seed a Payment via
the exact constructor shape used by ``tests/integration/payments/conftest.py::
make_payment`` and ``tests/integration/test_payment_receipt_race.py:106-117``
(``Payment(subject_kind=SUBJECT_KIND_MEMBERSHIP, subject_id=uuid4(),
amount_kopecks=250_000, method='cash', received_by_user_id=owner.id,
received_at=datetime.now(tz=UTC), refund_of=None)``). User import is via
``app.core.models`` and Role via ``app.core.permissions`` per the verified
analog in test_payment_receipt_race.py:34-35 (NOT app.modules.users.*).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, cast
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
    """W-3 locked seeding shape — Payment factory analog from
    tests/integration/payments/conftest.py::make_payment.

    Creates one User (owner) + one Payment row inside the SAVEPOINT-wrapped
    session, returns the Payment.id for FK targeting. The Payment ledger has
    no client_id (per-subject, not per-client — see plan interfaces section).
    """
    owner = User(
        email=f"fiscal-test-{uuid4()}@example.com",
        password_hash=None,  # nullable per D-43-06/08
        role=Role.OWNER,
        full_name="Fiscal Receipt Test Owner",
    )
    session.add(owner)
    await session.flush()  # populate owner.id without commit

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


async def test_0035_creates_fiscal_receipts_table(db_session: AsyncSession) -> None:
    """D-50-30 — table is reachable after upgrade head."""

    def _has_table(sync_conn: object) -> bool:
        inspector = inspect(sync_conn)
        return inspector.has_table("fiscal_receipts")

    conn = await db_session.connection()
    has_table = await conn.run_sync(_has_table)
    assert has_table is True


async def test_0035_fiscal_receipts_has_unique_payment_id_kind(
    db_session: AsyncSession,
) -> None:
    """FISCAL-02 — cross-channel-discriminator UNIQUE(payment_id, kind) ships in 0035."""

    def _uq_constraints(sync_conn: Any) -> list[dict[str, Any]]:
        inspector = inspect(sync_conn)
        return inspector.get_unique_constraints("fiscal_receipts")

    conn = await db_session.connection()
    uqs = await conn.run_sync(_uq_constraints)
    by_name: dict[str | None, dict[str, Any]] = {uc["name"]: uc for uc in uqs}
    assert "uq_fiscal_receipts_payment_id_kind" in by_name
    cols = sorted(cast(list[str], by_name["uq_fiscal_receipts_payment_id_kind"]["column_names"]))
    assert cols == ["kind", "payment_id"]


async def test_0035_fiscal_receipts_has_check_constraints(
    db_session: AsyncSession,
) -> None:
    """D-50-30 — kind + status DB-enforced enum CHECKs ship in 0035."""

    def _checks(sync_conn: Any) -> set[str | None]:
        inspector = inspect(sync_conn)
        return {cc["name"] for cc in inspector.get_check_constraints("fiscal_receipts")}

    conn = await db_session.connection()
    check_names = await conn.run_sync(_checks)
    assert "ck_fiscal_receipts_kind" in check_names
    assert "ck_fiscal_receipts_status" in check_names


async def test_0035_fiscal_receipts_fk_points_at_payments(
    db_session: AsyncSession,
) -> None:
    """T-50-01-01 mitigation — payment_id FK targets payments.id (NOT online_payments.id)."""

    def _fks(sync_conn: Any) -> list[dict[str, Any]]:
        inspector = inspect(sync_conn)
        return inspector.get_foreign_keys("fiscal_receipts")

    conn = await db_session.connection()
    fks = await conn.run_sync(_fks)
    assert len(fks) == 1
    fk = fks[0]
    assert fk["referred_table"] == "payments"
    assert fk["constrained_columns"] == ["payment_id"]
    assert fk["referred_columns"] == ["id"]
    assert fk.get("options", {}).get("ondelete") == "RESTRICT"


# ---------------------------------------------------------------------------
# Row-level constraint enforcement (each test inside its own SAVEPOINT so the
# IntegrityError on a guarded write doesn't poison the outer rollback).
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_0035_fiscal_receipts_kind_check_enforced(
    db_session: AsyncSession,
) -> None:
    """CHECK ck_fiscal_receipts_kind rejects rows with kind='invoice'."""
    payment_id = await _seed_payments_row(db_session)

    with pytest.raises(IntegrityError):
        async with db_session.begin_nested():
            db_session.add(
                FiscalReceipt(
                    payment_id=payment_id,
                    kind="invoice",  # NOT in ('payment', 'refund')
                    status="sent",
                    customer_email="x@y.z",
                )
            )
            await db_session.flush()


@pytest.mark.asyncio
async def test_0035_fiscal_receipts_status_check_enforced(
    db_session: AsyncSession,
) -> None:
    """CHECK ck_fiscal_receipts_status rejects rows with status='invalid'."""
    payment_id = await _seed_payments_row(db_session)

    with pytest.raises(IntegrityError):
        async with db_session.begin_nested():
            db_session.add(
                FiscalReceipt(
                    payment_id=payment_id,
                    kind="payment",
                    status="invalid",  # NOT in enum
                    customer_email="x@y.z",
                )
            )
            await db_session.flush()


@pytest.mark.asyncio
async def test_0035_unique_payment_id_kind_enforced(
    db_session: AsyncSession,
) -> None:
    """FISCAL-02: (payment_id, kind) UNIQUE; duplicate same-kind row rejected, different kind OK."""
    payment_id = await _seed_payments_row(db_session)

    # First INSERT (payment_id, 'payment') succeeds.
    db_session.add(
        FiscalReceipt(
            payment_id=payment_id,
            kind="payment",
            status="sent",
            customer_email="first@example.com",
        )
    )
    await db_session.flush()

    # Same (payment_id, 'payment') again → IntegrityError on UNIQUE constraint.
    with pytest.raises(IntegrityError):
        async with db_session.begin_nested():
            db_session.add(
                FiscalReceipt(
                    payment_id=payment_id,
                    kind="payment",
                    status="sent",
                    customer_email="dup@example.com",
                )
            )
            await db_session.flush()

    # Different kind ('refund') on same payment_id → succeeds.
    db_session.add(
        FiscalReceipt(
            payment_id=payment_id,
            kind="refund",
            status="sent",
            customer_email="refund@example.com",
        )
    )
    await db_session.flush()

    # Verify two rows present.
    count = await db_session.scalar(
        text("SELECT COUNT(*) FROM fiscal_receipts WHERE payment_id = :pid").bindparams(
            pid=payment_id
        )
    )
    assert count == 2
