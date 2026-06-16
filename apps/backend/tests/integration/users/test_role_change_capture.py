"""Phase 117 Plan 02 Task 1 — Capture real role-change response (D-V32-DRIFT-LESSON).

Hits PATCH /api/v1/users/{user_id}/role with a real seeded reception user via
ASGITransport, serializes the actual JSON response to the shared FE fixtures dir:
  apps/admin/src/features/users/capture/role-change-response.json

The captured JSON is then parsed by the FE vitest contract test
(features/users/role-change.contract.test.ts) using the REAL FE Zod UserSchema.

Seed: inserts a fresh reception user via _seed_user and targets their id.
"""

from __future__ import annotations

import json
import pathlib

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models import User
from app.core.permissions import Role

from .conftest import _csrf_headers

pytestmark = pytest.mark.asyncio(loop_scope="function")

# ---------------------------------------------------------------------------
# Shared fixtures dir
# tests/integration/users/ → parents[5] = repo root
# ---------------------------------------------------------------------------

_REPO_ROOT = pathlib.Path(__file__).resolve().parents[5]
FIXTURES_DIR = _REPO_ROOT / "apps/admin/src/features/users/capture"

_PLACEHOLDER_PWD_HASH = "$argon2id$" + "placeholder"


# ---------------------------------------------------------------------------
# Capture test — serialize REAL role-change response to shared FE fixture
# ---------------------------------------------------------------------------


async def test_capture_role_change_response(
    authed_client_owner: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """PATCH /api/v1/users/{id}/role → 204; also GET list and serialize item to capture dir.

    PATCH /api/v1/users/{id}/role returns 204 No Content — no JSON body.
    We capture the updated user from the list to get the real wire shape.
    """
    # Seed a fresh reception user distinct from the default seeded_owner.
    target = User(
        email="capture-role-target@example.com",
        password_hash=_PLACEHOLDER_PWD_HASH,
        role=Role.RECEPTION,
        full_name="Capture Role Target",
        email_verified=True,
        status="active",
        is_active=True,
    )
    db_session.add(target)
    await db_session.commit()
    await db_session.refresh(target)

    r_patch = await authed_client_owner.patch(
        f"/api/v1/users/{target.id}/role",
        json={"role": "owner"},
        headers=_csrf_headers(authed_client_owner),
    )
    assert r_patch.status_code == 204, r_patch.text

    # List the users to capture the updated wire shape.
    r_list = await authed_client_owner.get("/api/v1/users")
    assert r_list.status_code == 200, r_list.text
    list_body = r_list.json()

    # Stable field assertion.
    items = list_body["data"]["items"]
    updated_user = next(
        (u for u in items if u["id"] == str(target.id)),
        None,
    )
    assert updated_user is not None, f"Updated user {target.id} not found in list"
    assert updated_user["role"] == "owner", f"Role not updated: {updated_user}"

    # Build a single-user response envelope matching what the FE expects.
    # The PATCH response is 204; we use the list item (the real wire shape) as the
    # representative fixture for role-change. The list envelope is what the FE Zod
    # UserSchema actually parses (the item shape), so we capture the list response.
    capture_payload = list_body

    # Verify captured path is inside repo root before writing.
    assert str(FIXTURES_DIR).startswith(str(_REPO_ROOT)), (
        f"FIXTURES_DIR {FIXTURES_DIR} is outside the repo root {_REPO_ROOT}"
    )

    FIXTURES_DIR.mkdir(parents=True, exist_ok=True)
    (FIXTURES_DIR / "role-change-response.json").write_text(
        json.dumps(capture_payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
