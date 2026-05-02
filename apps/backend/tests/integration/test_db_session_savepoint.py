"""Smoke test for the SAVEPOINT-based db_session fixture (TEST-01 / D-22).

Asserts that a service-style `session.commit()` inside a test becomes a nested
SAVEPOINT under the outer transaction, and that the outer rollback wipes the
write across test runs. If two consecutive tests insert the same UNIQUE email
without raising IntegrityError, the SAVEPOINT pattern is working.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permissions import Role
from app.core.security import hash_password
from app.modules.auth.models import User


async def _insert_owner(db_session: AsyncSession, email: str) -> User:
    user = User(
        email=email,
        password_hash=await hash_password("hunter22hunter22"),
        role=Role.OWNER,
        full_name="Owner",
    )
    db_session.add(user)
    await db_session.commit()  # service-style commit — should become nested SAVEPOINT
    return user


async def test_savepoint_first_insert(db_session: AsyncSession) -> None:
    """Inserts an owner; relies on the next test to prove rollback happened."""
    await _insert_owner(db_session, "savepoint-smoke@test.local")
    found = await db_session.scalar(
        select(User).where(User.email == "savepoint-smoke@test.local")
    )
    assert found is not None
    assert found.email == "savepoint-smoke@test.local"


async def test_savepoint_second_insert_same_email(db_session: AsyncSession) -> None:
    """Same email as previous test — must succeed, proving the previous commit was rolled back."""
    await _insert_owner(db_session, "savepoint-smoke@test.local")
    found = await db_session.scalar(
        select(User).where(User.email == "savepoint-smoke@test.local")
    )
    assert found is not None
