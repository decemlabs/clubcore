# Phase 27: Expiring-soon Telegram Notifications - Pattern Map

**Mapped:** 2026-05-09
**Files analyzed:** 13 (5 NEW + 8 MODIFIED, plus 3 wording-only doc updates)
**Analogs found:** 13 / 13 (100% — Phase 27 is a near-pure mirror of Phase 18 / 25 / 26 patterns)

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `apps/backend/alembic/versions/0010_notifications.py` | migration | DDL/batch | `apps/backend/alembic/versions/0008_freeze.py` | exact (multi-table create + UNIQUE + index) |
| `apps/backend/app/workers/scheduled/send_expiring_notifications.py` | worker (scheduled cron) | event-driven (ARQ tick → fanout) | `apps/backend/app/workers/scheduled/expire_memberships.py` | exact (only owning module differs) |
| `apps/backend/app/integrations/telegram/copy.py` | integration constants module | static (locked module-level constants + pure helper) | `apps/backend/app/integrations/telegram/handlers.py` (lines 71-87 locked DM block) + `apps/backend/app/integrations/telegram/sender.py` (line 18 RUF001 noqa) | role-match (same locked-Russian-DM convention; new file because separation) |
| `apps/backend/tests/integration/notifications/*.py` (5-6 files) | integration test | request-response + state-assert | `apps/backend/tests/integration/memberships/test_expire_due_memberships_service.py` + `…/conftest.py` | exact (same fixtures, same SAVEPOINT pattern, same clock-injection) |
| `apps/backend/tests/unit/integrations/telegram/test_copy_*.py` (2 files) | unit test | pure-function | `apps/backend/tests/unit/test_audit_taxonomy.py` (literal-string AST gate shape — for variant `pick_variant` determinism); `apps/backend/tests/unit/memberships/test_renewal_constants.py` (constants-only unit shape) | role-match (no existing telegram unit tests; nearest is constants/AST literal-string) |
| `apps/backend/app/modules/memberships/models.py` (+ `MembershipNotification`) | ORM model | static schema | `MembershipFreezePeriod` in same file (lines 188-259) | exact (same file; same Base + Mixin composition; same __table_args__ shape) |
| `apps/backend/app/modules/memberships/repository.py` (+ `find_expiring_candidates`, `ExpiringCandidate`) | repository | CRUD (read-only SELECT) | `expire_due_rows` (lines 408-444) and `find_active_for_client` (lines 338-400) in same file | exact (same `today: date` arg shape; bulk-result returning Sequence) |
| `apps/backend/app/modules/memberships/service.py` (+ `_send_expiring_notifications`) | service (private fanout) | event-driven (per-row side-effect) | `_expire_due_memberships` (lines 1086-1145) in same file | exact (`# noqa: SVC001 caller-owns-txn` mirror) |
| `apps/backend/app/modules/memberships/constants.py` (+ `EXPIRING_KIND_*`) | constants module | static | existing `RENEWAL_STRATEGY_*` constants (lines 31-35) and `MEMBERSHIP_STATUS_TRANSITIONS` (lines 22-29) | exact (same file; same module-level literal pattern) |
| `apps/backend/app/workers/__init__.py` (cron registration) | config (worker bootstrap) | static | existing `expire_memberships` registration (lines 61, 76, 87-95) | exact (same file; one-line additions) |
| `apps/backend/app/core/audit.py` (docstring drift closure lines 67-71) | docstring fix | doc | Phase 26 D-26-26 closure of `membership_renewed` docstring drift (same file, same convention) | exact (same file; identical drift-close shape) |
| `.planning/REQUIREMENTS.md`, `.planning/ROADMAP.md`, `.planning/milestones/v1.3-ROADMAP.md` | doc | wording-only | Phase 25 D-25-01 milestone-roadmap wording update | exact (sed-style mechanical replacement) |

---

## Pattern Assignments

### `apps/backend/alembic/versions/0010_notifications.py` (migration, DDL/batch)

**Analog:** `apps/backend/alembic/versions/0008_freeze.py` (Phase 25 — most recent multi-table migration with create_table + UNIQUE + index pattern)

**Header docstring + revision identifiers** (analog lines 1-35):
```python
"""Phase 27 / NTF-01: expiring-soon notification idempotency table.

Revision ID: 0010_notifications
Revises: 0009_renewal
Create Date: 2026-05-09 00:00:00.000000

Notes:
- The unique constraint `uq_membership_notifications_membership_kind` is
  the single source of truth for cron idempotency (D-27-15). Helper code
  in `app/modules/memberships/service.py:_send_expiring_notifications`
  catches IntegrityError on this constraint to skip race-duplicates.
- Constraint name literal-ref'd? D-27-15: planner finalises whether to
  add to alembic/env.py:_include_object (mirrors Phase 25 D-25-22 — only
  literal-ref'd constraint names go there).
- Downgrade DROPs the table — disaster recovery only; loses idempotency
  history (worst case: client receives a duplicate DM in the next 7d/3d/1d
  window after an upgrade-then-downgrade cycle).
- Alembic chain context: 0007_status_taxonomy → 0008_freeze → 0009_renewal
  → 0010_notifications (Phase 27).
"""

from __future__ import annotations
from collections.abc import Sequence
import sqlalchemy as sa
from alembic import op

revision: str = "0010_notifications"
down_revision: str | None = "0009_renewal"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None
```

**`upgrade()` shape — copy from `0008_freeze.py:74-125`:**
```python
def upgrade() -> None:
    # 1) CREATE TABLE membership_notifications (single new table — Phase 27 NTF-01)
    op.create_table(
        "membership_notifications",
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("membership_id", sa.UUID(), nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column(
            "sent_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("telegram_chat_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_membership_notifications")),
        sa.ForeignKeyConstraint(
            ["membership_id"],
            ["memberships.id"],
            name=op.f("fk_membership_notifications_membership_id_memberships"),
            ondelete="CASCADE",  # D-27-02: cascade — DBA-direct hard-delete drops history
        ),
        sa.CheckConstraint(
            "kind IN ('expiring_7d', 'expiring_3d', 'expiring_1d')",
            name=op.f("ck_membership_notifications_kind"),
        ),
    )

    # 2) UNIQUE constraint on (membership_id, kind) — idempotency single source of truth.
    op.create_unique_constraint(
        "uq_membership_notifications_membership_kind",
        "membership_notifications",
        ["membership_id", "kind"],
    )

    # 3) Single-column index for forensic per-membership lookup.
    op.create_index(
        op.f("ix_membership_notifications_membership_id"),
        "membership_notifications",
        ["membership_id"],
    )
```

**`downgrade()` reverse-order pattern — copy from `0008_freeze.py:128-144`:**
```python
def downgrade() -> None:
    """Reverse upgrade in reverse order — disaster recovery only (D-27-03)."""
    op.drop_index(
        op.f("ix_membership_notifications_membership_id"),
        table_name="membership_notifications",
    )
    op.drop_constraint(
        "uq_membership_notifications_membership_kind",
        "membership_notifications",
        type_="unique",
    )
    op.drop_table("membership_notifications")
```

---

### `apps/backend/app/workers/scheduled/send_expiring_notifications.py` (worker, event-driven)

**Analog:** `apps/backend/app/workers/scheduled/expire_memberships.py` (Phase 18 — full file, 73 lines; Phase 27 mirrors 1:1 except owning module + telegram integration imports)

**Module-level docstring header** (analog lines 1-28):
```python
"""ARQ scheduled job: send expiring-soon Telegram DMs to clients (Phase 27 NTF-02).

Per Phase 7 D-06 / Phase 18 D-09 / Phase 27 D-27-06: this worker file MAY import
`app.modules.memberships.service` AND `app.integrations.telegram.{sender,copy,bot}`.
The first is the single owning-module exception; the integrations imports are
unrestricted (workers may freely call app.integrations.* per workers/__init__.py:7).

Transaction ownership (Phase 27 D-27-07 pattern b — multi-session):
  - Read session for SELECT of candidates via repository.find_expiring_candidates
  - Per successful DM: separate write session opens, INSERTs membership_notifications
    row + audit.emit + commit + closes. Failed sends open NO write session.
  - The service helper `_send_expiring_notifications` carries `# noqa: SVC001
    caller-owns-txn` (Phase 27 D-27-09; mirrors Phase 18 _expire_due_memberships).

Observability (Phase 18 CD-03 / Phase 27 D-27-XX): emits one structlog INFO
`send_expiring_notifications_complete count=N` AFTER the helper returns.
Locks the `<job_name>_complete count=N` summary-event convention (Phase 18
specifics line 195).
"""
```

**Imports + logger** (analog lines 30-38):
```python
from __future__ import annotations
from typing import Any

import structlog

from app.integrations.telegram import copy as telegram_copy
from app.integrations.telegram import sender as telegram_sender
from app.integrations.telegram.bot import build_bot  # planner: see D-27-06 — verify build_bot exists; if not, add it OR inline Bot(token=...)
from app.modules.memberships import service as memberships_service

_log = structlog.get_logger("workers.scheduled.send_expiring_notifications")
```

**Public coroutine** (analog lines 41-72):
```python
async def send_expiring_notifications(ctx: dict[str, Any]) -> int:
    """Send 7d/3d/1d expiring DMs; return count of successful sends.

    Args:
        ctx: ARQ job context dict. Required keys:
            - ctx["sessionmaker"]: `async_sessionmaker[AsyncSession]` from on_startup.
            - ctx["job_id"], ctx["function_name"]: bound on structlog contextvars.

    Returns:
        int — count of successful DM sends on this run. Each success ⇒ one
        membership_notifications row inserted + one audit_log row emitted.
        ARQ writes this count into its result store automatically.
    """
    session_factory = ctx["sessionmaker"]
    bot = build_bot()  # OR inline Bot(token=settings.telegram_bot_token) per D-27-06
    count = await memberships_service._send_expiring_notifications(
        session_factory,
        bot=bot,
        sender=telegram_sender,
        copy_module=telegram_copy,
    )
    _log.info("send_expiring_notifications_complete", count=count)
    return count
```

**Key shape contract** (from analog `expire_memberships.py:64-71`): summary log AFTER the helper call returns; payload carries only `count` (job_id/job_name on contextvars stack via `on_job_start`); event name follows `<job_name>_complete` convention.

---

### `apps/backend/app/integrations/telegram/copy.py` (integration constants module, static)

**Primary analog (locked DM constants pattern):** `apps/backend/app/integrations/telegram/handlers.py:71-87` (Phase 20 locked Russian DMs)
**Secondary analog (RUF001 noqa convention):** `apps/backend/app/integrations/telegram/sender.py:18`

**RUF001 noqa pattern** (`sender.py` line 18 verbatim):
```python
# Russian DM body -- locked copy per CONTEXT line 253. No i18n framework (RU/CIS only).
# RUF001 disabled: Cyrillic letters are intentional (Russian-only product per PROJECT.md).
_OTP_DM_TEMPLATE = "Ваш код: {code}\nДействителен 5 минут."  # noqa: RUF001
```

**Locked-block pattern** (`handlers.py:71-87`):
```python
# Russian copy -- locked per specifics line 253. Single-language by design.
_DM_STRANGER = (
    "Этот Telegram не привязан к аккаунту Sportzal. "
    "Обратитесь к администратору."
)
_DM_REPLAY = "Этот код уже использован, запросите новый."

# Phase 20 — locked Russian DM copy per AUTH-TG-11. Owner-signed-off (gated in 20-03).
# Phase 22 D-22-11 — owner sign-off received (Option B: special-case zero).
_DM_NO_MEMBERSHIP = "У вас нет активного абонемента. Обратитесь к администратору."  # noqa: RUF001
_DM_DUPLICATE = "Вы уже отмечались сегодня."
```

**Phase 27 `copy.py` shape** (D-27-10; reuses both conventions above):
```python
"""Locked Russian DM templates for Phase 27 expiring-soon notifications (NTF-COPY-01).

6 templates × 2 variants × 3 windows. Anti-oracle pattern (v1.2 D-5 / Phase 20):
per-client deterministic A/B variant selection prevents send-pattern fingerprinting.

Owner sign-off recorded in PROJECT.md Key Decisions for v1.3 BEFORE Phase 27 merge
(D-27-11 — mirrors Phase 20 D-20-9 / D-5 sign-off pattern). Modifying these strings
requires a new owner sign-off entry.
"""
from __future__ import annotations
from datetime import date
from typing import Literal
from uuid import UUID

Kind = Literal["expiring_7d", "expiring_3d", "expiring_1d"]
Variant = Literal["A", "B"]

# Phase 27 NTF-COPY-01 — locked Russian DM copy. Owner-signed-off (D-27-11).
# RUF001 disabled: Cyrillic letters are intentional (Russian-only product).
EXPIRING_7D_VARIANT_A = "Привет! Ваш абонемент истекает {end_date}. Самое время продлить — обратитесь к администратору."  # noqa: RUF001
EXPIRING_7D_VARIANT_B = "Напоминаем: ваш абонемент действует до {end_date}. Продление через администратора."  # noqa: RUF001
# … 4 more
```

**Pure-function helper pattern** (mirrors `handlers.py:101-116` `_hash_token_for_log` shape — pure stdlib helper, no imports beyond stdlib + types):
```python
def pick_variant(client_id: UUID) -> Variant:
    """Deterministic A/B selection per client (Phase 27 D-27-10 anti-oracle).

    UUIDv4 first byte from os.urandom is uniformly random ⇒ ~50/50 split,
    stable across processes / restarts / time. NOT `hash(client_id)` — that
    is salted with PYTHONHASHSEED and would yield different variants per
    worker run (CONTEXT.md Risks/Watchpoints — variant fingerprint discipline).
    """
    return "A" if (client_id.bytes[0] & 1) == 0 else "B"
```

---

### `apps/backend/app/modules/memberships/models.py` — adds `MembershipNotification` (ORM, static schema)

**Analog:** `MembershipFreezePeriod` (lines 188-259 in same file — Phase 25 added this; identical shape Phase 27 should mirror)

**Class composition + tablename pattern** (`models.py:188-214`):
```python
class MembershipFreezePeriod(Base, UUIDPkMixin, TimestampMixin):
    """Membership freeze period — open while ended_at IS NULL (Phase 25 MEM-FRZ-02).

    Composition: Base + UUIDPkMixin + TimestampMixin (NO SoftDeleteMixin —
    lifecycle is encoded by `ended_at IS NULL` per D-25-04).
    …
    DB-level invariants:
    - FK fk_membership_freeze_periods_membership_id_memberships ON DELETE RESTRICT…
    - Partial unique index uq_membership_freeze_periods_active_per_membership …
      The constraint name is literal-ref'd by service.py:_is_already_frozen_conflict
      (D-25-22). Installed via raw op.execute() in the migration; mirrored here in
      __table_args__ for ORM awareness; suppressed in alembic/env.py:_include_object
      to keep autogenerate clean.
    """

    __tablename__ = "membership_freeze_periods"
```

**`__table_args__` shape (mirroring constraints from migration)** (`models.py:252-259`):
```python
    __table_args__ = (
        Index(
            "uq_membership_freeze_periods_active_per_membership",
            "membership_id",
            unique=True,
            postgresql_where=text("ended_at IS NULL"),
        ),
    )
```

**Phase 27 `MembershipNotification` to add (after `MembershipFreezePeriod` block, ~line 260+):**
```python
class MembershipNotification(Base, UUIDPkMixin, TimestampMixin):
    """Idempotency record for expiring-soon Telegram DM (Phase 27 NTF-01).

    Composition: Base + UUIDPkMixin + TimestampMixin (NO SoftDeleteMixin —
    rows are append-only; the (membership_id, kind) UNIQUE is the
    single source of truth for cron idempotency D-27-15).

    DB-level invariants:
    - kind IN ('expiring_7d', 'expiring_3d', 'expiring_1d') (CHECK ck_membership_notifications_kind).
    - FK fk_membership_notifications_membership_id_memberships ON DELETE CASCADE
      to memberships.id — DBA-direct hard-delete drops history (D-27-02).
    - UNIQUE (membership_id, kind) — single source of truth for cron idempotency.
      Catches IntegrityError in service.py:_send_expiring_notifications race path
      (D-27-15). NOT literal-ref'd by service code (no constraint-name discriminator
      needed; the entire UNIQUE family is treated uniformly), so NO entry added
      to alembic/env.py:_include_object.
    """

    __tablename__ = "membership_notifications"

    membership_id: Mapped[UUIDType] = mapped_column(…)
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"), nullable=False)
    telegram_chat_id: Mapped[int] = mapped_column(BigInteger, nullable=False)

    __table_args__ = (
        CheckConstraint(
            "kind IN ('expiring_7d', 'expiring_3d', 'expiring_1d')",
            name="kind",
        ),
        # NAMING_CONVENTION expands to uq_membership_notifications_membership_id_kind
        # — match migration's explicit name OR rename migration to align.
        UniqueConstraint("membership_id", "kind", name="uq_membership_notifications_membership_kind"),
    )
```

---

### `apps/backend/app/modules/memberships/repository.py` — adds `find_expiring_candidates` + `ExpiringCandidate` (repository, read-only CRUD)

**Analog (signature shape):** `expire_due_rows` (lines 408-444) and `find_active_for_client` (lines 338-400)

**`today: date` arg + return-Sequence pattern** (`repository.py:408-444`):
```python
async def expire_due_rows(
    session: AsyncSession, today: date
) -> Sequence[Row[tuple[UUID, UUID]]]:
    """Bulk-flip overdue active memberships to expired (Phase 18 D-01 / D-04 / ARQ-02).

    `today` is a `date` (not `CURRENT_DATE`) so the comparison is TZ-unambiguous
    even though the worker container runs `TZ=UTC` (Phase 18 D-05). Production
    callers pass `today=datetime.now(ZoneInfo("Europe/Moscow")).date()`; tests
    pass an explicit `today` for determinism.
    """
    stmt = (
        update(Membership)
        .where(Membership.end_date < today, Membership.status == "active")
        .values(status="expired")
        .returning(Membership.id, Membership.client_id)
    )
    result = await session.execute(stmt)
    return result.all()
```

**Phase 27 `ExpiringCandidate` + `find_expiring_candidates` shape (D-27-18 / D-27-19):**
```python
@dataclass(frozen=True)
class ExpiringCandidate:
    """A membership eligible for expiring-soon DM (Phase 27 NTF-02 / D-27-18).

    `kind` is the suffix of the audit event name AND the unique-index key.
    `chat_id` is `client.telegram_user_id` snapshot (D-27-04 — Telegram private DM
    convention chat_id == user_id).
    """
    membership_id: UUID
    client_id: UUID
    end_date: date
    chat_id: int
    kind: str  # one of EXPIRING_KIND_{7,3,1}D constants

async def find_expiring_candidates(
    session: AsyncSession,
    *,
    today: date,
) -> Sequence[ExpiringCandidate]:
    """SELECT membership × client matching one of three expiring windows AND
    lacking the corresponding membership_notifications row (D-27-05).

    Cross-module note (D-27-19): import-linter forbids
    `from app.modules.clients.models import Client` here. Use SQLAlchemy
    `text()` fragment for the JOIN against `clients` OR declare a SA Core
    Table for clients ad-hoc. Planner finalises; recommend `text()`.

    Returns a list (not generator) so the worker can iterate without holding
    the session open during DM sends. Phase 27 D-27-07 pattern (b).
    """
    # Planner: choose between
    #   (a) inline sa.text() with named bindparams :today_plus_1/3/7
    #   (b) three separate ORM SELECT(Membership) queries combined with union_all()
    #   (c) single Membership query + CASE expr; clients join via text()
    # Recommend (a) for clarity given cross-module restriction.
```

---

### `apps/backend/app/modules/memberships/service.py` — adds `_send_expiring_notifications` (service, event-driven private fanout)

**Analog:** `_expire_due_memberships` (lines 1086-1145 in same file — Phase 18 reference)

**`# noqa: SVC001 caller-owns-txn` marker pattern** (`service.py:1086-1099`):
```python
async def _expire_due_memberships(  # noqa: SVC001 caller-owns-txn
    session: AsyncSession,
    today: date | None = None,
) -> int:
    """Bulk-flip overdue active memberships to expired + emit per-row audits.

    Phase 18 D-01: this is a private helper consumed ONLY by
    `app.workers.scheduled.expire_memberships:expire_memberships(ctx)`. The
    worker is the transaction owner and calls `await session.commit()` after
    this function returns. The `# noqa: SVC001 caller-owns-txn` marker on the
    def line is the documented opt-out from the AST commit-gate (Phase 15
    INFRA-13 / D-04: marker valid only on private `_`-prefixed helpers; public
    service functions MUST commit themselves). The leading underscore +
    marker is NOT optional — both are required for the gate to pass.
    """
```

**`today=None` Europe/Moscow fallback pattern** (`service.py:1130-1131`):
```python
    if today is None:
        today = datetime.now(ZoneInfo("Europe/Moscow")).date()
```

**Per-row audit literal-event pattern (AST gate compliance)** (`service.py:1133-1145`):
```python
    rows = await repository.expire_due_rows(session, today)

    for membership_id, client_id in rows:
        await audit.emit(
            session,
            "membership_expired",  # LITERAL (Phase 15 INFRA-11 AST gate)
            actor_user_id=None,  # system-driven cron — no human actor
            resource_type="membership",  # LITERAL
            resource_id=membership_id,
            client_id=str(client_id),  # JSONB-serialisable
        )

    return len(rows)
```

**Phase 27 `_send_expiring_notifications` shape (D-27-07/08/09/12/14/15):**
```python
async def _send_expiring_notifications(  # noqa: SVC001 caller-owns-txn
    session_factory: async_sessionmaker[AsyncSession],
    *,
    today: date | None = None,
    bot: Bot,                       # injected for testability
    sender: ModuleType,             # app.integrations.telegram.sender
    copy_module: ModuleType,        # app.integrations.telegram.copy
) -> int:
    """Phase 27 NTF-02 / D-27-09. Caller (worker) owns session_factory; this
    helper opens its own scoped sessions per send (D-27-07 pattern b)."""
    if today is None:
        today = datetime.now(ZoneInfo("Europe/Moscow")).date()

    # 1) Read session for the SELECT.
    async with session_factory() as read_session:
        candidates = await repository.find_expiring_candidates(read_session, today=today)

    sent = 0
    for cand in candidates:
        # 2) Send DM via existing sender boundary (Phase 7/20).
        text = copy_module.render_expiring_dm(
            kind=cand.kind, client_id=cand.client_id, end_date=cand.end_date,
        )
        result = await sender.send_text_dm(bot, cand.chat_id, text)

        # 3) Failure → log + skip (NO row insert, NO audit emit).
        if not result.ok:
            reason = "bot_blocked" if result.blocked else "transient"
            structlog.get_logger("memberships.notifications").warning(
                "expiring_notification_send_failed",
                reason=reason,
                membership_id=str(cand.membership_id),
                client_id=str(cand.client_id),
                telegram_chat_id=cand.chat_id,
                error_msg=result.error,
            )
            continue

        # 4) Success → write session: INSERT + audit.emit + commit (D-27-15 IntegrityError catch).
        async with session_factory() as write_session:
            try:
                write_session.add(MembershipNotification(
                    membership_id=cand.membership_id,
                    kind=cand.kind,
                    telegram_chat_id=cand.chat_id,
                ))
                await _emit_send_event(  # 3-branch literal-string helper per D-27-12
                    write_session,
                    kind=cand.kind,
                    membership_id=cand.membership_id,
                    client_id=cand.client_id,
                    chat_id=cand.chat_id,
                )
                await write_session.commit()
                sent += 1
            except IntegrityError:
                await write_session.rollback()
                structlog.get_logger("memberships.notifications").warning(
                    "expiring_notification_idempotency_conflict",
                    membership_id=str(cand.membership_id),
                    kind=cand.kind,
                    reason="duplicate_row",
                )

    return sent
```

**`_emit_send_event` 3-branch literal-string helper (D-27-12 — AST gate compliance):**
```python
async def _emit_send_event(  # noqa: SVC001 caller-owns-txn
    session: AsyncSession, *, kind: str, membership_id: UUID,
    client_id: UUID, chat_id: int,
) -> None:
    """Three explicit if/elif/else callsites — AST gate forbids dynamic event names."""
    if kind == "expiring_7d":
        await audit.emit(session, "expiring_notification_sent_7d",
                         actor_user_id=None, resource_type="membership",
                         resource_id=membership_id,
                         client_id=str(client_id),
                         telegram_chat_id=chat_id,
                         kind="expiring_7d", channel="telegram")
    elif kind == "expiring_3d":
        await audit.emit(session, "expiring_notification_sent_3d",
                         actor_user_id=None, resource_type="membership",
                         resource_id=membership_id,
                         client_id=str(client_id),
                         telegram_chat_id=chat_id,
                         kind="expiring_3d", channel="telegram")
    else:  # "expiring_1d"
        await audit.emit(session, "expiring_notification_sent_1d",
                         actor_user_id=None, resource_type="membership",
                         resource_id=membership_id,
                         client_id=str(client_id),
                         telegram_chat_id=chat_id,
                         kind="expiring_1d", channel="telegram")
```

---

### `apps/backend/app/modules/memberships/constants.py` — adds `EXPIRING_KIND_*` (constants module, static)

**Analog:** existing `RENEWAL_STRATEGY_*` constants (lines 31-35 in same file)

**Pattern excerpt** (`constants.py:31-41`):
```python
# Phase 26 D-26-13 — start_date strategy literals (audit payload values).
# Captured as module-level constants so tests can assert exact literals; service
# emits these via the audit payload key `start_date_strategy` (D-26-15).
RENEWAL_STRATEGY_FROM_SOURCE_END_DATE = "from_source_end_date"
RENEWAL_STRATEGY_FROM_TODAY_EXPIRED_SOURCE = "from_today_expired_source"

__all__ = [
    "MEMBERSHIP_STATUS_TRANSITIONS",
    "RENEWAL_STRATEGY_FROM_SOURCE_END_DATE",
    "RENEWAL_STRATEGY_FROM_TODAY_EXPIRED_SOURCE",
]
```

**Phase 27 additions (after RENEWAL_STRATEGY_* block, D-27-25):**
```python
# Phase 27 D-27-25 — expiring-soon notification kind literals.
# Long-form per REQUIREMENTS NTF-01 verbatim and forensic-SQL grep simplicity.
EXPIRING_KIND_7D = "expiring_7d"
EXPIRING_KIND_3D = "expiring_3d"
EXPIRING_KIND_1D = "expiring_1d"
EXPIRING_KINDS: tuple[str, ...] = (EXPIRING_KIND_7D, EXPIRING_KIND_3D, EXPIRING_KIND_1D)
```

Append to `__all__` accordingly.

---

### `apps/backend/app/workers/__init__.py` — extend `functions` + `cron_jobs` (config)

**Analog:** existing `expire_memberships` registration (lines 61, 76, 87-95)

**Import pattern** (line 61 verbatim):
```python
from app.workers.scheduled.expire_memberships import expire_memberships
```

**Phase 27 mirrors** (add line 62-ish):
```python
from app.workers.scheduled.send_expiring_notifications import send_expiring_notifications
```

**`functions` registry pattern** (line 76):
```python
functions: ClassVar[list[Any]] = [expire_memberships]
```

**Phase 27 mirror** (D-27-16):
```python
functions: ClassVar[list[Any]] = [expire_memberships, send_expiring_notifications]
```

**`cron_jobs` registry pattern** (lines 87-95):
```python
cron_jobs: ClassVar[list[Any]] = [
    cron(
        expire_memberships,
        hour=3,
        minute=5,
        unique=True,
        keep_result=60,
    ),
]
```

**Phase 27 mirror** (D-27-16; 06:15 Europe/Moscow = 03:15 UTC, 10-min buffer after `expire_memberships`):
```python
cron_jobs: ClassVar[list[Any]] = [
    cron(
        expire_memberships,
        hour=3,
        minute=5,
        unique=True,
        keep_result=60,
    ),
    cron(
        send_expiring_notifications,
        hour=3,
        minute=15,
        unique=True,
        keep_result=60,
    ),
]
```

**`on_startup` invariant** (lines 110-117) auto-passes — no code change there; new function shows up in both `functions` and `cron_jobs` so the assert holds.

---

### `apps/backend/app/core/audit.py` — docstring drift closure lines 67-71 (doc fix)

**Analog (closure pattern):** Phase 26 D-26-26 — same kind of closure for `membership_renewed`. The fix shape: when adding the callsite, update the docstring sketch to match the actual payload kwargs.

**Current state** (`audit.py:67-71`):
```python
  - expiring_notification_sent_7d       {membership_id, client_id, channel}
                                        # 'membership' (Phase 27 — 7-day reminder, ARQ)
  - expiring_notification_sent_3d       {membership_id, client_id, channel}
                                        # 'membership' (Phase 27 — 3-day reminder, ARQ)
  - expiring_notification_sent_1d       {membership_id, client_id, channel}
                                        # 'membership' (Phase 27 — 1-day reminder, ARQ)
```

**Phase 27 D-27-13 fix** (close drift; `membership_id` lives in `resource_id`, not payload — same convention as `membership_expired` line 110-style entries; payload gains `telegram_chat_id` + `kind`):
```python
  - expiring_notification_sent_7d       {client_id, telegram_chat_id, kind, channel}
                                        # 'membership' (Phase 27 — 7-day reminder, ARQ;
                                        # resource_id = membership.id; kind="expiring_7d";
                                        # channel="telegram")
  - expiring_notification_sent_3d       {client_id, telegram_chat_id, kind, channel}
                                        # 'membership' (Phase 27 — 3-day reminder, ARQ;
                                        # resource_id = membership.id; kind="expiring_3d";
                                        # channel="telegram")
  - expiring_notification_sent_1d       {client_id, telegram_chat_id, kind, channel}
                                        # 'membership' (Phase 27 — 1-day reminder, ARQ;
                                        # resource_id = membership.id; kind="expiring_1d";
                                        # channel="telegram")
```

---

### Integration tests under `apps/backend/tests/integration/notifications/` (5-6 NEW files)

**Analog:** `apps/backend/tests/integration/memberships/test_expire_due_memberships_service.py` (Phase 18 reference — 195 lines, exact shape mirror) + `…/conftest.py` (fixtures shared)

**File header docstring pattern** (analog `test_expire_due_memberships_service.py:1-15`):
```python
"""Integration tests for `service._send_expiring_notifications` (Phase 27 NTF-TEST-01..03).

The private orchestrator is the per-cron-tick fanout the worker calls. It calls
`repository.find_expiring_candidates`, sends DMs via the injected sender stub,
and (on success) INSERTs membership_notifications + emits audit.emit per row,
opening a fresh write session per send (Phase 27 D-27-07 pattern b). It DOES
NOT commit the read session (`# noqa: SVC001 caller-owns-txn` on def line).

Behaviours covered:
  1. 7d window happy-path → DM sent, row inserted, audit emitted.
  2. Idempotent re-run → no second DM, no second row.
  3. Frozen / cancelled / expired memberships → skipped at SELECT.
  4. Soft-deleted client / unlinked telegram_user_id → skipped at SELECT.
  5. 403 (bot blocked) → no row, no audit; next-tick retry semantics.
"""
```

**Imports + helpers pattern** (analog lines 17-49):
```python
from __future__ import annotations
from datetime import date, timedelta
from typing import Any
from uuid import UUID

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit_models import AuditLog
from app.modules.memberships import service
from app.modules.memberships.models import MembershipNotification
```

**Test body shape with explicit `today` injection** (analog lines 52-90):
```python
async def test_send_expiring_7d_happy_path(
    authed_client_owner: AsyncClient,
    db_session: AsyncSession,
    make_plan: Any,
    make_membership: Any,
    fake_bot: Any,         # tests provide a fake Bot recording calls
    sender_stub: Any,      # tests provide a sender returning canned SendResult
) -> None:
    today = date(2026, 6, 1)
    plan = await make_plan(name="Notif Happy 7d")
    cid = await _create_client_with_telegram(authed_client_owner, telegram_user_id=123456)
    m = await make_membership(
        client_id=cid, plan=plan, status="active",
        start_date=today - timedelta(days=23),
        end_date=today + timedelta(days=7),
    )
    # Use session_factory pattern; helper opens its own write sessions.
    count = await service._send_expiring_notifications(
        session_factory_fixture, today=today, bot=fake_bot,
        sender=sender_stub, copy_module=telegram_copy,
    )
    assert count == 1

    # Assert row + audit row.
    rows = (await db_session.execute(
        select(MembershipNotification).where(MembershipNotification.membership_id == m.id)
    )).scalars().all()
    assert len(rows) == 1 and rows[0].kind == "expiring_7d"

    audits = (await db_session.execute(
        select(AuditLog).where(
            AuditLog.action == "expiring_notification_sent_7d",
            AuditLog.resource_id == m.id,
        )
    )).scalars().all()
    assert len(audits) == 1
    assert audits[0].payload == {
        "client_id": str(cid),
        "telegram_chat_id": 123456,
        "kind": "expiring_7d",
        "channel": "telegram",
    }
```

**Conftest fixture shape** (analog `tests/integration/memberships/conftest.py:1-71`): reuse `authed_client_owner`, `db_session`, `make_plan`, `make_membership`. Phase 27 needs ADDITIONAL fixtures:
- `fake_bot` — minimal protocol object with async `send_message(chat_id, text)` recording calls.
- `sender_stub` — module-typed stub with `send_text_dm(bot, chat_id, text) -> SendResult`. Tests inject canned results.
- `_create_client_with_telegram` helper — extends `_create_client` to set `clients.telegram_user_id` post-create (or use direct ORM insert in conftest).

Recommend new file `tests/integration/notifications/conftest.py` to host `fake_bot` + `sender_stub` + a `notifications_session_factory` fixture.

---

### Unit tests under `apps/backend/tests/unit/integrations/telegram/` (2 NEW files)

**Analog (closest, since no telegram unit tests exist yet):**
- `apps/backend/tests/unit/test_audit_taxonomy.py` (lines 1-120) — for the AST gate verification shape and unit-test scaffolding.
- `apps/backend/tests/unit/memberships/test_renewal_constants.py` — for constants/pure-function unit shape.

**`test_copy_variant_selection.py` shape (NTF-TEST D-27-20):**
```python
"""Unit tests for app.integrations.telegram.copy.pick_variant (Phase 27 NTF-COPY-01).

`pick_variant(client_id)` MUST be deterministic per UUID (stable across processes
and time — D-27-10 anti-oracle property) and produce ~50/50 split over uniformly
random UUIDv4 inputs (chi-square within tolerance).
"""
from __future__ import annotations
from collections import Counter
from uuid import UUID, uuid4

from app.integrations.telegram.copy import pick_variant


def test_pick_variant_is_deterministic_per_uuid() -> None:
    cid = UUID("12345678-1234-5678-1234-567812345678")
    assert pick_variant(cid) == pick_variant(cid)


def test_pick_variant_split_is_balanced_over_random_uuids() -> None:
    counts: Counter[str] = Counter()
    for _ in range(1000):
        counts[pick_variant(uuid4())] += 1
    # Expect ~500/500; allow ±10% drift (well within chi-square @ p=0.01 for n=1000).
    assert 400 <= counts["A"] <= 600
    assert 400 <= counts["B"] <= 600
```

**`test_copy_render.py` shape:**
```python
"""Unit tests for render_expiring_dm: each (kind, variant) renders the locked
template with the formatted Russian date."""
from __future__ import annotations
from datetime import date
from uuid import UUID

from app.integrations.telegram import copy as telegram_copy

# Pin variant by choosing UUIDs whose byte[0] forces A vs B deterministically.
_UUID_FORCES_A = UUID(bytes=b"\x00" * 16)  # byte[0] & 1 == 0 → "A"
_UUID_FORCES_B = UUID(bytes=b"\x01" + b"\x00" * 15)  # byte[0] & 1 == 1 → "B"


def test_render_7d_variant_a_contains_locked_string() -> None:
    out = telegram_copy.render_expiring_dm(
        kind="expiring_7d", client_id=_UUID_FORCES_A, end_date=date(2026, 5, 16),
    )
    assert "истекает" in out  # noqa: RUF001
```

---

### Doc updates (wording-only — no code analog needed)

| File | Change | D-ref |
|---|---|---|
| `.planning/REQUIREMENTS.md` § "Notifications — Expiring-soon" NTF-01 | `0008_notifications.py` → `0010_notifications.py` | D-27-01 |
| `.planning/ROADMAP.md` § "Phase 27" | `0009_notifications.py` → `0010_notifications.py` | D-27-01 |
| `.planning/milestones/v1.3-ROADMAP.md` § "Phase 27" + § "Notes on dependencies" | `0009` → `0010` (2 hits) | D-27-01 |

Mechanical sed-style replacement; bundle into the same commit that creates `0010_notifications.py`. Mirror Phase 25 D-25-01 milestone-roadmap update.

---

## Shared Patterns

### Worker → service single-owning-module import (cross-cutting D-27-06)
**Source:** `apps/backend/app/workers/scheduled/expire_memberships.py:36` + `apps/backend/app/workers/__init__.py:1-21` (docstring relaxation rationale)
**Apply to:** `send_expiring_notifications.py` worker file
```python
from app.modules.memberships import service as memberships_service
# Plus app.integrations.telegram.* imports (always allowed, not cross-module)
```
**Rule:** Each `app/workers/scheduled/<job>.py` may import EXACTLY ONE owning module's service layer. Cross-module imports remain forbidden inside one scheduled file.

### `# noqa: SVC001 caller-owns-txn` private-helper marker (cross-cutting D-27-09)
**Source:** `apps/backend/app/modules/memberships/service.py:1086` + `:209` (`_build_membership_response`)
**Apply to:** `_send_expiring_notifications` and `_emit_send_event` in service.py
```python
async def _send_expiring_notifications(  # noqa: SVC001 caller-owns-txn
    …
) -> int:
```
**Rule:** Marker valid ONLY on private `_`-prefixed helpers; public service functions MUST commit themselves. Both leading underscore AND noqa marker are required for the SVC001 walker (`tests/unit/test_service_commit_gate.py:167-211`) to pass.

### Audit literal-string callsite + AST gate (cross-cutting D-27-12)
**Source:** `apps/backend/app/modules/memberships/service.py:1136-1143` (`_expire_due_memberships`) + `apps/backend/tests/unit/test_audit_taxonomy.py:103-120` (gate)
**Apply to:** Three Phase 27 callsites — wrap in 3-branch if/elif/else helper `_emit_send_event`
```python
await audit.emit(
    session,
    "expiring_notification_sent_7d",  # LITERAL — gate REJECTS f-strings
    actor_user_id=None,                # cron is actor-less (D-06 documented exception)
    resource_type="membership",        # LITERAL
    resource_id=membership_id,
    client_id=str(client_id),          # JSONB-serialisable
    telegram_chat_id=chat_id,          # int, raw
    kind="expiring_7d",                # forensic convenience (D-27-12)
    channel="telegram",                # extensibility hook (D-27-12)
)
```
**Rule:** Both `event` and `resource_type` MUST be `ast.Constant(str)` at the callsite. Dynamic event names → CI fails. Use 3 explicit if/elif/else branches.

### `today=None` Europe/Moscow injection (cross-cutting D-27-21)
**Source:** `apps/backend/app/modules/memberships/service.py:1130-1131` + `:1076-1077` + Phase 24 D-24-06 (no `freezegun`)
**Apply to:** `_send_expiring_notifications` and `find_expiring_candidates`
```python
if today is None:
    today = datetime.now(ZoneInfo("Europe/Moscow")).date()
```
**Rule:** Production callers omit `today`; tests pass explicit `today=date(2026, 5, 16)` for determinism. NEVER use `freezegun` (Phase 24 D-24-06 precedent).

### `<job_name>_complete count=N` summary log (cross-cutting Phase 18 specifics line 195)
**Source:** `apps/backend/app/workers/scheduled/expire_memberships.py:69-71`
**Apply to:** `send_expiring_notifications.py` worker
```python
_log.info("send_expiring_notifications_complete", count=count)
```
**Rule:** AFTER all per-membership commits (NOT inside the iteration loop). NOT an audit event — payload carries only `count`; `job_id`/`job_name` come for free from `on_job_start` contextvars binding.

### `# noqa: RUF001` Cyrillic-letters discipline (cross-cutting Phase 7 D-07 / Phase 20 D-20-9)
**Source:** `apps/backend/app/integrations/telegram/sender.py:18` + `apps/backend/app/integrations/telegram/handlers.py:85-86`
**Apply to:** All 6 locked Russian DM constants in new `copy.py`
```python
EXPIRING_7D_VARIANT_A = "Привет! Ваш абонемент истекает {end_date}. …"  # noqa: RUF001
```
**Rule:** Per-line `# noqa: RUF001` on every constant containing Cyrillic; ruff RUF001 flags ambiguous unicode and we accept Cyrillic intentionally (Russian-only product per PROJECT.md i18n).

### `import-linter modules-independent` cross-module workaround (cross-cutting D-27-19)
**Source:** import-linter contract; `apps/backend/app/modules/memberships/repository.py` already avoids `from app.modules.clients.models import Client`
**Apply to:** `find_expiring_candidates` SELECT that joins `clients`
**Rule:** memberships.repository MUST NOT `from app.modules.clients.* import …`. Workarounds (planner picks):
- (recommend) `sa.text("JOIN clients c ON c.id = memberships.client_id WHERE c.telegram_user_id IS NOT NULL AND c.deleted_at IS NULL")` fragment composition.
- Alternative: declare a SA Core `Table("clients", metadata, …)` with the 3 columns we need.

### Owner sign-off via PROJECT.md Key Decisions row (cross-cutting D-27-11)
**Source:** v1.2 Phase 20 D-20-9 / D-5; `.planning/PROJECT.md` § "Key Decisions" line 179 (D-20 row)
**Apply to:** New row D-27-OWNER-COPY-LOCK with the 6 signed-off Russian DM templates
**Rule:** Plan agent surfaces 6 draft templates in SUMMARY.md + `human_verification` block in PLAN.md. Code MUST NOT merge until PROJECT.md row appears. Phase 29 (auditor) verifies the row exists.

---

## No Analog Found

None. Phase 27 is a near-pure mirror of established Phase 18 / 25 / 26 patterns. Every new or modified file has a strong analog in the existing codebase.

The closest "weak analog" is the unit-test scaffolding for `tests/unit/integrations/telegram/` — there are no existing telegram unit tests, but the pattern is trivial (pure-function tests with stdlib only) and `tests/unit/test_audit_taxonomy.py` + `tests/unit/memberships/test_renewal_constants.py` give sufficient shape guidance.

---

## Metadata

**Analog search scope:**
- `apps/backend/alembic/versions/` (10 migrations scanned — 0008/0009 strongest matches)
- `apps/backend/app/workers/` (full directory — only one prior scheduled job analog)
- `apps/backend/app/integrations/telegram/` (4 files — sender, handlers, bot, __init__)
- `apps/backend/app/modules/memberships/` (models, repository, service, constants — full path)
- `apps/backend/app/core/audit.py` (full file)
- `apps/backend/tests/integration/memberships/` (29 test files; closest = `test_expire_due_memberships_service.py`)
- `apps/backend/tests/unit/` (top-level + `memberships/` subdir; closest = `test_audit_taxonomy.py`, `memberships/test_renewal_constants.py`)

**Files scanned in detail:** 12 (CONTEXT.md + 11 codebase files)

**Pattern extraction date:** 2026-05-09
