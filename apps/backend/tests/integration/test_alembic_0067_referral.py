"""Phase 96 REFER-01/03/07 — Alembic 0067 + 0068 referral tables + seed.

Migration under test: ``0067_referral_tables`` (DDL) + ``0068_seed_referral_config`` (seed).

Background:
- 0067 creates three tables: referral_codes, referral_captures, referral_config.
- 0068 seeds the referral_config singleton row with referrer_bonus_kopecks=50000
  and referee_welcome_kopecks=30000.

Test strategy:
- Schema-shape tests: verify the three tables exist in information_schema.
- Seed-content test: assert referral_config singleton row has the expected kopeck values.
- UNIQUE index tests: assert uq_referral_codes_code and
  uq_referral_captures_referee_client_id exist in pg_indexes by their exact names.

The ``db_session`` fixture from tests/conftest.py wraps each test in a SAVEPOINT
rollback so seeded rows never persist between tests. The conftest app fixture
fires migrations to head before the session is yielded.
"""

from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.mark.asyncio
async def test_three_referral_tables_exist(db_session: AsyncSession) -> None:
    """0067 must create referral_codes, referral_captures, and referral_config tables."""
    result = await db_session.execute(
        text(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = 'public' "
            "  AND table_name IN ('referral_codes', 'referral_captures', 'referral_config') "
            "ORDER BY table_name"
        )
    )
    found = {row[0] for row in result.fetchall()}
    assert found == {"referral_codes", "referral_captures", "referral_config"}, (
        f"Expected all three referral tables; found: {found}"
    )


@pytest.mark.asyncio
async def test_referral_config_singleton_seed_values(db_session: AsyncSession) -> None:
    """0068 must seed exactly one referral_config row with kopecks 50000 / 30000."""
    row = await db_session.execute(
        text(
            "SELECT referrer_bonus_kopecks, referee_welcome_kopecks "
            "FROM referral_config "
            "WHERE id = CAST(:sid AS uuid)"
        ).bindparams(sid="00000000-0000-0000-0000-000000000002")
    )
    record = row.mappings().one_or_none()
    assert record is not None, "referral_config singleton row must exist after 0068"
    assert record["referrer_bonus_kopecks"] == 50_000, (
        f"referrer_bonus_kopecks should be 50000; got {record['referrer_bonus_kopecks']}"
    )
    assert record["referee_welcome_kopecks"] == 30_000, (
        f"referee_welcome_kopecks should be 30000; got {record['referee_welcome_kopecks']}"
    )


@pytest.mark.asyncio
async def test_uq_referral_codes_code_index_exists(db_session: AsyncSession) -> None:
    """0067 must create UNIQUE index uq_referral_codes_code on referral_codes.code."""
    result = await db_session.execute(
        text(
            "SELECT indexname FROM pg_indexes "
            "WHERE tablename = 'referral_codes' "
            "  AND indexname = 'uq_referral_codes_code'"
        )
    )
    assert result.fetchone() is not None, (
        "UNIQUE index uq_referral_codes_code must exist on referral_codes"
    )


@pytest.mark.asyncio
async def test_uq_referral_captures_referee_client_id_index_exists(
    db_session: AsyncSession,
) -> None:
    """0067 must create UNIQUE index uq_referral_captures_referee_client_id."""
    result = await db_session.execute(
        text(
            "SELECT indexname FROM pg_indexes "
            "WHERE tablename = 'referral_captures' "
            "  AND indexname = 'uq_referral_captures_referee_client_id'"
        )
    )
    assert result.fetchone() is not None, (
        "UNIQUE index uq_referral_captures_referee_client_id must exist on referral_captures"
    )
