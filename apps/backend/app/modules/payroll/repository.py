"""Payroll repository — ORM writes + own-module reads for payroll tables (Phase 58 PAY-01..07).

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
  - ``insert_accrual_on_conflict`` uses ON CONFLICT DO NOTHING RETURNING and does NOT
    call ``session.commit()`` — the service-layer orchestrator owns the commit (SVC001).
  - ``resolve_active_comp_config`` and ``select_accrual_for_update`` are pure reads.

INVARIANTS:
  - ZERO INSERT/UPDATE/DELETE against pt_sessions, payments, or pt_packages tables.
  - ORM model imports from other modules (``app.modules.*``): FORBIDDEN.
  - ORM model imports from ``app.modules.payroll.*``: ALLOWED (own module).
"""

from __future__ import annotations

from datetime import date
from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.payroll.constants import PAYMENT_SUBJECT_KIND_PT_PACKAGE
from app.modules.payroll.models import TrainerCompConfig, TrainerPayrollAccrual


async def fetch_trainer_session_revenue(
    session: AsyncSession,
    trainer_id: UUID,
    period_start: date,
    period_end: date,
) -> tuple[int, int]:
    """Return (commission_revenue_kopecks, conducting_session_count) for a trainer + period.

    CROSS-MODULE READ — raw SQL text() only; NO ORM imports of other modules.
    Verified columns:
      pt_packages (apps/backend/app/modules/pt_packages/models.py:103-186):
        - id            UUID PK
        - trainer_id    UUID NULLABLE (attribution: assigned-at-sale; skip when NULL)
        - client_id     UUID NOT NULL
        - status        TEXT IN ('active','exhausted','expired','cancelled')
      pt_sessions (apps/backend/app/modules/pt_sessions/models.py:50-137):
        - id            UUID PK
        - pt_package_id UUID FK→pt_packages.id NOT NULL
        - trainer_id    UUID NOT NULL  (the conducting trainer)
        - performed_at  TIMESTAMPTZ NOT NULL
        - cancelled_at  TIMESTAMPTZ NULL  (exclude cancelled sessions)
      payments (apps/backend/app/modules/payments/models.py:51-154):
        - subject_kind  TEXT ('pt_package' for package sales; 'refund' for refunds)
        - subject_id    UUID (= pt_packages.id for package sales)
        - amount_kopecks INT signed (sale > 0, refund < 0)
        - refund_of     UUID NULL (self-ref for refund rows)

    Returns:
        commission_revenue_kopecks: Net package revenue (SUM of sale + refund payments)
            for pt_packages where pt_packages.trainer_id = :trainer_id AND the package
            has >= 1 non-cancelled session in the MSK-inclusive period.
            Attribution: assigned-at-sale (D-58-21).
        conducting_session_count: COUNT of non-cancelled pt_sessions where
            pt_sessions.trainer_id = :trainer_id AND the MSK-cast performed_at date
            falls within the inclusive period.
            Attribution: conducting (D-58-21).

    Period bounds are inclusive MSK dates via
    ``(performed_at AT TIME ZONE 'Europe/Moscow')::date BETWEEN :period_start AND :period_end``
    (D-58-05).

    INVARIANTS:
      - ZERO INSERT / UPDATE / DELETE.
      - ORM model imports from other modules: FORBIDDEN (D-58-19).
    """
    row = (
        await session.execute(
            text(
                # ----------------------------------------------------------------
                # commission_revenue_kopecks — attribution: assigned-at-sale
                # ----------------------------------------------------------------
                # SUM net payments (sale + refunds via refund_of FK) for packages
                # whose assigned trainer is :trainer_id AND have >= 1 non-cancelled
                # session in the MSK-inclusive period.  Refund payments carry a
                # negative amount_kopecks, so SUM naturally nets them out.
                # COALESCE handles trainers with no matching packages (returns 0).
                "SELECT "
                "  COALESCE(( "
                "    SELECT SUM(p.amount_kopecks) "
                "    FROM payments p "
                "    WHERE p.subject_kind = :subject_kind "
                "      AND p.subject_id IN ( "
                "        SELECT pkg.id "
                "        FROM pt_packages pkg "
                "        WHERE pkg.trainer_id = :trainer_id "  # attribution: assigned-at-sale
                "          AND EXISTS ( "
                "            SELECT 1 FROM pt_sessions s "
                "            WHERE s.pt_package_id = pkg.id "
                "              AND s.cancelled_at IS NULL "
                "              AND (s.performed_at AT TIME ZONE 'Europe/Moscow')::date "
                "                  BETWEEN :period_start AND :period_end "
                "          ) "
                "      ) "
                "  ), 0) AS commission_revenue_kopecks, "
                # ----------------------------------------------------------------
                # conducting_session_count — attribution: conducting
                # ----------------------------------------------------------------
                # COUNT non-cancelled sessions conducted by :trainer_id in the period.
                "  COALESCE(( "
                "    SELECT COUNT(*) "
                "    FROM pt_sessions s "
                "    WHERE s.trainer_id = :trainer_id "  # attribution: conducting
                "      AND s.cancelled_at IS NULL "
                "      AND (s.performed_at AT TIME ZONE 'Europe/Moscow')::date "
                "          BETWEEN :period_start AND :period_end "
                "  ), 0) AS conducting_session_count"
            ),
            {
                "trainer_id": str(trainer_id),
                "subject_kind": PAYMENT_SUBJECT_KIND_PT_PACKAGE,
                "period_start": period_start,
                "period_end": period_end,
            },
        )
    ).mappings().one()
    return int(row["commission_revenue_kopecks"]), int(row["conducting_session_count"])


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


async def insert_accrual_on_conflict(
    session: AsyncSession,
    *,
    trainer_id: UUID,
    period_start: date,
    period_end: date,
    sessions_count: int,
    revenue_kopecks: int,
    commission_pct_bps_snapshot: int | None,
    session_fee_kopecks_snapshot: int | None,
    comp_config_id_snapshot: UUID,
    accrual_kopecks: int,
) -> UUID | None:
    """INSERT a TrainerPayrollAccrual row; return id on success or None on duplicate.

    Uses ``INSERT ... ON CONFLICT (trainer_id, period_start, period_end)
    WHERE clawback_of_accrual_id IS NULL DO NOTHING RETURNING id`` (D-58-06
    DB-wins-the-race idempotency — NO SELECT-then-INSERT, no TOCTOU race).

    The ``index_where`` predicate MUST match the partial UNIQUE constraint
    ``uq_trainer_payroll_accruals_period_alive`` exactly:
        WHERE clawback_of_accrual_id IS NULL
    This ensures only live (non-clawback) accruals are checked for duplicates;
    clawback rows (PAY-06) may coexist for the same period.

    ``status`` defaults to 'pending' via the DB server-default; ``clawback_of_accrual_id``
    and ``source_refund_payment_id`` remain NULL (regular accrual, not a clawback).

    Does NOT call ``session.commit()`` — the service-layer orchestrator owns the
    transactional moment (SVC001).

    Returns:
        UUID of the newly inserted row, or ``None`` when ON CONFLICT suppressed
        the insert (the period already has a live accrual for this trainer).
    """
    stmt = (
        pg_insert(TrainerPayrollAccrual)
        .values(
            trainer_id=trainer_id,
            period_start=period_start,
            period_end=period_end,
            sessions_count=sessions_count,
            revenue_kopecks=revenue_kopecks,
            commission_pct_bps_snapshot=commission_pct_bps_snapshot,
            session_fee_kopecks_snapshot=session_fee_kopecks_snapshot,
            comp_config_id_snapshot=comp_config_id_snapshot,
            accrual_kopecks=accrual_kopecks,
            # status, accrued_at use DB server-defaults ('pending', now())
            # clawback_of_accrual_id and source_refund_payment_id stay NULL
        )
        .on_conflict_do_nothing(
            index_elements=["trainer_id", "period_start", "period_end"],
            # MUST match partial UNIQUE uq_trainer_payroll_accruals_period_alive predicate
            index_where=TrainerPayrollAccrual.clawback_of_accrual_id.is_(None),
        )
        .returning(TrainerPayrollAccrual.id)
    )
    result = await session.execute(stmt)
    row = result.scalar_one_or_none()
    return row  # UUID on insert, None when ON CONFLICT suppressed the row


async def select_accrual_for_update(
    session: AsyncSession,
    accrual_id: UUID,
) -> TrainerPayrollAccrual | None:
    """SELECT a TrainerPayrollAccrual row WITH FOR UPDATE row-lock (D-58-08).

    Used by the mark-paid path to prevent concurrent double-pay races:
    the row lock is acquired before the status check, ensuring only one
    concurrent transition from 'pending' → 'paid' can succeed.

    Own-module ORM read — ``TrainerPayrollAccrual`` lives in this module;
    no cross-module import concern.

    Returns the row or ``None`` when the accrual_id does not exist.
    """
    stmt = (
        select(TrainerPayrollAccrual)
        .where(TrainerPayrollAccrual.id == accrual_id)
        .with_for_update()
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
