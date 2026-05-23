"""Phase 51 D-51-18 — shared settle-the-refund UoW.

Used by:
  - apps/backend/app/api/v1/_internal/yookassa/handlers.py:handle_refund_succeeded
    (webhook path; chain_root_event='yookassa_webhook_received')
  - apps/backend/app/workers/scheduled/poll_pending_refunds.py (plan 51-09)
    (cron path; chain_root_event='online_refund_polled_settled')

Caller-owns-txn (D-32-10): callers open their own ``async with session.begin():``
block BEFORE invoking this helper. The helper does NOT commit, does NOT catch
IntegrityError on the PaymentRefunder partial-UNIQUE conflict — it lets the
conflict propagate so each caller records its own audit outcome
(webhook → silent 200 + idempotency_outcome='replay';
cron → continue to next row + structlog 'yookassa_refund_poll_idempotent_replay').

Errata #4 — direct repository call for the subject transition. The sale-side
activator slots are forward-only (D-50-22 sale lineage); refund-side rewinds
go through ``update_membership_status`` / ``update_pt_package_status`` directly
with the ``CANCELLATION_REASON_REFUNDED`` sentinel.

PII discipline (Threat T-51-07-07): ``customer_email`` MAY appear in audit-DB
rows (the audit DB is PII-acceptable per project policy) but MUST NOT appear in
structlog event kwargs. This module emits no structlog lines with customer_email.
"""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal
from uuid import UUID

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import audit
from app.core.dependencies import get_payment_refunder
from app.modules.clients.models import Client
from app.modules.fiscal_receipts.constants import KIND_REFUND, STATUS_SENT
from app.modules.fiscal_receipts.repository import insert_fiscal_receipt
from app.modules.memberships import repository as memberships_repo
from app.modules.memberships.constants import CANCELLATION_REASON_REFUNDED
from app.modules.memberships.models import Membership
from app.modules.online_payments.models import OnlinePayment
from app.modules.online_refunds import repository as refund_repo
from app.modules.payments.constants import (
    SUBJECT_KIND_MEMBERSHIP,
    SUBJECT_KIND_PT_PACKAGE,
)
from app.modules.payments.models import Payment
from app.modules.pt_packages import repository as pt_packages_repo
from app.modules.pt_packages.constants import (
    CANCELLATION_REASON_REFUNDED as PT_CANCELLATION_REASON_REFUNDED,
)
from app.modules.pt_packages.models import PtPackage

_log = structlog.get_logger("modules.online_refunds.settle")


async def _settle_online_refund(  # noqa: SVC001 caller-owns-txn
    session: AsyncSession,
    *,
    online_refund_id: UUID,
    chain_root_corr: UUID,
    chain_root_event: Literal[
        "yookassa_webhook_received", "online_refund_polled_settled"
    ],
    chain_root_event_payload_kwargs: dict[str, Any] | None = None,
) -> None:
    """Phase 51 D-51-18 shared settle UoW (D-51-11 steps 3d-3i).

    Sequence:
      1. Re-load OnlineRefund row by id (defensive — caller should have just
         SELECT-FOR-UPDATE'd it; missing here is a programming error).
      2. ``mark_succeeded(row, succeeded_at=now(UTC))`` — pure attribute mutator.
      3. Load parent OnlinePayment; derive ``subject_kind`` from the XOR'd plan
         FK columns (D-51-11; the 0034 CHECK guarantees exactly one is non-None).
      4. Load the ORIGINAL sale-side Payment row (online_refunds.original_payment_id
         FK) to derive ``subject_id`` for the PaymentRefunder Protocol call —
         that subject_id is the activated Membership/PtPackage row id (NOT the
         plan id). The activator (Phase 50 D-50-22) creates the Membership/PtPackage
         row and the in-memory subject_id is recorded on the original Payment.
      5. PaymentRefunder Protocol call (Phase 32 D-32-14). The registered
         implementation (``payments.service.issue_refund``) catches IntegrityError
         on ``uq_payments_refund_of_alive`` internally, rolls back the failed
         flush, and re-raises ``AlreadyRefundedError``. The helper does NOT catch
         either — both bubble to the caller (D-51-18 boundary pinned per checker
         review iteration 1).
      6. Direct subject transition (Errata #4 — NOT activator):
         ``update_membership_status`` or ``update_pt_package_status`` with the
         ``CANCELLATION_REASON_REFUNDED`` sentinel.
      7. Narrow scalar SELECT of ``clients.email`` (mirrors handlers.py
         ``_read_customer_email`` — Phase 50 Blocker #4). The fiscal_receipts row
         carries it for ЮKassa 54-ФЗ delivery.
      8. INSERT fiscal_receipts(kind='refund', status='sent',
         audit_correlation_id=chain_root_corr).
      9. Emit child audits: ``online_payment_refunded`` + subject_refunded_event
         (``membership_refunded`` OR ``pt_package_refunded``).
     10. Emit chain-root audit with the supplied ``chain_root_event`` and merge
         ``chain_root_event_payload_kwargs`` into the payload.

    Does NOT call ``session.commit()`` — caller owns the txn boundary.
    Does NOT catch IntegrityError / AlreadyRefundedError on the PaymentRefunder
    partial-UNIQUE conflict — caller catches and records its own audit outcome.
    """
    # Step 1: defensive re-load.
    row = await refund_repo.get_online_refund_by_id(session, online_refund_id)
    if row is None:
        raise RuntimeError(
            f"OnlineRefund {online_refund_id} not found at settle time — "
            "caller should have SELECT-FOR-UPDATE'd it just before delegating"
        )

    # Step 2: mark succeeded (pure attribute mutator).
    refund_repo.mark_succeeded(row, succeeded_at=datetime.now(UTC))

    # Step 3: load parent OnlinePayment and derive subject_kind from XOR'd FKs.
    op = await session.get(OnlinePayment, row.online_payment_id)
    if op is None:
        raise RuntimeError(
            f"OnlinePayment {row.online_payment_id} missing — FK RESTRICT violated"
        )
    if op.membership_plan_id is not None:
        subject_kind = SUBJECT_KIND_MEMBERSHIP
    elif op.pt_package_plan_id is not None:
        subject_kind = SUBJECT_KIND_PT_PACKAGE
    else:  # pragma: no cover — 0034 CHECK exactly_one_subject_fk guarantees XOR
        raise RuntimeError(
            f"OnlinePayment {op.id} has neither membership_plan_id nor "
            "pt_package_plan_id — DB CHECK constraint violated"
        )

    # Step 4: load ORIGINAL sale-side Payment to read its subject_id (used as
    # the PaymentRefunder lookup key — refunder filters
    # ``Payment WHERE subject_kind=:k AND subject_id=:id AND amount > 0``).
    # Phase 50 webhook records ``subject_id = membership_plan_id`` (the PLAN
    # id, not the activated instance id) so the PaymentRefunder lookup matches.
    original_payment = await session.get(Payment, row.original_payment_id)
    if original_payment is None:
        raise RuntimeError(
            f"original Payment {row.original_payment_id} missing — FK RESTRICT violated"
        )
    subject_id: UUID = original_payment.subject_id

    # Step 5: PaymentRefunder Protocol call (Phase 32 D-32-14). Errors bubble.
    refund_payment = await get_payment_refunder()(
        session,
        subject_kind=subject_kind,
        subject_id=subject_id,
        refund_user_id=row.requested_by_user_id,
        reason=row.reason or "online_refund",
        audit_actor=None,  # type: ignore[arg-type]
    )

    # Step 6: direct subject transition (Errata #4 — NOT activator). The
    # activated Membership / PtPackage row is looked up via (client_id, plan_id)
    # — the Phase 50 activator stores ``plan_id`` on the row but does NOT carve
    # an FK from the instance back to OnlinePayment. The OnlinePayment carries
    # both client_id and ``{membership,pt_package}_plan_id``, so the pair is
    # the canonical join key. Only one ALIVE instance per (client_id, plan_id)
    # should exist at a given moment (Phase 32 D-32-08 + Membership FSM
    # discipline); we filter active/exhausted rows to skip already-cancelled
    # historical rows on the same plan.
    if subject_kind == SUBJECT_KIND_MEMBERSHIP:
        membership_stmt = select(Membership).where(
            Membership.client_id == op.client_id,
            Membership.plan_id == op.membership_plan_id,
            Membership.status.in_(("active", "frozen", "expired")),
        )
        membership = await session.scalar(membership_stmt)
        if membership is None:
            raise RuntimeError(
                f"no live Membership for client={op.client_id} plan={op.membership_plan_id}"
            )
        await memberships_repo.update_membership_status(
            session,
            membership,
            status="cancelled",
            cancelled_at=datetime.now(UTC),
        )
        # `update_membership_status` exposes a `cancel_reason` kwarg that maps to
        # a DIFFERENT column (`Membership.cancel_reason` does not exist; see
        # repository.py:374 — the kwarg writes to `membership.cancel_reason`
        # which is a no-op attribute on the ORM). The canonical refund pattern
        # (memberships.service.refund_membership:965) sets
        # `membership.cancellation_reason` directly — mirror that here.
        membership.cancellation_reason = CANCELLATION_REASON_REFUNDED
        subject_refunded_event: Literal[
            "membership_refunded", "pt_package_refunded"
        ] = "membership_refunded"
        subject_resource_type: Literal["membership", "pt_package"] = "membership"
        subject_resource_id: UUID = membership.id
        subject_client_id: UUID = membership.client_id
    else:
        pt_package_stmt = select(PtPackage).where(
            PtPackage.client_id == op.client_id,
            PtPackage.plan_id == op.pt_package_plan_id,
            PtPackage.status.in_(("active", "exhausted", "expired")),
        )
        pt_package = await session.scalar(pt_package_stmt)
        if pt_package is None:
            raise RuntimeError(
                f"no live PtPackage for client={op.client_id} plan={op.pt_package_plan_id}"
            )
        await pt_packages_repo.update_pt_package_status(
            session,
            pt_package,
            status="cancelled",
            cancellation_reason=PT_CANCELLATION_REASON_REFUNDED,
        )
        subject_refunded_event = "pt_package_refunded"
        subject_resource_type = "pt_package"
        subject_resource_id = pt_package.id
        subject_client_id = pt_package.client_id

    # Step 7: narrow scalar SELECT of clients.email (Phase 50 Blocker #4 mirror).
    # MUST NOT log this value to structlog (T-51-07-07).
    customer_email = await session.scalar(
        select(Client.email).where(Client.id == row.client_id)
    )
    if customer_email is None:
        raise RuntimeError(
            f"Client {row.client_id} has no email at refund settle time"
        )

    # Step 8: INSERT fiscal_receipts(kind='refund', status='sent').
    fr_row = await insert_fiscal_receipt(
        session,
        payment_id=refund_payment.id,
        kind=KIND_REFUND,
        status=STATUS_SENT,
        customer_email=customer_email,
        audit_correlation_id=chain_root_corr,
        sent_at=datetime.now(UTC),
    )

    # Flush so the new IDs (refund_payment.id, fr_row.id) are populated for
    # downstream audit-payload kwargs (mirror activate_membership_from_webhook
    # line 1912 discipline).
    await session.flush()

    # Step 9: child audits. UUIDs str-cast for JSONB-serialisability
    # (Phase 32-02 deviation #1 lesson — raw UUID fails JSON encoder).

    # 9a — online_payment_refunded (carries audit_correlation_id from chain root).
    await audit.emit(
        session,
        "online_payment_refunded",
        actor_user_id=None,  # system emit (D-41-10 / INFRA-39)
        resource_type="online_payment",
        resource_id=op.id,
        audit_correlation_id=str(chain_root_corr),
        online_payment_id=str(op.id),
        refund_payment_id=str(refund_payment.id),
        amount_kopecks=refund_payment.amount_kopecks,
    )

    # 9b — subject_refunded (membership_refunded or pt_package_refunded). The
    # locked payload schema does NOT include audit_correlation_id (REF-07
    # baseline — mirrors memberships.service.refund_membership:974-984).
    await audit.emit(
        session,
        subject_refunded_event,
        actor_user_id=None,
        resource_type=subject_resource_type,
        resource_id=subject_resource_id,
        **{
            ("membership_id" if subject_kind == SUBJECT_KIND_MEMBERSHIP else "pt_package_id"): str(
                subject_resource_id
            ),
            "client_id": str(subject_client_id),
            "refund_payment_id": str(refund_payment.id),
            "reason": row.reason or "online_refund",
        },
    )

    # Step 10: chain-root audit. The caller picks the event label; merge any
    # extra kwargs the caller wants surfaced (e.g. event_type / object_id /
    # idempotency_outcome for the webhook chain root). Fiscal-receipt-id is
    # captured here for chain inspection but lives only in structlog (the
    # YookassaWebhookReceivedPayload schema does not include it).
    extra_kwargs = chain_root_event_payload_kwargs or {}

    if chain_root_event == "yookassa_webhook_received":
        await audit.emit(
            session,
            "yookassa_webhook_received",
            actor_user_id=None,
            resource_type="yookassa_webhook",
            resource_id=op.id,
            audit_correlation_id=None,  # this row IS the chain root
            **extra_kwargs,
        )
    else:
        # online_refund_polled_settled chain root (plan 51-09 cron path).
        await audit.emit(
            session,
            "online_refund_polled_settled",
            actor_user_id=None,
            resource_type="online_refund",
            resource_id=row.id,
            audit_correlation_id=str(chain_root_corr),
            online_refund_id=str(row.id),
            yookassa_refund_id=row.yookassa_refund_id,
            settled_at=datetime.now(UTC),
            **extra_kwargs,
        )

    _log.info(
        "online_refund_settled",
        online_refund_id=str(row.id),
        subject_kind=subject_kind,
        fiscal_receipt_id=str(fr_row.id),
        refund_payment_id=str(refund_payment.id),
    )


__all__ = ("_settle_online_refund",)
