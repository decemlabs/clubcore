"""Integration tests for generate_recurring_slots cron helper (Phase 59 REC-02).

Covers REC-02 acceptance criteria:
  1. DST golden test (PITFALL 7 / T-59-15):
       _expand_template_occurrences(MONDAY, time(10,0), from=2026-03-30)
       → 2026-03-30 07:00:00+00:00  (MSK UTC+3, no DST since 2014)
  2. Idempotency (PITFALL 8 / T-59-13):
       First helper run inserts N>0 rows; second run over identical state → 0.
  3. Time-off window skip (PITFALL 9 inverse / T-59-16):
       A slot whose window falls inside an active time-off block is NOT inserted.
  4. slot_published audit emitted only on real inserts (ROADMAP SC#2 / T-59-14):
       On a pure-conflict re-run, 0 audit rows are added.
  5. created_by_user_id IS NULL for all cron-generated rows (D-59-05).
"""

from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta
from typing import Any
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit_models import AuditLog
from app.modules.schedule.models import (
    RecurringSlotTemplate,
    TrainerAvailabilitySlot,
    TrainerTimeOff,
)
from app.modules.schedule.service import _expand_template_occurrences, _generate_recurring_slots
from app.modules.trainers.models import Trainer

# ---------------------------------------------------------------------------
# 1. DST golden test — pure unit, no DB required
# ---------------------------------------------------------------------------


def test_expand_dst_golden_monday_10am() -> None:
    """PITFALL 7 / T-59-15 — expand(MONDAY, 10:00, from=2026-03-30).

    Moscow has been permanently UTC+3 since 2014-10-26 (last DST clock change).
    ZoneInfo("Europe/Moscow") must resolve UTC+3 for 2026-03-30, giving
    2026-03-30 07:00:00+00:00 for a 10:00 MSK slot.
    """
    results = _expand_template_occurrences(
        trainer_id=uuid4(),
        day_of_week=0,  # Monday
        start_time_local=time(10, 0),
        end_time_local=time(11, 0),
        from_date=date(2026, 3, 30),
        to_date=date(2026, 3, 30),
    )
    assert len(results) == 1, f"expected 1 occurrence, got {len(results)}"
    start_utc = results[0]["start_time"]
    assert isinstance(start_utc, datetime)
    assert start_utc.tzinfo is not None, "start_time must be TZ-aware"
    # Canonical check: UTC offset must be exactly -3 hours from local 10:00 MSK.
    expected = datetime(2026, 3, 30, 7, 0, 0, tzinfo=UTC)
    assert start_utc == expected, (
        f"DST golden FAILED: expected {expected}, got {start_utc}. "
        "Likely cause: naive timedelta or wrong tz (PITFALL 7)."
    )


def test_expand_no_match_on_wrong_day() -> None:
    """expand returns empty list when from_date to to_date has no matching weekday."""
    results = _expand_template_occurrences(
        trainer_id=uuid4(),
        day_of_week=0,  # Monday
        start_time_local=time(10, 0),
        end_time_local=time(11, 0),
        # 2026-03-31 is Tuesday — no Mondays in this range.
        from_date=date(2026, 3, 31),
        to_date=date(2026, 3, 31),
    )
    assert results == []


# ---------------------------------------------------------------------------
# 2. Happy-path insert + idempotency + time-off-skip + audit
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_generate_recurring_slots_inserts_and_audits(
    db_session: AsyncSession,
    make_trainer: Any,
) -> None:
    """First run inserts rows and emits slot_published; second run inserts 0 rows."""
    trainer: Trainer = await make_trainer(is_active=True)

    # Create an active template: every Monday 09:00-10:00 MSK.
    # now() is ~2026-05-25; horizon=56 days from "now_override" below.
    # We pin now_override to a Wednesday so there are Mondays ahead in the window.
    now_override = datetime(2026, 5, 27, 4, 0, 0, tzinfo=UTC)  # Wednesday 07:00 MSK

    tmpl = RecurringSlotTemplate(
        trainer_id=trainer.id,
        day_of_week=0,  # Monday
        start_time=time(9, 0),
        end_time=time(10, 0),
        valid_from=now_override.date(),
        valid_until=None,
        is_active=True,
    )
    db_session.add(tmpl)
    await db_session.commit()

    # Count Mondays between now_override+1day and horizon_end (inclusive).
    # Mondays in the window 2026-05-28..2026-07-22: 2026-06-01,08,15,22,29, 07-06,13,20
    # = 8 Mondays whose start (06:00 UTC) is > now_override.
    count_first = await _generate_recurring_slots(db_session, now=now_override)
    await db_session.commit()

    assert count_first > 0, f"expected > 0 inserts on first run, got {count_first}"

    # Audit rows emitted: exactly count_first slot_published rows.
    audit_rows = (
        (
            await db_session.execute(
                select(AuditLog).where(
                    AuditLog.action == "slot_published",
                    AuditLog.actor_user_id.is_(None),
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(audit_rows) == count_first, (
        f"expected {count_first} slot_published audit rows, got {len(audit_rows)}"
    )
    # All audit rows have actor_user_id=None (cron actor).
    for row in audit_rows:
        assert row.actor_user_id is None

    # created_by_user_id IS NULL on all inserted slots.
    slots = (
        (
            await db_session.execute(
                select(TrainerAvailabilitySlot).where(
                    TrainerAvailabilitySlot.trainer_id == trainer.id,
                    TrainerAvailabilitySlot.status == "active",
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(slots) == count_first
    for slot in slots:
        assert slot.created_by_user_id is None, (
            f"expected created_by_user_id=NULL on cron-generated slot {slot.id}"
        )

    # 2nd run — idempotency: must insert 0 rows and emit 0 new audit rows.
    count_second = await _generate_recurring_slots(db_session, now=now_override)
    await db_session.commit()

    assert count_second == 0, (
        f"idempotency FAILED: second run inserted {count_second} rows (expected 0)"
    )

    # Audit row count must be unchanged (no new slot_published).
    audit_rows_after = (
        (
            await db_session.execute(
                select(AuditLog).where(
                    AuditLog.action == "slot_published",
                    AuditLog.actor_user_id.is_(None),
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(audit_rows_after) == count_first, (
        f"idempotency FAILED: new audit rows emitted on re-run "
        f"({len(audit_rows_after)} total, expected {count_first})"
    )


@pytest.mark.asyncio
async def test_generate_recurring_slots_skips_time_off_window(
    db_session: AsyncSession,
    make_trainer: Any,
) -> None:
    """PITFALL 9 inverse / T-59-16 — slots inside active time-off windows are NOT inserted."""
    trainer: Trainer = await make_trainer(is_active=True)

    # now pinned to 2026-05-27 04:00 UTC (Wednesday 07:00 MSK).
    now_override = datetime(2026, 5, 27, 4, 0, 0, tzinfo=UTC)

    # Template: every Monday 09:00-10:00 MSK.
    tmpl = RecurringSlotTemplate(
        trainer_id=trainer.id,
        day_of_week=0,  # Monday
        start_time=time(9, 0),
        end_time=time(10, 0),
        valid_from=now_override.date(),
        valid_until=None,
        is_active=True,
    )
    db_session.add(tmpl)

    # Time-off block that covers the FIRST Monday in the horizon
    # (2026-06-01 06:00 UTC = 09:00 MSK).
    # Block: 2026-06-01 05:00 UTC → 2026-06-01 08:00 UTC (covers the 06:00-07:00 slot).
    first_monday_start_utc = datetime(2026, 6, 1, 6, 0, 0, tzinfo=UTC)
    time_off = TrainerTimeOff(
        trainer_id=trainer.id,
        block_start=first_monday_start_utc - timedelta(hours=1),
        block_end=first_monday_start_utc + timedelta(hours=2),
        reason="vacation",
    )
    db_session.add(time_off)
    await db_session.commit()

    count = await _generate_recurring_slots(db_session, now=now_override)
    await db_session.commit()

    # All Mondays except the first (covered by time-off) should be inserted.
    assert count > 0, "expected at least some slots to be inserted"

    # The slot at first_monday_start_utc must NOT exist.
    blocked_slot = (
        await db_session.execute(
            select(TrainerAvailabilitySlot).where(
                TrainerAvailabilitySlot.trainer_id == trainer.id,
                TrainerAvailabilitySlot.start_time == first_monday_start_utc,
            )
        )
    ).scalar_one_or_none()
    assert blocked_slot is None, (
        f"time-off skip FAILED: slot at {first_monday_start_utc} was inserted "
        "despite falling inside the time-off window (PITFALL 9 inverse)"
    )


@pytest.mark.asyncio
async def test_generate_recurring_slots_no_templates_returns_zero(
    db_session: AsyncSession,
) -> None:
    """When there are no active recurring templates, helper returns 0."""
    now_override = datetime(2026, 5, 27, 4, 0, 0, tzinfo=UTC)
    count = await _generate_recurring_slots(db_session, now=now_override)
    await db_session.commit()
    assert count == 0
