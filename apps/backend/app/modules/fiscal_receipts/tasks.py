"""ARQ task — dispatch fiscal_receipts(status='sent') to ЮKassa /v3/receipts (Phase 51 FISCAL-05).

Picks up a fiscal_receipts row (inserted by Phase 50 atomic UoW or refund webhook
in plan 51-07), posts the receipt to ЮKassa under a circuit breaker, retries on
transient errors with exponential backoff + jitter, and writes back the
yookassa_receipt_id (on success) or transitions the row to 'failed' (on terminal
permanent error or max_tries exhaustion).

D-51-13 / D-51-14 / Pitfall 11.

Status flip ('sent' → 'succeeded') is NOT done by this task — the inbound
receipt.succeeded webhook (plan 51-07 handle_receipt_succeeded) does that.
This task only writes yookassa_receipt_id + emits fiscal_receipt_dispatched
on the success path.

The FiscalReceiptDispatcher Protocol implementation (the closure that enqueues
this task into ARQ) lives in BOTH composition roots — app/main.py:create_app()
and app/workers/__init__.py:WorkerSettings.on_startup — per REG-29-03
double-wire. No module-level scaffold lives in this file.

PII discipline (Threat T-51-05-03): structlog event kwargs NEVER include
customer_email; the field is fed to ЮKassa via the receipt body and lives in
the audit_log JSONB payload only.
"""

from __future__ import annotations

import random
from datetime import UTC, datetime
from typing import Any, Final
from uuid import UUID

import structlog
from arq import Retry
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import audit
from app.core.audit_models import AuditLog
from app.integrations.yookassa.circuit_breaker import is_circuit_open, record_failure
from app.integrations.yookassa.receipt import (
    PaymentMode,
    PaymentSubject,
    VatCode,
    build_receipt_item,
)
from app.integrations.yookassa.settings import YooKassaSettings
from app.modules.fiscal_receipts import repository as fiscal_repo
from app.modules.fiscal_receipts.constants import (
    KIND_PAYMENT,
    KIND_REFUND,
    STATUS_FAILED,
    STATUS_SENT,
)
from app.modules.fiscal_receipts.models import FiscalReceipt

_log: Final = structlog.get_logger("modules.fiscal_receipts.tasks")
_PROVIDER: Final[str] = "receipts"  # circuit-breaker scope → cc:yookassa:circuit:receipts

# D-51-14 / Pitfall 11 step 4 backoff schedule (job_try is 1-indexed in ARQ).
_BACKOFF_BASE_SECONDS: Final[tuple[int, ...]] = (30, 120, 600)

# D-51-Discretion / Pitfall 11 step 2 — max ARQ tries before terminal failure.
_MAX_TRIES: Final[int] = 3


def _backoff_with_jitter(job_try: int) -> int:
    """Return defer seconds for the given (1-indexed) try count, with ±10% jitter.

    job_try=1 → ~30s, job_try=2 → ~120s, job_try=3 → ~600s.
    Defensive clamp: out-of-range job_try (e.g. 0 or 4+) uses the final tier.
    """
    idx = max(0, min(job_try - 1, len(_BACKOFF_BASE_SECONDS) - 1))
    base = _BACKOFF_BASE_SECONDS[idx]
    # Backoff jitter is a non-cryptographic timing perturbation; stdlib
    # random is the canonical primitive for thundering-herd avoidance.
    jitter = random.uniform(-0.1, 0.1) * base  # noqa: S311
    return int(base + jitter)


async def _resolve_yookassa_object_id(
    session: AsyncSession,
    fr_row: FiscalReceipt,
) -> str | None:
    """Resolve the ЮKassa-side object_id (payment_id or refund_id) for a fiscal_receipt.

    For kind='payment': walks audit_log for ``online_payment_succeeded`` whose
    payload.audit_correlation_id matches fr_row.audit_correlation_id.

    For kind='refund': two paths are tried in order:
      1. Audit-log path: ``online_refund_polled_settled`` whose
         payload.audit_correlation_id matches fr_row.audit_correlation_id.
         This covers the poll-cron settle path (plan 51-09).
      2. DB-join path: walk
         FiscalReceipt.payment_id → refund Payment.refund_of
         → OnlineRefund.original_payment_id == original_payment.id
         to read OnlineRefund.yookassa_refund_id directly.
         This covers the webhook settle path (plan 51-07) where the fiscal
         receipt's audit_correlation_id is the webhook_intake_corr UUID, not
         the online_refund_initiated chain UUID.

    Returns None if no matching record is found (dispatch task treats this
    as a permanent error — a fiscal_receipt without a resolvable payment chain
    is a misconfiguration).
    """

    if fr_row.audit_correlation_id is None:
        # Try DB-join path for refund even without audit_correlation_id.
        if fr_row.kind == KIND_REFUND:
            return await _resolve_refund_id_via_db_join(session, fr_row)
        return None

    corr_str = str(fr_row.audit_correlation_id)
    if fr_row.kind == KIND_PAYMENT:
        action = "online_payment_succeeded"
        payload_key = "yookassa_payment_id"
        stmt = (
            select(AuditLog.payload)
            .where(AuditLog.action == action)
            .where(AuditLog.payload["audit_correlation_id"].astext == corr_str)
            .order_by(AuditLog.created_at.desc())
            .limit(1)
        )
        result = await session.execute(stmt)
        row = result.first()
        if row is None:
            return None
        payload = row[0] or {}
        value = payload.get(payload_key)
        return str(value) if value is not None else None
    elif fr_row.kind == KIND_REFUND:
        # Path 1: audit-log via online_refund_polled_settled (poll-cron path).
        stmt = (
            select(AuditLog.payload)
            .where(AuditLog.action == "online_refund_polled_settled")
            .where(AuditLog.payload["audit_correlation_id"].astext == corr_str)
            .order_by(AuditLog.created_at.desc())
            .limit(1)
        )
        result = await session.execute(stmt)
        row = result.first()
        if row is not None:
            payload = row[0] or {}
            value = payload.get("yookassa_refund_id")
            if value is not None:
                return str(value)
        # Path 2: DB-join via payments/online_refunds (webhook settle path).
        return await _resolve_refund_id_via_db_join(session, fr_row)
    else:  # pragma: no cover — defended by DB CHECK ck_fiscal_receipts_kind
        return None


async def _resolve_refund_id_via_db_join(
    session: AsyncSession,
    fr_row: FiscalReceipt,
) -> str | None:
    """Resolve yookassa_refund_id for kind='refund' fiscal receipts via DB join.

    Walk: FiscalReceipt.payment_id → refund Payment (amount < 0)
          → refund Payment.refund_of → OnlineRefund.original_payment_id

    Used for webhook-settle path receipts where the audit_correlation_id is
    the webhook_intake_corr UUID, not the online_refund chain UUID.
    """
    from app.modules.online_refunds.models import OnlineRefund
    from app.modules.payments.models import Payment as PaymentModel

    # Load the refund Payment row (the negative payment linked to the FR).
    refund_payment = await session.scalar(
        select(PaymentModel).where(PaymentModel.id == fr_row.payment_id)
    )
    if refund_payment is None or refund_payment.refund_of is None:
        return None

    # Find the OnlineRefund whose original_payment_id matches the original payment.
    online_refund = await session.scalar(
        select(OnlineRefund).where(OnlineRefund.original_payment_id == refund_payment.refund_of)
    )
    if online_refund is None:
        return None
    return online_refund.yookassa_refund_id


async def _resolve_amount_kopecks(
    session: AsyncSession,
    fr_row: FiscalReceipt,
) -> int | None:
    """Resolve the amount (kopecks) for the fiscal_receipt via the parent Payment row.

    The Payment.amount_kopecks is signed (refund rows < 0); take abs() so the
    ЮKassa receipt body is always positive.
    """
    from app.modules.payments.models import Payment

    stmt = select(Payment.amount_kopecks).where(Payment.id == fr_row.payment_id)
    result = await session.execute(stmt)
    row = result.first()
    if row is None:
        return None
    return abs(int(row[0]))


async def _terminal_failure(
    session_factory: Any,
    receipt_uuid: UUID,
    failure_reason: str,
    arq_pool: Any | None = None,
) -> str:
    """Open a fresh session, flip the fiscal_receipt to status='failed', emit audit, commit.

    Helper shared between the validation_error / permanent_error branch and the
    max-tries-exhausted-on-transient branch so the FSM `sent → failed` flip
    always lives in a single place. Returns ``"failed"`` so callers can
    propagate the ARQ return value.

    Phase 52 D-52-10: when ``arq_pool`` is non-None, enqueues
    ``dispatch_payment_notification(kind='fiscal_failed')`` post-commit as a
    best-effort owner alert. The enqueue is guard-wrapped (arq_pool is not None)
    so unit tests that pass None are unaffected.
    """
    async with session_factory() as session:
        fr_row = await fiscal_repo.get_fiscal_receipt_by_id(session, receipt_uuid)
        if fr_row is None:
            _log.warning(
                "fiscal_receipt_disappeared_during_dispatch",
                row_id=str(receipt_uuid),
            )
            return "skipped"
        fr_row.status = STATUS_FAILED
        fr_row.failed_at = datetime.now(UTC)
        fr_row.failure_reason = failure_reason
        await audit.emit(
            session,
            "fiscal_receipt_failed",
            actor_user_id=None,
            resource_type="fiscal_receipt",
            resource_id=fr_row.id,
            audit_correlation_id=(
                str(fr_row.audit_correlation_id)
                if fr_row.audit_correlation_id is not None
                else None
            ),
            fiscal_receipt_id=str(fr_row.id),
            failure_reason=failure_reason,
        )
        # Capture payment_id before commit closes the session (row detaches after).
        fr_payment_id: UUID = fr_row.payment_id
        await session.commit()
    # Phase 52 D-52-10 — best-effort owner alert, post-commit, None-safe.
    if arq_pool is not None:
        await arq_pool.enqueue_job(
            "dispatch_payment_notification",
            _kwargs={"payment_id": str(fr_payment_id), "kind": "fiscal_failed"},
            _max_tries=3,
            _expires=60,
        )
    return "failed"


async def dispatch_fiscal_receipt(ctx: dict[str, Any], fiscal_receipt_id: str) -> str:
    """ARQ task body. Returns ``'sent'`` | ``'failed'`` | ``'skipped'``.

    ctx keys required (wired in WorkerSettings.on_startup):
      - sessionmaker: async_sessionmaker[AsyncSession]
      - yookassa_client: YooKassaClient
      - redis: redis.asyncio.Redis
      - job_try: int (provided by ARQ runtime; defaults to 1 if absent)
    """
    session_factory = ctx["sessionmaker"]
    yookassa_client = ctx["yookassa_client"]
    redis = ctx["redis"]

    # D-51-13 step 2 — circuit-breaker check at head-of-body. Raises Retry
    # WITHOUT consuming a try-count (Pitfall 11 step 1).
    if await is_circuit_open(redis, _PROVIDER):
        _log.warning("yookassa_receipt_circuit_short_circuit", provider=_PROVIDER)
        raise Retry(defer=300)

    receipt_uuid = UUID(fiscal_receipt_id)

    # Multi-session pattern (Threat T-51-05-08): open session, look up row +
    # snapshot the data needed for the HTTP call, close the session BEFORE
    # the httpx round-trip so the DB connection is not held during the
    # ЮKassa POST.
    async with session_factory() as session:
        fr_row = await fiscal_repo.get_fiscal_receipt_by_id(session, receipt_uuid)
        if fr_row is None or fr_row.status != STATUS_SENT:
            _log.info(
                "fiscal_receipt_skip_nonactive",
                row_id=fiscal_receipt_id,
                status=fr_row.status if fr_row else None,
            )
            return "skipped"

        kind = fr_row.kind
        customer_email = fr_row.customer_email
        # D-10 (Phase 999.5): snapshot the phone too (inside the session block,
        # before it closes for the HTTP call) so a phone-only «Чек не нужен»
        # receipt fiscalizes to the phone. create_receipt routes to whichever
        # contact is present (email preferred), so forward both verbatim.
        customer_phone = fr_row.customer_phone
        yookassa_object_id = await _resolve_yookassa_object_id(session, fr_row)
        amount_kopecks = await _resolve_amount_kopecks(session, fr_row)

    if yookassa_object_id is None or amount_kopecks is None:
        # Misconfiguration: fiscal_receipt has no resolvable parent ЮKassa
        # object. Treat as terminal permanent_error so the cron does not
        # alarm forever.
        return await _terminal_failure(
            session_factory,
            receipt_uuid,
            "permanent_error::missing_yookassa_object_id",
            arq_pool=redis,
        )

    # FISCAL-07: consume settings, NEVER hardcode.
    settings = YooKassaSettings()
    tax_system_code = int(settings.tax_system_code)
    vat_code = VatCode(int(settings.default_vat_code))

    # 54-ФЗ-compliant item description (<= 128 chars per build_receipt_item guard).
    description = "Возврат услуги клуба" if kind == KIND_REFUND else "Услуга фитнес-клуба"

    items = [
        build_receipt_item(
            description=description,
            amount_kopecks=amount_kopecks,
            payment_subject=PaymentSubject.SERVICE,  # FISCAL-03 LOCKED literal
            payment_mode=PaymentMode.FULL_PAYMENT,
            vat_code=vat_code,
        ),
    ]

    # HTTP call OUTSIDE the session block. The client never re-raises (SC1) —
    # every transport outcome is a typed YooKassaReceiptResult.
    result = await yookassa_client.create_receipt(
        payment_id=yookassa_object_id,
        customer_email=customer_email,
        customer_phone=customer_phone,
        items=items,
        tax_system_code=tax_system_code,
        idempotency_key=receipt_uuid.hex,  # deterministic per D-51-20
        kind="payment" if kind == KIND_PAYMENT else "refund",
    )

    job_try = int(ctx.get("job_try", 1))

    if result.classification == "transient_error":
        # D-51-14 — record one failure into the sliding window; the breaker
        # opens itself once the count crosses 5 within 60s.
        await record_failure(redis, _PROVIDER)

        if job_try >= _MAX_TRIES:
            # Max-tries exhausted — force terminal failure so the FSM flip
            # `sent → failed` always lives on the dispatch path and the
            # monitor_stale_fiscal_receipts cron does not need to handle this case.
            reason = (
                f"max_tries_exhausted_transient:"
                f"{result.http_status or ''}:"
                f"{result.error_code or ''}"
            )
            return await _terminal_failure(session_factory, receipt_uuid, reason, arq_pool=redis)

        defer = _backoff_with_jitter(job_try)
        _log.warning(
            "yookassa_receipt_dispatch_retry",
            row_id=fiscal_receipt_id,
            job_try=job_try,
            defer_seconds=defer,
        )
        raise Retry(defer=defer)

    if result.classification in ("validation_error", "permanent_error"):
        failure_reason = (
            f"{result.classification}:{result.http_status or ''}:{result.error_code or ''}"
        )
        return await _terminal_failure(
            session_factory, receipt_uuid, failure_reason, arq_pool=redis
        )

    # classification == "ok" — write yookassa_receipt_id + emit dispatched audit.
    # Do NOT flip status to 'succeeded' — the inbound receipt.succeeded webhook
    # (plan 51-07) owns that transition per D-51-13 step 5.
    async with session_factory() as session:
        fr_row = await fiscal_repo.get_fiscal_receipt_by_id(session, receipt_uuid)
        if fr_row is None:
            _log.warning(
                "fiscal_receipt_disappeared_during_dispatch",
                row_id=fiscal_receipt_id,
            )
            return "skipped"
        # result.receipt_id is populated on ok classification (see types.py).
        if result.receipt_id is not None:
            fr_row.yookassa_receipt_id = result.receipt_id
        await audit.emit(
            session,
            "fiscal_receipt_dispatched",
            actor_user_id=None,
            resource_type="fiscal_receipt",
            resource_id=fr_row.id,
            audit_correlation_id=(
                str(fr_row.audit_correlation_id)
                if fr_row.audit_correlation_id is not None
                else None
            ),
            fiscal_receipt_id=str(fr_row.id),
            payment_id=str(fr_row.payment_id),
            kind=fr_row.kind,
            customer_email=fr_row.customer_email,
            # D-10 (Phase 999.5): forensic completeness — audit-DB rows are
            # PII-acceptable. NOT a structlog kwarg (T-999.5-12).
            customer_phone=fr_row.customer_phone,
        )
        await session.commit()

    return "sent"
