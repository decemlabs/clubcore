"""Trainers router — /trainers CRUD with RBAC + CSRF gates (Phase 31 TRN-02..07).

Endpoint surface (5 routes):
  - GET    /api/v1/trainers           — list alive trainers (TRN-04, D-31-09)
  - GET    /api/v1/trainers/{id}      — read single alive trainer (TRN-02)
  - POST   /api/v1/trainers           — create trainer (TRN-02, owner-only)
  - PATCH  /api/v1/trainers/{id}      — partial update / deactivate / reactivate (TRN-03)
  - DELETE /api/v1/trainers/{id}      — hard-delete (TRN-05, owner-only)

Permission mapping:
  - GET (list + read-one) → require_permission(VIEW, TRAINERS) — reception allowed (D-31-09)
  - POST                  → require_permission(CREATE, TRAINERS) + verify_csrf — owner-only
  - PATCH                 → require_permission(EDIT, TRAINERS) + verify_csrf — owner-only
  - DELETE                → require_permission(DELETE, TRAINERS) + verify_csrf — owner-only

RBAC-04 ordering: in every mutation endpoint, `Depends(require_permission(...))`
is declared BEFORE `Depends(verify_csrf)`. FastAPI resolves signature dependencies in
declaration order, so 401 (auth) fires before 403 (rbac/csrf).
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
from app.modules.trainers import service
from app.modules.trainers.schemas import (
    TrainerCreateRequest,
    TrainerListQuery,
    TrainerResponse,
    TrainerUpdateRequest,
)

router = APIRouter()


@router.get(
    "",
    response_model=ResponseEnvelope[PaginatedData[TrainerResponse]],
    summary="List alive trainers with optional is_active filter and pagination",
)
async def list_trainers(
    query: Annotated[TrainerListQuery, Depends()],
    _actor: Annotated[
        CurrentUser, Depends(require_permission(Action.VIEW, Resource.TRAINERS))
    ],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ResponseEnvelope[PaginatedData[TrainerResponse]]:
    """List alive trainers (TRN-04). VIEW permission required — reception allowed (D-31-09)."""
    page = await service.list_trainers(session, query)
    return envelope(page)


@router.get(
    "/{trainer_id}",
    response_model=ResponseEnvelope[TrainerResponse],
    summary="Get a single alive trainer by id (404 if soft-deleted or missing)",
)
async def get_trainer(
    trainer_id: UUID,
    _actor: Annotated[
        CurrentUser, Depends(require_permission(Action.VIEW, Resource.TRAINERS))
    ],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ResponseEnvelope[TrainerResponse]:
    """Read one alive trainer (TRN-02). 404 for missing or soft-deleted ids."""
    trainer = await service.get_trainer(session, trainer_id)
    return envelope(trainer)


@router.post(
    "",
    response_model=ResponseEnvelope[TrainerResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Create a new trainer (E.164 phone optional; 409 phone_exists on conflict)",
)
async def create_trainer(
    payload: TrainerCreateRequest,
    actor: Annotated[
        CurrentUser, Depends(require_permission(Action.CREATE, Resource.TRAINERS))
    ],
    _csrf: Annotated[None, Depends(verify_csrf)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ResponseEnvelope[TrainerResponse]:
    """Create a trainer (TRN-02). CREATE permission + CSRF required (RBAC-04 ordering)."""
    trainer = await service.create_trainer(session, actor, payload)
    return envelope(trainer)


@router.patch(
    "/{trainer_id}",
    response_model=ResponseEnvelope[TrainerResponse],
    summary="Partial update (PATCH semantics; handles deactivate/reactivate via isActive)",
)
async def update_trainer(
    trainer_id: UUID,
    payload: TrainerUpdateRequest,
    actor: Annotated[
        CurrentUser, Depends(require_permission(Action.EDIT, Resource.TRAINERS))
    ],
    _csrf: Annotated[None, Depends(verify_csrf)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ResponseEnvelope[TrainerResponse]:
    """Partial update of an alive trainer (TRN-03). EDIT + CSRF (RBAC-04 ordering)."""
    trainer = await service.update_trainer(session, actor, trainer_id, payload)
    return envelope(trainer)


@router.delete(
    "/{trainer_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Hard-delete a trainer (owner-only; 409 trainer_in_use if pt_sessions FK)",
)
async def delete_trainer(
    trainer_id: UUID,
    actor: Annotated[
        CurrentUser, Depends(require_permission(Action.DELETE, Resource.TRAINERS))
    ],
    _csrf: Annotated[None, Depends(verify_csrf)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    """Hard-delete an alive trainer (TRN-05).

    Owner-only: (DELETE, TRAINERS) is in OWNER_ONLY, so reception → 403 from
    require_permission. CSRF required on the mutation. Returns 204 No Content.
    Maps IntegrityError pgcode=23503 → 409 trainer_in_use (pre-emptive D-31-07).
    """
    await service.delete_trainer(session, actor, trainer_id)
    return None
