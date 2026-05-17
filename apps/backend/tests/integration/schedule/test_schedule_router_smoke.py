"""Router-level smoke tests for /api/v1/trainer-slots (Phase 38 plan 38-01 Task 2).

Covers the RBAC + Idempotency + envelope shape contract that Task 2 ships.
Behavioural tests for publish_slot / cancel_slot / list filters land in
Task 3 (`test_schedule_service.py`).
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_get_trainer_slots_owner_empty_envelope(
    authed_client_owner: AsyncClient,
) -> None:
    """SLOT-08 — owner can list slots; empty store → {items: [], total: 0, ...}."""
    r = await authed_client_owner.get("/api/v1/trainer-slots")
    assert r.status_code == 200, r.text
    body = r.json()
    data = body["data"]
    assert data["items"] == []
    assert data["total"] == 0
    assert data["page"] == 1
    assert data["pageSize"] == 20


@pytest.mark.asyncio
async def test_get_trainer_slots_reception_allowed(
    authed_client_reception: AsyncClient,
) -> None:
    """SLOT-08 — reception sees the list (LIST is NOT in OWNER_ONLY)."""
    r = await authed_client_reception.get("/api/v1/trainer-slots")
    assert r.status_code == 200, r.text


@pytest.mark.asyncio
async def test_get_trainer_slots_anon_401(
    anon_client: AsyncClient,
) -> None:
    """SLOT-08 — unauthenticated client receives 401."""
    r = await anon_client.get("/api/v1/trainer-slots")
    assert r.status_code == 401, r.text


@pytest.mark.asyncio
async def test_post_trainer_slots_reception_403(
    authed_client_reception: AsyncClient,
) -> None:
    """SLOT-02 — (CREATE, SCHEDULE_SLOTS) is OWNER_ONLY (Phase 37 INFRA-27)."""
    # Acquire CSRF cookie + Idempotency-Key so the RBAC gate (which runs
    # BEFORE verify_csrf / verify_idempotency in the Depends graph for the
    # FastAPI ordering used here) is the first/only gate to fire. Both
    # outcomes (RBAC 403 vs CSRF 403) are acceptable for this assertion;
    # the contract is "reception cannot CREATE".
    r = await authed_client_reception.post(
        "/api/v1/trainer-slots",
        json={
            "trainerId": str(uuid4()),
            "startTime": "2026-06-01T09:00:00+03:00",
            "endTime": "2026-06-01T10:00:00+03:00",
        },
        headers={
            "X-CSRF-Token": authed_client_reception.cookies.get("sportzal_csrf") or "",
            "Idempotency-Key": "test-key-reception-publish",
        },
    )
    assert r.status_code == 403, r.text


@pytest.mark.asyncio
async def test_post_trainer_slots_owner_missing_idempotency_key_422(
    authed_client_owner: AsyncClient,
) -> None:
    """D-38-14 / Pitfall 14 — Idempotency-Key is required on POST /trainer-slots."""
    r = await authed_client_owner.post(
        "/api/v1/trainer-slots",
        json={
            "trainerId": str(uuid4()),
            "startTime": "2026-06-01T09:00:00+03:00",
            "endTime": "2026-06-01T10:00:00+03:00",
        },
        headers={
            "X-CSRF-Token": authed_client_owner.cookies.get("sportzal_csrf") or "",
        },
    )
    # verify_idempotency raises ValidationAppError("idempotency_key_required")
    # which the global handler maps to 422 with {code: 'validation_error',
    # message: 'idempotency_key_required'}.
    assert r.status_code == 422, r.text
    body = r.json()
    assert body["code"] == "validation_error"
    assert body["message"] == "idempotency_key_required"


@pytest.mark.asyncio
async def test_slot_create_request_extra_field_422(
    authed_client_owner: AsyncClient,
) -> None:
    """SlotCreateRequest is `extra='forbid'` — unknown fields surface as 422."""
    r = await authed_client_owner.post(
        "/api/v1/trainer-slots",
        json={
            "trainerId": str(uuid4()),
            "startTime": "2026-06-01T09:00:00+03:00",
            "endTime": "2026-06-01T10:00:00+03:00",
            # T-38-01-07 — created_by_user_id MUST be server-set, not client-supplied.
            "createdByUserId": str(uuid4()),
        },
        headers={
            "X-CSRF-Token": authed_client_owner.cookies.get("sportzal_csrf") or "",
            "Idempotency-Key": "test-key-extra-field",
        },
    )
    assert r.status_code == 422, r.text
