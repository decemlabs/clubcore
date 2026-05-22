"""Smoke test for Plan 50-04 webhook route mount.

Independent of Plan 50-06's full e2e suite — B-3 fix: this baseline ensures
that even if Plan 50-06's 12 behavior tests don't all land, Plan 50-04's
own minimum smoke (router mount) is still verified at the plan boundary.
"""

from fastapi.testclient import TestClient

from app.main import create_app


def test_yookassa_webhook_route_is_mounted_at_internal_path() -> None:
    app = create_app()
    paths = [r.path for r in app.routes]  # type: ignore[attr-defined]
    assert "/api/v1/_internal/yookassa/webhook" in paths, (
        "Plan 50-04 baseline: /api/v1/_internal/yookassa/webhook MUST be mounted; "
        f"found paths matching /_internal/: "
        f"{[p for p in paths if '_internal' in p]}"
    )


def test_create_app_does_not_fail_after_webhook_mount() -> None:
    """Composition root smoke — create_app() returns a TestClient-usable app."""
    app = create_app()
    client = TestClient(app)
    # Sanity: TestClient instantiates without raising — the router mount is well-formed.
    assert client is not None
