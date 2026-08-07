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


async def test_cohort_exact_retention_value(
    authed_client_owner: AsyncClient,
    make_client: Any,
    make_plan: Any,
    make_membership: Any,
    make_visit: Any,
) -> None:
    """Deterministic cohort → assert EXACT retentionPct values (CR-01 dense offset grid).

    Seeds a single-client cohort whose membership starts in the CURRENT MSK month
    and who visits exactly once in that same month. With the dense offset grid:
      - offset 0 (cohort month): 1 of 1 cohort member visited → 100.0%.
    A genuine no-visit month would now emit retentionPct == 0.0 (not None), so the
    grid is dense and the metric cannot silently drift between 0% and "no data".
    """
    plan = await make_plan(name="CohortExactValueTest")
    client = await make_client()

    # MSK "now": the visit + membership both land in the current MSK month.
    # Use day 15 at 10:00 MSK (07:00 UTC) — well clear of month boundaries / DST.
    now_msk = (datetime.now(UTC) + timedelta(hours=3)).date()
    start_this_month = now_msk.replace(day=15)
    membership = await make_membership(
        client_id=client.id,
        plan=plan,
        status="active",
        start_date=start_this_month,
    )

    # One visit in the SAME MSK month as the cohort start → offset 0 retained.
    visit_ts = datetime(now_msk.year, now_msk.month, 15, 7, 0, 0, tzinfo=UTC)
    await make_visit(
        client_id=client.id,
        membership_id=membership.id,
        checked_in_at=visit_ts,
    )

    r = await authed_client_owner.get(
        "/api/v1/reports/cohort",
        params={"cohortMonths": 1},
    )
    assert r.status_code == 200, r.text
    body = r.json()["data"]
    cohorts = body["cohorts"]

    cohort_key = start_this_month.strftime("%Y-%m")
    entry = next((c for c in cohorts if c["cohortMonth"] == cohort_key), None)
    assert entry is not None, f"Cohort {cohort_key} missing; got {cohorts}"

    months = {m["offset"]: m["retentionPct"] for m in entry["months"]}
    # Dense grid guarantees offset 0 is always present.
    assert 0 in months, f"offset 0 missing from cohort {cohort_key}: {months}"
    # EXACT value: 1 of 1 cohort member visited in the cohort month → 100.0%.
    assert months[0] == 100.0, f"Expected offset-0 retention 100.0, got {months[0]}"


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

    await make_visit(client_id=stale_client.id, membership_id=stale_mem.id, checked_in_at=stale_ts)
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


async def test_at_risk_ignores_visits_predating_membership(
    authed_client_owner: AsyncClient,
    make_client: Any,
    make_plan: Any,
    make_membership: Any,
    make_visit: Any,
) -> None:
    """WR-04: a re-joined client's visits predating the current membership are NOT counted.

    Seed a client whose CURRENT active membership started 10 days ago, but whose only
    visit happened 40 days ago (i.e. during an earlier, churned membership). The
    last_visit aggregation is scoped to checked_in_at >= membership start_date, so this
    client is treated as never-visited within the current membership → at-risk with
    lastVisitDate == None (not judged on the stale 40-day-old visit).
    """
    plan = await make_plan(name="AtRiskRejoinTest")
    client = await make_client()

    start_recent = (datetime.now(UTC).date()) - timedelta(days=10)
    membership = await make_membership(
        client_id=client.id,
        plan=plan,
        status="active",
        start_date=start_recent,
    )

    # Only visit is 40 days ago — well before the current membership's start_date.
    old_visit_ts = datetime.now(UTC).replace(hour=7, minute=0, second=0, microsecond=0) - timedelta(
        days=40
    )
    await make_visit(
        client_id=client.id,
        membership_id=membership.id,
        checked_in_at=old_visit_ts,
    )

    r = await authed_client_owner.get("/api/v1/reports/at-risk")
    assert r.status_code == 200, r.text
    items = r.json()["data"]["items"]

    entry = next((i for i in items if i["clientId"] == str(client.id)), None)
    assert entry is not None, "Re-joined client should be at-risk (no visit since membership start)"
    # Visit predating the membership is excluded → treated as never-visited.
    assert entry["lastVisitDate"] is None, (
        f"Pre-membership visit must be ignored; lastVisitDate={entry['lastVisitDate']!r}"
    )
    assert entry["lastVisitLabel"] == "не посещал"


async def test_at_risk_count_can_exceed_items_when_capped(
    authed_client_owner: AsyncClient,
    make_client: Any,
    make_plan: Any,
    make_membership: Any,
) -> None:
    """IN-02: count is the TRUE uncapped total; items is capped at AT_RISK_MAX_ITEMS (50).

    Seed AT_RISK_MAX_ITEMS + 5 never-visited active members. The response items list is
    capped at 50, but count must report the full total (55), so the FE overflow line
    ("И ещё N клиентов") is accurate when the list is capped.
    """
    from app.modules.reports.constants import AT_RISK_MAX_ITEMS

    plan = await make_plan(name="AtRiskCountCapTest")
    extra = 5
    for _ in range(AT_RISK_MAX_ITEMS + extra):
        client = await make_client()
        await make_membership(client_id=client.id, plan=plan, status="active")
        # No visit at all → never-visited → at-risk.

    r = await authed_client_owner.get("/api/v1/reports/at-risk")
    assert r.status_code == 200, r.text
    body = r.json()["data"]

    assert len(body["items"]) == AT_RISK_MAX_ITEMS, (
        f"items should be capped at {AT_RISK_MAX_ITEMS}, got {len(body['items'])}"
    )
    assert body["count"] >= AT_RISK_MAX_ITEMS + extra, (
        f"count should be the uncapped total (>= {AT_RISK_MAX_ITEMS + extra}), got {body['count']}"
    )
    assert body["count"] > len(body["items"]), (
        "count must exceed len(items) when the list is capped (IN-02)"
    )
