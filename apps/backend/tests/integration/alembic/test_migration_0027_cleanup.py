"""CR-04 regression tests — defensive UPDATE pass in migration 0027.

Revision under test: ``0027_otp_channel_discriminator``

Background: Migration 0027 creates a partial-UNIQUE index
``uq_otp_codes_user_channel_active ON otp_codes (user_id, channel)
WHERE consumed_at IS NULL``. Without a defensive cleanup pass, any
pre-existing rows with the same ``(user_id, channel)`` pair and
``consumed_at IS NULL`` would cause the index creation to fail with
``duplicate key value violates unique constraint``.

CR-04 fix (plan 42-15): a ``DISTINCT ON``-based UPDATE runs BEFORE
the partial-UNIQUE creation and marks all but the latest per group as
consumed. These tests seed the colliding-row scenario and verify the
upgrade survives it.

Test strategy (mirrors test_alembic_clean.py):
- alembic commands are dispatched via ``subprocess.run`` with
  ``uv run alembic`` (blocking calls in async test bodies, matching
  the existing integration-test convention).
- SQL seeding uses a direct async engine from ``get_settings()`` so
  seeded rows are COMMITTED to the DB before the upgrade subprocess
  reads them (SAVEPOINT-wrapped sessions would hide them).
- Cleanup: DELETE the seeded rows after each test so the test leaves
  the DB in a clean state for subsequent runs.
"""

from __future__ import annotations

import subprocess
from collections.abc import AsyncIterator
from pathlib import Path
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings

BACKEND_DIR = Path(__file__).resolve().parent.parent.parent.parent

# Alembic revision identifiers used in downgrade/upgrade calls.
_REV_0026 = "0026_email_send_log"
_REV_0027 = "0027_otp_channel_discriminator"

# SQL INSERT for otp_codes (pre-0027 schema: no channel column).
# Two variants: row_a uses now() for created_at; row_b uses now() + 1 second
# so the DISTINCT ON (user_id, channel ORDER BY created_at DESC) keeps row_b.
_INSERT_OTP_A = (
    "INSERT INTO otp_codes "
    "(id, user_id, deep_link_token_hash, code_hash,"
    " expires_at, attempts, consumed_at, created_at)"
    " VALUES"
    " (gen_random_uuid(), :uid, :dlh, :ch,"
    " now() + interval '10 minutes', 0, NULL, now())"
    " RETURNING id"
)
_INSERT_OTP_B = (
    "INSERT INTO otp_codes "
    "(id, user_id, deep_link_token_hash, code_hash,"
    " expires_at, attempts, consumed_at, created_at)"
    " VALUES"
    " (gen_random_uuid(), :uid, :dlh, :ch,"
    " now() + interval '10 minutes', 0, NULL,"
    " now() + interval '1 second')"
    " RETURNING id"
)

# Test users INSERT — satisfies fk_otp_codes_user_id_users for the seeded
# otp_codes rows. Columns mirror the live users schema (email, password_hash,
# role, full_name NOT NULL). Test rows are deleted in the test's finally block.
_INSERT_USER = (
    "INSERT INTO users (id, email, password_hash, role, full_name, created_at, updated_at)"
    " VALUES (:uid, :email, 'x', 'reception', 'cr04-test', now(), now())"
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _run_alembic(*args: str) -> subprocess.CompletedProcess[str]:
    """Run an alembic sub-command via ``uv run alembic <args>``.

    Uses ``subprocess.run`` (blocking) to match the project convention
    in ``test_alembic_clean.py``.
    """
    return subprocess.run(  # noqa: S603
        ["uv", "run", "alembic", *args],  # noqa: S607
        cwd=str(BACKEND_DIR),
        capture_output=True,
        text=True,
        check=False,
    )


def _assert_alembic_ok(result: subprocess.CompletedProcess[str], label: str) -> None:
    """Assert that an alembic subprocess call exited 0."""
    assert result.returncode == 0, (
        f"alembic {label} failed (exit {result.returncode}):\n"
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def direct_engine_session() -> AsyncIterator[AsyncSession]:
    """Async session with REAL commits against the test DB.

    Unlike the SAVEPOINT-wrapped ``db_session`` fixture, this session
    issues genuine COMMITs so that seeded rows are visible to alembic
    subprocess commands that open their own connection.

    Skips the test cleanly if Postgres is unreachable.
    """
    settings = get_settings()
    engine = create_async_engine(str(settings.database_url), pool_pre_ping=True)

    try:
        async with engine.connect() as probe:
            await probe.execute(text("select 1"))
    except Exception as exc:  # broad: skip on any connectivity failure
        await engine.dispose()
        pytest.skip(f"DATABASE_URL not reachable; run `docker compose up postgres` first ({exc!r})")

    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session

    await engine.dispose()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


async def test_0027_upgrade_with_colliding_unconsumed_rows(
    direct_engine_session: AsyncSession,
) -> None:
    """Upgrade from 0026 to 0027 succeeds even with pre-existing colliding rows.

    Scenario: two OtpCode rows with the same ``user_id`` and
    ``consumed_at IS NULL`` exist on the 0026 schema (no ``channel``
    column yet — DEFAULT 'telegram' backfill happens during upgrade).
    Without the CR-04 defensive UPDATE, the partial-UNIQUE creation
    would raise ``duplicate key value violates unique constraint``.
    With it, the upgrade succeeds and exactly one row per user survives
    with ``consumed_at IS NULL``.

    CR-04 regression guard.
    """
    session = direct_engine_session
    user_id = uuid4()
    seeded_ids: list[str] = []

    # Step 1: downgrade to 0026 so we can seed pre-0027 rows (no ``channel``
    # column, which the 0027 upgrade adds with DEFAULT 'telegram').
    result = _run_alembic("downgrade", _REV_0026)
    _assert_alembic_ok(result, f"downgrade {_REV_0026}")

    try:
        # Seed the parent user row (FK target for the otp_codes seeds below).
        await session.execute(
            text(_INSERT_USER),
            {"uid": str(user_id), "email": f"cr04-{uuid4().hex}@test.local"},
        )

        # Step 2: seed two rows with the SAME user_id, both consumed_at=NULL.
        # ``deep_link_token_hash`` must be UNIQUE per row (separate constraint).
        # row_b's created_at is 1 second later — DISTINCT ON keeps row_b.
        row_a = await session.execute(
            text(_INSERT_OTP_A),
            {"uid": str(user_id), "dlh": f"test-cr04-a-{uuid4().hex}", "ch": "ch_a"},
        )
        seeded_ids.append(str(row_a.scalar_one()))

        row_b = await session.execute(
            text(_INSERT_OTP_B),
            {"uid": str(user_id), "dlh": f"test-cr04-b-{uuid4().hex}", "ch": "ch_b"},
        )
        seeded_ids.append(str(row_b.scalar_one()))
        await session.commit()

        # Step 3: upgrade to 0027 (head). Without the CR-04 defensive UPDATE
        # this would fail on the partial-UNIQUE creation.
        upgrade_result = _run_alembic("upgrade", "head")
        _assert_alembic_ok(upgrade_result, "upgrade head (CR-04 regression check)")

        # Step 4: assert exactly ONE unconsumed row per (user_id, channel).
        # The older row (created_at earlier) should have been consumed by
        # the defensive UPDATE; the newer row should remain unconsumed.
        rows = (
            await session.execute(
                text("SELECT id, consumed_at FROM otp_codes WHERE user_id = :uid"),
                {"uid": str(user_id)},
            )
        ).fetchall()
        assert len(rows) == 2, f"expected both seeded rows to survive the upgrade, got {len(rows)}"
        unconsumed = [r for r in rows if r.consumed_at is None]
        assert len(unconsumed) == 1, (
            f"expected exactly 1 unconsumed row after CR-04 defensive cleanup, "
            f"got {len(unconsumed)} (CR-04 regression)"
        )

    finally:
        # Cleanup: remove the seeded rows so subsequent test runs start clean.
        # Delete otp_codes by user_id (simpler than passing an array param);
        # then delete the parent user row.
        await session.execute(
            text("DELETE FROM otp_codes WHERE user_id = :uid"), {"uid": str(user_id)}
        )
        await session.execute(text("DELETE FROM users WHERE id = :uid"), {"uid": str(user_id)})
        await session.commit()


async def test_0027_round_trip_with_data(
    direct_engine_session: AsyncSession,
) -> None:
    """alembic downgrade 0026 + upgrade head round-trips cleanly with seeded data.

    Verifies that the defensive UPDATE pass also fires on a repeat upgrade
    after a downgrade (round-trip discipline).

    CR-04 regression guard.
    """
    session = direct_engine_session
    user_id = uuid4()
    seeded_ids: list[str] = []

    # Ensure we start at head before downgrading.
    head_result = _run_alembic("upgrade", "head")
    _assert_alembic_ok(head_result, "upgrade head (round-trip pre-seed)")

    # Downgrade to 0026 to seed pre-0027 colliding rows.
    result = _run_alembic("downgrade", _REV_0026)
    _assert_alembic_ok(result, f"downgrade {_REV_0026} (round-trip)")

    try:
        # Seed the parent user row (FK target for the otp_codes seeds below).
        await session.execute(
            text(_INSERT_USER),
            {"uid": str(user_id), "email": f"cr04-rt-{uuid4().hex}@test.local"},
        )

        row_a = await session.execute(
            text(_INSERT_OTP_A),
            {"uid": str(user_id), "dlh": f"test-cr04-rt-a-{uuid4().hex}", "ch": "ch_a"},
        )
        seeded_ids.append(str(row_a.scalar_one()))

        row_b = await session.execute(
            text(_INSERT_OTP_B),
            {"uid": str(user_id), "dlh": f"test-cr04-rt-b-{uuid4().hex}", "ch": "ch_b"},
        )
        seeded_ids.append(str(row_b.scalar_one()))
        await session.commit()

        # Round-trip: upgrade head again — defensive UPDATE must run cleanly.
        upgrade_result = _run_alembic("upgrade", "head")
        _assert_alembic_ok(upgrade_result, "upgrade head (round-trip with data)")

        # Sanity check: the schema should now be at head (the partial-UNIQUE
        # from 0027 is in place; later migrations have also applied).
        current_result = _run_alembic("current")
        _assert_alembic_ok(current_result, "current (round-trip verification)")
        assert "(head)" in current_result.stdout, (
            f"alembic current did not show head revision after upgrade:\n{current_result.stdout}"
        )

    finally:
        # Cleanup: remove seeded rows (otp_codes by user_id, then the user).
        await session.execute(
            text("DELETE FROM otp_codes WHERE user_id = :uid"), {"uid": str(user_id)}
        )
        await session.execute(text("DELETE FROM users WHERE id = :uid"), {"uid": str(user_id)})
        await session.commit()
