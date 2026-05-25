"""Payroll service — orchestrator for comp-config + accrual lifecycle (Phase 58 PAY-01..06).

Each exported function owns the full unit-of-work for its operation:
  - ``set_comp_config`` — INSERT new versioned comp config + audit emit + commit (PAY-01).
  - ``get_active_comp_config`` — read-only resolver; raises 404 if no config exists (PAY-01).

Subsequent plans append ``preview_accrual`` (PAY-02), ``run_payroll_period`` (PAY-03),
``mark_accrual_paid`` (PAY-04), ``list_accruals`` (PAY-05), and
``record_clawback_for_pt_package_refund`` (PAY-06) to this module.

Commit discipline (SVC001):
  ``set_comp_config`` is the orchestrator for PAY-01 writes — it calls
  ``session.commit()``.  Repository helpers flush but do NOT commit.  Later
  plans follow the same pattern: each service function that mutates state
  owns the final ``session.commit()``.

Exception conventions:
  ``CompConfigMissingError`` — 404 on the GET read path (PAY-01 D-58-11).
  Plan 58-07 (PAY-03 run_payroll_period) will add a 422-mapped variant or
  reuse this class with a router-layer mapping; for now this is the GET form.
"""

from __future__ import annotations

from datetime import date
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy.ext.asyncio import AsyncSession

from app.core import audit
from app.core.dependencies import CurrentUser
from app.core.exceptions import NotFoundError
from app.modules.payroll import repository
from app.modules.payroll.models import TrainerCompConfig
from app.modules.payroll.schemas import TrainerCompConfigRequest

_MSK = ZoneInfo("Europe/Moscow")


class CompConfigMissingError(NotFoundError):
    """No active compensation config exists for the given trainer + date (PAY-01 D-58-11).

    GET /payroll/trainer-configs/{trainer_id} raises this when
    ``resolve_active_comp_config`` returns None → 404.

    Plan 58-07 (PAY-03): ``run_payroll_period`` needs a 422 variant of this
    error for the accrual path (D-58-07 / D-58-09). At that point either a
    new ``CompConfigMissingFor422Error(ValidationAppError)`` subclass will be
    added, or the router will remap the 404 to 422 for that endpoint.
    For now, ship the 404 form used by the PAY-01 GET path.
    """

    code = "comp_config_missing"
    status_code = 404


async def set_comp_config(
    session: AsyncSession,
    actor: CurrentUser,
    trainer_id: UUID,
    body: TrainerCompConfigRequest,
) -> TrainerCompConfig:
    """INSERT a new versioned comp config for *trainer_id* (PAY-01 / D-58-02 + D-58-17).

    Atomic unit-of-work (orchestrator owns commit) — mirror of D-33-11 sequence:
      1. ``repository.insert_comp_config`` — constructs ORM row + flushes (assigns id).
      2. ``audit.emit("trainer_comp_config_set", ...)`` — BEFORE commit (D-58-17).
      3. ``session.commit()`` — SVC001 gate; atomically commits config row + audit row.
      4. Return the committed config row.

    Existing config rows are NEVER modified. Every call inserts a NEW row with its
    own ``effective_from`` (D-58-02 INSERT-only versioned discipline).
    """
    config = await repository.insert_comp_config(
        session,
        trainer_id=trainer_id,
        commission_pct_bps=body.commission_pct_bps,
        session_fee_kopecks=body.session_fee_kopecks,
        effective_from=body.effective_from,
        created_by_user_id=actor.id,
    )

    # Audit emit BEFORE commit (D-58-17 atomic chain — flush already assigned config.id).
    # Literal strings "trainer_comp_config_set" and "trainer_comp_config" required by
    # INFRA-11 AST gate (tests/unit/test_audit_taxonomy.py).
    await audit.emit(
        session,
        "trainer_comp_config_set",
        actor_user_id=actor.id,
        resource_type="trainer_comp_config",
        resource_id=config.id,
        comp_config_id=str(config.id),
        trainer_id=str(trainer_id),
        commission_pct_bps=body.commission_pct_bps,
        session_fee_kopecks=body.session_fee_kopecks,
        effective_from=str(body.effective_from),
    )

    await session.commit()
    return config


async def get_active_comp_config(
    session: AsyncSession,
    trainer_id: UUID,
    as_of_date: date | None = None,
) -> TrainerCompConfig:
    """Return the active comp config for *trainer_id* as of *as_of_date* (PAY-01 D-58-11).

    If *as_of_date* is None, defaults to today in Europe/Moscow (project TZ discipline).
    Raises ``CompConfigMissingError`` (404) when no config exists.
    """
    from datetime import datetime

    resolved_date = as_of_date or datetime.now(_MSK).date()
    config = await repository.resolve_active_comp_config(session, trainer_id, resolved_date)
    if config is None:
        raise CompConfigMissingError("comp_config_missing")
    return config
