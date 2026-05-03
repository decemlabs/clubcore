"""Clients module Pydantic DTOs (Phase 8 — CLIENTS-01, CLIENTS-04, CLIENTS-06, CLIENTS-07).

All DTOs inherit the ContractModel chain (RequestContract / ResponseData / PageQuery)
so wire format is camelCase via `alias_generator=to_camel` while Python stays snake_case.

Decisions enforced here at the DTO boundary (defence-in-depth — DB constraints in
models.py / migration are the second line):

- D-10  E.164 phone validation `^\\+[1-9]\\d{1,14}$` for Client.phone and
        EmergencyContact.phone.
- D-15  Gender uses the StrEnum from models.py (closed enum: male / female).
- D-16  tags array: max 16 items, max 32 chars/tag, lowercase. Allowed chars:
        ASCII a-z + 0-9 + Cyrillic lowercase + hyphen + underscore. Regex defined
        in TAG_REGEX below. Same rules apply on create + update.
- D-17  EmergencyContact is a Pydantic model (JSONB shape on the wire).

ClientUpdateRequest + ClientListQuery are added in the next task — D-01 (null-rejection),
D-12 (q minimum), D-14 (datetime boundaries) live there.

No ORM imports cross this boundary except `Gender` (a pure StrEnum, not an ORM class).
"""

import re
from datetime import date, datetime
from uuid import UUID

from pydantic import EmailStr, Field, field_validator

from app.core.schemas import RequestContract, ResponseData
from app.modules.clients.models import Gender

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

PHONE_REGEX = r"^\+[1-9]\d{1,14}$"  # E.164 (D-10)
# D-16 allows Cyrillic lowercase letters in tags. The regex below contains a
# literal Cyrillic range; RUF001 (ambiguous unicode) is suppressed intentionally.
TAG_REGEX = re.compile(r"^[a-z0-9а-я\-_]+$")  # noqa: RUF001
MAX_TAGS = 16
MAX_TAG_LENGTH = 32


# ---------------------------------------------------------------------------
# Tag validator — shared between ClientCreateRequest and (future) ClientUpdateRequest
# ---------------------------------------------------------------------------


def _validate_tags(v: list[str]) -> list[str]:
    """D-16: lowercase + size + regex normalisation.

    Rules:
      * len(tags) <= MAX_TAGS (16)
      * each tag.strip().lower() must be non-empty, <= MAX_TAG_LENGTH (32) chars,
        and match TAG_REGEX (see module-level constant).

    Returns the normalised list (lowercase + stripped).
    """
    if len(v) > MAX_TAGS:
        raise ValueError(f"Maximum {MAX_TAGS} tags per client")
    result: list[str] = []
    for tag in v:
        normalised = tag.strip().lower()
        if len(normalised) == 0:
            raise ValueError("Empty tag not allowed")
        if len(normalised) > MAX_TAG_LENGTH:
            raise ValueError(f"Tag '{normalised}' exceeds {MAX_TAG_LENGTH} characters")
        if not TAG_REGEX.match(normalised):
            raise ValueError(f"Tag '{normalised}' contains invalid characters")
        result.append(normalised)
    return result


# ---------------------------------------------------------------------------
# EmergencyContact (D-17) — embedded JSONB shape
# ---------------------------------------------------------------------------


class EmergencyContact(ResponseData):
    """Free-shape contact owned by UI (D-17). Same E.164 phone as Client.phone."""

    name: str = Field(min_length=1, max_length=128)
    phone: str = Field(pattern=PHONE_REGEX)
    relation: str | None = Field(default=None, max_length=64)


# ---------------------------------------------------------------------------
# ClientCreateRequest (CLIENTS-06, D-10, D-15, D-16, D-17)
# ---------------------------------------------------------------------------


class ClientCreateRequest(RequestContract):
    """POST /api/v1/clients body. Required: lastName, firstName, phone."""

    last_name: str = Field(min_length=1, max_length=128)
    first_name: str = Field(min_length=1, max_length=128)
    middle_name: str | None = Field(default=None, max_length=128)
    phone: str = Field(pattern=PHONE_REGEX)
    email: EmailStr | None = None
    birthday: date | None = None
    gender: Gender | None = None
    tags: list[str] = Field(default_factory=list)
    notes: str | None = Field(default=None, max_length=4096)
    emergency_contact: EmergencyContact | None = None
    telegram_user_id: int | None = None  # bigint; service may set, FE usually does not

    @field_validator("tags")
    @classmethod
    def _normalise_tags(cls, v: list[str]) -> list[str]:
        """D-16: lowercase + size + regex constraints."""
        return _validate_tags(v)


# ---------------------------------------------------------------------------
# ClientResponse — read-side DTO
# ---------------------------------------------------------------------------


class ClientResponse(ResponseData):
    """Single client read DTO. `from_attributes=True` (inherited via ContractModel)
    allows `ClientResponse.model_validate(orm_client_instance)`.

    `deleted_at` is intentionally omitted — soft-deleted rows are 404'd at the
    repository boundary (Plan 04 `get_alive`); the response shape never carries it.
    """

    id: UUID
    last_name: str
    first_name: str
    middle_name: str | None = None
    phone: str
    email: str | None = None
    birthday: date | None = None
    gender: Gender | None = None
    tags: list[str]
    notes: str | None = None
    emergency_contact: EmergencyContact | None = None
    telegram_user_id: int | None = None
    created_by_user_id: UUID
    created_at: datetime
    updated_at: datetime
