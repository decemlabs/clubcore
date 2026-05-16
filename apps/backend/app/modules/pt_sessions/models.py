"""PtSession ORM model (Phase 34 PT-14).

Composition: Base + UUIDPkMixin + TimestampMixin (NO SoftDeleteMixin —
lifecycle is single-cancel via `cancelled_at IS NOT NULL`; D-34-02 mirrors
PtPackage D-33-03 status-only pattern).

B-05 — `trainer_name_snapshot` is captured at INSERT time in
`pt_sessions.service.record_pt_session` (Plan 34-02) by reading
`trainer.full_name` off the `TrainerById` Protocol (Phase 31 D-31-13 +
Phase 34 D-34-12a additive extension). This preserves UI integrity if the
parent trainer is later renamed/deactivated.

This ORM is the ONLY direct cross-reference between pt_sessions and
pt_packages. Balance mutations on `pt_packages.sessions_remaining` and
the conditional `exhausted ↔ active` reverse transition (D-34-11a carve-out)
are performed via raw `sa.text()` SQL in `pt_sessions.repository` so that
this module NEVER `from app.modules.pt_packages import ...` — the
`modules-independent` importlinter contract is preserved (D-34-04a).

DB-level invariants (D-34-02 — defence-in-depth mirrors of the migration):
- CHECK ck_pt_sessions_cancel_reason_requires_cancelled_at
    (cancel_reason IS NULL OR cancelled_at IS NOT NULL)
- CHECK ck_pt_sessions_cancel_reason_length (≤200)
- CHECK ck_pt_sessions_notes_length (≤500)
- FK fk_pt_sessions_pt_package_id_pt_packages ON DELETE RESTRICT
- FK fk_pt_sessions_trainer_id_trainers ON DELETE RESTRICT
- FK fk_pt_sessions_client_id_clients ON DELETE RESTRICT
- FK fk_pt_sessions_performed_by_user_id_users ON DELETE RESTRICT
- Composite index ix_pt_sessions_pt_package_id_performed_at_desc
  supports `GET /pt-packages/{id}/sessions` (PT-19).
- Composite index ix_pt_sessions_trainer_id_performed_at_desc
  supports future trainer-load analytics (out of v1.4, cheap index now).
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID as UUIDType  # noqa: N811

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Text, text
from sqlalchemy.dialects.postgresql import UUID as PgUUID  # noqa: N811
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, TimestampMixin, UUIDPkMixin


class PtSession(Base, UUIDPkMixin, TimestampMixin):
    """PT-session row — one per recorded training (Phase 34 PT-14)."""

    __tablename__ = "pt_sessions"

    pt_package_id: Mapped[UUIDType] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey(
            "pt_packages.id",
            ondelete="RESTRICT",
            name="fk_pt_sessions_pt_package_id_pt_packages",
        ),
        nullable=False,
    )
    trainer_id: Mapped[UUIDType] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey(
            "trainers.id",
            ondelete="RESTRICT",
            name="fk_pt_sessions_trainer_id_trainers",
        ),
        nullable=False,
    )
    client_id: Mapped[UUIDType] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey(
            "clients.id",
            ondelete="RESTRICT",
            name="fk_pt_sessions_client_id_clients",
        ),
        nullable=False,
    )
    performed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    performed_by_user_id: Mapped[UUIDType] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey(
            "users.id",
            ondelete="RESTRICT",
            name="fk_pt_sessions_performed_by_user_id_users",
        ),
        nullable=False,
    )
    cancelled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    cancel_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    trainer_name_snapshot: Mapped[str] = mapped_column(Text, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        # NAMING_CONVENTION expands to ck_pt_sessions_cancel_reason_requires_cancelled_at
        CheckConstraint(
            "cancel_reason IS NULL OR cancelled_at IS NOT NULL",
            name="cancel_reason_requires_cancelled_at",
        ),
        # NAMING_CONVENTION expands to ck_pt_sessions_cancel_reason_length
        CheckConstraint(
            "cancel_reason IS NULL OR char_length(cancel_reason) <= 200",
            name="cancel_reason_length",
        ),
        # NAMING_CONVENTION expands to ck_pt_sessions_notes_length
        CheckConstraint(
            "notes IS NULL OR char_length(notes) <= 500",
            name="notes_length",
        ),
        Index(
            "ix_pt_sessions_pt_package_id_performed_at_desc",
            "pt_package_id",
            text("performed_at DESC"),
        ),
        Index(
            "ix_pt_sessions_trainer_id_performed_at_desc",
            "trainer_id",
            text("performed_at DESC"),
        ),
    )
