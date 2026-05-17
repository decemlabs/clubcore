"""Schedule module HTTP router — /trainer-slots surface (Phase 38 plan 38-01).

RBAC mapping (Phase 37 INFRA-27 / D-37-02-03):
- POST /trainer-slots               → (CREATE, SCHEDULE_SLOTS) owner-only
- POST /trainer-slots/{id}/cancel   → (CANCEL, SCHEDULE_SLOTS) owner-only
- GET  /trainer-slots               → (LIST,   SCHEDULE_SLOTS) reception+owner
- GET  /trainer-slots/{id}          → (VIEW,   SCHEDULE_SLOTS) reception+owner

RBAC-04 ordering: `Depends(require_permission(...))` BEFORE `Depends(verify_csrf)`
on every mutation endpoint. `tests/integration/test_route_introspection.py`
enforces statically.

Idempotency:
- Both mutating endpoints (POST publish / POST cancel) require `Idempotency-Key`
  per D-38-14 / Pitfall 14, using the verbatim two-phase Redis claim + replay
  block from `pt_sessions/router.py:116-157` (CR-02 from Phase 33 review).
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
from app.modules.schedule import service
from app.modules.schedule.schemas import (
    SlotCancelRequest,
    SlotCreateRequest,
    SlotListQuery,
    SlotResponse,
)

schedule_router = APIRouter()


@schedule_router.post(
    "",
    response_model=ResponseEnvelope[SlotResponse],
    status_code=status.HTTP_201_CREATED,
    summary=(
        "Publish a trainer availability slot (owner-only; "
        "409 slot_overlap / slot_too_close / slot_in_past / "
        "trainer_inactive / trainer_not_found; requires Idempotency-Key — D-38-14)"
    ),
)
async def publish_slot(
    payload: SlotCreateRequest,
    request: Request,
    actor: Annotated[
        CurrentUser,
        Depends(require_permission(Action.CREATE, Resource.SCHEDULE_SLOTS)),
    ],
    _csrf: Annotated[None, Depends(verify_csrf)],
    idempotency_key: Annotated[str, Depends(verify_idempotency)],
    redis: Annotated[Redis, Depends(get_redis)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> Response:
    """Publish a trainer availability slot (Phase 38 SLOT-02).

    (CREATE, SCHEDULE_SLOTS) IS in OWNER_ONLY (Phase 37 INFRA-27) — reception
    receives 403 from the RBAC gate BEFORE any side effect. Two-phase Redis
    claim + replay (CR-02 from Phase 33 review) closes the same-key race.

    Error surface (service layer):
      - 404 trainer_not_found       (no such trainer id)
      - 409 trainer_inactive        (trainer.is_active=False)
      - 409 slot_in_past            (start_time <= now() UTC)
      - 409 slot_overlap            (overlap with non-cancelled slot, same trainer)
      - 409 slot_too_close          (gap < SLOT_BUFFER_MINUTES, discriminated)
      - 422 idempotency_key_reuse   (same key, different body)
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

    slot = await service.publish_slot(session, actor, payload)
    response_envelope = envelope(slot)
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


@schedule_router.get(
    "",
    response_model=ResponseEnvelope[PaginatedData[SlotResponse]],
    summary="List trainer slots (reception+owner; paginated; trainer/status/time-window filters)",
)
async def list_slots(
    query: Annotated[SlotListQuery, Depends()],
    _actor: Annotated[
        CurrentUser,
        Depends(require_permission(Action.LIST, Resource.SCHEDULE_SLOTS)),
    ],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ResponseEnvelope[PaginatedData[SlotResponse]]:
    """Paginated slot list (SLOT-08 read tier).

    (LIST, SCHEDULE_SLOTS) is NOT in OWNER_ONLY — reception sees the same
    list as owner (slot picker for booking flow). Default window is bounded
    to 14 days forward (T-38-01-04 mitigation — prevents unbounded
    enumeration).
    """
    page = await service.list_slots(session, query)
    return envelope(page)


@schedule_router.get(
    "/{slot_id}",
    response_model=ResponseEnvelope[SlotResponse],
    summary="Read a single trainer slot (reception+owner; 404 slot_not_found)",
)
async def get_slot(
    slot_id: UUID,
    _actor: Annotated[
        CurrentUser,
        Depends(require_permission(Action.VIEW, Resource.SCHEDULE_SLOTS)),
    ],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ResponseEnvelope[SlotResponse]:
    """Read a single slot (SLOT-08 detail). 404 slot_not_found for missing id."""
    slot = await service.get_slot(session, slot_id)
    return envelope(slot)


@schedule_router.post(
    "/{slot_id}/cancel",
    response_model=ResponseEnvelope[SlotResponse],
    status_code=status.HTTP_200_OK,
    summary=(
        "Cancel a trainer slot (owner-only; 404 slot_not_found; "
        "409 invalid_transition for cancelled source or booked-cascade "
        "deferred to 38-03; requires Idempotency-Key — D-38-14)"
    ),
)
async def cancel_slot(
    slot_id: UUID,
    payload: SlotCancelRequest,
    request: Request,
    actor: Annotated[
        CurrentUser,
        Depends(require_permission(Action.CANCEL, Resource.SCHEDULE_SLOTS)),
    ],
    _csrf: Annotated[None, Depends(verify_csrf)],
    idempotency_key: Annotated[str, Depends(verify_idempotency)],
    redis: Annotated[Redis, Depends(get_redis)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> Response:
    """Cancel a trainer slot (SLOT-09 — active-only path in plan 38-01).

    For Phase 38 plan 38-01: only the `active → cancelled` transition is
    supported. Cancelling a `booked` slot triggers the booked-cascade flow
    which lands in plan 38-03 (it must atomically cancel the linked confirmed
    booking + emit both `slot_cancelled` and `booking_cancelled`). In this
    plan, attempting to cancel a booked slot raises
    `InvalidSlotTransitionError` (409 `invalid_transition`) with an explicit
    forward-link message.

    (CANCEL, SCHEDULE_SLOTS) IS in OWNER_ONLY — reception receives 403.
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

    slot = await service.cancel_slot(session, actor, slot_id, payload)
    response_envelope = envelope(slot)
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
