"""Application factory (BE-02).

Run with `uvicorn app.main:create_app --factory` so each invocation creates
a fresh FastAPI instance — required for test isolation (Phase 3 conftest creates
a new app per test) and for the lifespan-managed engine pattern (D-06/D-08).

DO NOT add a module-level `app = create_app()` here. That would break the factory
contract and reintroduce module-level engine singletons.
"""

from fastapi import FastAPI

from app.api.router import api
from app.core.config import get_settings
from app.core.database import db_lifespan
from app.core.exceptions import register_exception_handlers
from app.core.logging import configure_logging
from app.core.middleware import register_middleware


def create_app() -> FastAPI:
    """Compose and return a FastAPI application instance.

    Composition order matters:
      1. configure_logging — must run before any structlog calls.
      2. FastAPI(lifespan=db_lifespan) — registers engine startup/shutdown.
      3. register_middleware — adds Timing then RequestId (REVERSED add order;
         see app/core/middleware.py docstring).
      4. register_exception_handlers — attaches AppError → JSONResponse handler.
      5. include_router(api) — mounts /healthz (Phase A's only real endpoint).
    """
    settings = get_settings()
    configure_logging(settings)

    app = FastAPI(
        title="Sportzal API",
        lifespan=db_lifespan,
        docs_url="/docs" if settings.environment == "dev" else None,
        redoc_url=None,
    )
    register_middleware(app)
    register_exception_handlers(app)
    app.include_router(api)
    return app
