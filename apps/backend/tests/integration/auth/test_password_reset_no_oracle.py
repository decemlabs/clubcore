"""Anti-oracle contract for POST /auth/password-reset/request (RESET-01 / RESET-06).

Phase 41 plan 11 landed this test as xfail-strict; Phase 44 plan 05 ungates
it (D-41-17 / D-44-29) atomically with the endpoint shipping in 44-04/05
(same commit — no CI-red window on master). Plan 44-06 extends the test
with the audit-row assertion (D-44-30) in a follow-on commit.

Contract (RESET-06):
  For all 4 cases — existing-active / existing-deactivated / owner-account
  / non-existent — the response must be IDENTICAL:

  - status code 202
  - byte-for-byte identical response body (no email-presence leak in
    headers/body/redirect-target)
  - bounded-equal timing within a 100 ms tolerance (no timing oracle)

  Additionally (audit half of RESET-01, covered by plan 44-06 in a
  follow-on commit per D-44-30): ``password_reset_requested`` audit row is
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
from fastapi import FastAPI
from httpx import AsyncClient
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit_models import AuditLog
from app.core.permissions import Role
from app.core.security import hash_password

# Import via the auth.models shim path (D-41-01 / D-41-02) — resolves both
# pre- and post-Plan-41-10 without depending on wave ordering.
from app.modules.auth.models import User

pytestmark = pytest.mark.asyncio


# Reasonably long deterministic password — clears AUTH-EP-05's 12-char floor.
_FIXTURE_PASSWORD = "reset-oracle-fixture-pw"  # noqa: S105 — test literal


@pytest_asyncio.fixture
async def redis_clean(app: FastAPI) -> Redis:
    """Flush Redis between tests so rate-limit counters don't bleed.

    The 3-key reset rate-limit (per-IP, per-email-minute, per-email-hour)
    triggers on the 5th IP-key bump within 15 minutes — and ASGITransport
    defaults `client.host` to "127.0.0.1" so prior tests in the same process
    share the IP key. Without this flush, the 4-case anti-oracle assertion
    flips into the rate-limit-hit branch (no audit row emitted per D-44-11)
    and breaks the D-44-30 audit-row assertion. Mirrors the established
    pattern at `tests/integration/auth/test_login.py:27-32`.
    """
    client: Redis = app.state.redis
    await client.flushdb()
    return client


@pytest_asyncio.fixture
async def four_fixture_users(
    db_session: AsyncSession,
    redis_clean: Redis,
) -> dict[str, User | None]:
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


async def test_password_reset_request_no_oracle(
    async_client: AsyncClient,
    db_session: AsyncSession,
    four_fixture_users: dict[str, User | None],
) -> None:
    """4-case identical-202 + identical-body + bounded-timing-100ms contract.

    Plan 44-06 extension (D-44-30): also asserts that
    ``password_reset_requested`` is emitted in BOTH the known-email branch
    (3 fixture users — active / deactivated / owner) AND the unknown-email
    branch, per D-44-08 dual-branch emit + D-41-10 system-emit (the unknown
    branch has ``target_user_id=None`` and ``actor_user_id=None``).
    """

    active = four_fixture_users["active"]
    deactivated = four_fixture_users["deactivated"]
    owner = four_fixture_users["owner"]
    assert active is not None
    assert deactivated is not None
    assert owner is not None

    nonexistent_email = f"nonexistent+{uuid4().hex}@example.com"
    emails = [
        active.email,
        deactivated.email,
        owner.email,
        nonexistent_email,
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

    # ------------------------------------------------------------------
    # Plan 44-06 / D-44-30 — dual-branch audit-row assertion.
    #
    # `password_reset_requested` audit row MUST be emitted in BOTH branches
    # of D-44-08: known-email (target_user_id=UUID-string, email_hint=lower)
    # and unknown-email (target_user_id=None, email_hint=lower). D-41-10
    # forces actor_user_id=None for system-emitted rows in both branches.
    # JSONB roundtrip stringifies UUIDs, so the comparison target is
    # `str(user.id)` (Phase 43 plan 11 / test_users_invitation_flow.py
    # established this pattern).
    # ------------------------------------------------------------------
    audit_rows = (
        (
            await db_session.execute(
                select(AuditLog).where(AuditLog.action == "password_reset_requested")
            )
        )
        .scalars()
        .all()
    )
    assert len(audit_rows) == 4, (
        "expected 4 password_reset_requested audit rows (1 per case — D-44-08 "
        f"dual-branch emit); got {len(audit_rows)}"
    )

    # D-41-10 — every system-emitted row in BOTH branches has actor_user_id=None.
    for row in audit_rows:
        assert row.actor_user_id is None, (
            f"actor_user_id must be None for system-emitted password_reset_requested "
            f"(D-41-10); got {row.actor_user_id!r}"
        )
        assert row.actor_email_snapshot is None, (
            f"actor_email_snapshot must be None (mirrors actor_user_id per D-41-10); "
            f"got {row.actor_email_snapshot!r}"
        )
        # audit_correlation_id is generated per-request even in the unknown
        # branch (D-44-08); JSONB stores it as a string.
        assert row.payload["audit_correlation_id"] is not None, (
            "audit_correlation_id must be non-None for every request (D-44-08)"
        )

    by_email = {row.payload["email_hint"]: row for row in audit_rows}
    assert set(by_email.keys()) == {
        active.email.lower(),
        deactivated.email.lower(),
        owner.email.lower(),
        nonexistent_email.lower(),
    }, (
        "email_hint set mismatch — expected one row per case keyed by lowercased "
        f"email; got {sorted(by_email.keys())}"
    )

    # Known-email branch: target_user_id is the resolved user UUID (stringified).
    assert by_email[active.email.lower()].payload["target_user_id"] == str(active.id)
    assert by_email[deactivated.email.lower()].payload["target_user_id"] == str(
        deactivated.id
    )
    assert by_email[owner.email.lower()].payload["target_user_id"] == str(owner.id)

    # Unknown-email branch (D-41-10 / D-44-08): target_user_id IS NULL.
    assert by_email[nonexistent_email.lower()].payload["target_user_id"] is None
