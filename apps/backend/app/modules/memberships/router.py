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

Phase 26 endpoint surface (1 new route on `memberships_router`):
  - POST   /api/v1/memberships/{id}/renew          — renew, 201 (MEM-REN-EP-01)

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

import json
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response, status
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import CurrentUser, require_permission, verify_csrf
from app.core.idempotency import (
    idempotent_execute,
    verify_idempotency,
)
from app.core.pagination import PaginatedData
from app.core.permissions import Action, Resource
from app.core.redis import get_redis
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
    MembershipRefundRequest,
    MembershipResponse,
)

router = APIRouter(tags=["Memberships"])


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

memberships_router = APIRouter(tags=["Memberships"])


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
    summary=(
        "Sell a membership (reception+owner; 404 plan_not_found, 409 plan_inactive; "
        "requires Idempotency-Key — Phase 32 PAY-09)"
    ),
)
async def create_membership(
    payload: MembershipCreateRequest,
    request: Request,
    actor: Annotated[
        CurrentUser,
        Depends(require_permission(Action.CREATE, Resource.MEMBERSHIPS)),
    ],
    _csrf: Annotated[None, Depends(verify_csrf)],
    idempotency_key: Annotated[str, Depends(verify_idempotency)],
    redis: Annotated[Redis, Depends(get_redis)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> Response:
    """Sell a membership (MEM-EP-03). CREATE permission + CSRF + Idempotency-Key required.

    (CREATE, MEMBERSHIPS) is NOT in OWNER_ONLY — reception receives 201 on success.
    Service layer validates plan presence (404 plan_not_found) and active flag
    (409 plan_inactive) and computes start_date/end_date server-side (D-04).

    Phase 32 PAY-09 idempotency contract (D-32-18..D-32-20):
      - Header `Idempotency-Key` is required; missing or malformed → 422
        (idempotency_key_required / idempotency_key_invalid_format).
      - First call: SET NX claims the key with an in-flight placeholder, runs
        the service, stores the response envelope under the same key, returns.
      - Replay with identical key + identical body → 200 with the cached
        envelope bytes (byte-identical to the original response). Status code
        is also replayed from the stored envelope.
      - Replay with identical key + different body → 422 idempotency_key_reuse;
        no second sale is recorded.
      - Concurrent-in-flight (placeholder still set) → 409 idempotency_in_flight.

    RBAC-04 ordering: auth → require_permission → verify_csrf → verify_idempotency.
    Idempotency claim+replay+store delegated to the shared ``idempotent_execute``
    orchestrator (Phase 66 IDM-06 / D-66-LIFECYCLE-HELPER).
    """
    # Read raw incoming body for hash comparison on replay. FastAPI already
    # consumed it into `payload`, but `request.body()` is cached by Starlette
    # so this is cheap and deterministic.
    incoming_body = await request.body()

    async def _runner() -> tuple[int, bytes]:
        membership = await service.create_membership(session, actor, payload)
        body_bytes = json.dumps(
            envelope(membership).model_dump(mode="json", by_alias=True),
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
        return status.HTTP_201_CREATED, body_bytes

    return await idempotent_execute(redis, idempotency_key, incoming_body, runner=_runner)


@memberships_router.post(
    "/{membership_id}/cancel",
    status_code=status.HTTP_200_OK,
    summary="Cancel a membership (owner-only; 409 invalid_transition for non-active source)",
)
async def cancel_membership(
    membership_id: UUID,
    payload: MembershipCancelRequest,
    request: Request,
    actor: Annotated[
        CurrentUser,
        Depends(require_permission(Action.CANCEL, Resource.MEMBERSHIPS)),
    ],
    _csrf: Annotated[None, Depends(verify_csrf)],
    idempotency_key: Annotated[str, Depends(verify_idempotency)],
    redis: Annotated[Redis, Depends(get_redis)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> Response:
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

    RBAC-04 ordering: auth → require_permission → verify_csrf → verify_idempotency.
    Idempotency claim+replay+store delegated to the shared ``idempotent_execute``
    orchestrator (Phase 66 IDM-07 / D-66-LIFECYCLE-HELPER). Wired per IDM-07 (66-03):
    emits audit on every successful call; in-flight double-cancel race patched.
    """
    incoming_body = await request.body()

    async def _runner() -> tuple[int, bytes]:
        membership = await service.cancel_membership(session, actor, membership_id, payload)
        body_bytes = json.dumps(
            envelope(membership).model_dump(mode="json", by_alias=True),
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
        return status.HTTP_200_OK, body_bytes

    return await idempotent_execute(redis, idempotency_key, incoming_body, runner=_runner)


@memberships_router.post(
    "/{membership_id}/freeze",
    status_code=status.HTTP_200_OK,
    summary=(
        "Freeze membership (reception+owner; "
        "409 freeze_limit_exceeded / already_frozen / invalid_transition)"
    ),
)
async def freeze_membership(
    membership_id: UUID,
    request: Request,
    actor: Annotated[
        CurrentUser,
        Depends(require_permission(Action.CREATE, Resource.MEMBERSHIPS)),
    ],
    _csrf: Annotated[None, Depends(verify_csrf)],
    idempotency_key: Annotated[str, Depends(verify_idempotency)],
    redis: Annotated[Redis, Depends(get_redis)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> Response:
    """Freeze a membership (MEM-FRZ-EP-01). CREATE permission + CSRF required.

    Transitions active -> frozen and opens a freeze period. Returns the
    updated MembershipResponse including freezeDaysUsed/Remaining and
    currentFreezePeriod populated.

    Errors:
      - 404 membership_not_found
      - 409 invalid_transition (source not active)
      - 409 freeze_limit_exceeded (cumulative days >= snapshot limit)
      - 409 already_frozen (concurrent INSERT race)

    RBAC-04 ordering: auth → require_permission → verify_csrf → verify_idempotency.
    Idempotency claim+replay+store delegated to the shared ``idempotent_execute``
    orchestrator (Phase 66 IDM-07 / D-66-LIFECYCLE-HELPER). Wired per IDM-07 (66-03):
    emits audit on every successful call; no request body (incoming_body = b""),
    key is user+method+path-scoped so empty-body collision is correctly bounded.
    """
    # freeze_membership has no request body; request.body() returns b"".
    # The idempotency key is scoped as {user_id}:{method}:{path}:{header-key}
    # (D-66-USER-SCOPE) so an empty body does not allow cross-user collisions.
    incoming_body = await request.body()

    async def _runner() -> tuple[int, bytes]:
        membership = await service.freeze_membership(session, actor, membership_id)
        body_bytes = json.dumps(
            envelope(membership).model_dump(mode="json", by_alias=True),
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
        return status.HTTP_200_OK, body_bytes

    return await idempotent_execute(redis, idempotency_key, incoming_body, runner=_runner)


@memberships_router.post(
    "/{membership_id}/unfreeze",
    status_code=status.HTTP_200_OK,
    summary="Unfreeze membership (reception+owner; 409 invalid_transition)",
)
async def unfreeze_membership(
    membership_id: UUID,
    request: Request,
    actor: Annotated[
        CurrentUser,
        Depends(require_permission(Action.CREATE, Resource.MEMBERSHIPS)),
    ],
    _csrf: Annotated[None, Depends(verify_csrf)],
    idempotency_key: Annotated[str, Depends(verify_idempotency)],
    redis: Annotated[Redis, Depends(get_redis)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> Response:
    """Unfreeze a membership (MEM-FRZ-EP-02). CREATE permission + CSRF required.

    Closes the open freeze period, extends end_date by ceil(delta_seconds /
    86400) (minimum 1 day), and transitions frozen -> active.

    Errors:
      - 404 membership_not_found
      - 409 invalid_transition (source not frozen)

    RBAC-04 ordering: auth → require_permission → verify_csrf → verify_idempotency.
    Idempotency claim+replay+store delegated to the shared ``idempotent_execute``
    orchestrator (Phase 66 IDM-07 / D-66-LIFECYCLE-HELPER). Wired per IDM-07 (66-03):
    emits audit on every successful call; no request body (incoming_body = b""),
    key is user+method+path-scoped so empty-body collision is correctly bounded.
    """
    # unfreeze_membership has no request body; request.body() returns b"".
    # Key scoped as {user_id}:{method}:{path}:{header-key} (D-66-USER-SCOPE).
    incoming_body = await request.body()

    async def _runner() -> tuple[int, bytes]:
        membership = await service.unfreeze_membership(session, actor, membership_id)
        body_bytes = json.dumps(
            envelope(membership).model_dump(mode="json", by_alias=True),
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
        return status.HTTP_200_OK, body_bytes

    return await idempotent_execute(redis, idempotency_key, incoming_body, runner=_runner)


@memberships_router.post(
    "/{membership_id}/renew",
    status_code=status.HTTP_201_CREATED,
    summary=(
        "Renew membership (reception+owner; "
        "404 plan_not_found / membership_not_found; "
        "409 cannot_renew_cancelled / plan_archived)"
    ),
)
async def renew_membership(
    membership_id: UUID,
    request: Request,
    actor: Annotated[
        CurrentUser,
        Depends(require_permission(Action.CREATE, Resource.MEMBERSHIPS)),
    ],
    _csrf: Annotated[None, Depends(verify_csrf)],
    idempotency_key: Annotated[str, Depends(verify_idempotency)],
    redis: Annotated[Redis, Depends(get_redis)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> Response:
    """Renew a membership (MEM-REN-EP-01). CREATE permission + CSRF required.

    Creates a follow-up membership chained via ``previous_membership_id`` to
    the source. Snapshots from the CURRENT plan (so price increases between
    sale and renewal apply — PROJECT.md). Returns 201 + new
    ``MembershipResponse`` including ``previousMembershipId`` field.

    Date strategy:
      - source 'active' / 'frozen' → start_date = source.end_date + 1 day
      - source 'expired'           → start_date = today (Europe/Moscow)

    Errors:
      - 404 membership_not_found  (source missing)
      - 404 plan_not_found        (source's plan hard-deleted; defence-in-depth)
      - 409 cannot_renew_cancelled (source is cancelled — operator must sell new)
      - 409 plan_archived          (source's plan soft-deleted by owner)

    RBAC-04 ordering: auth → require_permission → verify_csrf → verify_idempotency.
    Idempotency claim+replay+store delegated to the shared ``idempotent_execute``
    orchestrator (Phase 66 IDM-07 / D-66-LIFECYCLE-HELPER). Wired per IDM-07 (66-03):
    value-creating (new membership row); no DB uniqueness gate — double-submit
    without idempotency would create duplicate chained membership rows.
    No request body (incoming_body = b""), key scoped by user+method+path+header.
    """
    # renew_membership has no request body; request.body() returns b"".
    # Key scoped as {user_id}:{method}:{path}:{header-key} (D-66-USER-SCOPE).
    incoming_body = await request.body()

    async def _runner() -> tuple[int, bytes]:
        new_membership = await service.renew_membership(session, actor, membership_id)
        body_bytes = json.dumps(
            envelope(new_membership).model_dump(mode="json", by_alias=True),
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
        return status.HTTP_201_CREATED, body_bytes

    return await idempotent_execute(redis, idempotency_key, incoming_body, runner=_runner)


@memberships_router.post(
    "/{membership_id}/refund",
    response_model=ResponseEnvelope[MembershipResponse],
    status_code=status.HTTP_200_OK,
    summary=(
        "Refund a membership (reception+owner per B-07; "
        "409 must_unfreeze_first / cannot_refund_renewed_source / "
        "invalid_transition / already_refunded; "
        "422 if amountKopecks supplied [REF-05])"
    ),
)
async def refund_membership(
    membership_id: UUID,
    payload: MembershipRefundRequest,
    actor: Annotated[
        CurrentUser,
        Depends(require_permission(Action.REFUND, Resource.MEMBERSHIPS)),
    ],
    _csrf: Annotated[None, Depends(verify_csrf)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ResponseEnvelope[MembershipResponse]:
    """Refund a membership (Phase 32 REF-01). REFUND permission + CSRF required.

    (REFUND, MEMBERSHIPS) is NOT in OWNER_ONLY per B-07 — reception+owner can
    both refund (H-13 AlertDialog mitigation handled at admin-web FE-13 in
    Phase 35). NO Idempotency-Key dependency — refund flow uses DB partial
    UNIQUE ``uq_payments_refund_of_alive`` for natural idempotency (D-32-20);
    repeat POST → 409 ``already_refunded``.

    Status-guard ordering (D-32-11 invariant — specific code wins):
      1. status='frozen'                        → 409 must_unfreeze_first   (B-08)
      2. has_renewal_descendants(membership_id) → 409 cannot_refund_renewed_source (B-09)
      3. generic _assert_can_transition         → 409 invalid_transition
         (already cancelled / expired)

    DB-side / refunder-side error mapping:
      - uq_payments_refund_of_alive race → 409 already_refunded (AlreadyRefundedError)
      - no original sale row (legacy)    → 404 original_payment_not_found
        (OriginalPaymentNotFoundError)

    Schema-layer validation (REF-05):
      - amountKopecks or any other extra field → 422 (BackendSchemaBase extra='forbid')
      - empty reason / reason >200 chars       → 422

    RBAC-04 ordering: auth → require_permission → verify_csrf.
    """
    membership = await service.refund_membership(session, actor, membership_id, payload)
    return envelope(membership)
