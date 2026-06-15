"""Phase 113 promo codes admin CRUD router (PROMO-01/PROMO-02).

Endpoint surface (4 routes):
  - GET   /api/v1/promo-codes                        — paginated list (PROMO-02)
  - POST  /api/v1/promo-codes                        — create (PROMO-01)
  - PATCH /api/v1/promo-codes/{promo_id}             — partial edit (PROMO-01)
  - PATCH /api/v1/promo-codes/{promo_id}/deactivate  — deactivate (PROMO-01)

Permission mapping (113-CONTEXT.md RBAC decision):
  - GET                    → require_permission(LIST,   PROMO_CODES)   [both roles]
  - POST /                 → require_permission(CREATE, PROMO_CODES) + CSRF [owner-only]
  - PATCH /{id}            → require_permission(EDIT,   PROMO_CODES) + CSRF [owner-only]
  - PATCH /{id}/deactivate → require_permission(DELETE, PROMO_CODES) + CSRF [owner-only]

RBAC-04 ordering invariant (D-43-29): in every mutation endpoint,
`Depends(require_permission(...))` is declared BEFORE `Depends(verify_csrf)` in the
function signature. FastAPI resolves signature dependencies in declaration order, so
401 (auth) fires before 403 (rbac/csrf).

Exception handling: all service-layer exceptions (PromoCodeNotFoundError,
PromoCodeAlreadyExistsError, ...) extend AppError and are mapped to JSON responses
by the global handler in app.core.exceptions — no per-endpoint try/except.

Wire format:
  - GET  → ResponseEnvelope[PaginatedData[PromoCodeListItemResponse]] (200)
  - POST → ResponseEnvelope[PromoCodeResponse] (201)
  - PATCH /{id} → ResponseEnvelope[PromoCodeResponse] (200)
  - PATCH /{id}/deactivate → 204 No Content (no body)
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
from app.modules.promo_codes import service
from app.modules.promo_codes.schemas import (
    PromoCodeCreateRequest,
    PromoCodeListItemResponse,
    PromoCodeListQuery,
    PromoCodeResponse,
    PromoCodeUpdateRequest,
)

router = APIRouter(tags=["Promo Codes"])


@router.get(
    "",
    response_model=ResponseEnvelope[PaginatedData[PromoCodeListItemResponse]],
    summary="List promo codes with optional active filter and pagination",
)
async def list_promo_codes_endpoint(
    query: Annotated[PromoCodeListQuery, Depends()],
    _actor: Annotated[CurrentUser, Depends(require_permission(Action.LIST, Resource.PROMO_CODES))],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ResponseEnvelope[PaginatedData[PromoCodeListItemResponse]]:
    """PROMO-02 — paginated list with used_count aggregate. LIST required; no CSRF (read)."""
    from app.modules.promo_codes import repository

    page = await repository.list_promo_codes(session, query)
    return envelope(page)


@router.post(
    "",
    response_model=ResponseEnvelope[PromoCodeResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Create a promo code (owner-only; UPPER-normalizes code; 409 on alive duplicate)",
)
async def create_promo_code_endpoint(
    payload: PromoCodeCreateRequest,
    actor: Annotated[CurrentUser, Depends(require_permission(Action.CREATE, Resource.PROMO_CODES))],
    _csrf: Annotated[None, Depends(verify_csrf)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ResponseEnvelope[PromoCodeResponse]:
    """PROMO-01 — create promo code. CREATE permission + CSRF required (RBAC-04 ordering)."""
    promo = await service.create_promo_code(session, actor, payload)
    return envelope(PromoCodeResponse.model_validate(promo))


@router.patch(
    "/{promo_id}",
    response_model=ResponseEnvelope[PromoCodeResponse],
    summary="Partial edit of an alive promo code (owner-only; 404 missing, 409 duplicate code)",
)
async def edit_promo_code_endpoint(
    promo_id: UUID,
    payload: PromoCodeUpdateRequest,
    actor: Annotated[CurrentUser, Depends(require_permission(Action.EDIT, Resource.PROMO_CODES))],
    _csrf: Annotated[None, Depends(verify_csrf)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ResponseEnvelope[PromoCodeResponse]:
    """PROMO-01 — partial edit. EDIT permission + CSRF required (RBAC-04 ordering)."""
    promo = await service.update_promo_code(session, actor, promo_id, payload)
    return envelope(PromoCodeResponse.model_validate(promo))


@router.patch(
    "/{promo_id}/deactivate",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Deactivate promo code (soft - sets is_active=False); 404 if missing",
)
async def deactivate_promo_code_endpoint(
    promo_id: UUID,
    actor: Annotated[CurrentUser, Depends(require_permission(Action.DELETE, Resource.PROMO_CODES))],
    _csrf: Annotated[None, Depends(verify_csrf)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    """PROMO-01 — deactivate (DELETE permission maps to deactivate). RBAC-04 ordering."""
    await service.deactivate_promo_code(session, actor, promo_id)
    return None
