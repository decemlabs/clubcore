"""Booking ORM model (Phase 38 BOOK-01).

Composition: Base + UUIDPkMixin + TimestampMixin.

NO SoftDeleteMixin (D-38-04 mirror) — decommission via status flip to
'cancelled'; cancelled bookings stay for audit + history. Phase 38
bookings.service.cancel_booking performs the confirmed→cancelled
transition (plan 38-03).

DB-level invariants (BOOK-01 / D-38-02 / D-38-15 / Pitfall 6):
- status IN ('confirmed', 'cancelled', 'no_show', 'completed')
                         (CHECK ck_bookings_status)
- pt_package_id is NOT NULL FK to pt_packages.id ON DELETE RESTRICT
                         (D-38-02: every booking references a live package)
- slot_id is NOT NULL FK to trainer_availability_slots.id ON DELETE RESTRICT
- client_id is NOT NULL FK to clients.id ON DELETE RESTRICT
- created_by_user_id is NULLABLE FK to users.id ON DELETE RESTRICT (NULL =
  self-service via bot — see audit_log.payload.actor_role; Phase 40 D-40-05)
- Partial UNIQUE uq_bookings_slot_confirmed on (slot_id) WHERE status='confirmed'
  — one confirmed booking per slot (BOOK-01 / C-02 / D-38-15; service
  catches IntegrityError via _is_slot_confirmed_conflict discriminator).

NO snapshot columns (D-38-08) — display payloads use joinedload(Booking.slot)
+ joinedload(Booking.pt_package) at the repository layer (Phase 38 plan
38-03 list/detail endpoints).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID as UUIDType  # noqa: N811

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PgUUID  # noqa: N811
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, TimestampMixin, UUIDPkMixin


class Booking(Base, UUIDPkMixin, TimestampMixin):
    """PT-session booking (Phase 38 BOOK-01 / D-38-02)."""

    __tablename__ = "bookings"

    slot_id: Mapped[UUIDType] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey(
            "trainer_availability_slots.id",
            ondelete="RESTRICT",
            name="fk_bookings_slot_id_trainer_availability_slots",
        ),
        nullable=False,
    )
    client_id: Mapped[UUIDType] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey(
            "clients.id",
            ondelete="RESTRICT",
            name="fk_bookings_client_id_clients",
        ),
        nullable=False,
    )
    pt_package_id: Mapped[UUIDType] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey(
            "pt_packages.id",
            ondelete="RESTRICT",
            name="fk_bookings_pt_package_id_pt_packages",
        ),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(16),
        server_default=text("'confirmed'"),
        nullable=False,
    )
    # Phase 40 D-40-05 / BLOCKER-4 — NULL = self-service via Telegram bot;
    # the audit_log row's payload.actor_role discriminates 'telegram_bot' vs.
    # 'reception' / 'owner'. Alembic 0021 relaxed the DB NOT NULL constraint.
    created_by_user_id: Mapped[UUIDType | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey(
            "users.id",
            ondelete="RESTRICT",
            name="fk_bookings_created_by_user_id_users",
        ),
        nullable=True,
    )
    cancelled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    cancel_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    no_show_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Cross-module relationships (Phase 38 plan 38-03 / BOOK-09 — joinedload
    # discipline per Pitfall 19 for the GET /bookings/{id} detail endpoint).
    #
    # STRING-KEYED relationships preserve the modules-independent import-linter
    # contract: SQLAlchemy resolves "TrainerAvailabilitySlot" / "PtPackage"
    # against the SHARED `Base.registry` at mapper-configuration time (all
    # models register into the same Base metadata). NO `from app.modules.X`
    # import is added to this file — import-linter's AST walker sees zero
    # cross-module imports, while the ORM resolves the class lookups via
    # registry-string discovery (independent of Python import order, but the
    # target classes are guaranteed loaded by the time SA configures mappers
    # because `alembic/env.py` and `app/main.py` both import all module
    # `models` packages eagerly).
    #
    # `Mapped[Any]` keeps mypy strict happy without naming the cross-module
    # type — the joinedload-fetched objects are consumed in the bookings
    # service layer where they are projected into the local `SlotSnapshot`
    # Pydantic class (D-38-08 / plan 38-03 §Task 1).
    slot: Mapped[Any] = relationship(
        "TrainerAvailabilitySlot",
        foreign_keys=[slot_id],
        lazy="select",
        viewonly=True,
    )
    pt_package: Mapped[Any] = relationship(
        "PtPackage",
        foreign_keys=[pt_package_id],
        lazy="select",
        viewonly=True,
    )
    # Phase 39 NOTIFY-03/04 — string-keyed cross-module relationship so the
    # `_dispatch_booking_dm` helper can render DMs with `client.first_name`
    # and `client.telegram_user_id`. Same modules-independent discipline as
    # the `slot` / `pt_package` relationships above (no
    # `from app.modules.clients` import; SA resolves via Base.registry).
    client: Mapped[Any] = relationship(
        "Client",
        foreign_keys=[client_id],
        lazy="select",
        viewonly=True,
    )

    __table_args__ = (
        # NAMING_CONVENTION expands to ck_bookings_status (matches migration 0017
        # literal-string CHECK name so `alembic check` produces empty diff).
        CheckConstraint(
            "status IN ('confirmed', 'cancelled', 'no_show', 'completed')",
            name="status",
        ),
        # Partial UNIQUE — MUST match migration 0017 literal name letter-for-letter
        # (literal-ref'd by service.py:_is_slot_confirmed_conflict, D-38-15).
        Index(
            "uq_bookings_slot_confirmed",
            "slot_id",
            unique=True,
            postgresql_where=text("status = 'confirmed'"),
        ),
        Index("ix_bookings_client_status", "client_id", "status"),
        Index("ix_bookings_slot_status", "slot_id", "status"),
    )


class BookingNotification(Base, UUIDPkMixin, TimestampMixin):
    """Idempotency record for 24h reminder Telegram DM (Phase 39 NOTIFY-05).

    Composition: Base + UUIDPkMixin + TimestampMixin (NO SoftDeleteMixin —
    rows are append-only; the (booking_id, kind) UNIQUE is the single source
    of truth for cron idempotency per D-39-13).

    DB-level invariants:
    - kind IN ('reminder_24h') (CHECK ck_booking_notifications_kind).
    - FK fk_booking_notifications_booking_id_bookings ON DELETE RESTRICT
      to bookings.id (D-39-13 — deviation from v1.3 CASCADE; bookings
      never hard-delete per Phase 38 D-38-04, so RESTRICT prevents silent
      orphaning on accidental DBA-direct surgery).
    - UNIQUE (booking_id, kind) (uq_booking_notifications_booking_kind) —
      single source of truth for cron idempotency. Plan 39-04's service
      helper `_send_booking_reminders` catches IntegrityError on this
      constraint to skip race-duplicates (D-39-13).

    NO `telegram_chat_id` snapshot column (D-39-03 — deviation from v1.3
    MembershipNotification). The reminder cron resolves
    `clients.telegram_user_id` at send time via JOIN, so the chat id is
    always current (a client who re-links between booking + reminder uses
    the new chat). Plan 39-04's cron consumer reads `c.telegram_user_id`
    via the candidate SELECT — never via this side-table.

    NO `Booking.notifications` back-relationship — cron reads via raw SQL
    LEFT JOIN; write-once side-table semantics make a relationship
    attribute load-bearing for nothing.
    """

    __tablename__ = "booking_notifications"

    booking_id: Mapped[UUIDType] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey(
            "bookings.id",
            ondelete="RESTRICT",  # D-39-13 deviation from v1.3 CASCADE
            name="fk_booking_notifications_booking_id_bookings",
        ),
        nullable=False,
    )
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    sent_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=text("now()"),
        nullable=False,
    )
    # Phase 45 D-45-13 — cross-channel discriminator. ORM-side default mirrors
    # the DB server_default 'telegram' (Alembic 0024); INSERTs MUST pass
    # channel=<literal> explicitly per D-45-13. No `telegram_chat_id` column
    # ever existed on this table (Phase 39 D-39-03 — explicit deviation from
    # membership_notifications); the cron resolves chat ids via JOIN at send
    # time, so widening-to-NULLABLE is N/A here.
    channel: Mapped[Literal["telegram", "email"]] = mapped_column(
        Text,
        nullable=False,
        server_default=text("'telegram'"),
    )

    __table_args__ = (
        CheckConstraint(
            "kind IN ('reminder_24h')",
            # NAMING_CONVENTION expands to ck_booking_notifications_kind
            # (matches migration 0020 op.f()-derived name).
            name="kind",
        ),
        # Phase 45 D-45-13 — UNIQUE renamed by Alembic 0024 to include channel.
        # Name MUST match 0024's _BOOKING_NOTIFS_NEW_UNIQUE letter-for-letter
        # so `alembic check` produces empty diff.
        UniqueConstraint(
            "booking_id",
            "kind",
            "channel",
            name="uq_booking_notifications_booking_kind_channel",
        ),
        # Mirrors migration 0020 op.create_index() — required for
        # `alembic check` to stay clean (drift detection treats migration-only
        # indexes as drift).
        Index(
            "ix_booking_notifications_booking_id",
            "booking_id",
        ),
    )
