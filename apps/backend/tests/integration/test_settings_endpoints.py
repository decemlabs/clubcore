"""Phase 108 Plan 108-02 — Settings + staff-gym API integration tests (CFG-01/02/03/04).

Proves:
  - GET /api/v1/settings/hours, /booking, /notifications → 200, seeded singletons (owner)
  - GET /api/v1/gym (staff) → 200 (owner), 403 (reception — gym card is owner-only)
  - Owner PUT each settings endpoint → 200, value persists on subsequent GET (round-trip)
  - Each PUT emits the LOCKED audit event (row in audit_log with correct event + resource_type)
  - Reception PUT each settings endpoint → 403 (OWNER_ONLY (EDIT, SETTINGS) — T-108-06)
  - Reception GET /api/v1/gym → 403 (gym card EDIT-gated — owner-only end to end)
  - PUT with unknown key → 422 (extra='forbid' — T-108-05)
  - PUT with out-of-bounds numeric → 422 (Field bounds — T-108-05)
  - Missing CSRF header on owner PUT → 403 (verify_csrf — T-108-07)
  - RBAC-04 ordering: reception fails at 403 before CSRF is checked (T-108-06)

Harness: SAVEPOINT db_session + ASGITransport async_client (no real network — CLAUDE.md).
Staff auth: /api/v1/auth/login with seeded owner/reception (mirrors test_gym_info.py).
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit_models import AuditLog
from app.core.database import get_db
from app.core.permissions import Role
from app.core.redis import get_redis
from app.core.security import hash_password
from app.modules.auth.models import User

pytestmark = pytest.mark.asyncio

_OWNER_EMAIL = "settings-test-owner@example.com"
_OWNER_PASSWORD = "settings-test-owner-pw-secure-123"  # noqa: S105
_RECEPTION_EMAIL = "settings-test-reception@example.com"
_RECEPTION_PASSWORD = "settings-test-reception-pw-secure-456"  # noqa: S105


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def _overridden_app(
    app: FastAPI,
    db_session: AsyncSession,
) -> AsyncIterator[FastAPI]:
    """Install dependency overrides so route handlers use the SAVEPOINT session."""

    async def _override_get_db() -> AsyncIterator[AsyncSession]:
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_redis] = lambda: app.state.redis
    try:
        yield app
    finally:
        app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def seeded_owner(db_session: AsyncSession) -> User:
    user = User(
        email=_OWNER_EMAIL,
        password_hash=await hash_password(_OWNER_PASSWORD),
        role=Role.OWNER,
        full_name="Settings Test Owner",
    )
    db_session.add(user)
    await db_session.commit()
    return user


@pytest_asyncio.fixture
async def seeded_reception(db_session: AsyncSession, seeded_owner: User) -> User:
    """Reception user (depends on seeded_owner to ensure commit ordering)."""
    user = User(
        email=_RECEPTION_EMAIL,
        password_hash=await hash_password(_RECEPTION_PASSWORD),
        role=Role.RECEPTION,
        full_name="Settings Test Reception",
    )
    db_session.add(user)
    await db_session.commit()
    return user


@pytest_asyncio.fixture
async def http_client_owner(
    _overridden_app: FastAPI,
    seeded_owner: User,
) -> AsyncIterator[AsyncClient]:
    """ASGITransport client logged in as owner."""
    transport = ASGITransport(app=_overridden_app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as c:
        r = await c.post(
            "/api/v1/auth/login",
            json={"email": _OWNER_EMAIL, "password": _OWNER_PASSWORD},
        )
        assert r.status_code == 200, f"Owner login failed: {r.text}"
        yield c


@pytest_asyncio.fixture
async def http_client_reception(
    _overridden_app: FastAPI,
    seeded_reception: User,
) -> AsyncIterator[AsyncClient]:
    """ASGITransport client logged in as reception."""
    transport = ASGITransport(app=_overridden_app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as c:
        r = await c.post(
            "/api/v1/auth/login",
            json={"email": _RECEPTION_EMAIL, "password": _RECEPTION_PASSWORD},
        )
        assert r.status_code == 200, f"Reception login failed: {r.text}"
        yield c


@pytest_asyncio.fixture(autouse=True)
async def flush_redis(app: FastAPI) -> None:
    """Flush Redis before each test."""
    await app.state.redis.flushdb()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _csrf(client: AsyncClient) -> dict[str, str]:
    """Extract CSRF token from cookie."""
    return {"X-CSRF-Token": client.cookies.get("clubcore_csrf", "")}


async def _audit_rows(
    session: AsyncSession,
    event: str,
    resource_type: str,
) -> list[AuditLog]:
    """Return all audit_log rows matching event + resource_type."""
    rows = (
        await session.scalars(
            select(AuditLog).where(
                AuditLog.action == event,
                AuditLog.resource_type == resource_type,
            )
        )
    ).all()
    return list(rows)


# ---------------------------------------------------------------------------
# GET /api/v1/settings/hours (CFG-02)
# ---------------------------------------------------------------------------


async def test_owner_get_working_hours_returns_seeded_singleton(
    http_client_owner: AsyncClient,
) -> None:
    """Owner GET /api/v1/settings/hours → 200 with seeded singleton fields.

    Seeded by migration 0071: schedule/breaks/closures are all lists.
    """
    r = await http_client_owner.get("/api/v1/settings/hours")
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert "schedule" in data, "schedule field missing from WorkingHoursResponse"
    assert "breaks" in data, "breaks field missing from WorkingHoursResponse"
    assert "closures" in data, "closures field missing from WorkingHoursResponse"
    assert isinstance(data["schedule"], list), "schedule must be a list"


async def test_owner_put_working_hours_round_trip(
    http_client_owner: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Owner PUT /api/v1/settings/hours → 200; GET reflects updated value (round-trip)."""
    new_closures = [{"date": "2026-12-31", "reason": "Новый год"}]

    put_r = await http_client_owner.put(
        "/api/v1/settings/hours",
        json={"closures": new_closures},
        headers=_csrf(http_client_owner),
    )
    assert put_r.status_code == 200, put_r.text
    assert put_r.json()["data"]["closures"] == new_closures

    get_r = await http_client_owner.get("/api/v1/settings/hours")
    assert get_r.status_code == 200, get_r.text
    assert get_r.json()["data"]["closures"] == new_closures, (
        "GET after PUT should reflect updated closures"
    )


async def test_owner_put_working_hours_emits_audit_event(
    http_client_owner: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Owner PUT /api/v1/settings/hours emits working_hours_updated audit event."""
    await http_client_owner.put(
        "/api/v1/settings/hours",
        json={"breaks": []},
        headers=_csrf(http_client_owner),
    )
    rows = await _audit_rows(db_session, "working_hours_updated", "settings")
    assert len(rows) >= 1, f"Expected working_hours_updated audit row, got {len(rows)}"


async def test_reception_put_working_hours_forbidden(
    http_client_reception: AsyncClient,
) -> None:
    """Reception PUT /api/v1/settings/hours → 403 (OWNER_ONLY (EDIT, SETTINGS) — T-108-06)."""
    r = await http_client_reception.put(
        "/api/v1/settings/hours",
        json={"schedule": []},
        headers=_csrf(http_client_reception),
    )
    assert r.status_code == 403, r.text


async def test_reception_put_working_hours_blocked_before_csrf(
    http_client_reception: AsyncClient,
) -> None:
    """RBAC-04: reception blocked at 403 even without CSRF header (T-108-06).

    require_permission(EDIT, SETTINGS) fires BEFORE verify_csrf so reception
    never reaches the CSRF check.
    """
    r = await http_client_reception.put(
        "/api/v1/settings/hours",
        json={"schedule": []},
        # NO X-CSRF-Token header — should still be 403 (not CSRF-error)
    )
    assert r.status_code == 403, f"Expected 403 (RBAC), got {r.status_code}: {r.text}"


async def test_owner_put_working_hours_missing_csrf_rejected(
    http_client_owner: AsyncClient,
) -> None:
    """Owner PUT /api/v1/settings/hours without CSRF header → 403 (T-108-07)."""
    r = await http_client_owner.put(
        "/api/v1/settings/hours",
        json={"breaks": []},
        # No CSRF header
    )
    assert r.status_code == 403, f"Expected 403 (CSRF), got {r.status_code}: {r.text}"


async def test_owner_put_working_hours_unknown_key_422(
    http_client_owner: AsyncClient,
) -> None:
    """Owner PUT /api/v1/settings/hours with unknown key → 422 (extra='forbid' — T-108-05)."""
    r = await http_client_owner.put(
        "/api/v1/settings/hours",
        json={"unknownField": "неизвестное поле"},
        headers=_csrf(http_client_owner),
    )
    assert r.status_code == 422, r.text


# ---------------------------------------------------------------------------
# GET/PUT /api/v1/settings/booking (CFG-03)
# ---------------------------------------------------------------------------


async def test_owner_get_booking_config_returns_seeded_singleton(
    http_client_owner: AsyncClient,
) -> None:
    """Owner GET /api/v1/settings/booking → 200 with seeded singleton fields."""
    r = await http_client_owner.get("/api/v1/settings/booking")
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    # Seeded defaults from migration 0071
    assert data["scheduleStepMinutes"] == 60
    assert data["bookingAheadDays"] == 14
    assert data["cutoffMinutes"] == 60
    assert data["cancelWindowHours"] == 24
    assert data["cancelWindowEnabled"] is True
    assert data["groupLimit"] == 20
    assert data["waitlistLimit"] == 10


async def test_owner_put_booking_config_round_trip(
    http_client_owner: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Owner PUT /api/v1/settings/booking → 200; GET reflects updated value."""
    new_ahead = 30

    put_r = await http_client_owner.put(
        "/api/v1/settings/booking",
        json={"bookingAheadDays": new_ahead},
        headers=_csrf(http_client_owner),
    )
    assert put_r.status_code == 200, put_r.text
    assert put_r.json()["data"]["bookingAheadDays"] == new_ahead

    get_r = await http_client_owner.get("/api/v1/settings/booking")
    assert get_r.status_code == 200, get_r.text
    assert get_r.json()["data"]["bookingAheadDays"] == new_ahead


async def test_owner_put_booking_config_emits_audit_event(
    http_client_owner: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Owner PUT /api/v1/settings/booking emits booking_config_updated audit event."""
    await http_client_owner.put(
        "/api/v1/settings/booking",
        json={"groupLimit": 25},
        headers=_csrf(http_client_owner),
    )
    rows = await _audit_rows(db_session, "booking_config_updated", "settings")
    assert len(rows) >= 1, f"Expected booking_config_updated audit row, got {len(rows)}"


async def test_reception_put_booking_config_forbidden(
    http_client_reception: AsyncClient,
) -> None:
    """Reception PUT /api/v1/settings/booking → 403 (OWNER_ONLY (EDIT, SETTINGS))."""
    r = await http_client_reception.put(
        "/api/v1/settings/booking",
        json={"bookingAheadDays": 7},
        headers=_csrf(http_client_reception),
    )
    assert r.status_code == 403, r.text


async def test_owner_put_booking_config_unknown_key_422(
    http_client_owner: AsyncClient,
) -> None:
    """Owner PUT /api/v1/settings/booking with unknown key → 422 (extra='forbid')."""
    r = await http_client_owner.put(
        "/api/v1/settings/booking",
        json={"unknownBookingField": 999},
        headers=_csrf(http_client_owner),
    )
    assert r.status_code == 422, r.text


async def test_owner_put_booking_config_out_of_bounds_booking_ahead_days_0_422(
    http_client_owner: AsyncClient,
) -> None:
    """booking_ahead_days=0 → 422 (ge=1 — T-108-05)."""
    r = await http_client_owner.put(
        "/api/v1/settings/booking",
        json={"bookingAheadDays": 0},
        headers=_csrf(http_client_owner),
    )
    assert r.status_code == 422, r.text


async def test_owner_put_booking_config_out_of_bounds_booking_ahead_days_too_large_422(
    http_client_owner: AsyncClient,
) -> None:
    """booking_ahead_days=999 → 422 (le=365 — T-108-05)."""
    r = await http_client_owner.put(
        "/api/v1/settings/booking",
        json={"bookingAheadDays": 999},
        headers=_csrf(http_client_owner),
    )
    assert r.status_code == 422, r.text


async def test_owner_put_booking_config_invalid_schedule_step_422(
    http_client_owner: AsyncClient,
) -> None:
    """schedule_step_minutes=45 → 422 (not in {15,30,60,90} — T-108-05)."""
    r = await http_client_owner.put(
        "/api/v1/settings/booking",
        json={"scheduleStepMinutes": 45},
        headers=_csrf(http_client_owner),
    )
    assert r.status_code == 422, r.text


async def test_owner_put_booking_config_missing_csrf_rejected(
    http_client_owner: AsyncClient,
) -> None:
    """Owner PUT /api/v1/settings/booking without CSRF → 403 (T-108-07)."""
    r = await http_client_owner.put(
        "/api/v1/settings/booking",
        json={"groupLimit": 15},
        # No CSRF header
    )
    assert r.status_code == 403, r.text


# ---------------------------------------------------------------------------
# GET/PUT /api/v1/settings/notifications (CFG-04)
# ---------------------------------------------------------------------------


async def test_owner_get_notification_prefs_returns_seeded_singleton(
    http_client_owner: AsyncClient,
) -> None:
    """Owner GET /api/v1/settings/notifications → 200 with seeded singleton fields."""
    r = await http_client_owner.get("/api/v1/settings/notifications")
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert "matrix" in data, "matrix field missing from NotificationPrefsResponse"
    assert "senderSignature" in data, "senderSignature field missing"
    assert "quietHoursStart" in data, "quietHoursStart field missing"
    assert "quietHoursEnd" in data, "quietHoursEnd field missing"
    assert isinstance(data["matrix"], dict), "matrix must be a dict"


async def test_owner_put_notification_prefs_round_trip(
    http_client_owner: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Owner PUT /api/v1/settings/notifications → 200; GET reflects updated value."""
    # WR-02: sender_signature must be uppercase Latin only — use valid value.
    new_signature = "MYGYM"

    put_r = await http_client_owner.put(
        "/api/v1/settings/notifications",
        json={"senderSignature": new_signature},
        headers=_csrf(http_client_owner),
    )
    assert put_r.status_code == 200, put_r.text
    assert put_r.json()["data"]["senderSignature"] == new_signature

    get_r = await http_client_owner.get("/api/v1/settings/notifications")
    assert get_r.status_code == 200, get_r.text
    assert get_r.json()["data"]["senderSignature"] == new_signature


async def test_owner_put_notification_prefs_emits_audit_event(
    http_client_owner: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Owner PUT /api/v1/settings/notifications emits notification_prefs_updated audit event."""
    await http_client_owner.put(
        "/api/v1/settings/notifications",
        json={"senderSignature": "TEST"},  # WR-02: must be uppercase Latin only
        headers=_csrf(http_client_owner),
    )
    rows = await _audit_rows(db_session, "notification_prefs_updated", "settings")
    assert len(rows) >= 1, f"Expected notification_prefs_updated audit row, got {len(rows)}"


async def test_reception_put_notification_prefs_forbidden(
    http_client_reception: AsyncClient,
) -> None:
    """Reception PUT /api/v1/settings/notifications → 403 (OWNER_ONLY (EDIT, SETTINGS))."""
    r = await http_client_reception.put(
        "/api/v1/settings/notifications",
        json={"senderSignature": "не должен"},
        headers=_csrf(http_client_reception),
    )
    assert r.status_code == 403, r.text


async def test_owner_put_notification_prefs_sender_signature_too_long_422(
    http_client_owner: AsyncClient,
) -> None:
    """sender_signature > 11 chars → 422 (max_length=11 — T-108-05)."""
    r = await http_client_owner.put(
        "/api/v1/settings/notifications",
        json={"senderSignature": "TooLongSigHere"},  # 14 chars
        headers=_csrf(http_client_owner),
    )
    assert r.status_code == 422, r.text


async def test_owner_put_notification_prefs_invalid_quiet_hours_422(
    http_client_owner: AsyncClient,
) -> None:
    """quietHoursStart not in HH:MM format → 422 (T-108-05)."""
    r = await http_client_owner.put(
        "/api/v1/settings/notifications",
        json={"quietHoursStart": "9:00"},  # missing leading zero
        headers=_csrf(http_client_owner),
    )
    assert r.status_code == 422, r.text


async def test_owner_put_notification_prefs_unknown_key_422(
    http_client_owner: AsyncClient,
) -> None:
    """Owner PUT /api/v1/settings/notifications with unknown key → 422 (extra='forbid')."""
    r = await http_client_owner.put(
        "/api/v1/settings/notifications",
        json={"unknownNotifField": True},
        headers=_csrf(http_client_owner),
    )
    assert r.status_code == 422, r.text


# ---------------------------------------------------------------------------
# Staff GET/PUT /api/v1/gym (CFG-01)
# ---------------------------------------------------------------------------


async def test_owner_get_gym_info_staff_side(
    http_client_owner: AsyncClient,
) -> None:
    """Owner GET /api/v1/gym → 200 (staff-side form pre-population — CFG-01).

    The staff GET is EDIT-gated (require_permission(EDIT, GYM)) so only owner can read.
    Response includes new latitude/longitude fields.
    """
    r = await http_client_owner.get("/api/v1/gym")
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert "name" in data, "name field missing from GymInfoResponse"
    assert "latitude" in data, "latitude field missing (Phase 108 CFG-01 additive)"
    assert "longitude" in data, "longitude field missing (Phase 108 CFG-01 additive)"


async def test_reception_get_gym_info_staff_side_forbidden(
    http_client_reception: AsyncClient,
) -> None:
    """Reception GET /api/v1/gym → 403 (gym card is owner-only end to end — T-108-06).

    The staff GET is EDIT-gated (require_permission(EDIT, GYM)) — there is no
    reception-accessible VIEW gate on the staff side (locked CONTEXT decision).
    """
    r = await http_client_reception.get("/api/v1/gym")
    assert r.status_code == 403, r.text


async def test_owner_put_gym_info_lat_lng(
    http_client_owner: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Owner PUT /api/v1/gym with latitude/longitude → 200; persists and emits gym_card_updated."""
    put_r = await http_client_owner.put(
        "/api/v1/gym",
        json={"latitude": 55.7617, "longitude": 37.6082},
        headers=_csrf(http_client_owner),
    )
    assert put_r.status_code == 200, put_r.text
    data = put_r.json()["data"]
    assert data["latitude"] == pytest.approx(55.7617)
    assert data["longitude"] == pytest.approx(37.6082)

    # Verify audit event emitted
    rows = await _audit_rows(db_session, "gym_card_updated", "gym")
    assert len(rows) >= 1, f"Expected gym_card_updated audit row, got {len(rows)}"


async def test_owner_put_gym_info_lat_out_of_bounds_422(
    http_client_owner: AsyncClient,
) -> None:
    """latitude > 90 → 422 (ge=-90, le=90 — T-108-05)."""
    r = await http_client_owner.put(
        "/api/v1/gym",
        json={"latitude": 95.0},
        headers=_csrf(http_client_owner),
    )
    assert r.status_code == 422, r.text


async def test_owner_put_gym_info_lng_out_of_bounds_422(
    http_client_owner: AsyncClient,
) -> None:
    """longitude > 180 → 422 (ge=-180, le=180 — T-108-05)."""
    r = await http_client_owner.put(
        "/api/v1/gym",
        json={"longitude": 200.0},
        headers=_csrf(http_client_owner),
    )
    assert r.status_code == 422, r.text
