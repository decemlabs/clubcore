"""Shared fixtures for promo_codes integration tests (Phase 113 PROMO-01/PROMO-02).

Reuses the memberships-package fixture machinery (owner/reception clients,
make_client, make_user, make_plan). Adds:
  - make_promo_code: inserts a PromoCode row directly via the SAVEPOINT session
  - make_redemption: inserts a PromoRedemption row (requires an OnlinePayment stub)
  - _csrf_headers: helper returning X-CSRF-Token from the cookie jar

The make_redemption factory creates a minimal OnlinePayment row first to satisfy
the NOT NULL FK on promo_redemptions.online_payment_id (RESTRICT). The
OnlinePayment stub must satisfy ck_online_payments_exactly_one_subject_fk —
(membership_plan_id IS NOT NULL) <> (pt_package_plan_id IS NOT NULL) — so
make_redemption accepts a membership_plan_id (created via make_plan).
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from uuid import UUID, uuid4

import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.memberships.models import MembershipPlan
from app.modules.online_payments.models import OnlinePayment
from app.modules.promo_codes.models import PromoCode, PromoRedemption

# Re-export memberships package fixtures (owner / reception clients, factories).
from tests.integration.memberships.conftest import (  # noqa: F401
    _client_app_overrides,
    authed_client_owner,
    authed_client_reception,
    db_session_real_commit,
    make_client,
    make_plan,
    make_user,
    redis_clean,
    seeded_owner,
    seeded_reception,
)


def _csrf_headers(client: AsyncClient) -> dict[str, str]:
    """Return ``{X-CSRF-Token: <cookie>}`` for CSRF-protected mutating routes.

    ``or ""`` coerces str | None from httpx.Cookies.get to satisfy mypy strict.
    """
    return {"X-CSRF-Token": client.cookies.get("clubcore_csrf") or ""}


@pytest_asyncio.fixture
async def make_promo_code(
    db_session: AsyncSession,
) -> Callable[..., Awaitable[PromoCode]]:
    """Insert a PromoCode row directly via the SAVEPOINT-mode session.

    All fields are overridable. Returns the refreshed ORM instance so
    tests can read back the generated UUID and timestamps.
    """

    _counter = {"i": 0}

    async def _make(
        *,
        code: str | None = None,
        discount_type: str = "percentage",
        discount_value: int = 1000,  # 10% (percent*100)
        max_uses: int | None = None,
        per_client_limit: int | None = None,
        is_active: bool = True,
        applicable_to: str | None = None,
        description: str | None = None,
    ) -> PromoCode:
        _counter["i"] += 1
        resolved_code = code or f"TESTCODE{_counter['i']:03d}"
        promo = PromoCode(
            code=resolved_code.upper(),
            discount_type=discount_type,
            discount_value=discount_value,
            max_uses=max_uses,
            per_client_limit=per_client_limit,
            is_active=is_active,
            applicable_to=applicable_to,
            description=description,
        )
        db_session.add(promo)
        await db_session.commit()
        await db_session.refresh(promo)
        return promo

    return _make


@pytest_asyncio.fixture
async def make_redemption(
    db_session: AsyncSession,
    make_plan: Callable[..., Awaitable[MembershipPlan]],  # noqa: F811
) -> Callable[..., Awaitable[PromoRedemption]]:
    """Insert a PromoRedemption row directly via the SAVEPOINT-mode session.

    Creates a minimal OnlinePayment stub first (NOT NULL FK RESTRICT on
    promo_redemptions.online_payment_id). The OnlinePayment stub must also
    satisfy ck_online_payments_exactly_one_subject_fk: exactly one of
    membership_plan_id / pt_package_plan_id must be NOT NULL. A MembershipPlan
    row is created via make_plan (re-exported from memberships fixtures).

    Each call gets unique yookassa_payment_id / idempotency_key so the
    per-yookassa_payment_id / per-idempotency_key UNIQUE constraints are safe.

    Parameters
    ----------
    promo_code_id:
        UUID of the PromoCode row to associate.
    client_id:
        UUID of the Client row (FK on promo_redemptions.client_id).
    discount_kopecks:
        Discount applied (must be > 0; CHECK ck_promo_redemptions_discount_kopecks_positive).
    """

    _counter = {"i": 0}

    async def _make(
        *,
        promo_code_id: UUID,
        client_id: UUID,
        discount_kopecks: int = 100,
    ) -> PromoRedemption:
        _counter["i"] += 1
        # A fresh plan per call avoids the uq_online_payments_membership_double_tap
        # partial unique index (client_id + membership_plan_id + date WHERE status != 'canceled').
        plan = await make_plan(name=f"PromoTest Plan {_counter['i']}")

        # Minimal OnlinePayment stub satisfying all NOT NULL + CHECK constraints.
        online_payment = OnlinePayment(
            client_id=client_id,
            membership_plan_id=plan.id,  # satisfies exactly_one_subject_fk
            yookassa_payment_id=f"yoo-test-{_counter['i']}-{uuid4().hex[:8]}",
            idempotency_key=f"idem-test-{_counter['i']}-{uuid4().hex[:8]}",
            amount_kopecks=100000,
            status="succeeded",
            confirmation_type="redirect",
            audit_correlation_id=uuid4(),
        )
        db_session.add(online_payment)
        await db_session.flush()  # materialise id before the FK reference

        redemption = PromoRedemption(
            promo_code_id=promo_code_id,
            client_id=client_id,
            online_payment_id=online_payment.id,
            discount_kopecks=discount_kopecks,
        )
        db_session.add(redemption)
        await db_session.commit()
        await db_session.refresh(redemption)
        return redemption

    return _make
