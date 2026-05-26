"""PT-sessions HTTP router (Phase 34 D-34-08).

Two `APIRouter` instances are exported here:

- `pt_sessions_router` — mounted at `/api/v1/pt-sessions` by the v1
  aggregator (`app.api.v1.router`). Hosts POST `/pt-sessions` (record —
  Plan 34-02), POST `/pt-sessions/{id}/cancel` + GET `/pt-sessions/{id}`
  (Plan 34-03).
- `package_scoped_router` — mounted at `/api/v1/pt-packages` so the
  single nested endpoint `GET /pt-packages/{id}/sessions` (PT-19 / Plan
  34-03) lives alongside its sibling pt-sessions handlers. Subject-side
  ownership principle (D-33-18): implementation lives with the entity
  that owns the data (pt_sessions), even though the URL path is rooted
  at the parent resource.

Plan 34-02 attaches the POST `/pt-sessions` record handler with the
verbatim two-phase Redis claim + replay Idempotency-Key pattern from
`pt_packages.router.create_pt_package` (D-34-10 / CR-02 from Phase 33
review — closes the gap where two concurrent record requests with the
same Idempotency-Key would emit two `pt_session_recorded` audit rows).

RBAC-04 ordering: ``Depends(require_permission(...))`` appears BEFORE
``Depends(verify_csrf)`` in every mutation endpoint signature
(``tests/integration/test_route_introspection.py`` enforces statically).
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
    begin_idempotency,
    body_sha256,
    load_idempotency_response,
    verify_idempotency,
)
from app.core.pagination import PaginatedData
from app.core.permissions import Action, Resource
from app.core.redis import get_redis
from app.core.schemas import ResponseEnvelope, envelope
from app.modules.pt_sessions import service
from app.modules.pt_sessions.schemas import (
    PtSessionCancelRequest,
    PtSessionCreateRequest,
    PtSessionListByPackageQuery,
    PtSessionResponse,
)

pt_sessions_router = APIRouter(tags=["Payments"])
package_scoped_router = APIRouter(tags=["Payments"])


@pt_sessions_router.post(
    "",
    response_model=ResponseEnvelope[PtSessionResponse],
    status_code=status.HTTP_201_CREATED,
    summary=(
        "Record a PT-session (reception+owner; "
        "404 pt_package_not_found / trainer_not_found; "
        "409 pt_package_not_active / pt_package_exhausted; "
        "422 trainer_inactive / performed_at_in_future / "
        "performed_at_out_of_window / idempotency_key_reuse; "
        "requires Idempotency-Key — D-34-10)"
    ),
)
async def record_pt_session(
    payload: PtSessionCreateRequest,
    request: Request,
    actor: Annotated[
        CurrentUser,
        Depends(require_permission(Action.CREATE, Resource.PT_SESSIONS)),
    ],
    _csrf: Annotated[None, Depends(verify_csrf)],
    idempotency_key: Annotated[str, Depends(verify_idempotency)],
    redis: Annotated[Redis, Depends(get_redis)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> Response:
    """Record a PT-session (PT-15 / PT-16 / PT-17).

    (CREATE, PT_SESSIONS) is NOT in OWNER_ONLY (Phase 30 INFRA-19) —
    reception + owner both receive 201 from the RBAC gate. The 7-day
    backdating window (B-11) is enforced application-layer in
    ``service.record_pt_session`` and surfaces as 422
    ``performed_at_out_of_window`` for reception.

    RBAC-04 ordering: auth → require_permission → verify_csrf →
    verify_idempotency → get_db.

    Two-phase Redis claim + replay (CR-02 from Phase 33 review): SET NX
    claims the key with an in-flight placeholder so concurrent callers
    carrying the SAME Idempotency-Key cannot both pass the "no stored
    entry" gate and double-execute the orchestrator (which would emit
    two pt_session_recorded audit rows AND decrement
    sessions_remaining twice). The losing caller falls into the replay
    branch and either gets the cached envelope (matching body) or 409
    ``idempotency_in_flight`` (placeholder still set).

    Error surface (service layer):
      - 404 pt_package_not_found / trainer_not_found.
      - 409 pt_package_not_active (pre-decrement guard fires first).
      - 409 pt_package_exhausted (race-loser at atomic UPDATE).
      - 422 trainer_inactive / performed_at_in_future /
        performed_at_out_of_window.
      - 422 idempotency_key_reuse (same key, different body).
    """
    incoming_body = await request.body()
    incoming_hash = body_sha256(incoming_body)

    is_first = await begin_idempotency(redis, idempotency_key)
    if not is_first:
        stored = await load_idempotency_response(redis, idempotency_key)
        if stored is None or isinstance(stored, str):
            raise ConflictError("idempotency_in_flight")
        if stored["body_hash"] != incoming_hash:
            raise ValidationAppError("idempotency_key_reuse")
        return Response(
            content=base64.b64decode(stored["body_b64"]),
            status_code=stored["status_code"],
            media_type="application/json",
        )

    pt_session = await service.record_pt_session(session, actor, payload)
    response_envelope = envelope(pt_session)
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


# ---------------------------------------------------------------------------
# Plan 34-03 — Cancel + read endpoints (PT-18 / PT-19).
# ---------------------------------------------------------------------------


@pt_sessions_router.post(
    "/{pt_session_id}/cancel",
    response_model=ResponseEnvelope[PtSessionResponse],
    status_code=status.HTTP_200_OK,
    summary=(
        "Cancel a recorded PT-session (reception ≤24h since recording per B-12 / "
        "owner anytime; 404 pt_session_not_found; 409 already_cancelled; "
        "403 cancel_window_expired; requires Idempotency-Key — D-34-10)"
    ),
)
async def cancel_pt_session(
    pt_session_id: UUID,
    payload: PtSessionCancelRequest,
    request: Request,
    actor: Annotated[
        CurrentUser,
        Depends(require_permission(Action.CANCEL, Resource.PT_SESSIONS)),
    ],
    _csrf: Annotated[None, Depends(verify_csrf)],
    idempotency_key: Annotated[str, Depends(verify_idempotency)],
    redis: Annotated[Redis, Depends(get_redis)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> Response:
    """Cancel a recorded PT-session (PT-18 / D-34-07 / D-34-11a).

    `(CANCEL, PT_SESSIONS)` is NOT in `OWNER_ONLY` (Plan 34-01 removed it) —
    reception + owner both pass the RBAC gate. The 24h cancel-window (B-12,
    measured from `pt_session.created_at`, NOT `performed_at` per D-34-07)
    is enforced application-layer in `service.cancel_pt_session` and surfaces
    as 403 `cancel_window_expired` for reception. Owner is anytime.

    RBAC-04 ordering: auth → require_permission → verify_csrf →
    verify_idempotency → get_db.

    Two-phase Redis claim + replay (CR-02 from Phase 33 review): SET NX
    claims the key with an in-flight placeholder so concurrent callers
    carrying the SAME Idempotency-Key cannot both pass the "no stored
    entry" gate and double-execute the orchestrator (which would emit
    two `pt_session_cancelled` audit rows AND increment
    `sessions_remaining` twice).

    Error surface (service layer):
      - 404 pt_session_not_found.
      - 409 already_cancelled.
      - 403 cancel_window_expired (reception >24h since created_at).
      - 422 idempotency_key_reuse (same key, different body).
    """
    incoming_body = await request.body()
    incoming_hash = body_sha256(incoming_body)

    is_first = await begin_idempotency(redis, idempotency_key)
    if not is_first:
        stored = await load_idempotency_response(redis, idempotency_key)
        if stored is None or isinstance(stored, str):
            raise ConflictError("idempotency_in_flight")
        if stored["body_hash"] != incoming_hash:
            raise ValidationAppError("idempotency_key_reuse")
        return Response(
            content=base64.b64decode(stored["body_b64"]),
            status_code=stored["status_code"],
            media_type="application/json",
        )

    pt_session = await service.cancel_pt_session(session, actor, pt_session_id, payload)
    response_envelope = envelope(pt_session)
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


@pt_sessions_router.get(
    "/{pt_session_id}",
    response_model=ResponseEnvelope[PtSessionResponse],
    summary="Read a single PT-session (reception+owner; 404 pt_session_not_found)",
)
async def get_pt_session(
    pt_session_id: UUID,
    _actor: Annotated[
        CurrentUser,
        Depends(require_permission(Action.VIEW, Resource.PT_SESSIONS)),
    ],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ResponseEnvelope[PtSessionResponse]:
    """Read a single PT-session row (PT-19 read tier).

    Reception + owner both pass (single-zone CRM, T-34-M accepted). Returns
    404 `pt_session_not_found` if the id is unknown.
    """
    return envelope(await service.get_pt_session(session, pt_session_id))


@package_scoped_router.get(
    "/{pt_package_id}/sessions",
    response_model=ResponseEnvelope[PaginatedData[PtSessionResponse]],
    summary=(
        "List PT-sessions for a package (reception+owner; paginated; "
        "?includeCancelled filter; performed_at DESC, created_at DESC)"
    ),
)
async def list_sessions_by_pt_package(
    pt_package_id: UUID,
    query: Annotated[PtSessionListByPackageQuery, Depends()],
    _actor: Annotated[
        CurrentUser,
        Depends(require_permission(Action.VIEW, Resource.PT_SESSIONS)),
    ],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ResponseEnvelope[PaginatedData[PtSessionResponse]]:
    """Paginated PT-session history for a package (PT-19 / D-34-08).

    Subject-side ownership (D-33-18): implementation lives in the
    `pt_sessions` module even though the URL path is rooted at
    `/pt-packages/{id}/sessions`. The `package_scoped_router` is
    mounted at `/api/v1/pt-packages` by `app.api.v1.router`.

    Returns the standard `{items, total, page, pageSize}` envelope ordered
    `performed_at DESC, created_at DESC, id DESC`. The `include_cancelled`
    query param (camelCase `?includeCancelled`) defaults to `true`.
    Returns `items=[], total=0` for unknown `pt_package_id` (no 404 —
    package-existence check is out of scope for list endpoints per
    `pt_packages` list precedent).
    """
    page = await service.list_sessions_by_pt_package(session, pt_package_id, query)
    return envelope(page)
