"""Online refunds service — initiate orchestrator (Phase 51 REFUND-01 / D-51-08/09).

ORDER OF OPERATIONS (D-51-08 / D-51-09):

  1. Idempotency-Key replay check (D-51-Discretion). If a row with this caller-
     supplied idempotency_key already exists, return its data 202-style without
     re-running guards or hitting ЮKassa. (No second audit emit, no second
     INSERT, no second create_refund call.)

  2. Specific-first guards (D-32-11 lineage; verbatim mirror of
     memberships/service.py:refund_membership and pt_packages/service.py:
     refund_pt_package):

       a. Load the subject row (Membership XOR PtPackage).
          → 404 membership_not_found / pt_package_not_found if missing.
       b. For memberships only: status='frozen' → 409 must_unfreeze_first (B-08).
       c. For memberships only: repository.has_renewal_descendants → 409
          cannot_refund_renewed_source (B-09).
       d. _assert_refund_can_transition(subject_row, target='cancelled') —
          refund-local FSM gate that consults the appropriate
          STATUS_TRANSITIONS constant. Raises InvalidTransitionError.
       e. Locate the original OnlinePayment row for this client + plan
          (status='succeeded'). → 404 online_payment_not_found.
       f. Locate the original Payment ledger row created by the Phase 50
          webhook handler (subject_kind, subject_id=membership_plan_id|
          pt_package_plan_id, method='online'). → 404 original_payment_not_found.

  3. D-51-09 call-then-INSERT:

       a. await yookassa_client.create_refund(payment_id, amount, idempotency_key).
       b. Classification mapping (mirror online_payments/service.py:331-342):
            ok                → continue
            validation_error  → raise ValidationAppError(YOOKASSA_VALIDATION_ERROR)
            transient_error   → raise ServiceUnavailableAppError(YOOKASSA_UNAVAILABLE)
            permanent_error   → raise BadGatewayAppError(YOOKASSA_PERMANENT_ERROR)
       c. INSERT online_refunds(status='pending', yookassa_refund_id, …) via
          refund_repo.insert_online_refund (caller-owns-txn).
       d. flush() — surface uq_online_refunds_alive_per_online_payment partial
          UNIQUE conflict on concurrent operator double-tap that slipped past
          the step-1 replay check. Translate IntegrityError → 409
          refund_already_in_flight (mirrors Phase 25 D-25-22 freeze-race
          discriminator).
       e. audit.emit("online_refund_initiated", …) inside the same UoW
          (D-04 / D-14 co-transactional). audit_correlation_id is a FRESH
          uuid4 (chain ROOT — D-51-09); downstream poll-cron events chain
          back via this UUID.

  4. session.commit() — orchestrator owns the txn per
     core/services.py SVC001 invariant.

  5. Return OnlineRefundResponse(status='pending', …).

D-51-09 trade-off (call-then-INSERT, accepted): on classification != 'ok' no
DB rows are written. If the INSERT in step 3c fails AFTER ЮKassa created the
refund, the orphan is reconciled by the poll_pending_refunds cron (plan 51-09)
via the uq_online_refunds_yookassa_refund_id UNIQUE backstop on retry.

Cross-module imports notes (modules-independent contract — see
``apps/backend/.importlinter``):

  - ``online_refunds`` is NOT listed in the modules-independent contract at
    Phase 51 (the contract block enumerates 14 modules; online_refunds is the
    15th sibling and is intentionally left out). Cross-imports from this file
    to memberships / pt_packages / online_payments / payments / clients are
    therefore unconstrained by the contract.
  - However: the refund-local FSM helper (``_assert_refund_can_transition``)
    is preferred over importing the underscore-private ``_assert_can_transition``
    from memberships/service.py or pt_packages/service.py — underscore-private
    cross-module imports are forbidden by convention even when not enforced.
  - The two public guard exceptions (MustUnfreezeFirstError,
    CannotRefundRenewedSourceError) ARE imported from memberships.service —
    they are public top-level classes (memberships/service.py:180,194) and
    re-implementing them locally would diverge the wire ``code`` literals.
"""

from __future__ import annotations

from uuid import UUID, uuid4

import structlog
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import audit
from app.core.audit_payloads import OnlineRefundInitiatedPayload
from app.core.dependencies import CurrentUser
from app.core.exceptions import (
    BadGatewayAppError,
    ConflictError,
    NotFoundError,
    ServiceUnavailableAppError,
    ValidationAppError,
)
from app.integrations.yookassa.client import YooKassaClient
from app.modules.memberships.constants import MEMBERSHIP_STATUS_TRANSITIONS
from app.modules.memberships.models import Membership
from app.modules.memberships.repository import has_renewal_descendants
from app.modules.memberships.service import (
    CannotRefundRenewedSourceError,
    MustUnfreezeFirstError,
)
from app.modules.online_payments.models import OnlinePayment
from app.modules.online_refunds import repository as refund_repo
from app.modules.online_refunds.constants import STATUS_PENDING, ErrorCode
from app.modules.online_refunds.schemas import OnlineRefundResponse
from app.modules.payments.constants import (
    SUBJECT_KIND_MEMBERSHIP,
    SUBJECT_KIND_PT_PACKAGE,
)
from app.modules.payments.models import Payment
from app.modules.pt_packages.constants import PT_PACKAGE_STATUS_TRANSITIONS
from app.modules.pt_packages.models import PtPackage

_log = structlog.get_logger("modules.online_refunds.service")


class InvalidTransitionError(ConflictError):
    """Refund-local FSM gate violation (mirrors memberships /pt_packages
    InvalidTransitionError shape; lives in this module so the cross-module
    underscore-private ``_assert_can_transition`` is not imported)."""

    code = "invalid_transition"
    status_code = 409


class RefundAlreadyInFlightError(ConflictError):
    """Raised when the ``uq_online_refunds_alive_per_online_payment`` partial
    UNIQUE backstop trips — a concurrent operator double-tap that slipped past
    the step-1 idempotency-key replay check (threat T-51-08-05 mitigation)."""

    code = "refund_already_in_flight"
    status_code = 409


def _assert_refund_can_transition_membership(membership: Membership) -> None:
    """Refund-local FSM gate (D-32-11 mirror) for memberships.

    Consults MEMBERSHIP_STATUS_TRANSITIONS to decide whether membership.status
    → 'cancelled' is allowed; raises InvalidTransitionError otherwise.
    """
    allowed = MEMBERSHIP_STATUS_TRANSITIONS.get(membership.status, frozenset())
    if "cancelled" not in allowed:
        raise InvalidTransitionError(
            "invalid_transition",
            fields={"from_status": membership.status, "to_status": "cancelled"},
        )


def _assert_refund_can_transition_pt_package(pt_package: PtPackage) -> None:
    """Refund-local FSM gate (D-33-04 mirror) for pt_packages."""
    allowed = PT_PACKAGE_STATUS_TRANSITIONS.get(pt_package.status, frozenset())
    if "cancelled" not in allowed:
        raise InvalidTransitionError(
            "invalid_transition",
            fields={"from_status": pt_package.status, "to_status": "cancelled"},
        )


def _is_alive_per_online_payment_conflict(exc: IntegrityError) -> bool:
    """Discriminator for the ``uq_online_refunds_alive_per_online_payment``
    partial UNIQUE backstop. Mirror of Phase 25 D-25-22 freeze-race shape.
    """
    constraint = getattr(exc.orig, "constraint_name", None) or ""
    if constraint == "uq_online_refunds_alive_per_online_payment":
        return True
    return "uq_online_refunds_alive_per_online_payment" in str(exc.orig)


async def _find_succeeded_online_payment_for_membership(
    session: AsyncSession, *, client_id: UUID, membership_plan_id: UUID
) -> OnlinePayment | None:
    """Locate the most recent succeeded OnlinePayment for this client + plan.

    The D-49-04 XOR shape means a membership-flow OnlinePayment row carries
    a non-NULL ``membership_plan_id`` and NULL ``pt_package_plan_id``.
    """
    stmt = (
        select(OnlinePayment)
        .where(
            OnlinePayment.client_id == client_id,
            OnlinePayment.membership_plan_id == membership_plan_id,
            OnlinePayment.status == "succeeded",
        )
        .order_by(OnlinePayment.succeeded_at.desc())
        .limit(1)
    )
    result: OnlinePayment | None = await session.scalar(stmt)
    return result


async def _find_succeeded_online_payment_for_pt_package(
    session: AsyncSession, *, client_id: UUID, pt_package_plan_id: UUID
) -> OnlinePayment | None:
    """Locate the most recent succeeded OnlinePayment for this client + plan."""
    stmt = (
        select(OnlinePayment)
        .where(
            OnlinePayment.client_id == client_id,
            OnlinePayment.pt_package_plan_id == pt_package_plan_id,
            OnlinePayment.status == "succeeded",
        )
        .order_by(OnlinePayment.succeeded_at.desc())
        .limit(1)
    )
    result: OnlinePayment | None = await session.scalar(stmt)
    return result


async def _find_original_online_payment_ledger_row(
    session: AsyncSession,
    *,
    subject_kind: str,
    plan_id: UUID,
) -> Payment | None:
    """Locate the original Payment ledger row created by the Phase 50 webhook.

    Phase 50 D-50-23 records online sale payments via the PaymentRecorder
    Protocol slot with ``subject_kind in {'membership','pt_package'}``,
    ``subject_id=membership_plan_id|pt_package_plan_id`` (per
    ``app/api/v1/_internal/yookassa/handlers.py:302-308``), and
    ``method='online'``. The sale row is positive-signed (refund_of IS NULL).
    """
    stmt = (
        select(Payment)
        .where(
            Payment.subject_kind == subject_kind,
            Payment.subject_id == plan_id,
            Payment.method == "online",
            Payment.refund_of.is_(None),
            Payment.amount_kopecks > 0,
        )
        .order_by(Payment.received_at.desc())
        .limit(1)
    )
    result: Payment | None = await session.scalar(stmt)
    return result


async def initiate_online_refund(
    session: AsyncSession,
    actor: CurrentUser,
    *,
    membership_id: UUID | None = None,
    pt_package_id: UUID | None = None,
    idempotency_key: UUID,
    reason: str | None,
    yookassa_client: YooKassaClient,
) -> OnlineRefundResponse:
    """Phase 51 REFUND-01 initiate orchestrator (D-51-08 / D-51-09).

    Caller passes EXACTLY ONE of membership_id or pt_package_id (router
    enforces this by splitting into two endpoints calling this with the
    correct kwarg). The other branch is defended via ValueError so a
    caller misuse surfaces loudly at runtime.

    Raises:
      NotFoundError — 404 membership_not_found / pt_package_not_found
        / online_payment_not_found / original_payment_not_found.
      MustUnfreezeFirstError — 409 must_unfreeze_first (B-08).
      CannotRefundRenewedSourceError — 409 cannot_refund_renewed_source (B-09).
      InvalidTransitionError — 409 invalid_transition (refund-local FSM gate).
      ValidationAppError — 422 yookassa_validation_error.
      ServiceUnavailableAppError — 503 yookassa_unavailable.
      BadGatewayAppError — 502 yookassa_permanent_error.
      RefundAlreadyInFlightError — 409 refund_already_in_flight (partial UNIQUE).

    Returns:
      OnlineRefundResponse(status='pending', online_refund_id, yookassa_refund_id).
    """
    # 0. Cross-XOR defensive guard (router enforces; this is a depth-in-defense).
    if (membership_id is None) == (pt_package_id is None):
        raise ValueError(
            "initiate_online_refund: exactly one of membership_id or pt_package_id must be set"
        )

    # 1. Idempotency-Key replay check (D-51-Discretion). Runs BEFORE step 2
    #    guards so a benign double-click does not pay the guard cost twice
    #    and does NOT re-emit audit.
    existing = await refund_repo.get_online_refund_by_idempotency_key(session, str(idempotency_key))
    if existing is not None:
        _log.info(
            "online_refund_initiate_replay",
            online_refund_id=str(existing.id),
            online_payment_id=str(existing.online_payment_id),
            actor_user_id=str(actor.id),
        )
        return OnlineRefundResponse(
            online_refund_id=existing.id,
            status=existing.status,
            yookassa_refund_id=existing.yookassa_refund_id,
        )

    # 2. Specific-first guards.
    subject_kind: str
    plan_id_for_lookup: UUID
    client_id: UUID

    if membership_id is not None:
        # 2a (membership): load.
        membership = await session.scalar(select(Membership).where(Membership.id == membership_id))
        if membership is None:
            raise NotFoundError("membership_not_found")

        # 2b: frozen guard — must fire BEFORE the FSM gate so the operator
        #     UI surfaces the specific actionable error (Phase 32 D-32-11).
        if membership.status == "frozen":
            raise MustUnfreezeFirstError("must_unfreeze_first")

        # 2c: renewed-source guard (B-09).
        if await has_renewal_descendants(session, membership_id):
            raise CannotRefundRenewedSourceError("cannot_refund_renewed_source")

        # 2d: refund-local FSM gate.
        _assert_refund_can_transition_membership(membership)

        # 2e: locate OnlinePayment row.
        op = await _find_succeeded_online_payment_for_membership(
            session,
            client_id=membership.client_id,
            membership_plan_id=membership.plan_id,
        )
        if op is None:
            raise NotFoundError("online_payment_not_found")

        subject_kind = SUBJECT_KIND_MEMBERSHIP
        plan_id_for_lookup = membership.plan_id
        client_id = membership.client_id
    else:
        assert pt_package_id is not None
        # 2a (pt_package): load.
        pt_package = await session.scalar(select(PtPackage).where(PtPackage.id == pt_package_id))
        if pt_package is None:
            raise NotFoundError("pt_package_not_found")

        # 2d: refund-local FSM gate (no must_unfreeze / renewed-source for
        #     pt_packages — no freeze concept and no renewal chain in v1.x).
        _assert_refund_can_transition_pt_package(pt_package)

        # 2e: locate OnlinePayment row.
        op = await _find_succeeded_online_payment_for_pt_package(
            session,
            client_id=pt_package.client_id,
            pt_package_plan_id=pt_package.plan_id,
        )
        if op is None:
            raise NotFoundError("online_payment_not_found")

        subject_kind = SUBJECT_KIND_PT_PACKAGE
        plan_id_for_lookup = pt_package.plan_id
        client_id = pt_package.client_id

    # 2f: locate the original Payment ledger row created by the Phase 50
    #     webhook handler (subject_kind + plan_id + method='online').
    original_payment = await _find_original_online_payment_ledger_row(
        session, subject_kind=subject_kind, plan_id=plan_id_for_lookup
    )
    if original_payment is None:
        raise NotFoundError("original_payment_not_found")

    # 3a. D-51-09 call-then-INSERT — call ЮKassa BEFORE the DB write.
    refund_amount = abs(original_payment.amount_kopecks)
    result = await yookassa_client.create_refund(
        payment_id=op.yookassa_payment_id,
        amount_kopecks=refund_amount,
        idempotency_key=idempotency_key,
    )

    # 3b. Classification mapping (mirror online_payments/service.py:331-342).
    if result.classification != "ok":
        _log.warning(
            "online_refund_initiate_yookassa_failure",
            classification=result.classification,
            error_code=result.error_code,
            online_payment_id=str(op.id),
            actor_user_id=str(actor.id),
        )
        if result.classification == "validation_error":
            raise ValidationAppError(ErrorCode.YOOKASSA_VALIDATION_ERROR.value)
        if result.classification == "transient_error":
            raise ServiceUnavailableAppError(ErrorCode.YOOKASSA_UNAVAILABLE.value)
        # permanent_error fallthrough.
        raise BadGatewayAppError(ErrorCode.YOOKASSA_PERMANENT_ERROR.value)

    assert result.refund_id is not None

    # 3c. INSERT OnlineRefund row inside the same UoW as the audit emit.
    correlation_id = uuid4()
    row = await refund_repo.insert_online_refund(
        session,
        online_payment_id=op.id,
        original_payment_id=original_payment.id,
        client_id=client_id,
        yookassa_refund_id=result.refund_id,
        idempotency_key=str(idempotency_key),
        amount_kopecks=refund_amount,
        status=STATUS_PENDING,
        requested_by_user_id=actor.id,
        reason=reason,
        audit_correlation_id=correlation_id,
    )
    # 3d. Surface partial UNIQUE on uq_online_refunds_alive_per_online_payment
    #     BEFORE audit emit (Phase 25 D-25-22 shape).
    try:
        await session.flush()
    except IntegrityError as exc:
        await session.rollback()
        if _is_alive_per_online_payment_conflict(exc):
            raise RefundAlreadyInFlightError("refund_already_in_flight") from exc
        raise

    # 3e. Audit emit — fresh chain ROOT (D-51-09). All UUID kwargs str-cast
    #     for JSONB-serialisability (Phase 32-02 deviation #1 lesson).
    initiated_payload = OnlineRefundInitiatedPayload(
        audit_correlation_id=correlation_id,
        online_refund_id=row.id,
        online_payment_id=op.id,
        original_payment_id=original_payment.id,
        amount_kopecks=row.amount_kopecks,
        requested_by_user_id=actor.id,
        reason=reason,
    )
    await audit.emit(
        session,
        "online_refund_initiated",  # LITERAL (Phase 15 INFRA-11 AST gate)
        actor_user_id=actor.id,
        resource_type="online_refund",  # LITERAL
        resource_id=row.id,
        **initiated_payload.model_dump(mode="json"),
    )

    # 4. Commit (SVC001 invariant — orchestrator owns the txn).
    await session.commit()

    _log.info(
        "online_refund_initiate_succeeded",
        online_refund_id=str(row.id),
        online_payment_id=str(op.id),
        actor_user_id=str(actor.id),
        amount_kopecks=refund_amount,
    )

    # 5. Return response.
    return OnlineRefundResponse(
        online_refund_id=row.id,
        status=STATUS_PENDING,
        yookassa_refund_id=result.refund_id,
    )


__all__ = (
    "InvalidTransitionError",
    "RefundAlreadyInFlightError",
    "initiate_online_refund",
)
