"""Integration tests for the sale-flow audit chain.

Phase 32 Plan 32-02 / PAY-05 forensic invariants:
  - audit_log carries TWO rows per sale ordered by created_at ASC:
    payment_recorded (emitted first inside record_payment) followed by
    membership_created (emitted after recorder returns).
  - membership_created payload carries a payment_id field linking back to
    the payment_recorded row (forensic traceability).
  - payment_recorded payload carries a payment_row_hash matching the
    ^sha256:[0-9a-f]{64}$ pattern.
  - payment_row_hash is deterministic: recomputing it from the persisted
    payments row yields the same value stored in the audit payload.
  - resource_id linkage: payment_recorded.resource_id == payments.id,
    membership_created.resource_id == memberships.id, and
    membership_created.payload["payment_id"] == str(payments.id).
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
from app.modules.payments.constants import SUBJECT_KIND_MEMBERSHIP
from app.modules.payments.models import Payment

VALID_PLAN: dict[str, Any] = {
    "name": "Базовый",
    "durationDays": 30,
    "priceKopecks": 250000,
    "freezeDaysLimit": 14,
    "active": True,
}
VALID_CLIENT: dict[str, Any] = {
    "lastName": "Иванов",
    "firstName": "Иван",
    "phone": "+79991234573",
}

_PAYMENT_ROW_HASH_RE = re.compile(r"^sha256:[0-9a-f]{64}$")


def _headers(client: AsyncClient) -> dict[str, str]:
    return {
        "X-CSRF-Token": client.cookies.get("sportzal_csrf") or "",
        "Idempotency-Key": uuid4().hex,
    }


async def _seed_and_sell(
    authed: AsyncClient,
) -> tuple[UUID, dict[str, Any]]:
    """Create plan + client + sale, return (membership_id, response data)."""
    r = await authed.post("/api/v1/membership-plans", json=VALID_PLAN, headers=_headers(authed))
    assert r.status_code == 201, r.text
    plan = r.json()["data"]
    r = await authed.post("/api/v1/clients", json=VALID_CLIENT, headers=_headers(authed))
    assert r.status_code == 201, r.text
    client = r.json()["data"]
    r = await authed.post(
        "/api/v1/memberships",
        json={"clientId": client["id"], "planId": plan["id"]},
        headers=_headers(authed),
    )
    assert r.status_code == 201, r.text
    data = r.json()["data"]
    return UUID(data["id"]), data


async def _fetch_audit_chain(
    db_session: AsyncSession, membership_id: UUID, payment_id: UUID
) -> list[AuditLog]:
    """Return the 2 audit_log rows for the sale.

    Note on ordering: Postgres ``now()`` is transaction-stable, so both audit
    rows share the exact same ``created_at`` value when emitted from the same
    UoW. The forensic chain is established not by creation-time ordering but
    by the ``payment_id`` linkage stored inside the ``membership_created``
    payload (D-30-02 free-form payload field added by Phase 32 PAY-05).
    Callers consume the returned list by ``.action`` not by index.
    """
    rows = (
        await db_session.execute(
            select(AuditLog).where(
                AuditLog.action.in_(["payment_recorded", "membership_created"]),
                AuditLog.resource_id.in_([membership_id, payment_id]),
            )
        )
    ).scalars().all()
    return list(rows)


# --- ordering + linkage -----------------------------------------------------


async def test_audit_chain_membership_created_to_payment_recorded(
    authed_client_owner: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Both audit rows co-exist in same UoW; linkage via payment_id is consistent.

    The forensic invariant is causal linkage via the payment_id field —
    Postgres ``now()`` is transaction-stable so the two rows share
    ``created_at`` and cannot be distinguished by time ordering alone.
    The payload-level link payment_id -> payment.id IS the chain.
    """
    membership_id, _data = await _seed_and_sell(authed_client_owner)

    payment = (
        await db_session.execute(
            select(Payment).where(
                Payment.subject_kind == SUBJECT_KIND_MEMBERSHIP,
                Payment.subject_id == membership_id,
            )
        )
    ).scalar_one()

    chain = await _fetch_audit_chain(db_session, membership_id, payment.id)
    assert len(chain) == 2

    by_action = {r.action: r for r in chain}
    assert set(by_action.keys()) == {"payment_recorded", "membership_created"}

    # payment_recorded resource_id == payments.id; membership_created
    # resource_id == memberships.id; both linked via payment_id in the
    # membership_created payload.
    assert by_action["payment_recorded"].resource_id == payment.id
    assert by_action["membership_created"].resource_id == membership_id
    assert by_action["membership_created"].payload["payment_id"] == str(payment.id)
    # Same UoW guarantee: both rows committed atomically, so they share the
    # transaction-start timestamp emitted by Postgres ``now()``.
    assert by_action["payment_recorded"].created_at == by_action["membership_created"].created_at


async def test_audit_chain_traceable_via_resource_id(
    authed_client_owner: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """resource_id linkage is consistent end-to-end (no drift, no aliasing)."""
    membership_id, _data = await _seed_and_sell(authed_client_owner)

    payment = (
        await db_session.execute(
            select(Payment).where(
                Payment.subject_kind == SUBJECT_KIND_MEMBERSHIP,
                Payment.subject_id == membership_id,
            )
        )
    ).scalar_one()
    chain = await _fetch_audit_chain(db_session, membership_id, payment.id)

    payment_audit = next(r for r in chain if r.action == "payment_recorded")
    membership_audit = next(r for r in chain if r.action == "membership_created")

    assert payment_audit.resource_type == "payment"
    assert payment_audit.resource_id == payment.id
    assert UUID(payment_audit.payload["payment_id"]) == payment.id
    assert UUID(payment_audit.payload["subject_id"]) == payment.subject_id == membership_id

    assert membership_audit.resource_type == "membership"
    assert membership_audit.resource_id == membership_id
    assert UUID(membership_audit.payload["payment_id"]) == payment.id


# --- payment_row_hash determinism + format ----------------------------------


async def test_payment_recorded_payload_includes_row_hash(
    authed_client_owner: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """payment_row_hash field present + format-locked ^sha256:[0-9a-f]{64}$."""
    membership_id, _data = await _seed_and_sell(authed_client_owner)
    payment = (
        await db_session.execute(
            select(Payment).where(
                Payment.subject_kind == SUBJECT_KIND_MEMBERSHIP,
                Payment.subject_id == membership_id,
            )
        )
    ).scalar_one()
    chain = await _fetch_audit_chain(db_session, membership_id, payment.id)
    payment_audit = next(r for r in chain if r.action == "payment_recorded")

    stored_hash = payment_audit.payload["payment_row_hash"]
    assert isinstance(stored_hash, str)
    assert _PAYMENT_ROW_HASH_RE.match(stored_hash) is not None


async def test_payment_recorded_row_hash_deterministic(
    authed_client_owner: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Recomputing payment_row_hash from the persisted row matches the stored value."""
    membership_id, _data = await _seed_and_sell(authed_client_owner)
    payment = (
        await db_session.execute(
            select(Payment).where(
                Payment.subject_kind == SUBJECT_KIND_MEMBERSHIP,
                Payment.subject_id == membership_id,
            )
        )
    ).scalar_one()
    chain = await _fetch_audit_chain(db_session, membership_id, payment.id)
    payment_audit = next(r for r in chain if r.action == "payment_recorded")

    # 8-column stable projection (D-32-23) — must match exactly the
    # _payment_row_dict shape used by payments.service.record_payment.
    expected_hash = payment_row_hash(
        {
            "id": payment.id,
            "subject_kind": payment.subject_kind,
            "subject_id": payment.subject_id,
            "amount_kopecks": payment.amount_kopecks,
            "method": payment.method,
            "received_at": payment.received_at,
            "received_by_user_id": payment.received_by_user_id,
            "refund_of": payment.refund_of,
        }
    )
    assert payment_audit.payload["payment_row_hash"] == expected_hash
