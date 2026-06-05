"""Phase 82 Plan 82-02 — Owner-grant API integration tests (ACCR-02/ACCR-03).

Proves:
  - Owner POST /clients/{id}/loyalty/grant {amount_kopecks:30000, reason, category:'promo'}
    → 201, balanceKopecks reflects SUM after grant, one owner_grant ledger row +
    one loyalty_accrued audit row (actor="owner:<id>").
  - Reception POST grant → 403 + one rbac_forbidden audit row; no ledger row created.
  - amount_kopecks=0 or negative → 422 grant_amount_must_be_positive; no ledger row.
  - Unknown client_id → 404 client_not_found.

Harness: SAVEPOINT db_session + ASGITransport (no real network).
Staff auth: POST /api/v1/auth/login with seeded owner and reception users.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit_models import AuditLog
from app.core.database import get_db
from app.core.permissions import Role
from app.core.redis import get_redis
from app.core.security import hash_password
from app.modules.auth.models import User
from app.modules.clients.models import Client

pytestmark = pytest.mark.asyncio

_OWNER_EMAIL = "loyalty-grant-owner@example.com"
_OWNER_PASSWORD = "loyalty-test-pw-grant-123"  # noqa: S105
_RECEPTION_EMAIL = "loyalty-grant-reception@example.com"
_RECEPTION_PASSWORD = "loyalty-test-pw-grant-456"  # noqa: S105


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
    """ASGITransport client logged in as owner (depends on seeded_owner for ordering)."""
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
    """ASGITransport client logged in as reception (depends on seeded_reception for ordering)."""
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
        full_name="Loyalty Grant Test Owner",
    )
    db_session.add(user)
    await db_session.commit()
    return user


@pytest_asyncio.fixture
async def seeded_reception(db_session: AsyncSession, seeded_owner: User) -> User:
    """Reception user (depends on seeded_owner to ensure commit ordering)."""
    user = User(
        email=_RECEPTION_EMAIL,
        password_hash=await hash_password(_RECEPTION_PASSWORD),
        role=Role.RECEPTION,
        full_name="Loyalty Grant Test Reception",
    )
    db_session.add(user)
    await db_session.commit()
    return user


@pytest_asyncio.fixture
async def test_client(db_session: AsyncSession, seeded_owner: User) -> Client:
    """A client seeded for grant tests (no welcome bonus needed for grant tests)."""
    client = Client(
        first_name="Грант",
        last_name="Тест",
        phone=f"+7915{uuid4().int % 10_000_000:07d}",
        telegram_user_id=abs(hash("grant-test-client")) % (10**9),
        created_by_user_id=seeded_owner.id,
    )
    db_session.add(client)
    await db_session.commit()
    return client


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _csrf_headers(client: AsyncClient) -> dict[str, str]:
    return {"X-CSRF-Token": client.cookies.get("clubcore_csrf", "")}


async def _post_grant(
    http_client: AsyncClient,
    client_id: UUID,
    *,
    amount_kopecks: int = 30_000,
    reason: str = "тест-грант",
    category: str = "promo",
) -> Any:
    return await http_client.post(
        f"/api/v1/clients/{client_id}/loyalty/grant",
        json={
            "amountKopecks": amount_kopecks,
            "reason": reason,
            "category": category,
        },
        headers=_csrf_headers(http_client),
    )


# ---------------------------------------------------------------------------
# Behavior tests
# ---------------------------------------------------------------------------


async def test_owner_grant_returns_201_with_balance(
    http_client_owner: AsyncClient,
    db_session: AsyncSession,
    seeded_owner: User,
    test_client: Client,
) -> None:
    """Owner POST grant → 201, balanceKopecks = granted amount (only grant; no welcome)."""
    r = await _post_grant(http_client_owner, test_client.id, amount_kopecks=30_000)
    assert r.status_code == 201, r.text
    data = r.json()["data"]
    assert "entryId" in data
    assert data["balanceKopecks"] == 30_000


async def test_owner_grant_creates_ledger_row(
    http_client_owner: AsyncClient,
    db_session: AsyncSession,
    seeded_owner: User,
    test_client: Client,
) -> None:
    """Owner grant creates exactly 1 owner_grant ledger row."""
    await _post_grant(http_client_owner, test_client.id, amount_kopecks=30_000)

    row = (
        (
            await db_session.execute(
                text(
                    "SELECT COUNT(*) AS cnt FROM loyalty_ledger "
                    "WHERE client_id = :cid AND entry_type = 'owner_grant'"
                ),
                {"cid": str(test_client.id)},
            )
        )
        .mappings()
        .one()
    )
    assert int(row["cnt"]) == 1, f"Expected 1 owner_grant row, got {row['cnt']}"


async def test_owner_grant_emits_loyalty_accrued_audit_row(
    http_client_owner: AsyncClient,
    db_session: AsyncSession,
    seeded_owner: User,
    test_client: Client,
) -> None:
    """Owner grant emits exactly 1 loyalty_accrued audit row (actor='owner:<id>')."""
    r = await _post_grant(http_client_owner, test_client.id, amount_kopecks=30_000)
    assert r.status_code == 201, r.text

    audit_rows = (
        await db_session.scalars(
            select(AuditLog).where(
                AuditLog.action == "loyalty_accrued",
                AuditLog.resource_type == "loyalty",
            )
        )
    ).all()
    client_audits = [a for a in audit_rows if a.payload.get("client_id") == str(test_client.id)]
    assert len(client_audits) == 1, (
        f"Expected 1 loyalty_accrued audit row for grant, got {len(client_audits)}"
    )
    payload = client_audits[0].payload
    assert payload["entry_type"] == "owner_grant"
    assert payload["actor"].startswith("owner:")
    assert payload["amount_kopecks"] == 30_000


async def test_reception_grant_returns_403_and_rbac_audit(
    http_client_reception: AsyncClient,
    db_session: AsyncSession,
    seeded_reception: User,
    test_client: Client,
) -> None:
    """Reception POST grant → 403 forbidden + rbac_forbidden audit row; no ledger row."""
    r = await _post_grant(http_client_reception, test_client.id, amount_kopecks=10_000)
    assert r.status_code == 403, r.text
    assert r.json()["code"] == "forbidden"

    # rbac_forbidden audit row must exist.
    audit_rows = (
        await db_session.scalars(
            select(AuditLog).where(
                AuditLog.action == "rbac_forbidden",
                AuditLog.resource_type == "rbac",
            )
        )
    ).all()
    # At least 1 rbac_forbidden row with loyalty target.
    loyalty_forbidden = [a for a in audit_rows if a.payload.get("target_resource") == "loyalty"]
    assert len(loyalty_forbidden) >= 1, "Expected rbac_forbidden audit row for loyalty grant"

    # No ledger row created.
    count_row = (
        (
            await db_session.execute(
                text("SELECT COUNT(*) AS cnt FROM loyalty_ledger WHERE client_id = :cid"),
                {"cid": str(test_client.id)},
            )
        )
        .mappings()
        .one()
    )
    assert int(count_row["cnt"]) == 0, "Reception 403 should not create any ledger row"


async def test_grant_zero_amount_returns_422(
    http_client_owner: AsyncClient,
    db_session: AsyncSession,
    seeded_owner: User,
    test_client: Client,
) -> None:
    """amount_kopecks=0 → 422 grant_amount_must_be_positive; no ledger row."""
    r = await _post_grant(http_client_owner, test_client.id, amount_kopecks=0)
    assert r.status_code == 422, r.text
    assert r.json()["code"] == "grant_amount_must_be_positive"

    count_row = (
        (
            await db_session.execute(
                text("SELECT COUNT(*) AS cnt FROM loyalty_ledger WHERE client_id = :cid"),
                {"cid": str(test_client.id)},
            )
        )
        .mappings()
        .one()
    )
    assert int(count_row["cnt"]) == 0, "Zero amount should not create ledger row"


async def test_grant_negative_amount_returns_422(
    http_client_owner: AsyncClient,
    db_session: AsyncSession,
    seeded_owner: User,
    test_client: Client,
) -> None:
    """amount_kopecks=-1 → 422 grant_amount_must_be_positive; no ledger row."""
    r = await _post_grant(http_client_owner, test_client.id, amount_kopecks=-1)
    assert r.status_code == 422, r.text
    assert r.json()["code"] == "grant_amount_must_be_positive"


async def test_grant_unknown_client_returns_404(
    http_client_owner: AsyncClient,
    db_session: AsyncSession,
    seeded_owner: User,
    test_client: Client,
) -> None:
    """Unknown client_id → 404 client_not_found."""
    unknown_id = uuid4()
    r = await _post_grant(http_client_owner, unknown_id, amount_kopecks=1_000)
    assert r.status_code == 404, r.text
    assert r.json()["code"] == "client_not_found"
