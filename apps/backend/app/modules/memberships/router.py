"""Membership Plans router — /membership-plans CRUD with RBAC + CSRF gates (Phase 16 — Plan 16-04).

Endpoint surface (5 routes):
  - GET    /api/v1/membership-plans           — list alive plans (MEM-PLAN-EP-01)
  - GET    /api/v1/membership-plans/{id}      — read single alive plan
  - POST   /api/v1/membership-plans           — create plan (MEM-PLAN-EP-02)
  - PATCH  /api/v1/membership-plans/{id}      — partial update; duration_days immutable
                                               (MEM-PLAN-EP-03)
  - DELETE /api/v1/membership-plans/{id}      — soft-delete, 204 (MEM-PLAN-EP-04, D-15)

Permission mapping:
  - GET (list + read-one) → require_permission(VIEW, MEMBERSHIP_PLANS)
  - POST                  → require_permission(CREATE, MEMBERSHIP_PLANS) + verify_csrf
  - PATCH                 → require_permission(EDIT, MEMBERSHIP_PLANS) + verify_csrf
  - DELETE                → require_permission(DELETE, MEMBERSHIP_PLANS) + verify_csrf

All 4 actions x MEMBERSHIP_PLANS are in OWNER_ONLY (Phase 15 INFRA-08) — reception
receives 403 on every endpoint.

RBAC-04 ordering (clients/router.py precedent): in every mutation endpoint,
`Depends(require_permission(...))` is declared BEFORE `Depends(verify_csrf)` in the
function signature. FastAPI resolves signature dependencies in declaration order, so
401 (auth) fires before 403 (rbac/csrf), preserving the invariant that an
unauthenticated caller never sees a CSRF error. `tests/integration/test_route_introspection.py`
enforces this invariant statically.

Wire format (Phase 4):
  - Request bodies are BackendSchemaBase subclasses (camelCase via alias_generator).
  - Successful responses wrap payloads in ResponseEnvelope[T] via envelope() (D-14).
  - POST → 201 Created; DELETE → 204 No Content; others → 200 OK.

D-15: Phase 16 DELETE is soft-delete only. No 409 plan_in_use check — the memberships
table and FK plan_id ON DELETE RESTRICT arrive in Phase 17. The IntegrityError translation
_is_plan_in_use_conflict() is a Phase 17 concern.

Service layer is the single mutation entry point — this router never imports the
MembershipPlan ORM model (architectural boundary maintained transitively via service.py).
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
from app.modules.memberships import service
from app.modules.memberships.schemas import (
    MembershipPlanCreateRequest,
    MembershipPlanListQuery,
    MembershipPlanResponse,
    MembershipPlanUpdateRequest,
)

router = APIRouter()


@router.get(
    "",
    response_model=ResponseEnvelope[PaginatedData[MembershipPlanResponse]],
    summary="List alive membership plans (owner-only); paginated; ?active filter",
)
async def list_plans(
    query: Annotated[MembershipPlanListQuery, Depends()],
    _actor: Annotated[
        CurrentUser,
        Depends(require_permission(Action.VIEW, Resource.MEMBERSHIP_PLANS)),
    ],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ResponseEnvelope[PaginatedData[MembershipPlanResponse]]:
    """List alive membership plans (MEM-PLAN-EP-01). VIEW permission required."""
    page = await service.list_plans(session, query)
    return envelope(page)


@router.get(
    "/{plan_id}",
    response_model=ResponseEnvelope[MembershipPlanResponse],
    summary="Fetch a single alive membership plan (owner-only)",
)
async def get_plan(
    plan_id: UUID,
    _actor: Annotated[
        CurrentUser,
        Depends(require_permission(Action.VIEW, Resource.MEMBERSHIP_PLANS)),
    ],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ResponseEnvelope[MembershipPlanResponse]:
    """Read one alive membership plan. 404 for missing or soft-deleted ids."""
    plan = await service.get_plan(session, plan_id)
    return envelope(plan)


@router.post(
    "",
    response_model=ResponseEnvelope[MembershipPlanResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Create a membership plan (owner-only; 409 plan_name_exists on duplicate alive name)",
)
async def create_plan(
    payload: MembershipPlanCreateRequest,
    actor: Annotated[
        CurrentUser,
        Depends(require_permission(Action.CREATE, Resource.MEMBERSHIP_PLANS)),
    ],
    _csrf: Annotated[None, Depends(verify_csrf)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ResponseEnvelope[MembershipPlanResponse]:
    """Create a membership plan (MEM-PLAN-EP-02). CREATE permission + CSRF required."""
    plan = await service.create_plan(session, actor, payload)
    return envelope(plan)


@router.patch(
    "/{plan_id}",
    response_model=ResponseEnvelope[MembershipPlanResponse],
    summary="Patch a membership plan (owner-only); durationDays is immutable (rejected with 422)",
)
async def update_plan(
    plan_id: UUID,
    payload: MembershipPlanUpdateRequest,
    actor: Annotated[
        CurrentUser,
        Depends(require_permission(Action.EDIT, Resource.MEMBERSHIP_PLANS)),
    ],
    _csrf: Annotated[None, Depends(verify_csrf)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ResponseEnvelope[MembershipPlanResponse]:
    """Partial update of an alive membership plan (MEM-PLAN-EP-03). EDIT + CSRF required."""
    plan = await service.update_plan(session, actor, plan_id, payload)
    return envelope(plan)


@router.delete(
    "/{plan_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Soft-delete a membership plan (owner-only); frees lower(name) unique slot",
)
async def soft_delete_plan(
    plan_id: UUID,
    actor: Annotated[
        CurrentUser,
        Depends(require_permission(Action.DELETE, Resource.MEMBERSHIP_PLANS)),
    ],
    _csrf: Annotated[None, Depends(verify_csrf)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    """Soft-delete an alive membership plan (MEM-PLAN-EP-04).

    Owner-only: (DELETE, MEMBERSHIP_PLANS) is in OWNER_ONLY, so reception → 403 from
    require_permission. CSRF required on the mutation. Returns 204 No Content.

    D-15: Phase 16 ships soft-delete only — no 409 plan_in_use. The memberships table
    FK plan_id ON DELETE RESTRICT and _is_plan_in_use_conflict helper arrive in Phase 17.
    """
    await service.soft_delete_plan(session, actor, plan_id)
    return None
