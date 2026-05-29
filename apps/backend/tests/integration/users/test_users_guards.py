"""Phase 43 USERS-04/05/07 guard-condition tests — D-43-16/18/29.

Six guard tests covering:
  - Self-guards (D-43-16/18): owner cannot deactivate or delete themselves → 409.
  - Last-owner guards (D-43-16): when the actor IS the only active owner, the
    self-guard fires first; either ``cannot_deactivate_self`` or
    ``cannot_deactivate_last_owner`` is acceptable per the plan-text fallback
    (the fixture ``single_active_owner_id`` collapses to the authed owner id).
  - RBAC (D-43-29): reception is denied every ``/api/v1/users/*`` route — every
    ``(Action.{CREATE,UPDATE,DELETE,LIST}, Resource.USERS)`` pair is in
    ``OWNER_ONLY`` (``app/core/permissions.py:120-123``).
  - CSRF (D-43-29): mutations without ``X-CSRF-Token`` header → 403
    ``csrf_mismatch`` (``app/core/dependencies.py:verify_csrf``).

Fixture surface (all from ``tests/integration/users/conftest.py`` — owned by
plan 43-07b; do NOT redefine here):
  - ``authed_client_owner``                — owner cookies + CSRF in jar.
  - ``authed_client_reception``            — reception cookies + CSRF in jar.
  - ``current_owner_user_id``              — UUID of the seeded owner.
  - ``single_active_owner_id``             — UUID of the *only* active owner
                                              (same row as ``current_owner_user_id``
                                              by construction; the fixture
                                              deactivates extras to force the
                                              last-owner precondition).

Error-body convention (``app/core/exceptions.py:399-411``): the global
``AppError`` JSON handler returns ``{"code", "message", "fields"}`` at the
TOP level (NOT under ``detail`` — that would be FastAPI's RequestValidation
shape). All assertions use ``r.json()["code"]``.
"""

from __future__ import annotations

from uuid import UUID

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


def _csrf(client: AsyncClient) -> dict[str, str]:
    """Return ``{X-CSRF-Token: <cookie>}`` for CSRF-protected mutating routes.

    Mirrors ``tests/integration/users/conftest.py:_csrf_headers``; inlined here
    to keep the test file self-readable. ``or ""`` coerces the ``str | None``
    that ``httpx.Cookies.get`` returns to satisfy mypy strict.
    """
    return {"X-CSRF-Token": client.cookies.get("clubcore_csrf") or ""}


async def test_cannot_deactivate_self_returns_409(
    authed_client_owner: AsyncClient,
    current_owner_user_id: UUID,
) -> None:
    """D-43-16 — owner cannot deactivate own account (self-guard, 409)."""
    r = await authed_client_owner.patch(
        f"/api/v1/users/{current_owner_user_id}/deactivate",
        headers=_csrf(authed_client_owner),
    )
    assert r.status_code == 409, r.text
    assert r.json()["code"] == "cannot_deactivate_self"


async def test_cannot_deactivate_last_owner_returns_409(
    authed_client_owner: AsyncClient,
    single_active_owner_id: UUID,
) -> None:
    """D-43-16 — cannot deactivate the last active owner (409).

    The ``single_active_owner_id`` fixture deactivates every other active
    owner so the precondition for the last-owner guard holds. In the
    single-owner test seed this fixture returns the same id as
    ``current_owner_user_id`` (the seeded owner is the survivor), which
    means the self-guard at ``service.deactivate_user`` (line 244) fires
    BEFORE the last-owner branch (lines 246-252). Accept either outcome —
    both prove the guard chain is wired (Pitfall: an unprotected last-owner
    deactivation would return 204, not 409).
    """
    r = await authed_client_owner.patch(
        f"/api/v1/users/{single_active_owner_id}/deactivate",
        headers=_csrf(authed_client_owner),
    )
    assert r.status_code == 409, r.text
    code = r.json()["code"]
    assert code in ("cannot_deactivate_last_owner", "cannot_deactivate_self"), code


async def test_cannot_delete_self_returns_409(
    authed_client_owner: AsyncClient,
    current_owner_user_id: UUID,
) -> None:
    """D-43-18 — owner cannot soft-delete own account (self-guard, 409)."""
    r = await authed_client_owner.delete(
        f"/api/v1/users/{current_owner_user_id}",
        headers=_csrf(authed_client_owner),
    )
    assert r.status_code == 409, r.text
    assert r.json()["code"] == "cannot_delete_self"


async def test_reception_cannot_create_user_403(
    authed_client_reception: AsyncClient,
) -> None:
    """D-43-29 / USERS-07 — reception is denied POST /api/v1/users (RBAC).

    ``(Action.CREATE, Resource.USERS)`` is in ``OWNER_ONLY``
    (``app/core/permissions.py:120``) — ``require_permission`` short-circuits
    before any service logic runs.
    """
    r = await authed_client_reception.post(
        "/api/v1/users",
        json={"email": "x@example.com", "fullName": "X", "role": "reception"},
        headers=_csrf(authed_client_reception),
    )
    assert r.status_code == 403, r.text
    assert r.json()["code"] == "forbidden"


async def test_reception_cannot_list_users_403(
    authed_client_reception: AsyncClient,
) -> None:
    """D-43-29 — reception is denied GET /api/v1/users (LIST is OWNER_ONLY).

    ``(Action.LIST, Resource.USERS)`` is in ``OWNER_ONLY``
    (``app/core/permissions.py:123``). GET is a safe method so no CSRF
    check fires — the 403 comes exclusively from RBAC.
    """
    r = await authed_client_reception.get("/api/v1/users")
    assert r.status_code == 403, r.text
    assert r.json()["code"] == "forbidden"


async def test_create_missing_csrf_returns_403(
    authed_client_owner: AsyncClient,
) -> None:
    """D-43-29 — POST /api/v1/users without ``X-CSRF-Token`` → 403 csrf_mismatch.

    RBAC-04 ordering (``users/router.py:19-25``): ``require_permission``
    declares BEFORE ``verify_csrf`` in the endpoint signature, but the
    actor IS owner here, so RBAC passes and ``verify_csrf`` (which reads
    the cookie + header pair) is what raises ``CsrfMismatch``
    (``app/core/dependencies.py:870``).
    """
    r = await authed_client_owner.post(
        "/api/v1/users",
        json={"email": "no-csrf@example.com", "fullName": "X", "role": "reception"},
        # NB: NO _csrf(...) headers — verify_csrf must fire.
    )
    assert r.status_code == 403, r.text
    assert r.json()["code"] == "csrf_mismatch"
