"""Phase 113 PROMO-01/PROMO-02 RBAC + CSRF guard integration tests.

Coverage (mirrors users/test_users_guards.py structure):
  (1) reception 403 on create — POST /api/v1/promo-codes → 403 forbidden
  (2) reception 403 on edit   — PATCH /{id} → 403 forbidden
  (3) reception 403 on deactivate — PATCH /{id}/deactivate → 403 forbidden
  (4) reception CAN list     — GET /api/v1/promo-codes → 200 (locked: reception retains LIST/VIEW)
  (5) CSRF-missing 403       — owner POST without X-CSRF-Token → 403 csrf_mismatch
  (6) owner CAN write        — sanity: owner POST with CSRF → 201 (proves the 403s above
                               are role/CSRF-driven, not a broken route)

RBAC-04 ordering (promo_codes/router.py): require_permission fires BEFORE verify_csrf
in every write endpoint signature — so reception hits 403 (forbidden) before CSRF fires,
and owner with missing CSRF hits 403 (csrf_mismatch) after RBAC passes.

Error-body convention (app/core/exceptions.py): AppError handler returns
``{"code","message","fields"}`` at TOP level. All assertions use ``r.json()["code"]``.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable

import pytest
from httpx import AsyncClient

from app.modules.promo_codes.models import PromoCode
from tests.integration.promo_codes.conftest import _csrf_headers

pytestmark = pytest.mark.asyncio

# ---------------------------------------------------------------------------
# Valid promo-code body reused across multiple tests
# ---------------------------------------------------------------------------

_VALID_CREATE_BODY = {
    "code": "RBACTEST",
    "discountType": "percentage",
    "discountValue": 500,  # 5%
}


# ---------------------------------------------------------------------------
# (1) Reception 403 on create
# ---------------------------------------------------------------------------


async def test_reception_cannot_create_promo_code_403(
    authed_client_reception: AsyncClient,
) -> None:
    """PROMO-01 — reception POST → 403 forbidden (OWNER_ONLY pair CREATE,PROMO_CODES)."""
    r = await authed_client_reception.post(
        "/api/v1/promo-codes",
        json=_VALID_CREATE_BODY,
        headers=_csrf_headers(authed_client_reception),
    )
    assert r.status_code == 403, r.text
    assert r.json()["code"] == "forbidden"


# ---------------------------------------------------------------------------
# (2) Reception 403 on edit
# ---------------------------------------------------------------------------


async def test_reception_cannot_edit_promo_code_403(
    authed_client_reception: AsyncClient,
    make_promo_code: Callable[..., Awaitable[PromoCode]],
) -> None:
    """PROMO-01 — reception PATCH /{id} → 403 forbidden (OWNER_ONLY pair EDIT,PROMO_CODES)."""
    promo = await make_promo_code(code="EDITRBAC")
    r = await authed_client_reception.patch(
        f"/api/v1/promo-codes/{promo.id}",
        json={"description": "should not land"},
        headers=_csrf_headers(authed_client_reception),
    )
    assert r.status_code == 403, r.text
    assert r.json()["code"] == "forbidden"


# ---------------------------------------------------------------------------
# (3) Reception 403 on deactivate
# ---------------------------------------------------------------------------


async def test_reception_cannot_deactivate_promo_code_403(
    authed_client_reception: AsyncClient,
    make_promo_code: Callable[..., Awaitable[PromoCode]],
) -> None:
    """PROMO-01 — reception PATCH /{id}/deactivate → 403 forbidden
    (OWNER_ONLY pair DELETE,PROMO_CODES — deactivate maps to DELETE action).
    """
    promo = await make_promo_code(code="DEACRBAC")
    r = await authed_client_reception.patch(
        f"/api/v1/promo-codes/{promo.id}/deactivate",
        headers=_csrf_headers(authed_client_reception),
    )
    assert r.status_code == 403, r.text
    assert r.json()["code"] == "forbidden"


# ---------------------------------------------------------------------------
# (4) Reception CAN list (locked: LIST/VIEW not in OWNER_ONLY)
# ---------------------------------------------------------------------------


async def test_reception_can_list_promo_codes_200(
    authed_client_reception: AsyncClient,
) -> None:
    """PROMO-02 — reception GET /api/v1/promo-codes → 200 with data envelope.

    (Action.LIST, Resource.PROMO_CODES) is NOT in OWNER_ONLY — reception
    retains read-only list access (113-CONTEXT.md RBAC decision).
    """
    r = await authed_client_reception.get("/api/v1/promo-codes")
    assert r.status_code == 200, r.text
    body = r.json()
    assert "data" in body
    assert "items" in body["data"]


# ---------------------------------------------------------------------------
# (5) CSRF-missing 403 — csrf_mismatch
# ---------------------------------------------------------------------------


async def test_create_missing_csrf_returns_403_csrf_mismatch(
    authed_client_owner: AsyncClient,
) -> None:
    """PROMO-01 — owner POST without X-CSRF-Token → 403 csrf_mismatch.

    RBAC-04 ordering (promo_codes/router.py): require_permission fires first
    (passes for owner), then verify_csrf fires and raises CsrfMismatch because
    the header is absent. Response code == 'csrf_mismatch'.
    """
    r = await authed_client_owner.post(
        "/api/v1/promo-codes",
        json={
            "code": "NOCSRF",
            "discountType": "percentage",
            "discountValue": 500,
        },
        # NB: no _csrf_headers(authed_client_owner) — verify_csrf must fire.
    )
    assert r.status_code == 403, r.text
    assert r.json()["code"] == "csrf_mismatch"


# ---------------------------------------------------------------------------
# (6) Owner CAN write — sanity guard
# ---------------------------------------------------------------------------


async def test_owner_can_create_promo_code_201(
    authed_client_owner: AsyncClient,
) -> None:
    """PROMO-01 — owner POST with CSRF → 201 (proves the 403s above are role/CSRF-driven)."""
    r = await authed_client_owner.post(
        "/api/v1/promo-codes",
        json={
            "code": "OWNERCAN",
            "discountType": "fixed",
            "discountValue": 10000,  # 100 ₽ in kopecks
        },
        headers=_csrf_headers(authed_client_owner),
    )
    assert r.status_code == 201, r.text
    assert r.json()["data"]["code"] == "OWNERCAN"
