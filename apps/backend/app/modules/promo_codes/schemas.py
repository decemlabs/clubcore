"""Phase 113 promo_codes admin CRUD — request/response DTOs (PROMO-01/PROMO-02).

All request schemas inherit from BackendSchemaBase (camelCase wire, extra='forbid').
Response schemas inherit from ResponseData (from_attributes=True for ORM→DTO).

Discount value semantics (113-CONTEXT.md D-04):
  - discount_type='fixed'      → discount_value is integer kopecks
  - discount_type='percentage' → discount_value is percent*100 (basis points)
                                  e.g. 10% → 1000, 100% → 10000

Code is UPPER-normalized in the service layer before persistence.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import field_validator, model_validator

from app.core.pagination import PageQuery
from app.core.schemas import BackendSchemaBase, ResponseData

# Valid applicable_to values (must match model String(16) semantics + validate_promo_code)
_APPLICABLE_TO_VALUES = {"membership", "pt_package"}


class PromoCodeCreateRequest(BackendSchemaBase):
    """POST /api/v1/promo-codes body (PROMO-01)."""

    code: str
    discount_type: Literal["percentage", "fixed"]
    discount_value: int  # kopecks for fixed; percent*100 for percentage
    max_uses: int | None = None
    per_client_limit: int | None = None
    valid_from: datetime | None = None
    valid_until: datetime | None = None
    applicable_to: str | None = None
    description: str | None = None

    @field_validator("discount_value")
    @classmethod
    def validate_discount_value_positive(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("discount_value must be > 0")
        return v

    @field_validator("applicable_to")
    @classmethod
    def validate_applicable_to(cls, v: str | None) -> str | None:
        if v is not None and v not in _APPLICABLE_TO_VALUES:
            raise ValueError(f"applicable_to must be one of {sorted(_APPLICABLE_TO_VALUES)}")
        return v

    def model_post_init(self, __context: object) -> None:
        # percentage discount_value must be <= 10000 (100% * 100)
        if self.discount_type == "percentage" and self.discount_value > 10000:
            raise ValueError("discount_value for percentage must be <= 10000 (i.e. 100%)")

    @model_validator(mode="after")
    def validate_validity_window(self) -> PromoCodeCreateRequest:
        # WR-02: valid_until must not precede valid_from.
        if (
            self.valid_from is not None
            and self.valid_until is not None
            and self.valid_until < self.valid_from
        ):
            raise ValueError("valid_until must be >= valid_from")
        return self


class PromoCodeUpdateRequest(BackendSchemaBase):
    """PATCH /api/v1/promo-codes/{id} body — partial edit (PROMO-01).

    All fields optional; service applies only those provided (exclude_unset).
    """

    code: str | None = None
    discount_type: Literal["percentage", "fixed"] | None = None
    discount_value: int | None = None
    max_uses: int | None = None
    per_client_limit: int | None = None
    valid_from: datetime | None = None
    valid_until: datetime | None = None
    applicable_to: str | None = None
    description: str | None = None

    @field_validator("discount_value")
    @classmethod
    def validate_discount_value_positive(cls, v: int | None) -> int | None:
        if v is not None and v <= 0:
            raise ValueError("discount_value must be > 0")
        return v

    @field_validator("applicable_to")
    @classmethod
    def validate_applicable_to(cls, v: str | None) -> str | None:
        if v is not None and v not in _APPLICABLE_TO_VALUES:
            raise ValueError(f"applicable_to must be one of {sorted(_APPLICABLE_TO_VALUES)}")
        return v


class PromoCodeListQuery(PageQuery):
    """GET /api/v1/promo-codes query params (PROMO-02).

    active=None → return all (active + inactive).
    active=True / active=False → filter by is_active.
    """

    active: bool | None = None


class PromoCodeListItemResponse(ResponseData):
    """Item shape for GET /api/v1/promo-codes list — includes used_count aggregate."""

    id: UUID
    code: str
    discount_type: str
    discount_value: int
    max_uses: int | None
    per_client_limit: int | None
    valid_from: datetime | None
    valid_until: datetime | None
    is_active: bool
    applicable_to: str | None
    description: str | None
    used_count: int  # correlated COUNT from promo_redemptions
    created_at: datetime


class PromoCodeResponse(ResponseData):
    """Response shape for POST (create) and PATCH (edit) — full row."""

    id: UUID
    code: str
    discount_type: str
    discount_value: int
    max_uses: int | None
    per_client_limit: int | None
    valid_from: datetime | None
    valid_until: datetime | None
    is_active: bool
    applicable_to: str | None
    description: str | None
    created_at: datetime
