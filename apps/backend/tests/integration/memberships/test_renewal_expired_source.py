"""Phase 26 MEM-REN-TEST-04 — expired source renewal starts TODAY (Europe/Moscow).

The lock against retroactive renewals (D-26-12): if source expired weeks ago,
`source.end_date + 1` would yield a renewal whose `end_date < today` — the
client would pay for a membership that is instantly expired. UX-anti-pattern.
For an expired source, the renewal `start_date` MUST equal today (Europe/Moscow)
and `end_date == today + plan.duration_days - 1` so the client always gets the
full duration_days from the moment of purchase.

The audit payload `start_date_strategy` literal switches between branches:
  - source.status in ('active', 'frozen') → 'from_source_end_date'
  - source.status == 'expired'            → 'from_today_expired_source'

Per Phase 24 D-24-06 / Phase 25 D-25-24 / D-26-30: avoid `freezegun`. Use real
wall-clock `datetime.now(ZoneInfo("Europe/Moscow")).date()`. The MSK comparison
is captured immediately before the POST and compared against the response —
midnight-MSK race is theoretically possible but practically irrelevant inside a
sub-second test (and the assertion would still surface the bug as a date
mismatch rather than a silent regression).
"""

from __future__ import annotations

from datetime import datetime as _datetime
from datetime import timedelta
from typing import Any
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

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
    "phone": "+79991239040",
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


async def test_renew_expired_source_starts_today(
    authed_client_reception: AsyncClient,
    db_session: AsyncSession,
    make_plan: Any,
    make_membership: Any,
) -> None:
    """MEM-REN-TEST-04: expired source → start_date = today MSK; strategy literal flips.

    Source ended ~31 days before today MSK; the new row MUST start today MSK
    (NOT source.end_date + 1, which would be ~30 days in the past).
    """
    plan = await make_plan(
        name="MEM-REN-TEST-04 plan",
        duration_days=30,
        price_kopecks=200_000,
        freeze_days_limit=14,
    )
    client = await _create_client(authed_client_reception, phone="+79991239040")
    client_uuid = UUID(client["id"])

    # Anchor today MSK at test start; service uses the same TZ inside.
    today_msk = _datetime.now(ZoneInfo("Europe/Moscow")).date()
    long_past_start = today_msk - timedelta(days=60)
    long_past_end = today_msk - timedelta(days=31)
    source = await make_membership(
        client_id=client_uuid,
        plan=plan,
        status="expired",
        start_date=long_past_start,
        end_date=long_past_end,
    )

    r = await authed_client_reception.post(
        f"/api/v1/memberships/{source.id}/renew",
        headers=_csrf_headers(authed_client_reception),
    )
    assert r.status_code == 201, r.text
    body: dict[str, Any] = r.json()["data"]

    # Re-anchor after the POST in case midnight MSK rolled over mid-test (the
    # service captured "today" inside its own call). Accept the call's day or
    # the one immediately after (race window).
    today_msk_after = _datetime.now(ZoneInfo("Europe/Moscow")).date()
    accepted = {today_msk.isoformat(), today_msk_after.isoformat()}
    assert body["startDate"] in accepted, (
        f"startDate={body['startDate']} not in accepted MSK days {accepted}"
    )
    # endDate = startDate + (plan.duration_days - 1) — INCLUSIVE.
    accepted_end = {(d + timedelta(days=29)).isoformat() for d in [today_msk, today_msk_after]}
    assert body["endDate"] in accepted_end

    # Audit payload literal flips to from_today_expired_source.
    audit_row = await db_session.scalar(
        select(AuditLog).where(
            AuditLog.action == "membership_renewed",
            AuditLog.resource_id == UUID(body["id"]),
        )
    )
    assert audit_row is not None
    assert audit_row.payload["start_date_strategy"] == "from_today_expired_source"


async def test_renew_active_uses_source_end_date_strategy_for_comparison(
    authed_client_reception: AsyncClient,
    db_session: AsyncSession,
    make_plan: Any,
    make_membership: Any,
) -> None:
    """Sanity-pin: active source produces strategy='from_source_end_date'.

    Proves the literal flip in test_renew_expired_source_starts_today actually
    branches on source.status — without this comparison, a service regression
    that always emitted 'from_source_end_date' would pass the expired test
    only by coincidence.
    """
    plan = await make_plan(name="Strategy comparison plan")
    client = await _create_client(authed_client_reception, phone="+79991239041")
    client_uuid = UUID(client["id"])
    source = await make_membership(client_id=client_uuid, plan=plan, status="active")

    r = await authed_client_reception.post(
        f"/api/v1/memberships/{source.id}/renew",
        headers=_csrf_headers(authed_client_reception),
    )
    assert r.status_code == 201, r.text
    new_id = UUID(r.json()["data"]["id"])

    audit_row = await db_session.scalar(
        select(AuditLog).where(
            AuditLog.action == "membership_renewed",
            AuditLog.resource_id == new_id,
        )
    )
    assert audit_row is not None
    assert audit_row.payload["start_date_strategy"] == "from_source_end_date"
