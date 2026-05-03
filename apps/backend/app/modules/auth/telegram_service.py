"""Telegram OTP business logic (Phase 7 D-05, D-11, D-13, D-14, D-19).

Sibling of service.py -- same module, separate concerns. Owns:
  start_deep_link() -- mint OtpCode { code_hash IS NULL } + deep-link token
  bind_and_issue()  -- match user by username; mint raw_code in-memory (NO COMMIT)
  commit_otp()      -- after successful DM, persist code_hash + bind chat_id
  consume()         -- /verify endpoint logic; raises distinct exceptions per D-13
  get_status()      -- poll endpoint logic -- never raises (D-19)

Atomicity (D-11): bind_and_issue does NOT commit; commit_otp commits ONLY after
sender returns ok=True. Guarantees: a code valid in DB iff the user actually
received it via DM.

Bind-existing-only (D-01): this module NEVER inserts a User row.
bind_and_issue only matches existing email/password Users; commit_otp only
mutates User.telegram_chat_id (set if currently NULL).

Architectural constraint: this module lives in app.modules.auth -- bot handlers
in app.integrations.telegram.* MUST NOT import from here directly; they receive
the module via HandlerContext closure constructed in app/workers/telegram_bot.py
(D-05). Workers->modules.auth is the sole relaxation per D-06.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import audit
from app.core.config import get_settings
from app.core.exceptions import AppError
from app.core.security import generate_deep_link_token, generate_otp_code
from app.modules.auth.exceptions import (
    BotNotStarted,
    OtpAlreadyConsumed,
    OtpExpired,
    OtpInvalid,
    OtpMaxAttempts,
    TokenUnknown,
)
from app.modules.auth.models import OtpCode, User

# ---------------------------------------------------------------------------
# Local helpers
# ---------------------------------------------------------------------------


def _sha256_hex(value: str) -> str:
    """Hash helper local to this module.

    `app.core.security._sha256_hex` is name-mangled (underscore-prefixed) and
    `service.py` ships its own copy at lines 64-65; mirror that pattern here
    rather than reach across module boundaries for a private helper.
    """
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


class TelegramUnknownAccount(AppError):  # noqa: N818
    """Raised by bind_and_issue when no User matches lower(username) (D-04).

    Bot handler catches and DMs the fixed Russian "Этот Telegram не привязан..."
    message. The /verify endpoint never sees this exception -- it sees the
    OtpCode untouched (code_hash IS NULL) and raises BotNotStarted instead, so
    the FE single-branch error UX (D-04) is preserved.
    """

    code = "telegram_unknown_account"
    status_code = 403  # handler-only; never rendered to API clients


# ---------------------------------------------------------------------------
# 1. start_deep_link -- POST /auth/telegram/start (D-11 step 1)
# ---------------------------------------------------------------------------


async def start_deep_link(session: AsyncSession) -> tuple[str, str]:
    """Mint an OtpCode placeholder + return (raw_deep_link_token, sha256_hash).

    Inserts an OtpCode row with code_hash=NULL -- the bot has not issued the
    code yet. Emits event=telegram_deep_link_issued.
    """
    settings = get_settings()
    raw_token = generate_deep_link_token()
    token_hash = _sha256_hex(raw_token)
    now = datetime.now(tz=UTC)
    row = OtpCode(
        deep_link_token_hash=token_hash,
        code_hash=None,
        user_id=None,
        telegram_chat_id=None,
        expires_at=now + timedelta(seconds=settings.otp_deep_link_ttl_seconds),
        attempts=0,
        consumed_at=None,
    )
    session.add(row)
    # Pitfall 2: emit BEFORE commit so the audit row commits atomically with
    # the OtpCode placeholder INSERT.
    await audit.emit(
        session,
        "telegram_deep_link_issued",
        actor_user_id=None,
        resource_type="otp",
        deep_link_token_hash=token_hash,
    )
    await session.commit()
    return raw_token, token_hash


# ---------------------------------------------------------------------------
# 2. bind_and_issue -- bot handler step (D-11 steps 2-3, NO COMMIT)
# ---------------------------------------------------------------------------


async def bind_and_issue(
    session: AsyncSession,
    raw_deep_link_token: str,
    telegram_chat_id: int,
    telegram_username: str | None,
) -> tuple[User, str, OtpCode]:
    """Match user by lower(username); generate (raw_code, code_hash) IN-MEMORY.

    DOES NOT commit OTP state -- the handler must call commit_otp() after the
    sender confirms DM delivery (D-11 atomic-after-DM).

    Returns: (user, raw_code, otp_row)

    Raises:
        TokenUnknown -- deep_link_token_hash not in DB.
        OtpAlreadyConsumed -- token already used (D-20 single-use).
        OtpExpired -- deep-link token TTL exceeded.
        TelegramUnknownAccount -- no User matches the username, or the matched
            user has telegram_chat_id != NULL AND != provided chat_id (D-04 --
            handler catches and DMs the Russian "не привязан" message).
    """
    if telegram_username is None:
        raise TelegramUnknownAccount("no_username")
    username_lower = telegram_username.lstrip("@").lower()

    token_hash = _sha256_hex(raw_deep_link_token)
    otp_row = await session.scalar(
        select(OtpCode).where(OtpCode.deep_link_token_hash == token_hash)
    )
    if otp_row is None:
        raise TokenUnknown("deep_link_token_unknown")
    if otp_row.consumed_at is not None:
        raise OtpAlreadyConsumed("deep_link_already_consumed")
    if otp_row.expires_at < datetime.now(tz=UTC):
        raise OtpExpired("deep_link_expired")

    user = await session.scalar(
        select(User).where(User.telegram_username == username_lower)
    )
    if user is None:
        raise TelegramUnknownAccount("no_user_for_username")
    if user.telegram_chat_id is not None and user.telegram_chat_id != telegram_chat_id:
        raise TelegramUnknownAccount("chat_id_collision")

    raw_code, _code_hash = generate_otp_code()
    return user, raw_code, otp_row


# ---------------------------------------------------------------------------
# 3. commit_otp -- after sender.ok=True (D-11 step 4)
# ---------------------------------------------------------------------------


async def commit_otp(
    session: AsyncSession,
    otp_row: OtpCode,
    user: User,
    raw_code: str,
    telegram_chat_id: int,
) -> None:
    """Persist OTP state ONLY after a successful DM (D-11 atomicity).

    - Bind user.telegram_chat_id if currently NULL (D-01: never inserts a
      User row, only mutates this single column).
    - Mutate otp_row { code_hash, user_id, telegram_chat_id,
      expires_at = now + otp_code_ttl_seconds, attempts = 0 }.
    - Commit.
    - Emit event=otp_issued.
    """
    settings = get_settings()
    now = datetime.now(tz=UTC)
    if user.telegram_chat_id is None:
        user.telegram_chat_id = telegram_chat_id
    otp_row.code_hash = _sha256_hex(raw_code)
    otp_row.user_id = user.id
    otp_row.telegram_chat_id = telegram_chat_id
    otp_row.expires_at = now + timedelta(seconds=settings.otp_code_ttl_seconds)
    otp_row.attempts = 0
    # Pitfall 2: emit BEFORE commit so the audit row commits atomically with
    # the OtpCode + User mutations.
    await audit.emit(
        session,
        "otp_issued",
        actor_user_id=user.id,
        resource_type="otp",
        chat_id=telegram_chat_id,
    )
    await session.commit()


# ---------------------------------------------------------------------------
# 4. consume -- POST /auth/telegram/verify (D-13 dispatch table)
# ---------------------------------------------------------------------------


async def consume(
    session: AsyncSession,
    raw_deep_link_token: str,
    raw_code: str,
) -> User:
    """Validate raw_code against OtpCode; on success stamp consumed_at, return User.

    Raises (per D-13 table):
        TokenUnknown          -- 404, deep_link_token_hash not found
        OtpAlreadyConsumed    -- 409, consumed_at IS NOT NULL (replay)
        BotNotStarted         -- 409, code_hash IS NULL (router adds
                                 fields={'deepLinkUrl': ...} for the response)
        OtpExpired            -- 410, expires_at < now
        OtpInvalid            -- 401, code mismatch with attempts < max
                                 (fields={'attemptsRemaining': n})
        OtpMaxAttempts        -- 429, attempts >= max after this miss

    Order matters: consumed_at -> code_hash IS NULL -> expiry -> hash compare,
    so replays of consumed codes report `otp_consumed`, not `bot_not_started`.
    """
    settings = get_settings()
    token_hash = _sha256_hex(raw_deep_link_token)
    otp_row = await session.scalar(
        select(OtpCode).where(OtpCode.deep_link_token_hash == token_hash)
    )
    if otp_row is None:
        raise TokenUnknown("deep_link_token_unknown")
    if otp_row.consumed_at is not None:
        raise OtpAlreadyConsumed("otp_already_consumed")
    if otp_row.code_hash is None:
        # Bot has not DMed the code yet -- D-04 stranger path or DM blocked.
        raise BotNotStarted("bot_not_started")
    if otp_row.expires_at < datetime.now(tz=UTC):
        raise OtpExpired("otp_expired")

    presented_hash = _sha256_hex(raw_code)
    if presented_hash != otp_row.code_hash:
        # Inc + commit BEFORE raise so an attacker dropping the response
        # cannot rewind the counter.
        otp_row.attempts += 1
        await session.commit()
        if otp_row.attempts >= settings.otp_max_attempts:
            raise OtpMaxAttempts("otp_max_attempts")
        remaining = settings.otp_max_attempts - otp_row.attempts
        raise OtpInvalid("otp_invalid", fields={"attemptsRemaining": remaining})

    # Success -- stamp consumed_at, load user.
    otp_row.consumed_at = datetime.now(tz=UTC)
    user_id: UUID | None = otp_row.user_id
    if user_id is None:
        # Defensive: code_hash being non-NULL implies commit_otp ran, which
        # also sets user_id. Treat the inconsistency as token-unknown.
        await session.commit()
        raise TokenUnknown("user_disappeared")
    user = await session.scalar(select(User).where(User.id == user_id))
    if user is None:
        # Race / corruption -- treat as unknown.
        await session.commit()
        raise TokenUnknown("user_disappeared")
    # Pitfall 2: emit BEFORE commit so the audit row commits atomically with
    # the consumed_at stamp.
    await audit.emit(
        session,
        "otp_consumed",
        actor_user_id=user.id,
        resource_type="otp",
    )
    await session.commit()
    return user


# ---------------------------------------------------------------------------
# 5. get_status -- GET /auth/telegram/status (D-19 -- never raises)
# ---------------------------------------------------------------------------


async def get_status(session: AsyncSession, raw_deep_link_token: str) -> bool:
    """Return True iff the bot has DMed the code (code_hash IS NOT NULL) and
    the OtpCode is still alive (not expired, not consumed).

    Never raises (D-19): unknown / expired / consumed all return False so the
    endpoint cannot be used as an oracle for token validity.
    """
    try:
        token_hash = _sha256_hex(raw_deep_link_token)
        otp_row = await session.scalar(
            select(OtpCode).where(OtpCode.deep_link_token_hash == token_hash)
        )
    except Exception:
        return False
    if otp_row is None:
        return False
    if otp_row.code_hash is None:
        return False
    if otp_row.expires_at < datetime.now(tz=UTC):
        return False
    return otp_row.consumed_at is None
