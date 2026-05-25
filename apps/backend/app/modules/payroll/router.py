"""Payroll router — owner-only endpoints under /api/v1/payroll/ (Phase 58 PAY-01..06).

Endpoint surface (Plans 58-05..08):
  Plan 58-05 (PAY-01):
    PUT  /trainer-configs/{trainer_id}  — Set/replace comp config (INSERT-only versioned)
    GET  /trainer-configs/{trainer_id}  — Get active comp config (latest effective_from <= today)
  Plan 58-06 (PAY-02):
    GET  /preview                       — Read-only payroll preview (zero-persistence)

Later plans append:
  Plan 58-07 (PAY-03): POST /accruals
  Plan 58-08 (PAY-04): POST /accruals/{id}/mark-paid
  Plan 58-09 (PAY-05): GET /accruals

Permission mapping:
  PUT  trainer-configs: (CREATE, COMPENSATION) ∈ OWNER_ONLY (pre-registered Plan 58-01)
  GET  trainer-configs: (VIEW,   COMPENSATION) ∈ OWNER_ONLY (pre-registered Phase A)
  GET  /preview:        (LIST, PAYROLL)         ∈ OWNER_ONLY (pre-registered Plan 58-01)
  Reception receives 403 on all three (T-58-17 / T-58-22 mitigation).

CompConfigMissingError routing:
  GET /trainer-configs/{trainer_id} → 404 (GET path keeps its NotFoundError mapping).
  GET /preview                      → router-layer remap to 422 ValidationAppError
    (D-58-07 / D-58-09 preview/accrual paths require 422 comp_config_missing).

Router is NOT mounted here — Plan 58-10 (or the last plan in the wave) adds
  `v1.include_router(router, prefix="/payroll", tags=["payroll"])` to
  apps/backend/app/api/v1/router.py. Test infrastructure mounts it locally.
"""

from __future__ import annotations

from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import CurrentUser, require_permission
from app.core.exceptions import ValidationAppError
from app.core.permissions import Action, Resource
from app.core.schemas import ResponseEnvelope, envelope
from app.modules.payroll import service
from app.modules.payroll.schemas import (
    PayrollPreviewResponse,
    TrainerCompConfigRequest,
    TrainerCompConfigResponse,
)
from app.modules.payroll.service import CompConfigMissingError

router = APIRouter()


class _CompConfigMissing422Error(ValidationAppError):
    """Router-level 422 variant of CompConfigMissingError (D-58-07 / D-58-09).

    ``CompConfigMissingError`` (404) is re-raised as this class inside the preview
    and accrual endpoints so the AppError handler emits HTTP 422 with the same
    ``comp_config_missing`` code.  This is the router-remap approach (one service-level
    error class; only the router decides the HTTP status).  The GET comp-config path
    keeps its 404 (CompConfigMissingError propagates unchanged there).
    """

    code = "comp_config_missing"  # same code, 422 status (inherited from ValidationAppError)


@router.put(
    "/trainer-configs/{trainer_id}",
    response_model=ResponseEnvelope[TrainerCompConfigResponse],
    summary="Set/replace trainer comp config (INSERT-only versioned; owner-only PAY-01 / D-58-10)",
)
async def set_trainer_comp_config(
    trainer_id: UUID,
    body: TrainerCompConfigRequest,
    actor: Annotated[
        CurrentUser, Depends(require_permission(Action.CREATE, Resource.COMPENSATION))
    ],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ResponseEnvelope[TrainerCompConfigResponse]:
    """INSERT a new versioned compensation config for the given trainer (PAY-01 / D-58-02).

    Every PUT inserts a NEW row — prior config rows are never modified.  The
    response body contains the newly created config row with its assigned ``id``.
    Owner-only: ``(CREATE, COMPENSATION) ∈ OWNER_ONLY`` (Plan 58-01 pre-registration).
    Reception receives 403 (T-58-17 mitigate).
    """
    config = await service.set_comp_config(session, actor, trainer_id, body)
    return envelope(TrainerCompConfigResponse.model_validate(config, from_attributes=True))


@router.get(
    "/trainer-configs/{trainer_id}",
    response_model=ResponseEnvelope[TrainerCompConfigResponse],
    summary=(
        "Get the active comp config (latest effective_from <= today; owner-only PAY-01 / D-58-11)"
    ),
)
async def get_trainer_comp_config(
    trainer_id: UUID,
    actor: Annotated[
        CurrentUser, Depends(require_permission(Action.VIEW, Resource.COMPENSATION))
    ],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ResponseEnvelope[TrainerCompConfigResponse]:
    """Resolve and return the active compensation config for the given trainer (PAY-01 / D-58-11).

    "Active" means the row with the latest ``effective_from`` that is <= today (MSK).
    Returns 404 ``comp_config_missing`` when no config exists for the trainer.
    Owner-only: ``(VIEW, COMPENSATION) ∈ OWNER_ONLY`` (pre-registered Phase A).
    Reception receives 403 (T-58-17 mitigate).
    ``CompConfigMissingError`` propagates to the centralised AppError handler → 404.
    """
    config = await service.get_active_comp_config(session, trainer_id)
    return envelope(TrainerCompConfigResponse.model_validate(config, from_attributes=True))


@router.get(
    "/preview",
    response_model=ResponseEnvelope[PayrollPreviewResponse],
    summary=(
        "Preview payroll accrual for a trainer + period (read-only, zero-persistence;"
        " owner-only PAY-02 / D-58-12)"
    ),
)
async def preview_payroll(
    actor: Annotated[
        CurrentUser, Depends(require_permission(Action.LIST, Resource.PAYROLL))
    ],
    session: Annotated[AsyncSession, Depends(get_db)],
    trainer_id: Annotated[UUID, Query(alias="trainerId")],
    period_start: Annotated[date, Query(alias="periodStart")],
    period_end: Annotated[date, Query(alias="periodEnd")],
) -> ResponseEnvelope[PayrollPreviewResponse]:
    """Return session_count, fixed_kopecks, commission_kopecks, total_kopecks for a period.

    Read-only — ZERO rows persisted, ZERO audit events emitted (D-58-12).
    Shares compute logic with PAY-03 via ``service.compute_accrual_components`` to
    prevent recompute drift between preview and persisted accrual (PITFALL 1 / T-58-23).

    Owner-only: ``(LIST, PAYROLL) ∈ OWNER_ONLY`` (pre-registered Plan 58-01).
    Reception receives 403 (T-58-22 mitigate).

    Router-layer 422 remap for CompConfigMissingError (D-58-07 / D-58-09):
      ``CompConfigMissingError`` from the service is caught HERE and re-raised as a
      ``ValidationAppError`` with the same ``comp_config_missing`` code and 422 status.
      This is the router-remap approach (one error class; PAY-01 GET path keeps 404).
    """
    try:
        result = await service.preview_accrual(session, trainer_id, period_start, period_end)
    except CompConfigMissingError as exc:
        # Router-layer remap: preview path needs 422, not 404 (D-58-07 / D-58-09).
        # _CompConfigMissing422Error keeps the same "comp_config_missing" code at HTTP 422.
        raise _CompConfigMissing422Error(exc.message) from exc
    return envelope(result)
