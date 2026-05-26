"""Phase 51 D-51-25 + D-51-26 — Route introspection invariants for the 2 new POST /refund routes.

Verifies:
1. Both POST /refund routes are discoverable in the OpenAPI spec.
2. Both routes declare require_permission(REFUND, MEMBERSHIPS/PT_PACKAGES) in their deps tree.
3. Both routes declare verify_csrf in their deps tree.
4. Neither new route appears in EXCLUDED_PATHS (D-51-26 — they MUST be gated).
5. /api/v1/_internal/yookassa/webhook remains in EXCLUDED_PATHS (D-51-25 — unchanged).
6. (Action.REFUND, Resource.MEMBERSHIPS) and (Action.REFUND, Resource.PT_PACKAGES) are
   registered as valid RBAC pairs in app.core.permissions (D-51-10).

This file is a SIBLING of tests/integration/test_route_introspection.py.
The existing project-wide gate test is NOT modified — Phase 51 invariants live here.
"""

from __future__ import annotations

from typing import Any

from fastapi.routing import APIRoute

from app.core.permissions import Action, Resource
from app.main import create_app

# New Phase 51 POST /refund routes that MUST be gated.
_NEW_REFUND_ROUTE_MEMBERSHIP = "/api/v1/online-payments/memberships/{membership_id}/refund"
_NEW_REFUND_ROUTE_PT_PACKAGE = "/api/v1/online-payments/pt-packages/{pt_package_id}/refund"

# Gate qualifier prefixes — mirrored from test_route_introspection.py.
_GATE_PREFIXES: tuple[str, ...] = (
    "require_permission.",
    "require_authenticated.",
    "require_payments_view_for_subject.",
)


def _walk_dependant(dep: Any, seen: set[int] | None = None) -> list[str]:
    """Collect __qualname__ strings of all callables in the dependant tree."""
    if seen is None:
        seen = set()
    if id(dep) in seen:
        return []
    seen.add(id(dep))
    result: list[str] = []
    call = getattr(dep, "call", None)
    if call is not None:
        qn = getattr(call, "__qualname__", "")
        if qn:
            result.append(qn)
    for sub in getattr(dep, "dependencies", []):
        result.extend(_walk_dependant(sub, seen))
    return result


def _get_route(path: str) -> APIRoute:
    """Return the APIRoute for the given path or raise AssertionError."""
    app = create_app()
    for route in app.routes:
        if isinstance(route, APIRoute) and route.path == path:
            return route
    raise AssertionError(
        f"Route {path!r} not found in the app. "
        "Verify it is mounted with the correct prefix in app/api/v1/router.py."
    )


# ---------------------------------------------------------------------------
# 1. Routes present in OpenAPI spec.
# ---------------------------------------------------------------------------


def test_phase51_refund_routes_present_in_app_routes() -> None:
    """Both new POST /refund routes are discoverable in the FastAPI route registry.

    Validates REFUND-01 (D-51-08) route mounting: both endpoints are present
    with method=POST in create_app()'s route tree.
    """
    app = create_app()
    found: set[str] = set()
    for route in app.routes:
        if isinstance(route, APIRoute) and "POST" in route.methods:
            found.add(route.path)

    assert _NEW_REFUND_ROUTE_MEMBERSHIP in found, (
        f"Missing POST route {_NEW_REFUND_ROUTE_MEMBERSHIP!r}. "
        f"Present POST routes: {sorted(p for p in found if 'refund' in p)}"
    )
    assert _NEW_REFUND_ROUTE_PT_PACKAGE in found, (
        f"Missing POST route {_NEW_REFUND_ROUTE_PT_PACKAGE!r}. "
        f"Present POST routes: {sorted(p for p in found if 'refund' in p)}"
    )


# ---------------------------------------------------------------------------
# 2. Routes declare require_permission dependency.
# ---------------------------------------------------------------------------


def test_phase51_refund_routes_have_require_permission_dependency() -> None:
    """Both routes carry require_permission in their dependant chain (D-51-08 RBAC-04).

    Verifies the architectural pattern: auth → require_permission(REFUND, *)
    → verify_csrf.
    """
    membership_route = _get_route(_NEW_REFUND_ROUTE_MEMBERSHIP)
    pt_package_route = _get_route(_NEW_REFUND_ROUTE_PT_PACKAGE)

    membership_qualnames = _walk_dependant(membership_route.dependant)
    pt_package_qualnames = _walk_dependant(pt_package_route.dependant)

    assert any(qn.startswith("require_permission.") for qn in membership_qualnames), (
        f"Membership refund route missing require_permission gate. "
        f"Found qualnames: {[q for q in membership_qualnames if 'require' in q]}"
    )
    assert any(qn.startswith("require_permission.") for qn in pt_package_qualnames), (
        f"PT-package refund route missing require_permission gate. "
        f"Found qualnames: {[q for q in pt_package_qualnames if 'require' in q]}"
    )


# ---------------------------------------------------------------------------
# 3. Routes declare verify_csrf dependency.
# ---------------------------------------------------------------------------


def test_phase51_refund_routes_have_verify_csrf_dependency() -> None:
    """Both routes carry verify_csrf in their dependant chain (D-51-08 / Phase 6 D-25).

    CSRF protection is REQUIRED on all mutating owner-only endpoints.
    """
    membership_route = _get_route(_NEW_REFUND_ROUTE_MEMBERSHIP)
    pt_package_route = _get_route(_NEW_REFUND_ROUTE_PT_PACKAGE)

    membership_qualnames = _walk_dependant(membership_route.dependant)
    pt_package_qualnames = _walk_dependant(pt_package_route.dependant)

    assert any("verify_csrf" in qn for qn in membership_qualnames), (
        f"Membership refund route missing verify_csrf dependency. "
        f"Found qualnames: {[q for q in membership_qualnames if 'csrf' in q.lower()]}"
    )
    assert any("verify_csrf" in qn for qn in pt_package_qualnames), (
        f"PT-package refund route missing verify_csrf dependency. "
        f"Found qualnames: {[q for q in pt_package_qualnames if 'csrf' in q.lower()]}"
    )


# ---------------------------------------------------------------------------
# 4. New routes NOT in EXCLUDED_PATHS (D-51-26).
# ---------------------------------------------------------------------------


def test_phase51_refund_routes_not_in_excluded_paths() -> None:
    """Neither new POST /refund route appears in test_route_introspection.EXCLUDED_PATHS.

    D-51-26: the refund routes are GATED (require_permission + verify_csrf);
    they must NOT be in the exclusion set. Adding them there would silently
    exempt them from the architectural gate check.
    """
    from tests.integration.test_route_introspection import EXCLUDED_PATHS

    assert _NEW_REFUND_ROUTE_MEMBERSHIP not in EXCLUDED_PATHS, (
        f"{_NEW_REFUND_ROUTE_MEMBERSHIP!r} is in EXCLUDED_PATHS — "
        "gated routes must not be excluded from the gate introspection check."
    )
    assert _NEW_REFUND_ROUTE_PT_PACKAGE not in EXCLUDED_PATHS, (
        f"{_NEW_REFUND_ROUTE_PT_PACKAGE!r} is in EXCLUDED_PATHS — "
        "gated routes must not be excluded from the gate introspection check."
    )


# ---------------------------------------------------------------------------
# 5. Webhook URL unchanged in EXCLUDED_PATHS (D-51-25).
# ---------------------------------------------------------------------------


def test_phase51_internal_webhook_url_unchanged_in_excluded_paths() -> None:
    """Phase 51 adds refund + receipt event branches to the SAME webhook URL.

    No new webhook URLs were added (D-51-25). Verify the canonical URL is
    still in EXCLUDED_PATHS (IP-allowlist auth, anonymous-by-design).
    """
    from tests.integration.test_route_introspection import EXCLUDED_PATHS

    assert "/api/v1/_internal/yookassa/webhook" in EXCLUDED_PATHS, (
        "Webhook URL was removed from EXCLUDED_PATHS — this is a breaking change "
        "that would cause test_every_protected_route_declares_a_gate to flag it."
    )


# ---------------------------------------------------------------------------
# 6. RBAC pairs registered in permissions.py (D-51-10).
# ---------------------------------------------------------------------------


def test_phase51_refund_routes_rbac_pairs_registered() -> None:
    """(Action.REFUND, Resource.MEMBERSHIPS) and (Action.REFUND, Resource.PT_PACKAGES)
    are valid RBAC pairs (D-51-10 — they must exist as Action/Resource enum values).

    Verifies the enum membership so a future enum pruning does not silently break
    the route's require_permission call with a ValueError at startup.
    """
    assert Action.REFUND is not None, "Action.REFUND not defined in permissions.py"
    assert Resource.MEMBERSHIPS is not None, "Resource.MEMBERSHIPS not defined in permissions.py"
    assert Resource.PT_PACKAGES is not None, "Resource.PT_PACKAGES not defined in permissions.py"

    # Verify require_permission accepts these pairs without raising.
    from app.core.dependencies import require_permission

    mbr_dep = require_permission(Action.REFUND, Resource.MEMBERSHIPS)
    pt_dep = require_permission(Action.REFUND, Resource.PT_PACKAGES)

    assert mbr_dep.__qualname__.startswith("require_permission."), mbr_dep.__qualname__
    assert pt_dep.__qualname__.startswith("require_permission."), pt_dep.__qualname__
