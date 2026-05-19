"""Anti-oracle contract for POST /auth/otp/request (all channels) — AUTH-EM-04 / D-42-24.

GREEN at land-time. Mirrors ``test_password_reset_no_oracle.py`` (RESET-06 lineage,
PATTERNS.md §21) but exercises the Phase 42 unified OTP endpoint that ships in plan
42-09. Unlike the Phase 41 RESET test (which lands xfail-strict ahead of its endpoint),
this test goes green on land because the endpoint + anti-oracle floor already exist.

Contract (D-42-24, 4 cases):
  Cases A, B, C, D — ALL MUST produce:
    - status code 202
    - byte-for-byte identical response body
    - bounded-equal timing within a 100 ms tolerance (RESET-06 precedent)

  Case B — sent without a ``channel`` field — exercises the Telegram-default
  backwards-compat path (D-42-22). Per CR-02 fix (Phase 42 plan 42-13), case B
  is now INCLUDED in the body-parity AND timing-parity assertions: both
  channels return byte-identical ``envelope(None)`` (router.py:411) AND
  converge on the same ``_constant_time_floor`` distribution. This enforces
  the D-42-22 anti-oracle uniformity invariant across BOTH channels of
  /auth/otp/request.

Per-case fixtures (D-42-24):
  - case_a: email_verified=True AND telegram_chat_id=None  (eligible email branch)
  - case_b: email_verified=True AND telegram_chat_id set   (Telegram-default path)
  - case_c: email_verified=False                            (anti-oracle silent drop)
  - case_d: nonexistent email                               (anti-oracle silent drop)

Per-test seeding (D-41-18 SAVEPOINT isolation); ``time.perf_counter()`` deltas for
the bounded-timing assertion.
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

# Import via the auth.models shim (D-41-01 / D-41-02) — mirrors the RESET-06 test.
from app.modules.auth.models import User

pytestmark = pytest.mark.asyncio


# Long deterministic password — clears AUTH-EP-05's 12-char floor.
_FIXTURE_PASSWORD = "otp-email-anti-oracle-fixture-pw"  # noqa: S105 — test literal


@pytest_asyncio.fixture
async def four_otp_fixture_users(db_session: AsyncSession) -> dict[str, str]:
    """Seed the 4 D-42-24 cases per-test. Returns email-string lookup map.

    case_d is NEVER inserted (it is the nonexistent-email branch). The other
    three rows differ on (``email_verified``, ``telegram_chat_id``) so they
    cover every reachable code path inside ``service.request_otp_email`` /
    ``service.request_otp_telegram`` that the D-42-22 anti-oracle floor is
    designed to mask.
    """
    pw_hash = await hash_password(_FIXTURE_PASSWORD)
    suffix = uuid4().hex[:8]

    case_a = User(
        email=f"verified_no_tg+{suffix}@example.com",
        password_hash=pw_hash,
        role=Role.RECEPTION,
        full_name="Verified No TG",
        email_verified=True,
        telegram_chat_id=None,
    )
    case_b = User(
        email=f"verified_with_tg+{suffix}@example.com",
        password_hash=pw_hash,
        role=Role.RECEPTION,
        full_name="Verified With TG",
        email_verified=True,
        # Deterministic per-test BIGINT — uuid4 hex is hex-only and short, so
        # ``int(suffix, 16)`` is a safe collision-free namespace inside the
        # SAVEPOINT-rolled-back transaction.
        telegram_chat_id=10_000_000 + int(suffix, 16) % 1_000_000,
    )
    case_c = User(
        email=f"unverified+{suffix}@example.com",
        password_hash=pw_hash,
        role=Role.RECEPTION,
        full_name="Unverified",
        email_verified=False,
    )
    case_d_email = f"nonexistent+{suffix}@example.com"
    db_session.add_all([case_a, case_b, case_c])
    await db_session.commit()
    return {
        "case_a": case_a.email,
        "case_b": case_b.email,
        "case_c": case_c.email,
        "case_d": case_d_email,
    }


async def test_otp_email_anti_oracle(
    async_client: AsyncClient,
    four_otp_fixture_users: dict[str, str],
) -> None:
    """AUTH-EM-04 (D-42-24) + CR-02 — 4-case anti-oracle gate (cases A+B+C+D).

    All four cases MUST produce:
      - status code 202
      - byte-for-byte identical response body
      - bounded-equal timing within 100 ms (RESET-06 precedent + D-42-22 uniformity)

    Cases A, C, D send ``{channel:'email', email:<x>}``. Case B sends ``{email:<x>}``
    (no channel field) and exercises the Telegram-default backwards-compat path;
    after CR-02 fix (plan 42-13), case B's request_otp_telegram applies the same
    ``_constant_time_floor`` so timing converges.
    """
    probes: list[tuple[str, dict[str, str]]] = [
        ("case_a", {"channel": "email", "email": four_otp_fixture_users["case_a"]}),
        ("case_b", {"email": four_otp_fixture_users["case_b"]}),  # Telegram-default
        ("case_c", {"channel": "email", "email": four_otp_fixture_users["case_c"]}),
        ("case_d", {"channel": "email", "email": four_otp_fixture_users["case_d"]}),
    ]
    responses: list[tuple[str, int, bytes, float]] = []
    for name, body in probes:
        t0 = time.perf_counter()
        resp = await async_client.post("/api/v1/auth/otp/request", json=body)
        t1 = time.perf_counter()
        responses.append((name, resp.status_code, resp.content, t1 - t0))

    # Status-code parity — all four cases must respond 202.
    statuses = {r[1] for r in responses}
    assert statuses == {202}, f"non-uniform statuses (anti-oracle leak): {responses}"

    # Body parity — byte-for-byte identical across all 4 cases (cross-channel).
    bodies = {r[2] for r in responses}
    assert len(bodies) == 1, (
        "response body diverges across 4 cases — anti-oracle leak: "
        f"{[(r[0], r[2]) for r in responses]}"
    )

    # Timing parity — bounded-equal within 100 ms (D-42-22 floor + RESET-06 precedent).
    timings = [r[3] for r in responses]
    assert max(timings) - min(timings) < 0.100, (
        "cross-channel timing oracle on /auth/otp/request: "
        f"max-min={max(timings) - min(timings):.3f}s > 100ms; "
        f"per-case timings={list(zip([r[0] for r in responses], timings, strict=True))}"
    )
