"""Phase 81 Plan 81-01 — GET /client/activity/weekly endpoint behavior + IDOR tests (WACT-01).

Proves the endpoint contracts:
  - 7-item Mon→Sun array, workouts=0 for all days when no visits in current week.
  - A visit on Monday of the current Moscow week → Monday bucket workouts=1, others 0.
  - dates are strictly ascending over 7 consecutive days (Mon→Sun ordering).
  - minutes is always null in all response items.
  - IDOR: client_b's visit does NOT appear in client_a's response buckets.
  - No-auth request → 401.

Note on same-day double-count: visits has UNIQUE(client_id, gym_date), so a single
client can have at most one visit row per Moscow day (workouts≤1 per own bucket).
The aggregate COUNT(*) is still tested with a real row returning workouts=1.
Two different clients can each have a visit on the same day — that is verified by
the IDOR test (each sees only their own count).

Harness: SAVEPOINT db_session + ASGITransport async_client.
Auth: OTP flow via _auth_as_client (cookies stored on http_client; CSRF from cookie jar).
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.permissions import Role
from app.core.redis import get_redis
from app.core.security import hash_password
from app.modules.auth.models import User
from app.modules.clients.models import Client
from tests.integration.client_portal.test_idor_sweep import _auth_as_client

pytestmark = pytest.mark.asyncio
_MSK = ZoneInfo("Europe/Moscow")

# ---------------------------------------------------------------------------
# Fixtures — dependency overrides + authed http_client
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
async def http_client(_overridden_app: FastAPI) -> AsyncIterator[AsyncClient]:
    """ASGITransport client that persists cookies across requests."""
    transport = ASGITransport(app=_overridden_app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as c:
        yield c


@pytest.fixture(autouse=True)
def stub_otp_sender(app: FastAPI, monkeypatch: pytest.MonkeyPatch) -> None:
    """Replace real OTP sender with no-op for all tests in this module."""
    _ = app
    from app.modules.client_auth import service as client_auth_service

    async def _noop(chat_id: int, code: str) -> None:
        pass

    monkeypatch.setattr(client_auth_service, "_client_otp_sender", _noop)


@pytest_asyncio.fixture(autouse=True)
async def flush_redis(app: FastAPI) -> None:
    """Flush Redis before each test to clear rate-limit counters and session keys."""
    await app.state.redis.flushdb()


# ---------------------------------------------------------------------------
# Seed helpers
# ---------------------------------------------------------------------------


async def _seed_staff(db_session: AsyncSession) -> User:
    """Insert a staff user for client created_by_user_id FK."""
    user = User(
        email=f"wact-staff-{datetime.now(UTC).timestamp():.0f}@example.com",
        password_hash=await hash_password("staff-test-pw-secure-456"),
        role=Role.RECEPTION,
        full_name="Weekly Activity Test Staff",
    )
    db_session.add(user)
    await db_session.flush()
    return user


async def _seed_client(db_session: AsyncSession, staff: User, phone: str) -> Client:
    """Insert a client with the given phone number."""
    client = Client(
        first_name="Wact",
        last_name=f"Test-{phone[-4:]}",
        phone=phone,
        telegram_user_id=int(phone[-9:]),
        created_by_user_id=staff.id,
    )
    db_session.add(client)
    await db_session.flush()
    return client


async def _seed_membership(
    db_session: AsyncSession,
    client: Client,
) -> None:
    """Seed a minimal active membership so visit FKs are satisfiable."""
    from app.modules.memberships.models import Membership, MembershipPlan

    plan = MembershipPlan(
        name=f"WACT-Plan-{client.phone[-4:]}",
        duration_days=30,
        price_kopecks=100_000,
        freeze_days_limit=5,
        active=True,
    )
    db_session.add(plan)
    await db_session.flush()

    now = datetime.now(UTC)
    membership = Membership(
        client_id=client.id,
        plan_id=plan.id,
        plan_name_snapshot=plan.name,
        duration_days_snapshot=plan.duration_days,
        price_kopecks_snapshot=plan.price_kopecks,
        freeze_days_limit_snapshot=plan.freeze_days_limit,
        start_date=(now - timedelta(days=10)).date(),
        end_date=(now + timedelta(days=20)).date(),
        status="active",
    )
    db_session.add(membership)
    await db_session.flush()
    return membership  # type: ignore[return-value]


async def _seed_visit_on_monday(
    db_session: AsyncSession,
    client: Client,
) -> None:
    """Insert a visit row whose gym_date lands on Monday of the current Moscow week.

    We compute Monday of the current Moscow week, then set checked_in_at to noon
    Moscow time on that Monday (12:00 MSK = 09:00 UTC in summer, 11:00 UTC in winter).
    Using noon ensures it stays in the same day regardless of DST.
    """
    now_msk = datetime.now(_MSK)
    monday = (now_msk - timedelta(days=now_msk.weekday())).date()
    # Use noon Moscow time → unambiguously same Moscow calendar day
    monday_noon_msk = datetime(monday.year, monday.month, monday.day, 12, 0, tzinfo=_MSK)
    monday_noon_utc = monday_noon_msk.astimezone(UTC)

    # Fetch the client's active membership id for the FK
    row = (
        await db_session.execute(
            text("SELECT id FROM memberships WHERE client_id = :cid AND status = 'active' LIMIT 1"),
            {"cid": str(client.id)},
        )
    ).mappings().one()
    membership_id = row["id"]

    await db_session.execute(
        text(
            "INSERT INTO visits (id, client_id, membership_id, checked_in_at, channel, "
            "created_at, updated_at) VALUES "
            "(gen_random_uuid(), :client_id, :membership_id, :checked_in_at, 'reception', "
            "now(), now())"
        ),
        {
            "client_id": str(client.id),
            "membership_id": str(membership_id),
            "checked_in_at": monday_noon_utc,  # datetime object required by asyncpg
        },
    )
    await db_session.flush()


async def _seed_visit_at_utc(
    db_session: AsyncSession,
    client: Client,
    checked_in_at_utc: datetime,
) -> None:
    """Insert a visit row at an EXACT UTC instant (no DST-safe rounding).

    Unlike `_seed_visit_on_monday` (which deliberately picks noon to avoid the
    midnight boundary), this helper writes the raw UTC timestamp so a test can
    exercise the STORED `visits.gym_date` generated column
    `(checked_in_at AT TIME ZONE 'Europe/Moscow')::date` across the 21:00-UTC
    Moscow-midnight boundary.
    """
    row = (
        await db_session.execute(
            text("SELECT id FROM memberships WHERE client_id = :cid AND status = 'active' LIMIT 1"),
            {"cid": str(client.id)},
        )
    ).mappings().one()
    membership_id = row["id"]

    await db_session.execute(
        text(
            "INSERT INTO visits (id, client_id, membership_id, checked_in_at, channel, "
            "created_at, updated_at) VALUES "
            "(gen_random_uuid(), :client_id, :membership_id, :checked_in_at, 'reception', "
            "now(), now())"
        ),
        {
            "client_id": str(client.id),
            "membership_id": str(membership_id),
            "checked_in_at": checked_in_at_utc,  # datetime object required by asyncpg
        },
    )
    await db_session.flush()


# ---------------------------------------------------------------------------
# Behavior tests
# ---------------------------------------------------------------------------


async def test_weekly_activity_empty_week_returns_7_items(
    http_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Empty week → exactly 7 items, all workouts=0, minutes=null."""
    staff = await _seed_staff(db_session)
    client = await _seed_client(db_session, staff, "+79111000101")
    await db_session.commit()

    await _auth_as_client(http_client, db_session, client)

    resp = await http_client.get("/api/v1/client/activity/weekly")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    items = body["data"]
    assert len(items) == 7
    for item in items:
        assert item["workouts"] == 0
        assert item["minutes"] is None


async def test_weekly_activity_minutes_always_null(
    http_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """minutes is always null in all response items (WACT-01 — WACT-03 deferred)."""
    staff = await _seed_staff(db_session)
    client = await _seed_client(db_session, staff, "+79111000102")
    await _seed_membership(db_session, client)
    await _seed_visit_on_monday(db_session, client)
    await db_session.commit()

    await _auth_as_client(http_client, db_session, client)

    resp = await http_client.get("/api/v1/client/activity/weekly")
    assert resp.status_code == 200, resp.text
    items = resp.json()["data"]
    assert len(items) == 7
    for item in items:
        assert item["minutes"] is None


async def test_weekly_activity_monday_visit_appears_in_monday_bucket(
    http_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """One visit on Monday → Monday bucket workouts=1, all other buckets workouts=0."""
    staff = await _seed_staff(db_session)
    client = await _seed_client(db_session, staff, "+79111000103")
    await _seed_membership(db_session, client)
    await _seed_visit_on_monday(db_session, client)
    await db_session.commit()

    await _auth_as_client(http_client, db_session, client)

    resp = await http_client.get("/api/v1/client/activity/weekly")
    assert resp.status_code == 200, resp.text
    items = resp.json()["data"]
    assert len(items) == 7

    # Monday is index 0 in the Mon→Sun order
    assert items[0]["workouts"] == 1
    # All other days are zero
    for item in items[1:]:
        assert item["workouts"] == 0


async def test_weekly_activity_boundary_2130_utc_lands_next_moscow_day(
    http_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Golden-TZ integration: a visit at Monday 21:30 UTC must bucket into TUESDAY.

    21:30 UTC = 00:30 MSK on the NEXT calendar day (Moscow is UTC+3). The STORED
    generated column `(checked_in_at AT TIME ZONE 'Europe/Moscow')::date` therefore
    yields the Tuesday date, so the visit must land in bucket index 1 (Tuesday),
    NOT index 0 (Monday).

    This is the regression the contract forbids: if someone swaps the aggregation
    to group on `DATE(checked_in_at)` (the UTC date), the visit would land in the
    Monday bucket (index 0) and THIS test would fail — exactly as intended. It
    exercises the real endpoint + Postgres STORED column end-to-end, unlike the
    unit suite which only re-checks `datetime.astimezone` arithmetic.

    Monday→Tuesday is chosen so both the UTC date and its Moscow successor stay
    inside the current Moscow week regardless of which weekday "today" is.
    """
    staff = await _seed_staff(db_session)
    client = await _seed_client(db_session, staff, "+79111000109")
    await _seed_membership(db_session, client)

    # Monday of the current Moscow week, at 21:30 UTC.
    now_msk = datetime.now(_MSK)
    monday = (now_msk - timedelta(days=now_msk.weekday())).date()
    checked_in_at_utc = datetime(monday.year, monday.month, monday.day, 21, 30, tzinfo=UTC)
    await _seed_visit_at_utc(db_session, client, checked_in_at_utc)
    await db_session.commit()

    await _auth_as_client(http_client, db_session, client)

    resp = await http_client.get("/api/v1/client/activity/weekly")
    assert resp.status_code == 200, resp.text
    items = resp.json()["data"]
    assert len(items) == 7

    # Tuesday bucket (index 1) gets the workout; Monday (index 0) stays zero.
    assert items[1]["workouts"] == 1, (
        "21:30 UTC visit must bucket into the NEXT Moscow day (Tuesday) via STORED "
        f"gym_date — got Monday={items[0]['workouts']} Tuesday={items[1]['workouts']}"
    )
    assert items[0]["workouts"] == 0, (
        "Monday bucket must be empty — a non-zero count here means the aggregation "
        "grouped on DATE(checked_in_at) (UTC date) instead of the STORED gym_date"
    )
    # Every other day remains zero.
    for item in items[2:]:
        assert item["workouts"] == 0


async def test_weekly_activity_response_ordered_mon_to_sun(
    http_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Response dates are strictly ascending Mon→Sun (7 consecutive days)."""
    from datetime import date

    staff = await _seed_staff(db_session)
    client = await _seed_client(db_session, staff, "+79111000104")
    await db_session.commit()

    await _auth_as_client(http_client, db_session, client)

    resp = await http_client.get("/api/v1/client/activity/weekly")
    assert resp.status_code == 200, resp.text
    items = resp.json()["data"]
    assert len(items) == 7

    dates = [date.fromisoformat(item["date"]) for item in items]
    # Must be strictly ascending
    for i in range(1, len(dates)):
        assert dates[i] - dates[i - 1] == timedelta(days=1)
    # First must be Monday
    assert dates[0].isoweekday() == 1
    # Last must be Sunday
    assert dates[6].isoweekday() == 7


async def test_weekly_activity_no_auth_returns_401(
    http_client: AsyncClient,
) -> None:
    """No auth cookie → 401 (require_client guard)."""
    resp = await http_client.get("/api/v1/client/activity/weekly")
    assert resp.status_code == 401


async def test_weekly_activity_idor_client_b_visit_absent_from_client_a_response(
    http_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """IDOR: client_b's visit does NOT appear in client_a's weekly activity response.

    client_a has no visits this week → all 7 workouts=0.
    client_b has a visit on Monday of this week.
    client_a's response must remain all-zero (no cross-client data leak).
    """
    staff = await _seed_staff(db_session)
    client_a = await _seed_client(db_session, staff, "+79111000105")
    client_b = await _seed_client(db_session, staff, "+79111000106")
    # Only seed membership + visit for client_b
    await _seed_membership(db_session, client_b)
    await _seed_visit_on_monday(db_session, client_b)
    await db_session.commit()

    # Authenticate as client_a
    await _auth_as_client(http_client, db_session, client_a)

    resp = await http_client.get("/api/v1/client/activity/weekly")
    assert resp.status_code == 200, resp.text
    items = resp.json()["data"]
    assert len(items) == 7
    # client_a must see all zeros — client_b's Monday visit must NOT appear
    for item in items:
        assert item["workouts"] == 0, (
            f"IDOR leak: client_a saw workouts={item['workouts']} on {item['date']}"
        )


async def test_weekly_activity_idor_client_a_visit_absent_from_client_b_response(
    http_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """IDOR (reverse): client_a's visit does NOT appear in client_b's response.

    client_a has a visit on Monday; client_b has no visits.
    client_b's response must be all-zero.
    """
    staff = await _seed_staff(db_session)
    client_a = await _seed_client(db_session, staff, "+79111000107")
    client_b = await _seed_client(db_session, staff, "+79111000108")
    await _seed_membership(db_session, client_a)
    await _seed_visit_on_monday(db_session, client_a)
    await db_session.commit()

    # Authenticate as client_b
    await _auth_as_client(http_client, db_session, client_b)

    resp = await http_client.get("/api/v1/client/activity/weekly")
    assert resp.status_code == 200, resp.text
    items = resp.json()["data"]
    assert len(items) == 7
    for item in items:
        assert item["workouts"] == 0, (
            f"IDOR leak: client_b saw workouts={item['workouts']} on {item['date']}"
        )
