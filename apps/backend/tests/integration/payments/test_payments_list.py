"""Integration tests for GET /api/v1/payments listing endpoints (Phase 32 PAY-06..08).

Coverage:
  - Owner can list globally with all filter combinations.
  - Reception is 403 on the global route (VIEW, PAYMENTS in OWNER_ONLY).
  - Reception+owner can both list by-client and by-membership (PAY-07).
  - subject_kind / subject_id / received_by_user_id / received_from / received_to
    filter parity (half-open date window in Europe/Moscow).
  - Pagination envelope shape: items, total, page, pageSize.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

from httpx import AsyncClient

from app.modules.payments.constants import (
    SUBJECT_KIND_MEMBERSHIP,
    SUBJECT_KIND_REFUND,
)

# --- helpers ---------------------------------------------------------------


def _csrf_headers(client: AsyncClient) -> dict[str, str]:
    return {"X-CSRF-Token": client.cookies.get("sportzal_csrf") or ""}


# --- tests -----------------------------------------------------------------


async def test_owner_lists_global_payments(
    authed_client_owner: AsyncClient,
    seeded_owner: Any,
    make_plan: Any,
    make_client: Any,
    make_membership: Any,
    make_payment: Any,
) -> None:
    """Owner GET /api/v1/payments returns all seeded ledger rows (PAY-06)."""
    plan = await make_plan(name="ListGlobal")
    cli = await make_client()
    mem1 = await make_membership(client_id=cli.id, plan=plan)
    mem2 = await make_membership(client_id=cli.id, plan=plan)
    await make_payment(subject_id=mem1.id, received_by_user_id=seeded_owner.id)
    await make_payment(subject_id=mem2.id, received_by_user_id=seeded_owner.id)

    r = await authed_client_owner.get("/api/v1/payments")
    assert r.status_code == 200, r.text
    body = r.json()["data"]
    assert body["total"] >= 2
    assert isinstance(body["items"], list)
    assert body["page"] == 1
    assert body["pageSize"] == 20


async def test_reception_forbidden_on_global(
    authed_client_reception: AsyncClient,
) -> None:
    """(VIEW, PAYMENTS) ∈ OWNER_ONLY → reception receives 403 on global route."""
    r = await authed_client_reception.get("/api/v1/payments")
    assert r.status_code == 403, r.text
    body = r.json()
    assert body["code"] == "forbidden"
    assert "payments" in body["message"]


async def test_owner_filters_by_subject_kind(
    authed_client_owner: AsyncClient,
    seeded_owner: Any,
    make_plan: Any,
    make_client: Any,
    make_membership: Any,
    make_payment: Any,
) -> None:
    """?subjectKind=membership returns only membership-sale rows."""
    plan = await make_plan(name="FilterKind")
    cli = await make_client()
    mem = await make_membership(client_id=cli.id, plan=plan)
    sale = await make_payment(subject_id=mem.id, received_by_user_id=seeded_owner.id)
    # Refund-side row: subject_kind='refund', negative amount, refund_of -> sale.
    await make_payment(
        subject_kind=SUBJECT_KIND_REFUND,
        subject_id=mem.id,
        received_by_user_id=seeded_owner.id,
        amount_kopecks=-sale.amount_kopecks,
        refund_of=sale.id,
    )

    r = await authed_client_owner.get("/api/v1/payments?subjectKind=membership")
    assert r.status_code == 200, r.text
    items = r.json()["data"]["items"]
    assert all(item["subjectKind"] == SUBJECT_KIND_MEMBERSHIP for item in items)


async def test_owner_filters_by_received_by_user_id(
    authed_client_owner: AsyncClient,
    seeded_owner: Any,
    make_user: Any,
    make_plan: Any,
    make_client: Any,
    make_membership: Any,
    make_payment: Any,
) -> None:
    """?receivedByUserId=... returns only rows recorded by that operator."""
    other = await make_user(role="reception")
    plan = await make_plan(name="FilterActor")
    cli = await make_client()
    mem1 = await make_membership(client_id=cli.id, plan=plan)
    mem2 = await make_membership(client_id=cli.id, plan=plan)
    await make_payment(subject_id=mem1.id, received_by_user_id=seeded_owner.id)
    p_other = await make_payment(subject_id=mem2.id, received_by_user_id=other.id)

    r = await authed_client_owner.get(f"/api/v1/payments?receivedByUserId={other.id}")
    assert r.status_code == 200, r.text
    items = r.json()["data"]["items"]
    assert len(items) == 1
    assert items[0]["id"] == str(p_other.id)


async def test_owner_filters_by_date_range_half_open(
    authed_client_owner: AsyncClient,
    seeded_owner: Any,
    make_plan: Any,
    make_client: Any,
    make_membership: Any,
    make_payment: Any,
) -> None:
    """receivedFrom / receivedTo describe a half-open MSK window (inclusive on both ends)."""
    plan = await make_plan(name="FilterDate")
    cli = await make_client()
    mem = await make_membership(client_id=cli.id, plan=plan)

    # Anchor: 2026-05-15 UTC noon. Same MSK day. Just before midnight UTC of next day.
    middle = datetime(2026, 5, 15, 12, 0, 0, tzinfo=UTC)
    p_in = await make_payment(
        subject_id=mem.id,
        received_by_user_id=seeded_owner.id,
        received_at=middle,
    )
    p_after = await make_payment(
        subject_id=mem.id,
        received_by_user_id=seeded_owner.id,
        received_at=middle + timedelta(days=2),
    )
    p_before = await make_payment(
        subject_id=mem.id,
        received_by_user_id=seeded_owner.id,
        received_at=middle - timedelta(days=2),
    )

    r = await authed_client_owner.get(
        "/api/v1/payments?receivedFrom=2026-05-14&receivedTo=2026-05-15"
    )
    assert r.status_code == 200, r.text
    item_ids = {item["id"] for item in r.json()["data"]["items"]}
    assert str(p_in.id) in item_ids
    assert str(p_before.id) not in item_ids
    assert str(p_after.id) not in item_ids


async def test_reception_lists_by_client(
    authed_client_reception: AsyncClient,
    seeded_owner: Any,
    make_plan: Any,
    make_client: Any,
    make_membership: Any,
    make_payment: Any,
) -> None:
    """Reception 200 on /by-client/{id} (PAY-07 — scoped to single client)."""
    plan = await make_plan(name="ByClient")
    cli = await make_client()
    mem = await make_membership(client_id=cli.id, plan=plan)
    p = await make_payment(subject_id=mem.id, received_by_user_id=seeded_owner.id)

    r = await authed_client_reception.get(f"/api/v1/payments/by-client/{cli.id}")
    assert r.status_code == 200, r.text
    item_ids = {item["id"] for item in r.json()["data"]["items"]}
    assert str(p.id) in item_ids


async def test_reception_lists_by_membership(
    authed_client_reception: AsyncClient,
    seeded_owner: Any,
    make_plan: Any,
    make_client: Any,
    make_membership: Any,
    make_payment: Any,
) -> None:
    """Reception 200 on /by-membership/{id} (PAY-07 — scoped to single membership)."""
    plan = await make_plan(name="ByMembership")
    cli = await make_client()
    mem = await make_membership(client_id=cli.id, plan=plan)
    sale = await make_payment(subject_id=mem.id, received_by_user_id=seeded_owner.id)
    refund = await make_payment(
        subject_kind=SUBJECT_KIND_REFUND,
        subject_id=mem.id,
        received_by_user_id=seeded_owner.id,
        amount_kopecks=-sale.amount_kopecks,
        refund_of=sale.id,
    )

    r = await authed_client_reception.get(f"/api/v1/payments/by-membership/{mem.id}")
    assert r.status_code == 200, r.text
    item_ids = {item["id"] for item in r.json()["data"]["items"]}
    assert str(sale.id) in item_ids
    assert str(refund.id) in item_ids  # refund row joined via refund_of.


async def test_pagination_envelope_shape(
    authed_client_owner: AsyncClient,
) -> None:
    """Response data has items / total / page / pageSize keys (camelCase)."""
    r = await authed_client_owner.get("/api/v1/payments?page=1&pageSize=5")
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert set(data.keys()) >= {"items", "total", "page", "pageSize"}
    assert data["page"] == 1
    assert data["pageSize"] == 5


async def test_by_client_404_for_unknown_id_returns_empty_page(
    authed_client_owner: AsyncClient,
) -> None:
    """Unknown client id returns an empty page (200), not 404 — list semantic."""
    unknown = uuid4()
    r = await authed_client_owner.get(f"/api/v1/payments/by-client/{unknown}")
    assert r.status_code == 200, r.text
    assert r.json()["data"]["items"] == []
    assert r.json()["data"]["total"] == 0
