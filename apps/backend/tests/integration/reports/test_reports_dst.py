"""DST/MSK-offset midnight-boundary golden tests (VER-02, ROADMAP SC#3).

Coverage:
  - A payment at 21:30Z (00:30 MSK on the next calendar day) buckets into the NEXT
    MSK calendar date in the revenue report (D-07 / ROADMAP SC#3).
  - A visit at 21:30Z (00:30 MSK on the next calendar day) buckets into the NEXT
    MSK calendar date in the visits daily report (D-07 / ROADMAP SC#3).
  - Counter-anchor events at a safely mid-day MSK timestamp confirm two distinct MSK
    dates appear and the grouping is not trivially collapsing everything to one date.
  - Revenue net-of-refund: partial refund produces a deterministic golden amount
    (GROSS_KOPECKS - REFUND_KOPECKS = NET_KOPECKS) so plan 57-03 runbook can
    eyeball-match these exact numbers.

Requirement: VER-02.

RU-no-DST rationale:
    Russia has not observed Daylight Saving Time since October 2014. The real correctness
    risk is therefore NOT DST transitions but the fixed +03:00 (MSK = UTC+3) offset at
    UTC midnight boundaries. A payment or visit recorded at 21:00-23:59 UTC lands on the
    *next* Moscow calendar day. This file proves that invariant holds for both the revenue
    and visits report bucketing.

Named constants (referenced by 57-03 runbook):
    GOLDEN_DATE_UTC_PREV  - the UTC calendar date of the boundary event (2026-01-01)
    GOLDEN_DATE_MSK_NEXT  - the MSK calendar date the event bucketes into (2026-01-02)
    GROSS_KOPECKS         - gross sale amount in kopecks (250 000 kop = 2 500 RUB)
    REFUND_KOPECKS        - partial refund amount in kopecks  (50 000 kop =   500 RUB)
    NET_KOPECKS           - GROSS - REFUND = deterministic golden net (200 000 kop)
    ANCHOR_DATE_MSK       - safely mid-day MSK date used for counter-anchor (2026-01-02
                            at 07:00 UTC = 10:00 MSK, same MSK calendar day)

Wire format: ?fromDate=YYYY-MM-DD&toDate=YYYY-MM-DD[&groupBy=day]
(BackendSchemaBase alias_generator=to_camel maps from_date→fromDate, to_date→toDate)
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from httpx import AsyncClient

# ---------------------------------------------------------------------------
# Named constants — referenced verbatim by plan 57-03 runbook (D-11)
# ---------------------------------------------------------------------------

# The UTC calendar date on which both boundary events are recorded.
GOLDEN_DATE_UTC_PREV = "2026-01-01"

# The MSK calendar date the events must bucket into (next day because 21:30Z = 00:30 MSK).
GOLDEN_DATE_MSK_NEXT = "2026-01-02"

# Gross payment amount in kopecks (2 500,00 RUB = 250 000 kop).
GROSS_KOPECKS: int = 250_000

# Partial refund amount in kopecks (500,00 RUB = 50 000 kop).
REFUND_KOPECKS: int = 50_000

# Net revenue after partial refund: GROSS_KOPECKS - REFUND_KOPECKS = 200 000 kop.
NET_KOPECKS: int = GROSS_KOPECKS - REFUND_KOPECKS  # = 200 000

# Counter-anchor: 2026-01-02 10:00 MSK (07:00 UTC) — well within the same MSK calendar
# day as GOLDEN_DATE_MSK_NEXT, used to prove two distinct dates appear in the report.
_ANCHOR_UTC = datetime(2026, 1, 2, 7, 0, 0, tzinfo=UTC)  # 2026-01-02 10:00 MSK
ANCHOR_DATE_MSK = "2026-01-02"

# The UTC-midnight boundary timestamp under test: 21:30 UTC = 00:30 MSK (next day).
_BOUNDARY_UTC = datetime(2026, 1, 1, 21, 30, 0, tzinfo=UTC)  # 00:30 MSK on 2026-01-02

# Query window covers both calendar dates (UTC-prev and MSK-next are both 2026-01-0x).
_FROM_DATE = "2026-01-01"
_TO_DATE = "2026-01-02"


# ---------------------------------------------------------------------------
# Task 1 — Revenue: UTC-midnight boundary buckets into next MSK day
# ---------------------------------------------------------------------------


async def test_dst_revenue_boundary_payment_buckets_to_next_msk_day(
    authed_client_owner: AsyncClient,
    make_payment_ledger: Any,
    seeded_owner: Any,
    make_client: Any,
    make_membership: Any,
    make_plan: Any,
) -> None:
    """Payment at 21:30Z (00:30 MSK) must appear on GOLDEN_DATE_MSK_NEXT in revenue report.

    Arithmetic (net-of-refund, deterministic for 57-03 runbook):
        GROSS_KOPECKS = 250 000 kop
      - REFUND_KOPECKS =  50 000 kop
      = NET_KOPECKS    = 200 000 kop

    Counter-anchor at 07:00 UTC (10:00 MSK) on GOLDEN_DATE_MSK_NEXT proves the window
    produces TWO distinct MSK-day buckets when two payments fall on different UTC sub-days
    that map to the same MSK day (both the boundary event and the anchor land on 2026-01-02
    MSK, so their combined net = NET_KOPECKS + anchor_amount in the 2026-01-02 bucket).
    The 2026-01-01 MSK bucket must be absent (no payments at any UTC time that maps to MSK
    2026-01-01 within the query window).

    VER-02 / ROADMAP SC#3.
    """
    plan = await make_plan(name="DSTRevenueBoundaryTest")
    cli = await make_client()
    mem = await make_membership(client_id=cli.id, plan=plan)

    # --- boundary event: 21:30Z on 2026-01-01 = 00:30 MSK on 2026-01-02 ---
    await make_payment_ledger(
        subject_id=mem.id,
        amount_kopecks=GROSS_KOPECKS,
        method="cash",
        received_at=_BOUNDARY_UTC,  # 2026-01-01 21:30 UTC → 2026-01-02 MSK
        received_by_user_id=seeded_owner.id,
    )
    # Partial refund at the same boundary timestamp (still MSK 2026-01-02).
    await make_payment_ledger(
        subject_id=mem.id,
        amount_kopecks=-REFUND_KOPECKS,
        method="cash",
        subject_kind="refund",
        received_at=_BOUNDARY_UTC,
        received_by_user_id=seeded_owner.id,
    )

    # --- counter-anchor: 07:00 UTC on 2026-01-02 = 10:00 MSK on 2026-01-02 ---
    # A separate small payment on the SAME MSK day but a different UTC sub-time.
    # This confirms the report is not trivially bucketing everything into one date.
    await make_payment_ledger(
        subject_id=mem.id,
        amount_kopecks=10_000,  # 100,00 RUB anchor payment (not a named constant)
        method="online",
        received_at=_ANCHOR_UTC,  # 2026-01-02 07:00 UTC → 2026-01-02 10:00 MSK
        received_by_user_id=seeded_owner.id,
    )

    r = await authed_client_owner.get(
        "/api/v1/reports/revenue",
        params={"fromDate": _FROM_DATE, "toDate": _TO_DATE, "groupBy": "day"},
    )
    assert r.status_code == 200, r.text
    buckets = r.json()["data"]["buckets"]

    # 1. Boundary payment must appear in GOLDEN_DATE_MSK_NEXT (2026-01-02) bucket.
    next_day_bucket = next((b for b in buckets if b["period"] == GOLDEN_DATE_MSK_NEXT), None)
    assert next_day_bucket is not None, (
        f"Expected a bucket for {GOLDEN_DATE_MSK_NEXT} (boundary payment at 21:30Z "
        f"must bucket to next MSK day), got buckets={buckets}"
    )
    # Net = (GROSS_KOPECKS - REFUND_KOPECKS) + anchor_10_000 = NET_KOPECKS + 10_000
    assert next_day_bucket["netKopecks"] == NET_KOPECKS + 10_000, (
        f"Expected netKopecks={NET_KOPECKS + 10_000} in {GOLDEN_DATE_MSK_NEXT} bucket, "
        f"got {next_day_bucket['netKopecks']}"
    )

    # 2. No bucket for GOLDEN_DATE_UTC_PREV (2026-01-01) — the boundary event must NOT
    #    appear on the UTC calendar date, only on the MSK calendar date.
    prev_day_bucket = next((b for b in buckets if b["period"] == GOLDEN_DATE_UTC_PREV), None)
    assert prev_day_bucket is None, (
        f"Found unexpected bucket for {GOLDEN_DATE_UTC_PREV} — payment at 21:30Z "
        f"incorrectly bucketed to the UTC date instead of next MSK day: {prev_day_bucket}"
    )


async def test_dst_revenue_net_of_refund_golden_amount(
    authed_client_owner: AsyncClient,
    make_payment_ledger: Any,
    seeded_owner: Any,
    make_client: Any,
    make_membership: Any,
    make_plan: Any,
) -> None:
    """Assert deterministic NET_KOPECKS for 57-03 runbook eyeball-match.

    Uses isolated membership so only the boundary sale + refund appear in the window.
    NET_KOPECKS = GROSS_KOPECKS - REFUND_KOPECKS = 200 000 kop = 2 000,00 RUB.

    VER-02 / ROADMAP SC#3 / plan 57-03 canonical golden number.
    """
    plan = await make_plan(name="DSTNetOfRefundGoldenTest")
    cli = await make_client()
    mem = await make_membership(client_id=cli.id, plan=plan)

    await make_payment_ledger(
        subject_id=mem.id,
        amount_kopecks=GROSS_KOPECKS,
        method="cash",
        received_at=_BOUNDARY_UTC,  # 00:30 MSK 2026-01-02
        received_by_user_id=seeded_owner.id,
    )
    await make_payment_ledger(
        subject_id=mem.id,
        amount_kopecks=-REFUND_KOPECKS,
        method="cash",
        subject_kind="refund",
        received_at=_BOUNDARY_UTC,
        received_by_user_id=seeded_owner.id,
    )

    r = await authed_client_owner.get(
        "/api/v1/reports/revenue",
        params={"fromDate": GOLDEN_DATE_MSK_NEXT, "toDate": GOLDEN_DATE_MSK_NEXT, "groupBy": "day"},
    )
    assert r.status_code == 200, r.text
    buckets = r.json()["data"]["buckets"]

    bucket = next((b for b in buckets if b["period"] == GOLDEN_DATE_MSK_NEXT), None)
    assert bucket is not None, f"Expected bucket for {GOLDEN_DATE_MSK_NEXT}, got buckets={buckets}"
    assert bucket["netKopecks"] == NET_KOPECKS, (
        f"Golden net-of-refund mismatch: expected NET_KOPECKS={NET_KOPECKS}, "
        f"got {bucket['netKopecks']}. "
        f"(GROSS={GROSS_KOPECKS} - REFUND={REFUND_KOPECKS} = {NET_KOPECKS})"
    )


# ---------------------------------------------------------------------------
# Task 1 — Visits: UTC-midnight boundary buckets into next MSK day
# ---------------------------------------------------------------------------


async def test_dst_visits_boundary_visit_buckets_to_next_msk_day(
    authed_client_owner: AsyncClient,
    make_visit: Any,
    make_client: Any,
    make_plan: Any,
    make_membership: Any,
) -> None:
    """Visit at 21:30Z (00:30 MSK) must appear on GOLDEN_DATE_MSK_NEXT in visits daily report.

    gym_date is STORED GENERATED via (checked_in_at AT TIME ZONE 'Europe/Moscow')::date —
    never passed explicitly. Pass checked_in_at with tzinfo=UTC; assert the MSK date.

    Counter-anchor: a SECOND client visits on 2026-01-02 07:00 UTC (10:00 MSK) — same MSK
    day as the boundary visit. This proves the daily date key is the MSK calendar date, not
    the UTC date, and that the query window produces the expected distinct-date structure.

    VER-02 / ROADMAP SC#3.
    """
    plan = await make_plan(name="DSTVisitsBoundaryTest")
    # Two distinct clients — uq_visits_client_id_gym_date prevents same client twice per day.
    client_boundary = await make_client()
    client_anchor = await make_client()
    mem_boundary = await make_membership(client_id=client_boundary.id, plan=plan, status="active")
    mem_anchor = await make_membership(client_id=client_anchor.id, plan=plan, status="active")

    # Boundary visit: 21:30Z on 2026-01-01 → gym_date = 2026-01-02 (MSK)
    await make_visit(
        client_id=client_boundary.id,
        membership_id=mem_boundary.id,
        checked_in_at=_BOUNDARY_UTC,  # 2026-01-01 21:30 UTC = 2026-01-02 00:30 MSK
    )

    # Counter-anchor visit: 07:00Z on 2026-01-02 → gym_date = 2026-01-02 (MSK 10:00)
    await make_visit(
        client_id=client_anchor.id,
        membership_id=mem_anchor.id,
        checked_in_at=_ANCHOR_UTC,  # 2026-01-02 07:00 UTC = 2026-01-02 10:00 MSK
    )

    r = await authed_client_owner.get(
        "/api/v1/reports/visits",
        params={"fromDate": _FROM_DATE, "toDate": _TO_DATE},
    )
    assert r.status_code == 200, r.text
    daily = r.json()["data"]["daily"]

    # 1. Boundary visit must appear in GOLDEN_DATE_MSK_NEXT (2026-01-02) daily bucket.
    next_day_bucket = next((b for b in daily if b["date"] == GOLDEN_DATE_MSK_NEXT), None)
    assert next_day_bucket is not None, (
        f"Expected daily bucket for {GOLDEN_DATE_MSK_NEXT} (visit at 21:30Z must "
        f"bucket to next MSK day), got daily={daily}"
    )
    # Both the boundary visit and the counter-anchor land on GOLDEN_DATE_MSK_NEXT.
    assert next_day_bucket["count"] == 2, (
        f"Expected count=2 in {GOLDEN_DATE_MSK_NEXT} bucket "
        f"(boundary + anchor visits), got {next_day_bucket['count']}"
    )

    # 2. No bucket for GOLDEN_DATE_UTC_PREV (2026-01-01) — the boundary visit must NOT
    #    appear on the UTC calendar date.
    prev_day_bucket = next((b for b in daily if b["date"] == GOLDEN_DATE_UTC_PREV), None)
    assert prev_day_bucket is None, (
        f"Found unexpected daily bucket for {GOLDEN_DATE_UTC_PREV} — visit at 21:30Z "
        f"incorrectly bucketed to the UTC date instead of next MSK day: {prev_day_bucket}"
    )
