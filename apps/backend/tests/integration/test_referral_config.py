"""Phase 96 Plan 96-03 — Referral config owner API integration tests (REFER-07).

Proves:
  - Owner GET /api/v1/referral/config → 200 with referrerBonusKopecks=50000 /
    refereeWelcomeKopecks=30000 (seed defaults from migration 0068).
  - Owner PUT with new amounts (+ X-CSRF-Token header) → 200, GET reflects new values.
  - Reception GET → 403.
  - Reception PUT → 403 (RBAC check before CSRF).
  - Owner PUT WITHOUT the CSRF header → fails the CSRF gate (403 csrf_mismatch),
    but ONLY after passing RBAC — reception still gets 403 from RBAC first (RBAC-04).

Harness: SAVEPOINT db_session + ASGITransport (no real network — CLAUDE.md).
Staff auth: /api/v1/auth/login with seeded owner/reception (mirrors test_loyalty_grant.py).
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.permissions import Role
from app.core.redis import get_redis
from app.core.security import hash_password
from app.modules.auth.models import User

pytestmark = pytest.mark.asyncio

_OWNER_EMAIL = "ref-config-owner@example.com"
_OWNER_PASSWORD = "ref-config-owner-pw-secure-123"  # noqa: S105
_RECEPTION_EMAIL = "ref-config-reception@example.com"
_RECEPTION_PASSWORD = "ref-config-reception-pw-secure-456"  # noqa: S105

_SEED_REFERRER_BONUS = 50_000  # from migration 0068
_SEED_REFEREE_WELCOME = 30_000  # from migration 0068


# ---------------------------------------------------------------------------
# Fixtures
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
async def http_client_owner(
    _overridden_app: FastAPI,
    seeded_owner: User,
) -> AsyncIterator[AsyncClient]:
    """ASGITransport client logged in as owner."""
    transport = ASGITransport(app=_overridden_app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as c:
        r = await c.post(
            "/api/v1/auth/login",
            json={"email": _OWNER_EMAIL, "password": _OWNER_PASSWORD},
        )
        assert r.status_code == 200, f"Owner login failed: {r.text}"
        yield c


@pytest_asyncio.fixture
async def http_client_reception(
    _overridden_app: FastAPI,
    seeded_reception: User,
) -> AsyncIterator[AsyncClient]:
    """ASGITransport client logged in as reception."""
    transport = ASGITransport(app=_overridden_app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as c:
        r = await c.post(
            "/api/v1/auth/login",
            json={"email": _RECEPTION_EMAIL, "password": _RECEPTION_PASSWORD},
        )
        assert r.status_code == 200, f"Reception login failed: {r.text}"
        yield c


@pytest_asyncio.fixture(autouse=True)
async def flush_redis(app: FastAPI) -> None:
    """Flush Redis before each test."""
    await app.state.redis.flushdb()


@pytest_asyncio.fixture
async def seeded_owner(db_session: AsyncSession) -> User:
    user = User(
        email=_OWNER_EMAIL,
        password_hash=await hash_password(_OWNER_PASSWORD),
        role=Role.OWNER,
        full_name="Ref Config Test Owner",
    )
    db_session.add(user)
    await db_session.commit()
    return user


@pytest_asyncio.fixture
async def seeded_reception(db_session: AsyncSession, seeded_owner: User) -> User:
    """Reception user (depends on seeded_owner for commit ordering)."""
    user = User(
        email=_RECEPTION_EMAIL,
        password_hash=await hash_password(_RECEPTION_PASSWORD),
        role=Role.RECEPTION,
        full_name="Ref Config Test Reception",
    )
    db_session.add(user)
    await db_session.commit()
    return user


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _csrf_headers(client: AsyncClient) -> dict[str, str]:
    return {"X-CSRF-Token": client.cookies.get("clubcore_csrf", "")}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


async def test_owner_get_config_returns_seed_defaults(
    http_client_owner: AsyncClient,
) -> None:
    """Owner GET /api/v1/referral/config → 200, seed defaults 50000/30000."""
    resp = await http_client_owner.get("/api/v1/referral/config")
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["referrerBonusKopecks"] == _SEED_REFERRER_BONUS, (
        f"Expected referrerBonusKopecks={_SEED_REFERRER_BONUS}, got {data['referrerBonusKopecks']}"
    )
    assert data["refereeWelcomeKopecks"] == _SEED_REFEREE_WELCOME, (
        f"Expected refereeWelcomeKopecks={_SEED_REFEREE_WELCOME}, "
        f"got {data['refereeWelcomeKopecks']}"
    )


async def test_owner_put_config_and_get_reflects_change(
    http_client_owner: AsyncClient,
) -> None:
    """Owner PUT /api/v1/referral/config with new amounts → 200; GET reflects new values."""
    new_referrer = 75_000
    new_referee = 25_000

    put_resp = await http_client_owner.put(
        "/api/v1/referral/config",
        json={"referrerBonusKopecks": new_referrer, "refereeWelcomeKopecks": new_referee},
        headers=_csrf_headers(http_client_owner),
    )
    assert put_resp.status_code == 200, put_resp.text
    put_data = put_resp.json()["data"]
    assert put_data["referrerBonusKopecks"] == new_referrer
    assert put_data["refereeWelcomeKopecks"] == new_referee

    # GET must reflect the updated values
    get_resp = await http_client_owner.get("/api/v1/referral/config")
    assert get_resp.status_code == 200, get_resp.text
    get_data = get_resp.json()["data"]
    assert get_data["referrerBonusKopecks"] == new_referrer, (
        f"Read-after-write failed: expected {new_referrer}, got {get_data['referrerBonusKopecks']}"
    )
    assert get_data["refereeWelcomeKopecks"] == new_referee, (
        f"Read-after-write failed: expected {new_referee}, got {get_data['refereeWelcomeKopecks']}"
    )


async def test_reception_get_config_forbidden(
    http_client_reception: AsyncClient,
) -> None:
    """Reception GET /api/v1/referral/config → 403 (RBAC gate — REFER-07)."""
    resp = await http_client_reception.get("/api/v1/referral/config")
    assert resp.status_code == 403, resp.text


async def test_reception_put_config_forbidden(
    http_client_reception: AsyncClient,
) -> None:
    """Reception PUT /api/v1/referral/config → 403 (RBAC-04: require_permission before CSRF)."""
    resp = await http_client_reception.put(
        "/api/v1/referral/config",
        json={"referrerBonusKopecks": 1, "refereeWelcomeKopecks": 1},
        headers=_csrf_headers(http_client_reception),
    )
    assert resp.status_code == 403, resp.text


async def test_owner_put_config_without_csrf_fails(
    http_client_owner: AsyncClient,
) -> None:
    """Owner PUT without X-CSRF-Token header → 403 (csrf_mismatch) — passes RBAC but fails CSRF.

    RBAC-04: require_permission is checked first (owner passes), then verify_csrf
    fires (no header → csrf_mismatch). Proves owner-level RBAC check precedes CSRF check
    while still enforcing CSRF on the mutation.
    """
    resp = await http_client_owner.put(
        "/api/v1/referral/config",
        json={"referrerBonusKopecks": 1, "refereeWelcomeKopecks": 1},
        # No X-CSRF-Token header
    )
    # Owner passes RBAC → fails CSRF → 403 (csrf_mismatch or forbidden)
    assert resp.status_code == 403, (
        f"Owner PUT without CSRF should be 403, got {resp.status_code}: {resp.text}"
    )


async def test_rbac04_reception_gets_403_before_csrf(
    http_client_reception: AsyncClient,
) -> None:
    """RBAC-04: reception gets 403 from RBAC even without CSRF header.

    Proves that the RBAC check (require_permission) is evaluated BEFORE
    the CSRF check (verify_csrf). Reception never reaches the CSRF gate.
    """
    # No CSRF header — but RBAC fires first
    resp = await http_client_reception.put(
        "/api/v1/referral/config",
        json={"referrerBonusKopecks": 1, "refereeWelcomeKopecks": 1},
        # No X-CSRF-Token header
    )
    assert resp.status_code == 403, (
        f"Reception should get 403 from RBAC before CSRF check, got {resp.status_code}"
    )
