"""Shared fixtures for reports integration tests (Phase 55 REV/CLR/VIS-R; Phase 56 AUD)."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit_models import AuditLog
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


@pytest_asyncio.fixture
async def make_audit_log_row(
    db_session: AsyncSession,
) -> Callable[..., Awaitable[AuditLog]]:
    """Insert an AuditLog row with explicit created_at for deterministic tests.

    Mirrors make_payment_ledger / make_visit fixture pattern.
    Uses the SAVEPOINT-mode session so teardown rolls back all inserts.

    Required: action, resource_type, created_at.
    Optional: actor_user_id, actor_email_snapshot, resource_id, payload.
    action/resource_type must be valid LOCKED_AUDIT_EVENTS pairs.
    """

    async def _make(
        *,
        action: str,
        resource_type: str,
        created_at: datetime,
        actor_user_id: UUID | None = None,
        actor_email_snapshot: str | None = None,
        resource_id: UUID | None = None,
        payload: dict[str, Any] | None = None,
    ) -> AuditLog:
        row = AuditLog(
            action=action,
            resource_type=resource_type,
            actor_user_id=actor_user_id,
            actor_email_snapshot=actor_email_snapshot,
            resource_id=resource_id,
            payload=payload or {},
        )
        row.created_at = created_at
        db_session.add(row)
        await db_session.commit()
        await db_session.refresh(row)
        return row

    return _make


__all__ = (
    "UTC",
    "datetime",
    "make_audit_log_row",
    "make_payment_ledger",
    "make_visit",
)
