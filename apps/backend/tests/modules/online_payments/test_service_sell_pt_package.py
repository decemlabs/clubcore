"""Phase 49 Plan 49-03 — sell_pt_package service-layer tests (PAY-04/05/06).

Mirrors test_service_sell_membership.py for the PT-package subject kind.
Skips the deterministic-key + fiscal-stub tests (covered there); preserves
the full 4 x classification x confirmation matrix + QR replay re-fetch.
"""

from __future__ import annotations

import pytest
from sqlalchemy import select

from app.core.exceptions import (
    BadGatewayAppError,
    ClientEmailRequiredForOnlinePaymentError,
    ServiceUnavailableAppError,
    ValidationAppError,
)
from app.modules.online_payments import service
from app.modules.online_payments.models import OnlinePayment

pytestmark = pytest.mark.asyncio


async def test_sell_pt_package_email_gate_blocks_when_email_null(
    app,
    db_session,
    make_client_no_email,
    make_pt_package_plan,
    make_actor,
    yookassa_settings,
):
    """FIS-05 / D-49-12."""
    client = await make_client_no_email()
    plan = await make_pt_package_plan()
    actor = await make_actor()
    with pytest.raises(ClientEmailRequiredForOnlinePaymentError) as ei:
        await service.sell_pt_package(
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


async def test_sell_pt_package_ok_redirect(
    app,
    db_session,
    make_client_with_email,
    make_pt_package_plan,
    make_actor,
    yookassa_create_payment_success,
    yookassa_settings,
):
    client = await make_client_with_email()
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
    assert resp.qr_payload is None
    row = await db_session.scalar(
        select(OnlinePayment).where(OnlinePayment.id == resp.online_payment_id)
    )
    assert row is not None
    assert row.status == "pending"
    assert row.confirmation_type == "redirect"
    assert row.pt_package_plan_id == plan.id
    assert row.membership_plan_id is None


async def test_sell_pt_package_ok_qr(
    app,
    db_session,
    make_client_with_email,
    make_pt_package_plan,
    make_actor,
    yookassa_create_payment_qr_success,
    yookassa_settings,
):
    client = await make_client_with_email()
    plan = await make_pt_package_plan()
    actor = await make_actor()
    resp = await service.sell_pt_package(
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


async def test_sell_pt_package_validation_error_no_db_row(
    app,
    db_session,
    make_client_with_email,
    make_pt_package_plan,
    make_actor,
    yookassa_create_payment_422,
    yookassa_settings,
):
    client = await make_client_with_email()
    plan = await make_pt_package_plan()
    actor = await make_actor()
    with pytest.raises(ValidationAppError):
        await service.sell_pt_package(
            db_session,
            plan_id=plan.id,
            client_id=client.id,
            confirmation_type="redirect",
            actor=actor,
            yookassa_settings=yookassa_settings,
        )
    rows = (await db_session.execute(select(OnlinePayment))).all()
    assert rows == []


async def test_sell_pt_package_transient_error_503(
    app,
    db_session,
    make_client_with_email,
    make_pt_package_plan,
    make_actor,
    yookassa_create_payment_500,
    yookassa_settings,
):
    client = await make_client_with_email()
    plan = await make_pt_package_plan()
    actor = await make_actor()
    with pytest.raises(ServiceUnavailableAppError):
        await service.sell_pt_package(
            db_session,
            plan_id=plan.id,
            client_id=client.id,
            confirmation_type="redirect",
            actor=actor,
            yookassa_settings=yookassa_settings,
        )
    rows = (await db_session.execute(select(OnlinePayment))).all()
    assert rows == []


async def test_sell_pt_package_permanent_error_502(
    app,
    db_session,
    make_client_with_email,
    make_pt_package_plan,
    make_actor,
    yookassa_create_payment_404,
    yookassa_settings,
):
    client = await make_client_with_email()
    plan = await make_pt_package_plan()
    actor = await make_actor()
    with pytest.raises(BadGatewayAppError):
        await service.sell_pt_package(
            db_session,
            plan_id=plan.id,
            client_id=client.id,
            confirmation_type="redirect",
            actor=actor,
            yookassa_settings=yookassa_settings,
        )
    rows = (await db_session.execute(select(OnlinePayment))).all()
    assert rows == []


async def test_sell_pt_package_replay_qr_refetches_and_returns_qr_payload(
    app,
    db_session,
    make_client_with_email,
    make_pt_package_plan,
    make_actor,
    yookassa_create_payment_qr_success,
    yookassa_get_payment_qr_pending,
    yookassa_settings,
):
    """BLOCKER #1 mirror — same QR-replay re-fetch contract for PT-package."""
    client = await make_client_with_email()
    plan = await make_pt_package_plan()
    actor = await make_actor()
    r1 = await service.sell_pt_package(
        db_session,
        plan_id=plan.id,
        client_id=client.id,
        confirmation_type="qr",
        actor=actor,
        yookassa_settings=yookassa_settings,
    )
    r2 = await service.sell_pt_package(
        db_session,
        plan_id=plan.id,
        client_id=client.id,
        confirmation_type="qr",
        actor=actor,
        yookassa_settings=yookassa_settings,
    )
    assert r1.online_payment_id == r2.online_payment_id
    assert r2.confirmation_url is None
    assert r2.qr_payload is not None
    rows = (await db_session.execute(select(OnlinePayment))).all()
    assert len(rows) == 1
