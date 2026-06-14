"""Gym-info service — orchestration between router and repository (Phase 86 GYM-01/GYM-02).

Read path: get_gym_info raises GymInfoNotFoundError (404) if the seed row is absent.
Write path: update_gym_info upserts the singleton, emits LOCKED audit event, flushes and commits.

Phase 108 CFG-01: gym_card_updated LOCKED audit event is now emitted on update.
The event was pre-registered in Plan 01 per INFRA-15 discipline. The actor argument
(previously unused) is now consumed by the audit emit.

D-03 caller-owns-txn: flush + commit live HERE (service layer), not in repository.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.core import audit
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
    """Upsert singleton. Emits LOCKED audit event. Caller-owns-txn: flush + commit here (D-03).

    Phase 108 CFG-01: gym_card_updated LOCKED audit event emitted before commit per INFRA-15.
    The event was pre-registered in Plan 01; this is the first callsite.
    """
    gym = await repository.upsert_singleton(session, data)
    await audit.emit(
        session,
        "gym_card_updated",
        actor_user_id=actor.id,
        resource_type="gym",
        changed_fields=list(data.model_dump(exclude_unset=True).keys()),
    )
    await session.flush()
    await session.commit()
    return GymInfoResponse.model_validate(gym)
