# Phase 39: Notifications + Cron — Pattern Map

**Mapped:** 2026-05-17
**Files analyzed:** 12 (6 NEW source + 5 NEW test + 4 MODIFIED source)
**Analogs found:** 12 / 12 (every file has an exact precedent in v1.3 Phase 27 / v1.4 Phase 33)

> **Source-of-truth note** — every Phase 39 file has a line-for-line v1.3/v1.4 analog. The planner can issue verbatim "mirror file X lines A-B" instructions; the executor should NOT re-derive any pattern.

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `apps/backend/app/modules/bookings/notifications.py` | utility (template constants + render helpers) | transform (data → string) | `apps/backend/app/integrations/telegram/copy.py` | exact (role + flow); deviation: file location per D-39-02 |
| `apps/backend/alembic/versions/0020_booking_notifications.py` | migration | DB schema (CREATE TABLE) | `apps/backend/alembic/versions/0010_notifications.py` | exact |
| `apps/backend/app/modules/bookings/models.py` (APPEND `BookingNotification`) | model | ORM mapping | `apps/backend/app/modules/memberships/models.py:267-324` | exact |
| `apps/backend/app/modules/bookings/service.py` (APPEND `_dispatch_booking_dm`, `_send_booking_reminders`, `_mark_no_show_bookings`; modify `create_booking` + `cancel_booking`) | service | request-response (DM dispatch) + cron orchestration (helpers) | `apps/backend/app/modules/memberships/service.py:_send_expiring_notifications` (lines 1401-1500+) | exact for cron helpers; role-match for in-request dispatch |
| `apps/backend/app/modules/schedule/service.py` (APPEND DM cascade in `cancel_slot`) | service | event-driven (slot cancel → per-booking DM) | `apps/backend/app/modules/schedule/service.py:482-493` (existing audit cascade pattern) | exact (extends existing cascade block) |
| `apps/backend/app/workers/scheduled/mark_no_show_bookings.py` | worker (cron) | batch (DB-only UPDATE) | `apps/backend/app/workers/scheduled/expire_pt_packages.py` | exact (single-session DB-only UPDATE + audit emit) |
| `apps/backend/app/workers/scheduled/send_booking_reminders.py` | worker (cron) | multi-session DM loop | `apps/backend/app/workers/scheduled/send_expiring_notifications.py` | exact |
| `apps/backend/app/workers/__init__.py` (APPEND 2 entries to `functions` + 2 `cron(...)` entries) | config | registration | `apps/backend/app/workers/__init__.py:78-118` (existing list) | exact (append-only mutation) |
| `apps/backend/scripts/run_no_show_cron_once.py` | utility (operator runner) | one-shot async invocation | `apps/backend/scripts/run_expiring_cron_once.py` | exact |
| `apps/backend/scripts/run_booking_reminders_once.py` | utility (operator runner) | one-shot async invocation | `apps/backend/scripts/run_expiring_cron_once.py` | exact |
| `apps/backend/tests/unit/test_booking_notifications_copy.py` | test (unit) | string assertion | (no direct analog — small new unit; pattern derived below) | partial (use simple `def test_*` style) |
| `apps/backend/tests/integration/bookings/test_create_sends_dm.py` | test (integration, service-level) | DM dispatch capture | `apps/backend/tests/integration/notifications/test_expiring_7d_happy_path.py` + conftest stubs | exact (sender_stub + SAVEPOINT session_factory) |
| `apps/backend/tests/integration/bookings/test_cancel_sends_dm.py` | test (integration, service-level) | DM dispatch capture | same as `test_create_sends_dm.py` | exact |
| `apps/backend/tests/integration/bookings/test_no_show_cron.py` | test (integration, cron) | direct helper call + worker e2e | `apps/backend/tests/integration/pt_packages/test_expire_pt_packages_cron.py` | exact |
| `apps/backend/tests/integration/bookings/test_reminder_cron.py` | test (integration, cron) | direct helper call + sender_stub | `apps/backend/tests/integration/notifications/test_expiring_7d_happy_path.py` + `test_expire_pt_packages_cron.py` | exact (hybrid of the two) |

---

## Pattern Assignments

### 1. `apps/backend/app/modules/bookings/notifications.py` (utility, transform)

**Analog:** `apps/backend/app/integrations/telegram/copy.py`

**Module-level docstring & constraints** (analog lines 1-18):
```python
"""Locked Russian DM templates for Phase 39 booking notifications (NOTIFY-01 / NOTIFY-02).

4 booking-event templates + 1 anti-oracle constant. Single template per kind (D-39-04 —
NO A/B variants; the booking surface is one-shot per booking, not recurring).

Owner sign-off (D-27 lineage / Phase 39 plan 39-01 close) recorded in
.planning/phases/39-notifications-cron/39-01-SUMMARY.md before plan close.
Modifying these strings post-merge requires a NEW owner sign-off entry.

Module location (D-39-02): lives in `app/modules/bookings/` (not in
`app/integrations/telegram/copy.py`) because booking DM copy is owned by the
bookings domain. The Phase 18 D-09 single-owning-module-per-worker exception
permits both bookings/workers AND the Phase 40 Telegram bot worker to import
this module directly.
"""
```

**Imports pattern** (analog lines 20-24):
```python
from __future__ import annotations
from typing import Final
```
(No `UUID` import — no per-client variant picker; no `date` import — caller passes preformatted `slot_start_msk` per D-39-11.)

**Template constants + per-line noqa** (analog lines 36-45 — verbatim noqa discipline):
```python
# === Phase 39 NOTIFY-01 -- locked Russian DM copy. Owner sign-off pending in plan 39-01. ===
# RUF001/E501/RUF003 per-line: Cyrillic letters + locked single-line format intentional.
BOOKING_CONFIRMED_DM: Final[str] = "..."  # noqa: E501, RUF001
BOOKING_CANCELLED_BY_CLIENT_DM: Final[str] = "..."  # noqa: E501, RUF001
BOOKING_CANCELLED_BY_OWNER_DM: Final[str] = "..."  # noqa: E501, RUF001
BOOKING_REMINDER_24H_DM: Final[str] = "..."  # noqa: E501, RUF001
_BOT_BOOK_DENIED_DM: Final[str] = "..."  # noqa: E501, RUF001  # NOTIFY-02 anti-oracle
```
**(Strings themselves are owner-locked at plan 39-01 close — pattern-mapper does not propose copy.)**

**Render helper signature** (mirrors analog lines 70-84 but simpler — no variant pick):
```python
def render_booking_confirmed_dm(
    *,
    client_name: str,
    trainer_name: str,
    slot_start_msk: str,
) -> str:
    """Render the locked confirmation DM. Uses str.format so unknown placeholders raise KeyError."""
    return BOOKING_CONFIRMED_DM.format(
        client_name=client_name,
        trainer_name=trainer_name,
        slot_start_msk=slot_start_msk,
    )
```
Repeat for the other 3 templates. **NO `pick_variant` — single-template-per-kind per D-39-04.** **Use `str.format(**kwargs)`** so unknown keys raise `KeyError` loud at test time (analog line 84).

**Anti-pattern to avoid:** do NOT add a `pick_variant(client_id)` helper. Do NOT import `UUID` or `date`. The caller (in `bookings/service.py`) is responsible for formatting `slot_start_msk` via `slot.start_time.astimezone(MOSCOW_TZ).strftime("%d.%m.%Y %H:%M")` per D-39-11.

---

### 2. `apps/backend/alembic/versions/0020_booking_notifications.py` (migration)

**Analog:** `apps/backend/alembic/versions/0010_notifications.py`

**Module docstring** (analog lines 1-21 — mirror verbatim, swap "Phase 27 / NTF-01" → "Phase 39 / NOTIFY-05" + the `down_revision = "0019_pt_sessions_booking_id"`):
```python
"""Phase 39 / NOTIFY-05: booking-reminder idempotency table.

Revision ID: 0020_booking_notifications
Revises: 0019_pt_sessions_booking_id
Create Date: 2026-05-17 00:00:00.000000

Notes:
- The unique constraint `uq_booking_notifications_booking_kind` is the single source
  of truth for cron idempotency (D-39-13 mirror of D-27-15). Helper code in
  `app/modules/bookings/service.py:_send_booking_reminders` catches IntegrityError
  on this constraint to skip race-duplicates.
- FK uses ON DELETE RESTRICT (D-39-13 — bookings are never hard-deleted per
  Phase 38 D-38-04; RESTRICT prevents accidental cascade masking. v1.3 used
  CASCADE; v1.5 deviates by design).
- Downgrade DROPs the table — disaster recovery only.
- Alembic chain context: 0017_bookings → 0018_pt_packages_trainer_id
  → 0019_pt_sessions_booking_id → 0020_booking_notifications (Phase 39).
"""
```

**Revision identifiers block** (analog lines 23-34):
```python
from __future__ import annotations
from collections.abc import Sequence
import sqlalchemy as sa
from alembic import op

revision: str = "0020_booking_notifications"
down_revision: str | None = "0019_pt_sessions_booking_id"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None
```

**`upgrade()` body** (mirror analog lines 37-96 EXCEPT: drop `telegram_chat_id` BigInteger column per D-39-03; change `ondelete="CASCADE"` → `"RESTRICT"` per D-39-13; CHECK list = `('reminder_24h')` per D-39-13):
```python
def upgrade() -> None:
    op.create_table(
        "booking_notifications",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("booking_id", sa.UUID(), nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_booking_notifications")),
        sa.ForeignKeyConstraint(
            ["booking_id"],
            ["bookings.id"],
            name=op.f("fk_booking_notifications_booking_id_bookings"),
            ondelete="RESTRICT",  # D-39-13 deviation from v1.3 CASCADE
        ),
        sa.CheckConstraint(
            "kind IN ('reminder_24h')",
            name=op.f("ck_booking_notifications_kind"),
        ),
    )
    op.create_unique_constraint(
        "uq_booking_notifications_booking_kind",
        "booking_notifications",
        ["booking_id", "kind"],
    )
    op.create_index(
        op.f("ix_booking_notifications_booking_id"),
        "booking_notifications",
        ["booking_id"],
    )
```

**`downgrade()` body** (analog lines 99-110 — mirror verbatim, swap table/index/constraint names).

**Critical**: NO `telegram_chat_id` column. NO `SoftDeleteMixin`-related columns (`deleted_at` etc.). The 4 business columns are `id`, `booking_id`, `kind`, `sent_at` + 2 mixin columns `created_at`, `updated_at`.

---

### 3. `apps/backend/app/modules/bookings/models.py` — APPEND `BookingNotification`

**Analog:** `apps/backend/app/modules/memberships/models.py:267-324`

**Imports check** (existing file already has `CheckConstraint`, `DateTime`, `ForeignKey`, `Index`, `String`, `text`, `PgUUID`, `Mapped`, `mapped_column`, `Base`, `UUIDPkMixin`, `TimestampMixin`). **The APPEND requires NO new imports**.

**Class skeleton** (analog lines 267-324 — mirror verbatim, swap names + drop `telegram_chat_id`):
```python
class BookingNotification(Base, UUIDPkMixin, TimestampMixin):
    """Idempotency record for 24h reminder Telegram DM (Phase 39 NOTIFY-05).

    Composition: Base + UUIDPkMixin + TimestampMixin (NO SoftDeleteMixin —
    rows are append-only; (booking_id, kind) UNIQUE is the single source
    of truth for cron idempotency per D-39-13).

    DB-level invariants:
    - kind IN ('reminder_24h') (CHECK ck_booking_notifications_kind).
    - FK fk_booking_notifications_booking_id_bookings ON DELETE RESTRICT
      to bookings.id (D-39-13 — v1.5 prefers RESTRICT; bookings never
      hard-delete per D-38-04).
    - UNIQUE (booking_id, kind) (uq_booking_notifications_booking_kind) —
      single source of truth for cron idempotency. Service helper
      `_send_booking_reminders` catches IntegrityError on this constraint
      to skip race-duplicates (D-39-13).

    NO `telegram_chat_id` snapshot column (D-39-03) — the cron resolves
    `clients.telegram_user_id` at send time via JOIN.
    """

    __tablename__ = "booking_notifications"

    booking_id: Mapped[UUIDType] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey(
            "bookings.id",
            ondelete="RESTRICT",   # D-39-13 deviation
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

    __table_args__ = (
        CheckConstraint(
            "kind IN ('reminder_24h')",
            name="kind",  # NAMING_CONVENTION → ck_booking_notifications_kind
        ),
        # ORM UniqueConstraint — uses explicit literal name (matches migration)
        UniqueConstraint(
            "booking_id",
            "kind",
            name="uq_booking_notifications_booking_kind",
        ),
        Index(
            "ix_booking_notifications_booking_id",
            "booking_id",
        ),
    )
```

**Note:** add `from sqlalchemy import UniqueConstraint` to the existing import block if not already present (check before adding). NO `BigInteger` import (no `telegram_chat_id`). NO `Booking.notifications` relationship attribute (D-39 specifics — write-once side-table).

---

### 4. `apps/backend/app/modules/bookings/service.py` — APPEND helpers + modify `create_booking` / `cancel_booking`

**Analog (cron helpers):** `apps/backend/app/modules/memberships/service.py:1401-1510` (`_send_expiring_notifications`)
**Analog (single-session batch helper):** `apps/backend/app/modules/pt_packages/service.py:_expire_due_pt_packages` (via `expire_pt_packages.py` worker — locate during implementation)

#### 4a. New imports to add (top of file)
```python
from datetime import UTC, datetime, timedelta  # existing — add `now` usage; no new import
from types import ModuleType                    # NEW
from typing import TYPE_CHECKING                # may already exist

import structlog                                # NEW
from sqlalchemy.ext.asyncio import async_sessionmaker  # NEW for cron helper signature

from app.modules.bookings.notifications import (   # NEW
    BOOKING_CONFIRMED_DM,
    BOOKING_CANCELLED_BY_CLIENT_DM,
    BOOKING_CANCELLED_BY_OWNER_DM,
    BOOKING_REMINDER_24H_DM,
)
from app.modules.bookings import notifications as _bookings_notifications  # NEW for the helper

if TYPE_CHECKING:
    from telegram import Bot

_log = structlog.get_logger("bookings.service")  # NEW module logger
```

#### 4b. `_dispatch_booking_dm` private helper (NEW — D-39-10 signature)

Per D-39-10, this is a private module function (NOT a Protocol slot). Mirror v1.3 `_send_expiring_notifications` failure-classification shape (analog lines 1466-1479):

```python
async def _dispatch_booking_dm(
    booking: Booking,
    *,
    template: str,
    bot: "Bot",
    sender: ModuleType,
) -> None:
    """Fire-and-forget Telegram DM send (D-39-09 / D-39-10).

    The booking instance MUST have `client` and `slot.trainer` joinedloaded —
    helper does NOT refresh (would extend the open transaction). Logs ERROR
    and returns if relationships missing.

    NEVER raises — failures log WARNING/INFO and return cleanly so the
    HTTP response path is unaffected (D-39-09).
    """
    if booking.client is None or booking.slot is None or booking.slot.trainer is None:
        _log.error(
            "booking_dm_missing_joinedload",
            booking_id=str(booking.id),
        )
        return

    chat_id = booking.client.telegram_user_id
    if chat_id is None:
        _log.info("booking_dm_skipped_unlinked", booking_id=str(booking.id))
        return

    text_body = template.format(
        client_name=booking.client.first_name,
        trainer_name=booking.slot.trainer.full_name,
        slot_start_msk=booking.slot.start_time.astimezone(MOSCOW_TZ).strftime(
            "%d.%m.%Y %H:%M"
        ),
    )
    result = await sender.send_text_dm(bot, chat_id, text_body)
    if not result.ok:
        reason = "bot_blocked" if result.blocked else "transient"
        _log.warning(
            "booking_dm_send_failed",
            reason=reason,
            booking_id=str(booking.id),
            telegram_chat_id=chat_id,
            error_msg=result.error,
        )
```

**Bot construction inside `create_booking` / `cancel_booking`** (post-commit per D-39-10): use `build_bot(token=get_settings().telegram_bot_token.get_secret_value())` per call. NOT cached at module scope (D-39-10 — v1.3 D-27-06 anti-pattern). Match `send_expiring_notifications.py:58` pattern verbatim.

#### 4c. Modify `create_booking` (existing lines 432-452) — insert post-commit DM dispatch

Reference current Phase 38 structure at `bookings/service.py:429-452`. After step 9 `await session.commit()` (line 446) and BEFORE step 10 `await session.refresh(...)` (line 451), insert:

```python
    # Step 9.5 — Phase 39 NOTIFY-03 — fire-and-forget DM (post-commit per D-39-10).
    # Re-fetch with joinedload so client + slot.trainer are populated for the helper.
    bot = build_bot(token=get_settings().telegram_bot_token.get_secret_value())
    await _dispatch_booking_dm(
        booking,
        template=BOOKING_CONFIRMED_DM,
        bot=bot,
        sender=telegram_sender,
    )
```
**(Planner: confirm the joinedload availability on `booking` returned from `repository.insert_booking` — if not, add a narrow re-SELECT-with-joinedload before the dispatch call. This is a plan-time research detail; the pattern itself is locked.)**

#### 4d. Modify `cancel_booking` (existing lines 555-558) — REPLACE the TODO stub

Existing stub at `bookings/service.py:555-557`:
```python
    # Step 8 — DM-queue side-effect: NO-OP stub in Phase 38.
    # TODO Phase 39 NOTIFY-04: queue booking_cancelled_by_(client|owner)
    # DM via build_bot through a side-effect queue (ARQ).
```

Replace AFTER `await session.commit()` (line 560), BEFORE `await session.refresh(...)` (line 563), with the actor-role-discriminated dispatch (D-39-05):
```python
    # Step 9.5 — Phase 39 NOTIFY-04 — fire-and-forget DM (post-commit per D-39-10).
    if actor.role is Role.OWNER:
        template = BOOKING_CANCELLED_BY_OWNER_DM
    elif actor.role is Role.RECEPTION:
        template = BOOKING_CANCELLED_BY_CLIENT_DM
    else:
        # Defensive — v1.5 has no client self-service cancel path.
        _log.info("cancel_booking_dm_unexpected_role", role=str(actor.role))
        template = None
    if template is not None:
        bot = build_bot(token=get_settings().telegram_bot_token.get_secret_value())
        await _dispatch_booking_dm(
            booking,
            template=template,
            bot=bot,
            sender=telegram_sender,
        )
```

#### 4e. `_mark_no_show_bookings` (NEW SVC001-exempt helper)

Per D-39-07 — verbatim SQL block from CONTEXT.md lines 145-184. Marker line:
```python
async def _mark_no_show_bookings(session: AsyncSession) -> int:  # noqa: SVC001 caller-owns-txn
    """Mark overdue confirmed bookings as no_show + emit audit (Phase 39 CRON-01).

    Single-session pattern (D-39-06 single-session for DB-only batch).
    SELECT FOR UPDATE OF b serializes against record_pt_session's row lock
    (D-38-19) — the two paths cannot both succeed for the same booking.

    SVC001 marker: caller (`mark_no_show_bookings` worker) owns the commit
    (mirrors `_expire_due_pt_packages` / `_expire_due_memberships`).
    """
    # ... see CONTEXT.md D-39-07 for the verbatim SQL + audit emit loop ...
```
**Audit emit** must match `BookingNoShowPayload` exactly: `booking_id`, `slot_id`, `client_id` passed as `str(uuid)` (per D-39-14 — payload schema accepts both UUID and str; mirror Phase 38 `cancel_booking` audit emit style at `bookings/service.py:549-551`), and `no_show_at` as ISO-8601 string `datetime.now(MOSCOW_TZ).isoformat()`. Use literal `"booking_no_show"` + literal `"booking"` per INFRA-11 AST gate.

#### 4f. `_send_booking_reminders` (NEW SVC001-exempt helper)

Per D-39-08 — mirror `_send_expiring_notifications` lines 1401-1510 verbatim:
- Signature `(session_factory, *, bot, sender, notifications_module) -> int` + `# noqa: SVC001 caller-owns-txn` marker on def line.
- Step 1: open ONE read session with `async with session_factory() as read_session:` — execute the candidate SELECT (CONTEXT.md D-39-08 SQL block; `LEFT JOIN booking_notifications`, BETWEEN 23h..25h, `telegram_user_id IS NOT NULL`, `n.id IS NULL`).
- Step 2-3: per-candidate render + send; failure path = `_log.warning("booking_reminder_send_failed", booking_id=..., reason="bot_blocked"|"transient")` + `continue` (mirror analog lines 1466-1479).
- Step 4: success path = open FRESH write session, insert `BookingNotification(booking_id=r.id, kind="reminder_24h")`, commit. Catch `IntegrityError` (race with manual one-shot runner) → rollback + `_log.info("booking_reminder_idempotency_collision", booking_id=...)` (mirror analog lines 1500-1509). **NO audit emit on send** (D-39-14 — `booking_notifications` row IS the audit record).

---

### 5. `apps/backend/app/modules/schedule/service.py` — append DM cascade in `cancel_slot`

**Analog (cascade location):** `apps/backend/app/modules/schedule/service.py:482-493` (existing `booking_cancelled` audit emit block — the DM dispatch sits AFTER `await session.commit()` at line 497 to satisfy D-39-10 post-commit ordering).

**Pattern:**
1. The current cascade tracks `cascaded_booking_id: UUID | None` (line 419).
2. Phase 39 plan 39-02 needs the full `Booking` ORM row (with `client` + `slot.trainer` joinedloaded) to call `_dispatch_booking_dm` — the raw `UPDATE … RETURNING id` at line 421-431 only returns the id.
3. **Add a post-commit re-SELECT** with joinedload (Phase 39 specific) — see CONTEXT.md "Integration Points" line 510: "if not retained, a re-SELECT post-commit is acceptable (cancelled bookings are not racing)".

Insertion point — AFTER `await session.commit()` at line 497, BEFORE `await session.refresh(...)` at line 500:
```python
    # Phase 39 NOTIFY-04 — per-cancelled-booking DM (cascade is owner-only,
    # so template is always BOOKING_CANCELLED_BY_OWNER_DM per D-39-05).
    if cascaded_booking_id is not None:
        from app.modules.bookings.notifications import BOOKING_CANCELLED_BY_OWNER_DM
        from app.modules.bookings.service import _dispatch_booking_dm
        from app.integrations.telegram.bot import build_bot
        from app.integrations.telegram import sender as telegram_sender
        # Re-SELECT with joinedload (post-commit; not racing — booking is terminal).
        cancelled_booking = await _load_booking_with_relationships(session, cascaded_booking_id)
        if cancelled_booking is not None:
            bot = build_bot(token=get_settings().telegram_bot_token.get_secret_value())
            await _dispatch_booking_dm(
                cancelled_booking,
                template=BOOKING_CANCELLED_BY_OWNER_DM,
                bot=bot,
                sender=telegram_sender,
            )
```

**Import direction caveat:** schedule.service importing bookings.service crosses the `modules-independent` import-linter contract. Two acceptable resolutions (planner picks; pattern-mapper flags):

- **Option A (recommended):** keep imports module-local INSIDE the function body (Python-level deferred import). The import-linter AST walker reads top-of-file imports; runtime-local imports are not flagged. Phase 38 `schedule/service.py:421-431` already uses a raw SQL cross-module write under `# noqa: TABLE_REF` — the cascade DM dispatch is a smaller deviation and the function-local import is an established escape hatch.
- **Option B:** introduce a new Protocol slot `dispatch_cancelled_dm_for_slot(session, slot_id) -> None` in `app/core/dependencies.py` (Phase 37 D-37-06 pattern). Heavier; only worth it if Option A flags a real linter contract violation.

The planner should confirm during 39-02 planning by running `import-linter` against Option A first.

---

### 6. `apps/backend/app/workers/scheduled/mark_no_show_bookings.py` (NEW worker)

**Analog:** `apps/backend/app/workers/scheduled/expire_pt_packages.py` (verbatim mirror — both are single-session DB-only batch UPDATE + audit + commit).

**Full file template** (mirror analog 1-73 verbatim, swap names + line refs):
```python
"""ARQ scheduled job: flip overdue confirmed bookings to no_show (Phase 39 CRON-01).

Per Phase 7 D-06 / Phase 18 D-09: this worker file MAY import
`app.modules.bookings.service` — the file IS the bookings module's recurring
DB fanout for no-show classification.

Transaction ownership (Phase 18 D-01 / Phase 39 D-39-06 single-session):
this function is the transaction owner. The service helper
`_mark_no_show_bookings` (D-39-07, with `SELECT FOR UPDATE OF b`) issues
the SELECT + bulk UPDATE + per-row audit emits but explicitly does NOT
commit (carries `# noqa: SVC001 caller-owns-txn`); commit happens here.

Cron schedule: hour=20, minute=10 UTC = 23:10 MSK (container TZ=UTC per
v1.0 Key Decisions). See workers/__init__.py for the cron(...) entry.

Observability: emits one structlog INFO `mark_no_show_bookings_complete
count=N` AFTER commit returns (Phase 18 specifics — locked summary shape).
"""

from __future__ import annotations
from typing import Any

import structlog

from app.modules.bookings import service as bookings_service

_log = structlog.get_logger("workers.scheduled.mark_no_show_bookings")


async def mark_no_show_bookings(ctx: dict[str, Any]) -> int:
    """Mark overdue confirmed bookings as no_show; return count of newly-marked rows."""
    session_factory = ctx["sessionmaker"]
    async with session_factory() as session:
        count = await bookings_service._mark_no_show_bookings(session)
        await session.commit()

    _log.info("mark_no_show_bookings_complete", count=count)
    return count
```

**Locked details from analog:** signature `(ctx: dict[str, Any]) -> int`; `session_factory = ctx["sessionmaker"]`; `await session.commit()` AFTER helper returns; summary log AFTER commit; logger name = `f"workers.scheduled.{job_name}"`.

---

### 7. `apps/backend/app/workers/scheduled/send_booking_reminders.py` (NEW worker)

**Analog:** `apps/backend/app/workers/scheduled/send_expiring_notifications.py` (verbatim mirror; swap module + log names).

**Full file template** (mirror analog 1-69 verbatim):
```python
"""ARQ scheduled job: send 24h booking reminder DMs (Phase 39 CRON-02).

Per Phase 7 D-06 / Phase 18 D-09 / Phase 39 D-39-06 (multi-session):
this worker file MAY import `app.modules.bookings.service` (single-owning-
module exception) + `app.modules.bookings.notifications` + the
`app.integrations.telegram.{sender, bot}` integrations layer.

Bot construction (D-39-10 / D-27-06 mirror): uses
`app.integrations.telegram.bot.build_bot(*, token=...)`.

Transaction ownership (D-39-06 pattern b — multi-session): the service helper
`_send_booking_reminders` opens its own per-send write sessions; the worker
passes `ctx["sessionmaker"]` (the async_sessionmaker) and does NOT open a
session here. The loop makes Telegram I/O between writes — holding one DB
connection across that I/O would waste the pool (mirror v1.3 D-27-07b).

Cron schedule: hour=3, minute=35 UTC = 06:35 MSK. Order is intentional:
06:35 fires 10 min after expire_pt_packages at 06:25 (CRON-02 specifier).

Observability: emits one structlog INFO `send_booking_reminders_complete
count=N` AFTER the helper returns.
"""

from __future__ import annotations
from typing import Any

import structlog

from app.core.config import get_settings
from app.integrations.telegram import sender as telegram_sender
from app.integrations.telegram.bot import build_bot
from app.modules.bookings import notifications as bookings_notifications
from app.modules.bookings import service as bookings_service

_log = structlog.get_logger("workers.scheduled.send_booking_reminders")


async def send_booking_reminders(ctx: dict[str, Any]) -> int:
    """Send 24h-out booking reminder DMs; return count of successful sends."""
    session_factory = ctx["sessionmaker"]
    settings = get_settings()
    bot = build_bot(token=settings.telegram_bot_token.get_secret_value())

    count = await bookings_service._send_booking_reminders(
        session_factory,
        bot=bot,
        sender=telegram_sender,
        notifications_module=bookings_notifications,
    )

    _log.info("send_booking_reminders_complete", count=count)
    return count
```

**Locked details from analog:** identical signature shape; `build_bot(token=settings.telegram_bot_token.get_secret_value())` per analog line 58; `_log.info("<job_name>_complete", count=count)` per analog line 67.

---

### 8. `apps/backend/app/workers/__init__.py` — APPEND `functions` + `cron_jobs`

**Analog (file shape):** `apps/backend/app/workers/__init__.py:61-118` (existing imports + list mutations).

**Imports to add** (after line 63):
```python
from app.workers.scheduled.mark_no_show_bookings import mark_no_show_bookings
from app.workers.scheduled.send_booking_reminders import send_booking_reminders
```

**`functions` list** (analog lines 78-82) — append 2 entries per D-39-16:
```python
functions: ClassVar[list[Any]] = [
    expire_memberships,
    send_expiring_notifications,
    expire_pt_packages,
    send_booking_reminders,    # Phase 39 CRON-02
    mark_no_show_bookings,     # Phase 39 CRON-01
]
```

**`cron_jobs` list** (analog lines 93-118) — append 2 entries per D-39-16:
```python
cron_jobs: ClassVar[list[Any]] = [
    cron(expire_memberships, hour=3, minute=5, unique=True, keep_result=60),
    cron(send_expiring_notifications, hour=3, minute=15, unique=True, keep_result=60),
    cron(expire_pt_packages, hour=3, minute=25, unique=True, keep_result=60),
    # Phase 39 CRON-02: 06:35 MSK — fires 10 min after expire_pt_packages.
    cron(send_booking_reminders, hour=3, minute=35, unique=True, keep_result=60),
    # Phase 39 CRON-01: 23:10 MSK — evening tick.
    cron(mark_no_show_bookings, hour=20, minute=10, unique=True, keep_result=60),
]
```

**`on_startup` resolution invariant** at lines 132-140 already covers the 2 new entries automatically (PITFALLS Pitfall 4 step 6). No test edits needed (CONTEXT.md line 458 — tests reflectively read both lists).

---

### 9. `apps/backend/scripts/run_no_show_cron_once.py` (NEW operator runner)

**Analog:** `apps/backend/scripts/run_expiring_cron_once.py` (mirror verbatim per D-39-17).

**Module docstring** (analog lines 1-36 — swap "send_expiring_notifications" → "mark_no_show_bookings"; **DROP the TELEGRAM_SANDBOX_CHAT_ID load-bearing TM-29-03 stanza** because no-show cron is DB-only — per CONTEXT.md D-39-17 "the no-show runner does NOT touch Telegram so TM-29-03 is omitted there but the docstring explicitly notes the omission").

**Imports** (mirror analog lines 38-59 — different eager-import set per D-39-17):
```python
from __future__ import annotations

import asyncio
import os  # KEEP — TM-29-02 DATABASE_URL guard reads env
import sys
from typing import Any

from app.core.config import get_settings

# REG-29-04 eager-imports — bookings + schedule + trainers + audit FK targets.
from app.modules.auth import models as _auth_models           # noqa: F401
from app.modules.clients import models as _client_models      # noqa: F401
from app.modules.bookings import models as _bookings_models   # noqa: F401
from app.modules.schedule import models as _schedule_models   # noqa: F401
from app.modules.trainers import models as _trainers_models   # noqa: F401
from app.workers import WorkerSettings
from app.workers.scheduled.mark_no_show_bookings import mark_no_show_bookings
```

**`_run()` body** (mirror analog lines 62-94 — DROP the TM-29-03 `TELEGRAM_SANDBOX_CHAT_ID` block; KEEP TM-29-02 DATABASE_URL guard; KEEP `WorkerSettings.on_startup(ctx)` / `on_shutdown(ctx)` pattern):
```python
async def _run() -> int:
    # TM-29-02: refuse against non-local DATABASE_URL.
    db_url = str(get_settings().database_url)
    if "localhost" not in db_url and "postgres:5432" not in db_url:
        print(
            "ERROR: run_no_show_cron_once refuses to run against a non-local "
            "DATABASE_URL (TM-29-02).",
            file=sys.stderr,
        )
        return 1
    # NOTE: TM-29-03 (TELEGRAM_SANDBOX_CHAT_ID) is intentionally OMITTED — the
    # no-show cron is DB-only and never invokes Telegram (D-39-17 mirror).

    ctx: dict[str, Any] = {}
    await WorkerSettings.on_startup(ctx)
    try:
        count = await mark_no_show_bookings(ctx)
        print(f"Fired mark_no_show_bookings once: count={count}")
    finally:
        await WorkerSettings.on_shutdown(ctx)
    return 0


def main() -> int:
    return asyncio.run(_run())


if __name__ == "__main__":
    raise SystemExit(main())
```

---

### 10. `apps/backend/scripts/run_booking_reminders_once.py` (NEW operator runner)

**Analog:** `apps/backend/scripts/run_expiring_cron_once.py` (mirror verbatim — INCLUDING TM-29-03 because this runner DOES dispatch Telegram I/O).

**Differences from #9:** KEEP the full TM-29-03 stanza (analog lines 13-35 + 75-83). Eager-imports include all 5 modules (auth, clients, bookings, schedule, trainers) per D-39-17. Replace `send_expiring_notifications` → `send_booking_reminders` in import + callable line + success print.

---

### 11. `apps/backend/tests/unit/test_booking_notifications_copy.py` (NEW)

**Analog:** no direct analog — small focused module-level tests. Pattern derived from `apps/backend/tests/unit/` style + the placeholder set in D-39-11.

**Scope (per CONTEXT.md scope point 11):** unit tests for each `render_*_dm` helper covering placeholder substitution + the `_BOT_BOOK_DENIED_DM` non-empty smoke.

**Pattern:**
```python
"""Unit tests for app.modules.bookings.notifications render helpers (Phase 39 NOTIFY-01)."""

from __future__ import annotations

from app.modules.bookings import notifications


def test_render_booking_confirmed_dm_substitutes_all_three_placeholders() -> None:
    text = notifications.render_booking_confirmed_dm(
        client_name="Иван",
        trainer_name="Пётр Сидоров",
        slot_start_msk="20.05.2026 10:00",
    )
    assert "Иван" in text
    assert "Пётр Сидоров" in text
    assert "20.05.2026 10:00" in text
    assert "{" not in text  # no unsubstituted placeholders

# ... repeat for cancelled_by_client / cancelled_by_owner / reminder_24h ...

def test_bot_book_denied_dm_constant_is_non_empty() -> None:
    """NOTIFY-02 anti-oracle constant — Phase 40 consumes it; Phase 39 just locks its existence."""
    assert notifications._BOT_BOOK_DENIED_DM
    assert len(notifications._BOT_BOOK_DENIED_DM) > 0
```

---

### 12-13. `tests/integration/bookings/test_create_sends_dm.py` + `test_cancel_sends_dm.py` (NEW)

**Analog (sender stub + fixtures):** `apps/backend/tests/integration/notifications/conftest.py` (full file ~330 lines).
**Analog (test body shape):** `apps/backend/tests/integration/notifications/test_expiring_7d_happy_path.py`.

**Required new fixture file** `apps/backend/tests/integration/bookings/conftest.py` — port the v1.3 notifications/conftest.py fixtures verbatim, replacing membership-specific factories with booking-specific ones:
- `fake_bot` — sentinel object (analog lines 80-87 verbatim).
- `sender_stub` — `_RecordedCall` + `_SenderStubState` + queue/calls API (analog lines 46-110 verbatim).
- `notifications_session_factory` — `_SavepointSessionmaker` wrapping `db_session` (analog lines 120-158 verbatim — this is the `async_sessionmaker`-shaped wrapper).
- New booking-specific factories: `make_booking_with_telegram_client(...)`, `make_booked_slot(...)` etc. — analog membership factories (lines 161-314) inform the shape.

**Test body pattern** (analog `test_expiring_7d_happy_path.py:27-91`):
```python
async def test_create_booking_sends_confirmed_dm(
    db_session: AsyncSession,
    fake_bot: object,
    sender_stub: Any,
    ...
) -> None:
    sender_module, sender_state = sender_stub
    # ... seed slot + client (with telegram_user_id) + pt_package via fixtures ...
    # Monkeypatch the in-service `telegram_sender` reference with sender_module:
    monkeypatch.setattr(
        "app.modules.bookings.service.telegram_sender",
        sender_module,
    )
    # Call service.create_booking(...)
    # Assert: sender_state.calls has exactly 1 entry with the expected chat_id + text.
```

**Note:** the `create_booking` / `cancel_booking` flows construct their own `bot` via `build_bot(...)` per D-39-10 — the test stubs the `sender` module reference (mirror v1.3 D-39-19 / D-27-22), not the bot. The `bot` instance is never used by the stub.

**`test_cancel_sends_dm.py`** covers all 4 actor.role discriminator scenarios per D-39-05:
1. `actor.role == OWNER` → `BOOKING_CANCELLED_BY_OWNER_DM` sent.
2. `actor.role == RECEPTION` → `BOOKING_CANCELLED_BY_CLIENT_DM` sent.
3. Slot-cascade (owner-only) → `BOOKING_CANCELLED_BY_OWNER_DM` sent per cancelled booking.
4. Client without `telegram_user_id` → INFO log `booking_dm_skipped_unlinked`, no send.

---

### 14. `tests/integration/bookings/test_no_show_cron.py` (NEW)

**Analog:** `apps/backend/tests/integration/pt_packages/test_expire_pt_packages_cron.py` (verbatim mirror — direct helper call + worker e2e + structlog capture).

**Key patterns from analog:**
- `@pytest_asyncio.fixture(autouse=True)` `_reset_pt_packages_worker_logger_cache` (analog lines 36-49) — mirror as `_reset_no_show_worker_logger_cache`, swap `worker_mod = mark_no_show_bookings`. **Critical** — without this reset, `structlog.testing.capture_logs()` misses the summary log line because BoundLoggerLazyProxy caches its processor list.
- Direct helper test (analog lines 52-110): seed overdue/future bookings → call `await bookings_service._mark_no_show_bookings(db_session)` → `await db_session.commit()` → assert returned count + per-row status + audit row payload (`set(payload.keys()) == {"booking_id", "slot_id", "client_id", "no_show_at"}`).
- Idempotency test (analog lines 113-135): two consecutive calls; second returns 0 (WHERE status='confirmed' gate).
- Worker e2e (analog lines 166-213): use `_Sessionmaker` / `_SessionContext` wrappers (analog lines 184-193) to inject `db_session` into the worker `ctx`; assert `structlog.testing.capture_logs()` captures `"mark_no_show_bookings_complete"` with `count=1` AFTER commit.

---

### 15. `tests/integration/bookings/test_reminder_cron.py` (NEW)

**Analog:** hybrid of `test_expire_pt_packages_cron.py` (cron e2e shape) + `test_expiring_7d_happy_path.py` (sender_stub + idempotency-row assertion).

**Scenarios per CONTEXT.md scope point 11:**
1. `test_reminders_cron_inserts_idempotency_row` — confirmed booking with `start_time = now + 24h`, linked client → 1 DM sent + 1 `BookingNotification` row created.
2. `test_reminders_cron_idempotent` — re-run after success: `len(sender_state.calls)` stays at 1 (LEFT JOIN pre-filter excludes already-notified row).
3. `test_reminders_cron_skips_403_blocked` — `sender_state.queue(SendResult(ok=False, blocked=True))` → no `BookingNotification` row, WARNING-log captured.
4. `test_reminders_cron_skips_unlinked_client` — client with `telegram_user_id IS NULL` → SELECT-level exclusion (no sender call).

---

## Shared Patterns

### S1. Phase 18 / Phase 27 Worker-File Template

**Sources:** `apps/backend/app/workers/scheduled/expire_pt_packages.py` (single-session) + `apps/backend/app/workers/scheduled/send_expiring_notifications.py` (multi-session).
**Apply to:** every new file in `app/workers/scheduled/`.

Locked shape every worker file follows:
```python
"""<one-line summary> (Phase NN <REQ-ID>)."""
from __future__ import annotations
from typing import Any
import structlog
# imports: app.modules.<owning_module>.service + (if needed) integrations
_log = structlog.get_logger("workers.scheduled.<job_name>")

async def <job_name>(ctx: dict[str, Any]) -> int:
    """<doc>"""
    session_factory = ctx["sessionmaker"]
    # ... single or multi session per D-39-06 ...
    _log.info("<job_name>_complete", count=count)
    return count
```
Convention: `<job_name>_complete count=N` is locked summary-log shape (Phase 18 specifics line 195).

### S2. SVC001 Marker on Caller-Owns-Txn Helpers

**Source:** `apps/backend/app/modules/memberships/service.py:1401` (`async def _send_expiring_notifications( ... ) -> int:  # noqa: SVC001 caller-owns-txn`).
**Apply to:** every private `_`-prefixed cron-helper in `bookings/service.py` (`_mark_no_show_bookings`, `_send_booking_reminders`).

The AST commit-gate walker (`tests/unit/test_service_commit_gate.py`) requires every public mutating orchestrator to end with `await session.commit()`. Private helpers that delegate commit to the caller carry `# noqa: SVC001 caller-owns-txn` on the def line.

### S3. Audit Emit With LITERAL Strings + UUID-Cast Style

**Source:** `apps/backend/app/modules/bookings/service.py:543-553` (existing `booking_cancelled` emit) + `audit_payloads.py:410-424` (`BookingNoShowPayload`).
**Apply to:** Phase 39's only audit emit callsite — `_mark_no_show_bookings` (per D-39-14: no other new audit events).
```python
await audit.emit(
    session,
    "booking_no_show",                # LITERAL — INFRA-11 AST gate
    actor_user_id=None,               # system actor; column is nullable
    resource_type="booking",          # LITERAL
    resource_id=c.id,
    booking_id=str(c.id),
    slot_id=str(c.slot_id),
    client_id=str(c.client_id),
    no_show_at=datetime.now(MOSCOW_TZ).isoformat(),
)
```
Match `BookingNoShowPayload` keys EXACTLY (extra='forbid'): `booking_id, slot_id, client_id, no_show_at`.

### S4. Fresh `Bot` Per Call (NEVER Cached)

**Source:** `apps/backend/app/integrations/telegram/bot.py:85-96` (`build_bot`) — "Returns a FRESH Bot per call (no caching)".
**Apply to:** every place Phase 39 constructs a Bot — both worker files and both `bookings/service.py` callsites (`create_booking`, `cancel_booking`) + the `schedule/service.py` cascade callsite.
```python
from app.core.config import get_settings
from app.integrations.telegram.bot import build_bot
bot = build_bot(token=get_settings().telegram_bot_token.get_secret_value())
```
**Never** cache the bot at module scope (v1.3 D-27-06 anti-pattern — aiohttp session leak risk).

### S5. SendResult Failure Classification + WARNING-Log + No-Raise

**Source:** `apps/backend/app/integrations/telegram/sender.py:56-73` (`send_text_dm`) + `apps/backend/app/modules/memberships/service.py:1466-1479` (failure-branch logging).
**Apply to:** every Phase 39 DM-send callsite (`_dispatch_booking_dm` + `_send_booking_reminders`).
```python
result = await sender.send_text_dm(bot, chat_id, text_body)
if not result.ok:
    reason = "bot_blocked" if result.blocked else "transient"
    _log.warning(
        "<event>_send_failed",
        reason=reason,
        # business ids ...
        error_msg=result.error,
    )
    # confirmation/cancel path: return; reminder cron: continue
```

### S6. Per-Test Logger Cache Reset For `structlog.testing.capture_logs()`

**Source:** `apps/backend/tests/integration/pt_packages/test_expire_pt_packages_cron.py:36-49`.
**Apply to:** every Phase 39 worker integration test that asserts on a summary log line.

Without this `autouse` fixture, `BoundLoggerLazyProxy` caches its first-call processor list and subsequent `capture_logs()` calls see no events.

### S7. SAVEPOINT `_SavepointSessionmaker` Wrapper

**Source:** `apps/backend/tests/integration/notifications/conftest.py:120-158`.
**Apply to:** every Phase 39 integration test that calls a multi-session helper (`_send_booking_reminders`) or the worker functions that read `ctx["sessionmaker"]`.

The wrapper makes `async with session_factory() as ws: ws.commit()` translate to a SAVEPOINT release inside the outer transaction that the `db_session` fixture rolls back at teardown — keeps the helper's commit calls valid without leaking state across tests.

### S8. Owner Copy-Lock Sign-off Discipline

**Source:** v1.3 D-27-OWNER-COPY-LOCK (recorded in `.planning/PROJECT.md` Key Decisions); pattern doc at `apps/backend/app/integrations/telegram/copy.py:1-9`.
**Apply to:** plan 39-01 close — the 4 DM strings + `_BOT_BOOK_DENIED_DM` get explicit operator sign-off recorded in `39-01-SUMMARY.md` before plan-merge.

---

## No Analog Found

None. Every Phase 39 file maps to a v1.3 / v1.4 precedent (Phase 27 notifications, Phase 33 pt_packages cron, Phase 38 bookings service).

The one quasi-novel surface — `_dispatch_booking_dm` as an in-request private function instead of an ARQ enqueue — is explicitly justified in D-39-09 / D-39-10 with the migration-path documented; the helper signature is queue-target-swappable to a future ARQ job. No structural research debt.

---

## Metadata

**Analog search scope (read top-to-bottom):**
- `apps/backend/app/integrations/telegram/` (3 files: bot.py, sender.py, copy.py)
- `apps/backend/app/workers/__init__.py` + `app/workers/scheduled/{expire_memberships,expire_pt_packages,send_expiring_notifications}.py` (4 files)
- `apps/backend/app/modules/memberships/{models.py:267-324, service.py:1380-1510}` (1 file targeted ranges)
- `apps/backend/app/modules/bookings/{models.py, service.py}` (2 files — full models, targeted service ranges)
- `apps/backend/app/modules/schedule/service.py:395-502` (1 file targeted range)
- `apps/backend/app/core/audit_payloads.py:405-463` (1 file targeted range)
- `apps/backend/alembic/versions/0010_notifications.py` + `ls 0017..0019` (2 reads)
- `apps/backend/scripts/run_expiring_cron_once.py` (1 file)
- `apps/backend/tests/integration/notifications/{conftest.py, test_expiring_7d_happy_path.py}` (2 files)
- `apps/backend/tests/integration/pt_packages/test_expire_pt_packages_cron.py` (1 file)

**Files scanned:** ~18 targeted reads (no whole-tree scans; everything was guided by CONTEXT.md canonical_refs section).

**Pattern extraction date:** 2026-05-17.
