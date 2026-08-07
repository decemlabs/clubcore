"""Phase 113 PROMO-01/02 CRUD behavior integration tests.

Tests parse REAL backend response shapes to close the mock↔real drift gap
per D-V32-DRIFT-LESSON. No mock fixtures — every assertion is against the
live ASGITransport backend response.

Coverage:
  (1) create happy — percentage discount, UPPER-normalization, usedCount absent in
      create response (PromoCodeResponse has no usedCount; only list does)
  (2) create fixed-discount happy
  (3) duplicate alive conflict → 409 promo_code_already_exists
  (4) invalid discount → 422 (zero and over-100% percentage)
  (5) edit happy — PATCH updates description + maxUses
  (6) edit not-found → 404 promo_code_not_found
  (7) deactivate happy — 204, then list shows isActive=False
  (8) list pagination envelope shape — data.{items,total,page,pageSize}
  (9) used_count aggregate — make_redemption x2 → list item usedCount == 2

Error-body convention (app/core/exceptions.py): AppError handler returns
``{"code","message","fields"}`` at TOP level (not under ``detail``).
All assertions use ``r.json()["code"]``.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient

from app.modules.promo_codes.models import PromoCode, PromoRedemption
from tests.integration.promo_codes.conftest import _csrf_headers

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# (1) Create happy — percentage discount, UPPER-normalization
# ---------------------------------------------------------------------------


async def test_create_percentage_happy_returns_201_and_normalizes_code(
    authed_client_owner: AsyncClient,
) -> None:
    """PROMO-01 — create percentage promo code, UPPER-normalize code, usedCount absent."""
    r = await authed_client_owner.post(
        "/api/v1/promo-codes",
        json={
            "code": "summer25",
            "discountType": "percentage",
            "discountValue": 1000,  # 10%
            "maxUses": 100,
            "description": "Летняя скидка",
        },
        headers=_csrf_headers(authed_client_owner),
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert "data" in body
    data = body["data"]
    # UPPER-normalization: 'summer25' → 'SUMMER25'
    assert data["code"] == "SUMMER25"
    assert data["discountType"] == "percentage"
    assert data["discountValue"] == 1000
    assert data["maxUses"] == 100
    assert data["description"] == "Летняя скидка"
    assert data["isActive"] is True
    # PromoCodeResponse does NOT expose usedCount — it's a list-only aggregate.
    assert "usedCount" not in data
    # id must be a valid UUID
    _ = UUID(data["id"])


# ---------------------------------------------------------------------------
# (2) Create fixed-discount happy
# ---------------------------------------------------------------------------


async def test_create_fixed_discount_happy_returns_201(
    authed_client_owner: AsyncClient,
) -> None:
    """PROMO-01 — create fixed-kopecks promo code returns 201 + persisted."""
    r = await authed_client_owner.post(
        "/api/v1/promo-codes",
        json={
            "code": "FIXED500",
            "discountType": "fixed",
            "discountValue": 50000,  # 500 ₽ in kopecks
        },
        headers=_csrf_headers(authed_client_owner),
    )
    assert r.status_code == 201, r.text
    data = r.json()["data"]
    assert data["code"] == "FIXED500"
    assert data["discountType"] == "fixed"
    assert data["discountValue"] == 50000
    assert data["isActive"] is True


# ---------------------------------------------------------------------------
# (3) Duplicate alive conflict → 409 promo_code_already_exists
# ---------------------------------------------------------------------------


async def test_create_duplicate_alive_code_returns_409(
    authed_client_owner: AsyncClient,
) -> None:
    """PROMO-01 — second POST with the same code (case-insensitive) → 409 conflict."""
    # First create succeeds.
    r1 = await authed_client_owner.post(
        "/api/v1/promo-codes",
        json={"code": "DUP", "discountType": "percentage", "discountValue": 500},
        headers=_csrf_headers(authed_client_owner),
    )
    assert r1.status_code == 201, r1.text

    # Second create with lowercase variant → same UPPER('dup') == 'DUP' → alive conflict.
    r2 = await authed_client_owner.post(
        "/api/v1/promo-codes",
        json={"code": "dup", "discountType": "percentage", "discountValue": 500},
        headers=_csrf_headers(authed_client_owner),
    )
    assert r2.status_code == 409, r2.text
    assert r2.json()["code"] == "promo_code_already_exists"


# ---------------------------------------------------------------------------
# (4) Invalid discount → 422
# ---------------------------------------------------------------------------


async def test_create_zero_discount_value_returns_422(
    authed_client_owner: AsyncClient,
) -> None:
    """PROMO-01 — discountValue=0 violates > 0 validator → 422."""
    r = await authed_client_owner.post(
        "/api/v1/promo-codes",
        json={"code": "ZEROVAL", "discountType": "percentage", "discountValue": 0},
        headers=_csrf_headers(authed_client_owner),
    )
    assert r.status_code == 422, r.text


async def test_create_percentage_over_100_returns_422(
    authed_client_owner: AsyncClient,
) -> None:
    """PROMO-01 — percentage discountValue > 10000 (>100%) → 422."""
    r = await authed_client_owner.post(
        "/api/v1/promo-codes",
        json={
            "code": "OVER100",
            "discountType": "percentage",
            "discountValue": 15000,  # 150% — invalid
        },
        headers=_csrf_headers(authed_client_owner),
    )
    assert r.status_code == 422, r.text


# ---------------------------------------------------------------------------
# (5) Edit happy — PATCH updates description + maxUses
# ---------------------------------------------------------------------------


async def test_edit_promo_code_happy_returns_200(
    authed_client_owner: AsyncClient,
    make_promo_code: Callable[..., Awaitable[PromoCode]],
) -> None:
    """PROMO-01 — PATCH /{id} updates fields; returns 200 with updated data."""
    promo = await make_promo_code(code="EDITME", discount_value=2000, description="old")
    promo_id = str(promo.id)

    r = await authed_client_owner.patch(
        f"/api/v1/promo-codes/{promo_id}",
        json={"description": "new desc", "maxUses": 5},
        headers=_csrf_headers(authed_client_owner),
    )
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert data["description"] == "new desc"
    assert data["maxUses"] == 5
    assert data["code"] == "EDITME"


# ---------------------------------------------------------------------------
# (6) Edit not-found → 404 promo_code_not_found
# ---------------------------------------------------------------------------


async def test_edit_nonexistent_promo_code_returns_404(
    authed_client_owner: AsyncClient,
) -> None:
    """PROMO-01 — PATCH on unknown UUID → 404 promo_code_not_found."""
    r = await authed_client_owner.patch(
        f"/api/v1/promo-codes/{uuid4()}",
        json={"description": "irrelevant"},
        headers=_csrf_headers(authed_client_owner),
    )
    assert r.status_code == 404, r.text
    assert r.json()["code"] == "promo_code_not_found"


# ---------------------------------------------------------------------------
# (7) Deactivate happy — 204, then list shows isActive=False
# ---------------------------------------------------------------------------


async def test_deactivate_promo_code_happy_returns_204(
    authed_client_owner: AsyncClient,
    make_promo_code: Callable[..., Awaitable[PromoCode]],
) -> None:
    """PROMO-01 — PATCH /{id}/deactivate returns 204; list shows isActive=False."""
    promo = await make_promo_code(code="DEACTVME")
    promo_id = str(promo.id)

    r = await authed_client_owner.patch(
        f"/api/v1/promo-codes/{promo_id}/deactivate",
        headers=_csrf_headers(authed_client_owner),
    )
    assert r.status_code == 204, r.text

    # Verify via list (active=false filter to narrow results)
    r_list = await authed_client_owner.get(
        "/api/v1/promo-codes",
        params={"active": "false"},
    )
    assert r_list.status_code == 200, r_list.text
    items = r_list.json()["data"]["items"]
    matching = [item for item in items if item["id"] == promo_id]
    assert len(matching) == 1, f"deactivated promo not found in list: {promo_id}"
    assert matching[0]["isActive"] is False


# ---------------------------------------------------------------------------
# (8) List pagination envelope shape
# ---------------------------------------------------------------------------


async def test_list_pagination_envelope_shape(
    authed_client_owner: AsyncClient,
    make_promo_code: Callable[..., Awaitable[PromoCode]],
) -> None:
    """PROMO-02 — GET list returns {data:{items,total,page,pageSize}} envelope."""
    # Seed 2 codes deterministically.
    await make_promo_code(code="LISTTEST1")
    await make_promo_code(code="LISTTEST2")

    r = await authed_client_owner.get("/api/v1/promo-codes", params={"page": 1, "pageSize": 20})
    assert r.status_code == 200, r.text
    body = r.json()
    assert "data" in body
    data = body["data"]
    # Required envelope keys (camelCase per PaginatedData ResponseData alias_generator).
    assert {"items", "total", "page", "pageSize"}.issubset(data.keys()), (
        f"Missing pagination keys: {set(data.keys())}"
    )
    assert data["total"] >= 2
    assert isinstance(data["items"], list)
    assert data["page"] == 1
    # Each item must have the expected keys (camelCase).
    for item in data["items"]:
        for key in ("id", "code", "discountType", "discountValue", "isActive", "usedCount"):
            assert key in item, f"Missing key {key!r} in list item"


# ---------------------------------------------------------------------------
# (9) used_count aggregate — THE real-backend contract test for this domain
# ---------------------------------------------------------------------------


async def test_used_count_reflects_promo_redemptions(
    authed_client_owner: AsyncClient,
    make_promo_code: Callable[..., Awaitable[PromoCode]],
    make_redemption: Callable[..., Awaitable[PromoRedemption]],
    make_client: Callable[..., Awaitable[object]],
) -> None:
    """PROMO-02 — usedCount in list equals the count of promo_redemptions rows.

    This is the D-V32-DRIFT-LESSON contract test: parses the REAL backend list
    response and asserts the correlated subquery aggregate is wired correctly.
    """
    promo = await make_promo_code(code="UCTEST")
    client = await make_client()

    # Insert 2 redemptions for this promo code.
    await make_redemption(promo_code_id=promo.id, client_id=client.id)
    await make_redemption(promo_code_id=promo.id, client_id=client.id)

    r = await authed_client_owner.get("/api/v1/promo-codes", params={"page": 1, "pageSize": 50})
    assert r.status_code == 200, r.text
    items = r.json()["data"]["items"]

    promo_id_str = str(promo.id)
    matching = [item for item in items if item["id"] == promo_id_str]
    assert len(matching) == 1, f"Promo {promo_id_str} not found in list response"
    assert matching[0]["usedCount"] == 2, (
        f"Expected usedCount=2, got {matching[0]['usedCount']} "
        f"(real backend correlated subquery aggregate)"
    )


# ---------------------------------------------------------------------------
# (10) WR-01 — update path enforces the percentage <= 100% cap
# ---------------------------------------------------------------------------


async def test_update_percentage_over_100_returns_422(
    authed_client_owner: AsyncClient,
    make_promo_code: Callable[..., Awaitable[PromoCode]],
) -> None:
    """WR-01 — PATCH a percentage promo to discountValue > 10000 (>100%) → 422."""
    promo = await make_promo_code(code="WR01CAP", discount_type="percentage", discount_value=1000)
    r = await authed_client_owner.patch(
        f"/api/v1/promo-codes/{promo.id}",
        json={"discountValue": 50000},  # 500% — must be rejected on update too
        headers=_csrf_headers(authed_client_owner),
    )
    assert r.status_code == 422, r.text


# ---------------------------------------------------------------------------
# (11) WR-03 — changing discount_type re-validates the merged discount_value
# ---------------------------------------------------------------------------


async def test_update_type_change_revalidates_existing_value_returns_422(
    authed_client_owner: AsyncClient,
    make_promo_code: Callable[..., Awaitable[PromoCode]],
) -> None:
    """WR-03 — flip a fixed(50000 kopecks) promo to percentage WITHOUT a new
    value: the merged effective value (50000 = 500%) exceeds the cap → 422."""
    promo = await make_promo_code(code="WR03FLIP", discount_type="fixed", discount_value=50000)
    r = await authed_client_owner.patch(
        f"/api/v1/promo-codes/{promo.id}",
        json={"discountType": "percentage"},  # value omitted; effective = 50000
        headers=_csrf_headers(authed_client_owner),
    )
    assert r.status_code == 422, r.text


# ---------------------------------------------------------------------------
# (12) WR-02 — validity-window validation (create + update)
# ---------------------------------------------------------------------------


async def test_create_valid_until_before_valid_from_returns_422(
    authed_client_owner: AsyncClient,
) -> None:
    """WR-02 — create with valid_until < valid_from → 422."""
    r = await authed_client_owner.post(
        "/api/v1/promo-codes",
        json={
            "code": "BADWINDOW",
            "discountType": "percentage",
            "discountValue": 1000,
            "validFrom": "2026-12-01T00:00:00Z",
            "validUntil": "2026-01-01T00:00:00Z",  # before validFrom
        },
        headers=_csrf_headers(authed_client_owner),
    )
    assert r.status_code == 422, r.text


async def test_update_valid_until_before_existing_valid_from_returns_422(
    authed_client_owner: AsyncClient,
    make_promo_code: Callable[..., Awaitable[PromoCode]],
) -> None:
    """WR-02 — PATCH a valid_until that precedes the EXISTING valid_from → 422."""
    promo = await make_promo_code(code="WINDOWPATCH")
    # First set a valid_from in the future.
    r1 = await authed_client_owner.patch(
        f"/api/v1/promo-codes/{promo.id}",
        json={"validFrom": "2026-12-01T00:00:00Z"},
        headers=_csrf_headers(authed_client_owner),
    )
    assert r1.status_code == 200, r1.text
    # Now PATCH only valid_until to before the stored valid_from → merged window invalid.
    r2 = await authed_client_owner.patch(
        f"/api/v1/promo-codes/{promo.id}",
        json={"validUntil": "2026-01-01T00:00:00Z"},
        headers=_csrf_headers(authed_client_owner),
    )
    assert r2.status_code == 422, r2.text
