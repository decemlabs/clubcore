"""Memberships module routers — /membership-plans + /memberships HTTP surface.

Phase 16 (Plan 16-04) — `router` (mounted as `plans_router`) — /membership-plans CRUD.
Phase 17 (Plan 17-04) — `memberships_router` — /memberships sale + cancel + list/get.

The two APIRouter instances coexist in this module per CD-02 (router-split strategy):
the existing `router` keeps its export name so `app.api.v1.router` still imports it as
`plans_router`; the new `memberships_router` is mounted at `/memberships` alongside.

Phase 17 endpoint surface (4 routes — all on `memberships_router`):
  - GET    /api/v1/memberships                     — list, paginated (MEM-EP-01)
  - GET    /api/v1/memberships/{id}                — read single (MEM-EP-02)
  - POST   /api/v1/memberships                     — sell, 201 (MEM-EP-03)
  - POST   /api/v1/memberships/{id}/cancel         — cancel, 200 (MEM-EP-04)

Phase 25 endpoint surface (2 new routes — both on `memberships_router`):
  - POST   /api/v1/memberships/{id}/freeze         — freeze, 200 (MEM-FRZ-EP-01)
  - POST   /api/v1/memberships/{id}/unfreeze       — unfreeze, 200 (MEM-FRZ-EP-02)

Phase 17 permission mapping (CONTEXT.md `<domain>` line 19):
  - GET (list + read-one) → require_permission(VIEW, MEMBERSHIPS)   — reception+owner
  - POST (sell)           → require_permission(CREATE, MEMBERSHIPS) + verify_csrf
                            (NOT in OWNER_ONLY — reception+owner)
  - POST (cancel)         → require_permission(CANCEL, MEMBERSHIPS) + verify_csrf
                            (IN OWNER_ONLY — owner-only; reception → 403)

Phase 16 endpoint surface (5 routes — all on `router`):
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
    MembershipCancelRequest,
    MembershipCreateRequest,
    MembershipListQuery,
    MembershipPlanCreateRequest,
    MembershipPlanListQuery,
    MembershipPlanResponse,
    MembershipPlanUpdateRequest,
    MembershipResponse,
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


# ===========================================================================
# Phase 17 — Membership instance HTTP surface (MEM-EP-01..04)
# ===========================================================================
#
# Second APIRouter per CD-02 (router-split strategy). Mounted at `/memberships`
# in `app/api/v1/router.py`, separately from `plans_router` at `/membership-plans`.
# Both routers coexist in this module file because they share the same domain
# module (Phase 16 plans + Phase 17 instances).
#
# RBAC mapping (CONTEXT.md `<domain>` line 19):
#   - GET  list/get → require_permission(VIEW, MEMBERSHIPS)        — reception+owner
#   - POST sell     → require_permission(CREATE, MEMBERSHIPS) + verify_csrf
#   - POST cancel   → require_permission(CANCEL, MEMBERSHIPS) + verify_csrf
#                     ((CANCEL, MEMBERSHIPS) in OWNER_ONLY — reception → 403)
#
# RBAC-04 ordering invariant: in every mutation endpoint signature,
# `Depends(require_permission(...))` appears BEFORE `Depends(verify_csrf)`.
# `tests/integration/test_route_introspection.py` enforces this statically.

memberships_router = APIRouter()


@memberships_router.get(
    "",
    response_model=ResponseEnvelope[PaginatedData[MembershipResponse]],
    summary="List memberships filtered by clientId/status with pagination",
)
async def list_memberships(
    query: Annotated[MembershipListQuery, Depends()],
    _actor: Annotated[
        CurrentUser,
        Depends(require_permission(Action.VIEW, Resource.MEMBERSHIPS)),
    ],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ResponseEnvelope[PaginatedData[MembershipResponse]]:
    """List memberships, paginated (MEM-EP-01).

    Query parameters (Phase 17 D-09; Phase 24 DEBT-02 adds expiring/within):
      - clientId — optional UUID filter; omit for global feed (owner)
      - status   — optional single-value enum (active|expired|cancelled); omit for all
      - sort     — created_at_desc (default) | end_date_desc | start_date_desc
      - page / pageSize — PageQuery contract (default 1 / 20, max 100)
      - expiring — bool (default false); when true, forces status='active' and
                   adds inclusive end_date window [today, today + (within - 1)]
                   (Europe/Moscow today). Conflict with status != active -> 422
                   query_invalid {status: incompatible_with_expiring}.
      - within   — int (default 7, bounded 1..30); window size in days when
                   expiring=true. Silently ignored when expiring=false.
    """
    page = await service.list_memberships(session, query)
    return envelope(page)


@memberships_router.get(
    "/{membership_id}",
    response_model=ResponseEnvelope[MembershipResponse],
    summary="Get a membership by id (404 membership_not_found)",
)
async def get_membership(
    membership_id: UUID,
    _actor: Annotated[
        CurrentUser,
        Depends(require_permission(Action.VIEW, Resource.MEMBERSHIPS)),
    ],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ResponseEnvelope[MembershipResponse]:
    """Read one membership (MEM-EP-02). 404 `membership_not_found` for missing ids."""
    membership = await service.get_membership(session, membership_id)
    return envelope(membership)


@memberships_router.post(
    "",
    response_model=ResponseEnvelope[MembershipResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Sell a membership (reception+owner; 404 plan_not_found, 409 plan_inactive)",
)
async def create_membership(
    payload: MembershipCreateRequest,
    actor: Annotated[
        CurrentUser,
        Depends(require_permission(Action.CREATE, Resource.MEMBERSHIPS)),
    ],
    _csrf: Annotated[None, Depends(verify_csrf)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ResponseEnvelope[MembershipResponse]:
    """Sell a membership (MEM-EP-03). CREATE permission + CSRF required.

    (CREATE, MEMBERSHIPS) is NOT in OWNER_ONLY — reception receives 201 on success.
    Service layer validates plan presence (404 plan_not_found) and active flag
    (409 plan_inactive) and computes start_date/end_date server-side (D-04).
    """
    membership = await service.create_membership(session, actor, payload)
    return envelope(membership)


@memberships_router.post(
    "/{membership_id}/cancel",
    response_model=ResponseEnvelope[MembershipResponse],
    status_code=status.HTTP_200_OK,
    summary="Cancel a membership (owner-only; 409 invalid_transition for non-active source)",
)
async def cancel_membership(
    membership_id: UUID,
    payload: MembershipCancelRequest,
    actor: Annotated[
        CurrentUser,
        Depends(require_permission(Action.CANCEL, Resource.MEMBERSHIPS)),
    ],
    _csrf: Annotated[None, Depends(verify_csrf)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ResponseEnvelope[MembershipResponse]:
    """Cancel a membership (MEM-EP-04). Owner-only — reception → 403 from RBAC gate.

    (CANCEL, MEMBERSHIPS) is in OWNER_ONLY (Phase 15 INFRA-08). CSRF required on
    the mutation. Returns 200 with the cancelled MembershipResponse (NOT 204 —
    the body carries the post-transition row including `cancelled_at`).

    State machine (Phase 17 D-12 + Phase 25 D-25-20): `active → cancelled` and
    `frozen → cancelled` are both allowed; `expired` and `cancelled` source
    states raise 409 `invalid_transition` with payload `{from_status, to_status}`.

    Phase 25 D-25-20: also accepts frozen source. When called on a frozen
    membership, the open freeze period is closed without end_date extension
    (cancellation supersedes freeze) and audit emits `membership_unfrozen`
    (days_added=0) before `membership_cancelled` in the same UoW. Owner-only
    via existing (CANCEL, MEMBERSHIPS) ∈ OWNER_ONLY.
    """
    membership = await service.cancel_membership(session, actor, membership_id, payload)
    return envelope(membership)


@memberships_router.post(
    "/{membership_id}/freeze",
    response_model=ResponseEnvelope[MembershipResponse],
    status_code=status.HTTP_200_OK,
    summary=(
        "Freeze membership (reception+owner; "
        "409 freeze_limit_exceeded / already_frozen / invalid_transition)"
    ),
)
async def freeze_membership(
    membership_id: UUID,
    actor: Annotated[
        CurrentUser,
        Depends(require_permission(Action.CREATE, Resource.MEMBERSHIPS)),
    ],
    _csrf: Annotated[None, Depends(verify_csrf)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ResponseEnvelope[MembershipResponse]:
    """Freeze a membership (MEM-FRZ-EP-01). CREATE permission + CSRF required.

    Transitions active -> frozen and opens a freeze period. Returns the
    updated MembershipResponse including freezeDaysUsed/Remaining and
    currentFreezePeriod populated.

    Errors:
      - 404 membership_not_found
      - 409 invalid_transition (source not active)
      - 409 freeze_limit_exceeded (cumulative days >= snapshot limit)
      - 409 already_frozen (concurrent INSERT race)
    """
    membership = await service.freeze_membership(  # type: ignore[attr-defined]  # Wave 4: service.freeze_membership defined in Plan 03
        session, actor, membership_id
    )
    return envelope(membership)


@memberships_router.post(
    "/{membership_id}/unfreeze",
    response_model=ResponseEnvelope[MembershipResponse],
    status_code=status.HTTP_200_OK,
    summary="Unfreeze membership (reception+owner; 409 invalid_transition)",
)
async def unfreeze_membership(
    membership_id: UUID,
    actor: Annotated[
        CurrentUser,
        Depends(require_permission(Action.CREATE, Resource.MEMBERSHIPS)),
    ],
    _csrf: Annotated[None, Depends(verify_csrf)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ResponseEnvelope[MembershipResponse]:
    """Unfreeze a membership (MEM-FRZ-EP-02). CREATE permission + CSRF required.

    Closes the open freeze period, extends end_date by ceil(delta_seconds /
    86400) (minimum 1 day), and transitions frozen -> active.

    Errors:
      - 404 membership_not_found
      - 409 invalid_transition (source not frozen)
    """
    membership = await service.unfreeze_membership(  # type: ignore[attr-defined]  # Wave 4: service.unfreeze_membership defined in Plan 03
        session, actor, membership_id
    )
    return envelope(membership)
