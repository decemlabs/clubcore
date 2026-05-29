"""Phase 26 MEM-REN-TEST-02 — snapshot uses CURRENT plan price after PATCH.

Locks the canonical PROJECT.md decision: "Snapshot pricing на renewal — берём
текущую цену плана. Если plan подорожал между sale и renewal — клиент платит
новую цену". Without this lock, owners would not be able to apply price
changes without cancelling all existing memberships first.

The contract:
  - source.price_kopecks_snapshot is captured at sale time and is IMMUTABLE;
  - renewal new.price_kopecks_snapshot is captured from the CURRENT plan
    (post-PATCH value), NOT from source's stale snapshot;
  - audit payload `current_price_kopecks` mirrors the same CURRENT value, so
    forensic SQL `SUM(payload->>'current_price_kopecks')` answers the
    "renewal revenue per period" question correctly.

Analog: tests/integration/memberships/test_memberships_audit.py (audit payload
assertions) + tests/integration/memberships/test_plans_crud.py (PATCH plan
price flow).
"""

from __future__ import annotations

from typing import Any
from uuid import UUID, uuid4

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit_models import AuditLog


def _csrf_headers(client: AsyncClient) -> dict[str, str]:
    # Phase 66 IDM-07: renew_membership now requires Idempotency-Key.
    return {
        "X-CSRF-Token": client.cookies.get("clubcore_csrf") or "",
        "Idempotency-Key": uuid4().hex,
    }


VALID_CLIENT: dict[str, Any] = {
    "lastName": "Иванов",
    "firstName": "Иван",
    "phone": "+79991239020",
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


async def test_renewal_uses_current_plan_price_after_patch(
    authed_client_owner: AsyncClient,
    db_session: AsyncSession,
    make_plan: Any,
    make_membership: Any,
) -> None:
    """MEM-REN-TEST-02: PATCH plan price 200_000 → 300_000 → renewal snapshots 300_000.

    The owner-only PATCH is exercised through direct ORM mutation (an HTTP
    PATCH would round-trip through the plans router but the production code
    path under test here is the renewal snapshot — `service.renew_membership`
    reads the PLAN row, not the source membership's snapshot fields).

    The strict assertions:
      1. After PATCH, plan.price_kopecks == 300_000.
      2. POST /renew → 201; response.priceKopecksSnapshot == 300_000.
      3. Audit payload current_price_kopecks == 300_000.
      4. Source row's price_kopecks_snapshot remains 200_000 (immutable).
    """
    plan = await make_plan(
        name="MEM-REN-TEST-02 plan",
        duration_days=30,
        price_kopecks=200_000,
        freeze_days_limit=14,
    )
    client = await _create_client(authed_client_owner, phone="+79991239020")
    client_uuid = UUID(client["id"])
    source = await make_membership(client_id=client_uuid, plan=plan, status="active")
    assert source.price_kopecks_snapshot == 200_000  # sale-time snapshot

    # Owner mutates plan price between sale and renewal.
    plan.price_kopecks = 300_000
    await db_session.commit()
    await db_session.refresh(plan)
    assert plan.price_kopecks == 300_000

    r = await authed_client_owner.post(
        f"/api/v1/memberships/{source.id}/renew",
        headers=_csrf_headers(authed_client_owner),
    )
    assert r.status_code == 201, r.text
    body: dict[str, Any] = r.json()["data"]

    # CURRENT plan price wins (NOT source's stale snapshot).
    assert body["priceKopecksSnapshot"] == 300_000

    # Audit payload mirrors the same CURRENT value — forensic SQL contract.
    audit_row = await db_session.scalar(
        select(AuditLog).where(
            AuditLog.action == "membership_renewed",
            AuditLog.resource_id == UUID(body["id"]),
        )
    )
    assert audit_row is not None
    assert audit_row.payload["current_price_kopecks"] == 300_000

    # Source's snapshot is immutable — sale-time pricing preserved.
    await db_session.refresh(source)
    assert source.price_kopecks_snapshot == 200_000
