"""Phase 43 users module request/response DTOs (USERS-01/02/03).

All schemas inherit from BackendSchemaBase (camelCase wire format, extra='forbid').
Response models inherit from ResponseData (adds from_attributes=True for ORM-to-DTO validation).

Excluded from EVERY response model (D-43-10 explicit denylist):
  - password_hash (never returned)
  - password_changed_at (auth-internal)
  - telegram_chat_id, telegram_username (D-43-10)
  - email_verified (D-43-02 — operationally interesting only at invite-accept / login)
  - raw invitation tokens (D-43-13 — token row id only, raw token only in email)
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import EmailStr, Field, computed_field

from app.core.pagination import PageQuery
from app.core.permissions import Role
from app.core.schemas import BackendSchemaBase, ResponseData


class UserCreateRequest(BackendSchemaBase):
    """POST /api/v1/users body — D-43-13."""

    email: EmailStr = Field(max_length=255)
    full_name: str = Field(min_length=1, max_length=128)
    role: Role


class UserListQuery(PageQuery):
    """GET /api/v1/users query params — D-43-15.

    Defaults: active unset (returns both active+inactive),
    deleted=False (only deleted_at IS NULL rows).
    """

    active: bool | None = None
    deleted: bool = False


class UserListItemResponse(ResponseData):
    """Item shape for GET /api/v1/users list — D-43-10.

    Fields explicitly enumerated per ROADMAP success criterion #5.
    NO password_hash / telegram_* / email_verified leak.
    """

    id: UUID
    email: EmailStr
    full_name: str
    role: Role
    is_active: bool
    status: Literal["active", "pending_invitation"]
    created_at: datetime
    deactivated_at: datetime | None
    deactivated_by_user_id: UUID | None
    invitation_expires_at: datetime | None
    invitation_token_id: UUID | None = None

    @computed_field  # type: ignore[prop-decorator]
    @property
    def is_deactivated(self) -> bool:
        """Derived per D-43-10 — `not is_active and deactivated_at is not None`."""
        return not self.is_active and self.deactivated_at is not None


class UserCreateResponse(ResponseData):
    """POST /api/v1/users response — D-43-13. NEVER returns plaintext password."""

    id: UUID
    email: EmailStr
    role: Role
    invitation_expires_at: datetime
    # D-43-14 — populated only when ?include_invite_link=true was passed.
    invite_link_url: str | None = None


class InvitationRevokeRequest(BackendSchemaBase):
    """POST /api/v1/users/invitations/{token_id}/revoke body — D-43-19."""

    reason: str | None = Field(default=None, max_length=500)


class InvitationAcceptRequest(BackendSchemaBase):
    """Body for POST /api/v1/users/invitations/accept (RESET-04).

    - ``token`` is the raw urlsafe-base64 token from the invitation URL fragment.
    - ``password`` is the user's chosen initial password (>=8 chars enforced
      at the service layer per D-44-17 — domain error, not pydantic 422).
    - ``full_name`` is optional; non-empty value overwrites the owner-set
      value per D-44-23 (self-healing typo correction at accept time).
      Max length mirrors ``UserCreateRequest.full_name`` (128).
    """

    token: str = Field(min_length=1, max_length=128)
    password: str = Field(min_length=1, max_length=256)
    full_name: str | None = Field(default=None, max_length=128)
