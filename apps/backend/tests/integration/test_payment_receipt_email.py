"""Phase 45 NOTIFY-11/12/13 — payment-receipt email fanout integration tests.

Asserts D-45-08 best-effort post-commit fanout at the memberships orchestrator
sites: SALE (POST /api/v1/memberships) + REFUND (POST /api/v1/memberships/
{id}/refund) + skip-no-email (D-45-10).

Three cases:
  1. test_membership_sale_with_email_fanouts_receipt — client.email IS NOT
     NULL: 1 payment_receipts row + 1 payment_receipt_emailed audit row +
     recorder.calls includes template_id="EMAIL_PAYMENT_RECEIPT_SALE".
  2. test_membership_refund_with_email_fanouts_receipt — refund flow on the
     refund Payment row: receipt_kind="refund", template_id="EMAIL_PAYMENT_
     RECEIPT_REFUND".
  3. test_membership_sale_no_email_skips_fanout — client.email IS NULL:
     zero receipts + zero audits + zero recorder calls; membership creation
     succeeds (best-effort, D-45-08).

Mirrors tests/integration/auth/test_invitation_accept.py sandbox_email_client
fixture (D-45-29 stub registration discipline) + tests/integration/memberships
/conftest.py auth fixtures (declared LOCAL here because the conftest at
tests/integration/memberships/ is not auto-inherited up the directory tree).
Runs on the SAVEPOINT-mode db_session — the orchestrator's first commit + the
helper's post-commit second commit BOTH become nested SAVEPOINT releases under
the outer rollback at teardown.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit_models import AuditLog
from app.core.database import get_db
from app.core.dependencies import register_email_dispatcher
from app.core.models import User
from app.core.permissions import Role
from app.core.redis import get_redis
from app.core.security import hash_password
from app.modules.clients.models import Client
from app.modules.memberships.models import MembershipPlan
from app.modules.payments.constants import SUBJECT_KIND_MEMBERSHIP, SUBJECT_KIND_REFUND
from app.modules.payments.models import Payment, PaymentReceipt

pytestmark = pytest.mark.asyncio


_OWNER_EMAIL = "receipt-flow-owner@example.com"
_OWNER_PASSWORD = "hunter22hunter22"  # noqa: S105 -- test literal (>=12 chars)


class _RecordingEmailDispatcher:
    """EmailDispatcher Protocol satisfier — records every dispatch kwarg."""

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def __call__(
        self,
        *,
        template_id: str,
        to: str,
        audit_correlation_id: UUID | None,
        **template_vars: Any,
    ) -> None:
        self.calls.append(
            {
                "template_id": template_id,
                "to": to,
                "audit_correlation_id": audit_correlation_id,
                **template_vars,
            }
        )


# ---------------------------------------------------------------------------
# Local fixture machinery (mirrors tests/integration/memberships/conftest.py).
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def _redis_clean(app: FastAPI) -> Any:
    client = app.state.redis
    await client.flushdb()
    return client


@pytest_asyncio.fixture
async def _seeded_owner(
    db_session: AsyncSession,
    _redis_clean: Any,
) -> User:
    """Owner user seeded directly (commits release a SAVEPOINT)."""
    _ = _redis_clean
    user = User(
        email=_OWNER_EMAIL,
        password_hash=await hash_password(_OWNER_PASSWORD),
        role=Role.OWNER,
        full_name="Receipt Flow Owner",
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def _app_overrides(
    app: FastAPI,
    db_session: AsyncSession,
) -> AsyncIterator[FastAPI]:
    """Install get_db + get_redis overrides so route handlers + tests share
    the SAVEPOINT-rolled session."""

    async def _override_get_db() -> AsyncIterator[AsyncSession]:
        yield db_session

    def _override_get_redis() -> Any:
        return app.state.redis

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_redis] = _override_get_redis
    try:
        yield app
    finally:
        app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def authed_owner_client(
    _app_overrides: FastAPI,
    _seeded_owner: User,
) -> AsyncIterator[AsyncClient]:
    """Owner-authed httpx client (cookies in jar after /auth/login)."""
    _ = _seeded_owner
    transport = ASGITransport(app=_app_overrides)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        r = await client.post(
            "/api/v1/auth/login",
            json={"email": _OWNER_EMAIL, "password": _OWNER_PASSWORD},
        )
        assert r.status_code == 200, r.text
        yield client


@pytest_asyncio.fixture
async def sandbox_email_recorder() -> AsyncIterator[_RecordingEmailDispatcher]:
    """Register a recording EmailDispatcher; restore prior slot on teardown.

    Mirrors tests/integration/auth/test_invitation_accept.py:168-186.
    """
    from app.core import dependencies as deps_mod

    prior = deps_mod._email_dispatcher
    recorder = _RecordingEmailDispatcher()
    register_email_dispatcher(recorder)
    try:
        yield recorder
    finally:
        if prior is not None:
            register_email_dispatcher(prior)
        else:
            deps_mod._email_dispatcher = None


async def _seed_plan(
    db_session: AsyncSession,
    *,
    name: str,
) -> MembershipPlan:
    plan = MembershipPlan(
        name=name,
        duration_days=30,
        price_kopecks=250000,
        freeze_days_limit=14,
        active=True,
    )
    db_session.add(plan)
    await db_session.commit()
    await db_session.refresh(plan)
    return plan


async def _seed_client(
    db_session: AsyncSession,
    *,
    owner: User,
    phone: str,
    email: str | None,
) -> Client:
    client = Client(
        last_name="Иванов",
        first_name="Иван",
        phone=phone,
        email=email,
        created_by_user_id=owner.id,
    )
    db_session.add(client)
    await db_session.commit()
    await db_session.refresh(client)
    return client


def _csrf_sale_headers(client: AsyncClient) -> dict[str, str]:
    return {
        "X-CSRF-Token": client.cookies.get("clubcore_csrf") or "",
        "Idempotency-Key": uuid4().hex,
    }


def _csrf_refund_headers(client: AsyncClient) -> dict[str, str]:
    return {"X-CSRF-Token": client.cookies.get("clubcore_csrf") or ""}


# ---------------------------------------------------------------------------
# Test 1 — SALE with email set: fanout fires.
# ---------------------------------------------------------------------------


async def test_membership_sale_with_email_fanouts_receipt(
    authed_owner_client: AsyncClient,
    db_session: AsyncSession,
    sandbox_email_recorder: _RecordingEmailDispatcher,
    _seeded_owner: User,
) -> None:
    """SALE path: 1 payment_receipts row + 1 audit row + 1 recorder call."""
    plan = await _seed_plan(db_session, name=f"SalePlan-{uuid4().hex[:6]}")
    client_row = await _seed_client(
        db_session,
        owner=_seeded_owner,
        phone="+79991230011",
        email="sale-receipt@example.com",
    )

    r = await authed_owner_client.post(
        "/api/v1/memberships",
        json={"clientId": str(client_row.id), "planId": str(plan.id)},
        headers=_csrf_sale_headers(authed_owner_client),
    )
    assert r.status_code == 201, r.text
    membership_id = UUID(r.json()["data"]["id"])

    sale_payment = (
        await db_session.execute(
            select(Payment).where(
                Payment.subject_id == membership_id,
                Payment.subject_kind == SUBJECT_KIND_MEMBERSHIP,
            )
        )
    ).scalar_one()

    # (a) Exactly 1 payment_receipts row with channel='email'.
    receipts = (
        (
            await db_session.execute(
                select(PaymentReceipt).where(PaymentReceipt.payment_id == sale_payment.id)
            )
        )
        .scalars()
        .all()
    )
    assert len(receipts) == 1
    assert receipts[0].channel == "email"
    assert receipts[0].to_address == "sale-receipt@example.com"
    assert receipts[0].audit_correlation_id is not None

    # (b) Exactly 1 audit_log row for ('payment_receipt_emailed', 'payment')
    # with receipt_kind='sale' in payload.
    audit_rows = (
        (
            await db_session.execute(
                select(AuditLog).where(
                    AuditLog.action == "payment_receipt_emailed",
                    AuditLog.resource_type == "payment",
                    AuditLog.resource_id == sale_payment.id,
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(audit_rows) == 1
    payload = audit_rows[0].payload
    assert payload["receipt_kind"] == "sale"
    assert payload["to_email"] == "sale-receipt@example.com"
    assert payload["payment_id"] == str(sale_payment.id)
    assert payload["audit_correlation_id"] == str(receipts[0].audit_correlation_id)

    # (c) Recorder captured exactly 1 dispatch call with the SALE template.
    sale_calls = [
        c for c in sandbox_email_recorder.calls if c["template_id"] == "EMAIL_PAYMENT_RECEIPT_SALE"
    ]
    assert len(sale_calls) == 1
    call = sale_calls[0]
    assert call["to"] == "sale-receipt@example.com"
    assert call["audit_correlation_id"] == receipts[0].audit_correlation_id
    # Pre-rendered template vars present (D-45-12 / D-45-17).
    assert "amount" in call
    assert "paid_at" in call
    assert "plan_snapshot" in call
    assert "actor_display_name" in call


# ---------------------------------------------------------------------------
# Test 2 — REFUND with email set: REFUND template dispatch.
# ---------------------------------------------------------------------------


async def test_membership_refund_with_email_fanouts_receipt(
    authed_owner_client: AsyncClient,
    db_session: AsyncSession,
    sandbox_email_recorder: _RecordingEmailDispatcher,
    _seeded_owner: User,
) -> None:
    """REFUND path: refund Payment gets its own receipt + REFUND template call."""
    plan = await _seed_plan(db_session, name=f"RefundPlan-{uuid4().hex[:6]}")
    client_row = await _seed_client(
        db_session,
        owner=_seeded_owner,
        phone="+79991230012",
        email="refund-receipt@example.com",
    )

    r = await authed_owner_client.post(
        "/api/v1/memberships",
        json={"clientId": str(client_row.id), "planId": str(plan.id)},
        headers=_csrf_sale_headers(authed_owner_client),
    )
    assert r.status_code == 201, r.text
    membership_id = UUID(r.json()["data"]["id"])

    # Reset recorder so we only inspect REFUND-side calls below.
    sandbox_email_recorder.calls.clear()

    r = await authed_owner_client.post(
        f"/api/v1/memberships/{membership_id}/refund",
        json={"reason": "client requested"},
        headers=_csrf_refund_headers(authed_owner_client),
    )
    assert r.status_code == 200, r.text

    refund_payment = (
        await db_session.execute(
            select(Payment).where(
                Payment.subject_id == membership_id,
                Payment.subject_kind == SUBJECT_KIND_REFUND,
            )
        )
    ).scalar_one()
    assert refund_payment.amount_kopecks < 0

    # (a) payment_receipts row for the REFUND payment, channel='email'.
    refund_receipts = (
        (
            await db_session.execute(
                select(PaymentReceipt).where(PaymentReceipt.payment_id == refund_payment.id)
            )
        )
        .scalars()
        .all()
    )
    assert len(refund_receipts) == 1
    assert refund_receipts[0].channel == "email"
    assert refund_receipts[0].to_address == "refund-receipt@example.com"

    # (b) audit_log row with receipt_kind='refund'.
    audit_rows = (
        (
            await db_session.execute(
                select(AuditLog).where(
                    AuditLog.action == "payment_receipt_emailed",
                    AuditLog.resource_type == "payment",
                    AuditLog.resource_id == refund_payment.id,
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(audit_rows) == 1
    assert audit_rows[0].payload["receipt_kind"] == "refund"
    assert audit_rows[0].payload["payment_id"] == str(refund_payment.id)

    # (c) Recorder captured exactly one REFUND-template dispatch.
    refund_calls = [
        c
        for c in sandbox_email_recorder.calls
        if c["template_id"] == "EMAIL_PAYMENT_RECEIPT_REFUND"
    ]
    assert len(refund_calls) == 1
    call = refund_calls[0]
    assert call["to"] == "refund-receipt@example.com"
    assert call["audit_correlation_id"] == refund_receipts[0].audit_correlation_id


# ---------------------------------------------------------------------------
# Test 3 — SALE with client.email IS NULL → fanout skipped (D-45-10).
# ---------------------------------------------------------------------------


async def test_membership_sale_no_email_skips_fanout(
    authed_owner_client: AsyncClient,
    db_session: AsyncSession,
    sandbox_email_recorder: _RecordingEmailDispatcher,
    _seeded_owner: User,
) -> None:
    """client.email IS NULL → 0 receipts + 0 audits + 0 recorder calls."""
    plan = await _seed_plan(db_session, name=f"NoEmailPlan-{uuid4().hex[:6]}")
    client_row = await _seed_client(
        db_session,
        owner=_seeded_owner,
        phone="+79991230013",
        email=None,
    )
    assert client_row.email is None

    r = await authed_owner_client.post(
        "/api/v1/memberships",
        json={"clientId": str(client_row.id), "planId": str(plan.id)},
        headers=_csrf_sale_headers(authed_owner_client),
    )
    # Membership creation succeeds even without email (best-effort fanout).
    assert r.status_code == 201, r.text
    membership_id = UUID(r.json()["data"]["id"])

    sale_payment = (
        await db_session.execute(
            select(Payment).where(
                Payment.subject_id == membership_id,
                Payment.subject_kind == SUBJECT_KIND_MEMBERSHIP,
            )
        )
    ).scalar_one()

    # (a) Zero payment_receipts rows for this payment.
    receipt_count = await db_session.scalar(
        select(func.count())
        .select_from(PaymentReceipt)
        .where(PaymentReceipt.payment_id == sale_payment.id)
    )
    assert receipt_count == 0

    # (b) Zero payment_receipt_emailed audit rows for this payment.
    audit_count = await db_session.scalar(
        select(func.count())
        .select_from(AuditLog)
        .where(
            AuditLog.action == "payment_receipt_emailed",
            AuditLog.resource_id == sale_payment.id,
        )
    )
    assert audit_count == 0

    # (c) Recorder saw zero calls.
    assert sandbox_email_recorder.calls == []
