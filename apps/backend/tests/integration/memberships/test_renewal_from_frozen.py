"""Phase 26 — cross-flow basic happy path: freeze → renew (frozen ≠ expired).

Pins the contract that a frozen source is renewable WITHOUT collapsing to the
"expired" date strategy. The boundary:

  - source.status == 'frozen' → start_date = source.end_date + 1 day
    (NOT today; D-26-10 — frozen ≠ expired);
  - source row remains status='frozen' (D-26-24 — renewal is INSERT, not
    transition; freeze period stays open);
  - audit payload start_date_strategy='from_source_end_date'.

Resolver / check-in interaction during the freeze window is part of the
Phase 29 cross-phase sweep (D-25-deferred / D-26-29 last entry); Phase 26
only locks the basic renewal-from-frozen happy path here.

Analog: tests/integration/memberships/test_cancel_during_freeze.py +
test_freeze_cycle.py.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit_models import AuditLog


def _csrf_headers(client: AsyncClient) -> dict[str, str]:
    # Phase 66 IDM-07: renew_membership now requires Idempotency-Key.
    return {
        "X-CSRF-Token": client.cookies.get("sportzal_csrf") or "",
        "Idempotency-Key": uuid4().hex,
    }


VALID_CLIENT: dict[str, Any] = {
    "lastName": "Иванов",
    "firstName": "Иван",
    "phone": "+79991239050",
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


async def test_renew_frozen_source_uses_source_end_date(
    authed_client_reception: AsyncClient,
    db_session: AsyncSession,
    make_plan: Any,
    make_membership: Any,
) -> None:
    """Frozen source → renewal start_date = source.end_date + 1; source stays frozen.

    Flow:
      1. Seed an active membership with deterministic dates.
      2. POST /freeze (Phase 25 endpoint) → status flips to 'frozen' on source.
      3. POST /renew → 201; new row uses source.end_date + 1 day; audit
         strategy is from_source_end_date; source row remains 'frozen'.
    """
    plan = await make_plan(
        name="Frozen renewal plan",
        duration_days=30,
        price_kopecks=200_000,
        freeze_days_limit=14,
    )
    client = await _create_client(authed_client_reception, phone="+79991239050")
    client_uuid = UUID(client["id"])
    today = datetime.now(tz=UTC).date()
    source = await make_membership(
        client_id=client_uuid,
        plan=plan,
        status="active",
        start_date=today,
        end_date=today + timedelta(days=29),
    )
    expected_renewal_start = (source.end_date + timedelta(days=1)).isoformat()

    # 1: freeze the source (Phase 25 endpoint — emits its own audit row).
    r_freeze = await authed_client_reception.post(
        f"/api/v1/memberships/{source.id}/freeze",
        headers=_csrf_headers(authed_client_reception),
    )
    assert r_freeze.status_code == 200, r_freeze.text
    assert r_freeze.json()["data"]["status"] == "frozen"

    # 2: renew the frozen source.
    r_renew = await authed_client_reception.post(
        f"/api/v1/memberships/{source.id}/renew",
        headers=_csrf_headers(authed_client_reception),
    )
    assert r_renew.status_code == 201, r_renew.text
    body: dict[str, Any] = r_renew.json()["data"]

    # New row starts the day AFTER source.end_date (NOT today; D-26-10).
    assert body["startDate"] == expected_renewal_start

    # Audit payload: from_source_end_date branch.
    audit_row = await db_session.scalar(
        select(AuditLog).where(
            AuditLog.action == "membership_renewed",
            AuditLog.resource_id == UUID(body["id"]),
        )
    )
    assert audit_row is not None
    assert audit_row.payload["start_date_strategy"] == "from_source_end_date"

    # Source row remains 'frozen' — renewal is INSERT, not transition (D-26-24).
    await db_session.refresh(source)
    assert source.status == "frozen"
