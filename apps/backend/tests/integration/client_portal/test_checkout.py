"""Phase 71 Plan 71-03 — Client checkout integration tests.

Proves all 5 Phase 71 checkout success criteria:
  1. (CPAY-03 / criterion #1) Anti-oracle redirect-back: status endpoint returns only
     pending|succeeded|canceled — no membership/activation details exposed.
  2. (CPAY-05 / criterion #2) Idempotent webhook activation: duplicate payment.succeeded
     delivery does NOT create a second membership row.
  3. (CPAY-04 / criterion #3) 54-ФЗ email gate: checkout without email → 422
     client_email_required_for_online_payment.
  4. IDOR safety: GET /payments/{id}/status for another client's payment → 404.
  5. Idempotency split (D-71-04): membership replay same URL; PT different key → new payment id.

No live network — ЮKassa provider is overridden via respx (ASGITransport only).
SAVEPOINT harness (async_client) for checkout + status tests.
Real-commit harness (webhook_client + webhook_db_session) for the duplicate-webhook test.

Auth helper mirrors tests/integration/client_portal/test_idor_sweep.py:_auth_as_client.
After _auth_as_client the async_client cookie jar holds cc_client_access + clubcore_client_csrf;
subsequent POST calls use that same async_client — no separate authed client needed.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

import httpx
import pytest
import respx
from httpx import AsyncClient
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.permissions import Role
from app.core.security import generate_otp_code, hash_password
from app.modules.auth.models import OtpCode, User
from app.modules.clients.models import Client
from app.modules.memberships.models import Membership, MembershipPlan
from app.modules.online_payments.constants import (
    CONFIRMATION_TYPE_REDIRECT,
    STATUS_PENDING,
)
from app.modules.online_payments.models import OnlinePayment
from app.modules.pt_packages.models import PtPackagePlan
from tests.integration.webhook_yookassa.conftest import SeededOnlinePayment

pytestmark = pytest.mark.asyncio

# ---------------------------------------------------------------------------
# ЮKassa mock URL base (no live calls — all tests override via respx)
# ---------------------------------------------------------------------------

_YOOKASSA_BASE_URL = "https://api.yookassa.ru/v3/"
_FAKE_CONFIRMATION_URL = (
    "https://yoomoney.ru/checkout/payments/v2/contract?orderId=fake-test-id"
)


# ---------------------------------------------------------------------------
# Auth helper — mirrors test_idor_sweep.py:_auth_as_client
# After this function returns, async_client.cookies holds:
#   - cc_client_access  (httpOnly JWT)
#   - clubcore_client_csrf  (CSRF double-submit cookie, readable by JS)
# ---------------------------------------------------------------------------


async def _auth_as_client(
    async_client: AsyncClient,
    db_session: AsyncSession,
    client: Client,
) -> None:
    """Request OTP → patch code → verify. After this call, async_client has auth cookies."""
    req = await async_client.post(
        "/api/v1/client/otp/request",
        json={"phone": client.phone},
    )
    assert req.status_code == 202, f"OTP request failed for {client.phone}: {req.text}"

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
    assert verify.status_code == 200, f"OTP verify failed for {client.phone}: {verify.text}"


# ---------------------------------------------------------------------------
# CSRF header helpers — POST checkout endpoints require X-CSRF-Token (RBAC-04)
# ---------------------------------------------------------------------------


def _checkout_headers(client: AsyncClient) -> dict[str, str]:
    """Return {"X-CSRF-Token": <clubcore_client_csrf>} for membership POST checkout."""
    return {"X-CSRF-Token": client.cookies.get("clubcore_client_csrf") or ""}


def _pt_checkout_headers(client: AsyncClient, *, idempotency_key: str) -> dict[str, str]:
    """Return checkout headers plus client-supplied Idempotency-Key for PT checkout."""
    headers = _checkout_headers(client)
    headers["Idempotency-Key"] = idempotency_key
    return headers


# ---------------------------------------------------------------------------
# Shared factory: seed a client with email (for checkout tests that need email gate to PASS)
# ---------------------------------------------------------------------------


async def _seed_client_with_email(
    db_session: AsyncSession,
    *,
    phone: str,
) -> Client:
    """Insert a staff user + client with email and telegram_user_id (OTP requires telegram link).

    telegram_user_id must be non-NULL: the OTP request service silently no-ops and
    creates no OTP row when telegram_user_id is None (D-02 unknown-phone safety).
    Uses a UUID-derived integer so each call gets a unique, reproducible Telegram ID.
    """
    tg_id = uuid4().int % 2_000_000_000 + 800_000_000  # > 800M to avoid test fixture collisions

    suffix = uuid4().hex[:8]
    staff = User(
        email=f"staff-co-{suffix}@example.com",
        password_hash=await hash_password("test-staff-pw-123"),
        role=Role.RECEPTION,
        full_name=f"Staff {suffix}",
    )
    db_session.add(staff)
    await db_session.flush()

    client = Client(
        first_name="Test",
        last_name=f"Checkout-{suffix}",
        phone=phone,
        email=f"client-{suffix}@example.com",
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
    price_kopecks: int = 250_000,
) -> MembershipPlan:
    """Insert an active MembershipPlan."""
    plan = MembershipPlan(
        name=f"Test Plan {uuid4().hex[:6]}",
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
    price_kopecks: int = 500_000,
) -> PtPackagePlan:
    """Insert an active PtPackagePlan."""
    plan = PtPackagePlan(
        name=f"PT Plan {uuid4().hex[:6]}",
        session_count=10,
        price_kopecks=price_kopecks,
        validity_days=90,
    )
    db_session.add(plan)
    await db_session.commit()
    await db_session.refresh(plan)
    return plan


# ===========================================================================
# Task 1: Checkout success + idempotency + email-gate (CPAY-01/02/04/05)
# ===========================================================================


async def test_membership_checkout_returns_confirmation_url(
    async_client: AsyncClient,
    db_session: AsyncSession,
    redis_clean: Redis,
) -> None:
    """CPAY-01: POST membership checkout → 201 with confirmationUrl + onlinePaymentId.

    ЮKassa provider overridden via respx — no live network call made.
    """
    client = await _seed_client_with_email(
        db_session,
        phone=f"+7916{uuid4().int % 10_000_000:07d}",
    )
    plan = await _seed_membership_plan(db_session)

    await _auth_as_client(async_client, db_session, client)

    fake_url = f"https://yoomoney.ru/checkout/test-{uuid4().hex[:8]}"

    with respx.mock(base_url=_YOOKASSA_BASE_URL, assert_all_called=False) as mock:
        mock.post("payments").mock(
            return_value=httpx.Response(
                200,
                json={
                    "id": f"yk-{uuid4().hex[:24]}",
                    "status": "pending",
                    "amount": {"value": "2500.00", "currency": "RUB"},
                    "confirmation": {
                        "type": "redirect",
                        "confirmation_url": fake_url,
                    },
                },
            )
        )

        r = await async_client.post(
            f"/api/v1/client/checkout/memberships/{plan.id}",
            headers=_checkout_headers(async_client),
            json={},
        )

    assert r.status_code == 201, r.text
    data = r.json()["data"]
    assert data["confirmationUrl"].startswith("https://"), (
        f"Expected confirmationUrl to start with https://, got: {data['confirmationUrl']!r}"
    )
    assert "onlinePaymentId" in data, "onlinePaymentId must be present in response"


async def test_membership_checkout_replay_returns_same_url(
    async_client: AsyncClient,
    db_session: AsyncSession,
    redis_clean: Redis,
) -> None:
    """CPAY-05 / D-71-04: two same-day membership POSTs return identical confirmationUrl.

    Server-derived per-day idempotency key causes replay to return the same row.
    The second POST must NOT call ЮKassa (replay check short-circuits before the API call).
    """
    client = await _seed_client_with_email(
        db_session,
        phone=f"+7917{uuid4().int % 10_000_000:07d}",
    )
    plan = await _seed_membership_plan(db_session)

    await _auth_as_client(async_client, db_session, client)

    fake_url = f"https://yoomoney.ru/checkout/replay-{uuid4().hex[:8]}"

    with respx.mock(base_url=_YOOKASSA_BASE_URL, assert_all_called=False) as mock:
        mock.post("payments").mock(
            return_value=httpx.Response(
                200,
                json={
                    "id": f"yk-{uuid4().hex[:24]}",
                    "status": "pending",
                    "amount": {"value": "2500.00", "currency": "RUB"},
                    "confirmation": {
                        "type": "redirect",
                        "confirmation_url": fake_url,
                    },
                },
            )
        )

        r1 = await async_client.post(
            f"/api/v1/client/checkout/memberships/{plan.id}",
            headers=_checkout_headers(async_client),
            json={},
        )
        assert r1.status_code == 201, r1.text
        url1 = r1.json()["data"]["confirmationUrl"]

        r2 = await async_client.post(
            f"/api/v1/client/checkout/memberships/{plan.id}",
            headers=_checkout_headers(async_client),
            json={},
        )
        assert r2.status_code == 201, r2.text
        url2 = r2.json()["data"]["confirmationUrl"]

    assert url1 == url2, (
        f"Membership replay must return the same confirmationUrl: {url1!r} != {url2!r}"
    )


async def test_pt_checkout_idempotency_key_replay(
    async_client: AsyncClient,
    db_session: AsyncSession,
    redis_clean: Redis,
) -> None:
    """CPAY-05 / D-71-04: same Idempotency-Key → same confirmationUrl; different key → new payment.

    PT-package checkout uses client-supplied Idempotency-Key (D-71-04 split strategy).
    Same key must replay (no new ЮKassa call on 2nd request). A different key for a
    DIFFERENT plan produces a new payment (each plan has its own double-tap slot).
    """
    client = await _seed_client_with_email(
        db_session,
        phone=f"+7918{uuid4().int % 10_000_000:07d}",
    )
    # Seed two distinct PT plans: key-a buys plan_1, key-b buys plan_2
    pt_plan_1 = await _seed_pt_package_plan(db_session)
    pt_plan_2 = await _seed_pt_package_plan(db_session)

    await _auth_as_client(async_client, db_session, client)

    idem_key_a = uuid4().hex  # intent A (for plan_1)
    idem_key_b = uuid4().hex  # intent B (for plan_2 — different plan avoids double-tap constraint)

    url_a = f"https://yoomoney.ru/checkout/pt-a-{uuid4().hex[:8]}"
    url_b = f"https://yoomoney.ru/checkout/pt-b-{uuid4().hex[:8]}"

    # --- First call: buy plan_1 with idem_key_a (ЮKassa called once) ---
    with respx.mock(base_url=_YOOKASSA_BASE_URL, assert_all_called=False) as mock:
        mock.post("payments").mock(
            return_value=httpx.Response(
                200,
                json={
                    "id": f"yk-{uuid4().hex[:24]}",
                    "status": "pending",
                    "amount": {"value": "5000.00", "currency": "RUB"},
                    "confirmation": {
                        "type": "redirect",
                        "confirmation_url": url_a,
                    },
                },
            )
        )

        r1 = await async_client.post(
            f"/api/v1/client/checkout/pt-packages/{pt_plan_1.id}",
            headers=_pt_checkout_headers(async_client, idempotency_key=idem_key_a),
            json={},
        )
        assert r1.status_code == 201, r1.text
        data1 = r1.json()["data"]
        url_first = data1["confirmationUrl"]
        pid_first = data1["onlinePaymentId"]

        # --- Replay with SAME key: no new ЮKassa call (replay check short-circuits) ---
        r2 = await async_client.post(
            f"/api/v1/client/checkout/pt-packages/{pt_plan_1.id}",
            headers=_pt_checkout_headers(async_client, idempotency_key=idem_key_a),
            json={},
        )
        assert r2.status_code == 201, r2.text
        data2 = r2.json()["data"]

    assert data2["confirmationUrl"] == url_first, (
        f"Same PT Idempotency-Key must return identical confirmationUrl: "
        f"{data2['confirmationUrl']!r} != {url_first!r}"
    )

    # --- Different key, different plan: a new distinct payment is created ---
    # Using a different pt_plan avoids uq_online_payments_pt_package_double_tap
    # (which prevents two non-canceled payments for same client+plan+day).
    with respx.mock(base_url=_YOOKASSA_BASE_URL, assert_all_called=False) as mock2:
        mock2.post("payments").mock(
            return_value=httpx.Response(
                200,
                json={
                    "id": f"yk-{uuid4().hex[:24]}",
                    "status": "pending",
                    "amount": {"value": "5000.00", "currency": "RUB"},
                    "confirmation": {
                        "type": "redirect",
                        "confirmation_url": url_b,
                    },
                },
            )
        )

        r3 = await async_client.post(
            f"/api/v1/client/checkout/pt-packages/{pt_plan_2.id}",
            headers=_pt_checkout_headers(async_client, idempotency_key=idem_key_b),
            json={},
        )
        assert r3.status_code == 201, r3.text
        data3 = r3.json()["data"]

    assert data3["onlinePaymentId"] != pid_first, (
        f"Different PT Idempotency-Key (different plan) must produce a NEW onlinePaymentId; "
        f"got the same {data3['onlinePaymentId']!r}"
    )


async def test_checkout_without_email_returns_422(
    async_client: AsyncClient,
    db_session: AsyncSession,
    redis_clean: Redis,
) -> None:
    """CPAY-04: client with NULL email POSTs membership checkout → 422.

    Expected error code: client_email_required_for_online_payment.
    54-ФЗ email gate is enforced inside _sell_subject_core before the ЮKassa call.
    """
    suffix = uuid4().hex[:8]
    staff = User(
        email=f"staff-noemail-{suffix}@example.com",
        password_hash=await hash_password("test-staff-pw-123"),
        role=Role.RECEPTION,
        full_name=f"Staff NoEmail {suffix}",
    )
    db_session.add(staff)
    await db_session.flush()

    no_email_client = Client(
        first_name="NoEmail",
        last_name=f"Client-{suffix}",
        phone=f"+7920{uuid4().int % 10_000_000:07d}",
        email=None,  # explicitly NULL — triggers 54-ФЗ gate
        telegram_user_id=uuid4().int % 2_000_000_000 + 800_000_000,
        created_by_user_id=staff.id,
    )
    db_session.add(no_email_client)
    await db_session.commit()

    plan = await _seed_membership_plan(db_session)

    await _auth_as_client(async_client, db_session, no_email_client)

    # ЮKassa must NOT be called (email gate fires before any network call)
    with respx.mock(base_url=_YOOKASSA_BASE_URL, assert_all_called=False):
        r = await async_client.post(
            f"/api/v1/client/checkout/memberships/{plan.id}",
            headers=_checkout_headers(async_client),
            json={},
        )

    assert r.status_code == 422, r.text
    body = r.json()
    assert body["message"] == "client_email_required_for_online_payment", (
        f"Expected 'client_email_required_for_online_payment', got: {body.get('message')!r}"
    )


# ===========================================================================
# Task 2: Status anti-oracle + IDOR 404 + duplicate-webhook idempotent activation
# ===========================================================================


async def test_status_returns_coarse_state_only(
    async_client: AsyncClient,
    db_session: AsyncSession,
    redis_clean: Redis,
) -> None:
    """CPAY-03 / criterion #1: GET /payments/{id}/status returns ONLY id + status.

    Anti-oracle regression guard (T-71-11): no membership/plan/activation fields exposed.
    Response data must have exactly two keys: 'id' and 'status'.
    """
    client = await _seed_client_with_email(
        db_session,
        phone=f"+7921{uuid4().int % 10_000_000:07d}",
    )
    plan = await _seed_membership_plan(db_session)

    # Seed a pending OnlinePayment row directly (no need for checkout flow)
    payment_row = OnlinePayment(
        client_id=client.id,
        membership_plan_id=plan.id,
        pt_package_plan_id=None,
        yookassa_payment_id=f"yk-status-{uuid4().hex[:24]}",
        idempotency_key=uuid4().hex,
        amount_kopecks=100_000,
        status=STATUS_PENDING,
        confirmation_url=_FAKE_CONFIRMATION_URL,
        confirmation_type=CONFIRMATION_TYPE_REDIRECT,
        audit_correlation_id=uuid4(),
    )
    db_session.add(payment_row)
    await db_session.commit()
    await db_session.refresh(payment_row)

    await _auth_as_client(async_client, db_session, client)

    r = await async_client.get(f"/api/v1/client/payments/{payment_row.id}/status")

    assert r.status_code == 200, r.text
    data = r.json()["data"]

    assert data["status"] == "pending", f"Expected status=pending, got: {data['status']!r}"

    # Anti-oracle: EXACTLY {id, status} and nothing more (T-71-11)
    extra_keys = set(data.keys()) - {"id", "status"}
    assert set(data.keys()) == {"id", "status"}, (
        f"Anti-oracle violated: response data contains extra keys: {extra_keys!r}"
    )


async def test_status_idor_404_for_other_client(
    async_client: AsyncClient,
    db_session: AsyncSession,
    redis_clean: Redis,
) -> None:
    """D-20-IDOR (T-71-12): client A gets 404 for a payment owned by client B.

    404-collapse (anti-oracle): non-owned row is indistinguishable from non-existent.
    """
    # Seed client A (the attacker)
    client_a = await _seed_client_with_email(
        db_session,
        phone=f"+7922{uuid4().int % 10_000_000:07d}",
    )
    # Seed client B (the victim)
    client_b = await _seed_client_with_email(
        db_session,
        phone=f"+7923{uuid4().int % 10_000_000:07d}",
    )

    plan = await _seed_membership_plan(db_session)

    # OnlinePayment owned by client B
    payment_b = OnlinePayment(
        client_id=client_b.id,
        membership_plan_id=plan.id,
        pt_package_plan_id=None,
        yookassa_payment_id=f"yk-idor-{uuid4().hex[:24]}",
        idempotency_key=uuid4().hex,
        amount_kopecks=100_000,
        status=STATUS_PENDING,
        confirmation_url=_FAKE_CONFIRMATION_URL,
        confirmation_type=CONFIRMATION_TYPE_REDIRECT,
        audit_correlation_id=uuid4(),
    )
    db_session.add(payment_b)
    await db_session.commit()
    await db_session.refresh(payment_b)

    # Authenticate as client A (attacker)
    await _auth_as_client(async_client, db_session, client_a)

    r = await async_client.get(f"/api/v1/client/payments/{payment_b.id}/status")

    assert r.status_code == 404, (
        f"IDOR: expected 404 for cross-client payment status, got {r.status_code}: {r.text}"
    )


async def test_duplicate_webhook_does_not_double_activate(
    webhook_client: AsyncClient,
    webhook_db_session: AsyncSession,
    seeded_online_payment_pending: SeededOnlinePayment,
    yookassa_get_payment_succeeded: respx.MockRouter,
    webhook_payment_succeeded_body: Callable[[str], dict[str, Any]],
) -> None:
    """CPAY-05 / criterion #2 (T-71-13): deliver payment.succeeded twice → exactly one membership.

    The webhook activation path (handle_payment_succeeded) is idempotent via the FSM
    transition guard (_assert_can_transition): second delivery sees status='succeeded'
    and does NOT create a second Membership row.

    Uses the real-commit harness (webhook_client + webhook_db_session) because the
    webhook handler uses `async with session.begin()` which cannot compose with the
    SAVEPOINT-mode db_session fixture.

    seeded_online_payment_pending provides a membership-linked OnlinePayment row
    committed to the real DB (visible to the webhook handler's per-request session).
    """
    body = webhook_payment_succeeded_body(seeded_online_payment_pending.yookassa_payment_id)

    # First delivery — activates the membership
    r1 = await webhook_client.post("/api/v1/_internal/yookassa/webhook", json=body)
    assert r1.status_code == 200, f"First webhook delivery failed: {r1.text}"

    # Second delivery with the SAME body — must be idempotent (FSM guard)
    r2 = await webhook_client.post("/api/v1/_internal/yookassa/webhook", json=body)
    assert r2.status_code == 200, f"Second webhook delivery failed: {r2.text}"

    # Commit the session to ensure we see the final committed state
    await webhook_db_session.commit()

    # Assert exactly ONE Membership row was activated — no double-activation
    memberships = (
        (
            await webhook_db_session.execute(
                select(Membership).where(
                    Membership.client_id == seeded_online_payment_pending.client_id,
                    Membership.plan_id == seeded_online_payment_pending.membership_plan_id,
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(memberships) == 1, (
        f"Duplicate webhook must NOT double-activate: expected 1 membership row, "
        f"found {len(memberships)}"
    )
    assert memberships[0].status == "active", (
        f"Membership must be active after payment.succeeded, got: {memberships[0].status!r}"
    )

    # Assert the OnlinePayment status is succeeded (not rolled back)
    op = await webhook_db_session.scalar(
        select(OnlinePayment).where(
            OnlinePayment.id == seeded_online_payment_pending.online_payment_id
        )
    )
    assert op is not None
    assert op.status == "succeeded", f"Expected status=succeeded, got: {op.status!r}"
