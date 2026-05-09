"""Phase 26 MEM-REN-TEST-01 — active-source renewal happy path.

Locks the canonical happy-path renewal flow on an `active` source membership:

  - response 201 + envelope shape (camelCase wire format including
    `previousMembershipId` + freeze projection baseline);
  - new row's `start_date == source.end_date + 1 day`;
  - new row's `end_date == new.start_date + plan.duration_days - 1`
    (INCLUSIVE end-date semantic per PROJECT.md);
  - snapshots equal CURRENT plan fields (price/duration/freeze_limit);
  - `status='active'`;
  - source row remains untouched (`status='active'`, snapshots unchanged);
  - audit row `event='membership_renewed'` (column `action` per Phase 26 D-26-Audit)
    payload contains `start_date_strategy='from_source_end_date'`,
    `current_price_kopecks=plan.price_kopecks`, `source_membership_id`,
    `source_plan_id`, `client_id`.

Also pins the role-parity invariant (D-26-20): both reception and owner POST
return 201 — `(CREATE, MEMBERSHIPS)` is NOT in OWNER_ONLY.

Analog: tests/integration/memberships/test_freeze_cycle.py + test_memberships_audit.py.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from typing import Any
from uuid import UUID

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit_models import AuditLog
from app.modules.memberships.models import Membership


def _csrf_headers(client: AsyncClient) -> dict[str, str]:
    return {"X-CSRF-Token": client.cookies.get("sportzal_csrf") or ""}


VALID_CLIENT: dict[str, Any] = {
    "lastName": "Иванов",
    "firstName": "Иван",
    "phone": "+79991239010",
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


async def test_renew_active_source_creates_chained_row(
    authed_client_owner: AsyncClient,
    db_session: AsyncSession,
    make_plan: Any,
    make_membership: Any,
) -> None:
    """MEM-REN-TEST-01: active source → 201 + chained row + audit payload.

    Deterministic dates: source has start=2026-05-01, end=2026-05-30, so the
    renewal row MUST have start=2026-05-31 (source.end_date + 1 day) and
    end=2026-06-29 (start + 29 = duration_days - 1, INCLUSIVE).
    """
    plan = await make_plan(
        name="MEM-REN-TEST-01 plan",
        duration_days=30,
        price_kopecks=200_000,
        freeze_days_limit=14,
    )
    client = await _create_client(authed_client_owner, phone="+79991239010")
    client_uuid = UUID(client["id"])
    source = await make_membership(
        client_id=client_uuid,
        plan=plan,
        status="active",
        start_date=date(2026, 5, 1),
        end_date=date(2026, 5, 30),
    )

    r = await authed_client_owner.post(
        f"/api/v1/memberships/{source.id}/renew",
        headers=_csrf_headers(authed_client_owner),
    )
    assert r.status_code == 201, r.text
    body: dict[str, Any] = r.json()["data"]

    # --- Response envelope shape -------------------------------------------
    assert body["previousMembershipId"] == str(source.id)
    assert body["startDate"] == "2026-05-31"  # source.end_date + 1 day
    assert body["endDate"] == "2026-06-29"  # start + (duration_days - 1)
    assert body["priceKopecksSnapshot"] == 200_000
    assert body["durationDaysSnapshot"] == 30
    assert body["freezeDaysLimitSnapshot"] == 14
    assert body["status"] == "active"
    # Baseline freeze projection on a brand-new row.
    assert body["freezeDaysUsed"] == 0
    assert body["currentFreezePeriod"] is None
    assert body["freezeDaysRemaining"] == 14

    new_id = UUID(body["id"])

    # --- Source row stays untouched (renewal is INSERT, not transition; D-26-24)
    await db_session.refresh(source)
    assert source.status == "active"
    assert source.end_date == date(2026, 5, 30)
    assert source.price_kopecks_snapshot == 200_000

    # --- DB row is chained --------------------------------------------------
    new_row = await db_session.scalar(select(Membership).where(Membership.id == new_id))
    assert new_row is not None
    assert new_row.previous_membership_id == source.id
    assert new_row.client_id == source.client_id
    assert new_row.status == "active"

    # --- Audit row payload contract (D-26-15) ------------------------------
    audit_row = await db_session.scalar(
        select(AuditLog).where(
            AuditLog.action == "membership_renewed",
            AuditLog.resource_id == new_id,
        )
    )
    assert audit_row is not None
    payload: dict[str, Any] = audit_row.payload
    assert payload["start_date_strategy"] == "from_source_end_date"
    assert payload["source_membership_id"] == str(source.id)
    assert payload["source_plan_id"] == str(source.plan_id)
    assert payload["client_id"] == str(source.client_id)
    assert payload["current_price_kopecks"] == 200_000


async def test_renew_active_returns_201_for_both_roles(
    authed_client_owner: AsyncClient,
    authed_client_reception: AsyncClient,
    db_session: AsyncSession,
    make_plan: Any,
    make_membership: Any,
) -> None:
    """Both reception and owner can renew — (CREATE, MEMBERSHIPS) ∉ OWNER_ONLY.

    Issuing two POSTs against the same source produces two follow-up rows; the
    chain stacks (D-26-06 — multi-hop chains allowed). This pins the role
    parity AND the absence of single-renewal-per-source enforcement (no such
    constraint in v1.3 scope).
    """
    plan = await make_plan(
        name="Role parity plan",
        duration_days=30,
        price_kopecks=150_000,
        freeze_days_limit=10,
    )
    client = await _create_client(authed_client_owner, phone="+79991239011")
    client_uuid = UUID(client["id"])
    today = datetime.now(tz=UTC).date()
    source = await make_membership(
        client_id=client_uuid,
        plan=plan,
        status="active",
        start_date=today,
        end_date=today + timedelta(days=29),
    )

    r_reception = await authed_client_reception.post(
        f"/api/v1/memberships/{source.id}/renew",
        headers=_csrf_headers(authed_client_reception),
    )
    assert r_reception.status_code == 201, r_reception.text

    r_owner = await authed_client_owner.post(
        f"/api/v1/memberships/{source.id}/renew",
        headers=_csrf_headers(authed_client_owner),
    )
    assert r_owner.status_code == 201, r_owner.text

    # Two distinct renewal rows now exist for the same source.
    rows = (
        await db_session.scalars(
            select(Membership).where(Membership.previous_membership_id == source.id)
        )
    ).all()
    assert len(rows) == 2
