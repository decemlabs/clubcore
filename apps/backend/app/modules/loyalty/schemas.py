"""Loyalty module Pydantic schemas (Phase 82 LOYL-01/ACCR-02).

Response schemas use ResponseData (camelCase wire via alias_generator=to_camel).
Request schema uses BackendSchemaBase (extra='forbid', camelCase inbound).
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

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
    amount_kopecks must be > 0 (service raises 422 on <= 0).
    category covers promotional, referral (manual, not automated), or manual grants.
    """

    amount_kopecks: int  # wire: amountKopecks; must be > 0 (validated in service)
    reason: str
    category: Literal["promo", "referral", "manual"]
