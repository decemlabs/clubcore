"""REF-07 audit chain traceability tests (Phase 32 Plan 32-03).

Verifies the full forensic chain on a sale→refund flow:
  payment_recorded → membership_created → refund_issued → membership_refunded

All four audit_log rows must co-exist after a successful refund. Postgres
``now()`` is transaction-stable so creation-time ordering between rows in the
SAME UoW is unreliable; rows across DIFFERENT UoWs (sale txn vs refund txn)
DO differ in created_at because the txns commit at distinct wall-clock times.

Forensic invariants asserted:
  - All 4 locked audit events present (no stale ``payment_refunded`` typo).
  - ``refund_issued`` payload contains payment_row_hash matching
    ``^sha256:[0-9a-f]{64}$``; deterministic recomputation from the ORIGINAL
    sale row's 8 stable columns yields the same hash.
  - ``membership_refunded`` payload links the refund Payment row id, carries
    the operator-supplied reason, and the membership / client UUIDs.
"""

from __future__ import annotations

import re
from typing import Any
from uuid import UUID, uuid4

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit_hash import payment_row_hash
from app.core.audit_models import AuditLog
from app.modules.payments.constants import SUBJECT_KIND_MEMBERSHIP, SUBJECT_KIND_REFUND
from app.modules.payments.models import Payment

_PAYMENT_ROW_HASH_RE = re.compile(r"^sha256:[0-9a-f]{64}$")


def _headers(client: AsyncClient) -> dict[str, str]:
    return {
        "X-CSRF-Token": client.cookies.get("sportzal_csrf") or "",
        "Idempotency-Key": uuid4().hex,
    }


def _refund_headers(client: AsyncClient) -> dict[str, str]:
    """Refund POST does NOT require Idempotency-Key (D-32-20)."""
    return {"X-CSRF-Token": client.cookies.get("sportzal_csrf") or ""}


async def _seed_sold_membership(
    authed: AsyncClient,
    *,
    make_plan: Any,
    make_client: Any,
    phone_suffix: str,
) -> UUID:
    """Seed plan + client via DB-direct factories; sell via real HTTP POST.

    Returns the membership_id.
    """
    plan = await make_plan(name=f"ChainPlan-{phone_suffix}-{uuid4().hex[:6]}")
    client = await make_client(phone=f"+7991234{phone_suffix}")
    r = await authed.post(
        "/api/v1/memberships",
        json={"clientId": str(client.id), "planId": str(plan.id)},
        headers=_headers(authed),
    )
    assert r.status_code == 201, r.text
    return UUID(r.json()["data"]["id"])


async def _refund(
    authed: AsyncClient, membership_id: UUID, reason: str = "audit chain test"
) -> dict[str, Any]:
    r = await authed.post(
        f"/api/v1/memberships/{membership_id}/refund",
        json={"reason": reason},
        headers=_refund_headers(authed),
    )
    assert r.status_code == 200, r.text
    data: dict[str, Any] = r.json()["data"]
    return data


# --- chain ordering / completeness ------------------------------------------


async def test_refund_audit_chain_order(
    authed_client_owner: AsyncClient,
    db_session: AsyncSession,
    make_plan: Any,
    make_client: Any,
) -> None:
    """All 4 locked audit events present after sale → refund.

    payment_recorded + membership_created come from the sale UoW;
    refund_issued + membership_refunded come from the refund UoW. Asserts
    the chain as an order-agnostic set lookup — Postgres ``now()`` is
    transaction-stable, so rows within the same UoW share created_at and
    cannot be sorted by time. The forensic invariant is presence of all 4
    LOCKED event names verbatim (refund_issued, NOT payment_refunded —
    ROADMAP SC #5 terminology drift).
    """
    membership_id = await _seed_sold_membership(
        authed_client_owner,
        make_plan=make_plan,
        make_client=make_client,
        phone_suffix="0701",
    )

    # Fetch the sale payment row so we can include its id in the resource_id
    # filter (refund_issued.resource_id == refund_payment.id, not sale.id).
    sale_payment = (
        await db_session.execute(
            select(Payment).where(
                Payment.subject_kind == SUBJECT_KIND_MEMBERSHIP,
                Payment.subject_id == membership_id,
                Payment.amount_kopecks > 0,
            )
        )
    ).scalar_one()

    await _refund(authed_client_owner, membership_id, reason="forensic chain")

    refund_payment = (
        await db_session.execute(
            select(Payment).where(
                Payment.subject_kind == SUBJECT_KIND_REFUND,
                Payment.subject_id == membership_id,
            )
        )
    ).scalar_one()

    rows = (
        (
            await db_session.execute(
                select(AuditLog)
                .where(
                    AuditLog.action.in_(
                        [
                            "payment_recorded",
                            "membership_created",
                            "refund_issued",
                            "membership_refunded",
                        ]
                    ),
                    AuditLog.resource_id.in_([membership_id, sale_payment.id, refund_payment.id]),
                )
                .order_by(AuditLog.created_at.asc())
            )
        )
        .scalars()
        .all()
    )

    actions = {r.action for r in rows}
    assert actions == {
        "payment_recorded",
        "membership_created",
        "refund_issued",
        "membership_refunded",
    }, f"Audit chain missing rows; got actions={actions}"

    # resource_id linkage:
    by_action: dict[str, AuditLog] = {r.action: r for r in rows}
    assert by_action["payment_recorded"].resource_id == sale_payment.id
    assert by_action["membership_created"].resource_id == membership_id
    assert by_action["refund_issued"].resource_id == refund_payment.id
    assert by_action["membership_refunded"].resource_id == membership_id


# --- refund_issued payload + payment_row_hash determinism -------------------


async def test_refund_issued_payload_includes_payment_row_hash(
    authed_client_owner: AsyncClient,
    db_session: AsyncSession,
    make_plan: Any,
    make_client: Any,
) -> None:
    """refund_issued audit row carries a SHA-256 of the ORIGINAL sale row.

    Hash is recomputed from the 8 stable columns of the ORIGINAL sale payment
    (D-32-23) and must match the value stored in the audit_log payload.
    Determinism is the forensic invariant: any future query against the
    audit_log can independently verify the chain by re-hashing the sale row.
    """
    membership_id = await _seed_sold_membership(
        authed_client_owner,
        make_plan=make_plan,
        make_client=make_client,
        phone_suffix="0702",
    )

    sale_payment = (
        await db_session.execute(
            select(Payment).where(
                Payment.subject_kind == SUBJECT_KIND_MEMBERSHIP,
                Payment.subject_id == membership_id,
                Payment.amount_kopecks > 0,
            )
        )
    ).scalar_one()

    await _refund(authed_client_owner, membership_id, reason="hash test")

    refund_issued_row = (
        await db_session.execute(select(AuditLog).where(AuditLog.action == "refund_issued"))
    ).scalar_one()

    payload = refund_issued_row.payload
    assert "payment_row_hash" in payload
    stored_hash = payload["payment_row_hash"]
    assert _PAYMENT_ROW_HASH_RE.match(stored_hash) is not None, stored_hash

    # Recompute hash from the 8 stable columns of the ORIGINAL sale row.
    expected = payment_row_hash(
        {
            "id": sale_payment.id,
            "subject_kind": sale_payment.subject_kind,
            "subject_id": sale_payment.subject_id,
            "amount_kopecks": sale_payment.amount_kopecks,
            "method": sale_payment.method,
            "received_at": sale_payment.received_at,
            "received_by_user_id": sale_payment.received_by_user_id,
            "refund_of": sale_payment.refund_of,
        }
    )
    assert stored_hash == expected, (
        f"payment_row_hash mismatch: stored={stored_hash} expected={expected}"
    )


# --- membership_refunded payload linkage ------------------------------------


async def test_membership_refunded_payload_links_refund_payment(
    authed_client_owner: AsyncClient,
    db_session: AsyncSession,
    make_plan: Any,
    make_client: Any,
) -> None:
    """membership_refunded payload carries refund_payment_id + reason + uuids."""
    membership_id = await _seed_sold_membership(
        authed_client_owner,
        make_plan=make_plan,
        make_client=make_client,
        phone_suffix="0703",
    )
    reason = "operator note: client moved"
    await _refund(authed_client_owner, membership_id, reason=reason)

    refund_payment = (
        await db_session.execute(
            select(Payment).where(
                Payment.subject_kind == SUBJECT_KIND_REFUND,
                Payment.subject_id == membership_id,
            )
        )
    ).scalar_one()

    refunded_row = (
        await db_session.execute(
            select(AuditLog).where(
                AuditLog.action == "membership_refunded",
                AuditLog.resource_id == membership_id,
            )
        )
    ).scalar_one()

    payload = refunded_row.payload
    assert payload["refund_payment_id"] == str(refund_payment.id)
    assert payload["reason"] == reason
    assert payload["membership_id"] == str(membership_id)
    # client_id presence (str-cast UUID) — exact value derived from sale
    assert UUID(payload["client_id"])  # well-formed
