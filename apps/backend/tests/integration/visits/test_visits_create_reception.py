"""Integration tests for POST /api/v1/visits (VIS-EP-03).

Covers:
- Happy path 201 + response shape
- All 4 reject paths: client_not_found (404), outside_gym_hours (409),
  no_active_membership (409), duplicate_checkin (409)
- extra='forbid' from BackendSchemaBase rejects unknown fields (422)
- Pitfall 11 inclusive end_date: membership ending today is still active
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.models import User
from app.modules.clients.models import Client
from app.modules.visits.models import Visit

_MSK = ZoneInfo("Europe/Moscow")


def _csrf(client: AsyncClient) -> dict[str, str]:
    return {"X-CSRF-Token": client.cookies.get("sportzal_csrf") or ""}


# ── Happy path ────────────────────────────────────────────────────────────────


async def test_create_visit_201_happy_path(
    authed_client_reception: AsyncClient,
    db_session: AsyncSession,
    seeded_reception: User,
    make_visit_setup: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """VIS-EP-03 happy path: 201 with channel='reception' and checkedInBy=actor.id."""
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
    await db_session.commit()  # flush SAVEPOINT so route handler sees the data

    r = await authed_client_reception.post(
        "/api/v1/visits",
        json={"clientId": client_id_str},
        headers=_csrf(authed_client_reception),
    )
    assert r.status_code == 201, r.text
    data = r.json()["data"]
    UUID(data["id"])
    assert data["clientId"] == client_id_str
    assert data["channel"] == "reception"
    assert data["checkedInBy"] == str(seeded_reception.id)
    assert data["gymDate"] is not None
    assert data["checkedInAt"] is not None


# ── Outside gym hours ─────────────────────────────────────────────────────────


async def test_create_visit_409_outside_gym_hours(
    authed_client_reception: AsyncClient,
    db_session: AsyncSession,
    make_visit_setup: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Monkeypatched settings with 00:00-00:01 window → any wall-clock → 409."""
    from datetime import time

    import app.modules.visits.service as svc_mod
    from app.core.config import get_settings

    settings = get_settings()
    monkeypatch.setattr(settings, "gym_hours_start", time(0, 0))
    monkeypatch.setattr(settings, "gym_hours_end", time(0, 1))
    # Also patch the get_settings call inside the service to return mutated object
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
    body = r.json()
    assert body["code"] == "outside_gym_hours"
    assert "open" in body["fields"]
    assert "close" in body["fields"]


# ── No active membership ──────────────────────────────────────────────────────


async def test_create_visit_409_no_active_membership(
    authed_client_reception: AsyncClient,
    db_session: AsyncSession,
    seeded_reception: User,
    make_visit_setup: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Client without a membership → 409 no_active_membership."""
    from datetime import time

    import app.modules.visits.service as svc_mod
    from app.core.config import get_settings

    # Open gym so the service reaches the membership check (not outside_hours)
    settings = get_settings()
    monkeypatch.setattr(settings, "gym_hours_start", time(0, 0))
    monkeypatch.setattr(settings, "gym_hours_end", time(23, 59))
    monkeypatch.setattr(svc_mod, "get_settings", lambda: settings)

    # Seed only a client with no membership
    phone_suffix = uuid4().int % 10**7
    c = Client(
        last_name=f"NoMem-{uuid4().hex[:8]}",
        first_name="Test",
        phone=f"+7902{phone_suffix:07d}",
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
    body = r.json()
    assert body["code"] == "no_active_membership"


# ── Duplicate check-in ────────────────────────────────────────────────────────


async def test_create_visit_409_duplicate_checkin(
    authed_client_reception: AsyncClient,
    db_session: AsyncSession,
    seeded_reception: User,
    make_visit_setup: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Pre-insert visit then POST → 409 duplicate_checkin with client_id + gym_date."""
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

    # Pre-insert a visit for today so the UNIQUE index blocks a second insert
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
    body = r.json()
    assert body["code"] == "duplicate_checkin"
    assert "client_id" in body["fields"]
    assert "gym_date" in body["fields"]


# ── Extra field rejected (D-01 / BackendSchemaBase) ───────────────────────────


async def test_create_visit_422_extra_field_rejected(
    authed_client_reception: AsyncClient,
    make_visit_setup: Any,
    db_session: AsyncSession,
) -> None:
    """D-01: extra field 'channel' in body → 422 (BackendSchemaBase extra='forbid')."""
    client_obj, _membership = await make_visit_setup()
    client_id_str = str(client_obj.id)  # capture before session expires obj
    await db_session.commit()

    r = await authed_client_reception.post(
        "/api/v1/visits",
        json={"clientId": client_id_str, "channel": "telegram_bot"},
        headers=_csrf(authed_client_reception),
    )
    assert r.status_code == 422, r.text


# ── Pitfall 11: membership ends today (inclusive end_date) ────────────────────


async def test_create_visit_201_membership_ends_today_inclusive(
    authed_client_reception: AsyncClient,
    db_session: AsyncSession,
    make_visit_setup: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Pitfall 11: membership end_date == today → still active → 201.

    resolve_active_membership returns a membership when end_date >= today.
    """
    from datetime import datetime, time
    from zoneinfo import ZoneInfo

    import app.modules.visits.service as svc_mod
    from app.core.config import get_settings

    # Monkeypatch gym hours to always-open so this test passes at any wall-clock time
    settings = get_settings()
    monkeypatch.setattr(settings, "gym_hours_start", time(0, 0))
    monkeypatch.setattr(settings, "gym_hours_end", time(23, 59))
    monkeypatch.setattr(svc_mod, "get_settings", lambda: settings)

    today_msk = datetime.now(ZoneInfo("Europe/Moscow")).date()
    client_obj, _membership = await make_visit_setup(end_date=today_msk)
    client_id_str = str(client_obj.id)  # capture before session expires obj
    await db_session.commit()

    r = await authed_client_reception.post(
        "/api/v1/visits",
        json={"clientId": client_id_str},
        headers=_csrf(authed_client_reception),
    )
    assert r.status_code == 201, r.text


# ── Client not found ─────────────────────────────────────────────────────────


async def test_create_visit_409_client_not_found_no_membership(
    authed_client_reception: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Random client_id with no membership → 409 no_active_membership.

    Note: there is no explicit 404 for missing client — the resolve_active_membership
    resolver returns None if the client has no active membership, whether the client
    doesn't exist or has no membership. The service raises NoActiveMembershipError.
    """
    from datetime import time

    import app.modules.visits.service as svc_mod
    from app.core.config import get_settings

    # Open gym so the service reaches the membership check (not outside_hours)
    settings = get_settings()
    monkeypatch.setattr(settings, "gym_hours_start", time(0, 0))
    monkeypatch.setattr(settings, "gym_hours_end", time(23, 59))
    monkeypatch.setattr(svc_mod, "get_settings", lambda: settings)

    r = await authed_client_reception.post(
        "/api/v1/visits",
        json={"clientId": str(uuid4())},
        headers=_csrf(authed_client_reception),
    )
    assert r.status_code == 409, r.text
    assert r.json()["code"] == "no_active_membership"
