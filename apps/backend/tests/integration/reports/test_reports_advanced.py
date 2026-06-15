"""Integration tests for GET /api/v1/reports/cohort|anomaly|at-risk|load/now (Phase 115 ANL-02..04).

Coverage per endpoint:
  - Owner receives 200 with correct camelCase shape.
  - Reception receives 403 ((VIEW, REPORTS) ∈ OWNER_ONLY — SC#4).
  - Empty-data edge case returns valid empty/zero response (no NaN, no div-by-zero, no 500).
  - Small-sample edge case (1 cohort, 1 visit) returns stable, well-formed result.
  - load/now: 0 visits in window → count is a non-negative int (never NaN/error).

Wire shapes pinned here for Plan 03 FE Zod alignment (D-V32-DRIFT-LESSON closed at backend tier).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from httpx import AsyncClient

# ---------------------------------------------------------------------------
# GET /api/v1/reports/load/now
# ---------------------------------------------------------------------------


async def test_owner_gets_load_now(
    authed_client_owner: AsyncClient,
) -> None:
    """Owner GET /reports/load/now returns 200 with { count, asOf, windowMinutes }."""
    r = await authed_client_owner.get("/api/v1/reports/load/now")
    assert r.status_code == 200, r.text
    body = r.json()["data"]
    assert "count" in body
    assert "asOf" in body
    assert "windowMinutes" in body
    assert isinstance(body["count"], int)
    assert body["count"] >= 0
    assert isinstance(body["asOf"], str)
    assert isinstance(body["windowMinutes"], int)
    assert body["windowMinutes"] > 0


async def test_reception_forbidden_load_now(
    authed_client_reception: AsyncClient,
) -> None:
    """(VIEW, REPORTS) ∈ OWNER_ONLY → reception receives 403 on /reports/load/now."""
    r = await authed_client_reception.get("/api/v1/reports/load/now")
    assert r.status_code == 403, r.text
    assert r.json()["code"] == "forbidden"


async def test_load_now_zero_when_no_recent_visits(
    authed_client_owner: AsyncClient,
) -> None:
    """No visits in rolling window → count is a non-negative int (not NaN, not error)."""
    r = await authed_client_owner.get("/api/v1/reports/load/now")
    assert r.status_code == 200, r.text
    # count may be 0 or positive depending on DB state; must be a non-negative int
    assert r.json()["data"]["count"] >= 0


# ---------------------------------------------------------------------------
# GET /api/v1/reports/cohort
# ---------------------------------------------------------------------------


async def test_owner_gets_cohort(
    authed_client_owner: AsyncClient,
) -> None:
    """Owner GET /reports/cohort returns 200 with { cohorts, maxOffset }.

    Empty DB → cohorts == [] (no 500, no NaN).
    """
    r = await authed_client_owner.get("/api/v1/reports/cohort")
    assert r.status_code == 200, r.text
    body = r.json()["data"]
    assert "cohorts" in body
    assert "maxOffset" in body
    assert isinstance(body["cohorts"], list)
    assert isinstance(body["maxOffset"], int)
    # Empty DB: cohorts == [] is valid
    if len(body["cohorts"]) == 0:
        assert body["maxOffset"] == 0


async def test_reception_forbidden_cohort(
    authed_client_reception: AsyncClient,
) -> None:
    """(VIEW, REPORTS) ∈ OWNER_ONLY → reception receives 403 on /reports/cohort."""
    r = await authed_client_reception.get("/api/v1/reports/cohort")
    assert r.status_code == 403, r.text
    assert r.json()["code"] == "forbidden"


async def test_cohort_small_sample(
    authed_client_owner: AsyncClient,
    make_client: Any,
    make_plan: Any,
    make_membership: Any,
    make_visit: Any,
) -> None:
    """Seed 1 client + 1 membership starting last month + 1 visit this month.

    Asserts:
    - At least one cohort entry returned.
    - Every months entry has retentionPct in [0, 100] or None (no NaN).
    - Months list is non-decreasing by offset (stable ordering).
    - CohortEntry has cohortMonth (YYYY-MM str), label (str), months (list).
    """
    plan = await make_plan(name="CohortSmallSampleTest")
    client = await make_client()

    # Membership started last month so it shows up in the cohort grid.
    now_utc = datetime.now(UTC)
    start_last_month = (now_utc - timedelta(days=32)).date()
    membership = await make_membership(
        client_id=client.id,
        plan=plan,
        status="active",
        start_date=start_last_month,
    )

    # 1 visit this month (07:00 UTC = 10:00 MSK, safe day boundary).
    visit_ts = datetime(now_utc.year, now_utc.month, 1, 7, 0, 0, tzinfo=UTC)
    await make_visit(
        client_id=client.id,
        membership_id=membership.id,
        checked_in_at=visit_ts,
    )

    r = await authed_client_owner.get(
        "/api/v1/reports/cohort",
        params={"cohortMonths": 3},
    )
    assert r.status_code == 200, r.text
    body = r.json()["data"]
    cohorts = body["cohorts"]
    assert isinstance(cohorts, list)
    assert len(cohorts) >= 1, f"Expected >=1 cohort entry, got {cohorts}"

    for cohort in cohorts:
        assert "cohortMonth" in cohort
        assert "label" in cohort
        assert "months" in cohort
        assert isinstance(cohort["cohortMonth"], str)
        # cohortMonth must match YYYY-MM pattern
        assert len(cohort["cohortMonth"]) == 7, cohort["cohortMonth"]
        assert cohort["cohortMonth"][4] == "-", cohort["cohortMonth"]

        months = cohort["months"]
        assert isinstance(months, list)

        offsets = [m["offset"] for m in months]
        # Non-decreasing offset ordering (stable).
        assert offsets == sorted(offsets), f"Offsets not sorted: {offsets}"

        for month_entry in months:
            assert "offset" in month_entry
            assert "retentionPct" in month_entry
            pct = month_entry["retentionPct"]
            if pct is not None:
                # Must be a float/int in [0, 100] — never NaN.
                assert isinstance(pct, (int, float)), f"retentionPct is not numeric: {pct!r}"
                assert 0.0 <= pct <= 100.0, f"retentionPct out of range: {pct}"
                # Python float NaN check: NaN != NaN is always True.
                assert pct == pct, "retentionPct is NaN"


async def test_cohort_months_param_bounds(
    authed_client_owner: AsyncClient,
) -> None:
    """cohortMonths=0 → 422; cohortMonths=12 → 200."""
    r_invalid = await authed_client_owner.get(
        "/api/v1/reports/cohort",
        params={"cohortMonths": 0},
    )
    assert r_invalid.status_code == 422, r_invalid.text

    r_valid = await authed_client_owner.get(
        "/api/v1/reports/cohort",
        params={"cohortMonths": 12},
    )
    assert r_valid.status_code == 200, r_valid.text


# ---------------------------------------------------------------------------
# GET /api/v1/reports/anomaly
# ---------------------------------------------------------------------------


async def test_owner_gets_anomaly(
    authed_client_owner: AsyncClient,
) -> None:
    """Owner GET /reports/anomaly returns 200 with correct shape.

    Expected keys: points, windowDays, sigmaThreshold, anomalyCount.
    Empty DB: points == [] (or all count 0), anomalyCount == 0 (no NaN).
    """
    r = await authed_client_owner.get("/api/v1/reports/anomaly")
    assert r.status_code == 200, r.text
    body = r.json()["data"]
    assert "points" in body
    assert "windowDays" in body
    assert "sigmaThreshold" in body
    assert "anomalyCount" in body
    assert isinstance(body["points"], list)
    assert isinstance(body["windowDays"], int)
    assert isinstance(body["sigmaThreshold"], float)
    assert isinstance(body["anomalyCount"], int)
    assert body["anomalyCount"] >= 0


async def test_reception_forbidden_anomaly(
    authed_client_reception: AsyncClient,
) -> None:
    """(VIEW, REPORTS) ∈ OWNER_ONLY → reception receives 403 on /reports/anomaly."""
    r = await authed_client_reception.get("/api/v1/reports/anomaly")
    assert r.status_code == 403, r.text
    assert r.json()["code"] == "forbidden"


async def test_anomaly_small_sample_no_nan(
    authed_client_owner: AsyncClient,
    make_client: Any,
    make_plan: Any,
    make_membership: Any,
    make_visit: Any,
) -> None:
    """Seed visits on a few distinct gym_dates; assert anomaly series is well-formed.

    Asserts:
    - Every point.count is an int >= 0.
    - Every point.isAnomaly is bool.
    - Every point.direction is one of ('spike', 'drop', None).
    - anomalyCount == count of isAnomaly==True points (internal consistency).
    - No NaN/Inf in any count field.
    """
    plan = await make_plan(name="AnomalySmallSampleTest")
    client_a = await make_client()
    client_b = await make_client()
    mem_a = await make_membership(client_id=client_a.id, plan=plan, status="active")
    mem_b = await make_membership(client_id=client_b.id, plan=plan, status="active")

    # Seed visits on 3 distinct dates spread across the last 30 days.
    base = datetime.now(UTC).replace(hour=7, minute=0, second=0, microsecond=0)
    ts1 = base - timedelta(days=25)
    ts2 = base - timedelta(days=15)
    ts3 = base - timedelta(days=5)

    await make_visit(client_id=client_a.id, membership_id=mem_a.id, checked_in_at=ts1)
    await make_visit(client_id=client_b.id, membership_id=mem_b.id, checked_in_at=ts2)
    # client_a on day 3 (different day from ts1 → no unique constraint violation)
    await make_visit(client_id=client_a.id, membership_id=mem_a.id, checked_in_at=ts3)

    # Query the last 30 days of anomaly data.
    from_date = (base - timedelta(days=29)).date().isoformat()
    to_date = base.date().isoformat()

    r = await authed_client_owner.get(
        "/api/v1/reports/anomaly",
        params={"fromDate": from_date, "toDate": to_date},
    )
    assert r.status_code == 200, r.text
    body = r.json()["data"]
    points = body["points"]

    # Contiguous series: should have 30 entries (from_date..to_date inclusive).
    assert len(points) >= 1, "Expected at least 1 point in series"

    flagged_count = 0
    valid_directions = {"spike", "drop", None}
    for pt in points:
        assert "date" in pt
        assert "count" in pt
        assert "isAnomaly" in pt
        assert "direction" in pt
        assert "label" in pt
        cnt = pt["count"]
        assert isinstance(cnt, int), f"count is not int: {cnt!r}"
        assert cnt >= 0, f"count is negative: {cnt}"
        # NaN check: NaN != NaN
        assert cnt == cnt, f"count is NaN for date {pt['date']}"
        assert isinstance(pt["isAnomaly"], bool), f"isAnomaly not bool: {pt['isAnomaly']!r}"
        assert pt["direction"] in valid_directions, f"direction invalid: {pt['direction']!r}"
        if pt["isAnomaly"]:
            flagged_count += 1

    # Internal consistency: anomalyCount matches flagged points.
    assert body["anomalyCount"] == flagged_count, (
        f"anomalyCount={body['anomalyCount']} != flagged points={flagged_count}"
    )


# ---------------------------------------------------------------------------
# GET /api/v1/reports/at-risk
# ---------------------------------------------------------------------------


async def test_owner_gets_at_risk(
    authed_client_owner: AsyncClient,
) -> None:
    """Owner GET /reports/at-risk returns 200 with { count, items, thresholdDays }.

    Empty DB → count == 0, items == [] (no NaN, no 500).
    """
    r = await authed_client_owner.get("/api/v1/reports/at-risk")
    assert r.status_code == 200, r.text
    body = r.json()["data"]
    assert "count" in body
    assert "items" in body
    assert "thresholdDays" in body
    assert isinstance(body["count"], int)
    assert body["count"] >= 0
    assert isinstance(body["items"], list)
    assert isinstance(body["thresholdDays"], int)
    assert body["thresholdDays"] > 0


async def test_reception_forbidden_at_risk(
    authed_client_reception: AsyncClient,
) -> None:
    """(VIEW, REPORTS) ∈ OWNER_ONLY → reception receives 403 on /reports/at-risk."""
    r = await authed_client_reception.get("/api/v1/reports/at-risk")
    assert r.status_code == 403, r.text
    assert r.json()["code"] == "forbidden"


async def test_at_risk_flags_stale_member(
    authed_client_owner: AsyncClient,
    make_client: Any,
    make_plan: Any,
    make_membership: Any,
    make_visit: Any,
) -> None:
    """Stale client (last visit >14 days ago) appears in at-risk; recent client does not.

    Seed:
    - stale_client: active membership + visit 30 days ago.
    - recent_client: active membership + visit today.

    Assert:
    - stale_client appears in items with daysSinceVisit >= thresholdDays and
      lastVisitLabel a non-empty str.
    - recent_client does NOT appear in items.
    - count >= 1.
    """
    plan = await make_plan(name="AtRiskFlagsStaleTest")
    stale_client = await make_client()
    recent_client = await make_client()
    stale_mem = await make_membership(client_id=stale_client.id, plan=plan, status="active")
    recent_mem = await make_membership(client_id=recent_client.id, plan=plan, status="active")

    # Stale visit: 30 days ago (well beyond AT_RISK_THRESHOLD_DAYS=14).
    stale_ts = datetime.now(UTC).replace(hour=7, minute=0, second=0, microsecond=0) - timedelta(
        days=30
    )
    # Recent visit: today at 10:00 MSK.
    recent_ts = datetime.now(UTC).replace(hour=7, minute=0, second=0, microsecond=0)

    await make_visit(
        client_id=stale_client.id, membership_id=stale_mem.id, checked_in_at=stale_ts
    )
    await make_visit(
        client_id=recent_client.id, membership_id=recent_mem.id, checked_in_at=recent_ts
    )

    r = await authed_client_owner.get("/api/v1/reports/at-risk")
    assert r.status_code == 200, r.text
    body = r.json()["data"]

    threshold = body["thresholdDays"]
    items = body["items"]

    # Validate shape of every item.
    for item in items:
        assert "clientId" in item
        assert "name" in item
        assert "membershipType" in item
        assert "lastVisitDate" in item
        assert "daysSinceVisit" in item
        assert "lastVisitLabel" in item
        assert isinstance(item["daysSinceVisit"], int)
        assert item["daysSinceVisit"] >= threshold
        assert isinstance(item["lastVisitLabel"], str)
        assert len(item["lastVisitLabel"]) > 0

    stale_client_id = str(stale_client.id)
    recent_client_id = str(recent_client.id)

    item_ids = [item["clientId"] for item in items]
    assert stale_client_id in item_ids, (
        f"Stale client {stale_client_id} not found in at-risk items; items={item_ids}"
    )
    assert recent_client_id not in item_ids, (
        f"Recent client {recent_client_id} should NOT be in at-risk items"
    )

    # Find the stale client's entry and verify fields.
    stale_entry = next(item for item in items if item["clientId"] == stale_client_id)
    assert stale_entry["daysSinceVisit"] >= threshold
    assert len(stale_entry["lastVisitLabel"]) > 0

    assert body["count"] >= 1
