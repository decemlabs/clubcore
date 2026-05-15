"""MembershipPlan + Membership request/response DTOs.

Phase 16 — MembershipPlan DTOs (MEM-PLAN-EP-01..03).
Phase 17 — Membership DTOs + enums (MEM-EP-01..04).

Inputs inherit from BackendSchemaBase (camelCase wire <-> snake_case Python,
extra='forbid'). Responses inherit from ResponseData.

Decision references — Phase 16 (16-CONTEXT.md):
- D-01: trim-only name normalization, preserve casing
- D-04: PATCH does NOT declare duration_days -> stock 422 from extra='forbid'
- D-05: explicit null in PATCH body is rejected with a clear message
- D-06: Pydantic bounds atop DB CHECKs (defence-in-depth)
- D-07: PATCH-able fields are name, price_kopecks, active only
- D-08: list query supports active filter + sort enum, page/page_size from PageQuery
- D-09: NO `q` (name search) in Phase 16
- CD-04: MembershipPlanSort lives module-local (mirror of ClientSort)

Decision references — Phase 17 (17-CONTEXT.md):
- D-03: POST /memberships body = {clientId, planId, paidAt?, notes?}
- D-09: list query — clientId optional, status optional, sort enum default CREATED_AT_DESC
- D-10: response exposes ALL snapshot fields + lifecycle timestamps
- D-11: cancel body = {reason?: str | None, max_length=500}, explicit-null guard
"""

from __future__ import annotations

from datetime import date, datetime
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
    freeze_days_limit: int = Field(ge=1, le=365)  # Phase 25 D-25-10 — explicit, no default
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
    freeze_days_limit: int  # Phase 25 D-25-10
    active: bool
    created_at: datetime
    updated_at: datetime
    # deleted_at intentionally omitted — soft-deleted rows are 404'd at the
    # repository boundary and never serialised.


# --- Phase 25: Freeze period response (D-25-12) ---------------------------


class FreezePeriodResponse(ResponseData):
    """Outbound representation of a MembershipFreezePeriod (Phase 25 D-25-12).

    Used as the value of MembershipResponse.current_freeze_period. When surfaced
    that way, ended_at and ended_by are always None (open period definition).
    """

    id: UUID
    started_at: datetime
    started_by: UUID
    ended_at: datetime | None
    ended_by: UUID | None


# --- List query ------------------------------------------------------------


class MembershipPlanListQuery(PageQuery):
    """GET /api/v1/membership-plans query parameters (D-08)."""

    active: bool | None = None  # omit = include both active and inactive
    sort: MembershipPlanSort = MembershipPlanSort.CREATED_AT_DESC
    # NO `q` — D-09 (catalog <=20 rows, search not justified in Phase 16)


# ===========================================================================
# Phase 17 — Membership instance DTOs (MEM-EP-01..04, 17-CONTEXT.md D-03/D-09/D-10/D-11)
# ===========================================================================


# --- Status + sort enums ---------------------------------------------------


class MembershipStatus(StrEnum):
    """Membership lifecycle status (CONTEXT.md domain line 12)."""

    ACTIVE = "active"
    EXPIRED = "expired"
    CANCELLED = "cancelled"
    FROZEN = "frozen"  # Phase 25 D-25-13


class MembershipListSort(StrEnum):
    """Membership list sort modes (Phase 17 D-09)."""

    CREATED_AT_DESC = "created_at_desc"  # default — newest first
    END_DATE_DESC = "end_date_desc"
    START_DATE_DESC = "start_date_desc"


# --- Create request --------------------------------------------------------


class MembershipCreateRequest(BackendSchemaBase):
    """POST /api/v1/memberships body (Phase 17 D-03).

    start_date / end_date / status / activation_policy are server-computed
    (D-04) and intentionally absent — the inherited extra='forbid' will reject
    any payload that includes them.
    """

    client_id: UUID
    plan_id: UUID
    # D-03: omit -> NULL. Owner may back-date cash receipts by passing an
    # explicit ISO timestamp.
    paid_at: datetime | None = None
    # D-03: free-text operator note, capped at 1000 chars (T-17-02 mitigation).
    notes: str | None = Field(default=None, max_length=1000)


# --- Cancel request --------------------------------------------------------


class MembershipCancelRequest(BackendSchemaBase):
    """POST /api/v1/memberships/{id}/cancel body (Phase 17 D-11).

    Reason is optional (matches MEM-AUDIT-01 — `reason?` in audit payload).
    Max length 500 — half the notes ceiling: a cancellation reason is a short
    operator note, not a free-form essay (T-17-01 mitigation).

    Explicit-null guard ported VERBATIM from Phase 16 D-05 (T-PYDANTIC-NULL).
    """

    reason: str | None = Field(default=None, max_length=500)

    @model_validator(mode="before")
    @classmethod
    def _reject_explicit_null(cls, data: Any) -> Any:
        # D-11: explicit null is rejected; omit the key to leave the field unset.
        if isinstance(data, dict):
            null_keys = [k for k, v in data.items() if v is None]
            if null_keys:
                raise ValueError(
                    f"Explicit null not supported for: {sorted(null_keys)}. "
                    "Omit the key to leave the field unchanged."
                )
        return data


# --- Response --------------------------------------------------------------


class MembershipResponse(ResponseData):
    """Outbound representation of a Membership (Phase 17 D-10).

    Exposes ALL snapshot fields so the frontend (Phase 22) can render
    historical sales correctly even after the source plan is edited or
    deleted.
    """

    id: UUID
    client_id: UUID
    plan_id: UUID
    plan_name_snapshot: str
    duration_days_snapshot: int
    price_kopecks_snapshot: int
    start_date: date
    end_date: date
    status: MembershipStatus
    cancelled_at: datetime | None
    cancel_reason: str | None
    cancellation_reason: str | None = None  # Phase 32 REF-01
    paid_at: datetime | None
    notes: str | None
    created_at: datetime
    updated_at: datetime
    # Phase 25 MEM-FRZ-EP-03 — freeze projection fields (D-25-12):
    freeze_days_limit_snapshot: int
    freeze_days_used: int
    freeze_days_remaining: int  # computed = limit - used, clamped to 0
    current_freeze_period: FreezePeriodResponse | None  # None when status != frozen
    # Phase 26 MEM-REN-01 — chain attribution (auto-camelCased to previousMembershipId).
    previous_membership_id: UUID | None = None


# --- List query ------------------------------------------------------------


class MembershipListQuery(PageQuery):
    """GET /api/v1/memberships query parameters (Phase 17 D-09; Phase 24 DEBT-02).

    clientId — optional. Owner can call without it for a global feed.
    status   — single-value enum filter; omit -> all 3 statuses.
    sort     — single sort axis, default CREATED_AT_DESC.
    expiring — Phase 24 DEBT-02: filter to active memberships whose `end_date`
               falls in `[today_msk, today_msk + (within - 1)]` (inclusive on
               both ends per PROJECT.md "Key Decisions" + D-24-12). Default
               False — current behaviour unchanged.
    within   — Phase 24 DEBT-02: window size in days, 1..30 (Pydantic-bounded;
               out-of-range -> 422). Default 7 matches the legacy FE-08 D-2
               window. Silently ignored when `expiring=False`.

    Conflict semantics (D-24-11): `expiring=True` forces `status='active'`. If
    the caller explicitly passes `status` as anything other than `active`, the
    repository raises `ValidationAppError("query_invalid",
    fields={"status": "incompatible_with_expiring"})` -> 422 (no silent
    override). The schema stays flat (no model_validator) — the conflict
    needs the resolved enum and is decided at the repository layer.

    NO `q` text search, NO date-range from/to in Phase 17 (D-09).
    """

    client_id: UUID | None = None
    status: MembershipStatus | None = None
    sort: MembershipListSort = MembershipListSort.CREATED_AT_DESC
    # Phase 24 DEBT-02 — defence-in-depth defaults.
    expiring: bool = False
    within: int = Field(default=7, ge=1, le=30)
