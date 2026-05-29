"""Phase 46 D-46-14 #2 / VER-10 — soft-delete + re-invite concurrent race.

Real-Postgres concurrent ``DELETE /api/v1/users/{old_id}`` + ``POST /api/v1/users``
with the same email via :func:`asyncio.gather`. The partial-UNIQUE
``uq_users_email_active ON (lower(email)) WHERE deleted_at IS NULL`` (Alembic
0022) permits the second INSERT only AFTER the first row's ``deleted_at`` lands.

Mirrors the Phase 45 D-45-28 ``test_payment_receipt_race.py`` real-commit
engine pattern: a self-contained ``real_commit_engine`` fixture issues real
COMMITs so concurrent INSERTs across SEPARATE sessions actually race against
the partial UNIQUE index at COMMIT time. The default SAVEPOINT ``db_session``
fixture composes nested transactions and cannot demonstrate this serialisation.

Race outcomes — both legitimate per partial-UNIQUE semantics + the
Phase 43 D-43-13 four-branch idempotent ``create_user``:

* DELETE first, POST after → 204 + 201, two rows in the table — one
  soft-deleted (the old row), one new active (the re-invite).
* POST first while the old row is still active → INSERT either blocks on
  the partial UNIQUE and converts to 409 via the Branch A IntegrityError
  translation, OR the duplicate-email guard in service.create_user
  short-circuits to 409 ``email_already_active``.

The invariant the test enforces — independent of ordering — is "exactly one
active row with this email exists post-race AND the old row is soft-deleted".
That invariant is the production contract Alembic 0022 + the soft-delete
service path are jointly responsible for.

Pass-OR-skip: the test cleanly skips if Postgres is unreachable so it never
blocks suites running on machines without docker-compose up.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import Any
from uuid import uuid4

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import get_settings
from app.core.database import get_db
from app.core.models import User
from app.core.permissions import Role
from app.core.redis import get_redis
from app.core.security import hash_password
from app.main import create_app

_RACE_OWNER_EMAIL = "soft-delete-race-owner@example.com"
_RACE_OWNER_PASSWORD = "hunter22hunter22"  # noqa: S105 -- test password literal


@pytest_asyncio.fixture
async def real_commit_engine() -> AsyncIterator[AsyncEngine]:
    """Standalone real-commit engine for the soft-delete + re-invite race.

    The default ``db_session`` SAVEPOINT pattern (tests/conftest.py:57)
    composes nested transactions; concurrent INSERTs from two separate
    sessions cannot race against the partial-UNIQUE index inside a single
    outer SAVEPOINT, so this fixture spins up its own engine that issues
    real COMMITs.

    Defensively probes Postgres at fixture entry — cleanly SKIPs on
    unreachable Postgres rather than erroring inside ``asyncio.gather``.
    Cleans up with TRUNCATE at teardown (real-commit writes are not rolled
    back); CASCADE handles every FK chain seeded by the users module
    (password_reset_tokens, audit_log).
    """
    settings = get_settings()
    engine = create_async_engine(str(settings.database_url), pool_pre_ping=True)

    try:
        async with engine.connect() as probe:
            await probe.execute(text("select 1"))
    except Exception as exc:  # broad: skip on any connectivity failure
        await engine.dispose()
        pytest.skip(
            f"DATABASE_URL not reachable for D-46-14 #2; "
            f"run `docker compose up postgres` first ({exc!r})"
        )

    try:
        yield engine
    finally:
        async with engine.begin() as conn:
            await conn.execute(
                text("TRUNCATE users, password_reset_tokens, audit_log RESTART IDENTITY CASCADE")
            )
        await engine.dispose()


@pytest.mark.asyncio
async def test_soft_delete_reinvite_race(
    real_commit_engine: AsyncEngine,
) -> None:
    """Concurrent DELETE old + POST new with same email → one active survivor.

    Race outcomes (both legitimate per partial-UNIQUE semantics):
      - DELETE first → POST second succeeds (201): two rows in the table,
        one soft-deleted (old), one active (new) — ``active_count == 1``.
      - POST first while old row still active → 409 ``email_already_active``;
        DELETE still soft-deletes the old row → one row in the table, the
        old row, soft-deleted — ``active_count == 0`` (no new row was ever
        inserted; the old row no longer matches ``deleted_at IS NULL``).

    Invariants (asserted regardless of ordering):
      1. The old row has ``deleted_at IS NOT NULL`` (DELETE always wins
         its own side, soft-deleting the row).
      2. ``active_count <= 1`` — the partial-UNIQUE
         ``uq_users_email_active`` makes >1 impossible. We assert the
         stricter per-branch shape: ==1 on POST=201, ==0 on POST=409.
      3. If POST=201, the active row is a NEW id (distinct from
         ``old_user_id``) — DELETE soft-deleted the original AND
         create_user inserted a fresh row, NOT a re-read of the old.

    These are the production contract the partial-UNIQUE
    ``uq_users_email_active`` (Alembic 0022) + the Phase 43 D-43-13
    four-branch ``create_user`` are jointly responsible for. A regression
    that drops the partial predicate (allowing both rows to be active) OR
    converts the soft-delete to a hard-delete would surface here.
    """
    session_factory = async_sessionmaker(real_commit_engine, expire_on_commit=False)

    shared_email = f"race-reinvite+{uuid4().hex[:8]}@local.dev"
    owner_email = f"owner+{uuid4().hex[:8]}@local.dev"

    # ── Seed owner (actor) + old user with shared_email ──
    async with session_factory() as setup:
        owner = User(
            email=owner_email,
            password_hash=await hash_password(_RACE_OWNER_PASSWORD),
            role=Role.OWNER,
            full_name="Race Owner",
            email_verified=True,
            is_active=True,
            status="active",
        )
        setup.add(owner)
        await setup.commit()
        await setup.refresh(owner)

        old_user = User(
            email=shared_email,
            password_hash=await hash_password("OldPass123!OldPass"),
            role=Role.RECEPTION,
            full_name="Original Holder",
            email_verified=True,
            is_active=True,
            status="active",
        )
        setup.add(old_user)
        await setup.commit()
        await setup.refresh(old_user)
        old_user_id = old_user.id

    # ── Build a FastAPI app + override get_db so route handlers use the
    # real-commit engine (their own per-request sessions). Without the
    # override the app would fall back to its lifespan-bound engine which
    # does not share connection state with `session_factory` above, so the
    # seeded owner+old user rows would be invisible to the route. With the
    # override every request opens its own session against `real_commit_engine`
    # — exactly the production shape, which is what makes the COMMIT-time
    # partial-UNIQUE race meaningful. ──
    app = create_app()

    async def _override_get_db() -> AsyncIterator[AsyncSession]:
        async with session_factory() as session:
            yield session

    def _override_get_redis() -> Any:
        return app.state.redis

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_redis] = _override_get_redis

    # We need lifespan fired so app.state.redis is bound.
    from asgi_lifespan import LifespanManager

    try:
        async with LifespanManager(app):
            transport = ASGITransport(app=app)
            async with AsyncClient(
                transport=transport, base_url="http://testserver"
            ) as owner_client:
                # Owner login → carries auth cookie + CSRF cookie.
                login = await owner_client.post(
                    "/api/v1/auth/login",
                    json={"email": owner_email, "password": _RACE_OWNER_PASSWORD},
                )
                assert login.status_code == 200, f"owner login failed: {login.text}"
                csrf_headers = {"X-CSRF-Token": owner_client.cookies.get("clubcore_csrf") or ""}

                # ── Race: DELETE old user || POST new user with same email ──
                async def _delete_old() -> tuple[int, str]:
                    r = await owner_client.delete(
                        f"/api/v1/users/{old_user_id}",
                        headers=csrf_headers,
                    )
                    return r.status_code, (r.text or "")

                async def _create_new() -> tuple[int, str]:
                    r = await owner_client.post(
                        "/api/v1/users",
                        json={
                            "email": shared_email,
                            "full_name": "New Holder",
                            "role": "reception",
                        },
                        headers=csrf_headers,
                    )
                    return r.status_code, (r.text or "")

                (del_status, del_body), (post_status, post_body) = await asyncio.gather(
                    _delete_old(), _create_new()
                )
    finally:
        app.dependency_overrides.clear()

    # Either ordering is legitimate. The partial-UNIQUE + four-branch
    # create_user collapse the race to a 2-element outcome set per side:
    #   DELETE: 204 (success) — DELETE never legitimately 409s here since
    #     the old row exists and is owned by no-one's session.
    #   POST: 201 (Branch A INSERT succeeded — DELETE ran first) OR
    #         409 (Branch C / Branch A IntegrityError translation — POST
    #              raced ahead while old row still had deleted_at IS NULL).
    assert del_status == 204, f"DELETE expected 204, got {del_status}: {del_body}"
    assert post_status in {201, 409}, f"POST expected 201 or 409, got {post_status}: {post_body}"

    # ── DB invariants ──
    async with session_factory() as verify:
        # Invariant 1 — old row exists AND is soft-deleted (DELETE always
        # wins its own side; soft-delete must be SOFT, not a row removal).
        old_row = (
            await verify.execute(
                text("SELECT deleted_at FROM users WHERE id = :uid"),
                {"uid": old_user_id},
            )
        ).first()
        assert old_row is not None, "old row vanished entirely — DELETE must be SOFT"
        assert old_row.deleted_at is not None, (
            "old row must have deleted_at IS NOT NULL after soft-delete"
        )

        # Invariant 2 — at most one ACTIVE row with this email
        # (deleted_at IS NULL). This is the partial-UNIQUE
        # uq_users_email_active contract.
        active_count = (
            await verify.execute(
                text(
                    "SELECT count(*) FROM users "
                    "WHERE lower(email) = lower(:e) AND deleted_at IS NULL"
                ),
                {"e": shared_email},
            )
        ).scalar_one()
        assert active_count <= 1, (
            f"partial-UNIQUE violated: {active_count} active rows with "
            f"email {shared_email!r} survived the race"
        )

        # Invariant 3 — per-branch shape:
        #   POST=201 → exactly 1 active row, and its id is NEW (not the old).
        #   POST=409 → no new row was inserted; the old row is the only one,
        #              and it is soft-deleted ⇒ active_count==0.
        if post_status == 201:
            assert active_count == 1, (
                f"POST returned 201 but active_count={active_count} (expected 1)"
            )
            new_row_count = (
                await verify.execute(
                    text(
                        "SELECT count(*) FROM users "
                        "WHERE lower(email) = lower(:e) AND id <> :old "
                        "AND deleted_at IS NULL"
                    ),
                    {"e": shared_email, "old": old_user_id},
                )
            ).scalar_one()
            assert new_row_count == 1, (
                "POST=201 but no new ACTIVE row with the shared email "
                "exists distinct from the soft-deleted old row"
            )
        else:
            # post_status == 409.
            assert active_count == 0, (
                f"POST returned 409 but active_count={active_count} "
                f"(expected 0 — no new row inserted, old row soft-deleted)"
            )
            total_rows = (
                await verify.execute(
                    text("SELECT count(*) FROM users WHERE lower(email) = lower(:e)"),
                    {"e": shared_email},
                )
            ).scalar_one()
            assert total_rows == 1, (
                f"POST=409 expected exactly 1 row (the soft-deleted old row); got {total_rows}"
            )
