"""Loyalty client-portal read endpoints (Phase 82 LOYL-01/LOYL-02).

Mounted under /api/v1/client (alongside client_portal_router) via a dedicated
loyalty_router — this avoids a client_portal→loyalty cross-module edge
(D-20-MODULE; mirrors the separation pattern at v1/router.py:101-103).

Endpoints:
  - GET /api/v1/client/loyalty/balance  → ClientLoyaltyBalanceResponse
  - GET /api/v1/client/loyalty/history  → PaginatedData[ClientLoyaltyHistoryItem]

Both endpoints are IDOR-safe: client_id comes from require_client() principal only,
never from a URL parameter (D-20-IDOR / T-82-05).
D-69-03: empty ledger returns 200 with balanceKopecks=0 (never 404).
No try/except — AppError bubbles to _app_error_handler.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import ClientPrincipal, require_client
from app.core.pagination import PageQuery, PaginatedData
from app.core.schemas import ResponseEnvelope, envelope
from app.modules.loyalty import service
from app.modules.loyalty.schemas import (
    ClientLoyaltyBalanceResponse,
    ClientLoyaltyHistoryItem,
)

router = APIRouter(tags=["Client-Portal"])


@router.get(
    "/loyalty/balance",
    response_model=ResponseEnvelope[ClientLoyaltyBalanceResponse],
    operation_id="client_get_loyalty_balance",
    summary="Current bonus balance for the authenticated client (LOYL-01; IDOR-safe)",
)
async def client_get_loyalty_balance(
    client: Annotated[ClientPrincipal, Depends(require_client())],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ResponseEnvelope[ClientLoyaltyBalanceResponse]:
    """Return the SUM fold balance for the principal's client only.

    D-20-IDOR: client_id sourced from require_client() principal — never from URL.
    D-69-03: empty ledger returns 200/{ balanceKopecks: 0 }, never 404.
    No try/except — AppError bubbles to _app_error_handler.
    """
    result = await service.get_client_loyalty_balance(session, client.id)
    return envelope(result)


@router.get(
    "/loyalty/history",
    response_model=ResponseEnvelope[PaginatedData[ClientLoyaltyHistoryItem]],
    operation_id="client_list_loyalty_history",
    summary="Paginated loyalty ledger history for the authenticated client (LOYL-02)",
)
async def client_list_loyalty_history(
    query: Annotated[PageQuery, Depends()],
    client: Annotated[ClientPrincipal, Depends(require_client())],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ResponseEnvelope[PaginatedData[ClientLoyaltyHistoryItem]]:
    """Return paginated loyalty rows (signed amountKopecks, DESC order) for the principal.

    D-20-IDOR: client_id from require_client() principal only.
    No try/except — AppError bubbles to _app_error_handler.
    """
    page = await service.list_client_loyalty_history(session, client.id, query)
    return envelope(page)
