"""Phase 117 Plan 02 Task 1 — Capture real staff inbox response (D-V32-DRIFT-LESSON).

Hits GET /api/v1/messages/threads via ASGITransport after seeding a thread, serializes
the actual JSON response to the shared FE fixtures dir:
  apps/admin/src/features/messages/capture/threads-list-response.json

The captured JSON is parsed by the FE vitest contract test
(features/messages/messages.contract.test.ts) using the REAL FE Zod StaffInboxSchema.

Pattern: mirrors test_messaging_rest.py (own ASGITransport fixtures + SAVEPOINT session).
Auth: uses memberships conftest authed_client_owner (staff login with cc_access cookie).

Note: this file lives in tests/messaging/ (per plan) alongside the WS tests but uses
the async ASGITransport pattern (not the sync TestClient WS pattern).
"""

from __future__ import annotations

import json
import pathlib
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

# Re-export the authed client fixtures from memberships conftest.
from tests.integration.memberships.conftest import (  # noqa: F401
    _client_app_overrides,
    authed_client_owner,
    make_client,
    make_user,
    redis_clean,
    seeded_owner,
    seeded_reception,
)

pytestmark = pytest.mark.asyncio(loop_scope="function")

# ---------------------------------------------------------------------------
# Shared fixtures dir
# tests/messaging/ → parents[4] = repo root
# ---------------------------------------------------------------------------

_REPO_ROOT = pathlib.Path(__file__).resolve().parents[4]
FIXTURES_DIR = _REPO_ROOT / "apps/admin/src/features/messages/capture"


# ---------------------------------------------------------------------------
# Seed helper — create a thread with one client message
# ---------------------------------------------------------------------------


async def _seed_thread_with_client_message(
    session: AsyncSession,
    client_id: Any,
) -> None:
    """Insert a message_threads row and one client message for the inbox."""
    thread_result = await session.execute(
        text(
            "INSERT INTO message_threads (client_id, last_message_at) "
            "VALUES (:cid, now()) "
            "RETURNING id"
        ),
        {"cid": str(client_id)},
    )
    thread_id = thread_result.scalar_one()
    await session.execute(
        text(
            "INSERT INTO messages (thread_id, role, body, sent_at) "
            "VALUES (:tid, 'client', 'Привет из capture теста', now())"
        ),
        {"tid": str(thread_id)},
    )
    await session.commit()


# ---------------------------------------------------------------------------
# Capture test — serialize REAL staff inbox response to shared FE fixture
# ---------------------------------------------------------------------------


async def test_capture_threads_list_response(
    authed_client_owner: AsyncClient,
    make_client: Any,
    db_session: AsyncSession,
) -> None:
    """GET /api/v1/messages/threads → 200; serialize r.json() to capture dir.

    Seeds one thread so the inbox always has at least one item.
    """
    # Seed a client + thread with one client message.
    client = await make_client(first_name="Иван", last_name="Захватов")
    await _seed_thread_with_client_message(db_session, client.id)

    r = await authed_client_owner.get("/api/v1/messages/threads")
    assert r.status_code == 200, r.text

    body = r.json()
    # Stable field assertions — test fails loudly if the response shape collapses.
    data = body["data"]
    assert "items" in data, f"Expected 'items' in data, got: {data}"
    assert "total" in data, f"Expected 'total' in data, got: {data}"
    assert isinstance(data["items"], list), f"items must be a list, got: {type(data['items'])}"
    assert data["total"] >= 1, f"Expected at least 1 thread, got total={data['total']}"

    # Verify captured path is inside repo root before writing.
    assert str(FIXTURES_DIR).startswith(str(_REPO_ROOT)), (
        f"FIXTURES_DIR {FIXTURES_DIR} is outside the repo root {_REPO_ROOT}"
    )

    FIXTURES_DIR.mkdir(parents=True, exist_ok=True)
    (FIXTURES_DIR / "threads-list-response.json").write_text(
        json.dumps(body, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
