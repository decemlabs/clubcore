"""Top-level API router (Phase 5 — D-16).

/healthz stays at the root URL (Kubernetes liveness convention from Phase 2 D-14).
All v1 endpoints live under /api/v1/. The first endpoint to use this prefix
is /api/v1/auth/* (Phase 5 — five auth routes). Future business modules mount
onto v1 via app/api/v1/router.py.
"""

from fastapi import APIRouter

from app.api.v1 import health
from app.api.v1.router import v1

api = APIRouter()
# /healthz — root, no prefix (k8s liveness contract from Phase 2 D-14).
api.include_router(health.router)
# All v1 endpoints under /api/v1.
api.include_router(v1, prefix="/api/v1")
