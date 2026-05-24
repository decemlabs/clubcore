"""Integration tests for GET /api/v1/reports/visits (Phase 55 VIS-R-01..04).

Coverage:
  - Owner receives 200 with daily/hourly/averagePerDay (VIS-R-01..03).
  - Two visits on the same gym_date → one daily bucket count=2 (VIS-R-01, VIS-R-04).
  - Visits at distinct MSK hours → hourly buckets reflect those hours (VIS-R-02).
  - averagePerDay = total visits / calendar_days inclusive (D-10).
  - Reception receives 403 ((VIEW, REPORTS) ∈ OWNER_ONLY — SC#4).
  - toDate < fromDate → 422 (D-05).
  - range > 366 days → 422 report_range_too_large (D-06).

Wire format: ?fromDate=YYYY-MM-DD&toDate=YYYY-MM-DD
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from httpx import AsyncClient

# --- tests -------------------------------------------------------------------


async def test_owner_gets_visits_report(
    authed_client_owner: AsyncClient,
) -> None:
    """Owner GET /reports/visits returns 200 with correct shape (VIS-R-01..03)."""
    r = await authed_client_owner.get(
        "/api/v1/reports/visits",
        params={"fromDate": "2026-05-01", "toDate": "2026-05-31"},
    )
    assert r.status_code == 200, r.text
    body = r.json()["data"]
    assert "daily" in body
    assert "hourly" in body
    assert "averagePerDay" in body
    assert "fromDate" in body
    assert "toDate" in body
    assert isinstance(body["daily"], list)
    assert isinstance(body["hourly"], list)
    assert body["fromDate"] == "2026-05-01"
    assert body["toDate"] == "2026-05-31"


async def test_reception_forbidden_visits(
    authed_client_reception: AsyncClient,
) -> None:
    """(VIEW, REPORTS) ∈ OWNER_ONLY → reception receives 403 on /reports/visits (SC#4)."""
    r = await authed_client_reception.get(
        "/api/v1/reports/visits",
        params={"fromDate": "2026-05-01", "toDate": "2026-05-31"},
    )
    assert r.status_code == 403, r.text
    assert r.json()["code"] == "forbidden"


async def test_two_visits_same_gym_date_one_daily_bucket(
    authed_client_owner: AsyncClient,
    make_visit: Any,
    make_client: Any,
    make_plan: Any,
    make_membership: Any,
) -> None:
    """Two visits from different clients on the same MSK date produce one daily bucket count=2.

    Note: uq_visits_client_id_gym_date prevents two visits from the SAME client on one day.
    We use two distinct clients to produce two visit rows on 2026-08-10 MSK.

    Covers VIS-R-01 (daily count by gym_date) and VIS-R-04 (filter gym_date directly).
    """
    plan = await make_plan(name="TwoDailyVisitsTest")
    client1 = await make_client()
    client2 = await make_client()
    mem1 = await make_membership(client_id=client1.id, plan=plan, status="active")
    mem2 = await make_membership(client_id=client2.id, plan=plan, status="active")

    # Both visits on 2026-08-10 MSK (UTC+3 → 07:00 UTC is 10:00 MSK = same MSK day)
    msk_day = datetime(2026, 8, 10, 7, 0, 0, tzinfo=UTC)  # 2026-08-10 10:00 MSK
    await make_visit(client_id=client1.id, membership_id=mem1.id, checked_in_at=msk_day)
    await make_visit(client_id=client2.id, membership_id=mem2.id, checked_in_at=msk_day)

    r = await authed_client_owner.get(
        "/api/v1/reports/visits",
        params={"fromDate": "2026-08-10", "toDate": "2026-08-10"},
    )
    assert r.status_code == 200, r.text
    daily = r.json()["data"]["daily"]

    # Exactly one bucket for 2026-08-10 with count=2
    assert len(daily) == 1, f"Expected 1 daily bucket, got {daily}"
    assert daily[0]["date"] == "2026-08-10"
    assert daily[0]["count"] == 2, f"Expected count=2, got {daily[0]['count']}"


async def test_hourly_buckets_reflect_msk_hours(
    authed_client_owner: AsyncClient,
    make_visit: Any,
    make_client: Any,
    make_plan: Any,
    make_membership: Any,
) -> None:
    """Visits at distinct MSK hours produce separate hourly buckets (VIS-R-02)."""
    plan = await make_plan(name="HourlyBucketsTest")
    client_a = await make_client()
    client_b = await make_client()
    mem_a = await make_membership(client_id=client_a.id, plan=plan, status="active")
    mem_b = await make_membership(client_id=client_b.id, plan=plan, status="active")

    # client_a visits on 2026-09-01 at 09:00 MSK (UTC+3 → 06:00 UTC)
    ts_09_msk = datetime(2026, 9, 1, 6, 0, 0, tzinfo=UTC)  # 09:00 MSK
    # client_b visits on 2026-09-02 at 18:00 MSK (UTC+3 → 15:00 UTC) — different day for uniqueness
    ts_18_msk = datetime(2026, 9, 2, 15, 0, 0, tzinfo=UTC)  # 18:00 MSK

    await make_visit(client_id=client_a.id, membership_id=mem_a.id, checked_in_at=ts_09_msk)
    await make_visit(client_id=client_b.id, membership_id=mem_b.id, checked_in_at=ts_18_msk)

    r = await authed_client_owner.get(
        "/api/v1/reports/visits",
        params={"fromDate": "2026-09-01", "toDate": "2026-09-02"},
    )
    assert r.status_code == 200, r.text
    hourly = r.json()["data"]["hourly"]

    hours = {bucket["hour"]: bucket["count"] for bucket in hourly}
    assert 9 in hours, f"Expected hour 9 in hourly buckets, got {hours}"
    assert 18 in hours, f"Expected hour 18 in hourly buckets, got {hours}"
    assert hours[9] == 1
    assert hours[18] == 1


async def test_average_per_day_calculation(
    authed_client_owner: AsyncClient,
    make_visit: Any,
    make_client: Any,
    make_plan: Any,
    make_membership: Any,
) -> None:
    """averagePerDay = total visits / calendar_days inclusive (D-10).

    3 visits over a 3-day window → averagePerDay = 1.0.
    """
    plan = await make_plan(name="AvgPerDayTest")
    c1 = await make_client()
    c2 = await make_client()
    c3 = await make_client()
    m1 = await make_membership(client_id=c1.id, plan=plan, status="active")
    m2 = await make_membership(client_id=c2.id, plan=plan, status="active")
    m3 = await make_membership(client_id=c3.id, plan=plan, status="active")

    # One visit per day for 3 days (each on a different client to avoid unique constraint)
    await make_visit(
        client_id=c1.id,
        membership_id=m1.id,
        checked_in_at=datetime(2026, 10, 1, 7, 0, 0, tzinfo=UTC),  # 10:00 MSK
    )
    await make_visit(
        client_id=c2.id,
        membership_id=m2.id,
        checked_in_at=datetime(2026, 10, 2, 7, 0, 0, tzinfo=UTC),  # 10:00 MSK
    )
    await make_visit(
        client_id=c3.id,
        membership_id=m3.id,
        checked_in_at=datetime(2026, 10, 3, 7, 0, 0, tzinfo=UTC),  # 10:00 MSK
    )

    r = await authed_client_owner.get(
        "/api/v1/reports/visits",
        params={"fromDate": "2026-10-01", "toDate": "2026-10-03"},
    )
    assert r.status_code == 200, r.text
    body = r.json()["data"]

    # 3 visits over 3 calendar days = 1.0 average
    assert body["averagePerDay"] == 1.0, (
        f"Expected averagePerDay=1.0 (3 visits / 3 days), got {body['averagePerDay']}"
    )
    # Verify daily has 3 buckets (one per day — sparse, VIS-R-04)
    assert len(body["daily"]) == 3


async def test_average_per_day_denominator_uses_calendar_range(
    authed_client_owner: AsyncClient,
    make_visit: Any,
    make_client: Any,
    make_plan: Any,
    make_membership: Any,
) -> None:
    """averagePerDay divides by calendar_days in range, not days-with-visits (D-10).

    2 visits on day 1 of a 4-day window → averagePerDay = round(2/4, 2) = 0.5.
    """
    plan = await make_plan(name="CalDenominatorTest")
    c1 = await make_client()
    c2 = await make_client()
    m1 = await make_membership(client_id=c1.id, plan=plan, status="active")
    m2 = await make_membership(client_id=c2.id, plan=plan, status="active")

    # Two clients visit on day 1 only (day 2-4 are empty)
    await make_visit(
        client_id=c1.id,
        membership_id=m1.id,
        checked_in_at=datetime(2026, 11, 1, 7, 0, 0, tzinfo=UTC),  # 10:00 MSK
    )
    await make_visit(
        client_id=c2.id,
        membership_id=m2.id,
        checked_in_at=datetime(2026, 11, 1, 8, 0, 0, tzinfo=UTC),  # 11:00 MSK
    )

    # 4-day range: 2026-11-01 to 2026-11-04 (4 calendar days inclusive)
    r = await authed_client_owner.get(
        "/api/v1/reports/visits",
        params={"fromDate": "2026-11-01", "toDate": "2026-11-04"},
    )
    assert r.status_code == 200, r.text
    body = r.json()["data"]

    # 2 visits / 4 calendar days = 0.5
    assert body["averagePerDay"] == 0.5, (
        f"Expected averagePerDay=0.5 (2 visits / 4 calendar days), got {body['averagePerDay']}"
    )


async def test_to_before_from_returns_422_visits(
    authed_client_owner: AsyncClient,
) -> None:
    """toDate < fromDate → 422 (D-05)."""
    r = await authed_client_owner.get(
        "/api/v1/reports/visits",
        params={"fromDate": "2026-05-31", "toDate": "2026-05-01"},
    )
    assert r.status_code == 422, r.text


async def test_range_over_366_days_returns_422_visits(
    authed_client_owner: AsyncClient,
) -> None:
    """Range > 366 days → 422 with code 'report_range_too_large' (D-06)."""
    r = await authed_client_owner.get(
        "/api/v1/reports/visits",
        params={"fromDate": "2024-01-01", "toDate": "2026-01-01"},
    )
    assert r.status_code == 422, r.text
    assert r.json()["code"] == "report_range_too_large"
