"""Trainers module Pydantic DTOs (Phase 31 — TRN-01).

All DTOs inherit the ContractModel chain (BackendSchemaBase / ResponseData / PageQuery)
so wire format is camelCase via `alias_generator=to_camel` while Python stays snake_case.

Decisions enforced here at the DTO boundary:
- D-31-05 E.164 phone validation `^\\+[1-9]\\d{1,14}$` reused from clients module.
- PATCH semantics: omit key to leave unchanged (D-01).
- is_active accepted on PATCH for deactivate/reactivate (D-31-11).
"""

from datetime import datetime
from uuid import UUID

from pydantic import Field

from app.core.pagination import PageQuery
from app.core.schemas import BackendSchemaBase, ResponseData

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

PHONE_REGEX = r"^\+[1-9]\d{1,14}$"  # E.164 (D-10 reuse per D-31-05)


# ---------------------------------------------------------------------------
# TrainerCreateRequest (TRN-01, D-31-02, D-31-05)
# ---------------------------------------------------------------------------


class TrainerCreateRequest(BackendSchemaBase):
    """POST /api/v1/trainers body. Required: fullName. Phone optional."""

    full_name: str = Field(min_length=1, max_length=200)
    phone: str | None = Field(default=None, pattern=PHONE_REGEX)


# ---------------------------------------------------------------------------
# TrainerUpdateRequest (TRN-03, D-01, D-31-11)
# ---------------------------------------------------------------------------


class TrainerUpdateRequest(BackendSchemaBase):
    """PATCH /api/v1/trainers/{id} body.

    PATCH semantics: omit key to leave unchanged (D-01).
    is_active accepted on PATCH for deactivate/reactivate (D-31-11).
    """

    full_name: str | None = Field(default=None, min_length=1, max_length=200)
    phone: str | None = Field(default=None, pattern=PHONE_REGEX)
    is_active: bool | None = None


# ---------------------------------------------------------------------------
# TrainerResponse — read-side DTO
# ---------------------------------------------------------------------------


class TrainerResponse(ResponseData):
    """Single trainer read DTO. `from_attributes=True` inherited via ContractModel."""

    id: UUID
    full_name: str
    phone: str | None = None
    is_active: bool
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# TrainerListQuery (TRN-04, D-31-09, D-31-10)
# ---------------------------------------------------------------------------


class TrainerListQuery(PageQuery):
    """GET /api/v1/trainers query params.

    active=true → WHERE is_active = true AND deleted_at IS NULL
    active=false → WHERE is_active = false AND deleted_at IS NULL
    omit → both (D-31-09)
    """

    active: bool | None = None
