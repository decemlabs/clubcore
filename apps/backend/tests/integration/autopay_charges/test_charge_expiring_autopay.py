"""Phase 84 APAY-01/02/03 — charge_expiring_autopay service helper integration tests.

Tests the `_charge_expiring_autopay_memberships` service helper directly,
using a SAVEPOINT-backed db_session and respx for YooKassa mocking.

Coverage:
1. OK path: eligible membership → autopay_charges pending + online_payments(autopay) +
   autopay_charge_initiated audit; NO new membership created.
2. Decline path: 4xx → autopay_charges failed + NO online_payments + audit failure +
   declined claim id returned.
3. Amount matches plan's current price_kopecks.
4. ФЗ-376: consent_recorded_at IS NULL → ZERO charges.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any
from uuid import UUID, uuid4

import pytest
import respx
from httpx import Response
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.autopay_charges.service import _charge_expiring_autopay_memberships

# ЮKassa API base URL used by YooKassaClient.
_YK_BASE = "https://api.yookassa.ru/v3/"
_FAKE_PAYMENT_ID = "pay-autopay-ok-0001"
_FAKE_PAYMENT_ID_2 = "pay-autopay-ok-0002"


# ---------------------------------------------------------------------------
# Seed helpers
# ---------------------------------------------------------------------------


async def _seed_autopay_membership(
    session: AsyncSession,
    *,
    end_date: date | None = None,
    autopay_enabled: bool = True,
    with_consent: bool = True,
    with_alive_card: bool = True,
    price_kopecks: int = 199_000,
) -> dict[str, Any]:
    """Seed user→client→plan→membership→client_payment_methods chain."""
    nonce = uuid4().hex[:8]
    user_id = uuid4()
    client_id = uuid4()
    plan_id = uuid4()
    membership_id = uuid4()
    cpm_id = uuid4()
    method_id = "saved-card-" + nonce

    if end_date is None:
        end_date = date.today() + timedelta(days=2)  # noqa: DTZ011

    await session.execute(
        text(
            "INSERT INTO users (id, email, password_hash, role, full_name, created_at, updated_at)"
            " VALUES (:u_id, :u_email, 'x', 'owner', 'Autopay Test', now(), now())"
        ),
        {"u_id": user_id, "u_email": f"ap-{nonce}@example.com"},
    )
    await session.execute(
        text(
            "INSERT INTO clients"
            " (id, last_name, first_name, phone, created_by_user_id, created_at, updated_at)"
            " VALUES (:c_id, 'Autopay', 'Client', :c_phone, :c_uid, now(), now())"
        ),
        {"c_id": client_id, "c_phone": f"+7900{nonce}", "c_uid": user_id},
    )
    await session.execute(
        text(
            "INSERT INTO membership_plans"
            " (id, name, duration_days, price_kopecks, freeze_days_limit, created_at, updated_at)"
            " VALUES (:p_id, :p_name, 30, :p_price, 30, now(), now())"
        ),
        {"p_id": plan_id, "p_name": f"AutoPlan-{nonce}", "p_price": price_kopecks},
    )
    await session.execute(
        text(
            "INSERT INTO memberships"
            " (id, client_id, plan_id, plan_name_snapshot, duration_days_snapshot,"
            "  price_kopecks_snapshot, freeze_days_limit_snapshot,"
            "  start_date, end_date, status, created_at, updated_at)"
            " VALUES (:m_id, :m_cid, :m_pid, 'AutoPlan', 30, :m_price, 30,"
            "         :m_start, :m_end, 'active', now(), now())"
        ),
        {
            "m_id": membership_id,
            "m_cid": client_id,
            "m_pid": plan_id,
            "m_price": price_kopecks,
            "m_start": end_date - timedelta(days=30),
            "m_end": end_date,
        },
    )

    if with_alive_card:
        await session.execute(
            text(
                "INSERT INTO client_payment_methods"
                " (id, client_id, yookassa_method_id, last4, brand,"
                "  autopay_enabled, created_at, updated_at)"
                " VALUES (:pm_id, :pm_cid, :pm_mid, '4477', 'Visa',"
                "  :pm_ae, now(), now())"
            ),
            {
                "pm_id": cpm_id,
                "pm_cid": client_id,
                "pm_mid": method_id,
                "pm_ae": autopay_enabled,
            },
        )
        if with_consent:
            await session.execute(
                text(
                    "UPDATE client_payment_methods"
                    " SET consent_recorded_at = now() WHERE id = :pm_id"
                ),
                {"pm_id": cpm_id},
            )
    await session.flush()
    return {
        "membership_id": membership_id,
        "client_id": client_id,
        "plan_id": plan_id,
        "cpm_id": cpm_id,
        "method_id": method_id,
        "price_kopecks": price_kopecks,
        "end_date": end_date,
    }


def _ok_payment_response(payment_id: str, amount_value: str = "1990.00") -> dict[str, Any]:
    return {
        "id": payment_id,
        "status": "pending",
        "amount": {"value": amount_value, "currency": "RUB"},
        "description": "Автопродление",
        "paid": False,
        "refundable": False,
        "metadata": {},
    }


def _decline_response() -> dict[str, Any]:
    return {
        "type": "error",
        "id": "some-error-id",
        "code": "card_declined",
        "description": "Card declined by issuer",
    }


# ---------------------------------------------------------------------------
# Test 1: OK path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_charge_ok_path(db_session: AsyncSession) -> None:
    """Eligible autopay membership → ok provider response → correct DB state."""
    today = date.today()  # noqa: DTZ011
    seed = await _seed_autopay_membership(db_session, end_date=today + timedelta(days=2))
    membership_id: UUID = seed["membership_id"]
    plan_id: UUID = seed["plan_id"]
    price_kopecks: int = seed["price_kopecks"]

    ok_resp = _ok_payment_response(_FAKE_PAYMENT_ID, "1990.00")

    with respx.mock(base_url=_YK_BASE, assert_all_called=False) as router:
        router.post("payments").mock(return_value=Response(200, json=ok_resp))

        count, declined_ids = await _charge_expiring_autopay_memberships(
            db_session, today=today, window_days=3
        )

    # Exactly 1 charge attempt initiated
    assert count == 1
    assert declined_ids == []

    # Flush pending ORM objects (audit rows) so raw SQL SELECTs below see them.
    await db_session.flush()

    # autopay_charges row: status=pending, online_payment_id set, yookassa_payment_id set
    charge_row = (
        (
            await db_session.execute(
                text(
                    "SELECT id, status, online_payment_id, yookassa_payment_id"
                    " FROM autopay_charges WHERE membership_id = :ap_mid"
                ),
                {"ap_mid": str(membership_id)},
            )
        )
        .mappings()
        .one()
    )
    assert charge_row["status"] == "pending"
    assert charge_row["online_payment_id"] is not None
    assert charge_row["yookassa_payment_id"] == _FAKE_PAYMENT_ID
    claim_id = charge_row["id"]
    online_payment_id = charge_row["online_payment_id"]

    # online_payments row: confirmation_type='autopay', membership_plan_id set, status pending
    op_row = (
        (
            await db_session.execute(
                text(
                    "SELECT confirmation_type, membership_plan_id, status, amount_kopecks"
                    " FROM online_payments WHERE id = :op_id"
                ),
                {"op_id": str(online_payment_id)},
            )
        )
        .mappings()
        .one()
    )
    assert op_row["confirmation_type"] == "autopay"
    assert str(op_row["membership_plan_id"]) == str(plan_id)
    assert op_row["status"] == "pending"
    assert op_row["amount_kopecks"] == price_kopecks

    # autopay_charge_initiated audit row — resource_id = claim_id (autopay_charges.id)
    audit_count = (
        await db_session.execute(
            text(
                "SELECT COUNT(*) FROM audit_log"
                " WHERE action = 'autopay_charge_initiated'"
                "  AND resource_id = :ar_id"
            ),
            {"ar_id": str(claim_id)},
        )
    ).scalar_one()
    assert audit_count == 1

    # NO new membership created (activation is webhook-locked, D-06)
    membership_count = (
        await db_session.execute(
            text("SELECT COUNT(*) FROM memberships WHERE client_id = :mc_id"),
            {"mc_id": str(seed["client_id"])},
        )
    ).scalar_one()
    assert membership_count == 1


# ---------------------------------------------------------------------------
# Test 2: Decline path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_charge_decline_path(db_session: AsyncSession) -> None:
    """Provider 4xx → claim status='failed' + NO online_payments + failure audit + id returned."""
    today = date.today()  # noqa: DTZ011
    seed = await _seed_autopay_membership(db_session, end_date=today + timedelta(days=1))
    membership_id: UUID = seed["membership_id"]

    with respx.mock(base_url=_YK_BASE, assert_all_called=False) as router:
        router.post("payments").mock(return_value=Response(402, json=_decline_response()))

        count, declined_ids = await _charge_expiring_autopay_memberships(
            db_session, today=today, window_days=3
        )

    # Flush pending ORM objects (audit rows)
    await db_session.flush()

    assert count == 1  # one attempt (failed)
    assert len(declined_ids) == 1

    # autopay_charges row: status=failed, failure_reason set, NO online_payment_id
    charge_row = (
        (
            await db_session.execute(
                text(
                    "SELECT id, status, online_payment_id, failure_reason"
                    " FROM autopay_charges WHERE membership_id = :ap_mid"
                ),
                {"ap_mid": str(membership_id)},
            )
        )
        .mappings()
        .one()
    )
    assert charge_row["status"] == "failed"
    assert charge_row["online_payment_id"] is None
    assert charge_row["failure_reason"] is not None
    assert str(charge_row["id"]) == str(declined_ids[0])

    # NO online_payments row for this client
    op_count = (
        await db_session.execute(
            text("SELECT COUNT(*) FROM online_payments WHERE client_id = :op_cid"),
            {"op_cid": str(seed["client_id"])},
        )
    ).scalar_one()
    assert op_count == 0

    # autopay_charge_failed audit row
    audit_count = (
        await db_session.execute(
            text(
                "SELECT COUNT(*) FROM audit_log WHERE action = 'autopay_charge_failed'"
                "  AND resource_id = :df_id"
            ),
            {"df_id": str(charge_row["id"])},
        )
    ).scalar_one()
    assert audit_count == 1


# ---------------------------------------------------------------------------
# Test 2b (CR-02 regression): transient provider error → claim DELETED → retryable
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_charge_transient_error_is_retryable(db_session: AsyncSession) -> None:
    """Provider 5xx (transient) → claim DELETED, NO failure, period re-eligible next tick.

    CR-02: a transient blip must NOT permanently mark the period 'failed' (which the
    ON CONFLICT DO NOTHING guard would then skip forever). The claim row is deleted so
    a later tick re-attempts; a subsequent 'ok' response charges normally.
    """
    today = date.today()  # noqa: DTZ011
    seed = await _seed_autopay_membership(db_session, end_date=today + timedelta(days=1))
    membership_id: UUID = seed["membership_id"]

    # First tick: provider 503 (transient).
    with respx.mock(base_url=_YK_BASE, assert_all_called=False) as router:
        router.post("payments").mock(return_value=Response(503, json={"type": "error"}))
        count, declined_ids = await _charge_expiring_autopay_memberships(
            db_session, today=today, window_days=3
        )
    await db_session.flush()

    assert count == 0, "transient error must NOT count as an initiated/failed charge"
    assert declined_ids == [], "transient error must NOT enqueue a failure notification"

    # Claim row DELETED (not left as 'failed' → period stays fully eligible).
    charge_count = (
        await db_session.execute(
            text("SELECT COUNT(*) FROM autopay_charges WHERE membership_id = :m_id"),
            {"m_id": str(membership_id)},
        )
    ).scalar_one()
    assert charge_count == 0, "transient error must DELETE the claim so the next tick retries"

    # No failure audit emitted for a transient blip.
    fail_audits = (
        await db_session.execute(
            text("SELECT COUNT(*) FROM audit_log WHERE action = 'autopay_charge_failed'")
        )
    ).scalar_one()
    assert fail_audits == 0

    # Second tick: provider recovers (200 ok) → charges normally (proves retryability).
    with respx.mock(base_url=_YK_BASE, assert_all_called=False) as router:
        router.post("payments").mock(
            return_value=Response(200, json=_ok_payment_response(_FAKE_PAYMENT_ID, "1990.00"))
        )
        count2, declined2 = await _charge_expiring_autopay_memberships(
            db_session, today=today, window_days=3
        )
    await db_session.flush()

    assert count2 == 1, "after a transient failure the period must be re-chargeable"
    assert declined2 == []
    retry_row = (
        (
            await db_session.execute(
                text(
                    "SELECT status, online_payment_id FROM autopay_charges"
                    " WHERE membership_id = :m_id"
                ),
                {"m_id": str(membership_id)},
            )
        )
        .mappings()
        .one()
    )
    assert retry_row["status"] == "pending"
    assert retry_row["online_payment_id"] is not None


# ---------------------------------------------------------------------------
# Test 3: Amount equals plan's current price_kopecks
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_charge_amount_matches_plan_price(db_session: AsyncSession) -> None:
    """amount_kopecks on autopay_charges and online_payments = plan's current price_kopecks."""
    today = date.today()  # noqa: DTZ011
    specific_price = 350_000  # 3500.00 RUB
    seed = await _seed_autopay_membership(
        db_session,
        end_date=today + timedelta(days=1),
        price_kopecks=specific_price,
    )

    # YooKassa returns the actual amount; the service stores the PLAN price.
    ok_resp = _ok_payment_response(_FAKE_PAYMENT_ID_2, "3500.00")
    # Adjust the response amount_kopecks to match (service reads from provider result).
    ok_resp["amount"]["value"] = "3500.00"

    with respx.mock(base_url=_YK_BASE, assert_all_called=False) as router:
        router.post("payments").mock(return_value=Response(200, json=ok_resp))

        count, declined_ids = await _charge_expiring_autopay_memberships(
            db_session, today=today, window_days=3
        )

    assert count == 1
    assert declined_ids == []

    # The autopay_charges.amount_kopecks should be the PLAN price (from eligibility query).
    charge_row = (
        (
            await db_session.execute(
                text("SELECT amount_kopecks FROM autopay_charges WHERE membership_id = :am_mid"),
                {"am_mid": str(seed["membership_id"])},
            )
        )
        .mappings()
        .one()
    )
    assert charge_row["amount_kopecks"] == specific_price


# ---------------------------------------------------------------------------
# Test 4: ФЗ-376 — consent_recorded_at IS NULL → ZERO charges
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_no_consent_zero_charges(db_session: AsyncSession) -> None:
    """ФЗ-376: membership with no consent_recorded_at on the card MUST NOT be charged."""
    today = date.today()  # noqa: DTZ011
    await _seed_autopay_membership(
        db_session,
        end_date=today + timedelta(days=1),
        with_consent=False,  # consent_recorded_at IS NULL
    )

    call_count = 0

    with respx.mock(base_url=_YK_BASE, assert_all_called=False) as router:

        def _unexpected_call(*args: Any, **kwargs: Any) -> Response:
            nonlocal call_count
            call_count += 1
            return Response(200, json={"unexpected": True})

        router.post("payments").mock(side_effect=_unexpected_call)

        count, declined_ids = await _charge_expiring_autopay_memberships(
            db_session, today=today, window_days=3
        )

    # ФЗ-376: ZERO charges regardless of autopay_enabled status
    assert count == 0
    assert declined_ids == []
    # YooKassa was NOT called
    assert call_count == 0
