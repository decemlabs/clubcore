"""Clients router — /clients CRUD with RBAC + CSRF gates (Phase 8 — Plan 08-07).

Endpoint surface (5 routes):
  - GET    /api/v1/clients           — list alive clients (CLIENTS-03/04)
  - GET    /api/v1/clients/{id}      — read single alive client (CLIENTS-05)
  - POST   /api/v1/clients           — create client (CLIENTS-06)
  - PATCH  /api/v1/clients/{id}      — partial update (CLIENTS-07)
  - DELETE /api/v1/clients/{id}      — soft-delete (CLIENTS-08, owner-only via OWNER_ONLY)

Permission mapping (D-21):
  - GET (list + read-one) → require_permission(VIEW, CLIENTS)
  - POST + PATCH          → require_permission(EDIT, CLIENTS) + verify_csrf
  - DELETE                → require_permission(DELETE, CLIENTS) + verify_csrf
                            (DELETE,CLIENTS) is in OWNER_ONLY → reception → 403.

RBAC-04 ordering (D-22): in every mutation endpoint, `Depends(require_permission(...))`
is declared BEFORE `Depends(verify_csrf)` in the function signature. FastAPI resolves
signature dependencies in declaration order, so 401 (auth) fires before 403 (rbac/csrf),
preserving the invariant that an unauthenticated caller never sees a CSRF error.

Wire format (Phase 4):
  - Request bodies are BackendSchemaBase subclasses (camelCase via alias_generator).
  - Successful responses wrap payloads in ResponseEnvelope[T] via envelope() (D-14).
  - POST → 201 Created; DELETE → 204 No Content; others → 200 OK.

Service layer is the single mutation entry point — this router never imports the Client
ORM model (D-02 architectural boundary maintained transitively via service.py).
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import CurrentUser, require_permission, verify_csrf
from app.core.pagination import PaginatedData
from app.core.permissions import Action, Resource
from app.core.schemas import ResponseEnvelope, envelope
from app.modules.clients import service
from app.modules.clients.schemas import (
    ClientCreateRequest,
    ClientListQuery,
    ClientResponse,
    ClientUpdateRequest,
)
from app.modules.loyalty import service as loyalty_service
from app.modules.loyalty.permissions import require_owner_for_loyalty_grant
from app.modules.loyalty.schemas import ClientLoyaltyGrantResponse, LoyaltyGrantRequest

router = APIRouter(tags=["Clients"])


@router.get(
    "",
    response_model=ResponseEnvelope[PaginatedData[ClientResponse]],
    summary="List alive clients with filters and pagination",
)
async def list_clients(
    query: Annotated[ClientListQuery, Depends()],
    _actor: Annotated[CurrentUser, Depends(require_permission(Action.VIEW, Resource.CLIENTS))],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ResponseEnvelope[PaginatedData[ClientResponse]]:
    """List alive clients (CLIENTS-03/04). VIEW permission required (D-21)."""
    page = await service.list_clients(session, query)
    return envelope(page)


@router.get(
    "/{client_id}",
    response_model=ResponseEnvelope[ClientResponse],
    summary="Get a single alive client by id (404 if soft-deleted or missing)",
)
async def get_client(
    client_id: UUID,
    _actor: Annotated[CurrentUser, Depends(require_permission(Action.VIEW, Resource.CLIENTS))],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ResponseEnvelope[ClientResponse]:
    """Read one alive client (CLIENTS-05). 404 for missing or soft-deleted ids."""
    client = await service.get_client(session, client_id)
    return envelope(client)


@router.post(
    "",
    response_model=ResponseEnvelope[ClientResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Create a new client (E.164 phone; 409 phone_exists on partial-unique conflict)",
)
async def create_client(
    payload: ClientCreateRequest,
    actor: Annotated[CurrentUser, Depends(require_permission(Action.EDIT, Resource.CLIENTS))],
    _csrf: Annotated[None, Depends(verify_csrf)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ResponseEnvelope[ClientResponse]:
    """Create a client (CLIENTS-06). EDIT permission + CSRF required (D-21)."""
    client = await service.create_client(session, actor, payload)
    return envelope(client)


@router.patch(
    "/{client_id}",
    response_model=ResponseEnvelope[ClientResponse],
    summary="Partial update (PATCH semantics; null-out via PATCH not supported in v1.1)",
)
async def update_client(
    client_id: UUID,
    payload: ClientUpdateRequest,
    actor: Annotated[CurrentUser, Depends(require_permission(Action.EDIT, Resource.CLIENTS))],
    _csrf: Annotated[None, Depends(verify_csrf)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ResponseEnvelope[ClientResponse]:
    """Partial update of an alive client (CLIENTS-07). EDIT + CSRF (D-21)."""
    client = await service.update_client(session, actor, client_id, payload)
    return envelope(client)


@router.delete(
    "/{client_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Soft-delete a client (owner-only; sets deleted_at, never hard-deletes)",
)
async def soft_delete_client(
    client_id: UUID,
    actor: Annotated[CurrentUser, Depends(require_permission(Action.DELETE, Resource.CLIENTS))],
    _csrf: Annotated[None, Depends(verify_csrf)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    """Soft-delete an alive client (CLIENTS-08).

    Owner-only: (DELETE, CLIENTS) is in OWNER_ONLY, so reception → 403 from
    require_permission. CSRF required on the mutation. Returns 204 No Content;
    FastAPI emits an empty body for 204 status_code.
    """
    await service.soft_delete_client(session, actor, client_id)
    return None


@router.post(
    "/{client_id}/loyalty/grant",
    response_model=ResponseEnvelope[ClientLoyaltyGrantResponse],
    status_code=status.HTTP_201_CREATED,
    operation_id="owner_grant_loyalty",
    summary="Owner-only: manually grant bonus kopecks to a client (ACCR-02)",
)
async def owner_grant_loyalty(
    client_id: UUID,
    payload: LoyaltyGrantRequest,
    actor: Annotated[CurrentUser, Depends(require_owner_for_loyalty_grant())],
    _csrf: Annotated[None, Depends(verify_csrf)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ResponseEnvelope[ClientLoyaltyGrantResponse]:
    """Grant loyalty bonus to a client (owner-only, ACCR-02).

    Reception → 403 via require_owner_for_loyalty_grant (+ rbac_forbidden audit).
    RBAC-04 ordering: auth → custom_perm → verify_csrf → get_db.
    Router owns session.commit() (caller-owns-txn discipline — service flushes only).
    No try/except — AppError bubbles to _app_error_handler.
    """
    result = await loyalty_service.owner_grant_loyalty(session, actor, client_id, payload)
    await session.commit()
    return envelope(result)
