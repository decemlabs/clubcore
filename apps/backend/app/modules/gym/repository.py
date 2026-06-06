"""Gym-info repository — single point of access to the `GymInfo` ORM (GYM-01, D-31-08).

This is the ONLY module that imports the `GymInfo` ORM model. Service layer
calls these module-level async helpers and never executes `select(GymInfo)` directly.

Transaction control (D-03): NO session.commit() and NO session.flush() here.
Caller (service.py) owns the transactional moment.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.gym.models import GymInfo
from app.modules.gym.schemas import GymInfoUpdateRequest


async def get_singleton(session: AsyncSession) -> GymInfo | None:
    """Return the single gym row, or None if seed not yet run."""
    stmt = select(GymInfo).limit(1)
    result: GymInfo | None = await session.scalar(stmt)
    return result


async def upsert_singleton(session: AsyncSession, data: GymInfoUpdateRequest) -> GymInfo:
    """Update the singleton row in-place. Caller owns flush+commit (D-03).

    Applies exclude_unset model_dump so partial payloads only touch supplied fields.
    Defensive guard: if the seed row is somehow missing, constructs a new GymInfo
    (should not happen post-migration, but prevents a hard 500 on misconfigured envs).
    """
    gym = await get_singleton(session)
    if gym is None:
        # Defensive path — should not occur after migration 0059 seed.
        gym = GymInfo(name="", address="")
        session.add(gym)
    updates = data.model_dump(exclude_unset=True)
    for key, value in updates.items():
        setattr(gym, key, value)
    return gym
