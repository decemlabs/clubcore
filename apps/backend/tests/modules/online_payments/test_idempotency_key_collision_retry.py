"""Plan 999.5-06 Task 2 — Idempotence-Key collision single-retry in _sell_subject_core.

Closes UAT-10 (MAJOR): the deterministic per-(subject_kind, plan_id, client_id,
UTC-date) membership key (``_derive_idempotency_key``) excludes the receipt
contact. Phase 999.5's email-OR-phone gate makes the SAME client+plan+day
produce different receipt bodies (phone-only «Чек не нужен» vs email gate).
Reusing the burned key with a changed body → ЮKassa 400 ``invalid_request``,
``parameter=Idempotence-Key`` → mapped to ``permanent_error`` → 502. Because a
ЮKassa-rejected attempt INSERTs no local row, the existing-row retry-key
fallback never fires and the burned key locks the client out for ~24h.

These tests lock the diagnosis-(b) fix: on a ЮKassa Idempotence-Key collision,
retry ``create_payment`` ONCE with a fresh key even when no local row exists,
gated narrowly on ``error_parameter == "Idempotence-Key"`` and bounded to one
attempt. The replay short-circuit (service.py replay branch) runs FIRST so
genuine same-body double-taps still replay the existing row.
"""

from __future__ import annotations

from collections.abc import Generator

import httpx
import pytest
import respx
from sqlalchemy import select

from app.core.exceptions import BadGatewayAppError
from app.modules.online_payments import service
from app.modules.online_payments.models import OnlinePayment
from tests.integrations.yookassa.conftest import _YOOKASSA_BASE_URL

pytestmark = pytest.mark.asyncio


_COLLISION_BODY = {
    "type": "error",
    "code": "invalid_request",
    "parameter": "Idempotence-Key",
    "description": (
        "You've already used this idempotence key for another request "
        "within the past 24 hours."
    ),
}

_OK_BODY = {
    "id": "29ab1a59-000f-5000-8000-1399cb40ba0e",
    "status": "pending",
    "amount": {"value": "2500.00", "currency": "RUB"},
    "confirmation": {
        "type": "redirect",
        "confirmation_url": "https://yoomoney.ru/checkout/payments/v2/contract?orderId=x",
    },
}


@pytest.fixture
def yookassa_collision_then_ok() -> Generator[respx.MockRouter, None, None]:
    """POST /payments → 400 Idempotence-Key collision, then 200 on the retry."""
    with respx.mock(base_url=_YOOKASSA_BASE_URL, assert_all_called=False) as router:
        router.post("payments").mock(
            side_effect=[
                httpx.Response(400, json=_COLLISION_BODY),
                httpx.Response(200, json=_OK_BODY),
            ]
        )
        yield router


@pytest.fixture
def yookassa_collision_twice() -> Generator[respx.MockRouter, None, None]:
    """POST /payments → 400 Idempotence-Key collision on BOTH calls (retry bound)."""
    with respx.mock(base_url=_YOOKASSA_BASE_URL, assert_all_called=False) as router:
        router.post("payments").mock(
            side_effect=[
                httpx.Response(400, json=_COLLISION_BODY),
                httpx.Response(400, json=_COLLISION_BODY),
            ]
        )
        yield router


@pytest.fixture
def yookassa_other_400() -> Generator[respx.MockRouter, None, None]:
    """POST /payments → 400 invalid_request on a DIFFERENT parameter (not retried)."""
    with respx.mock(base_url=_YOOKASSA_BASE_URL, assert_all_called=False) as router:
        router.post("payments").mock(
            return_value=httpx.Response(
                400,
                json={
                    "type": "error",
                    "code": "invalid_request",
                    "parameter": "amount",
                    "description": "bad amount",
                },
            )
        )
        yield router


async def test_collision_retries_once_with_fresh_key_and_succeeds(
    app,
    db_session,
    make_client_with_email,
    make_membership_plan,
    make_actor,
    yookassa_collision_then_ok,
    yookassa_settings,
):
    """UAT-10 — burned day-key + changed body retries ONCE with a fresh key → confirmation_url.

    No existing online_payments row is present (the ЮKassa-rejected attempt
    inserted nothing), so the retry must NOT be gated on ``existing is not None``.
    The persisted row records the retry key actually accepted by ЮKassa.
    """
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

    assert resp.confirmation_url is not None, "retry must produce a confirmation_url, not a 502"
    # Exactly two POSTs were made: the burned-key attempt + the fresh-key retry.
    assert yookassa_collision_then_ok.routes[0].call_count == 2
    # Scope to THIS client_id — the host test DB may carry leftover rows from
    # prior manual UAT sessions (committed outside the per-test SAVEPOINT).
    rows = (
        await db_session.execute(
            select(OnlinePayment).where(OnlinePayment.client_id == client.id)
        )
    ).scalars().all()
    assert len(rows) == 1
    # The persisted key is the retry-shaped key (fresh uuid4 hex appended).
    assert ":retry-" in rows[0].idempotency_key


async def test_collision_retry_fires_without_existing_row(
    app,
    db_session,
    make_client_with_email,
    make_membership_plan,
    make_actor,
    yookassa_collision_then_ok,
    yookassa_settings,
):
    """The retry path is reached with NO prior online_payments row in the DB."""
    client = await make_client_with_email()
    plan = await make_membership_plan()
    actor = await make_actor()

    # Pre-condition: no rows exist for THIS freshly-created client before the call.
    pre = (
        await db_session.execute(
            select(OnlinePayment).where(OnlinePayment.client_id == client.id)
        )
    ).scalars().all()
    assert pre == []

    resp = await service.sell_membership(
        db_session,
        plan_id=plan.id,
        client_id=client.id,
        confirmation_type="redirect",
        actor=actor,
        yookassa_settings=yookassa_settings,
    )
    assert resp.confirmation_url is not None


async def test_non_idempotence_key_400_is_not_retried(
    app,
    db_session,
    make_client_with_email,
    make_membership_plan,
    make_actor,
    yookassa_other_400,
    yookassa_settings,
):
    """A permanent_error with parameter != 'Idempotence-Key' still raises BadGateway (no retry)."""
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
    # Only ONE POST — the non-Idempotence-Key 400 is not retried.
    assert yookassa_other_400.routes[0].call_count == 1
    rows = (
        await db_session.execute(
            select(OnlinePayment).where(OnlinePayment.client_id == client.id)
        )
    ).scalars().all()
    assert rows == []


async def test_second_consecutive_collision_raises_bad_gateway(
    app,
    db_session,
    make_client_with_email,
    make_membership_plan,
    make_actor,
    yookassa_collision_twice,
    yookassa_settings,
):
    """Retry is bounded to ONE attempt — a second collision raises BadGateway (no loop)."""
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
    # Exactly two POSTs: original + one bounded retry. No third attempt.
    assert yookassa_collision_twice.routes[0].call_count == 2
    rows = (
        await db_session.execute(
            select(OnlinePayment).where(OnlinePayment.client_id == client.id)
        )
    ).scalars().all()
    assert rows == []


async def test_genuine_double_tap_still_replays_without_create_payment(
    app,
    db_session,
    make_client_with_email,
    make_membership_plan,
    make_actor,
    yookassa_create_payment_success,
    yookassa_settings,
):
    """Replay safety preserved — same-body second call replays the existing row, no second POST."""
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
    # Only ONE POST — second call hit the replay short-circuit, no new ЮKassa call.
    assert yookassa_create_payment_success.routes[0].call_count == 1
    rows = (
        await db_session.execute(
            select(OnlinePayment).where(OnlinePayment.client_id == client.id)
        )
    ).scalars().all()
    assert len(rows) == 1
