"""Phase 999.5 Plan 02 Task 2 — client_portal.service update_client_profile + get_client_me.

RED gate: these tests define behavior BEFORE the implementation exists.
ALL tests here MUST fail on the current service.py (missing functions).

Behaviors locked (D-05/D-07/D-08/D-09/D-10):
  - update_client_profile persists all non-None fields atomically (D-08).
  - onboarding_completed=True stamps onboarding_completed_at (D-05 skip path).
  - goal not in allow-list → ValidationAppError (D-07).
  - height_cm outside 140–210 → ValidationAppError.
  - weight_kg outside 40–150 → ValidationAppError.
  - email malformed → ValidationAppError (D-10 server-side email gate).
  - first_name > 24 chars → ValidationAppError.
  - get_client_payment_status on succeeded → receipt_email/receipt_phone populated (D-09/D-10).
  - Anti-oracle: pending/canceled payment exposes no receipt contact.
"""  # noqa: RUF002

from __future__ import annotations

from collections.abc import Awaitable, Callable
from uuid import UUID, uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ValidationAppError
from app.modules.client_portal import service
from app.modules.client_portal.schemas import (
    ClientMeResponse,
    ClientProfileUpdateRequest,
)
from app.modules.clients.models import Client

pytestmark = pytest.mark.asyncio(loop_scope="function")


# ── Helper to build a payload ────────────────────────────────────────────────


def _payload(**kwargs: object) -> ClientProfileUpdateRequest:
    return ClientProfileUpdateRequest(**kwargs)


# ── get_client_me ─────────────────────────────────────────────────────────────


async def test_get_client_me_returns_profile(
    db_session: AsyncSession,
    make_client: Callable[..., Awaitable[Client]],
) -> None:
    """get_client_me returns a ClientMeResponse with the client's profile fields."""
    client = await make_client(
        first_name="Аня",
        last_name="Иванова",
        email="anya@example.com",
    )
    result = await service.get_client_me(db_session, client.id)
    assert isinstance(result, ClientMeResponse)
    assert result.first_name == "Аня"
    assert result.last_name == "Иванова"
    assert result.email == "anya@example.com"
    assert result.phone == client.phone


async def test_get_client_me_null_fields(
    db_session: AsyncSession,
    make_client: Callable[..., Awaitable[Client]],
) -> None:
    """get_client_me returns None for optional fields not yet set."""
    client = await make_client(email=None, goal=None, height_cm=None, weight_kg=None)
    result = await service.get_client_me(db_session, client.id)
    assert result.email is None
    assert result.goal is None
    assert result.height_cm is None
    assert result.weight_kg is None
    assert result.onboarding_completed_at is None


# ── update_client_profile — happy paths ──────────────────────────────────────


async def test_update_client_profile_persists_all_fields(
    db_session: AsyncSession,
    make_client: Callable[..., Awaitable[Client]],
) -> None:
    """update_client_profile with valid data persists all four profile fields."""
    client = await make_client()
    result = await service.update_client_profile(
        db_session,
        client_id=client.id,
        payload=_payload(
            first_name="Аня",
            goal="lose_weight",
            height_cm=180,
            weight_kg=80,
        ),
    )
    assert isinstance(result, ClientMeResponse)
    assert result.first_name == "Аня"
    assert result.goal == "lose_weight"
    assert result.height_cm == 180
    assert result.weight_kg == 80
    assert result.onboarding_completed_at is None  # not requested


async def test_update_client_profile_onboarding_skip_stamps_flag(
    db_session: AsyncSession,
    make_client: Callable[..., Awaitable[Client]],
) -> None:
    """D-05: onboarding_completed=True stamps onboarding_completed_at, writes nothing else."""
    client = await make_client(first_name="Пётр")
    result = await service.update_client_profile(
        db_session,
        client_id=client.id,
        payload=_payload(onboarding_completed=True),
    )
    # onboarding_completed_at must be stamped
    assert result.onboarding_completed_at is not None
    # first_name must remain unchanged (skip writes nothing else)
    assert result.first_name == "Пётр"


async def test_update_client_profile_all_goals_accepted(
    db_session: AsyncSession,
    make_client: Callable[..., Awaitable[Client]],
) -> None:
    """All four valid goal values are accepted by update_client_profile."""
    valid_goals = ["lose_weight", "gain_mass", "tone", "maintain"]
    for goal in valid_goals:
        client = await make_client()
        result = await service.update_client_profile(
            db_session,
            client_id=client.id,
            payload=_payload(goal=goal),
        )
        assert result.goal == goal, f"Expected goal={goal!r} to be persisted"


# ── update_client_profile — validation rejections ────────────────────────────


async def test_update_client_profile_rejects_invalid_goal(
    db_session: AsyncSession,
    make_client: Callable[..., Awaitable[Client]],
) -> None:
    """D-07: unknown goal value → ValidationAppError, no write occurs."""
    client = await make_client(goal="lose_weight")
    with pytest.raises(ValidationAppError) as exc_info:
        await service.update_client_profile(
            db_session,
            client_id=client.id,
            payload=_payload(goal="bogus"),
        )
    assert exc_info.value.code is not None


async def test_update_client_profile_rejects_height_above_range(
    db_session: AsyncSession,
    make_client: Callable[..., Awaitable[Client]],
) -> None:
    """height_cm=300 (above 210) → ValidationAppError."""
    client = await make_client()
    with pytest.raises(ValidationAppError):
        await service.update_client_profile(
            db_session,
            client_id=client.id,
            payload=_payload(height_cm=300),
        )


async def test_update_client_profile_rejects_height_below_range(
    db_session: AsyncSession,
    make_client: Callable[..., Awaitable[Client]],
) -> None:
    """height_cm=100 (below 140) → ValidationAppError."""
    client = await make_client()
    with pytest.raises(ValidationAppError):
        await service.update_client_profile(
            db_session,
            client_id=client.id,
            payload=_payload(height_cm=100),
        )


async def test_update_client_profile_rejects_weight_above_range(
    db_session: AsyncSession,
    make_client: Callable[..., Awaitable[Client]],
) -> None:
    """weight_kg=200 (above 150) → ValidationAppError."""
    client = await make_client()
    with pytest.raises(ValidationAppError):
        await service.update_client_profile(
            db_session,
            client_id=client.id,
            payload=_payload(weight_kg=200),
        )


async def test_update_client_profile_rejects_weight_below_range(
    db_session: AsyncSession,
    make_client: Callable[..., Awaitable[Client]],
) -> None:
    """weight_kg=30 (below 40) → ValidationAppError."""
    client = await make_client()
    with pytest.raises(ValidationAppError):
        await service.update_client_profile(
            db_session,
            client_id=client.id,
            payload=_payload(weight_kg=30),
        )


async def test_update_client_profile_rejects_malformed_email(
    db_session: AsyncSession,
    make_client: Callable[..., Awaitable[Client]],
) -> None:
    """D-10: server-side email format check — malformed email → ValidationAppError."""
    client = await make_client()
    with pytest.raises(ValidationAppError):
        await service.update_client_profile(
            db_session,
            client_id=client.id,
            payload=_payload(email="not-an-email"),
        )


async def test_update_client_profile_rejects_first_name_too_long(
    db_session: AsyncSession,
    make_client: Callable[..., Awaitable[Client]],
) -> None:
    """D-08: first_name > 24 chars → ValidationAppError."""
    client = await make_client()
    with pytest.raises(ValidationAppError):
        await service.update_client_profile(
            db_session,
            client_id=client.id,
            payload=_payload(first_name="А" * 25),  # noqa: RUF001
        )


async def test_update_client_profile_boundary_height_accepted(
    db_session: AsyncSession,
    make_client: Callable[..., Awaitable[Client]],
) -> None:
    """Boundary values 140 and 210 are accepted (inclusive range)."""
    for height in [140, 210]:
        client = await make_client()
        result = await service.update_client_profile(
            db_session,
            client_id=client.id,
            payload=_payload(height_cm=height),
        )
        assert result.height_cm == height


async def test_update_client_profile_boundary_weight_accepted(
    db_session: AsyncSession,
    make_client: Callable[..., Awaitable[Client]],
) -> None:
    """Boundary values 40 and 150 are accepted (inclusive range)."""
    for weight in [40, 150]:
        client = await make_client()
        result = await service.update_client_profile(
            db_session,
            client_id=client.id,
            payload=_payload(weight_kg=weight),
        )
        assert result.weight_kg == weight


# ── get_client_payment_status — receipt fields (anti-oracle) ─────────────────

# Helper: insert an online_payments row using a real membership_plan_id FK.
# The online_payments table requires: yookassa_payment_id (unique text),
# confirmation_type ('redirect'|'qr'), audit_correlation_id (UUID), amount_kopecks > 0,
# and exactly one of membership_plan_id / pt_package_plan_id.


async def _insert_online_payment(
    db_session: AsyncSession,
    *,
    client_id: UUID,
    status: str,
) -> UUID:
    """Insert a minimal online_payments row using raw SQL with a real membership_plan.

    Creates a membership_plan first (to satisfy the FK), then inserts the payment.
    Returns the payment UUID.
    """
    from sqlalchemy import text

    payment_id = uuid4()
    audit_id = uuid4()
    plan_id = uuid4()

    # Create a minimal membership_plan row to satisfy FK
    await db_session.execute(
        text(
            "INSERT INTO membership_plans (id, name, duration_days, price_kopecks, freeze_days_limit) "  # noqa: E501
            "VALUES (:id, :name, 30, 250000, 14)"
        ),
        {"id": str(plan_id), "name": f"test-plan-{plan_id}"},
    )

    await db_session.execute(
        text(
            "INSERT INTO online_payments "
            "(id, client_id, membership_plan_id, status, amount_kopecks, "
            " idempotency_key, yookassa_payment_id, confirmation_type, audit_correlation_id) "
            "VALUES (:id, :cid, :plan_id, :status, 250000, :ikey, :yk_id, 'redirect', :audit)"
        ),
        {
            "id": str(payment_id),
            "cid": str(client_id),
            "plan_id": str(plan_id),
            "status": status,
            "ikey": f"ikey-{payment_id}",
            "yk_id": f"yk-{payment_id}",
            "audit": str(audit_id),
        },
    )
    await db_session.commit()
    return payment_id


async def test_payment_status_succeeded_populates_receipt_email(
    db_session: AsyncSession,
    make_client: Callable[..., Awaitable[Client]],
) -> None:
    """D-09: succeeded payment with email → receipt_email set, receipt_phone None."""
    client = await make_client(email="receipt@example.com")
    payment_id = await _insert_online_payment(db_session, client_id=client.id, status="succeeded")
    result = await service.get_client_payment_status(db_session, payment_id, client.id)
    assert result.status == "succeeded"
    assert result.receipt_email == "receipt@example.com"
    assert result.receipt_phone is None  # email takes precedence


async def test_payment_status_succeeded_phone_fallback_when_no_email(
    db_session: AsyncSession,
    make_client: Callable[..., Awaitable[Client]],
) -> None:
    """D-10: succeeded payment with email=None → receipt_phone set, receipt_email None."""
    client = await make_client(email=None)
    payment_id = await _insert_online_payment(db_session, client_id=client.id, status="succeeded")
    result = await service.get_client_payment_status(db_session, payment_id, client.id)
    assert result.status == "succeeded"
    assert result.receipt_email is None
    assert result.receipt_phone == client.phone


async def test_payment_status_pending_no_receipt_contact(
    db_session: AsyncSession,
    make_client: Callable[..., Awaitable[Client]],
) -> None:
    """Anti-oracle: pending payment → receipt_email and receipt_phone both None."""
    client = await make_client(email="pending@example.com")
    payment_id = await _insert_online_payment(db_session, client_id=client.id, status="pending")
    result = await service.get_client_payment_status(db_session, payment_id, client.id)
    assert result.status == "pending"
    assert result.receipt_email is None
    assert result.receipt_phone is None


async def test_payment_status_canceled_no_receipt_contact(
    db_session: AsyncSession,
    make_client: Callable[..., Awaitable[Client]],
) -> None:
    """Anti-oracle: canceled payment → receipt_email and receipt_phone both None."""
    client = await make_client(email="canceled@example.com")
    payment_id = await _insert_online_payment(db_session, client_id=client.id, status="canceled")
    result = await service.get_client_payment_status(db_session, payment_id, client.id)
    assert result.status == "canceled"
    assert result.receipt_email is None
    assert result.receipt_phone is None
