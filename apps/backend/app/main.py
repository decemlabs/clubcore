"""Application factory (Phase 5 — composition root for auth wiring).

Run with `uvicorn app.main:create_app --factory`. Each call creates a fresh
FastAPI instance.

DO NOT add a module-level `app = create_app()` here. That breaks the factory
contract.

Phase 5 additions:
- combined_lifespan chains db_lifespan + redis_lifespan (D-08).
- register_user_loader(load_user_by_id) fills the Phase 4 D-24 slot (D-15).
   app.main is exempt from core-not-depend-on-modules because that contract
   scopes source_modules = app.core, not app.
- Prod startup assertion: cookie_secure MUST be True when environment=='prod'
   (Phase 4 D-25 — fail-fast at startup, not at first login).
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.router import api
from app.core.config import get_settings
from app.core.database import db_lifespan
from app.core.dependencies import register_user_loader
from app.core.exceptions import register_exception_handlers
from app.core.logging import configure_logging
from app.core.middleware import register_middleware
from app.core.redis import redis_lifespan
from app.modules.auth.service import load_user_by_id


@asynccontextmanager
async def combined_lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Chain db_lifespan + redis_lifespan adapters (Phase 5 D-08, refactored Phase 7 D-08).

    The adapters internally open db_lifespan_manager() / redis_lifespan_manager()
    so the bot worker (app/workers/telegram_bot.py) can reuse the managers
    without FastAPI app.state coupling.
    """
    async with db_lifespan(app), redis_lifespan(app):
        yield


def create_app() -> FastAPI:
    """Compose and return a FastAPI application instance.

    Composition order matters:
      1. configure_logging (must precede any structlog calls).
      2. Prod-mode assertion: cookie_secure must be True (Phase 4 D-25).
      3. FastAPI(lifespan=combined_lifespan) registers DB + Redis lifecycles.
      4. register_middleware adds Timing then RequestId (REVERSED add order).
      5. register_exception_handlers attaches AppError → JSONResponse handler.
      6. register_user_loader(load_user_by_id) fills the Phase 4 D-24 slot.
      7. include_router(api) mounts /healthz at root + /api/v1/auth/*.
    """
    settings = get_settings()
    configure_logging(settings)

    if settings.environment == "prod" and not settings.cookie_secure:
        raise RuntimeError(
            "COOKIE_SECURE must be true in prod (Phase 4 D-25). "
            "Set COOKIE_SECURE=true in the environment."
        )

    app = FastAPI(
        title="Sportzal API",
        version="1.1.0",
        lifespan=combined_lifespan,
        docs_url="/docs" if settings.environment == "dev" else None,
        redoc_url=None,
    )
    register_middleware(app)
    register_exception_handlers(app)

    # D-15: composition root fills the Phase 4 loader slot. This is the ONLY
    # place where app.main reaches into app.modules.*. The importlinter
    # contract scopes source_modules=app.core, so app.main is intentionally
    # outside the scope.
    #
    # WR-05 (Phase 9 review): register_user_loader is idempotent by design —
    # see app/core/dependencies.py:54-61. Re-registering replaces the slot,
    # which is intentional so tests can inject a stub loader through
    # create_app(). Calling it on every create_app() (per-test, per-export)
    # is therefore safe; the export script never enters lifespan and tests
    # use the slot to swap in fakes deterministically.
    register_user_loader(load_user_by_id)

    app.include_router(api)
    return app
