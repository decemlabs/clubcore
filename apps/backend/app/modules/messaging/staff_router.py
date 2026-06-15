"""Staff messaging endpoints (Phase 116 MSG-01/MSG-02).

Mounted under /api/v1 via staff_messaging_router at prefix /messages — separate from
the client router at /api/v1/client (D-20-MODULE pattern; same split as notifications_router).

Endpoints:
  GET  /api/v1/messages/threads                    → StaffInboxResponse (both roles)
  GET  /api/v1/messages/threads/{thread_id}        → StaffThreadHistoryResponse (both roles)
  POST /api/v1/messages/threads/{thread_id}/reply  → StaffMessageItem (owner-only)
  POST /api/v1/messages/threads/{thread_id}/read   → 204 No Content (both roles)

RBAC-04 ordering: require_permission BEFORE verify_csrf on all mutation endpoints.
  (CREATE, MESSAGES) ∈ OWNER_ONLY → reception POST /reply → 403.
  (LIST, MESSAGES) and (VIEW, MESSAGES) NOT in OWNER_ONLY → reception can read.

Delivery: POST /reply reuses the existing publish_new_message after commit (CR-02 /
DB-first, P5). No forward_to_staff enqueue — staff sends go directly to the client WS
+ Telegram via the existing channel (that bridge is for client→staff direction only).

No try/except — AppError bubbles to _app_error_handler.
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Response, status
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import CurrentUser, require_permission, verify_csrf
from app.core.permissions import Action, Resource
from app.core.redis import get_redis
from app.core.schemas import ResponseEnvelope, envelope
from app.modules.messaging import service
from app.modules.messaging.repository import get_thread_client_id
from app.modules.messaging.schemas import (
    StaffInboxResponse,
    StaffMessageItem,
    StaffReplyRequest,
    StaffThreadHistoryResponse,
)

router = APIRouter(tags=["Messaging"])


@router.get(
    "/threads",
    response_model=ResponseEnvelope[StaffInboxResponse],
    operation_id="staff_list_threads",
    summary=(
        "Staff inbox: all client threads with unread counts (LIST, MESSAGES; both roles)"
    ),
)
async def staff_list_threads(
    _actor: Annotated[CurrentUser, Depends(require_permission(Action.LIST, Resource.MESSAGES))],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ResponseEnvelope[StaffInboxResponse]:
    """Return all client threads with per-thread staff unread count + last-message preview.

    Both roles (owner + reception) may list the inbox.
    No CSRF dep — GET is a safe method per RBAC-04.
    No try/except — AppError bubbles to _app_error_handler.
    No session.commit() — read path.
    """
    result = await service.list_threads(session)
    return envelope(result)


@router.get(
    "/threads/{thread_id}",
    response_model=ResponseEnvelope[StaffThreadHistoryResponse],
    operation_id="staff_get_thread",
    summary=(
        "Staff thread history: full message list for one thread (VIEW, MESSAGES; both roles)"
    ),
)
async def staff_get_thread(
    thread_id: UUID,
    _actor: Annotated[CurrentUser, Depends(require_permission(Action.VIEW, Resource.MESSAGES))],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ResponseEnvelope[StaffThreadHistoryResponse]:
    """Return full chronological message history for a client↔gym thread.

    Both roles (owner + reception) may view thread history.
    No CSRF dep — GET is a safe method per RBAC-04.
    No try/except — AppError bubbles to _app_error_handler.
    No session.commit() — read path.
    """
    result = await service.get_staff_thread(session, thread_id=thread_id)
    return envelope(result)


@router.post(
    "/threads/{thread_id}/reply",
    response_model=ResponseEnvelope[StaffMessageItem],
    operation_id="staff_send_reply",
    summary=(
        "Staff send reply to client thread (CREATE, MESSAGES; owner-only)"
    ),
)
async def staff_send_reply(
    thread_id: UUID,
    payload: StaffReplyRequest,
    # RBAC-04 ordering: require_permission BEFORE verify_csrf (T-116-02 + T-116-01).
    _actor: Annotated[CurrentUser, Depends(require_permission(Action.CREATE, Resource.MESSAGES))],
    _csrf: Annotated[None, Depends(verify_csrf)],
    session: Annotated[AsyncSession, Depends(get_db)],
    redis: Annotated[Redis, Depends(get_redis)],
) -> ResponseEnvelope[StaffMessageItem]:
    """Persist a staff reply and publish via the existing client delivery channel.

    (CREATE, MESSAGES) ∈ OWNER_ONLY → reception → 403 (T-116-01 mitigation).
    RBAC-04: require_permission declared BEFORE verify_csrf (T-116-02 mitigation —
    a forbidden reception never reaches the CSRF check).

    DB-first (CR-02 / P5): send_staff_reply persists but does NOT publish; the router
    commits FIRST, then calls publish_new_message so the notification frame is only
    emitted once the row is durable.

    Reuses record_staff_message which emits the message_sent audit co-transactionally.
    No forward_to_staff enqueue — staff→client direction uses the existing WS + Telegram
    channel; forward_to_staff is the client→staff bridge only.

    No try/except — AppError bubbles to _app_error_handler.
    """
    result = await service.send_staff_reply(session, thread_id=thread_id, payload=payload)

    # Resolve client_id for publish_new_message (needed post-commit — resolve before commit).
    client_id = await get_thread_client_id(session, thread_id)

    await session.commit()

    # CR-02: publish ONLY after the row is durable (post-commit).
    if client_id is not None:
        await service.publish_new_message(
            redis,
            client_id=client_id,
            message_id=result.id,
        )

    return envelope(result)


@router.post(
    "/threads/{thread_id}/read",
    status_code=status.HTTP_204_NO_CONTENT,
    operation_id="staff_mark_thread_read",
    summary=(
        "Reset staff-side unread watermark for thread (VIEW, MESSAGES; both roles)"
    ),
)
async def staff_mark_thread_read(
    thread_id: UUID,
    # RBAC-04 ordering: require_permission BEFORE verify_csrf (T-116-02 mitigation).
    _actor: Annotated[CurrentUser, Depends(require_permission(Action.VIEW, Resource.MESSAGES))],
    _csrf: Annotated[None, Depends(verify_csrf)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> Response:
    """Set staff_last_read_at = now() so next inbox fetch shows staffUnreadCount = 0.

    Both roles (owner + reception) may mark-read — inbox is readable by both.
    RBAC-04: require_permission before verify_csrf.
    No try/except — AppError bubbles to _app_error_handler.
    """
    await service.mark_staff_thread_read(session, thread_id=thread_id)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
