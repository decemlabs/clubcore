"""Password-reset rate limiter (D-44-10/11/12/13 — RESET-01).

Three independent Redis fixed-window counters guard `/password-reset/request`:

  - per-IP:           5 requests / 15 minutes (key: ratelimit:password_reset:ip:<ip>)
  - per-email/minute: 1 request  / 60 seconds (key: ratelimit:password_reset:email_min:<email>)
  - per-email/hour:   5 requests / 60 minutes (key: ratelimit:password_reset:email_hour:<email>)

Order of checks (D-44-13): IP → email-minute → email-hour. ALL three CHECK
helpers run BEFORE any user lookup so an unknown-email rate-limited request
matches the timing/audit profile of a known-email rate-limited request
(anti-oracle parity).

BUMP helpers run UNCONDITIONALLY on every request (not just failures — unlike
the login limiter which only bumps on auth failure) so a flood of requests
against a non-existent email still trips the limit.

The service-layer caller (`password_reset_service.request_password_reset`)
catches `RateLimited` and translates to the same 202 envelope as the success
path (D-44-11 — anti-oracle: a 429 leaks "this email exists AND someone is
hammering it"). The structlog WARN emission (`password_reset.rate_limited`)
lives in `password_reset_service.py`, NOT here — this module keeps a pure
Redis surface with zero observability coupling.

Mirrors `app/modules/auth/rate_limit.py` (login limiter) shape verbatim
except for the 3-key topology.
"""

from typing import Final

from redis.asyncio import Redis

from app.core.exceptions import RateLimited

# D-44-10 — thresholds + windows (RESET-01).
_IP_LIMIT: Final[int] = 5
_IP_WINDOW_SECONDS: Final[int] = 900  # 15 minutes
_EMAIL_MIN_LIMIT: Final[int] = 1
_EMAIL_MIN_WINDOW_SECONDS: Final[int] = 60  # 1 minute
_EMAIL_HOUR_LIMIT: Final[int] = 5
_EMAIL_HOUR_WINDOW_SECONDS: Final[int] = 3600  # 1 hour


def _key_ip(ip: str) -> str:
    return f"ratelimit:password_reset:ip:{ip}"


def _key_email_minute(email_lower: str) -> str:
    return f"ratelimit:password_reset:email_min:{email_lower}"


def _key_email_hour(email_lower: str) -> str:
    return f"ratelimit:password_reset:email_hour:{email_lower}"


async def check_reset_rate_ip(redis: Redis, ip: str) -> None:
    """Raise RateLimited if the per-IP window count >= 5 (D-44-10/13).

    Called BEFORE any user lookup so an attacker cannot distinguish
    'unknown email' from 'known email' via latency once the IP limit kicks in.
    """
    raw = await redis.get(_key_ip(ip))
    if raw is not None and int(raw) >= _IP_LIMIT:
        raise RateLimited("rate_limited")


async def check_reset_rate_email_minute(redis: Redis, email_lower: str) -> None:
    """Raise RateLimited if the per-email/minute window count >= 1 (D-44-10/13).

    Called BEFORE any user lookup (anti-oracle parity — D-44-13).
    """
    raw = await redis.get(_key_email_minute(email_lower))
    if raw is not None and int(raw) >= _EMAIL_MIN_LIMIT:
        raise RateLimited("rate_limited")


async def check_reset_rate_email_hour(redis: Redis, email_lower: str) -> None:
    """Raise RateLimited if the per-email/hour window count >= 5 (D-44-10/13).

    Called BEFORE any user lookup (anti-oracle parity — D-44-13).
    """
    raw = await redis.get(_key_email_hour(email_lower))
    if raw is not None and int(raw) >= _EMAIL_HOUR_LIMIT:
        raise RateLimited("rate_limited")


async def bump_reset_rate_ip(redis: Redis, ip: str) -> None:
    """INCR + EXPIRE per-IP key in a single pipeline (D-44-10).

    Bumped UNCONDITIONALLY on every request (not only failures), so flood
    against unknown emails still trips the limit.
    """
    pipe = redis.pipeline()
    pipe.incr(_key_ip(ip))
    pipe.expire(_key_ip(ip), _IP_WINDOW_SECONDS)
    await pipe.execute()


async def bump_reset_rate_email_minute(redis: Redis, email_lower: str) -> None:
    """INCR + EXPIRE per-email/minute key in a single pipeline (D-44-10).

    Bumped UNCONDITIONALLY on every request.
    """
    pipe = redis.pipeline()
    pipe.incr(_key_email_minute(email_lower))
    pipe.expire(_key_email_minute(email_lower), _EMAIL_MIN_WINDOW_SECONDS)
    await pipe.execute()


async def bump_reset_rate_email_hour(redis: Redis, email_lower: str) -> None:
    """INCR + EXPIRE per-email/hour key in a single pipeline (D-44-10).

    Bumped UNCONDITIONALLY on every request.
    """
    pipe = redis.pipeline()
    pipe.incr(_key_email_hour(email_lower))
    pipe.expire(_key_email_hour(email_lower), _EMAIL_HOUR_WINDOW_SECONDS)
    await pipe.execute()
