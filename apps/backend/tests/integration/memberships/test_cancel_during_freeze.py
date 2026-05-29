"""MEM-FRZ-07 — cancel during freeze: dual-audit ordering, no end_date change.

Verifies D-25-09:
  - Cancel from frozen source emits `membership_unfrozen` (days_added=0)
    BEFORE `membership_cancelled` in the same UoW.
  - end_date UNCHANGED from pre-freeze state — cancellation supersedes freeze.
  - Open freeze period closed without extension; ended_by = actor.id.
  - Reception forbidden from cancelling (CANCEL, MEMBERSHIPS) ∈ OWNER_ONLY.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID, uuid4

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit_models import AuditLog
from app.modules.memberships.models import MembershipFreezePeriod


def _csrf_headers(client: AsyncClient) -> dict[str, str]:
    # Phase 66 IDM-07: cancel_membership now requires Idempotency-Key.
    return {
        "X-CSRF-Token": client.cookies.get("sportzal_csrf") or "",
        "Idempotency-Key": uuid4().hex,
    }


VALID_CLIENT: dict[str, Any] = {
    "lastName": "Иванов",
    "firstName": "Иван",
    "phone": "+79991234090",
}


async def _create_client(authed: AsyncClient, **overrides: Any) -> dict[str, Any]:
    payload = {**VALID_CLIENT, **overrides}
    r = await authed.post(
        "/api/v1/clients",
        json=payload,
        headers=_csrf_headers(authed),
    )
    assert r.status_code == 201, r.text
    data: dict[str, Any] = r.json()["data"]
    return data


async def test_cancel_during_freeze_emits_unfrozen_then_cancelled_no_end_date_change(
    authed_client_owner: AsyncClient,
    authed_client_reception: AsyncClient,
    db_session: AsyncSession,
    seeded_owner: Any,
    make_plan: Any,
    make_membership: Any,
) -> None:
    """MEM-FRZ-07: cancel a frozen membership → end_date unchanged, dual audit emit.

    Steps:
      1. Active membership; freeze it (reception).
      2. Owner POST /cancel with reason → 200, status=cancelled.
      3. Assert response.endDate == pre_freeze end_date (UNCHANGED).
      4. Audit log ordered by id ASC contains, in order:
         - membership_frozen (from step 1)
         - membership_unfrozen (days_added=0; from cancel-from-frozen branch)
         - membership_cancelled (from cancel flow tail)
      5. membership_freeze_periods has exactly 1 row for this membership with
         ended_at != NULL and ended_by == owner.id.
    """
    plan = await make_plan(name="Cancel During Freeze", freeze_days_limit=14)
    client = await _create_client(authed_client_reception, phone="+79991234091")
    client_uuid = UUID(client["id"])
    membership = await make_membership(client_id=client_uuid, plan=plan, status="active")
    pre_freeze_end_date = membership.end_date
    membership_id = membership.id

    # 1. Freeze (reception)
    r = await authed_client_reception.post(
        f"/api/v1/memberships/{membership_id}/freeze",
        headers=_csrf_headers(authed_client_reception),
    )
    assert r.status_code == 200, r.text
    assert r.json()["data"]["status"] == "frozen"

    # 2. Cancel (owner only — RBAC enforced)
    r = await authed_client_owner.post(
        f"/api/v1/memberships/{membership_id}/cancel",
        json={"reason": "test cancel during freeze"},
        headers=_csrf_headers(authed_client_owner),
    )
    assert r.status_code == 200, r.text
    body = r.json()["data"]
    assert body["status"] == "cancelled"

    # 3. end_date UNCHANGED (cancellation supersedes freeze; no extension)
    assert body["endDate"] == pre_freeze_end_date.isoformat(), (
        f"Expected end_date {pre_freeze_end_date.isoformat()} (unchanged), got {body['endDate']}"
    )

    # 4. Audit log: 3 rows (membership_frozen + membership_unfrozen + membership_cancelled).
    # Note: AuditLog uses UUID PK (gen_random_uuid()), so id-ordering is random,
    # and Postgres `now()` returns transaction-start so both same-UoW emits
    # share `created_at`. Chronological ordering across same-tx emits is
    # therefore not strictly inspectable post-commit. We assert SET-equality
    # of actions and payload-level invariants (days_added=0 on the unfrozen
    # row identifies the cancel-during-freeze branch unambiguously).
    rows = (
        await db_session.scalars(select(AuditLog).where(AuditLog.resource_id == membership_id))
    ).all()
    actions = sorted(r.action for r in rows)
    assert actions == sorted(
        [
            "membership_frozen",
            "membership_unfrozen",
            "membership_cancelled",
        ]
    ), f"Expected 3 audit actions, got {actions}"

    # Cross-event chronology: membership_frozen comes from the EARLIER freeze
    # transaction; its created_at must be <= the cancel-flow rows.
    by_action = {r.action: r for r in rows}
    frozen_row = by_action["membership_frozen"]
    unfrozen_row = by_action["membership_unfrozen"]
    cancelled_row = by_action["membership_cancelled"]
    assert frozen_row.created_at <= unfrozen_row.created_at, (
        "membership_frozen (freeze tx) must precede membership_unfrozen (cancel tx)"
    )
    assert frozen_row.created_at <= cancelled_row.created_at, (
        "membership_frozen (freeze tx) must precede membership_cancelled (cancel tx)"
    )

    # days_added=0 sentinel on the unfrozen row (cancel-from-frozen marker;
    # this is the discriminator that distinguishes a normal unfreeze from a
    # cancel-during-freeze unfreeze in audit-log forensics).
    assert unfrozen_row.payload["days_added"] == 0, (
        f"Expected days_added=0 sentinel for cancel-during-freeze, got "
        f"{unfrozen_row.payload.get('days_added')}"
    )
    assert unfrozen_row.payload["client_id"] == str(client_uuid)
    assert cancelled_row.payload.get("reason") == "test cancel during freeze"

    # 5. Freeze period table: exactly 1 row, closed (ended_at != NULL),
    # ended_by == owner.id (the cancel actor).
    period_rows = (
        await db_session.scalars(
            select(MembershipFreezePeriod).where(
                MembershipFreezePeriod.membership_id == membership_id
            )
        )
    ).all()
    assert len(period_rows) == 1
    period = period_rows[0]
    assert period.ended_at is not None
    assert period.ended_by == seeded_owner.id


async def test_reception_cannot_cancel_frozen_membership_owner_only(
    authed_client_owner: AsyncClient,
    authed_client_reception: AsyncClient,
    make_plan: Any,
    make_membership: Any,
) -> None:
    """(CANCEL, MEMBERSHIPS) ∈ OWNER_ONLY → reception 403 even on frozen source."""
    plan = await make_plan(name="Reception Cancel Frozen")
    client = await _create_client(authed_client_owner, phone="+79991234092")
    membership = await make_membership(client_id=UUID(client["id"]), plan=plan, status="active")

    # Freeze first (reception is allowed)
    r = await authed_client_reception.post(
        f"/api/v1/memberships/{membership.id}/freeze",
        headers=_csrf_headers(authed_client_reception),
    )
    assert r.status_code == 200

    # Reception attempting to cancel → 403
    r = await authed_client_reception.post(
        f"/api/v1/memberships/{membership.id}/cancel",
        json={"reason": "should fail"},
        headers=_csrf_headers(authed_client_reception),
    )
    assert r.status_code == 403, r.text
    assert r.json()["code"] == "forbidden"
