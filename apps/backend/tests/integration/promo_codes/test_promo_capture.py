"""Phase 117 Plan 02 Task 1 — Capture real promo codes list response (D-V32-DRIFT-LESSON).

Hits GET /api/v1/promo-codes via ASGITransport after seeding a promo code, serializes
the actual JSON response to the shared FE fixtures dir:
  apps/admin/src/features/promoCodes/capture/promo-codes-list-response.json

The captured JSON is then parsed by the FE vitest contract test
(features/promoCodes/promo.contract.test.ts) using the REAL FE Zod PromoCodesListResponseSchema.
"""

from __future__ import annotations

import json
import pathlib
from collections.abc import Awaitable, Callable

import pytest
from httpx import AsyncClient

from app.modules.promo_codes.models import PromoCode

pytestmark = pytest.mark.asyncio(loop_scope="function")

# ---------------------------------------------------------------------------
# Shared fixtures dir
# tests/integration/promo_codes/ → parents[5] = repo root
# ---------------------------------------------------------------------------

_REPO_ROOT = pathlib.Path(__file__).resolve().parents[5]
FIXTURES_DIR = _REPO_ROOT / "apps/admin/src/features/promoCodes/capture"


# ---------------------------------------------------------------------------
# Capture test — serialize REAL promo codes list response to shared FE fixture
# ---------------------------------------------------------------------------


async def test_capture_promo_codes_list_response(
    authed_client_owner: AsyncClient,
    make_promo_code: Callable[..., Awaitable[PromoCode]],
) -> None:
    """GET /api/v1/promo-codes → 200; serialize r.json() to capture dir.

    Seeds one promo code so the list always has at least one item.
    """
    # Seed a promo code via the conftest fixture.
    await make_promo_code(
        code="CAPTURE117",
        discount_type="percentage",
        discount_value=1000,  # 10%
        max_uses=50,
        description="117 capture test code",
    )

    r = await authed_client_owner.get("/api/v1/promo-codes")
    assert r.status_code == 200, r.text

    body = r.json()
    # Stable field assertions — test fails loudly if the response shape collapses.
    data = body["data"]
    assert "items" in data, f"Expected 'items' in data, got: {data}"
    assert "total" in data, f"Expected 'total' in data, got: {data}"
    assert isinstance(data["items"], list), f"items must be a list, got: {type(data['items'])}"

    # Verify the seeded code appears in the list.
    codes = [item["code"] for item in data["items"]]
    assert "CAPTURE117" in codes, f"Seeded code CAPTURE117 not in list: {codes}"

    # Verify captured path is inside repo root before writing.
    assert str(FIXTURES_DIR).startswith(str(_REPO_ROOT)), (
        f"FIXTURES_DIR {FIXTURES_DIR} is outside the repo root {_REPO_ROOT}"
    )

    FIXTURES_DIR.mkdir(parents=True, exist_ok=True)
    (FIXTURES_DIR / "promo-codes-list-response.json").write_text(
        json.dumps(body, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
