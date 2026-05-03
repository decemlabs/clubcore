"""Clients module Pydantic DTOs (Phase 8 — CLIENTS-01, CLIENTS-04, CLIENTS-06, CLIENTS-07).

All DTOs inherit the ContractModel chain (RequestContract / ResponseData / PageQuery)
so wire format is camelCase via `alias_generator=to_camel` while Python stays snake_case.

Decisions enforced here at the DTO boundary (defence-in-depth — DB constraints in
models.py / migration are the second line):

- D-01  ClientUpdateRequest rejects explicit `null` (PATCH semantics: omit key to leave
        unchanged; explicit clear is unsupported in v1.1).
- D-10  E.164 phone validation `^\\+[1-9]\\d{1,14}$` for Client.phone and
        EmergencyContact.phone.
- D-12  ClientListQuery.q < 2 chars after strip → normalised to None (service skips
        ILIKE filter — no full-table scan).
- D-14  ClientListQuery.created_from / created_to accept date or datetime; date-only
        inputs are normalised to UTC boundaries (00:00:00 / 23:59:59.999999).
- D-15  Gender uses the StrEnum from models.py (closed enum: male / female).
- D-16  tags array: max 16 items, max 32 chars/tag, lowercase. Allowed chars:
        ASCII a-z + 0-9 + Cyrillic lowercase + hyphen + underscore. Regex defined
        in TAG_REGEX below. Same rules apply on create + update.
- D-17  EmergencyContact is a Pydantic model (JSONB shape on the wire).

No ORM imports cross this boundary except `Gender` (a pure StrEnum, not an ORM class).
"""

import re
from datetime import UTC, date, datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import EmailStr, Field, ValidationInfo, field_validator, model_validator

from app.core.pagination import PageQuery
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


class ClientSort(StrEnum):
    """Client list sort modes (CLIENTS-04)."""

    CREATED_AT_DESC = "created_at_desc"  # default — newest first
    LAST_NAME_ASC = "last_name_asc"


# ---------------------------------------------------------------------------
# Tag validator — shared between ClientCreateRequest and ClientUpdateRequest
# ---------------------------------------------------------------------------


def _validate_tags(v: list[str]) -> list[str]:
    """D-16: lowercase + dedupe-rule-free normalisation.

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
# ClientUpdateRequest (CLIENTS-07, D-01, D-16)
# ---------------------------------------------------------------------------


class ClientUpdateRequest(RequestContract):
    """PATCH /api/v1/clients/{id} body.

    Semantics: caller sends only the fields they want to change; service does
    `model_dump(exclude_unset=True)` and applies that subset. D-01 forbids explicit
    null in v1.1 — to leave a field unchanged, OMIT the key entirely.
    """

    last_name: str | None = Field(default=None, min_length=1, max_length=128)
    first_name: str | None = Field(default=None, min_length=1, max_length=128)
    middle_name: str | None = Field(default=None, max_length=128)
    phone: str | None = Field(default=None, pattern=PHONE_REGEX)
    email: EmailStr | None = None
    birthday: date | None = None
    gender: Gender | None = None
    tags: list[str] | None = None
    notes: str | None = Field(default=None, max_length=4096)
    emergency_contact: EmergencyContact | None = None
    telegram_user_id: int | None = None

    @model_validator(mode="before")
    @classmethod
    def _reject_explicit_null(cls, data: Any) -> Any:
        """D-01: explicit `{"key": null}` is rejected. Caller must omit the key."""
        if isinstance(data, dict):
            null_keys = [k for k, v in data.items() if v is None]
            if null_keys:
                raise ValueError(
                    f"Explicit null not supported for: {sorted(null_keys)}. "
                    "Omit the key to leave the field unchanged."
                )
        return data

    @field_validator("tags")
    @classmethod
    def _normalise_tags(cls, v: list[str] | None) -> list[str] | None:
        """D-16: same rules as create. None bypasses validation (PATCH-absent)."""
        if v is None:
            return v
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


# ---------------------------------------------------------------------------
# ClientListQuery (CLIENTS-04, D-12, D-14)
# ---------------------------------------------------------------------------


class ClientListQuery(PageQuery):
    """GET /api/v1/clients query params.

    Inherits page + page_size from PageQuery (1-based pagination).
    Wire mapping: created_from→createdFrom, created_to→createdTo, has_telegram→hasTelegram
    (alias_generator=to_camel inherited via PageQuery → RequestContract → ContractModel).
    """

    q: str | None = Field(default=None, max_length=128)
    tag: str | None = Field(default=None, max_length=MAX_TAG_LENGTH)
    gender: Gender | None = None
    created_from: datetime | None = None
    created_to: datetime | None = None
    has_telegram: bool | None = None
    sort: ClientSort = ClientSort.CREATED_AT_DESC

    @field_validator("created_from", "created_to", mode="before")
    @classmethod
    def _normalise_date_boundary(cls, v: Any, info: ValidationInfo) -> Any:
        """D-14: date-only inputs normalised to UTC boundaries.

        - created_from on date-only → 00:00:00.000000 UTC (start of day)
        - created_to on date-only   → 23:59:59.999999 UTC (end of day, inclusive)
        - datetime inputs pass through unchanged.
        """
        if v is None:
            return v
        # String input: detect "YYYY-MM-DD" without time component.
        if isinstance(v, str) and len(v) == 10 and v.count("-") == 2:
            try:
                parsed = datetime.strptime(v, "%Y-%m-%d").replace(tzinfo=UTC)
            except ValueError:
                return v  # let pydantic surface the parse error with its own message
            if info.field_name == "created_to":
                return parsed.replace(hour=23, minute=59, second=59, microsecond=999999)
            return parsed
        # date instance (NOT datetime — datetime is a subclass of date).
        if isinstance(v, date) and not isinstance(v, datetime):
            base = datetime(v.year, v.month, v.day, tzinfo=UTC)
            if info.field_name == "created_to":
                return base.replace(hour=23, minute=59, second=59, microsecond=999999)
            return base
        return v

    @field_validator("q")
    @classmethod
    def _normalise_q(cls, v: str | None) -> str | None:
        """D-12: q < 2 chars after strip → None (service skips ILIKE filter)."""
        if v is None:
            return None
        stripped = v.strip()
        if len(stripped) < 2:
            return None
        return stripped
