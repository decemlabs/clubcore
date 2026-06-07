"""Messaging service — send / list / mark-read + audit + pub/sub seam (Phase 90 MSG-01..04 + RT-03).

No session.commit() — caller-owns-txn (D-32-10/D-49-19).

The Redis publish side of the pub/sub fan-out (RT-03) is notification-only and is
performed by the CALLER strictly AFTER a successful DB commit (CR-02 / DB-first, P5):
  - The persist functions (send_client_message / record_staff_message) do NOT publish;
    they neither commit nor touch Redis (caller-owns-txn).
  - The caller commits, then calls publish_new_message(redis, client_id, message_id)
    once the row is durable — so a failed commit can never emit a phantom new_message
    frame for a row that does not exist.
  - The id-only frame is published to cc:messaging:client:{client_id}.
  - The WS subscriber (Plan 03) receives the frame and notifies the PWA to refetch via REST.
  - The full message payload is NEVER published over pub/sub (at-most-once loss risk, P5).

Staff messages are created via record_staff_message() — an internal function with NO
REST endpoint (admin-web frozen → v2.6). It is exercised by integration tests and
the Phase 93 Telegram bridge.

A Phase 93 forward seam is documented here as a clearly-marked no-op TODO.

Public API:
  send_client_message   — persist role='client', audit (MSG-02; caller publishes after commit)
  record_staff_message  — persist role='staff', audit (internal — no endpoint)
  publish_new_message   — id-only Redis frame; call AFTER a successful commit (CR-02 / RT-03)
  list_thread_history   — paginated read with unreadCount (MSG-01)
  mark_thread_read      — mark staff messages read, reset unreadCount (MSG-04)
"""

from __future__ import annotations

from uuid import UUID

import structlog
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import audit
from app.modules.messaging import repository
from app.modules.messaging.schemas import (
    MessageItem,
    MessageListResponse,
    MessageResponse,
    NewMessageEvent,
    SendMessageRequest,
)

_log = structlog.get_logger("modules.messaging.service")


async def publish_new_message(
    redis: Redis,
    *,
    client_id: UUID,
    message_id: UUID,
) -> None:
    """Publish the id-only new_message WS frame (RT-03 notification-only).

    CR-02 / DB-first (P5): callers MUST invoke this STRICTLY AFTER a successful
    session.commit(), so a failed commit can never emit a phantom new_message frame
    for a row that does not exist.

    Channel is derived ONLY from the principal's client_id (T-90-04 / T-90-07 — never
    from request payload). The frame carries only the id; the WS subscriber (Plan 03)
    triggers a REST refetch (the full payload is never published, P5).
    """
    await redis.publish(
        f"cc:messaging:client:{client_id}",
        NewMessageEvent(message_id=message_id).model_dump_json(by_alias=True),
    )


async def send_client_message(
    session: AsyncSession,
    *,
    client_id: UUID,
    payload: SendMessageRequest,
) -> MessageResponse:
    """Persist a client message and emit audit (MSG-02).

    Sequence (DB-first, P5):
      1. get_or_create_thread — ensures the thread exists.
      2. insert_message(role='client') — persists the message.
      3. audit.emit("message_sent") co-transactionally.

    This function does NOT publish to Redis and does NOT commit (caller-owns-txn).
    CR-02: the caller (router) commits FIRST, then calls publish_new_message() so the
    notification frame is only emitted once the row is durable (no phantom notify).
    IDOR: client_id MUST come from the require_client() principal (D-20-IDOR / T-90-04).
    """
    thread_id = await repository.get_or_create_thread(session, client_id)
    message_id, sent_at = await repository.insert_message(
        session,
        thread_id=thread_id,
        role="client",
        body=payload.body,
    )

    await audit.emit(
        session,
        "message_sent",
        actor_user_id=None,  # client-initiated; no staff actor
        resource_type="message",
        resource_id=message_id,
        client_id=str(client_id),
    )

    _log.info(
        "client_message_sent",
        client_id=str(client_id),
        message_id=str(message_id),
        thread_id=str(thread_id),
    )

    # TODO Phase 93: Telegram bridge forward seam (record + enqueue ARQ DM)
    # When the bridge is active, enqueue an ARQ task here to forward the message
    # body to STAFF_TELEGRAM_CHAT_ID via bot.send_message(). This is a no-op in
    # Phase 90 — the seam is documented here so Phase 93 has a clear insertion point.

    return MessageResponse(
        id=message_id,
        role="client",
        body=payload.body,
        sent_at=sent_at,
        read_at=None,
        thread_id=thread_id,
    )


async def record_staff_message(
    session: AsyncSession,
    *,
    client_id: UUID,
    body: str,
    telegram_user_id: int | None = None,
    telegram_username: str | None = None,
) -> MessageResponse:
    """Persist a staff message and emit audit (internal — no endpoint).

    This function is NOT exposed via a REST endpoint (admin-web frozen → v2.6).
    It is called by integration tests and will be called by the Phase 93 Telegram bridge.

    telegram_user_id and telegram_username are nullable audit fields for future
    staff identity tracking (v2.6 admin-web inbox). In Phase 90 staff identity
    is anonymous (role='staff' only). The chat_staff_reply_sent audit event is
    reserved for the Phase 93 bridge callsite — "message_sent" is used here.

    Sequence (DB-first, P5):
      1. get_or_create_thread — ensures the thread exists.
      2. insert_message(role='staff') — persists + increments client_unread_count.
      3. audit.emit("message_sent") co-transactionally.

    This function does NOT publish to Redis and does NOT commit (caller-owns-txn).
    CR-02: the caller commits FIRST, then calls publish_new_message(redis, ...) with
    the returned message id so the notification is only emitted once the row is durable.
    """
    thread_id = await repository.get_or_create_thread(session, client_id)
    message_id, sent_at = await repository.insert_message(
        session,
        thread_id=thread_id,
        role="staff",
        body=body,
    )

    await audit.emit(
        session,
        "message_sent",
        actor_user_id=None,  # system-initiated (bridge / test); no staff user actor
        resource_type="message",
        resource_id=message_id,
        client_id=str(client_id),
    )

    _log.info(
        "staff_message_recorded",
        client_id=str(client_id),
        message_id=str(message_id),
        thread_id=str(thread_id),
        telegram_user_id=telegram_user_id,
    )

    return MessageResponse(
        id=message_id,
        role="staff",
        body=body,
        sent_at=sent_at,
        read_at=None,
        thread_id=thread_id,
    )


async def list_thread_history(
    session: AsyncSession,
    *,
    client_id: UUID,
    page: int,
    page_size: int,
    after: UUID | None = None,
) -> MessageListResponse:
    """Return paginated message history newest-first with unreadCount (MSG-01 + RT-04).

    Calls repository.list_thread_history which auto-creates the thread on first GET
    (returns empty list, not 404 — per CONTEXT.md Thread lifecycle decision).

    RT-04: ``after`` cursor returns only messages newer than the given message id.
    No audit, no commit — GET path.
    """
    rows, total, unread_count = await repository.list_thread_history(
        session,
        client_id,
        page=page,
        page_size=page_size,
        after=after,
    )

    items = [
        MessageItem(
            id=row["id"],
            role=row["role"],
            body=row["body"],
            sent_at=row["sent_at"],
            read_at=row["read_at"],
            thread_id=row["thread_id"],
        )
        for row in rows
    ]

    return MessageListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        unread_count=unread_count,
    )


async def mark_thread_read(
    session: AsyncSession,
    *,
    client_id: UUID,
) -> None:
    """Mark all unread staff messages read; reset unreadCount to 0 (MSG-04).

    Calls repository.mark_thread_read which returns True if any rows were updated.
    Emits "message_read" audit event if anything was marked (T-90-08 mitigate).

    No session.commit() — caller-owns-txn (router commits).
    """
    marked = await repository.mark_thread_read(session, client_id)

    if marked:
        # Resolve thread_id for audit resource_id.
        thread_id = await repository.get_or_create_thread(session, client_id)
        await audit.emit(
            session,
            "message_read",
            actor_user_id=None,  # client-initiated; no staff actor
            resource_type="message",
            resource_id=thread_id,
            client_id=str(client_id),
        )
        _log.info(
            "thread_messages_marked_read",
            client_id=str(client_id),
            thread_id=str(thread_id),
        )
