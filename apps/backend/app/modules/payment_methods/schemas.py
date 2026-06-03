"""Payment method Pydantic schemas (Phase 79 PAYM-02/04).

Client-safe field projection: NEVER include yookassa_method_id (T-79-04).
camelCase wire via alias_generator=to_camel on ResponseData base.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from app.core.schemas import ResponseData


class ClientPaymentMethodResponse(ResponseData):
    """GET /client/payment-method payload — display fields only (PAYM-02).

    yookassa_method_id is NEVER included (D-decision: token never wired to client, T-79-04).
    expiry_month / expiry_year optional (may be absent for some card types).
    consent_recorded_at: None means autopay has never been enabled.
    """

    id: UUID
    last4: str
    brand: str
    expiry_month: int | None = None      # wire: expiryMonth
    expiry_year: int | None = None       # wire: expiryYear
    autopay_enabled: bool                # wire: autopayEnabled
    consent_recorded_at: datetime | None = None  # wire: consentRecordedAt


class ClientAutopayPatchRequest(ResponseData):
    """PATCH /client/payment-method/autopay body (PAYM-04).

    enabled=True requires consent_acknowledged=True (ФЗ-376 gate).
    enabled=False is ungated — no consent needed.
    extra='forbid' (ResponseData base) rejects unknown keys.
    """

    enabled: bool
    consent_acknowledged: bool = False  # wire: consentAcknowledged; required when enabled=True
