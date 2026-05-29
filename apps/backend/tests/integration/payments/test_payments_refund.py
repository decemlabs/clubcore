"""Integration tests for POST /api/v1/memberships/{id}/refund (Phase 32 Plan 32-03).

Coverage:
  - Happy path: 200, status='cancelled', cancellation_reason='refunded',
    exactly one negative-amount Payment row with refund_of pointing at the
    original sale.
  - 4 conflict mappings (D-32-11 status-guard ordering):
      * 409 must_unfreeze_first             (frozen source)         REF-03 / B-08
      * 409 cannot_refund_renewed_source    (renewed source)        REF-04 / B-09
      * 409 invalid_transition              (already cancelled)
      * 409 already_refunded                (repeat refund)         REF-08
  - 404 mappings:
      * 404 membership_not_found            (random UUID)
      * 404 original_payment_not_found      (legacy membership w/o payment)
  - REF-05 schema-layer rejection:
      * amountKopecks → 422
      * unknown extra field → 422
      * empty reason / reason >200 chars → 422
  - B-07 reception+owner uniform: both roles return 200.
  - RBAC-04 ordering: anonymous → 401; missing CSRF → 403.

All tests run on the SAVEPOINT-mode ``db_session`` fixture; concurrent-race
behaviour lives in ``test_payments_refund_race.py`` with ``db_session_real_commit``.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID, uuid4

from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.memberships.models import Membership
from app.modules.payments.constants import SUBJECT_KIND_MEMBERSHIP, SUBJECT_KIND_REFUND
from app.modules.payments.models import Payment


def _headers(client: AsyncClient) -> dict[str, str]:
    """Headers for POST /memberships sale (includes Idempotency-Key)."""
    return {
        "X-CSRF-Token": client.cookies.get("clubcore_csrf") or "",
        "Idempotency-Key": uuid4().hex,
    }


def _refund_headers(client: AsyncClient) -> dict[str, str]:
    """Headers for POST /memberships/{id}/refund — NO Idempotency-Key (D-32-20)."""
    return {"X-CSRF-Token": client.cookies.get("clubcore_csrf") or ""}


async def _seed_sold_membership(
    authed: AsyncClient,
    *,
    make_plan: Any,
    make_client: Any,
    phone_suffix: str,
) -> tuple[UUID, UUID, UUID]:
    """Seed plan + client via DB-direct factories; sell membership via real HTTP.

    Plan + client are seeded directly (POST /membership-plans is owner-only;
    reception fixtures cannot use the HTTP plan flow). The sale POST primes
    the payments ledger via the recorder Protocol slot, which is what every
    refund test requires.

    Returns (plan_id, client_id, membership_id).
    """
    plan = await make_plan(name=f"Plan-{phone_suffix}-{uuid4().hex[:6]}")
    client = await make_client(phone=f"+7991234{phone_suffix}")
    r = await authed.post(
        "/api/v1/memberships",
        json={"clientId": str(client.id), "planId": str(plan.id)},
        headers=_headers(authed),
    )
    assert r.status_code == 201, r.text
    membership = r.json()["data"]
    return plan.id, client.id, UUID(membership["id"])


# --- happy path -------------------------------------------------------------


async def test_refund_happy_path(
    authed_client_reception: AsyncClient,
    db_session: AsyncSession,
    make_plan: Any,
    make_client: Any,
) -> None:
    """Reception refunds a sold active membership → 200 cancelled + 1 refund row."""
    _, _, membership_id = await _seed_sold_membership(
        authed_client_reception,
        make_plan=make_plan,
        make_client=make_client,
        phone_suffix="0001",
    )
    r = await authed_client_reception.post(
        f"/api/v1/memberships/{membership_id}/refund",
        json={"reason": "client requested"},
        headers=_refund_headers(authed_client_reception),
    )
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert data["status"] == "cancelled"
    assert data["cancellationReason"] == "refunded"

    # DB invariant: exactly 1 negative-amount refund row pointing at the sale.
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
    # Append-only: original sale row unchanged (amount stays positive).
    assert sale_rows[0].amount_kopecks > 0


# --- 4 conflict mappings ----------------------------------------------------


async def test_refund_must_unfreeze_first_409(
    authed_client_reception: AsyncClient,
    db_session: AsyncSession,
    make_plan: Any,
    make_client: Any,
) -> None:
    """Frozen source → 409 must_unfreeze_first (B-08); no refund row inserted."""
    _, _, membership_id = await _seed_sold_membership(
        authed_client_reception,
        make_plan=make_plan,
        make_client=make_client,
        phone_suffix="0002",
    )
    # Freeze first
    # Phase 66 IDM-07: freeze_membership now requires Idempotency-Key.
    r = await authed_client_reception.post(
        f"/api/v1/memberships/{membership_id}/freeze",
        headers={**_refund_headers(authed_client_reception), "Idempotency-Key": uuid4().hex},
    )
    assert r.status_code == 200, r.text

    r = await authed_client_reception.post(
        f"/api/v1/memberships/{membership_id}/refund",
        json={"reason": "test"},
        headers=_refund_headers(authed_client_reception),
    )
    assert r.status_code == 409, r.text
    assert r.json()["code"] == "must_unfreeze_first"

    # No refund row inserted.
    refund_count = await db_session.scalar(
        select(func.count())
        .select_from(Payment)
        .where(
            Payment.subject_id == membership_id,
            Payment.subject_kind == SUBJECT_KIND_REFUND,
        )
    )
    assert refund_count == 0


async def test_refund_cannot_refund_renewed_source_409(
    authed_client_reception: AsyncClient,
    db_session: AsyncSession,
    make_plan: Any,
    make_client: Any,
) -> None:
    """Renewed source → 409 cannot_refund_renewed_source (B-09)."""
    _, _, source_id = await _seed_sold_membership(
        authed_client_reception,
        make_plan=make_plan,
        make_client=make_client,
        phone_suffix="0003",
    )
    # Renew it (creates descendant with previous_membership_id=source.id)
    # Phase 66 IDM-07: renew_membership now requires Idempotency-Key.
    r = await authed_client_reception.post(
        f"/api/v1/memberships/{source_id}/renew",
        headers={**_refund_headers(authed_client_reception), "Idempotency-Key": uuid4().hex},
    )
    assert r.status_code == 201, r.text

    r = await authed_client_reception.post(
        f"/api/v1/memberships/{source_id}/refund",
        json={"reason": "test"},
        headers=_refund_headers(authed_client_reception),
    )
    assert r.status_code == 409, r.text
    assert r.json()["code"] == "cannot_refund_renewed_source"


async def test_refund_invalid_transition_409_when_already_cancelled(
    authed_client_owner: AsyncClient,
    db_session: AsyncSession,
    make_plan: Any,
    make_client: Any,
) -> None:
    """Already-cancelled source → 409 invalid_transition (admin cancel path).

    Uses owner fixture because (CANCEL, MEMBERSHIPS) is in OWNER_ONLY.
    """
    _, _, membership_id = await _seed_sold_membership(
        authed_client_owner,
        make_plan=make_plan,
        make_client=make_client,
        phone_suffix="0004",
    )
    # Cancel via admin path (owner-only)
    # Phase 66 IDM-07: cancel_membership now requires Idempotency-Key.
    r = await authed_client_owner.post(
        f"/api/v1/memberships/{membership_id}/cancel",
        json={"reason": "test admin cancel"},
        headers={**_refund_headers(authed_client_owner), "Idempotency-Key": uuid4().hex},
    )
    assert r.status_code == 200, r.text

    r = await authed_client_owner.post(
        f"/api/v1/memberships/{membership_id}/refund",
        json={"reason": "test"},
        headers=_refund_headers(authed_client_owner),
    )
    assert r.status_code == 409, r.text
    assert r.json()["code"] == "invalid_transition"


async def test_refund_already_refunded_409(
    authed_client_reception: AsyncClient,
    db_session: AsyncSession,
    make_plan: Any,
    make_client: Any,
) -> None:
    """Second refund on same membership → 409 already_refunded (DB partial UNIQUE).

    After the first refund the membership is cancelled, so the second attempt
    would normally hit 409 invalid_transition first. We manually re-flip the
    status back to 'active' on the SAVEPOINT-mode session to drive the flow
    past the transition guard and exercise the ``uq_payments_refund_of_alive``
    UNIQUE constraint specifically. In production the DB partial UNIQUE is the
    real race winner — see test_payments_refund_race.py for the concurrent
    behaviour.
    """
    _, _, membership_id = await _seed_sold_membership(
        authed_client_reception,
        make_plan=make_plan,
        make_client=make_client,
        phone_suffix="0005",
    )
    # First refund — success
    r = await authed_client_reception.post(
        f"/api/v1/memberships/{membership_id}/refund",
        json={"reason": "first"},
        headers=_refund_headers(authed_client_reception),
    )
    assert r.status_code == 200, r.text

    # Manually re-flip status to active so the refund flow reaches the DB layer
    # (exercising uq_payments_refund_of_alive specifically rather than the
    # transition guard).
    membership = (
        await db_session.execute(select(Membership).where(Membership.id == membership_id))
    ).scalar_one()
    membership.status = "active"
    membership.cancelled_at = None
    membership.cancellation_reason = None
    await db_session.commit()

    r = await authed_client_reception.post(
        f"/api/v1/memberships/{membership_id}/refund",
        json={"reason": "second"},
        headers=_refund_headers(authed_client_reception),
    )
    assert r.status_code == 409, r.text
    assert r.json()["code"] == "already_refunded"

    # DB: exactly 1 refund row.
    refund_count = await db_session.scalar(
        select(func.count())
        .select_from(Payment)
        .where(
            Payment.subject_id == membership_id,
            Payment.subject_kind == SUBJECT_KIND_REFUND,
        )
    )
    assert refund_count == 1


# --- 404 mappings -----------------------------------------------------------


async def test_refund_membership_not_found_404(
    authed_client_reception: AsyncClient,
) -> None:
    """Random UUID → 404 membership_not_found."""
    r = await authed_client_reception.post(
        f"/api/v1/memberships/{uuid4()}/refund",
        json={"reason": "test"},
        headers=_refund_headers(authed_client_reception),
    )
    assert r.status_code == 404, r.text
    assert r.json()["code"] == "membership_not_found"


async def test_refund_legacy_membership_no_payment(
    authed_client_reception: AsyncClient,
    db_session: AsyncSession,
    make_plan: Any,
    make_membership: Any,
    make_client: Any,
) -> None:
    """Membership without recorded sale (legacy) → 404 original_payment_not_found.

    Seeds a Membership row directly via the SAVEPOINT-mode session, bypassing
    the sale flow so no Payment row exists. The refunder raises
    OriginalPaymentNotFoundError which maps to 404.
    """
    plan = await make_plan(name=f"LegacyPlan-{uuid4().hex[:6]}")
    client = await make_client(phone="+79912340099")
    membership = await make_membership(client_id=client.id, plan=plan, status="active")
    r = await authed_client_reception.post(
        f"/api/v1/memberships/{membership.id}/refund",
        json={"reason": "test"},
        headers=_refund_headers(authed_client_reception),
    )
    assert r.status_code == 404, r.text
    assert r.json()["code"] == "original_payment_not_found"


# --- REF-05 schema-layer rejection ------------------------------------------


async def test_refund_rejects_amount_kopecks_field_422(
    authed_client_reception: AsyncClient,
    db_session: AsyncSession,
    make_plan: Any,
    make_client: Any,
) -> None:
    """POST /refund with amountKopecks in body → 422 (REF-05; BackendSchemaBase extra='forbid')."""
    _, _, membership_id = await _seed_sold_membership(
        authed_client_reception,
        make_plan=make_plan,
        make_client=make_client,
        phone_suffix="0006",
    )
    r = await authed_client_reception.post(
        f"/api/v1/memberships/{membership_id}/refund",
        json={"reason": "test", "amountKopecks": 1000},
        headers=_refund_headers(authed_client_reception),
    )
    assert r.status_code == 422, r.text

    # No refund row was created (schema rejected before service ran).
    refund_count = await db_session.scalar(
        select(func.count())
        .select_from(Payment)
        .where(
            Payment.subject_id == membership_id,
            Payment.subject_kind == SUBJECT_KIND_REFUND,
        )
    )
    assert refund_count == 0


async def test_refund_rejects_unknown_field_422(
    authed_client_reception: AsyncClient,
    make_plan: Any,
    make_client: Any,
) -> None:
    """POST /refund with any unknown field → 422 (extra='forbid')."""
    _, _, membership_id = await _seed_sold_membership(
        authed_client_reception,
        make_plan=make_plan,
        make_client=make_client,
        phone_suffix="0007",
    )
    r = await authed_client_reception.post(
        f"/api/v1/memberships/{membership_id}/refund",
        json={"reason": "test", "foo": "bar"},
        headers=_refund_headers(authed_client_reception),
    )
    assert r.status_code == 422, r.text


async def test_refund_reason_min_length_validation(
    authed_client_reception: AsyncClient,
    make_plan: Any,
    make_client: Any,
) -> None:
    """POST /refund with empty reason → 422 (Field min_length=1)."""
    _, _, membership_id = await _seed_sold_membership(
        authed_client_reception,
        make_plan=make_plan,
        make_client=make_client,
        phone_suffix="0008",
    )
    r = await authed_client_reception.post(
        f"/api/v1/memberships/{membership_id}/refund",
        json={"reason": ""},
        headers=_refund_headers(authed_client_reception),
    )
    assert r.status_code == 422, r.text


async def test_refund_reason_max_length_validation(
    authed_client_reception: AsyncClient,
    make_plan: Any,
    make_client: Any,
) -> None:
    """POST /refund with reason >200 chars → 422 (Field max_length=200)."""
    _, _, membership_id = await _seed_sold_membership(
        authed_client_reception,
        make_plan=make_plan,
        make_client=make_client,
        phone_suffix="0009",
    )
    r = await authed_client_reception.post(
        f"/api/v1/memberships/{membership_id}/refund",
        json={"reason": "x" * 201},
        headers=_refund_headers(authed_client_reception),
    )
    assert r.status_code == 422, r.text


# --- B-07 reception+owner uniformity ---------------------------------------


async def test_refund_reception_allowed(
    authed_client_reception: AsyncClient,
    make_plan: Any,
    make_client: Any,
) -> None:
    """Reception POST /refund → 200 (B-07: (REFUND, MEMBERSHIPS) NOT in OWNER_ONLY)."""
    _, _, membership_id = await _seed_sold_membership(
        authed_client_reception,
        make_plan=make_plan,
        make_client=make_client,
        phone_suffix="0010",
    )
    r = await authed_client_reception.post(
        f"/api/v1/memberships/{membership_id}/refund",
        json={"reason": "B-07 reception path"},
        headers=_refund_headers(authed_client_reception),
    )
    assert r.status_code == 200, r.text
    assert r.json()["data"]["status"] == "cancelled"


async def test_refund_owner_allowed(
    authed_client_owner: AsyncClient,
    make_plan: Any,
    make_client: Any,
) -> None:
    """Owner POST /refund → 200 (owner role short-circuits RBAC)."""
    _, _, membership_id = await _seed_sold_membership(
        authed_client_owner,
        make_plan=make_plan,
        make_client=make_client,
        phone_suffix="0011",
    )
    r = await authed_client_owner.post(
        f"/api/v1/memberships/{membership_id}/refund",
        json={"reason": "B-07 owner path"},
        headers=_refund_headers(authed_client_owner),
    )
    assert r.status_code == 200, r.text
    assert r.json()["data"]["status"] == "cancelled"


# --- RBAC-04 ordering -------------------------------------------------------


async def test_refund_anonymous_returns_401(
    async_client: AsyncClient,
) -> None:
    """RBAC-04 ordering: unauthenticated POST → 401 (auth fires before CSRF/RBAC)."""
    r = await async_client.post(
        f"/api/v1/memberships/{uuid4()}/refund",
        json={"reason": "no auth"},
    )
    assert r.status_code == 401, r.text


async def test_refund_csrf_missing_returns_403(
    authed_client_reception: AsyncClient,
    make_plan: Any,
    make_client: Any,
) -> None:
    """RBAC-04 ordering: missing X-CSRF-Token → 403 csrf_mismatch."""
    _, _, membership_id = await _seed_sold_membership(
        authed_client_reception,
        make_plan=make_plan,
        make_client=make_client,
        phone_suffix="0012",
    )
    # No X-CSRF-Token header
    r = await authed_client_reception.post(
        f"/api/v1/memberships/{membership_id}/refund",
        json={"reason": "missing csrf"},
    )
    assert r.status_code == 403, r.text
    assert r.json()["code"] == "csrf_mismatch"
