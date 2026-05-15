"""Payments module RBAC factories (Phase 32 D-32-25).

``require_payments_view_for_subject`` admits both owner and reception on the
scoped routes ``/api/v1/payments/by-client/{id}`` and
``/api/v1/payments/by-membership/{id}`` (PAY-07 — reception needs visibility
into the client/membership detail pages to serve customers). The global
``GET /api/v1/payments`` route stays owner-only via
``require_permission(VIEW, PAYMENTS)`` because ``(VIEW, PAYMENTS)`` is in
``OWNER_ONLY`` (Plan 30-02 lock).

Anonymous / unauthenticated callers cannot reach this factory — the
dependency graph routes through ``get_current_user`` first, which raises 401.
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


def require_payments_view_for_subject() -> Callable[..., Awaitable[CurrentUser]]:
    """Return a FastAPI dependency that admits owner + reception on scoped routes.

    Owner short-circuits (matches ``can()`` semantics). Reception is admitted
    because reception needs to see a client/membership's payment history to
    serve the customer in person. Any other role is denied with
    ``ForbiddenError("forbidden:view:payments")`` and a co-transactional
    ``rbac_forbidden`` audit row.
    """

    async def _checker(
        request: Request,
        user: Annotated[CurrentUser, Depends(get_current_user)],
        session: Annotated[AsyncSession, Depends(get_db)],
    ) -> CurrentUser:
        if user.role is Role.OWNER or user.role is Role.RECEPTION:
            return user
        await audit.emit(
            session,
            "rbac_forbidden",
            actor_user_id=user.id,
            resource_type="rbac",
            target_resource="payments",
            role=user.role.value,
            action="view",
            path=request.url.path,
            ip=request.client.host if request.client is not None else None,
        )
        raise ForbiddenError("forbidden:view:payments")

    return _checker


__all__ = ("require_payments_view_for_subject",)
