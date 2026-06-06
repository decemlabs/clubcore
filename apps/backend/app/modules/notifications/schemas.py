"""Notifications module Pydantic schemas (Phase 87 INBOX-01/INBOX-02).

Response schemas use ResponseData (camelCase wire via alias_generator=to_camel).
Request schemas use BackendSchemaBase (extra='forbid', camelCase inbound).

ClientNotificationsListResponse is a custom DTO embedding unread_count alongside
the standard paginated fields — PaginatedData[T] cannot carry extra fields per the
generic base definition, so we replicate the page/page_size/total/items shape here.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from app.core.schemas import BackendSchemaBase, ResponseData


class ClientNotificationItem(ResponseData):
    """Single inbox row for a client (INBOX-01 read path).

    read_at None = unread; read_at = timestamp = read.
    created_at used for ordering (newest first).
    """

    id: UUID
    kind: str
    title: str
    body: str
    read_at: datetime | None = None
    created_at: datetime


class ClientNotificationsListResponse(ResponseData):
    """Paginated notification list with server-computed unread_count (INBOX-01).

    Field names mirror PaginatedData for wire consistency.
    page_size → pageSize camelCase via alias_generator=to_camel on ResponseData base.
    unread_count → unreadCount on the wire.
    """

    items: list[ClientNotificationItem]
    total: int
    page: int
    page_size: int
    unread_count: int


class ClientPushTokenRegisterRequest(BackendSchemaBase):
    """Request body for POST /client/notifications/push-token (INBOX-02).

    extra='forbid' (inherited from BackendSchemaBase) rejects unknown fields (T-87-04).
    platform constrained to web/android/ios by the DB CheckConstraint (T-87-04).
    """

    token: str
    platform: str
