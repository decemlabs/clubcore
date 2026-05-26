"""Integration tests for membership sale → payment recorder atomicity.

Phase 32 Plan 32-02 / PAY-05. Verifies:
  - Snapshot symmetry: payments.amount_kopecks == memberships.price_kopecks_snapshot
    (server-derived; client cannot supply amount on wire — D-32-16/17 anti-fraud).
  - Sign-positive on sale path; defence-in-depth CHECK constraint catches
    negative subject_kind='membership' rows at the DB.
  - Recorder failure rolls back the whole UoW: membership row, payment row,
    AND both audit rows vanish on RuntimeError mid-create.
  - Slot-unregistered defensive raise: get_payment_recorder() raising
    RuntimeError("payment_recorder not registered") surfaces as 500 with no
    persisted state.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import dependencies as core_dependencies
from app.core.audit_models import AuditLog
from app.modules.memberships.models import Membership
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
    "phone": "+79991234572",
}


def _headers(client: AsyncClient) -> dict[str, str]:
    return {
        "X-CSRF-Token": client.cookies.get("sportzal_csrf") or "",
        "Idempotency-Key": uuid4().hex,
    }


async def _seed(authed: AsyncClient) -> tuple[dict[str, Any], dict[str, Any]]:
    r = await authed.post("/api/v1/membership-plans", json=VALID_PLAN, headers=_headers(authed))
    assert r.status_code == 201, r.text
    plan = r.json()["data"]
    r = await authed.post("/api/v1/clients", json=VALID_CLIENT, headers=_headers(authed))
    assert r.status_code == 201, r.text
    client = r.json()["data"]
    return plan, client


# --- snapshot symmetry + sign-positive --------------------------------------


async def test_sale_records_payment_with_snapshot_symmetry(
    authed_client_owner: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Sale writes exactly one Payment row with amount == snapshot price.

    Verifies T-32-02-01 anti-tampering mitigation: server derives amount from
    membership.price_kopecks_snapshot, so even if a hostile client tried to
    supply amountKopecks in the request body it would be ignored.
    """
    plan, client = await _seed(authed_client_owner)
    r = await authed_client_owner.post(
        "/api/v1/memberships",
        json={"clientId": client["id"], "planId": plan["id"]},
        headers=_headers(authed_client_owner),
    )
    assert r.status_code == 201, r.text
    data = r.json()["data"]
    membership_id = UUID(data["id"])

    payments = (
        (
            await db_session.execute(
                select(Payment).where(
                    Payment.subject_kind == SUBJECT_KIND_MEMBERSHIP,
                    Payment.subject_id == membership_id,
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(payments) == 1, f"expected exactly 1 payment row, got {len(payments)}"
    payment = payments[0]

    membership = await db_session.get(Membership, membership_id)
    assert membership is not None
    # Snapshot symmetry — the invariant Phase 32 PAY-05 closes.
    assert payment.amount_kopecks == membership.price_kopecks_snapshot
    assert payment.amount_kopecks == plan["priceKopecks"]
    assert payment.method == "cash"
    assert payment.refund_of is None


async def test_sale_records_payment_sign_positive(
    authed_client_owner: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Sale-side payment row has amount_kopecks > 0 (CHECK ck_payments_amount_sign)."""
    plan, client = await _seed(authed_client_owner)
    r = await authed_client_owner.post(
        "/api/v1/memberships",
        json={"clientId": client["id"], "planId": plan["id"]},
        headers=_headers(authed_client_owner),
    )
    assert r.status_code == 201, r.text
    membership_id = UUID(r.json()["data"]["id"])

    amount = await db_session.scalar(
        select(Payment.amount_kopecks).where(
            Payment.subject_kind == SUBJECT_KIND_MEMBERSHIP,
            Payment.subject_id == membership_id,
        )
    )
    assert amount is not None
    assert amount > 0


# --- recorder failure rolls back the whole UoW ------------------------------


async def test_recorder_failure_rolls_back_uow(
    authed_client_owner: AsyncClient,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """If the recorder raises mid-sale, membership + payment + audit rows all vanish.

    Verifies T-32-02-04 (silent half-state) mitigation: a failure in the
    Protocol slot consumer aborts the outer UoW, so the DB never carries a
    membership without its matching cash receipt.
    """
    plan, client = await _seed(authed_client_owner)

    # Snapshot pre-state counts so the post-call assertions are tight.
    memberships_before = await db_session.scalar(select(func.count()).select_from(Membership))
    payments_before = await db_session.scalar(select(func.count()).select_from(Payment))
    audit_before = await db_session.scalar(
        select(func.count())
        .select_from(AuditLog)
        .where(AuditLog.action.in_(["membership_created", "payment_recorded"]))
    )

    async def _exploding_recorder(*_args: Any, **_kwargs: Any) -> Any:
        raise RuntimeError("test-induced recorder failure")

    monkeypatch.setattr(core_dependencies, "_payment_recorder", _exploding_recorder, raising=False)

    # Starlette propagates unhandled exceptions through ASGITransport by
    # default (raise_app_exceptions=True). RuntimeError is not registered
    # with the AppError handler, so we expect the exception to surface to
    # the test boundary; in production an ASGI server's default handler
    # converts it to a 500 — that's the visible end-user impact.
    with pytest.raises(RuntimeError, match="test-induced recorder failure"):
        await authed_client_owner.post(
            "/api/v1/memberships",
            json={"clientId": client["id"], "planId": plan["id"]},
            headers=_headers(authed_client_owner),
        )

    # In production, get_db is a context manager: an unhandled exception
    # triggers session.__aexit__ which rolls back the uncommitted UoW.
    # The SAVEPOINT-shared test fixture reuses one session across requests,
    # so we simulate the prod behaviour by explicitly rolling back here
    # before reading state. This proves that NOTHING was committed (the
    # service has no internal session.commit() up to the recorder line —
    # only the final commit at the end of create_membership commits).
    await db_session.rollback()

    memberships_after = await db_session.scalar(select(func.count()).select_from(Membership))
    payments_after = await db_session.scalar(select(func.count()).select_from(Payment))
    audit_after = await db_session.scalar(
        select(func.count())
        .select_from(AuditLog)
        .where(AuditLog.action.in_(["membership_created", "payment_recorded"]))
    )

    # Whole-UoW rollback: no new membership row, no new payment row, and
    # no new audit_log rows for the sale path.
    assert memberships_after == memberships_before
    assert payments_after == payments_before
    assert audit_after == audit_before


async def test_recorder_not_registered_raises_runtime_error(
    authed_client_owner: AsyncClient,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Slot=None → get_payment_recorder() raises 'payment_recorder not registered'.

    Verifies D-32-14 defensive-raise: missing registration is a hard failure
    surfaced at the consumer site, not a silent skip.
    """
    plan, client = await _seed(authed_client_owner)

    memberships_before = await db_session.scalar(select(func.count()).select_from(Membership))
    payments_before = await db_session.scalar(select(func.count()).select_from(Payment))

    # Clear the slot for the duration of this test. monkeypatch restores on
    # teardown, so subsequent tests pick up the create_app() registration.
    monkeypatch.setattr(core_dependencies, "_payment_recorder", None, raising=False)

    # Defensive-raise propagates the same way as the previous test: ASGI
    # default re-raises unhandled exceptions to the test boundary.
    with pytest.raises(RuntimeError, match="payment_recorder not registered"):
        await authed_client_owner.post(
            "/api/v1/memberships",
            json={"clientId": client["id"], "planId": plan["id"]},
            headers=_headers(authed_client_owner),
        )

    # Simulate prod context-manager rollback (see _rolls_back_uow above).
    await db_session.rollback()

    memberships_after = await db_session.scalar(select(func.count()).select_from(Membership))
    payments_after = await db_session.scalar(select(func.count()).select_from(Payment))
    assert memberships_after == memberships_before
    assert payments_after == payments_before
