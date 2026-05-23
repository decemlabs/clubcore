"""Payments service — caller-owns-txn record_payment + issue_refund (Phase 32 PAY-03..05 / D-32-10).

Both functions are PUBLIC Protocol-slot consumers (wired from
``app.main.create_app`` via ``register_payment_recorder`` /
``register_payment_refunder``). They INTENTIONALLY do NOT call
``session.commit()`` — the sale-flow / refund-flow orchestrator (in
``memberships.service``) owns the UoW so the audit row + payment row +
membership status transition co-write atomically.

The ``# noqa: SVC001 caller-owns-txn`` marker tells the AST commit-gate
walker (``tests/unit/test_service_commit_gate.py``) that this delegation is
intentional. Phase 32 D-32-10 extends the walker to accept the marker on
public Protocol-slot functions in addition to private helpers.

Append-only invariant (B-01 INFRA-22): the only mutations against the
``Payment`` ORM in this module are ``session.add(...)`` via repository
``insert_payment``. NO ``update(Payment)``, NO ``delete(Payment)``,
NO ``on_conflict_do_update``.

Audit payloads (D-30-03 / D-30-04):
  - payment_recorded → PaymentRecordedPayload (7 fields incl. payment_row_hash).
  - refund_issued → RefundIssuedPayload (8 fields incl. payment_row_hash of
    ORIGINAL sale row + refund_of_payment_id pointing at the sale row id).
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import audit
from app.core.audit_hash import payment_row_hash
from app.core.dependencies import CurrentUser
from app.core.exceptions import ConflictError, NotFoundError
from app.modules.payments import repository
from app.modules.payments.constants import (
    SUBJECT_KIND_MEMBERSHIP,
    SUBJECT_KIND_PT_PACKAGE,
    SUBJECT_KIND_REFUND,
)
from app.modules.payments.models import Payment


class OriginalPaymentNotFoundError(NotFoundError):
    """No original sale row exists for the given subject (Phase 32 REF-02).

    Raised by ``issue_refund`` when the membership being refunded has no
    recorded sale payment (legacy pre-Phase 32 row). Mapped to 404 via the
    AppError handler; the operator UI surfaces this as "no sale on record".
    """

    code = "original_payment_not_found"
    status_code = 404


class AlreadyRefundedError(ConflictError):
    """Original sale row already has a refund row (Phase 32 REF-02).

    Raised when the partial UNIQUE ``uq_payments_refund_of_alive`` rejects
    a concurrent / repeat refund insert. Discriminated against
    ``IntegrityError`` via ``repository._is_refund_of_uniqueness_conflict``.
    """

    code = "already_refunded"
    status_code = 409


def _payment_row_dict(payment: Payment) -> dict[str, object]:
    """Stable 8-column projection used to compute ``payment_row_hash`` (D-32-23).

    Mirrors the natural-key column set: id + subject_kind + subject_id +
    amount_kopecks + method + received_at + received_by_user_id + refund_of.
    ``audit_log_id`` is intentionally OMITTED — it is mutated post-INSERT when
    the audit row latches on, so including it would defeat determinism.

    Phase 50 Plan 50-03 / Blocker #2 — ``received_by_user_id`` may be NULL
    for ЮKassa-webhook-originated rows; the hash still includes the field
    (None hashes deterministically just like any other value).
    """
    return {
        "id": payment.id,
        "subject_kind": payment.subject_kind,
        "subject_id": payment.subject_id,
        "amount_kopecks": payment.amount_kopecks,
        "method": payment.method,
        "received_at": payment.received_at,
        "received_by_user_id": payment.received_by_user_id,
        "refund_of": payment.refund_of,
    }


async def record_payment(  # noqa: SVC001 caller-owns-txn — sale orchestrator owns UoW
    session: AsyncSession,
    *,
    subject_kind: str,
    subject_id: UUID,
    amount_kopecks: int,
    method: str = "cash",
    received_by_user_id: UUID | None = None,  # Phase 50 Plan 50-03 Blocker #2
    audit_actor: CurrentUser | None = None,  # Phase 50 Plan 50-03 Blocker #2
) -> Payment:
    """Append a sale-side Payment row (Phase 32 PAY-03..05).

    Order: INSERT via repository → flush (surface FK + CHECK conflicts) →
    compute row hash → emit ``payment_recorded`` audit event with the
    PaymentRecordedPayload. The CALLER (sale-flow orchestrator in
    ``memberships.service.create_membership``) owns the commit.

    Phase 50 Plan 50-03 / Blocker #2 — ``audit_actor`` and
    ``received_by_user_id`` are widened to Optional. The ЮKassa webhook
    flow (Plan 50-04) is anonymous; the recorder is invoked with both as
    ``None``. Body handles both None branches:
      - ``received_by_user_id=None`` is passed straight through to the
        ledger row (Alembic 0036 made the column nullable).
      - ``audit_actor=None`` causes the ``payment_recorded`` audit row to
        be a SYSTEM EMIT (``actor_user_id=None`` per D-41-10 / INFRA-39).
      - Audit payload ``received_by_user_id`` is emitted as None when
        no operator UUID is present; ``PaymentRecordedPayload`` accepts
        ``UUID | None`` after Plan 50-03 widening.
    Existing in-person sale callers continue to pass non-None values for
    BOTH kwargs and exercise the same code path with no behavior change.
    """
    payment = await repository.insert_payment(
        session,
        subject_kind=subject_kind,
        subject_id=subject_id,
        amount_kopecks=amount_kopecks,
        method=method,
        received_by_user_id=received_by_user_id,
        refund_of=None,
    )
    # Flush to surface FK / CHECK violations before audit emit.
    await session.flush()

    row_hash = payment_row_hash(_payment_row_dict(payment))

    # UUIDs in **payload kwargs land in JSONB unaltered; the JSON encoder
    # rejects raw `UUID` instances ("Object of type UUID is not JSON
    # serializable"). Cast to str so Postgres JSONB roundtrips cleanly.
    # Pydantic UUID fields accept both UUID and well-formed str on
    # validation, so PaymentRecordedPayload still passes.
    #
    # Phase 50 Plan 50-03 / Blocker #2 — guard the audit_actor.id and the
    # str(received_by_user_id) accesses; either may be None for the
    # webhook flow. The audit emit becomes a SYSTEM EMIT
    # (actor_user_id=None) when no operator is present.
    await audit.emit(
        session,
        "payment_recorded",
        actor_user_id=audit_actor.id if audit_actor is not None else None,
        resource_type="payment",
        resource_id=payment.id,
        payment_id=str(payment.id),
        subject_kind=subject_kind,
        subject_id=str(subject_id),
        amount_kopecks=amount_kopecks,
        method=method,
        received_by_user_id=(
            str(received_by_user_id) if received_by_user_id is not None else None
        ),
        payment_row_hash=row_hash,
    )
    return payment


async def issue_refund(  # noqa: SVC001 caller-owns-txn — refund orchestrator owns UoW
    session: AsyncSession,
    *,
    subject_kind: str,
    subject_id: UUID,
    refund_user_id: UUID,
    reason: str,
    audit_actor: CurrentUser | None,
) -> Payment:
    """Append a refund-side (negative-amount) Payment row (Phase 32 REF-02..04).

    Internally loads the ORIGINAL sale-side payment via
    ``repository.get_original_membership_payment`` /
    ``repository.get_original_pt_package_payment`` (D-32-14 — refunder takes
    subject_kind/subject_id, NOT original_payment_id, so cross-module callers
    never import ``payments.repository``). Inserts a negative-amount row with
    ``subject_kind='refund'`` and ``refund_of=original.id``; the partial
    UNIQUE ``uq_payments_refund_of_alive`` enforces at-most-one refund per
    sale. Caller owns the commit.

    Phase 33 extends ``subject_kind`` support to 'pt_package' (REF-02 / PT-13)
    — replaces the Phase 32 NotImplementedError gate. Future kinds raise
    NotImplementedError.
    """
    if subject_kind == SUBJECT_KIND_MEMBERSHIP:
        original = await repository.get_original_membership_payment(session, subject_id)
    elif subject_kind == SUBJECT_KIND_PT_PACKAGE:
        original = await repository.get_original_pt_package_payment(session, subject_id)
    else:
        raise NotImplementedError(
            f"refund subject_kind={subject_kind!r} not supported"
        )

    if original is None:
        raise OriginalPaymentNotFoundError("original_payment_not_found")

    original_hash = payment_row_hash(_payment_row_dict(original))

    refund_payment = await repository.insert_payment(
        session,
        subject_kind=SUBJECT_KIND_REFUND,
        subject_id=subject_id,
        amount_kopecks=-original.amount_kopecks,
        method=original.method,
        received_by_user_id=refund_user_id,
        refund_of=original.id,
    )
    try:
        await session.flush()
    except IntegrityError as exc:
        await session.rollback()
        if repository._is_refund_of_uniqueness_conflict(exc):
            raise AlreadyRefundedError("already_refunded") from exc
        raise

    # `subject_kind` field of RefundIssuedPayload constrains to
    # ('membership','pt_package') — pass the ORIGINAL's kind, not 'refund'.
    # Cast UUID kwargs to str — JSONB encoder rejects raw UUIDs (see
    # record_payment above); Pydantic UUID fields still accept str input.
    await audit.emit(
        session,
        "refund_issued",
        # Phase 51 Plan 51-07 — webhook-driven refund settlement passes
        # audit_actor=None (anonymous flow, mirrors Plan 50-03 Blocker #2
        # widening of record_payment).
        actor_user_id=audit_actor.id if audit_actor is not None else None,
        resource_type="payment",
        resource_id=refund_payment.id,
        payment_id=str(refund_payment.id),
        refund_of_payment_id=str(original.id),
        amount_kopecks=refund_payment.amount_kopecks,
        subject_kind=original.subject_kind,
        subject_id=str(subject_id),
        received_by_user_id=str(refund_user_id),
        reason=reason,
        payment_row_hash=original_hash,
    )
    return refund_payment


__all__ = (
    "AlreadyRefundedError",
    "OriginalPaymentNotFoundError",
    "issue_refund",
    "record_payment",
)
