"""Integration tests for POST /api/v1/pt-packages/{id}/refund (Phase 33 PT-13 / REF-02).

D-33-11 refund flow:
  - Reception+owner per B-07 ((REFUND, PT_PACKAGES) NOT in OWNER_ONLY).
  - CSRF + Idempotency-Key required per D-33-16.
  - Consumes get_payment_refunder() Protocol slot (modules-independent —
    pt_packages/* does NOT import app.modules.payments.*).
  - Transitions status='cancelled' + cancellation_reason=CANCELLATION_REASON_REFUNDED
    ('refunded' sentinel — distinguishable from operator cancel free-text).
  - 3-row audit chain: payment_recorded (sale) → refund_issued (payment-side,
    in issue_refund) → pt_package_refunded (subject-side, in orchestrator).
  - payment_row_hash SHA-256 forensic anchor on the refund-side audit row.
  - 409 already_refunded surfaced via uq_payments_refund_of_alive partial
    UNIQUE (REF-TEST-02 covers the concurrent race in test_pt_package_refund_race.py).
"""

from __future__ import annotations

import re
from collections.abc import Awaitable, Callable
from typing import Any
from uuid import UUID, uuid4

from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit_models import AuditLog
from app.modules.clients.models import Client
from app.modules.payments.constants import (
    SUBJECT_KIND_PT_PACKAGE,
    SUBJECT_KIND_REFUND,
)
from app.modules.payments.models import Payment
from app.modules.pt_packages.models import PtPackage, PtPackagePlan

_PAYMENT_ROW_HASH_RE = re.compile(r"^sha256:[0-9a-f]{64}$")


def _csrf_headers(client: AsyncClient, *, idempotency_key: str | None = None) -> dict[str, str]:
    headers: dict[str, str] = {"X-CSRF-Token": client.cookies.get("clubcore_csrf", "") or ""}
    if idempotency_key is not None:
        headers["Idempotency-Key"] = idempotency_key
    return headers


async def _sell_pt_package(
    authed: AsyncClient,
    *,
    client_id: UUID,
    plan: PtPackagePlan,
) -> UUID:
    """Sell a PT-package via the real HTTP sale flow.

    W4 compliance: the sale endpoint internally calls
    ``get_payment_recorder()`` (Protocol-slot path) which inserts the
    original payment row + emits ``payment_recorded`` audit. Using the
    HTTP sale ensures the seeded sale row has the correct
    ``payment_row_hash`` derivation surface for the refund audit chain
    assertions (NOT a raw ``session.execute(insert(Payment))``).
    """
    r = await authed.post(
        "/api/v1/pt-packages",
        json={
            "clientId": str(client_id),
            "planId": str(plan.id),
            "amountKopecks": plan.price_kopecks,
        },
        headers=_csrf_headers(authed, idempotency_key=uuid4().hex),
    )
    assert r.status_code == 201, r.text
    return UUID(r.json()["data"]["id"])


# --- happy paths -------------------------------------------------------------


async def test_refund_pt_package_owner_happy_path_active(
    authed_client_owner: AsyncClient,
    db_session: AsyncSession,
    make_client: Callable[..., Awaitable[Client]],
    make_pt_package_plan: Callable[..., Awaitable[PtPackagePlan]],
) -> None:
    """REF-02 happy path from active source — 200, sentinel reason, refund row, audit emit."""
    plan = await make_pt_package_plan(name="refund-active")
    client = await make_client()
    pt_package_id = await _sell_pt_package(authed_client_owner, client_id=client.id, plan=plan)

    r = await authed_client_owner.post(
        f"/api/v1/pt-packages/{pt_package_id}/refund",
        json={"reason": "client_dispute"},
        headers=_csrf_headers(authed_client_owner, idempotency_key=uuid4().hex),
    )
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert data["status"] == "cancelled"
    # Sentinel — NOT free-text "client_dispute".
    assert data["cancellationReason"] == "refunded"
    assert data["isActive"] is False

    # DB invariants — refund Payment row with negative amount + refund_of FK.
    payments = (
        await db_session.scalars(select(Payment).where(Payment.subject_id == pt_package_id))
    ).all()
    sale_rows = [p for p in payments if p.subject_kind == SUBJECT_KIND_PT_PACKAGE]
    refund_rows = [p for p in payments if p.subject_kind == SUBJECT_KIND_REFUND]
    assert len(sale_rows) == 1
    assert len(refund_rows) == 1
    assert refund_rows[0].amount_kopecks == -sale_rows[0].amount_kopecks
    assert refund_rows[0].refund_of == sale_rows[0].id
    # Append-only: original sale row unchanged.
    assert sale_rows[0].amount_kopecks > 0

    # Audit row.
    audit_rows = (
        await db_session.scalars(
            select(AuditLog).where(
                AuditLog.action == "pt_package_refunded",
                AuditLog.resource_id == pt_package_id,
            )
        )
    ).all()
    assert len(audit_rows) == 1
    payload = audit_rows[0].payload
    assert set(payload.keys()) == {
        "pt_package_id",
        "client_id",
        "refund_payment_id",
        "reason",
    }
    assert payload["reason"] == "client_dispute"
    assert payload["refund_payment_id"] == str(refund_rows[0].id)


async def test_refund_pt_package_reception_happy_path_active(
    authed_client_reception: AsyncClient,
    db_session: AsyncSession,
    make_client: Callable[..., Awaitable[Client]],
    make_pt_package_plan: Callable[..., Awaitable[PtPackagePlan]],
) -> None:
    """B-07: (REFUND, PT_PACKAGES) NOT in OWNER_ONLY → reception 200."""
    plan = await make_pt_package_plan(name="refund-reception")
    client = await make_client()
    pt_package_id = await _sell_pt_package(authed_client_reception, client_id=client.id, plan=plan)

    r = await authed_client_reception.post(
        f"/api/v1/pt-packages/{pt_package_id}/refund",
        json={"reason": "reception_refund_path"},
        headers=_csrf_headers(authed_client_reception, idempotency_key=uuid4().hex),
    )
    assert r.status_code == 200, r.text
    assert r.json()["data"]["status"] == "cancelled"


async def test_refund_pt_package_exhausted_owner_happy_path(
    authed_client_owner: AsyncClient,
    db_session: AsyncSession,
    make_client: Callable[..., Awaitable[Client]],
    make_pt_package_plan: Callable[..., Awaitable[PtPackagePlan]],
) -> None:
    """D-33-04 exhausted → cancelled allowed; refund flow transitions ok."""
    plan = await make_pt_package_plan(name="refund-exhausted")
    client = await make_client()
    pt_package_id = await _sell_pt_package(authed_client_owner, client_id=client.id, plan=plan)

    # Flip status to exhausted directly (Phase 34 PT-session decrement
    # path doesn't exist yet — simulate the terminal exhausted state).
    pkg = (
        await db_session.execute(select(PtPackage).where(PtPackage.id == pt_package_id))
    ).scalar_one()
    pkg.status = "exhausted"
    pkg.sessions_remaining = 0
    await db_session.commit()

    r = await authed_client_owner.post(
        f"/api/v1/pt-packages/{pt_package_id}/refund",
        json={"reason": "refund_of_exhausted"},
        headers=_csrf_headers(authed_client_owner, idempotency_key=uuid4().hex),
    )
    assert r.status_code == 200, r.text
    assert r.json()["data"]["status"] == "cancelled"


async def test_refund_pt_package_expired_owner_happy_path(
    authed_client_owner: AsyncClient,
    db_session: AsyncSession,
    make_client: Callable[..., Awaitable[Client]],
    make_pt_package_plan: Callable[..., Awaitable[PtPackagePlan]],
) -> None:
    """D-33-04 expired → cancelled allowed; refund flow transitions ok."""
    plan = await make_pt_package_plan(name="refund-expired")
    client = await make_client()
    pt_package_id = await _sell_pt_package(authed_client_owner, client_id=client.id, plan=plan)

    # Flip status to expired directly (ARQ cron path; simulate terminal state).
    pkg = (
        await db_session.execute(select(PtPackage).where(PtPackage.id == pt_package_id))
    ).scalar_one()
    pkg.status = "expired"
    await db_session.commit()

    r = await authed_client_owner.post(
        f"/api/v1/pt-packages/{pt_package_id}/refund",
        json={"reason": "refund_of_expired"},
        headers=_csrf_headers(authed_client_owner, idempotency_key=uuid4().hex),
    )
    assert r.status_code == 200, r.text


# --- 4xx surfaces -----------------------------------------------------------


async def test_refund_pt_package_already_cancelled_409(
    authed_client_owner: AsyncClient,
    db_session: AsyncSession,
    make_client: Callable[..., Awaitable[Client]],
    make_pt_package_plan: Callable[..., Awaitable[PtPackagePlan]],
) -> None:
    """Cancelled source → 409 invalid_transition (FSM guard fires BEFORE refunder).

    NOT 409 already_refunded — that surface is only for concurrent races
    (REF-TEST-02). The already-cancelled instance is caught at the service
    layer's _assert_can_transition guard.
    """
    plan = await make_pt_package_plan(name="refund-cancelled")
    client = await make_client()
    pt_package_id = await _sell_pt_package(authed_client_owner, client_id=client.id, plan=plan)

    # Cancel via the admin path first.
    r1 = await authed_client_owner.post(
        f"/api/v1/pt-packages/{pt_package_id}/cancel",
        json={"reason": "admin_cancel"},
        headers=_csrf_headers(authed_client_owner, idempotency_key=uuid4().hex),
    )
    assert r1.status_code == 200, r1.text

    # Now attempt to refund — FSM guard rejects.
    r2 = await authed_client_owner.post(
        f"/api/v1/pt-packages/{pt_package_id}/refund",
        json={"reason": "should_be_blocked"},
        headers=_csrf_headers(authed_client_owner, idempotency_key=uuid4().hex),
    )
    assert r2.status_code == 409, r2.text
    body = r2.json()
    assert body["code"] == "invalid_transition"


async def test_refund_pt_package_no_original_payment_404(
    authed_client_owner: AsyncClient,
    db_session: AsyncSession,
    make_client: Callable[..., Awaitable[Client]],
    make_pt_package_plan: Callable[..., Awaitable[PtPackagePlan]],
    make_pt_package: Callable[..., Awaitable[PtPackage]],
) -> None:
    """PT-package without original payment row → 404 original_payment_not_found.

    Seeds a pt_packages row via factory (NO sale flow, NO payment row), then
    POST /refund — the refunder raises OriginalPaymentNotFoundError which the
    AppError handler maps to 404.
    """
    plan = await make_pt_package_plan(name="refund-no-payment")
    client = await make_client()
    pkg = await make_pt_package(client_id=client.id, plan=plan, status="active")

    r = await authed_client_owner.post(
        f"/api/v1/pt-packages/{pkg.id}/refund",
        json={"reason": "no_sale_row"},
        headers=_csrf_headers(authed_client_owner, idempotency_key=uuid4().hex),
    )
    assert r.status_code == 404, r.text
    assert r.json()["code"] == "original_payment_not_found"


async def test_refund_pt_package_second_attempt_409(
    authed_client_owner: AsyncClient,
    db_session: AsyncSession,
    make_client: Callable[..., Awaitable[Client]],
    make_pt_package_plan: Callable[..., Awaitable[PtPackagePlan]],
) -> None:
    """Second refund on same instance → 409 invalid_transition (FSM wins).

    After the first refund the instance is cancelled, so the second attempt
    is caught by the FSM guard BEFORE reaching the DB partial UNIQUE. The
    concurrent-race case (which DOES surface 409 already_refunded via the
    partial UNIQUE) is covered by REF-TEST-02.
    """
    plan = await make_pt_package_plan(name="refund-second")
    client = await make_client()
    pt_package_id = await _sell_pt_package(authed_client_owner, client_id=client.id, plan=plan)

    r1 = await authed_client_owner.post(
        f"/api/v1/pt-packages/{pt_package_id}/refund",
        json={"reason": "first"},
        headers=_csrf_headers(authed_client_owner, idempotency_key=uuid4().hex),
    )
    assert r1.status_code == 200, r1.text

    r2 = await authed_client_owner.post(
        f"/api/v1/pt-packages/{pt_package_id}/refund",
        json={"reason": "second"},
        headers=_csrf_headers(authed_client_owner, idempotency_key=uuid4().hex),
    )
    assert r2.status_code == 409, r2.text
    assert r2.json()["code"] == "invalid_transition"

    # Exactly one refund payment row exists (the second was guard-rejected
    # BEFORE reaching the DB).
    refund_count = await db_session.scalar(
        select(func.count())
        .select_from(Payment)
        .where(
            Payment.subject_id == pt_package_id,
            Payment.subject_kind == SUBJECT_KIND_REFUND,
        )
    )
    assert refund_count == 1


async def test_refund_pt_package_idempotency_replay(
    authed_client_owner: AsyncClient,
    db_session: AsyncSession,
    make_client: Callable[..., Awaitable[Client]],
    make_pt_package_plan: Callable[..., Awaitable[PtPackagePlan]],
) -> None:
    """D-33-16 same Idempotency-Key + same body → cached envelope, NO duplicate side effects."""
    plan = await make_pt_package_plan(name="refund-idem")
    client = await make_client()
    pt_package_id = await _sell_pt_package(authed_client_owner, client_id=client.id, plan=plan)
    idem = uuid4().hex
    body: dict[str, Any] = {"reason": "idem_test"}

    r1 = await authed_client_owner.post(
        f"/api/v1/pt-packages/{pt_package_id}/refund",
        json=body,
        headers=_csrf_headers(authed_client_owner, idempotency_key=idem),
    )
    assert r1.status_code == 200, r1.text

    # Replay: same key + same body → cached envelope.
    r2 = await authed_client_owner.post(
        f"/api/v1/pt-packages/{pt_package_id}/refund",
        json=body,
        headers=_csrf_headers(authed_client_owner, idempotency_key=idem),
    )
    assert r2.status_code == 200, r2.text
    assert r1.json() == r2.json()

    # Exactly 1 refund payment row + 1 pt_package_refunded audit row.
    refund_count = await db_session.scalar(
        select(func.count())
        .select_from(Payment)
        .where(
            Payment.subject_id == pt_package_id,
            Payment.subject_kind == SUBJECT_KIND_REFUND,
        )
    )
    assert refund_count == 1
    audit_count = await db_session.scalar(
        select(func.count())
        .select_from(AuditLog)
        .where(
            AuditLog.action == "pt_package_refunded",
            AuditLog.resource_id == pt_package_id,
        )
    )
    assert audit_count == 1


# --- audit chain forensic integrity -----------------------------------------


async def test_refund_pt_package_audit_chain_traceable(
    authed_client_owner: AsyncClient,
    db_session: AsyncSession,
    make_client: Callable[..., Awaitable[Client]],
    make_pt_package_plan: Callable[..., Awaitable[PtPackagePlan]],
) -> None:
    """REF-07 / D-32-02: 3-row audit chain payment_recorded → refund_issued → pt_package_refunded.

    Postgres ``now()`` is transaction-stable so created_at WITHIN a UoW is
    identical across rows; the forensic invariant is presence of all 3
    LOCKED event names across the chain (across the sale UoW and the refund
    UoW). The refund-side ``refund_issued`` payload carries the SHA-256
    ``payment_row_hash`` over the original sale row's 8 stable columns
    (D-30-04 forensic anchor).
    """
    plan = await make_pt_package_plan(name="refund-chain")
    client = await make_client()
    pt_package_id = await _sell_pt_package(authed_client_owner, client_id=client.id, plan=plan)

    # Fetch the sale payment to seed the resource_id filter.
    sale_payment = (
        await db_session.execute(
            select(Payment).where(
                Payment.subject_kind == SUBJECT_KIND_PT_PACKAGE,
                Payment.subject_id == pt_package_id,
                Payment.amount_kopecks > 0,
            )
        )
    ).scalar_one()

    r = await authed_client_owner.post(
        f"/api/v1/pt-packages/{pt_package_id}/refund",
        json={"reason": "forensic_chain"},
        headers=_csrf_headers(authed_client_owner, idempotency_key=uuid4().hex),
    )
    assert r.status_code == 200, r.text

    refund_payment = (
        await db_session.execute(
            select(Payment).where(
                Payment.subject_kind == SUBJECT_KIND_REFUND,
                Payment.subject_id == pt_package_id,
            )
        )
    ).scalar_one()

    rows = (
        (
            await db_session.execute(
                select(AuditLog)
                .where(
                    AuditLog.action.in_(
                        [
                            "payment_recorded",
                            "refund_issued",
                            "pt_package_refunded",
                        ]
                    ),
                    AuditLog.resource_id.in_([pt_package_id, sale_payment.id, refund_payment.id]),
                )
                .order_by(AuditLog.created_at.asc())
            )
        )
        .scalars()
        .all()
    )

    actions = {r.action for r in rows}
    assert actions == {
        "payment_recorded",
        "refund_issued",
        "pt_package_refunded",
    }, f"Audit chain missing rows; got actions={actions}"

    by_action: dict[str, AuditLog] = {r.action: r for r in rows}
    # payment_recorded.resource_id == sale_payment.id (subject of payment_recorded
    # is the Payment row itself).
    assert by_action["payment_recorded"].resource_id == sale_payment.id
    # refund_issued.resource_id == refund_payment.id (subject is the new refund row).
    assert by_action["refund_issued"].resource_id == refund_payment.id
    # pt_package_refunded.resource_id == pt_package_id (subject is the pt_package).
    assert by_action["pt_package_refunded"].resource_id == pt_package_id

    # D-30-04: SHA-256 payment_row_hash forensic anchor on refund_issued payload.
    refund_issued_payload = by_action["refund_issued"].payload
    assert "payment_row_hash" in refund_issued_payload
    assert _PAYMENT_ROW_HASH_RE.match(refund_issued_payload["payment_row_hash"]), (
        f"payment_row_hash does not match SHA-256 pattern: "
        f"{refund_issued_payload['payment_row_hash']}"
    )


# --- RBAC / CSRF / schema rejection -----------------------------------------


async def test_refund_pt_package_no_csrf_403(
    authed_client_owner: AsyncClient,
    make_client: Callable[..., Awaitable[Client]],
    make_pt_package_plan: Callable[..., Awaitable[PtPackagePlan]],
) -> None:
    """RBAC-04: missing X-CSRF-Token → 403."""
    plan = await make_pt_package_plan(name="refund-no-csrf")
    client = await make_client()
    pt_package_id = await _sell_pt_package(authed_client_owner, client_id=client.id, plan=plan)
    r = await authed_client_owner.post(
        f"/api/v1/pt-packages/{pt_package_id}/refund",
        json={"reason": "no_csrf"},
        headers={"Idempotency-Key": uuid4().hex},  # no CSRF
    )
    assert r.status_code == 403, r.text


async def test_refund_pt_package_extra_field_422(
    authed_client_owner: AsyncClient,
    make_client: Callable[..., Awaitable[Client]],
    make_pt_package_plan: Callable[..., Awaitable[PtPackagePlan]],
) -> None:
    """BackendSchemaBase extra='forbid' → 422 on unknown body field (mirrors REF-05)."""
    plan = await make_pt_package_plan(name="refund-extra")
    client = await make_client()
    pt_package_id = await _sell_pt_package(authed_client_owner, client_id=client.id, plan=plan)
    r = await authed_client_owner.post(
        f"/api/v1/pt-packages/{pt_package_id}/refund",
        json={"reason": "ok", "amountKopecks": 1000},
        headers=_csrf_headers(authed_client_owner, idempotency_key=uuid4().hex),
    )
    assert r.status_code == 422, r.text


async def test_refund_pt_package_reason_empty_422(
    authed_client_owner: AsyncClient,
    make_client: Callable[..., Awaitable[Client]],
    make_pt_package_plan: Callable[..., Awaitable[PtPackagePlan]],
) -> None:
    """Field(min_length=1) → 422 on empty reason."""
    plan = await make_pt_package_plan(name="refund-empty")
    client = await make_client()
    pt_package_id = await _sell_pt_package(authed_client_owner, client_id=client.id, plan=plan)
    r = await authed_client_owner.post(
        f"/api/v1/pt-packages/{pt_package_id}/refund",
        json={"reason": ""},
        headers=_csrf_headers(authed_client_owner, idempotency_key=uuid4().hex),
    )
    assert r.status_code == 422, r.text


async def test_refund_pt_package_reason_too_long_422(
    authed_client_owner: AsyncClient,
    make_client: Callable[..., Awaitable[Client]],
    make_pt_package_plan: Callable[..., Awaitable[PtPackagePlan]],
) -> None:
    """Field(max_length=200) → 422 on reason >200 chars."""
    plan = await make_pt_package_plan(name="refund-long")
    client = await make_client()
    pt_package_id = await _sell_pt_package(authed_client_owner, client_id=client.id, plan=plan)
    r = await authed_client_owner.post(
        f"/api/v1/pt-packages/{pt_package_id}/refund",
        json={"reason": "x" * 201},
        headers=_csrf_headers(authed_client_owner, idempotency_key=uuid4().hex),
    )
    assert r.status_code == 422, r.text
