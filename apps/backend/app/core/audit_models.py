"""AuditLog ORM (Phase 8 D-05).

Lives in `app.core` because audit is a cross-cutting concern that every business
module emits into. The FK reference to `users.id` is a STRING so this module does
NOT import `app.modules.auth.models` — that keeps the import-linter contract
`core-not-depend-on-modules` GREEN.

Schema notes:
- `actor_user_id` is NULLABLE (D-06) for actor-less events: `login_failed`,
  `telegram_bind_pending`, `telegram_bind_completed`, etc.
- `resource_id` is `PgUUID NULL` (D-07). Non-UUID identifiers (e.g. an email,
  a Telegram chat id) belong inside `payload`, not in this column.
- `payload` is JSONB with server-side default `'{}'::jsonb` so emitters don't
  have to pass an empty dict explicitly.
- Only `created_at` is recorded — audit rows are immutable, no `updated_at`.
- Btree index `(actor_user_id, created_at)` supports the per-actor history
  queries planned for Phase 8+ (admin "who did what" view).
"""

from datetime import datetime
from typing import Any
from uuid import UUID as UUIDType  # noqa: N811

from sqlalchemy import DateTime, ForeignKey, Index, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PgUUID  # noqa: N811
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, UUIDPkMixin


class AuditLog(Base, UUIDPkMixin):
    """Audit log row. D-05: lives in app.core (cross-cutting), FK is string ref."""

    __tablename__ = "audit_log"

    actor_user_id: Mapped[UUIDType | None] = mapped_column(
        PgUUID(as_uuid=True),
        # Phase 41 INFRA-39 / migration 0023 — FK flipped from RESTRICT to
        # SET NULL so audit rows survive any future hard-delete of users
        # with `actor_email_snapshot` preserved (D-41-08-10).
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,  # D-06: NULLABLE for actor-less events (login_failed, telegram_*)
    )
    # Phase 41 INFRA-39 / D-41-08 — denormalised email captured at emit() time;
    # populated via actor_context_var (app/core/actor_context.py). NULL whenever
    # actor_user_id is NULL (D-41-10 system-emit rule).
    actor_email_snapshot: Mapped[str | None] = mapped_column(Text, nullable=True)
    action: Mapped[str] = mapped_column(Text, nullable=False)
    resource_type: Mapped[str] = mapped_column(Text, nullable=False)
    resource_id: Mapped[UUIDType | None] = mapped_column(
        PgUUID(as_uuid=True),
        nullable=True,
    )  # D-07: PgUUID NULL; non-UUID identifiers go in payload
    payload: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    __table_args__ = (
        Index(
            "ix_audit_log_actor_user_id_created_at",
            "actor_user_id",
            "created_at",
        ),
    )
