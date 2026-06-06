"""Notifications client-portal endpoints (Phase 87 INBOX-01/INBOX-02).

Mounted under /api/v1/client via a dedicated notifications_router — this avoids
a client_portal→notifications cross-module edge (D-20-MODULE; mirrors loyalty_router
separation pattern at v1/router.py).

Endpoints:
  GET  /api/v1/client/notifications               → ClientNotificationsListResponse (paginated)
  PATCH /api/v1/client/notifications/read-all     → 204 No Content
  PATCH /api/v1/client/notifications/{id}/read    → ClientNotificationItem
  POST  /api/v1/client/push-tokens                → 204 No Content

All mutation endpoints are RBAC-04 ordered:
  require_client() → verify_client_csrf → get_db

IDOR safety: client_id comes from require_client() ClientPrincipal only — never
from URL parameters or request body (D-20-IDOR / T-87-06 / T-87-07).

No try/except — AppError bubbles to _app_error_handler.
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import ClientPrincipal, require_client, verify_client_csrf
from app.core.pagination import PageQuery
from app.core.schemas import ResponseEnvelope, envelope
from app.modules.notifications import service
from app.modules.notifications.schemas import (
    ClientNotificationItem,
    ClientNotificationsListResponse,
    ClientPushTokenRegisterRequest,
)

router = APIRouter(tags=["Client-Portal"])


@router.get(
    "/notifications",
    response_model=ResponseEnvelope[ClientNotificationsListResponse],
    operation_id="client_list_notifications",
    summary=(
        "Paginated notification inbox for the authenticated client (INBOX-01; "
        "IDOR-safe; newest-first; includes unreadCount)"
    ),
)
async def client_list_notifications(
    query: Annotated[PageQuery, Depends()],
    client: Annotated[ClientPrincipal, Depends(require_client())],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ResponseEnvelope[ClientNotificationsListResponse]:
    """Return paginated inbox rows newest-first with unreadCount (INBOX-01).

    D-20-IDOR: client_id from require_client() principal only — never from URL.
    No CSRF dep — GET is a safe method per RBAC-04.
    No try/except — AppError bubbles to _app_error_handler.
    No session.commit() — read path.
    """
    result = await service.list_client_notifications(session, client.id, query)
    return envelope(result)


# ROUTE ORDERING NOTE: /notifications/read-all declared BEFORE /notifications/{id}/read
# so the literal path segment "read-all" is not captured by the path-param route.


@router.patch(
    "/notifications/read-all",
    status_code=204,
    operation_id="client_mark_all_notifications_read",
    summary="Mark all unread notifications read for the authenticated client (INBOX-01)",
)
async def client_mark_all_notifications_read(
    client: Annotated[ClientPrincipal, Depends(require_client())],
    _csrf: Annotated[None, Depends(verify_client_csrf)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> Response:
    """Bulk mark-read scoped to the calling client (INBOX-01).

    RBAC-04 ordering: require_client() → verify_client_csrf → get_db.
    T-87-06: client_id from principal only.
    No try/except — AppError bubbles to _app_error_handler.
    """
    await service.mark_all_notifications_read(session, client_id=client.id)
    await session.commit()
    return Response(status_code=204)


@router.patch(
    "/notifications/{notification_id}/read",
    response_model=ResponseEnvelope[ClientNotificationItem],
    operation_id="client_mark_notification_read",
    summary=(
        "Mark one notification read; 404-collapses on non-owned or absent id (INBOX-01; "
        "IDOR-safe via T-87-07)"
    ),
)
async def client_mark_notification_read(
    notification_id: UUID,
    client: Annotated[ClientPrincipal, Depends(require_client())],
    _csrf: Annotated[None, Depends(verify_client_csrf)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ResponseEnvelope[ClientNotificationItem]:
    """Mark a single notification read; 404-collapse on non-owned rows (INBOX-01).

    IDOR (T-87-07): UPDATE scoped by (client_id, notification_id) — caller cannot
    distinguish "wrong owner" from "already read" from "id doesn't exist" (404-collapse).
    notification_id from path only. client_id from require_client() principal ONLY.
    RBAC-04 ordering: require_client() → verify_client_csrf → get_db.
    No try/except — AppError (including NotFoundError → 404) bubbles to _app_error_handler.
    """
    result = await service.mark_notification_read(
        session,
        client_id=client.id,
        notification_id=notification_id,
    )
    await session.commit()
    return envelope(result)


@router.post(
    "/push-tokens",
    status_code=204,
    operation_id="client_register_push_token",
    summary=(
        "Register (or revive) a push token for the authenticated client (INBOX-02; "
        "idempotent; no token echoed — T-87-08)"
    ),
)
async def client_register_push_token(
    payload: ClientPushTokenRegisterRequest,
    client: Annotated[ClientPrincipal, Depends(require_client())],
    _csrf: Annotated[None, Depends(verify_client_csrf)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> Response:
    """Idempotent push-token upsert; returns 204 with no body (INBOX-02).

    T-87-08: response body MUST NOT echo the token.
    T-87-09: extra='forbid' (ClientPushTokenRegisterRequest base) → 422 on unknown fields.
    platform constrained to web/android/ios by DB CheckConstraint (T-87-09).
    RBAC-04 ordering: require_client() → verify_client_csrf → get_db.
    client_id from principal only (D-20-IDOR).
    No try/except — AppError bubbles to _app_error_handler.
    """
    await service.register_push_token(session, client_id=client.id, payload=payload)
    await session.commit()
    return Response(status_code=204)
