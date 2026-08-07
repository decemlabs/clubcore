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
            text("SELECT id FROM message_threads WHERE client_id = :cid"),
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
    attachment_id: UUID | None = None,
) -> tuple[UUID, datetime]:
    """Insert a message row and update thread metadata; return (message_id, sent_at).

    For role='client': bump message_threads.last_message_at = now().
    For role='staff': bump last_message_at AND increment client_unread_count by 1
    (staff sends → client has new unread message).

    WR-05: ``role`` is typed ``Literal['client','staff']`` (the DB CHECK domain) and
    validated explicitly before any SQL is issued, so a bad value fails fast in
    Python rather than poisoning the caller's open transaction with an IntegrityError.

    sent_at defaults to now() if not provided.
    attachment_id (optional): set messages.attachment_id for attachment-bearing messages
    (Phase 92 ATT-03 two-step flow). Must be an already-persisted message_attachments.id.
    No session.commit() — caller-owns-txn.
    """
    if role not in ("client", "staff"):
        # Defensive: fail fast in Python before entering the DB round-trip so a
        # bad role never poisons the caller's open UoW (WR-05).
        raise ValueError(f"invalid message role: {role!r} (expected 'client' or 'staff')")

    effective_sent_at = sent_at or datetime.now(tz=UTC)

    # Insert the message row (with optional attachment_id).
    result = await session.execute(
        text(
            "INSERT INTO messages (thread_id, role, body, sent_at, attachment_id) "
            "VALUES (:tid, :role, :body, :sent_at, :att_id) "
            "RETURNING id, sent_at"
        ),
        {
            "tid": str(thread_id),
            "role": role,
            "body": body,
            "sent_at": effective_sent_at,
            "att_id": str(attachment_id) if attachment_id is not None else None,
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
        (
            await session.execute(
                text(
                    "SELECT "
                    "  (SELECT COUNT(*) FROM messages WHERE thread_id = :tid) AS total, "
                    "  client_unread_count "
                    "FROM message_threads WHERE id = :tid"
                ),
                {"tid": str(thread_id)},
            )
        )
        .mappings()
        .one()
    )
    total = int(counts["total"])
    unread_count = int(counts["client_unread_count"])

    # Build message list query with LEFT JOIN on message_attachments for attachment sub-object.
    # Phase 92 ATT-03: attachment columns projected so service can build MessageAttachmentItem.
    # Columns and JOIN clause are fixed server-side strings (no user input, no injection risk).
    select_cols = (
        "m.id, m.role, m.body, m.sent_at, m.read_at, m.thread_id, "
        "ma.id AS att_id, ma.mime_type AS att_mime, ma.size_bytes AS att_size"
    )
    from_join = "FROM messages m LEFT JOIN message_attachments ma ON ma.id = m.attachment_id"
    if after is not None:
        # CR-01 / WR-04 catch-up cursor: native (sent_at, id) tuple comparison
        # (not id::text), thread-scoped cursor subquery, chronological-forward
        # order, and NO offset (cursor + offset are mutually exclusive).
        rows = (
            (
                await session.execute(
                    text(
                        f"SELECT {select_cols} "  # noqa: S608 — columns are server-defined constants
                        f"{from_join} "
                        "WHERE m.thread_id = :tid "
                        "  AND (m.sent_at, m.id) > "
                        "      (SELECT sent_at, id FROM messages "
                        "       WHERE id = :after_id AND thread_id = :tid) "
                        "ORDER BY m.sent_at ASC, m.id ASC "
                        "LIMIT :limit"
                    ),
                    {
                        "tid": str(thread_id),
                        "after_id": str(after),
                        "limit": page_size,
                    },
                )
            )
            .mappings()
            .all()
        )
    else:
        offset = (page - 1) * page_size
        rows = (
            (
                await session.execute(
                    text(
                        f"SELECT {select_cols} "
                        f"{from_join} "
                        "WHERE m.thread_id = :tid "
                        "ORDER BY m.sent_at DESC, m.id DESC "
                        "LIMIT :limit OFFSET :offset"
                    ),
                    {"tid": str(thread_id), "limit": page_size, "offset": offset},
                )
            )
            .mappings()
            .all()
        )

    return [dict(r) for r in rows], total, unread_count


async def get_owned_attachment(
    session: AsyncSession,
    attachment_id: UUID,
    *,
    client_id: UUID,
) -> dict[str, object] | None:
    """Return attachment row dict if attachment_id is owned by client_id; else None (ATT-03 IDOR).

    The client_id predicate IS the IDOR gate (P8 / MSG-02 precedent):
    a non-owned or missing id yields no row → None. The caller maps None to
    404 (never 403 — no existence leak, 404-collapse).

    Returns dict with keys: id, object_key, mime_type, size_bytes, thread_id.
    Raw-SQL text() per D-54-08.
    No session.commit() — caller-owns-txn.
    """
    row = (
        (
            await session.execute(
                text(
                    "SELECT id, object_key, mime_type, size_bytes, thread_id "
                    "FROM message_attachments "
                    "WHERE id = :aid AND client_id = :cid"
                ),
                {"aid": str(attachment_id), "cid": str(client_id)},
            )
        )
        .mappings()
        .one_or_none()
    )
    if row is None:
        return None
    return dict(row)


async def insert_attachment(
    session: AsyncSession,
    *,
    thread_id: UUID,
    client_id: UUID,
    mime_type: str,
    object_key: str,
    size_bytes: int,
) -> UUID:
    """Insert a message_attachments row and return the new attachment id (Phase 92 ATT-01).

    Raw-SQL text() INSERT ... RETURNING id (D-54-08 cross-module read discipline).
    No session.commit() — caller-owns-txn (D-32-10/D-49-19).

    client_id is ALWAYS the principal's id (IDOR anchor — T-92-07): callers must
    source it from require_client() only, never from user input.
    object_key is a server-generated UUID-based path (T-92-08: no user filename).
    """
    result = await session.execute(
        text(
            "INSERT INTO message_attachments "
            "    (thread_id, client_id, mime_type, object_key, size_bytes) "
            "VALUES (:tid, :cid, :mime, :key, :size) "
            "RETURNING id"
        ),
        {
            "tid": str(thread_id),
            "cid": str(client_id),
            "mime": mime_type,
            "key": object_key,
            "size": size_bytes,
        },
    )
    row = result.scalar_one()
    return UUID(str(row))


async def mark_client_messages_read(
    session: AsyncSession,
    client_id: UUID,
    *,
    thread_id: UUID | None = None,
) -> datetime | None:
    """Mark all unread role='client' messages as read; return max sent_at (Phase 91 RCPT-03).

    Reply-as-read path: when a staff member replies to a client, all prior unread
    messages sent by the CLIENT (role='client') are marked read. This is the INVERSE
    of mark_thread_read (which marks role='staff' messages read when the CLIENT reads them).

    Role split (do NOT conflate — 91-CONTEXT.md):
      mark_thread_read     → role='staff'  (client reads staff messages → resets unread counter)
      mark_client_messages_read → role='client' (staff replies → client's ✓✓ display, RCPT-01/03)

    thread_id (WR-01): callers that have ALREADY resolved the thread (e.g.
    record_staff_message resolves it once to scope the staff-message insert) MUST pass
    the pre-resolved thread_id so this UPDATE is scoped by the SAME id the insert uses.
    This eliminates a redundant second get_or_create_thread round-trip and removes the
    latent inconsistency seam where two independent resolutions could diverge (e.g. under
    a future soft-delete/re-create path), landing the staff message in a different thread
    than the one whose client messages were marked read. When None (no pre-resolved id is
    available), the thread is resolved here via get_or_create_thread.

    Returns:
      The max sent_at WATERMARK of the rows whose read_at was set in this call, or None if
      there was nothing to mark (no unread role='client' messages in the thread).
      This is a SEND-TIME watermark (the original client send times), NOT a read-clock
      value: the DB read_at is set to now() and is strictly later than this max(sent_at).
      The returned datetime drives the thread-level readAt in the WS read_receipt event
      (client marks all its sent messages with sent_at <= readAt as ✓✓ — see WR-02).

    Does NOT touch client_unread_count — that counter tracks staff→client unread (MSG-04),
    not the reply-as-read direction.

    Uses RETURNING sent_at to detect changes (mypy-safe, no .rowcount).
    Uses text() + :name bind params; UUIDs cast to str (D-54-08).
    No session.commit() — caller-owns-txn (D-32-10/D-49-19).

    T-91-XTHREAD: WHERE clause is scoped to thread_id from get_or_create_thread(client_id)
    (or the caller-supplied pre-resolved thread_id) so cross-thread / cross-client
    read-marking is impossible.
    """
    if thread_id is None:
        thread_id = await get_or_create_thread(session, client_id)

    # Mark unread client messages as read; RETURNING sent_at to compute max.
    #
    # WR-03: under the default READ COMMITTED isolation this watermark may
    # transiently OVER-COVER a concurrent same-thread client send. A client
    # message that commits after this UPDATE's snapshot but with sent_at earlier
    # than the computed max satisfies `sent_at <= readAt` on the client and would
    # be shown ✓✓ even though its read_at stays NULL in the DB. This thread-level
    # marker tradeoff is explicitly ACCEPTED (91-CONTEXT.md:40-42): the next REST
    # refetch (triggered by the new_message frame) is the source of truth and
    # self-heals the display. Do NOT "tighten" this into a per-message guarantee.
    updated = (
        await session.execute(
            text(
                "UPDATE messages "
                "SET read_at = now(), updated_at = now() "
                "WHERE thread_id = :tid AND role = 'client' AND read_at IS NULL "
                "RETURNING sent_at"
            ),
            {"tid": str(thread_id)},
        )
    ).fetchall()

    if not updated:
        return None

    # Return the maximum sent_at watermark so the caller can drive the thread-level
    # readAt. This is a send-time cutoff, not a read timestamp (see docstring / WR-02).
    max_sent_at: datetime = max(row[0] for row in updated)
    return max_sent_at


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


async def list_all_threads_with_unread(
    session: AsyncSession,
) -> list[dict[str, Any]]:
    """Return all threads with staff_unread_count, last_message preview (Phase 116 MSG-01).

    staff_unread_count = COUNT(*) of messages WHERE role='client'
    AND (staff_last_read_at IS NULL OR sent_at > staff_last_read_at).
    NULL staff_last_read_at means never read by staff → all client messages counted.

    WR-03 — WATERMARK TRADEOFF (mirrors mark_client_messages_read at repository.py):
      Staff-side unread is a strict `sent_at > staff_last_read_at` comparison against a
      single per-thread timestamp WATERMARK (set by mark_staff_thread_read = now()), NOT
      a per-message read flag. A client message whose sent_at equals the mark-read now()
      to the timestamp resolution — or one that commits with an earlier sent_at but after
      the mark-read snapshot under READ COMMITTED — can be transiently mis-counted (hidden
      as read or shown as unread). This thread-level marker tradeoff is intentional and
      ACCEPTED: the next inbox poll self-heals the count (it is a near-realtime triage
      hint, NOT an exact per-message guarantee). Do NOT "tighten" this into a per-message
      read flag or treat the count as exact.

    Joins to clients table (alive only: deleted_at IS NULL) to get first/last name.
    Orders by last_message_at DESC NULLS LAST (threads with no messages appear last).

    raw SQL text() + :name bind params (D-54-08 cross-module read discipline).
    No session.commit() — caller-owns-txn (D-32-10/D-49-19).
    """
    rows = (
        (
            await session.execute(
                text(
                    "SELECT "
                    "  mt.id, mt.client_id, mt.last_message_at, "
                    "  mt.staff_last_read_at, "
                    "  ( SELECT COUNT(*) FROM messages m "
                    "    WHERE m.thread_id = mt.id AND m.role = 'client' "
                    "    AND (mt.staff_last_read_at IS NULL OR m.sent_at > mt.staff_last_read_at) "
                    "  ) AS staff_unread_count, "
                    "  ( SELECT m2.body FROM messages m2 "
                    "    WHERE m2.thread_id = mt.id "
                    "    ORDER BY m2.sent_at DESC LIMIT 1 "
                    "  ) AS last_message_body, "
                    "  ( SELECT m3.role FROM messages m3 "
                    "    WHERE m3.thread_id = mt.id "
                    "    ORDER BY m3.sent_at DESC LIMIT 1 "
                    "  ) AS last_message_role, "
                    "  c.first_name, c.last_name "
                    "FROM message_threads mt "
                    "JOIN clients c ON c.id = mt.client_id AND c.deleted_at IS NULL "
                    "ORDER BY mt.last_message_at DESC NULLS LAST"
                )
            )
        )
        .mappings()
        .all()
    )
    return [dict(r) for r in rows]


async def get_thread_client_id(
    session: AsyncSession,
    thread_id: UUID,
) -> UUID | None:
    """Resolve client_id from message_threads.id via raw SQL (Phase 116 MSG-01).

    Returns None if the thread_id does not exist.
    Used by staff history + reply endpoints to call the existing client_id-keyed functions.
    raw SQL text() + :name bind params (D-54-08 cross-module read discipline).
    No session.commit() — caller-owns-txn (D-32-10/D-49-19).
    """
    row = (
        (
            await session.execute(
                text("SELECT client_id FROM message_threads WHERE id = :tid"),
                {"tid": str(thread_id)},
            )
        )
        .mappings()
        .one_or_none()
    )
    if row is None:
        return None
    return UUID(str(row["client_id"]))


async def mark_staff_thread_read(
    session: AsyncSession,
    thread_id: UUID,
) -> None:
    """Set staff_last_read_at = now() for thread; staff unread is derived from this watermark.

    No RETURNING needed — unread count is derived on read from the staff_last_read_at
    watermark (COUNT WHERE role='client' AND sent_at > watermark). No counter to recompute.

    WR-03 — WATERMARK TRADEOFF (mirrors mark_client_messages_read at repository.py):
      This sets a single per-thread timestamp watermark = now(); list_all_threads_with_unread
      then derives staff unread via a strict `sent_at > staff_last_read_at` comparison. Because
      this is a timestamp watermark and NOT a per-message read flag, a client message whose
      sent_at lands at/just before this now() (timestamp resolution, or a concurrent same-thread
      send under READ COMMITTED) may be transiently mis-counted. This is intentional and ACCEPTED
      (thread-level marker, self-heals on the next inbox poll). Do NOT tighten it into a
      per-message guarantee. See list_all_threads_with_unread for the read-side note + the
      boundary test in tests/integration/messaging/test_staff_messaging.py.

    raw SQL text() + :name bind params (D-54-08 discipline).
    No session.commit() — caller-owns-txn (D-32-10/D-49-19).
    """
    await session.execute(
        text(
            "UPDATE message_threads "
            "SET staff_last_read_at = now(), updated_at = now() "
            "WHERE id = :tid"
        ),
        {"tid": str(thread_id)},
    )


async def list_thread_messages_for_staff(
    session: AsyncSession,
    thread_id: UUID,
) -> list[dict[str, Any]]:
    """Return all messages in a thread chronological (oldest first) for staff view (Phase 116).

    Staff thread history is a full chronological list (not paginated, no after cursor).
    Returns id, role, body, sent_at for each message.

    raw SQL text() + :name bind params (D-54-08 cross-module read discipline).
    No session.commit() — caller-owns-txn.
    """
    rows = (
        (
            await session.execute(
                text(
                    "SELECT id, role, body, sent_at "
                    "FROM messages "
                    "WHERE thread_id = :tid "
                    "ORDER BY sent_at ASC, id ASC"
                ),
                {"tid": str(thread_id)},
            )
        )
        .mappings()
        .all()
    )
    return [dict(r) for r in rows]


async def get_client_display(
    session: AsyncSession,
    client_id: UUID,
) -> dict[str, str] | None:
    """Return first_name, last_name, phone for client_id via raw SQL (D-54-08).

    Phase 93 BRDG-01: used by the messaging router to render the client identity
    header for the staff Telegram DM. Cross-module read via raw SQL text() — ZERO
    new ignore_imports edges (per messaging module .importlinter comment).

    Returns None if the client row is missing or soft-deleted.
    No session.commit() — caller-owns-txn.
    """
    row = (
        (
            await session.execute(
                text(
                    "SELECT first_name, last_name, phone "
                    "FROM clients "
                    "WHERE id = :cid AND deleted_at IS NULL"
                ),
                {"cid": str(client_id)},
            )
        )
        .mappings()
        .one_or_none()
    )
    if row is None:
        return None
    return {
        "first_name": str(row["first_name"]),
        "last_name": str(row["last_name"]),
        "phone": str(row["phone"]),
    }
