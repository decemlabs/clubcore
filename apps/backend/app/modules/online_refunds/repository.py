"""Online refunds repository — caller-owns-txn INSERT + GET (Phase 51 D-51-07).

Caller-owns-txn (D-32-10 lineage): NO ``session.flush()`` and NO
``session.commit()`` calls live here. The service layer (Plan 51-08)
and webhook/poll-cron layers (Plans 51-07 / 51-09) own the transactional
moment so the audit rows co-write with the online_refunds mutation in a
single UoW.

Status transitions are pure attribute mutators (``mark_succeeded`` /
``mark_canceled``) — the FSM gate lives in the calling service per D-51-07.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from uuid import UUID

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.online_refunds.constants import STATUS_PENDING
from app.modules.online_refunds.models import OnlineRefund


async def insert_online_refund(  # noqa: SVC001 caller-owns-txn — service UoW owns flush+commit
    session: AsyncSession,
    *,
    online_payment_id: UUID,
    original_payment_id: UUID,
    client_id: UUID,
    yookassa_refund_id: str,
    idempotency_key: str,
    amount_kopecks: int,
    status: str,
    requested_by_user_id: UUID,
    reason: str | None,
    audit_correlation_id: UUID | None,
) -> OnlineRefund:
    """Insert OnlineRefund row; caller owns flush + commit (D-51-07)."""
    row = OnlineRefund(
        online_payment_id=online_payment_id,
        original_payment_id=original_payment_id,
        client_id=client_id,
        yookassa_refund_id=yookassa_refund_id,
        idempotency_key=idempotency_key,
        amount_kopecks=amount_kopecks,
        status=status,
        requested_by_user_id=requested_by_user_id,
        reason=reason,
        audit_correlation_id=audit_correlation_id,
    )
    session.add(row)
    return row


async def get_online_refund_by_id(session: AsyncSession, refund_id: UUID) -> OnlineRefund | None:
    """Return OnlineRefund by id, or None."""
    stmt: Select[tuple[OnlineRefund]] = select(OnlineRefund).where(OnlineRefund.id == refund_id)
    result: OnlineRefund | None = await session.scalar(stmt)
    return result


async def get_online_refund_by_yookassa_refund_id(
    session: AsyncSession, yookassa_refund_id: str
) -> OnlineRefund | None:
    """Webhook handler entry point — look up by ЮKassa-side refund handle."""
    stmt: Select[tuple[OnlineRefund]] = select(OnlineRefund).where(
        OnlineRefund.yookassa_refund_id == yookassa_refund_id
    )
    result: OnlineRefund | None = await session.scalar(stmt)
    return result


async def get_online_refund_by_idempotency_key(
    session: AsyncSession, idempotency_key: str
) -> OnlineRefund | None:
    """Replay-check entry point for the POST /refund endpoint (D-48-11)."""
    stmt: Select[tuple[OnlineRefund]] = select(OnlineRefund).where(
        OnlineRefund.idempotency_key == idempotency_key
    )
    result: OnlineRefund | None = await session.scalar(stmt)
    return result


async def select_pending_older_than(
    session: AsyncSession,
    *,
    cutoff: datetime,
    limit: int = 50,
) -> Sequence[OnlineRefund]:
    """Pending refunds older than ``cutoff``, locked SKIP LOCKED for poll cron.

    Used by the Phase 51 poll-pending-refunds ARQ task (D-51-17 step 6). Default
    ``limit=50`` is the loop budget cap; callers must pass an explicit kwarg to
    raise it (mitigates T-51-02-05 — unbounded query DoS).
    """
    stmt: Select[tuple[OnlineRefund]] = (
        select(OnlineRefund)
        .where(
            OnlineRefund.status == STATUS_PENDING,
            OnlineRefund.requested_at < cutoff,
        )
        .limit(limit)
        .with_for_update(skip_locked=True)
    )
    result = await session.scalars(stmt)
    return result.all()


def mark_succeeded(row: OnlineRefund, *, succeeded_at: datetime) -> None:
    """Mutate the row to ``succeeded`` terminal state — caller owns the txn."""
    from app.modules.online_refunds.constants import STATUS_SUCCEEDED

    row.status = STATUS_SUCCEEDED
    row.succeeded_at = succeeded_at


def mark_canceled(row: OnlineRefund, *, canceled_at: datetime) -> None:
    """Mutate the row to ``canceled`` terminal state — caller owns the txn."""
    from app.modules.online_refunds.constants import STATUS_CANCELED

    row.status = STATUS_CANCELED
    row.canceled_at = canceled_at
