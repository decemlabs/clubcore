"""Online payments wire schemas (Phase 49 D-49-14 + Claude's discretion).

SellRequest / SellResponse. SellResponse enforces XOR between
confirmation_url and qr_payload via a Pydantic root validator —
exactly one must be populated per the chosen confirmation_type.
"""

from __future__ import annotations

from uuid import UUID

from pydantic import model_validator

from app.core.schemas import BackendSchemaBase, ResponseData


class SellRequest(BackendSchemaBase):
    """POST /api/v1/online-payments/.../sell* body (Phase 49 PAY-03..05)."""

    client_id: UUID


class SellResponse(ResponseData):
    """201 response for any of the 4 sell endpoints (Phase 49 D-49-14)."""

    confirmation_url: str | None = None
    qr_payload: str | None = None
    online_payment_id: UUID

    @model_validator(mode="after")
    def _exactly_one(self) -> SellResponse:
        if (self.confirmation_url is None) == (self.qr_payload is None):
            raise ValueError(
                "exactly one of confirmation_url / qr_payload must be set"
            )
        return self
