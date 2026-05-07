"""Visits HTTP router (Phase 19 VIS-EP-01..03).

Three endpoints under /api/v1/visits (mounted in app/api/v1/router.py):
  - GET    /                   list visits (reception+owner; (VIEW, VISITS))
  - GET    /{id}               get one visit (reception+owner; (VIEW, VISITS))
  - POST   /                   reception manual check-in (reception+owner;
                               (CHECK_IN, VISITS); CSRF required)

RBAC-04 ordering (clients/router.py + memberships/router.py precedent): in
every mutation endpoint, `Depends(require_permission(...))` is declared BEFORE
`Depends(verify_csrf)` in the function signature. FastAPI resolves signature
dependencies in declaration order, so 401 (auth) fires before 403 (rbac/csrf),
preserving the invariant that an unauthenticated caller never sees a CSRF
error. `tests/integration/test_route_introspection.py` enforces this
invariant statically.
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
from app.modules.visits import service
from app.modules.visits.schemas import (
    VisitCreateRequest,
    VisitListQuery,
    VisitResponse,
)

router = APIRouter()


@router.get(
    "",
    response_model=ResponseEnvelope[PaginatedData[VisitResponse]],
    summary="List visits filtered by clientId/from/to with pagination",
)
async def list_visits(
    query: Annotated[VisitListQuery, Depends()],
    _actor: Annotated[
        CurrentUser,
        Depends(require_permission(Action.VIEW, Resource.VISITS)),
    ],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ResponseEnvelope[PaginatedData[VisitResponse]]:
    """List visits, paginated (VIS-EP-01). VIEW permission required."""
    page = await service.list_visits(session, query)
    return envelope(page)


@router.get(
    "/{visit_id}",
    response_model=ResponseEnvelope[VisitResponse],
    summary="Get a single visit by id (404 visit_not_found)",
)
async def get_visit(
    visit_id: UUID,
    _actor: Annotated[
        CurrentUser,
        Depends(require_permission(Action.VIEW, Resource.VISITS)),
    ],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ResponseEnvelope[VisitResponse]:
    """Read one visit (VIS-EP-02). 404 `visit_not_found` for missing ids."""
    visit = await service.get_visit(session, visit_id)
    return envelope(visit)


@router.post(
    "",
    response_model=ResponseEnvelope[VisitResponse],
    status_code=status.HTTP_201_CREATED,
    summary=(
        "Reception manual check-in (reception+owner; "
        "409 outside_gym_hours / no_active_membership / duplicate_checkin)"
    ),
)
async def create_visit(
    payload: VisitCreateRequest,
    actor: Annotated[
        CurrentUser,
        Depends(require_permission(Action.CHECK_IN, Resource.VISITS)),
    ],
    _csrf: Annotated[None, Depends(verify_csrf)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ResponseEnvelope[VisitResponse]:
    """Reception manual check-in (VIS-EP-03). CHECK_IN permission + CSRF required.

    Sealed body — only `clientId` accepted (D-01). Every other field is
    server-derived: membershipId resolved via resolve_active_membership;
    checkedInAt defaults to DB now(); gymDate is the STORED GENERATED column;
    channel is 'reception'; checkedInBy is actor.id.

    RBAC-04: `actor` (require_permission) parameter is declared BEFORE
    `_csrf` (verify_csrf) so unauthenticated callers see 401, not CSRF
    errors. (CHECK_IN, VISITS) is NOT in OWNER_ONLY — reception receives
    201 on success.
    """
    visit = await service.create_visit_reception(session, actor, payload)
    return envelope(visit)
