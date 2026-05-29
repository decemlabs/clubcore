"""Per-phone client OTP rate limiters (D-11 / CAUTH-06).

Three limits enforced in this module:
  - per-IP:   5 requests per 15 min (spec: 5/15min)
  - cooldown: 1 per 60s per phone   (spec: >=60s between requests)
  - daily:    5 per 24h per phone   (spec: <=5/24h)

Key rationale (D-11): these are SEPARATE keys from the staff login limiter
in app/modules/auth/rate_limit.py — the two principals must never share quota.
Client OTP keys: ratelimit:client_otp_*  (this module, never overlapping staff)

Enforcement order in request_client_otp (CAUTH-02 anti-oracle):
  1. check_client_ip_rate — before any DB lookup
  2. check_client_otp_cooldown — before any DB lookup
  3. check_client_otp_daily — before any DB lookup
All three checks run BEFORE the Client lookup so latency does not vary
by whether the phone belongs to a known/linked/eligible client.
"""

from redis.asyncio import Redis

from app.core.exceptions import RateLimited

# ---------------------------------------------------------------------------
# Window constants
# ---------------------------------------------------------------------------

_IP_LIMIT = 5
_IP_WINDOW = 900  # 15 min

_COOLDOWN_SECONDS = 60  # per phone — 1 request per 60s

_DAILY_LIMIT = 5
_DAILY_WINDOW = 86400  # 24h


# ---------------------------------------------------------------------------
# Key builders — namespaced SEPARATELY from staff limiters (D-11)
# ---------------------------------------------------------------------------


def _ip_key(ip: str) -> str:
    return f"ratelimit:client_otp_ip:{ip}"


def _cooldown_key(phone: str) -> str:
    return f"ratelimit:client_otp_cooldown:{phone}"


def _daily_key(phone: str) -> str:
    return f"ratelimit:client_otp_daily:{phone}"


# ---------------------------------------------------------------------------
# Check functions — raise RateLimited when threshold is hit
# ---------------------------------------------------------------------------


async def check_client_ip_rate(redis: Redis, ip: str | None) -> None:
    """Raise RateLimited if the IP has hit the 5/15min cap.

    None ip (no client host visible) is silently skipped — avoids rejecting
    all requests behind a reverse proxy that strips X-Forwarded-For.
    """
    if ip is None:
        return
    raw = await redis.get(_ip_key(ip))
    if raw is not None and int(raw) >= _IP_LIMIT:
        raise RateLimited("rate_limited")


async def check_client_otp_cooldown(redis: Redis, phone: str) -> None:
    """Raise RateLimited if a code was sent within the last 60 seconds."""
    if await redis.exists(_cooldown_key(phone)):
        raise RateLimited("rate_limited")


async def check_client_otp_daily(redis: Redis, phone: str) -> None:
    """Raise RateLimited if the phone has hit the 5/24h daily cap."""
    raw = await redis.get(_daily_key(phone))
    if raw is not None and int(raw) >= _DAILY_LIMIT:
        raise RateLimited("rate_limited")


# ---------------------------------------------------------------------------
# Bump functions — INCR + EXPIRE in a pipeline; called AFTER successful send
# ---------------------------------------------------------------------------


async def bump_client_ip_rate(redis: Redis, ip: str | None) -> None:
    """INCR per-IP counter; EXPIRE 900s anchored to FIRST hit (NX).

    WR-01: nx=True ensures the TTL is set only when the key has no TTL — i.e.
    the first request in the window. Subsequent bumps skip the EXPIRE, so the
    window is anchored to the first request rather than rolling to the last.
    """
    if ip is None:
        return
    pipe = redis.pipeline()
    pipe.incr(_ip_key(ip))
    pipe.expire(_ip_key(ip), _IP_WINDOW, nx=True)  # nx=True: set TTL only if absent
    await pipe.execute()


async def record_client_otp_sent(redis: Redis, phone: str) -> None:
    """SET cooldown key with 60s TTL (one-shot: expires naturally)."""
    await redis.set(_cooldown_key(phone), "1", ex=_COOLDOWN_SECONDS)


async def bump_client_otp_daily(redis: Redis, phone: str) -> None:
    """INCR per-phone daily counter; EXPIRE 86400s anchored to FIRST hit (NX).

    WR-01: nx=True ensures the TTL is set only when the key has no TTL — i.e.
    the first OTP request in the 24h window. Subsequent bumps skip the EXPIRE,
    anchoring the window to the first request so it cannot be extended
    indefinitely by repeated requests.
    """
    pipe = redis.pipeline()
    pipe.incr(_daily_key(phone))
    pipe.expire(_daily_key(phone), _DAILY_WINDOW, nx=True)  # nx=True: set TTL only if absent
    await pipe.execute()
