"""Payroll repository — ORM writes + own-module reads for payroll tables (Phase 58 PAY-01..06).

CROSS-MODULE READ DISCIPLINE (D-58-19 / D-54-08 / Phase 49 D-49-03 precedent):
  - Use ``from sqlalchemy import text`` for cross-module table reads — NEVER import
    another module's ORM model.
  - Bind params via ``:name`` placeholders + a dict; cast UUIDs to ``str``.
  - ``.mappings().one()`` for scalar/aggregate reads.
  - Each reader documents verified columns + source file:line of the foreign table.

OWN-MODULE WRITE DISCIPLINE (D-32-10 caller-owns-txn precedent):
  - ``insert_comp_config`` calls ``session.flush()`` to surface deferred FK/CHECK
    violations and assign server-side defaults (e.g. ``id``).  It does NOT call
    ``session.commit()`` — the service-layer orchestrator owns the commit (SVC001).
  - ``resolve_active_comp_config`` is a pure read; no mutations.

INVARIANTS:
  - ZERO INSERT/UPDATE/DELETE against pt_sessions, payments, or pt_packages tables.
  - ORM model imports from other modules (``app.modules.*``): FORBIDDEN.
  - ORM model imports from ``app.modules.payroll.*``: ALLOWED (own module).
"""

from __future__ import annotations

from datetime import date
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.payroll.models import TrainerCompConfig


async def resolve_active_comp_config(
    session: AsyncSession,
    trainer_id: UUID,
    as_of_date: date,
) -> TrainerCompConfig | None:
    """Return the active comp config for *trainer_id* as of *as_of_date*, or None.

    "Active" means the row with the latest ``effective_from`` that is still
    <= *as_of_date* (D-58-02 INSERT-only versioned resolver pattern).

    Own-module ORM read — ``TrainerCompConfig`` lives in this module; no
    cross-module import concern.
    """
    stmt = (
        select(TrainerCompConfig)
        .where(
            TrainerCompConfig.trainer_id == trainer_id,
            TrainerCompConfig.effective_from <= as_of_date,
        )
        .order_by(TrainerCompConfig.effective_from.desc())
        .limit(1)
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def insert_comp_config(
    session: AsyncSession,
    *,
    trainer_id: UUID,
    commission_pct_bps: int | None,
    session_fee_kopecks: int | None,
    effective_from: date,
    created_by_user_id: UUID,
) -> TrainerCompConfig:
    """INSERT a new TrainerCompConfig row; caller owns commit (SVC001).

    ``session.flush()`` is called here to:
      1. Assign the server-generated ``id`` (``gen_random_uuid()``) so the
         service layer can reference it in the audit payload.
      2. Surface deferred CHECK constraint violations (bps range, kopecks >= 0)
         before the caller emits the audit event.

    DOES NOT call ``session.commit()`` — the service-layer orchestrator owns the
    transactional moment (D-33-11 mirror / caller-owns-commit SVC001).
    """
    row = TrainerCompConfig(
        trainer_id=trainer_id,
        commission_pct_bps=commission_pct_bps,
        session_fee_kopecks=session_fee_kopecks,
        effective_from=effective_from,
        created_by_user_id=created_by_user_id,
    )
    session.add(row)
    await session.flush()  # assigns id + surfaces FK/CHECK violations; caller owns commit
    return row
