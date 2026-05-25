"""Payroll service — orchestrator for comp-config + accrual lifecycle (Phase 58 PAY-01..06).

Each exported function owns the full unit-of-work for its operation:
  - ``set_comp_config`` — INSERT new versioned comp config + audit emit + commit (PAY-01).
  - ``get_active_comp_config`` — read-only resolver; raises 404 if no config exists (PAY-01).
  - ``compute_accrual_components`` — pure computation helper (PAY-02 / PAY-03); ZERO writes.
  - ``preview_accrual`` — read-only preview endpoint handler (PAY-02 / D-58-12); ZERO writes.

Subsequent plans append ``run_payroll_period`` (PAY-03),
``mark_accrual_paid`` (PAY-04), ``list_accruals`` (PAY-05), and
``record_clawback_for_pt_package_refund`` (PAY-06) to this module.

Commit discipline (SVC001):
  ``set_comp_config`` is the orchestrator for PAY-01 writes — it calls
  ``session.commit()``.  Repository helpers flush but do NOT commit.  Later
  plans follow the same pattern: each service function that mutates state
  owns the final ``session.commit()``.
  ``compute_accrual_components`` and ``preview_accrual`` are read-only — they
  call ZERO session.commit() / session.add() / audit.emit().

Exception conventions:
  ``CompConfigMissingError`` — raised on two paths with different HTTP status codes:
    - GET /payroll/trainer-configs/{trainer_id}: router passes through → 404 (PAY-01 D-58-11).
    - GET /payroll/preview: router remaps to 422 at the endpoint layer (PAY-02 D-58-07).
      The same exception class is reused; the router decides the HTTP status code by
      catching CompConfigMissingError and raising HTTPException(422) before FastAPI's
      centralised AppError handler can emit 404. This keeps one error class (D-58-09).
"""

from __future__ import annotations

import math
from datetime import date
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy.ext.asyncio import AsyncSession

from app.core import audit
from app.core.dependencies import CurrentUser
from app.core.exceptions import NotFoundError
from app.modules.payroll import repository
from app.modules.payroll.models import TrainerCompConfig
from app.modules.payroll.schemas import PayrollPreviewResponse, TrainerCompConfigRequest

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


async def compute_accrual_components(
    session: AsyncSession,
    trainer_id: UUID,
    period_start: date,
    period_end: date,
) -> tuple[int, int, int, int, TrainerCompConfig]:
    """Compute payroll accrual components for a trainer + period (PAY-02 / PAY-03 / D-58-12).

    This is the SINGLE source of truth for commission + fixed computation reused by
    both preview_accrual (PAY-02) and run_payroll_period (PAY-03) — guaranteeing that
    preview and the persisted accrual produce identical numbers (PITFALL 1
    recompute-drift mitigation / T-58-23).

    Returns:
        (session_count, fixed_kopecks, commission_kopecks, total_kopecks, resolved_config)

    Algorithm:
      1. Resolve comp config as of period_end via repository.resolve_active_comp_config.
         If None OR both commission_pct_bps and session_fee_kopecks are NULL → raise
         CompConfigMissingError (D-58-07 / D-58-09). The router remaps this to 422 on
         the preview/accrual paths; the GET config path keeps its 404.
      2. Fetch (commission_revenue_kopecks, session_count) from
         repository.fetch_trainer_session_revenue for the given period.
      3. commission_kopecks = math.ceil(revenue_kopecks * bps / 10000) when bps is
         non-NULL else 0.  Integer-only: math.ceil on a Python int * int / int
         expression produces an exact rational result via Python's arbitrary-precision
         integers before division; no float intermediate (D-58-04 / T-58-25).
      4. fixed_kopecks = (session_fee_kopecks or 0) * session_count.
      5. total_kopecks = commission_kopecks + fixed_kopecks.

    ZERO writes: no session.commit(), no session.add(), no audit.emit() (D-58-12).
    """
    # Step 1 — resolve config as of period_end (D-58-02 INSERT-only versioned resolver).
    config = await repository.resolve_active_comp_config(session, trainer_id, period_end)
    if config is None or (
        config.commission_pct_bps is None and config.session_fee_kopecks is None
    ):
        raise CompConfigMissingError("comp_config_missing")

    # Step 2 — cross-module revenue + session count read.
    revenue_kopecks, session_count = await repository.fetch_trainer_session_revenue(
        session, trainer_id, period_start, period_end
    )

    # Step 3 — commission: integer-only math.ceil in trainer's favor (D-58-04 / T-58-25).
    # math.ceil(a * b / c) where a, b, c are Python ints: Python evaluates a * b as an
    # exact integer then divides by c using true division — math.ceil returns an int.
    # No float() conversion occurs; this is exact rational arithmetic.
    bps = config.commission_pct_bps
    commission_kopecks: int = math.ceil(revenue_kopecks * bps / 10000) if bps is not None else 0

    # Step 4 — fixed: session fee per conducting session.
    fixed_kopecks: int = (config.session_fee_kopecks or 0) * session_count

    # Step 5 — total.
    total_kopecks: int = commission_kopecks + fixed_kopecks

    return session_count, fixed_kopecks, commission_kopecks, total_kopecks, config


async def preview_accrual(
    session: AsyncSession,
    trainer_id: UUID,
    period_start: date,
    period_end: date,
) -> PayrollPreviewResponse:
    """Return a read-only payroll preview for a trainer + period (PAY-02 / D-58-12).

    Maps the first four ints from compute_accrual_components into PayrollPreviewResponse.
    NO session.commit(), NO audit.emit(), NO session.add() / INSERT — zero-persistence
    (D-58-12 zero-persistence invariant / T-58-23).

    CompConfigMissingError propagates to the router, which remaps it to 422 for this
    endpoint (see module docstring). This is the router-remap approach (one error class).
    """
    session_count, fixed_kopecks, commission_kopecks, total_kopecks, _config = (
        await compute_accrual_components(session, trainer_id, period_start, period_end)
    )
    return PayrollPreviewResponse(
        session_count=session_count,
        fixed_kopecks=fixed_kopecks,
        commission_kopecks=commission_kopecks,
        total_kopecks=total_kopecks,
    )
