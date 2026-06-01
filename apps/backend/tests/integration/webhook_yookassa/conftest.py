"""Phase 50 Plan 50-06 — integration test fixtures for ЮKassa webhook e2e suite.

Anonymous-by-design ``/_internal/yookassa/webhook`` is intentionally NOT
cookie-jarred (D-50-39 / D-50-42). The Phase 49 ``tests/integration/online_payments/
conftest.py`` cookie-jar machinery is DELIBERATELY DROPPED — there is no
``authed_client_owner`` or ``authed_client_reception`` here. Instead the
``webhook_client`` fixture is a plain ``httpx.AsyncClient`` over
``ASGITransport`` with no auth.

Phase 48 / Phase 49 fixtures REUSED via direct import (pytest conftest discovery
is directory-tree-only, so explicit ``# noqa: F401`` re-export is the documented
Sportzal-internal pattern — same shape as ``tests/integration/online_payments/
conftest.py`` lines 49-55):

- ``yookassa_get_payment_pending``  (Phase 48 ADAPTER-06)
- ``yookassa_get_payment_succeeded`` (Phase 48 ADAPTER-06)
- ``yookassa_webhook_payload``      (Phase 48 ADAPTER-06 — canonical body dict)
- ``_YOOKASSA_BASE_URL``            (Phase 48 ADAPTER-06)

New Plan 50-06 fixtures (B-2 / W-5 fixes):

- ``yookassa_get_payment_canceled`` — W-5 fix: explicitly created here (concrete,
  NOT a deferred "may not exist in Phase 48 conftest" hedge). Cancellation-path
  tests (WH-06) depend on it directly.
- ``sqlalchemy_query_log_timestamps`` — B-2 fix (revision 2): records
  ``time.perf_counter()`` per executed SQL statement so the WH-02 ordering test
  can compare against respx ``side_effect`` callback timestamps recorded with
  ``time.perf_counter()`` — SINGLE clock domain on both sides. Revision 1's
  pattern (``respx_mock.calls.last.response.elapsed.total_seconds()`` —
  a ``timedelta`` duration ~0.001s) mismatched a ``perf_counter()`` value
  (~10000s) and made the ordering assertion trivially true regardless of the
  actual call order. The new fixture removes that broken comparison.
- ``webhook_client`` — anonymous ``httpx.AsyncClient`` over ``ASGITransport``;
  no cookie jar, no CSRF, no Idempotency-Key. The webhook is anonymous-by-design.
- ``seeded_online_payment_pending`` (alias: ``seed_online_payment_pending``) —
  factory inserting a pending OnlinePayment row alongside a Client (with email)
  and a MembershipPlan, returning a ``SeededOnlinePayment`` carrier dataclass.
- ``seeded_online_payment_pending_pt_package`` — mirror of the membership
  factory but seeding a ``pt_package_plan_id`` row instead so WH-05 PT-package
  path tests can exercise the activator branch.
- ``webhook_payment_succeeded_body`` / ``webhook_payment_canceled_body`` /
  ``webhook_payment_succeeded_qr_body`` — canonical webhook body factories
  with parameterisable object_id (defaults to a constant; tests pin to the
  seeded row's yookassa_payment_id).
- ``redis_test_client`` — exposes the app-state Redis client; on teardown
  flushes keys with the ``cc:yookassa:webhook:`` prefix to keep tests
  isolated.
- ``YOOKASSA_TRUSTED_IPS`` — re-exported from
  ``app.integrations.yookassa.webhook_verifier`` for tests that need to set a
  realistic ``X-Real-IP`` header.

DROPPED fixture (revision 2):

- ``arq_pool_spy`` — REMOVED. Revision 1 introduced this to record
  ``enqueue()`` calls on the post-commit seam, but the handler passes
  ``arq_pool=None`` positionally to ``_post_commit_enqueue``, so the spy
  mounted on ``app.state.arq_pool`` was never reached (tautological pass
  regardless of stub-body correctness). Replaced by the AST gate in
  ``test_post_commit_seam.py`` which does NOT require a runtime fixture.
"""

from __future__ import annotations

import importlib
import time
from collections.abc import AsyncIterator, Callable, Generator
from dataclasses import dataclass
from typing import Any
from uuid import UUID, uuid4

import httpx
import pytest
import pytest_asyncio
import respx
import structlog
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from redis.asyncio import Redis
from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import get_settings
from app.core.database import get_db
from app.core.redis import get_redis
from app.integrations.yookassa.webhook_verifier import (
    YOOKASSA_TRUSTED_IPS,
)
from app.modules.clients.models import Client
from app.modules.memberships.models import MembershipPlan
from app.modules.online_payments.constants import (
    CONFIRMATION_TYPE_REDIRECT,
    STATUS_PENDING,
)
from app.modules.online_payments.models import OnlinePayment
from app.modules.pt_packages.models import PtPackagePlan

# Re-export Phase 48 respx fixtures + canonical body dict.
from tests.integrations.yookassa.conftest import (  # noqa: F401
    _YOOKASSA_BASE_URL,
    yookassa_get_payment_pending,
    yookassa_get_payment_succeeded,
    yookassa_webhook_payload,
)

# ---------------------------------------------------------------------------
# Plan 50-06 — Structlog reset (mirror Phase 49 conftest pattern). The
# autouse fixture in ``tests/integrations/yookassa/conftest.py`` does NOT
# cascade into this directory; redeclared here so ``capture_logs()`` in the
# webhook tests works deterministically.
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _reset_structlog_for_capture_webhook_integration() -> Generator[None, None, None]:
    """Reset structlog defaults + re-bind the cached factory logger proxy."""
    structlog.reset_defaults()
    try:
        import app.integrations.yookassa.factory as _factory_mod

        importlib.reload(_factory_mod)
    except Exception:  # noqa: S110 -- best-effort isolation, do not fail tests
        pass
    yield


# ---------------------------------------------------------------------------
# W-5 FIX — Concrete `yookassa_get_payment_canceled` fixture.
# ---------------------------------------------------------------------------


@pytest.fixture
def yookassa_get_payment_canceled() -> Generator[respx.MockRouter, None, None]:
    """W-5 fix: this fixture is EXPLICITLY created here (concrete, not a deferred
    'add if not in Phase 48 conftest' hedge). Cancellation-path tests (WH-06)
    depend on it directly.

    GET /v3/payments/{id} → 200 with status='canceled' + cancellation_details.
    """
    with respx.mock(base_url=_YOOKASSA_BASE_URL, assert_all_called=False) as router:
        router.get(url__regex=r"^https://api\.yookassa\.ru/v3/payments/[\w-]+$").mock(
            return_value=httpx.Response(
                200,
                json={
                    "id": "00000000-0000-0000-0000-000000000000",
                    "status": "canceled",
                    "amount": {"value": "100.00", "currency": "RUB"},
                    "cancellation_details": {
                        "party": "yandex_checkout",
                        "reason": "general_decline",
                    },
                },
            )
        )
        yield router


# ---------------------------------------------------------------------------
# B-2 FIX (revision 2) — `sqlalchemy_query_log_timestamps` fixture.
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Real-commit DB session (mirror of
# tests/integration/memberships/conftest.py::db_session_real_commit, D-13).
#
# The webhook handler uses ``async with session.begin():`` which conflicts
# with the root ``db_session`` fixture's ``join_transaction_mode='create_savepoint'``
# pattern (the savepoint-wrapped session is ALREADY inside a transaction by
# the time ``session.begin()`` is called — SQLAlchemy raises
# ``InvalidRequestError: A transaction is already begun on this Session``).
#
# Solution: use a fresh real-commit engine + TRUNCATE cleanup at fixture
# exit. This mirrors the established pattern from
# ``tests/integration/memberships/conftest.py::db_session_real_commit``
# (Plan 25-05 D-13) which exists for the same reason — patterns that need
# real BEGIN/COMMIT semantics cannot compose with nested savepoints.
# ---------------------------------------------------------------------------

# Tables touched by the webhook UoW + activator + payment_recorder +
# fiscal_receipts INSERT. TRUNCATE in this order via CASCADE handles the
# FK chain (audit_log refs users, fiscal_receipts → payments, etc.).
_TRUNCATE_TABLES = (
    "audit_log",
    "fiscal_receipts",
    "payments",
    "memberships",
    "pt_packages",
    "online_payments",
    "membership_plans",
    "pt_package_plans",
    "clients",
    "users",
)


@pytest_asyncio.fixture
async def webhook_engine() -> AsyncIterator[Any]:
    """Real-commit engine SHARED by ``webhook_db_session`` + ``webhook_client``
    + ``sqlalchemy_query_log_timestamps``.

    Sharing the engine matters for the WH-02 ordering test: the SQL listener
    is bound to ``sync_engine``; if seeding + the route used different
    engines, the listener would only see one side's statements.
    """
    settings = get_settings()
    engine = create_async_engine(str(settings.database_url), pool_pre_ping=True)
    try:
        yield engine
    finally:
        # TRUNCATE all tables the webhook flow seeds + writes (CASCADE handles
        # FK references). Runs BEFORE engine.dispose() so the cleanup uses the
        # same connection pool as the test.
        async with engine.begin() as conn:
            await conn.execute(
                text(f"TRUNCATE {', '.join(_TRUNCATE_TABLES)} RESTART IDENTITY CASCADE")
            )
        await engine.dispose()


@pytest_asyncio.fixture
async def webhook_db_session(
    webhook_engine: Any,
) -> AsyncIterator[AsyncSession]:
    """Real BEGIN/COMMIT session for webhook tests.

    The webhook handler uses ``async with session.begin():`` which cannot
    compose with the root SAVEPOINT-mode ``db_session``. Mirrors
    ``db_session_real_commit`` from the memberships conftest (Plan 25-05 D-13).
    """
    session_factory = async_sessionmaker(webhook_engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session


@pytest_asyncio.fixture
async def sqlalchemy_query_log_timestamps(
    webhook_engine: Any,
) -> AsyncIterator[list[tuple[str, float]]]:
    """B-2 fix (revision 2): records `time.perf_counter()` per statement so the
    WH-02 ordering test can compare against respx side_effect callback
    timestamps recorded with `time.perf_counter()` — SINGLE clock domain on
    both sides.

    Bound to the SHARED ``webhook_engine`` (the same engine the route's
    per-request session uses); seeding statements + route statements both
    flow through the listener.

    Earlier draft used `respx_mock.calls.last.response.elapsed.total_seconds()`
    (a timedelta duration ~0.001s) which mismatched a `perf_counter()` value
    (~10000s) and made the assertion trivially true regardless of actual call
    order.
    """
    log: list[tuple[str, float]] = []

    def _before_execute(
        conn: Any,
        clauseelement: Any,
        multiparams: Any,
        params: Any,
        execution_options: Any,
    ) -> None:
        try:
            stmt_text = str(clauseelement.compile(compile_kwargs={"literal_binds": False}))
        except Exception:
            stmt_text = str(clauseelement)
        log.append((stmt_text, time.perf_counter()))

    sync_engine = webhook_engine.sync_engine
    event.listen(sync_engine, "before_execute", _before_execute)
    try:
        yield log
    finally:
        event.remove(sync_engine, "before_execute", _before_execute)


# ---------------------------------------------------------------------------
# Anonymous webhook client + redis helper.
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def webhook_client(
    app: FastAPI,
    webhook_engine: Any,
    webhook_db_session: AsyncSession,
) -> AsyncIterator[AsyncClient]:
    """Anonymous ``httpx.AsyncClient`` over ``ASGITransport`` (D-50-42).

    No cookie jar, no auth, no CSRF, no Idempotency-Key. The Phase 49
    cookie-jar pattern is DELIBERATELY DROPPED — the webhook is
    anonymous-by-design (D-50-39). The X-Real-IP header is settable per
    request when WH-01 tests need a specific IP (``YOOKASSA_SANDBOX=true``
    in .env.example bypasses the verifier anyway — that bypass is the
    happy-path; WH-01 untrusted-IP tests temporarily override the
    ``verify_yookassa_ip`` dependency to force the 403 branch).

    Installs the standard dependency overrides so route handlers see the
    real-commit ``webhook_db_session`` + the lifespan-bound Redis singleton.
    The real-commit session is required because the webhook handler uses
    ``async with session.begin():`` which cannot compose with the root
    SAVEPOINT-mode session.
    """

    # Each route invocation needs a FRESH session (the handler opens its
    # own ``session.begin()`` block). Yielding the same long-lived session
    # for both seeding (the test setup) and the route call would re-trigger
    # the autobegin conflict. So the override creates a per-request session
    # bound to the shared ``webhook_engine`` (same engine the SQL listener
    # is bound to, so WH-02 ordering test sees both sides' statements).
    session_factory = async_sessionmaker(webhook_engine, expire_on_commit=False)

    async def _override_get_db() -> AsyncIterator[AsyncSession]:
        async with session_factory() as session:
            yield session

    def _override_get_redis() -> Any:
        return app.state.redis

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_redis] = _override_get_redis
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            yield client
    finally:
        app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def redis_test_client(app: FastAPI) -> AsyncIterator[Redis]:
    """Expose the app-state Redis client; flush ``cc:yookassa:webhook:*`` after
    each test so dedup keys do not bleed between tests."""
    client: Redis = app.state.redis
    # Pre-clean any leftover keys from a previous run.
    keys = await client.keys("cc:yookassa:webhook:*")
    if keys:
        await client.delete(*keys)
    yield client
    keys = await client.keys("cc:yookassa:webhook:*")
    if keys:
        await client.delete(*keys)


# ---------------------------------------------------------------------------
# DB-direct factories (SAVEPOINT-wrapped session). The factory shapes mirror
# tests/integration/online_payments/conftest.py and tests/integration/
# test_alembic_0035_fiscal_receipts.py — no operator-flow / cookie-jar
# machinery here, just the minimum rows needed to drive the webhook UoW.
# ---------------------------------------------------------------------------


@dataclass
class SeededOnlinePayment:
    """Carrier returned by ``seeded_online_payment_pending`` factory.

    Holds the IDs the tests need to reference; no ORM identity-map lock-in.
    """

    online_payment_id: UUID
    yookassa_payment_id: str
    client_id: UUID
    client_email: str
    client_phone: str
    membership_plan_id: UUID | None
    pt_package_plan_id: UUID | None
    audit_correlation_id: UUID
    amount_kopecks: int


async def _seed_client(
    session: AsyncSession, *, email: str | None = None, phone_only: bool = False
) -> Client:
    """Insert a Client; the OnlinePayment factory wires ``client_id`` to this
    row and the webhook UoW reads the receipt contact (email OR phone) via
    ``_read_client_receipt_contact``.

    D-10 (Phase 999.5) retired the PAY-06 email-NOT-NULL invariant: a phone-only
    «Чек не нужен» client (email NULL, phone set) is valid. When
    ``phone_only=True`` the email is persisted as NULL (NOT coerced to a default)
    so the phone-only webhook path can be exercised end-to-end. Otherwise email
    defaults to a generated address (back-compat with the email-bearing tests).

    Phase 49 sell-flow normally creates Clients via the cookie-jar'd API;
    Plan 50-06 webhook tests skip that scaffolding and INSERT directly via
    the SAVEPOINT-wrapped session.
    """
    nonce = uuid4().hex[:8]
    resolved_email = None if phone_only else email or f"phase50-webhook-{nonce}@example.com"
    # Clients table requires ``created_by_user_id`` (FK NOT NULL); seed an
    # owner first so the FK satisfies.
    from app.core.models import User
    from app.core.permissions import Role
    from app.core.security import hash_password

    owner = User(
        email=f"phase50-webhook-owner-{nonce}@example.com",
        password_hash=await hash_password("hunter22hunter22"),
        role=Role.OWNER,
        full_name="Phase 50 Webhook Test Owner",
    )
    session.add(owner)
    await session.flush()

    client = Client(
        last_name="Иванов",
        first_name="Иван",
        phone=f"+7999{nonce}",
        email=resolved_email,
        created_by_user_id=owner.id,
    )
    session.add(client)
    await session.flush()
    return client


async def _seed_membership_plan(session: AsyncSession) -> MembershipPlan:
    plan = MembershipPlan(
        name=f"Phase50-Webhook-Plan-{uuid4().hex[:6]}",
        duration_days=30,
        price_kopecks=100_000,
        freeze_days_limit=7,
        active=True,
    )
    session.add(plan)
    await session.flush()
    return plan


async def _seed_pt_package_plan(session: AsyncSession) -> PtPackagePlan:
    plan = PtPackagePlan(
        name=f"Phase50-Webhook-PT-{uuid4().hex[:6]}",
        session_count=8,
        price_kopecks=200_000,
        validity_days=60,
    )
    session.add(plan)
    await session.flush()
    return plan


@pytest_asyncio.fixture
async def seeded_online_payment_pending(
    webhook_db_session: AsyncSession,
) -> SeededOnlinePayment:
    """Insert one Client + one MembershipPlan + one OnlinePayment(status='pending').

    Real-commit seed: rows are visible to the route's per-request session
    (which connects to the same DB). Returns a ``SeededOnlinePayment`` carrier.
    Used by WH-02..06 happy paths + the FSM and audit-chain tests.
    """
    client = await _seed_client(webhook_db_session)
    plan = await _seed_membership_plan(webhook_db_session)
    yk_id = f"yk-{uuid4().hex[:24]}"
    corr = uuid4()
    op = OnlinePayment(
        client_id=client.id,
        membership_plan_id=plan.id,
        pt_package_plan_id=None,
        yookassa_payment_id=yk_id,
        idempotency_key=uuid4().hex,
        amount_kopecks=100_000,
        status=STATUS_PENDING,
        confirmation_url="https://example.com/confirm",
        confirmation_type=CONFIRMATION_TYPE_REDIRECT,
        audit_correlation_id=corr,
    )
    webhook_db_session.add(op)
    await webhook_db_session.flush()
    await webhook_db_session.commit()
    return SeededOnlinePayment(
        online_payment_id=op.id,
        yookassa_payment_id=yk_id,
        client_id=client.id,
        client_email=client.email or "",
        client_phone=client.phone,
        membership_plan_id=plan.id,
        pt_package_plan_id=None,
        audit_correlation_id=corr,
        amount_kopecks=100_000,
    )


# Legacy alias kept for back-compat with revision 1 of this plan and any
# external callsites that reference the older name.
seed_online_payment_pending = seeded_online_payment_pending


@pytest_asyncio.fixture
async def seeded_online_payment_pending_phone_only(
    webhook_db_session: AsyncSession,
) -> SeededOnlinePayment:
    """Phone-only «Чек не нужен» seed: Client with email NULL + phone set.

    Mirror of ``seeded_online_payment_pending`` but the client is seeded with
    ``phone_only=True`` so ``clients.email IS NULL`` actually persists. Drives
    the Plan 08 phone-only payment.succeeded path: the webhook must read the
    phone (not raise on the NULL email) and persist a phone-carrying
    fiscal_receipts row. ``client_email`` is the empty string (no email).
    """
    client = await _seed_client(webhook_db_session, phone_only=True)
    plan = await _seed_membership_plan(webhook_db_session)
    yk_id = f"yk-{uuid4().hex[:24]}"
    corr = uuid4()
    op = OnlinePayment(
        client_id=client.id,
        membership_plan_id=plan.id,
        pt_package_plan_id=None,
        yookassa_payment_id=yk_id,
        idempotency_key=uuid4().hex,
        amount_kopecks=100_000,
        status=STATUS_PENDING,
        confirmation_url="https://example.com/confirm",
        confirmation_type=CONFIRMATION_TYPE_REDIRECT,
        audit_correlation_id=corr,
    )
    webhook_db_session.add(op)
    await webhook_db_session.flush()
    await webhook_db_session.commit()
    return SeededOnlinePayment(
        online_payment_id=op.id,
        yookassa_payment_id=yk_id,
        client_id=client.id,
        client_email="",
        client_phone=client.phone,
        membership_plan_id=plan.id,
        pt_package_plan_id=None,
        audit_correlation_id=corr,
        amount_kopecks=100_000,
    )


@pytest_asyncio.fixture
async def seeded_online_payment_pending_pt_package(
    webhook_db_session: AsyncSession,
) -> SeededOnlinePayment:
    """Mirror of ``seeded_online_payment_pending`` for the PT-package branch."""
    client = await _seed_client(webhook_db_session)
    plan = await _seed_pt_package_plan(webhook_db_session)
    yk_id = f"yk-{uuid4().hex[:24]}"
    corr = uuid4()
    op = OnlinePayment(
        client_id=client.id,
        membership_plan_id=None,
        pt_package_plan_id=plan.id,
        yookassa_payment_id=yk_id,
        idempotency_key=uuid4().hex,
        amount_kopecks=200_000,
        status=STATUS_PENDING,
        confirmation_url="https://example.com/confirm",
        confirmation_type=CONFIRMATION_TYPE_REDIRECT,
        audit_correlation_id=corr,
    )
    webhook_db_session.add(op)
    await webhook_db_session.flush()
    await webhook_db_session.commit()
    return SeededOnlinePayment(
        online_payment_id=op.id,
        yookassa_payment_id=yk_id,
        client_id=client.id,
        client_email=client.email or "",
        client_phone=client.phone,
        membership_plan_id=None,
        pt_package_plan_id=plan.id,
        audit_correlation_id=corr,
        amount_kopecks=200_000,
    )


@pytest.fixture
def webhook_payment_succeeded_body() -> Callable[[str], dict[str, Any]]:
    """Factory returning a canonical payment.succeeded webhook body for a given
    yookassa_payment_id.
    """

    def _build(object_id: str) -> dict[str, Any]:
        return {
            "event": "payment.succeeded",
            "object": {
                "id": object_id,
                "status": "succeeded",
                "amount": {"value": "1000.00", "currency": "RUB"},
            },
        }

    return _build


@pytest.fixture
def webhook_payment_canceled_body() -> Callable[[str], dict[str, Any]]:
    """Factory returning a canonical payment.canceled webhook body with
    cancellation_details for a given yookassa_payment_id.
    """

    def _build(
        object_id: str,
        *,
        party: str | None = "yoo_money",
        reason: str | None = "fraud_suspected",
    ) -> dict[str, Any]:
        body: dict[str, Any] = {
            "event": "payment.canceled",
            "object": {
                "id": object_id,
                "status": "canceled",
            },
        }
        if party is not None or reason is not None:
            details: dict[str, str] = {}
            if party is not None:
                details["party"] = party
            if reason is not None:
                details["reason"] = reason
            body["object"]["cancellation_details"] = details
        return body

    return _build


@pytest.fixture
def webhook_payment_succeeded_qr_body() -> Callable[[str], dict[str, Any]]:
    """Factory returning a payment.succeeded body for a PT-package / QR sale."""

    def _build(object_id: str) -> dict[str, Any]:
        return {
            "event": "payment.succeeded",
            "object": {
                "id": object_id,
                "status": "succeeded",
                "amount": {"value": "2000.00", "currency": "RUB"},
                "paid": True,
            },
        }

    return _build


# ---------------------------------------------------------------------------
# Helper: trusted IP header used across the success-path tests so the IP
# allowlist accepts the request even with YOOKASSA_SANDBOX=false (the
# sandbox bypass in .env.example is the default, but tests that explicitly
# turn it off rely on this helper to spoof a trusted IP).
# ---------------------------------------------------------------------------


def trusted_ip_header() -> dict[str, str]:
    """Return a header dict with ``X-Real-IP`` set to a value inside
    YOOKASSA_TRUSTED_IPS.

    Used by WH-01's trusted-IP smoke test. Most other tests rely on the
    ``YOOKASSA_SANDBOX=true`` default (Phase 47 D-47-07 — verifier returns
    immediately when ``settings.sandbox`` is True).
    """
    # First CIDR in the set, take its network address.
    import ipaddress

    cidr = next(iter(YOOKASSA_TRUSTED_IPS))
    network = ipaddress.ip_network(cidr)
    return {"X-Real-IP": str(network.network_address)}


__all__ = (
    "SeededOnlinePayment",
    "seed_online_payment_pending",
    "trusted_ip_header",
)


# Re-export the ``app`` and ``db_session`` fixtures from the root conftest by
# name (pytest will find them via the parent-directory walk; this comment
# documents the dependency so a developer adding a new fixture does not
# accidentally duplicate the SAVEPOINT machinery).
#
# The ``make_user`` / ``make_client_*`` factories live in
# ``tests/integration/online_payments/conftest.py`` but are NOT re-exported
# here — the webhook UoW seeds its rows inline (``_seed_client`` /
# ``_seed_membership_plan`` / ``_seed_pt_package_plan``) to keep the test
# wiring self-contained.
