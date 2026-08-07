"""Referral repository — single point of ORM access for the referral domain (D-31-08).

Transaction control (D-03): NO session.commit() and NO session.flush() here.
Caller (service.py) owns the transactional moment.

All five helpers follow the gym/repository.py pattern: thin select wrappers that
return the ORM row or None.  No business logic, no audit calls.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.referrals.models import ReferralCapture, ReferralCode, ReferralConfig
from app.modules.referrals.schemas import ReferralConfigUpdateRequest


async def get_code_by_client_id(
    session: AsyncSession,
    client_id: UUID,
) -> ReferralCode | None:
    """Return the referral code row for *client_id*, or None if not yet minted."""
    stmt = select(ReferralCode).where(ReferralCode.client_id == client_id)
    result: ReferralCode | None = await session.scalar(stmt)
    return result


async def get_code_by_value(
    session: AsyncSession,
    code_str: str,
) -> ReferralCode | None:
    """Return the referral code row whose code matches *code_str* (case-insensitive).

    Codes are stored upper-case; callers should upper-case before calling, but
    this function also normalises for safety.
    """
    stmt = select(ReferralCode).where(ReferralCode.code == code_str.upper())
    result: ReferralCode | None = await session.scalar(stmt)
    return result


async def get_capture_by_referee(
    session: AsyncSession,
    referee_client_id: UUID,
) -> ReferralCapture | None:
    """Return the referral capture row for *referee_client_id*, or None.

    Used as the idempotency gate in capture_referral: if a row already exists
    the capture call is a no-op (first binding wins).
    """
    stmt = select(ReferralCapture).where(ReferralCapture.referee_client_id == referee_client_id)
    result: ReferralCapture | None = await session.scalar(stmt)
    return result


async def get_config(session: AsyncSession) -> ReferralConfig | None:
    """Return the singleton referral-config row, or None if the seed has not run."""
    stmt = select(ReferralConfig).limit(1)
    result: ReferralConfig | None = await session.scalar(stmt)
    return result


async def upsert_config(
    session: AsyncSession,
    data: ReferralConfigUpdateRequest,
) -> ReferralConfig:
    """Update the singleton referral-config row in-place. Caller owns flush+commit (D-03).

    Applies exclude_unset model_dump so partial payloads only touch supplied fields.
    Defensive guard: if the seed row is somehow missing, constructs a new ReferralConfig
    (should not happen after migration 0068 seed, but prevents a hard 500).
    """
    config = await get_config(session)
    if config is None:
        # Defensive path — should not occur after migration 0068 seed.
        config = ReferralConfig(referrer_bonus_kopecks=0, referee_welcome_kopecks=0)
        session.add(config)
    updates = data.model_dump(exclude_unset=True)
    for key, value in updates.items():
        setattr(config, key, value)
    return config
