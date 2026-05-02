"""Per-email login rate limiter (D-18, D-19 — AUTH-EP-03).

Fixed-window counter in Redis: 5 failures per 15 minutes per `email_lower`.
Per-email (not per-IP — D-19) because RU/CIS shared NAT (coffee-shops, mobile
CGNAT, corporate egress) makes per-IP a false-positive minefield.

The check runs BEFORE Argon2 verify so a rate-limited request never hits the
slow path (D-18 timing-equivalence guard: the check is unconditional on email,
not conditional on user existence — no enumeration via response time).
"""

from redis.asyncio import Redis

from app.core.exceptions import RateLimited

_LIMIT = 5
_WINDOW_SECONDS = 900  # 15 minutes (AUTH-EP-03)


def _key(email_lower: str) -> str:
    return f"ratelimit:login:{email_lower}"


async def check_login_rate(redis: Redis, email_lower: str) -> None:
    """Raise RateLimited if the current window count >= 5.

    Called at the top of `authenticate(...)` BEFORE the user lookup, so an
    attacker cannot distinguish 'unknown email' from 'wrong password' via
    latency once the limit kicks in.
    """
    raw = await redis.get(_key(email_lower))
    if raw is not None and int(raw) >= _LIMIT:
        raise RateLimited("rate_limited")


async def bump_login_rate(redis: Redis, email_lower: str) -> None:
    """INCR + EXPIRE 900 in a single pipeline. Called on every failed login.

    Successful login does NOT reset the counter — it expires naturally. This
    keeps the limiter mechanically simple at the cost of a slightly stickier
    block for the operator who fat-fingered once before succeeding (acceptable
    for a 1-2-user system).
    """
    pipe = redis.pipeline()
    pipe.incr(_key(email_lower))
    pipe.expire(_key(email_lower), _WINDOW_SECONDS)
    await pipe.execute()
