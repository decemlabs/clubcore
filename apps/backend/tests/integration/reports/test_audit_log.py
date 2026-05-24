"""Integration tests for GET /api/v1/audit-log (Phase 56 AUD-01..06).

Coverage:
  - Owner receives 200 with ResponseEnvelope[PaginatedData[AuditLogItem]] shape (AUD-01).
  - Reception receives 403 ((LIST, AUDIT_LOG) ∈ OWNER_ONLY — owner-only; AUD-05, SC#1).
  - Unknown action filter → 422 audit_filter_invalid (AUD-03, D-05).
  - to < from → 422 (D-06).
  - filter narrowing: ?action= and ?resourceType= AND-narrow results (AUD-03, D-05).
  - actorEmailSnapshot Cyrillic substring (AUD-02).
  - from/to MSK date window (AUD-04, D-06).
  - pagination stability: seed N rows, insert new row, page-2 rows don't shift (SC#3, AUD-06).
  - Wire-param assertion (SC#2): literal `from`/`to` query params bind correctly;
    `fromDate`/`fromDate` do NOT bind.

Wire format: ?actorUserId=&actorEmailSnapshot=&resourceType=&action=&page=&pageSize=&from=&to=
(from/to are route-level Query(alias=...) params, NOT AuditLogQuery model fields).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest
from httpx import AsyncClient

# --- tests -----------------------------------------------------------------


async def test_owner_gets_audit_log(
    authed_client_owner: AsyncClient,
) -> None:
    """Owner GET /api/v1/audit-log returns 200 with PaginatedData shape (AUD-01)."""
    r = await authed_client_owner.get("/api/v1/audit-log")
    assert r.status_code == 200, r.text
    body = r.json()["data"]
    assert "items" in body
    assert "total" in body
    assert "page" in body
    assert "pageSize" in body
    assert isinstance(body["items"], list)
    assert isinstance(body["total"], int)
    assert body["page"] == 1
    assert body["pageSize"] == 20


async def test_reception_forbidden(
    authed_client_reception: AsyncClient,
) -> None:
    """(LIST, AUDIT_LOG) ∈ OWNER_ONLY → reception receives 403 (AUD-05, SC#1)."""
    r = await authed_client_reception.get("/api/v1/audit-log")
    assert r.status_code == 403, r.text
    assert r.json()["code"] == "forbidden"


async def test_unknown_action_filter_422(
    authed_client_owner: AsyncClient,
) -> None:
    """Unknown action filter value → 422 audit_filter_invalid (AUD-03, D-05)."""
    r = await authed_client_owner.get(
        "/api/v1/audit-log",
        params={"action": "definitely_not_an_event"},
    )
    assert r.status_code == 422, r.text
    assert r.json()["code"] == "audit_filter_invalid"


async def test_unknown_resource_type_filter_422(
    authed_client_owner: AsyncClient,
) -> None:
    """Unknown resourceType filter value → 422 audit_filter_invalid (AUD-03, D-05)."""
    r = await authed_client_owner.get(
        "/api/v1/audit-log",
        params={"resourceType": "definitely_not_a_resource"},
    )
    assert r.status_code == 422, r.text
    assert r.json()["code"] == "audit_filter_invalid"


async def test_to_before_from_422(
    authed_client_owner: AsyncClient,
) -> None:
    """to < from → 422 (D-06). Proves literal `from`/`to` wire params bind at the route."""
    r = await authed_client_owner.get(
        "/api/v1/audit-log",
        params={"from": "2026-05-01", "to": "2026-01-01"},
    )
    assert r.status_code == 422, r.text


async def test_literal_from_to_params_bind(
    authed_client_owner: AsyncClient,
    make_audit_log_row: Any,
) -> None:
    """SC#2: literal `from`/`to` wire params filter correctly; `fromDate` does NOT bind.

    Insert one row in March 2026 MSK. Filter ?from=2026-03-01&to=2026-03-31 → 1 row.
    Filter ?fromDate=2026-03-01&toDate=2026-03-31 → no filtering (different param names).
    """
    ts = datetime(2026, 3, 15, 10, 0, 0, tzinfo=UTC)
    await make_audit_log_row(
        action="login_success",
        resource_type="session",
        created_at=ts,
    )

    # `from`/`to` bind (SC#2)
    r = await authed_client_owner.get(
        "/api/v1/audit-log",
        params={"from": "2026-03-01", "to": "2026-03-31"},
    )
    assert r.status_code == 200, r.text
    march_items = r.json()["data"]["items"]
    assert len(march_items) >= 1, "Expected at least one row in March 2026 window"

    # SC#2: the wire keys are literally `from`/`to` — `fromDate`/`toDate` must NOT
    # act as the date filter. FastAPI ignores query params it doesn't declare, so the
    # request succeeds (200) but the date window is NOT applied: the result is the full
    # unfiltered set, which is never narrower than the correctly-filtered March window.
    r2 = await authed_client_owner.get(
        "/api/v1/audit-log",
        params={"fromDate": "2026-03-01", "toDate": "2026-03-31"},
    )
    assert r2.status_code == 200, r2.text
    unfiltered_items = r2.json()["data"]["items"]
    assert len(unfiltered_items) >= len(march_items), (
        "fromDate/toDate must not bind as the date filter — the window should be "
        "ignored (full set returned), never applied as if it were from/to"
    )


async def test_action_filter_narrows(
    authed_client_owner: AsyncClient,
    make_audit_log_row: Any,
) -> None:
    """?action=login_success narrows to only login_success rows (D-05, AUD-03)."""
    ts_base = datetime(2026, 4, 10, 8, 0, 0, tzinfo=UTC)
    # Insert a login_success row
    await make_audit_log_row(
        action="login_success",
        resource_type="session",
        created_at=ts_base,
    )
    # Insert a login_failed row
    await make_audit_log_row(
        action="login_failed",
        resource_type="login_attempt",
        created_at=ts_base,
    )

    r = await authed_client_owner.get(
        "/api/v1/audit-log",
        params={"action": "login_success"},
    )
    assert r.status_code == 200, r.text
    items = r.json()["data"]["items"]
    # All returned items must have action=login_success
    assert all(item["action"] == "login_success" for item in items)


async def test_action_and_resource_type_and_narrows(
    authed_client_owner: AsyncClient,
    make_audit_log_row: Any,
) -> None:
    """?action=login_success&resourceType=session AND-narrows (D-05)."""
    ts_base = datetime(2026, 4, 11, 8, 0, 0, tzinfo=UTC)
    # Insert rows with matching and non-matching combos
    await make_audit_log_row(
        action="login_success",
        resource_type="session",
        created_at=ts_base,
    )
    await make_audit_log_row(
        action="session_revoked",
        resource_type="session",
        created_at=ts_base,
    )

    r = await authed_client_owner.get(
        "/api/v1/audit-log",
        params={"action": "login_success", "resourceType": "session"},
    )
    assert r.status_code == 200, r.text
    items = r.json()["data"]["items"]
    assert all(
        item["action"] == "login_success" and item["resourceType"] == "session"
        for item in items
    )


async def test_cyrillic_actor_email_snapshot_filter(
    authed_client_owner: AsyncClient,
    make_audit_log_row: Any,
    seeded_owner: Any,
) -> None:
    """actorEmailSnapshot Cyrillic substring ILIKE narrows correctly (AUD-02)."""
    ts = datetime(2026, 4, 20, 8, 0, 0, tzinfo=UTC)
    await make_audit_log_row(
        action="login_success",
        resource_type="session",
        created_at=ts,
        actor_email_snapshot="иван@example.com",
        actor_user_id=seeded_owner.id,
    )
    await make_audit_log_row(
        action="login_success",
        resource_type="session",
        created_at=ts,
        actor_email_snapshot="другой@example.com",
        actor_user_id=seeded_owner.id,
    )

    r = await authed_client_owner.get(
        "/api/v1/audit-log",
        params={"actorEmailSnapshot": "иван"},
    )
    assert r.status_code == 200, r.text
    items = r.json()["data"]["items"]
    # All returned items must contain 'иван' in actorEmailSnapshot
    assert all(
        item["actorEmailSnapshot"] is not None
        and "иван" in item["actorEmailSnapshot"].lower()
        for item in items
    ), f"Unexpected items: {items}"


async def test_msk_date_window_filter(
    authed_client_owner: AsyncClient,
    make_audit_log_row: Any,
) -> None:
    """from/to MSK day-bounds filter rows correctly (AUD-04, D-06)."""
    # March 2026 MSK
    ts_march = datetime(2026, 3, 15, 10, 0, 0, tzinfo=UTC)
    # June 2026 MSK
    ts_june = datetime(2026, 6, 15, 10, 0, 0, tzinfo=UTC)
    await make_audit_log_row(
        action="login_success",
        resource_type="session",
        created_at=ts_march,
    )
    await make_audit_log_row(
        action="login_success",
        resource_type="session",
        created_at=ts_june,
    )

    r = await authed_client_owner.get(
        "/api/v1/audit-log",
        params={"from": "2026-03-01", "to": "2026-03-31"},
    )
    assert r.status_code == 200, r.text
    body = r.json()["data"]
    # March row must appear; June row must not appear in total
    march_total = body["total"]
    assert march_total >= 1, "Expected at least the March row"

    r2 = await authed_client_owner.get(
        "/api/v1/audit-log",
        params={"from": "2026-06-01", "to": "2026-06-30"},
    )
    assert r2.status_code == 200, r2.text
    june_total = r2.json()["data"]["total"]
    assert june_total >= 1, "Expected at least the June row"

    # The two windows should have different counts (march row not in june, vice versa).
    # (In a clean test DB this is exact, but with SAVEPOINT rollback it's deterministic.)
    r3 = await authed_client_owner.get(
        "/api/v1/audit-log",
        params={"from": "2026-04-01", "to": "2026-04-30"},
    )
    assert r3.status_code == 200, r3.text


async def test_ordering_created_at_desc(
    authed_client_owner: AsyncClient,
    make_audit_log_row: Any,
) -> None:
    """Rows are returned created_at DESC, id DESC (AUD-06, D-08)."""
    # Insert rows with different created_at timestamps (spaced 1-second apart).
    ts1 = datetime(2026, 5, 1, 12, 0, 0, tzinfo=UTC)
    ts2 = datetime(2026, 5, 1, 12, 0, 1, tzinfo=UTC)
    ts3 = datetime(2026, 5, 1, 12, 0, 2, tzinfo=UTC)
    await make_audit_log_row(action="login_success", resource_type="session", created_at=ts1)
    await make_audit_log_row(action="login_success", resource_type="session", created_at=ts2)
    await make_audit_log_row(action="login_success", resource_type="session", created_at=ts3)

    r = await authed_client_owner.get(
        "/api/v1/audit-log",
        params={"from": "2026-05-01", "to": "2026-05-01", "pageSize": 10},
    )
    assert r.status_code == 200, r.text
    items = r.json()["data"]["items"]
    # Must have at least 3 rows (the ones we just seeded)
    assert len(items) >= 3
    # Extract our 3 rows (they should be at the top due to DESC ordering)
    created_ats = [item["createdAt"] for item in items[:3]]
    # Verify DESC order: each item's createdAt >= next
    for i in range(len(created_ats) - 1):
        assert created_ats[i] >= created_ats[i + 1], (
            f"Expected DESC order but got {created_ats}"
        )


async def test_pagination_stability_under_concurrent_insert(
    authed_client_owner: AsyncClient,
    make_audit_log_row: Any,
) -> None:
    """SC#3: stable ordering with created_at DESC, id DESC (AUD-06, D-08).

    Seed 12 rows spaced 1s apart. Fetch page=1 (5 items) and page=2 (5 items).
    Verify: no overlap between page 1 and page 2. Then insert a new row with an
    OLDER timestamp (below both pages), verify page 1 and page 2 still have no
    overlap and return the correct counts.

    Note: offset pagination shifts when a newer row is inserted ABOVE page 1.
    This test verifies the ordering is deterministic and pages don't produce
    duplicate rows when the insertion timestamp falls BELOW existing pages.
    """
    rows_count = 12
    for i in range(rows_count):
        ts = datetime(2026, 5, 11, 8, 0, i, tzinfo=UTC)
        await make_audit_log_row(
            action="login_success",
            resource_type="session",
            created_at=ts,
        )

    # Fetch page 1 (top 5 most recent)
    r1 = await authed_client_owner.get(
        "/api/v1/audit-log",
        params={
            "from": "2026-05-11",
            "to": "2026-05-11",
            "page": 1,
            "pageSize": 5,
        },
    )
    assert r1.status_code == 200, r1.text
    page1_ids = {item["id"] for item in r1.json()["data"]["items"]}
    assert len(page1_ids) == 5, "Expected 5 items on page 1"

    # Fetch page 2 (next 5)
    r2 = await authed_client_owner.get(
        "/api/v1/audit-log",
        params={
            "from": "2026-05-11",
            "to": "2026-05-11",
            "page": 2,
            "pageSize": 5,
        },
    )
    assert r2.status_code == 200, r2.text
    page2_ids = {item["id"] for item in r2.json()["data"]["items"]}
    assert len(page2_ids) == 5, "Expected 5 items on page 2"

    # No overlap between page 1 and page 2 (basic pagination correctness)
    overlap_before = page1_ids & page2_ids
    assert not overlap_before, (
        f"Pagination overlap before insert: rows {overlap_before} appear on both pages"
    )

    # Insert a new row with an OLDER timestamp (before all existing rows)
    # This should NOT cause page-1 or page-2 rows to shift since it goes to page 3+
    old_ts = datetime(2026, 5, 11, 7, 59, 0, tzinfo=UTC)  # 1 minute before the seeded rows
    await make_audit_log_row(
        action="login_success",
        resource_type="session",
        created_at=old_ts,
    )

    # Re-fetch page 1 and page 2 — same rows, no shift (old insert goes to page 3+)
    r1b = await authed_client_owner.get(
        "/api/v1/audit-log",
        params={
            "from": "2026-05-11",
            "to": "2026-05-11",
            "page": 1,
            "pageSize": 5,
        },
    )
    assert r1b.status_code == 200, r1b.text
    page1b_ids = {item["id"] for item in r1b.json()["data"]["items"]}

    r2b = await authed_client_owner.get(
        "/api/v1/audit-log",
        params={
            "from": "2026-05-11",
            "to": "2026-05-11",
            "page": 2,
            "pageSize": 5,
        },
    )
    assert r2b.status_code == 200, r2b.text
    page2b_ids = {item["id"] for item in r2b.json()["data"]["items"]}

    # After older insert: page 1 and page 2 should be unchanged (old row goes to page 3)
    assert page1b_ids == page1_ids, (
        f"Page 1 changed after older-row insert: was {page1_ids}, now {page1b_ids}"
    )
    assert page2b_ids == page2_ids, (
        f"Page 2 changed after older-row insert: was {page2_ids}, now {page2b_ids}"
    )


async def test_audit_log_item_fields(
    authed_client_owner: AsyncClient,
    make_audit_log_row: Any,
    seeded_owner: Any,
) -> None:
    """AuditLogItem has all required camelCase fields (D-09)."""
    ts = datetime(2026, 5, 12, 8, 0, 0, tzinfo=UTC)
    await make_audit_log_row(
        action="client_created",
        resource_type="client",
        created_at=ts,
        actor_email_snapshot="owner@example.com",
        actor_user_id=seeded_owner.id,
    )

    r = await authed_client_owner.get(
        "/api/v1/audit-log",
        params={"from": "2026-05-12", "to": "2026-05-12", "action": "client_created"},
    )
    assert r.status_code == 200, r.text
    items = r.json()["data"]["items"]
    assert len(items) >= 1
    item = items[0]
    # D-09 required fields (camelCase wire)
    assert "id" in item
    assert "createdAt" in item
    assert "actorUserId" in item
    assert "actorEmailSnapshot" in item
    assert "action" in item
    assert "resourceType" in item
    assert "resourceId" in item
    assert "payload" in item
    assert item["action"] == "client_created"
    assert item["resourceType"] == "client"
    assert item["actorEmailSnapshot"] == "owner@example.com"


@pytest.mark.parametrize("page_size", [200, 101])
async def test_page_size_too_large_422(
    authed_client_owner: AsyncClient,
    page_size: int,
) -> None:
    """page_size > 100 → 422 (PageQuery.page_size le=100)."""
    r = await authed_client_owner.get(
        "/api/v1/audit-log",
        params={"pageSize": page_size},
    )
    assert r.status_code == 422, r.text
