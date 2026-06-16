"""Phase 117 Plan 02 Task 1 — Capture real refund response (D-V32-DRIFT-LESSON).

Hits POST /api/v1/payments/{payment_id}/refund with a real seeded payment via
ASGITransport, serializes the actual JSON response to the shared FE fixtures dir:
  apps/admin/src/features/payments/capture/refund-response.json

The captured JSON is then parsed by the FE vitest contract test
(features/payments/refund.contract.test.ts) using the REAL FE Zod PaymentSchema.

Seed helper: _seed_sale_payment from test_payments_arbitrary_refund.py (reused inline).
"""

from __future__ import annotations

import json
import pathlib
from typing import Any
from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio(loop_scope="function")

# ---------------------------------------------------------------------------
# Shared fixtures dir (relative to repo root, resolved from this file's location)
# tests/integration/payments/ → parents[5] = repo root
# ---------------------------------------------------------------------------

_REPO_ROOT = pathlib.Path(__file__).resolve().parents[5]
FIXTURES_DIR = _REPO_ROOT / "apps/admin/src/features/payments/capture"


# ---------------------------------------------------------------------------
# Helpers (mirror test_payments_arbitrary_refund.py)
# ---------------------------------------------------------------------------


def _csrf_headers(client: AsyncClient) -> dict[str, str]:
    """CSRF header for mutating requests."""
    return {"X-CSRF-Token": client.cookies.get("clubcore_csrf") or ""}


def _sale_headers(client: AsyncClient) -> dict[str, str]:
    """Headers for membership sale POST (Idempotency-Key required since Phase 66)."""
    return {
        "X-CSRF-Token": client.cookies.get("clubcore_csrf") or "",
        "Idempotency-Key": uuid4().hex,
    }


async def _seed_sale_payment(
    authed: AsyncClient,
    *,
    make_plan: Any,
    make_client: Any,
    phone_suffix: str,
) -> tuple[UUID, UUID]:
    """Seed a membership sale via HTTP; return (membership_id, sale_payment_id)."""
    plan = await make_plan(name=f"CapturePlan-{phone_suffix}-{uuid4().hex[:6]}")
    client = await make_client(phone=f"+7991{phone_suffix}")
    r = await authed.post(
        "/api/v1/memberships",
        json={"clientId": str(client.id), "planId": str(plan.id)},
        headers=_sale_headers(authed),
    )
    assert r.status_code == 201, r.text
    membership_id = UUID(r.json()["data"]["id"])

    r2 = await authed.get(f"/api/v1/payments/by-membership/{membership_id}")
    assert r2.status_code == 200, r2.text
    items = r2.json()["data"]["items"]
    sale_rows = [p for p in items if p["subjectKind"] == "membership" and p["amountKopecks"] > 0]
    assert len(sale_rows) == 1, f"Expected 1 sale row, got: {items}"
    payment_id = UUID(sale_rows[0]["id"])
    return membership_id, payment_id


# ---------------------------------------------------------------------------
# Capture test — serialize REAL refund response to shared FE fixture
# ---------------------------------------------------------------------------


async def test_capture_refund_response(
    authed_client_owner: AsyncClient,
    make_plan: Any,
    make_client: Any,
) -> None:
    """POST /api/v1/payments/{id}/refund → 201; serialize r.json() to capture dir.

    The captured JSON is the source of truth for the FE contract test.
    """
    membership_id, payment_id = await _seed_sale_payment(
        authed_client_owner,
        make_plan=make_plan,
        make_client=make_client,
        phone_suffix="1170201",
    )

    r_orig = await authed_client_owner.get(f"/api/v1/payments/by-membership/{membership_id}")
    orig_amount = r_orig.json()["data"]["items"][0]["amountKopecks"]

    r = await authed_client_owner.post(
        f"/api/v1/payments/{payment_id}/refund",
        json={"amountKopecks": orig_amount, "reason": "capture test refund"},
        headers=_csrf_headers(authed_client_owner),
    )
    assert r.status_code == 201, r.text

    # Stable field assertion — test fails loudly if the response shape collapses.
    data = r.json()["data"]
    assert data["subjectKind"] == "refund", f"Expected subjectKind='refund', got: {data}"
    assert data["amountKopecks"] < 0, (
        f"Refund amount must be negative, got: {data['amountKopecks']}"
    )
    assert data["refundOf"] == str(payment_id), f"refundOf mismatch: {data}"

    # Verify captured path is inside repo root before writing.
    assert str(FIXTURES_DIR).startswith(str(_REPO_ROOT)), (
        f"FIXTURES_DIR {FIXTURES_DIR} is outside the repo root {_REPO_ROOT}"
    )

    FIXTURES_DIR.mkdir(parents=True, exist_ok=True)
    (FIXTURES_DIR / "refund-response.json").write_text(
        json.dumps(r.json(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
