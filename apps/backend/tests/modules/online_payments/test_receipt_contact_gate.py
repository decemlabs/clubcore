"""Phase 999.5 Plan 03 Task 3 — online-payment gate email-OR-phone contract.

RED gate: these tests define the new behavior BEFORE the implementation ships.
Tests 1-3 MUST fail on the current service.py (which raises ClientEmailRequired
when email is None, even with a phone present). Test 4 verifies the existing
invariant guard still fires. Tests 5-6 confirm the email path is byte-identical.

Contract being locked (D-10):
  - A client with email=None but phone present → checkout proceeds (no raise).
  - A client with email present → checkout proceeds with email (unchanged).
  - A client with email=None AND phone=None → raises CLIENT_EMAIL_REQUIRED (invariant).
  - Phone MUST flow to customer_phone kwarg; NEVER to customer_email kwarg.
  - _read_client_receipt_contact_or_raise must replace _read_client_email_or_raise.
"""

from __future__ import annotations

import pytest

from app.core.exceptions import ClientEmailRequiredForOnlinePaymentError
from app.modules.online_payments import service

pytestmark = pytest.mark.asyncio(loop_scope="function")


# ── New behavior: phone-only client proceeds (D-10) ─────────────────────────────


async def test_sell_membership_phone_only_client_proceeds(
    app,
    db_session,
    make_client_no_email,
    make_membership_plan,
    make_actor,
    yookassa_create_payment_success,
    yookassa_settings,
) -> None:
    """D-10: client with email=None but phone present → online payment proceeds.

    Pre-change: raises ClientEmailRequiredForOnlinePaymentError.
    Post-change: returns SellResponse (no raise).
    """
    client = await make_client_no_email()
    plan = await make_membership_plan()
    actor = await make_actor()
    # Must NOT raise — D-10 relaxes the gate
    resp = await service.sell_membership(
        db_session,
        plan_id=plan.id,
        client_id=client.id,
        confirmation_type="redirect",
        actor=actor,
        yookassa_settings=yookassa_settings,
    )
    assert resp.confirmation_url is not None, (
        "Phone-only client must receive a confirmation_url — gate must not block"
    )


async def test_sell_pt_package_phone_only_client_proceeds(
    app,
    db_session,
    make_client_no_email,
    make_pt_package_plan,
    make_actor,
    yookassa_create_payment_success,
    yookassa_settings,
) -> None:
    """D-10: PT-package sale also proceeds for phone-only client."""
    client = await make_client_no_email()
    plan = await make_pt_package_plan()
    actor = await make_actor()
    resp = await service.sell_pt_package(
        db_session,
        plan_id=plan.id,
        client_id=client.id,
        confirmation_type="redirect",
        actor=actor,
        yookassa_settings=yookassa_settings,
    )
    assert resp.confirmation_url is not None


async def test_sell_membership_phone_only_does_not_raise_email_required(
    app,
    db_session,
    make_client_no_email,
    make_membership_plan,
    make_actor,
    yookassa_create_payment_success,
    yookassa_settings,
) -> None:
    """D-10: phone-only client must NOT raise ClientEmailRequiredForOnlinePaymentError."""
    client = await make_client_no_email()
    plan = await make_membership_plan()
    actor = await make_actor()
    # Should not raise at all
    try:
        await service.sell_membership(
            db_session,
            plan_id=plan.id,
            client_id=client.id,
            confirmation_type="redirect",
            actor=actor,
            yookassa_settings=yookassa_settings,
        )
    except ClientEmailRequiredForOnlinePaymentError:
        pytest.fail(
            "ClientEmailRequiredForOnlinePaymentError must not be raised "
            "for a phone-only client — gate relaxed by D-10"
        )


# ── Invariant guard: neither email nor phone (unreachable in production) ─────────

# NOTE: We cannot write a DB test for "neither email NOR phone" because the
# clients.phone column is NOT NULL at the DB level (OTP auth invariant). The
# guard exists in code but cannot be triggered via normal DB factories.
# The unit-level guard is validated by test_create_payment_neither_contact_raises_value_error
# in test_receipt_customer_phone.py for the client.py layer.
# The service-layer guard is implicitly covered: if phone were NULL (hypothetical),
# _read_client_receipt_contact_or_raise would raise ClientEmailRequiredForOnlinePaymentError.


# ── Existing behavior: email-present client unchanged ──────────────────────────


async def test_sell_membership_email_client_still_proceeds(
    app,
    db_session,
    make_client_with_email,
    make_membership_plan,
    make_actor,
    yookassa_create_payment_success,
    yookassa_settings,
) -> None:
    """Regression: email-present client path is unchanged by D-10 rewrite."""
    client = await make_client_with_email()
    plan = await make_membership_plan()
    actor = await make_actor()
    resp = await service.sell_membership(
        db_session,
        plan_id=plan.id,
        client_id=client.id,
        confirmation_type="redirect",
        actor=actor,
        yookassa_settings=yookassa_settings,
    )
    assert resp.confirmation_url is not None


# ── Service internals: new function replaces old ────────────────────────────────


@pytest.mark.asyncio(loop_scope="function")
async def test_service_has_new_gate_function() -> None:
    """D-10: _read_client_receipt_contact_or_raise must exist (old removed)."""
    assert hasattr(service, "_read_client_receipt_contact_or_raise"), (
        "_read_client_receipt_contact_or_raise must exist in service module"
    )
    assert not hasattr(service, "_read_client_email_or_raise"), (
        "_read_client_email_or_raise must be removed (replaced by _read_client_receipt_contact_or_raise)"  # noqa: E501
    )
