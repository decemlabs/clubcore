"""Plan 38-02 Task 2 — router-level smoke tests for /api/v1/bookings.

Covers:
  - schema import smoke (BookingCreateRequest / BookingResponse).
  - bookings_router mounted on the FastAPI app at /api/v1/bookings.
  - POST /api/v1/bookings without auth → 401.
  - POST /api/v1/bookings missing Idempotency-Key → 422 (validation_error
    with message='idempotency_key_required'; mirrors schedule smoke shape).
  - POST /api/v1/bookings with extra field → 422 (extra='forbid' rejection).

Task 3 ships the orchestrator + happy-path + 9 negative-path tests
separately in test_bookings_create.py.
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi import FastAPI
from httpx import AsyncClient


def test_schemas_import() -> None:
    """Smoke: BookingCreateRequest + BookingResponse importable; extra='forbid'."""
    # extra='forbid' inherited from BackendSchemaBase.
    from pydantic import ValidationError as _PydanticValidationError

    from app.modules.bookings.schemas import (
        BookingCreateRequest,
        BookingResponse,
        BookingStatus,
    )

    with pytest.raises(_PydanticValidationError):
        BookingCreateRequest(
            slot_id=uuid4(),
            client_id=uuid4(),
            pt_package_id=uuid4(),
            unexpected_extra="reject_me",  # type: ignore[call-arg]
        )

    # Status enum values byte-stable with migration CHECK.
    assert BookingStatus.CONFIRMED.value == "confirmed"
    assert BookingStatus.CANCELLED.value == "cancelled"
    assert BookingStatus.NO_SHOW.value == "no_show"
    assert BookingStatus.COMPLETED.value == "completed"
    # BookingResponse importable (full attribute set).
    assert BookingResponse.__name__ == "BookingResponse"


def test_bookings_router_mounted(app: FastAPI) -> None:
    """Smoke: POST /api/v1/bookings is registered on the FastAPI route table."""
    paths = {r.path for r in app.routes}  # type: ignore[attr-defined]
    assert "/api/v1/bookings" in paths, (
        f"/api/v1/bookings not mounted; "
        f"saw: {sorted(p for p in paths if 'book' in p.lower())}"
    )


def test_repository_caller_owns_txn_discipline() -> None:
    """SVC001/repository invariant: bookings/repository.py contains NO session.commit
    and NO session.flush calls (caller-owns-txn per memberships D-14 / D-38)."""
    from pathlib import Path

    repo_path = (
        Path(__file__).resolve().parents[3]
        / "app"
        / "modules"
        / "bookings"
        / "repository.py"
    )
    src = repo_path.read_text(encoding="utf-8")
    # Strip docstrings/comments to avoid false positives from the module
    # top-doc that *describes* the caller-owns-txn discipline.
    code_only = "\n".join(
        line for line in src.splitlines() if not line.lstrip().startswith("#")
    )
    # Crude but sufficient: strip triple-quoted blocks.
    import re

    code_only = re.sub(r'""".*?"""', "", code_only, flags=re.DOTALL)
    assert "await session.commit" not in code_only, "bookings repository must not commit"
    assert "await session.flush" not in code_only, "bookings repository must not flush"
    # TABLE_REF noqa marker present for cross-module raw SQL.
    assert "noqa: TABLE_REF" in src, "cross-module raw SQL must carry TABLE_REF noqa"


def test_repository_no_direct_schedule_import() -> None:
    """D-38-11: cross-module reach goes through raw SQL only — bookings repository
    must NEVER `from app.modules.schedule import ...`."""
    from pathlib import Path

    repo_path = (
        Path(__file__).resolve().parents[3]
        / "app"
        / "modules"
        / "bookings"
        / "repository.py"
    )
    src = repo_path.read_text(encoding="utf-8")
    assert "from app.modules.schedule" not in src, (
        "bookings repository must NOT import from app.modules.schedule "
        "(D-38-11 modules-independent contract)"
    )


@pytest.mark.asyncio
async def test_post_bookings_anon_401(anon_client: AsyncClient) -> None:
    """Anonymous POST /api/v1/bookings → 401."""
    r = await anon_client.post(
        "/api/v1/bookings",
        json={
            "slotId": str(uuid4()),
            "clientId": str(uuid4()),
            "ptPackageId": str(uuid4()),
        },
        headers={"Idempotency-Key": "book-smoke-anon"},
    )
    assert r.status_code == 401, r.text


@pytest.mark.asyncio
async def test_post_bookings_owner_missing_idempotency_key_422(
    authed_client_owner: AsyncClient,
) -> None:
    """Owner POST without Idempotency-Key → 422 (validation_error /
    idempotency_key_required)."""
    csrf_token = authed_client_owner.cookies.get("sportzal_csrf") or ""
    r = await authed_client_owner.post(
        "/api/v1/bookings",
        json={
            "slotId": str(uuid4()),
            "clientId": str(uuid4()),
            "ptPackageId": str(uuid4()),
        },
        headers={"X-CSRF-Token": csrf_token},
    )
    assert r.status_code == 422, r.text
    body = r.json()
    assert body["code"] == "validation_error"
    assert body["message"] == "idempotency_key_required"


@pytest.mark.asyncio
async def test_post_bookings_owner_extra_field_422(
    authed_client_owner: AsyncClient,
) -> None:
    """Owner POST with extra field → 422 (extra='forbid' rejection at schema)."""
    csrf_token = authed_client_owner.cookies.get("sportzal_csrf") or ""
    r = await authed_client_owner.post(
        "/api/v1/bookings",
        json={
            "slotId": str(uuid4()),
            "clientId": str(uuid4()),
            "ptPackageId": str(uuid4()),
            "unexpectedExtra": "reject_me",
        },
        headers={
            "X-CSRF-Token": csrf_token,
            "Idempotency-Key": "book-smoke-extra",
        },
    )
    assert r.status_code == 422, r.text
