# Phase 7: Telegram OTP Channel - Pattern Map

**Mapped:** 2026-05-02
**Files analyzed:** 23 (new + modified)
**Analogs found:** 22 / 23 (1 has no analog — `app/integrations/telegram/sender.py`-as-typed-SendResult-wrapper, partial pattern from email integration only)

All analog file paths are absolute under `/Users/andre/Workspace/Development/clubcore/`.

---

## File Classification

| New / Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `apps/backend/app/core/config.py` (M) | config | request-response (env load) | self (extend in place) | exact |
| `apps/backend/.env.example` (M) | config | static | self | exact |
| `apps/backend/app/core/database.py` (M) | core lifespan | async-context-manager | self (`db_lifespan`, lines 107-126) | exact (rename + reuse) |
| `apps/backend/app/core/redis.py` (M) | core lifespan | async-context-manager | self (`redis_lifespan`, lines 20-38) | exact (rename + reuse) |
| `apps/backend/app/main.py` (M) | composition root | lifecycle | self (`combined_lifespan`, lines 34-38) | exact (thin adapter refactor) |
| `apps/backend/alembic/versions/0003_telegram_username.py` (NEW) | migration | DDL | `apps/backend/alembic/versions/0001_auth.py` | role-match |
| `apps/backend/app/modules/auth/models.py` (M) | model | ORM | self (`User`, lines 23-55) | exact (add column) |
| `apps/backend/app/modules/auth/telegram_service.py` (NEW) | service | CRUD + transactional | `apps/backend/app/modules/auth/service.py` | exact |
| `apps/backend/app/modules/auth/exceptions.py` (NEW) | error subclasses | declarative | `apps/backend/app/core/exceptions.py` (lines 53-78) | exact |
| `apps/backend/app/modules/auth/router.py` (M) | controller | request-response | self (lines 56-106 — `/login`, `/refresh`) | exact |
| `apps/backend/app/modules/auth/schemas.py` (M) | DTO | static | self (entire file) | exact |
| `apps/backend/app/modules/auth/service.py` (M, one-line) | service | event emit | self (line 138 `emit("login_success", ...)`) | exact (additive kwarg) |
| `apps/backend/app/integrations/telegram/__init__.py` (M) | package marker | docstring only | self (placeholder) | exact (replace text) |
| `apps/backend/app/integrations/telegram/bot.py` (M) | factory | builder | none in repo (new shape) | role-match (factory pattern from `app/main.py:create_app`) |
| `apps/backend/app/integrations/telegram/handlers.py` (M) | handler | event-driven (ptb update) | none in repo | NO ANALOG (pattern from RESEARCH/D-04/D-05) |
| `apps/backend/app/integrations/telegram/sender.py` (M) | I/O wrapper | outbound RPC | none (`app/integrations/email/client.py` is also placeholder) | NO ANALOG (typed SendResult is novel) |
| `apps/backend/app/workers/__init__.py` (M) | package docstring | static | self (5-line file) | exact (extend docstring) |
| `apps/backend/app/workers/telegram_bot.py` (NEW) | worker entry | process lifecycle | `apps/backend/app/workers/arq_app.py` (settings shape) + `app/main.py:create_app` (lifespan composition) | partial-match |
| `apps/backend/docker-compose.yml` (M) | infra | static | self (`backend` service, lines 5-20) | exact (clone pattern) |
| `apps/backend/scripts/seed_demo_data.py` (M) | script | CRUD upsert | self (lines 31-70) | exact |
| `apps/backend/tests/conftest.py` (M) | fixture | test-infra | self (lines 47-142) | exact (add fixture in place) |
| `apps/backend/tests/integration/auth/test_telegram_start.py` (NEW) | integration test | request-response | `apps/backend/tests/integration/auth/test_login.py` | exact |
| `apps/backend/tests/integration/auth/test_telegram_verify_happy.py` (NEW) | integration test | request-response | `apps/backend/tests/integration/auth/test_login.py` lines 47-83 (cookie assertions) + `test_refresh.py` lines 22-51 (login + structlog capture) | exact |
| `apps/backend/tests/integration/auth/test_telegram_verify_errors.py` (NEW) | integration test (parametrized) | request-response | `apps/backend/tests/integration/auth/test_login.py` lines 85-108 (4xx body shape) | exact |
| `apps/backend/tests/integration/telegram/__init__.py` (NEW) | empty package | n/a | `apps/backend/tests/integration/auth/__init__.py` | exact |
| `apps/backend/tests/integration/telegram/test_handler_start.py` (NEW) | unit-ish (handler direct call) | event-driven | none in repo | NO ANALOG (pattern from RESEARCH + D-15) |

---

## Pattern Assignments

### `apps/backend/app/core/database.py` (rename `db_lifespan` → factor reusable manager)

**Analog:** self, `apps/backend/app/core/database.py` lines 107-126.

**Current shape (lines 107-126):**
```python
@asynccontextmanager
async def db_lifespan(app: FastAPI) -> AsyncIterator[None]:
    """FastAPI lifespan: create engine + sessionmaker on startup, dispose on shutdown."""
    settings = get_settings()
    engine = create_async_engine(
        str(settings.database_url),
        pool_pre_ping=True,
        echo=settings.debug,
    )
    session_factory = async_sessionmaker(
        engine,
        expire_on_commit=False,
        class_=AsyncSession,
    )
    app.state.engine = engine
    app.state.sessionmaker = session_factory
    try:
        yield
    finally:
        await engine.dispose()
```

**D-08 refactor pattern:** introduce `db_lifespan_manager()` that yields `(engine, sessionmaker)` (no `app` arg, no `app.state` writes). Keep `db_lifespan(app)` as a thin wrapper that opens the manager and assigns to `app.state` — back-compat with `app/main.py` and any test reading `app.state.engine` (e.g. `tests/conftest.py:72`).

**Suggested target shape:**
```python
@asynccontextmanager
async def db_lifespan_manager() -> AsyncIterator[tuple[AsyncEngine, async_sessionmaker[AsyncSession]]]:
    settings = get_settings()
    engine = create_async_engine(
        str(settings.database_url),
        pool_pre_ping=True,
        echo=settings.debug,
    )
    session_factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    try:
        yield engine, session_factory
    finally:
        await engine.dispose()


@asynccontextmanager
async def db_lifespan(app: FastAPI) -> AsyncIterator[None]:
    async with db_lifespan_manager() as (engine, session_factory):
        app.state.engine = engine
        app.state.sessionmaker = session_factory
        yield
```

**Constraint (D-08, importlinter `core-not-depend-on-modules`):** new manager MUST NOT import from `app.modules.*`.

---

### `apps/backend/app/core/redis.py` (extract `redis_lifespan_manager`)

**Analog:** self, `apps/backend/app/core/redis.py` lines 20-38.

**Current shape (lines 20-38):**
```python
@asynccontextmanager
async def redis_lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    client: Redis = from_url(  # type: ignore[no-untyped-call]
        str(settings.redis_url),
        decode_responses=True,
        encoding="utf-8",
    )
    app.state.redis = client
    try:
        yield
    finally:
        await client.aclose()
```

**Target:** mirror the database refactor — `redis_lifespan_manager()` yields the `Redis` client; `redis_lifespan(app)` becomes the FastAPI adapter that binds `app.state.redis`.

---

### `apps/backend/app/main.py` (no behavioral change, lifespan now uses managers)

**Analog:** self, lines 34-38 (`combined_lifespan`).

**Current shape:**
```python
@asynccontextmanager
async def combined_lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Chain db_lifespan + redis_lifespan (D-08)."""
    async with db_lifespan(app), redis_lifespan(app):
        yield
```

**No code change needed** — `db_lifespan` / `redis_lifespan` keep their signatures. Only the docstring reference to D-08 is extended to point at the new managers.

---

### `apps/backend/app/workers/telegram_bot.py` (NEW process entry)

**Analogs:**
- `apps/backend/app/workers/arq_app.py` — minimal worker module shape (settings load, redis_url from settings).
- `apps/backend/app/main.py:create_app()` lines 41-78 — composition order pattern (`configure_logging` first, then resources, then handlers).
- `apps/backend/app/main.py:combined_lifespan` lines 34-38 — chained `async with` over multiple lifespan managers.

**Pattern to follow (D-08 + D-09 + D-06):**
```python
"""Telegram bot worker entry — long-polling ptb 22 Application.

Per Phase 7 D-06: workers MAY import a single owning module's service layer
(here `app.modules.auth.telegram_service`). Cross-module imports are still forbidden.

Per Phase 7 D-09: no module-level Application — built inside main()'s scope.
"""
import asyncio
from contextlib import AsyncExitStack

from telegram import Bot

from app.core.config import get_settings
from app.core.database import db_lifespan_manager
from app.core.logging import configure_logging
from app.core.redis import redis_lifespan_manager
from app.integrations.telegram.bot import build_application
from app.integrations.telegram.handlers import HandlerContext, start_handler
from app.integrations.telegram import sender as telegram_sender
from app.modules.auth import telegram_service


async def main() -> None:
    settings = get_settings()
    configure_logging(settings)

    async with AsyncExitStack() as stack:
        engine, sessionmaker = await stack.enter_async_context(db_lifespan_manager())
        redis = await stack.enter_async_context(redis_lifespan_manager())

        bot = Bot(token=settings.telegram_bot_token.get_secret_value())
        ctx = HandlerContext(
            session_factory=sessionmaker,
            telegram_service=telegram_service,
            sender=telegram_sender,
        )
        application = build_application(
            token=settings.telegram_bot_token.get_secret_value(),
            handlers=[("start", start_handler)],
            ctx=ctx,
        )
        await application.initialize()
        try:
            await application.start()
            await application.updater.start_polling()
            # Block until cancelled
            await asyncio.Event().wait()
        finally:
            await application.updater.stop()
            await application.stop()
            await application.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
```

**Constraint:** the `from app.modules.auth import telegram_service` line is the only relaxation of the workers convention — see D-06 + the docstring update in `app/workers/__init__.py`.

---

### `apps/backend/app/workers/__init__.py` (M)

**Current shape (5 lines):**
```python
"""Background workers namespace (ARQ).

Workers consume tasks from Redis and may call app.integrations.* (D-03).
They MUST NOT import app.modules.* directly — events bus pattern lands in Phase B+.
"""
```

**Target (extend with D-06 relaxation):** keep the line and add an explicit Phase 7 exception clause documenting that `app.workers.telegram_bot` may import `app.modules.auth.telegram_service` because the worker IS that module's I/O fanout.

---

### `apps/backend/app/modules/auth/telegram_service.py` (NEW)

**Analog:** `apps/backend/app/modules/auth/service.py`.

**Imports pattern (lines 16-40):**
```python
from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import emit
from app.core.config import get_settings
from app.core.security import (
    generate_deep_link_token,
    generate_otp_code,
    _sha256_hex,  # or re-export — see service.py:64-65 for local _sha256_hex helper
)
from app.modules.auth.models import OtpCode, User
```

**Sha256 hash helper pattern** — `service.py` defines its own at lines 64-65, and `core/security.py` defines `_sha256_hex` at lines 162-164. Telegram service should import the existing `app.core.security._sha256_hex` (or re-define locally if name-mangled `_` prefix blocks import; service.py picks the latter). Do not copy-paste a third copy.

```python
# from app/modules/auth/service.py:64-65
def _sha256_hex(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()
```

**Service function shape pattern (issue_tokens, lines 147-188):**
```python
async def issue_tokens(
    session: AsyncSession,
    redis: Redis,
    user: User,
) -> tuple[str, str, str]:
    """Mint a fresh (access, refresh, csrf) tuple and persist DB+Redis state."""
    settings = get_settings()
    now = datetime.now(tz=UTC)
    family_id = uuid4()
    raw_refresh, refresh_hash = generate_refresh_token()
    access = encode_access_token(user.id, user.role, now=now)
    csrf = generate_csrf_token()
    rt = RefreshToken(
        user_id=user.id,
        family_id=family_id,
        token_hash=refresh_hash,
        expires_at=now + timedelta(seconds=settings.refresh_token_ttl_seconds),
    )
    session.add(rt)
    await session.commit()
    ...
    return access, raw_refresh, csrf
```

**Apply to:**
- `start_deep_link(session)` — generate token, sha256 it, INSERT `OtpCode(deep_link_token_hash=..., expires_at=now+10min, code_hash=None)`, `await session.commit()`, emit `event=telegram_deep_link_issued`.
- `bind_and_issue(session, deep_link_token, telegram_chat_id, telegram_username)` — `select(OtpCode)` by hash, `select(User)` by `lower(telegram_username)`, in-memory `(raw_code, code_hash) = generate_otp_code()`. RETURN `(user, raw_code, otp_row)` to caller (D-11: do not commit until DM succeeds).
- `commit_otp(session, otp_row, user, code_hash, telegram_chat_id)` — set `users.telegram_chat_id` if NULL, mutate `otp_row` fields, `await session.commit()`, emit `otp_issued`. Called by handler ONLY after `SendResult.ok=True`.
- `consume(session, deep_link_token, raw_code)` — SELECT row; raise `BotNotStarted` if `code_hash IS NULL`, `OtpExpired` if `expires_at < now`, `OtpInvalid` (after attempts++ commit) if hashes mismatch and attempts<5, `OtpMaxAttempts` if attempts>=5, `OtpAlreadyConsumed` if `consumed_at IS NOT NULL`, `TokenUnknown` if row is None. On success: stamp `consumed_at = now`, commit, return loaded `User`.
- `get_status(session, deep_link_token)` — SELECT, return `{bound: row is not None and row.code_hash is not None and row.expires_at > now}`. Per D-19, never raise; absent or expired returns `{bound: False}`.

**Audit emit pattern (line 138):**
```python
emit("login_success", user_id=str(user.id), email=email_lower, ip=ip)
```

**Phase 7 emit names to use (CONTEXT lines 174-176, 245):**
- `telegram_deep_link_issued` `{deep_link_token_hash}`
- `otp_issued` `{user_id, chat_id}`
- `otp_consumed` `{user_id}`
- `telegram_unknown_start` `{username, chat_id, deep_link_token_hash}` (handler emits this, NOT service)
- `telegram_dm_blocked` `{chat_id}` (handler)
- `telegram_dm_failed` `{chat_id, error}` (handler)
- `telegram_replay_attempt` `{deep_link_token_hash}` (handler)
- `login_success` with new kwarg `channel='telegram'` (router emits)

**Constraint:** `select(User).where(func.lower(User.telegram_username) == username_lower)` — telegram_username is stored already lowercased per D-02, so `User.telegram_username == username_lower` suffices unless we want defense-in-depth. Pick the simpler form (D-02 says column is `lower(username)` on write).

---

### `apps/backend/app/modules/auth/exceptions.py` (NEW)

**Analog:** `apps/backend/app/core/exceptions.py` lines 53-78.

**Exact pattern to copy:**
```python
"""Auth module-local exceptions — Phase 7 verify failure modes (D-13).

These live in app.modules.auth (NOT app.core) because they are Telegram-OTP specific.
Each rides the shared AppError → JSONResponse handler (Phase 2 D-12, app/core/exceptions.py:81-93)
producing the locked envelope `{code, message, fields?}`.
"""
from app.core.exceptions import AppError


class BotNotStarted(AppError):  # noqa: N818
    """OtpCode found but code_hash IS NULL — user has not pressed /start in the bot."""

    code = "bot_not_started"
    status_code = 409


class OtpExpired(AppError):  # noqa: N818
    code = "otp_expired"
    status_code = 410


class OtpInvalid(AppError):  # noqa: N818
    code = "otp_invalid"
    status_code = 401


class OtpMaxAttempts(AppError):  # noqa: N818
    code = "otp_max_attempts"
    status_code = 429


class OtpAlreadyConsumed(AppError):  # noqa: N818
    code = "otp_consumed"
    status_code = 409


class TokenUnknown(AppError):  # noqa: N818
    code = "token_unknown"
    status_code = 404
```

**`fields` payload (D-13):** raisers must pass `fields={"deepLinkUrl": ...}` for `BotNotStarted` and `fields={"attemptsRemaining": n}` for `OtpInvalid` — this matches the `AppError.__init__` signature at `app/core/exceptions.py:13-16`.

**Naming:** the existing `core/exceptions.py` uses `# noqa: N818` on every error class that does not end in `Error` (lines 29, 53, 60, 74). Carry that pattern forward.

---

### `apps/backend/app/modules/auth/router.py` (M — three new endpoints)

**Analogs (same file, lines 56-106):**

**Existing `/login` (lines 56-76)** — pattern for `/auth/telegram/verify`:
```python
@router.post("/login", response_model=ResponseEnvelope[LoginResponse])
async def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    session: Annotated[AsyncSession, Depends(get_db)],
    redis: Annotated[Redis, Depends(get_redis)],
) -> ResponseEnvelope[LoginResponse]:
    settings = get_settings()
    ip = request.client.host if request.client is not None else None
    user = await authenticate(session, redis, payload.email, payload.password, ip=ip)
    access, refresh, csrf = await issue_tokens(session, redis, user)
    issue_session_cookies(
        response,
        access_token=access,
        refresh_token=refresh,
        csrf_token=csrf,
        secure=settings.cookie_secure,
    )
    return envelope(LoginResponse(user=UserPublic.model_validate(user)))
```

**Apply to `/auth/telegram/verify`:** identical structure — replace `authenticate(...)` call with `telegram_service.consume(session, payload.deepLinkToken, payload.code)`, pass returned `user` to `issue_tokens(...)`, then `issue_session_cookies(...)`. Emit `event=login_success` with `channel='telegram'` after cookies.

**Existing `/refresh` (lines 79-106)** — note the CSRF-exempt pattern by SIGNATURE OMISSION — there is no `Depends(verify_csrf)` parameter. Phase 6 D-09 enforces this exemption for all three new telegram routes. Do NOT add `verify_csrf` to any of them.

**`/auth/telegram/start` shape:**
```python
@router.post("/telegram/start", response_model=ResponseEnvelope[TelegramStartResponse])
async def telegram_start(
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ResponseEnvelope[TelegramStartResponse]:
    """Mint a deep-link token; the FE shows it to the operator (AUTH-TG-01)."""
    settings = get_settings()
    deep_link_token, _hash = await telegram_service.start_deep_link(session)
    deep_link_url = f"https://t.me/{settings.telegram_bot_username}?start={deep_link_token}"
    return envelope(TelegramStartResponse(
        deep_link_url=deep_link_url,
        deep_link_token=deep_link_token,
    ))
```

**`/auth/telegram/status` shape (D-19, GET):**
```python
@router.get("/telegram/status", response_model=ResponseEnvelope[TelegramStatusResponse])
async def telegram_status(
    token: str,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ResponseEnvelope[TelegramStatusResponse]:
    bound = await telegram_service.get_status(session, token)
    return envelope(TelegramStatusResponse(bound=bound))
```

**`/auth/telegram/verify` shape (D-13, D-14):** mirrors `/login` — see "Apply to" above.

**Cross-cutting constraints:**
- Per Phase 6 D-04: routes are pre-listed in TEST-07's introspection exclusion list — no test changes required.
- Per Phase 6 D-09: ALL THREE routes have NO `verify_csrf` dep. The introspection test enforces the exemption list; adding `verify_csrf` would break TEST-07.
- Per Phase 6 D-02/D-03: routes use NO `require_authenticated()` — they predate the session.

---

### `apps/backend/app/modules/auth/schemas.py` (M — extend with three DTOs)

**Analog:** self (entire file, especially `LoginRequest`/`LoginResponse` lines 22-40).

**Pattern:**
```python
# Lines 22-26 — request DTO with strict-extra:
class LoginRequest(RequestContract):
    email: EmailStr
    password: str = Field(min_length=12)

# Lines 37-40 — response payload (auto-wrapped in ResponseEnvelope at the route):
class LoginResponse(ResponseData):
    user: UserPublic
```

**Apply to:**
```python
class TelegramStartResponse(ResponseData):
    deep_link_url: str  # → deepLinkUrl
    deep_link_token: str  # → deepLinkToken


class TelegramStatusResponse(ResponseData):
    bound: bool


class TelegramVerifyRequest(RequestContract):
    deep_link_token: str  # → deepLinkToken
    code: str = Field(min_length=6, max_length=6, pattern=r"^\d{6}$")
```

**Convention:** `RequestContract` (extra='forbid', `core/schemas.py:36-44`) for inputs; `ResponseData` for outputs. snake_case → camelCase happens automatically via `to_camel` alias generator (`core/schemas.py:27-33`).

---

### `apps/backend/app/modules/auth/service.py` (M — one-line)

**Analog:** self, line 138.

**Current line:**
```python
emit("login_success", user_id=str(user.id), email=email_lower, ip=ip)
```

**Target (per Phase 7 D-14):**
```python
emit("login_success", user_id=str(user.id), email=email_lower, ip=ip, channel="email_password")
```

**Side-effect:** `app/core/audit.py:7-14` lists `login_success` as locked; the `channel` kwarg is additive — no docstring rename needed beyond an addendum in `core/audit.py`. Update the docstring comment to mention `channel` is now part of the `login_success` payload (Phase 8 audit_log latch).

---

### `apps/backend/app/modules/auth/models.py` (M — add column)

**Analog:** self, lines 34-51 (`User` columns).

**Existing pattern (`telegram_chat_id`, lines 47-51):**
```python
telegram_chat_id: Mapped[int | None] = mapped_column(
    BigInteger,
    nullable=True,
    unique=True,
)
```

**Apply to (D-02):**
```python
telegram_username: Mapped[str | None] = mapped_column(
    Text,
    nullable=True,
    unique=True,
)
```

**Convention:** lowercased on write at the service layer (D-02). No CITEXT, no native CHECK constraint. The unique index uses the standard naming convention (`uq_users_telegram_username`) via `Base.metadata` at `core/database.py:27-44`.

---

### `apps/backend/alembic/versions/0003_telegram_username.py` (NEW)

**Analog:** `apps/backend/alembic/versions/0001_auth.py`.

**Header pattern (lines 1-19):**
```python
"""telegram_username

Revision ID: 0003_telegram_username
Revises: 0001_auth
Create Date: 2026-05-02 ...

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0003_telegram_username"
down_revision: str | None = "0001_auth"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None
```

**Important:** CONTEXT mentions `0002_*.py` exists (line 183: "analog for migration 0003 per D-18"), but `apps/backend/alembic/versions/` only contains `0001_auth.py`. The `down_revision` MUST point to whatever HEAD currently is — verify with `alembic current` or `ls alembic/versions/` at execution time. As of this analysis: HEAD is `0001_auth`. If a Phase 5/6 migration `0002_*.py` lands before Phase 7 implementation, switch `down_revision = "0002_..."`.

**Op pattern (Alembic auto-generated style, lines 22-52):**
```python
def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("telegram_username", sa.Text(), nullable=True),
    )
    op.create_unique_constraint(
        op.f("uq_users_telegram_username"),
        "users",
        ["telegram_username"],
    )


def downgrade() -> None:
    op.drop_constraint(op.f("uq_users_telegram_username"), "users", type_="unique")
    op.drop_column("users", "telegram_username")
```

**Constraint name pattern:** `op.f(...)` wrapping (line 49 of `0001_auth.py`) — required for the `naming_convention` template at `core/database.py:27-33` to apply consistently.

**No data backfill in migration body** (D-18) — seed script handles it.

---

### `apps/backend/docker-compose.yml` (M — add telegram-bot service)

**Analog:** lines 5-20 (`backend` service).

**Existing pattern:**
```yaml
backend:
  build: .
  command: uvicorn app.main:create_app --factory --host 0.0.0.0 --port 8000 --reload --reload-dir /app/app
  env_file: .env
  environment:
    DATABASE_URL: postgresql+asyncpg://app:app@postgres:5432/sportzal
    REDIS_URL: redis://redis:6379/0
  ports:
    - "8000:8000"
  volumes:
    - ./app:/app/app:ro
  depends_on:
    migrate:
      condition: service_completed_successfully
    redis:
      condition: service_started
```

**Apply (per CONTEXT block lines 38-52, INFRA-06):**
```yaml
telegram-bot:
  build: .
  command: python -m app.workers.telegram_bot
  env_file: .env
  environment:
    DATABASE_URL: postgresql+asyncpg://app:app@postgres:5432/sportzal
    REDIS_URL: redis://redis:6379/0
  restart: unless-stopped
  depends_on:
    migrate:
      condition: service_completed_successfully
    redis:
      condition: service_started
```

**Differences from `backend`:** no `ports:` (bot is outbound-only), no `volumes:` mount (bot does not hot-reload), `restart: unless-stopped` (per CONTEXT line 46), `command: python -m app.workers.telegram_bot` instead of uvicorn.

---

### `apps/backend/.env.example` (M)

**Analog:** self.

**Pattern (existing keys):** comment line, then `KEY=value` (or empty for secrets). Group with blank-line separator. Append at the bottom:
```env
# Phase 7 — Telegram OTP channel (D-10, D-03).
TELEGRAM_BOT_TOKEN=
TELEGRAM_BOT_USERNAME=
OTP_DEEP_LINK_TTL_SECONDS=600
OTP_CODE_TTL_SECONDS=300
OTP_MAX_ATTEMPTS=5

# Optional — consumed by `uv run python -m scripts.seed_demo_data` (D-03).
# Lowercase Telegram username without leading `@`. Idempotently writes users.telegram_username
# for the seeded owner.
TELEGRAM_OWNER_USERNAME=
```

---

### `apps/backend/app/core/config.py` (M)

**Analog:** self, lines 19-34.

**Existing pattern (lines 19-34):**
```python
database_url: PostgresDsn
redis_url: RedisDsn
environment: Literal["dev", "staging", "prod"] = "dev"
debug: bool = False
secret_key: SecretStr

# Phase 4 additions (D-05, D-25): JWT TTLs + cookie Secure flag, env-driven
access_token_ttl_seconds: int = 900
refresh_token_ttl_seconds: int = 2_592_000
jwt_clock_leeway_seconds: int = 30
cookie_secure: bool = False

# Phase 5 addition (D-13, AUTH-06): refresh-rotation reuse-window in seconds.
refresh_reuse_window_seconds: int = 5
```

**Apply (D-10, D-03):**
```python
# Phase 7 additions (D-10, D-03): Telegram OTP channel.
telegram_bot_token: SecretStr
telegram_bot_username: str  # without leading `@`
otp_deep_link_ttl_seconds: int = 600  # 10 min — AUTH-TG-01
otp_code_ttl_seconds: int = 300       # 5 min — AUTH-TG-02
otp_max_attempts: int = 5             # AUTH-TG-02
```

**Convention:** `SecretStr` for the bot token (mirrors `secret_key` line 23). Pydantic-settings reads UPPER_SNAKE env vars automatically — no `env=` kwarg needed.

---

### `apps/backend/scripts/seed_demo_data.py` (M)

**Analog:** self, lines 31-70.

**Existing pattern (env load + idempotent upsert):**
```python
async def _run() -> int:
    email = os.environ.get("SEED_OWNER_EMAIL")
    password = os.environ.get("SEED_OWNER_PASSWORD")
    if not email or not password:
        print(..., file=sys.stderr)
        return 1
    ...
    async with sessionmaker() as session:
        stmt = (
            pg_insert(User)
            .values(
                email=email_lower,
                password_hash=await hash_password(password),
                role=Role.OWNER.value,
                full_name="Owner",
            )
            .on_conflict_do_nothing(index_elements=["email"])
        )
        await session.execute(stmt)
        await session.commit()
```

**Apply (D-03 — extend AFTER the upsert, before `await session.commit()` is fine, or in a second statement):**
```python
telegram_username = os.environ.get("TELEGRAM_OWNER_USERNAME")
if telegram_username:
    tg_lower = telegram_username.lstrip("@").lower()
    # Idempotent: only update if NULL or different from desired value
    user = await session.scalar(select(User).where(User.email == email_lower))
    if user is not None and user.telegram_username != tg_lower:
        user.telegram_username = tg_lower
        await session.commit()
        print(f"Bound telegram_username={tg_lower} to {email_lower}.")
```

**Convention:** the script is a one-shot CLI that prints to stdout (lines 36, 44, 67) and exits with `int` from `_run()` — preserve that exit-code shape.

---

### `apps/backend/tests/conftest.py` (M — add `stub_telegram_sender` fixture)

**Analog:** same file, lines 47-142.

**Pattern (`db_session` lines 56-108, `async_client` lines 111-142):** fixtures live at module scope, decorated with `@pytest_asyncio.fixture`, type-annotated, with docstring referencing the relevant CONTEXT/D-decision.

**Apply (D-07, D-16):**
```python
from dataclasses import dataclass, field

@dataclass
class _StubSenderResult:
    ok: bool = True
    blocked: bool = False
    error: str | None = None


@dataclass
class _StubTelegramSender:
    """Recorder + result-injector for app.integrations.telegram.sender.send_otp_dm.

    Tests: read `.calls` (list of (chat_id, code) tuples) and set `.next_result`
    to control what send_otp_dm returns on the next call. Default: ok=True.
    """
    calls: list[tuple[int, str]] = field(default_factory=list)
    next_result: _StubSenderResult = field(default_factory=_StubSenderResult)


@pytest.fixture
def stub_telegram_sender(monkeypatch: pytest.MonkeyPatch) -> _StubTelegramSender:
    """Monkey-patch app.integrations.telegram.sender.send_otp_dm — D-07/D-16."""
    from app.integrations.telegram import sender as sender_mod

    stub = _StubTelegramSender()

    async def _fake_send_otp_dm(bot, chat_id: int, code: str):  # type: ignore[no-untyped-def]
        stub.calls.append((chat_id, code))
        return stub.next_result

    monkeypatch.setattr(sender_mod, "send_otp_dm", _fake_send_otp_dm)
    return stub
```

**Constraint:** the import must be local-to-the-fixture (`from app.integrations.telegram import sender as sender_mod`) so test collection does not import the telegram module before any other test setup.

---

### `apps/backend/tests/integration/auth/test_telegram_start.py` (NEW)

**Analog:** `apps/backend/tests/integration/auth/test_login.py`.

**Imports + fixtures pattern (test_login.py lines 1-44):**
```python
"""Integration tests for /api/v1/auth/telegram/start (Phase 7 AUTH-TG-01)."""
from __future__ import annotations

import pytest_asyncio
from fastapi import FastAPI
from httpx import AsyncClient
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.models import OtpCode


async def test_telegram_start_returns_deep_link_and_creates_otp_row(
    async_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    response = await async_client.post("/api/v1/auth/telegram/start")
    assert response.status_code == 200, response.text
    body = response.json()
    assert "data" in body
    assert body["data"]["deepLinkUrl"].startswith("https://t.me/")
    assert "?start=" in body["data"]["deepLinkUrl"]
    assert len(body["data"]["deepLinkToken"]) >= 32

    # Verify OtpCode row was created with code_hash IS NULL
    rows = (await db_session.execute(select(OtpCode))).scalars().all()
    assert len(rows) == 1
    assert rows[0].code_hash is None
```

**Cookie/envelope assertion conventions (test_login.py lines 56-83):** check `body["data"][...]` for envelope-wrapped success, `body["code"]` for error envelope.

---

### `apps/backend/tests/integration/auth/test_telegram_verify_happy.py` (NEW)

**Analogs:**
- `tests/integration/auth/test_login.py` lines 47-83 (cookie assertion shape).
- `tests/integration/auth/test_refresh.py` lines 22-51 (login + structlog capture pattern).

**Pattern (combine `seeded_owner` fixture + direct `telegram_service.bind_and_issue` call + stub sender):**
```python
import pytest_asyncio
from structlog.testing import capture_logs
from app.modules.auth import telegram_service
from app.modules.auth.models import User, OtpCode
from app.core.security import hash_password
from app.core.permissions import Role

OWNER_EMAIL = "tg-owner@example.com"
OWNER_PASSWORD = "hunter22hunter22"
TG_USERNAME = "owner_tg"
TG_CHAT_ID = 1234567


@pytest_asyncio.fixture
async def seeded_owner_with_tg(db_session, redis_clean) -> User:
    user = User(
        email=OWNER_EMAIL,
        password_hash=await hash_password(OWNER_PASSWORD),
        role=Role.OWNER,
        full_name="TG Owner",
        telegram_username=TG_USERNAME,
    )
    db_session.add(user)
    await db_session.commit()
    return user


async def test_telegram_verify_happy_path(
    async_client, db_session, seeded_owner_with_tg, stub_telegram_sender,
) -> None:
    # 1. /start → get deep_link_token
    r = await async_client.post("/api/v1/auth/telegram/start")
    deep_link_token = r.json()["data"]["deepLinkToken"]

    # 2. Simulate bot bind+issue directly (D-15: no live ptb)
    # — call telegram_service inside the SAVEPOINT-rolled session
    user, raw_code, otp_row = await telegram_service.bind_and_issue(
        db_session, deep_link_token, TG_CHAT_ID, TG_USERNAME,
    )
    # Simulate sender success path — write code_hash + commit
    await telegram_service.commit_otp(db_session, otp_row, user, raw_code, TG_CHAT_ID)

    # 3. /verify
    with capture_logs() as caplog:
        verify = await async_client.post(
            "/api/v1/auth/telegram/verify",
            json={"deepLinkToken": deep_link_token, "code": raw_code},
        )
    assert verify.status_code == 200, verify.text

    # 4. Assertions: cookies + audit
    set_cookies = verify.headers.get_list("set-cookie")
    joined = "\n".join(set_cookies)
    assert "sz_access=" in joined
    assert "sz_refresh=" in joined
    assert "sportzal_csrf=" in joined

    events = [c.get("event") for c in caplog]
    assert "otp_consumed" in events
    assert "login_success" in events
    login_evt = next(c for c in caplog if c.get("event") == "login_success")
    assert login_evt.get("channel") == "telegram"
```

**Structlog capture pattern (test_refresh.py:24, line: `from structlog.testing import capture_logs`).**

---

### `apps/backend/tests/integration/auth/test_telegram_verify_errors.py` (NEW, parametrized)

**Analog:** `test_login.py` lines 85-129 (error-shape assertions: `body["code"] == "..."`).

**Parametrize pattern:** standard pytest.mark.parametrize over the D-13 table:
```python
import pytest

@pytest.mark.parametrize(
    "scenario, expected_status, expected_code, has_fields",
    [
        ("expired", 410, "otp_expired", False),
        ("invalid_then_4_more", 401, "otp_invalid", True),     # attemptsRemaining
        ("invalid_5th", 429, "otp_max_attempts", False),
        ("already_consumed", 409, "otp_consumed", False),
        ("token_unknown", 404, "token_unknown", False),
        ("bot_not_started", 409, "bot_not_started", True),     # deepLinkUrl
    ],
)
async def test_verify_error_modes(
    scenario, expected_status, expected_code, has_fields,
    async_client, db_session, seeded_owner_with_tg, stub_telegram_sender,
):
    # set up scenario-specific OtpCode state via direct db_session writes
    ...
    response = await async_client.post(
        "/api/v1/auth/telegram/verify",
        json={"deepLinkToken": deep_link_token, "code": "000000"},
    )
    assert response.status_code == expected_status
    body = response.json()
    assert body["code"] == expected_code
    if has_fields:
        assert body["fields"] is not None
```

---

### `apps/backend/tests/integration/telegram/__init__.py` (NEW, empty)

**Analog:** `apps/backend/tests/integration/auth/__init__.py` — empty file (just a package marker). One blank line, no docstring required (matches sibling).

---

### `apps/backend/tests/integration/telegram/test_handler_start.py` (NEW)

**Analog:** none in repo (D-15 introduces the pattern). Closest pattern reference is the `stub_telegram_sender` fixture (defined in `conftest.py` per D-16).

**Pattern (D-15: hand-built ptb update objects, direct handler call):**
```python
"""Telegram /start handler — direct call with hand-built Update + stub sender (D-15)."""
from types import SimpleNamespace
from typing import NamedTuple

import pytest_asyncio
from sqlalchemy import select

from app.integrations.telegram.handlers import HandlerContext, start_handler
from app.modules.auth import telegram_service
from app.modules.auth.models import OtpCode, User
from app.core.security import hash_password
from app.core.permissions import Role


def _build_update(*, deep_link_token: str, username: str | None, chat_id: int):
    """Minimal ptb Update double — only fields the handler reads."""
    user = SimpleNamespace(id=chat_id, username=username, is_bot=False)
    chat = SimpleNamespace(id=chat_id, type="private")
    message = SimpleNamespace(
        text=f"/start {deep_link_token}",
        chat=chat,
        from_user=user,
    )
    return SimpleNamespace(
        effective_user=user,
        effective_chat=chat,
        message=message,
    )


async def test_handler_known_username_binds_and_dms(
    db_session, stub_telegram_sender, seeded_owner_with_tg,
):
    # Pre-seed OtpCode via /start service path
    deep_link_token, _ = await telegram_service.start_deep_link(db_session)

    update = _build_update(deep_link_token=deep_link_token, username="owner_tg", chat_id=999)
    ctx = HandlerContext(
        session_factory=lambda: db_session,  # adapter for SAVEPOINT session
        telegram_service=telegram_service,
        sender=__import__("app.integrations.telegram.sender", fromlist=["sender"]),
    )
    context = SimpleNamespace(bot=SimpleNamespace())  # ptb context double

    await start_handler(update, context, ctx)

    # Assertions
    assert len(stub_telegram_sender.calls) == 1
    chat_id_called, code = stub_telegram_sender.calls[0]
    assert chat_id_called == 999
    assert len(code) == 6 and code.isdigit()

    # OtpCode row was updated with code_hash
    row = (await db_session.execute(select(OtpCode))).scalar_one()
    assert row.code_hash is not None
```

**Three test cases per CONTEXT line 62:** (1) known username → bind+DM; (2) unknown username → no DM, `telegram_unknown_start` structlog event; (3) sender returns `blocked=True` → no `code_hash` written, `telegram_dm_blocked` event.

---

## Shared Patterns

### Authentication / Authorization
**Source:** `apps/backend/app/core/dependencies.py`
**Apply to:** ALL THREE Phase 7 routes — they DO NOT use any auth dep. Per Phase 6 D-09 + D-04, telegram routes are in the exclusion list. Do not add `Depends(require_authenticated())`, do not add `Depends(verify_csrf)`. The introspection test (`tests/integration/test_route_introspection.py`) enforces this.

### Error envelope handler (Phase 2 D-12)
**Source:** `apps/backend/app/core/exceptions.py` lines 81-93
```python
def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error_handler(request: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "code": exc.code,
                "message": exc.message,
                "fields": exc.fields,
            },
        )
```
**Apply to:** all six `app/modules/auth/exceptions.py` subclasses ride this handler automatically (already wired in `app/main.py:create_app` line 69 via `register_exception_handlers(app)`). NO new handler registration needed.

### Audit emit (D-21)
**Source:** `apps/backend/app/core/audit.py` lines 25-35
```python
def emit(event: str, **fields: Any) -> None:
    structlog.get_logger("audit").info(event, **fields)
```
**Apply to:** every emit in `telegram_service.py`, `handlers.py`, and the verify route. Use the LOCKED event names from CONTEXT lines 174-176 / 245. Update `app/core/audit.py:7-14` docstring to add the new Phase 7 names.

### Cookie issuance (Phase 4 D-25)
**Source:** `apps/backend/app/core/security.py` lines 204-254 (`issue_session_cookies`)
**Apply to:** `/auth/telegram/verify` success path — call `issue_session_cookies(response, access_token=access, refresh_token=refresh, csrf_token=csrf, secure=settings.cookie_secure)` exactly as `/login` does (router.py lines 69-75).

### SAVEPOINT-rolled `db_session` test fixture (Phase 5 D-22)
**Source:** `apps/backend/tests/conftest.py` lines 56-108
**Apply to:** all 4 new test files. Service-level `await session.commit()` calls inside `telegram_service` become nested SAVEPOINTs that the outer rollback wipes — same pattern as Phase 5 tests already use.

### Response envelope (Phase 4 D-13)
**Source:** `apps/backend/app/core/schemas.py` lines 51-73 (`ResponseEnvelope[T]`, `envelope()`)
**Apply to:** all three new endpoints — declare `response_model=ResponseEnvelope[XResponse]` and `return envelope(XResponse(...))`.

### snake_case ↔ camelCase wire format (Phase 4 D-09)
**Source:** `apps/backend/app/core/schemas.py` lines 24-44
**Apply to:** `TelegramStartResponse.deep_link_url` serializes as `deepLinkUrl` automatically. No manual `Field(alias=...)` needed — the `to_camel` generator handles it.

### Importlinter contracts (PROJECT.md + Phase 1)
- `core ⊥ modules` — `app.core.database`, `app.core.redis` lifespan managers MUST NOT import any auth/telegram code.
- `integrations ⊥ modules` — `app/integrations/telegram/{bot,handlers,sender}.py` MUST NOT import `app.modules.auth.*`. Handlers receive injected `HandlerContext` (D-05 closure pattern). The `app/workers/telegram_bot.py` is the SOLE relaxation per D-06 — it constructs the `HandlerContext` and binds `telegram_service` into it.

---

## No Analog Found

| File | Role | Data Flow | Reason | Fallback |
|------|------|-----------|--------|----------|
| `apps/backend/app/integrations/telegram/sender.py` | I/O wrapper | outbound RPC | The existing file is a 6-line placeholder; `app/integrations/email/client.py` is also a placeholder. No prior typed `SendResult` wrapper exists. | Use the SendResult dataclass shape from CONTEXT line 26; catch `telegram.error.Forbidden` / `BadRequest("chat not found")` per ptb 22 docs (consult Context7 for ptb error-class API at planning time). |
| `apps/backend/app/integrations/telegram/handlers.py` | event-driven handler | ptb update | Placeholder file; no handler exists. | Use the closure pattern in CONTEXT lines 25-26 + D-05; the `HandlerContext = NamedTuple(session_factory, telegram_service, sender)` is invented in this phase. |
| `apps/backend/app/integrations/telegram/bot.py` | factory | builder | Placeholder file. | Use the `build_application(token, handlers, ctx) -> Application` factory pattern from CONTEXT line 24 + D-09; align with `app/main.py:create_app` factory style (no module-level instances). |
| `apps/backend/tests/integration/telegram/test_handler_start.py` | direct-handler test | event-driven | No prior test calls a non-FastAPI handler with hand-built objects. | Pattern detailed in this PATTERNS.md above (D-15 + SimpleNamespace doubles). |

---

## Metadata

**Analog search scope:**
- `apps/backend/app/` (all subpackages: `core`, `modules/auth`, `integrations/telegram`, `workers`, `api`)
- `apps/backend/alembic/versions/` (1 migration)
- `apps/backend/tests/` (conftest + integration/{auth, rbac, telegram})
- `apps/backend/scripts/`
- `apps/backend/docker-compose.yml`, `apps/backend/.env.example`

**Files scanned:** 27

**Pattern extraction date:** 2026-05-02

**Importlinter contract IDs honored:** `core-not-depend-on-modules`, `integrations-not-depend-on-modules`. The `workers→modules.auth` relaxation (D-06) is documented-only; no contract change needed because no contract currently enforces `workers ⊥ modules`.
