"""Phase 84 APAY-03 — autopay idempotency tests.

Verifies the two-layer idempotency strategy:
  Layer 1 (DB): ON CONFLICT (membership_id, period_end) DO NOTHING in autopay_charges.
  Layer 2 (provider): deterministic sha256(membership_id:period_end) idempotency_key.

Tests:
  1. Duplicate cron tick: two invocations of `_charge_expiring_autopay_memberships` over the
     same eligible membership produce exactly ONE autopay_charges row and ONE create_payment
     call (the second tick's INSERT conflicts → skip).
  2. Crash-between-claim-and-provider: a pre-existing autopay_charges row with status='pending'
     (simulating crash after claim but before provider) → second run does NOT issue a second
     charge (DB conflict). The deterministic idempotency_key is stable across both runs for the
     same (membership_id, period_end).
  3. Failure-no-retry: a declined charge (status='failed') → next tick does NOT re-charge
     the same period (DB conflict on the existing failed claim row).
  4. Decline enqueue: cron invocation with a declined charge → exactly one
     dispatch_autopay_failure_notification enqueued AFTER commit with autopay_charge_id = the
     failed claim's id (NOT online_payment_id, which does not exist for declines).
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any
from uuid import UUID, uuid4

import pytest
import respx
from httpx import Response
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.autopay_charges.service import (
    _charge_expiring_autopay_memberships,
    _idempotency_key,
)
from app.workers.scheduled.charge_expiring_autopay import charge_expiring_autopay

# ---------------------------------------------------------------------------
# Seed helper (reused from test_charge_expiring_autopay pattern)
# ---------------------------------------------------------------------------


async def _seed_autopay_membership(
    session: AsyncSession,
    *,
    end_date: date | None = None,
    price_kopecks: int = 199_000,
) -> dict[str, Any]:
    """Seed a fully eligible autopay membership (with consent + alive card)."""
    nonce = uuid4().hex[:8]
    user_id = uuid4()
    client_id = uuid4()
    plan_id = uuid4()
    membership_id = uuid4()
    cpm_id = uuid4()
    method_id = "saved-card-" + nonce

    if end_date is None:
        end_date = date.today() + timedelta(days=2)  # noqa: DTZ011

    await session.execute(
        text(
            "INSERT INTO users (id, email, password_hash, role, full_name, created_at, updated_at)"
            " VALUES (:u_id, :u_email, 'x', 'owner', 'Idem Test', now(), now())"
        ),
        {"u_id": user_id, "u_email": f"id-{nonce}@example.com"},
    )
    await session.execute(
        text(
            "INSERT INTO clients"
            " (id, last_name, first_name, phone, created_by_user_id, created_at, updated_at)"
            " VALUES (:c_id, 'Idem', 'Client', :c_phone, :c_uid, now(), now())"
        ),
        {"c_id": client_id, "c_phone": f"+7902{nonce}", "c_uid": user_id},
    )
    await session.execute(
        text(
            "INSERT INTO membership_plans"
            " (id, name, duration_days, price_kopecks, freeze_days_limit, created_at, updated_at)"
            " VALUES (:p_id, :p_name, 30, :p_price, 30, now(), now())"
        ),
        {"p_id": plan_id, "p_name": f"IdemPlan-{nonce}", "p_price": price_kopecks},
    )
    await session.execute(
        text(
            "INSERT INTO memberships"
            " (id, client_id, plan_id, plan_name_snapshot, duration_days_snapshot,"
            "  price_kopecks_snapshot, freeze_days_limit_snapshot,"
            "  start_date, end_date, status, created_at, updated_at)"
            " VALUES (:m_id, :m_cid, :m_pid, 'IdemPlan', 30, :m_price, 30,"
            "         :m_start, :m_end, 'active', now(), now())"
        ),
        {
            "m_id": membership_id,
            "m_cid": client_id,
            "m_pid": plan_id,
            "m_price": price_kopecks,
            "m_start": end_date - timedelta(days=30),
            "m_end": end_date,
        },
    )
    await session.execute(
        text(
            "INSERT INTO client_payment_methods"
            " (id, client_id, yookassa_method_id, last4, brand,"
            "  autopay_enabled, created_at, updated_at)"
            " VALUES (:pm_id, :pm_cid, :pm_mid, '4477', 'Visa', true, now(), now())"
        ),
        {"pm_id": cpm_id, "pm_cid": client_id, "pm_mid": method_id},
    )
    await session.execute(
        text("UPDATE client_payment_methods SET consent_recorded_at = now() WHERE id = :pm_id"),
        {"pm_id": cpm_id},
    )
    await session.flush()
    return {
        "membership_id": membership_id,
        "client_id": client_id,
        "plan_id": plan_id,
        "end_date": end_date,
        "method_id": method_id,
    }


def _ok_response(payment_id: str) -> dict[str, Any]:
    return {
        "id": payment_id,
        "status": "pending",
        "amount": {"value": "1990.00", "currency": "RUB"},
        "description": "Автопродление",
        "paid": False,
        "refundable": False,
        "metadata": {},
    }


def _decline_response() -> dict[str, Any]:
    return {
        "type": "error",
        "id": "err-1",
        "code": "card_declined",
        "description": "Declined",
    }


# ---------------------------------------------------------------------------
# Test 1: Duplicate cron tick → exactly ONE autopay_charges + ONE create_payment
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_duplicate_tick_no_double_charge(db_session: AsyncSession) -> None:
    """Two cron invocations over the same eligible membership produce ONE charge.

    The ON CONFLICT (membership_id, period_end) DO NOTHING claim INSERT is the
    DB-level double-charge guard (T-84-01 / T-84-05).
    """
    today = date.today()  # noqa: DTZ011
    seed = await _seed_autopay_membership(db_session, end_date=today + timedelta(days=2))
    membership_id: UUID = seed["membership_id"]

    create_payment_calls: list[str] = []

    def _ok_side_effect(*args: Any, **kwargs: Any) -> Response:
        call_idx = len(create_payment_calls)
        payment_id = f"pay-dup-{call_idx:04d}"
        create_payment_calls.append(payment_id)
        return Response(200, json=_ok_response(payment_id))

    with respx.mock(base_url="https://api.yookassa.ru/v3/", assert_all_called=False) as router:
        router.post("payments").mock(side_effect=_ok_side_effect)

        # First tick
        count1, declined1 = await _charge_expiring_autopay_memberships(
            db_session, today=today, window_days=3
        )
        await db_session.flush()  # flush audit row from first tick

        # Second tick (same session, same data — ON CONFLICT should block)
        count2, declined2 = await _charge_expiring_autopay_memberships(
            db_session, today=today, window_days=3
        )

    # Exactly ONE charge attempt (first tick wins; second tick conflicts and skips)
    assert count1 == 1
    assert count2 == 0
    assert declined1 == []
    assert declined2 == []

    # Exactly ONE create_payment call (not two)
    assert len(create_payment_calls) == 1, (
        f"Expected 1 YooKassa call, got {len(create_payment_calls)}"
    )

    # Exactly ONE autopay_charges row
    ac_count = (
        await db_session.execute(
            text("SELECT COUNT(*) FROM autopay_charges WHERE membership_id = :m_id"),
            {"m_id": str(membership_id)},
        )
    ).scalar_one()
    assert ac_count == 1, f"Expected 1 autopay_charges row, got {ac_count}"


# ---------------------------------------------------------------------------
# Test 2: Crash-between-claim-and-provider — stable idempotency_key
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_crash_between_claim_and_provider_no_double_charge(db_session: AsyncSession) -> None:
    """Pre-existing pending claim row → second run skips (DB conflict).

    Simulates a crash after the autopay_charges INSERT but before the YooKassa call.
    The deterministic idempotency_key is stable across runs for the same (membership_id, period_end).
    """  # noqa: E501
    today = date.today()  # noqa: DTZ011
    seed = await _seed_autopay_membership(db_session, end_date=today + timedelta(days=1))
    membership_id: UUID = seed["membership_id"]
    period_end = seed["end_date"]

    # Pre-insert a 'pending' claim row (simulates crash after INSERT, before provider call).
    await db_session.execute(
        text(
            "INSERT INTO autopay_charges"
            " (id, membership_id, period_end, status, amount_kopecks, created_at, updated_at)"
            " VALUES (gen_random_uuid(), :m_id, :p_end, 'pending', 199000, now(), now())"
        ),
        {"m_id": str(membership_id), "p_end": period_end},
    )
    await db_session.flush()

    yk_calls: list[int] = []
    with respx.mock(base_url="https://api.yookassa.ru/v3/", assert_all_called=False) as router:
        router.post("payments").mock(
            side_effect=lambda *a, **k: (
                yk_calls.append(1),
                Response(200, json=_ok_response("pay-crash-0001")),
            )[1]
        )

        count, declined_ids = await _charge_expiring_autopay_memberships(
            db_session, today=today, window_days=3
        )

    # The pre-existing pending claim blocks the second charge (ON CONFLICT DO NOTHING)
    assert count == 0
    assert declined_ids == []
    assert len(yk_calls) == 0, "YooKassa must NOT be called when claim row already exists"

    # Still exactly ONE autopay_charges row (the pre-inserted one)
    ac_count = (
        await db_session.execute(
            text("SELECT COUNT(*) FROM autopay_charges WHERE membership_id = :m_id"),
            {"m_id": str(membership_id)},
        )
    ).scalar_one()
    assert ac_count == 1

    # Verify the deterministic idempotency_key is stable for the same (membership_id, period_end).
    key1 = _idempotency_key(membership_id, period_end)
    key2 = _idempotency_key(membership_id, period_end)
    assert key1 == key2, "idempotency_key must be deterministic across calls"
    assert len(key1) == 64, "sha256 hex digest must be 64 chars"


# ---------------------------------------------------------------------------
# Test 3: Failure-no-retry — failed claim blocks next tick
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_failed_claim_no_retry_on_next_tick(db_session: AsyncSession) -> None:
    """A failed autopay_charges row blocks the next cron tick from re-charging the period."""
    today = date.today()  # noqa: DTZ011
    seed = await _seed_autopay_membership(db_session, end_date=today + timedelta(days=2))
    membership_id: UUID = seed["membership_id"]
    period_end = seed["end_date"]

    # Pre-insert a 'failed' claim (simulates a previous declined charge).
    await db_session.execute(
        text(
            "INSERT INTO autopay_charges"
            " (id, membership_id, period_end, status, amount_kopecks, failure_reason,"
            "  created_at, updated_at)"
            " VALUES (gen_random_uuid(), :m_id, :p_end, 'failed', 199000, 'permanent_error:card_declined',"  # noqa: E501
            "  now(), now())"
        ),
        {"m_id": str(membership_id), "p_end": period_end},
    )
    await db_session.flush()

    yk_calls: list[int] = []
    with respx.mock(base_url="https://api.yookassa.ru/v3/", assert_all_called=False) as router:
        router.post("payments").mock(
            side_effect=lambda *a, **k: (
                yk_calls.append(1),
                Response(200, json=_ok_response("pay-retry-0001")),
            )[1]
        )

        count, declined_ids = await _charge_expiring_autopay_memberships(
            db_session, today=today, window_days=3
        )

    # The existing failed claim blocks re-charge (ON CONFLICT DO NOTHING)
    assert count == 0
    assert declined_ids == []
    assert len(yk_calls) == 0, "YooKassa must NOT be called when failed claim exists for the period"

    # Still exactly ONE autopay_charges row (status='failed', unchanged)
    charge_row = (
        (
            await db_session.execute(
                text("SELECT status FROM autopay_charges WHERE membership_id = :m_id"),
                {"m_id": str(membership_id)},
            )
        )
        .mappings()
        .one()
    )
    assert charge_row["status"] == "failed"


# ---------------------------------------------------------------------------
# Test 4: Decline enqueue — cron enqueues dispatch_autopay_failure_notification
# post-commit with autopay_charge_id (NOT online_payment_id)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_decline_enqueues_failure_notification(db_session: AsyncSession) -> None:
    """Cron with a declined charge enqueues the failure notification keyed on autopay_charge_id.

    T-84-12b: failure enqueue uses autopay_charges.id (always present), NOT online_payment_id
    (which doesn't exist for declines — yookassa_payment_id is NOT NULL invariant).

    Tests the full cron fn (charge_expiring_autopay) with a fake ARQ ctx.
    """
    today = date.today()  # noqa: DTZ011
    seed = await _seed_autopay_membership(db_session, end_date=today + timedelta(days=1))
    membership_id: UUID = seed["membership_id"]

    # --- Fake ARQ ctx with a sessionmaker that reuses db_session (SAVEPOINT mode) ---

    class _SessionCtx:
        def __init__(self, s: AsyncSession) -> None:
            self._s = s

        async def __aenter__(self) -> AsyncSession:
            return self._s

        async def __aexit__(self, *args: Any) -> None:
            # Commit SAVEPOINT — mirrors what the real cron does (session.commit()).
            # With join_transaction_mode='create_savepoint', commit() releases the SAVEPOINT
            # but keeps the outer transaction open, so the test can inspect the result.
            await self._s.commit()
            return None

    class _FakeSessionmaker:
        def __call__(self) -> _SessionCtx:
            return _SessionCtx(db_session)

    # Capture enqueue calls on a fake arq pool.
    enqueued_jobs: list[dict[str, Any]] = []

    class _FakeArqPool:
        async def enqueue_job(
            self, fn_name: str, *, _kwargs: dict[str, Any] | None = None, **kwargs: Any
        ) -> None:
            enqueued_jobs.append({"fn_name": fn_name, "kwargs": _kwargs or kwargs})

    ctx: dict[str, Any] = {
        "sessionmaker": _FakeSessionmaker(),
        "redis": _FakeArqPool(),
        "job_id": "test-decline-enqueue-job",
        "function_name": "charge_expiring_autopay",
    }

    with respx.mock(base_url="https://api.yookassa.ru/v3/", assert_all_called=False) as router:
        router.post("payments").mock(return_value=Response(402, json=_decline_response()))

        returned_count = await charge_expiring_autopay(ctx)

    # Cron returns count of charge attempts (1 — the declined attempt)
    assert returned_count == 1

    # Exactly one dispatch_autopay_failure_notification enqueued AFTER commit
    failure_notifs = [
        j for j in enqueued_jobs if j["fn_name"] == "dispatch_autopay_failure_notification"
    ]
    assert len(failure_notifs) == 1, (
        f"Expected 1 failure notification enqueue, got {len(failure_notifs)}: {enqueued_jobs}"
    )

    enqueued_kwargs = failure_notifs[0]["kwargs"]
    assert "autopay_charge_id" in enqueued_kwargs, (
        f"Enqueue must pass autopay_charge_id, got: {enqueued_kwargs}"
    )

    # The autopay_charge_id must be the failed claim's id
    autopay_charge_id_str = enqueued_kwargs["autopay_charge_id"]
    assert isinstance(autopay_charge_id_str, str)

    # Verify it matches the actual autopay_charges row for the membership
    charge_row = (
        (
            await db_session.execute(
                text(
                    "SELECT id, status, online_payment_id FROM autopay_charges"
                    " WHERE membership_id = :m_id"
                ),
                {"m_id": str(membership_id)},
            )
        )
        .mappings()
        .one()
    )
    assert charge_row["status"] == "failed"
    assert charge_row["online_payment_id"] is None, (
        "Decline MUST NOT create an online_payments row — no online_payment_id on claim"
    )
    assert str(charge_row["id"]) == autopay_charge_id_str, (
        "Enqueued autopay_charge_id must match the failed claim row's id"
    )
