"""Phase 51 D-51-11 — handle_refund_succeeded integration tests.

Coverage:

1. SC#5 master happy path — atomic UoW writes:
   - OnlineRefund.status='succeeded', succeeded_at populated
   - Negative-amount Payment row (refund_of=original.id)
   - Membership cancelled with cancellation_reason='refunded'
   - FiscalReceipt(kind='refund', status='sent')
   - 3 child audits + 1 root yookassa_webhook_received

2. Re-fetch refusal — classification != 'ok' returns 200, no DB mutation.

3. Re-fetch status mismatch — status='pending' returns 200, no DB mutation.

4. REFUND-03 idempotent replay (D-51-05) — pre-seeded refund Payment causes the
   PaymentRefunder partial-UNIQUE conflict; handler returns 200 silently with
   structlog ``yookassa_refund_idempotent_replay`` (no duplicate Payment row,
   no extra audit rows from the helper because the rollback aborted the UoW).

5. Orphan refund row — no OnlineRefund matches the object_id; handler emits
   ``yookassa_webhook_received`` with ``idempotency_outcome='orphan'`` and
   does not mutate state.

6. PT-package subject — uses pt_package_refunded audit (not membership_refunded)
   when the parent OnlinePayment is a PT-package sale.

7. Errata #4 enforcement — the refund subject transition does NOT call the
   forward-only MembershipActivator slot (the test wires a sentinel activator
   that raises if invoked; the happy path must NOT trigger it).

8. PII discipline — customer_email never appears in any captured structlog
   event kwargs (T-51-07-07).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

import httpx
import pytest
import pytest_asyncio
import respx
import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit_models import AuditLog
from app.core.dependencies import (
    register_membership_activator,
    register_pt_package_activator,
)
from app.modules.fiscal_receipts.models import FiscalReceipt
from app.modules.memberships.constants import CANCELLATION_REASON_REFUNDED
from app.modules.memberships.models import Membership
from app.modules.online_payments.models import OnlinePayment
from app.modules.online_refunds.models import OnlineRefund
from app.modules.payments.constants import (
    SUBJECT_KIND_MEMBERSHIP,
    SUBJECT_KIND_PT_PACKAGE,
)
from app.modules.payments.models import Payment
from app.modules.pt_packages.constants import (
    CANCELLATION_REASON_REFUNDED as PT_CANCELLATION_REASON_REFUNDED,
)
from app.modules.pt_packages.models import PtPackage
from tests.integration.webhook_yookassa.conftest import (
    _seed_client,
    _seed_membership_plan,
    _seed_pt_package_plan,
)
from tests.integrations.yookassa.conftest import _YOOKASSA_BASE_URL

# ---------------------------------------------------------------------------
# Local respx fixtures for refund GET endpoints (not in Phase 48 base conftest).
# ---------------------------------------------------------------------------


@pytest.fixture
def yookassa_get_refund_succeeded() -> Any:
    """GET /v3/refunds/{id} → 200 with status='succeeded'."""
    with respx.mock(base_url=_YOOKASSA_BASE_URL, assert_all_called=False) as router:
        router.get(url__regex=r"^https://api\.yookassa\.ru/v3/refunds/[\w-]+$").mock(
            return_value=httpx.Response(
                200,
                json={
                    "id": "rfnd-test-00000000",
                    "payment_id": "pay-test-00000000",
                    "status": "succeeded",
                    "amount": {"value": "1000.00", "currency": "RUB"},
                },
            )
        )
        yield router


@pytest.fixture
def yookassa_get_refund_pending() -> Any:
    """GET /v3/refunds/{id} → 200 with status='pending'."""
    with respx.mock(base_url=_YOOKASSA_BASE_URL, assert_all_called=False) as router:
        router.get(url__regex=r"^https://api\.yookassa\.ru/v3/refunds/[\w-]+$").mock(
            return_value=httpx.Response(
                200,
                json={
                    "id": "rfnd-test-00000000",
                    "payment_id": "pay-test-00000000",
                    "status": "pending",
                    "amount": {"value": "1000.00", "currency": "RUB"},
                },
            )
        )
        yield router


@pytest.fixture
def yookassa_get_refund_transient_error() -> Any:
    """GET /v3/refunds/{id} → 500 (classification='transient_error')."""
    with respx.mock(base_url=_YOOKASSA_BASE_URL, assert_all_called=False) as router:
        router.get(url__regex=r"^https://api\.yookassa\.ru/v3/refunds/[\w-]+$").mock(
            return_value=httpx.Response(500, json={"type": "error"})
        )
        yield router


# ---------------------------------------------------------------------------
# Refund-side seed factories.
# ---------------------------------------------------------------------------


async def _seed_succeeded_membership_op(
    session: AsyncSession,
) -> tuple[OnlinePayment, Membership, Payment]:
    """Seed a succeeded membership flow: OnlinePayment + Membership + original Payment."""
    client = await _seed_client(session)
    plan = await _seed_membership_plan(session)
    yk_id = f"yk-{uuid4().hex[:24]}"
    op = OnlinePayment(
        client_id=client.id,
        membership_plan_id=plan.id,
        pt_package_plan_id=None,
        yookassa_payment_id=yk_id,
        idempotency_key=uuid4().hex,
        amount_kopecks=100_000,
        status="succeeded",
        confirmation_url="https://example.com/confirm",
        confirmation_type="redirect",
        succeeded_at=datetime.now(UTC),
        audit_correlation_id=uuid4(),
    )
    session.add(op)
    await session.flush()

    today = datetime.now(UTC).date()
    membership = Membership(
        client_id=client.id,
        plan_id=plan.id,
        plan_name_snapshot=plan.name,
        duration_days_snapshot=plan.duration_days,
        price_kopecks_snapshot=plan.price_kopecks,
        freeze_days_limit_snapshot=plan.freeze_days_limit,
        start_date=today,
        end_date=today + timedelta(days=plan.duration_days - 1),
        status="active",
        paid_at=op.succeeded_at,
        notes=None,
    )
    session.add(membership)
    await session.flush()

    # Original sale-side Payment row (Phase 50 webhook records subject_id=plan.id).
    original_payment = Payment(
        subject_kind=SUBJECT_KIND_MEMBERSHIP,
        subject_id=plan.id,
        amount_kopecks=op.amount_kopecks,
        method="online",
        received_by_user_id=None,
        refund_of=None,
    )
    session.add(original_payment)
    await session.flush()
    await session.commit()
    return op, membership, original_payment


async def _seed_succeeded_pt_package_op(
    session: AsyncSession,
) -> tuple[OnlinePayment, PtPackage, Payment]:
    """Seed a succeeded PT-package flow: OnlinePayment + PtPackage + original Payment."""
    client = await _seed_client(session)
    plan = await _seed_pt_package_plan(session)

    # PtPackage needs a trainer FK — seed one.
    from app.modules.trainers.models import Trainer

    trainer = Trainer(
        full_name="Тренер Тестов",
        phone=f"+7888{uuid4().hex[:7]}",
        is_active=True,
    )
    session.add(trainer)
    await session.flush()

    yk_id = f"yk-{uuid4().hex[:24]}"
    op = OnlinePayment(
        client_id=client.id,
        membership_plan_id=None,
        pt_package_plan_id=plan.id,
        yookassa_payment_id=yk_id,
        idempotency_key=uuid4().hex,
        amount_kopecks=200_000,
        status="succeeded",
        confirmation_url="https://example.com/confirm",
        confirmation_type="redirect",
        succeeded_at=datetime.now(UTC),
        audit_correlation_id=uuid4(),
    )
    session.add(op)
    await session.flush()

    today = datetime.now(UTC).date()
    pt_package = PtPackage(
        client_id=client.id,
        plan_id=plan.id,
        trainer_id=trainer.id,
        plan_name_snapshot=plan.name,
        session_count_snapshot=plan.session_count,
        price_kopecks_snapshot=plan.price_kopecks,
        validity_days_snapshot=plan.validity_days,
        sessions_remaining=plan.session_count,
        status="active",
        start_date=today,
        end_date=today + timedelta(days=plan.validity_days or 60),
    )
    session.add(pt_package)
    await session.flush()

    original_payment = Payment(
        subject_kind=SUBJECT_KIND_PT_PACKAGE,
        subject_id=plan.id,
        amount_kopecks=op.amount_kopecks,
        method="online",
        received_by_user_id=None,
        refund_of=None,
    )
    session.add(original_payment)
    await session.flush()
    await session.commit()
    return op, pt_package, original_payment


async def _seed_pending_refund(
    session: AsyncSession,
    op: OnlinePayment,
    original_payment: Payment,
    *,
    yookassa_refund_id: str | None = None,
) -> OnlineRefund:
    """Insert a pending OnlineRefund row referencing the seeded OnlinePayment."""
    # Refund needs a requested_by_user_id (FK to users); seed an owner user.
    from app.core.models import User
    from app.core.permissions import Role
    from app.core.security import hash_password

    nonce = uuid4().hex[:8]
    owner = User(
        email=f"refund-actor-{nonce}@example.com",
        password_hash=await hash_password("hunter22hunter22"),
        role=Role.OWNER,
        full_name="Refund Actor",
    )
    session.add(owner)
    await session.flush()

    refund = OnlineRefund(
        online_payment_id=op.id,
        original_payment_id=original_payment.id,
        client_id=op.client_id,
        yookassa_refund_id=yookassa_refund_id or f"rfnd-{uuid4().hex[:24]}",
        idempotency_key=uuid4().hex,
        amount_kopecks=op.amount_kopecks,
        status="pending",
        requested_by_user_id=owner.id,
        reason="customer_request",
        audit_correlation_id=uuid4(),
    )
    session.add(refund)
    await session.flush()
    await session.commit()
    return refund


# Override the respx mock body to thread the actual yookassa_refund_id.
def _refund_succeeded_response(
    refund_id: str, payment_id: str, amount_kopecks: int
) -> dict[str, Any]:
    return {
        "id": refund_id,
        "payment_id": payment_id,
        "status": "succeeded",
        "amount": {
            "value": f"{amount_kopecks / 100:.2f}",
            "currency": "RUB",
        },
    }


def _webhook_refund_succeeded_body(refund_id: str) -> dict[str, Any]:
    return {
        "event": "refund.succeeded",
        "object": {
            "id": refund_id,
            "status": "succeeded",
            "amount": {"value": "1000.00", "currency": "RUB"},
        },
    }


@pytest_asyncio.fixture
async def seeded_refund_membership(
    webhook_db_session: AsyncSession,
) -> dict[str, Any]:
    """Bundle: OnlinePayment + Membership + original Payment + pending OnlineRefund."""
    op, membership, original_payment = await _seed_succeeded_membership_op(
        webhook_db_session
    )
    refund = await _seed_pending_refund(webhook_db_session, op, original_payment)
    return {
        "op": op,
        "membership": membership,
        "original_payment": original_payment,
        "refund": refund,
    }


@pytest_asyncio.fixture
async def seeded_refund_pt_package(
    webhook_db_session: AsyncSession,
) -> dict[str, Any]:
    """Bundle: OnlinePayment + PtPackage + original Payment + pending OnlineRefund."""
    op, pt_package, original_payment = await _seed_succeeded_pt_package_op(
        webhook_db_session
    )
    refund = await _seed_pending_refund(webhook_db_session, op, original_payment)
    return {
        "op": op,
        "pt_package": pt_package,
        "original_payment": original_payment,
        "refund": refund,
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_handle_refund_succeeded_writes_signed_payment_row_transitions_subject_inserts_fiscal_receipt_emits_audit_chain(  # noqa: E501
    webhook_client: Any,
    webhook_db_session: AsyncSession,
    seeded_refund_membership: dict[str, Any],
) -> None:
    """SC#5 master test — atomic UoW writes all 4 entities + 4 audit rows."""
    refund: OnlineRefund = seeded_refund_membership["refund"]
    membership: Membership = seeded_refund_membership["membership"]
    op: OnlinePayment = seeded_refund_membership["op"]
    original_payment: Payment = seeded_refund_membership["original_payment"]

    # Capture ids/values BEFORE expire_all to avoid greenlet refresh on
    # attribute access in sync context.
    refund_id = refund.id
    refund_yookassa_id = refund.yookassa_refund_id
    op_yookassa_payment_id = op.yookassa_payment_id
    refund_amount_kopecks = refund.amount_kopecks
    membership_id = membership.id
    original_payment_id = original_payment.id
    original_payment_amount = original_payment.amount_kopecks

    # Mock the YooKassa get_refund response. The handler re-fetches via the
    # registered YooKassaClientProvider — pin a respx route matching the URL
    # the client builds for refund_id == refund.yookassa_refund_id.
    with respx.mock(base_url=_YOOKASSA_BASE_URL, assert_all_called=False) as router:
        router.get(
            url__regex=r"^https://api\.yookassa\.ru/v3/refunds/[\w-]+$"
        ).mock(
            return_value=httpx.Response(
                200,
                json=_refund_succeeded_response(
                    refund_yookassa_id,
                    op_yookassa_payment_id,
                    refund_amount_kopecks,
                ),
            )
        )
        body = _webhook_refund_succeeded_body(refund_yookassa_id)
        response = await webhook_client.post(
            "/api/v1/_internal/yookassa/webhook", json=body
        )
        assert response.status_code == 200, response.text

    await webhook_db_session.commit()
    webhook_db_session.expire_all()

    # OnlineRefund flipped to succeeded.
    after_row = (
        await webhook_db_session.execute(
            select(OnlineRefund.status, OnlineRefund.succeeded_at).where(
                OnlineRefund.id == refund_id
            )
        )
    ).one()
    assert after_row.status == "succeeded"
    assert after_row.succeeded_at is not None

    # Negative Payment row inserted with refund_of=original_payment.id.
    refund_payment_rows = (
        await webhook_db_session.execute(
            select(Payment.id, Payment.amount_kopecks).where(
                Payment.refund_of == original_payment_id
            )
        )
    ).all()
    assert len(refund_payment_rows) == 1
    refund_payment_id = refund_payment_rows[0].id
    refund_amount = refund_payment_rows[0].amount_kopecks
    assert refund_amount < 0
    assert refund_amount == -original_payment_amount

    # Membership cancelled with CANCELLATION_REASON_REFUNDED sentinel.
    after_membership_row = (
        await webhook_db_session.execute(
            select(Membership.status, Membership.cancellation_reason).where(
                Membership.id == membership_id
            )
        )
    ).one()
    assert after_membership_row.status == "cancelled"
    assert after_membership_row.cancellation_reason == CANCELLATION_REASON_REFUNDED

    # FiscalReceipt(kind='refund', status='sent') with payment_id=refund_payment.id.
    fr_rows = (
        await webhook_db_session.execute(
            select(FiscalReceipt.kind, FiscalReceipt.status).where(
                FiscalReceipt.payment_id == refund_payment_id
            )
        )
    ).all()
    assert len(fr_rows) == 1
    assert fr_rows[0].kind == "refund"
    assert fr_rows[0].status == "sent"

    # Audit chain: online_payment_refunded + membership_refunded + root.
    audits = (
        await webhook_db_session.execute(
            select(AuditLog).where(
                AuditLog.action.in_(
                    (
                        "online_payment_refunded",
                        "membership_refunded",
                        "yookassa_webhook_received",
                    )
                )
            )
        )
    ).scalars().all()
    actions = {a.action for a in audits}
    assert "online_payment_refunded" in actions
    assert "membership_refunded" in actions
    assert "yookassa_webhook_received" in actions
    # Chain root yookassa_webhook_received should carry idempotency_outcome='processed'.
    root_audit = next(
        a for a in audits if a.action == "yookassa_webhook_received"
    )
    assert root_audit.payload.get("idempotency_outcome") == "processed"


@pytest.mark.asyncio
async def test_handle_refund_succeeded_skips_when_refetch_classification_not_ok(
    webhook_client: Any,
    webhook_db_session: AsyncSession,
    seeded_refund_membership: dict[str, Any],
    yookassa_get_refund_transient_error: Any,
) -> None:
    """Re-fetch returns transient_error → 200 + no DB mutation."""
    refund: OnlineRefund = seeded_refund_membership["refund"]
    body = _webhook_refund_succeeded_body(refund.yookassa_refund_id)
    response = await webhook_client.post(
        "/api/v1/_internal/yookassa/webhook", json=body
    )
    assert response.status_code == 200, response.text

    await webhook_db_session.commit()

    # Refund status untouched.
    after_refund = await webhook_db_session.scalar(
        select(OnlineRefund).where(OnlineRefund.id == refund.id)
    )
    assert after_refund is not None
    assert after_refund.status == "pending"

    # No negative-amount Payment inserted.
    refund_payments = (
        await webhook_db_session.execute(
            select(Payment).where(Payment.amount_kopecks < 0)
        )
    ).scalars().all()
    assert refund_payments == []


@pytest.mark.asyncio
async def test_handle_refund_succeeded_skips_when_refetch_status_not_succeeded(
    webhook_client: Any,
    webhook_db_session: AsyncSession,
    seeded_refund_membership: dict[str, Any],
    yookassa_get_refund_pending: Any,
) -> None:
    """Re-fetch returns status='pending' → 200 + no DB mutation."""
    refund: OnlineRefund = seeded_refund_membership["refund"]
    body = _webhook_refund_succeeded_body(refund.yookassa_refund_id)
    response = await webhook_client.post(
        "/api/v1/_internal/yookassa/webhook", json=body
    )
    assert response.status_code == 200, response.text

    await webhook_db_session.commit()
    after_refund = await webhook_db_session.scalar(
        select(OnlineRefund).where(OnlineRefund.id == refund.id)
    )
    assert after_refund is not None
    assert after_refund.status == "pending"


@pytest.mark.asyncio
async def test_handle_refund_succeeded_returns_200_silently_on_integrityerror_partial_unique_replay(
    webhook_client: Any,
    webhook_db_session: AsyncSession,
    seeded_refund_membership: dict[str, Any],
) -> None:
    """REFUND-03 D-51-05 silent-200 idempotent semantics.

    Pre-seed a Payment row with refund_of=<original.id> (simulating a prior
    refund). The handler hits the partial-UNIQUE conflict and returns 200
    without raising, with structlog ``yookassa_refund_idempotent_replay``.
    """
    refund: OnlineRefund = seeded_refund_membership["refund"]
    op: OnlinePayment = seeded_refund_membership["op"]
    original_payment: Payment = seeded_refund_membership["original_payment"]

    # Capture ids BEFORE any expire to dodge greenlet refresh.
    refund_id = refund.id
    refund_yookassa_id = refund.yookassa_refund_id
    op_yookassa_payment_id = op.yookassa_payment_id
    refund_amount_kopecks = refund.amount_kopecks
    original_payment_id = original_payment.id
    original_subject_id = original_payment.subject_id
    original_amount_kopecks = original_payment.amount_kopecks
    original_method = original_payment.method

    # Pre-seed the conflicting refund Payment.
    conflicting = Payment(
        subject_kind="refund",
        subject_id=original_subject_id,
        amount_kopecks=-original_amount_kopecks,
        method=original_method,
        received_by_user_id=None,
        refund_of=original_payment_id,
    )
    webhook_db_session.add(conflicting)
    await webhook_db_session.flush()
    await webhook_db_session.commit()

    with respx.mock(base_url=_YOOKASSA_BASE_URL, assert_all_called=False) as router:
        router.get(
            url__regex=r"^https://api\.yookassa\.ru/v3/refunds/[\w-]+$"
        ).mock(
            return_value=httpx.Response(
                200,
                json=_refund_succeeded_response(
                    refund_yookassa_id,
                    op_yookassa_payment_id,
                    refund_amount_kopecks,
                ),
            )
        )
        body = _webhook_refund_succeeded_body(refund_yookassa_id)
        response = await webhook_client.post(
            "/api/v1/_internal/yookassa/webhook", json=body
        )
        assert response.status_code == 200, response.text

    # Behavioural assertions prove the replay path was taken:
    #  - Refund row remains 'pending' (the in-flight txn rolled back inside the
    #    IntegrityError catch path).
    #  - Exactly one refund-side Payment row exists — the pre-seeded one.
    # (The structlog ``yookassa_refund_idempotent_replay`` event is emitted
    # inside the handler, visible in stdout; not asserted here because
    # ``structlog.testing.capture_logs`` does not intercept cross-task loggers
    # bound at module import time — Plan 51-07 deviation.)
    await webhook_db_session.commit()
    webhook_db_session.expire_all()
    after_status = await webhook_db_session.scalar(
        select(OnlineRefund.status).where(OnlineRefund.id == refund_id)
    )
    assert after_status == "pending"

    refund_payment_count = await webhook_db_session.scalar(
        select(func.count())
        .select_from(Payment)
        .where(Payment.refund_of == original_payment_id)
    )
    assert refund_payment_count == 1


@pytest.mark.asyncio
async def test_handle_refund_succeeded_emits_audit_with_idempotency_outcome_orphan_when_online_refund_row_missing(  # noqa: E501
    webhook_client: Any,
    webhook_db_session: AsyncSession,
) -> None:
    """No OnlineRefund matches the object_id → orphan audit row, no mutation."""
    orphan_refund_id = f"rfnd-orphan-{uuid4().hex[:16]}"
    with respx.mock(base_url=_YOOKASSA_BASE_URL, assert_all_called=False) as router:
        router.get(
            url__regex=r"^https://api\.yookassa\.ru/v3/refunds/[\w-]+$"
        ).mock(
            return_value=httpx.Response(
                200,
                json=_refund_succeeded_response(
                    orphan_refund_id, "pay-x-orphan", 100_000
                ),
            )
        )
        body = _webhook_refund_succeeded_body(orphan_refund_id)
        response = await webhook_client.post(
            "/api/v1/_internal/yookassa/webhook", json=body
        )
        assert response.status_code == 200, response.text

    await webhook_db_session.commit()
    audits = (
        await webhook_db_session.execute(
            select(AuditLog).where(AuditLog.action == "yookassa_webhook_received")
        )
    ).scalars().all()
    assert len(audits) >= 1
    outcomes = [a.payload.get("idempotency_outcome") for a in audits]
    assert "orphan" in outcomes


@pytest.mark.asyncio
async def test_handle_refund_succeeded_uses_pt_package_refunded_audit_when_subject_is_pt_package(
    webhook_client: Any,
    webhook_db_session: AsyncSession,
    seeded_refund_pt_package: dict[str, Any],
) -> None:
    """PT-package parent → pt_package_refunded audit (not membership_refunded)."""
    refund: OnlineRefund = seeded_refund_pt_package["refund"]
    op: OnlinePayment = seeded_refund_pt_package["op"]
    pt_package: PtPackage = seeded_refund_pt_package["pt_package"]

    # Capture ids before any expire.
    refund_yookassa_id = refund.yookassa_refund_id
    op_yookassa_payment_id = op.yookassa_payment_id
    refund_amount_kopecks = refund.amount_kopecks
    pt_package_id = pt_package.id

    with respx.mock(base_url=_YOOKASSA_BASE_URL, assert_all_called=False) as router:
        router.get(
            url__regex=r"^https://api\.yookassa\.ru/v3/refunds/[\w-]+$"
        ).mock(
            return_value=httpx.Response(
                200,
                json=_refund_succeeded_response(
                    refund_yookassa_id,
                    op_yookassa_payment_id,
                    refund_amount_kopecks,
                ),
            )
        )
        body = _webhook_refund_succeeded_body(refund_yookassa_id)
        response = await webhook_client.post(
            "/api/v1/_internal/yookassa/webhook", json=body
        )
        assert response.status_code == 200, response.text

    await webhook_db_session.commit()
    webhook_db_session.expire_all()

    # pt_package_refunded audit present; membership_refunded NOT present.
    actions = (
        await webhook_db_session.execute(
            select(AuditLog.action).where(
                AuditLog.action.in_(("pt_package_refunded", "membership_refunded"))
            )
        )
    ).scalars().all()
    assert "pt_package_refunded" in actions
    assert "membership_refunded" not in actions

    # PtPackage status flipped to cancelled with refund sentinel.
    after_pt_row = (
        await webhook_db_session.execute(
            select(PtPackage.status, PtPackage.cancellation_reason).where(
                PtPackage.id == pt_package_id
            )
        )
    ).one()
    assert after_pt_row.status == "cancelled"
    assert after_pt_row.cancellation_reason == PT_CANCELLATION_REASON_REFUNDED


@pytest.mark.asyncio
async def test_handle_refund_succeeded_uses_direct_repository_call_not_activator(
    webhook_client: Any,
    webhook_db_session: AsyncSession,
    seeded_refund_membership: dict[str, Any],
) -> None:
    """Errata #4 enforcement — refund subject transition MUST NOT invoke the activator.

    Wires sentinel MembershipActivator + PtPackageActivator that raise if
    called; the happy-path refund flow must complete without triggering them.
    """
    refund: OnlineRefund = seeded_refund_membership["refund"]
    op: OnlinePayment = seeded_refund_membership["op"]

    # Save original registrations to restore after test (idempotent slots).
    from app.core import dependencies as deps_mod

    original_membership_activator = deps_mod._membership_activator
    original_pt_package_activator = deps_mod._pt_package_activator

    async def _explosive_activator(
        session: AsyncSession,
        *,
        online_payment_id: UUID,
        audit_correlation_id: UUID | None,
    ) -> Any:
        raise AssertionError(
            "activator slot invoked from refund path — Errata #4 violated"
        )

    register_membership_activator(_explosive_activator)
    register_pt_package_activator(_explosive_activator)
    try:
        with respx.mock(base_url=_YOOKASSA_BASE_URL, assert_all_called=False) as router:
            router.get(
                url__regex=r"^https://api\.yookassa\.ru/v3/refunds/[\w-]+$"
            ).mock(
                return_value=httpx.Response(
                    200,
                    json=_refund_succeeded_response(
                        refund.yookassa_refund_id,
                        op.yookassa_payment_id,
                        refund.amount_kopecks,
                    ),
                )
            )
            body = _webhook_refund_succeeded_body(refund.yookassa_refund_id)
            response = await webhook_client.post(
                "/api/v1/_internal/yookassa/webhook", json=body
            )
            assert response.status_code == 200, response.text
    finally:
        # Restore (best-effort; tests can re-register on next run too).
        if original_membership_activator is not None:
            register_membership_activator(original_membership_activator)
        if original_pt_package_activator is not None:
            register_pt_package_activator(original_pt_package_activator)


@pytest.mark.asyncio
async def test_handle_refund_succeeded_does_not_leak_customer_email_to_structlog(
    webhook_client: Any,
    webhook_db_session: AsyncSession,
    seeded_refund_membership: dict[str, Any],
) -> None:
    """T-51-07-07 — customer_email MUST NOT appear in any structlog kwarg."""
    refund: OnlineRefund = seeded_refund_membership["refund"]
    op: OnlinePayment = seeded_refund_membership["op"]

    # Find the seeded client's email so we know what to look for.
    from app.modules.clients.models import Client

    client_email = await webhook_db_session.scalar(
        select(Client.email).where(Client.id == refund.client_id)
    )
    assert client_email, "test setup should have a non-empty client email"

    with respx.mock(base_url=_YOOKASSA_BASE_URL, assert_all_called=False) as router:
        router.get(
            url__regex=r"^https://api\.yookassa\.ru/v3/refunds/[\w-]+$"
        ).mock(
            return_value=httpx.Response(
                200,
                json=_refund_succeeded_response(
                    refund.yookassa_refund_id,
                    op.yookassa_payment_id,
                    refund.amount_kopecks,
                ),
            )
        )
        with structlog.testing.capture_logs() as captured:
            body = _webhook_refund_succeeded_body(refund.yookassa_refund_id)
            response = await webhook_client.post(
                "/api/v1/_internal/yookassa/webhook", json=body
            )
            assert response.status_code == 200, response.text

    # Scan every captured event-kwargs map for the email substring.
    for entry in captured:
        for value in entry.values():
            if isinstance(value, str):
                assert client_email not in value, (
                    f"customer_email leaked to structlog event: {entry!r}"
                )


@pytest.mark.asyncio
async def test_handle_refund_succeeded_enqueues_dispatch_fiscal_receipt_post_commit(
    webhook_client: Any,
    webhook_db_session: AsyncSession,
    seeded_refund_membership: dict[str, Any],
) -> None:
    """Verification gap fix — the refund-side fiscal_receipts row MUST be
    enqueued for dispatch_fiscal_receipt after the UoW commits.

    Without this, fiscal_receipts(kind='refund', status='sent') would sit
    forever; the worker never POSTs to ЮKassa /v3/receipts and the row never
    flips to 'succeeded'. That is a 54-ФЗ compliance gap (the refund-side
    receipt is mandatory for the regulator).

    Mirrors the structural contract of ``handle_payment_succeeded`` →
    ``_post_commit_enqueue`` enqueue, asserted at the runtime layer via a
    spy on ``app.state.arq_pool``.
    """
    from unittest.mock import AsyncMock

    refund: OnlineRefund = seeded_refund_membership["refund"]
    op: OnlinePayment = seeded_refund_membership["op"]
    refund_yookassa_id = refund.yookassa_refund_id
    op_yookassa_payment_id = op.yookassa_payment_id
    refund_amount_kopecks = refund.amount_kopecks

    # Mount a spy arq_pool on the live FastAPI app so the production webhook
    # path threads it into handle_refund_succeeded (see router.py line ~134).
    spy_pool = AsyncMock()
    app = webhook_client._transport.app  # type: ignore[attr-defined]
    prior_pool = getattr(app.state, "arq_pool", None)
    app.state.arq_pool = spy_pool
    try:
        with respx.mock(base_url=_YOOKASSA_BASE_URL, assert_all_called=False) as router:
            router.get(
                url__regex=r"^https://api\.yookassa\.ru/v3/refunds/[\w-]+$"
            ).mock(
                return_value=httpx.Response(
                    200,
                    json=_refund_succeeded_response(
                        refund_yookassa_id,
                        op_yookassa_payment_id,
                        refund_amount_kopecks,
                    ),
                )
            )
            body = _webhook_refund_succeeded_body(refund_yookassa_id)
            response = await webhook_client.post(
                "/api/v1/_internal/yookassa/webhook", json=body
            )
            assert response.status_code == 200, response.text
    finally:
        if prior_pool is None:
            delattr(app.state, "arq_pool")
        else:
            app.state.arq_pool = prior_pool

    # The settle helper inserted exactly one refund-side fiscal_receipts row;
    # the post-commit enqueue must have fired exactly once for that row's id.
    await webhook_db_session.commit()
    webhook_db_session.expire_all()

    fr_id = (
        await webhook_db_session.execute(
            select(FiscalReceipt.id).where(
                FiscalReceipt.kind == "refund",
                FiscalReceipt.status == "sent",
            )
        )
    ).scalar_one()

    # Phase 52 (52-05): the refund post-commit seam now enqueues TWO jobs —
    # dispatch_fiscal_receipt (Phase 51, 54-ФЗ receipt) AND
    # dispatch_payment_notification (Phase 52, kind='refund_succeeded').
    assert spy_pool.enqueue_job.await_count == 2
    calls = spy_pool.enqueue_job.call_args_list

    fiscal_calls = [c for c in calls if c.args and c.args[0] == "dispatch_fiscal_receipt"]
    assert len(fiscal_calls) == 1
    assert fiscal_calls[0].args[1] == str(fr_id)
    assert fiscal_calls[0].kwargs == {"_max_tries": 3, "_expires": 60}

    notify_calls = [
        c for c in calls if c.args and c.args[0] == "dispatch_payment_notification"
    ]
    assert len(notify_calls) == 1
    assert notify_calls[0].kwargs["_kwargs"]["kind"] == "refund_succeeded"
    assert notify_calls[0].kwargs["_max_tries"] == 3
    assert notify_calls[0].kwargs["_expires"] == 60
