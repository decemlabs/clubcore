"""Phase 84 APAY-03 — autopay skip-matrix integration tests.

Verifies that the `_charge_expiring_autopay_memberships` service helper does NOT charge
memberships in any skip condition. For each skip scenario: no autopay_charges rows are
inserted, no online_payments rows are created, and YooKassa is NOT called.

Skip conditions tested:
  (a) consent_recorded_at IS NULL [ФЗ-376 — explicit assert]
  (b) autopay_enabled = false
  (c) no alive card (unlinked_at is set / no card at all)
  (d) already-renewed (a membership covering the next period exists)
  (e) end_date outside the window (too far in the future)

These tests run the service helper directly (not the full cron fn) to keep them
independent of the ARQ ctx fixture. The helper is the logic owner.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any
from uuid import uuid4

import pytest
import respx
from httpx import Response
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.autopay_charges.service import _charge_expiring_autopay_memberships

# ---------------------------------------------------------------------------
# Seed helpers (no-card, no-consent, not-in-window variants)
# ---------------------------------------------------------------------------


async def _seed_client_plan(session: AsyncSession) -> dict[str, Any]:
    """Seed user + client + membership_plan. Returns IDs."""
    nonce = uuid4().hex[:8]
    user_id = uuid4()
    client_id = uuid4()
    plan_id = uuid4()

    await session.execute(
        text(
            "INSERT INTO users (id, email, password_hash, role, full_name, created_at, updated_at)"
            " VALUES (:u_id, :u_email, 'x', 'owner', 'Skip Test', now(), now())"
        ),
        {"u_id": user_id, "u_email": f"skip-{nonce}@example.com"},
    )
    await session.execute(
        text(
            "INSERT INTO clients"
            " (id, last_name, first_name, phone, created_by_user_id, created_at, updated_at)"
            " VALUES (:c_id, 'Skip', 'Client', :c_phone, :c_uid, now(), now())"
        ),
        {"c_id": client_id, "c_phone": f"+7901{nonce}", "c_uid": user_id},
    )
    await session.execute(
        text(
            "INSERT INTO membership_plans"
            " (id, name, duration_days, price_kopecks, freeze_days_limit, created_at, updated_at)"
            " VALUES (:p_id, :p_name, 30, 199000, 30, now(), now())"
        ),
        {"p_id": plan_id, "p_name": f"SkipPlan-{nonce}"},
    )
    return {"user_id": user_id, "client_id": client_id, "plan_id": plan_id}


async def _seed_active_membership(
    session: AsyncSession,
    *,
    client_id: Any,
    plan_id: Any,
    end_date: date,
) -> Any:
    membership_id = uuid4()
    await session.execute(
        text(
            "INSERT INTO memberships"
            " (id, client_id, plan_id, plan_name_snapshot, duration_days_snapshot,"
            "  price_kopecks_snapshot, freeze_days_limit_snapshot,"
            "  start_date, end_date, status, created_at, updated_at)"
            " VALUES (:m_id, :m_cid, :m_pid, 'SkipPlan', 30, 199000, 30,"
            "         :m_start, :m_end, 'active', now(), now())"
        ),
        {
            "m_id": membership_id,
            "m_cid": client_id,
            "m_pid": plan_id,
            "m_start": end_date - timedelta(days=30),
            "m_end": end_date,
        },
    )
    return membership_id


async def _seed_payment_method(
    session: AsyncSession,
    *,
    client_id: Any,
    autopay_enabled: bool = True,
    consent: bool = True,
    alive: bool = True,
) -> None:
    nonce = uuid4().hex[:8]
    cpm_id = uuid4()
    await session.execute(
        text(
            "INSERT INTO client_payment_methods"
            " (id, client_id, yookassa_method_id, last4, brand,"
            "  autopay_enabled, created_at, updated_at)"
            " VALUES (:pm_id, :pm_cid, :pm_mid, '4477', 'Visa',"
            "  :pm_ae, now(), now())"
        ),
        {
            "pm_id": cpm_id,
            "pm_cid": client_id,
            "pm_mid": "saved-card-" + nonce,
            "pm_ae": autopay_enabled,
        },
    )
    if consent:
        await session.execute(
            text("UPDATE client_payment_methods SET consent_recorded_at = now() WHERE id = :pm_id"),
            {"pm_id": cpm_id},
        )
    if not alive:
        await session.execute(
            text("UPDATE client_payment_methods SET unlinked_at = now() WHERE id = :pm_id"),
            {"pm_id": cpm_id},
        )
    await session.flush()


async def _assert_zero_charges(session: AsyncSession, membership_id: Any) -> None:
    """Assert no autopay_charges, no online_payments for the given membership."""
    ac_count = (
        await session.execute(
            text("SELECT COUNT(*) FROM autopay_charges WHERE membership_id = :m_id"),
            {"m_id": str(membership_id)},
        )
    ).scalar_one()
    assert ac_count == 0, (
        f"Expected 0 autopay_charges rows for membership {membership_id}, got {ac_count}"
    )


def _no_charge_mock(call_count_holder: list[int]) -> Any:
    """Return a respx side_effect that increments call_count_holder and returns 200."""
    from httpx import Response

    def _side_effect(*args: Any, **kwargs: Any) -> Response:
        call_count_holder.append(1)
        return Response(200, json={"id": "should-not-happen"})

    return _side_effect


# ---------------------------------------------------------------------------
# (a) ФЗ-376: consent_recorded_at IS NULL → ZERO charges
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_skip_no_consent(db_session: AsyncSession) -> None:
    """ФЗ-376: membership with consent_recorded_at IS NULL MUST NOT be charged."""
    today = date.today()  # noqa: DTZ011
    ids = await _seed_client_plan(db_session)
    membership_id = await _seed_active_membership(
        db_session,
        client_id=ids["client_id"],
        plan_id=ids["plan_id"],
        end_date=today + timedelta(days=2),
    )
    await _seed_payment_method(
        db_session,
        client_id=ids["client_id"],
        autopay_enabled=True,
        consent=False,  # ← ФЗ-376: consent_recorded_at IS NULL
        alive=True,
    )

    yk_calls: list[int] = []
    with respx.mock(base_url="https://api.yookassa.ru/v3/", assert_all_called=False) as router:
        router.post("payments").mock(side_effect=_no_charge_mock(yk_calls))

        count, declined_ids = await _charge_expiring_autopay_memberships(
            db_session, today=today, window_days=3
        )

    # ФЗ-376: zero charges, zero YooKassa calls
    assert count == 0
    assert declined_ids == []
    assert len(yk_calls) == 0, "YooKassa must NOT be called when consent_recorded_at IS NULL"
    await _assert_zero_charges(db_session, membership_id)


# ---------------------------------------------------------------------------
# (b) autopay_enabled = false → ZERO charges
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_skip_autopay_disabled(db_session: AsyncSession) -> None:
    """Membership with autopay_enabled=false MUST NOT be charged."""
    today = date.today()  # noqa: DTZ011
    ids = await _seed_client_plan(db_session)
    membership_id = await _seed_active_membership(
        db_session,
        client_id=ids["client_id"],
        plan_id=ids["plan_id"],
        end_date=today + timedelta(days=1),
    )
    await _seed_payment_method(
        db_session,
        client_id=ids["client_id"],
        autopay_enabled=False,  # ← autopay off
        consent=True,
        alive=True,
    )

    yk_calls: list[int] = []
    with respx.mock(base_url="https://api.yookassa.ru/v3/", assert_all_called=False) as router:
        router.post("payments").mock(side_effect=_no_charge_mock(yk_calls))

        count, declined_ids = await _charge_expiring_autopay_memberships(
            db_session, today=today, window_days=3
        )

    assert count == 0
    assert declined_ids == []
    assert len(yk_calls) == 0
    await _assert_zero_charges(db_session, membership_id)


# ---------------------------------------------------------------------------
# (c) no alive card (unlinked_at set) → ZERO charges
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_skip_dead_card(db_session: AsyncSession) -> None:
    """Membership whose card is unlinked (unlinked_at IS NOT NULL) MUST NOT be charged."""
    today = date.today()  # noqa: DTZ011
    ids = await _seed_client_plan(db_session)
    membership_id = await _seed_active_membership(
        db_session,
        client_id=ids["client_id"],
        plan_id=ids["plan_id"],
        end_date=today + timedelta(days=1),
    )
    await _seed_payment_method(
        db_session,
        client_id=ids["client_id"],
        autopay_enabled=True,
        consent=True,
        alive=False,  # ← unlinked_at IS NOT NULL
    )

    yk_calls: list[int] = []
    with respx.mock(base_url="https://api.yookassa.ru/v3/", assert_all_called=False) as router:
        router.post("payments").mock(side_effect=_no_charge_mock(yk_calls))

        count, declined_ids = await _charge_expiring_autopay_memberships(
            db_session, today=today, window_days=3
        )

    assert count == 0
    assert declined_ids == []
    assert len(yk_calls) == 0
    await _assert_zero_charges(db_session, membership_id)


# ---------------------------------------------------------------------------
# (c-alt) No card at all → ZERO charges
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_skip_no_card_at_all(db_session: AsyncSession) -> None:
    """Membership with no client_payment_methods row at all MUST NOT be charged."""
    today = date.today()  # noqa: DTZ011
    ids = await _seed_client_plan(db_session)
    membership_id = await _seed_active_membership(
        db_session,
        client_id=ids["client_id"],
        plan_id=ids["plan_id"],
        end_date=today + timedelta(days=1),
    )
    # No client_payment_methods row seeded.

    yk_calls: list[int] = []
    with respx.mock(base_url="https://api.yookassa.ru/v3/", assert_all_called=False) as router:
        router.post("payments").mock(side_effect=_no_charge_mock(yk_calls))

        count, declined_ids = await _charge_expiring_autopay_memberships(
            db_session, today=today, window_days=3
        )

    assert count == 0
    assert declined_ids == []
    assert len(yk_calls) == 0
    await _assert_zero_charges(db_session, membership_id)


# ---------------------------------------------------------------------------
# (d) already-renewed → ZERO charges
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_skip_already_renewed(db_session: AsyncSession) -> None:
    """Membership already renewed (a covering membership exists) MUST NOT be charged again."""
    today = date.today()  # noqa: DTZ011
    ids = await _seed_client_plan(db_session)
    end_date = today + timedelta(days=2)
    membership_id = await _seed_active_membership(
        db_session,
        client_id=ids["client_id"],
        plan_id=ids["plan_id"],
        end_date=end_date,
    )
    # Seed the renewal membership (start_date > original end_date → covers next period).
    renewal_id = uuid4()
    await db_session.execute(
        text(
            "INSERT INTO memberships"
            " (id, client_id, plan_id, plan_name_snapshot, duration_days_snapshot,"
            "  price_kopecks_snapshot, freeze_days_limit_snapshot,"
            "  start_date, end_date, status, created_at, updated_at)"
            " VALUES (:m_id, :m_cid, :m_pid, 'SkipPlan', 30, 199000, 30,"
            "         :m_start, :m_end, 'active', now(), now())"
        ),
        {
            "m_id": renewal_id,
            "m_cid": ids["client_id"],
            "m_pid": ids["plan_id"],
            "m_start": end_date + timedelta(days=1),  # start_date > end_date → already renewed
            "m_end": end_date + timedelta(days=31),
        },
    )
    await _seed_payment_method(
        db_session,
        client_id=ids["client_id"],
        autopay_enabled=True,
        consent=True,
        alive=True,
    )

    yk_calls: list[int] = []
    with respx.mock(base_url="https://api.yookassa.ru/v3/", assert_all_called=False) as router:
        router.post("payments").mock(side_effect=_no_charge_mock(yk_calls))

        count, declined_ids = await _charge_expiring_autopay_memberships(
            db_session, today=today, window_days=3
        )

    assert count == 0
    assert declined_ids == []
    assert len(yk_calls) == 0
    await _assert_zero_charges(db_session, membership_id)


# ---------------------------------------------------------------------------
# (e) end_date outside window → ZERO charges
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_skip_out_of_window(db_session: AsyncSession) -> None:
    """Membership whose end_date is outside [today, today+window_days] MUST NOT be charged."""
    today = date.today()  # noqa: DTZ011
    ids = await _seed_client_plan(db_session)
    # end_date = today + 10 days, window_days = 3 → outside window
    membership_id = await _seed_active_membership(
        db_session,
        client_id=ids["client_id"],
        plan_id=ids["plan_id"],
        end_date=today + timedelta(days=10),  # 10 > window_days=3
    )
    await _seed_payment_method(
        db_session,
        client_id=ids["client_id"],
        autopay_enabled=True,
        consent=True,
        alive=True,
    )

    yk_calls: list[int] = []
    with respx.mock(base_url="https://api.yookassa.ru/v3/", assert_all_called=False) as router:
        router.post("payments").mock(side_effect=_no_charge_mock(yk_calls))

        count, declined_ids = await _charge_expiring_autopay_memberships(
            db_session, today=today, window_days=3
        )

    assert count == 0
    assert declined_ids == []
    assert len(yk_calls) == 0
    await _assert_zero_charges(db_session, membership_id)
