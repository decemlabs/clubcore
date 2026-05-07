"""FastAPI dependencies: CurrentUser Protocol, loader registration, RBAC gate (D-24).

Architectural responsibility (PROJECT.md + .importlinter):
  `app.core` MUST NOT import from `app.modules.*` — but `get_current_user` lives in core
  and must load a User from `app.modules.auth`. The fix: a Protocol slot in core that the
  composition root (`app.main.create_app`) fills at startup with a concrete loader.

Phase 4 ships the slot + dependency factories. Phase 5 `create_app()` will call
`register_user_loader(app.modules.auth.service.load_user_by_id)` inside the factory
body (`app.main` is exempt from `core-not-depend-on-modules` because that contract has
`source_modules = app.core`, not `app`).

`Depends(require_permission(...))` lands on actual routes in Phase 6 (RBAC-02..05);
Phase 4 ships only the factory.
"""

import secrets
from collections.abc import Awaitable, Callable
from typing import Annotated, Protocol
from uuid import UUID

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import audit
from app.core.database import get_db
from app.core.exceptions import CsrfMismatch, ForbiddenError, InvalidAccessToken
from app.core.permissions import Action, Resource, Role, can
from app.core.security import decode_access_token


class CurrentUser(Protocol):
    """Structural type for the authenticated user (D-24).

    Phase 5's `app.modules.auth.models.User` will satisfy this protocol because it
    declares `id: Mapped[UUID]` and `role: Mapped[Role]`. Nothing in `app.core` imports
    the SA model — the Protocol is the boundary.
    """

    id: UUID
    role: Role


UserLoader = Callable[[AsyncSession, UUID], Awaitable[CurrentUser | None]]
"""Async callable: (session, user_id) -> CurrentUser | None.

Returns None if no user with that id exists (or is soft-deleted) so the dependency can
surface `InvalidAccessToken('user_not_found')`.
"""

_user_loader: UserLoader | None = None


def register_user_loader(loader: UserLoader) -> None:
    """Composition-root setter — called once by `app.main.create_app` in Phase 5.

    Idempotent: re-registering replaces the slot (useful in tests that want to inject a
    stub loader). Phase 4 has no caller; Phase 5 wires `load_user_by_id`.
    """
    global _user_loader
    _user_loader = loader


async def get_current_user(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> CurrentUser:
    """Resolve the authenticated user from the `sz_access` cookie.

    Failure modes (all → 401 InvalidAccessToken with a specific message):
      - missing cookie → 'missing_access_cookie'
      - decode failure (delegated to decode_access_token) → 'token_expired' or 'invalid_token'
      - composition root forgot to register a loader → 'user_loader_not_registered'
      - loader returned None (user deleted / unknown id) → 'user_not_found'
    """
    token = request.cookies.get("sz_access")
    if token is None:
        raise InvalidAccessToken("missing_access_cookie")

    # decode_access_token raises InvalidAccessToken on its own failure paths
    # (token_expired / invalid_token / wrong_token_type / unknown_role) — we don't
    # need to wrap here.
    claims = decode_access_token(token)

    if _user_loader is None:
        # Defensive: composition root MUST register before the request flow starts.
        # This branch surfaces a misconfiguration (Phase 5 forgot to call register_user_loader)
        # as a 401 instead of a 500 — same shape the client already handles.
        raise InvalidAccessToken("user_loader_not_registered")

    user = await _user_loader(session, UUID(claims.sub))
    if user is None:
        raise InvalidAccessToken("user_not_found")
    return user


def require_permission(
    action: Action,
    resource: Resource,
) -> Callable[..., Awaitable[CurrentUser]]:
    """Return a FastAPI dependency that resolves CurrentUser AND enforces RBAC.

    Phase 6 wires this onto every business route signature (RBAC-03):

        @router.delete("/clients/{id}", response_model=ResponseEnvelope[None])
        async def delete_client(
            user: Annotated[
                CurrentUser, Depends(require_permission(Action.DELETE, Resource.CLIENTS))
            ],
            ...
        ): ...

    Emits structlog `event=rbac_forbidden` with the locked key set
    (`user_id, role, action, resource, path, ip`) BEFORE raising `ForbiddenError`,
    so the Phase 8 audit_log DB writer (INFRA-04) latches on without renaming (D-23).

    The `request: Request` parameter is auto-injected by FastAPI; route-level callers
    declare only `Depends(require_permission(Action.X, Resource.Y))` — the dependency
    graph fills `request` and `user` automatically.

    Raises:
      ForbiddenError (403, code='forbidden') if `can(user.role, action, resource)` is False.
      (Whatever get_current_user raises — 401 paths — propagates upward unchanged.)
    """

    async def _checker(
        request: Request,
        user: Annotated[CurrentUser, Depends(get_current_user)],
        session: Annotated[AsyncSession, Depends(get_db)],
    ) -> CurrentUser:
        if not can(user.role, action, resource):
            # Phase 15 INFRA-11 / D-11: `resource_type` MUST be a literal at every
            # callsite (the AST literal-only gate in tests/unit/test_audit_taxonomy.py
            # cannot prove staticness if it is `resource.value`). The target
            # resource moves into the structlog/payload as `target_resource`.
            await audit.emit(
                session,
                "rbac_forbidden",
                actor_user_id=user.id,
                resource_type="rbac",
                target_resource=resource.value,
                role=user.role.value,
                action=action.value,
                path=request.url.path,
                ip=request.client.host if request.client is not None else None,
            )
            raise ForbiddenError(f"forbidden:{action.value}:{resource.value}")
        return user

    return _checker


def require_authenticated() -> Callable[..., Awaitable[CurrentUser]]:
    """Return a FastAPI dependency that resolves CurrentUser without a role gate.

    Sibling of `require_permission(...)` (D-01). Used by routes that need an
    authenticated caller but no RBAC check (`/auth/me`, `/auth/logout`,
    `/auth/logout-all`). The introspection test (TEST-07, Plan 06-05)
    identifies this factory via `__qualname__.startswith('require_authenticated.')`,
    so the closure name MUST be `_checker` and the function MUST be a single
    wrapping layer over `get_current_user` (do NOT nest inside another factory).
    """

    async def _checker(
        user: Annotated[CurrentUser, Depends(get_current_user)],
    ) -> CurrentUser:
        return user

    return _checker


_SAFE_METHODS: frozenset[str] = frozenset({"GET", "HEAD", "OPTIONS", "TRACE"})


async def verify_csrf(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    """Double-submit CSRF check (D-07). Short-circuits on safe methods (D-06).

    Validation:
      1. If method is in {GET, HEAD, OPTIONS, TRACE}, return None (read-only —
         no CSRF check; T-06-07 accept).
      2. Otherwise, read `sportzal_csrf` cookie + `X-CSRF-Token` header.
      3. If either is missing OR they don't match (`secrets.compare_digest`,
         constant-time per T-06-05 mitigation), emit `event=csrf_mismatch` and
         raise `CsrfMismatch`.

    `verify_csrf` runs BEFORE `get_current_user` per FastAPI's `dependencies=[...]`
    execution order, so `user_id` is best-effort `None` (D-23). Emit kwargs include
    only `has_cookie` / `has_header` booleans — never the raw token strings
    (T-06-09 mitigation).

    Raises:
      CsrfMismatch (403, code='csrf_mismatch') with locked envelope per D-21.
    """
    if request.method in _SAFE_METHODS:
        return
    cookie_val = request.cookies.get("sportzal_csrf")
    header_val = request.headers.get("x-csrf-token")
    if (
        cookie_val is None
        or header_val is None
        or not secrets.compare_digest(cookie_val, header_val)
    ):
        await audit.emit(
            session,
            "csrf_mismatch",
            actor_user_id=None,
            resource_type="csrf",
            path=request.url.path,
            method=request.method,
            ip=request.client.host if request.client is not None else None,
            has_cookie=cookie_val is not None,
            has_header=header_val is not None,
        )
        raise CsrfMismatch("csrf_mismatch")
