"""Phase 43 CR-02 regression — owner deactivate path runs cleanly on Postgres.

Pre-fix: count_active_owners_excluding compiled to:
    SELECT count(*) FROM users WHERE ... FOR UPDATE
which Postgres rejects with ProgrammingError ("FOR UPDATE is not allowed
with aggregate functions"). Every owner-target deactivate raised at runtime.

This test:
  1. Confirms the fixture is the asyncpg dialect (NOT a SQLite shim — SQLite
     silently allows the illegal query, defeating the regression catch).
  2. Seeds a second active owner.
  3. Deactivates the second owner via the HTTP path.
  4. Asserts 204 + DB state.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import FastAPI

from app.core.models import User
from app.core.permissions import Role

pytestmark = pytest.mark.asyncio


def _csrf(client: AsyncClient) -> dict[str, str]:
    return {"X-CSRF-Token": client.cookies.get("sportzal_csrf") or ""}


async def test_deactivate_owner_against_real_postgres(
    authed_client_owner: AsyncClient,
    db_session: AsyncSession,
    app: FastAPI,
) -> None:
    """CR-02 regression — deactivating an owner via HTTP returns 204 on real Postgres.

    Pre-fix: count_active_owners_excluding used SELECT count(*) FOR UPDATE.
    Postgres rejected this with ProgrammingError. Post-fix: SELECT user.id
    FOR UPDATE + len(result.all()) — legal and lock-serialised.

    If this test returns 500 after the fix is reverted, the ProgrammingError
    is back. If the test is somehow running against a SQLite shim, it skips
    (SQLite silently accepts the illegal query and defeats the regression catch).
    """
    # Sanity — this test only proves anything against asyncpg/Postgres.
    dialect_name = app.state.engine.dialect.name
    if dialect_name != "postgresql":
        pytest.skip(
            f"CR-02 regression requires Postgres (got '{dialect_name}'); "
            "SQLite silently accepts aggregate FOR UPDATE and defeats the catch."
        )

    # Seed a second active owner directly in the SAVEPOINT-rolled session.
    second_owner = User(
        email="second-owner-cr02@example.com",
        email_verified=True,
        password_hash="$argon2id$placeholder",
        role=Role.OWNER,
        full_name="Second Owner",
        is_active=True,
        status="active",
    )
    db_session.add(second_owner)
    await db_session.commit()
    await db_session.refresh(second_owner)
    second_owner_id = second_owner.id

    # Act — deactivate the second owner via the HTTP path.
    # Pre-fix: 500 (ProgrammingError). Post-fix: 204.
    response = await authed_client_owner.patch(
        f"/api/v1/users/{second_owner_id}/deactivate",
        headers=_csrf(authed_client_owner),
    )
    assert response.status_code == 204, (
        f"CR-02 regression — owner deactivate returned {response.status_code} "
        f"(body: {response.text!r}). "
        f"Expected 204. If 500, check the SQL emitted by "
        f"count_active_owners_excluding — it must NOT use FOR UPDATE on an "
        f"aggregate query (Postgres rejects this combination)."
    )

    # Assert DB state — the target row reflects the deactivation.
    await db_session.refresh(second_owner)
    assert second_owner.is_active is False, "Target owner should be inactive after deactivate"
    assert second_owner.deactivated_at is not None, "deactivated_at must be set"
    assert second_owner.deactivated_by_user_id is not None, "deactivated_by_user_id must be set"
