"""TEST-07: every non-excluded APIRoute declares a gate (Phase 6 D-04, D-17, D-18, D-19).

Walks `app.routes` from a fresh `create_app()`. For each `APIRoute`:
  - Skip if path is in `EXCLUDED_PATHS` (D-04 — auth bootstrap, healthz, FastAPI built-ins).
  - Skip if path starts with `/api/v1/auth/telegram/` (D-19 — Phase 7 routes, exempt by prefix).
  - Otherwise: assert the dependant tree contains a callable whose `__qualname__`
    starts with `require_permission.` or `require_authenticated.` (D-18).

The closure inside each factory is named `_checker`, but `__qualname__` is
`require_permission.<locals>._checker` — `startswith("require_permission.")`
picks up the literal prefix before `<locals>`.

THIS TEST IS THE ARCHITECTURAL ENFORCEMENT (CONTEXT.md specifics — "the test IS the rule").
A new business route that ships without a gate fails this test on the next CI run.
"""

from __future__ import annotations

from typing import Any

from fastapi.routing import APIRoute

from app.main import create_app

# D-04 + D-19: paths that may legally have NO gate. frozenset for fast lookup.
# The exclusion list IS the audit trail — a diff to this set is a deliberate decision.
EXCLUDED_PATHS: frozenset[str] = frozenset(
    {
        "/healthz",  # Phase 2 D-14 — Kubernetes liveness probe
        "/api/v1/auth/login",  # identity in body
        "/api/v1/auth/refresh",  # identity in sz_refresh cookie; access cookie may be expired
        "/api/v1/auth/telegram/start",  # Phase 7 — pre-auth deep-link handshake
        "/api/v1/auth/telegram/status",  # Phase 7 — pre-auth poll
        "/api/v1/auth/telegram/verify",  # Phase 7 — body carries token + code
        "/api/v1/auth/otp/request",  # Phase 42 D-42-22 — pre-auth OTP bootstrap (telegram + email channels)
        # Phase 49 D-49-26 — PAY-07 anonymous-by-design return-URL screen.
        # No auth, no CSRF; reveals no data (static HTML only). The handler
        # MUST stay this way — adding any DB lookup or query-param branching
        # re-introduces the oracle that Plan 49-05 was designed to eliminate.
        "/api/v1/online-payments/return",
        # FastAPI built-ins:
        "/openapi.json",
        "/docs",
        "/docs/oauth2-redirect",
        "/redoc",
    }
)

# D-19: prefix exclusions for subtrees (Phase 7 telegram routes; defensive
# in case Phase 7 mounts variants beyond the three listed paths).
#
# Phase 42 EMAIL-07 / D-42-17 — /api/v1/_internal/* is the transport-layer
# namespace for provider webhooks. Each inhabitant carries its OWN auth model
# (HMAC-SHA256 signature in X-Email-Webhook-Signature for the email webhook),
# verified BEFORE body parse with hmac.compare_digest. The gate IS present
# at the source level; it is not a FastAPI Depends so the introspection-based
# gate test cannot see it. Prefix-exclusion preserves the diff-as-audit-trail
# property (D-19) — adding new /_internal/* endpoints without HMAC will pass
# this test, so each new inhabitant must be reviewed for its own auth shape.
EXCLUDED_PREFIXES: tuple[str, ...] = (
    "/api/v1/auth/telegram/",
    "/api/v1/_internal/",
)

# D-18: __qualname__ prefix discriminator.
# Phase 32 D-32-25 — payments.permissions.require_payments_view_for_subject is a
# module-local factory mirroring require_permission shape. Reception is admitted
# on /by-client and /by-membership scoped routes; the closure name remains _checker
# so the qualname is `require_payments_view_for_subject.<locals>._checker`.
_GATE_PREFIXES: tuple[str, ...] = (
    "require_permission.",
    "require_authenticated.",
    "require_payments_view_for_subject.",
)


def _route_has_gate(route: APIRoute) -> bool:
    """Recursively walk route.dependant.dependencies for a require_* call.

    FastAPI nests Depends(...) chains:
      require_permission depends on get_current_user, which depends on get_db.
      We need ANY node in the tree whose `call.__qualname__` starts with a gate prefix.
    """
    seen: set[int] = set()

    def _walk(dep: Any) -> bool:
        if id(dep) in seen:
            return False
        seen.add(id(dep))
        call = getattr(dep, "call", None)
        if call is not None:
            qualname = getattr(call, "__qualname__", "")
            if any(qualname.startswith(p) for p in _GATE_PREFIXES):
                return True
        return any(_walk(sub) for sub in getattr(dep, "dependencies", []))

    return _walk(route.dependant)


def test_every_protected_route_declares_a_gate() -> None:
    """Architectural enforcement: every non-excluded APIRoute carries a gate.

    Failure message includes the exclusion list so the developer can immediately
    verify whether the missing-gate route was meant to be excluded (D-19).
    """
    app = create_app()
    failures: list[str] = []
    for route in app.routes:
        if not isinstance(route, APIRoute):
            continue  # Mount, WebSocketRoute — not in scope
        path = route.path
        if path in EXCLUDED_PATHS:
            continue
        if any(path.startswith(p) for p in EXCLUDED_PREFIXES):
            continue
        if not _route_has_gate(route):
            failures.append(path)

    assert not failures, (
        f"Routes missing require_permission/require_authenticated gate: {failures}\n"
        f"\n"
        f"If a route should be exempt (e.g., a new auth bootstrap endpoint), add it to\n"
        f"EXCLUDED_PATHS in this file. The diff is the audit trail (D-19).\n"
        f"\n"
        f"Current EXCLUDED_PATHS: {sorted(EXCLUDED_PATHS)}\n"
        f"Current EXCLUDED_PREFIXES: {EXCLUDED_PREFIXES}\n"
    )


def test_excluded_paths_set_is_locked() -> None:
    """Sanity belt — the exclusion list shape is deliberate. Any change MUST be a deliberate edit.

    This test exists so a future "let me just add /api/v1/clients to the exclusion list to
    unblock the build" gets caught in code review by a diff that touches this assertion.
    """
    # The current Phase 6 exclusion shape (Phase 7 telegram paths included even though
    # not yet mounted — D-04: "paths that DON'T need a gate when present").
    assert "/healthz" in EXCLUDED_PATHS
    assert "/api/v1/auth/login" in EXCLUDED_PATHS
    assert "/api/v1/auth/refresh" in EXCLUDED_PATHS
    # /me, /logout, /logout-all are NOT excluded — they carry require_authenticated
    # per Plan 06-03.
    assert "/api/v1/auth/me" not in EXCLUDED_PATHS
    assert "/api/v1/auth/logout" not in EXCLUDED_PATHS
    assert "/api/v1/auth/logout-all" not in EXCLUDED_PATHS


def test_gate_prefixes_match_factory_names() -> None:
    """Sanity belt — _GATE_PREFIXES must match the actual factory __qualname__ shape.

    If require_authenticated or require_permission is renamed, this test fails
    immediately with a clear message rather than silently letting all routes
    appear to lack a gate.
    """
    from app.core.dependencies import require_authenticated, require_permission
    from app.core.permissions import Action, Resource
    from app.modules.payments.permissions import require_payments_view_for_subject

    ra = require_authenticated()
    rp = require_permission(Action.DELETE, Resource.CLIENTS)
    rpv = require_payments_view_for_subject()
    assert ra.__qualname__.startswith("require_authenticated."), ra.__qualname__
    assert rp.__qualname__.startswith("require_permission."), rp.__qualname__
    assert rpv.__qualname__.startswith("require_payments_view_for_subject."), rpv.__qualname__
    assert _GATE_PREFIXES == (
        "require_permission.",
        "require_authenticated.",
        "require_payments_view_for_subject.",
    )
