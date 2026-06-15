"""Integration tests for staff messaging endpoints (Phase 116 MSG-01/MSG-02).

Coverage:
  - GET /api/v1/messages/threads as owner → 200 + StaffInboxResponse shape
  - GET /api/v1/messages/threads as reception → 200 (both roles allowed)
  - GET /api/v1/messages/threads/{id} as owner → 200 + thread history shape
  - POST /api/v1/messages/threads/{id}/reply as owner → 200 + StaffMessageItem shape
  - POST /api/v1/messages/threads/{id}/reply as reception → 403 "forbidden"
    ((CREATE, MESSAGES) ∈ OWNER_ONLY)
  - POST /api/v1/messages/threads/{id}/read as owner → 204
  - POST /api/v1/messages/threads/{id}/read as reception → 204 (both roles)
  - Empty inbox (no threads) → 200 with items == []
  - Mark-read resets staffUnreadCount to 0 on subsequent inbox fetch
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any
from uuid import UUID

import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.clients.models import Client


def _csrf(client: AsyncClient) -> dict[str, str]:
    """Return X-CSRF-Token header dict from the cookie jar (mirrors test_loyalty_grant pattern)."""
    return {"X-CSRF-Token": client.cookies.get("clubcore_csrf", "")}


# Re-export the standard authed client fixtures from memberships conftest.
from tests.integration.memberships.conftest import (  # noqa: F401
    _client_app_overrides,
    authed_client_owner,
    authed_client_reception,
    db_session_real_commit,
    make_client,
    make_user,
    redis_clean,
    seeded_owner,
    seeded_reception,
)


# ---------------------------------------------------------------------------
# Seed helpers
# ---------------------------------------------------------------------------


async def _seed_thread_with_client_message(
    session: AsyncSession,
    client_id: UUID,
) -> UUID:
    """Insert a message_threads row and one client message; return thread_id."""
    # Create thread
    thread_result = await session.execute(
        text(
            "INSERT INTO message_threads (client_id, last_message_at) "
            "VALUES (:cid, now()) "
            "RETURNING id"
        ),
        {"cid": str(client_id)},
    )
    thread_id = UUID(str(thread_result.scalar_one()))

    # Insert a client message
    await session.execute(
        text(
            "INSERT INTO messages (thread_id, role, body, sent_at) "
            "VALUES (:tid, 'client', 'Привет, хочу записаться', now())"
        ),
        {"tid": str(thread_id)},
    )
    await session.commit()
    return thread_id


@pytest_asyncio.fixture
async def seeded_thread(
    db_session: AsyncSession,
    make_client: Callable[..., Awaitable[Client]],
) -> dict[str, Any]:
    """Seed a client + thread with one client message; return {'client_id', 'thread_id'}."""
    client = await make_client(first_name="Иван", last_name="Тестов")
    thread_id = await _seed_thread_with_client_message(db_session, client.id)
    return {"client_id": client.id, "thread_id": thread_id}


# ---------------------------------------------------------------------------
# Tests — empty inbox
# ---------------------------------------------------------------------------


async def test_empty_inbox_owner(
    authed_client_owner: AsyncClient,
) -> None:
    """Owner GET /threads with no threads → 200 + empty items list."""
    r = await authed_client_owner.get("/api/v1/messages/threads")
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["data"]["items"] == []
    assert data["data"]["total"] == 0


# ---------------------------------------------------------------------------
# Tests — inbox list
# ---------------------------------------------------------------------------


async def test_owner_list_threads_200(
    authed_client_owner: AsyncClient,
    seeded_thread: dict[str, Any],
) -> None:
    """Owner GET /threads → 200 + StaffInboxResponse shape with staffUnreadCount > 0."""
    r = await authed_client_owner.get("/api/v1/messages/threads")
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert data["total"] >= 1
    assert len(data["items"]) >= 1

    # Check shape of first item
    item = data["items"][0]
    assert "id" in item
    assert "clientId" in item
    assert "clientName" in item
    assert "clientInitials" in item
    assert "staffUnreadCount" in item
    # The seeded client message should show as unread (staff_last_read_at IS NULL)
    assert item["staffUnreadCount"] >= 1


async def test_reception_list_threads_200(
    authed_client_reception: AsyncClient,
    seeded_thread: dict[str, Any],
) -> None:
    """Reception GET /threads → 200 (LIST, MESSAGES NOT in OWNER_ONLY)."""
    r = await authed_client_reception.get("/api/v1/messages/threads")
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert "items" in data
    assert "total" in data


# ---------------------------------------------------------------------------
# Tests — thread history
# ---------------------------------------------------------------------------


async def test_owner_get_thread_200(
    authed_client_owner: AsyncClient,
    seeded_thread: dict[str, Any],
) -> None:
    """Owner GET /threads/{id} → 200 + StaffThreadHistoryResponse shape."""
    thread_id = str(seeded_thread["thread_id"])
    r = await authed_client_owner.get(f"/api/v1/messages/threads/{thread_id}")
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert data["threadId"] == thread_id
    assert isinstance(data["messages"], list)
    assert len(data["messages"]) >= 1
    msg = data["messages"][0]
    assert "id" in msg
    assert msg["role"] == "client"
    assert "body" in msg
    assert "sentAt" in msg


async def test_reception_get_thread_200(
    authed_client_reception: AsyncClient,
    seeded_thread: dict[str, Any],
) -> None:
    """Reception GET /threads/{id} → 200 (VIEW, MESSAGES NOT in OWNER_ONLY)."""
    thread_id = str(seeded_thread["thread_id"])
    r = await authed_client_reception.get(f"/api/v1/messages/threads/{thread_id}")
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert data["threadId"] == thread_id


# ---------------------------------------------------------------------------
# Tests — reply (owner-only)
# ---------------------------------------------------------------------------


async def test_owner_reply_200(
    authed_client_owner: AsyncClient,
    seeded_thread: dict[str, Any],
    db_session: AsyncSession,
) -> None:
    """Owner POST /threads/{id}/reply → 200 + StaffMessageItem; message persists role='staff'."""
    thread_id = str(seeded_thread["thread_id"])
    r = await authed_client_owner.post(
        f"/api/v1/messages/threads/{thread_id}/reply",
        json={"body": "Привет! Запись возможна."},
        headers=_csrf(authed_client_owner),
    )
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert "id" in data
    assert data["role"] == "staff"
    assert data["body"] == "Привет! Запись возможна."
    assert "sentAt" in data

    # Verify message persists in DB with role='staff'
    row = (
        await db_session.execute(
            text("SELECT role, body FROM messages WHERE id = CAST(:mid AS uuid)"),
            {"mid": data["id"]},
        )
    ).mappings().one_or_none()
    assert row is not None, "Staff reply message not found in DB"
    assert row["role"] == "staff"
    assert row["body"] == "Привет! Запись возможна."


async def test_reception_reply_403(
    authed_client_reception: AsyncClient,
    seeded_thread: dict[str, Any],
) -> None:
    """(CREATE, MESSAGES) ∈ OWNER_ONLY → reception POST /reply → 403 forbidden (T-116-01)."""
    thread_id = str(seeded_thread["thread_id"])
    r = await authed_client_reception.post(
        f"/api/v1/messages/threads/{thread_id}/reply",
        json={"body": "test"},
        headers=_csrf(authed_client_reception),
    )
    assert r.status_code == 403, r.text
    assert r.json()["code"] == "forbidden"


# ---------------------------------------------------------------------------
# Tests — mark-read (both roles)
# ---------------------------------------------------------------------------


async def test_owner_mark_read_204(
    authed_client_owner: AsyncClient,
    seeded_thread: dict[str, Any],
) -> None:
    """Owner POST /threads/{id}/read → 204."""
    thread_id = str(seeded_thread["thread_id"])
    r = await authed_client_owner.post(
        f"/api/v1/messages/threads/{thread_id}/read",
        headers=_csrf(authed_client_owner),
    )
    assert r.status_code == 204, r.text


async def test_reception_mark_read_204(
    authed_client_reception: AsyncClient,
    seeded_thread: dict[str, Any],
) -> None:
    """Reception POST /threads/{id}/read → 204 (VIEW, MESSAGES NOT in OWNER_ONLY)."""
    thread_id = str(seeded_thread["thread_id"])
    r = await authed_client_reception.post(
        f"/api/v1/messages/threads/{thread_id}/read",
        headers=_csrf(authed_client_reception),
    )
    assert r.status_code == 204, r.text


async def test_mark_read_resets_staff_unread(
    authed_client_owner: AsyncClient,
    seeded_thread: dict[str, Any],
) -> None:
    """POST /threads/{id}/read resets staffUnreadCount to 0 on subsequent inbox fetch."""
    thread_id = str(seeded_thread["thread_id"])

    # Confirm there is unread before mark-read
    r_before = await authed_client_owner.get("/api/v1/messages/threads")
    assert r_before.status_code == 200, r_before.text
    items_before = r_before.json()["data"]["items"]
    target_before = next(
        (i for i in items_before if i["id"] == thread_id), None
    )
    assert target_before is not None
    assert target_before["staffUnreadCount"] >= 1

    # Mark as read
    r_read = await authed_client_owner.post(
        f"/api/v1/messages/threads/{thread_id}/read",
        headers=_csrf(authed_client_owner),
    )
    assert r_read.status_code == 204, r_read.text

    # Verify staffUnreadCount is now 0
    r_after = await authed_client_owner.get("/api/v1/messages/threads")
    assert r_after.status_code == 200, r_after.text
    items_after = r_after.json()["data"]["items"]
    target_after = next(
        (i for i in items_after if i["id"] == thread_id), None
    )
    assert target_after is not None
    assert target_after["staffUnreadCount"] == 0
