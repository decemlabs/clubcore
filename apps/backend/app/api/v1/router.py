"""v1 router. Aggregates business module routers under /api/v1 (D-16).

health.router is mounted on the parent api router at root (Phase 2 D-14
Kubernetes contract), NOT under v1. This file therefore only mounts
business modules.
"""

from fastapi import APIRouter

from app.modules.auth.router import router as auth_router
from app.modules.clients.router import router as clients_router
from app.modules.memberships.router import router as plans_router

v1 = APIRouter()
v1.include_router(auth_router, prefix="/auth", tags=["auth"])
v1.include_router(clients_router, prefix="/clients", tags=["clients"])
v1.include_router(plans_router, prefix="/membership-plans", tags=["membership-plans"])
