"""Notifications module repository — raw-SQL reads + ORM writes (Phase 87 INBOX-01/INBOX-02).

CROSS-MODULE READ DISCIPLINE (D-54-08 / D-20-MODULE):
  - ``from sqlalchemy import text`` for all cross-module reads.
  - Bind params via ``:name`` placeholders + a dict; cast UUIDs to ``str``.
  - INSERT uses pg_insert ON CONFLICT DO NOTHING to handle dedup without
    IntegrityError + rollback (SAVEPOINT-safe; mirrors loyalty accrue_welcome_bonus).

INVARIANTS:
  - No session.commit() — caller-owns-txn (D-32-10/D-49-19).
  - INSERT uses pg_insert ON CONFLICT DO NOTHING + flush (SAVEPOINT-safe dedup path).
  - Reads (COUNT / SELECT) use raw SQL text() per D-54-08 discipline.
  - mark_read / mark_all_read / upsert_push_token use raw UPDATE / INSERT ... ON CONFLICT.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.notifications.models import ClientPushToken, InAppNotification


async def insert_notification(
    session: AsyncSession,
    *,
    client_id: UUID,
    source_type: str,
    source_id: UUID,
    kind: str,
    title: str,
    body: str,
) -> bool:
    """Insert a notification row with ON CONFLICT DO NOTHING (idempotent dedup, T-87-03).

    Uses pg_insert ON CONFLICT ON CONSTRAINT uq_in_app_notifications_client_source_kind
    (named UNIQUE constraint — not a partial index, so ON CONSTRAINT works here,
    unlike loyalty_ledger which uses a partial index requiring index_elements).

    Returns True if a row was inserted, False if the conflict fired (dedup).
    SAVEPOINT-safe: no IntegrityError raised, no rollback needed by the caller.
    No session.commit() — caller-owns-txn.
    """
    stmt = (
        pg_insert(InAppNotification)
        .values(
            client_id=client_id,
            source_type=source_type,
            source_id=source_id,
            kind=kind,
            title=title,
            body=body,
        )
        .on_conflict_do_nothing(
            constraint="uq_in_app_notifications_client_source_kind",
        )
        .returning(InAppNotification.id)
    )
    result = await session.execute(stmt)
    inserted_id = result.scalar_one_or_none()
    return inserted_id is not None


async def count_notifications(
    session: AsyncSession,
    client_id: UUID,
) -> tuple[int, int]:
    """Return (total, unread_count) for a client.

    total = COUNT(*) all rows for client.
    unread_count = COUNT(*) WHERE read_at IS NULL.
    """
    row = (
        (
            await session.execute(
                text(
                    "SELECT "
                    "  COUNT(*) AS total, "
                    "  COUNT(*) FILTER (WHERE read_at IS NULL) AS unread_count "
                    "FROM in_app_notifications "
                    "WHERE client_id = :cid"
                ),
                {"cid": str(client_id)},
            )
        )
        .mappings()
        .one()
    )
    return int(row["total"]), int(row["unread_count"])


async def list_notifications(
    session: AsyncSession,
    client_id: UUID,
    *,
    limit: int,
    offset: int,
) -> list[dict[str, Any]]:
    """Return paginated notification rows, newest-first (ORDER BY created_at DESC).

    Returns a list of row dicts with keys: id, kind, title, body, read_at, created_at.
    """
    rows = (
        (
            await session.execute(
                text(
                    "SELECT id, kind, title, body, read_at, created_at "
                    "FROM in_app_notifications "
                    "WHERE client_id = :cid "
                    "ORDER BY created_at DESC "
                    "LIMIT :limit OFFSET :offset"
                ),
                {"cid": str(client_id), "limit": limit, "offset": offset},
            )
        )
        .mappings()
        .all()
    )
    return [dict(row) for row in rows]


async def mark_read(
    session: AsyncSession,
    *,
    client_id: UUID,
    notification_id: UUID,
) -> bool:
    """UPDATE read_at=now() WHERE id AND client_id AND read_at IS NULL.

    Returns True if a row was updated (found and was unread), False otherwise.
    Uses RETURNING id + scalar_one_or_none() to detect whether a row was updated
    (avoids Result.rowcount which is not surfaced by mypy's async type stubs).
    No session.commit() — caller-owns-txn.
    """
    updated_id = (
        await session.execute(
            text(
                "UPDATE in_app_notifications "
                "SET read_at = now(), updated_at = now() "
                "WHERE id = :id AND client_id = :cid AND read_at IS NULL "
                "RETURNING id"
            ),
            {"id": str(notification_id), "cid": str(client_id)},
        )
    ).scalar_one_or_none()
    return updated_id is not None


async def fetch_one_owned(
    session: AsyncSession,
    *,
    client_id: UUID,
    notification_id: UUID,
) -> dict[str, Any] | None:
    """SELECT a single notification row owned by client_id.

    Returns None if the row doesn't exist or doesn't belong to client_id (IDOR-safe).
    """
    row = (
        (
            await session.execute(
                text(
                    "SELECT id, kind, title, body, read_at, created_at "
                    "FROM in_app_notifications "
                    "WHERE id = :id AND client_id = :cid"
                ),
                {"id": str(notification_id), "cid": str(client_id)},
            )
        )
        .mappings()
        .one_or_none()
    )
    return dict(row) if row is not None else None


async def mark_all_read(
    session: AsyncSession,
    *,
    client_id: UUID,
) -> None:
    """UPDATE read_at=now() WHERE client_id AND read_at IS NULL (T-87-01).

    Scoped by client_id at the SQL level — cannot affect another client's rows.
    No session.commit() — caller-owns-txn.
    """
    await session.execute(
        text(
            "UPDATE in_app_notifications "
            "SET read_at = now(), updated_at = now() "
            "WHERE client_id = :cid AND read_at IS NULL"
        ),
        {"cid": str(client_id)},
    )


async def upsert_push_token(
    session: AsyncSession,
    *,
    client_id: UUID,
    token: str,
    platform: str,
) -> None:
    """Idempotent upsert of a push token (alive or previously unregistered).

    Strategy: UPDATE first (covers both "alive row" and "unregistered row");
    if no row was found (truly new token), INSERT.

    UPDATE path: sets unregistered_at = NULL (revives a soft-deleted token) and
    updates platform. This handles both "alive token re-register" (idempotent)
    and "previously unregistered token revival".

    INSERT path: only if no existing row for (client_id, token) at all.

    Partial UNIQUE on (client_id, token) WHERE unregistered_at IS NULL prevents
    duplicates for alive tokens. The UPDATE-first approach handles the unregistered
    revival case without needing a non-partial index.

    No session.commit() — caller-owns-txn.
    """
    # Attempt UPDATE on any existing row (alive or unregistered) for this (client, token)
    # Uses RETURNING id + scalar_one_or_none() to detect update vs. no-op.
    updated_id = (
        await session.execute(
            text(
                "UPDATE client_push_tokens "
                "SET unregistered_at = NULL, platform = :platform, updated_at = now() "
                "WHERE client_id = :cid AND token = :tok "
                "RETURNING id"
            ),
            {"cid": str(client_id), "tok": token, "platform": platform},
        )
    ).scalar_one_or_none()
    if updated_id is None:
        # No existing row — insert a fresh one
        new_token = ClientPushToken(
            client_id=client_id,
            token=token,
            platform=platform,
        )
        session.add(new_token)
        await session.flush()
