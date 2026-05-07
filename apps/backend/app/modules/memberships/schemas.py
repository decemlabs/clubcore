"""MembershipPlan request/response DTOs (Phase 16, MEM-PLAN-EP-01..03).

Inputs inherit from BackendSchemaBase (camelCase wire <-> snake_case Python,
extra='forbid'). Responses inherit from ResponseData.

Decision references (16-CONTEXT.md):
- D-01: trim-only name normalization, preserve casing
- D-04: PATCH does NOT declare duration_days -> stock 422 from extra='forbid'
- D-05: explicit null in PATCH body is rejected with a clear message
- D-06: Pydantic bounds atop DB CHECKs (defence-in-depth)
- D-07: PATCH-able fields are name, price_kopecks, active only
- D-08: list query supports active filter + sort enum, page/page_size from PageQuery
- D-09: NO `q` (name search) in Phase 16
- CD-04: MembershipPlanSort lives module-local (mirror of ClientSort)
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from app.core.pagination import PageQuery
from app.core.schemas import BackendSchemaBase, ResponseData

# --- Sort enum -------------------------------------------------------------


class MembershipPlanSort(StrEnum):
    """Membership plan list sort modes (D-08, CD-04)."""

    CREATED_AT_DESC = "created_at_desc"  # default — newest first
    NAME_ASC = "name_asc"


# --- Create request --------------------------------------------------------


class MembershipPlanCreateRequest(BackendSchemaBase):
    """POST /api/v1/membership-plans body."""

    name: str = Field(min_length=1, max_length=120)
    duration_days: int = Field(ge=1, le=3650)  # D-06
    price_kopecks: int = Field(ge=0, le=10**11)  # D-06
    active: bool = Field(default=True)  # D-06

    @field_validator("name", mode="before")
    @classmethod
    def _trim(cls, v: object) -> object:
        # D-01: trim only, preserve casing. min_length=1 enforced after trim.
        return v.strip() if isinstance(v, str) else v


# --- Update request --------------------------------------------------------


class MembershipPlanUpdateRequest(BackendSchemaBase):
    """PATCH /api/v1/membership-plans/{id} body.

    D-04: duration_days is intentionally absent — extra='forbid' (inherited
    from BackendSchemaBase) raises stock 422 if a payload contains
    `durationDays` (or `duration_days`). The rejected key is named in the
    Pydantic error response.
    """

    # D-07: only these three fields are PATCH-able
    name: str | None = Field(default=None, min_length=1, max_length=120)
    price_kopecks: int | None = Field(default=None, ge=0, le=10**11)
    active: bool | None = Field(default=None)

    @model_validator(mode="before")
    @classmethod
    def _reject_explicit_null(cls, data: Any) -> Any:
        # D-05: explicit null is rejected; omit the key to leave field unchanged.
        if isinstance(data, dict):
            null_keys = [k for k, v in data.items() if v is None]
            if null_keys:
                raise ValueError(
                    f"Explicit null not supported for: {sorted(null_keys)}. "
                    "Omit the key to leave the field unchanged."
                )
        return data

    @field_validator("name", mode="before")
    @classmethod
    def _trim(cls, v: object) -> object:
        # D-01: trim only on PATCH name as well.
        return v.strip() if isinstance(v, str) else v


# --- Response --------------------------------------------------------------


class MembershipPlanResponse(ResponseData):
    """Outbound representation of a MembershipPlan."""

    id: UUID
    name: str
    duration_days: int
    price_kopecks: int
    active: bool
    created_at: datetime
    updated_at: datetime
    # deleted_at intentionally omitted — soft-deleted rows are 404'd at the
    # repository boundary and never serialised.


# --- List query ------------------------------------------------------------


class MembershipPlanListQuery(PageQuery):
    """GET /api/v1/membership-plans query parameters (D-08)."""

    active: bool | None = None  # omit = include both active and inactive
    sort: MembershipPlanSort = MembershipPlanSort.CREATED_AT_DESC
    # NO `q` — D-09 (catalog <=20 rows, search not justified in Phase 16)
