"""PT-packages module routers — /pt-package-plans + /pt-packages HTTP surface.

Phase 33 Plan 33-01 — ``plans_router`` for /pt-package-plans CRUD (owner-only,
PT-02). ``pt_packages_router`` is declared empty here; sibling Plans 33-02
(sale + list + read + cron) and 33-03 (cancel + refund + FSM) populate it
in Wave 2 without conflicting on this file because they own non-overlapping
HTTP-verb / path combinations.

RBAC mapping (D-33-06):
  - All /pt-package-plans CRUD → require_permission(<Action>, PT_PACKAGE_PLANS)
    + verify_csrf on mutations. All 4 ``(<Action>, PT_PACKAGE_PLANS)`` pairs
    are in OWNER_ONLY (Phase 30 INFRA-19) — reception → 403.

RBAC-04 ordering invariant: in every mutation endpoint signature,
``Depends(require_permission(...))`` appears BEFORE ``Depends(verify_csrf)``.
``tests/integration/test_route_introspection.py`` enforces this statically.

PATCH semantics:
  - PATCH includes immutable fields (session_count / price_kopecks /
    validity_days) — the service-layer FieldImmutableError gate translates
    any mutation attempt to 409 ``field_immutable`` (D-33-07).

DELETE semantics:
  - Pre-flight ``repository.has_instances_for_plan`` → 409 ``plan_in_use``
    if any pt_packages row references the plan (D-33-08); else soft-delete
    by flipping ``deleted_at = now(UTC)``.
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
from app.modules.pt_packages import service
from app.modules.pt_packages.schemas import (
    PtPackagePlanCreateRequest,
    PtPackagePlanListQuery,
    PtPackagePlanResponse,
    PtPackagePlanUpdateRequest,
)

plans_router = APIRouter()


@plans_router.get(
    "",
    response_model=ResponseEnvelope[PaginatedData[PtPackagePlanResponse]],
    summary="List PT-package plans (owner-only); paginated; ?includeArchived toggle",
)
async def list_plans(
    query: Annotated[PtPackagePlanListQuery, Depends()],
    _actor: Annotated[
        CurrentUser,
        Depends(require_permission(Action.VIEW, Resource.PT_PACKAGE_PLANS)),
    ],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ResponseEnvelope[PaginatedData[PtPackagePlanResponse]]:
    """List PT-package plans (PT-02). Owner-only via OWNER_ONLY pair."""
    page = await service.list_pt_package_plans(session, query)
    return envelope(page)


@plans_router.get(
    "/{plan_id}",
    response_model=ResponseEnvelope[PtPackagePlanResponse],
    summary="Fetch a single alive PT-package plan (owner-only)",
)
async def get_plan(
    plan_id: UUID,
    _actor: Annotated[
        CurrentUser,
        Depends(require_permission(Action.VIEW, Resource.PT_PACKAGE_PLANS)),
    ],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ResponseEnvelope[PtPackagePlanResponse]:
    """Read one alive PT-package plan. 404 ``pt_package_plan_not_found`` for missing/archived."""
    plan = await service.get_pt_package_plan(session, plan_id)
    return envelope(plan)


@plans_router.post(
    "",
    response_model=ResponseEnvelope[PtPackagePlanResponse],
    status_code=status.HTTP_201_CREATED,
    summary=(
        "Create a PT-package plan (owner-only; "
        "409 pt_package_plan_name_conflict on duplicate alive name)"
    ),
)
async def create_plan(
    payload: PtPackagePlanCreateRequest,
    actor: Annotated[
        CurrentUser,
        Depends(require_permission(Action.CREATE, Resource.PT_PACKAGE_PLANS)),
    ],
    _csrf: Annotated[None, Depends(verify_csrf)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ResponseEnvelope[PtPackagePlanResponse]:
    """Create a PT-package plan (PT-02). CREATE + CSRF required."""
    plan = await service.create_pt_package_plan(session, actor, payload)
    return envelope(plan)


@plans_router.patch(
    "/{plan_id}",
    response_model=ResponseEnvelope[PtPackagePlanResponse],
    summary=(
        "Patch a PT-package plan (owner-only); session_count / price_kopecks / "
        "validity_days mutation -> 409 field_immutable (D-33-07)"
    ),
)
async def update_plan(
    plan_id: UUID,
    payload: PtPackagePlanUpdateRequest,
    actor: Annotated[
        CurrentUser,
        Depends(require_permission(Action.EDIT, Resource.PT_PACKAGE_PLANS)),
    ],
    _csrf: Annotated[None, Depends(verify_csrf)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ResponseEnvelope[PtPackagePlanResponse]:
    """Patch a PT-package plan (PT-02 / D-33-07). EDIT + CSRF required.

    Only ``name`` is mutable post-creation. Mutating session_count /
    price_kopecks / validity_days raises 409 ``field_immutable`` with
    ``fields.field`` carrying the offending field name.
    """
    plan = await service.update_pt_package_plan(session, actor, plan_id, payload)
    return envelope(plan)


@plans_router.delete(
    "/{plan_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary=(
        "Soft-delete a PT-package plan (owner-only); "
        "409 plan_in_use if any pt_packages row references it (D-33-08)"
    ),
)
async def archive_plan(
    plan_id: UUID,
    actor: Annotated[
        CurrentUser,
        Depends(require_permission(Action.DELETE, Resource.PT_PACKAGE_PLANS)),
    ],
    _csrf: Annotated[None, Depends(verify_csrf)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    """Soft-delete a PT-package plan (PT-02 / D-33-08).

    Owner-only — reception → 403 from require_permission. Pre-flight checks
    for any pt_packages row referencing this plan (409 plan_in_use) before
    flipping deleted_at. Returns 204 No Content on success.
    """
    await service.archive_pt_package_plan(session, actor, plan_id)
    return None


# ---------------------------------------------------------------------------
# PT-package instance HTTP surface — populated by Plans 33-02 and 33-03.
#
# Plan 33-02 owns: POST /pt-packages (sale, reception+owner, Idempotency-Key),
# GET /pt-packages (list, reception+owner), GET /pt-packages/{id} (read,
# reception+owner). Plan 33-03 owns: POST /pt-packages/{id}/cancel (owner-only),
# POST /pt-packages/{id}/refund (reception+owner per B-07).
#
# Empty router declared here so app/api/v1/router.py can include the mount
# point in Plan 33-01 without changes in Wave 2. Plans 33-02 / 33-03 add
# their endpoints via @pt_packages_router.<verb>(...) decorators in
# router.py edits — they do NOT conflict with the plans_router above and
# do not modify the include in app/api/v1/router.py.
# ---------------------------------------------------------------------------

pt_packages_router = APIRouter()
