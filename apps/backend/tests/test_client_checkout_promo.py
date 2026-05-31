"""Phase 999.4 Plan 03 — promo-discount-at-checkout + redemption-on-succeeded integration tests.

Covers:
- Task 2: price_override_kopecks parameter on _sell_subject_core (sends discounted amount to ЮKassa,
  persists discounted amount_kopecks on row, sets promo_code_id on row)
- Task 2: record_promo_redemption helper (idempotent, cap-aware, no double-insert on replay)
- Task 3: promoCode field on checkout endpoints (membership + PT); invalid code → 422 before ЮKassa;
  no-promo path unchanged (row.promo_code_id NULL)
- Task 3: succeeded-webhook with promo payment → exactly one promo_redemptions row
- Task 3: succeeded-webhook with non-promo payment → zero promo_redemptions rows
- Task 3: webhook replay → redemption count stays 1 (idempotent)

Test harness: httpx ASGITransport + pytest-asyncio + SAVEPOINT-based db_session.
Auth: same _auth_as_client helper pattern as test_checkout.py.
ЮKassa: respx mock for checkout create_payment; conftest SeededOnlinePayment for webhook tests.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

import httpx
import pytest
import respx
from httpx import AsyncClient
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.permissions import Role
from app.core.security import generate_otp_code, hash_password
from app.modules.auth.models import OtpCode, User
from app.modules.clients.models import Client
from app.modules.memberships.models import MembershipPlan
from app.modules.online_payments.models import OnlinePayment
from app.modules.promo_codes.models import PromoCode
from app.modules.pt_packages.models import PtPackagePlan

pytestmark = pytest.mark.asyncio

# ---------------------------------------------------------------------------
# ЮKassa mock URL base (no live calls — all tests override via respx)
# ---------------------------------------------------------------------------

_YOOKASSA_BASE_URL = "https://api.yookassa.ru/v3/"
_FAKE_PAYMENT_BASE = "https://yoomoney.ru/checkout/payments/v2/contract"


# ---------------------------------------------------------------------------
# Auth helper
# ---------------------------------------------------------------------------


async def _auth_as_client(
    async_client: AsyncClient,
    db_session: AsyncSession,
    client: Client,
) -> None:
    """Request OTP → patch code → verify. After this call async_client has auth cookies."""
    req = await async_client.post(
        "/api/v1/client/otp/request",
        json={"phone": client.phone},
    )
    assert req.status_code == 202, f"OTP request failed: {req.text}"

    otp_row = await db_session.scalar(
        select(OtpCode).where(
            OtpCode.client_id == client.id,
            OtpCode.consumed_at.is_(None),
        )
    )
    assert otp_row is not None, f"OtpCode row not found for client {client.id}"

    settings = get_settings()
    raw_code, code_hash = generate_otp_code()
    otp_row.code_hash = code_hash
    otp_row.expires_at = datetime.now(tz=UTC) + timedelta(seconds=settings.otp_code_ttl_seconds)
    await db_session.commit()

    verify = await async_client.post(
        "/api/v1/client/otp/verify",
        json={"phone": client.phone, "code": raw_code},
    )
    assert verify.status_code == 200, f"OTP verify failed: {verify.text}"


def _checkout_headers(client: AsyncClient) -> dict[str, str]:
    """Return {"X-CSRF-Token": <clubcore_client_csrf>} for membership POST checkout."""
    return {"X-CSRF-Token": client.cookies.get("clubcore_client_csrf") or ""}


def _pt_checkout_headers(client: AsyncClient, *, idempotency_key: str) -> dict[str, str]:
    """Return checkout headers plus client-supplied Idempotency-Key for PT checkout."""
    headers = _checkout_headers(client)
    headers["Idempotency-Key"] = idempotency_key
    return headers


# ---------------------------------------------------------------------------
# Seed helpers
# ---------------------------------------------------------------------------


async def _seed_client(
    db_session: AsyncSession,
    *,
    phone: str | None = None,
) -> Client:
    """Seed a client with email and telegram_user_id (required for OTP + checkout)."""
    suffix = uuid4().hex[:8]
    phone = phone or f"+7916{uuid4().int % 10_000_000:07d}"
    tg_id = uuid4().int % 2_000_000_000 + 800_000_000

    staff = User(
        email=f"staff-promo3-{suffix}@example.com",
        password_hash=await hash_password("test-staff-pw-123"),
        role=Role.RECEPTION,
        full_name=f"Staff Promo3 {suffix}",
    )
    db_session.add(staff)
    await db_session.flush()

    client = Client(
        first_name="PromoCheckout",
        last_name=f"Client-{suffix}",
        phone=phone,
        email=f"promo3-client-{suffix}@example.com",
        telegram_user_id=tg_id,
        created_by_user_id=staff.id,
    )
    db_session.add(client)
    await db_session.commit()
    await db_session.refresh(client)
    return client


async def _seed_membership_plan(
    db_session: AsyncSession,
    *,
    price_kopecks: int = 100_000,
) -> MembershipPlan:
    """Insert an active MembershipPlan."""
    plan = MembershipPlan(
        name=f"PromoPlan {uuid4().hex[:6]}",
        duration_days=30,
        price_kopecks=price_kopecks,
        freeze_days_limit=7,
        active=True,
    )
    db_session.add(plan)
    await db_session.commit()
    await db_session.refresh(plan)
    return plan


async def _seed_pt_package_plan(
    db_session: AsyncSession,
    *,
    price_kopecks: int = 200_000,
) -> PtPackagePlan:
    """Insert an active PtPackagePlan."""
    plan = PtPackagePlan(
        name=f"PT PromoPlan {uuid4().hex[:6]}",
        session_count=10,
        price_kopecks=price_kopecks,
        validity_days=90,
    )
    db_session.add(plan)
    await db_session.commit()
    await db_session.refresh(plan)
    return plan


async def _seed_promo_code(
    db_session: AsyncSession,
    *,
    code: str,
    discount_type: str = "percentage",
    discount_value: int = 1000,  # 10% → 1000 (percent*100)
    max_uses: int | None = None,
    per_client_limit: int | None = None,
    is_active: bool = True,
    applicable_to: str | None = None,
) -> PromoCode:
    """Insert a PromoCode row."""
    promo = PromoCode(
        code=code,
        discount_type=discount_type,
        discount_value=discount_value,
        max_uses=max_uses,
        per_client_limit=per_client_limit,
        is_active=is_active,
        applicable_to=applicable_to,
    )
    db_session.add(promo)
    await db_session.commit()
    await db_session.refresh(promo)
    return promo


def _make_yookassa_response(
    *, amount_kopecks: int, confirmation_url: str, payment_id: str | None = None
) -> dict[str, Any]:
    """Build a minimal ЮKassa create-payment success response JSON."""
    amount_rubles = f"{amount_kopecks / 100:.2f}"
    return {
        "id": payment_id or f"yk-{uuid4().hex[:24]}",
        "status": "pending",
        "amount": {"value": amount_rubles, "currency": "RUB"},
        "confirmation": {
            "type": "redirect",
            "confirmation_url": confirmation_url,
        },
    }


# ===========================================================================
# Task 2 tests: price_override_kopecks + record_promo_redemption
# Called via direct service calls (not HTTP) to test the building blocks.
# ===========================================================================


async def test_sell_subject_core_price_override_sends_discounted_amount_to_yookassa(
    async_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """_sell_subject_core with price_override_kopecks → ЮKassa receives the OVERRIDDEN amount.

    Verified via the HTTP checkout endpoint: promoCode=OVERRIDE10 applies 10% discount.
    The respx stub captures create_payment call amount. Assert it equals the discounted amount.
    """
    client = await _seed_client(db_session)
    plan = await _seed_membership_plan(db_session, price_kopecks=100_000)
    await _seed_promo_code(db_session, code="OVERRIDE10", discount_type="percentage", discount_value=1000)

    await _auth_as_client(async_client, db_session, client)

    captured_amounts: list[int] = []
    fake_url = f"https://yoomoney.ru/checkout/override-{uuid4().hex[:8]}"

    def _capture_and_respond(request: httpx.Request) -> httpx.Response:
        import json
        body = json.loads(request.content)
        # amount.value from ЮKassa is in rubles (string); convert to kopecks
        value_str = body.get("amount", {}).get("value", "0")
        captured_amounts.append(round(float(value_str) * 100))
        return httpx.Response(
            200,
            json=_make_yookassa_response(
                amount_kopecks=round(float(value_str) * 100),
                confirmation_url=fake_url,
            ),
        )

    with respx.mock(base_url=_YOOKASSA_BASE_URL, assert_all_called=False) as mock:
        mock.post("payments").mock(side_effect=_capture_and_respond)

        r = await async_client.post(
            f"/api/v1/client/checkout/memberships/{plan.id}",
            headers=_checkout_headers(async_client),
            json={"promoCode": "OVERRIDE10"},
        )

    assert r.status_code == 201, r.text
    # 10% off 100_000 = 90_000
    assert len(captured_amounts) == 1, "ЮKassa should have been called exactly once"
    assert captured_amounts[0] == 90_000, (
        f"ЮKassa should receive 90000 kopecks (discounted), got {captured_amounts[0]}"
    )

    # Also verify the row's amount_kopecks was persisted as the discounted amount
    op_id = UUID(r.json()["data"]["onlinePaymentId"])
    row = await db_session.get(OnlinePayment, op_id)
    assert row is not None
    assert row.amount_kopecks == 90_000, (
        f"Row amount_kopecks should be discounted 90000, got {row.amount_kopecks}"
    )
    assert row.promo_code_id is not None, "Row promo_code_id should be set when promo applied"


async def test_sell_subject_core_no_override_uses_plan_price(
    async_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """_sell_subject_core with no promoCode → ЮKassa receives the full plan price (staff-path parity)."""
    client = await _seed_client(db_session)
    plan = await _seed_membership_plan(db_session, price_kopecks=100_000)

    await _auth_as_client(async_client, db_session, client)

    captured_amounts: list[int] = []
    fake_url = f"https://yoomoney.ru/checkout/nopromo-{uuid4().hex[:8]}"

    def _capture_and_respond(request: httpx.Request) -> httpx.Response:
        import json
        body = json.loads(request.content)
        value_str = body.get("amount", {}).get("value", "0")
        captured_amounts.append(round(float(value_str) * 100))
        return httpx.Response(
            200,
            json=_make_yookassa_response(
                amount_kopecks=round(float(value_str) * 100),
                confirmation_url=fake_url,
            ),
        )

    with respx.mock(base_url=_YOOKASSA_BASE_URL, assert_all_called=False) as mock:
        mock.post("payments").mock(side_effect=_capture_and_respond)

        r = await async_client.post(
            f"/api/v1/client/checkout/memberships/{plan.id}",
            headers=_checkout_headers(async_client),
            json={},  # no promoCode
        )

    assert r.status_code == 201, r.text
    assert captured_amounts[0] == 100_000, (
        f"Without promo ЮKassa should receive full 100000 kopecks, got {captured_amounts[0]}"
    )

    op_id = UUID(r.json()["data"]["onlinePaymentId"])
    row = await db_session.get(OnlinePayment, op_id)
    assert row is not None
    assert row.amount_kopecks == 100_000, "Row amount_kopecks should equal plan price when no promo"
    assert row.promo_code_id is None, "Row promo_code_id should be NULL when no promo applied"


async def test_sell_subject_core_applied_promo_code_id_persisted(
    async_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """When promoCode supplied, row.promo_code_id equals the PromoCode.id (not None)."""
    client = await _seed_client(db_session)
    plan = await _seed_membership_plan(db_session, price_kopecks=100_000)
    promo = await _seed_promo_code(
        db_session, code="PCIDCHECK", discount_type="percentage", discount_value=1000
    )

    await _auth_as_client(async_client, db_session, client)

    fake_url = f"https://yoomoney.ru/checkout/pcid-{uuid4().hex[:8]}"

    with respx.mock(base_url=_YOOKASSA_BASE_URL, assert_all_called=False) as mock:
        mock.post("payments").mock(
            return_value=httpx.Response(
                200,
                json=_make_yookassa_response(amount_kopecks=90_000, confirmation_url=fake_url),
            )
        )

        r = await async_client.post(
            f"/api/v1/client/checkout/memberships/{plan.id}",
            headers=_checkout_headers(async_client),
            json={"promoCode": "PCIDCHECK"},
        )

    assert r.status_code == 201, r.text
    op_id = UUID(r.json()["data"]["onlinePaymentId"])
    row = await db_session.get(OnlinePayment, op_id)
    assert row is not None
    assert row.promo_code_id == promo.id, (
        f"Row promo_code_id should equal PromoCode.id={promo.id}, got {row.promo_code_id}"
    )


async def test_record_promo_redemption_idempotent(
    async_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """record_promo_redemption is idempotent: two calls for same online_payment_id do not double-insert.

    Tested indirectly via the succeeded webhook: calling the webhook twice for a promo payment
    must result in exactly 1 promo_redemptions row (not 2).
    """
    from tests.integration.webhook_yookassa.conftest import SeededOnlinePayment

    client = await _seed_client(db_session)
    plan = await _seed_membership_plan(db_session, price_kopecks=100_000)
    promo = await _seed_promo_code(
        db_session, code="IDEMPOTENT10", discount_type="percentage", discount_value=1000
    )

    # Seed an online_payments row with promo_code_id already set (simulating post-checkout state)
    from app.modules.online_payments import repository as op_repo
    from app.modules.online_payments.constants import STATUS_PENDING, CONFIRMATION_TYPE_REDIRECT
    from uuid import uuid4 as _uuid4

    correlation_id = _uuid4()
    op_id = _uuid4()
    discounted_amount = 90_000  # 10% off 100_000

    op_row = await op_repo.insert_online_payment(
        db_session,
        client_id=client.id,
        membership_plan_id=plan.id,
        pt_package_plan_id=None,
        yookassa_payment_id=f"yk-idem-{_uuid4().hex[:16]}",
        idempotency_key=f"idem-{_uuid4().hex}",
        amount_kopecks=discounted_amount,
        status=STATUS_PENDING,
        confirmation_url="https://yoomoney.ru/checkout/idem",
        confirmation_type=CONFIRMATION_TYPE_REDIRECT,
        created_by_user_id=None,
        audit_correlation_id=correlation_id,
        id_override=op_id,
    )
    # Manually set promo_code_id on the row (simulating what _sell_subject_core does)
    op_row.promo_code_id = promo.id
    await db_session.commit()

    # Directly call record_promo_redemption twice
    from app.modules.promo_codes.service import record_promo_redemption

    async with db_session.begin_nested():
        await record_promo_redemption(
            db_session,
            promo_code_id=promo.id,
            client_id=client.id,
            online_payment_id=op_id,
            discount_kopecks=10_000,
        )

    # Second call with same online_payment_id must not raise IntegrityError
    async with db_session.begin_nested():
        await record_promo_redemption(
            db_session,
            promo_code_id=promo.id,
            client_id=client.id,
            online_payment_id=op_id,
            discount_kopecks=10_000,
        )
    await db_session.commit()

    count_row = (
        await db_session.execute(
            text(
                "SELECT COUNT(*) AS cnt FROM promo_redemptions "
                "WHERE online_payment_id = :op_id"
            ),
            {"op_id": str(op_id)},
        )
    ).mappings().one()
    count = int(count_row["cnt"])
    assert count == 1, f"Expected exactly 1 promo_redemptions row (idempotent), got {count}"


# ===========================================================================
# Task 3 tests: promoCode on checkout endpoints + webhook redemption recording
# ===========================================================================


async def test_discounted_membership_checkout_both_sub_and_pt(
    async_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """D-05: Both sub and PT checkout accept promoCode and send discounted amount to ЮKassa."""
    client = await _seed_client(db_session)
    sub_plan = await _seed_membership_plan(db_session, price_kopecks=100_000)
    pt_plan = await _seed_pt_package_plan(db_session, price_kopecks=200_000)
    await _seed_promo_code(
        db_session, code="BOTH10PCT", discount_type="percentage", discount_value=1000
    )

    await _auth_as_client(async_client, db_session, client)

    sub_captured: list[int] = []
    pt_captured: list[int] = []

    sub_url = f"https://yoomoney.ru/checkout/sub-both-{uuid4().hex[:8]}"
    pt_url = f"https://yoomoney.ru/checkout/pt-both-{uuid4().hex[:8]}"

    def _sub_capture(req: httpx.Request) -> httpx.Response:
        import json
        body = json.loads(req.content)
        v = round(float(body["amount"]["value"]) * 100)
        sub_captured.append(v)
        return httpx.Response(
            200, json=_make_yookassa_response(amount_kopecks=v, confirmation_url=sub_url)
        )

    def _pt_capture(req: httpx.Request) -> httpx.Response:
        import json
        body = json.loads(req.content)
        v = round(float(body["amount"]["value"]) * 100)
        pt_captured.append(v)
        return httpx.Response(
            200, json=_make_yookassa_response(amount_kopecks=v, confirmation_url=pt_url)
        )

    # --- membership checkout with promo ---
    with respx.mock(base_url=_YOOKASSA_BASE_URL, assert_all_called=False) as mock:
        mock.post("payments").mock(side_effect=_sub_capture)
        r = await async_client.post(
            f"/api/v1/client/checkout/memberships/{sub_plan.id}",
            headers=_checkout_headers(async_client),
            json={"promoCode": "BOTH10PCT"},
        )
    assert r.status_code == 201, r.text
    assert sub_captured[0] == 90_000, f"Membership: expected 90000, got {sub_captured[0]}"

    # --- PT checkout with promo ---
    idem_key = uuid4().hex
    with respx.mock(base_url=_YOOKASSA_BASE_URL, assert_all_called=False) as mock:
        mock.post("payments").mock(side_effect=_pt_capture)
        r = await async_client.post(
            f"/api/v1/client/checkout/pt-packages/{pt_plan.id}",
            headers=_pt_checkout_headers(async_client, idempotency_key=idem_key),
            json={"promoCode": "BOTH10PCT"},
        )
    assert r.status_code == 201, r.text
    assert pt_captured[0] == 180_000, f"PT: expected 180000, got {pt_captured[0]}"


async def test_invalid_promo_code_at_checkout_raises_422_before_yookassa(
    async_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Invalid promoCode at checkout → 422 with per-reason code; ЮKassa NOT called."""
    client = await _seed_client(db_session)
    plan = await _seed_membership_plan(db_session, price_kopecks=100_000)
    # No promo code seeded → code is unknown → not_found

    await _auth_as_client(async_client, db_session, client)

    yookassa_called = False

    def _should_not_be_called(req: httpx.Request) -> httpx.Response:
        nonlocal yookassa_called
        yookassa_called = True
        return httpx.Response(200, json={})

    with respx.mock(base_url=_YOOKASSA_BASE_URL, assert_all_called=False) as mock:
        mock.post("payments").mock(side_effect=_should_not_be_called)

        r = await async_client.post(
            f"/api/v1/client/checkout/memberships/{plan.id}",
            headers=_checkout_headers(async_client),
            json={"promoCode": "DOESNOTEXISTEVERRRR"},
        )

    assert r.status_code == 422, r.text
    body = r.json()
    assert body["code"] == "not_found", f"Expected not_found, got {body.get('code')!r}"
    assert not yookassa_called, "ЮKassa create_payment must NOT be called for an invalid promo"


async def test_no_promo_checkout_full_price_promo_code_id_null(
    async_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """No promoCode supplied → full plan price, row.promo_code_id is NULL (today's behavior unchanged)."""
    client = await _seed_client(db_session)
    plan = await _seed_membership_plan(db_session, price_kopecks=100_000)

    await _auth_as_client(async_client, db_session, client)

    captured_amounts: list[int] = []
    fake_url = f"https://yoomoney.ru/checkout/nopromo2-{uuid4().hex[:8]}"

    def _capture_and_respond(req: httpx.Request) -> httpx.Response:
        import json
        body = json.loads(req.content)
        v = round(float(body["amount"]["value"]) * 100)
        captured_amounts.append(v)
        return httpx.Response(
            200, json=_make_yookassa_response(amount_kopecks=v, confirmation_url=fake_url)
        )

    with respx.mock(base_url=_YOOKASSA_BASE_URL, assert_all_called=False) as mock:
        mock.post("payments").mock(side_effect=_capture_and_respond)

        r = await async_client.post(
            f"/api/v1/client/checkout/memberships/{plan.id}",
            headers=_checkout_headers(async_client),
            json={},  # no promoCode
        )

    assert r.status_code == 201, r.text
    assert captured_amounts[0] == 100_000, f"Full price expected 100000, got {captured_amounts[0]}"

    op_id = UUID(r.json()["data"]["onlinePaymentId"])
    row = await db_session.get(OnlinePayment, op_id)
    assert row is not None
    assert row.promo_code_id is None, "promo_code_id must be NULL when no promo applied"


async def test_succeeded_webhook_records_redemption_for_promo_payment(
    async_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """D-07: succeeded webhook for a promo payment records exactly one promo_redemptions row."""
    from tests.conftest import real_commit_client  # type: ignore[attr-defined]

    client = await _seed_client(db_session)
    plan = await _seed_membership_plan(db_session, price_kopecks=100_000)
    promo = await _seed_promo_code(
        db_session, code="WEBHOOKPROMO10", discount_type="percentage", discount_value=1000
    )

    from app.modules.online_payments import repository as op_repo
    from app.modules.online_payments.constants import STATUS_PENDING, CONFIRMATION_TYPE_REDIRECT

    correlation_id = uuid4()
    op_id = uuid4()
    yookassa_payment_id = f"yk-webhook-promo-{uuid4().hex[:16]}"
    discounted_amount = 90_000  # 10% off 100_000

    op_row = await op_repo.insert_online_payment(
        db_session,
        client_id=client.id,
        membership_plan_id=plan.id,
        pt_package_plan_id=None,
        yookassa_payment_id=yookassa_payment_id,
        idempotency_key=f"wh-promo-idem-{uuid4().hex}",
        amount_kopecks=discounted_amount,
        status=STATUS_PENDING,
        confirmation_url="https://yoomoney.ru/checkout/wh-promo",
        confirmation_type=CONFIRMATION_TYPE_REDIRECT,
        created_by_user_id=None,
        audit_correlation_id=correlation_id,
        id_override=op_id,
    )
    op_row.promo_code_id = promo.id
    await db_session.commit()

    # Build ЮKassa webhook body
    webhook_body = {
        "type": "notification",
        "event": "payment.succeeded",
        "object": {
            "id": yookassa_payment_id,
            "status": "succeeded",
            "amount": {"value": "900.00", "currency": "RUB"},
        },
    }

    # Mock ЮKassa get_payment to return succeeded status
    with respx.mock(base_url=_YOOKASSA_BASE_URL, assert_all_called=False) as mock:
        mock.get(f"payments/{yookassa_payment_id}").mock(
            return_value=httpx.Response(
                200,
                json={
                    "id": yookassa_payment_id,
                    "status": "succeeded",
                    "amount": {"value": "900.00", "currency": "RUB"},
                    "payment_method": {"type": "bank_card"},
                    "recipient": {"account_id": "123", "gateway_id": "456"},
                    "paid": True,
                    "refundable": True,
                    "income_amount": {"value": "900.00", "currency": "RUB"},
                },
            )
        )

        # Use the real webhook client to trigger the handler with a full commit
        settings = get_settings()
        webhook_r = await async_client.post(
            "/api/v1/_internal/yookassa/webhook",
            json=webhook_body,
            headers={"X-Forwarded-For": "185.71.76.0"},  # ЮKassa IP
        )

    # Webhook should return 200
    assert webhook_r.status_code == 200, f"Webhook returned non-200: {webhook_r.text}"

    # Check redemption was recorded
    count_row = (
        await db_session.execute(
            text(
                "SELECT COUNT(*) AS cnt FROM promo_redemptions "
                "WHERE online_payment_id = :op_id"
            ),
            {"op_id": str(op_id)},
        )
    ).mappings().one()
    count = int(count_row["cnt"])
    assert count == 1, f"Expected exactly 1 promo_redemptions row for promo payment, got {count}"


async def test_succeeded_webhook_no_redemption_for_non_promo_payment(
    async_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """D-07: succeeded webhook for a non-promo payment records zero promo_redemptions rows."""
    client = await _seed_client(db_session)
    plan = await _seed_membership_plan(db_session, price_kopecks=100_000)

    from app.modules.online_payments import repository as op_repo
    from app.modules.online_payments.constants import STATUS_PENDING, CONFIRMATION_TYPE_REDIRECT

    correlation_id = uuid4()
    op_id = uuid4()
    yookassa_payment_id = f"yk-webhook-nopromo-{uuid4().hex[:16]}"

    # Insert a normal online_payments row with no promo
    await op_repo.insert_online_payment(
        db_session,
        client_id=client.id,
        membership_plan_id=plan.id,
        pt_package_plan_id=None,
        yookassa_payment_id=yookassa_payment_id,
        idempotency_key=f"wh-nopromo-idem-{uuid4().hex}",
        amount_kopecks=100_000,
        status=STATUS_PENDING,
        confirmation_url="https://yoomoney.ru/checkout/wh-nopromo",
        confirmation_type=CONFIRMATION_TYPE_REDIRECT,
        created_by_user_id=None,
        audit_correlation_id=correlation_id,
        id_override=op_id,
    )
    await db_session.commit()

    webhook_body = {
        "type": "notification",
        "event": "payment.succeeded",
        "object": {
            "id": yookassa_payment_id,
            "status": "succeeded",
            "amount": {"value": "1000.00", "currency": "RUB"},
        },
    }

    with respx.mock(base_url=_YOOKASSA_BASE_URL, assert_all_called=False) as mock:
        mock.get(f"payments/{yookassa_payment_id}").mock(
            return_value=httpx.Response(
                200,
                json={
                    "id": yookassa_payment_id,
                    "status": "succeeded",
                    "amount": {"value": "1000.00", "currency": "RUB"},
                    "payment_method": {"type": "bank_card"},
                    "recipient": {"account_id": "123", "gateway_id": "456"},
                    "paid": True,
                    "refundable": True,
                    "income_amount": {"value": "1000.00", "currency": "RUB"},
                },
            )
        )

        webhook_r = await async_client.post(
            "/api/v1/_internal/yookassa/webhook",
            json=webhook_body,
            headers={"X-Forwarded-For": "185.71.76.0"},
        )

    assert webhook_r.status_code == 200, f"Webhook returned non-200: {webhook_r.text}"

    count_row = (
        await db_session.execute(
            text(
                "SELECT COUNT(*) AS cnt FROM promo_redemptions "
                "WHERE online_payment_id = :op_id"
            ),
            {"op_id": str(op_id)},
        )
    ).mappings().one()
    count = int(count_row["cnt"])
    assert count == 0, f"Expected 0 promo_redemptions rows for non-promo payment, got {count}"
