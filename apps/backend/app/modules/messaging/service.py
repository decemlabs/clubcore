"""Messaging service — send / list / mark-read + audit + pub/sub seam (Phase 90 + Phase 91).

No session.commit() — caller-owns-txn (D-32-10/D-49-19).

The Redis publish side of the pub/sub fan-out (RT-03) is notification-only and is
performed by the CALLER strictly AFTER a successful DB commit (CR-02 / DB-first, P5):
  - The persist functions (send_client_message / record_staff_message) do NOT publish;
    they neither commit nor touch Redis (caller-owns-txn).
  - The caller commits, then calls publish_new_message / publish_read_receipt once the
    row is durable — so a failed commit can never emit a phantom frame.
  - The id-only / marker frame is published to cc:messaging:client:{client_id}.
  - The WS subscriber (Plan 03) receives the frame and notifies the PWA to refetch via REST.
  - The full message payload is NEVER published over pub/sub (at-most-once loss risk, P5).

Staff messages are created via record_staff_message() — an internal function with NO
REST endpoint (admin-web frozen → v2.6). It is exercised by integration tests and
the Phase 93 Telegram bridge.

A Phase 93 forward seam is documented here as a clearly-marked no-op TODO.

Public API:
  send_client_message   — persist role='client', audit (MSG-02; caller publishes after commit)
  record_staff_message  — persist role='staff' + reply-as-read (RCPT-03); returns StaffMessageResult
  publish_new_message   — id-only new_message Redis frame; call AFTER commit (CR-02 / RT-03)
  publish_read_receipt  — read_receipt Redis frame; call AFTER commit (CR-02 / T-91-PHANTOM)
  publish_typing        — ephemeral typing Redis frame; no DB, no commit dependency (RCPT-02)
  list_thread_history   — paginated read with unreadCount (MSG-01)
  mark_thread_read      — mark staff messages read, reset unreadCount (MSG-04)
"""

from __future__ import annotations

from datetime import datetime
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
    ReadReceiptEvent,
    SendMessageRequest,
    StaffMessageResult,
    TypingEvent,
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


async def publish_read_receipt(
    redis: Redis,
    *,
    client_id: UUID,
    read_at: datetime,
) -> None:
    """Publish the thread-level read_receipt WS frame (Phase 91 RCPT-03).

    CR-02 / DB-first (T-91-PHANTOM): callers MUST invoke this STRICTLY AFTER a
    successful session.commit(), so a failed commit can never emit a receipt for
    an uncommitted read_at change. The receipt reflects a durable DB write.

    Channel is derived ONLY from client_id (T-91-IDOR — never from inbound payload).
    read_at is the max sent_at of the client messages marked read; the PWA marks all
    its sent messages with sent_at <= readAt as ✓✓.
    """
    await redis.publish(
        f"cc:messaging:client:{client_id}",
        ReadReceiptEvent(read_at=read_at).model_dump_json(by_alias=True),
    )


async def publish_typing(
    redis: Redis,
    *,
    client_id: UUID,
) -> None:
    """Publish the ephemeral staff→client typing indicator frame (Phase 91 RCPT-02).

    Ephemeral: no DB access, no commit dependency — this frame is never persisted.
    The payload carries only {type:'typing', actor:'staff'} (T-91-LEAK: no body,
    preview, or message id).

    Channel is derived ONLY from client_id (T-91-IDOR — never from inbound payload).
    Auto-dismiss is client-side (~5 s); the server only publishes this event.

    No session parameter — typing is purely ephemeral and has no DB dependency.
    """
    await redis.publish(
        f"cc:messaging:client:{client_id}",
        TypingEvent().model_dump_json(by_alias=True),
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
) -> StaffMessageResult:
    """Persist a staff message, reply-as-read, and emit audit (internal — no endpoint).

    This function is NOT exposed via a REST endpoint (admin-web frozen → v2.6).
    It is called by integration tests and will be called by the Phase 93 Telegram bridge.

    telegram_user_id and telegram_username are nullable audit fields for future
    staff identity tracking (v2.6 admin-web inbox). In Phase 90/91 staff identity
    is anonymous (role='staff' only). The chat_staff_reply_sent audit event is
    reserved for the Phase 93 bridge callsite — "message_sent" is used here.

    Phase 91 reply-as-read (RCPT-03):
      Before inserting the staff message, mark all prior unread role='client' messages
      in the same thread as read. The max sent_at of the marked rows is captured as the
      thread-level readAt and returned in StaffMessageResult.reply_read_at. When the
      caller finds reply_read_at is not None, it MUST call publish_read_receipt AFTER
      commit (CR-02 / DB-first / T-91-PHANTOM).

    Sequence (DB-first, P5):
      1. get_or_create_thread — ensures the thread exists.
      2. repository.mark_client_messages_read — reply-as-read (role='client' rows).
      3. If reply_read_at is not None: audit.emit("message_read") co-transactionally.
      4. insert_message(role='staff') — persists + increments client_unread_count.
      5. audit.emit("message_sent") co-transactionally.

    This function does NOT publish to Redis and does NOT commit (caller-owns-txn).
    CR-02: the caller commits FIRST, then calls publish_new_message AND (if reply_read_at
    is not None) publish_read_receipt so notifications are only emitted once rows are durable.

    Returns StaffMessageResult — a superset of MessageResponse that adds reply_read_at.
    Existing callers that only use .id continue to work unchanged.
    """
    # WR-01: resolve the thread ONCE and reuse the same thread_id for BOTH the
    # reply-as-read UPDATE and the staff-message insert, so they can never diverge.
    # mark_client_messages_read previously re-resolved the thread internally — a
    # latent inconsistency seam under any future non-idempotent thread resolution.
    thread_id = await repository.get_or_create_thread(session, client_id)

    # Phase 91 reply-as-read: mark prior unread client messages read before/co-transactionally
    # with the staff message insert. Returns the max sent_at of marked rows (or None).
    reply_read_at = await repository.mark_client_messages_read(
        session, client_id, thread_id=thread_id
    )

    if reply_read_at is not None:
        # Emit message_read audit co-transactionally with the reply-as-read marks.
        # Reuses the pre-registered "message_read" event (LOCKED_AUDIT_EVENTS).
        await audit.emit(
            session,
            "message_read",
            actor_user_id=None,  # staff-initiated read; no individual staff actor
            resource_type="message",
            resource_id=thread_id,
            client_id=str(client_id),
        )
        _log.info(
            "client_messages_marked_read_on_staff_reply",
            client_id=str(client_id),
            thread_id=str(thread_id),
            reply_read_at=str(reply_read_at),
        )

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

    return StaffMessageResult(
        id=message_id,
        role="staff",
        body=body,
        sent_at=sent_at,
        read_at=None,
        thread_id=thread_id,
        reply_read_at=reply_read_at,
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
