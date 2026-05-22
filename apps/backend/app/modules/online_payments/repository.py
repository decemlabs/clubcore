"""Online payments repository — caller-owns-txn INSERT + GET (Phase 49 D-49-07).

Caller-owns-txn (D-32-10 lineage): NO ``session.flush()`` and NO
``session.commit()`` calls live here. The service layer owns the
transactional moment so the audit rows co-write with the
online_payments INSERT in a single UoW.

No UPDATE methods in Phase 49 — status transitions are Phase 50 (webhook FSM).
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.online_payments.models import OnlinePayment


async def insert_online_payment(
    session: AsyncSession,
    *,
    client_id: UUID,
    membership_plan_id: UUID | None,
    pt_package_plan_id: UUID | None,
    yookassa_payment_id: str,
    idempotency_key: str,
    amount_kopecks: int,
    status: str,
    confirmation_url: str | None,
    confirmation_type: str,
    created_by_user_id: UUID | None,
    audit_correlation_id: UUID,
) -> OnlinePayment:
    """Insert OnlinePayment row; caller owns flush + commit (D-49-07)."""
    row = OnlinePayment(
        client_id=client_id,
        membership_plan_id=membership_plan_id,
        pt_package_plan_id=pt_package_plan_id,
        yookassa_payment_id=yookassa_payment_id,
        idempotency_key=idempotency_key,
        amount_kopecks=amount_kopecks,
        status=status,
        confirmation_url=confirmation_url,
        confirmation_type=confirmation_type,
        created_by_user_id=created_by_user_id,
        audit_correlation_id=audit_correlation_id,
    )
    session.add(row)
    return row


async def get_online_payment_by_id(
    session: AsyncSession, online_payment_id: UUID
) -> OnlinePayment | None:
    """Return OnlinePayment by id, or None."""
    stmt: Select[tuple[OnlinePayment]] = select(OnlinePayment).where(
        OnlinePayment.id == online_payment_id
    )
    result: OnlinePayment | None = await session.scalar(stmt)
    return result


async def get_online_payment_by_idempotency_key(
    session: AsyncSession, idempotency_key: str
) -> OnlinePayment | None:
    """Replay-check entry point for D-49-08 deterministic key flow."""
    stmt: Select[tuple[OnlinePayment]] = select(OnlinePayment).where(
        OnlinePayment.idempotency_key == idempotency_key
    )
    result: OnlinePayment | None = await session.scalar(stmt)
    return result
