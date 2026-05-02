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

from uuid import UUID

from pydantic import EmailStr, Field

from app.core.permissions import Role
from app.core.schemas import RequestContract, ResponseData


class LoginRequest(RequestContract):
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
