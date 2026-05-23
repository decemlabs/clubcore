"""Online refunds wire schemas (Phase 51 D-51-08 / D-48-11).

OnlineRefundRequest / OnlineRefundResponse for POST
``/api/v1/online-payments/.../refund``. Caller-owned ``idempotency_key`` per
D-48-11 (replay-check pattern). No confirmation_url / qr_payload XOR — refunds
have no user-redirect.
"""

from __future__ import annotations

from uuid import UUID

from app.core.schemas import BackendSchemaBase, ResponseData


class OnlineRefundRequest(BackendSchemaBase):
    """POST /api/v1/online-payments/{id}/refund body (Phase 51 REFUND-01)."""

    idempotency_key: UUID
    reason: str | None = None


class OnlineRefundResponse(ResponseData):
    """201 response for the refund endpoint (Phase 51 D-51-08)."""

    online_refund_id: UUID
    status: str
    yookassa_refund_id: str
