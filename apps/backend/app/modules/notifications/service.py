"""Notifications service (Phase 87 INBOX-01..04).

No session.commit() — caller-owns-txn (D-32-10/D-49-19).

Dedup approach: repository.insert_notification uses pg_insert ON CONFLICT DO NOTHING
on the named UNIQUE constraint (not IntegrityError + rollback) — SAVEPOINT-safe so
callers in event hooks / webhook handlers don't break the outer transaction (T-87-03).

Public API (consumed by Plan 02 client router + Plan 03 event hooks):
  create_notification         — co-transactional insert with UNIQUE dedup (T-87-03)
  list_client_notifications   — paginated inbox read with unread_count
  mark_notification_read      — UPDATE WHERE client_id (IDOR-safe, T-87-01)
  mark_all_notifications_read — bulk mark-read scoped to caller (T-87-01)
  register_push_token         — idempotent upsert (alive) push-token (T-87-04)
"""

from __future__ import annotations

from uuid import UUID

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.core.pagination import PageQuery
from app.modules.notifications import repository
from app.modules.notifications.schemas import (
    ClientNotificationItem,
    ClientNotificationsListResponse,
    ClientPushTokenRegisterRequest,
)

_log = structlog.get_logger("modules.notifications.service")


async def create_notification(
    session: AsyncSession,
    *,
    client_id: UUID,
    source_type: str,
    source_id: UUID,
    kind: str,
    title: str,
    body: str,
) -> None:
    """Insert one in-app inbox row co-transactionally (caller-owns-txn).

    Idempotent: ON CONFLICT DO NOTHING on the named UNIQUE constraint
    uq_in_app_notifications_client_source_kind — duplicate calls return silently
    without raising or rolling back the session (SAVEPOINT-safe, T-87-03).

    Never raises — callers (event hooks, webhook handlers) depend on fire-and-return
    semantics. The dedup conflict is logged at INFO level for observability.
    """
    inserted = await repository.insert_notification(
        session,
        client_id=client_id,
        source_type=source_type,
        source_id=source_id,
        kind=kind,
        title=title,
        body=body,
    )
    if not inserted:
        _log.info(
            "notification_dedup_conflict",
            client_id=str(client_id),
            source_type=source_type,
            source_id=str(source_id),
            kind=kind,
            msg="duplicate notification suppressed",
        )


async def list_client_notifications(
    session: AsyncSession,
    client_id: UUID,
    query: PageQuery,
) -> ClientNotificationsListResponse:
    """Return paginated inbox rows for the principal (INBOX-01).

    Ordered newest-first (created_at DESC). Includes server-computed unread_count.
    D-20-IDOR: client_id always from the caller's principal, never from the URL.
    """
    total, unread_count = await repository.count_notifications(session, client_id)
    offset = (query.page - 1) * query.page_size
    rows = await repository.list_notifications(
        session,
        client_id,
        limit=query.page_size,
        offset=offset,
    )
    items = [
        ClientNotificationItem(
            id=row["id"],
            kind=row["kind"],
            title=row["title"],
            body=row["body"],
            read_at=row["read_at"],
            created_at=row["created_at"],
        )
        for row in rows
    ]
    return ClientNotificationsListResponse(
        items=items,
        total=total,
        page=query.page,
        page_size=query.page_size,
        unread_count=unread_count,
    )


async def mark_notification_read(
    session: AsyncSession,
    *,
    client_id: UUID,
    notification_id: UUID,
) -> ClientNotificationItem:
    """Mark a single notification read; 404-collapse on non-owned or already-read rows.

    UPDATE WHERE id=:id AND client_id=:cid AND read_at IS NULL.
    If no row was updated → NotFoundError (IDOR-safe: caller cannot distinguish
    "wrong owner" from "already read" from "id doesn't exist", T-87-01).

    Returns the now-read item.
    No session.commit() — caller-owns-txn.
    """
    updated = await repository.mark_read(
        session,
        client_id=client_id,
        notification_id=notification_id,
    )
    if not updated:
        raise NotFoundError("notification_not_found")

    row = await repository.fetch_one_owned(
        session,
        client_id=client_id,
        notification_id=notification_id,
    )
    if row is None:
        # Defensive: concurrent delete between mark_read and fetch (extremely rare).
        raise NotFoundError("notification_not_found")

    return ClientNotificationItem(
        id=row["id"],
        kind=row["kind"],
        title=row["title"],
        body=row["body"],
        read_at=row["read_at"],
        created_at=row["created_at"],
    )


async def mark_all_notifications_read(
    session: AsyncSession,
    *,
    client_id: UUID,
) -> None:
    """Mark all unread notifications as read for the calling client (INBOX-01).

    UPDATE WHERE client_id=:cid AND read_at IS NULL — scoped at SQL level (T-87-01).
    No session.commit() — caller-owns-txn.
    """
    await repository.mark_all_read(session, client_id=client_id)


async def register_push_token(
    session: AsyncSession,
    *,
    client_id: UUID,
    payload: ClientPushTokenRegisterRequest,
) -> None:
    """Idempotent upsert of a push token for the calling client (INBOX-02).

    Keyed by (client_id, token) alive: a second registration of the same token
    is a no-op (alive row already exists). A previously unregistered token is
    revived (unregistered_at → NULL). T-87-04: platform is constrained by the DB
    CheckConstraint (web/android/ios).

    No session.commit() — caller-owns-txn.
    """
    await repository.upsert_push_token(
        session,
        client_id=client_id,
        token=payload.token,
        platform=payload.platform,
    )
