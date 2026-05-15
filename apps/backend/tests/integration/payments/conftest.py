"""Shared fixtures for payments integration tests (Phase 32 PAY-06..08).

Reuses the memberships-package fixture machinery to seed owner/reception
users, plans, clients, memberships. Adds a ``make_payment`` factory that
inserts Payment rows directly via the SAVEPOINT-mode session so list tests
have deterministic ledger content without going through the (Plan 32-02)
sale-flow HTTP path.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from uuid import UUID

import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.payments.constants import SUBJECT_KIND_MEMBERSHIP
from app.modules.payments.models import Payment

# Re-export memberships package fixtures (owner / reception clients, factories).
from tests.integration.memberships.conftest import (  # noqa: F401
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
    _client_app_overrides,
)


@pytest_asyncio.fixture
async def make_payment(
    db_session: AsyncSession,
) -> Callable[..., Awaitable[Payment]]:
    """Insert a Payment row directly via the SAVEPOINT-mode session.

    Provides explicit-timestamp + explicit-method overrides so date-window
    and method-filter tests can pin the resulting rows deterministically.
    """

    async def _make(
        *,
        subject_id: UUID,
        received_by_user_id: UUID,
        subject_kind: str = SUBJECT_KIND_MEMBERSHIP,
        amount_kopecks: int = 250000,
        method: str = "cash",
        refund_of: UUID | None = None,
        received_at: datetime | None = None,
    ) -> Payment:
        payment = Payment(
            subject_kind=subject_kind,
            subject_id=subject_id,
            amount_kopecks=amount_kopecks,
            method=method,
            received_by_user_id=received_by_user_id,
            refund_of=refund_of,
        )
        if received_at is not None:
            payment.received_at = received_at
        db_session.add(payment)
        await db_session.commit()
        await db_session.refresh(payment)
        return payment

    return _make


# Re-export datetime helper for tests.
__all__ = ("make_payment", "UTC", "datetime")
