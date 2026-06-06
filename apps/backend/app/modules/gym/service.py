"""Gym-info service — orchestration between router and repository (Phase 86 GYM-01/GYM-02).

Read path: get_gym_info raises GymInfoNotFoundError (404) if the seed row is absent.
Write path: update_gym_info upserts the singleton, flushes and commits.

No audit emit on singleton upsert — gym-info is owner-only configuration content,
not a business event. A future audit trail for content CMS edits can be added without
changing the caller contract (additive). This is consistent with the singleton pattern:
there is no meaningful diff to record per-field beyond the PUT payload itself.

D-03 caller-owns-txn: flush + commit live HERE (service layer), not in repository.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import CurrentUser
from app.core.exceptions import NotFoundError
from app.modules.gym import repository
from app.modules.gym.schemas import GymInfoResponse, GymInfoUpdateRequest


class GymInfoNotFoundError(NotFoundError):
    """Raised when get_singleton returns None (seed migration not yet run).

    HTTP 404. Code 'gym_info_not_found' surfaces to the client so the PWA
    can show an appropriate placeholder rather than a generic error.
    """

    code = "gym_info_not_found"
    status_code = 404


async def get_gym_info(session: AsyncSession) -> GymInfoResponse:
    """Return singleton gym row. 404 via GymInfoNotFoundError if seed missing (GYM-01)."""
    gym = await repository.get_singleton(session)
    if gym is None:
        raise GymInfoNotFoundError("gym_info_not_found")
    return GymInfoResponse.model_validate(gym)


async def update_gym_info(
    session: AsyncSession,
    actor: CurrentUser,
    data: GymInfoUpdateRequest,
) -> GymInfoResponse:
    """Upsert singleton. Caller-owns-txn: flush + commit here (singleton write, D-03).

    actor is accepted for future audit emission or logging — not used in v2.4
    (no audit events for content CMS edits per design rationale above).
    """
    gym = await repository.upsert_singleton(session, data)
    await session.flush()
    await session.commit()
    return GymInfoResponse.model_validate(gym)
