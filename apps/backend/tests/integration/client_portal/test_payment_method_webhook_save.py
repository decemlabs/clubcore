"""Phase 79 Plan 79-03 — Webhook token-save integration tests (PAYM-01).

Proves the three save_payment_method webhook path behaviors:
  1. save=true + bank_card payment_method in get_payment response → one client_payment_methods
     row with correct token/display fields, autopay_enabled=false, consent_recorded_at=NULL.
  2. save=false (or payment_method absent in response) → no client_payment_methods row.
  3. Duplicate delivery of the same payment.succeeded → exactly one active row (upsert idempotency,
     ON CONFLICT ON CONSTRAINT uq_client_payment_methods_client_id_alive).

Token source: result.payment_method from get_payment re-fetch (PAYM-01 / D-06 / D-50-18 step 8.5).
PAN/CVV never stored — only token + last4/brand/expiry display fields.

No live network — ЮKassa GET /payments/{id} is overridden via respx.
Real-commit harness (webhook_client + webhook_db_session) required because the webhook handler
uses `async with session.begin():` which cannot compose with the SAVEPOINT-mode db_session.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any
from uuid import uuid4

import httpx
import pytest
import respx
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.memberships.models import MembershipPlan
from app.modules.online_payments.constants import CONFIRMATION_TYPE_REDIRECT, STATUS_PENDING
from app.modules.online_payments.models import OnlinePayment
from tests.integration.webhook_yookassa.conftest import SeededOnlinePayment

pytestmark = pytest.mark.asyncio

_YOOKASSA_BASE_URL = "https://api.yookassa.ru/v3/"

# ---------------------------------------------------------------------------
# Fake bank_card payment_method returned by get_payment when save=True
# ---------------------------------------------------------------------------

_FAKE_TOKEN = "fake-pm-token-0001-5000-a000-1d8b1d6e5c45"  # noqa: S105 — fake YooKassa method id, not a secret
_FAKE_LAST4 = "4242"
_FAKE_CARD_TYPE = "MasterCard"
_FAKE_EXPIRY_MONTH = 11
_FAKE_EXPIRY_YEAR = 2027


def _build_get_payment_with_bank_card(yookassa_payment_id: str) -> dict[str, Any]:
    """Return a get_payment succeeded response body with bank_card payment_method."""
    return {
        "id": yookassa_payment_id,
        "status": "succeeded",
        "amount": {"value": "1000.00", "currency": "RUB"},
        "payment_method": {
            "type": "bank_card",
            "id": _FAKE_TOKEN,
            "saved": True,
            "card": {
                "first6": "424242",
                "last4": _FAKE_LAST4,
                "card_type": _FAKE_CARD_TYPE,
                "expiry_month": str(_FAKE_EXPIRY_MONTH),
                "expiry_year": str(_FAKE_EXPIRY_YEAR),
            },
        },
        "captured_at": "2026-06-03T10:02:00.000Z",
        "created_at": "2026-06-03T10:00:05.000Z",
        "test": True,
        "paid": True,
        "refundable": True,
    }


def _build_get_payment_without_bank_card(yookassa_payment_id: str) -> dict[str, Any]:
    """Return a get_payment succeeded response body WITHOUT bank_card payment_method."""
    return {
        "id": yookassa_payment_id,
        "status": "succeeded",
        "amount": {"value": "1000.00", "currency": "RUB"},
        # No payment_method field at all — simulates a non-card payment
        "captured_at": "2026-06-03T10:02:00.000Z",
        "created_at": "2026-06-03T10:00:05.000Z",
        "test": True,
        "paid": True,
        "refundable": True,
    }


# ---------------------------------------------------------------------------
# Helper factories (seed OnlinePayment with save_payment_method flag)
# ---------------------------------------------------------------------------


async def _seed_save_payment_online_payment(
    session: AsyncSession,
    *,
    save_payment_method: bool = True,
) -> SeededOnlinePayment:
    """Seed a pending OnlinePayment row with the given save_payment_method flag.

    Mirrors the webhook_yookassa/conftest.py seeded_online_payment_pending pattern
    but exposes the save_payment_method column so tests can toggle the flag.
    Commits the session so the row is visible to the webhook handler's per-request session.
    """
    from app.core.models import User
    from app.core.permissions import Role
    from app.core.security import hash_password

    nonce = uuid4().hex[:8]
    owner = User(
        email=f"wh-save-owner-{nonce}@example.com",
        password_hash=await hash_password("hunter22hunter22"),
        role=Role.OWNER,
        full_name=f"WH Save Test Owner {nonce}",
    )
    session.add(owner)
    await session.flush()

    from app.modules.clients.models import Client

    client = Client(
        last_name="Тестов",
        first_name="Тест",
        phone=f"+7900{nonce}",
        email=f"wh-save-{nonce}@example.com",
        created_by_user_id=owner.id,
    )
    session.add(client)
    await session.flush()

    plan = MembershipPlan(
        name=f"WH-Save-Plan-{nonce}",
        duration_days=30,
        price_kopecks=100_000,
        freeze_days_limit=7,
        active=True,
    )
    session.add(plan)
    await session.flush()

    yk_id = f"yk-save-{uuid4().hex[:24]}"
    corr = uuid4()
    op = OnlinePayment(
        client_id=client.id,
        membership_plan_id=plan.id,
        pt_package_plan_id=None,
        yookassa_payment_id=yk_id,
        idempotency_key=uuid4().hex,
        amount_kopecks=100_000,
        status=STATUS_PENDING,
        confirmation_url="https://example.com/confirm",
        confirmation_type=CONFIRMATION_TYPE_REDIRECT,
        audit_correlation_id=corr,
        save_payment_method=save_payment_method,
    )
    session.add(op)
    await session.flush()
    await session.commit()

    return SeededOnlinePayment(
        online_payment_id=op.id,
        yookassa_payment_id=yk_id,
        client_id=client.id,
        client_email=client.email or "",
        client_phone=client.phone,
        membership_plan_id=plan.id,
        pt_package_plan_id=None,
        audit_correlation_id=corr,
        amount_kopecks=100_000,
    )


async def _fetch_payment_method_rows(
    session: AsyncSession,
    client_id: object,
) -> list[dict[str, Any]]:
    """Fetch all client_payment_methods rows for a client (including unlinked).

    Returns a list of dicts for assertions. Uses raw SQL (D-54-08).
    """
    rows = (
        (
            await session.execute(
                text(
                    "SELECT id, yookassa_method_id, last4, brand, "
                    "expiry_month, expiry_year, autopay_enabled, consent_recorded_at, unlinked_at "
                    "FROM client_payment_methods "
                    "WHERE client_id = :client_id"
                ),
                {"client_id": str(client_id)},
            )
        )
        .mappings()
        .all()
    )
    return [dict(row) for row in rows]


# ---------------------------------------------------------------------------
# Test 1: save=True + bank_card → row saved with token + display fields
# ---------------------------------------------------------------------------


async def test_webhook_save_true_upserts_card_token(
    webhook_client: AsyncClient,
    webhook_db_session: AsyncSession,
    webhook_payment_succeeded_body: Callable[[str], dict[str, Any]],
) -> None:
    """PAYM-01: payment.succeeded with save_payment_method=True + bank_card response
    → exactly one client_payment_methods row with token, last4, brand, expiry;
    autopay_enabled=false, consent_recorded_at=NULL (T-79-09 idempotency behavior confirmed
    by test_webhook_save_replay_idempotent).
    """
    seeded = await _seed_save_payment_online_payment(
        webhook_db_session,
        save_payment_method=True,
    )
    body = webhook_payment_succeeded_body(seeded.yookassa_payment_id)

    with respx.mock(base_url=_YOOKASSA_BASE_URL, assert_all_called=False) as mock:
        mock.get(url__regex=r"^https://api\.yookassa\.ru/v3/payments/[\w-]+$").mock(
            return_value=httpx.Response(
                200,
                json=_build_get_payment_with_bank_card(seeded.yookassa_payment_id),
            )
        )
        r = await webhook_client.post("/api/v1/_internal/yookassa/webhook", json=body)

    assert r.status_code == 200, f"Webhook delivery failed: {r.text}"

    # Verify the card row was upserted
    await webhook_db_session.commit()
    rows = await _fetch_payment_method_rows(webhook_db_session, seeded.client_id)
    assert len(rows) == 1, (
        f"Expected 1 client_payment_methods row after save=True, found {len(rows)}"
    )
    row = rows[0]
    assert row["yookassa_method_id"] == _FAKE_TOKEN, (
        f"Expected token {_FAKE_TOKEN!r}, got {row['yookassa_method_id']!r}"
    )
    assert row["last4"] == _FAKE_LAST4, f"Expected last4={_FAKE_LAST4!r}, got {row['last4']!r}"
    assert row["brand"] == _FAKE_CARD_TYPE, (
        f"Expected brand={_FAKE_CARD_TYPE!r}, got {row['brand']!r}"
    )
    assert row["expiry_month"] == _FAKE_EXPIRY_MONTH, (
        f"Expected expiry_month={_FAKE_EXPIRY_MONTH}, got {row['expiry_month']}"
    )
    assert row["expiry_year"] == _FAKE_EXPIRY_YEAR, (
        f"Expected expiry_year={_FAKE_EXPIRY_YEAR}, got {row['expiry_year']}"
    )
    assert row["autopay_enabled"] is False, (
        f"autopay_enabled must be false after initial save, got {row['autopay_enabled']!r}"
    )
    assert row["consent_recorded_at"] is None, (
        f"consent_recorded_at must be NULL after initial save, got {row['consent_recorded_at']!r}"
    )
    assert row["unlinked_at"] is None, (
        f"unlinked_at must be NULL (card is active), got {row['unlinked_at']!r}"
    )


# ---------------------------------------------------------------------------
# Test 2: save=False → no row created
# ---------------------------------------------------------------------------


async def test_webhook_save_false_no_card_row(
    webhook_client: AsyncClient,
    webhook_db_session: AsyncSession,
    webhook_payment_succeeded_body: Callable[[str], dict[str, Any]],
) -> None:
    """PAYM-01: payment.succeeded with save_payment_method=False → no client_payment_methods row,
    even if the get_payment response contains a bank_card payment_method.
    """
    seeded = await _seed_save_payment_online_payment(
        webhook_db_session,
        save_payment_method=False,
    )
    body = webhook_payment_succeeded_body(seeded.yookassa_payment_id)

    # Provide a response WITH bank_card to confirm the guard is on save_payment_method, not
    # the response content.
    with respx.mock(base_url=_YOOKASSA_BASE_URL, assert_all_called=False) as mock:
        mock.get(url__regex=r"^https://api\.yookassa\.ru/v3/payments/[\w-]+$").mock(
            return_value=httpx.Response(
                200,
                json=_build_get_payment_with_bank_card(seeded.yookassa_payment_id),
            )
        )
        r = await webhook_client.post("/api/v1/_internal/yookassa/webhook", json=body)

    assert r.status_code == 200, f"Webhook delivery failed: {r.text}"

    await webhook_db_session.commit()
    rows = await _fetch_payment_method_rows(webhook_db_session, seeded.client_id)
    assert len(rows) == 0, (
        f"Expected 0 client_payment_methods rows when save_payment_method=False, found {len(rows)}"
    )


# ---------------------------------------------------------------------------
# Test 3: Replay idempotency — duplicate delivery → exactly one active row
# ---------------------------------------------------------------------------


async def test_webhook_save_replay_idempotent(
    webhook_client: AsyncClient,
    webhook_db_session: AsyncSession,
    webhook_payment_succeeded_body: Callable[[str], dict[str, Any]],
) -> None:
    """T-79-09: delivering payment.succeeded twice with save=True → exactly one active row.

    The ON CONFLICT ON CONSTRAINT uq_client_payment_methods_client_id_alive DO UPDATE
    upsert ensures replay is idempotent — no duplicate rows, just an UPDATE in place.
    """
    seeded = await _seed_save_payment_online_payment(
        webhook_db_session,
        save_payment_method=True,
    )
    body = webhook_payment_succeeded_body(seeded.yookassa_payment_id)

    def _mock_get_payment(yk_id: str) -> httpx.Response:
        return httpx.Response(200, json=_build_get_payment_with_bank_card(yk_id))

    # First delivery
    with respx.mock(base_url=_YOOKASSA_BASE_URL, assert_all_called=False) as mock:
        mock.get(url__regex=r"^https://api\.yookassa\.ru/v3/payments/[\w-]+$").mock(
            return_value=_mock_get_payment(seeded.yookassa_payment_id)
        )
        r1 = await webhook_client.post("/api/v1/_internal/yookassa/webhook", json=body)
    assert r1.status_code == 200, f"First webhook delivery failed: {r1.text}"

    # Second delivery — FSM guard prevents double-activation; step 8.5 upsert is idempotent
    with respx.mock(base_url=_YOOKASSA_BASE_URL, assert_all_called=False) as mock2:
        mock2.get(url__regex=r"^https://api\.yookassa\.ru/v3/payments/[\w-]+$").mock(
            return_value=_mock_get_payment(seeded.yookassa_payment_id)
        )
        r2 = await webhook_client.post("/api/v1/_internal/yookassa/webhook", json=body)
    assert r2.status_code == 200, f"Second webhook delivery failed: {r2.text}"

    await webhook_db_session.commit()

    # Exactly ONE active (unlinked_at IS NULL) row — upsert, not double-insert
    rows = await _fetch_payment_method_rows(webhook_db_session, seeded.client_id)
    active_rows = [row for row in rows if row["unlinked_at"] is None]
    assert len(active_rows) == 1, (
        f"Replay must produce exactly 1 active client_payment_methods row, "
        f"found {len(active_rows)} (total rows: {len(rows)})"
    )
    # Token + display fields preserved from the (idempotent) second upsert
    assert active_rows[0]["yookassa_method_id"] == _FAKE_TOKEN, (
        f"Token must be preserved after replay: {active_rows[0]['yookassa_method_id']!r}"
    )
    assert active_rows[0]["autopay_enabled"] is False, (
        "autopay_enabled must remain false after replay"
    )
    assert active_rows[0]["consent_recorded_at"] is None, (
        "consent_recorded_at must be NULL after replay"
    )
