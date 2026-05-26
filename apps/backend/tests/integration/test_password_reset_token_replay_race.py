"""Phase 46 D-46-14 #1 / VER-10 — concurrent password-reset token-replay race.

Real-Postgres concurrent ``POST /api/v1/auth/password-reset/confirm`` via
``asyncio.gather`` with the SAME raw token. The atomic-consume SQL
``UPDATE password_reset_tokens SET consumed_at = NOW()
  WHERE token_hash = :hash AND purpose = :purpose
    AND consumed_at IS NULL AND expires_at > NOW()
  RETURNING id, user_id, audit_correlation_id`` (Phase 44 D-44-14) guarantees
exactly one request observes the consume; the loser hits the
``RETURNING NULL`` branch which the service translates to
:class:`~app.modules.auth.exceptions.InvalidOrExpiredTokenError` → HTTP 410
``invalid_or_expired_token``.

Mirrors Phase 45 D-45-28 ``test_payment_receipt_race.py`` real-commit-engine
pattern. Uses a local real-commit session factory (NOT the default
SAVEPOINT-wrapped ``db_session``) because UPDATE-RETURNING serialisation
fires at COMMIT time across SEPARATE sessions — nested SAVEPOINTs mask
the race. The two concurrent HTTP requests go through ``ASGITransport``
which means the FastAPI lifespan is fired via :class:`LifespanManager`
so the real ``get_db`` dependency resolves against the app's lifespan-bound
sessionmaker (real engine, real commits) — exactly the production shape.

Defensively probes Postgres at fixture entry — ``pytest.skip`` on
unreachable Postgres rather than erroring inside ``asyncio.gather``.
Cleans up with TRUNCATE at teardown; CASCADE handles the FK chain
``password_reset_tokens → users``.
"""

from __future__ import annotations

import asyncio
import hashlib
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
import pytest_asyncio
from asgi_lifespan import LifespanManager
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    async_sessionmaker,
    create_async_engine,
)

from app.core.audit_models import AuditLog
from app.core.config import get_settings
from app.core.models import User
from app.core.permissions import Role
from app.core.security import hash_password
from app.main import create_app
from app.modules.auth.password_reset_token_model import PasswordResetToken

_RACE_USER_EMAIL = "password-reset-race@example.com"
_RACE_RAW_TOKEN = uuid4().hex + uuid4().hex  # 64 hex chars — exercises the wire shape
_RACE_NEW_PASSWORD = "NewRacePass456!"  # noqa: S105 — test fixture, not a real secret


@pytest_asyncio.fixture
async def real_commit_engine() -> AsyncIterator[AsyncEngine]:
    """Standalone real-commit engine for the password-reset token-replay race test.

    The default ``db_session`` SAVEPOINT pattern (``tests/conftest.py:57``)
    composes nested transactions; concurrent UPDATEs from two separate
    sessions cannot race against the ``UPDATE ... RETURNING`` atomic-consume
    inside a single outer SAVEPOINT, so we need a real engine that issues
    real COMMITs.

    Defensively probes Postgres at fixture entry — cleanly SKIPs on
    unreachable Postgres rather than erroring inside ``asyncio.gather``.
    Cleans up with TRUNCATE at teardown (real-commit writes are not
    rolled back); CASCADE handles the FK chain
    ``password_reset_tokens → users``.
    """
    settings = get_settings()
    engine = create_async_engine(str(settings.database_url), pool_pre_ping=True)

    try:
        async with engine.connect() as probe:
            await probe.execute(text("select 1"))
    except Exception as exc:
        await engine.dispose()
        pytest.skip(
            f"DATABASE_URL not reachable for D-46-14 #1; "
            f"run `docker compose up postgres` first ({exc!r})"
        )

    try:
        yield engine
    finally:
        async with engine.begin() as conn:
            await conn.execute(
                text("TRUNCATE password_reset_tokens, audit_log, users RESTART IDENTITY CASCADE")
            )
        await engine.dispose()


@pytest.mark.asyncio
async def test_password_reset_token_replay_race(
    real_commit_engine: AsyncEngine,
) -> None:
    """Two concurrent /password-reset/confirm with same raw token → 1 win, 1 410.

    Race outcome (D-44-14 / D-44-15): exactly one request observes the
    ``UPDATE password_reset_tokens ... WHERE consumed_at IS NULL RETURNING ...``
    yielding a row → 200 envelope(None); the other observes ``RETURNING ()``
    → :class:`InvalidOrExpiredTokenError` → 410 ``invalid_or_expired_token``.
    Exactly one ``password_reset_completed`` audit row is written, and
    exactly one ``password_reset_tokens`` row carries a non-null
    ``consumed_at`` for the seeded ``user_id``.
    """
    session_factory = async_sessionmaker(real_commit_engine, expire_on_commit=False)

    # ── Seed user + a fresh unconsumed token in a setup session ─────────
    user_id = uuid4()
    token_id = uuid4()
    audit_correlation_id = uuid4()
    initial_password_hash = await hash_password("OldRacePass123!")

    async with session_factory() as setup_session:
        setup_session.add(
            User(
                id=user_id,
                email=_RACE_USER_EMAIL,
                password_hash=initial_password_hash,
                role=Role.RECEPTION,
                full_name="Password Reset Race User",
                is_active=True,
                status="active",
                email_verified=True,
            )
        )
        setup_session.add(
            PasswordResetToken(
                id=token_id,
                user_id=user_id,
                purpose="password_reset",
                token_hash=hashlib.sha256(_RACE_RAW_TOKEN.encode()).hexdigest(),
                expires_at=datetime.now(UTC) + timedelta(hours=1),
                audit_correlation_id=audit_correlation_id,
            )
        )
        await setup_session.commit()

    # ── Race: two concurrent POSTs through ASGITransport ────────────────
    # Fresh FastAPI app per test; LifespanManager fires startup so
    # app.state.sessionmaker is bound + register_user_session_invalidator
    # has wired the real invalidator (app/main.py:create_app).
    app = create_app()
    async with LifespanManager(app):
        transport = ASGITransport(app=app)

        async def _confirm() -> int:
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.post(
                    "/api/v1/auth/password-reset/confirm",
                    json={
                        "token": _RACE_RAW_TOKEN,
                        "new_password": _RACE_NEW_PASSWORD,
                    },
                )
                return resp.status_code

        statuses = await asyncio.gather(
            _confirm(),
            _confirm(),
            return_exceptions=False,
        )

    # ── Assertions ──────────────────────────────────────────────────────
    # Race-tight invariant: exactly one success (200), exactly one
    # invalid_or_expired_token (410). The loser CANNOT observe a
    # consumed_at-still-NULL row because UPDATE-RETURNING serialises at
    # the row level under PostgreSQL's default READ COMMITTED isolation.
    assert sorted(statuses) == [200, 410], f"expected one 200 + one 410, got {sorted(statuses)}"

    # ── DB invariants ───────────────────────────────────────────────────
    # Exactly one password_reset_completed audit row exists for this user.
    # `resource_id` on the audit row holds the target user_id per
    # password_reset_service.py:408. The audit_log table has no
    # `target_user_id` column — the user_id flat-kwarg lands in `payload`
    # JSONB (Phase 42 CR-01); we verify via resource_id which is the
    # canonical column-level reference.
    async with session_factory() as verify_session:
        audit_count = await verify_session.scalar(
            select(func.count())
            .select_from(AuditLog)
            .where(
                AuditLog.action == "password_reset_completed",
                AuditLog.resource_id == user_id,
            )
        )
        assert audit_count == 1, (
            f"expected exactly 1 password_reset_completed audit row, got {audit_count}"
        )

        # Exactly one password_reset_tokens row for the seeded user_id
        # carries consumed_at IS NOT NULL — the row our winner UPDATEd.
        consumed_count = await verify_session.scalar(
            select(func.count())
            .select_from(PasswordResetToken)
            .where(
                PasswordResetToken.user_id == user_id,
                PasswordResetToken.consumed_at.is_not(None),
            )
        )
        assert consumed_count == 1, (
            f"expected exactly 1 consumed password_reset_tokens row, got {consumed_count}"
        )

        # Sanity: the consumed row is the one we seeded (token_hash match).
        surviving_token_id = await verify_session.scalar(
            select(PasswordResetToken.id).where(
                PasswordResetToken.user_id == user_id,
                PasswordResetToken.consumed_at.is_not(None),
            )
        )
        assert surviving_token_id == token_id, (
            f"consumed token id {surviving_token_id!r} != seeded {token_id!r}"
        )
