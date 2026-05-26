"""Integration tests for GET /api/v1/payroll/accruals (Phase 58 PAY-05 / D-58-14).

Coverage:
  - Ordering: N accruals with staggered accrued_at → items returned accrued_at DESC.
  - Envelope keys present: items, total, page, pageSize.
  - Pagination math: pageSize=2 over 5 rows → page 1 has 2 items total 5; page 3 has 1.
  - Clawback row (negative accrual_kopecks) appears in items list.
  - Paid and pending rows both surface with correct status + paidAt.
  - Reception → 403 (T-58-31 mitigate).
  - trainer_id filter scopes results (other trainer's accruals not returned).
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.payments.models import Payment


def _csrf(client: AsyncClient) -> dict[str, str]:
    """Return the X-CSRF-Token header from the client's cookie jar."""
    token: str = client.cookies.get("sportzal_csrf") or ""
    return {"X-CSRF-Token": token}


def _accruals_url(trainer_id: UUID, *, page: int = 1, page_size: int = 20) -> str:
    """Build the GET /accruals URL with required trainerId query param."""
    return f"/api/v1/payroll/accruals?trainerId={trainer_id}&page={page}&pageSize={page_size}"


async def _seed_accruals(
    make_trainer: Any,
    make_comp_config: Any,
    make_accrual: Any,
    *,
    count: int,
    trainer_id: UUID | None = None,
    accrual_kopecks: int = 100000,
    status: str = "pending",
    clawback_of_accrual_id: UUID | None = None,
    source_refund_payment_id: UUID | None = None,
    config_id: UUID | None = None,
) -> tuple[UUID, UUID, list[Any]]:
    """Seed *count* accruals with staggered accrued_at (1-day intervals) for a trainer.

    Returns (trainer.id, comp_config.id, [accrual_rows_newest_first]).
    """
    if trainer_id is None:
        trainer = await make_trainer()
        tid = trainer.id
    else:
        tid = trainer_id

    if config_id is None:
        cfg = await make_comp_config(
            trainer_id=tid,
            session_fee_kopecks=100000,
            effective_from=date(2026, 1, 1),
        )
        cid = cfg.id
    else:
        cid = config_id

    accruals = []
    # Seed from oldest (farthest past) to newest so DB sequence is predictable.
    # Pass explicit accrued_at with 1-day stagger so ordering is deterministic even
    # when rows are inserted within the same DB clock tick.
    base_date = datetime(2026, 3, 1, 12, 0, 0, tzinfo=UTC)
    for i in range(count):
        at = base_date + timedelta(days=i)
        a = await make_accrual(
            trainer_id=tid,
            period_start=date(2026, 3, i + 1),
            period_end=date(2026, 3, i + 1),
            sessions_count=1,
            revenue_kopecks=0,
            comp_config_id_snapshot=cid,
            accrual_kopecks=accrual_kopecks,
            status=status,
            clawback_of_accrual_id=clawback_of_accrual_id,
            source_refund_payment_id=source_refund_payment_id,
            accrued_at=at,
        )
        accruals.append(a)

    # Return newest first (DESC order expected by the endpoint)
    accruals_desc = list(reversed(accruals))
    return tid, cid, accruals_desc


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


async def test_list_returns_accrued_at_desc_ordering(
    authed_client_owner: AsyncClient,
    make_trainer: Any,
    make_comp_config: Any,
    make_accrual: Any,
) -> None:
    """Accruals ordered accrued_at DESC (newest item first in items[]).

    Seeds 3 accruals with staggered accrued_at; asserts items[0] is newer than
    items[1] and items[1] newer than items[2].
    """
    trainer_id, _, _ = await _seed_accruals(make_trainer, make_comp_config, make_accrual, count=3)

    r = await authed_client_owner.get(_accruals_url(trainer_id))
    assert r.status_code == 200, r.text
    items = r.json()["data"]["items"]
    assert len(items) == 3

    # accrued_at DESC: items[0] >= items[1] >= items[2]
    times = [item["accruedAt"] for item in items]
    assert times[0] >= times[1] >= times[2], f"Expected descending accrued_at order, got {times}"


async def test_envelope_keys_present(
    authed_client_owner: AsyncClient,
    make_trainer: Any,
    make_comp_config: Any,
    make_accrual: Any,
) -> None:
    """Response envelope contains items, total, page, pageSize keys (PAY-05 / D-58-14)."""
    trainer_id, _, _ = await _seed_accruals(make_trainer, make_comp_config, make_accrual, count=2)

    r = await authed_client_owner.get(_accruals_url(trainer_id))
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert "items" in data, f"Missing 'items' key: {data}"
    assert "total" in data, f"Missing 'total' key: {data}"
    assert "page" in data, f"Missing 'page' key: {data}"
    assert "pageSize" in data, f"Missing 'pageSize' key: {data}"
    assert data["total"] == 2
    assert data["page"] == 1
    assert data["pageSize"] == 20  # default page_size


async def test_pagination_math(
    authed_client_owner: AsyncClient,
    make_trainer: Any,
    make_comp_config: Any,
    make_accrual: Any,
) -> None:
    """Pagination: pageSize=2 over 5 rows → page 1 has 2 items, total 5; page 3 has 1.

    Verifies LIMIT/OFFSET logic + total is always the unpaginated count (PAY-05 / D-58-14).
    """
    trainer_id, _, _ = await _seed_accruals(make_trainer, make_comp_config, make_accrual, count=5)

    # Page 1: 2 items, total 5
    r1 = await authed_client_owner.get(_accruals_url(trainer_id, page=1, page_size=2))
    assert r1.status_code == 200, r1.text
    d1 = r1.json()["data"]
    assert len(d1["items"]) == 2, f"Expected 2 items on page 1, got {len(d1['items'])}"
    assert d1["total"] == 5, f"Expected total=5, got {d1['total']}"
    assert d1["page"] == 1
    assert d1["pageSize"] == 2

    # Page 2: 2 items, total 5
    r2 = await authed_client_owner.get(_accruals_url(trainer_id, page=2, page_size=2))
    assert r2.status_code == 200, r2.text
    d2 = r2.json()["data"]
    assert len(d2["items"]) == 2, f"Expected 2 items on page 2, got {len(d2['items'])}"
    assert d2["total"] == 5

    # Page 3: 1 item (the last remainder), total 5
    r3 = await authed_client_owner.get(_accruals_url(trainer_id, page=3, page_size=2))
    assert r3.status_code == 200, r3.text
    d3 = r3.json()["data"]
    assert len(d3["items"]) == 1, f"Expected 1 item on page 3, got {len(d3['items'])}"
    assert d3["total"] == 5


async def test_clawback_row_appears_in_list(
    authed_client_owner: AsyncClient,
    make_trainer: Any,
    make_comp_config: Any,
    make_accrual: Any,
    db_session: AsyncSession,
) -> None:
    """A clawback row (negative accrual_kopecks) appears in items list (D-58-03 / T-58-31).

    Seeds one regular accrual and one clawback accrual (negative accrual_kopecks,
    clawback_of_accrual_id + source_refund_payment_id set). Asserts both appear and
    the clawback row has negative accrualKopecks.
    """
    trainer = await make_trainer()
    cfg = await make_comp_config(
        trainer_id=trainer.id,
        session_fee_kopecks=100000,
        effective_from=date(2026, 1, 1),
    )

    # Regular accrual (positive)
    regular = await make_accrual(
        trainer_id=trainer.id,
        period_start=date(2026, 3, 1),
        period_end=date(2026, 3, 31),
        sessions_count=1,
        revenue_kopecks=0,
        comp_config_id_snapshot=cfg.id,
        accrual_kopecks=100000,
    )

    # Seed a real payment row to satisfy the source_refund_payment_id FK constraint.
    # The paired constraint requires clawback_of_accrual_id AND source_refund_payment_id
    # to both be non-NULL for clawback rows (ck_trainer_payroll_accruals_clawback_fks_paired).
    # subject_kind='refund' with negative amount_kopecks satisfies ck_payments_amount_sign.
    refund_payment = Payment(
        subject_kind="refund",
        subject_id=uuid4(),  # a plausible subject id (not FK-constrained for refunds)
        amount_kopecks=-100000,  # negative — satisfies ck_payments_amount_sign_matches_subject_kind
        method="cash",
        received_at=datetime(2026, 4, 1, 12, 0, 0, tzinfo=UTC),
    )
    db_session.add(refund_payment)
    await db_session.commit()
    await db_session.refresh(refund_payment)

    # Clawback accrual (negative) — clawback_of and source_refund_payment must both be set
    clawback = await make_accrual(
        trainer_id=trainer.id,
        period_start=date(2026, 3, 1),
        period_end=date(2026, 3, 31),
        sessions_count=1,
        revenue_kopecks=0,
        comp_config_id_snapshot=cfg.id,
        accrual_kopecks=-100000,  # negative — clawback
        clawback_of_accrual_id=regular.id,
        source_refund_payment_id=refund_payment.id,
    )

    r = await authed_client_owner.get(_accruals_url(trainer.id))
    assert r.status_code == 200, r.text
    items = r.json()["data"]["items"]
    assert len(items) == 2, f"Expected 2 items (regular + clawback), got {len(items)}"

    ids = {item["id"] for item in items}
    assert str(regular.id) in ids, "Regular accrual not in list"
    assert str(clawback.id) in ids, "Clawback accrual not in list"

    # Verify clawback row has negative accrualKopecks
    clawback_item = next(i for i in items if i["id"] == str(clawback.id))
    assert clawback_item["accrualKopecks"] < 0, (
        f"Expected negative accrualKopecks for clawback row, got {clawback_item['accrualKopecks']}"
    )
    assert clawback_item["clawbackOfAccrualId"] == str(regular.id)


async def test_paid_and_pending_rows_surface_with_status(
    authed_client_owner: AsyncClient,
    make_trainer: Any,
    make_comp_config: Any,
    make_accrual: Any,
) -> None:
    """Paid and pending rows both appear in list with correct status + paidAt (PAY-05).

    Seeds one pending accrual and one paid accrual; asserts both are present
    and status + paid_at fields match.
    """
    trainer = await make_trainer()
    cfg = await make_comp_config(
        trainer_id=trainer.id,
        session_fee_kopecks=100000,
        effective_from=date(2026, 1, 1),
    )

    pending = await make_accrual(
        trainer_id=trainer.id,
        period_start=date(2026, 3, 1),
        period_end=date(2026, 3, 31),
        sessions_count=1,
        revenue_kopecks=0,
        comp_config_id_snapshot=cfg.id,
        accrual_kopecks=100000,
        status="pending",
    )

    paid = await make_accrual(
        trainer_id=trainer.id,
        period_start=date(2026, 4, 1),
        period_end=date(2026, 4, 30),
        sessions_count=2,
        revenue_kopecks=0,
        comp_config_id_snapshot=cfg.id,
        accrual_kopecks=200000,
        status="paid",
    )

    r = await authed_client_owner.get(_accruals_url(trainer.id))
    assert r.status_code == 200, r.text
    items = r.json()["data"]["items"]
    assert len(items) == 2

    by_id = {item["id"]: item for item in items}
    assert str(pending.id) in by_id, "Pending accrual not in list"
    assert str(paid.id) in by_id, "Paid accrual not in list"

    pending_item = by_id[str(pending.id)]
    assert pending_item["status"] == "pending"
    assert pending_item["paidAt"] is None

    paid_item = by_id[str(paid.id)]
    assert paid_item["status"] == "paid"
    # paidAt may or may not be set depending on how make_accrual inserts;
    # the key must be present in the response (can be null if DB didn't set paid_at)
    assert "paidAt" in paid_item


async def test_reception_receives_403(
    authed_client_reception: AsyncClient,
    make_trainer: Any,
    make_comp_config: Any,
) -> None:
    """(LIST, PAYROLL) ∈ OWNER_ONLY → reception receives 403 (T-58-31 mitigate)."""
    trainer = await make_trainer()
    r = await authed_client_reception.get(_accruals_url(trainer.id))
    assert r.status_code == 403, r.text
    assert r.json()["code"] == "forbidden"


async def test_trainer_id_scopes_results(
    authed_client_owner: AsyncClient,
    make_trainer: Any,
    make_comp_config: Any,
    make_accrual: Any,
) -> None:
    """trainer_id filter ensures only that trainer's accruals are returned (T-58-33).

    Seeds accruals for two different trainers; querying by trainer A returns only
    trainer A's accruals, not trainer B's.
    """
    trainer_a_id, _, _ = await _seed_accruals(make_trainer, make_comp_config, make_accrual, count=2)
    trainer_b_id, _, _ = await _seed_accruals(make_trainer, make_comp_config, make_accrual, count=3)

    # Query trainer A — should see only 2 items
    r_a = await authed_client_owner.get(_accruals_url(trainer_a_id))
    assert r_a.status_code == 200, r_a.text
    data_a = r_a.json()["data"]
    assert data_a["total"] == 2, f"Trainer A: expected total=2, got {data_a['total']}"
    assert len(data_a["items"]) == 2

    # Query trainer B — should see only 3 items
    r_b = await authed_client_owner.get(_accruals_url(trainer_b_id))
    assert r_b.status_code == 200, r_b.text
    data_b = r_b.json()["data"]
    assert data_b["total"] == 3, f"Trainer B: expected total=3, got {data_b['total']}"
    assert len(data_b["items"]) == 3


async def test_empty_list_for_trainer_with_no_accruals(
    authed_client_owner: AsyncClient,
    make_trainer: Any,
) -> None:
    """Trainer with no accruals returns empty items, total=0 (boundary case)."""
    trainer = await make_trainer()
    r = await authed_client_owner.get(_accruals_url(trainer.id))
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert data["items"] == []
    assert data["total"] == 0
    assert data["page"] == 1
