"""INFRA-41 regression tests — Alembic 0033 partial UNIQUE on clients.email.

Revision under test: ``0033_clients_email_partial_unique``

Background (Phase 47 INFRA-41 / D-47-03/04/05): the migration adds a partial
UNIQUE index ``ix_clients_email_lower_unique`` on ``clients(lower(email))``
with predicate ``WHERE email IS NOT NULL AND deleted_at IS NULL``. The
``clients.email`` column ALREADY exists since Alembic 0002 (v1.1), so the
migration does NOT add the column and does NOT narrow ``Text → VARCHAR(255)``.

The migration runs a pre-flight duplicate check (D-47-05): if any case-
insensitive duplicate among LIVE rows (``deleted_at IS NULL``) exists, the
upgrade aborts with a ``RuntimeError`` listing offenders so the operator can
resolve manually and re-run. No silent dedup, no soft-delete, no automatic
backfill.

Test strategy (mirrors ``test_migration_0027_cleanup.py``):
- Alembic commands are dispatched via ``subprocess.run`` with
  ``uv run alembic`` (blocking calls in async test bodies).
- SQL seeding uses a direct async engine from ``get_settings()`` so seeded
  rows are COMMITTED before the upgrade subprocess opens its own connection.
- Cleanup: DELETE seeded rows in a ``finally`` block.

Tests:
    test_0033_upgrade_clean_no_duplicates — fresh-DB upgrade succeeds + index exists.
    test_0033_upgrade_aborts_on_duplicate — case-insensitive collision triggers RuntimeError.
    test_0033_soft_deleted_duplicate_allowed — predicate excludes soft-deleted rows.
    test_0033_round_trip_drops_index — downgrade removes the index; clients.email untouched.
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

_REV_HEAD = "0033_clients_email_partial_unique"
_REV_PREV = "0032_booking_notif_widen_kind"
_INDEX_NAME = "ix_clients_email_lower_unique"

# Seed parent user row — clients.created_by_user_id NOT NULL FK -> users.id.
_INSERT_USER = (
    "INSERT INTO users (id, email, password_hash, role, full_name, created_at, updated_at)"
    " VALUES (:uid, :email, 'x', 'reception', 'infra41-test', now(), now())"
)

# Seed clients row with provided email + deleted_at semantics.
_INSERT_CLIENT_ALIVE = (
    "INSERT INTO clients"
    " (id, last_name, first_name, phone, email, created_by_user_id, deleted_at,"
    "  created_at, updated_at)"
    " VALUES (gen_random_uuid(), 'Test', 'Client', :phone, :email, :uid, NULL,"
    "         now(), now())"
    " RETURNING id"
)
_INSERT_CLIENT_SOFT_DELETED = (
    "INSERT INTO clients"
    " (id, last_name, first_name, phone, email, created_by_user_id, deleted_at,"
    "  created_at, updated_at)"
    " VALUES (gen_random_uuid(), 'Test', 'Client', :phone, :email, :uid, now(),"
    "         now(), now())"
    " RETURNING id"
)


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
    except Exception as exc:  # broad: skip on any connectivity failure
        await engine.dispose()
        pytest.skip(
            f"DATABASE_URL not reachable; run `docker compose up postgres` first ({exc!r})"
        )

    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session

    await engine.dispose()


async def test_0033_upgrade_clean_no_duplicates(
    direct_engine_session: AsyncSession,
) -> None:
    """Fresh-DB upgrade to 0033 head succeeds and creates ix_clients_email_lower_unique."""
    session = direct_engine_session

    # Ensure we start at head.
    _assert_alembic_ok(_run_alembic("upgrade", "head"), "upgrade head (pre-test)")

    # Sanity: head revision matches expected.
    current = _run_alembic("current")
    _assert_alembic_ok(current, "current (head probe)")
    assert _REV_HEAD in current.stdout, (
        f"expected alembic head to be {_REV_HEAD}; got:\n{current.stdout}"
    )

    # The partial UNIQUE index must exist in pg_indexes with the documented predicate.
    rows = (
        await session.execute(
            text(
                "SELECT indexdef FROM pg_indexes "
                "WHERE schemaname = 'public' AND indexname = :name"
            ),
            {"name": _INDEX_NAME},
        )
    ).fetchall()
    assert len(rows) == 1, f"expected exactly 1 row for index {_INDEX_NAME}; got {len(rows)}"
    indexdef = rows[0].indexdef
    assert "lower(email)" in indexdef
    assert "UNIQUE" in indexdef
    assert "email IS NOT NULL" in indexdef and "deleted_at IS NULL" in indexdef


async def test_0033_upgrade_aborts_on_duplicate(
    direct_engine_session: AsyncSession,
) -> None:
    """Pre-flight duplicate check aborts with RuntimeError listing offending email."""
    session = direct_engine_session
    user_id = uuid4()
    seeded_client_ids: list[str] = []

    # Ensure we start at head, then downgrade to 0032 so we can seed a duplicate.
    _assert_alembic_ok(_run_alembic("upgrade", "head"), "upgrade head (pre-seed)")
    _assert_alembic_ok(_run_alembic("downgrade", _REV_PREV), f"downgrade {_REV_PREV}")

    try:
        # Seed the parent user row.
        await session.execute(
            text(_INSERT_USER),
            {"uid": str(user_id), "email": f"infra41-{uuid4().hex}@test.local"},
        )

        # Seed two clients with case-insensitive duplicate emails (alive rows).
        # Different phones (clients.phone partial UNIQUE on deleted_at IS NULL).
        nonce = uuid4().hex[:8]
        row_a = await session.execute(
            text(_INSERT_CLIENT_ALIVE),
            {
                "uid": str(user_id),
                "phone": f"+7000{nonce}A",
                "email": f"Foo+{nonce}@Example.com",
            },
        )
        seeded_client_ids.append(str(row_a.scalar_one()))

        row_b = await session.execute(
            text(_INSERT_CLIENT_ALIVE),
            {
                "uid": str(user_id),
                "phone": f"+7000{nonce}B",
                "email": f"foo+{nonce}@example.com",
            },
        )
        seeded_client_ids.append(str(row_b.scalar_one()))
        await session.commit()

        # Upgrade head MUST fail with RuntimeError naming the offender.
        result = _run_alembic("upgrade", "head")
        assert result.returncode != 0, (
            f"expected upgrade to fail on case-insensitive duplicate; got exit 0:\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )
        combined = result.stdout + result.stderr
        assert "RuntimeError" in combined or "cannot apply 0033" in combined, (
            f"expected RuntimeError marker in output:\nstdout:\n{result.stdout}\n"
            f"stderr:\n{result.stderr}"
        )
        # The offender's lower-cased email must appear in the error.
        assert f"foo+{nonce}@example.com" in combined.lower(), (
            f"expected offending lower(email) in error output:\nstdout:\n{result.stdout}\n"
            f"stderr:\n{result.stderr}"
        )

        # Index must NOT exist after the failed upgrade.
        rows = (
            await session.execute(
                text(
                    "SELECT 1 FROM pg_indexes "
                    "WHERE schemaname = 'public' AND indexname = :name"
                ),
                {"name": _INDEX_NAME},
            )
        ).fetchall()
        assert len(rows) == 0, (
            f"index {_INDEX_NAME} must NOT exist after aborted upgrade"
        )

    finally:
        # Clean up seeded rows + restore head for downstream tests.
        await session.execute(
            text("DELETE FROM clients WHERE created_by_user_id = :uid"),
            {"uid": str(user_id)},
        )
        await session.execute(
            text("DELETE FROM users WHERE id = :uid"), {"uid": str(user_id)}
        )
        await session.commit()
        _assert_alembic_ok(
            _run_alembic("upgrade", "head"), "upgrade head (post-test restore)"
        )


async def test_0033_soft_deleted_duplicate_allowed(
    direct_engine_session: AsyncSession,
) -> None:
    """Soft-deleted duplicate (deleted_at IS NOT NULL) is excluded by predicate.

    Seeds two clients with the same case-insensitive email: one alive, one
    soft-deleted. The pre-flight ``WHERE deleted_at IS NULL`` excludes the
    soft-deleted row, so only ONE live row remains for the GROUP BY HAVING
    > 1 check, and the upgrade succeeds.
    """
    session = direct_engine_session
    user_id = uuid4()

    # Start at head, downgrade to 0032 for seeding.
    _assert_alembic_ok(_run_alembic("upgrade", "head"), "upgrade head (pre-seed)")
    _assert_alembic_ok(_run_alembic("downgrade", _REV_PREV), f"downgrade {_REV_PREV}")

    try:
        await session.execute(
            text(_INSERT_USER),
            {"uid": str(user_id), "email": f"infra41-sd-{uuid4().hex}@test.local"},
        )

        nonce = uuid4().hex[:8]
        # Soft-deleted client with email Foo@Example.com (excluded by predicate).
        await session.execute(
            text(_INSERT_CLIENT_SOFT_DELETED),
            {
                "uid": str(user_id),
                "phone": f"+7001{nonce}A",
                "email": f"Foo+{nonce}@Example.com",
            },
        )
        # Live client with email foo@example.com (only live duplicate — no collision).
        await session.execute(
            text(_INSERT_CLIENT_ALIVE),
            {
                "uid": str(user_id),
                "phone": f"+7001{nonce}B",
                "email": f"foo+{nonce}@example.com",
            },
        )
        await session.commit()

        # Upgrade head should succeed.
        result = _run_alembic("upgrade", "head")
        _assert_alembic_ok(result, "upgrade head (soft-deleted dup allowed)")

        # Index now exists.
        rows = (
            await session.execute(
                text(
                    "SELECT 1 FROM pg_indexes "
                    "WHERE schemaname = 'public' AND indexname = :name"
                ),
                {"name": _INDEX_NAME},
            )
        ).fetchall()
        assert len(rows) == 1

    finally:
        await session.execute(
            text("DELETE FROM clients WHERE created_by_user_id = :uid"),
            {"uid": str(user_id)},
        )
        await session.execute(
            text("DELETE FROM users WHERE id = :uid"), {"uid": str(user_id)}
        )
        await session.commit()
        _assert_alembic_ok(
            _run_alembic("upgrade", "head"), "upgrade head (post-test restore)"
        )


async def test_0033_round_trip_drops_index_but_keeps_column(
    direct_engine_session: AsyncSession,
) -> None:
    """Downgrade drops ix_clients_email_lower_unique; clients.email column untouched."""
    session = direct_engine_session

    # Ensure we're at head and the index exists.
    _assert_alembic_ok(_run_alembic("upgrade", "head"), "upgrade head (pre round-trip)")
    rows_before = (
        await session.execute(
            text(
                "SELECT 1 FROM pg_indexes "
                "WHERE schemaname = 'public' AND indexname = :name"
            ),
            {"name": _INDEX_NAME},
        )
    ).fetchall()
    assert len(rows_before) == 1, "index must exist at head before round-trip"

    # Downgrade to 0032 — drops only the index.
    _assert_alembic_ok(
        _run_alembic("downgrade", _REV_PREV), f"downgrade {_REV_PREV} (round-trip)"
    )

    try:
        # Index gone.
        rows_after = (
            await session.execute(
                text(
                    "SELECT 1 FROM pg_indexes "
                    "WHERE schemaname = 'public' AND indexname = :name"
                ),
                {"name": _INDEX_NAME},
            )
        ).fetchall()
        assert len(rows_after) == 0, f"index {_INDEX_NAME} must be gone after downgrade"

        # Column clients.email still present + unchanged (data_type='text', is_nullable='YES').
        col = (
            await session.execute(
                text(
                    "SELECT data_type, is_nullable FROM information_schema.columns"
                    " WHERE table_schema = 'public' AND table_name = 'clients'"
                    " AND column_name = 'email'"
                )
            )
        ).fetchall()
        assert len(col) == 1, "clients.email column must still exist after downgrade"
        assert col[0].data_type == "text", (
            f"clients.email data_type must remain 'text'; got {col[0].data_type!r}"
        )
        assert col[0].is_nullable == "YES", (
            f"clients.email is_nullable must remain 'YES'; got {col[0].is_nullable!r}"
        )

    finally:
        # Restore head for downstream tests.
        _assert_alembic_ok(
            _run_alembic("upgrade", "head"), "upgrade head (post round-trip restore)"
        )
