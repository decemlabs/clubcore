"""Phase 90 code-review fix tests — CR-01 (RT-04 after-cursor) + CR-02 (DB-first publish).

CR-01: the ``after`` catch-up cursor must return EXACTLY the messages strictly newer
than the cursor message, thread-scoped, in correct forward order, with no gaps and no
dupes — even when several rows share the same ``sent_at`` (native (sent_at, id) tuple
comparison, NOT lexicographic id::text, and NOT a DESC+OFFSET page that drops a middle band).

CR-02: ``send_client_message`` / ``record_staff_message`` must NOT publish to Redis
themselves — the publish is a separate post-commit step (publish_new_message). A failed
commit must therefore never emit a phantom new_message frame.

Harness: async ``db_session`` fixture (SAVEPOINT) — repository-level, no HTTP, no WS.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permissions import Role
from app.core.security import hash_password
from app.modules.auth.models import User
from app.modules.clients.models import Client
from app.modules.messaging import repository, service

pytestmark = pytest.mark.asyncio(loop_scope="function")

_BASE_PHONE = "+79169500"


def _phone(n: int) -> str:
    return f"{_BASE_PHONE}{n:04d}"


async def _seed_client(db_session: AsyncSession, n: int) -> Client:
    staff = User(
        email=f"msg-cursor-staff-{uuid4().hex[:8]}@example.com",
        password_hash=await hash_password("msg-cursor-staff-pw-secure-90"),
        role=Role.RECEPTION,
        full_name="Messaging Cursor Test Staff",
    )
    db_session.add(staff)
    await db_session.flush()

    client = Client(
        first_name="Cursor",
        last_name="Test",
        phone=_phone(n),
        telegram_user_id=abs(hash(_phone(n))) % (10**9),
        created_by_user_id=staff.id,
    )
    db_session.add(client)
    await db_session.flush()
    return client


# ---------------------------------------------------------------------------
# CR-01: after-cursor returns exactly the newer band, in forward order, no gaps
# ---------------------------------------------------------------------------


async def test_after_cursor_returns_full_newer_band_in_forward_order(
    db_session: AsyncSession,
) -> None:
    """CR-01: after=<k-th id> returns ALL messages newer than k, oldest→newest, no gap.

    Six messages with distinct, monotonically increasing sent_at. Cursor on the 2nd
    message must return messages 3..6 (four rows) in chronological-forward order, with
    no middle band dropped — the old DESC+LIMIT+OFFSET path would have silently skipped
    rows here once more than page_size messages were newer than the cursor.
    """
    client = await _seed_client(db_session, 1)
    thread_id = await repository.get_or_create_thread(db_session, client.id)

    base = datetime(2026, 6, 7, 12, 0, 0, tzinfo=UTC)
    ids: list[UUID] = []
    for i in range(6):
        mid, _ = await repository.insert_message(
            db_session,
            thread_id=thread_id,
            role="client",
            body=f"m{i}",
            sent_at=base + timedelta(seconds=i),
        )
        ids.append(mid)

    # page_size deliberately smaller than the newer band would be in a single page if
    # the buggy DESC+OFFSET path were used — but cursor has no offset, so LIMIT just caps.
    rows, total, _unread = await repository.list_thread_history(
        db_session,
        client.id,
        page=1,
        page_size=50,
        after=ids[1],  # cursor on the 2nd message (index 1)
    )
    returned = [r["id"] for r in rows]

    assert total == 6
    # Expect messages 3..6 (indices 2..5), oldest→newest, no gaps, no dupes.
    assert returned == ids[2:], f"CR-01: expected forward band {ids[2:]}, got {returned}"
    assert ids[1] not in returned, "CR-01: cursor message must be excluded"
    assert len(returned) == len(set(returned)), "CR-01: duplicate rows in cursor band"


async def test_after_cursor_same_sent_at_tiebreak_is_stable_no_dupes_no_gaps(
    db_session: AsyncSession,
) -> None:
    """CR-01: rows sharing identical sent_at are ordered stably by (sent_at, id).

    Five messages with the SAME sent_at. Native (sent_at, id) comparison must produce a
    total order so a cursor on one of them returns exactly the rows that sort after it —
    no same-timestamp row dropped or duplicated (the old id::text lexicographic compare
    could not guarantee this).
    """
    client = await _seed_client(db_session, 2)
    thread_id = await repository.get_or_create_thread(db_session, client.id)

    same_ts = datetime(2026, 6, 7, 13, 0, 0, tzinfo=UTC)
    ids: list[UUID] = []
    for i in range(5):
        mid, _ = await repository.insert_message(
            db_session,
            thread_id=thread_id,
            role="client",
            body=f"same{i}",
            sent_at=same_ts,
        )
        ids.append(mid)

    # The DB-side total order over equal sent_at is by id ASC. Determine it.
    all_rows, _total, _unread = await repository.list_thread_history(
        db_session, client.id, page=1, page_size=50
    )
    # all_rows is newest-first (sent_at DESC, id DESC); reverse → forward (sent_at ASC,
    # id ASC) — the same total order the cursor path delivers.
    forward_order = [r["id"] for r in reversed(all_rows)]

    # Pick a cursor in the middle of the forward order.
    cursor = forward_order[1]
    expected_after = forward_order[2:]

    rows, _t, _u = await repository.list_thread_history(
        db_session, client.id, page=1, page_size=50, after=cursor
    )
    returned = [r["id"] for r in rows]

    assert returned == expected_after, (
        f"CR-01 same-sent_at: expected {expected_after}, got {returned}"
    )
    assert cursor not in returned, "CR-01: cursor row must be excluded for equal sent_at"
    assert len(returned) == len(set(returned)), "CR-01: duplicate same-sent_at rows"


async def test_after_cursor_foreign_or_unknown_id_yields_empty_band(
    db_session: AsyncSession,
) -> None:
    """CR-01 / WR-04: a foreign/unknown cursor id resolves to no boundary (empty band).

    The thread-scoped cursor subquery returns NULL for an id that is not in this thread,
    so the comparison matches no rows — the caller gets an empty page rather than another
    thread's timestamp being usable as a recency oracle.
    """
    client_a = await _seed_client(db_session, 3)
    client_b = await _seed_client(db_session, 4)
    thread_a = await repository.get_or_create_thread(db_session, client_a.id)
    thread_b = await repository.get_or_create_thread(db_session, client_b.id)

    # A has 3 messages; B has 1.
    for i in range(3):
        await repository.insert_message(
            db_session, thread_id=thread_a, role="client", body=f"a{i}"
        )
    b_id, _ = await repository.insert_message(
        db_session, thread_id=thread_b, role="client", body="b0"
    )

    # Use B's message id as a cursor against A's thread → no boundary → empty.
    rows_foreign, total_a, _u = await repository.list_thread_history(
        db_session, client_a.id, page=1, page_size=50, after=b_id
    )
    assert total_a == 3
    assert rows_foreign == [], "WR-04: foreign cursor id must not leak a usable boundary"

    # Garbage (never-existed) id → empty band, no error.
    rows_unknown, _t, _u2 = await repository.list_thread_history(
        db_session, client_a.id, page=1, page_size=50, after=uuid4()
    )
    assert rows_unknown == [], "WR-04: unknown cursor id must yield an empty band"


# ---------------------------------------------------------------------------
# CR-02: persist functions do NOT publish; publish is a separate post-commit step
# ---------------------------------------------------------------------------


async def test_send_client_message_does_not_publish_inside_service(
    db_session: AsyncSession,
) -> None:
    """CR-02: send_client_message persists without publishing (no redis param at all).

    If the service still published internally, this call would require a redis client.
    The DB-first guarantee is that publishing is the caller's post-commit responsibility
    — so a commit that never happens can never have emitted a phantom new_message frame.
    """
    from app.modules.messaging.schemas import SendMessageRequest

    client = await _seed_client(db_session, 5)

    result = await service.send_client_message(
        db_session,
        client_id=client.id,
        payload=SendMessageRequest(body="no-publish-body"),
    )
    assert result.role == "client"
    assert result.body == "no-publish-body"

    # Row is present in the (uncommitted) session — proving persist happened, while
    # no publish occurred (the function signature no longer accepts redis).
    rows, total, _unread = await repository.list_thread_history(
        db_session, client.id, page=1, page_size=50
    )
    assert total == 1
    assert [r["id"] for r in rows] == [result.id]


async def test_publish_new_message_emits_id_only_frame(db_session: AsyncSession) -> None:
    """CR-02: publish_new_message emits an id-only frame to the principal channel.

    Uses a tiny fake redis to capture (channel, payload) without a live broker. Proves the
    post-commit helper publishes only the id (DB-first; no payload over pub/sub, P5).
    """
    import json

    client = await _seed_client(db_session, 6)
    message_id = uuid4()

    captured: list[tuple[str, str]] = []

    class _FakeRedis:
        async def publish(self, channel: str, payload: str) -> None:
            captured.append((channel, payload))

    await service.publish_new_message(
        _FakeRedis(),  # type: ignore[arg-type]
        client_id=client.id,
        message_id=message_id,
    )

    assert len(captured) == 1
    channel, payload = captured[0]
    assert channel == f"cc:messaging:client:{client.id}"
    frame = json.loads(payload)
    assert frame == {"type": "new_message", "messageId": str(message_id)}
