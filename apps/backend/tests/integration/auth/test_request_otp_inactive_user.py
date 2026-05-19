"""Phase 43 CR-03 secondary — request_otp_email silent-drops inactive users.

Pre-fix: getattr(user, "is_active", True) defensive Python read.
Post-fix: SQL predicate User.is_active.is_(True) AND User.deleted_at.is_(None).

The observable effect is unchanged (silent-drop with constant-time floor),
but the predicate is now consistent with the Phase 43 ORM column shape
and the authenticate() / rotate_refresh chokepoints.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permissions import Role
from app.core.security import hash_password
from app.modules.auth.models import OtpCode, User

pytestmark = pytest.mark.asyncio

_FIXTURE_PASSWORD = "OtpInactiveTestPw!"  # noqa: S105 — test password literal


async def test_request_otp_email_active_user_creates_otp_row(
    async_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Baseline — active verified user gets an otp_codes row."""
    user = User(
        email="active-otp-cr03@example.com",
        email_verified=True,
        password_hash=await hash_password(_FIXTURE_PASSWORD),
        role=Role.RECEPTION,
        full_name="Active OTP CR03",
        is_active=True,
        status="active",
    )
    db_session.add(user)
    await db_session.commit()

    response = await async_client.post(
        "/api/v1/auth/otp/request",
        json={"email": user.email, "channel": "email"},
    )
    assert response.status_code == 202, (
        f"Expected 202 for active verified user, got {response.status_code}: {response.text}"
    )

    count = (
        await db_session.execute(
            select(func.count()).select_from(OtpCode).where(
                OtpCode.user_id == user.id,
                OtpCode.channel == "email",
            )
        )
    ).scalar_one()
    assert count == 1, (
        f"Expected 1 OTP row for active user, got {count}."
    )


async def test_request_otp_email_deactivated_user_silent_drops(
    async_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """CR-03 secondary — deactivated user: same 202 anti-oracle shape, NO otp row created."""
    user = User(
        email="deactivated-otp-cr03@example.com",
        email_verified=True,
        password_hash=await hash_password(_FIXTURE_PASSWORD),
        role=Role.RECEPTION,
        full_name="Deactivated OTP CR03",
        is_active=False,  # deactivated from the start
        status="active",
        deactivated_at=datetime.now(tz=UTC),
    )
    db_session.add(user)
    await db_session.commit()

    response = await async_client.post(
        "/api/v1/auth/otp/request",
        json={"email": user.email, "channel": "email"},
    )
    assert response.status_code == 202, (
        f"Expected 202 anti-oracle shape for deactivated user, got {response.status_code}"
    )

    count = (
        await db_session.execute(
            select(func.count()).select_from(OtpCode).where(
                OtpCode.user_id == user.id,
                OtpCode.channel == "email",
            )
        )
    ).scalar_one()
    assert count == 0, (
        "CR-03 secondary — request_otp_email created an otp_codes row for a "
        "deactivated user. The SQL predicate User.is_active.is_(True) must "
        "fold this user into the unknown-email silent-drop bucket. "
        f"Got count={count}"
    )


async def test_request_otp_email_soft_deleted_user_silent_drops(
    async_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Soft-deleted user: same 202 anti-oracle shape, NO otp row created."""
    user = User(
        email="soft-deleted-otp-cr03@example.com",
        email_verified=True,
        password_hash=await hash_password(_FIXTURE_PASSWORD),
        role=Role.RECEPTION,
        full_name="Soft Deleted OTP CR03",
        is_active=False,
        status="active",
        deactivated_at=datetime.now(tz=UTC),
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.execute(
        update(User)
        .where(User.id == user.id)
        .values(deleted_at=datetime.now(tz=UTC))
    )
    await db_session.commit()

    response = await async_client.post(
        "/api/v1/auth/otp/request",
        json={"email": user.email, "channel": "email"},
    )
    assert response.status_code == 202, (
        f"Expected 202 anti-oracle shape for soft-deleted user, got {response.status_code}"
    )

    count = (
        await db_session.execute(
            select(func.count()).select_from(OtpCode).where(
                OtpCode.user_id == user.id,
                OtpCode.channel == "email",
            )
        )
    ).scalar_one()
    assert count == 0, (
        "Soft-deleted user: expected no otp_codes row (silent-drop), "
        f"got count={count}"
    )
