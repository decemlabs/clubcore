"""TEST-05: every OWNER_ONLY pair → owner=200 / reception=403 / unauth=401 (Phase 6 D-11).

Exercises the full RBAC chain on REAL seeded users:
  Argon2 verify → JWT mint → cookie issue → JWT decode → loader → require_permission
  → can() → ForbiddenError handler → JSON envelope.

The synthetic /_t/{action}/{resource} endpoints are mounted by the
`app_with_fixture_routes` conftest fixture (D-10, D-12).
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from structlog.testing import capture_logs

from app.core.permissions import OWNER_ONLY, Action, Resource

# Sort for stable parametrize output (StrEnum comparison falls back to underlying str).
_PAIRS: list[tuple[Action, Resource]] = sorted(
    OWNER_ONLY, key=lambda p: (p[0].value, p[1].value)
)


@pytest.mark.parametrize("action,resource", _PAIRS)
async def test_owner_allowed_on_every_owner_only_pair(
    owner_client: AsyncClient,
    action: Action,
    resource: Resource,
) -> None:
    r = await owner_client.get(f"/_t/{action.value}/{resource.value}")
    assert r.status_code == 200, r.text
    assert r.json() == {"ok": True}


@pytest.mark.parametrize("action,resource", _PAIRS)
async def test_reception_forbidden_on_every_owner_only_pair(
    reception_client: AsyncClient,
    action: Action,
    resource: Resource,
) -> None:
    r = await reception_client.get(f"/_t/{action.value}/{resource.value}")
    assert r.status_code == 403, r.text
    body = r.json()
    assert body["code"] == "forbidden"
    assert body["message"] == f"forbidden:{action.value}:{resource.value}"
    assert body["fields"] is None


@pytest.mark.parametrize("action,resource", _PAIRS)
async def test_unauthenticated_returns_401_before_403(
    rbac_async_client: AsyncClient,
    action: Action,
    resource: Resource,
) -> None:
    """RBAC-04 invariant (D-22): 401 fires BEFORE 403 when caller has no identity."""
    r = await rbac_async_client.get(f"/_t/{action.value}/{resource.value}")
    assert r.status_code == 401, r.text
    assert r.json()["code"] == "invalid_token"


async def test_reception_denial_emits_rbac_forbidden_event(
    reception_client: AsyncClient,
) -> None:
    """Smoke-test for D-23 wiring (Plan 06-02 Task 1) — event reaches structlog.

    Picks one OWNER_ONLY pair (`delete`/`clients` — a canonical owner-only
    action) and asserts the audit event was emitted with the locked payload keys.
    Phase 8 D-04: `actor_user_id` and `resource_type` are now AuditLog DB columns,
    not structlog kwargs (verified by Plan 08-08 DB-row tests).
    """
    a, r_ = Action.DELETE, Resource.CLIENTS
    with capture_logs() as captured:
        resp = await reception_client.get(f"/_t/{a.value}/{r_.value}")
    assert resp.status_code == 403
    events = [c for c in captured if c.get("event") == "rbac_forbidden"]
    assert len(events) >= 1, captured
    ev = events[-1]
    assert ev["role"] == "reception"
    assert ev["action"] == "delete"
    assert ev["path"] == f"/_t/{a.value}/{r_.value}"
