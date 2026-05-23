# Phase 52: Cross-Channel Notifications + v1.6 Carry-out — Pattern Map

**Mapped:** 2026-05-23
**Files analyzed:** 12 new/modified files
**Analogs found:** 12 / 12

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `app/modules/online_payments/notifications.py` | model/utility | event-driven | `app/modules/bookings/notifications.py` | exact |
| `app/modules/online_payments/email_templates.py` | config | event-driven | `app/modules/bookings/notifications.py` (email section) | exact |
| `app/modules/online_payments/tasks.py` | service/worker | event-driven | `app/modules/fiscal_receipts/tasks.py` | exact |
| `app/modules/online_payments/models.py` | model | CRUD | `app/modules/bookings/models.py` (BookingNotification) | exact |
| `alembic/versions/0039_payment_notifications.py` | migration | CRUD | `alembic/versions/0035_fiscal_receipts.py` | exact |
| `app/api/v1/_internal/yookassa/handlers.py` | controller | request-response | self (extend `_post_commit_enqueue` + `handle_payment_canceled`) | exact |
| `app/modules/online_refunds/settle.py` | service | CRUD | self (extend `_settle_online_refund`) | exact |
| `app/core/audit.py` | config | CRUD | self (extend `LOCKED_EMAIL_TEMPLATES`) | exact |
| `app/workers/__init__.py` | config | event-driven | self (extend `WorkerSettings.functions`) | exact |
| `tests/integration/webhook_yookassa/test_post_commit_seam.py` | test | request-response | self (update AST gate) | exact |
| `tests/unit/test_locked_email_templates_ast.py` | test | CRUD | self (update positive-fixture test) | exact |
| `apps/backend/scripts/verify/v1_6_email_probe.py` | utility | batch | self (extend for CARRY-01) | exact |

---

## Pattern Assignments

### `app/modules/online_payments/notifications.py` (new — locked DM templates)

**Analog:** `apps/backend/app/modules/bookings/notifications.py`

**Module docstring pattern** (lines 1-22):
```python
"""Locked Russian DM templates for Phase 52 online-payment notifications (NOT-01).

4 online-payment-event templates. Single template per kind (D-52-06 —
NO A/B variants; the payment surface is one-shot per event).

Owner sign-off (D-52-06 lineage / Phase 52 plan N close) recorded in
``.planning/phases/52-cross-channel-notifications-v1-6-carry-out/N-SUMMARY.md``
before plan close. Modifying these strings post-merge requires a NEW
owner sign-off entry.

Module location (D-52-06 mirror of D-39-02): lives in
``app/modules/online_payments/`` because payment DM copy is owned by
the online_payments domain.

Placeholder substitution (D-39-04 mirror): renderers use
``str.format(**kwargs)`` so any unknown placeholder key raises
``KeyError`` loud at test time — f-strings would silently shadow the
bug.
"""
```

**Imports pattern** (lines 24-26 of analog):
```python
from __future__ import annotations

from typing import Final
```

**Locked template constants pattern** (analog lines 31-38):
```python
# === Phase 52 NOT-01 -- locked Russian DM copy. Owner sign-off pending in plan N. ===
# RUF001/E501/RUF003 per-line: Cyrillic letters + locked single-line format are intentional
ONLINE_PAYMENT_SUCCEEDED_DM: Final[str] = "..."  # noqa: E501, RUF001  # OWNER-COPY-LOCK signed-off YYYY-MM-DD — see N-SUMMARY.md
ONLINE_PAYMENT_REFUNDED_DM: Final[str] = "..."  # noqa: E501, RUF001  # OWNER-COPY-LOCK signed-off YYYY-MM-DD — see N-SUMMARY.md
ONLINE_PAYMENT_CANCELED_DM: Final[str] = "..."  # noqa: E501, RUF001  # OWNER-COPY-LOCK signed-off YYYY-MM-DD — see N-SUMMARY.md  # OWNER-ALERT only (NOT-05) — NO client DM
FISCAL_RECEIPT_FAILED_DM: Final[str] = "..."  # noqa: E501, RUF001  # OWNER-COPY-LOCK signed-off YYYY-MM-DD — see N-SUMMARY.md  # OWNER-ALERT only (NOT-04)
```

**Renderer function pattern** (analog lines 41-52):
```python
def render_online_payment_succeeded_dm(
    *,
    client_name: str,
    amount_rub: str,
) -> str:
    """Render the locked payment-succeeded DM via ``str.format`` (unknown keys raise KeyError)."""
    return ONLINE_PAYMENT_SUCCEEDED_DM.format(
        client_name=client_name,
        amount_rub=amount_rub,
    )
```
Apply same pattern for `render_online_payment_refunded_dm`, `render_online_payment_canceled_dm` (operator-actionable: include `payment_id` + `yookassa_payment_id`), and `render_fiscal_receipt_failed_dm` (include `payment_id` + `failure_reason` — D-52-08). Client-facing templates carry no failure-cause disclosure (anti-oracle C-12).

---

### `app/modules/online_payments/email_templates.py` (extend — 4 email identifiers)

**Analog:** `apps/backend/app/modules/bookings/notifications.py` lines 97-181 (email-fallback section)

**Current state** (full file, lines 1-11): empty placeholder module — Phase 49 D-49-01.

**Pattern to add** — 4 module-level string constants (NOT dispatcher calls; the dispatcher calls live in `tasks.py` using literal strings):
```python
# Phase 52 NOTIFY-02 — email template identifiers. Added to LOCKED_EMAIL_TEMPLATES.
# OWNER-COPY-LOCK: identifiers carry the same sign-off lineage as the DM templates (D-52-07).
EMAIL_ONLINE_PAYMENT_SUCCEEDED: Final[str] = "EMAIL_ONLINE_PAYMENT_SUCCEEDED"
EMAIL_ONLINE_PAYMENT_REFUNDED: Final[str] = "EMAIL_ONLINE_PAYMENT_REFUNDED"
EMAIL_ONLINE_PAYMENT_CANCELED: Final[str] = "EMAIL_ONLINE_PAYMENT_CANCELED"  # owner-alert
EMAIL_FISCAL_RECEIPT_FAILED: Final[str] = "EMAIL_FISCAL_RECEIPT_FAILED"  # owner-alert
```

**Critical gate constraint:** The AST gate in `test_locked_email_templates_ast.py` requires `template_id=` arguments to `get_email_dispatcher()()` to be **literal string constants at the callsite** — NOT variable references. The constants defined here are for documentation only; the `tasks.py` dispatcher calls must use the literal strings directly (e.g. `template_id="EMAIL_ONLINE_PAYMENT_SUCCEEDED"`).

---

### `app/modules/online_payments/tasks.py` (new — ARQ dispatch task)

**Analog:** `apps/backend/app/modules/fiscal_receipts/tasks.py` (structure) + `apps/backend/app/workers/scheduled/send_booking_reminders.py` (dual-channel dispatch pattern)

**Imports pattern** (fiscal_receipts/tasks.py lines 26-55, adapted):
```python
from __future__ import annotations

from typing import Any, Final
from uuid import UUID

import structlog
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.core.config import get_settings
from app.integrations.telegram import sender as telegram_sender
from app.integrations.telegram.bot import build_bot
from app.modules.clients.models import Client
from app.modules.online_payments import notifications as payment_notifications
from app.modules.online_payments import repository as payment_repo
from app.modules.online_payments.models import PaymentNotification
from app.modules.payments.models import Payment

_log: Final = structlog.get_logger("modules.online_payments.tasks")
_MAX_TRIES: Final[int] = 3
```

**ARQ task signature pattern** (fiscal_receipts/tasks.py line 247):
```python
async def dispatch_payment_notification(ctx: dict[str, Any], *, payment_id: str, kind: str) -> str:
    """ARQ task body. Returns 'sent' | 'partial' | 'skipped'.

    ctx keys required (wired in WorkerSettings.on_startup):
      - sessionmaker: async_sessionmaker[AsyncSession]
      - job_try: int (provided by ARQ runtime)
    """
    session_factory = ctx["sessionmaker"]
    settings = get_settings()
    ...
```

**Per-channel claim-then-send pattern** (D-52-02 — derived from send_booking_reminders.py + fiscal_receipts/tasks.py):
```python
    # Bot constructed fresh per task invocation (D-39-10 aiohttp session leak risk).
    bot = build_bot(token=settings.telegram_bot_token.get_secret_value())

    payment_uuid = UUID(payment_id)

    for channel in ("telegram", "email"):
        # Step 1: resolve recipient address.
        if channel == "telegram":
            chat_id = await _resolve_telegram_chat_id(session_factory, payment_uuid, kind)
            if chat_id is None:
                _log.info(
                    "payment_notification_channel_skipped",
                    payment_id=payment_id,
                    kind=kind,
                    channel=channel,
                    reason="no_telegram_user_id",
                )
                continue
        else:
            email_addr = await _resolve_client_email(session_factory, payment_uuid, kind)
            if email_addr is None:
                _log.info(
                    "payment_notification_channel_skipped",
                    payment_id=payment_id,
                    kind=kind,
                    channel=channel,
                    reason="no_email",
                )
                continue

        # Step 2: INSERT claim row — on IntegrityError (UNIQUE) the channel
        # was already sent (idempotent replay). Claim BEFORE send (at-most-once
        # leaning — D-52-02 / D-52-Discretion claim-before-send recommendation).
        claimed = await payment_repo.claim_payment_notification(
            session_factory,
            payment_id=payment_uuid,
            kind=kind,
            channel=channel,
        )
        if not claimed:
            _log.info(
                "payment_notification_idempotent_replay",
                payment_id=payment_id,
                kind=kind,
                channel=channel,
            )
            continue

        # Step 3: send — best-effort; failure on one channel never blocks the
        # other and never rolls back the financial commit (D-52-02 / D-45-08).
        try:
            if channel == "telegram":
                text = _render_dm(kind, ...)
                await telegram_sender.send_text_dm(bot, chat_id=chat_id, text=text)
            else:
                await _dispatch_email(kind, email_addr)
        except Exception:  # noqa: BLE001
            _log.exception(
                "payment_notification_send_failed",
                payment_id=payment_id,
                kind=kind,
                channel=channel,
            )
```

**Owner-alert routing pattern** (D-52-09 — for `payment_canceled` and `fiscal_failed` kinds):
```python
    # Owner-alert kinds route to OWNER_ALERT_* settings, not to the client.
    owner_tg_chat_id = getattr(settings, "owner_alert_telegram_chat_id", None)
    if owner_tg_chat_id is None:
        _log.error(
            "owner_alert_telegram_not_configured",
            kind=kind,
            payment_id=payment_id,
        )
        # Best-effort: never raise, never block (D-52-09).
```

**Email dispatch sub-call pattern** (bookings/notifications.py lines 102-181 — literal template_id at callsite, AST gate):
```python
async def _dispatch_email(kind: str, to: str) -> None:
    dispatcher = get_email_dispatcher()
    audit_correlation_id = uuid4()
    if kind == "payment_succeeded":
        await dispatcher(
            template_id="EMAIL_ONLINE_PAYMENT_SUCCEEDED",
            to=to,
            audit_correlation_id=audit_correlation_id,
            # ... render kwargs
        )
    elif kind == "refund_succeeded":
        await dispatcher(
            template_id="EMAIL_ONLINE_PAYMENT_REFUNDED",
            to=to,
            audit_correlation_id=audit_correlation_id,
        )
    elif kind == "payment_canceled":
        await dispatcher(
            template_id="EMAIL_ONLINE_PAYMENT_CANCELED",
            to=to,
            audit_correlation_id=audit_correlation_id,
        )
    elif kind == "fiscal_failed":
        await dispatcher(
            template_id="EMAIL_FISCAL_RECEIPT_FAILED",
            to=to,
            audit_correlation_id=audit_correlation_id,
        )
    else:  # pragma: no cover
        raise ValueError(f"unknown payment notification kind: {kind}")
```
**Critical:** Every `template_id=` argument must be a string literal (`"EMAIL_..."`) — never a variable. The AST gate (`test_locked_email_templates_ast.py`) rejects non-literals.

---

### `app/modules/online_payments/models.py` (extend — add PaymentNotification)

**Analog:** `apps/backend/app/modules/bookings/models.py` lines 175-269 (`BookingNotification`)

**Model composition** (analog line 175):
```python
class PaymentNotification(Base, UUIDPkMixin, TimestampMixin):
    """Idempotency record for cross-channel payment notifications (Phase 52 NOT-03).

    Composition: Base + UUIDPkMixin + TimestampMixin (NO SoftDeleteMixin —
    rows are append-only; the (payment_id, kind, channel) UNIQUE is the
    single source of truth for cross-restart idempotency per D-52-04).

    DB-level invariants:
    - UNIQUE (payment_id, kind, channel) uq_payment_notifications_payment_kind_channel
    - FK fk_payment_notifications_payment_id_payments ON DELETE RESTRICT
    - kind CHECK IN ('payment_succeeded', 'refund_succeeded', 'payment_canceled',
      'fiscal_failed')
    - channel CHECK IN ('telegram', 'email')
    """

    __tablename__ = "payment_notifications"
```

**Columns pattern** (analog lines 211-239, adapted for payment_notifications):
```python
    payment_id: Mapped[UUIDType] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey(
            "payments.id",
            ondelete="RESTRICT",
            name="fk_payment_notifications_payment_id_payments",
        ),
        nullable=False,
    )
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    channel: Mapped[str] = mapped_column(Text, nullable=False)
    sent_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=text("now()"),
        nullable=False,
    )
```

**`__table_args__` pattern** (analog lines 241-268):
```python
    __table_args__ = (
        CheckConstraint(
            "kind IN ('payment_succeeded', 'refund_succeeded', "
            "'payment_canceled', 'fiscal_failed')",
            name="kind",  # NAMING_CONVENTION expands to ck_payment_notifications_kind
        ),
        CheckConstraint(
            "channel IN ('telegram', 'email')",
            name="channel",  # expands to ck_payment_notifications_channel
        ),
        UniqueConstraint(
            "payment_id",
            "kind",
            "channel",
            name="uq_payment_notifications_payment_kind_channel",
        ),
        Index("ix_payment_notifications_payment_id", "payment_id"),
    )
```

**Naming convention note:** CheckConstraints use BARE suffix names (`"kind"`, `"channel"`) so SA NAMING_CONVENTION expands to `ck_payment_notifications_kind` / `ck_payment_notifications_channel` — matching what `op.f()` in the Alembic migration writes. ForeignKey and UniqueConstraint pass full literal names (no expansion). See `online_payments/models.py` lines 9-15 for the exact docstring explaining this discipline.

---

### `alembic/versions/0039_payment_notifications.py` (new migration)

**Analog:** `apps/backend/alembic/versions/0035_fiscal_receipts.py`

**Header pattern** (analog lines 1-40):
```python
"""0039 — payment_notifications table (Phase 52 NOT-03 / D-52-04).

Creates the payment_notifications idempotency table for cross-channel
client notifications and owner operator alerts. ``payment_id`` FK targets
``payments.id`` ON DELETE RESTRICT (mirrors fiscal_receipts discipline —
the notification is tied to the ledger row, not the online_payment row,
except for canceled/fiscal-failed owner alerts which key on a stable id
TBD by planner per D-52-10).

NAMING_CONVENTION: op.f() wrappers on PK / FK / CHECK / UNIQUE.
ORM model lives at app/modules/online_payments/models.py (PaymentNotification).

Downgrade order: drop UNIQUE constraint BEFORE drop_table.

Revision ID: 0039_payment_notifications
Revises: 0038_fiscal_receipts_created_at
Create Date: 2026-05-23 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0039_payment_notifications"
down_revision: str | None = "0038_fiscal_receipts_created_at"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None
```

**upgrade() pattern** (analog lines 43-84):
```python
def upgrade() -> None:
    op.create_table(
        "payment_notifications",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("payment_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("channel", sa.Text(), nullable=False),
        sa.Column(
            "sent_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        # TimestampMixin columns (created_at / updated_at):
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_payment_notifications")),
        sa.ForeignKeyConstraint(
            ["payment_id"],
            ["payments.id"],
            name=op.f("fk_payment_notifications_payment_id_payments"),
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint(
            "kind IN ('payment_succeeded', 'refund_succeeded', "
            "'payment_canceled', 'fiscal_failed')",
            name=op.f("ck_payment_notifications_kind"),
        ),
        sa.CheckConstraint(
            "channel IN ('telegram', 'email')",
            name=op.f("ck_payment_notifications_channel"),
        ),
        sa.UniqueConstraint(
            "payment_id",
            "kind",
            "channel",
            name=op.f("uq_payment_notifications_payment_kind_channel"),
        ),
    )
    op.create_index(
        "ix_payment_notifications_payment_id",
        "payment_notifications",
        ["payment_id"],
    )
```

**downgrade() pattern** (analog lines 87-93):
```python
def downgrade() -> None:
    op.drop_index("ix_payment_notifications_payment_id", "payment_notifications")
    op.drop_constraint(
        op.f("uq_payment_notifications_payment_kind_channel"),
        "payment_notifications",
        type_="unique",
    )
    op.drop_table("payment_notifications")
```

---

### `app/api/v1/_internal/yookassa/handlers.py` (extend — `_post_commit_enqueue` + `handle_payment_canceled`)

**Analog:** self — current file at lines 269-316 and 515-639.

**Current `_post_commit_enqueue` body** (lines 302-316 — the shape the AST gate currently asserts):
```python
    _log.info(
        "webhook_post_commit_enqueue_skip",
        online_payment_id=str(online_payment_id),
        ...
    )
    if arq_pool is not None and fiscal_receipt_id is not None:
        await arq_pool.enqueue_job(
            "dispatch_fiscal_receipt",
            str(fiscal_receipt_id),
            _max_tries=3,
            _expires=60,
        )
```

**Phase 52 extension — add notification branch after fiscal branch** (D-52-10 / D-52-11). The body gains a second guarded enqueue; the AST gate must be updated in lockstep to assert 3 non-docstring statements (log + fiscal guard + notification guard), or a combined guard structure — planner chooses the shape and updates the test to match:
```python
    _log.info(
        "webhook_post_commit_enqueue",
        online_payment_id=str(online_payment_id),
        subject_kind=subject_kind,
        subject_id=str(subject_id),
        arq_pool_present=arq_pool is not None,
        fiscal_receipt_id=str(fiscal_receipt_id) if fiscal_receipt_id is not None else None,
        payment_id=str(payment_id) if payment_id is not None else None,
    )
    if arq_pool is not None and fiscal_receipt_id is not None:
        await arq_pool.enqueue_job(
            "dispatch_fiscal_receipt",
            str(fiscal_receipt_id),
            _max_tries=3,
            _expires=60,
        )
    if arq_pool is not None and payment_id is not None and kind is not None:
        await arq_pool.enqueue_job(
            "dispatch_payment_notification",
            _kwargs={"payment_id": str(payment_id), "kind": kind},
            _max_tries=3,
            _expires=60,
        )
```

**`handle_payment_canceled` extension point** (line 638-639 comment):
```python
    # No _post_commit_enqueue for cancellation in Phase 50 (Phase 52 NOT-05
    # may add a cancellation-DM enqueue here).
```
Phase 52 replaces this comment with an actual owner-alert enqueue. The `arq_pool` parameter must be added to `handle_payment_canceled`'s signature (currently absent — see line 515-520).

---

### `app/modules/online_refunds/settle.py` (extend — add refund notification enqueue)

**Analog:** self — current `SettledRefundLocals` dataclass (lines 60-74) and the `return` statement (lines 348-353).

**Extension:** The `SettledRefundLocals` dataclass gains a `refund_payment_id` field (the refund ledger row id) that the webhook + cron callers thread into `_post_commit_enqueue` as `payment_id` + `kind='refund_succeeded'`. Pattern mirrors how `fiscal_receipt_id` was added to `SettledRefundLocals` in Phase 51:

```python
@dataclass(frozen=True, slots=True)
class SettledRefundLocals:
    fiscal_receipt_id: UUID
    online_payment_id: UUID
    subject_kind: Literal["membership", "pt_package"]
    subject_id: UUID
    refund_payment_id: UUID  # Phase 52: ledger row id for refund notification dedup
```

The webhook and cron callers that destructure `SettledRefundLocals` to call `_post_commit_enqueue` are updated to pass `payment_id=locals.refund_payment_id, kind='refund_succeeded'`.

---

### `app/core/audit.py` (extend — LOCKED_EMAIL_TEMPLATES frozenset)

**Analog:** self — current frozenset at lines 399-422.

**Extension pattern** (add 4 entries, 15 → 19):
```python
LOCKED_EMAIL_TEMPLATES: frozenset[str] = frozenset(
    {
        # ... existing 15 entries ...
        # Phase 52 — online payment notifications (NOT-02 / D-52-07):
        "EMAIL_ONLINE_PAYMENT_SUCCEEDED",
        "EMAIL_ONLINE_PAYMENT_REFUNDED",
        "EMAIL_ONLINE_PAYMENT_CANCELED",    # owner operator alert
        "EMAIL_FISCAL_RECEIPT_FAILED",      # owner operator alert
    }
)
```

---

### `app/workers/__init__.py` (extend — register `dispatch_payment_notification`)

**Analog:** self — current `functions` list at lines 125-143.

**Extension pattern** (after `dispatch_fiscal_receipt`, mirrors the bare-callable + comment convention):
```python
    functions: ClassVar[list[Any]] = [
        # ... existing entries ...
        dispatch_fiscal_receipt,
        # Phase 52 NOT-01..05 — cross-channel client + owner-alert dispatch task.
        # Bare callable per dispatch_fiscal_receipt convention (Option B);
        # per-enqueue _max_tries=3, _expires=60 carries the ARQ retry contract
        # from D-52-Discretion / Pitfall 11 step 2.
        dispatch_payment_notification,
        ...
    ]
```

The import for `dispatch_payment_notification` is added to the `__init__.py` imports block alongside `dispatch_fiscal_receipt`.

---

### `tests/integration/webhook_yookassa/test_post_commit_seam.py` (update — AST gate lockstep)

**Analog:** self — current test at lines 65-177.

**Key constraint:** The test currently asserts `len(body) == 2` (log statement + one guarded enqueue). After Phase 52 adds the notification enqueue branch, the test must be updated to assert the new body shape in lockstep with the production change (D-52-11 / PATTERNS.md errata #3 discipline). The existing gate structure (AST inspection of `_post_commit_enqueue`) is the template — add assertions for the notification enqueue guard following the same pattern as the fiscal_receipt guard assertions (lines 99-177).

**Runtime test additions:** Add two new `@pytest.mark.asyncio` runtime tests:
1. `test_post_commit_enqueue_calls_notification_when_payment_id_present` — asserts `dispatch_payment_notification` is enqueued with `_max_tries=3, _expires=60` when `payment_id` + `kind` are non-None.
2. `test_post_commit_enqueue_no_client_dm_on_cancellation` — asserts that the cancellation handler (`handle_payment_canceled`) does NOT enqueue `dispatch_payment_notification` with `kind='payment_succeeded'` or `kind='refund_succeeded'` (NOT-05 regression guard).

---

### `tests/unit/test_locked_email_templates_ast.py` (update — positive-fixture test for 4 new identifiers)

**Analog:** self — positive-fixture test pattern at lines 162-323.

**Extension pattern** (add one `test_*` function per new literal template_id, following the Phase 42/43/44 positive-fixture discipline):
```python
def test_email_online_payment_succeeded_literal_at_tasks_callsite() -> None:
    """Phase 52 D-52-07 — positive-fixture for EMAIL_ONLINE_PAYMENT_SUCCEEDED.

    Pins the contract that the literal "EMAIL_ONLINE_PAYMENT_SUCCEEDED"
    exists as an ast.Constant(str) directly at a get_email_dispatcher()(...)
    callsite inside online_payments/tasks.py. A future refactor to a constant
    reference would silently bypass test_real_callsites_pass — this test
    catches it.
    """
    tasks_py = _BACKEND_APP / "modules" / "online_payments" / "tasks.py"
    tree = ast.parse(tasks_py.read_text(encoding="utf-8"))
    found_literal_template_ids: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        for kw in node.keywords:
            if (
                kw.arg == "template_id"
                and isinstance(kw.value, ast.Constant)
                and isinstance(kw.value.value, str)
            ):
                found_literal_template_ids.append(kw.value.value)
    assert "EMAIL_ONLINE_PAYMENT_SUCCEEDED" in found_literal_template_ids, ...
```
Repeat for `EMAIL_ONLINE_PAYMENT_REFUNDED`, `EMAIL_ONLINE_PAYMENT_CANCELED`, `EMAIL_FISCAL_RECEIPT_FAILED`.

---

### `apps/backend/scripts/verify/v1_6_email_probe.py` (extend — CARRY-01)

**Analog:** self — current script at lines 1-242.

**Extension pattern** (CARRY-01 / D-52-13): the script already covers yandex.ru, mail.ru, rambler.ru (lines 97-101). The Phase 52 carry-out confirms the script is sufficient as-is (3 provider probes already match the DEFER-46-01 scope) and updates the docstring + output block to reference `.planning/handoff/v1.7-email-deliverability-evidence/` as the capture target instead of `v1.6-VERIFICATION-LOG.md`. No structural changes needed if the script already meets the scope; the new evidence directory and its README are the primary deliverables.

---

## Shared Patterns

### Locked Russian copy (`# OWNER-COPY-LOCK`)
**Source:** `apps/backend/app/modules/bookings/notifications.py` lines 31-38
**Apply to:** `app/modules/online_payments/notifications.py` (all 4 `Final[str]` constants)

Key rules:
- `Final[str]` type annotation on every constant
- Trailing `# noqa: E501, RUF001` on every Cyrillic-containing line
- `# OWNER-COPY-LOCK signed-off YYYY-MM-DD — see N-SUMMARY.md` on same line
- `str.format(**kwargs)` rendering (NOT f-strings — unknown keys raise `KeyError` loud)
- Anti-oracle: owner-alert templates may include `payment_id` / `failure_reason`; client-facing templates carry NO failure-cause disclosure (C-12)

### ARQ task structure (`dispatch_*` tasks)
**Source:** `apps/backend/app/modules/fiscal_receipts/tasks.py` lines 247-395
**Apply to:** `app/modules/online_payments/tasks.py`

Key rules:
- `_MAX_TRIES: Final[int] = 3` module-level constant
- Task signature: `async def task_name(ctx: dict[str, Any], *, kwarg: str) -> str`
- Session-factory from `ctx["sessionmaker"]`; fresh bot from `build_bot(token=...)` per invocation (never cached at module scope — D-39-10 aiohttp session leak risk)
- Best-effort send: `except Exception: _log.exception(...)` never re-raises; one channel failure never blocks the other
- Structlog logger: `_log: Final = structlog.get_logger("modules.online_payments.tasks")`

### Cross-channel idempotency (claim-before-send)
**Source:** `apps/backend/app/modules/bookings/notifications.py` + v1.6 `booking_notifications` UNIQUE pattern
**Apply to:** `app/modules/online_payments/tasks.py` per-channel loop + `app/modules/online_payments/repository.py` `claim_payment_notification`

Key rules:
- INSERT before send so a crash mid-send leaves the row claimed (at-most-once leaning)
- On `IntegrityError` (UNIQUE violation): log `payment_notification_idempotent_replay` + skip — do NOT re-raise
- Null recipient → log `payment_notification_channel_skipped` + skip — no idempotency row written for absent channel

### Post-commit enqueue (fire-and-forget, never inside txn)
**Source:** `apps/backend/app/api/v1/_internal/yookassa/handlers.py` lines 269-316
**Apply to:** `_post_commit_enqueue` extension + `handle_payment_canceled` + refund webhook/cron post-commit calls

Key rules:
- Enqueue happens AFTER `session.begin()` block exits (never inside the txn)
- `arq_pool is not None` guard on every `enqueue_job` call (None is the unit-test-safe default)
- `_max_tries=3, _expires=60` on every `enqueue_job` call (D-52-Discretion / D-51-Discretion contract)
- AST gate update in the same commit as body change (PATTERNS.md errata #3 discipline)

### Literal `template_id` at dispatcher callsite (AST gate)
**Source:** `apps/backend/tests/unit/test_locked_email_templates_ast.py` + `apps/backend/app/modules/bookings/notifications.py` lines 143-177
**Apply to:** Every `get_email_dispatcher()(template_id=...)` callsite in `tasks.py`

Key rules:
- `template_id=` argument MUST be a string literal `"EMAIL_..."` — never a variable, constant reference, or f-string
- `LOCKED_EMAIL_TEMPLATES` frozenset in `audit.py` must contain the literal BEFORE the test suite runs
- Pattern: `if kind == "payment_succeeded": await dispatcher(template_id="EMAIL_ONLINE_PAYMENT_SUCCEEDED", ...)`

### `op.f()` naming in Alembic migrations
**Source:** `apps/backend/alembic/versions/0035_fiscal_receipts.py` lines 64-83
**Apply to:** `alembic/versions/0039_payment_notifications.py`

Key rules:
- `op.f("pk_<table>")`, `op.f("fk_<table>_<col>_<target_table>")`, `op.f("ck_<table>_<bare_name>")`, `op.f("uq_<table>_<cols>")` on all named constraints
- Downgrade: drop UNIQUE + index BEFORE drop_table
- `down_revision: str | None = "0038_fiscal_receipts_created_at"` (exact string)

---

## No Analog Found

All files have close analogs. No entries in this section.

---

## Metadata

**Analog search scope:** `apps/backend/app/modules/`, `apps/backend/app/api/`, `apps/backend/app/workers/`, `apps/backend/app/core/`, `apps/backend/alembic/versions/`, `apps/backend/tests/`
**Files scanned:** 15 source files read directly
**Pattern extraction date:** 2026-05-23
