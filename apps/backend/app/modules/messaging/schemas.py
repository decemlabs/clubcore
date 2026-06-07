"""Messaging module Pydantic schemas (Phase 90 MSG-01..04 + Phase 91 RCPT-01/03).

Response schemas use ResponseData (camelCase wire via alias_generator=to_camel).
Request schemas use BackendSchemaBase (extra='forbid', camelCase inbound).

MessageListResponse is a custom DTO embedding unread_count alongside the standard
paginated fields — PaginatedData[T] cannot carry extra fields per the generic base
definition, so we replicate the page/page_size/total/items shape here.
This mirrors ClientNotificationsListResponse from app.modules.notifications.schemas.

WS event discriminated union — three event types published to cc:messaging:client:{client_id}:
  NewMessageEvent  — id-only notification (Phase 90 RT-03); triggers REST refetch on client.
  ReadReceiptEvent — thread-level readAt marker (Phase 91 RCPT-01/03); post-commit, DB-first.
  TypingEvent      — ephemeral {type, actor} frame (Phase 91 RCPT-02); never persisted.
Each event type uses a Literal discriminator and is published independently via its own
model_dump_json(by_alias=True) call — matching the NewMessageEvent pattern.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import Field, field_validator

from app.core.schemas import BackendSchemaBase, ResponseData


class MessageItem(ResponseData):
    """Single message row returned in the thread history list (MSG-01 read path).

    role: 'client' = sent by the client; 'staff' = sent by gym/staff.
    read_at: None = unread; timestamp = read.
    sent_at + id provide the composite tiebreak ordering (newest-first).
    """

    id: UUID
    role: str
    body: str
    sent_at: datetime
    read_at: datetime | None = None
    thread_id: UUID


class MessageListResponse(ResponseData):
    """Paginated message list with server-computed unread_count (MSG-01).

    Field names mirror PaginatedData for wire consistency.
    page_size → pageSize camelCase via alias_generator=to_camel on ResponseData base.
    unread_count → unreadCount on the wire.
    unread_count is the count of unread STAFF messages (i.e. messages from staff
    that the client has not yet read — tracked in message_threads.client_unread_count).
    """

    items: list[MessageItem]
    total: int
    page: int
    page_size: int
    unread_count: int


class SendMessageRequest(BackendSchemaBase):
    """Request body for POST /client/messages (MSG-02).

    extra='forbid' (inherited from BackendSchemaBase) rejects unknown fields (T-90-05).
    Ownership fields (client_id, thread_id) are intentionally absent — client_id is
    derived ONLY from the require_client() principal (D-20-IDOR / T-90-04).

    body: min_length=1 rejects empty strings at the Field level.
    field_validator strips whitespace and re-checks non-empty so body="   " → 422
    (T-90-09: whitespace-only body is rejected before any DB write).
    max_length=4000 guards against oversized input.
    """

    body: Annotated[str, Field(min_length=1, max_length=4000)]

    @field_validator("body")
    @classmethod
    def body_not_whitespace_only(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("body must not be whitespace-only")
        return v


class MessageResponse(ResponseData):
    """Single message returned after POST /client/messages (MSG-02 send path).

    Field layout mirrors MessageItem; returned from send_client_message service call.
    """

    id: UUID
    role: str
    body: str
    sent_at: datetime
    read_at: datetime | None = None
    thread_id: UUID


class StaffMessageResult(ResponseData):
    """Return value of service.record_staff_message (Phase 91 extension).

    Extends the MessageResponse shape with reply_read_at — the thread-level
    readAt from reply-as-read (max sent_at of client messages marked read in
    the same call). None if no prior unread client messages existed.

    reply_read_at → replyReadAt on the wire via alias_generator=to_camel.
    Callers that only use .id (e.g. WS fanout tests) are unaffected — .id
    is inherited from the same field set as MessageResponse.
    """

    id: UUID
    role: str
    body: str
    sent_at: datetime
    read_at: datetime | None = None
    thread_id: UUID
    reply_read_at: datetime | None = None


class NewMessageEvent(ResponseData):
    """WS event frame for a new message notification (RT-03 pub/sub side).

    Minimal id-only frame — the PWA reacts by invalidating the messages query
    and refetching via REST (DB-first; pub/sub is notification-only, P5).

    type is a Literal discriminator; message_id → messageId on the wire via
    alias_generator=to_camel (P16).
    """

    type: Literal["new_message"] = "new_message"
    message_id: UUID


class ReadReceiptEvent(ResponseData):
    """WS event frame for a thread-level read receipt (Phase 91 RCPT-01/03).

    Published post-commit (CR-02 / DB-first) after reply-as-read marks prior
    unread role='client' messages read. The client marks all its sent messages
    with sent_at <= readAt as ✓✓.

    type is a Literal discriminator; read_at → readAt on the wire.

    WR-02 — read_at SEMANTICS (LOCKED field name, do NOT rename — 91-CONTEXT.md:41-42):
      Despite the name, this field carries the max(sent_at) WATERMARK of the just-read
      client messages — i.e. a SEND-TIME cutoff, NOT the moment the messages were read.
      The DB column messages.read_at is set to now() and is strictly LATER than this
      value. The thread-level marker contract is: the client marks every message it sent
      with sent_at <= readAt as ✓✓ (lighter than a per-message id list). A consumer
      (Phase 94 PWA / Phase 93 bridge) MUST treat readAt as a comparison cutoff and MUST
      NOT render it as a "прочитано в HH:MM" read timestamp — for that, use the REST
      MessageItem.readAt (the persisted now()), which will legitimately differ.

    CR-02: callers MUST invoke publish_read_receipt AFTER session.commit() so
    the receipt is never emitted for an uncommitted read_at change (T-91-PHANTOM).

    Channel is always cc:messaging:client:{client_id} — never from payload (T-91-IDOR).
    """

    type: Literal["read_receipt"] = "read_receipt"
    # WR-02: send-time WATERMARK (max sent_at of marked client rows), NOT a read clock.
    # Wire alias is `readAt` (LOCKED, do NOT rename). Client marks every sent message with
    # sent_at <= this value as ✓✓. See the class docstring for the full semantics.
    read_at: datetime


class TypingEvent(ResponseData):
    """WS event frame for a staff→client typing indicator (Phase 91 RCPT-02).

    Ephemeral — never persisted to DB; published directly to the principal
    channel with no commit dependency. Auto-dismiss is client-side (~5 s).

    Payload carries ONLY type + actor (T-91-LEAK: no body, preview, or message id).
    actor defaults to "staff" — only staff→client typing is supported in Phase 91.

    Channel is always cc:messaging:client:{client_id} — never from payload (T-91-IDOR).
    """

    type: Literal["typing"] = "typing"
    # IN-02: actor is a CLOSED Literal, not an open str — only staff→client typing
    # is supported in Phase 91. This locks the wire contract and fails fast on a typo
    # (e.g. actor="staf") or an unexpected actor="client" relay. Widen to
    # Literal["staff", "client"] if/when the deferred client→staff relay lands.
    actor: Literal["staff"] = "staff"
