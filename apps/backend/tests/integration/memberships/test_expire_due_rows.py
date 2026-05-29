"""Integration tests for `repository.expire_due_rows` (Phase 18 Plan 18-01, ARQ-02).

Tests the bulk UPDATE…RETURNING(id, client_id) helper directly against the
SAVEPOINT-mode db_session. The helper issues a single statement, returns the
affected rows, and DOES NOT commit/flush.

Behaviours covered (per 18-01-PLAN.md Task 1 <behavior>):
  1. Active row with `end_date < today` is flipped + returned with (id, client_id).
  2. Idempotent: a second call with the same `today` returns 0 rows (status now 'expired').
  3. Status filter: `status='cancelled'` rows with `end_date < today` are NOT touched.
  4. Inclusive end_date invariant: a row with `end_date == today` is NOT in the result
     (strict `<` filter; row stays active until tomorrow's run).
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any
from uuid import UUID

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.memberships import repository
from app.modules.memberships.models import Membership

VALID_CLIENT: dict[str, Any] = {
    "lastName": "Иванов",
    "firstName": "Иван",
    "phone": "+79991234567",
}


def _csrf_headers(client: AsyncClient) -> dict[str, str]:
    return {"X-CSRF-Token": client.cookies.get("clubcore_csrf") or ""}


async def _create_client(authed: AsyncClient, **overrides: Any) -> UUID:
    payload: dict[str, Any] = {**VALID_CLIENT, **overrides}
    r = await authed.post(
        "/api/v1/clients",
        json=payload,
        headers=_csrf_headers(authed),
    )
    assert r.status_code == 201, r.text
    return UUID(r.json()["data"]["id"])


async def test_expire_due_rows_flips_active_row_with_past_end_date(
    authed_client_owner: AsyncClient,
    db_session: AsyncSession,
    make_plan: Any,
    make_membership: Any,
) -> None:
    """Active row with end_date < today is returned with (id, client_id) and flipped."""
    today = date(2026, 6, 1)
    plan = await make_plan(name="Bulk Expire 1")

    cid_due = await _create_client(authed_client_owner, phone="+79991810001")
    cid_today = await _create_client(authed_client_owner, phone="+79991810002")
    cid_future = await _create_client(authed_client_owner, phone="+79991810003")

    m_due = await make_membership(
        client_id=cid_due,
        plan=plan,
        status="active",
        start_date=today - timedelta(days=10),
        end_date=today - timedelta(days=1),  # yesterday — due
    )
    await make_membership(
        client_id=cid_today,
        plan=plan,
        status="active",
        start_date=today - timedelta(days=10),
        end_date=today,  # today — inclusive, NOT due
    )
    await make_membership(
        client_id=cid_future,
        plan=plan,
        status="active",
        start_date=today,
        end_date=today + timedelta(days=10),  # future — NOT due
    )

    rows = await repository.expire_due_rows(db_session, today)

    assert len(rows) == 1
    (membership_id, client_id) = rows[0]
    assert membership_id == m_due.id
    assert client_id == cid_due

    # Flip is observable in the same transaction.
    refreshed = (
        await db_session.execute(select(Membership).where(Membership.id == m_due.id))
    ).scalar_one()
    assert refreshed.status == "expired"


async def test_expire_due_rows_is_idempotent(
    authed_client_owner: AsyncClient,
    db_session: AsyncSession,
    make_plan: Any,
    make_membership: Any,
) -> None:
    """Second call with the same `today` returns 0 rows (status filter is the gate)."""
    today = date(2026, 6, 1)
    plan = await make_plan(name="Bulk Expire 2")
    cid = await _create_client(authed_client_owner, phone="+79991810004")
    await make_membership(
        client_id=cid,
        plan=plan,
        status="active",
        start_date=today - timedelta(days=10),
        end_date=today - timedelta(days=1),
    )

    first = await repository.expire_due_rows(db_session, today)
    assert len(first) == 1

    second = await repository.expire_due_rows(db_session, today)
    assert len(second) == 0


async def test_expire_due_rows_skips_cancelled_rows(
    authed_client_owner: AsyncClient,
    db_session: AsyncSession,
    make_plan: Any,
    make_membership: Any,
) -> None:
    """Rows with status='cancelled' and end_date < today are NOT touched."""
    today = date(2026, 6, 1)
    plan = await make_plan(name="Bulk Expire 3")
    cid = await _create_client(authed_client_owner, phone="+79991810005")
    m_cancelled = await make_membership(
        client_id=cid,
        plan=plan,
        status="cancelled",
        start_date=today - timedelta(days=10),
        end_date=today - timedelta(days=1),
    )

    rows = await repository.expire_due_rows(db_session, today)
    assert len(rows) == 0

    refreshed = (
        await db_session.execute(select(Membership).where(Membership.id == m_cancelled.id))
    ).scalar_one()
    assert refreshed.status == "cancelled"


async def test_expire_due_rows_inclusive_end_date_today_stays_active(
    authed_client_owner: AsyncClient,
    db_session: AsyncSession,
    make_plan: Any,
    make_membership: Any,
) -> None:
    """A row with end_date == today is NOT in the result (strict `<` filter)."""
    today = date(2026, 6, 1)
    plan = await make_plan(name="Bulk Expire 4")
    cid = await _create_client(authed_client_owner, phone="+79991810006")
    m_today = await make_membership(
        client_id=cid,
        plan=plan,
        status="active",
        start_date=today - timedelta(days=10),
        end_date=today,  # exactly today — last valid day
    )

    rows = await repository.expire_due_rows(db_session, today)
    assert len(rows) == 0

    refreshed = (
        await db_session.execute(select(Membership).where(Membership.id == m_today.id))
    ).scalar_one()
    assert refreshed.status == "active"


def test_expire_due_rows_helper_does_not_commit_or_flush() -> None:
    """Static check: the helper body MUST NOT call session.commit / session.flush.

    The worker entry (Plan 18-02) owns the transaction (Phase 18 D-01).
    This test guards the contract at the source-text level.
    """
    from pathlib import Path

    src = Path(repository.__file__).read_text(encoding="utf-8")
    # locate the helper function body
    marker = "async def expire_due_rows("
    assert marker in src, "expire_due_rows is not defined in repository.py"
    start = src.index(marker)
    # crude but sufficient — assert no commit/flush appears anywhere AFTER this
    # marker until end-of-file (the helper is the last addition).
    tail = src[start:]
    # carve only the function body (everything until the next top-level "async def" or EOF)
    next_def = tail.find("\nasync def ", len(marker))
    body = tail if next_def == -1 else tail[:next_def]
    assert "session.commit" not in body, (
        "expire_due_rows must NOT call session.commit (caller-owns-txn per D-01)"
    )
    assert "session.flush" not in body, (
        "expire_due_rows must NOT call session.flush (caller-owns-txn per D-01)"
    )
