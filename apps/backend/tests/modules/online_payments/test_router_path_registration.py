"""Phase 49 BLOCKER #6 — runtime path-registration assertions.

Walks ``app.routes`` after ``create_app()`` and asserts the 4 POST sell paths
exist at their exact ``/api/v1/online-payments/...`` mount points. The 1 GET
``/return`` path (Plan 49-05 deliverable) is asserted conditionally: present
when Plan 49-05 has shipped, silently OK when not.

This replaces the hedged grep-based path-string assertion from the original
Plan 49-04 draft (BLOCKER #6) — concrete runtime evidence beats string-shape
guessing. The test instantiates a real FastAPI app via the production
factory so the assertion exercises the full ``api → v1 → online_payments``
include chain.
"""

from __future__ import annotations

from app.main import create_app

# The 4 POST paths Plan 49-04 ships (D-49-14 — verbatim from CONTEXT.md).
EXPECTED_POST_PATHS: frozenset[str] = frozenset(
    {
        "/api/v1/online-payments/memberships/{plan_id}/sell",
        "/api/v1/online-payments/memberships/{plan_id}/sell-qr",
        "/api/v1/online-payments/pt-packages/{plan_id}/sell",
        "/api/v1/online-payments/pt-packages/{plan_id}/sell-qr",
    }
)

# The 1 GET path Plan 49-05 ships (anonymous /return; D-49-26).
EXPECTED_GET_PATH: str = "/api/v1/online-payments/return"


def _all_paths() -> set[str]:
    """Return every ``path`` attribute on the routes registered by ``create_app()``."""
    app = create_app()
    return {r.path for r in app.routes if hasattr(r, "path")}


def test_all_four_post_sell_paths_registered_with_correct_mount_prefix() -> None:
    """Exact path strings for the 4 sell endpoints exist (BLOCKER #6).

    Asserts ALL four expected POST paths are present at the canonical mount
    prefix. Failure prints the actual ``/online-payments`` paths observed,
    so a mount drift (e.g. forgot ``prefix='/online-payments'`` or mounted
    under the wrong APIRouter) surfaces the diagnostic immediately.
    """
    paths = _all_paths()
    missing = EXPECTED_POST_PATHS - paths
    actual_subset = sorted(p for p in paths if "/online-payments" in p)
    assert not missing, (
        f"Expected POST sell paths not registered at /api/v1/online-payments/...: "
        f"{sorted(missing)}. Actual /online-payments paths observed: {actual_subset}"
    )


def test_return_path_registered_when_plan_49_05_has_shipped() -> None:
    """The ``/return`` path is owned by Plan 49-05; assert its location IFF present.

    Wave-2 ordering: this test ships alongside Plan 49-04 but the ``/return``
    handler belongs to Plan 49-05. We assert conditionally so the test passes
    BOTH before and after 49-05 lands, while still catching any 49-05 attempt
    to mount ``/return`` at the wrong prefix.
    """
    paths = _all_paths()
    online_payment_paths = {p for p in paths if "/online-payments" in p}
    # If ANY /online-payments path ends in /return, it MUST be exactly the
    # canonical D-49-26 location.
    return_like = {p for p in online_payment_paths if p.endswith("/return")}
    if return_like:
        assert EXPECTED_GET_PATH in paths, (
            f"Plan 49-05 /return path registered but at wrong location: "
            f"{sorted(return_like)}; expected {EXPECTED_GET_PATH!r}"
        )


def test_no_unexpected_online_payments_paths_registered() -> None:
    """Defensive — fail if any ``/online-payments`` path appears outside the contract.

    Phase 49 ships exactly 5 paths under the ``online_payments`` mount (4 POST
    sells from Plan 49-04 + 1 GET /return from Plan 49-05). Any additional
    path under the same prefix is contract drift and must be reviewed.
    """
    paths = _all_paths()
    online_payment_paths = {p for p in paths if "/online-payments" in p}
    expected = EXPECTED_POST_PATHS | {EXPECTED_GET_PATH}
    unexpected = online_payment_paths - expected
    assert not unexpected, (
        f"Unexpected /online-payments paths registered (Phase 49 contract drift?): "
        f"{sorted(unexpected)}"
    )
