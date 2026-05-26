"""Visits HTTP router (Phase 19 VIS-EP-01..03; Phase 22 D-22-1).

Four endpoints under /api/v1/visits (mounted in app/api/v1/router.py):
  - GET    /                   list visits (reception+owner; (VIEW, VISITS))
  - GET    /_meta              gym hours metadata (cacheable 5 min) (Phase 22 D-22-1)
                               (VIEW, VISITS); no DB access; Cache-Control: public, max-age=300
  - GET    /{id}               get one visit (reception+owner; (VIEW, VISITS))
  - POST   /                   reception manual check-in (reception+owner;
                               (CHECK_IN, VISITS); CSRF required)

Route registration order: /_meta MUST be registered BEFORE /{visit_id} to
prevent FastAPI's path resolver from routing "_meta" into the UUID parameter
(D-22-1 invariant enforced by tests/integration/test_visits_meta.py).

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

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
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
    VisitsMetaResponse,
)

router = APIRouter(tags=["Visits"])


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
    "/_meta",
    response_model=ResponseEnvelope[VisitsMetaResponse],
    summary="Gym hours metadata (cacheable 5 min) (Phase 22 D-22-1)",
)
async def get_visits_meta(
    response: Response,
    _actor: Annotated[
        CurrentUser,
        Depends(require_permission(Action.VIEW, Resource.VISITS)),
    ],
) -> ResponseEnvelope[VisitsMetaResponse]:
    """Return gym hours window. Reception + owner. No DB access.

    Cache-Control: public, max-age=300 — value travels with route (D-22-1).
    Reads Settings.gym_hours_start / gym_hours_end (lru_cache) and serialises
    via .isoformat()[:5] → HH:MM strings.
    """
    settings = get_settings()
    response.headers["Cache-Control"] = "public, max-age=300"
    meta = VisitsMetaResponse(
        gym_hours_start=settings.gym_hours_start.isoformat()[:5],
        gym_hours_end=settings.gym_hours_end.isoformat()[:5],
    )
    return envelope(meta)


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
