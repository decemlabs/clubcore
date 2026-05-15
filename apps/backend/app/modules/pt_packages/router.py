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

import base64
import json
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response, status
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import CurrentUser, require_permission, verify_csrf
from app.core.exceptions import ConflictError, ValidationAppError
from app.core.idempotency import (
    IDEMPOTENCY_REDIS_PREFIX,
    IDEMPOTENCY_TTL_SECONDS,
    body_sha256,
    load_idempotency_response,
    verify_idempotency,
)
from app.core.pagination import PaginatedData
from app.core.permissions import Action, Resource
from app.core.redis import get_redis
from app.core.schemas import ResponseEnvelope, envelope
from app.modules.pt_packages import service
from app.modules.pt_packages.schemas import (
    PtPackageCancelRequest,
    PtPackageCreateRequest,
    PtPackageListQuery,
    PtPackagePlanCreateRequest,
    PtPackagePlanListQuery,
    PtPackagePlanResponse,
    PtPackagePlanUpdateRequest,
    PtPackageRefundRequest,
    PtPackageResponse,
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


# ---------------------------------------------------------------------------
# Plan 33-02 endpoints — sale (POST), list (GET), detail (GET).
# Plan 33-03 will append: POST /{id}/cancel + POST /{id}/refund.
# ---------------------------------------------------------------------------


@pt_packages_router.post(
    "",
    response_model=ResponseEnvelope[PtPackageResponse],
    status_code=status.HTTP_201_CREATED,
    summary=(
        "Sell a PT-package (reception+owner; 404 pt_package_plan_not_found, "
        "422 amount_mismatch, 409 active_pt_package_already_exists; "
        "requires Idempotency-Key — D-33-16)"
    ),
)
async def create_pt_package(
    payload: PtPackageCreateRequest,
    request: Request,
    actor: Annotated[
        CurrentUser,
        Depends(require_permission(Action.CREATE, Resource.PT_PACKAGES)),
    ],
    _csrf: Annotated[None, Depends(verify_csrf)],
    idempotency_key: Annotated[str, Depends(verify_idempotency)],
    redis: Annotated[Redis, Depends(get_redis)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> Response:
    """Sell a PT-package (Phase 33 PT-07).

    (CREATE, PT_PACKAGES) is NOT in OWNER_ONLY — reception+owner receive 201.
    Service layer:
      - 404 pt_package_plan_not_found when plan archived/missing (D-33-08).
      - 422 amount_mismatch when amountKopecks != plan.priceKopecks (D-33-17).
      - 409 active_pt_package_already_exists (defensive pre-check AND DB
        partial UNIQUE race gate — D-33-09).
      - Idempotency-Key required (D-33-16); same Redis namespace
        ``sz:idem:{key}`` and TTL as Phase 32 PAY-09.

    RBAC-04 ordering: auth → require_permission → verify_csrf →
    verify_idempotency. Two-phase Redis claim + replay block mirrors
    ``memberships.router.create_membership``.
    """
    # Body hash for replay-collision detection on identical Idempotency-Key.
    incoming_body = await request.body()
    incoming_hash = body_sha256(incoming_body)

    # Phase 32 PAY-09 / D-33-16 — replay branch first; if a completed envelope
    # is cached for this key, return verbatim (matching body hash) OR raise
    # 422 idempotency_key_reuse (mismatched body).
    stored = await load_idempotency_response(redis, idempotency_key)
    if stored is not None:
        if isinstance(stored, str):
            # Placeholder (in-flight) — concurrent caller still running.
            raise ConflictError("idempotency_in_flight")
        if stored["body_hash"] != incoming_hash:
            raise ValidationAppError("idempotency_key_reuse")
        return Response(
            content=base64.b64decode(stored["body_b64"]),
            status_code=stored["status_code"],
            media_type="application/json",
        )

    # First call for this key — run the sale orchestrator. We do NOT pre-claim
    # the key with SET NX because the orchestrator's own commit failure path
    # would leave a stale placeholder; instead, store the envelope after a
    # successful run. Concurrent callers race on the partial UNIQUE
    # uq_pt_packages_active_per_client and exactly one wins with 201 — the
    # other surfaces 409 active_pt_package_already_exists (T-33-02-03).
    pt_package = await service.create_pt_package(session, actor, payload)
    response_envelope = envelope(pt_package)
    body_bytes = json.dumps(
        response_envelope.model_dump(mode="json", by_alias=True),
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    envelope_json = json.dumps(
        {
            "status_code": status.HTTP_201_CREATED,
            "body_hash": incoming_hash,
            "body_b64": base64.b64encode(body_bytes).decode("ascii"),
        },
        separators=(",", ":"),
        ensure_ascii=False,
    )
    await redis.set(
        f"{IDEMPOTENCY_REDIS_PREFIX}{idempotency_key}",
        envelope_json,
        ex=IDEMPOTENCY_TTL_SECONDS,
    )
    return Response(
        content=body_bytes,
        status_code=status.HTTP_201_CREATED,
        media_type="application/json",
    )


@pt_packages_router.get(
    "",
    response_model=ResponseEnvelope[PaginatedData[PtPackageResponse]],
    summary="List PT-packages (reception+owner; paginated; ?clientId / ?status filters)",
)
async def list_pt_packages(
    query: Annotated[PtPackageListQuery, Depends()],
    _actor: Annotated[
        CurrentUser,
        Depends(require_permission(Action.VIEW, Resource.PT_PACKAGES)),
    ],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ResponseEnvelope[PaginatedData[PtPackageResponse]]:
    """Paginated PT-package list (D-33-06 read tier).

    (VIEW, PT_PACKAGES) is NOT in OWNER_ONLY — reception sees the same list
    as owner (B-07 / Phase 35 PT-session form prefill — FE-10..18).
    """
    page = await service.list_pt_packages(session, query)
    return envelope(page)


@pt_packages_router.get(
    "/{pt_package_id}",
    response_model=ResponseEnvelope[PtPackageResponse],
    summary="Read a single PT-package (reception+owner; 404 pt_package_not_found)",
)
async def get_pt_package(
    pt_package_id: UUID,
    _actor: Annotated[
        CurrentUser,
        Depends(require_permission(Action.VIEW, Resource.PT_PACKAGES)),
    ],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ResponseEnvelope[PtPackageResponse]:
    """Read a single PT-package instance (D-33-06; D-33-10 ``is_active`` computed).

    404 ``pt_package_not_found`` for missing ids.
    """
    pt_package = await service.get_pt_package_by_id(session, pt_package_id)
    return envelope(pt_package)


# ---------------------------------------------------------------------------
# Plan 33-03 — Cancel + Refund terminal-lifecycle endpoints.
#
# Both routes mirror the sale endpoint's two-phase Redis claim + replay
# pattern so that Idempotency-Key reuse on the SAME route returns a verbatim
# cached envelope (D-33-16 — operator UX consistency across the 3 mutating
# PT-package endpoints). Different routes (cancel vs refund) hash to distinct
# Redis keys because the request method + URL path are part of the key
# derivation in ``verify_idempotency`` — same key on different routes does
# NOT collide (T-33-03-10 mitigation).
# ---------------------------------------------------------------------------


@pt_packages_router.post(
    "/{pt_package_id}/cancel",
    response_model=ResponseEnvelope[PtPackageResponse],
    status_code=status.HTTP_200_OK,
    summary=(
        "Cancel a PT-package without refund (owner-only; 404 pt_package_not_found; "
        "409 invalid_transition for cancelled source; requires Idempotency-Key — D-33-16)"
    ),
)
async def cancel_pt_package(
    pt_package_id: UUID,
    payload: PtPackageCancelRequest,
    request: Request,
    actor: Annotated[
        CurrentUser,
        Depends(require_permission(Action.CANCEL, Resource.PT_PACKAGES)),
    ],
    _csrf: Annotated[None, Depends(verify_csrf)],
    idempotency_key: Annotated[str, Depends(verify_idempotency)],
    redis: Annotated[Redis, Depends(get_redis)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> Response:
    """Cancel a PT-package without refund (PT-08 / D-33-10).

    (CANCEL, PT_PACKAGES) IS in OWNER_ONLY (Phase 30 INFRA-19) — reception
    receives 403 from the RBAC gate BEFORE any side effect.

    RBAC-04 ordering: auth → require_permission → verify_csrf →
    verify_idempotency → get_db. Two-phase Redis claim + replay pattern
    mirrors ``create_pt_package`` verbatim so same-Idempotency-Key replay
    returns the cached envelope WITHOUT a second audit emit.

    Error surface (service layer):
      - 404 pt_package_not_found  (missing instance).
      - 409 invalid_transition    (cancelled source — FSM terminal).
      - 422 (schema layer)        (extra field / empty reason / >200 chars).
    """
    incoming_body = await request.body()
    incoming_hash = body_sha256(incoming_body)

    # Idempotency replay branch — return cached envelope verbatim or surface
    # 422 idempotency_key_reuse / 409 idempotency_in_flight per D-33-16.
    stored = await load_idempotency_response(redis, idempotency_key)
    if stored is not None:
        if isinstance(stored, str):
            raise ConflictError("idempotency_in_flight")
        if stored["body_hash"] != incoming_hash:
            raise ValidationAppError("idempotency_key_reuse")
        return Response(
            content=base64.b64decode(stored["body_b64"]),
            status_code=stored["status_code"],
            media_type="application/json",
        )

    # First call for this key — run the cancel orchestrator.
    pt_package = await service.cancel_pt_package(session, actor, pt_package_id, payload)
    response_envelope = envelope(pt_package)
    body_bytes = json.dumps(
        response_envelope.model_dump(mode="json", by_alias=True),
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    envelope_json = json.dumps(
        {
            "status_code": status.HTTP_200_OK,
            "body_hash": incoming_hash,
            "body_b64": base64.b64encode(body_bytes).decode("ascii"),
        },
        separators=(",", ":"),
        ensure_ascii=False,
    )
    await redis.set(
        f"{IDEMPOTENCY_REDIS_PREFIX}{idempotency_key}",
        envelope_json,
        ex=IDEMPOTENCY_TTL_SECONDS,
    )
    return Response(
        content=body_bytes,
        status_code=status.HTTP_200_OK,
        media_type="application/json",
    )


@pt_packages_router.post(
    "/{pt_package_id}/refund",
    response_model=ResponseEnvelope[PtPackageResponse],
    status_code=status.HTTP_200_OK,
    summary=(
        "Refund a PT-package (reception+owner per B-07; "
        "404 pt_package_not_found / original_payment_not_found; "
        "409 invalid_transition / already_refunded; requires Idempotency-Key — D-33-16)"
    ),
)
async def refund_pt_package(
    pt_package_id: UUID,
    payload: PtPackageRefundRequest,
    request: Request,
    actor: Annotated[
        CurrentUser,
        Depends(require_permission(Action.REFUND, Resource.PT_PACKAGES)),
    ],
    _csrf: Annotated[None, Depends(verify_csrf)],
    idempotency_key: Annotated[str, Depends(verify_idempotency)],
    redis: Annotated[Redis, Depends(get_redis)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> Response:
    """Refund a PT-package (REF-02 / PT-13 / D-33-11).

    (REFUND, PT_PACKAGES) is NOT in OWNER_ONLY per B-07 — reception+owner can
    both refund (uniform-reception RBAC). RBAC-04 ordering: auth →
    require_permission → verify_csrf → verify_idempotency → get_db.

    Subject-side endpoint per D-33-18 (lives in pt_packages/router.py, NOT
    payments/router.py). Cross-module communication via the
    ``get_payment_refunder()`` Protocol slot — service layer NEVER imports
    ``app.modules.payments.*`` (modules-independent contract).

    Error surface:
      - 404 pt_package_not_found        (missing instance).
      - 404 original_payment_not_found  (no sale payment row — should not
                                        occur in v1.4 since PT-packages
                                        are introduced in Phase 33 with sale
                                        flow; defence-in-depth for parity
                                        with memberships).
      - 409 invalid_transition          (cancelled source — FSM terminal;
                                        fires BEFORE the refunder so the
                                        already-cancelled case never reaches
                                        the DB partial UNIQUE).
      - 409 already_refunded            (concurrent race on
                                        uq_payments_refund_of_alive partial
                                        UNIQUE — REF-TEST-02 exhaustive
                                        race coverage).
      - 422 (schema layer)              (extra field / empty reason /
                                        >200 chars).

    Idempotency-Key is REQUIRED per D-33-16 — uniform with the sale + cancel
    surfaces (all 3 mutating PT-package POSTs accept Idempotency-Key for
    operator UX consistency, beyond the DB partial UNIQUE which is the
    load-bearing race defence on its own).
    """
    incoming_body = await request.body()
    incoming_hash = body_sha256(incoming_body)

    # Idempotency replay branch — return cached envelope verbatim.
    stored = await load_idempotency_response(redis, idempotency_key)
    if stored is not None:
        if isinstance(stored, str):
            raise ConflictError("idempotency_in_flight")
        if stored["body_hash"] != incoming_hash:
            raise ValidationAppError("idempotency_key_reuse")
        return Response(
            content=base64.b64decode(stored["body_b64"]),
            status_code=stored["status_code"],
            media_type="application/json",
        )

    # First call for this key — run the refund orchestrator. Concurrent
    # callers race on the DB partial UNIQUE uq_payments_refund_of_alive;
    # exactly one wins with 200 + the others surface 409 already_refunded
    # via the refunder's discriminator path (REF-TEST-02).
    pt_package = await service.refund_pt_package(session, actor, pt_package_id, payload)
    response_envelope = envelope(pt_package)
    body_bytes = json.dumps(
        response_envelope.model_dump(mode="json", by_alias=True),
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    envelope_json = json.dumps(
        {
            "status_code": status.HTTP_200_OK,
            "body_hash": incoming_hash,
            "body_b64": base64.b64encode(body_bytes).decode("ascii"),
        },
        separators=(",", ":"),
        ensure_ascii=False,
    )
    await redis.set(
        f"{IDEMPOTENCY_REDIS_PREFIX}{idempotency_key}",
        envelope_json,
        ex=IDEMPOTENCY_TTL_SECONDS,
    )
    return Response(
        content=body_bytes,
        status_code=status.HTTP_200_OK,
        media_type="application/json",
    )
