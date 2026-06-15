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
  serve_attachment      — IDOR-safe proxy-stream with anti-XSS headers (Phase 92 ATT-03)
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

import structlog
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import StreamingResponse

from app.core import audit
from app.core.exceptions import NotFoundError, PayloadTooLargeError, UnsupportedMediaTypeError
from app.integrations.storage.mime import MAGIC_BYTE_READ_LEN, guess_allowed_mime
from app.integrations.storage.types import Storage
from app.modules.messaging import repository
from app.modules.messaging.schemas import (
    AttachmentUploadResponse,
    MessageAttachmentItem,
    MessageItem,
    MessageListResponse,
    MessageResponse,
    NewMessageEvent,
    ReadReceiptEvent,
    SendMessageRequest,
    StaffInboxResponse,
    StaffMessageItem,
    StaffMessageResult,
    StaffReplyRequest,
    StaffThreadHistoryResponse,
    StaffThreadItem,
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
    """Persist a client message and emit audit (MSG-02 + Phase 92 ATT-03 two-step flow).

    Sequence (DB-first, P5):
      1. If payload.attachment_id is present: IDOR check via get_owned_attachment.
         If the attachment is not owned by this client → NotFoundError (404-collapse;
         never 403 — no existence leak, P8/MSG-02 precedent). No message is written.
      2. get_or_create_thread — ensures the thread exists.
      3. insert_message(role='client') — persists the message (with attachment_id if present).
      4. audit.emit("message_sent") co-transactionally.

    This function does NOT publish to Redis and does NOT commit (caller-owns-txn).
    CR-02: the caller (router) commits FIRST, then calls publish_new_message() so the
    notification frame is only emitted once the row is durable (no phantom notify).
    IDOR: client_id MUST come from the require_client() principal (D-20-IDOR / T-90-04).
    """
    # Phase 92 ATT-03: IDOR check for attachment ownership BEFORE any thread or message write.
    attachment_row: dict[str, object] | None = None
    if payload.attachment_id is not None:
        attachment_row = await repository.get_owned_attachment(
            session, payload.attachment_id, client_id=client_id
        )
        if attachment_row is None:
            # T-92-14: foreign or non-existent attachment_id → 404-collapse (never 403).
            raise NotFoundError(
                f"Attachment {payload.attachment_id} not found or not owned by client"
            )

    thread_id = await repository.get_or_create_thread(session, client_id)

    # body is str | None; body-only and both-body-and-attachment are valid. Use empty
    # string sentinel for attachment-only messages so the DB NOT NULL body constraint
    # is satisfied while the UI displays the attachment as the message content.
    effective_body = payload.body if payload.body is not None else ""

    message_id, sent_at = await repository.insert_message(
        session,
        thread_id=thread_id,
        role="client",
        body=effective_body,
        attachment_id=payload.attachment_id,
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
        has_attachment=payload.attachment_id is not None,
    )

    # TODO Phase 93: Telegram bridge forward seam (record + enqueue ARQ DM)
    # When the bridge is active, enqueue an ARQ task here to forward the message
    # body to STAFF_TELEGRAM_CHAT_ID via bot.send_message(). This is a no-op in
    # Phase 90 — the seam is documented here so Phase 93 has a clear insertion point.

    # Build attachment sub-object if the message has one.
    attachment_item: MessageAttachmentItem | None = None
    if attachment_row is not None and payload.attachment_id is not None:
        raw_size = attachment_row["size_bytes"]
        assert isinstance(raw_size, int)
        attachment_item = MessageAttachmentItem(
            id=payload.attachment_id,
            mime_type=str(attachment_row["mime_type"]),
            size_bytes=raw_size,
            url=f"/api/v1/client/messages/attachments/{payload.attachment_id}",
        )

    return MessageResponse(
        id=message_id,
        role="client",
        body=effective_body,
        sent_at=sent_at,
        read_at=None,
        thread_id=thread_id,
        attachment=attachment_item,
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

    items = []
    for row in rows:
        # Phase 92 ATT-03: build attachment sub-object from LEFT JOIN columns if present.
        attachment_item: MessageAttachmentItem | None = None
        att_id = row.get("att_id")
        if att_id is not None:
            attachment_item = MessageAttachmentItem(
                id=UUID(str(att_id)),
                mime_type=str(row["att_mime"]),
                size_bytes=int(row["att_size"]),
                url=f"/api/v1/client/messages/attachments/{att_id}",
            )
        items.append(
            MessageItem(
                id=row["id"],
                role=row["role"],
                body=row["body"],
                sent_at=row["sent_at"],
                read_at=row["read_at"],
                thread_id=row["thread_id"],
                attachment=attachment_item,
            )
        )

    return MessageListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        unread_count=unread_count,
    )


_MAX_UPLOAD_BYTES: int = 5 * 1024 * 1024  # 5 MB cap (ATT-02 / T-92-06)


async def create_attachment(
    session: AsyncSession,
    storage: Storage,
    *,
    client_id: UUID,
    raw_bytes: bytes,
    claimed_content_type: str | None,
) -> AttachmentUploadResponse:
    """Validate, store, and persist a client file attachment (Phase 92 ATT-01/02).

    Sequence (all co-transactional, no commit — caller-owns-txn):
      1. Size cap: len(raw_bytes) > 5MB → PayloadTooLargeError (T-92-06, P17).
      2. Magic-byte allowlist: guess_allowed_mime(head) → None → UnsupportedMediaTypeError.
         claimed_content_type is NEVER trusted (T-92-05 LOCKED INVARIANT).
      3. get_or_create_thread — ensure thread exists for this client.
      4. Generate UUID4 object key `attachments/{uuid4()}` — no user filename (T-92-08).
      5. await storage.put(key, raw_bytes, content_type=validated_mime) — S3 upload.
      6. insert_attachment — persist row with client_id ownership (T-92-07 IDOR anchor).
      7. audit.emit("attachment_uploaded") co-transactionally (T-92-09).
      8. Return AttachmentUploadResponse with previewUrl = relative serve path.

    IDOR: client_id MUST come from require_client() principal (D-20-IDOR / T-92-07).
    No session.commit() — caller (router) commits after this returns.
    """
    # Step 1: size cap BEFORE any I/O (P17 — never buffer the whole body first).
    if len(raw_bytes) > _MAX_UPLOAD_BYTES:
        raise PayloadTooLargeError(
            f"Upload exceeds the 5MB size limit ({len(raw_bytes)} bytes received)"
        )

    # Step 2: magic-byte validation — Content-Type header is NEVER trusted (T-92-05).
    validated_mime = guess_allowed_mime(raw_bytes[:MAGIC_BYTE_READ_LEN])
    if validated_mime is None:
        raise UnsupportedMediaTypeError(
            "Unsupported file type: only JPEG, PNG, and WebP images are accepted"
        )

    # Step 3: ensure thread exists.
    thread_id = await repository.get_or_create_thread(session, client_id)

    # Step 4: server-generated UUID object key — no user filename, no extension (T-92-08).
    object_key = f"attachments/{uuid4()}"

    # Step 5: upload to S3 using the VALIDATED mime type (not claimed_content_type).
    await storage.put(object_key, raw_bytes, content_type=validated_mime)

    # Step 6: persist the attachment row (IDOR anchor: client_id from principal only).
    attachment_id = await repository.insert_attachment(
        session,
        thread_id=thread_id,
        client_id=client_id,
        mime_type=validated_mime,
        object_key=object_key,
        size_bytes=len(raw_bytes),
    )

    # Step 7: emit audit co-transactionally (T-92-09).
    await audit.emit(
        session,
        "attachment_uploaded",
        actor_user_id=None,  # client-initiated; no staff actor (mirrors message_sent)
        resource_type="message",
        resource_id=attachment_id,
        client_id=str(client_id),
    )

    _log.info(
        "attachment_created",
        client_id=str(client_id),
        attachment_id=str(attachment_id),
        thread_id=str(thread_id),
        mime_type=validated_mime,
        size_bytes=len(raw_bytes),
    )

    # Step 8: return response with relative serve path previewUrl.
    return AttachmentUploadResponse(
        attachment_id=attachment_id,
        preview_url=f"/api/v1/client/messages/attachments/{attachment_id}",
    )


async def serve_attachment(
    session: AsyncSession,
    storage: Storage,
    *,
    attachment_id: UUID,
    client_id: UUID,
) -> StreamingResponse:
    """IDOR-safe proxy-stream for a client attachment (Phase 92 ATT-03, T-92-10..13).

    Sequence (read path — no commit, no audit):
      1. get_owned_attachment(session, attachment_id, client_id=client_id):
         returns the DB row if owned by this client; None for non-owned or missing id.
      2. If None → NotFoundError (404-collapse — NEVER 403, no existence leak, P8/MSG-02).
      3. Build StreamingResponse over storage.open_stream(row['object_key']) with the
         anti-XSS header triad (T-92-11 LOCKED):
           Content-Type        = stored validated mime_type (NEVER client-derived)
           Content-Disposition = attachment (NEVER inline)
           X-Content-Type-Options = nosniff

    Security properties:
      - IDOR (T-92-10): ownership check via message_attachments.client_id == principal;
        client_id from require_client() only — never from URL param or body.
      - Object key read from owned DB row (T-92-12): no path traversal — the
        {attachment_id} UUID maps to a DB-stored key; never built from user input.
      - Unauthenticated (T-92-13): require_client() gates the route; 401 before this runs.
      - Anti-stored-XSS (T-92-11): the three-header triad is enforced here; the caller
        returns the StreamingResponse directly so FastAPI does NOT override these headers.
      - No session.commit() — read path, caller-owns-txn.
    """
    row = await repository.get_owned_attachment(session, attachment_id, client_id=client_id)
    if row is None:
        # T-92-10: 404-collapse — never 403 (no existence leak), MSG-02 precedent.
        raise NotFoundError(
            f"Attachment {attachment_id} not found or not owned by client"
        )

    object_key = str(row["object_key"])
    mime_type = str(row["mime_type"])

    _log.info(
        "attachment_served",
        client_id=str(client_id),
        attachment_id=str(attachment_id),
        mime_type=mime_type,
    )

    # T-92-11 LOCKED: Content-Type from STORED validated mime only; Content-Disposition:
    # attachment (never inline); X-Content-Type-Options: nosniff.
    return StreamingResponse(
        storage.open_stream(object_key),
        media_type=mime_type,
        headers={
            "Content-Disposition": "attachment",
            "X-Content-Type-Options": "nosniff",
        },
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


# ─────────────────────────────────────────────────────────────────────────────
# Phase 116 MSG-01/02 — Staff-side inbox + reply service functions
# ─────────────────────────────────────────────────────────────────────────────


def _make_initials(first_name: str, last_name: str) -> str:
    """Derive 1-2 char uppercase initials from first and last name."""
    parts = [first_name.strip(), last_name.strip()]
    initials = "".join(p[0].upper() for p in parts if p)
    return initials[:2] or "?"


async def list_threads(
    session: AsyncSession,
) -> StaffInboxResponse:
    """Return all client threads with staff unread count + last-message preview (Phase 116 MSG-01).

    Calls list_all_threads_with_unread and maps rows to StaffInboxResponse.
    clientInitials are derived from first/last name (1-2 uppercase chars).
    No session.commit() — caller-owns-txn.
    No try/except — AppError bubbles to _app_error_handler.
    """
    rows = await repository.list_all_threads_with_unread(session)
    items = [
        StaffThreadItem(
            id=UUID(str(row["id"])),
            client_id=UUID(str(row["client_id"])),
            client_name=f"{row['first_name']} {row['last_name']}",
            client_initials=_make_initials(str(row["first_name"]), str(row["last_name"])),
            last_message_at=row["last_message_at"],
            last_message_body=row["last_message_body"],
            last_message_role=row["last_message_role"],
            staff_unread_count=int(row["staff_unread_count"]),
        )
        for row in rows
    ]
    return StaffInboxResponse(items=items, total=len(items))


async def get_staff_thread(
    session: AsyncSession,
    *,
    thread_id: UUID,
) -> StaffThreadHistoryResponse:
    """Return full chronological message history for a single thread (Phase 116 MSG-01).

    Resolves client_id via get_thread_client_id, then fetches all messages via
    list_thread_messages_for_staff (oldest-first, no pagination in v1).

    Raises NotFoundError if thread_id does not exist.
    No session.commit() — caller-owns-txn.
    No try/except — AppError bubbles to _app_error_handler.
    """
    from app.core.exceptions import NotFoundError  # local import — avoids circular at module level

    client_id = await repository.get_thread_client_id(session, thread_id)
    if client_id is None:
        raise NotFoundError(f"Thread {thread_id} not found")

    rows = await repository.list_thread_messages_for_staff(session, thread_id)
    messages = [
        StaffMessageItem(
            id=UUID(str(row["id"])),
            role=str(row["role"]),
            body=str(row["body"]),
            sent_at=row["sent_at"],
        )
        for row in rows
    ]
    return StaffThreadHistoryResponse(thread_id=thread_id, messages=messages)


async def send_staff_reply(
    session: AsyncSession,
    *,
    thread_id: UUID,
    payload: StaffReplyRequest,
) -> StaffMessageItem:
    """Persist a staff reply via the existing record_staff_message; return StaffMessageItem.

    Reuses record_staff_message (resolves thread, marks prior client msgs read,
    inserts role='staff' message, emits message_sent audit). This function does NOT
    publish to Redis and does NOT commit — caller-owns-txn (CR-02 / DB-first).

    The caller (router) must: (1) await session.commit(), (2) call
    publish_new_message(redis, client_id=..., message_id=...) AFTER commit.

    Raises NotFoundError if thread_id does not exist.
    No try/except — AppError bubbles to _app_error_handler.
    """
    from app.core.exceptions import NotFoundError  # local import — avoids circular at module level

    client_id = await repository.get_thread_client_id(session, thread_id)
    if client_id is None:
        raise NotFoundError(f"Thread {thread_id} not found")

    result = await record_staff_message(
        session,
        client_id=client_id,
        body=payload.body,
    )

    _log.info(
        "staff_reply_sent",
        thread_id=str(thread_id),
        client_id=str(client_id),
        message_id=str(result.id),
    )

    return StaffMessageItem(
        id=result.id,
        role="staff",
        body=payload.body,
        sent_at=result.sent_at,
    )


async def mark_staff_thread_read(
    session: AsyncSession,
    *,
    thread_id: UUID,
) -> None:
    """Reset the staff-side unread watermark for a thread (Phase 116 MSG-01).

    Sets message_threads.staff_last_read_at = now() so subsequent inbox fetches
    show staffUnreadCount = 0 for this thread.

    No session.commit() — caller-owns-txn (router commits).
    No try/except — AppError bubbles to _app_error_handler.
    """
    await repository.mark_staff_thread_read(session, thread_id)
