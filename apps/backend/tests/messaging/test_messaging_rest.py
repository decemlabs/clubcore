"""Phase 90 Plan 02 Task 3 — messaging REST endpoint integration tests (TDD RED).

Proves MSG-01..04 + RT-04 HTTP contract:
  1. POST /api/v1/client/messages {body:"привет"} with auth+CSRF+Idempotency-Key → 200, persisted.
  2. GET /api/v1/client/messages → 200, items newest-first, total/page/pageSize/unreadCount present.
  3. POST with body="" → 422; POST with body="   " → 422.
  4. GET without client auth → 401.
  5. POST without CSRF header → 403 csrf_mismatch.
  6. IDOR — record_staff_message for client A, auth as client B; B's GET never shows A's messages.
  7. Idempotency — same Idempotency-Key + same body twice → same messageId; diff body + same key → 422.
  8. Staff send increments unreadCount; PATCH /api/v1/client/messages/read → unreadCount 0 on next GET.
  9. RT-04 — send 3 messages, GET ?after={firstMessageId} returns only the 2 newer ones.

Harness: SAVEPOINT db_session + ASGITransport AsyncClient (no real network — per CLAUDE.md).
Auth: OTP flow via _auth_as_client (cookies persisted on http_client).
Idempotency-Key: minimum 16 chars, alphanumeric per IDEMPOTENCY_KEY_PATTERN.
"""  # noqa: E501

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_db
from app.core.permissions import Role
from app.core.redis import get_redis
from app.core.security import generate_otp_code, hash_password
from app.modules.auth.models import OtpCode, User
from app.modules.clients.models import Client
from app.modules.messaging import service as messaging_service

pytestmark = pytest.mark.asyncio(loop_scope="function")

# ---------------------------------------------------------------------------
# Phone constants — unique to messaging tests; no collision with other modules
# ---------------------------------------------------------------------------

_BASE_PHONE = "+79169000"


def _phone(n: int) -> str:
    """Return a stable E.164 phone for test client n (1–99)."""  # noqa: RUF002
    return f"{_BASE_PHONE}{n:04d}"


# ---------------------------------------------------------------------------
# Fixtures — dependency overrides + ASGITransport http_client
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def _overridden_app(
    app: FastAPI,
    db_session: AsyncSession,
) -> AsyncIterator[FastAPI]:
    """Install dependency overrides so route handlers use the SAVEPOINT session."""

    async def _override_get_db() -> AsyncIterator[AsyncSession]:
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_redis] = lambda: app.state.redis
    try:
        yield app
    finally:
        app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def http_client(_overridden_app: FastAPI) -> AsyncIterator[AsyncClient]:
    """ASGITransport client that persists cookies across requests."""
    transport = ASGITransport(app=_overridden_app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as c:
        yield c


@pytest.fixture(autouse=True)
def stub_otp_sender(app: FastAPI, monkeypatch: pytest.MonkeyPatch) -> None:
    """Replace real OTP Telegram sender with no-op for all tests in this module."""
    _ = app
    from app.modules.client_auth import service as client_auth_service

    async def _noop(chat_id: int, code: str) -> None:
        pass

    monkeypatch.setattr(client_auth_service, "_client_otp_sender", _noop)


@pytest_asyncio.fixture(autouse=True)
async def flush_redis(app: FastAPI) -> None:
    """Flush Redis before each test so idempotency + rate-limit keys don't bleed."""
    await app.state.redis.flushdb()


# ---------------------------------------------------------------------------
# Auth helper — OTP flow (mirrors test_notifications_endpoints.py)
# ---------------------------------------------------------------------------


async def _auth_as_client(
    async_client: AsyncClient,
    db_session: AsyncSession,
    client: Client,
) -> str:
    """Request OTP → patch code → verify → return cc_client_access token value.

    Reads the OtpCode row and replaces the hash with a deterministic known code
    so the verify step succeeds without a real Telegram DM.
    """
    req = await async_client.post(
        "/api/v1/client/otp/request",
        json={"phone": client.phone},
    )
    assert req.status_code == 202, f"OTP request failed for {client.phone}: {req.text}"

    otp_row = await db_session.scalar(
        select(OtpCode).where(
            OtpCode.client_id == client.id,
            OtpCode.consumed_at.is_(None),
        )
    )
    assert otp_row is not None, f"OtpCode row not found for client {client.id}"

    settings = get_settings()
    raw_code, code_hash = generate_otp_code()
    otp_row.code_hash = code_hash
    otp_row.expires_at = datetime.now(tz=UTC) + timedelta(seconds=settings.otp_code_ttl_seconds)
    await db_session.commit()

    verify = await async_client.post(
        "/api/v1/client/otp/verify",
        json={"phone": client.phone, "code": raw_code},
    )
    assert verify.status_code == 200, f"OTP verify failed for {client.phone}: {verify.text}"

    set_cookies = verify.headers.get_list("set-cookie")
    access_cookie = next(
        (c for c in set_cookies if c.startswith("cc_client_access=")),
        None,
    )
    assert access_cookie is not None, "cc_client_access cookie missing from verify response"
    return access_cookie.split("=", 1)[1].split(";", 1)[0]


# ---------------------------------------------------------------------------
# Seed helpers
# ---------------------------------------------------------------------------


async def _seed_staff(db_session: AsyncSession, suffix: str = "") -> User:
    user = User(
        email=f"msg-ep-staff-{suffix or uuid4().hex[:8]}@example.com",
        password_hash=await hash_password("msg-ep-staff-pw-secure-90"),
        role=Role.RECEPTION,
        full_name="Messaging Endpoint Test Staff",
    )
    db_session.add(user)
    await db_session.flush()
    return user


async def _seed_client(
    db_session: AsyncSession,
    staff: User,
    phone: str,
) -> Client:
    client = Client(
        first_name="Чат",
        last_name="Тест",
        phone=phone,
        telegram_user_id=abs(hash(phone)) % (10**9),
        created_by_user_id=staff.id,
    )
    db_session.add(client)
    await db_session.flush()
    return client


def _idem_key(n: int = 1) -> str:
    """Generate a unique idempotency key meeting the 16-char min requirement."""
    return f"msg-idem-key-test-{n:04d}-{uuid4().hex[:4]}"


# ---------------------------------------------------------------------------
# Test 1: POST /api/v1/client/messages → 200, message persisted
# ---------------------------------------------------------------------------


async def test_post_message_valid_body_returns_200_and_persists(
    http_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """POST with auth+CSRF+Idempotency-Key → 200, message persisted (MSG-02)."""
    staff = await _seed_staff(db_session, "post-200")
    client = await _seed_client(db_session, staff, _phone(1))
    await db_session.commit()

    await _auth_as_client(http_client, db_session, client)
    csrf_token = http_client.cookies.get("clubcore_client_csrf") or ""

    resp = await http_client.post(
        "/api/v1/client/messages",
        json={"body": "привет"},
        headers={"X-CSRF-Token": csrf_token, "Idempotency-Key": _idem_key(1)},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["body"] == "привет"
    assert data["role"] == "client"
    assert "id" in data
    assert "sentAt" in data


# ---------------------------------------------------------------------------
# Test 2: GET /api/v1/client/messages → newest-first + pagination fields + unreadCount
# ---------------------------------------------------------------------------


async def test_get_messages_returns_200_with_pagination_and_unread_count(
    http_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """GET /messages → 200; items newest-first, total/page/pageSize/unreadCount present (MSG-01)."""
    staff = await _seed_staff(db_session, "get-200")
    client = await _seed_client(db_session, staff, _phone(2))
    await db_session.commit()

    await _auth_as_client(http_client, db_session, client)
    csrf_token = http_client.cookies.get("clubcore_client_csrf") or ""

    # Send 2 messages
    await http_client.post(
        "/api/v1/client/messages",
        json={"body": "первое"},
        headers={"X-CSRF-Token": csrf_token, "Idempotency-Key": _idem_key(2)},
    )
    await http_client.post(
        "/api/v1/client/messages",
        json={"body": "второе"},
        headers={"X-CSRF-Token": csrf_token, "Idempotency-Key": _idem_key(3)},
    )

    resp = await http_client.get("/api/v1/client/messages")
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert "items" in data
    assert "total" in data
    assert "page" in data
    assert "pageSize" in data
    assert "unreadCount" in data
    assert data["total"] == 2
    assert data["unreadCount"] == 0  # client sent, no staff messages yet
    # Newest-first: second message should be first in items
    assert len(data["items"]) == 2
    assert data["items"][0]["body"] == "второе"
    assert data["items"][1]["body"] == "первое"


# ---------------------------------------------------------------------------
# Test 3: POST empty/whitespace body → 422
# ---------------------------------------------------------------------------


async def test_post_message_empty_body_returns_422(
    http_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """POST with body="" → 422 (T-90-09 whitespace guard)."""
    staff = await _seed_staff(db_session, "empty-body")
    client = await _seed_client(db_session, staff, _phone(3))
    await db_session.commit()

    await _auth_as_client(http_client, db_session, client)
    csrf_token = http_client.cookies.get("clubcore_client_csrf") or ""

    resp = await http_client.post(
        "/api/v1/client/messages",
        json={"body": ""},
        headers={"X-CSRF-Token": csrf_token, "Idempotency-Key": _idem_key(4)},
    )
    assert resp.status_code == 422, (
        f"Expected 422 for empty body, got {resp.status_code}: {resp.text}"
    )


async def test_post_message_whitespace_body_returns_422(
    http_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """POST with body="   " → 422 (T-90-09 whitespace guard)."""
    staff = await _seed_staff(db_session, "ws-body")
    client = await _seed_client(db_session, staff, _phone(4))
    await db_session.commit()

    await _auth_as_client(http_client, db_session, client)
    csrf_token = http_client.cookies.get("clubcore_client_csrf") or ""

    resp = await http_client.post(
        "/api/v1/client/messages",
        json={"body": "   "},
        headers={"X-CSRF-Token": csrf_token, "Idempotency-Key": _idem_key(5)},
    )
    assert resp.status_code == 422, (
        f"Expected 422 for whitespace body, got {resp.status_code}: {resp.text}"
    )


# ---------------------------------------------------------------------------
# Test 4: GET without client auth → 401
# ---------------------------------------------------------------------------


async def test_get_messages_no_auth_returns_401(
    http_client: AsyncClient,
) -> None:
    """GET /messages without client auth → 401."""
    resp = await http_client.get("/api/v1/client/messages")
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Test 5: POST without CSRF header → 403
# ---------------------------------------------------------------------------


async def test_post_message_without_csrf_returns_403(
    http_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """POST without X-CSRF-Token → 403 (RBAC-04 / T-90-07)."""
    staff = await _seed_staff(db_session, "csrf-403")
    client = await _seed_client(db_session, staff, _phone(5))
    await db_session.commit()

    await _auth_as_client(http_client, db_session, client)

    resp = await http_client.post(
        "/api/v1/client/messages",
        json={"body": "test"},
        headers={"Idempotency-Key": _idem_key(6)},
        # Intentionally omitting X-CSRF-Token
    )
    assert resp.status_code == 403, (
        f"Expected 403 CSRF rejection, got {resp.status_code}: {resp.text}"
    )


# ---------------------------------------------------------------------------
# Test 6: IDOR — client B cannot see client A's messages
# ---------------------------------------------------------------------------


async def test_idor_client_b_does_not_see_client_a_messages(
    http_client: AsyncClient,
    db_session: AsyncSession,
    app: FastAPI,
) -> None:
    """IDOR (T-90-04): client B's GET never shows client A's messages (own thread only)."""
    staff = await _seed_staff(db_session, "idor")
    client_a = await _seed_client(db_session, staff, _phone(10))
    client_b = await _seed_client(db_session, staff, _phone(11))
    await db_session.commit()

    # Create a staff message for client A directly via service (no endpoint).
    await messaging_service.record_staff_message(
        db_session,
        client_id=client_a.id,
        body="Это сообщение для клиента А",  # noqa: RUF001
    )
    await db_session.commit()

    # Authenticate as client B.
    await _auth_as_client(http_client, db_session, client_b)

    # Client B GET should see only their own (empty) thread.
    resp = await http_client.get("/api/v1/client/messages")
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["total"] == 0, (
        f"IDOR: client B saw {data['total']} messages that belong to client A"
    )
    assert data["items"] == [], "IDOR: client B received items belonging to client A"
    # All item ids must belong to client B's thread (empty in this case)
    items_bodies = [item["body"] for item in data["items"]]
    assert "Это сообщение для клиента А" not in items_bodies  # noqa: RUF001


# ---------------------------------------------------------------------------
# Test 7: Idempotency — same key+body replays; different body + same key → 422
# ---------------------------------------------------------------------------


async def test_post_message_idempotency_same_key_same_body_replays(
    http_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Same Idempotency-Key + same body twice → same messageId, no duplicate row (MSG-03)."""
    staff = await _seed_staff(db_session, "idem-replay")
    client = await _seed_client(db_session, staff, _phone(20))
    await db_session.commit()

    await _auth_as_client(http_client, db_session, client)
    csrf_token = http_client.cookies.get("clubcore_client_csrf") or ""
    idem_key = _idem_key(100)

    resp1 = await http_client.post(
        "/api/v1/client/messages",
        json={"body": "идемпотентное"},
        headers={"X-CSRF-Token": csrf_token, "Idempotency-Key": idem_key},
    )
    assert resp1.status_code == 200, f"First POST failed: {resp1.text}"
    message_id_1 = resp1.json()["data"]["id"]

    # Second POST with SAME key + SAME body → must return same messageId.
    resp2 = await http_client.post(
        "/api/v1/client/messages",
        json={"body": "идемпотентное"},
        headers={"X-CSRF-Token": csrf_token, "Idempotency-Key": idem_key},
    )
    assert resp2.status_code == 200, f"Second POST (replay) failed: {resp2.text}"
    message_id_2 = resp2.json()["data"]["id"]

    assert message_id_1 == message_id_2, (
        f"Idempotency broken: first messageId={message_id_1}, second={message_id_2} (duplicate)"
    )


async def test_post_message_idempotency_same_key_different_body_returns_422(
    http_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Same Idempotency-Key + different body → 422 idempotency_key_reuse (T-90-06)."""
    staff = await _seed_staff(db_session, "idem-reuse")
    client = await _seed_client(db_session, staff, _phone(21))
    await db_session.commit()

    await _auth_as_client(http_client, db_session, client)
    csrf_token = http_client.cookies.get("clubcore_client_csrf") or ""
    idem_key = _idem_key(200)

    await http_client.post(
        "/api/v1/client/messages",
        json={"body": "первый вариант"},
        headers={"X-CSRF-Token": csrf_token, "Idempotency-Key": idem_key},
    )

    # Same key, different body → 422.
    resp = await http_client.post(
        "/api/v1/client/messages",
        json={"body": "другой вариант"},
        headers={"X-CSRF-Token": csrf_token, "Idempotency-Key": idem_key},
    )
    assert resp.status_code == 422, (
        f"Expected 422 idempotency_key_reuse for different body, got {resp.status_code}: {resp.text}"  # noqa: E501
    )


# ---------------------------------------------------------------------------
# Test 8: Staff send increments unreadCount; PATCH /read → unreadCount 0
# ---------------------------------------------------------------------------


async def test_staff_message_increments_unread_count_and_patch_read_clears_it(
    http_client: AsyncClient,
    db_session: AsyncSession,
    app: FastAPI,
) -> None:
    """Staff send increments unreadCount; PATCH /read → unreadCount 0 on next GET (MSG-04)."""
    staff = await _seed_staff(db_session, "unread")
    client = await _seed_client(db_session, staff, _phone(30))
    await db_session.commit()

    # Create a staff message via internal service.
    await messaging_service.record_staff_message(
        db_session,
        client_id=client.id,
        body="Сотрудник: ответ на вопрос",
    )
    await db_session.commit()

    await _auth_as_client(http_client, db_session, client)
    csrf_token = http_client.cookies.get("clubcore_client_csrf") or ""

    # GET should show unreadCount == 1.
    get_resp = await http_client.get("/api/v1/client/messages")
    assert get_resp.status_code == 200, get_resp.text
    data = get_resp.json()["data"]
    assert data["unreadCount"] == 1, (
        f"Expected unreadCount=1 after staff message, got {data['unreadCount']}"
    )

    # PATCH /messages/read → marks all read.
    patch_resp = await http_client.patch(
        "/api/v1/client/messages/read",
        headers={"X-CSRF-Token": csrf_token},
    )
    assert patch_resp.status_code in (200, 204), f"PATCH /read failed: {patch_resp.text}"

    # Next GET → unreadCount == 0.
    get_resp2 = await http_client.get("/api/v1/client/messages")
    assert get_resp2.status_code == 200, get_resp2.text
    data2 = get_resp2.json()["data"]
    assert data2["unreadCount"] == 0, (
        f"Expected unreadCount=0 after PATCH /read, got {data2['unreadCount']}"
    )


# ---------------------------------------------------------------------------
# Test 9: RT-04 — after-cursor returns only messages newer than cursor
# ---------------------------------------------------------------------------


async def test_get_messages_after_cursor_returns_only_newer_messages(
    http_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """RT-04: GET ?after={firstMessageId} returns only the 2 newer messages."""
    staff = await _seed_staff(db_session, "cursor")
    client = await _seed_client(db_session, staff, _phone(40))
    await db_session.commit()

    await _auth_as_client(http_client, db_session, client)
    csrf_token = http_client.cookies.get("clubcore_client_csrf") or ""

    # Send 3 messages in order.
    r1 = await http_client.post(
        "/api/v1/client/messages",
        json={"body": "сообщение 1 (самое старое)"},
        headers={"X-CSRF-Token": csrf_token, "Idempotency-Key": _idem_key(301)},
    )
    assert r1.status_code == 200, r1.text
    msg1_id = r1.json()["data"]["id"]

    r2 = await http_client.post(
        "/api/v1/client/messages",
        json={"body": "сообщение 2"},
        headers={"X-CSRF-Token": csrf_token, "Idempotency-Key": _idem_key(302)},
    )
    assert r2.status_code == 200, r2.text
    msg2_id = r2.json()["data"]["id"]

    r3 = await http_client.post(
        "/api/v1/client/messages",
        json={"body": "сообщение 3 (самое новое)"},
        headers={"X-CSRF-Token": csrf_token, "Idempotency-Key": _idem_key(303)},
    )
    assert r3.status_code == 200, r3.text
    msg3_id = r3.json()["data"]["id"]

    # GET all messages — verify 3 total.
    all_resp = await http_client.get("/api/v1/client/messages")
    assert all_resp.status_code == 200, all_resp.text
    assert all_resp.json()["data"]["total"] == 3

    # GET ?after=msg1_id → should return only msg2 and msg3 (newer than msg1).
    cursor_resp = await http_client.get(f"/api/v1/client/messages?after={msg1_id}")
    assert cursor_resp.status_code == 200, cursor_resp.text
    cursor_data = cursor_resp.json()["data"]
    cursor_items = cursor_data["items"]
    cursor_ids = [item["id"] for item in cursor_items]

    assert len(cursor_items) == 2, (
        f"RT-04: expected 2 items after cursor, got {len(cursor_items)}: {cursor_ids}"
    )
    assert str(msg1_id) not in cursor_ids, "RT-04: cursor message (msg1) must not appear in results"
    assert str(msg2_id) in cursor_ids, "RT-04: msg2 should be in results"
    assert str(msg3_id) in cursor_ids, "RT-04: msg3 should be in results"
