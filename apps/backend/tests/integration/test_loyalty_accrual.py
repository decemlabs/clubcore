"""Phase 82 Plan 82-02 — Welcome accrual idempotency integration tests (ACCR-01/ACCR-03).

Proves:
  - Creating a client via POST /api/v1/clients produces exactly ONE loyalty_ledger
    welcome row of 50000 kopecks AND exactly one loyalty_accrued audit row
    (entry_type='welcome', actor='welcome').
  - Calling accrue_welcome_bonus a second time (replay) leaves the ledger at one
    welcome row and writes NO additional loyalty_accrued audit row (idempotency —
    T-82-07 partial-UNIQUE guard on uq_loyalty_ledger_welcome).

Harness: SAVEPOINT db_session + ASGITransport async_client (not real network).
Staff auth: POST /api/v1/auth/login with seeded owner user.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit_models import AuditLog
from app.core.database import get_db
from app.core.permissions import Role
from app.core.redis import get_redis
from app.core.security import hash_password
from app.modules.auth.models import User
from app.modules.loyalty.service import accrue_welcome_bonus

pytestmark = pytest.mark.asyncio

_OWNER_EMAIL = "loyalty-accrual-owner@example.com"
_OWNER_PASSWORD = "loyalty-test-pw-accrual-123"  # noqa: S105


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
async def http_client(_overridden_app: FastAPI) -> AsyncIterator[AsyncClient]:
    """ASGITransport client that persists cookies across requests."""
    transport = ASGITransport(app=_overridden_app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as c:
        yield c


@pytest_asyncio.fixture(autouse=True)
async def flush_redis(app: FastAPI) -> None:
    """Flush Redis before each test to clear rate-limit counters and session keys."""
    await app.state.redis.flushdb()


@pytest_asyncio.fixture
async def seeded_owner(db_session: AsyncSession) -> User:
    """Insert an owner user for staff auth."""
    user = User(
        email=_OWNER_EMAIL,
        password_hash=await hash_password(_OWNER_PASSWORD),
        role=Role.OWNER,
        full_name="Loyalty Accrual Test Owner",
    )
    db_session.add(user)
    await db_session.commit()
    return user


# ---------------------------------------------------------------------------
# Helper: login as staff owner
# ---------------------------------------------------------------------------


async def _login_owner(http_client: AsyncClient) -> None:
    r = await http_client.post(
        "/api/v1/auth/login",
        json={"email": _OWNER_EMAIL, "password": _OWNER_PASSWORD},
    )
    assert r.status_code == 200, f"Owner login failed: {r.text}"


def _csrf_headers(client: AsyncClient) -> dict[str, str]:
    return {"X-CSRF-Token": client.cookies.get("clubcore_csrf", "")}


# ---------------------------------------------------------------------------
# Helper: create client via API
# ---------------------------------------------------------------------------


async def _create_client(http_client: AsyncClient, phone: str) -> dict[str, Any]:
    r = await http_client.post(
        "/api/v1/clients",
        json={"lastName": "Лояльность", "firstName": "Тест", "phone": phone},
        headers=_csrf_headers(http_client),
    )
    assert r.status_code == 201, f"Client creation failed: {r.text}"
    data: dict[str, Any] = r.json()["data"]
    return data


# ---------------------------------------------------------------------------
# Behavior tests
# ---------------------------------------------------------------------------


async def test_create_client_produces_one_welcome_ledger_row(
    http_client: AsyncClient,
    db_session: AsyncSession,
    seeded_owner: User,
) -> None:
    """Creating a client via the API produces exactly 1 welcome row of 50000 kopecks."""
    await _login_owner(http_client)
    client_data = await _create_client(http_client, "+79150001101")
    client_id = UUID(client_data["id"])

    # Assert exactly 1 welcome ledger row with correct amount.
    row = (
        await db_session.execute(
            text(
                "SELECT COUNT(*) AS cnt, "
                "MAX(amount_kopecks) AS amount, "
                "MAX(entry_type) AS etype "
                "FROM loyalty_ledger "
                "WHERE client_id = :cid AND entry_type = 'welcome'"
            ),
            {"cid": str(client_id)},
        )
    ).mappings().one()
    assert int(row["cnt"]) == 1, f"Expected 1 welcome row, got {row['cnt']}"
    assert int(row["amount"]) == 50_000, f"Expected 50000 kopecks, got {row['amount']}"
    assert row["etype"] == "welcome"


async def test_create_client_produces_one_loyalty_accrued_audit_row(
    http_client: AsyncClient,
    db_session: AsyncSession,
    seeded_owner: User,
) -> None:
    """Creating a client produces exactly 1 loyalty_accrued audit row (entry_type=welcome)."""
    await _login_owner(http_client)
    client_data = await _create_client(http_client, "+79150001102")
    client_id = UUID(client_data["id"])

    # Assert exactly 1 loyalty_accrued audit row with correct payload fields.
    audit_rows = (
        await db_session.scalars(
            select(AuditLog).where(
                AuditLog.action == "loyalty_accrued",
                AuditLog.resource_type == "loyalty",
            )
        )
    ).all()

    # Filter to this specific client (payload.client_id)
    client_audits = [
        r for r in audit_rows if r.payload.get("client_id") == str(client_id)
    ]
    assert len(client_audits) == 1, (
        f"Expected 1 loyalty_accrued audit row for client {client_id}, "
        f"got {len(client_audits)}"
    )
    payload = client_audits[0].payload
    assert payload["entry_type"] == "welcome"
    assert payload["actor"] == "welcome"
    assert payload["amount_kopecks"] == 50_000


async def test_welcome_accrual_idempotent_replay_no_extra_ledger_row(
    http_client: AsyncClient,
    db_session: AsyncSession,
    seeded_owner: User,
) -> None:
    """Replay of accrue_welcome_bonus: ledger stays at 1 row, no extra audit row."""
    await _login_owner(http_client)
    client_data = await _create_client(http_client, "+79150001103")
    client_id = UUID(client_data["id"])

    # Call the service directly a second time (replay).
    # The partial UNIQUE on uq_loyalty_ledger_welcome prevents double-credit.
    await accrue_welcome_bonus(db_session, client_id=client_id)
    await db_session.flush()

    # Still exactly 1 ledger row.
    count_row = (
        await db_session.execute(
            text(
                "SELECT COUNT(*) AS cnt FROM loyalty_ledger "
                "WHERE client_id = :cid AND entry_type = 'welcome'"
            ),
            {"cid": str(client_id)},
        )
    ).mappings().one()
    assert int(count_row["cnt"]) == 1, (
        f"Idempotency broken: expected 1 welcome row after replay, got {count_row['cnt']}"
    )

    # Still exactly 1 audit row (replay emits nothing).
    audit_rows = (
        await db_session.scalars(
            select(AuditLog).where(
                AuditLog.action == "loyalty_accrued",
                AuditLog.resource_type == "loyalty",
            )
        )
    ).all()
    client_audits = [
        r for r in audit_rows if r.payload.get("client_id") == str(client_id)
    ]
    assert len(client_audits) == 1, (
        f"Idempotency broken: expected 1 audit row after replay, "
        f"got {len(client_audits)} (replay should not emit)"
    )
