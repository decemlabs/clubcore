"""Phase 999.5 Plan 02 — client-portal service + repository test fixtures.

Provides:
- ``make_client`` — DB-direct factory (with email or without).
- ``make_user`` — DB-direct factory for creating an owner user.
- ``make_online_payment`` — DB-direct factory for an OnlinePayment row in a given status.

All factories commit via the SAVEPOINT-mode session so the outer per-test
transaction rolls back on teardown (D-22 / TEST-01 pattern).
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from uuid import UUID

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.models import User
from app.modules.clients.models import Client


@pytest_asyncio.fixture
async def make_user(
    db_session: AsyncSession,
) -> Callable[..., Awaitable[User]]:
    """Insert a User row directly — owner role by default."""
    from app.core.permissions import Role
    from app.core.security import hash_password

    _counter = {"i": 0}

    async def _make(*, role: str = "owner") -> User:
        _counter["i"] += 1
        user = User(
            email=f"user-cp-{_counter['i']}@example.com",
            password_hash=await hash_password("test_password"),
            role=Role(role),
            full_name=f"Test User {_counter['i']}",
        )
        db_session.add(user)
        await db_session.commit()
        await db_session.refresh(user)
        return user

    return _make


@pytest_asyncio.fixture
async def make_client(
    db_session: AsyncSession,
    make_user: Callable[..., Awaitable[User]],
) -> Callable[..., Awaitable[Client]]:
    """Insert a Client row with optional email, goal, height_cm, weight_kg fields."""

    _counter = {"i": 0}

    async def _make(
        *,
        last_name: str = "Тестов",
        first_name: str = "Тест",
        phone: str | None = None,
        email: str | None = None,
        goal: str | None = None,
        height_cm: int | None = None,
        weight_kg: int | None = None,
        created_by_user_id: UUID | None = None,
    ) -> Client:
        _counter["i"] += 1
        if created_by_user_id is None:
            owner = await make_user(role="owner")
            created_by_user_id = owner.id
        resolved_phone = phone or f"+799912370{_counter['i']:02d}"
        client = Client(
            last_name=last_name,
            first_name=first_name,
            phone=resolved_phone,
            email=email,
            goal=goal,
            height_cm=height_cm,
            weight_kg=weight_kg,
            created_by_user_id=created_by_user_id,
        )
        db_session.add(client)
        await db_session.commit()
        await db_session.refresh(client)
        return client

    return _make
