"""Integration test for the full freeze cycle (MEM-FRZ-TEST-01).

Sell membership (30 days) → freeze (open period) → simulate elapsed 5 days
by mutating started_at directly via db_session → unfreeze → assert
end_date += 5, freezeDaysUsed == 5, freezeDaysRemaining == 9, audit pair
emitted.

Avoids freezegun (Phase 24 D-24-06 precedent) — uses direct started_at
mutation on the freeze period row (db_session-scope) to deterministically
test the unfreeze-day math without monkeypatching the system clock.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit_models import AuditLog
from app.modules.memberships.models import MembershipFreezePeriod


def _csrf_headers(client: AsyncClient) -> dict[str, str]:
    return {"X-CSRF-Token": client.cookies.get("sportzal_csrf") or ""}


VALID_CLIENT: dict[str, Any] = {
    "lastName": "Иванов",
    "firstName": "Иван",
    "phone": "+79991234050",
}


async def _create_client(authed: AsyncClient, **overrides: Any) -> dict[str, Any]:
    payload = {**VALID_CLIENT, **overrides}
    r = await authed.post(
        "/api/v1/clients",
        json=payload,
        headers=_csrf_headers(authed),
    )
    assert r.status_code == 201, r.text
    data: dict[str, Any] = r.json()["data"]
    return data


async def test_freeze_cycle_extends_end_date_by_used_days(
    authed_client_reception: AsyncClient,
    authed_client_owner: AsyncClient,
    db_session: AsyncSession,
    make_plan: Any,
    make_membership: Any,
) -> None:
    """MEM-FRZ-TEST-01: sell 30d → freeze 5d → unfreeze → end_date += 5.

    Steps:
      1. Seed plan (freeze_days_limit=14) + client + active membership.
      2. POST /freeze with reception → 200, status=frozen,
         currentFreezePeriod populated.
      3. Mutate the open period's started_at to (now - 5 days) via
         db_session (avoids freezegun; deterministic ceil math).
      4. POST /unfreeze → 200, status=active, freezeDaysUsed=5,
         freezeDaysRemaining=9.
      5. Assert: response end_date == original_end_date + 5 days.
      6. Assert: 1 membership_frozen + 1 membership_unfrozen audit row,
         with days_added=5 in the unfreeze payload.
    """
    plan = await make_plan(name="Cycle Plan", duration_days=30, freeze_days_limit=14)
    client = await _create_client(authed_client_reception, phone="+79991234050")
    client_uuid = UUID(client["id"])
    membership = await make_membership(client_id=client_uuid, plan=plan, status="active")
    original_end_date = membership.end_date
    membership_id = membership.id

    # Step 2: Freeze
    r = await authed_client_reception.post(
        f"/api/v1/memberships/{membership_id}/freeze",
        headers=_csrf_headers(authed_client_reception),
    )
    assert r.status_code == 200, r.text
    body = r.json()["data"]
    assert body["status"] == "frozen"
    assert body["currentFreezePeriod"] is not None
    # Ongoing period — SQL CEIL returns 0 for ~0 seconds elapsed (Python's
    # max(1, ...) clamp only fires on unfreeze for the days_added audit
    # value). The user-facing display starts at 0 and ticks up.
    assert body["freezeDaysUsed"] == 0
    assert body["freezeDaysLimitSnapshot"] == 14

    # Step 3: Mutate started_at to simulate ~5 elapsed days (avoids freezegun).
    # Set to (now - 5 days + small buffer) so the unfreeze's now() - started_at
    # reads slightly LESS than 5 days (allowing for clock advance during the
    # subsequent HTTP roundtrip), yielding ceil = 5. Without the buffer, the
    # now-advance during unfreeze would push delta over 5d → ceil = 6.
    period_id = UUID(body["currentFreezePeriod"]["id"])
    period = await db_session.get(MembershipFreezePeriod, period_id)
    assert period is not None
    period.started_at = datetime.now(tz=UTC) - timedelta(days=5) + timedelta(seconds=30)
    await db_session.flush()
    await db_session.commit()

    # Step 4: Unfreeze
    r = await authed_client_reception.post(
        f"/api/v1/memberships/{membership_id}/unfreeze",
        headers=_csrf_headers(authed_client_reception),
    )
    assert r.status_code == 200, r.text
    body = r.json()["data"]
    assert body["status"] == "active"
    assert body["currentFreezePeriod"] is None
    assert body["freezeDaysUsed"] == 5
    assert body["freezeDaysRemaining"] == 9
    assert body["freezeDaysLimitSnapshot"] == 14

    # Step 5: end_date extended by 5 days
    new_end_date = body["endDate"]
    expected = (original_end_date + timedelta(days=5)).isoformat()
    assert new_end_date == expected, f"Expected end_date {expected}, got {new_end_date}"

    # Step 6: Audit pair emitted (membership_frozen + membership_unfrozen, days_added=5)
    frozen_rows = (
        await db_session.scalars(
            select(AuditLog).where(
                AuditLog.action == "membership_frozen",
                AuditLog.resource_id == membership_id,
            )
        )
    ).all()
    assert len(frozen_rows) == 1
    assert frozen_rows[0].payload["client_id"] == str(client_uuid)
    assert frozen_rows[0].payload["freeze_period_id"] == str(period_id)

    unfrozen_rows = (
        await db_session.scalars(
            select(AuditLog).where(
                AuditLog.action == "membership_unfrozen",
                AuditLog.resource_id == membership_id,
            )
        )
    ).all()
    assert len(unfrozen_rows) == 1
    assert unfrozen_rows[0].payload["client_id"] == str(client_uuid)
    assert unfrozen_rows[0].payload["freeze_period_id"] == str(period_id)
    assert unfrozen_rows[0].payload["days_added"] == 5
