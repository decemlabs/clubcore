"""Phase 87 INBOX-01/INBOX-02/INBOX-03 — notifications service-layer behavior tests.

Tests cover every behavior bullet in the plan:
  - create_notification inserts a row; second identical call results in exactly ONE row (dedup).
  - list_client_notifications returns items DESC by created_at; correct total/unread_count.
  - mark_notification_read on another client's id raises NotFoundError (IDOR 404-collapse).
  - mark_notification_read on own unread notification sets read_at.
  - mark_all_notifications_read sets read_at on all unread rows only.
  - register_push_token twice with same (client_id, token) yields one alive row.
  - A previously unregistered token is revived (unregistered_at → NULL).
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.core.pagination import PageQuery
from app.modules.clients.models import Client
from app.modules.notifications import service
from app.modules.notifications.schemas import ClientPushTokenRegisterRequest

pytestmark = pytest.mark.asyncio(loop_scope="function")


# ── helpers ──────────────────────────────────────────────────────────────────


async def _create_notif(
    session: AsyncSession,
    client_id: object,
    *,
    kind: str = "booking_confirmed",
    source_id: object | None = None,
) -> None:
    await service.create_notification(
        session,
        client_id=client_id,  # type: ignore[arg-type]
        source_type="booking",
        source_id=source_id or uuid4(),  # type: ignore[arg-type]
        kind=kind,
        title="Бронирование подтверждено",
        body="Тренировка в 10:00",
    )


# ── create_notification — insert + dedup ─────────────────────────────────────


async def test_create_notification_inserts_row(
    db_session: AsyncSession,
    make_client: Callable[..., Awaitable[Client]],
) -> None:
    """create_notification inserts one row visible in DB."""
    client = await make_client()
    src_id = uuid4()
    await service.create_notification(
        db_session,
        client_id=client.id,
        source_type="booking",
        source_id=src_id,
        kind="booking_confirmed",
        title="Подтверждение",
        body="Тело",
    )
    await db_session.flush()
    row = (
        (
            await db_session.execute(
                text(
                    "SELECT COUNT(*) AS cnt FROM in_app_notifications "
                    "WHERE client_id = :cid AND source_id = :sid"
                ),
                {"cid": str(client.id), "sid": str(src_id)},
            )
        )
        .mappings()
        .one()
    )
    assert int(row["cnt"]) == 1


async def test_create_notification_dedup_results_in_one_row(
    db_session: AsyncSession,
    make_client: Callable[..., Awaitable[Client]],
) -> None:
    """Two identical create_notification calls → exactly ONE row (UNIQUE dedup, T-87-03)."""
    client = await make_client()
    src_id = uuid4()
    kwargs = {
        "client_id": client.id,
        "source_type": "booking",
        "source_id": src_id,
        "kind": "booking_confirmed",
        "title": "T",
        "body": "B",
    }
    await service.create_notification(db_session, **kwargs)  # type: ignore[arg-type]
    await db_session.flush()
    # Second call must NOT raise — dedup catches IntegrityError silently.
    await service.create_notification(db_session, **kwargs)  # type: ignore[arg-type]
    await db_session.flush()

    row = (
        (
            await db_session.execute(
                text(
                    "SELECT COUNT(*) AS cnt FROM in_app_notifications "
                    "WHERE client_id = :cid AND source_id = :sid AND kind = 'booking_confirmed'"
                ),
                {"cid": str(client.id), "sid": str(src_id)},
            )
        )
        .mappings()
        .one()
    )
    assert int(row["cnt"]) == 1


# ── list_client_notifications ─────────────────────────────────────────────────


async def test_list_client_notifications_returns_newest_first(
    db_session: AsyncSession,
    make_client: Callable[..., Awaitable[Client]],
) -> None:
    """list_client_notifications returns items in DESC created_at order."""
    client = await make_client()
    src1, src2 = uuid4(), uuid4()
    await service.create_notification(
        db_session,
        client_id=client.id,
        source_type="booking",
        source_id=src1,
        kind="booking_confirmed",
        title="Первое",
        body="",
    )
    await db_session.flush()
    # Small delay is not needed — we rely on the DB insertion order via created_at
    await service.create_notification(
        db_session,
        client_id=client.id,
        source_type="booking",
        source_id=src2,
        kind="booking_rescheduled",
        title="Второе",
        body="",
    )
    await db_session.flush()

    result = await service.list_client_notifications(
        db_session, client.id, PageQuery(page=1, page_size=20)
    )
    assert result.total == 2
    assert result.page == 1
    assert result.page_size == 20
    # newest (rescheduled, src2) should be first
    assert result.items[0].kind == "booking_rescheduled"
    assert result.items[1].kind == "booking_confirmed"


async def test_list_client_notifications_unread_count(
    db_session: AsyncSession,
    make_client: Callable[..., Awaitable[Client]],
) -> None:
    """unread_count reflects only rows with read_at IS NULL."""
    client = await make_client()
    src_read = uuid4()
    src_unread = uuid4()

    await service.create_notification(
        db_session,
        client_id=client.id,
        source_type="booking",
        source_id=src_read,
        kind="booking_confirmed",
        title="T",
        body="B",
    )
    await service.create_notification(
        db_session,
        client_id=client.id,
        source_type="booking",
        source_id=src_unread,
        kind="booking_rescheduled",
        title="T",
        body="B",
    )
    await db_session.flush()

    # Mark the first one as read directly in DB to avoid dependency on mark_read service
    await db_session.execute(
        text(
            "UPDATE in_app_notifications SET read_at = now() "
            "WHERE client_id = :cid AND source_id = :sid"
        ),
        {"cid": str(client.id), "sid": str(src_read)},
    )
    await db_session.flush()

    result = await service.list_client_notifications(
        db_session, client.id, PageQuery(page=1, page_size=20)
    )
    assert result.total == 2
    assert result.unread_count == 1


async def test_list_client_notifications_pagination(
    db_session: AsyncSession,
    make_client: Callable[..., Awaitable[Client]],
) -> None:
    """Pagination respects page/page_size; page 2 returns the right slice."""
    client = await make_client()
    # Insert 3 rows with distinct source_ids
    for _ in range(3):
        await service.create_notification(
            db_session,
            client_id=client.id,
            source_type="booking",
            source_id=uuid4(),
            kind="booking_confirmed",
            title="T",
            body="B",
        )
    await db_session.flush()

    page1 = await service.list_client_notifications(
        db_session, client.id, PageQuery(page=1, page_size=2)
    )
    page2 = await service.list_client_notifications(
        db_session, client.id, PageQuery(page=2, page_size=2)
    )
    assert page1.total == 3
    assert len(page1.items) == 2
    assert page2.total == 3
    assert len(page2.items) == 1


# ── mark_notification_read ────────────────────────────────────────────────────


async def test_mark_notification_read_idor_raises_not_found(
    db_session: AsyncSession,
    make_client: Callable[..., Awaitable[Client]],
) -> None:
    """mark_notification_read on another client's notification → NotFoundError (IDOR 404-collapse, T-87-01)."""
    owner_client = await make_client()
    other_client = await make_client()

    src_id = uuid4()
    await service.create_notification(
        db_session,
        client_id=owner_client.id,
        source_type="booking",
        source_id=src_id,
        kind="booking_confirmed",
        title="T",
        body="B",
    )
    await db_session.flush()

    # Fetch the notification id directly
    row = (
        (
            await db_session.execute(
                text("SELECT id FROM in_app_notifications WHERE client_id = :cid AND source_id = :sid"),
                {"cid": str(owner_client.id), "sid": str(src_id)},
            )
        )
        .mappings()
        .one()
    )
    notif_id = row["id"]

    # other_client tries to mark it read → should raise NotFoundError (404-collapse, never 200/403)
    with pytest.raises(NotFoundError):
        await service.mark_notification_read(
            db_session,
            client_id=other_client.id,
            notification_id=notif_id,
        )


async def test_mark_notification_read_sets_read_at(
    db_session: AsyncSession,
    make_client: Callable[..., Awaitable[Client]],
) -> None:
    """mark_notification_read on own unread notification sets read_at."""
    client = await make_client()
    src_id = uuid4()
    await service.create_notification(
        db_session,
        client_id=client.id,
        source_type="booking",
        source_id=src_id,
        kind="booking_confirmed",
        title="T",
        body="B",
    )
    await db_session.flush()

    row = (
        (
            await db_session.execute(
                text("SELECT id FROM in_app_notifications WHERE client_id = :cid AND source_id = :sid"),
                {"cid": str(client.id), "sid": str(src_id)},
            )
        )
        .mappings()
        .one()
    )
    notif_id = row["id"]

    item = await service.mark_notification_read(
        db_session,
        client_id=client.id,
        notification_id=notif_id,
    )
    assert item.read_at is not None
    assert item.id == notif_id


async def test_mark_notification_read_idempotent(
    db_session: AsyncSession,
    make_client: Callable[..., Awaitable[Client]],
) -> None:
    """mark_notification_read on an already-read notification raises NotFoundError (WHERE read_at IS NULL)."""
    client = await make_client()
    src_id = uuid4()
    await service.create_notification(
        db_session,
        client_id=client.id,
        source_type="booking",
        source_id=src_id,
        kind="booking_confirmed",
        title="T",
        body="B",
    )
    await db_session.flush()

    row = (
        (
            await db_session.execute(
                text("SELECT id FROM in_app_notifications WHERE client_id = :cid AND source_id = :sid"),
                {"cid": str(client.id), "sid": str(src_id)},
            )
        )
        .mappings()
        .one()
    )
    notif_id = row["id"]

    # First read succeeds
    await service.mark_notification_read(db_session, client_id=client.id, notification_id=notif_id)
    await db_session.flush()

    # Second read on already-read row → NotFoundError (WHERE read_at IS NULL filters it out)
    with pytest.raises(NotFoundError):
        await service.mark_notification_read(db_session, client_id=client.id, notification_id=notif_id)


# ── mark_all_notifications_read ───────────────────────────────────────────────


async def test_mark_all_notifications_read_marks_only_callers_rows(
    db_session: AsyncSession,
    make_client: Callable[..., Awaitable[Client]],
) -> None:
    """mark_all_notifications_read only affects the caller's rows (T-87-01)."""
    client_a = await make_client()
    client_b = await make_client()

    for _ in range(2):
        await service.create_notification(
            db_session,
            client_id=client_a.id,
            source_type="booking",
            source_id=uuid4(),
            kind="booking_confirmed",
            title="T",
            body="B",
        )
    await service.create_notification(
        db_session,
        client_id=client_b.id,
        source_type="booking",
        source_id=uuid4(),
        kind="booking_confirmed",
        title="T",
        body="B",
    )
    await db_session.flush()

    await service.mark_all_notifications_read(db_session, client_id=client_a.id)
    await db_session.flush()

    # client_a: 0 unread
    result_a = await service.list_client_notifications(
        db_session, client_a.id, PageQuery(page=1, page_size=20)
    )
    assert result_a.unread_count == 0

    # client_b: still 1 unread (untouched)
    result_b = await service.list_client_notifications(
        db_session, client_b.id, PageQuery(page=1, page_size=20)
    )
    assert result_b.unread_count == 1


# ── register_push_token ───────────────────────────────────────────────────────


async def test_register_push_token_idempotent(
    db_session: AsyncSession,
    make_client: Callable[..., Awaitable[Client]],
) -> None:
    """Registering the same (client_id, token) twice yields exactly one alive row."""
    client = await make_client()
    token_val = "test-push-token-abc123"
    payload = ClientPushTokenRegisterRequest(token=token_val, platform="web")

    await service.register_push_token(db_session, client_id=client.id, payload=payload)
    await db_session.flush()
    await service.register_push_token(db_session, client_id=client.id, payload=payload)
    await db_session.flush()

    row = (
        (
            await db_session.execute(
                text(
                    "SELECT COUNT(*) AS cnt FROM client_push_tokens "
                    "WHERE client_id = :cid AND token = :tok AND unregistered_at IS NULL"
                ),
                {"cid": str(client.id), "tok": token_val},
            )
        )
        .mappings()
        .one()
    )
    assert int(row["cnt"]) == 1


async def test_register_push_token_revives_unregistered(
    db_session: AsyncSession,
    make_client: Callable[..., Awaitable[Client]],
) -> None:
    """Re-registering a previously unregistered token revives it (unregistered_at → NULL)."""
    client = await make_client()
    token_val = "test-push-token-revive"
    payload = ClientPushTokenRegisterRequest(token=token_val, platform="android")

    # Register once
    await service.register_push_token(db_session, client_id=client.id, payload=payload)
    await db_session.flush()

    # Unregister it manually (simulate device unregistration)
    await db_session.execute(
        text(
            "UPDATE client_push_tokens SET unregistered_at = now() "
            "WHERE client_id = :cid AND token = :tok"
        ),
        {"cid": str(client.id), "tok": token_val},
    )
    await db_session.flush()

    # Re-register — should revive (unregistered_at → NULL)
    await service.register_push_token(db_session, client_id=client.id, payload=payload)
    await db_session.flush()

    row = (
        (
            await db_session.execute(
                text(
                    "SELECT unregistered_at FROM client_push_tokens "
                    "WHERE client_id = :cid AND token = :tok "
                    "ORDER BY created_at DESC LIMIT 1"
                ),
                {"cid": str(client.id), "tok": token_val},
            )
        )
        .mappings()
        .one()
    )
    assert row["unregistered_at"] is None
