"""Client auth Pydantic schemas — request bodies + response models (Phase 68 D-04/D-05).

All models extend BackendSchemaBase which wires camelCase alias_generator (to_camel)
and populate_by_name=True for Python-side attribute access.

Decisions implemented:
  D-04  — ClientMePatchRequest accepts email only.
  D-05  — ClientMeResponse exposes core identity only (id/phone/email/names/birthday/gender).
  CAUTH-03 — phone fields validated against PHONE_REGEX (E.164).
"""

from datetime import date
from uuid import UUID

from pydantic import Field

from app.core.schemas import BackendSchemaBase
from app.modules.clients.schemas import PHONE_REGEX


class ClientOtpRequestBody(BackendSchemaBase):
    """POST /client/otp/request — phone-first OTP trigger (D-01, CAUTH-03)."""

    phone: str = Field(pattern=PHONE_REGEX)


class ClientOtpVerifyBody(BackendSchemaBase):
    """POST /client/otp/verify — consume OTP + issue session cookies (CAUTH-01)."""

    phone: str = Field(pattern=PHONE_REGEX)
    code: str


class ClientMeResponse(BackendSchemaBase):
    """GET /client/me — core identity only (D-05).

    Excludes staff-internal fields (notes, tags, created_by_user_id,
    emergency_contact) and all membership data — membership status is
    Phase 69 scope (GET /client/membership).
    """

    id: UUID
    phone: str
    email: str | None
    first_name: str
    last_name: str
    middle_name: str | None
    birthday: date | None
    gender: str | None  # "male" | "female" | None


class ClientMePatchRequest(BackendSchemaBase):
    """PATCH /client/me — email-only self-edit (D-04).

    Name, birthday, phone, tags, and notes are staff-owned and read-only via
    this endpoint; broader self-edit is deferred to a future phase.
    """

    email: str | None = None
