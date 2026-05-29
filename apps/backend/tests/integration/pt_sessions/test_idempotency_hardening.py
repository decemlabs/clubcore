"""Phase 66 Plan 66-05 — IDM-03 integration tests for pt_sessions category-A endpoints.

Asserts the hardened idempotency behavior (real Postgres + real Redis) for:
  - POST /api/v1/pt-sessions          (record_pt_session, A)
  - POST /api/v1/pt-sessions/{id}/cancel (cancel_pt_session, A)

Assertions per endpoint:
  1. Replay (same key + same body) returns byte-identical cached response.
  2. Replay does NOT re-emit AuditLog rows for the session id.
  3. Same key + different body → 422 idempotency_key_reuse.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit_models import AuditLog
from app.modules.clients.models import Client
from app.modules.pt_packages.models import PtPackage, PtPackagePlan
from app.modules.trainers.models import Trainer

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _csrf_header(client: AsyncClient) -> str:
    return client.cookies.get("clubcore_csrf") or ""


def _headers(client: AsyncClient, *, key: str) -> dict[str, str]:
    return {
        "X-CSRF-Token": _csrf_header(client),
        "Idempotency-Key": key,
    }


async def _audit_count(session: AsyncSession, resource_id: UUID) -> int:
    """Count AuditLog rows for a given resource_id."""
    result = await session.execute(
        select(func.count()).select_from(AuditLog).where(AuditLog.resource_id == resource_id)
    )
    return int(result.scalar_one())


def _record_body(
    pt_package_id: UUID,
    trainer_id: UUID,
    *,
    performed_at: datetime | None = None,
) -> dict[str, Any]:
    at = performed_at or (datetime.now(UTC) - timedelta(minutes=10))
    return {
        "ptPackageId": str(pt_package_id),
        "trainerId": str(trainer_id),
        "performedAt": at.isoformat(),
    }


# ===========================================================================
# record_pt_session — double-submit + no-re-emit-audit + reuse-422
# ===========================================================================


async def test_record_pt_session_double_submit_byte_identical(
    authed_client_owner: AsyncClient,
    db_session: AsyncSession,
    make_client: Callable[..., Awaitable[Client]],
    make_pt_package_plan: Callable[..., Awaitable[PtPackagePlan]],
    make_pt_package: Callable[..., Awaitable[PtPackage]],
    make_trainer: Callable[..., Awaitable[Trainer]],
) -> None:
    """Replay of record_pt_session returns byte-identical cached response."""
    plan = await make_pt_package_plan(session_count=5)
    client_row = await make_client()
    pkg = await make_pt_package(client_id=client_row.id, plan=plan, sessions_remaining=5)
    trainer = await make_trainer()
    key = uuid4().hex  # 32 chars, passes {16,128}

    # Capture a fixed performedAt so both submits send the exact same body
    performed_at = datetime.now(UTC) - timedelta(minutes=10)
    body_json = _record_body(pkg.id, trainer.id, performed_at=performed_at)
    headers = _headers(authed_client_owner, key=key)

    r1 = await authed_client_owner.post("/api/v1/pt-sessions", json=body_json, headers=headers)
    assert r1.status_code == 201, r1.text

    r2 = await authed_client_owner.post("/api/v1/pt-sessions", json=body_json, headers=headers)
    assert r2.status_code == 201, r2.text
    assert r2.content == r1.content, "Replay must return byte-identical content"


async def test_record_pt_session_replay_no_re_emit_audit(
    authed_client_owner: AsyncClient,
    db_session: AsyncSession,
    make_client: Callable[..., Awaitable[Client]],
    make_pt_package_plan: Callable[..., Awaitable[PtPackagePlan]],
    make_pt_package: Callable[..., Awaitable[PtPackage]],
    make_trainer: Callable[..., Awaitable[Trainer]],
) -> None:
    """Replay of record_pt_session does NOT re-emit AuditLog row."""
    plan = await make_pt_package_plan(session_count=5)
    client_row = await make_client()
    pkg = await make_pt_package(client_id=client_row.id, plan=plan, sessions_remaining=5)
    trainer = await make_trainer()
    key = uuid4().hex

    performed_at = datetime.now(UTC) - timedelta(minutes=10)
    body_json = _record_body(pkg.id, trainer.id, performed_at=performed_at)
    headers = _headers(authed_client_owner, key=key)

    r1 = await authed_client_owner.post("/api/v1/pt-sessions", json=body_json, headers=headers)
    assert r1.status_code == 201, r1.text
    session_id = UUID(r1.json()["data"]["id"])

    count_before = await _audit_count(db_session, session_id)
    assert count_before >= 1, "At least one audit row expected after first submit"

    r2 = await authed_client_owner.post("/api/v1/pt-sessions", json=body_json, headers=headers)
    assert r2.status_code == 201, r2.text

    count_after = await _audit_count(db_session, session_id)
    assert count_after == count_before, (
        f"Replay must NOT re-emit audit: before={count_before}, after={count_after}"
    )


async def test_record_pt_session_same_key_different_body_422(
    authed_client_owner: AsyncClient,
    db_session: AsyncSession,
    make_client: Callable[..., Awaitable[Client]],
    make_pt_package_plan: Callable[..., Awaitable[PtPackagePlan]],
    make_pt_package: Callable[..., Awaitable[PtPackage]],
    make_trainer: Callable[..., Awaitable[Trainer]],
) -> None:
    """Same key + different body (different trainer) → 422 idempotency_key_reuse."""
    plan = await make_pt_package_plan(session_count=10)
    client_row = await make_client()
    pkg = await make_pt_package(client_id=client_row.id, plan=plan, sessions_remaining=10)
    trainer_a = await make_trainer()
    trainer_b = await make_trainer()
    key = uuid4().hex

    performed_at = datetime.now(UTC) - timedelta(minutes=10)
    headers = _headers(authed_client_owner, key=key)

    r1 = await authed_client_owner.post(
        "/api/v1/pt-sessions",
        json=_record_body(pkg.id, trainer_a.id, performed_at=performed_at),
        headers=headers,
    )
    assert r1.status_code == 201, r1.text

    r2 = await authed_client_owner.post(
        "/api/v1/pt-sessions",
        json=_record_body(pkg.id, trainer_b.id, performed_at=performed_at),  # different trainer
        headers=headers,
    )
    assert r2.status_code == 422, r2.text
    body = r2.json()
    assert body["code"] == "validation_error"
    assert body["message"] == "idempotency_key_reuse"


# ===========================================================================
# cancel_pt_session — double-submit + no-re-emit-audit + reuse-422
# ===========================================================================


async def _seed_active_session(
    authed: AsyncClient,
    *,
    db_session: AsyncSession,
    make_client: Callable[..., Awaitable[Client]],
    make_pt_package_plan: Callable[..., Awaitable[PtPackagePlan]],
    make_pt_package: Callable[..., Awaitable[PtPackage]],
    make_trainer: Callable[..., Awaitable[Trainer]],
) -> UUID:
    """Seed and record a PT session; return its id."""
    plan = await make_pt_package_plan(session_count=5)
    client_row = await make_client()
    pkg = await make_pt_package(client_id=client_row.id, plan=plan, sessions_remaining=5)
    trainer = await make_trainer()
    performed_at = datetime.now(UTC) - timedelta(minutes=10)

    r = await authed.post(
        "/api/v1/pt-sessions",
        json=_record_body(pkg.id, trainer.id, performed_at=performed_at),
        headers=_headers(authed, key=uuid4().hex),
    )
    assert r.status_code == 201, r.text
    return UUID(r.json()["data"]["id"])


async def test_cancel_pt_session_double_submit_byte_identical(
    authed_client_owner: AsyncClient,
    db_session: AsyncSession,
    make_client: Callable[..., Awaitable[Client]],
    make_pt_package_plan: Callable[..., Awaitable[PtPackagePlan]],
    make_pt_package: Callable[..., Awaitable[PtPackage]],
    make_trainer: Callable[..., Awaitable[Trainer]],
) -> None:
    """Replay of cancel_pt_session returns byte-identical cached response."""
    session_id = await _seed_active_session(
        authed_client_owner,
        db_session=db_session,
        make_client=make_client,
        make_pt_package_plan=make_pt_package_plan,
        make_pt_package=make_pt_package,
        make_trainer=make_trainer,
    )
    key = uuid4().hex
    body_json = {"cancelReason": "owner_cancel_idem_test"}
    headers = _headers(authed_client_owner, key=key)

    r1 = await authed_client_owner.post(
        f"/api/v1/pt-sessions/{session_id}/cancel",
        json=body_json,
        headers=headers,
    )
    assert r1.status_code == 200, r1.text

    r2 = await authed_client_owner.post(
        f"/api/v1/pt-sessions/{session_id}/cancel",
        json=body_json,
        headers=headers,
    )
    assert r2.status_code == 200, r2.text
    assert r2.content == r1.content, "Replay must return byte-identical content"


async def test_cancel_pt_session_replay_no_re_emit_audit(
    authed_client_owner: AsyncClient,
    db_session: AsyncSession,
    make_client: Callable[..., Awaitable[Client]],
    make_pt_package_plan: Callable[..., Awaitable[PtPackagePlan]],
    make_pt_package: Callable[..., Awaitable[PtPackage]],
    make_trainer: Callable[..., Awaitable[Trainer]],
) -> None:
    """Replay of cancel_pt_session does NOT re-emit AuditLog row."""
    session_id = await _seed_active_session(
        authed_client_owner,
        db_session=db_session,
        make_client=make_client,
        make_pt_package_plan=make_pt_package_plan,
        make_pt_package=make_pt_package,
        make_trainer=make_trainer,
    )
    key = uuid4().hex
    body_json = {"cancelReason": "audit_check_cancel"}
    headers = _headers(authed_client_owner, key=key)

    r1 = await authed_client_owner.post(
        f"/api/v1/pt-sessions/{session_id}/cancel",
        json=body_json,
        headers=headers,
    )
    assert r1.status_code == 200, r1.text

    count_before = await _audit_count(db_session, session_id)
    assert count_before >= 1

    r2 = await authed_client_owner.post(
        f"/api/v1/pt-sessions/{session_id}/cancel",
        json=body_json,
        headers=headers,
    )
    assert r2.status_code == 200, r2.text

    count_after = await _audit_count(db_session, session_id)
    assert count_after == count_before, (
        f"Replay must NOT re-emit audit: before={count_before}, after={count_after}"
    )


async def test_cancel_pt_session_same_key_different_body_422(
    authed_client_owner: AsyncClient,
    db_session: AsyncSession,
    make_client: Callable[..., Awaitable[Client]],
    make_pt_package_plan: Callable[..., Awaitable[PtPackagePlan]],
    make_pt_package: Callable[..., Awaitable[PtPackage]],
    make_trainer: Callable[..., Awaitable[Trainer]],
) -> None:
    """Same key + different cancel body → 422 idempotency_key_reuse."""
    session_id = await _seed_active_session(
        authed_client_owner,
        db_session=db_session,
        make_client=make_client,
        make_pt_package_plan=make_pt_package_plan,
        make_pt_package=make_pt_package,
        make_trainer=make_trainer,
    )
    key = uuid4().hex
    headers = _headers(authed_client_owner, key=key)

    r1 = await authed_client_owner.post(
        f"/api/v1/pt-sessions/{session_id}/cancel",
        json={"cancelReason": "reason_alpha"},
        headers=headers,
    )
    assert r1.status_code == 200, r1.text

    r2 = await authed_client_owner.post(
        f"/api/v1/pt-sessions/{session_id}/cancel",
        json={"cancelReason": "reason_beta"},  # different body
        headers=headers,
    )
    assert r2.status_code == 422, r2.text
    body = r2.json()
    assert body["code"] == "validation_error"
    assert body["message"] == "idempotency_key_reuse"
