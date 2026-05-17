"""Unit-tier predicate-isolation test for D-34-11a reverse transition.

``atomic_transition_exhausted_to_active`` is the carve-out predicate-gated
UPDATE that flips ``pt_packages.status='exhausted' → 'active'`` inside
``cancel_pt_session`` ONLY. The global FSM constant
``PT_PACKAGE_STATUS_TRANSITIONS`` in ``pt_packages.constants`` is NOT
modified — the reverse transition is locally-scoped, justified by the
invariant "we just freed one balance unit from an exhausted package".

This test seeds 4 pt_packages rows with each of the 4 status values
(``active``, ``exhausted``, ``expired``, ``cancelled``) and runs the
helper against each id. Only the ``exhausted`` row must flip.

Also includes a static assertion that the FSM constant is unchanged
(``exhausted`` maps to ``frozenset({'cancelled'})`` — no ``active``).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.pt_packages.constants import PT_PACKAGE_STATUS_TRANSITIONS
from app.modules.pt_sessions.repository import (
    atomic_transition_exhausted_to_active,
)


def test_fsm_constant_has_no_reverse_active_edge() -> None:
    """D-34-11a invariant: PT_PACKAGE_STATUS_TRANSITIONS unchanged from
    Phase 33 — ``exhausted`` MUST NOT reach ``active`` via the global FSM.

    The reverse transition lives ONLY as the locally-scoped predicate-gated
    UPDATE inside ``cancel_pt_session``.
    """
    exhausted_transitions = PT_PACKAGE_STATUS_TRANSITIONS["exhausted"]
    assert "active" not in exhausted_transitions, (
        "PT_PACKAGE_STATUS_TRANSITIONS['exhausted'] must NOT include "
        "'active' — reverse transition is local-only (D-34-11a). "
        f"Got: {exhausted_transitions}"
    )
    # Sanity: exhausted → {cancelled} is the only forward edge from exhausted.
    assert exhausted_transitions == frozenset({"cancelled"})


@pytest.mark.asyncio
async def test_revert_flips_exhausted_only(db_session: AsyncSession) -> None:
    """Seed 4 pt_packages (one per status), call the helper on each id;
    only the ``exhausted`` row flips. Other statuses are untouched.

    Each pt_package is seeded against a DISTINCT client because the partial
    UNIQUE constraint ``uq_pt_packages_active_per_client`` (status='active')
    forbids two active rows per client — once the helper flips 'exhausted'
    → 'active' for client X, the prior seeded 'active' row for the same X
    would deadlock the UPDATE. Per-status isolation keeps the predicate's
    behaviour observable without bumping into the active-per-client invariant.
    """
    # Seed a synthetic owner + plan to satisfy FK references. We bypass
    # the make_* factories (unit-tier) and write minimal rows via raw SQL
    # so this test stays decoupled from the integration fixtures and uses
    # the SAVEPOINT-isolated db_session for cleanup.
    plan_id = uuid4()
    user_id = uuid4()

    await db_session.execute(
        text(
            "INSERT INTO users (id, email, password_hash, role, full_name, "
            "created_at, updated_at) VALUES "
            "(:id, :email, :pw, 'owner', 'Test', now(), now())"
        ),
        {
            "id": user_id,
            "email": f"revert-pred-{user_id.hex[:8]}@example.com",
            "pw": "x" * 60,
        },
    )
    await db_session.execute(
        text(
            "INSERT INTO pt_package_plans (id, name, session_count, "
            "price_kopecks, validity_days, created_at, "
            "updated_at) VALUES "
            "(:id, :name, 10, 500000, 90, now(), now())"
        ),
        {"id": plan_id, "name": f"REVERT-PRED-{plan_id.hex[:8]}"},
    )

    today = datetime.now(tz=UTC).date()
    end = today + timedelta(days=89)
    pkg_ids: dict[str, UUID] = {}
    for status_name in ("active", "exhausted", "expired", "cancelled"):
        # One client per status — see docstring rationale.
        client_id = uuid4()
        await db_session.execute(
            text(
                "INSERT INTO clients (id, last_name, first_name, phone, "
                "created_by_user_id, created_at, updated_at) VALUES "
                "(:id, 'Тест', 'Тест', :phone, :uid, now(), now())"
            ),
            {
                "id": client_id,
                "phone": f"+7999{client_id.hex[:7]}",
                "uid": user_id,
            },
        )
        pkg_id = uuid4()
        pkg_ids[status_name] = pkg_id
        await db_session.execute(
            text(
                "INSERT INTO pt_packages (id, client_id, plan_id, "
                "plan_name_snapshot, session_count_snapshot, "
                "price_kopecks_snapshot, validity_days_snapshot, "
                "sessions_remaining, status, start_date, end_date, "
                "created_at, updated_at) VALUES "
                "(:id, :client_id, :plan_id, :name, 10, 500000, 90, "
                ":remaining, :status, :start_date, :end_date, "
                "now(), now())"
            ),
            {
                "id": pkg_id,
                "client_id": client_id,
                "plan_id": plan_id,
                "name": f"REVERT-PRED-{status_name}",
                # `exhausted` requires sessions_remaining=0 by CHECK; the
                # others can carry an arbitrary balance ≤ ceiling.
                "remaining": 0 if status_name == "exhausted" else 5,
                "status": status_name,
                "start_date": today,
                "end_date": end,
            },
        )
    await db_session.flush()

    # Run the helper against EACH row. Only the exhausted row should flip.
    flipped_for: dict[str, bool] = {}
    for status_name, pkg_id in pkg_ids.items():
        result = await atomic_transition_exhausted_to_active(
            db_session,
            pkg_id,
        )
        flipped_for[status_name] = result

    assert flipped_for == {
        "active": False,
        "exhausted": True,
        "expired": False,
        "cancelled": False,
    }, flipped_for

    # Verify resulting status matrix in the DB.
    for status_name, pkg_id in pkg_ids.items():
        observed = await db_session.scalar(
            text("SELECT status FROM pt_packages WHERE id = :id"),
            {"id": pkg_id},
        )
        expected = "active" if status_name == "exhausted" else status_name
        assert observed == expected, (
            f"pt_packages[{status_name}] status drift: expected "
            f"{expected!r}, got {observed!r}"
        )
