"""Integration tests for Alembic 0045 — ck_visits_channel extended with 'client_qr'.

Revision under test: 0045_visits_channel_client_qr

Background (Phase 70 D-70-11 / T-70-04): the migration extends the visits.channel
CHECK constraint from ``channel IN ('reception', 'telegram_bot')`` to
``channel IN ('reception', 'telegram_bot', 'client_qr')``. Postgres does not
support ALTER for CHECK expressions — the migration drops and recreates the
constraint under the same name ``ck_visits_channel``.

Tests:
  test_0045_constraint_name_present — ck_visits_channel exists in pg_constraint.
  test_0045_constraint_includes_client_qr — the CHECK expression includes 'client_qr'.
  test_0045_channel_allows_client_qr — insert with channel='client_qr' is accepted.
  test_0045_channel_rejects_bogus — channel='bogus' is still rejected after upgrade.
  test_0045_round_trip — downgrade restores 2-value CHECK; upgrade re-extends it.
"""

from __future__ import annotations

import subprocess
from collections.abc import AsyncIterator
from pathlib import Path
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings

BACKEND_DIR = Path(__file__).resolve().parent.parent.parent.parent

_REV_PREV = "0044_client_refresh_token"


def _run_alembic(*args: str) -> subprocess.CompletedProcess[str]:
    """Run an alembic sub-command via ``uv run alembic <args>``."""
    return subprocess.run(  # noqa: S603
        ["uv", "run", "alembic", *args],  # noqa: S607
        cwd=str(BACKEND_DIR),
        capture_output=True,
        text=True,
        check=False,
    )


def _assert_alembic_ok(result: subprocess.CompletedProcess[str], label: str) -> None:
    assert result.returncode == 0, (
        f"alembic {label} failed (exit {result.returncode}):\n"
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )


@pytest_asyncio.fixture
async def direct_engine_session() -> AsyncIterator[AsyncSession]:
    """Async session with REAL commits against the test DB; skips on unreachable Postgres."""
    settings = get_settings()
    engine = create_async_engine(str(settings.database_url), pool_pre_ping=True)

    try:
        async with engine.connect() as probe:
            await probe.execute(text("select 1"))
    except Exception as exc:
        await engine.dispose()
        pytest.skip(
            f"DATABASE_URL not reachable; run `docker compose up postgres` first ({exc!r})"
        )

    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session

    await engine.dispose()


# ---------------------------------------------------------------------------
# Seed helpers — build a minimal but valid visits row.
# visits FKs: client_id → clients (RESTRICT), membership_id → memberships (RESTRICT)
# checked_in_by → users (SET NULL, nullable)
# ---------------------------------------------------------------------------

_INSERT_USER = """
    INSERT INTO users (id, email, password_hash, role, full_name, created_at, updated_at)
    VALUES (:uid, :email, 'x', 'reception', 'qr-mig-test', now(), now())
    ON CONFLICT DO NOTHING
"""

_INSERT_CLIENT = """
    INSERT INTO clients
        (id, last_name, first_name, phone, created_by_user_id, created_at, updated_at)
    VALUES (:cid, 'QR', 'Test', :phone, :uid, now(), now())
"""

# memberships: plan_id FK → membership_plans (must exist). Use the first available plan.
# Required non-null cols: client_id, plan_id, plan_name_snapshot, duration_days_snapshot,
# price_kopecks_snapshot, start_date, end_date, freeze_days_limit_snapshot.
_INSERT_MEMBERSHIP = """
    INSERT INTO memberships
      (client_id, plan_id, plan_name_snapshot, duration_days_snapshot,
       price_kopecks_snapshot, start_date, end_date, freeze_days_limit_snapshot,
       created_at, updated_at)
    SELECT :cid, id, name, duration_days, price_kopecks,
           now()::date, (now() + interval '30 days')::date, 0,
           now(), now()
    FROM membership_plans ORDER BY created_at LIMIT 1
    RETURNING id
"""

_INSERT_VISIT = """
    INSERT INTO visits
      (client_id, membership_id, checked_in_at, gym_date, channel, created_at, updated_at)
    VALUES (:cid, :mid, now(), now()::date, :channel, now(), now())
"""

_DELETE_VISITS = "DELETE FROM visits WHERE client_id = :cid"
_DELETE_MEMBERSHIPS = "DELETE FROM memberships WHERE client_id = :cid"
_DELETE_CLIENTS = "DELETE FROM clients WHERE id = :cid"
_DELETE_USER = "DELETE FROM users WHERE id = :uid"


async def _seed_parent_rows(
    session: AsyncSession,
    *,
    user_id: str,
    client_id: str,
    phone: str,
    user_email: str,
) -> str | None:
    """Seed user + client + membership; return membership_id or None if no plan exists."""
    await session.execute(text(_INSERT_USER), {"uid": user_id, "email": user_email})
    await session.execute(text(_INSERT_CLIENT), {"cid": client_id, "phone": phone, "uid": user_id})

    row = await session.execute(text(_INSERT_MEMBERSHIP), {"cid": client_id})
    mid = row.scalar_one_or_none()
    await session.commit()
    return str(mid) if mid is not None else None


async def _cleanup(session: AsyncSession, *, user_id: str, client_id: str) -> None:
    await session.execute(text(_DELETE_VISITS), {"cid": client_id})
    await session.execute(text(_DELETE_MEMBERSHIPS), {"cid": client_id})
    await session.execute(text(_DELETE_CLIENTS), {"cid": client_id})
    await session.execute(text(_DELETE_USER), {"uid": user_id})
    await session.commit()


# ---------------------------------------------------------------------------
# Schema-level tests (no row insertion required)
# ---------------------------------------------------------------------------


async def test_0045_constraint_name_present(
    direct_engine_session: AsyncSession,
) -> None:
    """ck_visits_channel constraint exists on the visits table after upgrade head."""
    _assert_alembic_ok(_run_alembic("upgrade", "head"), "upgrade head")

    session = direct_engine_session
    rows = (
        await session.execute(
            text(
                "SELECT conname FROM pg_constraint"
                " WHERE conrelid = 'visits'::regclass AND conname = 'ck_visits_channel'"
            )
        )
    ).fetchall()
    assert len(rows) == 1, "ck_visits_channel constraint must exist on visits table"


async def test_0045_constraint_includes_client_qr(
    direct_engine_session: AsyncSession,
) -> None:
    """After upgrade head, ck_visits_channel expression contains 'client_qr' (T-70-04)."""
    _assert_alembic_ok(_run_alembic("upgrade", "head"), "upgrade head")

    session = direct_engine_session
    row = (
        await session.execute(
            text(
                "SELECT pg_get_constraintdef(oid) AS constraint_def"
                " FROM pg_constraint"
                " WHERE conrelid = 'visits'::regclass AND conname = 'ck_visits_channel'"
            )
        )
    ).fetchone()
    assert row is not None, "ck_visits_channel must exist"
    assert "client_qr" in row.constraint_def, (
        f"expected 'client_qr' in CHECK expression; got: {row.constraint_def!r}"
    )


# ---------------------------------------------------------------------------
# Row-level tests (require at least one membership_plan to exist)
# ---------------------------------------------------------------------------


async def test_0045_channel_allows_client_qr(
    direct_engine_session: AsyncSession,
) -> None:
    """After upgrade head, inserting channel='client_qr' is accepted by the DB CHECK."""
    _assert_alembic_ok(_run_alembic("upgrade", "head"), "upgrade head")

    session = direct_engine_session
    uid = str(uuid4())
    cid = str(uuid4())
    nonce = uuid4().hex[:8]

    mid = await _seed_parent_rows(
        session,
        user_id=uid,
        client_id=cid,
        phone=f"+79000{nonce}",
        user_email=f"qrmig-{nonce}@test.local",
    )
    if mid is None:
        pytest.skip("No membership_plans in DB — seed a plan to run row-level tests")

    try:
        # Must not raise — 'client_qr' is in the extended CHECK.
        await session.execute(
            text(_INSERT_VISIT),
            {"cid": cid, "mid": mid, "channel": "client_qr"},
        )
        await session.commit()
    finally:
        await _cleanup(session, user_id=uid, client_id=cid)


async def test_0045_channel_rejects_bogus(
    direct_engine_session: AsyncSession,
) -> None:
    """After upgrade head, channel='bogus' is still rejected (T-70-04 allow-list integrity)."""
    _assert_alembic_ok(_run_alembic("upgrade", "head"), "upgrade head")

    session = direct_engine_session
    uid = str(uuid4())
    cid = str(uuid4())
    nonce = uuid4().hex[:8]

    mid = await _seed_parent_rows(
        session,
        user_id=uid,
        client_id=cid,
        phone=f"+79001{nonce}",
        user_email=f"qrmig-bogus-{nonce}@test.local",
    )
    if mid is None:
        pytest.skip("No membership_plans in DB — seed a plan to run row-level tests")

    try:
        with pytest.raises(IntegrityError):
            await session.execute(
                text(_INSERT_VISIT),
                {"cid": cid, "mid": mid, "channel": "bogus"},
            )
            await session.commit()
        await session.rollback()
    finally:
        await _cleanup(session, user_id=uid, client_id=cid)


async def test_0045_round_trip(
    direct_engine_session: AsyncSession,
) -> None:
    """Downgrade removes 'client_qr' from CHECK expression; upgrade head restores it."""
    _assert_alembic_ok(_run_alembic("upgrade", "head"), "upgrade head (pre round-trip)")

    session = direct_engine_session

    # 1. Downgrade to previous revision.
    _assert_alembic_ok(_run_alembic("downgrade", _REV_PREV), f"downgrade {_REV_PREV}")

    try:
        # After downgrade, 'client_qr' must NOT appear in the CHECK expression.
        row = (
            await session.execute(
                text(
                    "SELECT pg_get_constraintdef(oid) AS constraint_def"
                    " FROM pg_constraint"
                    " WHERE conrelid = 'visits'::regclass AND conname = 'ck_visits_channel'"
                )
            )
        ).fetchone()
        assert row is not None, "ck_visits_channel must still exist after downgrade"
        assert "client_qr" not in row.constraint_def, (
            f"expected 'client_qr' to be ABSENT after downgrade; got: {row.constraint_def!r}"
        )
    finally:
        # Always restore head for downstream tests.
        _assert_alembic_ok(_run_alembic("upgrade", "head"), "upgrade head (post round-trip)")

    # 2. After upgrade head, 'client_qr' must be back.
    row = (
        await session.execute(
            text(
                "SELECT pg_get_constraintdef(oid) AS constraint_def"
                " FROM pg_constraint"
                " WHERE conrelid = 'visits'::regclass AND conname = 'ck_visits_channel'"
            )
        )
    ).fetchone()
    assert row is not None, "ck_visits_channel must exist after re-upgrade"
    assert "client_qr" in row.constraint_def, (
        f"expected 'client_qr' back in CHECK after upgrade head; got: {row.constraint_def!r}"
    )
