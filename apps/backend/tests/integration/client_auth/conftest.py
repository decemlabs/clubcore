"""Fixtures for client_auth integration tests (Phase 68 Plan 06).

Provides:
  - stub_client_otp_sender: autouse fixture that replaces the composition-root
      client OTP sender slot with a no-op stub so tests never hit the Telegram API.
  - redis_clean: flush Redis between tests (rate-limit + session key isolation)
  - seeded_staff: a staff User required for created_by_user_id FK on Client rows
  - linked_client: Client with telegram_user_id set and alive (eligible for OTP)
  - unlinked_client: Client with telegram_user_id=None (D-02 silent no-op)
  - soft_deleted_client: Client with deleted_at set (D-02 silent no-op)
  - unknown_phone: a phone string that maps to no Client row at all

All client fixtures depend on seeded_staff for the created_by_user_id FK.
All fixtures use the SAVEPOINT-rolled-back db_session from the root conftest.

Note on stub_client_otp_sender:
  `create_app()` in main.py registers a real Telegram bot sender via
  register_client_otp_sender() during the lifespan. The autouse fixture replaces
  it with a no-op async callable so tests never make real Telegram API calls.
  This mirrors how tests/conftest.py stub_telegram_sender handles the staff OTP
  sender (Phase 7 TEST-03 precedent).
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest
import pytest_asyncio
from fastapi import FastAPI
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permissions import Role
from app.core.security import hash_password
from app.modules.auth.models import User
from app.modules.clients.models import Client

pytestmark = pytest.mark.asyncio


@pytest.fixture(autouse=True)
def stub_client_otp_sender(app: FastAPI, monkeypatch: pytest.MonkeyPatch) -> None:
    """Replace the real Telegram OTP sender with a no-op stub for all client_auth tests.

    `create_app()` unconditionally registers a real Telegram bot sender via
    register_client_otp_sender() during the app lifespan. Without this stub, any
    OTP request for a linked_client would attempt a real Telegram API call (which
    fails in CI/test environments).

    Depends on `app` to ensure the lifespan has already run register_client_otp_sender
    with the real sender before we replace it with the stub. Without this ordering,
    the patch would be overwritten when the lifespan fires after the fixture.

    Mirrors the test-isolation pattern from tests/conftest.py:stub_telegram_sender
    (Phase 7 TEST-03 precedent).
    """
    _ = app  # ensure lifespan + register_client_otp_sender has run before we patch
    from app.modules.client_auth import service as client_auth_service

    async def _noop_sender(chat_id: int, code: str) -> None:
        """No-op: records nothing; makes no network call."""

    monkeypatch.setattr(client_auth_service, "_client_otp_sender", _noop_sender)


# ---------------------------------------------------------------------------
# Phone constants — deterministic per test run
# ---------------------------------------------------------------------------

_LINKED_PHONE = "+79990000001"
_UNLINKED_PHONE = "+79990000002"
_SOFT_DELETED_PHONE = "+79990000003"
UNKNOWN_PHONE = "+79990000099"  # never inserted into DB

# Deterministic Telegram user_id used for the linked client's account
_LINKED_TELEGRAM_USER_ID = 123_456_789


@pytest_asyncio.fixture
async def redis_clean(app: FastAPI) -> Redis:
    """Flush Redis between tests so rate-limit + session keys don't bleed."""
    client: Redis = app.state.redis
    await client.flushdb()
    return client


@pytest_asyncio.fixture
async def seeded_staff(db_session: AsyncSession) -> User:
    """Insert a staff (RECEPTION) user — provides created_by_user_id FK for Client rows."""
    suffix = uuid4().hex[:8]
    user = User(
        email=f"staff-client-auth-test+{suffix}@example.com",
        password_hash=await hash_password("test-staff-pw-secure-123"),
        role=Role.RECEPTION,
        full_name="Test Staff Client Auth",
    )
    db_session.add(user)
    await db_session.commit()
    return user


@pytest_asyncio.fixture
async def linked_client(db_session: AsyncSession, seeded_staff: User) -> Client:
    """Alive Client with telegram_user_id set — eligible to receive OTP DMs (D-01)."""
    suffix = uuid4().hex[:6]
    client = Client(
        first_name="Linked",
        last_name=f"Client{suffix}",
        phone=_LINKED_PHONE,
        telegram_user_id=_LINKED_TELEGRAM_USER_ID,
        created_by_user_id=seeded_staff.id,
    )
    db_session.add(client)
    await db_session.commit()
    return client


@pytest_asyncio.fixture
async def unlinked_client(db_session: AsyncSession, seeded_staff: User) -> Client:
    """Alive Client with telegram_user_id=None — D-02 silent no-op (no OTP sent)."""
    suffix = uuid4().hex[:6]
    client = Client(
        first_name="Unlinked",
        last_name=f"Client{suffix}",
        phone=_UNLINKED_PHONE,
        telegram_user_id=None,
        created_by_user_id=seeded_staff.id,
    )
    db_session.add(client)
    await db_session.commit()
    return client


@pytest_asyncio.fixture
async def soft_deleted_client(db_session: AsyncSession, seeded_staff: User) -> Client:
    """Soft-deleted Client with Telegram link — deleted_at IS NOT NULL gate tested (IN-02).

    telegram_user_id is set to a real value so the only distinguishing factor is
    deleted_at. This ensures the deleted_at.is_(None) filter in the service is
    exercised directly: if the filter were accidentally removed, this fixture would
    no longer be blocked by the unlinked-phone guard and the test would catch it.
    """
    suffix = uuid4().hex[:6]
    client = Client(
        first_name="Deleted",
        last_name=f"Client{suffix}",
        phone=_SOFT_DELETED_PHONE,
        telegram_user_id=987_654_321,  # IN-02: was None — now isolates the deleted_at filter
        created_by_user_id=seeded_staff.id,
        deleted_at=datetime.now(tz=UTC),
    )
    db_session.add(client)
    await db_session.commit()
    return client
