"""Phase 66 Plan 66-05 — IDM-03 + IDM-05 + IDM-06 integration tests for memberships.

Asserts the hardened idempotency behavior (via real Postgres + real Redis):

  - Double-submit (same key, same body) returns byte-identical cached response.
  - Replay does NOT re-emit audit events: AuditLog count for the subject is
    unchanged after the replayed second submit.
  - Same key + different body → 422 idempotency_key_reuse.
  - IDM-05 cross-user: same Idempotency-Key from two different users yields
    two distinct Redis entries (user B is NOT served user A's cached body).
  - IDM-06 AppError replay: retry of an AppError-raising call replays the
    SAME error status+body, NOT 409 idempotency_in_flight.
  - IDM-06 rollback-retry: a first call that raises an unknown exception
    (monkeypatched RuntimeError) allows a fresh retry (no 24h lockout).

Category-A memberships endpoints covered (per v1.11-idempotency-audit.md):
  - POST /api/v1/memberships                      (create_membership, A)
  - POST /api/v1/memberships/{id}/cancel          (cancel_membership, A/IDM-07)
  - POST /api/v1/memberships/{id}/freeze          (freeze_membership, A/IDM-07)
  - POST /api/v1/memberships/{id}/unfreeze        (unfreeze_membership, A/IDM-07)
  - POST /api/v1/memberships/{id}/renew           (renew_membership, A/IDM-07)
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable, Callable
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit_models import AuditLog
from app.core.database import get_db
from app.core.permissions import Role
from app.core.redis import get_redis
from app.core.security import hash_password
from app.modules.auth.models import User
from app.modules.memberships.models import Membership, MembershipPlan

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SECOND_OWNER_EMAIL = "idem-hardening-owner2@example.com"
SECOND_OWNER_PASSWORD = "hunter22hunter22"  # noqa: S105 -- test password literal


def _csrf_header(client: AsyncClient) -> str:
    return client.cookies.get("clubcore_csrf") or ""


def _headers(client: AsyncClient, *, key: str) -> dict[str, str]:
    return {
        "X-CSRF-Token": _csrf_header(client),
        "Idempotency-Key": key,
    }


async def _audit_count(
    session: AsyncSession,
    resource_id: UUID,
) -> int:
    """Count AuditLog rows for a given resource_id."""
    result = await session.execute(
        select(func.count()).select_from(AuditLog).where(AuditLog.resource_id == resource_id)
    )
    return int(result.scalar_one())


async def _seed_plan(authed: AsyncClient) -> dict[str, Any]:
    """Create a MembershipPlan via HTTP using a fresh Idempotency-Key."""
    r = await authed.post(
        "/api/v1/membership-plans",
        json={
            "name": f"IDM-Test-{uuid4().hex[:8]}",
            "durationDays": 30,
            "priceKopecks": 250000,
            "freezeDaysLimit": 14,
            "active": True,
        },
        headers={"X-CSRF-Token": _csrf_header(authed), "Idempotency-Key": uuid4().hex},
    )
    assert r.status_code == 201, r.text
    return r.json()["data"]  # type: ignore[no-any-return]


async def _seed_client(authed: AsyncClient) -> dict[str, Any]:
    """Create a Client via HTTP using a fresh Idempotency-Key."""
    r = await authed.post(
        "/api/v1/clients",
        json={
            "lastName": f"IDM-{uuid4().hex[:6]}",
            "firstName": "Test",
            "phone": f"+7999{uuid4().int % 10_000_000:07d}",
        },
        headers={"X-CSRF-Token": _csrf_header(authed), "Idempotency-Key": uuid4().hex},
    )
    assert r.status_code == 201, r.text
    return r.json()["data"]  # type: ignore[no-any-return]


async def _create_membership(
    authed: AsyncClient,
    *,
    plan_id: str,
    client_id: str,
    key: str,
) -> Any:
    r = await authed.post(
        "/api/v1/memberships",
        json={"clientId": client_id, "planId": plan_id},
        headers=_headers(authed, key=key),
    )
    return r


# ---------------------------------------------------------------------------
# Additional second-user fixture (IDM-05 cross-user test)
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def seeded_second_owner(
    db_session: AsyncSession,
    app: FastAPI,
) -> User:
    """Seed a second owner user for the IDM-05 cross-user test."""
    user = User(
        email=SECOND_OWNER_EMAIL,
        password_hash=await hash_password(SECOND_OWNER_PASSWORD),
        role=Role.OWNER,
        full_name="IDM Hardening Second Owner",
    )
    db_session.add(user)
    await db_session.commit()
    return user


@pytest_asyncio.fixture
async def authed_client_second_owner(
    app: FastAPI,
    db_session: AsyncSession,
    seeded_second_owner: User,
) -> AsyncIterator[AsyncClient]:
    """Second authenticated owner client for cross-user isolation proof."""

    async def _override_get_db() -> AsyncIterator[AsyncSession]:
        yield db_session

    def _override_get_redis() -> Any:
        return app.state.redis

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_redis] = _override_get_redis

    transport = ASGITransport(app=app)
    try:
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            r = await client.post(
                "/api/v1/auth/login",
                json={"email": SECOND_OWNER_EMAIL, "password": SECOND_OWNER_PASSWORD},
            )
            assert r.status_code == 200, r.text
            yield client
    finally:
        app.dependency_overrides.clear()


# ===========================================================================
# Task 1 — create_membership: double-submit + no-re-emit-audit + reuse-422
# ===========================================================================


async def test_create_membership_double_submit_byte_identical(
    authed_client_owner: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Replay of create_membership returns byte-identical cached response."""
    plan = await _seed_plan(authed_client_owner)
    client_row = await _seed_client(authed_client_owner)
    key = uuid4().hex  # 32 chars, passes {16,128}

    r1 = await _create_membership(
        authed_client_owner,
        plan_id=plan["id"],
        client_id=client_row["id"],
        key=key,
    )
    assert r1.status_code == 201, r1.text

    r2 = await _create_membership(
        authed_client_owner,
        plan_id=plan["id"],
        client_id=client_row["id"],
        key=key,
    )
    assert r2.status_code == 201, r2.text
    assert r2.content == r1.content, "Replay must return byte-identical content"


async def test_create_membership_replay_no_re_emit_audit(
    authed_client_owner: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Replay of create_membership does NOT re-emit AuditLog row for the membership."""
    plan = await _seed_plan(authed_client_owner)
    client_row = await _seed_client(authed_client_owner)
    key = uuid4().hex

    r1 = await _create_membership(
        authed_client_owner,
        plan_id=plan["id"],
        client_id=client_row["id"],
        key=key,
    )
    assert r1.status_code == 201, r1.text
    membership_id = UUID(r1.json()["data"]["id"])

    count_before = await _audit_count(db_session, membership_id)
    assert count_before >= 1, "At least one audit row expected after first submit"

    # Replay — same key + same body
    r2 = await _create_membership(
        authed_client_owner,
        plan_id=plan["id"],
        client_id=client_row["id"],
        key=key,
    )
    assert r2.status_code == 201, r2.text

    count_after = await _audit_count(db_session, membership_id)
    assert count_after == count_before, (
        f"Replay must NOT re-emit audit: before={count_before}, after={count_after}"
    )


async def test_create_membership_same_key_different_body_422(
    authed_client_owner: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Same Idempotency-Key + different body → 422 idempotency_key_reuse."""
    plan_a = await _seed_plan(authed_client_owner)
    plan_b = await _seed_plan(authed_client_owner)
    client_row = await _seed_client(authed_client_owner)
    key = uuid4().hex

    r1 = await _create_membership(
        authed_client_owner,
        plan_id=plan_a["id"],
        client_id=client_row["id"],
        key=key,
    )
    assert r1.status_code == 201, r1.text

    # Same key, different body (different plan)
    r2 = await _create_membership(
        authed_client_owner,
        plan_id=plan_b["id"],
        client_id=client_row["id"],
        key=key,
    )
    assert r2.status_code == 422, r2.text
    body = r2.json()
    assert body["code"] == "validation_error"
    assert body["message"] == "idempotency_key_reuse"


# ===========================================================================
# Task 1 — cancel_membership: double-submit + no-re-emit-audit + reuse-422
# ===========================================================================


async def test_cancel_membership_double_submit_byte_identical(
    authed_client_owner: AsyncClient,
    db_session: AsyncSession,
    make_plan: Callable[..., Awaitable[MembershipPlan]],
    make_membership: Callable[..., Awaitable[Membership]],
    make_client: Callable[..., Awaitable[Any]],
) -> None:
    """Replay of cancel_membership returns byte-identical cached response."""
    plan = await make_plan()

    client_row = await make_client()
    membership = await make_membership(client_id=client_row.id, plan=plan, status="active")
    key = uuid4().hex

    body_json = {"reason": "test_cancel_reason"}
    headers = _headers(authed_client_owner, key=key)

    r1 = await authed_client_owner.post(
        f"/api/v1/memberships/{membership.id}/cancel",
        json=body_json,
        headers=headers,
    )
    assert r1.status_code == 200, r1.text

    r2 = await authed_client_owner.post(
        f"/api/v1/memberships/{membership.id}/cancel",
        json=body_json,
        headers=headers,
    )
    assert r2.status_code == 200, r2.text
    assert r2.content == r1.content, "Replay must return byte-identical content"


async def test_cancel_membership_replay_no_re_emit_audit(
    authed_client_owner: AsyncClient,
    db_session: AsyncSession,
    make_plan: Callable[..., Awaitable[MembershipPlan]],
    make_membership: Callable[..., Awaitable[Membership]],
    make_client: Callable[..., Awaitable[Any]],
) -> None:
    """Replay of cancel_membership does NOT re-emit AuditLog row."""
    plan = await make_plan()
    client_row = await make_client()
    membership = await make_membership(client_id=client_row.id, plan=plan, status="active")
    key = uuid4().hex

    body_json = {"reason": "audit_check_reason"}
    headers = _headers(authed_client_owner, key=key)

    r1 = await authed_client_owner.post(
        f"/api/v1/memberships/{membership.id}/cancel",
        json=body_json,
        headers=headers,
    )
    assert r1.status_code == 200, r1.text

    count_before = await _audit_count(db_session, membership.id)
    assert count_before >= 1

    r2 = await authed_client_owner.post(
        f"/api/v1/memberships/{membership.id}/cancel",
        json=body_json,
        headers=headers,
    )
    assert r2.status_code == 200, r2.text

    count_after = await _audit_count(db_session, membership.id)
    assert count_after == count_before, (
        f"Replay must NOT re-emit audit: before={count_before}, after={count_after}"
    )


async def test_cancel_membership_same_key_different_body_422(
    authed_client_owner: AsyncClient,
    db_session: AsyncSession,
    make_plan: Callable[..., Awaitable[MembershipPlan]],
    make_membership: Callable[..., Awaitable[Membership]],
    make_client: Callable[..., Awaitable[Any]],
) -> None:
    """Same key + different cancel body → 422 idempotency_key_reuse."""
    plan = await make_plan()
    client_row = await make_client()
    membership = await make_membership(client_id=client_row.id, plan=plan, status="active")
    key = uuid4().hex

    headers = _headers(authed_client_owner, key=key)

    r1 = await authed_client_owner.post(
        f"/api/v1/memberships/{membership.id}/cancel",
        json={"reason": "reason_a"},
        headers=headers,
    )
    assert r1.status_code == 200, r1.text

    r2 = await authed_client_owner.post(
        f"/api/v1/memberships/{membership.id}/cancel",
        json={"reason": "reason_b"},
        headers=headers,
    )
    assert r2.status_code == 422, r2.text
    body = r2.json()
    assert body["code"] == "validation_error"
    assert body["message"] == "idempotency_key_reuse"


# ===========================================================================
# Task 1 — freeze_membership: double-submit + no-re-emit-audit
# (freeze has no request body; both submits share empty incoming_body=b"")
# ===========================================================================


async def test_freeze_membership_double_submit_byte_identical(
    authed_client_owner: AsyncClient,
    db_session: AsyncSession,
    make_plan: Callable[..., Awaitable[MembershipPlan]],
    make_membership: Callable[..., Awaitable[Membership]],
    make_client: Callable[..., Awaitable[Any]],
) -> None:
    """Replay of freeze_membership (empty body) returns byte-identical response."""
    plan = await make_plan()
    client_row = await make_client()
    membership = await make_membership(client_id=client_row.id, plan=plan, status="active")
    key = uuid4().hex
    headers = _headers(authed_client_owner, key=key)

    r1 = await authed_client_owner.post(
        f"/api/v1/memberships/{membership.id}/freeze",
        headers=headers,
    )
    assert r1.status_code == 200, r1.text

    r2 = await authed_client_owner.post(
        f"/api/v1/memberships/{membership.id}/freeze",
        headers=headers,
    )
    assert r2.status_code == 200, r2.text
    assert r2.content == r1.content, "Replay must return byte-identical content"


async def test_freeze_membership_replay_no_re_emit_audit(
    authed_client_owner: AsyncClient,
    db_session: AsyncSession,
    make_plan: Callable[..., Awaitable[MembershipPlan]],
    make_membership: Callable[..., Awaitable[Membership]],
    make_client: Callable[..., Awaitable[Any]],
) -> None:
    """Replay of freeze_membership does NOT re-emit AuditLog row."""
    plan = await make_plan()
    client_row = await make_client()
    membership = await make_membership(client_id=client_row.id, plan=plan, status="active")
    key = uuid4().hex
    headers = _headers(authed_client_owner, key=key)

    r1 = await authed_client_owner.post(
        f"/api/v1/memberships/{membership.id}/freeze",
        headers=headers,
    )
    assert r1.status_code == 200, r1.text

    count_before = await _audit_count(db_session, membership.id)
    assert count_before >= 1

    r2 = await authed_client_owner.post(
        f"/api/v1/memberships/{membership.id}/freeze",
        headers=headers,
    )
    assert r2.status_code == 200, r2.text

    count_after = await _audit_count(db_session, membership.id)
    assert count_after == count_before, (
        f"Replay must NOT re-emit audit: before={count_before}, after={count_after}"
    )


# ===========================================================================
# Task 1 — unfreeze_membership: double-submit + no-re-emit-audit
# ===========================================================================


async def test_unfreeze_membership_double_submit_byte_identical(
    authed_client_owner: AsyncClient,
    db_session: AsyncSession,
    make_plan: Callable[..., Awaitable[MembershipPlan]],
    make_membership: Callable[..., Awaitable[Membership]],
    make_client: Callable[..., Awaitable[Any]],
) -> None:
    """Replay of unfreeze_membership returns byte-identical response."""
    plan = await make_plan()
    client_row = await make_client()
    # Start frozen so unfreeze is valid
    membership = await make_membership(client_id=client_row.id, plan=plan, status="active")
    # Freeze first via HTTP to create the freeze period
    freeze_key = uuid4().hex
    rf = await authed_client_owner.post(
        f"/api/v1/memberships/{membership.id}/freeze",
        headers=_headers(authed_client_owner, key=freeze_key),
    )
    assert rf.status_code == 200, rf.text

    key = uuid4().hex
    headers = _headers(authed_client_owner, key=key)

    r1 = await authed_client_owner.post(
        f"/api/v1/memberships/{membership.id}/unfreeze",
        headers=headers,
    )
    assert r1.status_code == 200, r1.text

    r2 = await authed_client_owner.post(
        f"/api/v1/memberships/{membership.id}/unfreeze",
        headers=headers,
    )
    assert r2.status_code == 200, r2.text
    assert r2.content == r1.content, "Replay must return byte-identical content"


async def test_unfreeze_membership_replay_no_re_emit_audit(
    authed_client_owner: AsyncClient,
    db_session: AsyncSession,
    make_plan: Callable[..., Awaitable[MembershipPlan]],
    make_membership: Callable[..., Awaitable[Membership]],
    make_client: Callable[..., Awaitable[Any]],
) -> None:
    """Replay of unfreeze_membership does NOT re-emit AuditLog row."""
    plan = await make_plan()
    client_row = await make_client()
    membership = await make_membership(client_id=client_row.id, plan=plan, status="active")

    # Freeze first
    rf = await authed_client_owner.post(
        f"/api/v1/memberships/{membership.id}/freeze",
        headers=_headers(authed_client_owner, key=uuid4().hex),
    )
    assert rf.status_code == 200, rf.text

    key = uuid4().hex
    headers = _headers(authed_client_owner, key=key)

    r1 = await authed_client_owner.post(
        f"/api/v1/memberships/{membership.id}/unfreeze",
        headers=headers,
    )
    assert r1.status_code == 200, r1.text

    count_before = await _audit_count(db_session, membership.id)
    assert count_before >= 1

    r2 = await authed_client_owner.post(
        f"/api/v1/memberships/{membership.id}/unfreeze",
        headers=headers,
    )
    assert r2.status_code == 200, r2.text

    count_after = await _audit_count(db_session, membership.id)
    assert count_after == count_before, (
        f"Replay must NOT re-emit audit: before={count_before}, after={count_after}"
    )


# ===========================================================================
# Task 1 — renew_membership: double-submit + no-re-emit-audit
# ===========================================================================


async def test_renew_membership_double_submit_byte_identical(
    authed_client_owner: AsyncClient,
    db_session: AsyncSession,
    make_plan: Callable[..., Awaitable[MembershipPlan]],
    make_membership: Callable[..., Awaitable[Membership]],
    make_client: Callable[..., Awaitable[Any]],
) -> None:
    """Replay of renew_membership (empty body) returns byte-identical response."""
    plan = await make_plan()
    client_row = await make_client()
    # Use expired membership so renew is valid
    yesterday = datetime.now(tz=UTC).date() - timedelta(days=1)
    membership = await make_membership(
        client_id=client_row.id,
        plan=plan,
        status="expired",
        start_date=yesterday - timedelta(days=29),
        end_date=yesterday,
    )

    key = uuid4().hex
    headers = _headers(authed_client_owner, key=key)

    r1 = await authed_client_owner.post(
        f"/api/v1/memberships/{membership.id}/renew",
        headers=headers,
    )
    assert r1.status_code == 201, r1.text

    r2 = await authed_client_owner.post(
        f"/api/v1/memberships/{membership.id}/renew",
        headers=headers,
    )
    assert r2.status_code == 201, r2.text
    assert r2.content == r1.content, "Replay must return byte-identical content"


async def test_renew_membership_replay_no_re_emit_audit(
    authed_client_owner: AsyncClient,
    db_session: AsyncSession,
    make_plan: Callable[..., Awaitable[MembershipPlan]],
    make_membership: Callable[..., Awaitable[Membership]],
    make_client: Callable[..., Awaitable[Any]],
) -> None:
    """Replay of renew_membership does NOT re-emit AuditLog row for the new membership."""
    plan = await make_plan()
    client_row = await make_client()
    yesterday = datetime.now(tz=UTC).date() - timedelta(days=1)
    membership = await make_membership(
        client_id=client_row.id,
        plan=plan,
        status="expired",
        start_date=yesterday - timedelta(days=29),
        end_date=yesterday,
    )

    key = uuid4().hex
    headers = _headers(authed_client_owner, key=key)

    r1 = await authed_client_owner.post(
        f"/api/v1/memberships/{membership.id}/renew",
        headers=headers,
    )
    assert r1.status_code == 201, r1.text
    new_membership_id = UUID(r1.json()["data"]["id"])

    count_before = await _audit_count(db_session, new_membership_id)
    assert count_before >= 1

    r2 = await authed_client_owner.post(
        f"/api/v1/memberships/{membership.id}/renew",
        headers=headers,
    )
    assert r2.status_code == 201, r2.text

    count_after = await _audit_count(db_session, new_membership_id)
    assert count_after == count_before, (
        f"Replay must NOT re-emit audit: before={count_before}, after={count_after}"
    )


# ===========================================================================
# Task 3 — IDM-05: cross-user — same Idempotency-Key from two different users
# yields two distinct outcomes (user B NOT served user A's cached body)
# ===========================================================================


async def test_cross_user_same_key_distinct_outcomes(
    authed_client_owner: AsyncClient,
    authed_client_second_owner: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """IDM-05: same Idempotency-Key from two different users → two independent results.

    Both calls succeed and create two distinct memberships (user B is NOT served
    user A's cached envelope). The user-scoped Redis key shape
    ``cc:idem:{user_id}:POST:/api/v1/memberships:{key}`` ensures the same
    header value from two users hits different Redis namespaces.
    """
    shared_key = uuid4().hex  # same header value for both users

    # User A seeds own plan + client
    plan_a = await _seed_plan(authed_client_owner)
    client_a = await _seed_client(authed_client_owner)

    # User B seeds own plan + client
    plan_b = await _seed_plan(authed_client_second_owner)
    client_b = await _seed_client(authed_client_second_owner)

    # Both use the SAME Idempotency-Key header value
    r_user_a = await _create_membership(
        authed_client_owner,
        plan_id=plan_a["id"],
        client_id=client_a["id"],
        key=shared_key,
    )
    assert r_user_a.status_code == 201, f"User A should succeed: {r_user_a.text}"

    r_user_b = await _create_membership(
        authed_client_second_owner,
        plan_id=plan_b["id"],
        client_id=client_b["id"],
        key=shared_key,
    )
    assert r_user_b.status_code == 201, f"User B should succeed independently: {r_user_b.text}"

    membership_id_a = UUID(r_user_a.json()["data"]["id"])
    membership_id_b = UUID(r_user_b.json()["data"]["id"])

    # The two responses must produce distinct membership IDs (not a cross-user replay)
    assert membership_id_a != membership_id_b, (
        "User B must NOT be served user A's cached response — membership IDs must differ"
    )
    # The two response bodies must differ (distinct clients/plans)
    assert r_user_b.content != r_user_a.content, (
        "User B must receive their own independent response, not user A's cached body"
    )


# ===========================================================================
# Task 3 — IDM-06: AppError-replay — retry of an AppError replays the SAME
# error status+body, NOT 409 idempotency_in_flight
# ===========================================================================


async def test_app_error_retry_replays_error_not_in_flight(
    authed_client_owner: AsyncClient,
    db_session: AsyncSession,
    make_plan: Callable[..., Awaitable[MembershipPlan]],
    make_membership: Callable[..., Awaitable[Membership]],
    make_client: Callable[..., Awaitable[Any]],
) -> None:
    """IDM-06 AppError branch: cancelling a cancelled membership replays the
    error (409 invalid_transition), NOT 409 idempotency_in_flight.

    Trigger: POST /cancel on an already-cancelled membership → ConflictError
    (409 invalid_transition). Retry with the same key+body → replays the SAME
    409 invalid_transition (not idempotency_in_flight).
    """
    plan = await make_plan()
    client_row = await make_client()
    # Seed an already-cancelled membership (invalid source for cancel)
    membership = await make_membership(client_id=client_row.id, plan=plan, status="cancelled")

    key = uuid4().hex
    headers = _headers(authed_client_owner, key=key)
    body_json = {"reason": "test_apperror_replay"}

    r1 = await authed_client_owner.post(
        f"/api/v1/memberships/{membership.id}/cancel",
        json=body_json,
        headers=headers,
    )
    # First call: expect 409 invalid_transition (cancel on cancelled source)
    assert r1.status_code == 409, f"Expected 409, got {r1.status_code}: {r1.text}"
    first_body = r1.json()
    assert first_body["message"] == "invalid_transition", (
        f"Expected invalid_transition error, got: {first_body}"
    )

    # Retry with same key+body: must replay the SAME error, NOT 409 idempotency_in_flight
    r2 = await authed_client_owner.post(
        f"/api/v1/memberships/{membership.id}/cancel",
        json=body_json,
        headers=headers,
    )
    assert r2.status_code == r1.status_code, (
        f"Retry must replay same status: expected {r1.status_code}, got {r2.status_code}"
    )
    second_body = r2.json()
    # Must NOT be idempotency_in_flight
    assert second_body["message"] != "idempotency_in_flight", (
        "Retry of AppError must replay the stored error, NOT return idempotency_in_flight"
    )
    # Must replay the original error
    assert second_body["message"] == first_body["message"], (
        f"Retry must replay same error message: expected {first_body['message']}, "
        f"got {second_body['message']}"
    )
    assert r2.content == r1.content, "AppError retry must return byte-identical cached error"


# ===========================================================================
# Task 3 — IDM-06: rollback-retry — unknown exception deletes placeholder
# so next retry is fresh (no 24h lockout)
# ===========================================================================


async def test_rollback_retry_allows_fresh_attempt(
    app: FastAPI,
    db_session: AsyncSession,
    seeded_owner: User,
    make_plan: Callable[..., Awaitable[MembershipPlan]],
    make_client: Callable[..., Awaitable[Any]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """IDM-06 unknown-exception branch: monkeypatched RuntimeError on first call
    deletes the placeholder; second call with same key is fresh (not 409 locked).

    The ``idempotent_execute`` orchestrator catches any non-AppError Exception,
    calls ``await redis.delete(_redis_key(key))``, and re-raises — so the next
    retry is treated as a fresh claim (SET NX succeeds again).

    Uses ``raise_app_exceptions=False`` on ASGITransport so that the server-side
    RuntimeError is returned as a 500 response instead of propagating to the test.
    """
    from app.modules.memberships import service as memberships_service
    from tests.integration.memberships.conftest import OWNER_EMAIL, OWNER_PASSWORD

    plan = await make_plan()
    client_row = await make_client()

    call_count: dict[str, int] = {"n": 0}
    original_create = memberships_service.create_membership

    async def _patched_create(*args: Any, **kwargs: Any) -> Any:
        call_count["n"] += 1
        if call_count["n"] == 1:
            raise RuntimeError("simulated transient failure")
        return await original_create(*args, **kwargs)

    monkeypatch.setattr(memberships_service, "create_membership", _patched_create)

    # Override deps so route sees the SAVEPOINT-rolled session and lifespan Redis
    async def _override_get_db() -> AsyncIterator[AsyncSession]:
        yield db_session

    def _override_get_redis() -> Any:
        return app.state.redis

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_redis] = _override_get_redis

    # raise_app_exceptions=False: server-side RuntimeError → 500 response (not propagated)
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    try:
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            # Login
            r_login = await client.post(
                "/api/v1/auth/login",
                json={"email": OWNER_EMAIL, "password": OWNER_PASSWORD},
            )
            assert r_login.status_code == 200, r_login.text

            key = uuid4().hex
            headers = _headers(client, key=key)
            body_json = {"clientId": str(client_row.id), "planId": str(plan.id)}

            # First call: RuntimeError → 500; placeholder deleted by orchestrator
            r1 = await client.post(
                "/api/v1/memberships",
                json=body_json,
                headers=headers,
            )
            assert r1.status_code == 500, (
                f"First call should fail with 500 due to RuntimeError, "
                f"got {r1.status_code}: {r1.text}"
            )

            # Second call: same key → NOT 409 idempotency_in_flight (placeholder was deleted)
            # Should proceed as a fresh attempt (201)
            r2 = await client.post(
                "/api/v1/memberships",
                json=body_json,
                headers=headers,
            )
            assert r2.status_code != 409, (
                f"Retry after rollback must NOT be locked out (409 idempotency_in_flight); "
                f"got {r2.status_code}: {r2.text}"
            )
            # The second call should succeed (201) since the monkeypatch only fails once
            assert r2.status_code == 201, (
                f"Second call should succeed with 201 (fresh retry); "
                f"got {r2.status_code}: {r2.text}"
            )
    finally:
        app.dependency_overrides.clear()
