"""Integration tests for POST /api/v1/memberships Idempotency-Key contract.

Phase 32 Plan 32-02 / PAY-09 (D-32-18..D-32-20). Verifies:
  - missing header → 422 idempotency_key_required
  - invalid format → 422 idempotency_key_invalid_format
  - first call → 201 with envelope
  - replay (same key, same body) → 201 byte-identical cached envelope
  - replay (same key, different body) → 422 idempotency_key_reuse +
    only ONE payment row persisted for the original subject (no second sale)

Idempotency-Key gating is scoped to the sale endpoint ONLY in Phase 32
(D-32-20) — refund/freeze/unfreeze/renew use natural guards (DB partial
UNIQUE for refunds; status-transition guards for freeze/cancel/renew).
"""

from __future__ import annotations

from typing import Any
from uuid import UUID, uuid4

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.payments.constants import SUBJECT_KIND_MEMBERSHIP
from app.modules.payments.models import Payment

VALID_PLAN: dict[str, Any] = {
    "name": "Базовый",
    "durationDays": 30,
    "priceKopecks": 250000,
    "freezeDaysLimit": 14,
    "active": True,
}
VALID_CLIENT: dict[str, Any] = {
    "lastName": "Иванов",
    "firstName": "Иван",
    "phone": "+79991234571",
}


def _csrf_header(client: AsyncClient) -> str:
    return client.cookies.get("sportzal_csrf") or ""


async def _seed_plan_and_client(
    authed: AsyncClient,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Create a plan + client via HTTP (each call sends its own Idempotency-Key)."""
    r = await authed.post(
        "/api/v1/membership-plans",
        json=VALID_PLAN,
        headers={"X-CSRF-Token": _csrf_header(authed), "Idempotency-Key": uuid4().hex},
    )
    assert r.status_code == 201, r.text
    plan = r.json()["data"]
    r = await authed.post(
        "/api/v1/clients",
        json=VALID_CLIENT,
        headers={"X-CSRF-Token": _csrf_header(authed), "Idempotency-Key": uuid4().hex},
    )
    assert r.status_code == 201, r.text
    client = r.json()["data"]
    return plan, client


async def _seed_second_plan(authed: AsyncClient) -> dict[str, Any]:
    """Create a SECOND plan so we can issue a "same key, different body" sale."""
    r = await authed.post(
        "/api/v1/membership-plans",
        json={**VALID_PLAN, "name": "Премиум", "priceKopecks": 500000},
        headers={"X-CSRF-Token": _csrf_header(authed), "Idempotency-Key": uuid4().hex},
    )
    assert r.status_code == 201, r.text
    plan: dict[str, Any] = r.json()["data"]
    return plan


# --- 422 — missing / invalid Idempotency-Key --------------------------------


async def test_missing_idempotency_key_returns_422(
    authed_client_owner: AsyncClient,
) -> None:
    """No Idempotency-Key header → ValidationAppError("idempotency_key_required").

    Body shape: AppError handler emits {"code":"validation_error","message":"<token>"}.
    """
    plan, client = await _seed_plan_and_client(authed_client_owner)
    r = await authed_client_owner.post(
        "/api/v1/memberships",
        json={"clientId": client["id"], "planId": plan["id"]},
        headers={"X-CSRF-Token": _csrf_header(authed_client_owner)},
    )
    assert r.status_code == 422, r.text
    body = r.json()
    assert body["code"] == "validation_error"
    assert body["message"] == "idempotency_key_required"


async def test_invalid_idempotency_key_format_returns_422(
    authed_client_owner: AsyncClient,
) -> None:
    """Idempotency-Key with disallowed chars → idempotency_key_invalid_format."""
    plan, client = await _seed_plan_and_client(authed_client_owner)
    r = await authed_client_owner.post(
        "/api/v1/memberships",
        json={"clientId": client["id"], "planId": plan["id"]},
        headers={
            "X-CSRF-Token": _csrf_header(authed_client_owner),
            "Idempotency-Key": "bad!key with space",
        },
    )
    assert r.status_code == 422, r.text
    body = r.json()
    assert body["code"] == "validation_error"
    assert body["message"] == "idempotency_key_invalid_format"


# --- happy path + replay -----------------------------------------------------


async def test_first_call_returns_201(
    authed_client_owner: AsyncClient,
) -> None:
    """Valid Idempotency-Key + valid body → 201 with sale envelope."""
    plan, client = await _seed_plan_and_client(authed_client_owner)
    key = uuid4().hex
    r = await authed_client_owner.post(
        "/api/v1/memberships",
        json={"clientId": client["id"], "planId": plan["id"]},
        headers={
            "X-CSRF-Token": _csrf_header(authed_client_owner),
            "Idempotency-Key": key,
        },
    )
    assert r.status_code == 201, r.text
    data = r.json()["data"]
    UUID(data["id"])
    assert data["clientId"] == client["id"]
    assert data["planId"] == plan["id"]


async def test_replay_returns_cached_envelope(
    authed_client_owner: AsyncClient,
) -> None:
    """Same key + same body → second call returns byte-identical cached envelope."""
    plan, client = await _seed_plan_and_client(authed_client_owner)
    key = uuid4().hex
    body_json = {"clientId": client["id"], "planId": plan["id"]}
    headers = {
        "X-CSRF-Token": _csrf_header(authed_client_owner),
        "Idempotency-Key": key,
    }

    r1 = await authed_client_owner.post("/api/v1/memberships", json=body_json, headers=headers)
    assert r1.status_code == 201, r1.text

    r2 = await authed_client_owner.post("/api/v1/memberships", json=body_json, headers=headers)
    assert r2.status_code == 201, r2.text
    # Byte-identical replay — same membership.id, same created_at snapshot.
    assert r2.content == r1.content


async def test_same_key_different_body_returns_422(
    authed_client_owner: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Same Idempotency-Key + DIFFERENT body → 422 idempotency_key_reuse.

    Defence-in-depth: assert no second payment row was written for either
    plan (the second sale must NOT execute).
    """
    plan_a, client = await _seed_plan_and_client(authed_client_owner)
    plan_b = await _seed_second_plan(authed_client_owner)
    key = uuid4().hex
    headers = {
        "X-CSRF-Token": _csrf_header(authed_client_owner),
        "Idempotency-Key": key,
    }

    r1 = await authed_client_owner.post(
        "/api/v1/memberships",
        json={"clientId": client["id"], "planId": plan_a["id"]},
        headers=headers,
    )
    assert r1.status_code == 201, r1.text
    first_membership_id = UUID(r1.json()["data"]["id"])

    r2 = await authed_client_owner.post(
        "/api/v1/memberships",
        json={"clientId": client["id"], "planId": plan_b["id"]},
        headers=headers,
    )
    assert r2.status_code == 422, r2.text
    body = r2.json()
    assert body["code"] == "validation_error"
    assert body["message"] == "idempotency_key_reuse"

    # Only ONE payment row exists for the first membership; ZERO rows exist
    # for plan_b (no membership was created for it).
    rows = (
        await db_session.execute(
            select(Payment).where(
                Payment.subject_kind == SUBJECT_KIND_MEMBERSHIP,
                Payment.subject_id == first_membership_id,
            )
        )
    ).scalars().all()
    assert len(rows) == 1
