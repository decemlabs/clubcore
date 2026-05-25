"""Payroll router — owner-only endpoints under /api/v1/payroll/ (Phase 58 PAY-01..06).

Endpoint surface (Plans 58-05..08):
  Plan 58-05 (PAY-01):
    PUT  /trainer-configs/{trainer_id}  — Set/replace comp config (INSERT-only versioned)
    GET  /trainer-configs/{trainer_id}  — Get active comp config (latest effective_from <= today)

Later plans append:
  Plan 58-06 (PAY-02): GET /preview
  Plan 58-07 (PAY-03): POST /accruals
  Plan 58-08 (PAY-04): POST /accruals/{id}/mark-paid
  Plan 58-09 (PAY-05): GET /accruals

Permission mapping:
  PUT  trainer-configs: (CREATE, COMPENSATION) ∈ OWNER_ONLY (pre-registered Plan 58-01)
  GET  trainer-configs: (VIEW,   COMPENSATION) ∈ OWNER_ONLY (pre-registered Phase A)
  Reception receives 403 on both (T-58-17 mitigation).

Router is NOT mounted here — Plan 58-10 (or the last plan in the wave) adds
  `v1.include_router(router, prefix="/payroll", tags=["payroll"])` to
  apps/backend/app/api/v1/router.py. Test infrastructure mounts it locally.
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import CurrentUser, require_permission
from app.core.permissions import Action, Resource
from app.core.schemas import ResponseEnvelope, envelope
from app.modules.payroll import service
from app.modules.payroll.schemas import TrainerCompConfigRequest, TrainerCompConfigResponse

router = APIRouter()


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
