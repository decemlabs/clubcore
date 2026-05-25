"""Schedule module HTTP router — /trainer-slots, /recurring-templates, /time-off surfaces.

Phase 38 plan 38-01 — /trainer-slots (original):
RBAC mapping (Phase 37 INFRA-27 / D-37-02-03):
- POST  /trainer-slots               → (CREATE, SCHEDULE_SLOTS) owner-only
- PATCH /trainer-slots/{id}/cancel   → (CANCEL, SCHEDULE_SLOTS) owner-only
- GET  /trainer-slots               → (LIST,   SCHEDULE_SLOTS) reception+owner
- GET  /trainer-slots/{id}          → (VIEW,   SCHEDULE_SLOTS) reception+owner

Phase 59 plan 59-04 — /recurring-templates + /time-off (new):
RBAC mapping (D-59-08 — reuses existing SCHEDULE_SLOTS pairs; NO new pairs):
- POST /recurring-templates                    → (CREATE, SCHEDULE_SLOTS) owner-only
- POST /recurring-templates/{id}/deactivate   → (CANCEL, SCHEDULE_SLOTS) owner-only
- GET  /recurring-templates                   → (LIST,   SCHEDULE_SLOTS) reception+owner
- POST /time-off                              → (CREATE, SCHEDULE_SLOTS) owner-only
- DELETE /time-off/{id}                       → (DELETE, SCHEDULE_SLOTS) owner-only
- GET  /time-off                              → (LIST,   SCHEDULE_SLOTS) reception+owner

RBAC-04 ordering: `Depends(require_permission(...))` BEFORE `Depends(verify_csrf)`
on every mutation endpoint. `tests/integration/test_route_introspection.py`
enforces statically.

Idempotency:
- All mutating endpoints require `Idempotency-Key` per D-38-14 / Pitfall 14,
  using the verbatim two-phase Redis claim + replay block from
  `pt_sessions/router.py:116-157` (CR-02 from Phase 33 review).
"""

import base64
import json
from typing import Annotated
from uuid import UUID

from fastapi import Query

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
    RecurringSlotTemplateCreate,
    RecurringSlotTemplateResponse,
    SlotCancelRequest,
    SlotCreateRequest,
    SlotListQuery,
    SlotResponse,
    TimeOffCreate,
    TimeOffConflictDetail,
    TimeOffResponse,
)

schedule_router = APIRouter()
recurring_templates_router = APIRouter()
time_off_router = APIRouter()


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


@schedule_router.patch(
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


# ===========================================================================
# Phase 59 REC-01 / REC-04 — Recurring slot template endpoints
# ===========================================================================


@recurring_templates_router.post(
    "",
    response_model=ResponseEnvelope[RecurringSlotTemplateResponse],
    status_code=status.HTTP_201_CREATED,
    summary=(
        "Create a recurring slot template (owner-only; "
        "409 recurring_template_duplicate on duplicate trainer+dow+start+valid_from; "
        "requires Idempotency-Key — D-38-14)"
    ),
)
async def create_recurring_template(
    payload: RecurringSlotTemplateCreate,
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
    """Create a recurring slot template (REC-01 / D-59-02).

    (CREATE, SCHEDULE_SLOTS) IS in OWNER_ONLY — reception 403.
    Two-phase Redis idempotency (D-38-14 / Pitfall 14).

    Error surface:
      - 409 recurring_template_duplicate  (UNIQUE trainer+dow+start+valid_from)
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

    tmpl = await service.create_recurring_template(session, actor, payload)
    response_envelope = envelope(tmpl)
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


@recurring_templates_router.post(
    "/{template_id}/deactivate",
    response_model=ResponseEnvelope[RecurringSlotTemplateResponse],
    status_code=status.HTTP_200_OK,
    summary=(
        "Deactivate a recurring slot template (owner-only; "
        "404 recurring_template_not_found; requires Idempotency-Key)"
    ),
)
async def deactivate_recurring_template(
    template_id: UUID,
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
    """Flip is_active=False on a recurring template (REC-01 deactivate).

    (CANCEL, SCHEDULE_SLOTS) IS in OWNER_ONLY — reception 403.
    Forward-only: does not cancel materialized slots.
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

    tmpl = await service.deactivate_recurring_template(session, actor, template_id)
    response_envelope = envelope(tmpl)
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


@recurring_templates_router.get(
    "",
    response_model=ResponseEnvelope[PaginatedData[RecurringSlotTemplateResponse]],
    summary="List recurring slot templates (reception+owner; trainer_id filter)",
)
async def list_recurring_templates(
    _actor: Annotated[
        CurrentUser,
        Depends(require_permission(Action.LIST, Resource.SCHEDULE_SLOTS)),
    ],
    session: Annotated[AsyncSession, Depends(get_db)],
    trainer_id: Annotated[UUID | None, Query(alias="trainerId")] = None,
    page: int = 1,
    page_size: int = 20,
) -> ResponseEnvelope[PaginatedData[RecurringSlotTemplateResponse]]:
    """List recurring templates (REC-04 — both roles).

    (LIST, SCHEDULE_SLOTS) NOT in OWNER_ONLY — reception sees same list.
    """
    page_data = await service.list_recurring_templates(
        session,
        trainer_id=trainer_id,
        page=page,
        page_size=page_size,
    )
    return envelope(page_data)


# ===========================================================================
# Phase 59 REC-03 / REC-04 — Trainer time-off endpoints
# ===========================================================================


@time_off_router.post(
    "",
    response_model=ResponseEnvelope[TimeOffResponse],
    status_code=status.HTTP_201_CREATED,
    summary=(
        "Create a trainer time-off block (owner-only; "
        "409 time_off_booked_conflict when booked slots overlap and ?force not set; "
        "?force=true cascades booking cancellations + client DMs; "
        "requires Idempotency-Key — D-38-14)"
    ),
)
async def create_time_off(
    payload: TimeOffCreate,
    request: Request,
    actor: Annotated[
        CurrentUser,
        Depends(require_permission(Action.CREATE, Resource.SCHEDULE_SLOTS)),
    ],
    _csrf: Annotated[None, Depends(verify_csrf)],
    idempotency_key: Annotated[str, Depends(verify_idempotency)],
    redis: Annotated[Redis, Depends(get_redis)],
    session: Annotated[AsyncSession, Depends(get_db)],
    force: bool = False,
) -> Response:
    """Create a trainer time-off block (REC-03 / D-59-06 LOCKED semantics).

    (CREATE, SCHEDULE_SLOTS) IS in OWNER_ONLY — reception 403 (on both
    force=true and force=false — threat model T-59-09).

    Error surface:
      - 409 time_off_booked_conflict  (booked slots overlap and force=False)
    """
    from fastapi.responses import JSONResponse

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

    try:
        time_off = await service.create_time_off(session, actor, payload, force=force)
    except service.TimeOffBookedConflictError as exc:
        # Map typed conflict to 409 with TimeOffConflictDetail body.
        # exc.fields is dict[str, object] | None per AppError signature.
        # The service serialises UUID strings into "conflicting_slot_ids" / "conflicting_booking_ids".
        from typing import cast as _cast

        exc_fields: dict[str, object] = exc.fields or {}
        raw_slot_ids = _cast(list[str], exc_fields.get("conflicting_slot_ids") or [])
        raw_booking_ids = _cast(list[str], exc_fields.get("conflicting_booking_ids") or [])
        conflict_detail = TimeOffConflictDetail(
            conflicting_slot_ids=[UUID(s) for s in raw_slot_ids],
            conflicting_booking_ids=[UUID(s) for s in raw_booking_ids],
        )
        return JSONResponse(
            status_code=409,
            content={
                "code": exc.code,
                "message": exc.message,
                "fields": exc.fields,
                "data": conflict_detail.model_dump(mode="json", by_alias=True),
            },
        )

    response_envelope = envelope(time_off)
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


@time_off_router.delete(
    "/{time_off_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary=(
        "Delete a trainer time-off block (owner-only; "
        "404 time_off_not_found; forward-only — does not resurrect cancelled slots)"
    ),
)
async def delete_time_off(
    time_off_id: UUID,
    request: Request,
    actor: Annotated[
        CurrentUser,
        Depends(require_permission(Action.DELETE, Resource.SCHEDULE_SLOTS)),
    ],
    _csrf: Annotated[None, Depends(verify_csrf)],
    idempotency_key: Annotated[str, Depends(verify_idempotency)],
    redis: Annotated[Redis, Depends(get_redis)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> Response:
    """Delete a trainer time-off block (REC-03 delete / forward-only).

    (DELETE, SCHEDULE_SLOTS) IS in OWNER_ONLY — reception 403.
    Does NOT resurrect cancelled slots — next cron tick re-materializes new ones.
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
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    await service.delete_time_off(session, actor, time_off_id)
    envelope_json = json.dumps(
        {
            "status_code": status.HTTP_204_NO_CONTENT,
            "body_hash": incoming_hash,
            "body_b64": base64.b64encode(b"").decode("ascii"),
        },
        separators=(",", ":"),
        ensure_ascii=False,
    )
    await redis.set(
        f"{IDEMPOTENCY_REDIS_PREFIX}{idempotency_key}",
        envelope_json,
        ex=IDEMPOTENCY_TTL_SECONDS,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@time_off_router.get(
    "",
    response_model=ResponseEnvelope[PaginatedData[TimeOffResponse]],
    summary="List trainer time-off blocks (reception+owner; trainer_id filter)",
)
async def list_time_off(
    _actor: Annotated[
        CurrentUser,
        Depends(require_permission(Action.LIST, Resource.SCHEDULE_SLOTS)),
    ],
    session: Annotated[AsyncSession, Depends(get_db)],
    trainer_id: Annotated[UUID | None, Query(alias="trainerId")] = None,
    page: int = 1,
    page_size: int = 20,
) -> ResponseEnvelope[PaginatedData[TimeOffResponse]]:
    """List time-off blocks (REC-04 — both roles).

    (LIST, SCHEDULE_SLOTS) NOT in OWNER_ONLY — reception sees same list.
    """
    page_data = await service.list_time_off(
        session,
        trainer_id=trainer_id,
        page=page,
        page_size=page_size,
    )
    return envelope(page_data)
