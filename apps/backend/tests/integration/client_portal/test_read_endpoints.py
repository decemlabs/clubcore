"""Behavioral tests for Phase 69 client-portal read endpoints (D-69-01/02/03/05).

Proves the contracts from the Plan 01 decisions:
  - D-69-02: membership returns daysUntilEnd (int) + expiringSoon (bool); server-computed.
  - D-69-03: own-scope empty state -> 200 with null (NOT 404).
  - D-69-01: /home composite returns {membership, nextBooking, expiringSoon} with null slots.
  - CHIST-01/02/03: history endpoints return {items, total, page, pageSize}; refunds visible.
  - D-69-05: trainer catalog items expose only id + fullName; no rates/isActive/audit fields.

Wire format: camelCase (alias_generator=to_camel from ContractModel — schemas.py D-07).
All response field names are camelCase in assertions.

Harness: SAVEPOINT rollback + ASGITransport async_client from root conftest.py.
Auth: _auth_as_client from test_idor_sweep.py (OTP flow, cookie-based).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permissions import Role
from app.core.security import hash_password
from app.modules.auth.models import User
from app.modules.clients.models import Client
from app.modules.memberships.models import Membership, MembershipPlan
from app.modules.trainers.models import Trainer
from tests.integration.client_portal.conftest import SeededOwnedData
from tests.integration.client_portal.test_idor_sweep import _auth_as_client

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _get_authed(
    async_client: AsyncClient,
    db_session: AsyncSession,
    client: Client,
    path: str,
) -> dict:  # type: ignore[type-arg]
    """Auth as client and GET path; return parsed JSON body."""
    token = await _auth_as_client(async_client, db_session, client)
    resp = await async_client.get(path, headers={"Cookie": f"cc_client_access={token}"})
    return resp.json()  # type: ignore[no-any-return]


# ---------------------------------------------------------------------------
# D-69-02: membership temporal fields (daysUntilEnd + expiringSoon)
# Wire format: camelCase per ContractModel alias_generator=to_camel (D-07)
# ---------------------------------------------------------------------------


async def test_membership_temporal_fields_present(
    async_client: AsyncClient,
    db_session: AsyncSession,
    client_a: Client,
    seeded_owned_data: SeededOwnedData,
    redis_clean: object,
) -> None:
    """D-69-02: GET /membership returns daysUntilEnd (int) and expiringSoon (bool).

    Wire format: camelCase (ContractModel alias_generator=to_camel, D-07).
    The far-future membership seeded for client_a has end_date ~60 days away.
    expiringSoon MUST be False; daysUntilEnd MUST be a non-negative int.
    """
    body = await _get_authed(async_client, db_session, client_a, "/api/v1/client/membership")
    assert body["data"] is not None, "Expected active membership data, got null"
    data = body["data"]

    assert "daysUntilEnd" in data, "daysUntilEnd missing from membership response"
    assert isinstance(data["daysUntilEnd"], int), (
        f"daysUntilEnd should be int, got {type(data['daysUntilEnd'])}"
    )
    assert data["daysUntilEnd"] >= 0, "daysUntilEnd should be non-negative"

    assert "expiringSoon" in data, "expiringSoon missing from membership response"
    assert isinstance(data["expiringSoon"], bool), (
        f"expiringSoon should be bool, got {type(data['expiringSoon'])}"
    )
    # Far-future membership (end_date ~60 days away) → expiringSoon must be False
    assert data["expiringSoon"] is False, (
        f"Far-future membership should have expiringSoon=False, got {data['expiringSoon']}"
    )


async def test_membership_expiring_soon_true_for_near_expiry(
    async_client: AsyncClient,
    db_session: AsyncSession,
    client_a: Client,
    seeded_owned_data: SeededOwnedData,
    redis_clean: object,
) -> None:
    """D-69-02: for a near-expiry membership, expiringSoon is True and daysUntilEnd <= 7.

    Seeds a fresh client with only a near-expiry active membership (end_date + 3 days).
    """
    suffix = uuid4().hex[:6]
    staff = User(
        email=f"staff-near-expiry-{suffix}@example.com",
        password_hash=await hash_password("test-pw-123"),
        role=Role.RECEPTION,
        full_name="Staff Near Expiry",
    )
    db_session.add(staff)
    await db_session.flush()

    near_client = Client(
        first_name="Near",
        last_name=f"Expiry-{suffix}",
        phone=f"+7999666{int(suffix[:4], 16) % 10000:04d}",
        telegram_user_id=666_000_000 + int(suffix[:4], 16),
        created_by_user_id=staff.id,
    )
    db_session.add(near_client)
    await db_session.flush()

    now = datetime.now(tz=UTC)
    plan = MembershipPlan(
        name=f"Near Plan {suffix}",
        duration_days=30,
        price_kopecks=50_000,
        freeze_days_limit=5,
        active=True,
    )
    db_session.add(plan)
    await db_session.flush()

    near_membership = Membership(
        client_id=near_client.id,
        plan_id=plan.id,
        plan_name_snapshot=plan.name,
        duration_days_snapshot=plan.duration_days,
        price_kopecks_snapshot=plan.price_kopecks,
        freeze_days_limit_snapshot=plan.freeze_days_limit,
        start_date=(now - timedelta(days=27)).date(),
        end_date=(now + timedelta(days=3)).date(),
        status="active",
    )
    db_session.add(near_membership)
    await db_session.commit()

    body = await _get_authed(async_client, db_session, near_client, "/api/v1/client/membership")
    assert body["data"] is not None
    data = body["data"]

    assert data["expiringSoon"] is True, (
        f"Near-expiry membership (3 days) should have expiringSoon=True, got {data['expiringSoon']}"
    )
    assert 0 <= data["daysUntilEnd"] <= 7, (
        f"Near-expiry membership should have daysUntilEnd <= 7, got {data['daysUntilEnd']}"
    )


# ---------------------------------------------------------------------------
# D-69-03: empty own-scope → 200 with null (not 404)
# ---------------------------------------------------------------------------


async def test_membership_empty_state_returns_200_null(
    async_client: AsyncClient,
    db_session: AsyncSession,
    seeded_owned_data: SeededOwnedData,
    redis_clean: object,
) -> None:
    """D-69-03: a client with NO active membership gets 200 with data=null, NOT 404."""
    suffix = uuid4().hex[:6]
    staff = User(
        email=f"staff-empty-{suffix}@example.com",
        password_hash=await hash_password("test-pw-123"),
        role=Role.RECEPTION,
        full_name="Staff Empty",
    )
    db_session.add(staff)
    await db_session.flush()

    empty_client = Client(
        first_name="Empty",
        last_name=f"Member-{suffix}",
        phone=f"+7999555{int(suffix[:4], 16) % 10000:04d}",
        telegram_user_id=555_000_000 + int(suffix[:4], 16),
        created_by_user_id=staff.id,
    )
    db_session.add(empty_client)
    await db_session.commit()

    token = await _auth_as_client(async_client, db_session, empty_client)
    resp = await async_client.get(
        "/api/v1/client/membership",
        headers={"Cookie": f"cc_client_access={token}"},
    )
    assert resp.status_code == 200, (
        f"Empty membership should return 200, got {resp.status_code} (D-69-03 violation)"
    )
    data = resp.json().get("data")
    assert data is None, (
        f"Empty membership should return null data, got {data!r} (D-69-03 violation)"
    )


# ---------------------------------------------------------------------------
# D-69-01 / D-69-03: /home composite — null slots for empty client
# ---------------------------------------------------------------------------


async def test_home_composite_empty_client_returns_null_slots(
    async_client: AsyncClient,
    db_session: AsyncSession,
    redis_clean: object,
    seeded_owned_data: SeededOwnedData,
) -> None:
    """D-69-01/D-69-03: /home for a client with no membership/booking returns 200
    with membership=null, nextBooking=null, and expiringSoon=False.
    """
    suffix = uuid4().hex[:6]
    staff = User(
        email=f"staff-home-empty-{suffix}@example.com",
        password_hash=await hash_password("test-pw-123"),
        role=Role.RECEPTION,
        full_name="Staff Home Empty",
    )
    db_session.add(staff)
    await db_session.flush()

    empty_client = Client(
        first_name="HomeEmpty",
        last_name=f"Client-{suffix}",
        phone=f"+7999444{int(suffix[:4], 16) % 10000:04d}",
        telegram_user_id=444_000_000 + int(suffix[:4], 16),
        created_by_user_id=staff.id,
    )
    db_session.add(empty_client)
    await db_session.commit()

    token = await _auth_as_client(async_client, db_session, empty_client)
    resp = await async_client.get(
        "/api/v1/client/home",
        headers={"Cookie": f"cc_client_access={token}"},
    )
    assert resp.status_code == 200, f"Empty /home should return 200, got {resp.status_code}"
    data = resp.json().get("data")
    assert data is not None, "/home should always return a data object (not null)"
    assert data.get("membership") is None, (
        f"Empty client /home should have membership=null, got {data.get('membership')!r}"
    )
    # next_booking serializes as nextBooking (camelCase)
    assert data.get("nextBooking") is None, (
        f"Empty client /home should have nextBooking=null, got {data.get('nextBooking')!r}"
    )
    assert data.get("expiringSoon") is False, (
        f"Empty client /home should have expiringSoon=False, got {data.get('expiringSoon')!r}"
    )
    # D-01: client with zero membership rows is a 'newbie'
    assert data.get("membershipState") == "newbie", (
        f"Client with zero membership rows should have membershipState='newbie', "
        f"got {data.get('membershipState')!r}"
    )


async def test_home_composite_with_data_returns_fields(
    async_client: AsyncClient,
    db_session: AsyncSession,
    client_a: Client,
    seeded_owned_data: SeededOwnedData,
    redis_clean: object,
) -> None:
    """D-69-01: /home for a client with data returns membership + expiringSoon fields."""
    body = await _get_authed(async_client, db_session, client_a, "/api/v1/client/home")
    data = body["data"]
    assert data is not None
    assert "membership" in data
    # nextBooking is the camelCase form of next_booking
    assert "nextBooking" in data
    assert "expiringSoon" in data
    assert isinstance(data["expiringSoon"], bool)
    # D-01: active client_a must have membershipState='active'
    assert data.get("membershipState") == "active", (
        f"client_a with active membership should have membershipState='active', "
        f"got {data.get('membershipState')!r}"
    )


# ---------------------------------------------------------------------------
# CHIST-01/02/03: history endpoints return {items, total, page, pageSize}
# Wire format: pageSize = camelCase of page_size (D-07)
# ---------------------------------------------------------------------------


async def test_visit_history_pagination_shape(
    async_client: AsyncClient,
    db_session: AsyncSession,
    client_a: Client,
    seeded_owned_data: SeededOwnedData,
    redis_clean: object,
) -> None:
    """CHIST-01: GET /history/visits returns {items, total, page, pageSize} shape."""
    body = await _get_authed(async_client, db_session, client_a, "/api/v1/client/history/visits")
    data = body["data"]
    assert "items" in data, "visits history missing 'items' key"
    assert "total" in data, "visits history missing 'total' key"
    assert "page" in data, "visits history missing 'page' key"
    assert "pageSize" in data, "visits history missing 'pageSize' key"
    assert isinstance(data["items"], list)
    assert isinstance(data["total"], int)
    # Client A has at least 1 seeded visit
    assert data["total"] >= 1, "Expected at least 1 visit for seeded client_a"


async def test_pt_session_history_pagination_shape(
    async_client: AsyncClient,
    db_session: AsyncSession,
    client_a: Client,
    seeded_owned_data: SeededOwnedData,
    redis_clean: object,
) -> None:
    """CHIST-02: GET /history/pt-sessions returns {items, total, page, pageSize} shape.

    Ownership is via pt_packages.client_id (not direct pt_sessions.client_id FK).
    """
    body = await _get_authed(
        async_client, db_session, client_a, "/api/v1/client/history/pt-sessions"
    )
    data = body["data"]
    assert "items" in data, "pt-sessions history missing 'items' key"
    assert "total" in data, "pt-sessions history missing 'total' key"
    assert "page" in data, "pt-sessions history missing 'page' key"
    assert "pageSize" in data, "pt-sessions history missing 'pageSize' key"
    assert isinstance(data["items"], list)
    # Client A has at least 1 seeded pt_session
    assert data["total"] >= 1, "Expected at least 1 pt-session for seeded client_a"


async def test_payment_history_pagination_shape_and_refund_visible(
    async_client: AsyncClient,
    db_session: AsyncSession,
    client_a: Client,
    seeded_owned_data: SeededOwnedData,
    redis_clean: object,
) -> None:
    """CHIST-03: GET /history/payments returns pagination shape + refund row visible.

    Refund items have negative amountKopecks and subjectKind='refund'.
    Wire format: amountKopecks, subjectKind are camelCase (D-07).
    """
    body = await _get_authed(async_client, db_session, client_a, "/api/v1/client/history/payments")
    data = body["data"]
    assert "items" in data, "payments history missing 'items' key"
    assert "total" in data, "payments history missing 'total' key"
    assert "page" in data, "payments history missing 'page' key"
    assert "pageSize" in data, "payments history missing 'pageSize' key"
    assert isinstance(data["items"], list)
    # Client A has 1 positive payment + 1 refund = 2 items
    assert data["total"] >= 2, (
        f"Expected at least 2 payment rows (1 payment + 1 refund), got {data['total']}"
    )
    items = data["items"]
    # subjectKind is the camelCase form of subject_kind (D-07)
    refund_items = [i for i in items if i.get("subjectKind") == "refund"]
    assert len(refund_items) >= 1, "Expected at least 1 refund item in payment history (CHIST-03)"
    # Refund must have negative amountKopecks
    for refund in refund_items:
        assert refund["amountKopecks"] < 0, (
            f"Refund item should have negative amountKopecks, got {refund['amountKopecks']}"
        )


# ---------------------------------------------------------------------------
# D-69-05: catalog field projections (client-safe fields only)
# Wire format: fullName = camelCase of full_name; isActive = camelCase of is_active
# ---------------------------------------------------------------------------


async def test_trainer_catalog_client_safe_fields(
    async_client: AsyncClient,
    db_session: AsyncSession,
    client_a: Client,
    seeded_owned_data: SeededOwnedData,
    redis_clean: object,
) -> None:
    """D-69-05: GET /trainers catalog items expose only id + fullName.

    Must NOT include: phone, isActive, deletedAt, createdAt, updatedAt, rates.
    Wire format: camelCase (D-07) — isActive, deletedAt, etc.
    """
    # Seed an active trainer so the catalog is non-empty
    trainer = Trainer(full_name="Test Trainer Catalog", is_active=True)
    db_session.add(trainer)
    await db_session.commit()

    body = await _get_authed(async_client, db_session, client_a, "/api/v1/client/trainers")
    data = body["data"]
    assert isinstance(data, list), f"Trainer catalog should be a list, got {type(data)}"
    assert len(data) >= 1, "Expected at least 1 trainer in catalog"

    # Check first item for field presence/absence
    item = data[0]
    assert "id" in item, "Trainer item missing 'id' field"
    assert "fullName" in item, "Trainer item missing 'fullName' field"

    # Owner-only fields that MUST NOT be exposed (D-69-05) — camelCase wire format
    forbidden_fields = [
        "phone",
        "isActive",
        "deletedAt",
        "createdAt",
        "updatedAt",
        "rates",
        # Also check snake_case variants (should not appear in camelCase wire)
        "is_active",
        "deleted_at",
        "created_at",
        "updated_at",
    ]
    for field in forbidden_fields:
        assert field not in item, (
            f"Trainer catalog item should NOT expose '{field}' (D-69-05 violation)"
        )


async def test_plans_catalog_returns_active_items(
    async_client: AsyncClient,
    db_session: AsyncSession,
    client_a: Client,
    seeded_owned_data: SeededOwnedData,
    redis_clean: object,
) -> None:
    """CPLAN-01: GET /plans returns active membership plans with client-safe fields."""
    body = await _get_authed(async_client, db_session, client_a, "/api/v1/client/plans")
    data = body["data"]
    assert isinstance(data, list), f"Plans catalog should be a list, got {type(data)}"
    # seeded_owned_data seeds MembershipPlan rows with active=True
    assert len(data) >= 1, "Expected at least 1 active plan in catalog"

    item = data[0]
    assert "id" in item
    assert "name" in item
    assert "priceKopecks" in item  # camelCase form of price_kopecks
    assert "durationDays" in item  # camelCase form of duration_days
    # freezeDaysLimit must not be exposed (D-69-05)
    assert "freezeDaysLimit" not in item, "Plan catalog must NOT expose freezeDaysLimit (D-69-05)"
    assert "freeze_days_limit" not in item, (
        "Plan catalog must NOT expose freeze_days_limit (D-69-05)"
    )


async def test_pt_packages_catalog_returns_items(
    async_client: AsyncClient,
    db_session: AsyncSession,
    client_a: Client,
    seeded_owned_data: SeededOwnedData,
    redis_clean: object,
) -> None:
    """CPLAN-02: GET /pt-packages returns PT-package plans with client-safe fields."""
    body = await _get_authed(async_client, db_session, client_a, "/api/v1/client/pt-packages")
    data = body["data"]
    assert isinstance(data, list), f"PT packages catalog should be a list, got {type(data)}"
    # seeded_owned_data seeds PtPackagePlan rows
    assert len(data) >= 1, "Expected at least 1 PT-package plan in catalog"

    item = data[0]
    assert "id" in item
    assert "name" in item
    assert "sessionCount" in item  # camelCase form of session_count
    assert "priceKopecks" in item  # camelCase form of price_kopecks


# ---------------------------------------------------------------------------
# D-01 / D-03: membershipState enum — newbie / lapsed / active
# ---------------------------------------------------------------------------


async def test_home_membership_state_lapsed(
    async_client: AsyncClient,
    db_session: AsyncSession,
    seeded_owned_data: SeededOwnedData,
    redis_clean: object,
) -> None:
    """D-01: /home for a client whose only membership is expired returns membershipState='lapsed'.

    A lapsed member has >=1 rows in memberships (status='expired') but no active one.
    This is distinct from a newbie (zero rows) — D-01 requires server-side detection.
    """
    suffix = uuid4().hex[:6]
    staff = User(
        email=f"staff-lapsed-{suffix}@example.com",
        password_hash=await hash_password("test-pw-123"),
        role=Role.RECEPTION,
        full_name="Staff Lapsed",
    )
    db_session.add(staff)
    await db_session.flush()

    lapsed_client = Client(
        first_name="Lapsed",
        last_name=f"Client-{suffix}",
        phone=f"+7999333{int(suffix[:4], 16) % 10000:04d}",
        telegram_user_id=333_000_000 + int(suffix[:4], 16),
        created_by_user_id=staff.id,
    )
    db_session.add(lapsed_client)
    await db_session.flush()

    now = datetime.now(tz=UTC)
    plan = MembershipPlan(
        name=f"Lapsed Plan {suffix}",
        duration_days=30,
        price_kopecks=50_000,
        freeze_days_limit=5,
        active=True,
    )
    db_session.add(plan)
    await db_session.flush()

    # Insert an expired membership (status='expired') — lapsed member pattern
    expired_membership = Membership(
        client_id=lapsed_client.id,
        plan_id=plan.id,
        plan_name_snapshot=plan.name,
        duration_days_snapshot=plan.duration_days,
        price_kopecks_snapshot=plan.price_kopecks,
        freeze_days_limit_snapshot=plan.freeze_days_limit,
        start_date=(now - timedelta(days=60)).date(),
        end_date=(now - timedelta(days=30)).date(),
        status="expired",
    )
    db_session.add(expired_membership)
    await db_session.commit()

    token = await _auth_as_client(async_client, db_session, lapsed_client)
    resp = await async_client.get(
        "/api/v1/client/home",
        headers={"Cookie": f"cc_client_access={token}"},
    )
    assert resp.status_code == 200, f"Lapsed /home should return 200, got {resp.status_code}"
    data = resp.json().get("data")
    assert data is not None, "/home should always return a data object for a lapsed client"
    assert data.get("membership") is None, (
        f"Lapsed client should have membership=null (no active), got {data.get('membership')!r}"
    )
    assert data.get("membershipState") == "lapsed", (
        f"Client with only expired membership should have membershipState='lapsed', "
        f"got {data.get('membershipState')!r}"
    )
