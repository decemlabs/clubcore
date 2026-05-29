"""Phase 46 D-46-14 #3 / VER-10 — deactivate + refresh concurrent race.

Real-Postgres concurrent ``PATCH /api/v1/users/{id}/deactivate`` (owner
session) + ``POST /api/v1/auth/refresh`` (target user's refresh family)
via ``asyncio.gather``. The refresh race-loses; returns 401 with code in
the anti-oracle-safe set ``{account_inactive, invalid_token,
invalid_session}``.

Phase 43 Plan 43-10 documented that in real prod sequencing the refresh
hits Branch C ``family_reuse_detected -> invalid_token`` (or Branch A
``account_inactive -> invalid_session`` per the anti-oracle harmonisation
in Phase 43 D-43-20), not a literal ``account_inactive`` body code, because
families are revoked in the same UoW as ``is_active=false``. We accept the
full anti-oracle-safe set so the test does not regress on either branch.

Tests SVC001 service-owns-txn boundary in
``users/service.deactivate_user`` + ``auth/service.refresh_session``.
The deactivate path commits is_active=false + revoke_all_sessions +
audit emits in a SINGLE atomic UoW (Phase 43 CR-04). If a regression
splits that UoW, the refresh could observe is_active=true after the
family is already revoked (or vice versa) and slip a fresh access cookie
to a deactivated user — this race test catches the regression.

Mirrors Phase 45 D-45-28 real-commit engine pattern
(``tests/integration/test_payment_receipt_race.py``) and Phase 38
BOOK-TEST-01 (``tests/integration/bookings/test_booking_race.py``)
real-commit + ASGI auth pattern. Uses a local real-commit session
factory (NOT the default SAVEPOINT-wrapped ``db_session``) because the
race is observable only across SEPARATE COMMITTED transactions.

Pass-OR-skip acceptance per Phase 46 Wave-3 convention — cleanly SKIPs
on unreachable Postgres rather than erroring inside ``asyncio.gather``.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import Any
from uuid import uuid4

import pytest
import pytest_asyncio
from asgi_lifespan import LifespanManager
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import get_settings
from app.core.permissions import Role
from app.core.security import hash_password
from app.main import create_app
from app.modules.auth.models import User

pytestmark = pytest.mark.asyncio

_OWNER_PASSWORD = "hunter22hunter22"  # noqa: S105 -- test password literal
_TARGET_PASSWORD = "hunter22hunter22"  # noqa: S105 -- test password literal


@pytest_asyncio.fixture
async def real_commit_engine() -> AsyncIterator[AsyncEngine]:
    """Standalone real-commit engine for the deactivate/refresh race test.

    The default ``db_session`` SAVEPOINT pattern (tests/conftest.py:57)
    composes nested transactions; the deactivate-and-revoke UoW under
    test commits ACROSS multiple service calls, and the refresh
    rotate_refresh equally commits separately. Neither side composes
    with the outer SAVEPOINT and the race is observable only across
    SEPARATE COMMITTED transactions (analogous to BOOK-TEST-01).

    Defensively probes Postgres at fixture entry — cleanly SKIPs on
    unreachable Postgres rather than erroring inside ``asyncio.gather``.
    Cleans up with TRUNCATE at teardown (real-commit writes are not
    rolled back); CASCADE handles the FK chain
    ``refresh_tokens -> users`` and ``audit_log`` partitions.
    """
    settings = get_settings()
    engine = create_async_engine(str(settings.database_url), pool_pre_ping=True)

    try:
        async with engine.connect() as probe:
            await probe.execute(text("select 1"))
    except Exception as exc:  # broad: skip on any connectivity failure
        await engine.dispose()
        pytest.skip(
            f"DATABASE_URL not reachable for D-46-14 #3 / VER-10; "
            f"run `docker compose up postgres` first ({exc!r})"
        )

    try:
        yield engine
    finally:
        async with engine.begin() as conn:
            await conn.execute(
                text("TRUNCATE refresh_tokens, users, audit_log RESTART IDENTITY CASCADE")
            )
        await engine.dispose()


async def _build_authed_client(app: FastAPI, *, email: str, password: str) -> AsyncClient:
    """Authenticate against the REAL app (no SAVEPOINT override).

    Mirrors BOOK-TEST-01's ``_build_authed_client`` — issues a POST
    /api/v1/auth/login that populates the cookie jar with
    ``cc_access`` / ``cc_refresh`` / ``clubcore_csrf``. The caller is
    responsible for closing the client.
    """
    transport = ASGITransport(app=app)
    client = AsyncClient(transport=transport, base_url="http://testserver")
    r = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert r.status_code == 200, f"login failed for {email}: {r.text}"
    return client


async def test_deactivate_refresh_race(
    real_commit_engine: AsyncEngine,
) -> None:
    """Phase 46 D-46-14 #3 / VER-10 — owner deactivate || target refresh race.

    Setup: seed one owner + one reception user (both active), log them in
    separately (each gets its own refresh family bound to its own cookie
    jar).

    Race: ``asyncio.gather`` runs:
      - ``PATCH /api/v1/users/{target_id}/deactivate`` (owner client)
      - ``POST  /api/v1/auth/refresh`` (target client)

    Acceptance — pass on either of the two race orderings:
      A. deactivate-first: refresh observes is_active=false and the
         family revoked → 401 in the anti-oracle-safe set
         ``{account_inactive, invalid_token, invalid_session}``.
      B. refresh-first then deactivate: refresh slipped in before the
         deactivate UoW committed → 200; the NEXT refresh MUST 401 with
         a code in the same anti-oracle-safe set (the SVC001 atomic UoW
         guarantees the second attempt cannot succeed).

    Invariants asserted post-race:
      - ``users.is_active = false`` for the target.
      - Deactivate status in ``{200, 204}`` (D-43-16 + Phase 46 Wave-2
        path-truth correction confirmed PATCH returns 204 in
        ``test_deactivate_owner_real_postgres.py``).
    """
    session_factory = async_sessionmaker(real_commit_engine, expire_on_commit=False)

    owner_email = f"deact-refresh-race-owner-{uuid4().hex[:8]}@example.com"
    target_email = f"deact-refresh-race-target-{uuid4().hex[:8]}@example.com"

    # ── Seed owner + target in a dedicated setup session ────────────────
    async with session_factory() as setup_session:
        owner_hashed = await hash_password(_OWNER_PASSWORD)
        owner = User(
            email=owner_email,
            password_hash=owner_hashed,
            role=Role.OWNER,
            full_name="Deact Refresh Race Owner",
            email_verified=True,
            is_active=True,
            status="active",
        )
        setup_session.add(owner)
        await setup_session.commit()
        await setup_session.refresh(owner)

        target_hashed = await hash_password(_TARGET_PASSWORD)
        target = User(
            email=target_email,
            password_hash=target_hashed,
            role=Role.RECEPTION,
            full_name="Deact Refresh Race Target",
            email_verified=True,
            is_active=True,
            status="active",
        )
        setup_session.add(target)
        await setup_session.commit()
        await setup_session.refresh(target)
        target_id = target.id

    # ── Build the real ASGI app and authenticate both clients ──────────
    app = create_app()
    async with LifespanManager(app):
        # Flush Redis so prior-test rate-limit / idempotency keys don't bleed.
        await app.state.redis.flushdb()

        owner_client = await _build_authed_client(app, email=owner_email, password=_OWNER_PASSWORD)
        target_client = await _build_authed_client(
            app, email=target_email, password=_TARGET_PASSWORD
        )

        try:
            owner_csrf = owner_client.cookies.get("clubcore_csrf") or ""

            async def _deactivate() -> int:
                r = await owner_client.patch(
                    f"/api/v1/users/{target_id}/deactivate",
                    headers={"X-CSRF-Token": owner_csrf},
                )
                return r.status_code

            async def _refresh() -> tuple[int, dict[str, Any]]:
                r = await target_client.post("/api/v1/auth/refresh")
                body = r.json() if r.content else {}
                return r.status_code, body

            deact_status, (refresh_status, refresh_body) = await asyncio.gather(
                _deactivate(), _refresh()
            )

            assert deact_status in {200, 204}, f"deactivate expected 200/204, got {deact_status}"

            # Two race orderings — both are valid per Phase 43 Plan 43-10 lineage.
            #
            # Ordering A (deactivate-first OR concurrent service-layer overlap):
            #   refresh observes the revoked family / inactive user and
            #   anti-oracle-collapses to 401 with code in
            #   {account_inactive, invalid_token, invalid_session}. The
            #   literal ``account_inactive`` is allowed even though the
            #   anti-oracle currently maps it to ``invalid_session`` —
            #   keeping it in the accept set guards against a future
            #   Plan-43-10 reversal where the explicit code is restored.
            #
            # Ordering B (refresh-first):
            #   refresh committed BEFORE the deactivate UoW started; the
            #   next refresh attempt MUST 401 because deactivate revoked
            #   the family it just rotated to.
            allowed_codes = {"account_inactive", "invalid_token", "invalid_session"}
            if refresh_status == 401:
                code = refresh_body.get("code") or refresh_body.get("error")
                assert code in allowed_codes, (
                    f"unexpected code {code!r} on race-loss refresh "
                    f"(expected one of {allowed_codes}, "
                    f"anti-oracle-safe per Phase 43 Plan 43-10 / D-43-20)"
                )
            else:
                assert refresh_status == 200, (
                    f"refresh expected 200 or 401, got {refresh_status} (body: {refresh_body!r})"
                )
                # Ordering B — the SVC001 UoW invariant says the next
                # refresh must fail because deactivate atomically revoked
                # every family belonging to the target user.
                second = await target_client.post("/api/v1/auth/refresh")
                assert second.status_code == 401, (
                    f"post-deactivate refresh MUST 401 "
                    f"(SVC001 UoW broken if 200), got {second.status_code} "
                    f"(body: {second.text!r})"
                )
                second_body: dict[str, Any] = second.json() if second.content else {}
                second_code = second_body.get("code") or second_body.get("error")
                assert second_code in allowed_codes, (
                    f"unexpected code {second_code!r} on post-deactivate "
                    f"refresh (expected one of {allowed_codes}, "
                    f"anti-oracle-safe per Phase 43 Plan 43-10 / D-43-20)"
                )
        finally:
            await owner_client.aclose()
            await target_client.aclose()

    # ── DB invariant: target row reflects the deactivation (atomic UoW) ──
    async with session_factory() as verify_session:
        is_active = await verify_session.scalar(select(User.is_active).where(User.id == target_id))
        assert is_active is False, (
            f"SVC001 UoW invariant broken: target user.is_active={is_active!r} "
            f"after deactivate race (expected False — the atomic UoW must "
            f"commit is_active=false regardless of the refresh race ordering)"
        )
