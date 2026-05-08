"""Phase 24 DEBT-02: GET /api/v1/memberships?expiring=true&within=N integration tests.

Covers:
- Default `within=7` with inclusive end-date semantics (D-24-12 + PROJECT.md
  "Key Decisions"): boundary at today+7 IS included; today+8 is excluded.
- Explicit `within=14` with inclusive boundary at today+14.
- Pydantic bound rejections (`within=0` and `within=31`).
- `expiring=true` forces status='active' (frozen/expired/cancelled excluded
  even when their `end_date` falls inside the window).
- Conflict: `?expiring=true&status=expired` -> 422 `query_invalid` with
  `fields.status="incompatible_with_expiring"` (D-24-11).
- Compatible status: `?expiring=true&status=active` is allowed.
- `expiring=false` silently ignores `within` (no date predicate added).
- Pagination envelope `{items,total,page,pageSize}` is preserved — the http
  adapter's BLK-06 single-page collapse is gone (D-24-13).

Response envelope: `r.json()["data"]["items"]` (mirror sibling
`test_memberships_list.py`). Field naming: camelCase `endDate` (Phase 17 D-10).

Conflict envelope (flat AppError shape from `core/exceptions.py:243-256`):
`{"code": "query_invalid", "message": "...", "fields": {...}}` — top-level,
NOT nested under `body["error"]`.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any
from uuid import UUID
from zoneinfo import ZoneInfo

import pytest
from httpx import AsyncClient

VALID_CLIENT: dict[str, Any] = {
    "lastName": "Иванов",
    "firstName": "Иван",
    "phone": "+79991234567",
}


def _csrf_headers(client: AsyncClient) -> dict[str, str]:
    return {"X-CSRF-Token": client.cookies.get("sportzal_csrf") or ""}


async def _create_client(
    authed_client_owner: AsyncClient,
    **overrides: Any,
) -> dict[str, Any]:
    payload: dict[str, Any] = {**VALID_CLIENT, **overrides}
    r = await authed_client_owner.post(
        "/api/v1/clients",
        json=payload,
        headers=_csrf_headers(authed_client_owner),
    )
    assert r.status_code == 201, r.text
    data: dict[str, Any] = r.json()["data"]
    return data


def _msk_today() -> Any:
    return datetime.now(ZoneInfo("Europe/Moscow")).date()


# --- Happy path: default within=7 (inclusive boundary) ---------------------


@pytest.mark.asyncio
async def test_list_expiring_within_default_7(
    authed_client_owner: AsyncClient,
    make_plan: Any,
    make_membership: Any,
) -> None:
    """expiring=true with no `within` defaults to 7 days, inclusive end_date semantics
    (D-24-12 + PROJECT.md "Key Decisions"): end_date in [today, today + 6] is
    INCLUDED (within=7 -> today + (7 - 1) = today + 6 inclusive). today + 7 is
    EXCLUDED.
    """
    today = _msk_today()
    plan = await make_plan(name="Default 7d")
    client = await _create_client(authed_client_owner, phone="+79990002001")
    client_uuid = UUID(client["id"])

    # In window — start of range (today):
    await make_membership(
        client_id=client_uuid,
        plan=plan,
        status="active",
        start_date=today - timedelta(days=30),
        end_date=today,
    )
    # In window — middle (today + 3):
    await make_membership(
        client_id=client_uuid,
        plan=plan,
        status="active",
        start_date=today - timedelta(days=30),
        end_date=today + timedelta(days=3),
    )
    # In window — boundary at today+6 (inclusive last day; within=7 -> +6):
    await make_membership(
        client_id=client_uuid,
        plan=plan,
        status="active",
        start_date=today - timedelta(days=30),
        end_date=today + timedelta(days=6),
    )
    # Out of window — today+7 (excluded; within=7 means up to today + 6):
    await make_membership(
        client_id=client_uuid,
        plan=plan,
        status="active",
        start_date=today - timedelta(days=30),
        end_date=today + timedelta(days=7),
    )

    resp = await authed_client_owner.get(
        f"/api/v1/memberships?expiring=true&clientId={client_uuid}&pageSize=100"
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()["data"]
    # Three rows in window (today, today+3, today+6); today+7 excluded.
    assert body["total"] == 3
    end_dates = sorted(item["endDate"] for item in body["items"])
    assert end_dates[0] == today.isoformat()
    assert end_dates[-1] == (today + timedelta(days=6)).isoformat()
    # Inclusive boundary at today+6 must appear:
    assert (today + timedelta(days=6)).isoformat() in end_dates
    # Exclusive boundary at today+7 must NOT appear:
    assert (today + timedelta(days=7)).isoformat() not in end_dates


# --- Happy path: explicit within=14 (inclusive boundary) -------------------


@pytest.mark.asyncio
async def test_list_expiring_within_14(
    authed_client_owner: AsyncClient,
    make_plan: Any,
    make_membership: Any,
) -> None:
    """within=14: end_date == today+13 IS included; today+14 excluded
    (within=14 -> today + (14 - 1) = today + 13 inclusive cap)."""
    today = _msk_today()
    plan = await make_plan(name="14d window")
    client = await _create_client(authed_client_owner, phone="+79990002002")
    client_uuid = UUID(client["id"])

    await make_membership(
        client_id=client_uuid,
        plan=plan,
        status="active",
        start_date=today - timedelta(days=60),
        end_date=today + timedelta(days=13),
    )
    await make_membership(
        client_id=client_uuid,
        plan=plan,
        status="active",
        start_date=today - timedelta(days=60),
        end_date=today + timedelta(days=14),
    )
    resp = await authed_client_owner.get(
        f"/api/v1/memberships?expiring=true&within=14&clientId={client_uuid}&pageSize=100"
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()["data"]
    assert body["total"] == 1
    assert body["items"][0]["endDate"] == (today + timedelta(days=13)).isoformat()


# --- Pydantic bound rejections ---------------------------------------------


@pytest.mark.asyncio
async def test_list_expiring_within_too_low_returns_422(
    authed_client_owner: AsyncClient,
) -> None:
    resp = await authed_client_owner.get("/api/v1/memberships?expiring=true&within=0")
    assert resp.status_code == 422, resp.text


@pytest.mark.asyncio
async def test_list_expiring_within_too_high_returns_422(
    authed_client_owner: AsyncClient,
) -> None:
    resp = await authed_client_owner.get("/api/v1/memberships?expiring=true&within=31")
    assert resp.status_code == 422, resp.text


# --- Status forcing: only active rows returned -----------------------------


@pytest.mark.asyncio
async def test_list_expiring_excludes_non_active(
    authed_client_owner: AsyncClient,
    make_plan: Any,
    make_membership: Any,
) -> None:
    """Only status='active' rows are returned, even if other statuses fall in the date window.

    NOTE Phase 24 status taxonomy after INFRA-16 still includes 'frozen' as a
    valid status string (CHECK extended in 0007). This test covers expired and
    cancelled (the canonical non-active statuses); 'frozen' lifecycle wiring
    lands in Phase 25.
    """
    today = _msk_today()
    plan = await make_plan(name="Status filter")
    client = await _create_client(authed_client_owner, phone="+79990002003")
    client_uuid = UUID(client["id"])

    # All three have end_date inside the default 7d window:
    await make_membership(
        client_id=client_uuid,
        plan=plan,
        status="expired",
        start_date=today - timedelta(days=30),
        end_date=today + timedelta(days=3),
    )
    await make_membership(
        client_id=client_uuid,
        plan=plan,
        status="cancelled",
        start_date=today - timedelta(days=30),
        end_date=today + timedelta(days=3),
    )
    await make_membership(
        client_id=client_uuid,
        plan=plan,
        status="active",
        start_date=today - timedelta(days=30),
        end_date=today + timedelta(days=3),
    )
    resp = await authed_client_owner.get(
        f"/api/v1/memberships?expiring=true&clientId={client_uuid}&pageSize=100"
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()["data"]
    assert body["total"] == 1
    assert body["items"][0]["status"] == "active"


# --- Conflict: expiring=true + status=non-active ---------------------------


@pytest.mark.asyncio
async def test_list_expiring_status_conflict_returns_422(
    authed_client_owner: AsyncClient,
) -> None:
    """expiring=true + status=expired -> 422 query_invalid with discriminating field.

    Conflict envelope is the flat AppError shape (core/exceptions.py:243-256):
    `{"code": ..., "message": ..., "fields": ...}` — NOT nested under
    `body["error"]`.
    """
    resp = await authed_client_owner.get(
        "/api/v1/memberships?expiring=true&status=expired"
    )
    assert resp.status_code == 422, resp.text
    body = resp.json()
    assert body["code"] == "query_invalid"
    assert body["fields"]["status"] == "incompatible_with_expiring"


@pytest.mark.asyncio
async def test_list_expiring_with_status_active_is_ok(
    authed_client_owner: AsyncClient,
    make_plan: Any,
    make_membership: Any,
) -> None:
    """expiring=true + status=active is allowed (status matches the forced predicate)."""
    today = _msk_today()
    plan = await make_plan(name="active+expiring")
    client = await _create_client(authed_client_owner, phone="+79990002004")
    client_uuid = UUID(client["id"])

    await make_membership(
        client_id=client_uuid,
        plan=plan,
        status="active",
        start_date=today - timedelta(days=30),
        end_date=today + timedelta(days=2),
    )
    resp = await authed_client_owner.get(
        f"/api/v1/memberships?expiring=true&status=active&clientId={client_uuid}&pageSize=100"
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()["data"]
    assert body["total"] == 1


# --- expiring=false ignores `within` silently ------------------------------


@pytest.mark.asyncio
async def test_list_non_expiring_ignores_within(
    authed_client_owner: AsyncClient,
    make_plan: Any,
    make_membership: Any,
) -> None:
    """expiring=false: `within` is silently ignored (no date predicate added)."""
    today = _msk_today()
    plan = await make_plan(name="non-expiring")
    client = await _create_client(authed_client_owner, phone="+79990002005")
    client_uuid = UUID(client["id"])

    # end_date well outside any 1..30 window:
    await make_membership(
        client_id=client_uuid,
        plan=plan,
        status="active",
        start_date=today - timedelta(days=30),
        end_date=today + timedelta(days=180),
    )
    resp = await authed_client_owner.get(
        f"/api/v1/memberships?within=14&clientId={client_uuid}&pageSize=100"
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()["data"]
    # The far-future-end-date row is returned because `within` is ignored when expiring=false.
    assert body["total"] >= 1
    assert any(
        item["endDate"] == (today + timedelta(days=180)).isoformat()
        for item in body["items"]
    )


# --- Pagination envelope intact (no BLK-06 collapse on backend) -----------


@pytest.mark.asyncio
async def test_list_expiring_pagination_envelope_intact(
    authed_client_owner: AsyncClient,
    make_plan: Any,
    make_membership: Any,
) -> None:
    """Backend paginates the filtered set honestly — no BLK-06 single-page collapse.

    Seeds 25 active rows with end_date inside the 7d window (today + i % 7 for
    i in 0..24), pages with pageSize=10, asserts the envelope reports total=25
    and only 10 items on the page.
    """
    today = _msk_today()
    plan = await make_plan(name="Pagination Test")
    client = await _create_client(authed_client_owner, phone="+79990002006")
    client_uuid = UUID(client["id"])

    for i in range(25):
        await make_membership(
            client_id=client_uuid,
            plan=plan,
            status="active",
            start_date=today - timedelta(days=30),
            end_date=today + timedelta(days=i % 7),
        )
    resp = await authed_client_owner.get(
        f"/api/v1/memberships?expiring=true&clientId={client_uuid}&pageSize=10&page=1"
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()["data"]
    assert body["total"] == 25
    assert body["pageSize"] == 10
    assert body["page"] == 1
    assert len(body["items"]) == 10
