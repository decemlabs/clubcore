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
from typing import Literal
from uuid import UUID

from pydantic import EmailStr, Field, model_validator

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
# Phase 42 — Unified OTP request channel discriminator (AUTH-EM-02 / D-42-22).
# ---------------------------------------------------------------------------


class OtpRequestBody(BackendSchemaBase):
    """POST /api/v1/auth/otp/request body (D-42-22 / AUTH-EM-02).

    channel='telegram' (default) preserves backwards compat — existing
    callers send no ``channel`` field and the route surfaces the unified
    OTP flow under one endpoint. The service-layer Telegram facade
    (``request_otp_telegram``) delegates to the pre-existing
    ``telegram_service.start_deep_link`` so /auth/telegram/start stays in
    place for any FE callers that already use it.

    channel='email' requires ``email`` to be present; the model_validator
    enforces this so FastAPI returns 422 BEFORE the route function runs.
    The 422 is not an anti-oracle leak: invalid body SHAPE is not a
    successful-vs-unknown-account discriminator — anti-oracle is enforced
    in the authenticated branches of ``request_otp_email`` (Task 4).
    """

    channel: Literal["telegram", "email"] = "telegram"
    email: EmailStr | None = None

    @model_validator(mode="after")
    def _email_required_when_email_channel(self) -> "OtpRequestBody":
        if self.channel == "email" and self.email is None:
            raise ValueError("email is required when channel='email'")
        return self


# ---------------------------------------------------------------------------
# Phase 44 — Password reset request/confirm bodies (RESET-01 / RESET-02).
# ---------------------------------------------------------------------------


class PasswordResetRequestBody(BackendSchemaBase):
    """Body for POST /api/v1/auth/password-reset/request (RESET-01).

    Anti-oracle: the email is lowercased server-side; format validation
    is intentionally permissive (any string admitted — the anti-oracle
    envelope hides resolution semantics, NOT format errors). ``EmailStr``
    is deliberately NOT used here — a 422-on-bad-format would leak a
    coarse "this string is shaped like an email vs. nonsense" oracle that
    the 4-case identical-202 envelope (D-44-06) is supposed to suppress.
    ``str`` with ``min_length=1`` accepts every shape and forces the
    service layer to handle resolution uniformly.
    """

    email: str = Field(min_length=1, max_length=320)


class PasswordResetConfirmBody(BackendSchemaBase):
    """Body for POST /api/v1/auth/password-reset/confirm (RESET-02).

    - ``token`` is the raw urlsafe-base64 token from the email URL fragment.
    - ``new_password`` is the user's chosen new password (min 8 chars
      enforced at service layer per D-44-17). The schema accepts any
      string >=1 chars so weak-password failures become domain errors
      (422 weak_password) rather than Pydantic validation errors —
      consistent with the v1.0 AUTH-* baseline.
    """

    token: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=1, max_length=256)


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
    is_current: bool  # → isCurrent (True if this family matches the current cc_refresh)


# Type alias — ResponseEnvelope[PaginatedData[ActiveSessionItem]] on the wire.
# Wire shape: {"data": {"items": [...], "total": N, "page": 1, "pageSize": 20}}
ActiveSessionsListResponse = PaginatedData[ActiveSessionItem]
