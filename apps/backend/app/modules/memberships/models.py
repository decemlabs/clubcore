"""MembershipPlan ORM model (Phase 16, MEM-PLAN-01).

Composition: Base + UUIDPkMixin + TimestampMixin + SoftDeleteMixin.

DB-level invariants:
- duration_days > 0 (CHECK ck_membership_plans_duration_days_positive)
- price_kopecks >= 0 (CHECK ck_membership_plans_price_kopecks_nonneg)
- lower(name) is partial-unique among alive rows (uq_membership_plans_name_alive,
  WHERE deleted_at IS NULL). Expression index — declared in __table_args__ for
  ORM awareness, installed via raw op.execute in the migration, and suppressed in
  alembic/env.py:_include_object to keep autogenerate clean.

Phase 17 / MEM-01 — Membership ORM model added below.

Composition: Base + UUIDPkMixin + TimestampMixin (NO SoftDeleteMixin — lifecycle
is purely status-based per Phase 17 D-12 / CONTEXT.md domain line 12).

DB-level invariants:
- status IN ('active', 'expired', 'cancelled') (CHECK ck_memberships_status)
- activation_policy = 'purchase_date' (CHECK ck_memberships_activation_policy)
- FK fk_memberships_client_id_clients ON DELETE RESTRICT to clients.id
- FK fk_memberships_plan_id_membership_plans ON DELETE RESTRICT to membership_plans.id
  (constraint name is literal-ref'd by service.py:_is_plan_in_use_conflict per D-05)
- Composite index ix_memberships_client_id_status_end_date on
  (client_id, status, end_date DESC) — covers the active-membership resolver
  query. DESC ordering installed via raw op.execute() in the migration.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal
from uuid import UUID as UUIDType  # noqa: N811

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PgUUID  # noqa: N811
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, SoftDeleteMixin, TimestampMixin, UUIDPkMixin


class MembershipPlan(Base, UUIDPkMixin, TimestampMixin, SoftDeleteMixin):
    """Gym membership plan / SKU (MEM-PLAN-01)."""

    __tablename__ = "membership_plans"

    name: Mapped[str] = mapped_column(String(120), nullable=False)
    duration_days: Mapped[int] = mapped_column(Integer, nullable=False)
    price_kopecks: Mapped[int] = mapped_column(BigInteger, nullable=False)
    freeze_days_limit: Mapped[int] = mapped_column(Integer, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))

    __table_args__ = (
        CheckConstraint(
            "duration_days > 0",
            # NAMING_CONVENTION expands to ck_membership_plans_duration_days_positive
            name="duration_days_positive",
        ),
        CheckConstraint(
            "price_kopecks >= 0",
            # NAMING_CONVENTION expands to ck_membership_plans_price_kopecks_nonneg
            name="price_kopecks_nonneg",
        ),
        # NAMING_CONVENTION expands to ck_membership_plans_freeze_days_limit_positive
        CheckConstraint("freeze_days_limit > 0", name="freeze_days_limit_positive"),
        Index(
            "uq_membership_plans_name_alive",
            text("lower(name)"),
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
    )


class Membership(Base, UUIDPkMixin, TimestampMixin):
    """Membership instance — client X bought plan Y on date Z (MEM-01).

    Snapshot pricing is immutable; status drives lifecycle. NO soft-delete
    column (Phase 17 D-12 / CONTEXT.md domain line 12) — cancelled rows
    keep their FK reference and block plan deletion (D-06).

    Structurally satisfies the `ActiveMembership` Protocol that Plan 17-02
    declares in core/dependencies.py (matches on id, client_id, end_date,
    status — D-18). No DTO conversion at the resolver boundary.

    Phase 26 MEM-REN-01: `previous_membership_id` self-FK — set ONCE at
    INSERT by `service.renew_membership`; immutable post-creation (D-26-04).
    ON DELETE SET NULL preserves renewal-row data when source is hard-deleted
    (D-26-05). Chain depth is implicitly unbounded (D-26-06).
    """

    __tablename__ = "memberships"

    client_id: Mapped[UUIDType] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey(
            "clients.id",
            ondelete="RESTRICT",
            name="fk_memberships_client_id_clients",
        ),
        nullable=False,
    )
    plan_id: Mapped[UUIDType] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey(
            "membership_plans.id",
            ondelete="RESTRICT",
            # Literal-ref'd by service.py:_is_plan_in_use_conflict (D-05).
            name="fk_memberships_plan_id_membership_plans",
        ),
        nullable=False,
    )
    plan_name_snapshot: Mapped[str] = mapped_column(String(120), nullable=False)
    duration_days_snapshot: Mapped[int] = mapped_column(Integer, nullable=False)
    price_kopecks_snapshot: Mapped[int] = mapped_column(BigInteger, nullable=False)
    freeze_days_limit_snapshot: Mapped[int] = mapped_column(Integer, nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(
        String(16),
        server_default=text("'active'"),
        nullable=False,
    )
    cancelled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    cancel_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Phase 32 REF-01 / D-32-07 — sentinel 'refunded' set by refund_membership
    # orchestrator (Plan 32-03). Coexists with cancel_reason; legacy cancelled
    # rows are NULL (no backfill in 0012_payments).
    cancellation_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    paid_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    activation_policy: Mapped[str] = mapped_column(
        String(32),
        server_default=text("'purchase_date'"),
        nullable=False,
    )
    # Phase 26 MEM-REN-01 — chain attribution self-FK (D-26-04 / D-26-05).
    previous_membership_id: Mapped[UUIDType | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey(
            "memberships.id",
            ondelete="SET NULL",
            name="fk_memberships_previous_membership_id_memberships",
        ),
        nullable=True,
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('active', 'expired', 'cancelled', 'frozen')",
            # NAMING_CONVENTION expands to ck_memberships_status
            name="status",
        ),
        CheckConstraint(
            "activation_policy = 'purchase_date'",
            # NAMING_CONVENTION expands to ck_memberships_activation_policy
            name="activation_policy",
        ),
        Index(
            "ix_memberships_client_id_status_end_date",
            "client_id",
            "status",
            text("end_date DESC"),
        ),
        # Phase 26 D-26-02 — forensic lookup index on the renewal chain column.
        Index(
            "ix_memberships_previous_membership_id",
            "previous_membership_id",
        ),
    )


class MembershipFreezePeriod(Base, UUIDPkMixin, TimestampMixin):
    """Membership freeze period — open while ended_at IS NULL (Phase 25 MEM-FRZ-02).

    Composition: Base + UUIDPkMixin + TimestampMixin (NO SoftDeleteMixin —
    lifecycle is encoded by `ended_at IS NULL` per D-25-04).

    Note: `created_at` (TimestampMixin) and `started_at` are SEMANTICALLY DISTINCT:
        - `created_at` is the audit-row wallclock (server-side func.now() at INSERT).
        - `started_at` is the operational period start (explicit Python datetime
          passed by the service layer at freeze time).
    They will be near-identical at INSERT time but tests must NOT assume equality.

    DB-level invariants:
    - FK fk_membership_freeze_periods_membership_id_memberships ON DELETE RESTRICT
      to memberships.id (audit-trail integrity — never cascade-delete history).
    - FK fk_membership_freeze_periods_started_by_users ON DELETE RESTRICT to users.id.
    - FK fk_membership_freeze_periods_ended_by_users ON DELETE SET NULL to users.id
      (operator may be deleted; period stays).
    - Partial unique index uq_membership_freeze_periods_active_per_membership on
      (membership_id) WHERE ended_at IS NULL — single open period per membership.
      The constraint name is literal-ref'd by service.py:_is_already_frozen_conflict
      (D-25-22). Installed via raw op.execute() in the migration; mirrored here in
      __table_args__ for ORM awareness; suppressed in alembic/env.py:_include_object
      to keep autogenerate clean.
    """

    __tablename__ = "membership_freeze_periods"

    membership_id: Mapped[UUIDType] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey(
            "memberships.id",
            ondelete="RESTRICT",
            name="fk_membership_freeze_periods_membership_id_memberships",
        ),
        nullable=False,
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    ended_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    started_by: Mapped[UUIDType] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey(
            "users.id",
            ondelete="RESTRICT",
            name="fk_membership_freeze_periods_started_by_users",
        ),
        nullable=False,
    )
    ended_by: Mapped[UUIDType | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey(
            "users.id",
            ondelete="SET NULL",
            name="fk_membership_freeze_periods_ended_by_users",
        ),
        nullable=True,
    )

    __table_args__ = (
        Index(
            "uq_membership_freeze_periods_active_per_membership",
            "membership_id",
            unique=True,
            postgresql_where=text("ended_at IS NULL"),
        ),
    )


class MembershipNotification(Base, UUIDPkMixin, TimestampMixin):
    """Idempotency record for expiring-soon Telegram DM (Phase 27 NTF-01).

    Composition: Base + UUIDPkMixin + TimestampMixin (NO SoftDeleteMixin —
    rows are append-only; the (membership_id, kind) UNIQUE is the single
    source of truth for cron idempotency per D-27-15).

    DB-level invariants:
    - kind IN ('expiring_7d', 'expiring_3d', 'expiring_1d')
      (CHECK ck_membership_notifications_kind).
    - FK fk_membership_notifications_membership_id_memberships ON DELETE CASCADE
      to memberships.id — DBA-direct hard-delete drops history (D-27-02).
    - UNIQUE (membership_id, kind) (uq_membership_notifications_membership_kind) —
      single source of truth for cron idempotency. Service helper
      `_send_expiring_notifications` catches IntegrityError on this constraint
      to skip race-duplicates (D-27-15). NOT literal-ref'd by service code
      (no constraint-name discriminator needed) — NO entry added to
      alembic/env.py:_include_object.
    """

    __tablename__ = "membership_notifications"

    membership_id: Mapped[UUIDType] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey(
            "memberships.id",
            ondelete="CASCADE",
            name="fk_membership_notifications_membership_id_memberships",
        ),
        nullable=False,
    )
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    sent_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=text("now()"),
        nullable=False,
    )
    # Phase 45 D-45-01 + Alembic 0031 — widened to NULLABLE so email-fallback
    # rows (channel='email') can record NULL chat_id (Telegram is the BLOCKED
    # channel at fanout time by definition).
    telegram_chat_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    # Phase 45 D-45-13 — cross-channel discriminator. ORM-side default mirrors
    # the DB server_default 'telegram' (Alembic 0024); INSERTs MUST pass
    # channel=<literal> explicitly per D-45-13 (no implicit app-layer default).
    channel: Mapped[Literal["telegram", "email"]] = mapped_column(
        Text,
        nullable=False,
        server_default=text("'telegram'"),
    )

    __table_args__ = (
        CheckConstraint(
            "kind IN ('expiring_7d', 'expiring_3d', 'expiring_1d')",
            # NAMING_CONVENTION expands to ck_membership_notifications_kind
            # (matches migration 0010_notifications.py op.f()-derived name).
            name="kind",
        ),
        # Phase 45 D-45-13 — UNIQUE renamed by Alembic 0024 to include channel.
        # Name MUST match 0024's _MEMBERSHIP_NOTIFS_NEW_UNIQUE letter-for-letter
        # so `alembic check` produces empty diff.
        UniqueConstraint(
            "membership_id",
            "kind",
            "channel",
            name="uq_membership_notifications_membership_kind_channel",
        ),
        # Mirrors migration 0010 op.create_index() — required for `alembic check`
        # to stay clean (drift detection treats migration-only indexes as drift).
        Index(
            "ix_membership_notifications_membership_id",
            "membership_id",
        ),
    )
