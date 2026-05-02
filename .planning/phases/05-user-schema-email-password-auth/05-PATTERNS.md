# Phase 5: User Schema + Email/Password Auth - Pattern Map

**Mapped:** 2026-05-02
**Files analyzed:** 19 (new + modified)
**Analogs found:** 17 / 19 (2 truly new patterns — Redis lifespan, audit emit — extrapolate from `db_lifespan` and structlog usage in `middleware.py`)

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `app/main.py` (modify) | composition root / lifespan factory | event-driven (lifespan) | `app/main.py` (current) | exact (extend) |
| `app/api/router.py` (modify) | router aggregator | request-response | `app/api/router.py` (current) | exact (extend) |
| `app/api/v1/router.py` (modify) | v1 aggregator | request-response | `app/api/v1/router.py` (current) | exact (extend) |
| `app/core/redis.py` (NEW) | core infra / lifespan | event-driven | `app/core/database.py:db_lifespan` | exact-pattern |
| `app/core/config.py` (modify) | config | static | `app/core/config.py` (current) | exact (extend) |
| `app/core/security.py` (modify, add `clear_session_cookies`) | core helper | request-response (cookie emission) | `issue_session_cookies` in same file | exact (sibling) |
| `app/core/audit.py` (NEW) | core helper / observability | event-driven (log emit) | `app/core/middleware.py:TimingMiddleware` (structlog usage) | role-match |
| `app/modules/auth/models.py` (fill) | ORM model | CRUD | (no analog — first business model) + `database.py` mixins | mixins-only |
| `app/modules/auth/schemas.py` (fill) | DTO | request-response | `app/core/pagination.py` (uses `RequestContract`/`ResponseData`) | role-match |
| `app/modules/auth/service.py` (fill) | service / SQL+Redis seam | CRUD + state-mutation | (no analog — first business service) + Phase 4 helper composition | composed |
| `app/modules/auth/router.py` (fill) | controller / endpoint | request-response | `app/api/v1/health.py` (shape) + `dependencies.py:require_permission` (auth dep) | role-match |
| `app/modules/auth/rate_limit.py` (NEW) | service helper | event-driven (Redis counter) | (no analog) — pure Redis ops | none |
| `alembic/versions/0001_auth.py` (NEW) | migration | batch | `alembic/script.py.mako` (template) + naming convention from `database.py` | template |
| `scripts/seed_demo_data.py` (rewrite) | script | batch | `scripts/seed_demo_data.py` (current placeholder) | shape-only |
| `.env.example` (modify) | config | static | `.env.example` (current) | exact (extend) |
| `pyproject.toml` (modify) | manifest | static | `pyproject.toml` (current) | exact (extend) |
| `tests/conftest.py` (modify `db_session`) | test fixture | request-response | `tests/conftest.py` (current `db_session` lines 58-77) | exact (replace body) |
| `tests/integration/auth/test_login.py` (NEW) | integration test | request-response | `tests/integration/test_healthz.py` (httpx + ASGITransport pattern) | role-match |
| `tests/integration/auth/test_refresh.py` (NEW) | integration test | request-response + race | same as above + multi-call race pattern | role-match |
| `tests/integration/auth/test_logout.py` (NEW) | integration test | request-response | same as above | role-match |
| `tests/integration/test_alembic_clean.py` (keep green) | integration test | batch | already exists | no change |

---

## Pattern Assignments

### `app/core/redis.py` (NEW — core infra / lifespan)

**Analog:** `app/core/database.py` — the lifespan-managed engine pattern is the exact blueprint Phase 5 follows for Redis (D-08).

**Imports pattern** (from `database.py:10-25`):
```python
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request

from app.core.config import get_settings
```

For Redis, swap the SA imports for:
```python
from redis.asyncio import Redis, from_url
```

**Core lifespan pattern** (from `database.py:107-126`):
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

For `redis_lifespan`, mirror exactly:
```python
@asynccontextmanager
async def redis_lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    client: Redis = from_url(
        str(settings.redis_url),
        decode_responses=True,           # D-08: deal in str not bytes
        encoding="utf-8",
    )
    app.state.redis = client
    try:
        yield
    finally:
        await client.aclose()
```

**Per-request dependency pattern** (from `database.py:129-133`):
```python
async def get_db(request: Request) -> AsyncIterator[AsyncSession]:
    """Per-request AsyncSession from app.state.sessionmaker (D-07)."""
    session_factory = request.app.state.sessionmaker
    async with session_factory() as session:
        yield session
```

For `get_redis`, no `async with`/yield — Redis client is process-singleton:
```python
def get_redis(request: Request) -> Redis:
    """Per-request Redis client from app.state.redis (D-08)."""
    return request.app.state.redis
```

---

### `app/main.py` (modify — extend `create_app()` for redis_lifespan + register_user_loader)

**Analog:** `app/main.py` (current — existing `create_app()` body)

**Current shape** (lines 21-44):
```python
def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings)

    app = FastAPI(
        title="Sportzal API",
        lifespan=db_lifespan,
        docs_url="/docs" if settings.environment == "dev" else None,
        redoc_url=None,
    )
    register_middleware(app)
    register_exception_handlers(app)
    app.include_router(api)
    return app
```

**Phase 5 extension shape** (D-08 chain via `contextlib.asynccontextmanager`, D-15 register loader):
```python
@asynccontextmanager
async def combined_lifespan(app: FastAPI) -> AsyncIterator[None]:
    async with db_lifespan(app), redis_lifespan(app):
        yield


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings)

    # Phase 5 D-25 prod assertion
    if settings.environment == "prod" and not settings.cookie_secure:
        raise RuntimeError("COOKIE_SECURE must be true in prod")

    app = FastAPI(
        title="Sportzal API",
        lifespan=combined_lifespan,
        docs_url="/docs" if settings.environment == "dev" else None,
        redoc_url=None,
    )
    register_middleware(app)
    register_exception_handlers(app)

    # D-15: composition root fills the Phase 4 loader slot.
    # `app.main` is exempt from `core-not-depend-on-modules` (contract scopes app.core).
    from app.modules.auth.service import load_user_by_id
    register_user_loader(load_user_by_id)

    app.include_router(api)
    return app
```

---

### `app/api/router.py` (modify — flip prefix, preserve `/healthz` at root)

**Analog:** current `app/api/router.py:1-15`

**Current** (lines 9-15):
```python
api = APIRouter()
# TODO Phase B+: add /api/v1 prefix; reconcile /healthz path (keep at root for k8s OR move)
api.include_router(v1)
```

**Phase 5 D-16** (separate `/healthz` from versioned router):
```python
from app.api.v1 import health
from app.api.v1.router import v1

api = APIRouter()
# /healthz stays at root (k8s liveness convention, Phase 2 D-14).
api.include_router(health.router)
# All v1 endpoints under /api/v1.
api.include_router(v1, prefix="/api/v1")
```

---

### `app/api/v1/router.py` (modify — include auth_router)

**Analog:** current `app/api/v1/router.py:1-12`

**Current** (already has the commented stub for the include):
```python
v1 = APIRouter()
v1.include_router(health.router)

# TODO Phase B+: include module routers here, e.g.
# from app.modules.auth.router import router as auth_router
# v1.include_router(auth_router, prefix="/auth", tags=["auth"])
```

**Phase 5** (uncomment + remove `health.router` since router.py now mounts it directly):
```python
from app.modules.auth.router import router as auth_router

v1 = APIRouter()
v1.include_router(auth_router, prefix="/auth", tags=["auth"])
```

---

### `app/core/security.py` (modify — add `clear_session_cookies`)

**Analog:** `issue_session_cookies` in same file (`security.py:204-254`)

**Mirror these attributes EXACTLY** for cookie deletion (D-17 — browsers only delete when Path/SameSite match):
```python
def clear_session_cookies(response: Response, *, secure: bool) -> None:
    """Clear sz_access + sz_refresh + sportzal_csrf with attributes matching issue_session_cookies."""
    # sz_access — Path=/
    response.delete_cookie(
        key="sz_access",
        path="/",
        httponly=True,
        secure=secure,
        samesite="lax",
    )
    # sz_refresh — Path=/api/v1/auth (must match issuer)
    response.delete_cookie(
        key="sz_refresh",
        path="/api/v1/auth",
        httponly=True,
        secure=secure,
        samesite="lax",
    )
    # sportzal_csrf — Path=/, NOT httpOnly
    response.delete_cookie(
        key="sportzal_csrf",
        path="/",
        httponly=False,
        secure=secure,
        samesite="lax",
    )
```

---

### `app/core/audit.py` (NEW — `emit(event, **fields)` structlog passthrough)

**Analog:** `app/core/middleware.py:39-44` (TimingMiddleware structlog usage)

**Imports + structlog call** (from `middleware.py:7,40-44`):
```python
import structlog

structlog.get_logger().info(
    "request_complete",
    duration_ms=round(duration_ms, 2),
    status_code=response.status_code,
)
```

**Phase 5 D-21 emit shape** (Phase 8 swaps in DB INSERT without changing call sites):
```python
"""Audit event emission. Phase 5: structlog passthrough; Phase 8: DB INSERT (INFRA-04)."""

from typing import Any

import structlog

_logger = structlog.get_logger("audit")


def emit(event: str, **fields: Any) -> None:
    """Emit an audit event with stable `event=` name. Phase 8 will gain a DB writer here."""
    _logger.info(event, **fields)
```

Locked event names per D-20: `login_success`, `login_failed`, `session_revoked`, `session_revoked_all`, `family_reuse_detected`, `password_changed_revokes_sessions`.

---

### `app/modules/auth/models.py` (fill — User, RefreshToken, OtpCode ORM)

**Analog:** `app/core/database.py:36-105` — the mixins to compose. (No existing model file uses them yet; Phase 5 is the first.)

**Mixin composition** (per Phase 4 D-18):
```python
class User(Base, UUIDPkMixin, TimestampMixin):
    __tablename__ = "users"
    ...
```

**`Mapped` + `mapped_column` usage pattern** (from `database.py:55-58, 70-80`):
```python
id: Mapped[UUIDType] = mapped_column(
    PgUUID(as_uuid=True),
    primary_key=True,
    server_default=text("gen_random_uuid()"),
)

created_at: Mapped[datetime] = mapped_column(
    DateTime(timezone=True),
    nullable=False,
    server_default=func.now(),
)
```

**Role enum mapping (D-07 — TEXT + CHECK constraint, NOT native PG enum):**
```python
from sqlalchemy import Enum as SAEnum, CheckConstraint

class User(Base, UUIDPkMixin, TimestampMixin):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    role: Mapped[Role] = mapped_column(
        SAEnum(Role, native_enum=False, length=16, validate_strings=True),
        nullable=False,
    )
    full_name: Mapped[str] = mapped_column(Text, nullable=False)
    telegram_chat_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, unique=True)

    __table_args__ = (
        CheckConstraint("role IN ('owner', 'reception')", name="users_role_check"),
    )
```

**FK with `ON DELETE CASCADE` and self-FK pattern** (D-04):
```python
class RefreshToken(Base, UUIDPkMixin, TimestampMixin):
    __tablename__ = "refresh_tokens"

    user_id: Mapped[UUIDType] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    family_id: Mapped[UUIDType] = mapped_column(PgUUID(as_uuid=True), nullable=False)
    token_hash: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    replaced_by_id: Mapped[UUIDType | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("refresh_tokens.id", ondelete="SET NULL"),
        nullable=True,
    )
    replaced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("ix_refresh_tokens_user_id_family_id", "user_id", "family_id"),
    )
```

`OtpCode` follows same shape per D-03; `TimestampMixin` is composed but `updated_at` is ignored (D-03 says "no updated_at needed"). Either compose only `UUIDPkMixin` and write `created_at` manually, or accept the inherited `updated_at` (cheaper). Planner decides.

---

### `app/modules/auth/schemas.py` (fill — LoginRequest, LoginResponse, MeResponse)

**Analog:** `app/core/pagination.py:14-43` — the `RequestContract`/`ResponseData` subclassing pattern.

**Imports + subclass** (from `pagination.py:15-17`):
```python
from pydantic import Field
from app.core.schemas import RequestContract, ResponseData
```

**Subclass shape** (from `pagination.py:20-29, 32-43`):
```python
class PageQuery(RequestContract):
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)


class PaginatedData[T](ResponseData):
    items: list[T]
    total: int
    page: int
    page_size: int
```

**Phase 5 schemas** (camelCase wire is automatic via `ContractModel.model_config.alias_generator=to_camel`):
```python
class LoginRequest(RequestContract):
    email: EmailStr
    password: str = Field(min_length=12)  # NIST 800-63B 2024


class UserPublic(ResponseData):
    id: UUID
    role: Role
    full_name: str  # → fullName on wire


class LoginResponse(ResponseData):
    user: UserPublic


class MeResponse(ResponseData):
    id: UUID
    role: Role
    full_name: str       # → fullName
    email: EmailStr
    has_telegram: bool   # → hasTelegram (derived: telegram_chat_id IS NOT NULL)
```

Endpoint return shape per Phase 4 D-14: `response_model=ResponseEnvelope[LoginResponse]`, body returns `envelope(LoginResponse(user=UserPublic.model_validate(user)))`.

---

### `app/modules/auth/service.py` (fill — load_user_by_id, authenticate, issue_tokens, rotate_refresh, revoke_session, revoke_all_sessions)

**Analog (composition):** Phase 4 helpers + `app/core/database.AsyncSession` patterns.

**`load_user_by_id` signature** (matches `dependencies.py:42` `UserLoader` Protocol):
```python
async def load_user_by_id(session: AsyncSession, user_id: UUID) -> User | None:
    """Loader registered via register_user_loader() in create_app() (D-15)."""
    return await session.get(User, user_id)
```

**Argon2 timing-equivalent authenticate** (D-28 sentinel hash, security.py:127-145 patterns):
```python
# Module-level sentinel (a real Argon2 hash of a never-used password) keeps timing equivalent
# even when email is unknown — see Phase 4 D-28 / Phase 5 AUTH-EP-02.
_SENTINEL_HASH = "$argon2id$v=19$m=65536,t=3,p=4$..."  # generated once at module import via hash_password


async def authenticate(session: AsyncSession, redis: Redis, email: str, password: str, *, ip: str | None = None) -> User:
    email_lower = email.lower()
    # Rate limit BEFORE user lookup (D-18) — per-email key, NOT per-IP (D-19).
    await check_login_rate(redis, email_lower)

    user = await session.scalar(select(User).where(User.email == email_lower))
    target_hash = user.password_hash if user else _SENTINEL_HASH
    try:
        await verify_password(password, target_hash)
    except InvalidPassword:
        await _bump_rate(redis, email_lower)
        emit("login_failed", email=email_lower, reason="invalid_credentials", ip=ip)
        raise

    if user is None:
        # User-not-found path: still bumped rate, still raises (post-verify)
        await _bump_rate(redis, email_lower)
        emit("login_failed", email=email_lower, reason="invalid_credentials", ip=ip)
        raise InvalidPassword("invalid_credentials")

    emit("login_success", user_id=str(user.id), email=email_lower, ip=ip)
    return user
```

**Refresh rotation** (D-13 — DB chain + `SELECT ... FOR UPDATE`):
```python
async def rotate_refresh(session: AsyncSession, redis: Redis, presented_token: str) -> tuple[str, str, str]:
    """Returns (new_access_token, new_refresh_token, new_csrf_token). Raises InvalidAccessToken on reuse."""
    presented_hash = _sha256_hex(presented_token)
    settings = get_settings()

    async with session.begin():
        row = (await session.execute(
            select(RefreshToken).where(RefreshToken.token_hash == presented_hash).with_for_update()
        )).scalar_one_or_none()

        if row is None:
            raise InvalidAccessToken("refresh_not_found")

        now = datetime.now(tz=UTC)
        # Active branch
        if row.revoked_at is None and row.replaced_by_id is None and row.expires_at > now:
            # Mint + insert + update
            new_raw, new_hash = generate_refresh_token()
            new_row = RefreshToken(
                user_id=row.user_id,
                family_id=row.family_id,
                token_hash=new_hash,
                expires_at=now + timedelta(seconds=settings.refresh_token_ttl_seconds),
            )
            session.add(new_row)
            await session.flush()
            row.replaced_by_id = new_row.id
            row.replaced_at = now
            # cache for race window
            await redis.set(
                f"auth:rotate:{presented_hash}",
                json.dumps({"refresh_token": new_raw, ...}),
                ex=settings.refresh_reuse_window_seconds,
                nx=True,
            )
            ...
        # Already-replaced within reuse window
        elif row.replaced_by_id is not None and row.replaced_at and row.replaced_at > now - timedelta(seconds=settings.refresh_reuse_window_seconds):
            cached = await redis.get(f"auth:rotate:{presented_hash}")
            if cached:
                return _unpack(cached)
            # else fall through
            ...
        # Reuse outside window OR family already revoked → family revocation
        await session.execute(
            update(RefreshToken)
            .where(RefreshToken.user_id == row.user_id, RefreshToken.family_id == row.family_id, RefreshToken.revoked_at.is_(None))
            .values(revoked_at=now)
        )
        await redis.delete(f"auth:session:{row.user_id}:{row.family_id}")
        emit("family_reuse_detected", user_id=str(row.user_id), family_id=str(row.family_id),
             presented_token_hash_prefix=presented_hash[:8])
        raise InvalidAccessToken("family_reuse_detected")
```

**Logout-all** (D-10 — Redis enumeration + DB sweep):
```python
async def revoke_all_sessions(session: AsyncSession, redis: Redis, user_id: UUID) -> int:
    family_ids = await redis.smembers(f"auth:user_sessions:{user_id}")
    pipe = redis.pipeline()
    for fid in family_ids:
        pipe.delete(f"auth:session:{user_id}:{fid}")
    pipe.delete(f"auth:user_sessions:{user_id}")
    await pipe.execute()

    await session.execute(
        update(RefreshToken)
        .where(RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=datetime.now(tz=UTC))
    )
    emit("session_revoked_all", user_id=str(user_id), family_count=len(family_ids))
    return len(family_ids)
```

---

### `app/modules/auth/router.py` (fill — /login, /refresh, /logout, /logout-all, /me)

**Analog (controller shape):** `app/api/v1/health.py:1-12` for the route declaration; `app/core/dependencies.py:62-92` for the `Depends(get_current_user)` pattern Phase 5 uses on `/logout`, `/logout-all`, `/me`.

**Imports pattern** (extend `health.py:1-5`):
```python
from typing import Annotated
from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession
from redis.asyncio import Redis

from app.core.database import get_db
from app.core.dependencies import CurrentUser, get_current_user
from app.core.config import get_settings
from app.core.redis import get_redis
from app.core.schemas import ResponseEnvelope, envelope
from app.core.security import (
    encode_access_token,
    generate_csrf_token,
    issue_session_cookies,
    clear_session_cookies,
)
from app.modules.auth.schemas import LoginRequest, LoginResponse, MeResponse, UserPublic
from app.modules.auth.service import (
    authenticate,
    issue_tokens,
    rotate_refresh,
    revoke_session,
    revoke_all_sessions,
)
```

**Endpoint pattern** (compose `health.py:8-11` shape with envelope + cookie helper):
```python
router = APIRouter()


@router.post("/login", response_model=ResponseEnvelope[LoginResponse])
async def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    session: Annotated[AsyncSession, Depends(get_db)],
    redis: Annotated[Redis, Depends(get_redis)],
) -> ResponseEnvelope[LoginResponse]:
    settings = get_settings()
    user = await authenticate(
        session, redis, payload.email, payload.password,
        ip=request.client.host if request.client else None,
    )
    access, refresh, csrf = await issue_tokens(session, redis, user)
    issue_session_cookies(
        response,
        access_token=access,
        refresh_token=refresh,
        csrf_token=csrf,
        secure=settings.cookie_secure,
    )
    return envelope(LoginResponse(user=UserPublic.model_validate(user)))


@router.get("/me", response_model=ResponseEnvelope[MeResponse])
async def me(
    user: Annotated[CurrentUser, Depends(get_current_user)],
) -> ResponseEnvelope[MeResponse]:
    return envelope(MeResponse(
        id=user.id,
        role=user.role,
        full_name=user.full_name,
        email=user.email,
        has_telegram=user.telegram_chat_id is not None,
    ))


@router.post("/logout", response_model=ResponseEnvelope[None])
async def logout(
    request: Request,
    response: Response,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
    redis: Annotated[Redis, Depends(get_redis)],
) -> ResponseEnvelope[None]:
    settings = get_settings()
    refresh_cookie = request.cookies.get("sz_refresh")
    if refresh_cookie:
        await revoke_session(session, redis, refresh_cookie)
    clear_session_cookies(response, secure=settings.cookie_secure)
    return envelope(None)
```

`/refresh` does NOT use `Depends(get_current_user)` — it reads `sz_refresh` directly and routes through `rotate_refresh`. CSRF dep is deferred (Phase 6 D-26 exempts /login and /refresh anyway).

---

### `app/modules/auth/rate_limit.py` (NEW — `check_login_rate(email)`)

**Analog:** none; Redis-only per D-18.

**Pattern (D-18 — fixed-window, per-email):**
```python
"""Per-email login rate limit (D-18 — AUTH-EP-03)."""

from redis.asyncio import Redis
from app.core.exceptions import RateLimited

_LIMIT = 5
_WINDOW_SECONDS = 900  # 15 min


async def check_login_rate(redis: Redis, email_lower: str) -> None:
    """Raises RateLimited (429) if the current window count >= 5."""
    key = f"ratelimit:login:{email_lower}"
    count = await redis.get(key)
    if count is not None and int(count) >= _LIMIT:
        raise RateLimited("rate_limited")


async def bump_login_rate(redis: Redis, email_lower: str) -> None:
    """INCR + EXPIRE 900 on every failed login (wrong password OR user-not-found)."""
    key = f"ratelimit:login:{email_lower}"
    pipe = redis.pipeline()
    pipe.incr(key)
    pipe.expire(key, _WINDOW_SECONDS)
    await pipe.execute()
```

---

### `alembic/versions/0001_auth.py` (NEW — first business migration)

**Analog:** `alembic/script.py.mako` (template) + naming convention attached to `Base.metadata` from `database.py:27-33,44`

**Template skeleton** (from `script.py.mako`):
```python
"""auth_initial

Revision ID: 0001_auth
Revises:
Create Date: ...
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, BIGINT

revision: str = '0001_auth'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("email", sa.Text(), nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.Column("full_name", sa.Text(), nullable=False),
        sa.Column("telegram_chat_id", BIGINT(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_users"),
        sa.UniqueConstraint("email", name="uq_users_email"),
        sa.UniqueConstraint("telegram_chat_id", name="uq_users_telegram_chat_id"),
        sa.CheckConstraint("role IN ('owner', 'reception')", name="ck_users_role_check"),
    )
    # refresh_tokens, otp_codes follow with same constraint-naming pattern.
    ...


def downgrade() -> None:
    op.drop_table("otp_codes")
    op.drop_table("refresh_tokens")
    op.drop_table("users")
```

**Constraint names MUST follow** `database.py:27-33` convention or `alembic check` fails (see TEST-08):
- `pk_<table>`
- `uq_<table>_<column>`
- `ix_<column0_label>`
- `ck_<table>_<constraint_name>`
- `fk_<table>_<column>_<referred_table>`

Practical generation: write models first, then `uv run alembic revision --autogenerate -m "auth_initial"` and edit the generated file (do not handwrite — names will drift).

---

### `scripts/seed_demo_data.py` (rewrite — owner upsert per D-25)

**Analog:** current placeholder `scripts/seed_demo_data.py:1-11`

**Current shape:**
```python
"""Phase A placeholder. Real seeding lands in Phase B+ when business modules exist."""
from __future__ import annotations


def main() -> int:
    print("Phase A: no data to seed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

**Phase 5 D-25 shape — read env, hash, ON CONFLICT DO NOTHING:**
```python
"""Seed the bootstrap owner. Idempotent (UPSERT on email)."""
from __future__ import annotations

import asyncio
import os

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.core.permissions import Role
from app.core.security import hash_password
from app.modules.auth.models import User


async def _run() -> int:
    email = os.environ.get("SEED_OWNER_EMAIL")
    password = os.environ.get("SEED_OWNER_PASSWORD")
    if not email or not password:
        print("SEED_OWNER_EMAIL and SEED_OWNER_PASSWORD must be set")
        return 1

    settings = get_settings()
    engine = create_async_engine(str(settings.database_url))
    sessionmaker = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with sessionmaker() as session:
            stmt = insert(User).values(
                email=email.lower(),
                password_hash=await hash_password(password),
                role=Role.OWNER.value,
                full_name="Owner",
            ).on_conflict_do_nothing(index_elements=["email"])
            await session.execute(stmt)
            await session.commit()
            print(f"Seeded owner {email.lower()} (idempotent).")
    finally:
        await engine.dispose()
    return 0


def main() -> int:
    return asyncio.run(_run())


if __name__ == "__main__":
    raise SystemExit(main())
```

Run as `uv run python -m scripts.seed_demo_data`.

---

### `app/core/config.py` (modify — add `refresh_reuse_window_seconds`)

**Analog:** current `config.py:25-29` (Phase 4 added 4 fields; pattern is identical)

**Existing pattern:**
```python
# Phase 4 additions (D-05, D-25): JWT TTLs + cookie Secure flag, env-driven
access_token_ttl_seconds: int = 900           # 15 min — access JWT lifetime
refresh_token_ttl_seconds: int = 2_592_000    # 30 days — refresh token lifetime
jwt_clock_leeway_seconds: int = 30
cookie_secure: bool = False
```

**Phase 5 addition (D-13 tunable race window):**
```python
# Phase 5 addition (D-13, AUTH-06): refresh-rotation reuse-window in seconds
refresh_reuse_window_seconds: int = 5
```

`.env.example` extend with `REFRESH_REUSE_WINDOW_SECONDS=5`, `SEED_OWNER_EMAIL=`, `SEED_OWNER_PASSWORD=`.

---

### `tests/conftest.py` (modify — `db_session` SAVEPOINT-based per-test rollback)

**Analog:** current `conftest.py:58-77` (the existing `db_session` fixture body to replace)

**Current body** (lines 58-77):
```python
@pytest_asyncio.fixture
async def db_session(app: FastAPI) -> AsyncIterator[AsyncSession]:
    sessionmaker = app.state.sessionmaker
    async with sessionmaker() as session:
        try:
            await session.execute(text("select 1"))
        except Exception as exc:
            pytest.skip(f"DATABASE_URL not reachable; ... ({exc!r})")
        try:
            yield session
        finally:
            await session.rollback()
```

**Phase 5 D-22 — SAVEPOINT-based per-test rollback** (SQLAlchemy 2.0 cookbook "Joining a session into an external transaction"):
```python
@pytest_asyncio.fixture
async def db_session(app: FastAPI) -> AsyncIterator[AsyncSession]:
    """SAVEPOINT-based per-test rollback (TEST-01, D-22).

    Outer transaction wraps the test; service-level commits become nested savepoints.
    On teardown, ROLLBACK of the outer tx wipes all writes, including those that
    `session.commit()` claimed to persist.
    """
    engine = app.state.engine
    async with engine.connect() as connection:
        try:
            await connection.execute(text("select 1"))
        except Exception as exc:  # noqa: BLE001
            pytest.skip(f"DATABASE_URL not reachable; run `docker compose up postgres` first ({exc!r})")

        trans = await connection.begin()
        AsyncSessionLocal = async_sessionmaker(
            bind=connection,
            expire_on_commit=False,
            class_=AsyncSession,
            join_transaction_mode="create_savepoint",
        )
        async with AsyncSessionLocal() as session:
            try:
                yield session
            finally:
                await trans.rollback()
```

---

### `tests/integration/auth/test_login.py` (NEW — TEST-02)

**Analog:** `tests/integration/test_healthz.py:1-32` for the httpx ASGITransport pattern.

**Imports + fixture pattern** (from `test_healthz.py:11-21`):
```python
from __future__ import annotations
from httpx import AsyncClient

async def test_healthz_returns_200_and_status_ok(async_client: AsyncClient) -> None:
    response = await async_client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
```

**Phase 5 login test pattern**:
```python
async def test_login_happy_returns_envelope_and_three_cookies(
    async_client: AsyncClient,
    db_session: AsyncSession,    # SAVEPOINT-based — rollback is automatic
) -> None:
    # arrange — insert User row in db_session (fixture supplies)
    user = User(email="op@example.com", password_hash=await hash_password("hunter22hunter22"), ...)
    db_session.add(user)
    await db_session.flush()

    # act
    response = await async_client.post("/api/v1/auth/login", json={
        "email": "op@example.com",
        "password": "hunter22hunter22",
    })

    # assert envelope
    assert response.status_code == 200
    body = response.json()
    assert "data" in body
    assert body["data"]["user"]["fullName"] == ...

    # assert cookies — see test_security.py:180-214 for the attribute-assertion idiom
    set_cookies = response.headers.get_list("set-cookie")
    assert any(h.startswith("sz_access=") and "Path=/" in h and "HttpOnly" in h for h in set_cookies)
    assert any(h.startswith("sz_refresh=") and "Path=/api/v1/auth" in h for h in set_cookies)
    assert any(h.startswith("sportzal_csrf=") and "HttpOnly" not in h for h in set_cookies)


async def test_login_429_after_5_failures(...): ...
async def test_login_401_invalid_credentials(...): ...
```

**Cookie attribute assertion idiom** (from `tests/unit/test_security.py:180-214`):
```python
sz_access = next(h for h in headers if h.startswith("sz_access="))
assert "Path=/" in sz_access and "Path=/api" not in sz_access
assert "HttpOnly" in sz_access
assert "samesite=lax" in sz_access.lower()
assert "Max-Age=900" in sz_access
```

---

### `tests/integration/auth/test_refresh.py` / `test_logout.py`

**Analog:** same as `test_login.py`. Use the same `async_client` + `db_session` fixtures.

For `test_refresh.py` (TEST-04 covers happy rotation, reuse-within-window same-pair return, family-reuse revocation):
- Use `caplog` + structlog test capture to assert `event=family_reuse_detected` (D-20).
- For reuse-within-window: invoke `POST /api/v1/auth/refresh` twice with the same `sz_refresh` cookie inside `settings.refresh_reuse_window_seconds` and assert the second response returns the same new pair (cached at `auth:rotate:{old_token_hash}` per D-13).

---

### `pyproject.toml` (modify — add `redis>=5,<6`)

Already present in current file (`pyproject.toml:18` — `"redis>=5.0"`); Phase 5 narrows to `redis>=5,<6` per D-08. `uv lock` regenerated.

---

## Shared Patterns

### Authentication / `Depends(get_current_user)`
**Source:** `app/core/dependencies.py:62-92` (Phase 4 ships the dependency; Phase 5 uses it)
**Apply to:** `/auth/me`, `/auth/logout`, `/auth/logout-all`. NOT `/auth/login`, NOT `/auth/refresh`.

```python
from typing import Annotated
from fastapi import Depends
from app.core.dependencies import CurrentUser, get_current_user

async def me(user: Annotated[CurrentUser, Depends(get_current_user)]) -> ...:
    ...
```

### Error Handling
**Source:** `app/core/exceptions.py:7-65` (existing AppError hierarchy)
**Apply to:** All Phase 5 service code.

Raise existing classes — handler shape `{code, message, fields?}` is wired in `register_exception_handlers`:
- `InvalidPassword("invalid_credentials")` — wrong password OR user-not-found (D-28 timing equivalence)
- `InvalidAccessToken("...")` — refresh-not-found, family-reuse, expired refresh
- `RateLimited("rate_limited")` — login throttle exhausted
- `ForbiddenError(...)` — Phase 6 will use; Phase 5 routes don't need it yet

NEVER raise raw `HTTPException`. ALWAYS subclass `AppError` (extending in `exceptions.py` if needed).

### Response Envelope (every endpoint)
**Source:** `app/core/schemas.py:51-73` (Phase 4 contract)
**Apply to:** Every Phase 5 endpoint.

Pattern (from `schemas.py:51-54, 70-73`):
```python
@router.post("/login", response_model=ResponseEnvelope[LoginResponse])
async def login(...) -> ResponseEnvelope[LoginResponse]:
    return envelope(LoginResponse(user=...))   # or ResponseEnvelope(data=...)
```

`response_model=` is mandatory (D-14 — keeps OpenAPI honest, no envelope-wrapping middleware).

### Audit emission
**Source:** `app/core/middleware.py:39-44` (structlog idiom) + Phase 5 D-21
**Apply to:** every state-mutating service flow.

```python
from app.core.audit import emit
emit("login_success", user_id=str(user.id), email=email_lower, ip=ip)
```

Locked event names (D-20): `login_success`, `login_failed`, `session_revoked`, `session_revoked_all`, `family_reuse_detected`, `password_changed_revokes_sessions`. Do NOT invent new names — they are Phase 8 contracts.

### Validation (request body)
**Source:** `app/core/schemas.py:36-44` (`RequestContract` with `extra="forbid"`)
**Apply to:** Every POST body schema.

Subclass `RequestContract` (NOT `ContractModel` directly), include `Field(...)` constraints inline:
```python
from pydantic import EmailStr, Field
from app.core.schemas import RequestContract

class LoginRequest(RequestContract):
    email: EmailStr
    password: str = Field(min_length=12)
```

### Architectural boundary (`core ⊥ modules`)
**Source:** `apps/backend/.importlinter:5-11`
**Apply to:** All Phase 5 NEW core files (`app/core/redis.py`, `app/core/audit.py`).

These files MUST NOT `from app.modules.* import ...`. The boundary crossing is exclusively in `app.main.create_app()` where `register_user_loader(load_user_by_id)` runs (D-15). Confirm with `uv run lint-imports` before merge.

### Test fixtures
**Source:** `tests/conftest.py:42-77` + `tests/integration/test_healthz.py`
**Apply to:** Every Phase 5 integration test.

Use `async_client: AsyncClient` (httpx ASGITransport) + `db_session: AsyncSession` (SAVEPOINT-based after D-22 upgrade). NEVER hit the real network (CLAUDE.md constraint). Drop a `pytest.skip` if compose Postgres is unreachable (idiom in `conftest.py:67-72`).

### Alembic migration constraint naming
**Source:** `app/core/database.py:27-33`
**Apply to:** `alembic/versions/0001_auth.py`.

Every constraint name in the migration file MUST follow the standard SA template, otherwise `tests/integration/test_alembic_clean.py::test_alembic_check_clean` (TEST-08) fails on the next phase. Generate via `alembic revision --autogenerate` rather than handwriting.

---

## No Analog Found

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| `app/modules/auth/rate_limit.py` | service helper | event-driven (Redis counter) | First Redis-backed feature in the codebase; no prior pattern. Pure Redis ops — `INCR` + `EXPIRE`. |

**Mitigations:** Plan reads RESEARCH.md / external `redis-py` async docs (CONTEXT.md canonical_refs). Pattern is mechanical: `redis.pipeline().incr(key).expire(key, 900).execute()`.

---

## Metadata

**Analog search scope:** `apps/backend/app/**`, `apps/backend/tests/**`, `apps/backend/scripts/**`, `apps/backend/alembic/**`
**Files scanned:** 60 (entire backend tree minus `__pycache__` / `.venv` / lockfiles)
**Pattern extraction date:** 2026-05-02
