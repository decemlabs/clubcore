"""Integration tests for POST /api/v1/pt-sessions/{id}/cancel (Plan 34-03).

PT-18 cancel flow + D-34-07 24h-from-`created_at` window for reception +
D-34-11a predicate-gated `exhausted → active` reverse transition +
package_reactivated audit-payload signal:

  - Reception happy path within 24h → 200 + sessions_remaining +1 +
    audit pt_session_cancelled (package_reactivated=False since prior
    status was 'active').
  - Reception 25h post recording → 403 cancel_window_expired (B-12 from
    `created_at`, NOT `performed_at`).
  - Owner 25h post recording → 200 (owner anytime).
  - Cancel session of exhausted-pkg → 200, sessions_remaining +1,
    package status flips back 'exhausted'→'active', payload
    package_reactivated=True (D-34-11a).
  - Cancel session of cancelled-pkg (refunded) → 200, balance still
    incremented (data integrity), status STAYS 'cancelled',
    package_reactivated=False.
  - Already cancelled → 409 already_cancelled.
  - Missing session id → 404 pt_session_not_found.
  - Idempotency-Key replay → same response body, only one audit row,
    balance incremented exactly once.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
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


async def _seed_pt_session_directly(
    db_session: AsyncSession,
    *,
    pt_package_id: UUID,
    trainer_id: UUID,
    client_id: UUID,
    performed_by_user_id: UUID,
    trainer_name_snapshot: str,
    created_at: datetime,
    performed_at: datetime | None = None,
) -> UUID:
    """INSERT a pt_sessions row with an explicit created_at timestamp.

    Used to bypass the real-time clock so cancel-window tests can stage
    "25-hour-old" sessions without sleeping.
    """
    pt_session_id = uuid4()
    performed = performed_at or created_at
    await db_session.execute(
        text(
            "INSERT INTO pt_sessions (id, pt_package_id, trainer_id, "
            "client_id, performed_at, performed_by_user_id, "
            "trainer_name_snapshot, notes, created_at, updated_at) "
            "VALUES (:id, :pkg, :trn, :cli, :perf, :uid, :name, NULL, "
            ":created, :created)"
        ),
        {
            "id": pt_session_id,
            "pkg": pt_package_id,
            "trn": trainer_id,
            "cli": client_id,
            "perf": performed,
            "uid": performed_by_user_id,
            "name": trainer_name_snapshot,
            "created": created_at,
        },
    )
    await db_session.flush()
    return pt_session_id


async def test_cancel_pt_session_happy_path_reception_within_24h(
    authed_client_reception: AsyncClient,
    db_session: AsyncSession,
    make_client: Callable[..., Awaitable[Client]],
    make_pt_package_plan: Callable[..., Awaitable[PtPackagePlan]],
    make_pt_package: Callable[..., Awaitable[PtPackage]],
    make_trainer: Callable[..., Awaitable[Trainer]],
) -> None:
    """PT-18 happy path: reception records + cancels same session in <24h."""
    plan = await make_pt_package_plan(session_count=5)
    client = await make_client()
    pkg = await make_pt_package(
        client_id=client.id, plan=plan, sessions_remaining=5
    )
    trainer = await make_trainer(full_name="Иван Иванович")

    # Record via HTTP so created_at is "now-ish".
    r_rec = await authed_client_reception.post(
        "/api/v1/pt-sessions",
        json={
            "ptPackageId": str(pkg.id),
            "trainerId": str(trainer.id),
            "performedAt": (datetime.now(UTC) - timedelta(minutes=5)).isoformat(),
        },
        headers=_csrf_headers(authed_client_reception, idempotency_key=uuid4().hex),
    )
    assert r_rec.status_code == 201, r_rec.text
    pt_session_id = UUID(r_rec.json()["data"]["id"])

    # Cancel.
    r_cancel = await authed_client_reception.post(
        f"/api/v1/pt-sessions/{pt_session_id}/cancel",
        json={"cancel_reason": "client_request"},
        headers=_csrf_headers(authed_client_reception, idempotency_key=uuid4().hex),
    )
    assert r_cancel.status_code == 200, r_cancel.text
    data = r_cancel.json()["data"]
    assert data["cancelledAt"] is not None
    assert data["cancelReason"] == "client_request"

    # sessions_remaining restored to 5 (was 4 after record).
    # 38-06 DEFER fix: removed expire_all to avoid MissingGreenlet in SAVEPOINT-mode session
    remaining = await db_session.scalar(
        select(PtPackage.sessions_remaining).where(PtPackage.id == pkg.id)
    )
    assert remaining == 5

    # Single pt_session_cancelled audit row; package_reactivated=False.
    rows = (
        await db_session.scalars(
            select(AuditLog).where(
                AuditLog.action == "pt_session_cancelled",
                AuditLog.resource_id == pt_session_id,
            )
        )
    ).all()
    assert len(rows) == 1
    payload = rows[0].payload
    assert payload["cancel_reason"] == "client_request"
    assert payload["sessions_remaining_after"] == 5
    assert payload["package_reactivated"] is False


async def test_cancel_25h_old_as_reception_returns_403(
    authed_client_reception: AsyncClient,
    db_session: AsyncSession,
    make_client: Callable[..., Awaitable[Client]],
    make_pt_package_plan: Callable[..., Awaitable[PtPackagePlan]],
    make_pt_package: Callable[..., Awaitable[PtPackage]],
    make_trainer: Callable[..., Awaitable[Trainer]],
    make_user: Callable[..., Awaitable[object]],
) -> None:
    """D-34-07 / B-12: reception >24h since pt_session.created_at → 403."""
    plan = await make_pt_package_plan(session_count=5)
    client = await make_client()
    pkg = await make_pt_package(client_id=client.id, plan=plan, sessions_remaining=4)
    trainer = await make_trainer()
    operator = await make_user(role="reception")
    pt_session_id = await _seed_pt_session_directly(
        db_session,
        pt_package_id=pkg.id,
        trainer_id=trainer.id,
        client_id=client.id,
        performed_by_user_id=operator.id,  # type: ignore[attr-defined]
        trainer_name_snapshot=trainer.full_name,
        created_at=datetime.now(UTC) - timedelta(hours=25),
    )

    r = await authed_client_reception.post(
        f"/api/v1/pt-sessions/{pt_session_id}/cancel",
        json={"cancel_reason": "too late"},
        headers=_csrf_headers(authed_client_reception, idempotency_key=uuid4().hex),
    )
    assert r.status_code == 403, r.text
    assert r.json()["code"] == "cancel_window_expired"


async def test_cancel_25h_old_as_owner_returns_200(
    authed_client_owner: AsyncClient,
    db_session: AsyncSession,
    make_client: Callable[..., Awaitable[Client]],
    make_pt_package_plan: Callable[..., Awaitable[PtPackagePlan]],
    make_pt_package: Callable[..., Awaitable[PtPackage]],
    make_trainer: Callable[..., Awaitable[Trainer]],
    make_user: Callable[..., Awaitable[object]],
) -> None:
    """D-34-07: owner is anytime — 25h-old session cancels successfully."""
    plan = await make_pt_package_plan(session_count=5)
    client = await make_client()
    pkg = await make_pt_package(client_id=client.id, plan=plan, sessions_remaining=4)
    trainer = await make_trainer()
    operator = await make_user(role="reception")
    pt_session_id = await _seed_pt_session_directly(
        db_session,
        pt_package_id=pkg.id,
        trainer_id=trainer.id,
        client_id=client.id,
        performed_by_user_id=operator.id,  # type: ignore[attr-defined]
        trainer_name_snapshot=trainer.full_name,
        created_at=datetime.now(UTC) - timedelta(hours=25),
    )

    r = await authed_client_owner.post(
        f"/api/v1/pt-sessions/{pt_session_id}/cancel",
        json={"cancel_reason": "operator correction"},
        headers=_csrf_headers(authed_client_owner, idempotency_key=uuid4().hex),
    )
    assert r.status_code == 200, r.text
    # 38-06 DEFER fix: removed expire_all to avoid MissingGreenlet in SAVEPOINT-mode session
    remaining = await db_session.scalar(
        select(PtPackage.sessions_remaining).where(PtPackage.id == pkg.id)
    )
    assert remaining == 5


async def test_cancel_session_of_exhausted_package_reactivates(
    authed_client_owner: AsyncClient,
    db_session: AsyncSession,
    make_client: Callable[..., Awaitable[Client]],
    make_pt_package_plan: Callable[..., Awaitable[PtPackagePlan]],
    make_pt_package: Callable[..., Awaitable[PtPackage]],
    make_trainer: Callable[..., Awaitable[Trainer]],
    make_user: Callable[..., Awaitable[object]],
) -> None:
    """D-34-11a: cancelling a session of an EXHAUSTED package flips it
    back to active and emits package_reactivated=True in the audit row."""
    plan = await make_pt_package_plan(session_count=5)
    client = await make_client()
    pkg = await make_pt_package(
        client_id=client.id,
        plan=plan,
        status="exhausted",
        sessions_remaining=0,
    )
    trainer = await make_trainer()
    operator = await make_user(role="reception")
    pt_session_id = await _seed_pt_session_directly(
        db_session,
        pt_package_id=pkg.id,
        trainer_id=trainer.id,
        client_id=client.id,
        performed_by_user_id=operator.id,  # type: ignore[attr-defined]
        trainer_name_snapshot=trainer.full_name,
        created_at=datetime.now(UTC) - timedelta(minutes=5),
    )

    r = await authed_client_owner.post(
        f"/api/v1/pt-sessions/{pt_session_id}/cancel",
        json={"cancel_reason": "client_request"},
        headers=_csrf_headers(authed_client_owner, idempotency_key=uuid4().hex),
    )
    assert r.status_code == 200, r.text

    # Package status flipped back to active; sessions_remaining=1.
    # 38-06 DEFER fix: use refresh() with targeted attribute_names instead of
    # expire_all() — pattern established in 38-02 SUMMARY deviation #3. The
    # cross-module raw UPDATE bypasses the ORM identity map; refresh forces
    # SA to overwrite attributes from the underlying row.
    await db_session.refresh(pkg, attribute_names=["status", "sessions_remaining"])
    assert pkg.status == "active"
    assert pkg.sessions_remaining == 1

    # Audit payload carries package_reactivated=True.
    rows = (
        await db_session.scalars(
            select(AuditLog).where(
                AuditLog.action == "pt_session_cancelled",
                AuditLog.resource_id == pt_session_id,
            )
        )
    ).all()
    assert len(rows) == 1
    assert rows[0].payload["package_reactivated"] is True
    assert rows[0].payload["sessions_remaining_after"] == 1


async def test_cancel_session_of_cancelled_package_keeps_cancelled(
    authed_client_owner: AsyncClient,
    db_session: AsyncSession,
    make_client: Callable[..., Awaitable[Client]],
    make_pt_package_plan: Callable[..., Awaitable[PtPackagePlan]],
    make_pt_package: Callable[..., Awaitable[PtPackage]],
    make_trainer: Callable[..., Awaitable[Trainer]],
    make_user: Callable[..., Awaitable[object]],
) -> None:
    """D-34-11 §"cancelled / expired": balance increment still happens (data
    integrity) but package status STAYS 'cancelled' and the audit payload
    carries package_reactivated=False (correctness over intent — T-34-K)."""
    plan = await make_pt_package_plan(session_count=5)
    client = await make_client()
    pkg = await make_pt_package(
        client_id=client.id,
        plan=plan,
        status="cancelled",
        sessions_remaining=4,
    )
    trainer = await make_trainer()
    operator = await make_user(role="reception")
    pt_session_id = await _seed_pt_session_directly(
        db_session,
        pt_package_id=pkg.id,
        trainer_id=trainer.id,
        client_id=client.id,
        performed_by_user_id=operator.id,  # type: ignore[attr-defined]
        trainer_name_snapshot=trainer.full_name,
        created_at=datetime.now(UTC) - timedelta(minutes=5),
    )

    r = await authed_client_owner.post(
        f"/api/v1/pt-sessions/{pt_session_id}/cancel",
        json={"cancel_reason": "audit correction"},
        headers=_csrf_headers(authed_client_owner, idempotency_key=uuid4().hex),
    )
    assert r.status_code == 200, r.text

    # Balance incremented; status UNCHANGED.
    # 38-06 DEFER fix: use refresh() with targeted attribute_names (38-02 deviation #3).
    await db_session.refresh(pkg, attribute_names=["status", "sessions_remaining"])
    assert pkg.status == "cancelled"  # terminal — stays
    assert pkg.sessions_remaining == 5

    # package_reactivated=False.
    rows = (
        await db_session.scalars(
            select(AuditLog).where(
                AuditLog.action == "pt_session_cancelled",
                AuditLog.resource_id == pt_session_id,
            )
        )
    ).all()
    assert len(rows) == 1
    assert rows[0].payload["package_reactivated"] is False


async def test_cancel_already_cancelled_session_returns_409(
    authed_client_owner: AsyncClient,
    db_session: AsyncSession,
    make_client: Callable[..., Awaitable[Client]],
    make_pt_package_plan: Callable[..., Awaitable[PtPackagePlan]],
    make_pt_package: Callable[..., Awaitable[PtPackage]],
    make_trainer: Callable[..., Awaitable[Trainer]],
) -> None:
    """409 already_cancelled when the session has been cancelled previously."""
    plan = await make_pt_package_plan(session_count=5)
    client = await make_client()
    pkg = await make_pt_package(client_id=client.id, plan=plan, sessions_remaining=5)
    trainer = await make_trainer()

    r_rec = await authed_client_owner.post(
        "/api/v1/pt-sessions",
        json={
            "ptPackageId": str(pkg.id),
            "trainerId": str(trainer.id),
            "performedAt": (datetime.now(UTC) - timedelta(minutes=5)).isoformat(),
        },
        headers=_csrf_headers(authed_client_owner, idempotency_key=uuid4().hex),
    )
    assert r_rec.status_code == 201
    pt_session_id = UUID(r_rec.json()["data"]["id"])

    r1 = await authed_client_owner.post(
        f"/api/v1/pt-sessions/{pt_session_id}/cancel",
        json={"cancel_reason": "first"},
        headers=_csrf_headers(authed_client_owner, idempotency_key=uuid4().hex),
    )
    assert r1.status_code == 200, r1.text

    r2 = await authed_client_owner.post(
        f"/api/v1/pt-sessions/{pt_session_id}/cancel",
        json={"cancel_reason": "second"},
        headers=_csrf_headers(authed_client_owner, idempotency_key=uuid4().hex),
    )
    assert r2.status_code == 409, r2.text
    assert r2.json()["code"] == "already_cancelled"


async def test_cancel_missing_session_returns_404(
    authed_client_owner: AsyncClient,
) -> None:
    """404 pt_session_not_found for unknown id."""
    r = await authed_client_owner.post(
        f"/api/v1/pt-sessions/{uuid4()}/cancel",
        json={"cancel_reason": "ghost"},
        headers=_csrf_headers(authed_client_owner, idempotency_key=uuid4().hex),
    )
    assert r.status_code == 404, r.text
    assert r.json()["code"] == "pt_session_not_found"


async def test_cancel_idempotency_replay_returns_cached_200(
    authed_client_owner: AsyncClient,
    db_session: AsyncSession,
    make_client: Callable[..., Awaitable[Client]],
    make_pt_package_plan: Callable[..., Awaitable[PtPackagePlan]],
    make_pt_package: Callable[..., Awaitable[PtPackage]],
    make_trainer: Callable[..., Awaitable[Trainer]],
) -> None:
    """D-34-10: same Idempotency-Key + same body on /cancel → 200 replay
    + one pt_session_cancelled audit row + balance incremented once."""
    plan = await make_pt_package_plan(session_count=5)
    client = await make_client()
    pkg = await make_pt_package(client_id=client.id, plan=plan, sessions_remaining=5)
    trainer = await make_trainer()

    r_rec = await authed_client_owner.post(
        "/api/v1/pt-sessions",
        json={
            "ptPackageId": str(pkg.id),
            "trainerId": str(trainer.id),
            "performedAt": (datetime.now(UTC) - timedelta(minutes=5)).isoformat(),
        },
        headers=_csrf_headers(authed_client_owner, idempotency_key=uuid4().hex),
    )
    assert r_rec.status_code == 201
    pt_session_id = UUID(r_rec.json()["data"]["id"])

    idem = uuid4().hex
    body = {"cancel_reason": "user requested"}
    r1 = await authed_client_owner.post(
        f"/api/v1/pt-sessions/{pt_session_id}/cancel",
        json=body,
        headers=_csrf_headers(authed_client_owner, idempotency_key=idem),
    )
    assert r1.status_code == 200, r1.text
    cancelled_at_1 = r1.json()["data"]["cancelledAt"]

    r2 = await authed_client_owner.post(
        f"/api/v1/pt-sessions/{pt_session_id}/cancel",
        json=body,
        headers=_csrf_headers(authed_client_owner, idempotency_key=idem),
    )
    assert r2.status_code == 200, r2.text
    # Identical cached body — same cancelledAt.
    assert r2.json()["data"]["cancelledAt"] == cancelled_at_1

    # Single audit row (no double-emit).
    # 38-06 DEFER fix: removed expire_all to avoid MissingGreenlet in SAVEPOINT-mode session
    audit_count = await db_session.scalar(
        select(func.count())
        .select_from(AuditLog)
        .where(
            AuditLog.action == "pt_session_cancelled",
            AuditLog.resource_id == pt_session_id,
        )
    )
    assert audit_count == 1

    # Balance incremented exactly once (back to 5 after the single record + single cancel).
    remaining = await db_session.scalar(
        select(PtPackage.sessions_remaining).where(PtPackage.id == pkg.id)
    )
    assert remaining == 5

    # Single pt_sessions row referenced (no extra cancel-side INSERT).
    rows = (
        await db_session.scalars(
            select(PtSession).where(PtSession.id == pt_session_id)
        )
    ).all()
    assert len(rows) == 1
