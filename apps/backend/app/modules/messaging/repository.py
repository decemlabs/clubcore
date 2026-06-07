"""Messaging module repository — raw-SQL reads + ORM writes (Phase 90 MSG-01..04).

CROSS-MODULE READ DISCIPLINE (D-54-08 / D-20-MODULE):
  - ``from sqlalchemy import text`` for all cross-module reads.
  - Bind params via ``:name`` placeholders + a dict; cast UUIDs to ``str``.
  - INSERT uses pg_insert ON CONFLICT DO NOTHING to handle get-or-create
    without IntegrityError + rollback (SAVEPOINT-safe).

INVARIANTS:
  - No session.commit() — caller-owns-txn (D-32-10/D-49-19).
  - get_or_create_thread uses pg_insert ON CONFLICT DO NOTHING to safely create
    the thread on first send/GET without racing (SAVEPOINT-safe).
  - list_thread_history resolves the thread via get_or_create so a first-time
    GET auto-creates the thread (empty list returned, not 404 — per CONTEXT.md).
  - Reads (COUNT / SELECT) use raw SQL text() per D-54-08 discipline.
  - mark_thread_read uses RETURNING to detect changes (mypy-safe, no .rowcount).
  - ZERO foreign ORM imports — messages module only (T-90-04 mitigate).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.messaging.models import MessageThread


async def get_or_create_thread(
    session: AsyncSession,
    client_id: UUID,
) -> UUID:
    """Lazily create the single 1:1 thread for a client; return its id (MSG-01).

    Uses pg_insert ON CONFLICT DO NOTHING on uq_message_threads_client_id.
    If the INSERT fires (new thread): returns the inserted id.
    If the conflict fires (thread exists): falls through to SELECT.
    SAVEPOINT-safe: no IntegrityError raised, no rollback needed by the caller.
    No session.commit() — caller-owns-txn.
    """
    stmt = (
        pg_insert(MessageThread)
        .values(client_id=client_id)
        .on_conflict_do_nothing(constraint="uq_message_threads_client_id")
        .returning(MessageThread.id)
    )
    inserted_id = (await session.execute(stmt)).scalar_one_or_none()
    if inserted_id is not None:
        return UUID(str(inserted_id))

    # Conflict fired — SELECT the existing thread id.
    row = (
        await session.execute(
            text(
                "SELECT id FROM message_threads WHERE client_id = :cid"
            ),
            {"cid": str(client_id)},
        )
    ).scalar_one()
    return UUID(str(row))


async def insert_message(
    session: AsyncSession,
    *,
    thread_id: UUID,
    role: Literal["client", "staff"],
    body: str,
    sent_at: datetime | None = None,
) -> tuple[UUID, datetime]:
    """Insert a message row and update thread metadata; return (message_id, sent_at).

    For role='client': bump message_threads.last_message_at = now().
    For role='staff': bump last_message_at AND increment client_unread_count by 1
    (staff sends → client has new unread message).

    WR-05: ``role`` is typed ``Literal['client','staff']`` (the DB CHECK domain) and
    validated explicitly before any SQL is issued, so a bad value fails fast in
    Python rather than poisoning the caller's open transaction with an IntegrityError.

    sent_at defaults to now() if not provided.
    No session.commit() — caller-owns-txn.
    """
    if role not in ("client", "staff"):
        # Defensive: fail fast in Python before entering the DB round-trip so a
        # bad role never poisons the caller's open UoW (WR-05).
        raise ValueError(f"invalid message role: {role!r} (expected 'client' or 'staff')")

    effective_sent_at = sent_at or datetime.now(tz=UTC)

    # Insert the message row.
    result = await session.execute(
        text(
            "INSERT INTO messages (thread_id, role, body, sent_at) "
            "VALUES (:tid, :role, :body, :sent_at) "
            "RETURNING id, sent_at"
        ),
        {
            "tid": str(thread_id),
            "role": role,
            "body": body,
            "sent_at": effective_sent_at,
        },
    )
    row = result.mappings().one()
    message_id = UUID(str(row["id"]))
    actual_sent_at: datetime = row["sent_at"]

    # Update thread metadata based on sender role.
    if role == "staff":
        await session.execute(
            text(
                "UPDATE message_threads "
                "SET last_message_at = :ts, client_unread_count = client_unread_count + 1, "
                "    updated_at = now() "
                "WHERE id = :tid"
            ),
            {"ts": actual_sent_at, "tid": str(thread_id)},
        )
    else:
        # role == 'client'
        await session.execute(
            text(
                "UPDATE message_threads "
                "SET last_message_at = :ts, updated_at = now() "
                "WHERE id = :tid"
            ),
            {"ts": actual_sent_at, "tid": str(thread_id)},
        )

    return message_id, actual_sent_at


async def list_thread_history(
    session: AsyncSession,
    client_id: UUID,
    *,
    page: int,
    page_size: int,
    after: UUID | None = None,
) -> tuple[list[dict[str, Any]], int, int]:
    """Return (rows, total, unread_count) for a client's thread (MSG-01 + RT-04).

    Resolves (get-or-create) the thread for client_id so a first GET works even
    before the first message is sent (returns empty list, not 404 — per CONTEXT.md).

    Non-cursor (paged) wire delivery is newest-first (sent_at DESC, id DESC);
    PWA reverses for display.

    RT-04 catch-up cursor (CR-01 + WR-04): when ``after`` is provided, only
    messages STRICTLY NEWER than the cursor message are returned, using native
    composite ``(sent_at, id)`` tuple comparison (NOT lexicographic ``id::text``)
    so the boundary is stable even for same-``sent_at`` rows. The catch-up band is
    delivered chronological-forward (``sent_at ASC, id ASC``) with NO offset —
    cursor and offset pagination are mutually exclusive, and DESC+OFFSET on the
    newer-than set would silently drop an arbitrary middle band of missed messages.
    The cursor subquery is thread-scoped so a foreign/unknown message id cannot be
    used as a recency-probing oracle and resolves to no boundary (empty page).

    total = COUNT(*) for the entire thread (not affected by the after cursor).
    unread_count = message_threads.client_unread_count.
    No session.commit() — caller-owns-txn.
    """
    thread_id = await get_or_create_thread(session, client_id)

    # Resolve total + unread_count from the thread row.
    counts = (
        await session.execute(
            text(
                "SELECT "
                "  (SELECT COUNT(*) FROM messages WHERE thread_id = :tid) AS total, "
                "  client_unread_count "
                "FROM message_threads WHERE id = :tid"
            ),
            {"tid": str(thread_id)},
        )
    ).mappings().one()
    total = int(counts["total"])
    unread_count = int(counts["client_unread_count"])

    # Build message list query.
    if after is not None:
        # CR-01 / WR-04 catch-up cursor: native (sent_at, id) tuple comparison
        # (not id::text), thread-scoped cursor subquery, chronological-forward
        # order, and NO offset (cursor + offset are mutually exclusive).
        rows = (
            await session.execute(
                text(
                    "SELECT id, role, body, sent_at, read_at, thread_id "
                    "FROM messages "
                    "WHERE thread_id = :tid "
                    "  AND (sent_at, id) > "
                    "      (SELECT sent_at, id FROM messages "
                    "       WHERE id = :after_id AND thread_id = :tid) "
                    "ORDER BY sent_at ASC, id ASC "
                    "LIMIT :limit"
                ),
                {
                    "tid": str(thread_id),
                    "after_id": str(after),
                    "limit": page_size,
                },
            )
        ).mappings().all()
    else:
        offset = (page - 1) * page_size
        rows = (
            await session.execute(
                text(
                    "SELECT id, role, body, sent_at, read_at, thread_id "
                    "FROM messages "
                    "WHERE thread_id = :tid "
                    "ORDER BY sent_at DESC, id DESC "
                    "LIMIT :limit OFFSET :offset"
                ),
                {"tid": str(thread_id), "limit": page_size, "offset": offset},
            )
        ).mappings().all()

    return [dict(r) for r in rows], total, unread_count


async def mark_thread_read(
    session: AsyncSession,
    client_id: UUID,
) -> bool:
    """Mark all unread staff messages as read; recompute client_unread_count (MSG-04).

    UPDATE messages SET read_at=now() WHERE role='staff' AND read_at IS NULL
    for the client's thread.

    WR-01: the unread counter is RECOMPUTED from the source of truth (the message
    rows) in the SAME statement, rather than blindly set to 0. A blind zero would
    clobber a staff increment that races in between the mark-read UPDATE and the
    counter write — leaving the client showing 0 unread while an unread staff
    message exists. Deriving the count from
    ``COUNT(*) WHERE role='staff' AND read_at IS NULL`` keeps the counter and the
    actual unread row set consistent under concurrent staff sends.

    Uses RETURNING to detect whether any row was changed (mypy-safe, no .rowcount).
    Returns True if anything was marked; False if there was nothing to mark.
    No session.commit() — caller-owns-txn.
    """
    # Resolve thread (get-or-create so mark-read on an empty thread is a no-op).
    thread_id = await get_or_create_thread(session, client_id)

    # Mark unread staff messages as read; RETURNING id detects whether any changed.
    updated = (
        await session.execute(
            text(
                "UPDATE messages "
                "SET read_at = now(), updated_at = now() "
                "WHERE thread_id = :tid AND role = 'staff' AND read_at IS NULL "
                "RETURNING id"
            ),
            {"tid": str(thread_id)},
        )
    ).fetchall()

    # WR-01: recompute the unread counter from the message rows rather than
    # blind-zeroing, so a concurrent staff increment is not clobbered.
    await session.execute(
        text(
            "UPDATE message_threads "
            "SET client_unread_count = ("
            "        SELECT COUNT(*) FROM messages "
            "        WHERE thread_id = :tid AND role = 'staff' AND read_at IS NULL"
            "    ), "
            "    updated_at = now() "
            "WHERE id = :tid"
        ),
        {"tid": str(thread_id)},
    )

    return len(updated) > 0
