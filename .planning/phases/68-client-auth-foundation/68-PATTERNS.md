# Phase 68: Client Auth Foundation - Pattern Map

**Mapped:** 2026-05-29
**Files analyzed:** 14 new/modified files
**Analogs found:** 14 / 14

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `app/modules/auth/models.py` (modify) | model | CRUD | `app/modules/auth/models.py` (existing) | exact — additive column + CHECK |
| `app/modules/client_auth/models.py` | model | CRUD | `app/modules/auth/models.py` `RefreshToken` | exact role+data-flow |
| `app/core/security.py` (modify) | utility | request-response | `app/core/security.py` (existing) | exact — parallel functions added |
| `app/core/dependencies.py` (modify) | middleware/DI | request-response | `app/core/dependencies.py` (existing) | exact — parallel Protocol + loader slot |
| `app/modules/client_auth/service.py` | service | CRUD + event-driven | `app/modules/auth/service.py` | exact role+data-flow |
| `app/modules/client_auth/rate_limit.py` | utility | request-response | `app/modules/auth/rate_limit.py` | exact role+data-flow |
| `app/modules/client_auth/schemas.py` | model | request-response | `app/modules/auth/schemas.py` | role-match |
| `app/modules/client_auth/router.py` | controller | request-response | `app/modules/auth/router.py` | exact role+data-flow |
| `app/api/v1/router.py` (modify) | config | request-response | `app/api/v1/router.py` (existing) | exact — add one include_router |
| `app/main.py` (modify) | config | request-response | `app/main.py` (existing) | exact — add register_client_loader call |
| `alembic/versions/NNNN_client_auth_otp.py` | migration | CRUD | `alembic/versions/0027_otp_email_channel.py` | role-match (additive column + constraint) |
| `alembic/versions/NNNN_client_refresh_token.py` | migration | CRUD | `alembic/versions/0001_auth.py` (RefreshToken table) | role-match (new table) |
| `tests/integration/client_auth/test_otp_isolation.py` | test | request-response | `tests/integration/auth/test_otp_email_anti_oracle.py` | exact — same harness |
| `tests/integration/client_auth/test_idor.py` | test | request-response | `tests/integration/auth/test_login.py` | role-match |

---

## Pattern Assignments

### `app/modules/auth/models.py` — MODIFY: add `client_id` FK + CHECK to `OtpCode`

**Analog:** `app/modules/auth/models.py` lines 97–160 (existing `OtpCode`) and `app/modules/clients/models.py` lines 99–120 (CHECK + partial-unique pattern)

**Existing `OtpCode.__table_args__` pattern to extend** (models.py lines 145–160):
```python
__table_args__ = (
    Index(
        "uq_otp_codes_user_channel_active",
        "user_id",
        "channel",
        unique=True,
        postgresql_where=text("consumed_at IS NULL"),
    ),
)
```

**New column to add** — mirror `user_id` shape (models.py lines 107–111) but pointing at `clients`:
```python
client_id: Mapped[UUIDType | None] = mapped_column(
    PgUUID(as_uuid=True),
    ForeignKey("clients.id", ondelete="CASCADE"),
    nullable=True,
)
```

**New CHECK constraint** — add to `__table_args__` alongside the existing Index:
```python
CheckConstraint(
    "(user_id IS NULL) <> (client_id IS NULL)",
    name="ck_otp_codes_principal_xor",
),
```

**Import addition needed** (top of file, already present: `CheckConstraint` from sqlalchemy is NOT currently imported in models.py — add it):
```python
from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, Index, Integer, Text, text
```

**Key constraint:** The partial-unique index `uq_otp_codes_user_channel_active` covers `(user_id, channel)` — it remains valid. Client OTPs use `client_id`, not `user_id`, so no client row can collide with a staff OTP row in that index (the XOR CHECK makes `user_id IS NULL` when `client_id IS NOT NULL`). A separate partial-unique index on `(client_id, channel) WHERE consumed_at IS NULL` mirrors the staff index for client principal uniqueness.

---

### `app/modules/client_auth/models.py` — NEW: `ClientRefreshToken` table

**Analog:** `app/modules/auth/models.py` `RefreshToken` class (lines 56–94) — copy structure exactly, replace FK target.

**Imports pattern** (copy from auth/models.py lines 17–26):
```python
from datetime import datetime
from uuid import UUID as UUIDType

from sqlalchemy import DateTime, ForeignKey, Index, Text
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, TimestampMixin, UUIDPkMixin
```

**Core model pattern** (mirror RefreshToken, lines 56–94, but FK → clients):
```python
class ClientRefreshToken(Base, UUIDPkMixin, TimestampMixin):
    """Client refresh token row (D-09).

    Fully parallel to auth.RefreshToken — FK target is clients, not users.
    Redis namespace: auth:client:session:{client_id}:{family_id}.
    """
    __tablename__ = "client_refresh_tokens"

    client_id: Mapped[UUIDType] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("clients.id", ondelete="CASCADE"),
        nullable=False,
    )
    family_id: Mapped[UUIDType] = mapped_column(PgUUID(as_uuid=True), nullable=False)
    token_hash: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    replaced_by_id: Mapped[UUIDType | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("client_refresh_tokens.id", ondelete="SET NULL"),
        nullable=True,
    )
    replaced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("ix_client_refresh_tokens_client_id_family_id", "client_id", "family_id"),
    )
```

---

### `app/core/security.py` — MODIFY: add `ClientAccessTokenClaims`, `encode_client_token`, `decode_client_token`, `issue_client_session_cookies`, `clear_client_session_cookies`

**Analog:** `app/core/security.py` lines 31–110 (staff JWT) and lines 204–292 (cookie helpers)

**`ClientAccessTokenClaims` shape** — mirror `AccessTokenClaims` (lines 31–43) but drop `role`, add `aud`:
```python
@dataclass(frozen=True, slots=True)
class ClientAccessTokenClaims:
    """Decoded client access-token claims (D-07).

    No `role` field — clients are not staff. `aud="client"` is the
    isolation discriminator. `require_client()` asserts aud; staff
    `decode_access_token` never validates aud (D-07 byte-parity).
    """
    sub: str   # str(client_uuid)
    aud: str   # always "client"
    typ: str   # always "access"
    iat: int
    exp: int
```

**`encode_client_token` pattern** — mirror `encode_access_token` (lines 45–69), add `aud`, remove `role`:
```python
def encode_client_token(client_id: UUID, *, now: datetime | None = None) -> str:
    settings = get_settings()
    issued = now or datetime.now(tz=UTC)
    expires = issued + timedelta(seconds=settings.access_token_ttl_seconds)
    payload = {
        "sub": str(client_id),
        "aud": "client",
        "typ": "access",
        "iat": int(issued.timestamp()),
        "exp": int(expires.timestamp()),
    }
    return jwt.encode(payload, settings.secret_key.get_secret_value(), algorithm="HS256")
```

**`decode_client_token` pattern** — mirror `decode_access_token` (lines 72–110), assert `aud=="client"`, no role coercion:
```python
def decode_client_token(token: str) -> ClientAccessTokenClaims:
    settings = get_settings()
    try:
        payload = jwt.decode(
            token,
            settings.secret_key.get_secret_value(),
            algorithms=["HS256"],
            leeway=settings.jwt_clock_leeway_seconds,
            options={"require": ["sub", "aud", "typ", "iat", "exp"]},
        )
    except jwt.ExpiredSignatureError as exc:
        raise InvalidAccessToken("token_expired") from exc
    except jwt.InvalidTokenError as exc:
        raise InvalidAccessToken("invalid_token") from exc

    if payload.get("typ") != "access":
        raise InvalidAccessToken("wrong_token_type")
    if payload.get("aud") != "client":
        raise InvalidAccessToken("wrong_audience")

    return ClientAccessTokenClaims(
        sub=payload["sub"],
        aud=payload["aud"],
        typ=payload["typ"],
        iat=payload["iat"],
        exp=payload["exp"],
    )
```

**`issue_client_session_cookies` pattern** — mirror `issue_session_cookies` (lines 204–254). Key difference: `cc_client_*` names and `Path=/api/v1/client` for refresh cookie (D-10):
```python
def issue_client_session_cookies(
    response: Response,
    *,
    access_token: str,
    refresh_token: str,
    csrf_token: str,
    secure: bool,
) -> None:
    settings = get_settings()
    response.set_cookie(
        key="cc_client_access",
        value=access_token,
        max_age=settings.access_token_ttl_seconds,
        path="/",
        httponly=True,
        secure=secure,
        samesite="lax",
    )
    response.set_cookie(
        key="cc_client_refresh",
        value=refresh_token,
        max_age=settings.refresh_token_ttl_seconds,
        path="/api/v1/client",   # D-10: scoped to client namespace only
        httponly=True,
        secure=secure,
        samesite="lax",
    )
    response.set_cookie(
        key="clubcore_client_csrf",
        value=csrf_token,
        max_age=settings.refresh_token_ttl_seconds,
        path="/",
        httponly=False,          # readable by frontend for double-submit
        secure=secure,
        samesite="lax",
    )
```

**`clear_client_session_cookies` pattern** — mirror `clear_session_cookies` (lines 257–292). Attributes MUST match issuer exactly or browser silently ignores the deletion:
```python
def clear_client_session_cookies(response: Response, *, secure: bool) -> None:
    response.delete_cookie(key="cc_client_access", path="/", httponly=True, secure=secure, samesite="lax")
    response.delete_cookie(key="cc_client_refresh", path="/api/v1/client", httponly=True, secure=secure, samesite="lax")
    response.delete_cookie(key="clubcore_client_csrf", path="/", httponly=False, secure=secure, samesite="lax")
```

---

### `app/core/dependencies.py` — MODIFY: add `ClientPrincipal`, `register_client_loader`, `get_current_client`, `require_client`

**Analog:** `app/core/dependencies.py` lines 33–68 (`CurrentUser` Protocol + `register_user_loader`) and lines 767–865 (`get_current_user` + `require_permission`).

**`ClientPrincipal` Protocol** — mirror `CurrentUser` (lines 33–48), omit `role` and `email` (D-05: `/me` returns id/phone/email/names/birthday/gender; the Protocol exposes what `require_client()` consumers need):
```python
class ClientPrincipal(Protocol):
    """Structural type for the authenticated gym client (D-08).

    `app.modules.clients.models.Client` satisfies this Protocol.
    No `role` — clients have no RBAC role (D-07 / CISO-01).
    """
    id: UUID
    phone: str
    email: str | None
```

**`ClientLoader` type alias + slot** — mirror `UserLoader` (lines 51–58):
```python
ClientLoader = Callable[[AsyncSession, UUID], Awaitable[ClientPrincipal | None]]
_client_loader: ClientLoader | None = None
```

**`register_client_loader`** — mirror `register_user_loader` (lines 61–68):
```python
def register_client_loader(loader: ClientLoader) -> None:
    """Composition-root setter — called once by app.main.create_app in Phase 68."""
    global _client_loader
    _client_loader = loader
```

**`get_current_client`** — mirror `get_current_user` (lines 767–809), read `cc_client_access` cookie, call `decode_client_token`:
```python
async def get_current_client(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ClientPrincipal:
    token = request.cookies.get("cc_client_access")
    if token is None:
        raise InvalidAccessToken("missing_access_cookie")
    claims = decode_client_token(token)   # validates aud=="client"
    if _client_loader is None:
        raise InvalidAccessToken("client_loader_not_registered")
    try:
        uid = UUID(claims.sub)
    except ValueError as e:
        raise InvalidSession("invalid_session") from e
    client = await _client_loader(session, uid)
    if client is None:
        raise InvalidAccessToken("user_not_found")
    return client
```

**`require_client`** — mirror `require_authenticated()` (lines 868–end): a factory returning a `_checker` closure that calls `get_current_client`. No RBAC gate needed (clients have no role). Return type is `ClientPrincipal`:
```python
def require_client() -> Callable[..., Awaitable[ClientPrincipal]]:
    async def _checker(
        client: Annotated[ClientPrincipal, Depends(get_current_client)],
    ) -> ClientPrincipal:
        return client
    return _checker
```

---

### `app/modules/client_auth/service.py` — NEW: client OTP + session service

**Analog:** `app/modules/auth/service.py` — `_write_session_keys` (L293–323), `rotate_refresh` 3-branch (L367–569), `request_otp_email` (L956–1103), `_constant_time_floor` (L942–953)

**Module-level imports pattern** (mirror auth/service.py lines 16–49):
```python
from __future__ import annotations

import asyncio
import json
import time
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import structlog
from redis.asyncio import Redis
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.exceptions import InvalidAccessToken, InvalidSession
from app.core.security import (
    encode_client_token,
    generate_csrf_token,
    generate_otp_code,
    generate_refresh_token,
)
from app.modules.client_auth.models import ClientRefreshToken
from app.modules.client_auth.rate_limit import (
    check_client_ip_rate,
    check_client_otp_cooldown,
    check_client_otp_daily,
    bump_client_ip_rate,
    bump_client_otp_daily,
    record_client_otp_sent,
)
from app.modules.auth.models import OtpCode
from app.modules.clients.models import Client

_log = structlog.get_logger(__name__)
```

**`_constant_time_floor` pattern** (copy from service.py lines 942–953 — identical logic, same floor constant):
```python
_CLIENT_OTP_FLOOR_MS: Final[float] = 200.0

async def _constant_time_floor(t_start: float) -> None:
    elapsed_ms = (time.perf_counter() - t_start) * 1000
    remaining_ms = _CLIENT_OTP_FLOOR_MS - elapsed_ms
    if remaining_ms > 0:
        await asyncio.sleep(remaining_ms / 1000)
```

**`request_client_otp` pattern** — mirror `request_otp_email` (L956–1103). Key differences: lookup by phone (not email), `OtpCode.client_id` (not `user_id`), `channel="telegram"`, rate-limit check fires BEFORE subject lookup:
```python
async def request_client_otp(
    session: AsyncSession,
    redis: Redis,
    phone: str,
    *,
    ip: str | None = None,
) -> None:
    t_start = time.perf_counter()
    try:
        # Rate-limit check BEFORE subject lookup (D-11 precedent: no oracle via latency).
        await check_client_ip_rate(redis, ip)
        await check_client_otp_cooldown(redis, phone)
        await check_client_otp_daily(redis, phone)

        client = await session.scalar(
            select(Client).where(
                Client.phone == phone,
                Client.deleted_at.is_(None),
            )
        )
        # D-02: silent no-op for unknown/unlinked phones — byte-identical to success.
        if client is None or client.telegram_user_id is None:
            return

        # Consume prior active OTP for this client (single-active per principal).
        await session.execute(
            update(OtpCode)
            .where(OtpCode.client_id == client.id, OtpCode.consumed_at.is_(None))
            .values(consumed_at=datetime.now(tz=UTC))
        )
        raw_code, code_hash = generate_otp_code()
        otp_row = OtpCode(
            client_id=client.id,
            user_id=None,
            channel="telegram",
            deep_link_token_hash=f"client-otp:{uuid4().hex}",  # placeholder, must be unique
            code_hash=code_hash,
            telegram_chat_id=client.telegram_user_id,
            expires_at=datetime.now(tz=UTC) + timedelta(seconds=300),
            attempts=0,
            consumed_at=None,
        )
        session.add(otp_row)
        await session.commit()

        # Send DM — real telegram sender call here (mirrors commit_otp pattern).
        await record_client_otp_sent(redis, phone)
        await bump_client_otp_daily(redis, phone)
        # TODO: call send_otp_dm(bot, client.telegram_user_id, raw_code)
    finally:
        await _constant_time_floor(t_start)
```

**`_write_client_session_keys` pattern** — mirror `_write_session_keys` (L293–323), Redis namespace `auth:client:*` (D-09):
```python
async def _write_client_session_keys(
    redis: Redis,
    *,
    client_id: UUID,
    family_id: UUID,
    refresh_hash: str,
    ttl: int,
    now: datetime,
) -> None:
    session_value = json.dumps({
        "family_id": str(family_id),
        "last_seen_at": now.isoformat(),
        "refresh_token_hash": refresh_hash,
    })
    pipe = redis.pipeline()
    pipe.set(f"auth:client:session:{client_id}:{family_id}", session_value, ex=ttl)
    pipe.sadd(f"auth:client:user_sessions:{client_id}", str(family_id))
    pipe.expire(f"auth:client:user_sessions:{client_id}", ttl)
    await pipe.execute()
```

**`rotate_client_refresh` pattern** — mirror `rotate_refresh` (L367–569), 3-branch identical structure. Replace:
- `RefreshToken` → `ClientRefreshToken`
- `User` lookup for active check → `Client` lookup (`Client.deleted_at.is_(None)`)
- `encode_access_token(user.id, user.role)` → `encode_client_token(client.id)`
- `auth:session:` namespace → `auth:client:session:`
- `auth:user_sessions:` namespace → `auth:client:user_sessions:`
- `auth:rotate:` namespace → `auth:client:rotate:`

Branch skeleton (the three branches are structurally identical):
```python
async def rotate_client_refresh(
    session: AsyncSession,
    redis: Redis,
    presented_token: str,
) -> tuple[str, str, str]:
    """Rotate a client refresh token; return new (access, refresh, csrf).
    Three branches: (A) ACTIVE, (B) REPLACED-WITHIN-WINDOW, (C) REUSE/REVOKED.
    Mirrors rotate_refresh exactly (service.py L367-569).
    """
    ...  # identical branch logic, different model/namespace
```

---

### `app/modules/client_auth/rate_limit.py` — NEW: per-phone OTP rate limiters

**Analog:** `app/modules/auth/rate_limit.py` (L1–47) — copy the fixed-window Redis pattern exactly, new key namespaces and different limits.

**Full file pattern** (mirror auth/rate_limit.py structure):
```python
"""Per-phone client OTP rate limiters (D-11 / CAUTH-06).

Three limits:
  - per-IP:   5 requests per 15 min   (spec: ≥5/15min)
  - cooldown: 1 per 60s per phone     (spec: ≥60s between requests)
  - daily:    5 per 24h per phone     (spec: ≤5/24h)

Key rationale (D-11): these are SEPARATE keys from the staff login limiter
(ratelimit:login:{email}) — the two principals must never share quota.
"""

from redis.asyncio import Redis
from app.core.exceptions import RateLimited

_IP_LIMIT = 5
_IP_WINDOW = 900          # 15 min
_COOLDOWN_SECONDS = 60    # per phone
_DAILY_LIMIT = 5
_DAILY_WINDOW = 86400     # 24h


def _ip_key(ip: str) -> str:
    return f"ratelimit:client_otp_ip:{ip}"

def _cooldown_key(phone: str) -> str:
    return f"ratelimit:client_otp_cooldown:{phone}"

def _daily_key(phone: str) -> str:
    return f"ratelimit:client_otp_daily:{phone}"


async def check_client_ip_rate(redis: Redis, ip: str | None) -> None:
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
    raw = await redis.get(_daily_key(phone))
    if raw is not None and int(raw) >= _DAILY_LIMIT:
        raise RateLimited("rate_limited")


async def bump_client_ip_rate(redis: Redis, ip: str | None) -> None:
    if ip is None:
        return
    pipe = redis.pipeline()
    pipe.incr(_ip_key(ip))
    pipe.expire(_ip_key(ip), _IP_WINDOW)
    await pipe.execute()


async def record_client_otp_sent(redis: Redis, phone: str) -> None:
    """SET cooldown key with 60s TTL (one-shot: expires naturally)."""
    await redis.set(_cooldown_key(phone), "1", ex=_COOLDOWN_SECONDS)


async def bump_client_otp_daily(redis: Redis, phone: str) -> None:
    pipe = redis.pipeline()
    pipe.incr(_daily_key(phone))
    pipe.expire(_daily_key(phone), _DAILY_WINDOW)
    await pipe.execute()
```

---

### `app/modules/client_auth/schemas.py` — NEW: request/response Pydantic models

**Analog:** `app/modules/auth/schemas.py` (LoginRequest/LoginResponse/MeResponse shape). Use `BackendSchemaBase` with `alias_generator` for camelCase wire format.

**Pattern** (mirror the camelCase + ResponseEnvelope convention):
```python
from app.core.schemas import BackendSchemaBase  # alias_generator=to_camel, populate_by_name=True

class ClientOtpRequestBody(BackendSchemaBase):
    phone: str  # E.164

class ClientOtpVerifyBody(BackendSchemaBase):
    phone: str
    code: str   # 6-digit raw OTP

class ClientMeResponse(BackendSchemaBase):
    id: UUID
    phone: str
    email: str | None
    first_name: str
    last_name: str
    middle_name: str | None
    birthday: date | None
    gender: str | None   # "male" | "female" | None

class ClientMePatchRequest(BackendSchemaBase):
    email: str | None = None   # D-04: email-only self-edit this phase
```

---

### `app/modules/client_auth/router.py` — NEW: `/api/v1/client` router

**Analog:** `app/modules/auth/router.py` (L1–200) — exact controller pattern. Also mirror `app/modules/clients/router.py` for the `GET/PATCH /me` shape.

**Imports pattern** (mirror auth/router.py lines 22–71):
```python
from typing import Annotated
from fastapi import APIRouter, Depends, Request, Response
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_db
from app.core.dependencies import require_client, verify_csrf
from app.core.exceptions import InvalidAccessToken
from app.core.redis import get_redis
from app.core.schemas import ResponseEnvelope, envelope
from app.core.security import (
    clear_client_session_cookies,
    issue_client_session_cookies,
)
from app.modules.client_auth import service
from app.modules.client_auth.schemas import (
    ClientMePatchRequest,
    ClientMeResponse,
    ClientOtpRequestBody,
    ClientOtpVerifyBody,
)

router = APIRouter(tags=["Client"])
```

**OTP request handler** — mirror `otp_request` (auth/router.py ~L380):
```python
@router.post("/otp/request", response_model=ResponseEnvelope[None])
async def client_otp_request(
    payload: ClientOtpRequestBody,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db)],
    redis: Annotated[Redis, Depends(get_redis)],
) -> ResponseEnvelope[None]:
    ip = request.client.host if request.client is not None else None
    await service.request_client_otp(session, redis, payload.phone, ip=ip)
    return envelope(None)
```

**OTP verify + session issue** — mirror `telegram_verify` (auth/router.py):
```python
@router.post("/otp/verify", response_model=ResponseEnvelope[None])
async def client_otp_verify(
    payload: ClientOtpVerifyBody,
    response: Response,
    session: Annotated[AsyncSession, Depends(get_db)],
    redis: Annotated[Redis, Depends(get_redis)],
) -> ResponseEnvelope[None]:
    settings = get_settings()
    access, refresh, csrf = await service.verify_client_otp(session, redis, payload.phone, payload.code)
    issue_client_session_cookies(response, access_token=access, refresh_token=refresh, csrf_token=csrf, secure=settings.cookie_secure)
    return envelope(None)
```

**Refresh handler** — mirror `/refresh` (auth/router.py lines 97–124), read `cc_client_refresh`:
```python
@router.post("/session/refresh", response_model=ResponseEnvelope[None])
async def client_session_refresh(
    request: Request,
    response: Response,
    session: Annotated[AsyncSession, Depends(get_db)],
    redis: Annotated[Redis, Depends(get_redis)],
) -> ResponseEnvelope[None]:
    settings = get_settings()
    presented = request.cookies.get("cc_client_refresh")
    if presented is None:
        raise InvalidAccessToken("missing_refresh_cookie")
    access, refresh, csrf = await service.rotate_client_refresh(session, redis, presented)
    issue_client_session_cookies(response, access_token=access, refresh_token=refresh, csrf_token=csrf, secure=settings.cookie_secure)
    return envelope(None)
```

**Logout handler** — mirror `/logout` (auth/router.py lines 127–150), CSRF-gated, RBAC-04 ordering (auth dep first):
```python
@router.post("/session/logout", response_model=ResponseEnvelope[None])
async def client_logout(
    request: Request,
    response: Response,
    _client: Annotated[ClientPrincipal, Depends(require_client())],
    _csrf: Annotated[None, Depends(verify_csrf)],
    session: Annotated[AsyncSession, Depends(get_db)],
    redis: Annotated[Redis, Depends(get_redis)],
) -> ResponseEnvelope[None]:
    settings = get_settings()
    presented = request.cookies.get("cc_client_refresh")
    if presented is not None:
        await service.revoke_client_session(session, redis, presented)
    clear_client_session_cookies(response, secure=settings.cookie_secure)
    return envelope(None)
```

**GET /me handler** — mirror `/me` (auth/router.py):
```python
@router.get("/me", response_model=ResponseEnvelope[ClientMeResponse])
async def get_client_me(
    client: Annotated[ClientPrincipal, Depends(require_client())],
) -> ResponseEnvelope[ClientMeResponse]:
    return envelope(ClientMeResponse.model_validate(client))
```

**PATCH /me handler** — mirror `update_client` (clients/router.py), HTTP 409 for duplicate email (D-06):
```python
@router.patch("/me", response_model=ResponseEnvelope[ClientMeResponse])
async def patch_client_me(
    payload: ClientMePatchRequest,
    client: Annotated[ClientPrincipal, Depends(require_client())],
    _csrf: Annotated[None, Depends(verify_csrf)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ResponseEnvelope[ClientMeResponse]:
    updated = await service.update_client_me(session, client.id, payload)
    return envelope(ClientMeResponse.model_validate(updated))
```

---

### `app/api/v1/router.py` — MODIFY: mount `/client` router

**Analog:** `app/api/v1/router.py` lines 47–109 — add one `v1.include_router` call at end of business mounts, before the `_internal` section:

```python
from app.modules.client_auth.router import router as client_auth_router

# Phase 68 — client auth + profile self-service (CAUTH-01..06, CISO-01..05)
v1.include_router(client_auth_router, prefix="/client")
```

---

### `app/main.py` — MODIFY: register `client_loader` in `create_app()`

**Analog:** `app/main.py` lines 452–453 (`register_user_loader(load_user_by_id)`) — add alongside:

```python
# Phase 68 D-08 — client principal composition-root slot.
# load_client_by_id lives in app.modules.clients.service (existing module).
from app.modules.clients.service import load_client_by_id  # local import inside create_app body
register_client_loader(load_client_by_id)
```

**Also add** to the `register_*` imports block at top of `create_app` (app/main.py lines 59–77):
```python
from app.core.dependencies import (
    ...
    register_client_loader,  # Phase 68
)
```

---

### `alembic/versions/NNNN_client_auth_otp.py` — NEW: add `client_id` FK + CHECK + partial-unique to `otp_codes`

**Analog:** Look at `alembic/versions/0001_auth.py` (lines 53–80) for table-level FK + constraint patterns, and the existing index-add migrations for the partial-unique pattern.

**Migration pattern** (additive: add column + constraint + index):
```python
def upgrade() -> None:
    op.add_column(
        "otp_codes",
        sa.Column(
            "client_id",
            sa.UUID(),
            sa.ForeignKey("clients.id", ondelete="CASCADE", name=op.f("fk_otp_codes_client_id_clients")),
            nullable=True,
        ),
    )
    op.create_check_constraint(
        "ck_otp_codes_principal_xor",
        "otp_codes",
        "(user_id IS NULL) <> (client_id IS NULL)",
    )
    op.create_index(
        "uq_otp_codes_client_channel_active",
        "otp_codes",
        ["client_id", "channel"],
        unique=True,
        postgresql_where=sa.text("consumed_at IS NULL"),
    )

def downgrade() -> None:
    op.drop_index("uq_otp_codes_client_channel_active", table_name="otp_codes")
    op.drop_constraint("ck_otp_codes_principal_xor", "otp_codes")
    op.drop_column("otp_codes", "client_id")
```

---

### `alembic/versions/NNNN_client_refresh_token.py` — NEW: create `client_refresh_tokens` table

**Analog:** `alembic/versions/0001_auth.py` `refresh_tokens` section — copy structure verbatim, replace FK target and table name.

**Migration pattern** (mirror 0001_auth.py `refresh_tokens` block):
```python
def upgrade() -> None:
    op.create_table(
        "client_refresh_tokens",
        sa.Column("client_id", sa.UUID(), nullable=False),
        sa.Column("family_id", sa.UUID(), nullable=False),
        sa.Column("token_hash", sa.Text(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("replaced_by_id", sa.UUID(), nullable=True),
        sa.Column("replaced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["client_id"], ["clients.id"],
            name=op.f("fk_client_refresh_tokens_client_id_clients"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["replaced_by_id"], ["client_refresh_tokens.id"],
            name=op.f("fk_client_refresh_tokens_replaced_by_id_client_refresh_tokens"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_client_refresh_tokens")),
        sa.UniqueConstraint("token_hash", name=op.f("uq_client_refresh_tokens_token_hash")),
    )
    op.create_index(
        "ix_client_refresh_tokens_client_id_family_id",
        "client_refresh_tokens", ["client_id", "family_id"],
    )
```

---

### `tests/integration/client_auth/test_otp_isolation.py` — NEW: two-principal isolation + anti-oracle tests

**Analog:** `tests/integration/auth/test_otp_email_anti_oracle.py` (L1–80) and `tests/integration/auth/test_login.py` (full file)

**Fixture + test harness pattern** (copy exactly from conftest.py lines 49–141 — SAVEPOINT + ASGITransport + Redis flush):
```python
pytestmark = pytest.mark.asyncio

@pytest_asyncio.fixture
async def redis_clean(app: FastAPI) -> Redis:
    """Flush Redis between tests so rate-limit + session keys don't bleed."""
    client: Redis = app.state.redis
    await client.flushdb()
    return client

@pytest_asyncio.fixture
async def seeded_client(db_session: AsyncSession, redis_clean: Redis) -> Client:
    client = Client(
        first_name="Test", last_name="Client",
        phone="+79001234567",
        telegram_user_id=123456789,
        created_by_user_id=...,  # requires seeded staff user
    )
    db_session.add(client)
    await db_session.commit()
    return client
```

**Two-principal isolation test** (CISO-02 — staff access-token rejected by client endpoint):
```python
async def test_staff_token_rejected_by_client_endpoint(
    async_client: AsyncClient,
    seeded_owner: User,  # existing staff fixture
) -> None:
    """A valid staff cc_access cookie MUST NOT authenticate /api/v1/client/me."""
    # Login as staff, get cc_access cookie
    resp = await async_client.post("/api/v1/auth/login", json={...})
    staff_access = resp.cookies["cc_access"]

    # Attempt to hit client endpoint with staff cookie
    me_resp = await async_client.get(
        "/api/v1/client/me",
        cookies={"cc_client_access": staff_access},  # wrong cookie name but same token value
    )
    assert me_resp.status_code == 401
```

**Anti-oracle test pattern** (mirror test_otp_email_anti_oracle.py) — all OTP-request cases return 202 and same body:
```python
@pytest.mark.parametrize("phone", [
    "+79001111111",   # case A: client with telegram_user_id
    "+79002222222",   # case B: client without telegram_user_id (silent drop)
    "+79009999999",   # case C: nonexistent phone (silent drop)
])
async def test_otp_request_anti_oracle(
    async_client: AsyncClient, phone: str, ...
) -> None:
    resp = await async_client.post("/api/v1/client/otp/request", json={"phone": phone})
    assert resp.status_code == 202
    assert resp.json() == {"data": None, ...}  # byte-identical envelope
```

---

### `tests/integration/client_auth/test_idor.py` — NEW: parametrized IDOR test

**Analog:** `tests/integration/auth/test_login.py` pattern — seed two clients, verify each only sees their own `/me` data.

**IDOR test pattern** (CISO-04):
```python
@pytest.mark.parametrize("attacker_as,victim_id_fixture", [
    ("client_a", "client_b_id"),
    ("client_b", "client_a_id"),
])
async def test_client_cannot_read_other_client_me(
    async_client: AsyncClient,
    attacker_as: str,
    victim_id_fixture: str,
    ...
) -> None:
    """A client can only GET /client/me for their own principal."""
    # Authenticate as attacker, attempt to GET victim profile
    # /client/me has no {id} parameter — returns the cookie principal's own profile
    # IDOR surface: ensure the returned id matches the authenticated client only
    resp = await async_client.get("/api/v1/client/me", cookies=attacker_cookies)
    assert resp.status_code == 200
    assert resp.json()["data"]["id"] == str(attacker_client.id)
    assert resp.json()["data"]["id"] != str(victim_client.id)
```

---

## Shared Patterns

### Anti-oracle `_constant_time_floor`
**Source:** `app/modules/auth/service.py` lines 942–953
**Apply to:** `request_client_otp` in client_auth/service.py — wrap the entire function body in `try/finally`, call `await _constant_time_floor(t_start)` in the `finally` block so exceptions (rate-limited, DB errors) also hit the floor.

```python
_CLIENT_OTP_FLOOR_MS: Final[float] = 200.0

async def _constant_time_floor(t_start: float) -> None:
    elapsed_ms = (time.perf_counter() - t_start) * 1000
    remaining_ms = _CLIENT_OTP_FLOOR_MS - elapsed_ms
    if remaining_ms > 0:
        await asyncio.sleep(remaining_ms / 1000)
```

### Cookie attribute discipline
**Source:** `app/core/security.py` lines 204–292 (`issue_session_cookies` + `clear_session_cookies`)
**Apply to:** `issue_client_session_cookies` and `clear_client_session_cookies` in security.py additions. The `clear_*` attributes (Path, HttpOnly, Secure, SameSite) MUST exactly match `issue_*` or the browser silently ignores the deletion. This is enforced structurally by keeping both functions in the same file and the same block.

### SAVEPOINT test harness
**Source:** `tests/conftest.py` lines 57–141
**Apply to:** All integration tests in `tests/integration/client_auth/`. Copy the `db_session` + `async_client` fixtures as-is from conftest.py (they are already session-fixture; no duplication needed — just use them). Add a `redis_clean` fixture (mirrors test_login.py lines 28–32) at the integration test module level.

### Composition-root loader slot pattern
**Source:** `app/core/dependencies.py` lines 51–68, `app/main.py` lines 452–453
**Apply to:** `register_client_loader` in dependencies.py + `create_app()` wiring in main.py. Pattern: global `_client_loader: ClientLoader | None = None`, setter `register_client_loader(loader)` replaces slot (idempotent — test stub injection), defensive raise in `get_current_client` if slot is None.

### Structlog event names
**Source:** `app/modules/auth/service.py` — locked event names (`otp_requested`, `otp_consumed`, `family_reuse_detected`)
**Apply to:** Client service should use parallel event names: `client_otp_requested`, `client_otp_consumed`, `client_family_reuse_detected`. Do NOT reuse staff event names (audit taxonomy must distinguish principals).

### `audit.emit` BEFORE `session.commit` (Pitfall 2)
**Source:** `app/modules/auth/telegram_service.py` lines 100–109, 194–203
**Apply to:** Every write path in `client_auth/service.py` that mutates OtpCode or ClientRefreshToken. Always call `audit.emit(session, ...)` before `await session.commit()` so the audit row is atomic with the mutation.

### ResponseEnvelope + `envelope()` wrapper
**Source:** `app/modules/auth/router.py` lines 81–94, `app/modules/clients/router.py` lines 62–64
**Apply to:** All handlers in `client_auth/router.py`. Every successful response uses `return envelope(payload)`.

---

## No Analog Found

All files for Phase 68 have close analogs. No `No Analog` entries.

---

## Notes for Planner

1. **Module location**: All new client auth code goes in `app/modules/client_auth/` (new module, not `app/modules/auth/`). The `app/modules/auth/` module is staff-only and must not be modified except for the `OtpCode.client_id` column addition to `models.py`.

2. **`load_client_by_id` in clients/service.py**: This function likely needs to be ADDED to the existing clients service (returning a `Client` by UUID for alive rows). Check `app/modules/auth/service.py` for `load_user_by_id` as the template.

3. **`verify_csrf` for client endpoints**: The existing `verify_csrf` dependency in `app/core/dependencies.py` checks the `X-CSRF-Token` header against `clubcore_csrf` cookie. For client endpoints, either reuse it (if it's cookie-name-agnostic) or add a `verify_client_csrf` that checks `clubcore_client_csrf`. Inspect `verify_csrf` implementation to decide.

4. **Migration numbering**: Check `alembic/versions/` for the latest revision to determine the correct next revision numbers. The two new migrations should be numbered sequentially after the current highest.

5. **`PUBLIC_ENDPOINT_OPERATION_IDS` in main.py**: Add client OTP request and verify operation IDs to the frozenset (lines 228–241) so they are excluded from the global security requirement in the OpenAPI spec.

---

## Metadata

**Analog search scope:** `apps/backend/app/` + `apps/backend/tests/`
**Files scanned:** ~20 source files read, ~15 via targeted grep
**Pattern extraction date:** 2026-05-29
