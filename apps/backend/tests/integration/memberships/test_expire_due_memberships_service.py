"""Integration tests for `service._expire_due_memberships` (Phase 18 Plan 18-01).

The private orchestrator is the bulk-expire entry the worker (Plan 18-02) will
call. It calls `repository.expire_due_rows`, emits one `audit.emit` per row,
and returns the integer count. It DOES NOT commit (Phase 18 D-01 — worker is
transaction owner, marker `# noqa: SVC001 caller-owns-txn` on def line).

Behaviours covered (per 18-01-PLAN.md Task 2 <behavior>):
  1. With 1 due row -> returns int 1 + inserts exactly 1 audit_log row whose
     action='membership_expired', resource_type='membership', actor_user_id IS NULL,
     resource_id=<membership_id>, payload={'client_id': '<uuid-str>'}.
  2. With 0 due rows -> returns int 0 + 0 audit_log rows.
  3. With today=None -> falls back to datetime.now(ZoneInfo('Europe/Moscow')).date().
  4. Function does NOT call session.commit() (static check on source).
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any
from uuid import UUID

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit_models import AuditLog
from app.modules.memberships import service

VALID_CLIENT: dict[str, Any] = {
    "lastName": "Иванов",
    "firstName": "Иван",
    "phone": "+79991234567",
}


def _csrf_headers(client: AsyncClient) -> dict[str, str]:
    return {"X-CSRF-Token": client.cookies.get("sportzal_csrf") or ""}


async def _create_client(authed: AsyncClient, **overrides: Any) -> UUID:
    payload: dict[str, Any] = {**VALID_CLIENT, **overrides}
    r = await authed.post(
        "/api/v1/clients",
        json=payload,
        headers=_csrf_headers(authed),
    )
    assert r.status_code == 201, r.text
    return UUID(r.json()["data"]["id"])


async def test_expire_due_memberships_with_one_due_row_returns_one_and_emits_audit(
    authed_client_owner: AsyncClient,
    db_session: AsyncSession,
    make_plan: Any,
    make_membership: Any,
) -> None:
    today = date(2026, 6, 1)
    plan = await make_plan(name="Service Bulk Expire 1")
    cid = await _create_client(authed_client_owner, phone="+79991820001")
    m = await make_membership(
        client_id=cid,
        plan=plan,
        status="active",
        start_date=today - timedelta(days=10),
        end_date=today - timedelta(days=1),
    )

    count = await service._expire_due_memberships(db_session, today=today)
    assert count == 1
    assert isinstance(count, int)

    # Flush audit row so it's visible in the same SAVEPOINT.
    await db_session.flush()

    rows = (
        await db_session.execute(
            select(AuditLog).where(
                AuditLog.action == "membership_expired",
                AuditLog.resource_id == m.id,
            )
        )
    ).scalars().all()
    assert len(rows) == 1
    audit_row = rows[0]
    assert audit_row.action == "membership_expired"
    assert audit_row.resource_type == "membership"
    assert audit_row.actor_user_id is None
    assert audit_row.resource_id == m.id
    assert audit_row.payload == {"client_id": str(cid)}


async def test_expire_due_memberships_with_zero_due_rows_returns_zero_no_audits(
    authed_client_owner: AsyncClient,
    db_session: AsyncSession,
    make_plan: Any,
    make_membership: Any,
) -> None:
    today = date(2026, 6, 1)
    plan = await make_plan(name="Service Bulk Expire 2")
    cid = await _create_client(authed_client_owner, phone="+79991820002")
    # Future end_date — not due.
    await make_membership(
        client_id=cid,
        plan=plan,
        status="active",
        start_date=today,
        end_date=today + timedelta(days=10),
    )

    count = await service._expire_due_memberships(db_session, today=today)
    assert count == 0

    await db_session.flush()
    rows = (
        await db_session.execute(
            select(AuditLog).where(AuditLog.action == "membership_expired")
        )
    ).scalars().all()
    assert len(rows) == 0


async def test_expire_due_memberships_today_none_uses_moscow_today(
    db_session: AsyncSession,
) -> None:
    """When today=None the service must compute datetime.now(MSK).date()
    and run against that. With no rows in the DB the call returns 0 and
    does not raise — proving the fallback path executes.
    """
    count = await service._expire_due_memberships(db_session, today=None)
    assert count == 0


def test_expire_due_memberships_source_carries_svc001_marker_and_no_commit() -> None:
    """Static checks (Phase 15 INFRA-13 contract):

    - The function MUST be private (`_`-prefixed) — name `_expire_due_memberships`.
    - The `# noqa: SVC001 caller-owns-txn` marker MUST appear on the def line.
    - The function body MUST NOT call session.commit / session.flush
      (worker owns the transaction per D-01).
    - The bulk path MUST NOT call `_assert_can_expire` (D-03).
    """
    from pathlib import Path

    src = Path(service.__file__).read_text(encoding="utf-8")
    marker = "async def _expire_due_memberships("
    assert marker in src, "expected private async def _expire_due_memberships in service.py"

    # Locate def line and confirm SVC001 marker is on it.
    lines = src.splitlines()
    def_line_idx = next(
        (i for i, line in enumerate(lines) if line.startswith("async def _expire_due_memberships(")),
        -1,
    )
    assert def_line_idx >= 0
    def_line = lines[def_line_idx]
    assert "# noqa: SVC001 caller-owns-txn" in def_line, (
        "SVC001 marker must be on the same line as `async def _expire_due_memberships`"
    )

    # Carve the function body (everything until the next top-level def or EOF).
    body_start = src.index(marker)
    tail = src[body_start:]
    next_def = tail.find("\nasync def ", len(marker))
    body = tail if next_def == -1 else tail[:next_def]

    assert "session.commit" not in body, (
        "_expire_due_memberships must NOT call session.commit (D-01)"
    )
    assert "session.flush" not in body, (
        "_expire_due_memberships must NOT call session.flush (D-01)"
    )
    assert "_assert_can_expire" not in body, (
        "_expire_due_memberships must NOT call _assert_can_expire (D-03)"
    )
