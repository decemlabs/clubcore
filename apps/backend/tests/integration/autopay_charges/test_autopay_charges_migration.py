"""Phase 84 APAY-03/APAY-04 — Alembic 0056 migration shape test.

Verifies that migration 0056 created the autopay_charges and
autopay_charge_notifications tables with the correct constraints:

1. autopay_charges:
   - Table exists with all required columns (incl. online_payment_id).
   - UNIQUE(membership_id, period_end) double-charge guard (T-84-01):
     a second INSERT with the same pair raises IntegrityError.
   - CHECK status IN ('pending','succeeded','failed') is enforced.

2. autopay_charge_notifications:
   - Table exists with all required columns.
   - UNIQUE(autopay_charge_id, kind, channel) dedup guard (T-84-04b):
     a second INSERT with the same triple raises IntegrityError.
   - CHECK channel IN ('telegram','email') is enforced.

Seeding: membership rows require a client and a membership_plan.
All inserts use raw SQL inside a SAVEPOINT so the outer db_session
fixture rolls everything back automatically.
"""

from __future__ import annotations

from typing import Any
from uuid import uuid4

import pytest
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

# ---------------------------------------------------------------------------
# Seed helpers
# ---------------------------------------------------------------------------


async def _seed_membership(session: AsyncSession) -> Any:
    """Seed the minimum chain required for autopay_charges FK.

    Returns membership_id.  No commit — caller owns the transaction.
    """
    nonce = uuid4().hex[:8]
    user_id = uuid4()
    client_id = uuid4()
    plan_id = uuid4()
    membership_id = uuid4()

    await session.execute(
        text(
            "INSERT INTO users (id, email, password_hash, role, full_name, created_at, updated_at)"
            " VALUES (:id, :email, 'x', 'owner', 'Test Owner 0056', now(), now())"
        ).bindparams(id=user_id, email=f"test-0056-{nonce}@example.com")
    )
    await session.execute(
        text(
            "INSERT INTO clients"
            " (id, last_name, first_name, phone, created_by_user_id, created_at, updated_at)"
            " VALUES (:id, 'Test', 'Client', :phone, :uid, now(), now())"
        ).bindparams(id=client_id, phone=f"+7999{nonce}", uid=user_id)
    )
    await session.execute(
        text(
            "INSERT INTO membership_plans"
            " (id, name, duration_days, price_kopecks, freeze_days_limit,"
            "  created_at, updated_at)"
            " VALUES (:id, :name, 30, 100000, 30, now(), now())"
        ).bindparams(id=plan_id, name=f"Plan-0056-{nonce}")
    )
    await session.execute(
        text(
            "INSERT INTO memberships"
            " (id, client_id, plan_id, plan_name_snapshot, duration_days_snapshot,"
            "  price_kopecks_snapshot, freeze_days_limit_snapshot,"
            "  start_date, end_date, status,"
            "  created_at, updated_at)"
            " VALUES (:id, :client_id, :plan_id, 'Plan-0056', 30, 100000, 30,"
            "         CURRENT_DATE, CURRENT_DATE + 30, 'active', now(), now())"
        ).bindparams(id=membership_id, client_id=client_id, plan_id=plan_id)
    )
    await session.flush()
    return membership_id


# ---------------------------------------------------------------------------
# 1. autopay_charges schema shape
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_0056_autopay_charges_table_exists_with_expected_columns(
    db_session: AsyncSession,
) -> None:
    """autopay_charges must have all declared columns including online_payment_id."""

    def _columns(sync_conn: Any) -> set[str]:
        inspector = inspect(sync_conn)
        return {c["name"] for c in inspector.get_columns("autopay_charges")}

    conn = await db_session.connection()
    cols = await conn.run_sync(_columns)

    required = {
        "id",
        "membership_id",
        "period_end",
        "status",
        "amount_kopecks",
        "yookassa_payment_id",
        "online_payment_id",  # required for Plan 02 UPDATE — PATTERNS.md omits it
        "failure_reason",
        "charged_at",
        "created_at",
        "updated_at",
    }
    missing = required - cols
    assert not missing, f"autopay_charges missing columns: {missing}"


@pytest.mark.asyncio
async def test_0056_autopay_charges_unique_membership_period_guard(
    db_session: AsyncSession,
) -> None:
    """UNIQUE(membership_id, period_end) must raise IntegrityError on duplicate (T-84-01)."""
    membership_id = await _seed_membership(db_session)

    await db_session.execute(
        text(
            "INSERT INTO autopay_charges"
            " (id, membership_id, period_end, status, amount_kopecks, created_at, updated_at)"
            " VALUES (gen_random_uuid(), :mid, '2026-07-01', 'pending', 100000, now(), now())"
        ).bindparams(mid=membership_id)
    )
    await db_session.flush()

    with pytest.raises(IntegrityError):
        async with db_session.begin_nested():
            await db_session.execute(
                text(
                    "INSERT INTO autopay_charges"
                    " (id, membership_id, period_end, status, amount_kopecks,"
                    "  created_at, updated_at)"
                    " VALUES (gen_random_uuid(), :mid, '2026-07-01', 'pending', 100000,"
                    "         now(), now())"
                ).bindparams(mid=membership_id)
            )
            await db_session.flush()


@pytest.mark.asyncio
async def test_0056_autopay_charges_status_check_rejects_invalid(
    db_session: AsyncSession,
) -> None:
    """CHECK status IN ('pending','succeeded','failed') must reject unknown values."""
    membership_id = await _seed_membership(db_session)

    with pytest.raises(IntegrityError):
        async with db_session.begin_nested():
            await db_session.execute(
                text(
                    "INSERT INTO autopay_charges"
                    " (id, membership_id, period_end, status, amount_kopecks,"
                    "  created_at, updated_at)"
                    " VALUES (gen_random_uuid(), :mid, '2026-08-01', 'bogus', 100000,"
                    "         now(), now())"
                ).bindparams(mid=membership_id)
            )
            await db_session.flush()


# ---------------------------------------------------------------------------
# 2. autopay_charge_notifications schema shape
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_0056_autopay_charge_notifications_table_exists_with_expected_columns(
    db_session: AsyncSession,
) -> None:
    """autopay_charge_notifications must have all declared columns."""

    def _columns(sync_conn: Any) -> set[str]:
        inspector = inspect(sync_conn)
        return {c["name"] for c in inspector.get_columns("autopay_charge_notifications")}

    conn = await db_session.connection()
    cols = await conn.run_sync(_columns)

    required = {
        "id",
        "autopay_charge_id",
        "kind",
        "channel",
        "sent_at",
        "created_at",
        "updated_at",
    }
    missing = required - cols
    assert not missing, f"autopay_charge_notifications missing columns: {missing}"


@pytest.mark.asyncio
async def test_0056_autopay_charge_notifications_unique_guard(
    db_session: AsyncSession,
) -> None:
    """UNIQUE(autopay_charge_id, kind, channel) must raise IntegrityError on duplicate.

    T-84-04b: dedup guard for the per-channel failure-notification claim store.
    """
    membership_id = await _seed_membership(db_session)

    # Insert the parent charge row
    charge_id = uuid4()
    await db_session.execute(
        text(
            "INSERT INTO autopay_charges"
            " (id, membership_id, period_end, status, amount_kopecks, created_at, updated_at)"
            " VALUES (:cid, :mid, '2026-09-01', 'failed', 100000, now(), now())"
        ).bindparams(cid=charge_id, mid=membership_id)
    )
    await db_session.flush()

    # First notification INSERT — must succeed
    await db_session.execute(
        text(
            "INSERT INTO autopay_charge_notifications"
            " (id, autopay_charge_id, kind, channel, sent_at, created_at, updated_at)"
            " VALUES (gen_random_uuid(), :cid, 'autopay_charge_failed', 'telegram',"
            "         now(), now(), now())"
        ).bindparams(cid=charge_id)
    )
    await db_session.flush()

    # Second INSERT with same (charge_id, kind, channel) — must raise IntegrityError
    with pytest.raises(IntegrityError):
        async with db_session.begin_nested():
            await db_session.execute(
                text(
                    "INSERT INTO autopay_charge_notifications"
                    " (id, autopay_charge_id, kind, channel, sent_at, created_at, updated_at)"
                    " VALUES (gen_random_uuid(), :cid, 'autopay_charge_failed', 'telegram',"
                    "         now(), now(), now())"
                ).bindparams(cid=charge_id)
            )
            await db_session.flush()


@pytest.mark.asyncio
async def test_0056_autopay_charge_notifications_channel_check_rejects_invalid(
    db_session: AsyncSession,
) -> None:
    """CHECK channel IN ('telegram','email') must reject unknown channels."""
    membership_id = await _seed_membership(db_session)
    charge_id = uuid4()
    await db_session.execute(
        text(
            "INSERT INTO autopay_charges"
            " (id, membership_id, period_end, status, amount_kopecks, created_at, updated_at)"
            " VALUES (:cid, :mid, '2026-10-01', 'failed', 100000, now(), now())"
        ).bindparams(cid=charge_id, mid=membership_id)
    )
    await db_session.flush()

    with pytest.raises(IntegrityError):
        async with db_session.begin_nested():
            await db_session.execute(
                text(
                    "INSERT INTO autopay_charge_notifications"
                    " (id, autopay_charge_id, kind, channel, sent_at, created_at, updated_at)"
                    " VALUES (gen_random_uuid(), :cid, 'autopay_charge_failed', 'sms',"
                    "         now(), now(), now())"
                ).bindparams(cid=charge_id)
            )
            await db_session.flush()


# ---------------------------------------------------------------------------
# 3. online_payments.confirmation_type widened to include 'autopay'
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_0056_online_payments_accepts_autopay_confirmation_type(
    db_session: AsyncSession,
) -> None:
    """confirmation_type='autopay' must no longer raise IntegrityError after 0056."""
    nonce = uuid4().hex[:8]
    user_id = uuid4()
    client_id = uuid4()
    plan_id = uuid4()

    await db_session.execute(
        text(
            "INSERT INTO users (id, email, password_hash, role, full_name, created_at, updated_at)"
            " VALUES (:id, :email, 'x', 'owner', 'Test Owner OP', now(), now())"
        ).bindparams(id=user_id, email=f"test-0056-op-{nonce}@example.com")
    )
    await db_session.execute(
        text(
            "INSERT INTO clients"
            " (id, last_name, first_name, phone, created_by_user_id, created_at, updated_at)"
            " VALUES (:id, 'Test', 'Client', :phone, :uid, now(), now())"
        ).bindparams(id=client_id, phone=f"+7998{nonce}", uid=user_id)
    )
    await db_session.execute(
        text(
            "INSERT INTO membership_plans"
            " (id, name, duration_days, price_kopecks, freeze_days_limit,"
            "  created_at, updated_at)"
            " VALUES (:id, :name, 30, 100000, 30, now(), now())"
        ).bindparams(id=plan_id, name=f"Plan-OP-{nonce}")
    )

    audit_corr_id = uuid4()
    idem_key = uuid4()
    # Insert online_payments row with confirmation_type='autopay' — must succeed after 0056.
    # Requires idempotency_key and audit_correlation_id (NOT NULL without defaults).
    await db_session.execute(
        text(
            "INSERT INTO online_payments"
            " (yookassa_payment_id, membership_plan_id, client_id,"
            "  idempotency_key, audit_correlation_id,"
            "  amount_kopecks, status, confirmation_type)"
            " VALUES (:yk_id, :plan_id, :client_id,"
            "         :idem_key, :audit_corr_id,"
            "         100000, 'pending', 'autopay')"
        ).bindparams(
            yk_id=f"yk-autopay-test-{nonce}",
            plan_id=plan_id,
            client_id=client_id,
            idem_key=idem_key,
            audit_corr_id=audit_corr_id,
        )
    )
    await db_session.flush()
