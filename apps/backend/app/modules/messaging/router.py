"""Messaging client-portal endpoints (Phase 90 MSG-01..04 + RT-01..04).

Mounted under /api/v1/client via a dedicated messaging_router — this avoids
a client_portal→messaging cross-module edge (D-20-MODULE; mirrors notifications_router
separation pattern at v1/router.py).

Endpoints:
  GET       /api/v1/client/messages               → MessageListResponse (paginated + unreadCount)
  POST      /api/v1/client/messages               → MessageResponse (idempotent create)
  PATCH     /api/v1/client/messages/read          → 204 No Content
  WS        /api/v1/client/ws/messages            → real-time new_message frames (RT-01..04)

Route ordering: /messages/read declared BEFORE any future /messages/{id} path-param route
so the literal path segment "read" is not captured by the param route.

All mutation REST endpoints are RBAC-04 ordered:
  require_client() → verify_client_csrf → get_db

WS endpoint (RT-01..04):
  Cookie auth (cc_client_access) via require_client() — NO URL token (T-90-10 / P1).
  Origin guard via verify_ws_origin (T-90-11 / P1 CSWSH).
  No verify_client_csrf — WS handshake cannot carry headers (per WS auth design).
  Per-connection Redis pub/sub + session-per-operation via app.state.sessionmaker.

IDOR safety: client_id comes from require_client() ClientPrincipal only — never
from URL parameters or request body (D-20-IDOR / T-90-04).

No try/except — AppError bubbles to _app_error_handler.
"""

from __future__ import annotations

import json
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response, WebSocket, status
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import (
    ClientPrincipal,
    require_client,
    verify_client_csrf,
    verify_ws_origin,
)
from app.core.idempotency import idempotent_execute, verify_client_idempotency
from app.core.pagination import PageQuery
from app.core.redis import get_redis
from app.core.schemas import ResponseEnvelope, envelope
from app.modules.messaging import service
from app.modules.messaging.schemas import (
    MessageListResponse,
    MessageResponse,
    SendMessageRequest,
)
from app.modules.messaging.ws import run_connection

router = APIRouter(tags=["Client-Portal"])


@router.get(
    "/messages",
    response_model=ResponseEnvelope[MessageListResponse],
    operation_id="client_list_messages",
    summary=(
        "Paginated message thread history for the authenticated client (MSG-01; "
        "IDOR-safe; newest-first; includes unreadCount; optional ?after cursor for RT-04)"
    ),
)
async def client_list_messages(
    query: Annotated[PageQuery, Depends()],
    client: Annotated[ClientPrincipal, Depends(require_client())],
    session: Annotated[AsyncSession, Depends(get_db)],
    after: UUID | None = None,
) -> ResponseEnvelope[MessageListResponse]:
    """Return paginated message history newest-first with unreadCount (MSG-01).

    D-20-IDOR: client_id from require_client() principal only — never from URL.
    RT-04: optional ?after={messageId} cursor returns only messages newer than the cursor.
    No CSRF dep — GET is a safe method per RBAC-04.
    No try/except — AppError bubbles to _app_error_handler.
    No session.commit() — read path.
    """
    result = await service.list_thread_history(
        session,
        client_id=client.id,
        page=query.page,
        page_size=query.page_size,
        after=after,
    )
    return envelope(result)


# ROUTE ORDERING NOTE: /messages/read declared BEFORE any future /messages/{id}
# path-param route so the literal path segment "read" is not captured by the param.


@router.patch(
    "/messages/read",
    status_code=status.HTTP_204_NO_CONTENT,
    operation_id="client_mark_messages_read",
    summary=(
        "Mark all unread staff messages as read for the authenticated client (MSG-04; "
        "IDOR-safe via client_id from principal; resets unreadCount to 0)"
    ),
)
async def client_mark_messages_read(
    client: Annotated[ClientPrincipal, Depends(require_client())],
    _csrf: Annotated[None, Depends(verify_client_csrf)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> Response:
    """Mark all unread staff messages read; reset unreadCount to 0 (MSG-04).

    RBAC-04 ordering: require_client() → verify_client_csrf → get_db.
    T-90-04: client_id from principal only.
    No try/except — AppError bubbles to _app_error_handler.
    """
    await service.mark_thread_read(session, client_id=client.id)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/messages",
    response_model=ResponseEnvelope[MessageResponse],
    operation_id="client_send_message",
    summary=(
        "Send a message in the authenticated client's thread (MSG-02; "
        "IDOR-safe; idempotent via Idempotency-Key; CSRF required)"
    ),
)
async def client_send_message(
    payload: SendMessageRequest,
    request: Request,
    client: Annotated[ClientPrincipal, Depends(require_client())],
    _csrf: Annotated[None, Depends(verify_client_csrf)],
    idempotency_key: Annotated[str, Depends(verify_client_idempotency)],
    redis: Annotated[Redis, Depends(get_redis)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> Response:
    """Send a client message; idempotent via Idempotency-Key header (MSG-02 + MSG-03).

    RBAC-04 ordering: require_client() → verify_client_csrf → verify_client_idempotency
    → get_db / get_redis.

    D-20-IDOR (T-90-04): client_id from principal ONLY — SendMessageRequest carries
    only `body`; extra='forbid' rejects any injected ownership fields (T-90-05).

    Idempotency (T-90-06): verify_client_idempotency + idempotent_execute wrap the DB
    write so duplicate key+body replays the cached response without creating a second row.
    Same key + different body → 422 idempotency_key_reuse. No bespoke dedup table.

    DB-first (P5 / CR-02): service.send_client_message writes the row but does NOT
    publish. The runner commits FIRST, then publishes the id-only Redis frame via
    service.publish_new_message — so a failed commit can never emit a phantom
    new_message frame for a row that does not exist.

    No try/except — AppError bubbles to _app_error_handler.
    """
    incoming_body = await request.body()
    client_id = client.id

    async def _runner() -> tuple[int, bytes]:
        result = await service.send_client_message(
            session,
            client_id=client_id,
            payload=payload,
        )
        await session.commit()
        # CR-02: publish ONLY after the row is durable (post-commit).
        await service.publish_new_message(
            redis,
            client_id=client_id,
            message_id=result.id,
        )
        body_bytes = json.dumps(
            envelope(result).model_dump(mode="json", by_alias=True),
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
        return status.HTTP_200_OK, body_bytes

    return await idempotent_execute(redis, idempotency_key, incoming_body, runner=_runner)


# ─────────────────────────────────────────────────────────────────────────────
# Phase 90 RT-01..04 — WebSocket real-time messaging endpoint
# ─────────────────────────────────────────────────────────────────────────────


@router.websocket("/ws/messages")
async def client_ws_messages(
    websocket: WebSocket,
    _origin: Annotated[None, Depends(verify_ws_origin)],
    client: Annotated[ClientPrincipal, Depends(require_client())],
) -> None:
    """Real-time message delivery via WebSocket + Redis pub/sub (RT-01..04).

    Auth:
      - Origin validated by verify_ws_origin BEFORE accept() (CSWSH guard, T-90-11 / P1).
      - Cookie auth via require_client() over the WS upgrade request (T-90-10 / P1).
      - Missing/expired cc_client_access cookie → 401 pre-accept (upgrade rejected).
      - Disallowed Origin → close 1008 pre-accept (verify_ws_origin).
      - NO verify_client_csrf — WS handshake cannot carry X-CSRF-Token header.
      - NO URL token (?token=...) — httpOnly cookie is the only auth mechanism.

    Connection lifecycle (all in run_connection / ws.py):
      - Dedicated Redis pub/sub subscriber for cc:messaging:client:{client.id}.
      - Channel derived from principal ONLY — never from path/query/payload (P2 / T-90-12).
      - Heartbeat every ~30s; idle close with 1001 after ~90s (P6 / T-90-14).
      - DB sessions opened per-operation via app.state.sessionmaker (P3 / T-90-13).
      - finally: cancel fan-out task, unsubscribe, pubsub.aclose() (P6).

    Frames (server → client):
      {"type": "new_message", "messageId": "<uuid>"}  (id-only — PWA refetches via REST)
      {"type": "ping"}  (heartbeat; client may respond with any text)

    No REST response — this endpoint does not return an HTTP body.
    """
    await websocket.accept()
    await run_connection(
        websocket=websocket,
        client_id=client.id,
        redis=websocket.app.state.redis,
        session_factory=websocket.app.state.sessionmaker,
    )
