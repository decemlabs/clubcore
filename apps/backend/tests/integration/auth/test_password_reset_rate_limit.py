"""Integration tests for /auth/password-reset/request rate-limit topology (RESET-01).

3 independent Redis fixed-window counters (D-44-10/12/13) guard the endpoint:

  - per-IP:           5 requests / 15 minutes
  - per-email/minute: 1 request  / 60 seconds
  - per-email/hour:   5 requests / 60 minutes

Anti-oracle invariant (D-44-11): rate-limit hits MUST NEVER surface as 429.
Every rate-limited response collapses to the SAME 202 + ``envelope(None)``
shape as the success path — a 429 would leak "this email exists AND
someone is hammering it" because attackers only flood real targets. The
service emits a structlog WARN (``password_reset.rate_limited``) for ops
visibility instead.

Test methodology — each test isolates ONE rate-limit key by:

  1. Flushing Redis via the ``redis_clean`` fixture.
  2. Crafting the request matrix so the OTHER two counters stay below
     threshold (different emails for the per-IP test; different IPs +
     manual key-clear between requests for the per-email tests).

The structlog logger-cache reset fixture mirrors the pattern in
``tests/integration/auth/conftest.py`` (auth.service) — needed because
``password_reset_service._log: Final = structlog.get_logger(...)`` caches
the processor list at first ``bind()``, so ``structlog.testing.capture_logs()``
otherwise misses emissions.
"""

from __future__ import annotations

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import AsyncClient
from redis.asyncio import Redis
from structlog.testing import capture_logs

pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture
async def redis_clean(app: FastAPI) -> Redis:
    """Flush Redis so the 3 rate-limit windows start at counter=0 per test."""
    client: Redis = app.state.redis
    await client.flushdb()
    return client


@pytest_asyncio.fixture(autouse=True)
def _refresh_password_reset_logger() -> None:
    """Force ``password_reset_service._log`` to re-resolve processors per test.

    Mirrors ``_reset_auth_service_logger_cache`` in
    ``tests/integration/auth/conftest.py``. ``structlog.configure(
    cache_logger_on_first_use=True)`` makes the lazy proxy cache a reference
    to the processor list active at first ``bind()``. ``capture_logs()``
    swaps the *current* config's processors but the cached logger keeps
    pointing at the old list → emissions vanish. Deleting ``__dict__['bind']``
    forces re-resolution on the next call.
    """
    from app.modules.auth import password_reset_service as service_mod

    if "bind" in service_mod._log.__dict__:
        del service_mod._log.__dict__["bind"]


async def test_rate_limit_per_ip_5_per_15min_returns_202_not_429(
    async_client: AsyncClient,
    redis_clean: Redis,
) -> None:
    """D-44-10 + D-44-11 — 6th request from same IP returns 202 (NOT 429).

    Crafts 5 successful requests with the SAME ``X-Forwarded-For: 127.0.0.1``
    header but DIFFERENT emails so the per-email-minute limit (1/60s) doesn't
    trip first. The per-IP counter (5/15min) reaches threshold; the 6th
    request must collapse to 202 + identical body per D-44-11.
    """
    _ = redis_clean  # fixture-graph dep — counters start at 0

    ip_header = {"X-Forwarded-For": "127.0.0.1"}
    success_responses: list[bytes] = []
    for i in range(5):
        r = await async_client.post(
            "/api/v1/auth/password-reset/request",
            json={"email": f"user-ip-{i}@example.com"},
            headers=ip_header,
        )
        assert r.status_code == 202, (i, r.text)
        success_responses.append(r.content)

    # 6th POST trips the per-IP limit — MUST collapse to 202 + identical body.
    with capture_logs() as logs:
        r6 = await async_client.post(
            "/api/v1/auth/password-reset/request",
            json={"email": "rate-limited-victim@example.com"},
            headers=ip_header,
        )
    assert r6.status_code == 202, r6.text
    # Body parity — every response (success AND rate-limit-hit) is byte-identical.
    assert r6.content == success_responses[0], (
        "rate-limit-hit body diverges from success body — anti-oracle leak: "
        f"hit={r6.content!r} success={success_responses[0]!r}"
    )

    # structlog ops visibility — exactly one password_reset.rate_limited event
    # for the 6th POST with ip='127.0.0.1' per D-44-11.
    rate_limit_events = [e for e in logs if e.get("event") == "password_reset.rate_limited"]
    assert len(rate_limit_events) == 1, (
        f"expected 1 password_reset.rate_limited event; got {len(rate_limit_events)}: {logs}"
    )
    assert rate_limit_events[0].get("ip") == "127.0.0.1"


async def test_rate_limit_per_email_minute_1_per_60s_returns_202(
    async_client: AsyncClient,
    redis_clean: Redis,
) -> None:
    """D-44-10 + D-44-11 — 2nd request for same email within 60s returns 202.

    Sends two requests with the SAME email but DIFFERENT IPs so the per-IP
    counter (5/15min) stays at 1 per IP — the per-email-minute counter (1/60s)
    is what trips. Verifies cross-IP per-email-minute key isolation.
    """
    _ = redis_clean

    email = "victim-email-minute@example.com"

    r1 = await async_client.post(
        "/api/v1/auth/password-reset/request",
        json={"email": email},
        headers={"X-Forwarded-For": "10.0.0.1"},
    )
    assert r1.status_code == 202, r1.text

    # 2nd POST — different IP, same email → per-email-minute counter hits limit.
    with capture_logs() as logs:
        r2 = await async_client.post(
            "/api/v1/auth/password-reset/request",
            json={"email": email},
            headers={"X-Forwarded-For": "10.0.0.2"},
        )
    assert r2.status_code == 202, r2.text
    assert r2.content == r1.content, (
        "rate-limit-hit body diverges from success body — anti-oracle leak"
    )

    rate_limit_events = [e for e in logs if e.get("event") == "password_reset.rate_limited"]
    assert len(rate_limit_events) == 1, (
        f"expected 1 password_reset.rate_limited event; got {len(rate_limit_events)}"
    )


async def test_rate_limit_per_email_hour_5_per_3600s_returns_202(
    async_client: AsyncClient,
    redis_clean: Redis,
) -> None:
    """D-44-10 + D-44-11 — 6th request for same email within 1h returns 202.

    Sends 5 successful requests with the SAME email but ROTATING IPs (so per-IP
    counters stay at 1 each), CLEARING the per-email-minute key between each
    request (otherwise that limit would trip at the 2nd). The per-email-hour
    counter (5/3600s) hits threshold on the 6th request.
    """
    redis = redis_clean
    email = "abuser-email-hour@example.com"
    email_min_key = f"ratelimit:password_reset:email_min:{email}"

    success_bodies: list[bytes] = []
    for i in range(5):
        r = await async_client.post(
            "/api/v1/auth/password-reset/request",
            json={"email": email},
            headers={"X-Forwarded-For": f"10.0.0.{i + 1}"},
        )
        assert r.status_code == 202, (i, r.text)
        success_bodies.append(r.content)
        # Clear per-email-minute key so the next request's per-email-minute
        # check passes; per-email-hour counter keeps climbing.
        await redis.delete(email_min_key)

    # 6th POST — per-email-hour counter at 5 → trips the limit.
    with capture_logs() as logs:
        r6 = await async_client.post(
            "/api/v1/auth/password-reset/request",
            json={"email": email},
            headers={"X-Forwarded-For": "10.0.0.99"},
        )
    assert r6.status_code == 202, r6.text
    assert r6.content == success_bodies[0], (
        "rate-limit-hit body diverges from success body — anti-oracle leak"
    )

    rate_limit_events = [e for e in logs if e.get("event") == "password_reset.rate_limited"]
    assert len(rate_limit_events) == 1, (
        f"expected 1 password_reset.rate_limited event; got {len(rate_limit_events)}: {logs}"
    )
