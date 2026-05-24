"""Integration tests for GET /api/v1/reports/revenue (Phase 55 REV-01..05).

Coverage:
  - Owner receives 200 with correct ResponseEnvelope[RevenueReportResponse] shape.
  - Reception receives 403 ((VIEW, REPORTS) ∈ OWNER_ONLY — owner-only; SC#4).
  - Net revenue reconciles: sale + refund in same period = 0 (REV-04 canonical assertion).
  - groupBy=day buckets by MSK date; groupBy=month truncates to YYYY-MM (REV-02).
  - byMethod carries only positive sale amounts; refund does not appear in bySubjectKind (D-01).
  - toDate < fromDate → 422.
  - range > 366 days → 422 report_range_too_large (D-06).
  - missing fromDate or toDate → 422.

Wire format: ?fromDate=YYYY-MM-DD&toDate=YYYY-MM-DD&groupBy=day|month
(BackendSchemaBase alias_generator=to_camel maps from_date->fromDate, to_date->toDate)
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from httpx import AsyncClient


# --- tests -----------------------------------------------------------------


async def test_owner_gets_revenue_report(
    authed_client_owner: AsyncClient,
) -> None:
    """Owner GET /reports/revenue?fromDate=...&toDate=... returns 200 with buckets list (REV-01)."""
    r = await authed_client_owner.get(
        "/api/v1/reports/revenue",
        params={"fromDate": "2026-05-01", "toDate": "2026-05-31", "groupBy": "day"},
    )
    assert r.status_code == 200, r.text
    body = r.json()["data"]
    assert isinstance(body["buckets"], list)
    assert body["fromDate"] == "2026-05-01"
    assert body["toDate"] == "2026-05-31"
    assert body["groupBy"] == "day"


async def test_reception_forbidden(
    authed_client_reception: AsyncClient,
) -> None:
    """(VIEW, REPORTS) ∈ OWNER_ONLY → reception receives 403 (SC#4)."""
    r = await authed_client_reception.get(
        "/api/v1/reports/revenue",
        params={"fromDate": "2026-05-01", "toDate": "2026-05-31"},
    )
    assert r.status_code == 403, r.text
    assert r.json()["code"] == "forbidden"


async def test_net_revenue_zero_after_full_refund(
    authed_client_owner: AsyncClient,
    make_payment_ledger: Any,
    seeded_owner: Any,
    make_client: Any,
    make_membership: Any,
    make_plan: Any,
) -> None:
    """Sale + same-period refund must net to zero (REV-04 canonical assertion)."""
    plan = await make_plan(name="NetZeroTest")
    cli = await make_client()
    mem = await make_membership(client_id=cli.id, plan=plan)
    msk_ts = datetime(2026, 5, 15, 10, 0, 0, tzinfo=UTC)  # well within test window
    await make_payment_ledger(
        subject_id=mem.id,
        amount_kopecks=250000,
        method="cash",
        received_at=msk_ts,
        received_by_user_id=seeded_owner.id,
    )
    await make_payment_ledger(
        subject_id=mem.id,
        amount_kopecks=-250000,
        method="cash",
        subject_kind="refund",
        received_at=msk_ts,
        received_by_user_id=seeded_owner.id,
    )
    r = await authed_client_owner.get(
        "/api/v1/reports/revenue",
        params={"fromDate": "2026-05-01", "toDate": "2026-05-31"},
    )
    assert r.status_code == 200, r.text
    buckets = r.json()["data"]["buckets"]
    day_bucket = next((b for b in buckets if b["period"] == "2026-05-15"), None)
    assert day_bucket is not None, f"Expected 2026-05-15 bucket in {buckets}"
    assert day_bucket["netKopecks"] == 0


async def test_by_method_positive_sale_amounts_refund_excluded_from_subject_kind(
    authed_client_owner: AsyncClient,
    make_payment_ledger: Any,
    seeded_owner: Any,
    make_client: Any,
    make_membership: Any,
    make_plan: Any,
) -> None:
    """bySubjectKind shows sale amount; refund does not reduce bySubjectKind (D-01)."""
    plan = await make_plan(name="ByMethodTest")
    cli = await make_client()
    mem = await make_membership(client_id=cli.id, plan=plan)
    msk_ts = datetime(2026, 6, 10, 9, 0, 0, tzinfo=UTC)
    await make_payment_ledger(
        subject_id=mem.id,
        amount_kopecks=100000,
        method="cash",
        subject_kind="membership",
        received_at=msk_ts,
        received_by_user_id=seeded_owner.id,
    )
    await make_payment_ledger(
        subject_id=mem.id,
        amount_kopecks=-100000,
        method="cash",
        subject_kind="refund",
        received_at=msk_ts,
        received_by_user_id=seeded_owner.id,
    )
    r = await authed_client_owner.get(
        "/api/v1/reports/revenue",
        params={"fromDate": "2026-06-01", "toDate": "2026-06-30"},
    )
    assert r.status_code == 200, r.text
    buckets = r.json()["data"]["buckets"]
    bucket = next((b for b in buckets if b["period"] == "2026-06-10"), None)
    assert bucket is not None
    # net is zero (sale + refund = 0)
    assert bucket["netKopecks"] == 0
    # bySubjectKind shows the sale amount, NOT adjusted by refund (D-01)
    assert bucket["bySubjectKind"]["membership"] == 100000
    assert bucket["bySubjectKind"]["ptPackage"] == 0


async def test_group_by_month_collapses_buckets(
    authed_client_owner: AsyncClient,
    make_payment_ledger: Any,
    seeded_owner: Any,
    make_client: Any,
    make_membership: Any,
    make_plan: Any,
) -> None:
    """groupBy=month collapses July rows into single 'YYYY-MM' bucket (REV-02)."""
    plan = await make_plan(name="MonthGroupTest")
    cli = await make_client()
    mem = await make_membership(client_id=cli.id, plan=plan)
    ts1 = datetime(2026, 7, 1, 10, 0, 0, tzinfo=UTC)
    ts2 = datetime(2026, 7, 15, 10, 0, 0, tzinfo=UTC)
    await make_payment_ledger(
        subject_id=mem.id,
        amount_kopecks=50000,
        method="cash",
        received_at=ts1,
        received_by_user_id=seeded_owner.id,
    )
    await make_payment_ledger(
        subject_id=mem.id,
        amount_kopecks=75000,
        method="online",
        received_at=ts2,
        received_by_user_id=seeded_owner.id,
    )
    r = await authed_client_owner.get(
        "/api/v1/reports/revenue",
        params={"fromDate": "2026-07-01", "toDate": "2026-07-31", "groupBy": "month"},
    )
    assert r.status_code == 200, r.text
    buckets = r.json()["data"]["buckets"]
    # Must produce exactly one "2026-07" bucket for the month (D-08 sparse buckets)
    assert len(buckets) == 1, f"Expected 1 month bucket, got {buckets}"
    assert buckets[0]["period"] == "2026-07"
    assert buckets[0]["netKopecks"] == 125000
    assert buckets[0]["byMethod"]["cash"] == 50000
    assert buckets[0]["byMethod"]["online"] == 75000


async def test_to_before_from_returns_422(
    authed_client_owner: AsyncClient,
) -> None:
    """toDate < fromDate → 422 validation error (D-05)."""
    r = await authed_client_owner.get(
        "/api/v1/reports/revenue",
        params={"fromDate": "2026-05-31", "toDate": "2026-05-01"},
    )
    assert r.status_code == 422, r.text


async def test_range_over_366_days_returns_422_with_code(
    authed_client_owner: AsyncClient,
) -> None:
    """Range > 366 days → 422 with code 'report_range_too_large' (D-06)."""
    r = await authed_client_owner.get(
        "/api/v1/reports/revenue",
        params={"fromDate": "2024-01-01", "toDate": "2026-01-01"},
    )
    assert r.status_code == 422, r.text
    assert r.json()["code"] == "report_range_too_large"


async def test_missing_from_date_param_returns_422(
    authed_client_owner: AsyncClient,
) -> None:
    """Missing 'fromDate' parameter → 422 (Pydantic required field; D-05)."""
    r = await authed_client_owner.get(
        "/api/v1/reports/revenue",
        params={"toDate": "2026-05-31"},
    )
    assert r.status_code == 422, r.text


async def test_missing_to_date_param_returns_422(
    authed_client_owner: AsyncClient,
) -> None:
    """Missing 'toDate' parameter → 422 (Pydantic required field; D-05)."""
    r = await authed_client_owner.get(
        "/api/v1/reports/revenue",
        params={"fromDate": "2026-05-01"},
    )
    assert r.status_code == 422, r.text
