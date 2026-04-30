"""Top-level API router. Includes v1 at empty prefix in Phase A.

The empty prefix means /healthz resolves at the root URL, satisfying ROADMAP
success criterion #2 and matching Kubernetes liveness probe conventions.
When the first business module lands (Phase B+), the prefix flips to /api/v1
and /healthz must be reconciled (move it or keep it at root for k8s).
"""

from fastapi import APIRouter

from app.api.v1.router import v1

api = APIRouter()
# TODO Phase B+: add /api/v1 prefix; reconcile /healthz path (keep at root for k8s OR move)
api.include_router(v1)
