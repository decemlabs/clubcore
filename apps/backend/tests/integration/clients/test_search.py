"""Integration regression tests for /api/v1/clients?q=... — Phase 14 (CR-01).

Plan 14-01 introduced `_escape_like_pattern` so that SQL LIKE
metacharacters (`%`, `_`, `\\`) inside the user-supplied `q` are matched
as literals instead of as wildcards. Before that fix, a reception user
could craft a `q` containing `%` and the resulting ILIKE pattern would
expand the user's `%` as a wildcard — leaking the full PII roster
(Phase 8 CR-01).

Mechanism note for the percent-literal tests below:
`ClientListQuery._normalise_q` (schemas.py:253-262) drops any `q` shorter
than 2 chars to None, so a bare `?q=%` (1 char) is filtered out by the
normaliser BEFORE reaching the ILIKE branch — it returns every alive
client because the filter is skipped, NOT because `%` is a wildcard.
That is a different code path and does not exercise CR-01. To
reproduce / regression-test the actual wildcard-expansion bug, the query
must be ≥ 2 chars AND contain a LIKE metacharacter. We use `"%a"` here.

These tests pin the post-fix behaviour from the HTTP boundary down
through the service → repository → Postgres stack via httpx
ASGITransport, the same way `test_clients_list.py` does.
"""

from __future__ import annotations

from typing import Any

from httpx import AsyncClient


def _csrf_headers(client: AsyncClient) -> dict[str, str]:
    """Echo the sportzal_csrf cookie value as X-CSRF-Token (D-09)."""
    token = client.cookies.get("sportzal_csrf") or ""
    return {"X-CSRF-Token": token}


async def _create(
    authed_client_owner: AsyncClient,
    *,
    last_name: str,
    phone: str,
    first_name: str = "Иван",
) -> dict[str, Any]:
    """POST a client and return its response data (asserts 201)."""
    payload: dict[str, Any] = {
        "lastName": last_name,
        "firstName": first_name,
        "phone": phone,
    }
    r = await authed_client_owner.post(
        "/api/v1/clients",
        json=payload,
        headers=_csrf_headers(authed_client_owner),
    )
    assert r.status_code == 201, r.text
    data: dict[str, Any] = r.json()["data"]
    return data


async def test_search_percent_literal_returns_zero_when_no_match(
    authed_client_owner: AsyncClient,
) -> None:
    """`?q=%a` MUST NOT match clients whose names lack the literal substring `%a`.

    Pre-fix (Phase 8): the ILIKE pattern was f"%{q.lower()}%" so q="%a"
    became `%%a%`. The leading `%` was a wildcard, reducing the pattern
    to "any row whose lowered name contains the letter `a`" — both
    Adams and Baker would leak (CR-01 PII over-exposure).

    Post-fix (Plan 14-01): the pattern is f"%{_escape_like_pattern(q.lower())}%"
    so q="%a" becomes `%\\%a%`. The `\\%` is a literal `%`, so the pattern
    now requires the contiguous substring `%a` in the name. Neither
    Adams nor Baker contains `%a` → total == 0.
    """
    await _create(authed_client_owner, last_name="Adams", phone="+79991111111")
    await _create(authed_client_owner, last_name="Baker", phone="+79992222222")

    r = await authed_client_owner.get("/api/v1/clients", params={"q": "%a"})
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert data["total"] == 0, f"expected 0 rows, got {data['total']}"
    assert data["items"] == []


async def test_search_percent_literal_matches_only_when_present(
    authed_client_owner: AsyncClient,
) -> None:
    """Literal `%a` substring in lastName MUST still substring-match `?q=%a`.

    Post-fix the ILIKE pattern is `%\\%a%` — it requires the contiguous
    substring `%a` somewhere in the lowered name. `100%apple` contains
    `%a` (between `100` and `pple`) and matches. `Adams` contains Latin
    `a` but no `%`, so the contiguous `%a` substring is absent and the
    row is correctly excluded — proving the escape narrows the match to
    literal substring without losing legitimate hits.
    """
    await _create(authed_client_owner, last_name="100%apple", phone="+79993333333")
    await _create(authed_client_owner, last_name="Adams", phone="+79991111111")

    r = await authed_client_owner.get("/api/v1/clients", params={"q": "%a"})
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert data["total"] == 1, f"expected 1 row, got {data['total']}"
    assert data["items"][0]["lastName"] == "100%apple"


async def test_search_underscore_is_literal_not_wildcard(
    authed_client_owner: AsyncClient,
) -> None:
    """`_test_` in `?q=` MUST match `_test_` literally, NOT `atestz`."""
    await _create(authed_client_owner, last_name="_test_", phone="+79995555555")
    await _create(authed_client_owner, last_name="atestz", phone="+79996666666")

    r = await authed_client_owner.get("/api/v1/clients", params={"q": "_test_"})
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert data["total"] == 1, f"expected 1 row, got {data['total']}"
    assert data["items"][0]["lastName"] == "_test_"


async def test_search_backslash_is_literal(
    authed_client_owner: AsyncClient,
) -> None:
    """Literal backslash in `q` MUST NOT cause escape-character confusion at SQL layer."""
    await _create(authed_client_owner, last_name="A\\B", phone="+79997777777")
    await _create(authed_client_owner, last_name="AB", phone="+79998888888")

    # In Python source, "A\\B" is the 3-char string A, \, B.
    r = await authed_client_owner.get("/api/v1/clients", params={"q": "A\\B"})
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert data["total"] == 1, f"expected 1 row, got {data['total']}"
    assert data["items"][0]["lastName"] == "A\\B"


async def test_search_plain_alphanumeric_still_matches(
    authed_client_owner: AsyncClient,
) -> None:
    """Regression guard for SC #4: plain substring match unchanged by the escape."""
    await _create(authed_client_owner, last_name="Иванов", phone="+79990000001")
    await _create(authed_client_owner, last_name="Иванова", phone="+79990000002")

    r = await authed_client_owner.get("/api/v1/clients", params={"q": "Иванов"})
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert data["total"] == 2, f"expected 2 rows, got {data['total']}"
    last_names = sorted(item["lastName"] for item in data["items"])
    assert last_names == ["Иванов", "Иванова"]
