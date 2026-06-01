"""Fiscal receipts repository — caller-owns-txn (Phase 50 D-50-28).

Caller-owns-txn (D-32-10 lineage): NO ``session.flush()`` and NO
``session.commit()`` calls live here. The Phase 50 webhook UoW
orchestrator (D-50-18 step 5) owns the transactional moment so the
fiscal_receipts INSERT co-writes with the online_payments status
transition and the audit emit in a single UoW.

No UPDATE methods in Phase 50 — status transitions to 'succeeded' /
'failed' are owned by the Phase 51 ARQ task.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.fiscal_receipts.models import FiscalReceipt


async def insert_fiscal_receipt(  # noqa: SVC001 caller-owns-txn — webhook UoW owns flush+commit
    session: AsyncSession,
    *,
    payment_id: UUID,
    kind: str,
    status: str,
    customer_email: str | None = None,
    customer_phone: str | None = None,
    yookassa_receipt_id: str | None = None,
    audit_correlation_id: UUID | None = None,
    sent_at: datetime | None = None,
) -> FiscalReceipt:
    """Insert FiscalReceipt row; caller owns flush + commit (D-50-28).

    Email-OR-phone contact (Phase 999.5 Plan 07 / D-10): supply ``customer_email``
    (preferred) or ``customer_phone`` (54-ФЗ fallback for «Чек не нужен» phone-only
    payments). The ck_fiscal_receipts_contact_present CHECK (DB + model) forbids a
    both-NULL row.
    """
    row = FiscalReceipt(
        payment_id=payment_id,
        kind=kind,
        status=status,
        customer_email=customer_email,
        customer_phone=customer_phone,
        yookassa_receipt_id=yookassa_receipt_id,
        audit_correlation_id=audit_correlation_id,
        sent_at=sent_at,
    )
    session.add(row)
    return row


async def get_fiscal_receipt_by_id(
    session: AsyncSession, fiscal_receipt_id: UUID
) -> FiscalReceipt | None:
    """Return FiscalReceipt by id, or None."""
    stmt: Select[tuple[FiscalReceipt]] = select(FiscalReceipt).where(
        FiscalReceipt.id == fiscal_receipt_id
    )
    result: FiscalReceipt | None = await session.scalar(stmt)
    return result


async def get_fiscal_receipt_by_payment_id_and_kind(
    session: AsyncSession,
    *,
    payment_id: UUID,
    kind: str,
) -> FiscalReceipt | None:
    """Lookup by the UNIQUE(payment_id, kind) discriminator — replay-check entry."""
    stmt: Select[tuple[FiscalReceipt]] = select(FiscalReceipt).where(
        FiscalReceipt.payment_id == payment_id,
        FiscalReceipt.kind == kind,
    )
    result: FiscalReceipt | None = await session.scalar(stmt)
    return result
