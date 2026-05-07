"""Integration tests for alembic/versions/0006_visits.py migration.

D-15 / Pitfall 5 mandate: test against real Postgres 16. SQLite cannot
represent STORED GENERATED columns, so this test ONLY passes against real
Postgres 16 — proving the migration's headline feature works.

The `db_session` fixture skips cleanly if compose Postgres is unreachable.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.visits.models import Visit


async def test_gym_date_generated_column_msk_shifted(
    db_session: AsyncSession,
    make_visit_setup: Any,
) -> None:
    """D-15 / Pitfall 5: STORED GENERATED gym_date computes MSK-local date.

    UTC 22:30 on 2026-05-07 = MSK 01:30 on 2026-05-08, so gym_date = 2026-05-08.
    SQLite cannot fake STORED GENERATED — only real Postgres 16 returns the
    correct date. This test is the canonical proof that the migration's
    `(checked_in_at AT TIME ZONE 'Europe/Moscow')::date` GENERATED ALWAYS column
    works as intended.
    """
    client_obj, membership = await make_visit_setup()

    # UTC 22:30 on 2026-05-07 = MSK 01:30 on 2026-05-08
    utc_2230 = datetime(2026, 5, 7, 22, 30, tzinfo=UTC)

    visit = Visit(
        client_id=client_obj.id,
        membership_id=membership.id,
        channel="reception",
        checked_in_at=utc_2230,
        checked_in_by=None,
    )
    db_session.add(visit)
    await db_session.flush()

    # Refresh to get the GENERATED column value from Postgres
    await db_session.refresh(visit, attribute_names=["gym_date"])

    assert visit.gym_date == date(2026, 5, 8), (
        f"Expected gym_date=2026-05-08 (MSK=01:30 next day), got {visit.gym_date}. "
        "This test requires real Postgres 16 with the Europe/Moscow timezone data. "
        "SQLite cannot represent STORED GENERATED columns (Pitfall 5 mandate)."
    )
