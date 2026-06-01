"""Client auth Pydantic schemas — OTP request/verify bodies (Phase 68).

All models extend BackendSchemaBase which wires camelCase alias_generator (to_camel)
and populate_by_name=True for Python-side attribute access.

GET/PATCH /client/me schemas (ClientMeResponse / ClientMePatchRequest) were removed
in the Phase 999.5 route-consolidation: client_portal/schemas.py now owns the
/client/me request/response models (the email round-trip + onboarding profile fields).
The duplicate /me pair here used to shadow the onboarding handlers under the shared
/api/v1/client prefix.

Decisions implemented:
  CAUTH-03 — phone fields validated against PHONE_REGEX (E.164).
"""

from pydantic import Field

from app.core.schemas import BackendSchemaBase

# E.164 phone regex (CAUTH-03). Mirrors PHONE_REGEX in clients/schemas.py
# but declared locally to avoid a cross-module import (importlinter contract:
# modules cannot import each other). Must be kept in sync if ever tightened.
_PHONE_REGEX: str = r"^\+[1-9]\d{1,14}$"


class ClientOtpRequestBody(BackendSchemaBase):
    """POST /client/otp/request — phone-first OTP trigger (D-01, CAUTH-03)."""

    phone: str = Field(pattern=_PHONE_REGEX)


class ClientOtpVerifyBody(BackendSchemaBase):
    """POST /client/otp/verify — consume OTP + issue session cookies (CAUTH-01)."""

    phone: str = Field(pattern=_PHONE_REGEX)
    code: str
