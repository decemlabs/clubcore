"""Shared fixtures for reports integration tests (Phase 55 REV/CLR/VIS-R)."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from uuid import UUID

import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.payments.models import Payment
from app.modules.visits.models import Visit

# Re-export memberships package fixtures (owner / reception clients, factories).
from tests.integration.memberships.conftest import (  # noqa: F401
    _client_app_overrides,
    authed_client_owner,
    authed_client_reception,
    db_session_real_commit,
    make_client,
    make_membership,
    make_plan,
    make_user,
    redis_clean,
    seeded_owner,
    seeded_reception,
)


@pytest_asyncio.fixture
async def make_payment_ledger(
    db_session: AsyncSession,
) -> Callable[..., Awaitable[Payment]]:
    """Insert a Payment row with explicit received_at for deterministic date-window tests.

    Mirrors tests/integration/payments/conftest.py make_payment pattern.
    Uses the SAVEPOINT-mode session so teardown rolls back all inserts.
    """

    async def _make(
        *,
        subject_id: UUID,
        received_by_user_id: UUID,
        amount_kopecks: int,
        method: str = "cash",
        subject_kind: str = "membership",
        received_at: datetime,
    ) -> Payment:
        payment = Payment(
            subject_kind=subject_kind,
            subject_id=subject_id,
            amount_kopecks=amount_kopecks,
            method=method,
            received_by_user_id=received_by_user_id,
        )
        payment.received_at = received_at
        db_session.add(payment)
        await db_session.commit()
        await db_session.refresh(payment)
        return payment

    return _make


@pytest_asyncio.fixture
async def make_visit(
    db_session: AsyncSession,
) -> Callable[..., Awaitable[Visit]]:
    """Insert a Visit row with explicit checked_in_at for deterministic MSK-date tests.

    gym_date is STORED GENERATED (Postgres computes it from checked_in_at via
    ``(checked_in_at AT TIME ZONE 'Europe/Moscow')::date``) — do NOT pass gym_date.

    Required: client_id, membership_id, checked_in_at (timestamptz).
    channel defaults to 'reception'.
    """

    async def _make(
        *,
        client_id: UUID,
        membership_id: UUID,
        checked_in_at: datetime,
        channel: str = "reception",
    ) -> Visit:
        visit = Visit(
            client_id=client_id,
            membership_id=membership_id,
            checked_in_at=checked_in_at,
            channel=channel,
        )
        db_session.add(visit)
        await db_session.commit()
        await db_session.refresh(visit)
        return visit

    return _make


__all__ = (
    "UTC",
    "datetime",
    "make_payment_ledger",
    "make_visit",
)
