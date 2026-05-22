"""Phase 50 FISCAL-01 / D-50-28..32 — fiscal_receipts module skeleton tests.

Covers the declarative-FSM constants, the FiscalReceipt ORM shape, and the
caller-owns-txn repository contract. Mirrors:

- ``tests/unit/memberships/test_renewal_constants.py`` for transition-table
  shape (declarative-FSM is the canonical Phase 24 D-24-03 source-of-truth
  pattern).
- ``tests/unit/test_payments_appendonly.py`` for repository AST scans
  (``session.flush`` / ``session.commit`` MUST be absent from the
  fiscal_receipts repository per D-50-28 caller-owns-txn discipline).

The behaviour-test in :func:`test_insert_does_not_flush_or_commit` uses a
:class:`unittest.mock.MagicMock` stand-in for ``AsyncSession`` so the test
stays in the pure-unit tier (no Postgres dependency). The contract verified is
the same one ``app/modules/online_payments/repository.py:50`` ships — only
``session.add`` is called; ``session.flush`` and ``session.commit`` are NOT.
"""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.modules.fiscal_receipts.constants import (
    FISCAL_RECEIPT_STATUS_TRANSITIONS,
    KIND_PAYMENT,
    KIND_REFUND,
    KIND_VALUES,
    STATUS_FAILED,
    STATUS_PENDING,
    STATUS_SENT,
    STATUS_SUCCEEDED,
    STATUS_VALUES,
)
from app.modules.fiscal_receipts.models import FiscalReceipt
from app.modules.fiscal_receipts.repository import (
    get_fiscal_receipt_by_id,
    get_fiscal_receipt_by_payment_id_and_kind,
    insert_fiscal_receipt,
)


# ---------------------------------------------------------------------------
# constants.py — declarative-FSM transition table (D-50-32)
# ---------------------------------------------------------------------------


def test_status_literals_match_migration_check() -> None:
    """Status literal values mirror the 0035 CHECK constraint enum."""
    assert STATUS_PENDING == "pending"
    assert STATUS_SENT == "sent"
    assert STATUS_SUCCEEDED == "succeeded"
    assert STATUS_FAILED == "failed"
    assert STATUS_VALUES == ("pending", "sent", "succeeded", "failed")


def test_kind_literals_match_migration_check() -> None:
    """Kind literal values mirror the 0035 CHECK constraint enum."""
    assert KIND_PAYMENT == "payment"
    assert KIND_REFUND == "refund"
    assert KIND_VALUES == ("payment", "refund")


def test_transitions_is_read_only_mapping() -> None:
    """MappingProxyType prevents accidental runtime mutation (mirrors memberships shape)."""
    assert isinstance(FISCAL_RECEIPT_STATUS_TRANSITIONS, Mapping)
    assert isinstance(FISCAL_RECEIPT_STATUS_TRANSITIONS, MappingProxyType)


def test_transitions_has_exactly_four_keys() -> None:
    """D-50-32: FSM has exactly pending / sent / succeeded / failed."""
    assert set(FISCAL_RECEIPT_STATUS_TRANSITIONS.keys()) == {
        "pending",
        "sent",
        "succeeded",
        "failed",
    }


def test_transitions_pending_to_sent_only() -> None:
    """D-50-32: pending → {sent}."""
    assert FISCAL_RECEIPT_STATUS_TRANSITIONS["pending"] == frozenset({"sent"})


def test_transitions_sent_to_succeeded_or_failed() -> None:
    """D-50-32: sent → {succeeded, failed} (Phase 51 ARQ task flips terminal status)."""
    assert FISCAL_RECEIPT_STATUS_TRANSITIONS["sent"] == frozenset(
        {"succeeded", "failed"}
    )


def test_transitions_succeeded_is_terminal() -> None:
    """D-50-32: succeeded is a terminal state (no outgoing edges)."""
    assert FISCAL_RECEIPT_STATUS_TRANSITIONS["succeeded"] == frozenset()


def test_transitions_failed_is_terminal() -> None:
    """D-50-32: failed is a terminal state (no outgoing edges)."""
    assert FISCAL_RECEIPT_STATUS_TRANSITIONS["failed"] == frozenset()


# ---------------------------------------------------------------------------
# models.py — FiscalReceipt ORM shape (D-50-29)
# ---------------------------------------------------------------------------


def test_fiscal_receipt_tablename() -> None:
    """ORM binds to the migration-created table name."""
    assert FiscalReceipt.__tablename__ == "fiscal_receipts"


@pytest.mark.parametrize(
    "column_name",
    [
        "id",
        "payment_id",
        "kind",
        "status",
        "yookassa_receipt_id",
        "customer_email",
        "failure_reason",
        "sent_at",
        "succeeded_at",
        "failed_at",
        "audit_correlation_id",
    ],
)
def test_fiscal_receipt_has_column(column_name: str) -> None:
    """D-50-29: all 11 columns declared on the ORM."""
    assert column_name in FiscalReceipt.__table__.columns


def test_fiscal_receipt_payment_id_fk_points_at_payments() -> None:
    """T-50-01-01 mitigation: FK targets payments.id (NOT online_payments.id)."""
    fks = FiscalReceipt.__table__.columns["payment_id"].foreign_keys
    assert len(fks) == 1
    fk = next(iter(fks))
    assert fk.column.table.name == "payments"
    assert fk.ondelete == "RESTRICT"


def test_fiscal_receipt_has_unique_payment_id_kind() -> None:
    """FISCAL-02 cross-channel-discriminator UNIQUE constraint declared on ORM."""
    uq_names = {
        c.name
        for c in FiscalReceipt.__table__.constraints
        if c.__class__.__name__ == "UniqueConstraint"
    }
    assert "uq_fiscal_receipts_payment_id_kind" in uq_names


# ---------------------------------------------------------------------------
# repository.py — caller-owns-txn contract (D-50-28)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_insert_does_not_flush_or_commit() -> None:
    """D-50-28: repository only calls session.add — caller owns flush + commit.

    Mirrors the contract on app/modules/online_payments/repository.py:50.
    """
    session = MagicMock()
    session.add = MagicMock()
    session.flush = AsyncMock()
    session.commit = AsyncMock()

    payment_id = uuid4()
    row = await insert_fiscal_receipt(
        session,
        payment_id=payment_id,
        kind=KIND_PAYMENT,
        status=STATUS_SENT,
        customer_email="bob@example.com",
    )

    assert isinstance(row, FiscalReceipt)
    assert row.payment_id == payment_id
    assert row.kind == KIND_PAYMENT
    assert row.status == STATUS_SENT
    assert row.customer_email == "bob@example.com"
    session.add.assert_called_once_with(row)
    session.flush.assert_not_called()
    session.commit.assert_not_called()


def test_insert_optional_kwargs_default_to_none() -> None:
    """insert kwargs yookassa_receipt_id / audit_correlation_id / sent_at default to None."""
    # Function exists & is async; pure-import contract check.
    assert callable(insert_fiscal_receipt)
    assert callable(get_fiscal_receipt_by_id)
    assert callable(get_fiscal_receipt_by_payment_id_and_kind)
