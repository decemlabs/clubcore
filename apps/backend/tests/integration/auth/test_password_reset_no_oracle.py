"""Anti-oracle contract for POST /auth/password-reset/request (RESET-06 / D-41-17).

LANDS RED at Phase 41 — the endpoint does not exist yet (HTTP 404 at the
request layer). GOES GREEN at Phase 44 RESET-01 in the same commit that
removes the xfail marker. ``strict=True`` ensures CI breaks loudly if the
marker is removed without the endpoint actually satisfying the contract.

Contract (RESET-06):
  For all 4 cases — existing-active / existing-deactivated / owner-account
  / non-existent — the response must be IDENTICAL:

  - status code 202
  - byte-for-byte identical response body (no email-presence leak in
    headers/body/redirect-target)
  - bounded-equal timing within a 100 ms tolerance (no timing oracle)

  Additionally (audit half of RESET-01, covered by separate Phase 44 tests
  once the endpoint lands): ``password_reset_requested`` audit row is
  emitted in BOTH branches (known and unknown email) per D-41-10.

D-41-18 — real Postgres via SAVEPOINT per-test isolation (see project
conftest ``db_session`` fixture); the 4 fixture users are seeded per-test
(NOT module-scoped) for deterministic isolation. Bounded-timing assertion
uses ``time.perf_counter()`` deltas.

Import-path choice (D-41-01 / D-41-02): ``User`` is imported from
``app.modules.auth.models`` (the one-milestone shim) — keeps this test
stable both pre- and post-hoist while Plan 41-10 and Plan 41-11 share a
wave.
"""

from __future__ import annotations

import time
from uuid import uuid4

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permissions import Role
from app.core.security import hash_password

# Import via the auth.models shim path (D-41-01 / D-41-02) — resolves both
# pre- and post-Plan-41-10 without depending on wave ordering.
from app.modules.auth.models import User

pytestmark = pytest.mark.asyncio


# Reasonably long deterministic password — clears AUTH-EP-05's 12-char floor.
_FIXTURE_PASSWORD = "reset-oracle-fixture-pw"  # noqa: S105 — test literal


@pytest_asyncio.fixture
async def four_fixture_users(db_session: AsyncSession) -> dict[str, User | None]:
    """Seed the 4 canonical RESET-06 cases per-test (D-41-18).

    Returns a mapping keyed by case name:

    - ``active``      → reception user (is_active semantics — column lands
                        with USERS-02 in Phase 43; for now the case is
                        represented by a present, non-owner row).
    - ``deactivated`` → reception user (deactivation column lands with
                        USERS-02; case represented by a second present
                        row whose email is documented as the deactivated
                        slot — endpoint MUST treat it identically to
                        ``active`` once Phase 44 RESET-01 ships).
    - ``owner``       → owner-role user.
    - ``nonexistent`` → ``None``; the email for this case is generated
                        per-test as ``nonexistent+{uuid}@example.com`` and
                        is NEVER inserted.

    NOTE: ``is_active`` and ``deleted_at`` columns on the ``User`` ORM do
    not exist yet at Phase 41 commit time (migration 0022 ships the
    ``deleted_at`` column at the DB level; the ORM Mapped attribute lands
    with USERS-02 in Phase 43). The case labels above are anchored on
    email values and roles; the contract assertions in this test do not
    read those columns directly — they only assert response equality.
    """

    pw_hash = await hash_password(_FIXTURE_PASSWORD)
    suffix = uuid4().hex[:8]

    active = User(
        email=f"active+{suffix}@example.com",
        password_hash=pw_hash,
        role=Role.RECEPTION,
        full_name="Active Reception",
    )
    deactivated = User(
        email=f"deactivated+{suffix}@example.com",
        password_hash=pw_hash,
        role=Role.RECEPTION,
        full_name="Deactivated Reception",
    )
    owner = User(
        email=f"owner+{suffix}@example.com",
        password_hash=pw_hash,
        role=Role.OWNER,
        full_name="Owner Account",
    )
    db_session.add_all([active, deactivated, owner])
    await db_session.commit()

    return {
        "active": active,
        "deactivated": deactivated,
        "owner": owner,
        "nonexistent": None,
    }


@pytest.mark.xfail(
    strict=True,
    reason=(
        "POST /api/v1/auth/password-reset/request lands in Phase 44 "
        "RESET-01; this test documents the anti-oracle contract as code "
        "per D-41-17. Remove the marker in the same commit that ships "
        "the endpoint. strict=True ensures CI fails loudly if the marker "
        "is removed without the endpoint actually passing."
    ),
)
async def test_password_reset_request_no_oracle(
    async_client: AsyncClient,
    four_fixture_users: dict[str, User | None],
) -> None:
    """4-case identical-202 + identical-body + bounded-timing-100ms contract."""

    active = four_fixture_users["active"]
    deactivated = four_fixture_users["deactivated"]
    owner = four_fixture_users["owner"]
    assert active is not None
    assert deactivated is not None
    assert owner is not None

    emails = [
        active.email,
        deactivated.email,
        owner.email,
        f"nonexistent+{uuid4().hex}@example.com",
    ]

    responses: list[tuple[int, bytes, float]] = []
    for email in emails:
        t0 = time.perf_counter()
        resp = await async_client.post(
            "/api/v1/auth/password-reset/request",
            json={"email": email},
        )
        t1 = time.perf_counter()
        responses.append((resp.status_code, resp.content, t1 - t0))

    # Status-code parity — every case must respond 202.
    statuses = {r[0] for r in responses}
    assert statuses == {202}, f"non-uniform statuses: {statuses}"

    # Body parity — byte-for-byte identical response body across all 4 cases.
    bodies = {r[1] for r in responses}
    assert len(bodies) == 1, (
        "response body diverges across the 4 cases — anti-oracle leak: "
        f"{[r[1] for r in responses]}"
    )

    # Timing parity — bounded-equal within 100 ms per RESET-06.
    timings = [r[2] for r in responses]
    assert max(timings) - min(timings) < 0.100, (
        f"timing oracle: max-min={max(timings) - min(timings):.3f}s "
        f"> 100ms; per-case timings={timings}"
    )
