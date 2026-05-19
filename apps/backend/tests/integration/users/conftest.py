"""Shared fixtures for users-module integration tests (Phase 43 plan 43-07b).

Source plan: ``.planning/phases/43-multi-user-admin-module/43-07b-PLAN.md``.

Consumer plans (Wave 4):
  - 43-08 — POST /api/v1/users edge tests (uses ``seeded_active_reception_email``)
  - 43-09 — deactivate / reactivate self-guard + last-owner guard
            (uses ``current_owner_user_id`` + ``single_active_owner_id``)
  - 43-10 — session invalidation + soft-delete refresh-break
            (uses ``fresh_authed_reception_client[_2]`` + matching user-id fixtures)
  - 43-11 — invitation sandbox email capture
            (uses ``sandbox_email_client``)
  - 43-12 — refresh anti-oracle 4-case sweep
            (uses ``refresh_client_active/_deactivated/_soft_deleted/_unknown_token``
             + ``deactivated_user_id``)

INVARIANT — this file is the single owner of users-module test fixtures.
Wave 4 test plans MUST NOT modify it. Any new shared fixture lands here
via a follow-up Wave-3-style plan, never as a side-edit from a Wave 4
plan.

Structural mirror of ``tests/integration/clients/conftest.py``:
  - Same OWNER/RECEPTION email + password constants pattern.
  - Same ``_seed_user`` / ``_login`` private helpers (extended with the
    Phase 43 lifecycle columns: ``status``, ``is_active``,
    ``deactivated_at``, ``deleted_at``).
  - Same ``redis_clean`` + ``_client_app_overrides`` +
    ``authed_client_owner`` / ``authed_client_reception`` shape so route
    handlers see the SAVEPOINT-rolled session.

Deviations from the clients/conftest.py analog:
  - Adds USERS-specific fixtures listed under "Consumer plans" above.
  - Adds a test-only ``RecordingEmailDispatcher`` that satisfies the
    Phase 41 ``EmailDispatcher`` Protocol and records every send for the
    ``sandbox_email_client`` fixture. The prod ``SandboxEmailClient``
    (``app.integrations.email.client.SandboxEmailClient``) does NOT
    capture envelopes — it's a no-op stub for dev/preview. The
    Phase 43 plan 43-11 test asserts on captured ``sent_emails`` shape,
    so this conftest registers a recording dispatcher via
    ``register_email_dispatcher`` and restores the prior slot on
    teardown.
  - User-status semantics align with the Phase 43 D-43-05 schema:
    deactivated rows carry ``is_active=False`` + ``deactivated_at``
    while ``status`` stays ``'active'`` (the ``user_status`` enum only
    admits ``'active'`` / ``'pending_invitation'`` — see
    ``app.core.models.User``). The plan-text reference to
    ``status='deactivated'`` is a deviation noted in 43-07b-SUMMARY.md.
"""

from __future__ import annotations

import secrets
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any, Literal
from uuid import UUID

import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from redis.asyncio import Redis
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import (
    _email_dispatcher as _email_dispatcher_module_ref,  # noqa: F401 -- imported to document the slot
)
from app.core.dependencies import (
    get_email_dispatcher,
    register_email_dispatcher,
)
from app.core.models import User
from app.core.permissions import Role
from app.core.redis import get_redis
from app.core.security import hash_password

OWNER_EMAIL = "users-owner@example.com"
OWNER_PASSWORD = "hunter22hunter22"  # noqa: S105 -- test password literal (>=12 chars)
RECEPTION_EMAIL = "users-reception@example.com"
RECEPTION_PASSWORD = "hunter22hunter22"  # noqa: S105 -- test password literal


# ---------------------------------------------------------------------------
# Helpers (sync API; ``_seed_user`` is async but not a pytest fixture).
# ---------------------------------------------------------------------------


async def _seed_user(
    db_session: AsyncSession,
    *,
    role: Role,
    email: str,
    password: str | None,
    full_name: str,
    status: Literal["active", "pending_invitation"] = "active",
    is_active: bool = True,
    deleted_at: datetime | None = None,
    deactivated_at: datetime | None = None,
    email_verified: bool = True,
) -> User:
    """Insert a User row in the SAVEPOINT-rolled session (Phase 5 D-22).

    Extended (Phase 43 D-43-05/06/08) with the user-lifecycle columns so a
    single helper produces every variant required by the Wave 4 fixtures:
      - active reception / owner
      - deactivated (``is_active=False`` + ``deactivated_at=now()``;
        ``status`` stays ``'active'`` per the CHECK in migration 0030)
      - soft-deleted (``deleted_at=now()`` + ``is_active=False``)
      - pending_invitation (``status='pending_invitation'``,
        ``password_hash`` may be NULL until Phase 44 RESET-04)
    """
    user = User(
        email=email,
        password_hash=(await hash_password(password)) if password is not None else None,
        role=role,
        full_name=full_name,
        email_verified=email_verified,
        status=status,
        is_active=is_active,
        deactivated_at=deactivated_at,
        deleted_at=deleted_at,
    )
    db_session.add(user)
    await db_session.commit()
    return user


async def _login(client: AsyncClient, *, email: str, password: str) -> None:
    r = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert r.status_code == 200, r.text


def _csrf_headers(client: AsyncClient) -> dict[str, str]:
    """Return ``{X-CSRF-Token: <cookie>}`` for CSRF-protected mutating routes.

    Re-exported here so consumer test modules can ``from .conftest import
    _csrf_headers`` instead of redefining the one-liner per file.
    """
    return {"X-CSRF-Token": client.cookies.get("sportzal_csrf") or ""}


# ---------------------------------------------------------------------------
# Test-only EmailDispatcher recorder (43-11 consumer).
# ---------------------------------------------------------------------------


class RecordingEmailDispatcher:
    """Satisfies the Phase 41 ``EmailDispatcher`` Protocol; records every send.

    Phase 43 plan 43-11 asserts on ``sandbox_email_client.sent_emails`` —
    a list of envelope dicts merging the dispatcher kwargs (``template_id``,
    ``to``, ``audit_correlation_id``) with the rendered ``subject`` /
    ``html`` / ``text`` template vars the service emits at enqueue time
    (Phase 43 D-43-24 render-at-enqueue). The prod
    ``SandboxEmailClient`` (no-op stub at
    ``app/integrations/email/client.py:174``) does NOT capture envelopes —
    hence this test-only recorder.
    """

    def __init__(self) -> None:
        self.sent_emails: list[dict[str, Any]] = []

    async def __call__(
        self,
        *,
        template_id: str,
        to: str,
        audit_correlation_id: UUID | None,
        **template_vars: Any,
    ) -> None:
        self.sent_emails.append(
            {
                "template_id": template_id,
                "to": to,
                "audit_correlation_id": audit_correlation_id,
                **template_vars,
            }
        )


# ---------------------------------------------------------------------------
# Core fixtures (mirrors clients/conftest.py).
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def redis_clean(app: FastAPI) -> Redis:
    """Flush Redis between tests so rate-limit + session keys don't bleed."""
    client: Redis = app.state.redis
    await client.flushdb()
    return client


@pytest_asyncio.fixture
async def seeded_owner(
    db_session: AsyncSession,
    redis_clean: Redis,
) -> User:
    """Owner user seeded via SAVEPOINT-rolled session (rolls back at teardown)."""
    return await _seed_user(
        db_session,
        role=Role.OWNER,
        email=OWNER_EMAIL,
        password=OWNER_PASSWORD,
        full_name="Users Owner",
    )


@pytest_asyncio.fixture
async def seeded_reception(
    db_session: AsyncSession,
    redis_clean: Redis,
) -> User:
    """Reception user seeded via SAVEPOINT-rolled session."""
    return await _seed_user(
        db_session,
        role=Role.RECEPTION,
        email=RECEPTION_EMAIL,
        password=RECEPTION_PASSWORD,
        full_name="Users Reception",
    )


@pytest_asyncio.fixture
async def _client_app_overrides(
    app: FastAPI,
    db_session: AsyncSession,
) -> AsyncIterator[FastAPI]:
    """Install dependency overrides on ``app`` so route handlers see the
    SAVEPOINT-rolled session and the lifespan-bound Redis singleton.

    Mirrors the root ``async_client`` fixture (tests/conftest.py) — required
    because each ``authed_client_*`` fixture builds its own AsyncClient and
    must share the same overrides for routes to see seeded data and
    audit_log writes the test inspects directly.
    """

    async def _override_get_db() -> AsyncIterator[AsyncSession]:
        yield db_session

    def _override_get_redis() -> Any:
        return app.state.redis

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_redis] = _override_get_redis
    try:
        yield app
    finally:
        app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def authed_client_owner(
    _client_app_overrides: FastAPI,
    seeded_owner: User,
) -> AsyncIterator[AsyncClient]:
    """Authenticated httpx client for the seeded owner (cookies in jar)."""
    transport = ASGITransport(app=_client_app_overrides)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        await _login(client, email=OWNER_EMAIL, password=OWNER_PASSWORD)
        yield client


@pytest_asyncio.fixture
async def authed_client_reception(
    _client_app_overrides: FastAPI,
    seeded_reception: User,
) -> AsyncIterator[AsyncClient]:
    """Authenticated httpx client for the seeded reception user."""
    transport = ASGITransport(app=_client_app_overrides)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        await _login(client, email=RECEPTION_EMAIL, password=RECEPTION_PASSWORD)
        yield client


# ---------------------------------------------------------------------------
# B. Owner-introspection fixtures (43-09 consumer).
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def current_owner_user_id(
    authed_client_owner: AsyncClient,
    db_session: AsyncSession,
) -> UUID:
    """Return the seeded owner's UUID pinned by ``OWNER_EMAIL`` (deterministic id).

    Depends on ``authed_client_owner`` purely as an ordering hint so the
    owner row is guaranteed to be inserted before the SELECT.
    """
    _ = authed_client_owner  # ordering dep, value unused
    row = await db_session.scalar(
        select(User).where(User.email == OWNER_EMAIL, User.deleted_at.is_(None))
    )
    assert row is not None, f"seeded owner row not found for {OWNER_EMAIL}"
    return row.id


@pytest_asyncio.fixture
async def single_active_owner_id(
    seeded_owner: User,
    db_session: AsyncSession,
) -> UUID:
    """Ensure exactly one active+non-deleted owner exists; return its id.

    If extra active owners are present, soft-deactivates the extras
    (``is_active=False`` + ``deactivated_at=now()``; ``status`` stays
    ``'active'`` per the migration-0030 CHECK constraint). The seeded
    owner pinned by ``OWNER_EMAIL`` is preserved as the survivor — this
    makes ``single_active_owner_id == current_owner_user_id`` and lets
    43-09 force the last-owner guard deterministically.
    """
    now = datetime.now(tz=UTC)
    await db_session.execute(
        update(User)
        .where(
            User.role == Role.OWNER,
            User.is_active.is_(True),
            User.deleted_at.is_(None),
            User.id != seeded_owner.id,
        )
        .values(is_active=False, deactivated_at=now)
    )
    await db_session.commit()
    return seeded_owner.id


# ---------------------------------------------------------------------------
# C. Active-existing email fixture (43-08 consumer).
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def seeded_active_reception_email(db_session: AsyncSession) -> str:
    """Seed an active reception user; return its email string.

    43-08 uses this email to assert POST /api/v1/users returns 409
    ``email_already_active`` on duplicate-active.
    """
    email = "active-existing@example.com"
    await _seed_user(
        db_session,
        role=Role.RECEPTION,
        email=email,
        password="hunter22hunter22",  # noqa: S106 -- test password literal
        full_name="Seeded Active",
        status="active",
        is_active=True,
        email_verified=True,
    )
    return email


# ---------------------------------------------------------------------------
# D. Deactivated / soft-deleted user fixtures (43-09 / 43-10 / 43-12).
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def deactivated_user(db_session: AsyncSession) -> User:
    """Insert a reception user already in the deactivated state.

    Schema (migration 0030) requires
    ``(is_active=true AND deactivated_at IS NULL)
     OR (is_active=false AND deactivated_at IS NOT NULL)``;
    ``status`` only admits ``'active'`` / ``'pending_invitation'``. So
    "deactivated" is encoded as ``status='active'`` +
    ``is_active=False`` + ``deactivated_at=now()``.
    """
    return await _seed_user(
        db_session,
        role=Role.RECEPTION,
        email="deactivated-existing@example.com",
        password="hunter22hunter22",  # noqa: S106 -- test password literal
        full_name="Deactivated User",
        status="active",
        is_active=False,
        deactivated_at=datetime.now(tz=UTC),
    )


@pytest_asyncio.fixture
async def deactivated_user_id(deactivated_user: User) -> UUID:
    """Alias used by 43-12 anti-oracle audit-row assertion."""
    return deactivated_user.id


@pytest_asyncio.fixture
async def soft_deleted_user(db_session: AsyncSession) -> User:
    """Insert a reception user already soft-deleted (``deleted_at IS NOT NULL``)."""
    now = datetime.now(tz=UTC)
    return await _seed_user(
        db_session,
        role=Role.RECEPTION,
        email="soft-deleted-existing@example.com",
        password="hunter22hunter22",  # noqa: S106 -- test password literal
        full_name="Soft Deleted User",
        status="active",
        is_active=False,
        deactivated_at=now,
        deleted_at=now,
    )


# ---------------------------------------------------------------------------
# E. Session-pair fixtures (43-10 consumer).
# ---------------------------------------------------------------------------


_FRESH_RECEPTION_PASSWORD = "hunter22hunter22"  # noqa: S105 -- test password literal


async def _make_authed_client_for_user(
    app: FastAPI,
    *,
    email: str,
) -> AsyncIterator[AsyncClient]:
    """Internal helper — build an AsyncClient against ``app`` and log in.

    Not a pytest fixture: consumers in this file wire it into
    ``pytest_asyncio.fixture``-flavoured generators below so the cookie
    jar lives for the test lifetime.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        await _login(client, email=email, password=_FRESH_RECEPTION_PASSWORD)
        yield client


@pytest_asyncio.fixture
async def fresh_authed_reception_user_id(
    db_session: AsyncSession,
    redis_clean: Redis,
) -> UUID:
    """Seed a NEW reception row distinct from ``seeded_reception``; return id."""
    _ = redis_clean  # ordering dep
    user = await _seed_user(
        db_session,
        role=Role.RECEPTION,
        email="fresh-reception-1@example.com",
        password=_FRESH_RECEPTION_PASSWORD,
        full_name="Fresh Reception 1",
    )
    return user.id


@pytest_asyncio.fixture
async def fresh_authed_reception_client(
    _client_app_overrides: FastAPI,
    fresh_authed_reception_user_id: UUID,
) -> AsyncIterator[AsyncClient]:
    """Logged-in AsyncClient for the ``fresh_authed_reception_user_id`` row."""
    _ = fresh_authed_reception_user_id  # ordering dep — row already inserted
    async for client in _make_authed_client_for_user(
        _client_app_overrides, email="fresh-reception-1@example.com"
    ):
        yield client


@pytest_asyncio.fixture
async def fresh_authed_reception_user_id_2(
    db_session: AsyncSession,
    redis_clean: Redis,
) -> UUID:
    """Second seeded reception row for the soft-delete branch of 43-10."""
    _ = redis_clean
    user = await _seed_user(
        db_session,
        role=Role.RECEPTION,
        email="fresh-reception-2@example.com",
        password=_FRESH_RECEPTION_PASSWORD,
        full_name="Fresh Reception 2",
    )
    return user.id


@pytest_asyncio.fixture
async def fresh_authed_reception_client_2(
    _client_app_overrides: FastAPI,
    fresh_authed_reception_user_id_2: UUID,
) -> AsyncIterator[AsyncClient]:
    """Logged-in AsyncClient for ``fresh_authed_reception_user_id_2``."""
    _ = fresh_authed_reception_user_id_2
    async for client in _make_authed_client_for_user(
        _client_app_overrides, email="fresh-reception-2@example.com"
    ):
        yield client


# ---------------------------------------------------------------------------
# F. Sandbox email fixture (43-11 consumer).
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def sandbox_email_client(app: FastAPI) -> AsyncIterator[RecordingEmailDispatcher]:
    """Register a recording ``EmailDispatcher`` for the test; yield it.

    Resolution path: the dispatcher is the Phase 41 D-41-24 Protocol slot
    set via ``app.core.dependencies.register_email_dispatcher``. The prod
    wiring (``app.main.create_app``) registers
    ``enqueue_email_dispatch`` (Phase 42 D-42-26). For tests we
    monkey-patch the slot to a ``RecordingEmailDispatcher`` and restore
    the prior callable on teardown so we don't poison subsequent tests
    that rely on the prod dispatcher being live.

    Note: the ``app`` argument is included for fixture-graph parity with
    the plan signature; the slot itself is a module-level global on
    ``app.core.dependencies`` and is NOT carried on ``app.state``.
    """
    _ = app  # fixture-graph ordering only
    from app.core import dependencies as deps_mod

    prior = deps_mod._email_dispatcher
    recorder = RecordingEmailDispatcher()
    register_email_dispatcher(recorder)
    try:
        yield recorder
    finally:
        # Restore prior slot (may be None if app fixture wasn't fully wired).
        if prior is not None:
            register_email_dispatcher(prior)
        else:
            deps_mod._email_dispatcher = None


# ---------------------------------------------------------------------------
# G. Refresh-token 4-case fixtures (43-12 consumer).
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def refresh_client_active(
    _client_app_overrides: FastAPI,
    db_session: AsyncSession,
    redis_clean: Redis,
) -> AsyncIterator[AsyncClient]:
    """Active reception logged in; refresh cookie present + user-row valid."""
    _ = redis_clean
    email = "refresh-active@example.com"
    await _seed_user(
        db_session,
        role=Role.RECEPTION,
        email=email,
        password=_FRESH_RECEPTION_PASSWORD,
        full_name="Refresh Active",
    )
    async for client in _make_authed_client_for_user(_client_app_overrides, email=email):
        yield client


@pytest_asyncio.fixture
async def refresh_client_deactivated(
    _client_app_overrides: FastAPI,
    db_session: AsyncSession,
    redis_clean: Redis,
    deactivated_user_id: UUID,
) -> AsyncIterator[AsyncClient]:
    """Issue a refresh cookie, THEN flip the user row to deactivated.

    Anti-oracle target (Phase 43 D-43-20): ``/api/v1/auth/refresh`` must
    return the same shape/body as the unknown-token case for this client
    because the user-row predicate (``is_active AND deleted_at IS NULL``)
    fails AFTER the cookie was issued.

    Uses the same row referenced by ``deactivated_user_id`` — but that
    fixture inserts the row already-deactivated, which would block the
    initial ``_login`` here. Strategy: seed a separate row, log in, then
    deactivate; expose ``deactivated_user_id`` independently so the test
    can audit-assert against either (per 43-12 plan, the audit row only
    needs SOME deactivated-user id and 43-12 reads it from the
    ``deactivated_user_id`` fixture, not from this client).
    """
    _ = redis_clean
    _ = deactivated_user_id  # fixture-graph ordering; audit-row consumer
    email = "refresh-deactivated@example.com"
    user = await _seed_user(
        db_session,
        role=Role.RECEPTION,
        email=email,
        password=_FRESH_RECEPTION_PASSWORD,
        full_name="Refresh Deactivated",
    )
    transport = ASGITransport(app=_client_app_overrides)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        await _login(client, email=email, password=_FRESH_RECEPTION_PASSWORD)
        # Flip user inactive AFTER cookie issuance — cookie is structurally
        # valid but the user-row predicate now fails.
        now = datetime.now(tz=UTC)
        await db_session.execute(
            update(User).where(User.id == user.id).values(is_active=False, deactivated_at=now)
        )
        await db_session.commit()
        yield client


@pytest_asyncio.fixture
async def refresh_client_soft_deleted(
    _client_app_overrides: FastAPI,
    db_session: AsyncSession,
    redis_clean: Redis,
) -> AsyncIterator[AsyncClient]:
    """Issue a refresh cookie, THEN soft-delete the user row."""
    _ = redis_clean
    email = "refresh-soft-deleted@example.com"
    user = await _seed_user(
        db_session,
        role=Role.RECEPTION,
        email=email,
        password=_FRESH_RECEPTION_PASSWORD,
        full_name="Refresh Soft Deleted",
    )
    transport = ASGITransport(app=_client_app_overrides)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        await _login(client, email=email, password=_FRESH_RECEPTION_PASSWORD)
        now = datetime.now(tz=UTC)
        await db_session.execute(
            update(User)
            .where(User.id == user.id)
            .values(is_active=False, deactivated_at=now, deleted_at=now)
        )
        await db_session.commit()
        yield client


@pytest_asyncio.fixture
async def refresh_client_unknown_token(
    _client_app_overrides: FastAPI,
    redis_clean: Redis,
) -> AsyncIterator[AsyncClient]:
    """Bare AsyncClient with a syntactically valid but never-issued refresh cookie.

    No ``_login`` is performed. A 48-byte URL-safe token is set on
    ``sz_refresh`` and a 64-hex CSRF token on ``sportzal_csrf`` so the
    request reaches the refresh handler the same way the active /
    deactivated / soft-deleted clients do — the difference is the
    refresh-token lookup returns no row.
    """
    _ = redis_clean
    transport = ASGITransport(app=_client_app_overrides)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        client.cookies.set("sz_refresh", secrets.token_urlsafe(48))
        client.cookies.set("sportzal_csrf", secrets.token_hex(32))
        yield client


# Surface ``get_email_dispatcher`` for tests that want to introspect the
# slot state without importing from ``app.core.dependencies`` directly.
__all__ = [
    "OWNER_EMAIL",
    "OWNER_PASSWORD",
    "RECEPTION_EMAIL",
    "RECEPTION_PASSWORD",
    "RecordingEmailDispatcher",
    "_csrf_headers",
    "get_email_dispatcher",
]
