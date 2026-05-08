"""Auth Pydantic schemas (Phase 5).

Wire format is camelCase via the to_camel alias generator on ContractModel
(Phase 4 D-09); Python identifiers stay snake_case. `validate_by_name=True`
+ `validate_by_alias=True` (set on the base in core.schemas) means consumers
can pass either form on input and we serialize to camelCase on output.

Locked password minimum length is 12 (AUTH-EP-05 / NIST 800-63B 2024 — no
complexity rules, no rotation, no lockout). The 12-char floor is enforced
here at the contract boundary so `authenticate(...)` never sees < 12 char
inputs.
"""

from datetime import datetime
from uuid import UUID

from pydantic import EmailStr, Field

from app.core.pagination import PaginatedData
from app.core.permissions import Role
from app.core.schemas import BackendSchemaBase, ResponseData


class LoginRequest(BackendSchemaBase):
    """POST /api/v1/auth/login body."""

    email: EmailStr
    password: str = Field(min_length=12)


class UserPublic(ResponseData):
    """Subset of User exposed on login response."""

    id: UUID
    role: Role
    full_name: str  # → fullName on wire


class LoginResponse(ResponseData):
    """POST /api/v1/auth/login response body (wrapped in ResponseEnvelope)."""

    user: UserPublic


class MeResponse(ResponseData):
    """GET /api/v1/auth/me response body (wrapped in ResponseEnvelope)."""

    id: UUID
    role: Role
    full_name: str  # → fullName
    email: EmailStr
    has_telegram: bool  # → hasTelegram (derived: telegram_chat_id IS NOT NULL)


# ---------------------------------------------------------------------------
# Phase 7 — Telegram OTP channel (AUTH-TG-01..06).
# ---------------------------------------------------------------------------


class TelegramStartResponse(ResponseData):
    """POST /auth/telegram/start success body (AUTH-TG-01).

    snake_case → camelCase auto: `deep_link_url` → `deepLinkUrl`,
    `deep_link_token` → `deepLinkToken`.
    """

    deep_link_url: str
    deep_link_token: str


class TelegramStatusResponse(ResponseData):
    """GET /auth/telegram/status success body (AUTH-TG-03)."""

    bound: bool


class TelegramVerifyRequest(BackendSchemaBase):
    """POST /auth/telegram/verify request body (AUTH-TG-04).

    `code` must be exactly 6 digits — short-circuits non-digit input
    before the service hits Postgres.
    """

    deep_link_token: str
    code: str = Field(min_length=6, max_length=6, pattern=r"^\d{6}$")


# ---------------------------------------------------------------------------
# Phase 23 — Active sessions surface (HYG-03, FE-09 consumer).
# ---------------------------------------------------------------------------


class ActiveSessionItem(ResponseData):
    """Single active session family row in the /sessions list response (D-23-4).

    camelCase serialization is automatic via alias_generator=to_camel on ContractModel.
    Wire names: familyId, createdAt, lastUsedAt, userAgent, channel, isCurrent.
    """

    family_id: UUID  # → familyId
    created_at: datetime  # → createdAt
    last_used_at: datetime  # → lastUsedAt
    user_agent: str | None  # → userAgent (None for pre-Phase-23 sessions, CD-01 trade-off)
    channel: str  # 'email_password' | 'telegram' | future; default 'email_password'
    is_current: bool  # → isCurrent (True if this family matches the current sz_refresh)


# Type alias — ResponseEnvelope[PaginatedData[ActiveSessionItem]] on the wire.
# Wire shape: {"data": {"items": [...], "total": N, "page": 1, "pageSize": 20}}
ActiveSessionsListResponse = PaginatedData[ActiveSessionItem]
