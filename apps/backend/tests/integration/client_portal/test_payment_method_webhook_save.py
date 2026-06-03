"""Phase 79 Plan 79-03 — Webhook token-save integration tests (PAYM-01).

Proves the three save_payment_method webhook path behaviors:
  1. save=true + bank_card payment_method in get_payment response → one client_payment_methods
     row with correct token/display fields, autopay_enabled=false, consent_recorded_at=NULL.
  2. save=false (or payment_method absent in response) → no client_payment_methods row.
  3. Two distinct succeeded payments for the SAME client → exactly one active row (upsert
     idempotency via the inference-predicate form
     ``ON CONFLICT (client_id) WHERE unlinked_at IS NULL`` — the partial unique index
     ``uq_client_payment_methods_client_id_alive`` is a CREATE INDEX, NOT a named constraint).
  4. Re-saving the SAME card token preserves existing autopay/consent; a NEW token resets them
     (CR-79-01).

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


def _build_get_payment_with_bank_card(
    yookassa_payment_id: str,
    *,
    token: str = _FAKE_TOKEN,
) -> dict[str, Any]:
    """Return a get_payment succeeded response body with bank_card payment_method.

    ``token`` overrides the saved payment_method.id so tests can simulate a
    same-token re-save (consent preserved) vs a new-token re-save (consent reset)
    on the step-8.5 upsert (CR-79-01).
    """
    return {
        "id": yookassa_payment_id,
        "status": "succeeded",
        "amount": {"value": "1000.00", "currency": "RUB"},
        "payment_method": {
            "type": "bank_card",
            "id": token,
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


async def _seed_second_pending_for_client(
    session: AsyncSession,
    *,
    client_id: object,
) -> SeededOnlinePayment:
    """Seed a SECOND pending OnlinePayment (save=True) for an existing client.

    Used to drive the step-8.5 upsert path TWICE (WR-79-02): two distinct
    succeeded payments for the same client each pass the FSM guard, so each one
    reaches the ON CONFLICT upsert (unlike redelivering the same payment, which
    short-circuits at the FSM guard before step 8.5).

    Creates a FRESH membership plan so the second row does not collide with the
    ``uq_online_payments_membership_double_tap`` unique index
    ``(client_id, membership_plan_id, day)`` — the realistic scenario is a
    second checkout for a DIFFERENT plan on the same day.
    """
    nonce = uuid4().hex[:8]
    plan = MembershipPlan(
        name=f"WH-Save-Plan2-{nonce}",
        duration_days=30,
        price_kopecks=100_000,
        freeze_days_limit=7,
        active=True,
    )
    session.add(plan)
    await session.flush()

    yk_id = f"yk-save2-{uuid4().hex[:24]}"
    corr = uuid4()
    op = OnlinePayment(
        client_id=client_id,
        membership_plan_id=plan.id,
        pt_package_plan_id=None,
        yookassa_payment_id=yk_id,
        idempotency_key=uuid4().hex,
        amount_kopecks=100_000,
        status=STATUS_PENDING,
        confirmation_url="https://example.com/confirm",
        confirmation_type=CONFIRMATION_TYPE_REDIRECT,
        audit_correlation_id=corr,
        save_payment_method=True,
    )
    session.add(op)
    await session.flush()
    await session.commit()
    return SeededOnlinePayment(
        online_payment_id=op.id,
        yookassa_payment_id=yk_id,
        client_id=client_id,  # type: ignore[arg-type]
        client_email="",
        client_phone="",
        membership_plan_id=plan.id,
        pt_package_plan_id=None,
        audit_correlation_id=corr,
        amount_kopecks=100_000,
    )


async def _enable_autopay_directly(
    session: AsyncSession,
    client_id: object,
) -> None:
    """Stamp autopay_enabled=true + consent_recorded_at=now() on the active card.

    Simulates a prior PATCH /autopay enable so the CR-79-01 re-save test can
    assert the consent survives an identical-token re-save. Raw SQL (D-54-08),
    commits so the webhook handler's per-request session sees it.
    """
    await session.execute(
        text(
            "UPDATE client_payment_methods "
            "SET autopay_enabled = true, consent_recorded_at = now() "
            "WHERE client_id = :client_id AND unlinked_at IS NULL"
        ),
        {"client_id": str(client_id)},
    )
    await session.commit()


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
    """T-79-09 / WR-79-02: the step-8.5 upsert runs TWICE → exactly one active row.

    Redelivering the SAME payment.succeeded would short-circuit at the FSM guard
    (the row is already ``succeeded``) and NEVER reach step 8.5 — so it cannot
    exercise the ON CONFLICT path. Instead this test seeds TWO distinct succeeded
    payments for the SAME client, each carrying ``save=True`` and the SAME card
    token. Both deliveries pass the FSM guard (distinct rows) and both reach the
    upsert, so the second genuinely drives ``ON CONFLICT (client_id) WHERE
    unlinked_at IS NULL DO UPDATE`` (the inference-predicate form — the partial
    unique index is a CREATE INDEX, NOT a named constraint).
    """
    seeded = await _seed_save_payment_online_payment(
        webhook_db_session,
        save_payment_method=True,
    )
    assert seeded.membership_plan_id is not None
    body1 = webhook_payment_succeeded_body(seeded.yookassa_payment_id)

    def _mock_get_payment(yk_id: str) -> httpx.Response:
        return httpx.Response(200, json=_build_get_payment_with_bank_card(yk_id))

    # First delivery → INSERT (the active card row is created).
    with respx.mock(base_url=_YOOKASSA_BASE_URL, assert_all_called=False) as mock:
        mock.get(url__regex=r"^https://api\.yookassa\.ru/v3/payments/[\w-]+$").mock(
            return_value=_mock_get_payment(seeded.yookassa_payment_id)
        )
        r1 = await webhook_client.post("/api/v1/_internal/yookassa/webhook", json=body1)
    assert r1.status_code == 200, f"First webhook delivery failed: {r1.text}"

    # Seed a SECOND distinct succeeded payment for the same client → its
    # payment.succeeded passes the FSM guard and reaches the step-8.5 upsert,
    # genuinely driving the ON CONFLICT DO UPDATE branch.
    seeded2 = await _seed_second_pending_for_client(
        webhook_db_session,
        client_id=seeded.client_id,
    )
    body2 = webhook_payment_succeeded_body(seeded2.yookassa_payment_id)
    with respx.mock(base_url=_YOOKASSA_BASE_URL, assert_all_called=False) as mock2:
        mock2.get(url__regex=r"^https://api\.yookassa\.ru/v3/payments/[\w-]+$").mock(
            return_value=_mock_get_payment(seeded2.yookassa_payment_id)
        )
        r2 = await webhook_client.post("/api/v1/_internal/yookassa/webhook", json=body2)
    assert r2.status_code == 200, f"Second webhook delivery failed: {r2.text}"

    await webhook_db_session.commit()

    # Exactly ONE active (unlinked_at IS NULL) row — upsert, not double-insert
    rows = await _fetch_payment_method_rows(webhook_db_session, seeded.client_id)
    active_rows = [row for row in rows if row["unlinked_at"] is None]
    assert len(active_rows) == 1, (
        f"Two distinct succeeded payments must produce exactly 1 active "
        f"client_payment_methods row, found {len(active_rows)} (total rows: {len(rows)})"
    )
    # Token + display fields preserved from the (idempotent) second upsert
    assert active_rows[0]["yookassa_method_id"] == _FAKE_TOKEN, (
        f"Token must be preserved after second upsert: {active_rows[0]['yookassa_method_id']!r}"
    )
    assert active_rows[0]["autopay_enabled"] is False, (
        "autopay_enabled must remain false after second upsert"
    )
    assert active_rows[0]["consent_recorded_at"] is None, (
        "consent_recorded_at must be NULL after second upsert"
    )


# ---------------------------------------------------------------------------
# Test 4: CR-79-01 — re-save preserves consent on same token, resets on new token
# ---------------------------------------------------------------------------


async def test_webhook_resave_same_token_preserves_autopay_consent(
    webhook_client: AsyncClient,
    webhook_db_session: AsyncSession,
    webhook_payment_succeeded_body: Callable[[str], dict[str, Any]],
) -> None:
    """CR-79-01: re-saving the SAME card token must PRESERVE autopay + consent.

    Sequence: save card → enable autopay (stamps consent) → a second payment
    re-saves the SAME token. The step-8.5 upsert must NOT wipe the live
    ФЗ-376 consent: autopay_enabled stays True and consent_recorded_at survives.
    """
    seeded = await _seed_save_payment_online_payment(
        webhook_db_session,
        save_payment_method=True,
    )
    assert seeded.membership_plan_id is not None

    def _mock_get_payment(yk_id: str, *, token: str) -> httpx.Response:
        return httpx.Response(200, json=_build_get_payment_with_bank_card(yk_id, token=token))

    # 1. First payment saves the card (token=_FAKE_TOKEN).
    with respx.mock(base_url=_YOOKASSA_BASE_URL, assert_all_called=False) as mock:
        mock.get(url__regex=r"^https://api\.yookassa\.ru/v3/payments/[\w-]+$").mock(
            return_value=_mock_get_payment(seeded.yookassa_payment_id, token=_FAKE_TOKEN)
        )
        r1 = await webhook_client.post(
            "/api/v1/_internal/yookassa/webhook",
            json=webhook_payment_succeeded_body(seeded.yookassa_payment_id),
        )
    assert r1.status_code == 200, f"First delivery failed: {r1.text}"

    # 2. Client later enables autopay (stamps consent_recorded_at).
    await _enable_autopay_directly(webhook_db_session, seeded.client_id)

    # 3. A second payment re-saves the SAME token.
    seeded2 = await _seed_second_pending_for_client(
        webhook_db_session,
        client_id=seeded.client_id,
    )
    with respx.mock(base_url=_YOOKASSA_BASE_URL, assert_all_called=False) as mock2:
        mock2.get(url__regex=r"^https://api\.yookassa\.ru/v3/payments/[\w-]+$").mock(
            return_value=_mock_get_payment(seeded2.yookassa_payment_id, token=_FAKE_TOKEN)
        )
        r2 = await webhook_client.post(
            "/api/v1/_internal/yookassa/webhook",
            json=webhook_payment_succeeded_body(seeded2.yookassa_payment_id),
        )
    assert r2.status_code == 200, f"Second delivery failed: {r2.text}"

    await webhook_db_session.commit()
    rows = await _fetch_payment_method_rows(webhook_db_session, seeded.client_id)
    active = [row for row in rows if row["unlinked_at"] is None]
    assert len(active) == 1, f"Expected 1 active row, found {len(active)}"
    assert active[0]["yookassa_method_id"] == _FAKE_TOKEN
    assert active[0]["autopay_enabled"] is True, (
        "Re-saving the SAME token must PRESERVE autopay_enabled=true (CR-79-01)"
    )
    assert active[0]["consent_recorded_at"] is not None, (
        "Re-saving the SAME token must PRESERVE consent_recorded_at (CR-79-01)"
    )


async def test_webhook_resave_new_token_resets_autopay_consent(
    webhook_client: AsyncClient,
    webhook_db_session: AsyncSession,
    webhook_payment_succeeded_body: Callable[[str], dict[str, Any]],
) -> None:
    """CR-79-01: re-saving a DIFFERENT card token RESETS autopay + consent.

    A new token means a new card, so the prior ФЗ-376 consent no longer applies
    and must be cleared (re-consent required): autopay_enabled→false,
    consent_recorded_at→NULL, and the stored token is the new one.
    """
    new_token = "fake-pm-token-9999-5000-a000-1d8b1d6e5c99"  # noqa: S105 — fake token, not a secret
    seeded = await _seed_save_payment_online_payment(
        webhook_db_session,
        save_payment_method=True,
    )
    assert seeded.membership_plan_id is not None

    def _mock_get_payment(yk_id: str, *, token: str) -> httpx.Response:
        return httpx.Response(200, json=_build_get_payment_with_bank_card(yk_id, token=token))

    with respx.mock(base_url=_YOOKASSA_BASE_URL, assert_all_called=False) as mock:
        mock.get(url__regex=r"^https://api\.yookassa\.ru/v3/payments/[\w-]+$").mock(
            return_value=_mock_get_payment(seeded.yookassa_payment_id, token=_FAKE_TOKEN)
        )
        r1 = await webhook_client.post(
            "/api/v1/_internal/yookassa/webhook",
            json=webhook_payment_succeeded_body(seeded.yookassa_payment_id),
        )
    assert r1.status_code == 200, f"First delivery failed: {r1.text}"

    await _enable_autopay_directly(webhook_db_session, seeded.client_id)

    # Second payment captures a DIFFERENT token (e.g. the client paid with a new card).
    seeded2 = await _seed_second_pending_for_client(
        webhook_db_session,
        client_id=seeded.client_id,
    )
    with respx.mock(base_url=_YOOKASSA_BASE_URL, assert_all_called=False) as mock2:
        mock2.get(url__regex=r"^https://api\.yookassa\.ru/v3/payments/[\w-]+$").mock(
            return_value=_mock_get_payment(seeded2.yookassa_payment_id, token=new_token)
        )
        r2 = await webhook_client.post(
            "/api/v1/_internal/yookassa/webhook",
            json=webhook_payment_succeeded_body(seeded2.yookassa_payment_id),
        )
    assert r2.status_code == 200, f"Second delivery failed: {r2.text}"

    await webhook_db_session.commit()
    rows = await _fetch_payment_method_rows(webhook_db_session, seeded.client_id)
    active = [row for row in rows if row["unlinked_at"] is None]
    assert len(active) == 1, f"Expected 1 active row, found {len(active)}"
    assert active[0]["yookassa_method_id"] == new_token, (
        "New token must replace the stored token (CR-79-01)"
    )
    assert active[0]["autopay_enabled"] is False, (
        "A NEW token must RESET autopay_enabled to false (CR-79-01)"
    )
    assert active[0]["consent_recorded_at"] is None, (
        "A NEW token must CLEAR consent_recorded_at (CR-79-01)"
    )
