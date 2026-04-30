"""v1 router. Aggregates health and (later) business module routers."""

from fastapi import APIRouter

from app.api.v1 import health

v1 = APIRouter()
v1.include_router(health.router)

# TODO Phase B+: include module routers here, e.g.
# from app.modules.auth.router import router as auth_router
# v1.include_router(auth_router, prefix="/auth", tags=["auth"])
