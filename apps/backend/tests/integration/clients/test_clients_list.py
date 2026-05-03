"""Integration tests for GET /api/v1/clients (CLIENTS-03 + CLIENTS-04).

Covers q/tag/gender/dateRange/hasTelegram/sort/pagination semantics from
the PLAN, end-to-end via httpx ASGITransport. All tests use the
`authed_client_owner` fixture — owner has VIEW permission on every
resource so each list call is RBAC-allowed.
"""

from __future__ import annotations

from typing import Any

from httpx import AsyncClient


def _csrf_headers(client: AsyncClient) -> dict[str, str]:
    """Return X-CSRF-Token header echoing the sportzal_csrf cookie value (D-09)."""
    return {"X-CSRF-Token": client.cookies.get("sportzal_csrf", "")}


async def _create(
    authed_client_owner: AsyncClient,
    **overrides: Any,
) -> dict[str, Any]:
    """POST a client and return its response data (asserts 201)."""
    payload: dict[str, Any] = {
        "lastName": "Иванов",
        "firstName": "Иван",
        "phone": "+79991234567",
        **overrides,
    }
    r = await authed_client_owner.post(
        "/api/v1/clients",
        json=payload,
        headers=_csrf_headers(authed_client_owner),
    )
    assert r.status_code == 201, r.text
    data: dict[str, Any] = r.json()["data"]
    return data


async def test_list_returns_envelope_with_items_total_page_page_size(
    authed_client_owner: AsyncClient,
) -> None:
    """List response wraps items + total + page + pageSize (PLAN, API-04)."""
    await _create(authed_client_owner, lastName="A", phone="+79990000001")
    await _create(authed_client_owner, lastName="B", phone="+79990000002")
    await _create(authed_client_owner, lastName="C", phone="+79990000003")

    r = await authed_client_owner.get("/api/v1/clients")
    assert r.status_code == 200, r.text
    body = r.json()
    assert "data" in body
    data = body["data"]
    assert isinstance(data["items"], list)
    assert data["total"] == 3
    assert data["page"] == 1
    assert data["pageSize"] == 20


async def test_list_q_filter_matches_last_name_or_phone(
    authed_client_owner: AsyncClient,
) -> None:
    """`?q=` ILIKEs last_name OR phone (D-12)."""
    await _create(authed_client_owner, lastName="Иванов", phone="+79991234567")
    await _create(authed_client_owner, lastName="Петров", phone="+79995555555")

    r = await authed_client_owner.get("/api/v1/clients", params={"q": "иванов"})
    assert r.status_code == 200
    items = r.json()["data"]["items"]
    assert len(items) == 1
    assert items[0]["lastName"] == "Иванов"

    # `999` is a substring of both phones — both rows must come back.
    r2 = await authed_client_owner.get("/api/v1/clients", params={"q": "999"})
    assert r2.status_code == 200
    items2 = r2.json()["data"]["items"]
    assert len(items2) == 2


async def test_list_q_below_min_length_is_ignored(
    authed_client_owner: AsyncClient,
) -> None:
    """D-12: q < 2 chars is normalised to None — full list is returned."""
    await _create(authed_client_owner, lastName="A", phone="+79990000010")
    await _create(authed_client_owner, lastName="B", phone="+79990000011")

    r = await authed_client_owner.get("/api/v1/clients", params={"q": "a"})
    assert r.status_code == 200
    assert r.json()["data"]["total"] == 2


async def test_list_filter_by_tag_exact_match(
    authed_client_owner: AsyncClient,
) -> None:
    """D-13: `?tag=` exact ARRAY-contains match."""
    await _create(
        authed_client_owner,
        lastName="A",
        phone="+79990000020",
        tags=["vip", "gym"],
    )
    await _create(
        authed_client_owner,
        lastName="B",
        phone="+79990000021",
        tags=["gym"],
    )

    r = await authed_client_owner.get("/api/v1/clients", params={"tag": "vip"})
    assert r.json()["data"]["total"] == 1

    r = await authed_client_owner.get("/api/v1/clients", params={"tag": "gym"})
    assert r.json()["data"]["total"] == 2

    r = await authed_client_owner.get("/api/v1/clients", params={"tag": "missing"})
    assert r.json()["data"]["total"] == 0


async def test_list_filter_by_gender(
    authed_client_owner: AsyncClient,
) -> None:
    """D-14: `?gender=male|female` filters to one enum value."""
    await _create(
        authed_client_owner,
        lastName="M",
        phone="+79990000030",
        gender="male",
    )
    await _create(
        authed_client_owner,
        lastName="F",
        phone="+79990000031",
        gender="female",
    )
    await _create(authed_client_owner, lastName="N", phone="+79990000032")

    r = await authed_client_owner.get("/api/v1/clients", params={"gender": "male"})
    assert r.status_code == 200
    items = r.json()["data"]["items"]
    assert len(items) == 1
    assert items[0]["gender"] == "male"


async def test_list_filter_by_date_range_inclusive(
    authed_client_owner: AsyncClient,
) -> None:
    """D-14: createdFrom/createdTo inclusive on date-only inputs."""
    await _create(authed_client_owner, lastName="A", phone="+79990000040")

    r = await authed_client_owner.get(
        "/api/v1/clients",
        params={"createdFrom": "2026-01-01", "createdTo": "2099-12-31"},
    )
    assert r.json()["data"]["total"] == 1

    # Narrow window that excludes today
    r2 = await authed_client_owner.get(
        "/api/v1/clients",
        params={"createdFrom": "1990-01-01", "createdTo": "1990-12-31"},
    )
    assert r2.json()["data"]["total"] == 0


async def test_list_filter_by_has_telegram(
    authed_client_owner: AsyncClient,
) -> None:
    """D-14: hasTelegram=true|false filters by telegram_user_id IS NULL/NOT NULL."""
    await _create(
        authed_client_owner,
        lastName="With",
        phone="+79990000050",
        telegramUserId=123456,
    )
    await _create(authed_client_owner, lastName="Without", phone="+79990000051")

    r = await authed_client_owner.get(
        "/api/v1/clients", params={"hasTelegram": "true"}
    )
    assert r.json()["data"]["total"] == 1
    assert r.json()["data"]["items"][0]["telegramUserId"] == 123456

    r2 = await authed_client_owner.get(
        "/api/v1/clients", params={"hasTelegram": "false"}
    )
    assert r2.json()["data"]["total"] == 1
    assert r2.json()["data"]["items"][0]["telegramUserId"] is None


async def test_list_sort_default_is_created_at_desc(
    authed_client_owner: AsyncClient,
) -> None:
    """CLIENTS-04: default sort is `created_at DESC, id DESC` (Plan 04 matrix).

    Within a single Postgres transaction `func.now()` returns
    `transaction_timestamp()` (constant for the duration of the tx). The
    SAVEPOINT-rolled `db_session` fixture means every test runs inside one
    outer transaction, so two POSTs in the same test produce rows with
    *identical* `created_at`. The repository's `id DESC` tie-breaker is
    therefore the deciding factor and that's what we assert here:

      - items list is ordered by `(created_at, id)` descending.
      - For two rows sharing `created_at`, the larger UUID comes first.
    """
    a = await _create(authed_client_owner, lastName="A", phone="+79990000060")
    b = await _create(authed_client_owner, lastName="B", phone="+79990000061")

    r = await authed_client_owner.get("/api/v1/clients")
    items = r.json()["data"]["items"]
    assert len(items) == 2
    expected_first = max(a["id"], b["id"])
    expected_second = min(a["id"], b["id"])
    assert items[0]["id"] == expected_first, "id DESC tie-breaker on equal created_at"
    assert items[1]["id"] == expected_second


async def test_list_sort_last_name_asc(
    authed_client_owner: AsyncClient,
) -> None:
    """CLIENTS-04: ?sort=last_name_asc orders alphabetically by last_name."""
    await _create(authed_client_owner, lastName="Петров", phone="+79990000070")
    await _create(authed_client_owner, lastName="Иванов", phone="+79990000071")

    r = await authed_client_owner.get(
        "/api/v1/clients", params={"sort": "last_name_asc"}
    )
    items = r.json()["data"]["items"]
    assert items[0]["lastName"] == "Иванов"
    assert items[1]["lastName"] == "Петров"


async def test_list_pagination(
    authed_client_owner: AsyncClient,
) -> None:
    """D-10: pagination via `?page=&pageSize=` returns expected slice + counts."""
    for i in range(25):
        await _create(
            authed_client_owner,
            lastName=f"P{i:02d}",
            phone=f"+7999000{i:04d}",
        )

    r = await authed_client_owner.get(
        "/api/v1/clients", params={"page": 2, "pageSize": 10}
    )
    assert r.status_code == 200
    body = r.json()["data"]
    assert len(body["items"]) == 10
    assert body["page"] == 2
    assert body["pageSize"] == 10
    assert body["total"] == 25
