"""Integration tests for POST /api/v1/payments/{payment_id}/refund (Phase 112 REF-01).

Coverage:
  - Happy path (full amount): 201, new refund row, amount negative, refund_of == original id.
  - Partial refund (amount < original): 201, refund row amount == -(partial).
  - Over-refund (amount > original): 409 code "over_refund".
  - Second refund of same original: 409 code "already_refunded".
  - Refund of a refund row: 409 code "cannot_refund_refund".
  - Reception POST: 403 (RBAC; REFUND+FINANCE is OWNER_ONLY).
  - Owner POST without X-CSRF-Token: 403 csrf_mismatch.
  - Missing payment id: 404 original_payment_not_found.

All tests use SAVEPOINT-mode ``db_session`` fixtures + ASGITransport.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.payments.constants import SUBJECT_KIND_MEMBERSHIP, SUBJECT_KIND_REFUND
from app.modules.payments.models import Payment

pytestmark = pytest.mark.asyncio

# Re-use all fixtures from the payments conftest (authed_client_owner,
# authed_client_reception, make_plan, make_client, db_session, etc.)
# These are auto-imported via conftest.py in this directory.


# ─── helpers ────────────────────────────────────────────────────────────────


def _csrf_headers(client: AsyncClient) -> dict[str, str]:
    """CSRF header for mutating requests (no Idempotency-Key needed for refund)."""
    return {"X-CSRF-Token": client.cookies.get("clubcore_csrf") or ""}


def _sale_headers(client: AsyncClient) -> dict[str, str]:
    """Headers for a membership sale POST (Idempotency-Key required since Phase 66)."""
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
    amount_override: int | None = None,
) -> tuple[UUID, UUID]:
    """Seed a membership sale via HTTP so the payments ledger has a recorded row.

    Returns (membership_id, sale_payment_id).
    The plan price defaults to 250_000 kopecks; ``amount_override`` is not
    supported at the membership-sell HTTP level (price comes from the plan),
    but we keep the parameter slot for clarity.

    Uses the membership sell endpoint (the same path used by test_payments_refund.py)
    to prime the append-only ledger with a real payment row.
    """
    plan = await make_plan(name=f"RefPlan-{phone_suffix}-{uuid4().hex[:6]}")
    client = await make_client(phone=f"+7991{phone_suffix}")
    r = await authed.post(
        "/api/v1/memberships",
        json={"clientId": str(client.id), "planId": str(plan.id)},
        headers=_sale_headers(authed),
    )
    assert r.status_code == 201, r.text
    membership_id = UUID(r.json()["data"]["id"])

    # Resolve the payment row id from the DB (the HTTP response does not return it).
    # We use the authed client's db_session indirectly via the refund endpoint itself,
    # but we need the payment_id here. Query via the existing list-by-membership endpoint.
    r2 = await authed.get(f"/api/v1/payments/by-membership/{membership_id}")
    assert r2.status_code == 200, r2.text
    items = r2.json()["data"]["items"]
    sale_rows = [p for p in items if p["subjectKind"] == "membership" and p["amountKopecks"] > 0]
    assert len(sale_rows) == 1, f"Expected 1 sale row, got: {items}"
    payment_id = UUID(sale_rows[0]["id"])
    return membership_id, payment_id


# ─── happy path — full refund ────────────────────────────────────────────────


async def test_arbitrary_refund_full_amount_201(
    authed_client_owner: AsyncClient,
    db_session: AsyncSession,
    make_plan: Any,
    make_client: Any,
) -> None:
    """Owner refunds full sale amount → 201 + new refund row with negative amount."""
    membership_id, payment_id = await _seed_sale_payment(
        authed_client_owner,
        make_plan=make_plan,
        make_client=make_client,
        phone_suffix="3001234",
    )

    # Get original amount for assertion
    r_orig = await authed_client_owner.get(f"/api/v1/payments/by-membership/{membership_id}")
    orig_amount = r_orig.json()["data"]["items"][0]["amountKopecks"]

    r = await authed_client_owner.post(
        f"/api/v1/payments/{payment_id}/refund",
        json={"amountKopecks": orig_amount, "reason": "full refund test"},
        headers=_csrf_headers(authed_client_owner),
    )
    assert r.status_code == 201, r.text
    data = r.json()["data"]
    assert data["amountKopecks"] == -orig_amount
    assert data["refundOf"] == str(payment_id)
    assert data["subjectKind"] == "refund"

    # DB invariant: refund row inserted, original unchanged.
    payments = (
        (await db_session.execute(select(Payment).where(Payment.subject_id == membership_id)))
        .scalars()
        .all()
    )
    sale_rows = [p for p in payments if p.subject_kind == SUBJECT_KIND_MEMBERSHIP]
    refund_rows = [p for p in payments if p.subject_kind == SUBJECT_KIND_REFUND]
    assert len(sale_rows) == 1
    assert len(refund_rows) == 1
    assert refund_rows[0].amount_kopecks == -sale_rows[0].amount_kopecks
    assert refund_rows[0].refund_of == sale_rows[0].id
    # Append-only: original sale row amount unchanged (positive).
    assert sale_rows[0].amount_kopecks > 0


# ─── happy path — partial refund ─────────────────────────────────────────────


async def test_arbitrary_refund_partial_amount_201(
    authed_client_owner: AsyncClient,
    db_session: AsyncSession,
    make_plan: Any,
    make_client: Any,
) -> None:
    """Owner partial refund (amount < original) → 201, refund row amount == -(partial)."""
    membership_id, payment_id = await _seed_sale_payment(
        authed_client_owner,
        make_plan=make_plan,
        make_client=make_client,
        phone_suffix="3001235",
    )

    r_orig = await authed_client_owner.get(f"/api/v1/payments/by-membership/{membership_id}")
    orig_amount = r_orig.json()["data"]["items"][0]["amountKopecks"]
    partial = orig_amount // 2  # Half the original amount

    r = await authed_client_owner.post(
        f"/api/v1/payments/{payment_id}/refund",
        json={"amountKopecks": partial, "reason": "partial refund test"},
        headers=_csrf_headers(authed_client_owner),
    )
    assert r.status_code == 201, r.text
    data = r.json()["data"]
    assert data["amountKopecks"] == -partial
    assert data["refundOf"] == str(payment_id)


# ─── over-refund → 409 ───────────────────────────────────────────────────────


async def test_arbitrary_refund_over_amount_409(
    authed_client_owner: AsyncClient,
    make_plan: Any,
    make_client: Any,
) -> None:
    """Amount > original → 409 over_refund."""
    membership_id, payment_id = await _seed_sale_payment(
        authed_client_owner,
        make_plan=make_plan,
        make_client=make_client,
        phone_suffix="3001236",
    )

    r_orig = await authed_client_owner.get(f"/api/v1/payments/by-membership/{membership_id}")
    orig_amount = r_orig.json()["data"]["items"][0]["amountKopecks"]

    r = await authed_client_owner.post(
        f"/api/v1/payments/{payment_id}/refund",
        json={"amountKopecks": orig_amount + 1, "reason": "over refund test"},
        headers=_csrf_headers(authed_client_owner),
    )
    assert r.status_code == 409, r.text
    assert r.json()["code"] == "over_refund"


# ─── duplicate refund → 409 ──────────────────────────────────────────────────


async def test_arbitrary_refund_double_409(
    authed_client_owner: AsyncClient,
    make_plan: Any,
    make_client: Any,
) -> None:
    """Second refund of same original → 409 already_refunded (unique constraint)."""
    membership_id, payment_id = await _seed_sale_payment(
        authed_client_owner,
        make_plan=make_plan,
        make_client=make_client,
        phone_suffix="3001237",
    )

    r_orig = await authed_client_owner.get(f"/api/v1/payments/by-membership/{membership_id}")
    orig_amount = r_orig.json()["data"]["items"][0]["amountKopecks"]

    # First refund — success
    r1 = await authed_client_owner.post(
        f"/api/v1/payments/{payment_id}/refund",
        json={"amountKopecks": orig_amount, "reason": "first refund"},
        headers=_csrf_headers(authed_client_owner),
    )
    assert r1.status_code == 201, r1.text

    # Second refund of same original — must fail with already_refunded
    r2 = await authed_client_owner.post(
        f"/api/v1/payments/{payment_id}/refund",
        json={"amountKopecks": orig_amount, "reason": "second refund"},
        headers=_csrf_headers(authed_client_owner),
    )
    assert r2.status_code == 409, r2.text
    assert r2.json()["code"] == "already_refunded"


# ─── refund of a refund row → 409 ────────────────────────────────────────────


async def test_arbitrary_refund_of_refund_409(
    authed_client_owner: AsyncClient,
    db_session: AsyncSession,
    make_plan: Any,
    make_client: Any,
) -> None:
    """Trying to refund a refund row itself → 409 cannot_refund_refund."""
    membership_id, payment_id = await _seed_sale_payment(
        authed_client_owner,
        make_plan=make_plan,
        make_client=make_client,
        phone_suffix="3001238",
    )

    r_orig = await authed_client_owner.get(f"/api/v1/payments/by-membership/{membership_id}")
    orig_amount = r_orig.json()["data"]["items"][0]["amountKopecks"]

    # Issue a refund to get a refund row
    r1 = await authed_client_owner.post(
        f"/api/v1/payments/{payment_id}/refund",
        json={"amountKopecks": orig_amount, "reason": "seed refund for refund-of-refund test"},
        headers=_csrf_headers(authed_client_owner),
    )
    assert r1.status_code == 201, r1.text
    refund_payment_id = r1.json()["data"]["id"]

    # Attempt to refund the refund row
    r2 = await authed_client_owner.post(
        f"/api/v1/payments/{refund_payment_id}/refund",
        json={"amountKopecks": 1, "reason": "refund of refund attempt"},
        headers=_csrf_headers(authed_client_owner),
    )
    assert r2.status_code == 409, r2.text
    assert r2.json()["code"] == "cannot_refund_refund"


# ─── RBAC — reception → 403 ──────────────────────────────────────────────────


async def test_arbitrary_refund_reception_403(
    authed_client_owner: AsyncClient,
    authed_client_reception: AsyncClient,
    make_plan: Any,
    make_client: Any,
) -> None:
    """Reception POST /payments/{id}/refund → 403 (REFUND+FINANCE is OWNER_ONLY)."""
    membership_id, payment_id = await _seed_sale_payment(
        authed_client_owner,  # Owner seeds the data
        make_plan=make_plan,
        make_client=make_client,
        phone_suffix="3001239",
    )

    r_orig = await authed_client_owner.get(f"/api/v1/payments/by-membership/{membership_id}")
    orig_amount = r_orig.json()["data"]["items"][0]["amountKopecks"]

    r = await authed_client_reception.post(
        f"/api/v1/payments/{payment_id}/refund",
        json={"amountKopecks": orig_amount, "reason": "reception should be blocked"},
        headers=_csrf_headers(authed_client_reception),
    )
    assert r.status_code == 403, r.text


# ─── CSRF missing → 403 ──────────────────────────────────────────────────────


async def test_arbitrary_refund_csrf_missing_403(
    authed_client_owner: AsyncClient,
    make_plan: Any,
    make_client: Any,
) -> None:
    """Owner POST without X-CSRF-Token → 403 csrf_mismatch."""
    membership_id, payment_id = await _seed_sale_payment(
        authed_client_owner,
        make_plan=make_plan,
        make_client=make_client,
        phone_suffix="3001240",
    )

    r_orig = await authed_client_owner.get(f"/api/v1/payments/by-membership/{membership_id}")
    orig_amount = r_orig.json()["data"]["items"][0]["amountKopecks"]

    # No X-CSRF-Token header
    r = await authed_client_owner.post(
        f"/api/v1/payments/{payment_id}/refund",
        json={"amountKopecks": orig_amount, "reason": "csrf missing test"},
    )
    assert r.status_code == 403, r.text
    assert r.json()["code"] == "csrf_mismatch"


# ─── missing payment id → 404 ────────────────────────────────────────────────


async def test_arbitrary_refund_missing_payment_404(
    authed_client_owner: AsyncClient,
) -> None:
    """Random payment UUID → 404 original_payment_not_found."""
    r = await authed_client_owner.post(
        f"/api/v1/payments/{uuid4()}/refund",
        json={"amountKopecks": 1000, "reason": "missing payment test"},
        headers=_csrf_headers(authed_client_owner),
    )
    assert r.status_code == 404, r.text
    assert r.json()["code"] == "original_payment_not_found"
