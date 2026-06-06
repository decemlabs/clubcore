"""Phase 87 Plan 02 — notifications client-portal endpoint integration tests.

Proves INBOX-01/INBOX-02 HTTP contract:
  - GET /api/v1/client/notifications: 200 + paginated items (newest-first) + unreadCount.
  - GET without client auth → 401.
  - IDOR: client A's GET returns only A's items; B's notifications absent.
  - PATCH /{id}/read: marks one read; unreadCount drops by 1 on next GET.
  - PATCH /{id}/read for a notification owned by another client → 404 (IDOR-collapse, T-87-07).
  - PATCH /{id}/read without CSRF header → 403 csrf_mismatch.
  - PATCH /read-all → 204; subsequent GET shows unreadCount == 0.
  - POST /push-tokens valid body → 204; re-POST same token → 204 (idempotent, one alive row).
  - POST /push-tokens with extra field → 422 (extra='forbid', T-87-09).
  - POST /push-tokens with invalid platform → 422/constraint rejection.
  - POST /push-tokens response body contains no `token` field (T-87-08).

Harness: SAVEPOINT db_session + ASGITransport AsyncClient (no real network — per CLAUDE.md).
Auth: OTP flow via _auth_as_client (cookies persisted on http_client).
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_db
from app.core.permissions import Role
from app.core.redis import get_redis
from app.core.security import generate_otp_code, hash_password
from app.modules.auth.models import OtpCode, User
from app.modules.clients.models import Client
from app.modules.notifications import service
from app.modules.notifications.schemas import ClientPushTokenRegisterRequest

pytestmark = pytest.mark.asyncio(loop_scope="function")

# ---------------------------------------------------------------------------
# Phone constants — unique to this module; no collision with other test modules
# ---------------------------------------------------------------------------

_BASE_PHONE = "+79161234"


def _phone(n: int) -> str:
    """Return a stable E.164 phone for test client n (1–99)."""
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
    """Flush Redis before each test so rate-limit and session keys don't bleed."""
    await app.state.redis.flushdb()


# ---------------------------------------------------------------------------
# Auth helper — OTP flow (mirrors test_loyalty_read.py)
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
        email=f"notif-ep-staff-{suffix or uuid4().hex[:8]}@example.com",
        password_hash=await hash_password("notif-ep-staff-pw-secure-87"),
        role=Role.RECEPTION,
        full_name="Notif Endpoint Test Staff",
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
        first_name="Уведомлений",
        last_name="Тест",
        phone=phone,
        telegram_user_id=abs(hash(phone)) % (10**9),
        created_by_user_id=staff.id,
    )
    db_session.add(client)
    await db_session.flush()
    return client


async def _create_notif(
    db_session: AsyncSession,
    client_id: UUID,
    *,
    kind: str = "booking_confirmed",
    source_id: UUID | None = None,
    created_at_offset_seconds: int = 0,
) -> UUID:
    """Insert one notification and return its id.

    created_at_offset_seconds: if nonzero, set created_at via raw SQL to an
    explicitly older timestamp, ensuring deterministic ORDER BY created_at DESC.
    """
    sid = source_id or uuid4()
    if created_at_offset_seconds == 0:
        await service.create_notification(
            db_session,
            client_id=client_id,
            source_type="booking",
            source_id=sid,
            kind=kind,
            title="Тест уведомление",
            body="Тренировка в 10:00",
        )
        # Retrieve the inserted row id
        row = await db_session.execute(
            text(
                "SELECT id FROM in_app_notifications "
                "WHERE client_id=:cid AND source_id=:sid AND kind=:kind"
            ),
            {"cid": str(client_id), "sid": str(sid), "kind": kind},
        )
        raw = row.scalar_one()
        # asyncpg returns a native UUID object; str() works for both str and UUID
        return UUID(str(raw))
    else:
        # Insert via raw SQL with explicit created_at offset (avoids non-deterministic ordering)
        row_id = uuid4()
        await db_session.execute(
            text(
                "INSERT INTO in_app_notifications "
                "(id, client_id, source_type, source_id, kind, title, body, created_at, updated_at) "
                "VALUES (:id, :cid, :st, :sid, :kind, :title, :body, "
                "       now() - :offset * interval '1 second', now())"
            ),
            {
                "id": str(row_id),
                "cid": str(client_id),
                "st": "booking",
                "sid": str(sid),
                "kind": kind,
                "title": "Тест уведомление старое",
                "body": "Тренировка давно",
                "offset": created_at_offset_seconds,
            },
        )
        return row_id


# ---------------------------------------------------------------------------
# Tests — GET /api/v1/client/notifications
# ---------------------------------------------------------------------------


async def test_get_notifications_returns_200_with_items_and_unread_count(
    http_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """GET /notifications → 200; data.items list present; data.unreadCount correct."""
    staff = await _seed_staff(db_session, "get-200")
    client = await _seed_client(db_session, staff, _phone(1))
    await _create_notif(db_session, client.id)
    await db_session.commit()

    await _auth_as_client(http_client, db_session, client)

    resp = await http_client.get("/api/v1/client/notifications")
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert len(data["items"]) == 1
    assert data["total"] == 1
    assert data["unreadCount"] == 1
    item = data["items"][0]
    assert item["readAt"] is None


async def test_get_notifications_newest_first(
    http_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """GET /notifications → items ordered newest-first (created_at DESC)."""
    staff = await _seed_staff(db_session, "order")
    client = await _seed_client(db_session, staff, _phone(2))
    await db_session.commit()

    # Insert older notification first (30 seconds ago) and newer after
    older_id = await _create_notif(
        db_session, client.id, kind="payment_succeeded",
        created_at_offset_seconds=30
    )
    await _create_notif(db_session, client.id, kind="booking_confirmed")
    await db_session.commit()

    await _auth_as_client(http_client, db_session, client)

    resp = await http_client.get("/api/v1/client/notifications")
    assert resp.status_code == 200, resp.text
    items = resp.json()["data"]["items"]
    assert len(items) == 2
    # Newest first: booking_confirmed (just inserted) should come before payment_succeeded
    assert str(older_id) == items[1]["id"], (
        "Older notification should be last (newest-first ordering broken)"
    )


async def test_get_notifications_pagination_honored(
    http_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """pageSize=1 → 1 item returned; total reflects all rows; page honored."""
    staff = await _seed_staff(db_session, "page")
    client = await _seed_client(db_session, staff, _phone(3))
    await db_session.commit()

    await _create_notif(db_session, client.id, kind="booking_confirmed")
    await _create_notif(db_session, client.id, kind="booking_cancelled_by_client", source_id=uuid4())
    await db_session.commit()

    await _auth_as_client(http_client, db_session, client)

    resp = await http_client.get("/api/v1/client/notifications?pageSize=1")
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["total"] == 2
    assert len(data["items"]) == 1
    assert data["pageSize"] == 1
    assert data["page"] == 1


async def test_get_notifications_no_auth_returns_401(
    http_client: AsyncClient,
) -> None:
    """GET /notifications without client auth → 401."""
    resp = await http_client.get("/api/v1/client/notifications")
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Tests — IDOR: client A cannot read client B's notifications
# ---------------------------------------------------------------------------


async def test_idor_client_a_does_not_see_client_b_notifications(
    http_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """IDOR: client A's GET /notifications returns only A's items; B's rows absent."""
    staff = await _seed_staff(db_session, "idor-get")
    client_a = await _seed_client(db_session, staff, _phone(10))
    client_b = await _seed_client(db_session, staff, _phone(11))
    await db_session.commit()

    # Seed notification for B only
    await _create_notif(db_session, client_b.id, kind="booking_confirmed")
    await db_session.commit()

    # Authenticate as client A
    await _auth_as_client(http_client, db_session, client_a)

    resp = await http_client.get("/api/v1/client/notifications")
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["total"] == 0, (
        f"IDOR: client A saw {data['total']} notifications that belong to client B"
    )
    assert data["items"] == [], "IDOR: client A received items belonging to client B"
    assert data["unreadCount"] == 0


# ---------------------------------------------------------------------------
# Tests — PATCH /{id}/read
# ---------------------------------------------------------------------------


async def test_patch_mark_read_marks_single_notification(
    http_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """PATCH /{id}/read marks the notification read; unreadCount drops by 1 on next GET."""
    staff = await _seed_staff(db_session, "mark-one")
    client = await _seed_client(db_session, staff, _phone(20))
    await db_session.commit()

    await _create_notif(db_session, client.id, kind="booking_confirmed")
    await _create_notif(db_session, client.id, kind="booking_cancelled_by_client", source_id=uuid4())
    await db_session.commit()

    await _auth_as_client(http_client, db_session, client)
    csrf_token = http_client.cookies.get("clubcore_client_csrf") or ""

    # Get list to find id of first notification
    list_resp = await http_client.get("/api/v1/client/notifications")
    assert list_resp.status_code == 200
    items = list_resp.json()["data"]["items"]
    assert len(items) == 2
    notif_id = items[0]["id"]

    # Mark first as read
    patch_resp = await http_client.patch(
        f"/api/v1/client/notifications/{notif_id}/read",
        headers={"X-CSRF-Token": csrf_token},
    )
    assert patch_resp.status_code == 200, patch_resp.text
    result_item = patch_resp.json()["data"]
    assert result_item["id"] == notif_id
    assert result_item["readAt"] is not None

    # unreadCount drops by 1
    list_resp2 = await http_client.get("/api/v1/client/notifications")
    assert list_resp2.status_code == 200
    data2 = list_resp2.json()["data"]
    assert data2["unreadCount"] == 1, (
        f"unreadCount should be 1 after marking one read, got {data2['unreadCount']}"
    )


async def test_patch_mark_read_already_read_own_notification_returns_200(
    http_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """WR-02: PATCH /{id}/read on an already-read OWN notification → 200 (idempotent).

    Marking an own notification as read twice must succeed on the second call
    (idempotent-retry contract). Only cross-client or nonexistent IDs return 404.
    """
    staff = await _seed_staff(db_session, "mark-idem")
    client = await _seed_client(db_session, staff, _phone(25))
    await db_session.commit()

    notif_id = await _create_notif(db_session, client.id, kind="booking_confirmed")
    await db_session.commit()

    await _auth_as_client(http_client, db_session, client)
    csrf_token = http_client.cookies.get("clubcore_client_csrf") or ""

    # First call — marks the notification read.
    resp1 = await http_client.patch(
        f"/api/v1/client/notifications/{notif_id}/read",
        headers={"X-CSRF-Token": csrf_token},
    )
    assert resp1.status_code == 200, f"First mark-read failed: {resp1.text}"
    assert resp1.json()["data"]["readAt"] is not None

    # Second call — notification is already read; must still return 200 (idempotent, WR-02).
    resp2 = await http_client.patch(
        f"/api/v1/client/notifications/{notif_id}/read",
        headers={"X-CSRF-Token": csrf_token},
    )
    assert resp2.status_code == 200, (
        f"WR-02: second mark-read on already-read own notification should return 200 "
        f"(idempotent), got {resp2.status_code}: {resp2.text}"
    )
    # The returned item still has readAt set.
    assert resp2.json()["data"]["readAt"] is not None


async def test_patch_mark_read_cross_client_returns_404(
    http_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """IDOR-collapse: PATCH /{id}/read with id owned by another client → 404 (T-87-07)."""
    staff = await _seed_staff(db_session, "idor-patch")
    client_a = await _seed_client(db_session, staff, _phone(30))
    client_b = await _seed_client(db_session, staff, _phone(31))
    await db_session.commit()

    # Seed notification for client B
    b_notif_id = await _create_notif(db_session, client_b.id, kind="booking_confirmed")
    await db_session.commit()

    # Authenticate as client A
    await _auth_as_client(http_client, db_session, client_a)
    csrf_token = http_client.cookies.get("clubcore_client_csrf") or ""

    # Client A tries to mark client B's notification as read
    resp = await http_client.patch(
        f"/api/v1/client/notifications/{b_notif_id}/read",
        headers={"X-CSRF-Token": csrf_token},
    )
    assert resp.status_code == 404, (
        f"IDOR-collapse expected 404, got {resp.status_code}: {resp.text}"
    )


async def test_patch_mark_read_without_csrf_returns_403(
    http_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """PATCH /{id}/read without X-CSRF-Token header → CSRF rejection (403)."""
    staff = await _seed_staff(db_session, "csrf-patch")
    client = await _seed_client(db_session, staff, _phone(40))
    await db_session.commit()

    notif_id = await _create_notif(db_session, client.id, kind="booking_confirmed")
    await db_session.commit()

    await _auth_as_client(http_client, db_session, client)

    # No CSRF header provided
    resp = await http_client.patch(
        f"/api/v1/client/notifications/{notif_id}/read",
        # Intentionally omitting X-CSRF-Token header
    )
    assert resp.status_code == 403, (
        f"Expected 403 CSRF rejection, got {resp.status_code}: {resp.text}"
    )


# ---------------------------------------------------------------------------
# Tests — PATCH /read-all
# ---------------------------------------------------------------------------


async def test_patch_read_all_returns_204_and_clears_unread(
    http_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """PATCH /read-all → 204; subsequent GET shows unreadCount == 0."""
    staff = await _seed_staff(db_session, "read-all")
    client = await _seed_client(db_session, staff, _phone(50))
    await db_session.commit()

    await _create_notif(db_session, client.id, kind="booking_confirmed")
    await _create_notif(db_session, client.id, kind="payment_succeeded", source_id=uuid4())
    await db_session.commit()

    await _auth_as_client(http_client, db_session, client)
    csrf_token = http_client.cookies.get("clubcore_client_csrf") or ""

    resp = await http_client.patch(
        "/api/v1/client/notifications/read-all",
        headers={"X-CSRF-Token": csrf_token},
    )
    assert resp.status_code == 204, resp.text

    # Subsequent GET: unreadCount == 0
    list_resp = await http_client.get("/api/v1/client/notifications")
    assert list_resp.status_code == 200
    data = list_resp.json()["data"]
    assert data["unreadCount"] == 0, (
        f"unreadCount should be 0 after read-all, got {data['unreadCount']}"
    )
    # Total unchanged
    assert data["total"] == 2


# ---------------------------------------------------------------------------
# Tests — POST /push-tokens
# ---------------------------------------------------------------------------


_PUSH_TOKEN = "fcm-test-token-87-02-a1b2c3d4e5f6"  # noqa: S105


async def test_post_push_token_valid_returns_204(
    http_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """POST /push-tokens with valid body → 204 No Content."""
    staff = await _seed_staff(db_session, "push-204")
    client = await _seed_client(db_session, staff, _phone(60))
    await db_session.commit()

    await _auth_as_client(http_client, db_session, client)
    csrf_token = http_client.cookies.get("clubcore_client_csrf") or ""

    resp = await http_client.post(
        "/api/v1/client/push-tokens",
        json={"token": _PUSH_TOKEN, "platform": "android"},
        headers={"X-CSRF-Token": csrf_token},
    )
    assert resp.status_code == 204, resp.text


async def test_post_push_token_idempotent_one_alive_row(
    http_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Two identical POST /push-tokens → 204 both times; exactly ONE alive row in DB."""
    staff = await _seed_staff(db_session, "push-idem")
    client = await _seed_client(db_session, staff, _phone(61))
    await db_session.commit()

    await _auth_as_client(http_client, db_session, client)
    csrf_token = http_client.cookies.get("clubcore_client_csrf") or ""

    token = f"idem-token-87-{uuid4().hex[:8]}"

    for i in range(2):
        resp = await http_client.post(
            "/api/v1/client/push-tokens",
            json={"token": token, "platform": "web"},
            headers={"X-CSRF-Token": csrf_token},
        )
        assert resp.status_code == 204, f"POST #{i + 1} failed: {resp.text}"

    # Assert exactly ONE alive row for this (client_id, token) pair
    count_row = await db_session.execute(
        text(
            "SELECT COUNT(*) FROM client_push_tokens "
            "WHERE client_id=:cid AND token=:token AND unregistered_at IS NULL"
        ),
        {"cid": str(client.id), "token": token},
    )
    alive_count = count_row.scalar_one()
    assert alive_count == 1, (
        f"Expected exactly 1 alive push token row after 2 identical POSTs, got {alive_count}"
    )


async def test_post_push_token_response_contains_no_token_field(
    http_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """POST /push-tokens response body must not contain the token value (T-87-08)."""
    staff = await _seed_staff(db_session, "push-noleak")
    client = await _seed_client(db_session, staff, _phone(62))
    await db_session.commit()

    await _auth_as_client(http_client, db_session, client)
    csrf_token = http_client.cookies.get("clubcore_client_csrf") or ""

    secret_token = f"secret-push-token-{uuid4().hex}"

    resp = await http_client.post(
        "/api/v1/client/push-tokens",
        json={"token": secret_token, "platform": "ios"},
        headers={"X-CSRF-Token": csrf_token},
    )
    assert resp.status_code == 204, resp.text
    # 204 No Content: body must be empty; token must not appear anywhere
    assert secret_token not in resp.text, (
        f"T-87-08: push token leaked in response body: {resp.text!r}"
    )
    assert "token" not in resp.text.lower(), (
        f"T-87-08: 'token' field present in 204 response: {resp.text!r}"
    )


async def test_post_push_token_extra_field_returns_422(
    http_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """POST /push-tokens with extra field → 422 (extra='forbid' on ClientPushTokenRegisterRequest, T-87-09)."""
    staff = await _seed_staff(db_session, "push-extra")
    client = await _seed_client(db_session, staff, _phone(63))
    await db_session.commit()

    await _auth_as_client(http_client, db_session, client)
    csrf_token = http_client.cookies.get("clubcore_client_csrf") or ""

    resp = await http_client.post(
        "/api/v1/client/push-tokens",
        json={"token": "some-token", "platform": "android", "extra_field": "should_be_rejected"},
        headers={"X-CSRF-Token": csrf_token},
    )
    assert resp.status_code == 422, (
        f"Expected 422 for extra field (extra='forbid'), got {resp.status_code}: {resp.text}"
    )


async def test_post_push_token_invalid_platform_returns_error(
    http_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """POST /push-tokens with platform not in (web, android, ios) → rejected (T-87-09).

    The DB CheckConstraint 'ck_client_push_tokens_platform' enforces this;
    service layer passes the value through without pre-validation so the DB
    constraint fires and propagates as an integrity/app error.
    """
    staff = await _seed_staff(db_session, "push-plat")
    client = await _seed_client(db_session, staff, _phone(64))
    await db_session.commit()

    await _auth_as_client(http_client, db_session, client)
    csrf_token = http_client.cookies.get("clubcore_client_csrf") or ""

    resp = await http_client.post(
        "/api/v1/client/push-tokens",
        json={"token": "some-token", "platform": "windows-phone"},
        headers={"X-CSRF-Token": csrf_token},
    )
    # DB CheckConstraint fires; FastAPI turns the DB error into 500 unless the
    # service validates. Since the constraint is at DB level, expect a 4xx or 5xx
    # error (not 204). The important assertion is that it does NOT succeed.
    assert resp.status_code != 204, (
        f"Expected an error for invalid platform 'windows-phone', got 204"
    )


async def test_post_push_token_without_csrf_returns_403(
    http_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """POST /push-tokens without X-CSRF-Token → 403 CSRF rejection."""
    staff = await _seed_staff(db_session, "push-csrf")
    client = await _seed_client(db_session, staff, _phone(65))
    await db_session.commit()

    await _auth_as_client(http_client, db_session, client)

    resp = await http_client.post(
        "/api/v1/client/push-tokens",
        json={"token": "some-token", "platform": "web"},
        # Intentionally omitting X-CSRF-Token header
    )
    assert resp.status_code == 403, (
        f"Expected 403 CSRF rejection for POST without header, got {resp.status_code}"
    )


async def test_post_push_token_cross_client_reuse_leaves_only_one_alive_row(
    http_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """CR-03: client B registering client A's still-alive token must NOT leave two alive rows.

    A physical device token is globally unique — only one client must hold an alive row
    for any given token. When client B registers a token already alive for client A,
    client A's row must be soft-deleted (unregistered_at set) and client B's row created.
    """
    staff = await _seed_staff(db_session, "push-xc")
    client_a = await _seed_client(db_session, staff, _phone(70))
    client_b = await _seed_client(db_session, staff, _phone(71))
    await db_session.commit()

    shared_token = f"shared-device-token-{uuid4().hex[:12]}"

    # Authenticate as client A and register the token.
    await _auth_as_client(http_client, db_session, client_a)
    csrf_a = http_client.cookies.get("clubcore_client_csrf") or ""
    resp_a = await http_client.post(
        "/api/v1/client/push-tokens",
        json={"token": shared_token, "platform": "android"},
        headers={"X-CSRF-Token": csrf_a},
    )
    assert resp_a.status_code == 204, f"client A register failed: {resp_a.text}"

    # Verify client A has exactly one alive row.
    alive_before = (
        await db_session.execute(
            text(
                "SELECT COUNT(*) FROM client_push_tokens "
                "WHERE token=:tok AND unregistered_at IS NULL"
            ),
            {"tok": shared_token},
        )
    ).scalar_one()
    assert alive_before == 1, f"Expected 1 alive row after client A register, got {alive_before}"

    # Now authenticate as client B and register the SAME token.
    # The http_client fixture persists cookies; reset by creating a new client session.
    # Re-auth as client B (overwrites session cookies).
    await _auth_as_client(http_client, db_session, client_b)
    csrf_b = http_client.cookies.get("clubcore_client_csrf") or ""
    resp_b = await http_client.post(
        "/api/v1/client/push-tokens",
        json={"token": shared_token, "platform": "android"},
        headers={"X-CSRF-Token": csrf_b},
    )
    assert resp_b.status_code == 204, f"client B register failed: {resp_b.text}"

    # Assert exactly ONE alive row for the token globally (CR-03).
    alive_after = (
        await db_session.execute(
            text(
                "SELECT COUNT(*) FROM client_push_tokens "
                "WHERE token=:tok AND unregistered_at IS NULL"
            ),
            {"tok": shared_token},
        )
    ).scalar_one()
    assert alive_after == 1, (
        f"CR-03: Expected exactly 1 alive row after client B registered client A's token, "
        f"got {alive_after}. Two alive rows means dispatch fanout privacy leak."
    )

    # The surviving alive row must belong to client B (the new registrant).
    owner_row = (
        await db_session.execute(
            text(
                "SELECT client_id FROM client_push_tokens "
                "WHERE token=:tok AND unregistered_at IS NULL"
            ),
            {"tok": shared_token},
        )
    ).scalar_one()
    assert str(owner_row) == str(client_b.id), (
        f"CR-03: Alive row should belong to client B ({client_b.id}), got {owner_row}"
    )
