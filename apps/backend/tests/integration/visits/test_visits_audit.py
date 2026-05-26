"""Integration tests for visits audit_log writes (VIS-AUDIT-01, D-05, D-16).

Pattern: exercise a /visits route (or service call), then query AuditLog rows
directly via the SAVEPOINT-rolled db_session.

Key invariants:
- D-05: rejection paths emit + commit + raise — audit rows ARE persisted.
- D-16: payload schemas, locked verbatim per CONTEXT.md.
- VIS-AUDIT-01: every rejection writes the locked event.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit_models import AuditLog
from app.modules.auth.models import User
from app.modules.clients.models import Client
from app.modules.visits.models import Visit

_MSK = ZoneInfo("Europe/Moscow")


def _csrf(client: AsyncClient) -> dict[str, str]:
    return {"X-CSRF-Token": client.cookies.get("sportzal_csrf") or ""}


# ── visit_created shape (D-16) ────────────────────────────────────────────────


async def test_visit_created_audit_row_payload_shape(
    authed_client_owner: AsyncClient,
    db_session: AsyncSession,
    seeded_owner: User,
    make_visit_setup: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """D-16: visit_created payload = {client_id, membership_id, channel}; resource_id=visit.id."""
    from datetime import time

    import app.modules.visits.service as svc_mod
    from app.core.config import get_settings

    # Monkeypatch gym hours to always-open so this test passes at any wall-clock time
    settings = get_settings()
    monkeypatch.setattr(settings, "gym_hours_start", time(0, 0))
    monkeypatch.setattr(settings, "gym_hours_end", time(23, 59))
    monkeypatch.setattr(svc_mod, "get_settings", lambda: settings)

    client_obj, _membership = await make_visit_setup()
    client_id_str = str(client_obj.id)  # capture before session expires obj
    await db_session.commit()

    r = await authed_client_owner.post(
        "/api/v1/visits",
        json={"clientId": client_id_str},
        headers=_csrf(authed_client_owner),
    )
    assert r.status_code == 201, r.text
    visit_id = r.json()["data"]["id"]

    rows = (
        await db_session.scalars(
            select(AuditLog).where(
                AuditLog.action == "visit_created",
                AuditLog.resource_id == visit_id,
            )
        )
    ).all()
    assert len(rows) == 1, f"expected exactly 1 visit_created row, got {len(rows)}"
    row = rows[0]
    assert row.actor_user_id == seeded_owner.id
    assert row.resource_type == "visit"
    assert str(row.resource_id) == visit_id

    payload = row.payload
    assert payload["client_id"] == client_id_str
    assert payload["channel"] == "reception"
    assert "membership_id" in payload
    # D-16 locked: exactly these 3 keys (visit_id lives in resource_id, not payload)
    assert set(payload.keys()) == {"client_id", "membership_id", "channel"}


# ── visit_rejected_outside_hours shape (D-16) ─────────────────────────────────


async def test_visit_rejected_outside_hours_payload_shape(
    authed_client_reception: AsyncClient,
    db_session: AsyncSession,
    seeded_reception: User,
    make_visit_setup: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """D-16: outside_hours payload = {client_id, channel, current_local_time, gym_open, gym_close}.

    Resource_id is None for rejections.
    """
    from datetime import time

    import app.modules.visits.service as svc_mod
    from app.core.config import get_settings

    settings = get_settings()
    monkeypatch.setattr(settings, "gym_hours_start", time(0, 0))
    monkeypatch.setattr(settings, "gym_hours_end", time(0, 1))
    monkeypatch.setattr(svc_mod, "get_settings", lambda: settings)

    client_obj, _membership = await make_visit_setup()
    client_id_str = str(client_obj.id)  # capture before session expires obj
    await db_session.commit()

    r = await authed_client_reception.post(
        "/api/v1/visits",
        json={"clientId": client_id_str},
        headers=_csrf(authed_client_reception),
    )
    assert r.status_code == 409, r.text
    assert r.json()["code"] == "outside_gym_hours"

    rows = (
        await db_session.scalars(
            select(AuditLog).where(
                AuditLog.action == "visit_rejected_outside_hours",
            )
        )
    ).all()
    # Filter to our client
    matching = [row for row in rows if row.payload.get("client_id") == client_id_str]
    assert len(matching) == 1, f"expected 1 row for our client, got {len(matching)}"
    row = matching[0]
    assert row.resource_type == "visit"
    assert row.resource_id is None  # D-16: resource_id=None for rejections

    payload = row.payload
    # D-16: locked payload keys for outside_hours
    expected_keys = {"client_id", "channel", "current_local_time", "gym_open", "gym_close"}
    assert set(payload.keys()) == expected_keys
    assert payload["channel"] == "reception"
    assert payload["gym_open"] is not None
    assert payload["gym_close"] is not None


# ── visit_rejected_no_membership shape (D-16) ─────────────────────────────────


async def test_visit_rejected_no_membership_payload_shape(
    authed_client_reception: AsyncClient,
    db_session: AsyncSession,
    seeded_reception: User,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """D-16: no_membership payload = {client_id, channel}; resource_id=None."""
    from datetime import time

    import app.modules.visits.service as svc_mod
    from app.core.config import get_settings

    # Open gym so the service reaches the membership check (not outside_hours)
    settings = get_settings()
    monkeypatch.setattr(settings, "gym_hours_start", time(0, 0))
    monkeypatch.setattr(settings, "gym_hours_end", time(23, 59))
    monkeypatch.setattr(svc_mod, "get_settings", lambda: settings)

    phone_suffix = uuid4().int % 10**7
    c = Client(
        last_name=f"NM-{uuid4().hex[:8]}",
        first_name="Test",
        phone=f"+7903{phone_suffix:07d}",
        created_by_user_id=seeded_reception.id,
    )
    db_session.add(c)
    await db_session.flush()
    c_id_str = str(c.id)  # capture before session expires obj
    await db_session.commit()

    r = await authed_client_reception.post(
        "/api/v1/visits",
        json={"clientId": c_id_str},
        headers=_csrf(authed_client_reception),
    )
    assert r.status_code == 409, r.text
    assert r.json()["code"] == "no_active_membership"

    rows = (
        await db_session.scalars(
            select(AuditLog).where(
                AuditLog.action == "visit_rejected_no_membership",
            )
        )
    ).all()
    matching = [row for row in rows if row.payload.get("client_id") == c_id_str]
    assert len(matching) == 1
    row = matching[0]
    assert row.resource_id is None
    payload = row.payload
    assert set(payload.keys()) == {"client_id", "channel"}
    assert payload["channel"] == "reception"


# ── visit_rejected_duplicate shape (D-16) ─────────────────────────────────────


async def test_visit_rejected_duplicate_payload_shape(
    authed_client_reception: AsyncClient,
    db_session: AsyncSession,
    seeded_reception: User,
    make_visit_setup: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """D-16: duplicate payload = {client_id, gym_date, channel}; resource_id=None."""
    from datetime import time

    import app.modules.visits.service as svc_mod
    from app.core.config import get_settings

    # Open gym so the service reaches the duplicate check (not outside_hours)
    settings = get_settings()
    monkeypatch.setattr(settings, "gym_hours_start", time(0, 0))
    monkeypatch.setattr(settings, "gym_hours_end", time(23, 59))
    monkeypatch.setattr(svc_mod, "get_settings", lambda: settings)

    client_obj, membership = await make_visit_setup()
    client_id_str = str(client_obj.id)  # capture before session expires obj

    now_msk = datetime.now(_MSK)
    visit = Visit(
        client_id=client_obj.id,
        membership_id=membership.id,
        channel="reception",
        checked_in_at=now_msk,
        checked_in_by=seeded_reception.id,
    )
    db_session.add(visit)
    await db_session.commit()

    r = await authed_client_reception.post(
        "/api/v1/visits",
        json={"clientId": client_id_str},
        headers=_csrf(authed_client_reception),
    )
    assert r.status_code == 409, r.text
    assert r.json()["code"] == "duplicate_checkin"

    rows = (
        await db_session.scalars(
            select(AuditLog).where(
                AuditLog.action == "visit_rejected_duplicate",
            )
        )
    ).all()
    matching = [row for row in rows if row.payload.get("client_id") == client_id_str]
    assert len(matching) == 1
    row = matching[0]
    assert row.resource_id is None
    payload = row.payload
    assert set(payload.keys()) == {"client_id", "gym_date", "channel"}
    assert payload["channel"] == "reception"
    assert payload["gym_date"] is not None


# ── D-05: reject-path audit rows ARE persisted ────────────────────────────────


async def test_reject_paths_are_persisted(
    authed_client_reception: AsyncClient,
    db_session: AsyncSession,
    seeded_reception: User,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """D-05 invariant: visit_rejected_no_membership IS written to audit_log.

    This test would FAIL if anyone reverts D-05 back to Phase 16/17's
    'no commit on raise' pattern — the audit row would disappear.
    """
    from datetime import time

    import app.modules.visits.service as svc_mod
    from app.core.config import get_settings

    # Open gym so the service reaches the membership check (not outside_hours)
    settings = get_settings()
    monkeypatch.setattr(settings, "gym_hours_start", time(0, 0))
    monkeypatch.setattr(settings, "gym_hours_end", time(23, 59))
    monkeypatch.setattr(svc_mod, "get_settings", lambda: settings)

    phone_suffix = uuid4().int % 10**7
    c = Client(
        last_name=f"D05-{uuid4().hex[:8]}",
        first_name="Test",
        phone=f"+7904{phone_suffix:07d}",
        created_by_user_id=seeded_reception.id,
    )
    db_session.add(c)
    await db_session.flush()
    c_id_str = str(c.id)  # capture before session expires obj
    await db_session.commit()

    count_before = await db_session.scalar(
        select(func.count())
        .select_from(AuditLog)
        .where(AuditLog.action == "visit_rejected_no_membership")
    )

    r = await authed_client_reception.post(
        "/api/v1/visits",
        json={"clientId": c_id_str},
        headers=_csrf(authed_client_reception),
    )
    assert r.status_code == 409, r.text

    count_after = await db_session.scalar(
        select(func.count())
        .select_from(AuditLog)
        .where(AuditLog.action == "visit_rejected_no_membership")
    )
    assert count_after == (count_before or 0) + 1, (
        "D-05 violated: rejection audit row was NOT committed "
        "(someone reverted to Phase 16/17 'no commit on raise' pattern)"
    )
