"""Test-only fixture router built dynamically from OWNER_ONLY (Phase 6 D-10).

NOT mounted by app.main.create_app(). Mounted only by the test app fixture in
tests/integration/rbac/conftest.py. The /_t prefix is deliberately ugly — it
signals "not real" at a glance in any route enumeration, log line, or stack
trace (per CONTEXT.md specifics — "deliberately ugly").

Each endpoint is a synthetic stub that declares
`Depends(require_permission(action, resource))`. Tests parametrize over
OWNER_ONLY and exercise the full RBAC chain (Argon2 → JWT → loader →
require_permission → can() → ForbiddenError) on REAL seeded users.
"""

from fastapi import APIRouter, Depends

from app.core.dependencies import require_permission
from app.core.permissions import OWNER_ONLY, Action, Resource

router = APIRouter(prefix="/_t", tags=["_test_only"])


def _make_endpoint(a: Action, r: Resource) -> None:
    """Closure factory — binds (a, r) per iteration to defeat Python late-binding.

    Without this indirection, every loop iteration would close over the same
    cell and all endpoints would resolve to the LAST (action, resource) pair.
    """

    @router.get(
        f"/{a.value}/{r.value}",
        dependencies=[Depends(require_permission(a, r))],
    )
    async def _stub() -> dict[str, bool]:
        return {"ok": True}

    _stub.__name__ = f"stub_{a.value}_{r.value}"


# sorted(OWNER_ONLY) works because Action/Resource are StrEnum (StrEnum
# comparison falls back to underlying string). Verified by
# tests/unit/test_permissions.py:62-63 which uses the same sorted(...) pattern.
for _action, _resource in sorted(OWNER_ONLY):
    _make_endpoint(_action, _resource)
