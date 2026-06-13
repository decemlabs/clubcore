"""Loyalty module RBAC factories (Phase 82 ACCR-02).

require_owner_for_loyalty_grant() admits ONLY Role.OWNER on POST /loyalty/grant.
Does NOT extend OWNER_ONLY frozenset or add a new Resource — the parity test
(Phase 6 TEST-06) and CISO-01 byte-parity guard stay green without touching
apps/admin-app/src/shared/session/can.ts.

Reception → 403 ForbiddenError + co-transactional rbac_forbidden audit row.
The ("rbac_forbidden", "rbac") pair is already in LOCKED_AUDIT_EVENTS — no new
pair needed for this emit.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import audit
from app.core.database import get_db
from app.core.dependencies import CurrentUser, get_current_user
from app.core.exceptions import ForbiddenError
from app.core.permissions import Role


def require_owner_for_loyalty_grant() -> Callable[..., Awaitable[CurrentUser]]:
    """Return a FastAPI dependency admitting ONLY Role.OWNER on the grant endpoint.

    Owner short-circuits. Any other role (e.g. reception) is denied with
    ForbiddenError("forbidden:grant:loyalty") and a co-transactional rbac_forbidden
    audit row (target_resource="loyalty", action="grant").

    Does NOT extend OWNER_ONLY frozenset or add a new Resource — Phase-6 parity
    test (TEST-06) and CISO-01 byte-parity guard stay green (no admin-app changes).
    """

    async def _checker(
        request: Request,
        user: Annotated[CurrentUser, Depends(get_current_user)],
        session: Annotated[AsyncSession, Depends(get_db)],
    ) -> CurrentUser:
        if user.role is Role.OWNER:
            return user
        await audit.emit(
            session,
            "rbac_forbidden",
            actor_user_id=user.id,
            resource_type="rbac",
            target_resource="loyalty",
            role=user.role.value,
            action="grant",
            path=request.url.path,
            ip=request.client.host if request.client is not None else None,
        )
        raise ForbiddenError("forbidden:grant:loyalty")

    return _checker


__all__ = ("require_owner_for_loyalty_grant",)
