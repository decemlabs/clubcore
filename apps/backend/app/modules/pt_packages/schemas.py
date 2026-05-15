"""PtPackagePlan + PtPackage request/response DTOs (Phase 33).

Inputs inherit BackendSchemaBase (camelCase wire ↔ snake_case Python,
extra='forbid'). Responses inherit ResponseData.

Decision references — Phase 33 (33-CONTEXT.md / 33-PATTERNS.md):
- D-33-02: plan CHECK bounds atop DB constraints (defence-in-depth).
- D-33-07: PATCH plan request INCLUDES immutable fields
  (session_count / price_kopecks / validity_days) so the service layer
  can return 409 ``field_immutable`` instead of stock 422. Mutating any
  of these via service.update_pt_package_plan raises FieldImmutableError.
- D-33-09: POST /pt-packages request shape — {clientId, planId,
  amountKopecks}; snapshot symmetry enforced server-side (Plan 33-02).
- D-33-10: POST /pt-packages/{id}/cancel request — {reason: 1..200 chars,
  REQUIRED} (admin-cancel-without-refund).
- D-33-11: POST /pt-packages/{id}/refund request — {reason: 1..200,
  REQUIRED}; ``amountKopecks`` is REJECTED with 422 via extra='forbid'.
- D-33-15: PtPackageStatus enum mirrors migration CHECK values.

Instance request schemas (Create/Cancel/Refund) and query schema are
defined here for sibling Plans 33-02 + 33-03 to consume without further
schemas.py edits in Wave 2.
"""

from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import Field, computed_field, field_validator, model_validator

from app.core.pagination import PageQuery
from app.core.schemas import BackendSchemaBase, ResponseData

# ---------------------------------------------------------------------------
# Status enum — mirrors pt_packages.status CHECK constraint values (D-33-15).
# ---------------------------------------------------------------------------


class PtPackageStatus(StrEnum):
    """PT-package lifecycle status (33-CONTEXT.md domain).

    Values byte-stable with migration 0014_pt_packages CHECK ck_pt_packages_status.
    """

    ACTIVE = "active"
    EXHAUSTED = "exhausted"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


# ---------------------------------------------------------------------------
# Plan sort enum
# ---------------------------------------------------------------------------


class PtPackagePlanSort(StrEnum):
    """PT-package plan list sort modes (mirror MembershipPlanSort)."""

    CREATED_AT_DESC = "created_at_desc"  # default — newest first
    NAME_ASC = "name_asc"


# ---------------------------------------------------------------------------
# Plan: Create / Update / Response / List query (PT-01, PT-02)
# ---------------------------------------------------------------------------


class PtPackagePlanCreateRequest(BackendSchemaBase):
    """POST /api/v1/pt-package-plans body (D-33-02)."""

    name: str = Field(min_length=1, max_length=120)
    session_count: int = Field(ge=1, le=1000)
    price_kopecks: int = Field(ge=1, le=10**11)
    validity_days: int | None = Field(default=None, ge=1, le=3650)

    @field_validator("name", mode="before")
    @classmethod
    def _trim(cls, v: object) -> object:
        return v.strip() if isinstance(v, str) else v


class PtPackagePlanUpdateRequest(BackendSchemaBase):
    """PATCH /api/v1/pt-package-plans/{id} body (D-33-07).

    Immutable fields (session_count / price_kopecks / validity_days) are
    INCLUDED as Optional[int] so the service layer can return 409
    ``field_immutable`` on a non-matching value (instead of stock 422 from
    extra='forbid' which would happen if we omitted them). Mutable fields
    are: name only.
    """

    name: str | None = Field(default=None, min_length=1, max_length=120)
    # Included so service can compare and reject — NOT for actual mutation.
    session_count: int | None = Field(default=None, ge=1, le=1000)
    price_kopecks: int | None = Field(default=None, ge=1, le=10**11)
    validity_days: int | None = Field(default=None, ge=1, le=3650)

    @model_validator(mode="before")
    @classmethod
    def _reject_explicit_null(cls, data: Any) -> Any:
        # Phase 16 D-05 mirror: explicit null is rejected; omit the key to leave
        # the field unchanged. Applies uniformly to name + the 3 immutable fields.
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
        return v.strip() if isinstance(v, str) else v


class PtPackagePlanResponse(ResponseData):
    """Outbound representation of a PtPackagePlan."""

    id: UUID
    name: str
    session_count: int
    price_kopecks: int
    validity_days: int | None
    created_at: datetime
    updated_at: datetime
    # deleted_at intentionally omitted — soft-deleted rows are 404'd at the
    # repository boundary and never serialised.


class PtPackagePlanListQuery(PageQuery):
    """GET /api/v1/pt-package-plans query parameters."""

    include_archived: bool = False
    sort: PtPackagePlanSort = PtPackagePlanSort.CREATED_AT_DESC


# ---------------------------------------------------------------------------
# Instance: Create / Cancel / Refund / Response / List query
# (Plans 33-02 + 33-03 will populate the service / router endpoints; schemas
# land here so siblings need not modify schemas.py.)
# ---------------------------------------------------------------------------


class PtPackageCreateRequest(BackendSchemaBase):
    """POST /api/v1/pt-packages body (D-33-09).

    ``amount_kopecks`` is REQUIRED; the service validates
    ``amount_kopecks == plan.price_kopecks`` server-side (snapshot symmetry,
    D-33-17). Disagreement → 422 ``amount_mismatch``.
    """

    client_id: UUID
    plan_id: UUID
    amount_kopecks: int = Field(ge=1, le=10**11)


class PtPackageCancelRequest(BackendSchemaBase):
    """POST /api/v1/pt-packages/{id}/cancel body (D-33-10).

    ``reason`` is REQUIRED — cancel-without-refund is a free-text operator
    note recording why the package was voided manually (distinct from refund,
    which sets the ``'refunded'`` sentinel automatically).
    """

    reason: str = Field(min_length=1, max_length=200)


class PtPackageRefundRequest(BackendSchemaBase):
    """POST /api/v1/pt-packages/{id}/refund body (D-33-11 / REF-05).

    Mirror ``MembershipRefundRequest``. ``reason`` is REQUIRED (1..200 chars).
    Backend rejects extra keys including ``amountKopecks`` via
    extra='forbid' (REF-05 server-derives-amount invariant).
    """

    reason: str = Field(min_length=1, max_length=200)


class PtPackageListSort(StrEnum):
    """PT-package instance list sort modes."""

    CREATED_AT_DESC = "created_at_desc"  # default — newest first
    END_DATE_DESC = "end_date_desc"
    START_DATE_DESC = "start_date_desc"


class PtPackageListQuery(PageQuery):
    """GET /api/v1/pt-packages query parameters."""

    client_id: UUID | None = None
    status: PtPackageStatus | None = None
    sort: PtPackageListSort = PtPackageListSort.CREATED_AT_DESC


class PtPackageResponse(ResponseData):
    """Outbound representation of a PtPackage instance (D-33-09).

    `is_active` is a computed field (D-33-10 sale-response contract): True
    iff `status == 'active'`. Convenience boolean for downstream consumers
    (admin-web badge, Phase 35 FE-10..18) — never persisted; derived from
    `status` on every response.
    """

    id: UUID
    client_id: UUID
    plan_id: UUID
    plan_name_snapshot: str
    session_count_snapshot: int
    price_kopecks_snapshot: int
    validity_days_snapshot: int | None
    sessions_remaining: int
    status: PtPackageStatus
    start_date: date
    end_date: date | None
    cancellation_reason: str | None
    created_at: datetime
    updated_at: datetime

    @computed_field  # type: ignore[prop-decorator]
    @property
    def is_active(self) -> bool:
        """True iff this PT-package is currently in the active state (D-33-10)."""
        return self.status == PtPackageStatus.ACTIVE
