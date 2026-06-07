"""Messaging module Pydantic schemas (Phase 90 MSG-01..04).

Response schemas use ResponseData (camelCase wire via alias_generator=to_camel).
Request schemas use BackendSchemaBase (extra='forbid', camelCase inbound).

MessageListResponse is a custom DTO embedding unread_count alongside the standard
paginated fields — PaginatedData[T] cannot carry extra fields per the generic base
definition, so we replicate the page/page_size/total/items shape here.
This mirrors ClientNotificationsListResponse from app.modules.notifications.schemas.

NewMessageEvent uses a Literal discriminator type for extensibility — only
"new_message" is in scope for Phase 90; future event types extend the union
without changing the wire format for existing events.
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


class NewMessageEvent(ResponseData):
    """WS event frame for a new message notification (RT-03 pub/sub side).

    Minimal id-only frame — the PWA reacts by invalidating the messages query
    and refetching via REST (DB-first; pub/sub is notification-only, P5).

    type is a Literal discriminator for extensibility — only "new_message" is
    implemented in Phase 90. Future event types (e.g. "message_read_receipt",
    "typing_indicator") extend the discriminated union without changing the wire
    format for this member.

    message_id → messageId on the wire via alias_generator=to_camel (P16).
    """

    type: Literal["new_message"] = "new_message"
    message_id: UUID
