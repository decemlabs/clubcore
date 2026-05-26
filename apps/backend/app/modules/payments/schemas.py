"""Payments module DTOs (Phase 32 PAY-06..08 + REF-05).

PaymentListQuery — extends PageQuery for global + scoped list endpoints.
PaymentResponse — outbound shape via ResponseEnvelope[PaginatedData[T]].
MembershipRefundRequest — body for POST /memberships/{id}/refund (REF-05).

`extra='forbid'` is inherited via BackendSchemaBase — no override required
(PATTERNS.md §7). Backend rejects ``amountKopecks`` (server derives amount
from snapshot per REF-05) because the field is undeclared.
"""

from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from pydantic import Field

from app.core.pagination import PageQuery
from app.core.schemas import BackendSchemaBase, ResponseData


class PaymentListQuery(PageQuery):
    """GET /api/v1/payments query parameters (Phase 32 PAY-06).

    Filters (all optional, AND-combined):
      - ``subject_kind`` — 'membership' | 'pt_package' | 'refund'.
      - ``subject_id`` — exact UUID match on the referenced row.
      - ``received_by_user_id`` — operator who recorded the payment.
      - ``received_from`` / ``received_to`` — half-open date window in
        Europe/Moscow; inclusive on both ends (received_to → start of next day).

    Wire form: ``?subjectKind=membership&receivedFrom=2026-05-01`` etc.
    """

    subject_kind: str | None = Field(default=None, pattern=r"^(membership|pt_package|refund)$")
    subject_id: UUID | None = None
    received_by_user_id: UUID | None = None
    received_from: date | None = None
    received_to: date | None = None


class PaymentResponse(ResponseData):
    """Outbound representation of a Payment ledger row (Phase 32 PAY-08).

    Mirrors the 9 DB columns minus implementation details (audit_log_id is
    surfaced for forensic UI but `id` carries the same operational weight).
    """

    id: UUID
    subject_kind: str
    subject_id: UUID
    amount_kopecks: int
    method: str
    received_at: datetime
    received_by_user_id: UUID
    refund_of: UUID | None = None
    audit_log_id: UUID | None = None


class MembershipRefundRequest(BackendSchemaBase):
    """POST /api/v1/memberships/{id}/refund body (Phase 32 REF-05/REF-06).

    ``reason`` is REQUIRED (REF-06 — non-empty 1..200 chars). Backend rejects
    extra keys including ``amountKopecks`` because BackendSchemaBase sets
    ``extra='forbid'`` (REF-05 server-derives-amount invariant).
    """

    reason: str = Field(
        min_length=1,
        max_length=200,
        description=(
            "Refund reason (REF-06). Backend rejects extra fields including amountKopecks (REF-05)."
        ),
    )
