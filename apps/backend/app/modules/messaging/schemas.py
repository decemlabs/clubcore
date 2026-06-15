"""Messaging module Pydantic schemas (Phase 90 MSG-01..04 + Phase 91 RCPT-01/03 + Phase 92 ATT-03).

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

Phase 92 Plan 03 additions:
  MessageAttachmentItem — sub-object carrying {id, mimeType, sizeBytes, url} for served attachments.
  MessageItem.attachment / MessageResponse.attachment — optional attachment sub-object on messages.
  SendMessageRequest — body made optional; body-OR-attachment model_validator (two-step flow).
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import Field, model_validator

from app.core.schemas import BackendSchemaBase, ResponseData


class MessageAttachmentItem(ResponseData):
    """Attachment sub-object returned on messages that have a photo (Phase 92 ATT-03).

    id: UUID of the message_attachments row.
    mime_type (→ mimeType on wire): validated MIME type (image/jpeg, image/png, or image/webp).
    size_bytes (→ sizeBytes on wire): file size in bytes.
    url: relative path to the authenticated serve endpoint
         /api/v1/client/messages/attachments/{id}.

    Aliases are camelCase via alias_generator=to_camel on the ResponseData base.
    The url field is intentionally not camel-cased (single word, no transform needed).
    """

    id: UUID
    mime_type: str
    size_bytes: int
    url: str


class MessageItem(ResponseData):
    """Single message row returned in the thread history list (MSG-01 read path).

    role: 'client' = sent by the client; 'staff' = sent by gym/staff.
    read_at: None = unread; timestamp = read.
    sent_at + id provide the composite tiebreak ordering (newest-first).
    attachment: None for text-only messages; MessageAttachmentItem when an attachment exists.
    """

    id: UUID
    role: str
    body: str
    sent_at: datetime
    read_at: datetime | None = None
    thread_id: UUID
    attachment: MessageAttachmentItem | None = None


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
    """Request body for POST /client/messages (MSG-02 + Phase 92 ATT-03 two-step flow).

    extra='forbid' (inherited from BackendSchemaBase) rejects unknown fields (T-90-05).
    Ownership fields (client_id, thread_id) are intentionally absent — client_id is
    derived ONLY from the require_client() principal (D-20-IDOR / T-90-04).

    Phase 92 two-step flow changes (Plan 03):
      body is now optional (str | None = None) — valid to omit when attachment_id is present.
      attachment_id (→ attachmentId on wire): optional UUID referencing a previously uploaded
        message_attachments row. When present without body, the empty-body 422 is relaxed.

    Validity matrix (enforced by model_validator):
      body only             → valid (unchanged Phase 90 path)
      attachment_id only    → valid (Phase 92 two-step flow)
      both                  → valid
      neither               → 422 (must have at least one)
      whitespace-only body  → 422 (whitespace guard preserved even when attachment_id present)

    max_length=4000 guards against oversized body input.
    """

    body: Annotated[str | None, Field(default=None, max_length=4000)] = None
    attachment_id: UUID | None = None

    @model_validator(mode="after")
    def body_or_attachment_required(self) -> Self:
        """Enforce: at least one of body / attachment_id must be present.

        If body is present, it must not be whitespace-only (preserves T-90-09).
        If body is absent and attachment_id is absent → 422.
        """
        if self.body is not None:
            stripped = self.body.strip()
            if not stripped:
                raise ValueError("body must not be whitespace-only")
        if self.body is None and self.attachment_id is None:
            raise ValueError("at least one of body or attachment_id must be provided")
        return self


class MessageResponse(ResponseData):
    """Single message returned after POST /client/messages (MSG-02 send path).

    Field layout mirrors MessageItem; returned from send_client_message service call.
    attachment: None for text-only messages; MessageAttachmentItem when an attachment was
    attached to the sent message (Phase 92 ATT-03 two-step flow).
    """

    id: UUID
    role: str
    body: str
    sent_at: datetime
    read_at: datetime | None = None
    thread_id: UUID
    attachment: MessageAttachmentItem | None = None


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


class StaffReplyRequest(BackendSchemaBase):
    """Request body for POST /api/v1/messages/threads/{id}/reply (Phase 116 MSG-02).

    extra='forbid' (inherited from BackendSchemaBase) rejects unknown fields.
    body must be non-empty and non-whitespace-only.
    max_length=4000 mirrors SendMessageRequest validation.
    """

    body: Annotated[str, Field(min_length=1, max_length=4000)]


class StaffThreadItem(ResponseData):
    """Single thread row in the staff inbox list (Phase 116 MSG-01).

    id: thread UUID.
    client_id (→ clientId on wire): the client's UUID.
    client_name (→ clientName on wire): first_name + last_name.
    client_initials (→ clientInitials on wire): 1-2 char uppercase initials.
    last_message_at (→ lastMessageAt on wire): when the last message was sent; None if empty.
    last_message_body (→ lastMessageBody on wire): body of the latest message; None if empty.
    last_message_role (→ lastMessageRole on wire): sender role of latest message; None if empty.
    staff_unread_count (→ staffUnreadCount on wire): count of client messages newer than
        staff_last_read_at (or all client messages if staff_last_read_at IS NULL).
    """

    id: UUID
    client_id: UUID
    client_name: str
    client_initials: str
    last_message_at: datetime | None = None
    last_message_body: str | None = None
    last_message_role: str | None = None
    staff_unread_count: int


class StaffInboxResponse(ResponseData):
    """Paginated staff inbox response (Phase 116 MSG-01).

    items: list of all client threads ordered by last_message_at DESC.
    total: total thread count (same as len(items) — inbox is not paginated in v1).
    """

    items: list[StaffThreadItem]
    total: int


class StaffMessageItem(ResponseData):
    """Single message row in the staff thread history (Phase 116 MSG-01).

    id: message UUID.
    role: 'client' or 'staff'.
    body: message text.
    sent_at (→ sentAt on wire): when the message was sent.
    """

    id: UUID
    role: str
    body: str
    sent_at: datetime


class StaffThreadHistoryResponse(ResponseData):
    """Full history of a single client↔gym thread (Phase 116 MSG-01).

    thread_id (→ threadId on wire): the thread UUID.
    messages: list of all messages in the thread, chronological order (oldest first).
    """

    thread_id: UUID
    messages: list[StaffMessageItem]


class AttachmentUploadResponse(ResponseData):
    """Response for POST /client/messages/attachments (Phase 92 ATT-01).

    Returned by service.create_attachment after the file is stored in S3 and
    a message_attachments row is persisted.

    attachment_id (→ attachmentId on wire via alias_generator=to_camel): the
    new message_attachments.id UUID, used by the client to attach to a message.
    preview_url (→ previewUrl on wire): relative path to the authenticated
    serve endpoint /api/v1/client/messages/attachments/{attachment_id}. The
    PWA must fetch this URL with credentials — NOT a presigned URL (D-92-ATT-03).

    The Python attribute is named attachment_id (not id) so the to_camel
    alias generator produces attachmentId on the wire (per plan contract).
    """

    attachment_id: UUID
    preview_url: str
