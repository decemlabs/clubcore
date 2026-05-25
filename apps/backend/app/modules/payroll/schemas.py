"""Payroll module DTOs (Phase 58 PAY-01..06 / D-58-10..14).

TrainerCompConfigRequest — body for PUT /payroll/trainer-configs/{trainer_id} (PAY-01).
TrainerCompConfigResponse — outbound shape for comp config endpoints (PAY-01).
PayrollPreviewResponse — outbound shape for GET /payroll/preview (PAY-02 / D-58-12).
PayrollAccrualCreate — body for POST /payroll/accruals (PAY-03 / D-58-13).
PayrollAccrualResponse — outbound shape for accrual endpoints (PAY-03..05 / D-58-13..14).

All amount fields are ``int`` (kopecks). NO Decimal/float at the wire boundary.
BackendSchemaBase provides camelCase wire aliases via to_camel alias generator.
DO NOT import from app.modules.* (modules-independent contract).
"""

from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from pydantic import Field, model_validator

from app.core.schemas import BackendSchemaBase


class TrainerCompConfigRequest(BackendSchemaBase):
    """PUT /payroll/trainer-configs/{trainer_id} request body (PAY-01 / D-58-10).

    T-58-13: bps ge=0/le=10000 mirrors DB CHECK
    ck_trainer_comp_configs_commission_pct_bps_range.
    T-58-14: kopecks ge=0 mirrors DB CHECK
    ck_trainer_comp_configs_session_fee_kopecks_nonneg.
    Both NULL is allowed at write time; service validates both-NULL at accrual run time
    (D-58-09).
    """

    commission_pct_bps: int | None = Field(default=None, ge=0, le=10000)
    session_fee_kopecks: int | None = Field(default=None, ge=0)
    effective_from: date


class TrainerCompConfigResponse(BackendSchemaBase):
    """Outbound representation of a TrainerCompConfig row (PAY-01 / D-58-11).

    T-58-15: Snapshot field exposure is accepted (owner-only RBAC gates the response).
    """

    id: UUID
    trainer_id: UUID
    commission_pct_bps: int | None
    session_fee_kopecks: int | None
    effective_from: date
    created_at: datetime


class PayrollPreviewResponse(BackendSchemaBase):
    """GET /payroll/preview response body (PAY-02 / D-58-12).

    Preview amounts are non-negative (no clawback in preview; that is a separate accrual).
    All amounts in integer kopecks.
    """

    session_count: int = Field(ge=0)
    fixed_kopecks: int = Field(ge=0)
    commission_kopecks: int = Field(ge=0)
    total_kopecks: int = Field(ge=0)


class PayrollAccrualCreate(BackendSchemaBase):
    """POST /payroll/accruals request body (PAY-03 / D-58-13).

    period_start <= period_end is enforced by model_validator to produce a 422
    with a descriptive message at the endpoint layer, before the service is called.
    """

    trainer_id: UUID
    period_start: date
    period_end: date

    @model_validator(mode="after")
    def validate_period_order(self) -> PayrollAccrualCreate:
        """Enforce period_start <= period_end (D-58-05)."""
        if self.period_start > self.period_end:
            raise ValueError(
                "period_start must be <= period_end "
                f"(got period_start={self.period_start}, period_end={self.period_end})"
            )
        return self


class PayrollAccrualResponse(BackendSchemaBase):
    """Outbound representation of a TrainerPayrollAccrual row (PAY-03..05 / D-58-13..14).

    accrual_kopecks is signed (positive for regular accruals; negative for clawback rows).
    All temporal columns are UTC-aware datetimes.
    """

    id: UUID
    trainer_id: UUID
    period_start: date
    period_end: date
    sessions_count: int
    revenue_kopecks: int
    commission_pct_bps_snapshot: int | None
    session_fee_kopecks_snapshot: int | None
    comp_config_id_snapshot: UUID
    accrual_kopecks: int  # signed; negative for clawback rows (D-58-03)
    status: str  # 'pending' | 'paid' (single-transition lifecycle, D-58-08)
    accrued_at: datetime
    paid_at: datetime | None
    paid_by_user_id: UUID | None
    clawback_of_accrual_id: UUID | None
    source_refund_payment_id: UUID | None
