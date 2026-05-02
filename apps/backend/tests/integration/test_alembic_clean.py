"""Integration test: Phase 4 SC #3 — alembic upgrade head + alembic check produce empty diff (D-29).

Two assertions:
  1. Structural — `Base.metadata.naming_convention == NAMING_CONVENTION` (catches the
     broken-Base case Pitfall B: empty target_metadata + clean DB would also satisfy
     alembic check trivially, which would mask `database.py` regressions).
  2. Functional — `alembic upgrade head` then `alembic check` against compose Postgres
     exits 0 with stdout containing "No new upgrade operations detected."

Skips cleanly if compose Postgres is unreachable (run `docker compose up postgres` first).
Reuses the Phase 3 db_session fixture skip-on-unreachable idiom.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import NAMING_CONVENTION, Base

BACKEND_DIR = Path(__file__).resolve().parent.parent.parent


def test_naming_convention_attached_to_base_metadata() -> None:
    """Pitfall B guard: Base.metadata.naming_convention must equal NAMING_CONVENTION.

    Without this assertion, an empty target_metadata + clean DB would satisfy
    `alembic check` trivially even if database.py had a regression that detached the
    naming convention from Base.
    """
    assert Base.metadata.naming_convention == NAMING_CONVENTION


async def test_alembic_check_clean(db_session: AsyncSession) -> None:
    """SC #3: alembic upgrade head + alembic check empty diff.

    The `db_session` fixture skips this test if compose Postgres is unreachable
    (per Phase 3 D-12 / conftest pattern). The fixture itself is yielded but not used
    directly — its only role here is to gate the test on DB availability.
    """
    # Step 1 — bring the DB up to head (no-op in Phase 4: no migrations exist yet).
    # Intentional blocking subprocess: uv run is not awaitable (ASYNC221); partial path needed (S607).  # noqa: E501
    upgrade = subprocess.run(  # noqa: ASYNC221
        ["uv", "run", "alembic", "upgrade", "head"],  # noqa: S607
        cwd=str(BACKEND_DIR),
        capture_output=True,
        text=True,
        check=False,
    )
    assert upgrade.returncode == 0, (
        f"alembic upgrade head failed:\nstdout:\n{upgrade.stdout}\nstderr:\n{upgrade.stderr}"
    )

    # Step 2 — alembic check (autogenerate-on-clean must produce empty diff).
    check = subprocess.run(  # noqa: ASYNC221
        ["uv", "run", "alembic", "check"],  # noqa: S607
        cwd=str(BACKEND_DIR),
        capture_output=True,
        text=True,
        check=False,
    )
    assert check.returncode == 0, (
        f"alembic check detected drift:\nstdout:\n{check.stdout}\nstderr:\n{check.stderr}"
    )
    assert "No new upgrade operations detected" in check.stdout, (
        f"alembic check stdout did not contain the expected success line:\n{check.stdout}"
    )
