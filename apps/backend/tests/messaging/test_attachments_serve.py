"""Phase 92 Plan 03 Task 3 — HTTP security suite for GET /messages/attachments/{id} (TDD RED).

Seven behaviours proven with real bytes and an in-memory Storage stub:
  1. Client A GET of A's own attachment → 200, bytes served, anti-XSS header triad.
  2. Client B GET of A's attachment → 404 (IDOR 404-collapse, never 403).
  3. Unauthenticated GET → 401.
  4. GET of random/non-existent UUID → 404.
  5. End-to-end: POST upload → POST /messages with attachmentId → GET list shows sub-object
     → GET serve URL returns bytes with anti-XSS headers.
  6. Upload SVG with Content-Type: image/png → 4xx (rejected; never stored).
  7. Upload 6MB payload → 413.

Harness: SAVEPOINT db_session + ASGITransport AsyncClient (no real network — CLAUDE.md).
Auth: OTP flow via _auth_as_client (mirrors test_messaging_rest.py).
Storage stub: InMemoryStorage — in-memory dict keyed by object_key; injected via get_storage
dependency override to avoid real S3.

Security assertions (T-92-10..14):
  - Content-Disposition: attachment (never inline) — T-92-11.
  - X-Content-Type-Options: nosniff — T-92-11.
  - Content-Type == stored validated mime (never client-derived) — T-92-11.
  - IDOR: client B → 404, not 403 (no existence leak) — T-92-10.
  - Unauthenticated → 401 — T-92-13.
  - Object key read from owned DB row only (no path traversal) — T-92-12.
"""

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
from app.integrations.storage import get_storage
from app.modules.auth.models import OtpCode, User
from app.modules.clients.models import Client

pytestmark = pytest.mark.asyncio(loop_scope="function")

# ---------------------------------------------------------------------------
# Phone constants — unique to serve tests; no collision with other modules
# ---------------------------------------------------------------------------

_BASE_PHONE = "+79169002"


def _phone(n: int) -> str:
    """Return a stable E.164 phone for test client n (1-99)."""
    return f"{_BASE_PHONE}{n:04d}"


# ---------------------------------------------------------------------------
# Magic byte constants (real bytes — no mocking)
# ---------------------------------------------------------------------------

# JPEG SOI marker — 261 bytes total so guess_allowed_mime sees enough
JPEG_BYTES = b"\xff\xd8\xff\xe0" + b"\x00" * 257

# SVG content — valid image but NOT on the allowlist (T-92-01)
SVG_BYTES = b'<svg xmlns="http://www.w3.org/2000/svg"><rect/></svg>' + b"\x00" * 209

# 6 MB of zeros — exceeds the 5 MB cap
SIX_MB = b"\x00" * (6 * 1024 * 1024)


# ---------------------------------------------------------------------------
# In-memory Storage stub
# ---------------------------------------------------------------------------


class InMemoryStorage:
    """In-memory Storage stub for serve-endpoint tests.

    Stores bytes by object_key so open_stream can return real stored bytes.
    No real S3 required.
    """

    def __init__(self) -> None:
        self._store: dict[str, bytes] = {}
        self._content_types: dict[str, str] = {}

    async def put(self, key: str, data: bytes, content_type: str) -> None:
        self._store[key] = data
        self._content_types[key] = content_type

    async def open_stream(self, key: str) -> AsyncIterator[bytes]:  # type: ignore[override]
        # Async generator (matches the real S3 adapter): calling open_stream(key)
        # returns an async iterator directly, NOT a coroutine — StreamingResponse
        # consumes it as-is (a coroutine here raises "'coroutine' object is not iterable").
        data = self._store.get(key, b"")
        if data:
            yield data

    async def ensure_bucket(self) -> None:
        pass


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def in_memory_storage() -> InMemoryStorage:
    return InMemoryStorage()


@pytest_asyncio.fixture
async def _overridden_app(
    app: FastAPI,
    db_session: AsyncSession,
    in_memory_storage: InMemoryStorage,
) -> AsyncIterator[FastAPI]:
    """Install dependency overrides: SAVEPOINT session + in-memory storage."""

    async def _override_get_db() -> AsyncIterator[AsyncSession]:
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_redis] = lambda: app.state.redis
    app.dependency_overrides[get_storage] = lambda: in_memory_storage
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
    """Flush Redis before each test so idempotency keys don't bleed."""
    await app.state.redis.flushdb()


# ---------------------------------------------------------------------------
# Auth helper — mirrors test_messaging_rest.py exactly
# ---------------------------------------------------------------------------


async def _auth_as_client(
    http_client: AsyncClient,
    db_session: AsyncSession,
    client: Client,
) -> str:
    """OTP flow: request → patch code → verify → return cc_client_access token value."""
    req = await http_client.post(
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

    verify = await http_client.post(
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
        email=f"serve-ep-staff-{suffix or uuid4().hex[:8]}@example.com",
        password_hash=await hash_password("serve-ep-staff-pw-secure-92"),
        role=Role.RECEPTION,
        full_name="Serve Endpoint Test Staff",
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
        first_name="Серв",
        last_name="Тест",
        phone=phone,
        telegram_user_id=abs(hash(phone)) % (10**9),
        created_by_user_id=staff.id,
    )
    db_session.add(client)
    await db_session.flush()
    return client


def _idem_key(n: int = 1) -> str:
    """Generate a unique idempotency key (16-char min)."""
    return f"serve-idem-key-test-{n:04d}-{uuid4().hex[:4]}"


def _csrf(client: AsyncClient) -> str:
    return client.cookies.get("clubcore_client_csrf") or ""


# ---------------------------------------------------------------------------
# Test 1: Client A GET of A's own attachment → 200, bytes, anti-XSS headers
# ---------------------------------------------------------------------------


async def test_serve_own_attachment_returns_200_with_anti_xss_headers(
    http_client: AsyncClient,
    db_session: AsyncSession,
    in_memory_storage: InMemoryStorage,
) -> None:
    """Client A GET of A's own attachment → 200, body=stored bytes, anti-XSS header triad.

    Asserts (T-92-11):
      Content-Type == stored validated mime (image/jpeg, never client-derived)
      Content-Disposition: attachment
      X-Content-Type-Options: nosniff
    """
    staff = await _seed_staff(db_session, "serve-1")
    client_a = await _seed_client(db_session, staff, _phone(1))
    await db_session.commit()

    await _auth_as_client(http_client, db_session, client_a)
    csrf = _csrf(http_client)

    # Upload a JPEG attachment
    resp = await http_client.post(
        "/api/v1/client/messages/attachments",
        headers={"X-CSRF-Token": csrf},
        files={"file": ("photo.jpg", JPEG_BYTES, "image/jpeg")},
    )
    assert resp.status_code == 200, f"Upload failed: {resp.text}"
    attachment_id = resp.json()["data"]["attachmentId"]

    # GET the serve endpoint
    serve_resp = await http_client.get(
        f"/api/v1/client/messages/attachments/{attachment_id}",
    )

    assert serve_resp.status_code == 200, f"Serve failed: {serve_resp.text}"
    # Body is the stored JPEG bytes
    assert serve_resp.content == JPEG_BYTES, "Served bytes do not match uploaded bytes"
    # Content-Type == stored validated mime (T-92-11 — never client-derived)
    assert serve_resp.headers["content-type"] == "image/jpeg", (
        f"Expected image/jpeg, got {serve_resp.headers.get('content-type')}"
    )
    # Content-Disposition: attachment (never inline) — T-92-11
    assert "attachment" in serve_resp.headers.get("content-disposition", ""), (
        f"Expected Content-Disposition: attachment, "
        f"got: {serve_resp.headers.get('content-disposition')}"
    )
    # X-Content-Type-Options: nosniff — T-92-11
    assert serve_resp.headers.get("x-content-type-options") == "nosniff", (
        f"Expected X-Content-Type-Options: nosniff, "
        f"got: {serve_resp.headers.get('x-content-type-options')}"
    )


# ---------------------------------------------------------------------------
# Test 2: Client B GET of Client A's attachment → 404 (IDOR 404-collapse)
# ---------------------------------------------------------------------------


async def test_serve_other_clients_attachment_returns_404_idor_collapse(
    http_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Client B GET of A's attachment → 404 (IDOR 404-collapse, never 403; T-92-10)."""
    staff = await _seed_staff(db_session, "serve-2")
    client_a = await _seed_client(db_session, staff, _phone(2))
    client_b = await _seed_client(db_session, staff, _phone(3))
    await db_session.commit()

    # Auth as client A and upload
    await _auth_as_client(http_client, db_session, client_a)
    csrf = _csrf(http_client)

    upload_resp = await http_client.post(
        "/api/v1/client/messages/attachments",
        files={"file": ("photo.jpg", JPEG_BYTES, "image/jpeg")},
        headers={"X-CSRF-Token": csrf},
    )
    assert upload_resp.status_code == 200, f"Upload failed: {upload_resp.text}"
    attachment_id = upload_resp.json()["data"]["attachmentId"]

    # Now auth as client B (clears client A's cookies)
    await _auth_as_client(http_client, db_session, client_b)

    # Client B tries to serve client A's attachment
    serve_resp = await http_client.get(
        f"/api/v1/client/messages/attachments/{attachment_id}",
    )
    # Must be 404 (never 403 — no existence leak, T-92-10)
    assert serve_resp.status_code == 404, (
        f"Expected 404 for IDOR attempt, got {serve_resp.status_code}: {serve_resp.text}"
    )


# ---------------------------------------------------------------------------
# Test 3: Unauthenticated GET → 401
# ---------------------------------------------------------------------------


async def test_serve_unauthenticated_returns_401(
    http_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Unauthenticated GET of any attachment id → 401 (T-92-13)."""
    # Use a random UUID — even if it existed, unauthenticated must be rejected first
    random_id = uuid4()

    serve_resp = await http_client.get(
        f"/api/v1/client/messages/attachments/{random_id}",
    )
    assert serve_resp.status_code == 401, (
        f"Expected 401 for unauthenticated request, got {serve_resp.status_code}"
    )


# ---------------------------------------------------------------------------
# Test 4: GET of non-existent UUID → 404
# ---------------------------------------------------------------------------


async def test_serve_nonexistent_attachment_returns_404(
    http_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Authenticated GET of a random/non-existent UUID → 404 (T-92-10)."""
    staff = await _seed_staff(db_session, "serve-4")
    client = await _seed_client(db_session, staff, _phone(4))
    await db_session.commit()

    await _auth_as_client(http_client, db_session, client)

    random_id = uuid4()
    serve_resp = await http_client.get(
        f"/api/v1/client/messages/attachments/{random_id}",
    )
    assert serve_resp.status_code == 404, (
        f"Expected 404 for non-existent attachment, got {serve_resp.status_code}"
    )


# ---------------------------------------------------------------------------
# Test 5: End-to-end round-trip — upload → send → list → serve
# ---------------------------------------------------------------------------


async def test_end_to_end_upload_send_list_serve(
    http_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Full two-step flow: POST upload → POST /messages with attachmentId
    → GET list shows attachment sub-object → GET serve URL returns bytes.

    All four steps proven with real bytes (JPEG_BYTES) and in-memory storage.
    """
    staff = await _seed_staff(db_session, "serve-5")
    client = await _seed_client(db_session, staff, _phone(5))
    await db_session.commit()

    await _auth_as_client(http_client, db_session, client)
    csrf = _csrf(http_client)

    # Step 1: Upload
    upload_resp = await http_client.post(
        "/api/v1/client/messages/attachments",
        files={"file": ("photo.jpg", JPEG_BYTES, "image/jpeg")},
        headers={"X-CSRF-Token": csrf},
    )
    assert upload_resp.status_code == 200, f"Upload failed: {upload_resp.text}"
    upload_data = upload_resp.json()["data"]
    attachment_id = upload_data["attachmentId"]
    preview_url = upload_data["previewUrl"]

    # Step 2: POST /messages with attachmentId (two-step flow)
    send_resp = await http_client.post(
        "/api/v1/client/messages",
        json={"attachmentId": attachment_id},
        headers={
            "X-CSRF-Token": csrf,
            "Idempotency-Key": _idem_key(5),
        },
    )
    assert send_resp.status_code == 200, f"Send failed: {send_resp.text}"
    send_data = send_resp.json()["data"]
    assert send_data["attachment"] is not None, "Expected attachment sub-object in send response"
    assert send_data["attachment"]["id"] == attachment_id
    assert send_data["attachment"]["mimeType"] == "image/jpeg"

    # Step 3: GET /messages list shows attachment sub-object
    list_resp = await http_client.get("/api/v1/client/messages")
    assert list_resp.status_code == 200, f"List failed: {list_resp.text}"
    items = list_resp.json()["data"]["items"]
    assert len(items) == 1, f"Expected 1 message, got {len(items)}"
    att_item = items[0]["attachment"]
    assert att_item is not None, "Expected attachment sub-object in list item"
    assert att_item["id"] == attachment_id
    assert att_item["mimeType"] == "image/jpeg"
    assert "/messages/attachments/" in att_item["url"]

    # Step 4: GET serve URL returns bytes with anti-XSS headers
    serve_resp = await http_client.get(preview_url)
    assert serve_resp.status_code == 200, f"Serve failed: {serve_resp.text}"
    assert serve_resp.content == JPEG_BYTES, "Served bytes do not match uploaded bytes"
    assert serve_resp.headers["content-type"] == "image/jpeg"
    assert "attachment" in serve_resp.headers.get("content-disposition", "")
    assert serve_resp.headers.get("x-content-type-options") == "nosniff"


# ---------------------------------------------------------------------------
# Test 6: SVG with fake Content-Type → 4xx (rejected; never stored)
# ---------------------------------------------------------------------------


async def test_upload_svg_with_fake_content_type_rejected(
    http_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Upload SVG bytes with Content-Type: image/png → 4xx (415).

    Magic-byte validation rejects it; the file is never stored/served (T-92-05 LOCKED).
    """
    staff = await _seed_staff(db_session, "serve-6")
    client = await _seed_client(db_session, staff, _phone(6))
    await db_session.commit()

    await _auth_as_client(http_client, db_session, client)
    csrf = _csrf(http_client)

    resp = await http_client.post(
        "/api/v1/client/messages/attachments",
        files={"file": ("photo.png", SVG_BYTES, "image/png")},
        headers={"X-CSRF-Token": csrf},
    )
    # Must be 4xx — magic-byte guard rejects SVG regardless of claimed Content-Type
    assert resp.status_code >= 400, (
        f"Expected 4xx for SVG-with-fake-Content-Type, got {resp.status_code}: {resp.text}"
    )


# ---------------------------------------------------------------------------
# Test 7: 6MB upload → 413
# ---------------------------------------------------------------------------


async def test_upload_six_mb_returns_413(
    http_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """6MB upload → 413 Payload Too Large (T-92-06)."""
    staff = await _seed_staff(db_session, "serve-7")
    client = await _seed_client(db_session, staff, _phone(7))
    await db_session.commit()

    await _auth_as_client(http_client, db_session, client)
    csrf = _csrf(http_client)

    resp = await http_client.post(
        "/api/v1/client/messages/attachments",
        files={"file": ("large.jpg", SIX_MB, "image/jpeg")},
        headers={"X-CSRF-Token": csrf},
    )
    assert resp.status_code == 413, (
        f"Expected 413 for 6MB upload, got {resp.status_code}: {resp.text}"
    )
