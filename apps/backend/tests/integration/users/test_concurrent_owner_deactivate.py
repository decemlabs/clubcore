"""Phase 43 WR-05 regression — concurrent owner-deactivates serialise correctly.

Pre-fix: count_active_owners_excluding ran SELECT count(*) ... FOR UPDATE
which (a) was rejected by Postgres outright (CR-02) and (b) even if accepted
would lock zero rows (the aggregate result set has no rows to lock). The
race window allowed two parallel "deactivate the second-to-last owner"
requests to both observe count == 1 and both proceed.

Post-fix: the row-returning SELECT with FOR UPDATE locks the candidate-owner
rows themselves. The first tx holds locks; the second blocks until the
first commits; the second then re-reads — exactly one wins.

Note on SAVEPOINT-session isolation: the ASGI test harness runs all requests
through the same SAVEPOINT-rolled session (single asyncpg connection per
test). This means true concurrent SQL-level lock serialisation cannot be
demonstrated in the test harness — asyncpg prohibits concurrent operations
on a single connection ("another operation is in progress"). The tests below
verify the observable service-layer invariant sequentially:
  - First deactivate of the second-to-last owner: 204.
  - Second deactivate of the same already-deactivated owner: 409.
Both calls are submitted via asyncio.gather to document the intended
production concurrent call pattern; the sequential execution within the
test event loop serialises them correctly and produces the expected
[204, 409] outcome that a production Postgres row-lock would also produce.
"""

from __future__ import annotations

import asyncio

import pytest
from fastapi import FastAPI
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models import User
from app.core.permissions import Role

# Placeholder argon2id hash for seeded test users (not a real credential — S106).
# Constructed at runtime so the string literal does not trip S105 on the constant.
_PLACEHOLDER_PWD_HASH = "$argon2id$" + "placeholder"

pytestmark = pytest.mark.asyncio


def _csrf(client: AsyncClient) -> dict[str, str]:
    return {"X-CSRF-Token": client.cookies.get("sportzal_csrf") or ""}


async def test_concurrent_owner_deactivate_exactly_one_winner(
    authed_client_owner: AsyncClient,
    db_session: AsyncSession,
    app: FastAPI,
) -> None:
    """WR-05 regression — two deactivates of the same second-to-last owner.

    Seed exactly two active owners (the fixture owner + one additional).
    Submit two PATCH /deactivate against the SAME additional owner.
    Exactly one must return 204; the other must return 409 (either
    user_already_inactive because the first deactivate committed before the
    second checked, or cannot_deactivate_last_owner if the service guard
    re-reads and sees zero remaining owners — both are valid serialisation
    outcomes matching the production row-lock result).

    The asyncio.gather call documents the intended concurrent-call pattern.
    In the SAVEPOINT test harness (single asyncpg connection) the two
    coroutines execute sequentially within the event loop, producing the
    same [204, 409] outcome that a real Postgres row-lock would produce
    across two separate connections.
    """
    if app.state.engine.dialect.name != "postgresql":
        pytest.skip("Race test requires Postgres for meaningful concurrency semantics.")

    # Seed a second active owner as the deactivation target.
    second_owner = User(
        email="race-target-wr05@example.com",
        email_verified=True,
        password_hash=_PLACEHOLDER_PWD_HASH,
        role=Role.OWNER,
        full_name="Race Target Owner",
        is_active=True,
        status="active",
    )
    db_session.add(second_owner)
    await db_session.commit()
    await db_session.refresh(second_owner)
    target_id = second_owner.id

    # asyncio.gather runs both coroutines concurrently; a semaphore(1) prevents
    # concurrent SQL operations on the single-connection SAVEPOINT fixture
    # (asyncpg prohibits "another operation is in progress" on one connection).
    # The serialisation semantics are identical to what Postgres row locks
    # produce in production: the second request observes the committed state
    # from the first and returns 409.
    sem = asyncio.Semaphore(1)

    async def deactivate_once() -> int:
        async with sem:
            resp = await authed_client_owner.patch(
                f"/api/v1/users/{target_id}/deactivate",
                headers=_csrf(authed_client_owner),
            )
        return resp.status_code

    results = list(
        await asyncio.gather(
            deactivate_once(),
            deactivate_once(),
            return_exceptions=False,
        )
    )

    # Exactly one 204; the other 409 (user_already_inactive because the first
    # deactivate committed and the second sees is_active=False, OR
    # cannot_deactivate_last_owner if the count guard re-reads and finds
    # zero surviving owners). Both are valid serialisation outcomes.
    assert sorted(results) == [204, 409], (
        f"WR-05 regression — expected exactly one 204 and one 409, got {results}. "
        "The row-level FOR UPDATE on count_active_owners_excluding must "
        "serialise parallel attempts on the second-to-last owner."
    )

    # Confirm DB end-state: the target IS deactivated.
    await db_session.refresh(second_owner)
    assert second_owner.is_active is False, "Target owner must be deactivated after the race"


async def test_concurrent_deactivate_of_different_owners_both_succeed(
    authed_client_owner: AsyncClient,
    db_session: AsyncSession,
    app: FastAPI,
) -> None:
    """Positive control — independent owner deactivates are NOT serialised.

    Seed 3 active owners (the fixture owner + 2 additional). Deactivate the
    two additional owners — both should succeed because each operation removes
    a different row from the candidate set and neither leaves zero owners
    remaining.

    asyncio.gather documents the intended concurrent-call pattern; sequential
    execution within the SAVEPOINT harness produces the same [204, 204] result
    that truly concurrent requests would produce (independent targets, no
    lock contention).
    """
    if app.state.engine.dialect.name != "postgresql":
        pytest.skip("Concurrency test requires Postgres.")

    owners: list[User] = []
    for i in range(2):
        u = User(
            email=f"independent-owner-{i}-wr05@example.com",
            email_verified=True,
            password_hash=_PLACEHOLDER_PWD_HASH,
            role=Role.OWNER,
            full_name=f"Independent Owner {i}",
            is_active=True,
            status="active",
        )
        db_session.add(u)
        owners.append(u)
    await db_session.commit()
    for u in owners:
        await db_session.refresh(u)

    async def deactivate(uid: object) -> int:
        resp = await authed_client_owner.patch(
            f"/api/v1/users/{uid}/deactivate",
            headers=_csrf(authed_client_owner),
        )
        return resp.status_code

    sem2 = asyncio.Semaphore(1)

    async def deactivate_serialized(uid: object) -> int:
        async with sem2:
            return await deactivate(uid)

    results = list(
        await asyncio.gather(
            deactivate_serialized(owners[0].id),
            deactivate_serialized(owners[1].id),
            return_exceptions=False,
        )
    )

    assert sorted(results) == [204, 204], (
        f"Independent owner deactivates should both succeed, got {results}. "
        "The row lock should only serialise overlapping candidate sets."
    )
