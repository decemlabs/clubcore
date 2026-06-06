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
    """Mark a single notification read; idempotent for own rows, 404 for non-owned (WR-02 fix).

    Idempotency contract: marking an already-read OWN notification is a no-op → 200.
    Only genuinely absent or cross-client IDs return 404 (IDOR-safe, T-87-01).

    Two-phase approach (WR-02):
      1. Attempt UPDATE WHERE id=:id AND client_id=:cid AND read_at IS NULL.
         (Updates only if the row is unread — no-op if already read.)
      2. Fetch the row owned by this client regardless of read state.
         If None → the ID does not exist or belongs to another client → 404.
         Otherwise → return current state (read or just-marked-read).

    Returns the current item state.
    No session.commit() — caller-owns-txn.
    """
    # Attempt to mark as read (no-op if already read — UPDATE matches 0 rows).
    await repository.mark_read(
        session,
        client_id=client_id,
        notification_id=notification_id,
    )

    # Fetch the row owned by this client (IDOR-safe: WHERE client_id = :cid).
    row = await repository.fetch_one_owned(
        session,
        client_id=client_id,
        notification_id=notification_id,
    )
    if row is None:
        # Genuinely not found or belongs to a different client — 404.
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

    Globally unique by token (CR-03): device tokens are physically unique per device;
    registering an existing-alive token for a new client first soft-deletes any
    other client's alive row for that token, then assigns it to the calling client.
    A same-client re-registration of the same token is a no-op (alive row updated).
    A previously unregistered token is revived (unregistered_at → NULL).
    T-87-04: platform constrained by DB CheckConstraint (web/android/ios).

    No session.commit() — caller-owns-txn.
    """
    await repository.upsert_push_token(
        session,
        client_id=client_id,
        token=payload.token,
        platform=payload.platform,
    )
