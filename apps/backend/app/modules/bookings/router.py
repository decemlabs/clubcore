"""Bookings module HTTP router — /bookings surface (Phase 38 plan 38-02).

Plan 38-02 ships ONLY the create endpoint. List + cancel endpoints land in
plan 38-03 (forward-link forensic chain: future plan 38-03 grep
`/api/v1/bookings` here to find the integration point).

RBAC mapping (Phase 37 INFRA-27 / D-37-02-03):
- POST /bookings → (CREATE, BOOKINGS) reception+owner (NOT in OWNER_ONLY —
  reception books per D-38-09 gym-staff trust model).

RBAC-04 ordering: `Depends(require_permission(...))` BEFORE
`Depends(verify_csrf)` on every mutation endpoint.
`tests/integration/test_route_introspection.py` enforces statically.

Idempotency (D-38-14 / Pitfall 14):
- POST /bookings requires `Idempotency-Key` header via
  `Depends(verify_idempotency)`. The two-phase Redis claim + replay block is
  copied verbatim from `pt_sessions/router.py:116-157` (CR-02 from Phase 33
  review). The race test BOOK-TEST-01 uses DISTINCT idempotency keys so the
  race surfaces at the DB partial UNIQUE (`uq_bookings_slot_confirmed`),
  NOT at the Redis cache.
"""

import base64
import json
from typing import Annotated

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
from app.core.permissions import Action, Resource
from app.core.redis import get_redis
from app.core.schemas import ResponseEnvelope, envelope
from app.modules.bookings import service
from app.modules.bookings.schemas import BookingCreateRequest, BookingResponse

bookings_router = APIRouter()


@bookings_router.post(
    "",
    response_model=ResponseEnvelope[BookingResponse],
    status_code=status.HTTP_201_CREATED,
    summary=(
        "Create a confirmed booking (reception+owner; "
        "404 slot_not_found; "
        "409 slot_not_available / slot_already_booked / trainer_mismatch / "
        "pt_package_not_active / pt_package_exhausted / "
        "pt_package_expired_before_slot; "
        "requires Idempotency-Key — D-38-14)"
    ),
)
async def create_booking(
    payload: BookingCreateRequest,
    request: Request,
    actor: Annotated[
        CurrentUser,
        Depends(require_permission(Action.CREATE, Resource.BOOKINGS)),
    ],
    _csrf: Annotated[None, Depends(verify_csrf)],
    idempotency_key: Annotated[str, Depends(verify_idempotency)],
    redis: Annotated[Redis, Depends(get_redis)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> Response:
    """Create a confirmed booking (Phase 38 BOOK-02).

    `(CREATE, BOOKINGS)` is NOT in `OWNER_ONLY` (Phase 37 INFRA-27) —
    reception+owner both pass the RBAC gate per D-38-09 (gym-staff trust
    model; audit records actor_user_id for accountability).

    RBAC-04 ordering: auth → require_permission → verify_csrf →
    verify_idempotency → get_db.

    Two-phase Redis claim + replay (CR-02 from Phase 33 review): SET NX
    claims the key with an in-flight placeholder so concurrent callers
    carrying the SAME Idempotency-Key cannot both pass the "no stored
    entry" gate and double-execute the orchestrator (which would attempt
    two slot UPDATE active→booked + two booking INSERTs — the second
    would be caught by the partial UNIQUE, but the cost is paid).

    Error surface (service layer):
      - 404 slot_not_found.
      - 409 slot_not_available (slot status != 'active' before INSERT).
      - 409 slot_already_booked (DB race-loser via partial UNIQUE — BOOK-10).
      - 409 trainer_mismatch (pt_package.trainer_id != slot.trainer_id).
      - 409 pt_package_not_active (no active package for client or id mismatch).
      - 409 pt_package_exhausted (sessions_remaining <= 0).
      - 409 pt_package_expired_before_slot (Moscow-TZ validity-window guard).
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

    booking = await service.create_booking(session, actor, payload)
    response_envelope = envelope(booking)
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
