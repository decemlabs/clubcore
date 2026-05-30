"""Online payments repository — caller-owns-txn INSERT + GET (Phase 49 D-49-07).

Caller-owns-txn (D-32-10 lineage): NO ``session.flush()`` and NO
``session.commit()`` calls live here. The service layer owns the
transactional moment so the audit rows co-write with the
online_payments INSERT in a single UoW.

No UPDATE methods in Phase 49 — status transitions are Phase 50 (webhook FSM).

Phase 52 (NOT-03 / D-52-05): ``claim_payment_notification`` is the exception —
it owns its own session + txn (fresh session via the session factory) so the
cross-restart idempotency INSERT happens outside the financial UoW. The helper
uses ``session_factory()`` directly so callers (ARQ task) need not hold an
open session when calling it.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import Select, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.modules.online_payments.models import OnlinePayment, PaymentNotification


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
    id_override: UUID | None = None,
) -> OnlinePayment:
    """Insert OnlinePayment row; caller owns flush + commit (D-49-07).

    ``id_override`` (CR-01/CR-02 Phase 71 fix): when provided, uses the
    supplied UUID as the row PK instead of the DB-generated gen_random_uuid().
    Used by the client checkout path so the PWA can embed the payment_id in the
    ЮKassa return_url BEFORE the INSERT — both the row id and the return_url
    carry the same UUID. Staff callers never pass this parameter.
    """
    kwargs: dict[str, Any] = dict(
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
    if id_override is not None:
        kwargs["id"] = id_override
    row = OnlinePayment(**kwargs)
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


async def claim_payment_notification(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    kind: str,
    channel: str,
    payment_id: UUID | None = None,
    online_payment_id: UUID | None = None,
) -> bool:
    """Claim a payment notification channel slot for idempotent dedup (D-52-05).

    Inserts a ``PaymentNotification`` row for the given ``(subject, kind, channel)``
    tuple BEFORE the notification is sent (claim-before-send, at-most-once leaning —
    D-52-02 / D-52-Discretion). Returns ``True`` on successful insert (channel
    claimed) or ``False`` if the partial-UNIQUE index fires (already claimed — the
    notification was sent in a prior invocation or concurrent task; idempotent replay).

    Exactly one of ``payment_id`` / ``online_payment_id`` must be supplied — the
    XOR mirrors the ``payment_notifications.subject_xor`` CHECK constraint (D-52-10).
    A programmer error (both null or both non-null) surfaces as ``AssertionError``
    rather than a deferred FK/CHECK violation, so the bug appears at the callsite
    rather than at flush time.

    NOTE: ``payment_canceled`` kind passes ``online_payment_id=`` (NOT
    ``payment_id=``) because a canceled online payment has no ``payments`` ledger
    row. The XOR CHECK + online-payment partial-unique index handle its dedup.

    This helper opens a FRESH session + transaction via the session factory so
    the claim is independent of the caller's (ARQ task) outer UoW. The
    ``IntegrityError`` is caught here — the transaction rolls back automatically
    when the context manager exits — and ``False`` is returned; no re-raise.
    """
    assert (payment_id is None) != (online_payment_id is None), (
        f"claim_payment_notification: exactly one of payment_id / online_payment_id "
        f"must be non-None (got payment_id={payment_id!r}, online_payment_id={online_payment_id!r})"
    )
    try:
        async with session_factory() as session, session.begin():
            session.add(
                PaymentNotification(
                    payment_id=payment_id,
                    online_payment_id=online_payment_id,
                    kind=kind,
                    channel=channel,
                )
            )
    except IntegrityError:
        # Partial-UNIQUE violation — this (subject, kind, channel) was already
        # claimed. The txn rolls back inside the context manager exit; return False
        # so the caller can log idempotent-replay and skip the send.
        return False
    return True
