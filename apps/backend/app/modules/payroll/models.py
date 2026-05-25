"""Payroll ORM models (Phase 58 PAY-01..06 / D-58-02..03).

Phase 58 introduces two tables:
- ``trainer_comp_configs`` (D-58-02): INSERT-only versioned compensation config.
  No UNIQUE(trainer_id) — multiple rows per trainer form a version history.
  Resolver picks ORDER BY effective_from DESC LIMIT 1 WHERE effective_from <= :as_of_date.
- ``trainer_payroll_accruals`` (D-58-03): append-only signed-amount accrual ledger.
  NO TimestampMixin (no created_at/updated_at), NO SoftDeleteMixin (no deleted_at).
  ``accrued_at`` is the SINGLE creation temporal column per D-58-03.
  UPDATE/DELETE banned by AST gate tests/unit/test_payroll_appendonly.py
  (planner to add — mirrors test_payments_appendonly.py).

DB-level invariants (mirror migration 0041_payroll_foundations):
- CHECK ck_trainer_comp_configs_commission_pct_bps_range: bps 0..10000 or NULL.
- CHECK ck_trainer_comp_configs_session_fee_kopecks_nonneg: >= 0 or NULL.
- CHECK ck_trainer_payroll_accruals_status: status IN ('pending','paid').
- CHECK ck_trainer_payroll_accruals_clawback_fks_paired: clawback FKs both NULL
  or both NOT NULL.
- FK fk_trainer_payroll_accruals_clawback_of_accrual_id ON DELETE RESTRICT
  (self-ref for clawback rows).
- Partial UNIQUE uq_trainer_payroll_accruals_period_alive ON
  (trainer_id, period_start, period_end) WHERE clawback_of_accrual_id IS NULL
  — one accrual per trainer per period (D-58-06).
"""

from __future__ import annotations

from datetime import date, datetime
from uuid import UUID as UUIDType  # noqa: N811

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PgUUID  # noqa: N811
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, UUIDPkMixin


class TrainerCompConfig(Base, UUIDPkMixin):
    """INSERT-only versioned trainer compensation config (D-58-02).

    NO UNIQUE(trainer_id) — multiple rows per trainer are allowed.
    Each INSERT creates a new version. Resolver picks:
        ORDER BY effective_from DESC LIMIT 1 WHERE effective_from <= :as_of_date.
    Created FIRST — accruals FK into this table via comp_config_id_snapshot.
    """

    __tablename__ = "trainer_comp_configs"

    trainer_id: Mapped[UUIDType] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey(
            "trainers.id",
            ondelete="RESTRICT",
            name="fk_trainer_comp_configs_trainer_id_trainers",
        ),
        nullable=False,
    )
    # Economics columns: both NULL is allowed at write time; both NULL at
    # accrual run time → 422 comp_config_missing (D-58-09 / D-58-02).
    commission_pct_bps: Mapped[int | None] = mapped_column(Integer, nullable=True)
    session_fee_kopecks: Mapped[int | None] = mapped_column(Integer, nullable=True)
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    created_by_user_id: Mapped[UUIDType | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey(
            "users.id",
            ondelete="RESTRICT",
            name="fk_trainer_comp_configs_created_by_user_id_users",
        ),
        nullable=True,
    )

    __table_args__ = (
        CheckConstraint(
            "commission_pct_bps IS NULL"
            " OR (commission_pct_bps >= 0 AND commission_pct_bps <= 10000)",
            # NAMING_CONVENTION expands to ck_trainer_comp_configs_commission_pct_bps_range
            name="commission_pct_bps_range",
        ),
        CheckConstraint(
            "session_fee_kopecks IS NULL OR session_fee_kopecks >= 0",
            # NAMING_CONVENTION expands to ck_trainer_comp_configs_session_fee_kopecks_nonneg
            name="session_fee_kopecks_nonneg",
        ),
        Index(
            "ix_trainer_comp_configs_trainer_effective",
            "trainer_id",
            text("effective_from DESC"),
        ),
    )


class TrainerPayrollAccrual(Base, UUIDPkMixin):
    """Append-only payroll accrual row (PAY-03 / D-58-03).

    NO TimestampMixin (no created_at/updated_at), NO SoftDeleteMixin (no deleted_at) —
    ``accrued_at`` is the SINGLE creation temporal column per D-58-03.
    UPDATE/DELETE banned by AST gate tests/unit/test_payroll_appendonly.py
    (planner to add — mirrors test_payments_appendonly.py).

    DB-level invariants (mirror migration 0041_payroll_foundations):
    - CHECK ck_trainer_payroll_accruals_status: status IN ('pending','paid').
    - CHECK ck_trainer_payroll_accruals_clawback_fks_paired: clawback FKs both NULL
      or both NOT NULL.
    - FK fk_trainer_payroll_accruals_clawback_of_accrual_id ON DELETE RESTRICT
      (self-ref for clawback rows).
    - Partial UNIQUE uq_trainer_payroll_accruals_period_alive ON
      (trainer_id, period_start, period_end) WHERE clawback_of_accrual_id IS NULL
      — one accrual per trainer per period (D-58-06).
    - Signed accrual_kopecks: positive for regular accruals; negative for clawback rows (D-58-03).
      NO >= 0 CHECK — clawback rows intentionally carry negative amounts (T-58-08).
    - Snapshot columns frozen at INSERT time; never recomputed (D-58-03 / D-58-04).
      The only allowed post-INSERT mutation is the single status='pending'→'paid' transition.
      Clawback rows are INSERTs with negative accrual_kopecks (NOT UPDATE).
    """

    __tablename__ = "trainer_payroll_accruals"

    trainer_id: Mapped[UUIDType] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey(
            "trainers.id",
            ondelete="RESTRICT",
            name="fk_trainer_payroll_accruals_trainer_id_trainers",
        ),
        nullable=False,
    )
    # Period bounds — inclusive [period_start, period_end] MSK dates (D-58-05)
    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)
    # Snapshot columns — frozen at INSERT time; never recomputed (D-58-03 / D-58-04)
    sessions_count: Mapped[int] = mapped_column(Integer, nullable=False)
    revenue_kopecks: Mapped[int] = mapped_column(Integer, nullable=False)
    # NULL when config was session-fee-only; NULL when config was pct-only
    commission_pct_bps_snapshot: Mapped[int | None] = mapped_column(Integer, nullable=True)
    session_fee_kopecks_snapshot: Mapped[int | None] = mapped_column(Integer, nullable=True)
    comp_config_id_snapshot: Mapped[UUIDType] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey(
            "trainer_comp_configs.id",
            ondelete="RESTRICT",
            name="fk_trainer_payroll_accruals_comp_config_id_snapshot",
        ),
        nullable=False,
    )
    # Signed: positive for regular accruals; negative for clawback rows (D-58-03)
    # NO >= 0 CHECK — clawback rows intentionally carry negative amounts (T-58-08)
    accrual_kopecks: Mapped[int] = mapped_column(Integer, nullable=False)
    # Lifecycle: single-transition 'pending' → 'paid' (PAY-04 / D-58-08)
    status: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        server_default=text("'pending'"),
    )
    accrued_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    paid_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    paid_by_user_id: Mapped[UUIDType | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey(
            "users.id",
            ondelete="RESTRICT",
            name="fk_trainer_payroll_accruals_paid_by_user_id_users",
        ),
        nullable=True,
    )
    # Clawback self-FK — mirrors Payment.refund_of (payments/models.py:81-89)
    # NULL on regular accrual rows; NOT NULL on clawback rows (D-58-03 / PAY-06)
    clawback_of_accrual_id: Mapped[UUIDType | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey(
            "trainer_payroll_accruals.id",
            ondelete="RESTRICT",
            name="fk_trainer_payroll_accruals_clawback_of_accrual_id",
        ),
        nullable=True,
    )
    # FK to the refund payment row that triggered this clawback (PAY-06)
    source_refund_payment_id: Mapped[UUIDType | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey(
            "payments.id",
            ondelete="RESTRICT",
            name="fk_trainer_payroll_accruals_source_refund_payment_id",
        ),
        nullable=True,
    )
    # Audit hash chain reference; SET NULL preserves accrual if audit row pruned
    audit_log_id: Mapped[UUIDType | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey(
            "audit_log.id",
            ondelete="SET NULL",
            name="fk_trainer_payroll_accruals_audit_log_id_audit_log",
        ),
        nullable=True,
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('pending','paid')",
            # NAMING_CONVENTION expands to ck_trainer_payroll_accruals_status
            name="status",
        ),
        CheckConstraint(
            "(clawback_of_accrual_id IS NULL AND source_refund_payment_id IS NULL)"
            " OR (clawback_of_accrual_id IS NOT NULL AND source_refund_payment_id IS NOT NULL)",
            # NAMING_CONVENTION expands to ck_trainer_payroll_accruals_clawback_fks_paired
            name="clawback_fks_paired",
        ),
        # Partial UNIQUE — covers only regular accrual rows (clawback_of_accrual_id IS NULL).
        # Mirrors uq_payments_refund_of_alive (payments/models.py:112-117) and the
        # Phase 49 double-tap guard pattern.
        # T-58-09: DB-wins-the-race idempotency: ON CONFLICT DO NOTHING targets this index.
        Index(
            "uq_trainer_payroll_accruals_period_alive",
            "trainer_id",
            "period_start",
            "period_end",
            unique=True,
            postgresql_where=text("clawback_of_accrual_id IS NULL"),
        ),
        # PAY-05: list ordering index — accrued_at DESC per D-58-14
        Index(
            "ix_trainer_payroll_accruals_trainer_accrued",
            "trainer_id",
            text("accrued_at DESC"),
        ),
        # Pending-accrual queries — status + period_start DESC per D-58-14
        Index(
            "ix_trainer_payroll_accruals_status_period",
            "status",
            text("period_start DESC"),
        ),
    )
