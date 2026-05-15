"""v1 router. Aggregates business module routers under /api/v1 (D-16).

health.router is mounted on the parent api router at root (Phase 2 D-14
Kubernetes contract), NOT under v1. This file therefore only mounts
business modules.
"""

from fastapi import APIRouter

from app.modules.auth.router import router as auth_router
from app.modules.clients.router import router as clients_router
from app.modules.memberships.router import (
    memberships_router,
)
from app.modules.memberships.router import (
    router as plans_router,
)
from app.modules.payments.router import router as payments_router
from app.modules.pt_packages.router import (
    plans_router as pt_package_plans_router,
)
from app.modules.pt_packages.router import (
    pt_packages_router,
)
from app.modules.trainers.router import router as trainers_router
from app.modules.visits.router import router as visits_router

v1 = APIRouter()
v1.include_router(auth_router, prefix="/auth", tags=["auth"])
v1.include_router(clients_router, prefix="/clients", tags=["clients"])
v1.include_router(plans_router, prefix="/membership-plans", tags=["membership-plans"])
v1.include_router(memberships_router, prefix="/memberships", tags=["memberships"])
v1.include_router(payments_router, prefix="/payments", tags=["payments"])
v1.include_router(
    pt_package_plans_router,
    prefix="/pt-package-plans",
    tags=["pt-package-plans"],
)
v1.include_router(pt_packages_router, prefix="/pt-packages", tags=["pt-packages"])
v1.include_router(trainers_router, prefix="/trainers", tags=["trainers"])
v1.include_router(visits_router, prefix="/visits", tags=["visits"])
