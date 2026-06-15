"""Payments router — GET endpoints + POST refund (Phase 32 PAY-06..08 / Phase 112 REF-01).

Endpoint surface:
  - GET /api/v1/payments               — global list, owner-only (VIEW, PAYMENTS).
  - GET /api/v1/payments/by-client/{id}     — reception+owner via scoped Depends.
  - GET /api/v1/payments/by-membership/{id} — reception+owner via scoped Depends.
  - POST /api/v1/payments/{payment_id}/refund — owner-only manual ledger refund (REF-01).

Permission mapping:
  - GET / (global) uses ``require_permission(Action.VIEW, Resource.PAYMENTS)`` →
    ``(VIEW, PAYMENTS)`` is in ``OWNER_ONLY``, so reception receives 403.
  - Scoped routes use ``require_payments_view_for_subject()`` which admits
    both owner and reception (PAY-07 — reception needs visibility on detail
    pages).
  - POST /{id}/refund uses ``require_permission(Action.REFUND, Resource.FINANCE)`` +
    ``verify_csrf``; ``(REFUND, FINANCE)`` is in ``OWNER_ONLY`` → reception 403.

All GET routes return ``ResponseEnvelope[PaginatedData[PaymentResponse]]``.
POST /refund returns ``ResponseEnvelope[PaymentResponse]`` (201 new ledger row).
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import CurrentUser, require_permission, verify_csrf
from app.core.pagination import PaginatedData
from app.core.permissions import Action, Resource
from app.core.schemas import ResponseEnvelope, envelope
from app.modules.payments import repository
from app.modules.payments import service as payments_service
from app.modules.payments.permissions import require_payments_view_for_subject
from app.modules.payments.schemas import PaymentListQuery, PaymentRefundRequest, PaymentResponse

router = APIRouter(tags=["Payments"])


@router.get(
    "",
    response_model=ResponseEnvelope[PaginatedData[PaymentResponse]],
    summary="List payments globally (owner-only; filters by subject + actor + date window)",
)
async def list_payments(
    query: Annotated[PaymentListQuery, Depends()],
    _actor: Annotated[CurrentUser, Depends(require_permission(Action.VIEW, Resource.PAYMENTS))],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ResponseEnvelope[PaginatedData[PaymentResponse]]:
    """List payments globally with filter parity (Phase 32 PAY-06).

    Owner-only because ``(VIEW, PAYMENTS)`` is in ``OWNER_ONLY``. Reception
    on the global route receives 403 — they use the scoped ``/by-client`` and
    ``/by-membership`` routes instead.
    """
    page = await repository.list_payments_filtered(session, query)
    return envelope(page)


@router.get(
    "/by-client/{client_id}",
    response_model=ResponseEnvelope[PaginatedData[PaymentResponse]],
    summary="List payments tied to a client's memberships (reception+owner; PAY-07)",
)
async def list_payments_by_client(
    client_id: UUID,
    _actor: Annotated[CurrentUser, Depends(require_payments_view_for_subject())],
    session: Annotated[AsyncSession, Depends(get_db)],
    page: int = 1,
    page_size: int = 50,
) -> ResponseEnvelope[PaginatedData[PaymentResponse]]:
    """List payments scoped to a client (Phase 32 PAY-07).

    Reception is admitted because the client detail page (Phase 35 UI) needs
    the customer's payment history. Includes refund rows whose
    ``refund_of`` references this client's membership sales.
    """
    page_data = await repository.list_payments_for_client(
        session, client_id, page=page, page_size=page_size
    )
    return envelope(page_data)


@router.get(
    "/by-membership/{membership_id}",
    response_model=ResponseEnvelope[PaginatedData[PaymentResponse]],
    summary="List payments tied to a single membership (reception+owner; PAY-07)",
)
async def list_payments_by_membership(
    membership_id: UUID,
    _actor: Annotated[CurrentUser, Depends(require_payments_view_for_subject())],
    session: Annotated[AsyncSession, Depends(get_db)],
    page: int = 1,
    page_size: int = 50,
) -> ResponseEnvelope[PaginatedData[PaymentResponse]]:
    """List payments scoped to a single membership (Phase 32 PAY-07).

    Returns the sale row plus the refund row (if any) for the same
    membership.
    """
    page_data = await repository.list_payments_for_membership(
        session, membership_id, page=page, page_size=page_size
    )
    return envelope(page_data)


@router.post(
    "/{payment_id}/refund",
    status_code=status.HTTP_201_CREATED,
    response_model=ResponseEnvelope[PaymentResponse],
    summary="Issue a manual ledger refund for any recorded payment (owner-only; REF-01)",
)
async def refund_payment_endpoint(
    payment_id: UUID,
    payload: PaymentRefundRequest,
    actor: Annotated[CurrentUser, Depends(require_permission(Action.REFUND, Resource.FINANCE))],
    _csrf: Annotated[None, Depends(verify_csrf)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ResponseEnvelope[PaymentResponse]:
    """REF-01 / Phase 112 — owner-only; RBAC-04: require_permission before verify_csrf.

    Posts a negative-amount refund row for any recorded non-refund payment.
    Partial refunds (amount_kopecks <= original) are accepted; over-refunds
    (amount_kopecks > original) return 409 over_refund. A second refund of
    the same original returns 409 already_refunded (unique-constraint). Trying
    to refund a refund row returns 409 cannot_refund_refund. Missing payment
    returns 404 original_payment_not_found.
    """
    refund = await payments_service.refund_arbitrary_payment(
        session,
        payment_id=payment_id,
        amount_kopecks=payload.amount_kopecks,
        reason=payload.reason,
        audit_actor=actor,
    )
    return envelope(PaymentResponse.model_validate(refund))
