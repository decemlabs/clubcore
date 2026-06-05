"""Loyalty module Pydantic schemas (Phase 82 LOYL-01/ACCR-02).

Response schemas use ResponseData (camelCase wire via alias_generator=to_camel).
Request schema uses BackendSchemaBase (extra='forbid', camelCase inbound).
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import Field

from app.core.schemas import BackendSchemaBase, ResponseData


class ClientLoyaltyBalanceResponse(ResponseData):
    """GET /client/loyalty/balance payload (LOYL-01).

    Wire: { balanceKopecks: int } — SUM fold over loyalty_ledger for the principal.
    Returns 0 when no rows exist (D-69-03: empty own-scope is 200/0, never 404).
    """

    balance_kopecks: int  # wire: balanceKopecks


class ClientLoyaltyHistoryItem(ResponseData):
    """Single ledger row for the paginated history endpoint (LOYL-02).

    Wire: { id, type, amountKopecks, createdAt }
    amountKopecks is signed: positive = accrual, negative = redemption (Phase 83).
    category/reason are deliberately NOT exposed here — they are owner-grant
    bookkeeping context (admin-only), not client-facing (IN-01).
    """

    id: UUID
    type: str  # entry_type: 'welcome' | 'owner_grant' | 'redemption'
    amount_kopecks: int  # wire: amountKopecks (signed)
    created_at: datetime  # wire: createdAt (ISO-8601 with TZ)


class ClientLoyaltyGrantResponse(ResponseData):
    """POST /clients/{id}/loyalty/grant response payload (ACCR-02).

    Wire: { entryId, balanceKopecks }
    balanceKopecks is the new client balance after the grant.
    """

    entry_id: UUID  # wire: entryId
    balance_kopecks: int  # wire: balanceKopecks (new balance after grant)


class LoyaltyGrantRequest(BackendSchemaBase):
    """Owner-only manual loyalty grant request body (ACCR-02).

    extra='forbid' (inherited from BackendSchemaBase) rejects unknown keys.
    amount_kopecks must be > 0 (schema-layer Field(gt=0); service keeps a
    belt-and-suspenders check). reason is capped at 255 to match the
    loyalty_ledger.reason VARCHAR(255) column — without this a longer value
    yields an unhandled 500 DataError instead of a clean 422 (CR-01).
    category covers promotional, referral (manual, not automated), or manual grants.
    """

    amount_kopecks: int = Field(gt=0)  # wire: amountKopecks
    reason: str = Field(max_length=255)
    category: Literal["promo", "referral", "manual"]
