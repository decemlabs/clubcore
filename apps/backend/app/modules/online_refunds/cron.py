"""Phase 51 online_refunds cron-body helpers (Plan 51-09 REFUND-04).

Caller-owns-txn (D-32-10): per-row UoW inside this helper. Each settled or
canceled row gets its own ``async with session.begin():`` block so an
IntegrityError on one row does not roll back work on other rows in the
same tick.

Multi-session pattern (Threat T-51-09-02 mitigation, D-39-06b lineage):
snapshot the row batch (single short txn), close the session, do HTTPS to
ЮKassa per row, re-open a fresh session per row for the settle UoW. This
avoids holding one DB connection across N upstream round-trips.

Threat mitigations:
- T-51-09-01 (race vs dispatch task / webhook handler): the snapshot uses
  ``SELECT FOR UPDATE SKIP LOCKED`` via ``select_pending_older_than`` so
  rows currently locked by a concurrent settle UoW are skipped.
- T-51-09-03 (DoS): ``limit=50`` loop budget per tick (D-51-17 step 6).
- T-51-09-04 (replay vs webhook): caller catches IntegrityError from the
  partial-UNIQUE backstop on ``payments.refund_of`` via
  ``_is_refund_of_uniqueness_conflict`` and records a structlog
  ``yookassa_refund_poll_idempotent_replay`` event; the prior webhook
  delivery already settled the refund.
- T-51-09-05 (PII): structlog event kwargs never include customer_email
  (mirrors settle.py PII discipline).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

import structlog
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.core import audit
from app.integrations.yookassa.client import YooKassaClient
from app.modules.online_refunds import repository as refund_repo
from app.modules.online_refunds.constants import STATUS_CANCELED
from app.modules.online_refunds.settle import _settle_online_refund
from app.modules.payments.repository import _is_refund_of_uniqueness_conflict

_log = structlog.get_logger("modules.online_refunds.cron")

# Plan 51-09 / D-51-17 — only consider rows older than 30 min (let the
# normal webhook path settle fresh refunds without cron interference).
_PENDING_AGE_MINUTES: int = 30

# Plan 51-09 / D-51-17 step 6 — loop budget per tick (T-51-09-03).
_LOOP_BUDGET_PER_TICK: int = 50


async def _poll_pending_refunds(
    session_factory: async_sessionmaker[Any],
    yookassa_client: YooKassaClient,
    arq_pool: Any | None = None,
) -> int:
    """Phase 51 REFUND-04 — reconcile pending online_refunds via get_refund.

    Sequence (D-51-17):
      1. Snapshot up to 50 pending rows older than 30 min (single short txn,
         FOR UPDATE SKIP LOCKED).
      2. For each row: call ``yookassa_client.get_refund(...)``.
      3a. ``result.status == 'succeeded'`` — re-open session, call
          ``_settle_online_refund`` with
          ``chain_root_event='online_refund_polled_settled'`` and a fresh
          ``chain_root_corr=uuid4()``. The webhook-already-settled race
          surfaces here as ``IntegrityError`` on the partial-UNIQUE
          ``uq_payments_refund_of_alive``; caller catches and records a
          structlog WARNING (REFUND-03 replay handling).
      3b. ``result.status == 'canceled'`` — UPDATE row to canceled, emit
          ``online_refund_canceled`` audit (chain root).
      3c. ``result.classification != 'ok'`` — structlog WARNING, leave for
          next tick.
      3d. otherwise (still 'pending' on ЮKassa side) — structlog INFO,
          leave for next tick.

    Returns count of rows processed (succeeded or canceled).
    """
    processed = 0
    cutoff = datetime.now(UTC) - timedelta(minutes=_PENDING_AGE_MINUTES)

    # Step 1 — snapshot the batch under SKIP LOCKED. Short-lived txn; the
    # session is released before any HTTPS call.
    async with session_factory() as session, session.begin():
        rows = await refund_repo.select_pending_older_than(
            session, cutoff=cutoff, limit=_LOOP_BUDGET_PER_TICK
        )
        row_refund_ids: list[tuple[Any, str]] = [(r.id, r.yookassa_refund_id) for r in rows]

    for refund_row_id, yookassa_refund_id in row_refund_ids:
        # Step 2 — HTTPS call OUTSIDE any session block.
        result = await yookassa_client.get_refund(yookassa_refund_id)

        if result.classification != "ok":
            _log.warning(
                "yookassa_refund_poll_refetch_failed",
                refund_row_id=str(refund_row_id),
                classification=result.classification,
            )
            continue

        if result.status == "succeeded":
            # Step 3a — synthesize the settle UoW. Fresh chain_root_corr so
            # the cron-path audit chain is distinct from any webhook chain
            # for the same refund.
            corr = uuid4()
            settled_locals = None
            async with session_factory() as session, session.begin():
                try:
                    settled_locals = await _settle_online_refund(
                        session,
                        online_refund_id=refund_row_id,
                        chain_root_corr=corr,
                        chain_root_event="online_refund_polled_settled",
                        chain_root_event_payload_kwargs={},
                    )
                except IntegrityError as exc:
                    if _is_refund_of_uniqueness_conflict(exc):
                        # T-51-09-04 replay: the webhook caller already
                        # settled this refund. Roll back this txn (the
                        # ``async with session.begin():`` block on exception
                        # rolls back), emit structlog, and continue.
                        _log.warning(
                            "yookassa_refund_poll_idempotent_replay",
                            refund_row_id=str(refund_row_id),
                        )
                        continue
                    raise
            # Phase 51 verification gap fix — enqueue dispatch_fiscal_receipt
            # for the just-INSERTed refund-side fiscal_receipts row. Mirrors
            # the handle_refund_succeeded post-commit hook so cron-path
            # settles also reach ЮKassa /v3/receipts (54-ФЗ compliance).
            # Phase 52 (D-52-10): also enqueue dispatch_payment_notification
            # with kind='refund_succeeded' so the client receives the refund DM.
            if settled_locals is not None and arq_pool is not None:
                await arq_pool.enqueue_job(
                    "dispatch_fiscal_receipt",
                    str(settled_locals.fiscal_receipt_id),
                    _max_tries=3,
                    _expires=60,
                )
                await arq_pool.enqueue_job(
                    "dispatch_payment_notification",
                    _kwargs={
                        "payment_id": str(settled_locals.refund_payment_id),
                        "kind": "refund_succeeded",
                    },
                    _max_tries=3,
                    _expires=60,
                )
            processed += 1

        elif result.status == "canceled":
            # Step 3b — UPDATE row to canceled, emit online_refund_canceled
            # audit (chain-root — no audit_correlation_id available).
            async with session_factory() as session, session.begin():
                row = await refund_repo.get_online_refund_by_id(session, refund_row_id)
                if row is None:
                    _log.warning(
                        "yookassa_refund_poll_row_disappeared",
                        refund_row_id=str(refund_row_id),
                    )
                    continue
                if row.status != "pending":
                    # FSM gate — refuse re-transition of finalised rows
                    # (e.g., a concurrent webhook already canceled it).
                    _log.info(
                        "yookassa_refund_poll_row_not_pending",
                        refund_row_id=str(refund_row_id),
                        status=row.status,
                    )
                    continue
                refund_repo.mark_canceled(row, canceled_at=datetime.now(UTC))
                row.status = STATUS_CANCELED  # defensive — repo helper sets this
                # cancellation_reason: YooKassaRefundResult does not currently
                # expose this field (DEFER-51-XX: Phase 53 cleanup may add it).
                await audit.emit(
                    session,
                    "online_refund_canceled",
                    actor_user_id=None,
                    resource_type="online_refund",
                    resource_id=row.id,
                    audit_correlation_id=None,  # chain root for terminal action
                    online_refund_id=str(row.id),
                    yookassa_refund_id=yookassa_refund_id,
                    cancellation_reason=None,
                )
            processed += 1

        else:
            # Step 3d — still 'pending' on ЮKassa side; next tick re-checks.
            _log.info(
                "yookassa_refund_poll_still_pending",
                refund_row_id=str(refund_row_id),
                status=result.status,
            )

    return processed


__all__ = ("_poll_pending_refunds",)
