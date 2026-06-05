"""Autopay charges repository — Phase 84 APAY-04.

claim_autopay_failure_notification: per-channel idempotency INSERT for the failure
notification path. The decline path has NO online_payments row, so it CANNOT use
claim_payment_notification (which XOR-requires payment_id OR online_payment_id).
Instead this helper INSERTs an AutopayChargeNotification row keyed on autopay_charge_id
(the always-present claim anchor from autopay_charges.id).

Mirrors claim_payment_notification (online_payments/repository.py) discipline:
  - Opens a FRESH session + transaction (never shares the caller's session).
  - Claim-before-send (at-most-once leaning — D-52-02).
  - Returns True on successful INSERT (channel claimed for this charge+kind+channel triple).
  - Returns False on UNIQUE(autopay_charge_id, kind, channel) IntegrityError (idempotent
    replay — already claimed in a prior invocation or concurrent task run).
  - Catches IntegrityError, NEVER re-raises (best-effort, caller continues).
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.modules.autopay_charges.models import AutopayChargeNotification


async def claim_autopay_failure_notification(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    channel: str,
    autopay_charge_id: UUID,
) -> bool:
    """Claim a failure-notification channel slot for idempotent dedup (D-52-05 mirror).

    Inserts an ``AutopayChargeNotification`` row for the given
    ``(autopay_charge_id, 'autopay_charge_failed', channel)`` triple BEFORE the
    notification is sent (claim-before-send, at-most-once leaning — D-52-02).

    Returns ``True`` on successful INSERT (channel claimed) or ``False`` if the
    UNIQUE(autopay_charge_id, kind, channel) constraint fires (already claimed —
    the notification was sent in a prior invocation or concurrent task run;
    idempotent replay).

    The ``kind`` is fixed to ``'autopay_charge_failed'`` — the only kind allowed by
    the ``AutopayChargeNotification.ck_autopay_charge_notifications_kind`` CHECK
    constraint on that table.

    This helper opens a FRESH session + transaction via the session factory so
    the claim is independent of the caller's (ARQ task) outer UoW. The
    ``IntegrityError`` is caught here — the transaction rolls back automatically
    when the context manager exits — and ``False`` is returned; no re-raise.

    Args:
        session_factory: ARQ-provided ``async_sessionmaker[AsyncSession]`` from
            ``ctx['sessionmaker']``.
        channel: Notification channel — ``'telegram'`` or ``'email'``.
        autopay_charge_id: The ``autopay_charges.id`` UUID for the declined charge.
            This is the idempotency key: there is no ``online_payments`` row for a
            decline (yookassa_payment_id is NOT NULL invariant), so the claim MUST
            key on the always-present autopay_charges row.
    """
    try:
        async with session_factory() as session, session.begin():
            session.add(
                AutopayChargeNotification(
                    autopay_charge_id=autopay_charge_id,
                    kind="autopay_charge_failed",
                    channel=channel,
                )
            )
    except IntegrityError:
        # UNIQUE(autopay_charge_id, kind, channel) violation — this triple was already
        # claimed in a prior invocation or concurrent task run. The txn rolls back inside
        # the context manager exit; return False so the caller can log idempotent-replay
        # and skip the send (D-52-02 at-most-once leaning discipline).
        return False
    return True
