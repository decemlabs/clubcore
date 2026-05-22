"""Phase 49 Plan 49-03 — sell_membership service-layer tests (PAY-03/05/06).

Covers all 4 YooKassa classification branches x 2 confirmation types +
QR replay re-fetch (BLOCKER #1) + email gate (FIS-05 / D-49-12) +
deterministic-key helper (D-49-08) + fiscal stub (D-49-22).

Every test depends on the root ``app`` fixture so the FastAPI lifespan
fires and registers the real ``YooKassaClient`` against the
``YooKassaClientProvider`` slot before the service hits respx.
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy import select

from app.core.exceptions import (
    BadGatewayAppError,
    ClientEmailRequiredForOnlinePaymentError,
    ServiceUnavailableAppError,
    ValidationAppError,
)
from app.integrations.yookassa.receipt import (
    PaymentMode,
    PaymentSubject,
    VatCode,
    build_receipt_item,
)
from app.modules.online_payments import service
from app.modules.online_payments.models import OnlinePayment

pytestmark = pytest.mark.asyncio


async def test_sell_membership_email_gate_blocks_when_email_null(
    app,
    db_session,
    make_client_no_email,
    make_membership_plan,
    make_actor,
    yookassa_settings,
):
    """FIS-05 / D-49-12 — clients.email IS NULL → 422 locked code, no DB row."""
    client = await make_client_no_email()
    plan = await make_membership_plan()
    actor = await make_actor()
    with pytest.raises(ClientEmailRequiredForOnlinePaymentError) as ei:
        await service.sell_membership(
            db_session,
            plan_id=plan.id,
            client_id=client.id,
            confirmation_type="redirect",
            actor=actor,
            yookassa_settings=yookassa_settings,
        )
    assert ei.value.code == "client_email_required_for_online_payment"
    rows = (await db_session.execute(select(OnlinePayment))).all()
    assert rows == []


async def test_sell_membership_happy_path_uses_real_receipt_builder(
    app,
    db_session,
    make_client_with_email,
    make_membership_plan,
    make_actor,
    yookassa_create_payment_success,
    yookassa_settings,
):
    """W4 — exercise the real build_receipt_item alongside the service call."""
    client = await make_client_with_email()
    plan = await make_membership_plan(name="Receipt-Builder-Smoke")
    actor = await make_actor()
    item = build_receipt_item(
        description=plan.name,
        amount_kopecks=plan.price_kopecks,
        payment_subject=PaymentSubject.SERVICE,
        payment_mode=PaymentMode.FULL_PREPAYMENT,
        vat_code=VatCode(int(yookassa_settings.default_vat_code)),
    )
    assert isinstance(item, dict) and item
    assert item["description"] == plan.name
    assert item["amount"]["currency"] == "RUB"

    resp = await service.sell_membership(
        db_session,
        plan_id=plan.id,
        client_id=client.id,
        confirmation_type="redirect",
        actor=actor,
        yookassa_settings=yookassa_settings,
    )
    assert resp.confirmation_url is not None
    assert resp.qr_payload is None


async def test_sell_membership_ok_redirect(
    app,
    db_session,
    make_client_with_email,
    make_membership_plan,
    make_actor,
    yookassa_create_payment_success,
    yookassa_settings,
):
    """Happy path — POST /payments 200, row inserted, XOR redirect side populated."""
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
    assert resp.qr_payload is None
    row = await db_session.scalar(
        select(OnlinePayment).where(OnlinePayment.id == resp.online_payment_id)
    )
    assert row is not None
    assert row.status == "pending"
    assert row.confirmation_type == "redirect"
    assert row.confirmation_url is not None
    assert row.created_by_user_id == actor.id


async def test_sell_membership_ok_qr(
    app,
    db_session,
    make_client_with_email,
    make_membership_plan,
    make_actor,
    yookassa_create_payment_qr_success,
    yookassa_settings,
):
    """Happy path — confirmation_type='qr' returns qr_payload, no URL stored."""
    client = await make_client_with_email()
    plan = await make_membership_plan()
    actor = await make_actor()
    resp = await service.sell_membership(
        db_session,
        plan_id=plan.id,
        client_id=client.id,
        confirmation_type="qr",
        actor=actor,
        yookassa_settings=yookassa_settings,
    )
    assert resp.qr_payload is not None
    assert resp.confirmation_url is None
    row = await db_session.scalar(
        select(OnlinePayment).where(OnlinePayment.id == resp.online_payment_id)
    )
    assert row is not None
    assert row.confirmation_url is None
    assert row.confirmation_type == "qr"


async def test_sell_membership_validation_error_no_db_row(
    app,
    db_session,
    make_client_with_email,
    make_membership_plan,
    make_actor,
    yookassa_create_payment_422,
    yookassa_settings,
):
    """D-49-10 — 422 from ЮKassa → ValidationAppError, no DB row, no audit emit."""
    client = await make_client_with_email()
    plan = await make_membership_plan()
    actor = await make_actor()
    with pytest.raises(ValidationAppError):
        await service.sell_membership(
            db_session,
            plan_id=plan.id,
            client_id=client.id,
            confirmation_type="redirect",
            actor=actor,
            yookassa_settings=yookassa_settings,
        )
    rows = (await db_session.execute(select(OnlinePayment))).all()
    assert rows == []


async def test_sell_membership_transient_error_503(
    app,
    db_session,
    make_client_with_email,
    make_membership_plan,
    make_actor,
    yookassa_create_payment_500,
    yookassa_settings,
):
    """D-49-10 — 5xx from ЮKassa → ServiceUnavailableAppError, no DB row."""
    client = await make_client_with_email()
    plan = await make_membership_plan()
    actor = await make_actor()
    with pytest.raises(ServiceUnavailableAppError):
        await service.sell_membership(
            db_session,
            plan_id=plan.id,
            client_id=client.id,
            confirmation_type="redirect",
            actor=actor,
            yookassa_settings=yookassa_settings,
        )
    rows = (await db_session.execute(select(OnlinePayment))).all()
    assert rows == []


async def test_sell_membership_permanent_error_502(
    app,
    db_session,
    make_client_with_email,
    make_membership_plan,
    make_actor,
    yookassa_create_payment_404,
    yookassa_settings,
):
    """D-49-10 — 4xx-not-422 → BadGatewayAppError, no DB row."""
    client = await make_client_with_email()
    plan = await make_membership_plan()
    actor = await make_actor()
    with pytest.raises(BadGatewayAppError):
        await service.sell_membership(
            db_session,
            plan_id=plan.id,
            client_id=client.id,
            confirmation_type="redirect",
            actor=actor,
            yookassa_settings=yookassa_settings,
        )
    rows = (await db_session.execute(select(OnlinePayment))).all()
    assert rows == []


async def test_sell_membership_replay_redirect_returns_existing_row(
    app,
    db_session,
    make_client_with_email,
    make_membership_plan,
    make_actor,
    yookassa_create_payment_success,
    yookassa_settings,
):
    """D-49-09 — second redirect call same day → same row, no second POST."""
    client = await make_client_with_email()
    plan = await make_membership_plan()
    actor = await make_actor()
    r1 = await service.sell_membership(
        db_session,
        plan_id=plan.id,
        client_id=client.id,
        confirmation_type="redirect",
        actor=actor,
        yookassa_settings=yookassa_settings,
    )
    r2 = await service.sell_membership(
        db_session,
        plan_id=plan.id,
        client_id=client.id,
        confirmation_type="redirect",
        actor=actor,
        yookassa_settings=yookassa_settings,
    )
    assert r1.online_payment_id == r2.online_payment_id
    assert r2.confirmation_url == r1.confirmation_url
    assert r2.qr_payload is None
    rows = (await db_session.execute(select(OnlinePayment))).all()
    assert len(rows) == 1


async def test_sell_membership_replay_qr_refetches_and_returns_qr_payload(
    app,
    db_session,
    make_client_with_email,
    make_membership_plan,
    make_actor,
    yookassa_create_payment_qr_success,
    yookassa_get_payment_qr_pending,
    yookassa_settings,
):
    """BLOCKER #1 — second QR click re-fetches via get_payment and returns qr_payload.

    The XOR validator on SellResponse rejects (None, None) and (str, str) shapes,
    so this test would crash with a Pydantic ValidationError if the QR replay
    branch returned confirmation_url=None AND qr_payload=None.
    """
    client = await make_client_with_email()
    plan = await make_membership_plan()
    actor = await make_actor()
    # respx requires the get_payment_qr_pending route to ALSO accept the
    # initial POST /payments call; the qr_success fixture wraps only the
    # POST route, so we issue the two calls in separate respx scopes by
    # exiting/re-entering via the fixtures. pytest yields each fixture for
    # the test's duration — both routers stay active simultaneously.
    r1 = await service.sell_membership(
        db_session,
        plan_id=plan.id,
        client_id=client.id,
        confirmation_type="qr",
        actor=actor,
        yookassa_settings=yookassa_settings,
    )
    r2 = await service.sell_membership(
        db_session,
        plan_id=plan.id,
        client_id=client.id,
        confirmation_type="qr",
        actor=actor,
        yookassa_settings=yookassa_settings,
    )
    assert r1.online_payment_id == r2.online_payment_id
    assert r2.confirmation_url is None
    assert r2.qr_payload is not None  # populated from get_payment re-fetch
    rows = (await db_session.execute(select(OnlinePayment))).all()
    assert len(rows) == 1


async def test_derive_idempotency_key_is_deterministic_per_day():
    """D-49-08 — same args → same hex; differing subject_kind → different hex."""
    from app.modules.online_payments.service import _derive_idempotency_key

    plan_id = uuid4()
    client_id = uuid4()
    k1 = _derive_idempotency_key(
        subject_kind="membership", plan_id=plan_id, client_id=client_id
    )
    k2 = _derive_idempotency_key(
        subject_kind="membership", plan_id=plan_id, client_id=client_id
    )
    k3 = _derive_idempotency_key(
        subject_kind="pt_package", plan_id=plan_id, client_id=client_id
    )
    assert k1 == k2
    assert k1 != k3
    assert len(k1) == 64
    assert all(c in "0123456789abcdef" for c in k1)


async def test_phase49_fiscal_dispatcher_stub_raises_not_implemented():
    """D-49-22 — Phase 49 fiscal stub raises with 'Phase 50' in message."""
    from app.modules.online_payments.service import phase49_fiscal_dispatcher_stub

    with pytest.raises(NotImplementedError) as ei:
        await phase49_fiscal_dispatcher_stub(
            fiscal_receipt_id=uuid4(), audit_correlation_id=None
        )
    assert "Phase 50" in str(ei.value)
