"""Integration tests for POST /api/v1/pt-sessions (Phase 34 Plan 34-02).

Marquee paths (D-34-04a / D-34-05 / D-34-06 / D-34-10 / D-34-12a / D-34-13a /
D-34-18):

  - Happy path reception: 201 + envelope + pt_sessions row + decrement to
    n-1 + single ``pt_session_recorded`` audit row.
  - Decrement-to-zero: 201 + sessions_remaining=0 + status='exhausted' +
    BOTH ``pt_session_recorded`` AND single ``pt_package_exhausted`` audit
    rows (PT-17 / D-34-05).
  - 409 ``pt_package_not_active`` for exhausted / expired / cancelled
    parent package status (pre-decrement guard fires first).
  - 422 ``trainer_inactive`` for is_active=False trainer.
  - 404 ``trainer_not_found`` for random trainer_id.
  - 422 ``performed_at_in_future`` for future-dated body.
  - 422 ``performed_at_out_of_window`` for reception 8d back; 201 for owner
    same body (B-11).
  - Idempotency-Key replay: same key + same body → 201 + identical body +
    only 1 audit row.
  - Idempotency-Key reuse: same key + different body → 422
    ``idempotency_key_reuse``.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

from httpx import AsyncClient
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit_models import AuditLog
from app.modules.clients.models import Client
from app.modules.pt_packages.models import PtPackage, PtPackagePlan
from app.modules.pt_sessions.models import PtSession
from app.modules.trainers.models import Trainer


def _csrf_headers(
    client: AsyncClient,
    *,
    idempotency_key: str | None = None,
) -> dict[str, str]:
    headers: dict[str, str] = {
        "X-CSRF-Token": client.cookies.get("sportzal_csrf", "") or ""
    }
    if idempotency_key is not None:
        headers["Idempotency-Key"] = idempotency_key
    return headers


def _record_body(
    pt_package_id: UUID,
    trainer_id: UUID,
    *,
    performed_at: datetime | None = None,
    notes: str | None = None,
) -> dict[str, Any]:
    body: dict[str, Any] = {
        "ptPackageId": str(pt_package_id),
        "trainerId": str(trainer_id),
        "performedAt": (
            performed_at or datetime.now(UTC) - timedelta(minutes=10)
        ).isoformat(),
    }
    if notes is not None:
        body["notes"] = notes
    return body


async def test_record_pt_session_happy_path(
    authed_client_reception: AsyncClient,
    db_session: AsyncSession,
    make_client: Callable[..., Awaitable[Client]],
    make_pt_package_plan: Callable[..., Awaitable[PtPackagePlan]],
    make_pt_package: Callable[..., Awaitable[PtPackage]],
    make_trainer: Callable[..., Awaitable[Trainer]],
) -> None:
    """PT-15 / PT-16 happy path: 201 + sessions_remaining decremented + audit row."""
    plan = await make_pt_package_plan(session_count=5)
    client = await make_client()
    pkg = await make_pt_package(client_id=client.id, plan=plan, sessions_remaining=5)
    trainer = await make_trainer(full_name="Иван Петрович")

    idem = uuid4().hex
    r = await authed_client_reception.post(
        "/api/v1/pt-sessions",
        json=_record_body(pkg.id, trainer.id),
        headers=_csrf_headers(authed_client_reception, idempotency_key=idem),
    )
    assert r.status_code == 201, r.text
    data = r.json()["data"]
    assert UUID(data["id"])
    assert data["ptPackageId"] == str(pkg.id)
    assert data["trainerId"] == str(trainer.id)
    assert data["clientId"] == str(client.id)
    assert data["trainerNameSnapshot"] == "Иван Петрович"
    assert data["cancelledAt"] is None
    assert data["cancelReason"] is None

    # sessions_remaining decremented to 4.
    remaining = await db_session.scalar(
        select(PtPackage.sessions_remaining).where(PtPackage.id == pkg.id)
    )
    assert remaining == 4

    # Exactly 1 pt_session_recorded audit row, no pt_package_exhausted.
    recorded = (
        await db_session.scalars(
            select(AuditLog).where(
                AuditLog.action == "pt_session_recorded",
                AuditLog.resource_id == UUID(data["id"]),
            )
        )
    ).all()
    assert len(recorded) == 1
    payload = recorded[0].payload
    assert payload["trainer_name_snapshot"] == "Иван Петрович"
    assert payload["sessions_remaining_after"] == 4

    exhausted_count = await db_session.scalar(
        select(func.count())
        .select_from(AuditLog)
        .where(
            AuditLog.action == "pt_package_exhausted",
            AuditLog.resource_id == pkg.id,
        )
    )
    assert exhausted_count == 0


async def test_record_decrement_to_zero_emits_exhausted(
    authed_client_owner: AsyncClient,
    db_session: AsyncSession,
    make_client: Callable[..., Awaitable[Client]],
    make_pt_package_plan: Callable[..., Awaitable[PtPackagePlan]],
    make_pt_package: Callable[..., Awaitable[PtPackage]],
    make_trainer: Callable[..., Awaitable[Trainer]],
) -> None:
    """PT-17 / D-34-05: decrement reaching 0 transitions to 'exhausted'
    and emits ``pt_package_exhausted`` exactly once."""
    plan = await make_pt_package_plan(session_count=5)
    client = await make_client()
    pkg = await make_pt_package(client_id=client.id, plan=plan, sessions_remaining=1)
    trainer = await make_trainer()

    r = await authed_client_owner.post(
        "/api/v1/pt-sessions",
        json=_record_body(pkg.id, trainer.id),
        headers=_csrf_headers(authed_client_owner, idempotency_key=uuid4().hex),
    )
    assert r.status_code == 201, r.text

    # Reload package from DB.
    db_session.expire_all()
    refreshed = await db_session.scalar(
        select(PtPackage).where(PtPackage.id == pkg.id)
    )
    assert refreshed is not None
    assert refreshed.sessions_remaining == 0
    assert refreshed.status == "exhausted"

    # Exactly 1 pt_session_recorded + exactly 1 pt_package_exhausted.
    recorded_count = await db_session.scalar(
        select(func.count())
        .select_from(AuditLog)
        .where(
            AuditLog.action == "pt_session_recorded",
            AuditLog.resource_id == UUID(r.json()["data"]["id"]),
        )
    )
    assert recorded_count == 1
    exhausted_count = await db_session.scalar(
        select(func.count())
        .select_from(AuditLog)
        .where(
            AuditLog.action == "pt_package_exhausted",
            AuditLog.resource_id == pkg.id,
        )
    )
    assert exhausted_count == 1


async def test_record_against_exhausted_package_returns_409(
    authed_client_owner: AsyncClient,
    make_client: Callable[..., Awaitable[Client]],
    make_pt_package_plan: Callable[..., Awaitable[PtPackagePlan]],
    make_pt_package: Callable[..., Awaitable[PtPackage]],
    make_trainer: Callable[..., Awaitable[Trainer]],
) -> None:
    """D-34-13a: pre-decrement guard surfaces 409 pt_package_not_active for
    exhausted parent package (before atomic UPDATE)."""
    plan = await make_pt_package_plan(session_count=5)
    client = await make_client()
    pkg = await make_pt_package(
        client_id=client.id,
        plan=plan,
        sessions_remaining=0,
        status="exhausted",
    )
    trainer = await make_trainer()
    r = await authed_client_owner.post(
        "/api/v1/pt-sessions",
        json=_record_body(pkg.id, trainer.id),
        headers=_csrf_headers(authed_client_owner, idempotency_key=uuid4().hex),
    )
    assert r.status_code == 409, r.text
    assert r.json()["code"] == "pt_package_not_active"


async def test_record_against_expired_package_returns_409(
    authed_client_owner: AsyncClient,
    make_client: Callable[..., Awaitable[Client]],
    make_pt_package_plan: Callable[..., Awaitable[PtPackagePlan]],
    make_pt_package: Callable[..., Awaitable[PtPackage]],
    make_trainer: Callable[..., Awaitable[Trainer]],
) -> None:
    """D-34-13a: expired parent package → 409 pt_package_not_active."""
    plan = await make_pt_package_plan(session_count=5)
    client = await make_client()
    pkg = await make_pt_package(
        client_id=client.id,
        plan=plan,
        sessions_remaining=2,
        status="expired",
    )
    trainer = await make_trainer()
    r = await authed_client_owner.post(
        "/api/v1/pt-sessions",
        json=_record_body(pkg.id, trainer.id),
        headers=_csrf_headers(authed_client_owner, idempotency_key=uuid4().hex),
    )
    assert r.status_code == 409, r.text
    assert r.json()["code"] == "pt_package_not_active"


async def test_record_against_cancelled_package_returns_409(
    authed_client_owner: AsyncClient,
    make_client: Callable[..., Awaitable[Client]],
    make_pt_package_plan: Callable[..., Awaitable[PtPackagePlan]],
    make_pt_package: Callable[..., Awaitable[PtPackage]],
    make_trainer: Callable[..., Awaitable[Trainer]],
) -> None:
    """D-34-13a: cancelled parent package → 409 pt_package_not_active."""
    plan = await make_pt_package_plan(session_count=5)
    client = await make_client()
    pkg = await make_pt_package(
        client_id=client.id,
        plan=plan,
        sessions_remaining=2,
        status="cancelled",
    )
    trainer = await make_trainer()
    r = await authed_client_owner.post(
        "/api/v1/pt-sessions",
        json=_record_body(pkg.id, trainer.id),
        headers=_csrf_headers(authed_client_owner, idempotency_key=uuid4().hex),
    )
    assert r.status_code == 409, r.text
    assert r.json()["code"] == "pt_package_not_active"


async def test_record_with_inactive_trainer_returns_422(
    authed_client_owner: AsyncClient,
    make_client: Callable[..., Awaitable[Client]],
    make_pt_package_plan: Callable[..., Awaitable[PtPackagePlan]],
    make_pt_package: Callable[..., Awaitable[PtPackage]],
    make_trainer: Callable[..., Awaitable[Trainer]],
) -> None:
    """D-34-12a: deactivated trainer → 422 trainer_inactive."""
    plan = await make_pt_package_plan()
    client = await make_client()
    pkg = await make_pt_package(client_id=client.id, plan=plan)
    trainer = await make_trainer(is_active=False)
    r = await authed_client_owner.post(
        "/api/v1/pt-sessions",
        json=_record_body(pkg.id, trainer.id),
        headers=_csrf_headers(authed_client_owner, idempotency_key=uuid4().hex),
    )
    assert r.status_code == 422, r.text
    assert r.json()["code"] == "trainer_inactive"


async def test_record_with_missing_trainer_returns_404(
    authed_client_owner: AsyncClient,
    make_client: Callable[..., Awaitable[Client]],
    make_pt_package_plan: Callable[..., Awaitable[PtPackagePlan]],
    make_pt_package: Callable[..., Awaitable[PtPackage]],
) -> None:
    """D-34-12a: unknown trainer_id → 404 trainer_not_found."""
    plan = await make_pt_package_plan()
    client = await make_client()
    pkg = await make_pt_package(client_id=client.id, plan=plan)
    r = await authed_client_owner.post(
        "/api/v1/pt-sessions",
        json=_record_body(pkg.id, uuid4()),
        headers=_csrf_headers(authed_client_owner, idempotency_key=uuid4().hex),
    )
    assert r.status_code == 404, r.text
    assert r.json()["code"] == "trainer_not_found"


async def test_record_future_dated_returns_422(
    authed_client_owner: AsyncClient,
    make_client: Callable[..., Awaitable[Client]],
    make_pt_package_plan: Callable[..., Awaitable[PtPackagePlan]],
    make_pt_package: Callable[..., Awaitable[PtPackage]],
    make_trainer: Callable[..., Awaitable[Trainer]],
) -> None:
    """B-11 / D-34-06: future-dated performed_at → 422 performed_at_in_future.

    Applies to both roles — recording a session that has not happened yet
    is a semantic error.
    """
    plan = await make_pt_package_plan()
    client = await make_client()
    pkg = await make_pt_package(client_id=client.id, plan=plan)
    trainer = await make_trainer()
    future = datetime.now(UTC) + timedelta(hours=1)
    r = await authed_client_owner.post(
        "/api/v1/pt-sessions",
        json=_record_body(pkg.id, trainer.id, performed_at=future),
        headers=_csrf_headers(authed_client_owner, idempotency_key=uuid4().hex),
    )
    assert r.status_code == 422, r.text
    assert r.json()["code"] == "performed_at_in_future"


async def test_record_8d_back_as_reception_returns_422(
    authed_client_reception: AsyncClient,
    make_client: Callable[..., Awaitable[Client]],
    make_pt_package_plan: Callable[..., Awaitable[PtPackagePlan]],
    make_pt_package: Callable[..., Awaitable[PtPackage]],
    make_trainer: Callable[..., Awaitable[Trainer]],
) -> None:
    """B-11 / D-34-06: reception 8d back → 422 performed_at_out_of_window."""
    plan = await make_pt_package_plan()
    client = await make_client()
    pkg = await make_pt_package(client_id=client.id, plan=plan)
    trainer = await make_trainer()
    too_old = datetime.now(UTC) - timedelta(days=8)
    r = await authed_client_reception.post(
        "/api/v1/pt-sessions",
        json=_record_body(pkg.id, trainer.id, performed_at=too_old),
        headers=_csrf_headers(authed_client_reception, idempotency_key=uuid4().hex),
    )
    assert r.status_code == 422, r.text
    assert r.json()["code"] == "performed_at_out_of_window"


async def test_record_8d_back_as_owner_returns_201(
    authed_client_owner: AsyncClient,
    make_client: Callable[..., Awaitable[Client]],
    make_pt_package_plan: Callable[..., Awaitable[PtPackagePlan]],
    make_pt_package: Callable[..., Awaitable[PtPackage]],
    make_trainer: Callable[..., Awaitable[Trainer]],
) -> None:
    """B-11 / D-34-06: owner unlimited past — 8d back → 201."""
    plan = await make_pt_package_plan()
    client = await make_client()
    pkg = await make_pt_package(client_id=client.id, plan=plan)
    trainer = await make_trainer()
    eight_days = datetime.now(UTC) - timedelta(days=8)
    r = await authed_client_owner.post(
        "/api/v1/pt-sessions",
        json=_record_body(pkg.id, trainer.id, performed_at=eight_days),
        headers=_csrf_headers(authed_client_owner, idempotency_key=uuid4().hex),
    )
    assert r.status_code == 201, r.text


async def test_record_idempotency_replay_returns_cached_201(
    authed_client_owner: AsyncClient,
    db_session: AsyncSession,
    make_client: Callable[..., Awaitable[Client]],
    make_pt_package_plan: Callable[..., Awaitable[PtPackagePlan]],
    make_pt_package: Callable[..., Awaitable[PtPackage]],
    make_trainer: Callable[..., Awaitable[Trainer]],
) -> None:
    """D-34-10 / D-32-10: same Idempotency-Key + same body → cached 201 replay.

    The replay branch returns the cached body verbatim without invoking
    the orchestrator a second time — only one pt_sessions row, only one
    audit emit. Decrement happens exactly once.
    """
    plan = await make_pt_package_plan(session_count=5)
    client = await make_client()
    pkg = await make_pt_package(client_id=client.id, plan=plan, sessions_remaining=5)
    trainer = await make_trainer()
    idem = uuid4().hex
    body = _record_body(pkg.id, trainer.id)

    r1 = await authed_client_owner.post(
        "/api/v1/pt-sessions",
        json=body,
        headers=_csrf_headers(authed_client_owner, idempotency_key=idem),
    )
    assert r1.status_code == 201, r1.text
    new_id = r1.json()["data"]["id"]

    r2 = await authed_client_owner.post(
        "/api/v1/pt-sessions",
        json=body,
        headers=_csrf_headers(authed_client_owner, idempotency_key=idem),
    )
    assert r2.status_code == 201, r2.text
    assert r2.json()["data"]["id"] == new_id

    # Exactly 1 pt_sessions row.
    rows = (
        await db_session.scalars(
            select(PtSession).where(PtSession.pt_package_id == pkg.id)
        )
    ).all()
    assert len(rows) == 1

    # Decrement happened exactly once.
    remaining = await db_session.scalar(
        text("SELECT sessions_remaining FROM pt_packages WHERE id = :id"),
        {"id": pkg.id},
    )
    assert remaining == 4

    # Only 1 pt_session_recorded audit row.
    recorded_count = await db_session.scalar(
        select(func.count())
        .select_from(AuditLog)
        .where(
            AuditLog.action == "pt_session_recorded",
            AuditLog.resource_id == UUID(new_id),
        )
    )
    assert recorded_count == 1


async def test_record_idempotency_key_reuse_different_body_returns_422(
    authed_client_owner: AsyncClient,
    make_client: Callable[..., Awaitable[Client]],
    make_pt_package_plan: Callable[..., Awaitable[PtPackagePlan]],
    make_pt_package: Callable[..., Awaitable[PtPackage]],
    make_trainer: Callable[..., Awaitable[Trainer]],
) -> None:
    """D-34-10 / CR-02: same key + DIFFERENT body → 422 idempotency_key_reuse."""
    plan = await make_pt_package_plan(session_count=5)
    client = await make_client()
    pkg = await make_pt_package(client_id=client.id, plan=plan, sessions_remaining=5)
    trainer1 = await make_trainer()
    trainer2 = await make_trainer()
    idem = uuid4().hex

    r1 = await authed_client_owner.post(
        "/api/v1/pt-sessions",
        json=_record_body(pkg.id, trainer1.id),
        headers=_csrf_headers(authed_client_owner, idempotency_key=idem),
    )
    assert r1.status_code == 201, r1.text

    r2 = await authed_client_owner.post(
        "/api/v1/pt-sessions",
        json=_record_body(pkg.id, trainer2.id),
        headers=_csrf_headers(authed_client_owner, idempotency_key=idem),
    )
    assert r2.status_code == 422, r2.text
    assert r2.json()["code"] == "idempotency_key_reuse"
