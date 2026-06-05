# Phase 84: Real Autopay Charge — Pattern Map

**Mapped:** 2026-06-05
**Files analyzed:** 12 new/modified files
**Analogs found:** 12 / 12

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `app/workers/scheduled/charge_expiring_autopay.py` | worker (cron) | batch, event-driven | `app/workers/scheduled/expire_memberships.py` | exact |
| `app/workers/__init__.py` | config | batch | `app/workers/__init__.py` (lines 110–282) | exact (modify) |
| `app/integrations/yookassa/client.py` | service | request-response | same file (lines 154–322) | exact (modify) |
| `app/modules/autopay_charges/models.py` | model | CRUD | `app/modules/payment_methods/models.py` | exact |
| `alembic/versions/0056_autopay_charges.py` | migration | CRUD | `alembic/versions/0054_loyalty_ledger.py` | exact |
| `alembic/env.py` | config | — | same file (lines 24–45) | exact (modify) |
| `app/modules/autopay_charges/service.py` | service | batch, CRUD | `app/modules/memberships/service.py` (lines 1469–1527) | role-match |
| `app/core/audit.py` | config | — | same file (lines 275–467) | exact (modify) |
| `app/core/audit_payloads.py` | config | — | same file (lines 1273–1412) | exact (modify) |
| `tests/unit/test_audit_taxonomy.py` | test | — | same file (line 237) | exact (modify) |
| `tests/integration/test_phase51_audit_chain_invariants.py` | test | — | same file (line 57) | exact (modify) |
| `app/modules/autopay_charges/notifications.py` | service | event-driven | `app/modules/online_payments/tasks.py` + `notifications.py` | role-match |

---

## Pattern Assignments

### `app/workers/scheduled/charge_expiring_autopay.py` (worker, batch)

**Analog:** `app/workers/scheduled/expire_memberships.py`

**Imports pattern** (lines 30–38):
```python
from __future__ import annotations

from typing import Any

import structlog

from app.modules.<domain> import service as <domain>_service

_log = structlog.get_logger("workers.scheduled.charge_expiring_autopay")
```

**Core cron pattern** (lines 41–72) — caller-owns-txn + commit-in-cron + summary log:
```python
async def charge_expiring_autopay(ctx: dict[str, Any]) -> int:
    """Initiate off-session autopay charges; return count of charge attempts.

    Transaction ownership: this function is the transaction owner.
    The helper _charge_expiring_autopay_memberships does NOT commit
    (carries # noqa: SVC001 caller-owns-txn); commit happens here.
    SQL-level idempotency gate: INSERT ... ON CONFLICT DO NOTHING on
    autopay_charges(membership_id, period_end) is the real guard.
    ARQ unique=True is the second line of defence (Pitfall 4).
    """
    session_factory = ctx["sessionmaker"]
    async with session_factory() as session:
        count = await autopay_service._charge_expiring_autopay_memberships(session)
        await session.commit()

    # Summary log AFTER commit returns (CD-03 convention — <job_name>_complete count=N)
    _log.info("charge_expiring_autopay_complete", count=count)
    return count
```

**SVC001 noqa marker** — the private helper MUST carry this (line 1469 of expire_memberships analog):
```python
async def _charge_expiring_autopay_memberships(  # noqa: SVC001 caller-owns-txn
    session: AsyncSession,
    ...
) -> int:
```

---

### `app/workers/__init__.py` — WorkerSettings additions (config, modify)

**Analog:** `app/workers/__init__.py` lines 92–282

**Pattern 1 — eager ORM import block** (lines 92–109): new model `AutopayCharge` must be imported here for REG-29-04 compliance:
```python
from app.modules.autopay_charges.models import (  # noqa: F401
    AutopayCharge,  # Phase 84 APAY-03 — autopay_charges eager-import (REG-29-04)
)
```

**Pattern 2 — functions list** (lines 134–161): append bare callable to the existing list:
```python
functions: ClassVar[list[Any]] = [
    expire_memberships,
    # ... existing entries ...
    charge_expiring_autopay,  # Phase 84 APAY-01 — daily off-session charge cron
]
```

**Pattern 3 — cron_jobs entry** (lines 172–282): pick a distinct UTC hour not in {0:30, 3:05, 3:15, 3:25, 3:35, 4:00, 20:10}. Use hour=2, minute=0 (01:00 MSK — well separated, not 3:05 which expire_memberships owns):
```python
cron_jobs: ClassVar[list[Any]] = [
    # ... existing entries ...
    # Phase 84 APAY-01 — 01:00 Europe/Moscow (container TZ=UTC → hour=22 previous day,
    # or choose 02:00 UTC = 05:00 MSK). Non-colliding with memberships 03:05 MSK tick.
    # SQL-level idempotency via UNIQUE(membership_id, period_end) ON CONFLICT DO NOTHING
    # is the real gate (PITFALLS Pitfall 4); unique=True dedups concurrent ARQ ticks.
    cron(
        charge_expiring_autopay,
        hour=2,       # 05:00 MSK — distinct from expire_memberships (06:05 MSK)
        minute=0,
        unique=True,
        keep_result=60,
    ),
]
```

---

### `app/integrations/yookassa/client.py` — off-session extension (service, modify)

**Analog:** `app/integrations/yookassa/client.py` lines 154–322 (`create_payment`)

**Extension pattern** — add `payment_method_id: str | None = None` param. When provided, build an off-session body (NO `confirmation` block, `capture=True`, `payment_method_id` key):

```python
async def create_payment(
    self,
    *,
    amount_kopecks: int,
    description: str,
    receipt_items: list[dict[str, Any]],
    customer_email: str | None = None,
    customer_phone: str | None = None,
    idempotency_key: UUID | str,
    confirmation_type: Literal["redirect", "qr"] = "redirect",
    return_url: str | None = None,
    metadata: dict[str, str] | None = None,
    save_payment_method: bool = False,
    payment_method_id: str | None = None,      # <-- NEW Phase 84 APAY-02
) -> YooKassaPaymentResult:
```

**Off-session body** (replace the `confirmation_body` block when `payment_method_id` is set):
```python
if payment_method_id is not None:
    # Off-session recurring charge (APAY-02): no confirmation block.
    # ЮKassa requires payment_method_id + capture=True; omit confirmation entirely.
    body: dict[str, Any] = {
        "amount": {"value": kopecks_to_yookassa(amount_kopecks), "currency": "RUB"},
        "description": description,
        "capture": True,
        "payment_method_id": payment_method_id,
        "receipt": {
            "customer": customer_obj,
            "items": receipt_items,
            "tax_system_code": int(self._settings.tax_system_code),
        },
    }
else:
    # Existing redirect/QR body (byte-identical to today — no change)
    confirmation_body: dict[str, Any]
    if confirmation_type == "redirect":
        ...  # existing code lines 215-223
    body = {
        "amount": ...,
        "capture": True,
        "confirmation": confirmation_body,
        ...
    }
```

**Idempotency key header** (line 246–248): caller-owned, verbatim, single-'t' header:
```python
response = await self._http.post(
    "payments",
    json=body,
    headers={IDEMPOTENCE_KEY_HEADER: str(idempotency_key)},  # ONE 't' — D-48-12
)
```

**Error handling** (lines 271–322): all exceptions classified via `_classify_http_status_error`; off-session path uses the SAME exception handling block — no changes needed there.

---

### `app/modules/autopay_charges/models.py` (model, CRUD)

**Analog:** `app/modules/payment_methods/models.py` (full file, 71 lines)

**Imports pattern** (lines 14–31 of analog):
```python
from __future__ import annotations

from datetime import datetime
from uuid import UUID as UUIDType  # noqa: N811

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PgUUID  # noqa: N811
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, TimestampMixin, UUIDPkMixin
```

**Model composition pattern** — `Base + UUIDPkMixin + TimestampMixin` (no SoftDeleteMixin — lifecycle tracked via `status` column, mirrors Payment model discipline):
```python
class AutopayCharge(Base, UUIDPkMixin, TimestampMixin):
    """Autopay charge claim / idempotency ledger (Phase 84 APAY-03).

    UNIQUE(membership_id, period_end) is the DB-level double-charge guard.
    status: 'pending' → 'succeeded' (via webhook) | 'failed' (sync decline).
    yookassa_payment_id: populated after successful POST /v3/payments.
    """
    __tablename__ = "autopay_charges"

    membership_id: Mapped[UUIDType] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("memberships.id", ondelete="RESTRICT",
                   name="fk_autopay_charges_membership_id_memberships"),
        nullable=False,
    )
    period_end: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("'pending'")
    )
    amount_kopecks: Mapped[int] = mapped_column(Integer, nullable=False)
    yookassa_payment_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    charged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'succeeded', 'failed')",
            name="status",  # NAMING_CONVENTION → ck_autopay_charges_status
        ),
        UniqueConstraint(
            "membership_id", "period_end",
            name="uq_autopay_charges_membership_period",
        ),
    )
```

---

### `alembic/versions/0056_autopay_charges.py` (migration, CRUD)

**Analog:** `alembic/versions/0054_loyalty_ledger.py` (full file, 94 lines)

**File header pattern** (lines 1–38 of analog):
```python
"""autopay_charges idempotency ledger (Phase 84 APAY-03).

Revision ID: 0056_autopay_charges
Revises: 0055_loyalty_redemption_columns
Create Date: 2026-06-05
...
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy import func, text
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0056_autopay_charges"
down_revision: str | None = "0055_loyalty_redemption_columns"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None
```

**upgrade() pattern** (lines 41–88 of analog) — FK + CHECK via `op.f()`, UNIQUE via `UniqueConstraint`:
```python
def upgrade() -> None:
    op.create_table(
        "autopay_charges",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("membership_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("period_end", sa.Date(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default=sa.text("'pending'")),
        sa.Column("amount_kopecks", sa.Integer(), nullable=False),
        sa.Column("yookassa_payment_id", sa.Text(), nullable=True),
        sa.Column("failure_reason", sa.Text(), nullable=True),
        sa.Column("charged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=func.now()),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_autopay_charges")),
        sa.ForeignKeyConstraint(
            ["membership_id"], ["memberships.id"],
            name=op.f("fk_autopay_charges_membership_id_memberships"),
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'succeeded', 'failed')",
            name=op.f("ck_autopay_charges_status"),
        ),
        sa.UniqueConstraint(
            "membership_id", "period_end",
            name="uq_autopay_charges_membership_period",
        ),
    )
    op.create_index(
        op.f("ix_autopay_charges_membership_id"),
        "autopay_charges",
        ["membership_id"],
        unique=False,
    )
```

**downgrade() pattern** (lines 91–94 of analog) — drop in reverse order:
```python
def downgrade() -> None:
    op.drop_index(op.f("ix_autopay_charges_membership_id"), table_name="autopay_charges")
    op.drop_table("autopay_charges")
```

---

### `alembic/env.py` — model allowlist addition (config, modify)

**Analog:** `alembic/env.py` lines 24–45 (existing model imports block)

Add after line 44 (`import app.modules.loyalty.models`):
```python
import app.modules.autopay_charges.models  # Phase 84 APAY-03 / 0056
```

If `autopay_charges` uses a literal-named partial index (e.g. a partial unique ON CONFLICT index), add it to `_include_object`'s skip-list (lines 76–106) following the `uq_loyalty_ledger_welcome` precedent (lines 98–104):
```python
# Phase 84 APAY-03 / 0056: if any partial-index literals are used, skip them here.
```

---

### `app/modules/autopay_charges/service.py` (service, batch)

**Analog:** `app/modules/memberships/service.py` lines 1469–1527 (`_expire_due_memberships`)

**Private helper pattern** — caller-owns-txn marker + no commit inside:
```python
async def _charge_expiring_autopay_memberships(  # noqa: SVC001 caller-owns-txn
    session: AsyncSession,
    today: date | None = None,
    window_days: int = 3,          # APAY-01 configurable window
) -> int:
    """Initiate off-session charges for eligible expiring memberships.

    Does NOT commit — caller (charge_expiring_autopay cron) owns the txn.
    SQL-level idempotency: INSERT INTO autopay_charges ... ON CONFLICT DO NOTHING.
    Returns count of charge attempts initiated.
    """
```

**Eligibility query pattern** — raw SQL via `session.execute(text(...))`:
```python
    # Find memberships expiring within [today, today + window_days]
    # with autopay_enabled=true, consent_recorded_at IS NOT NULL,
    # and an active saved card. Raw SQL (D-54-08 — no cross-module ORM).
    rows = await session.execute(
        text("""
            SELECT
                m.id AS membership_id,
                m.end_date,
                m.client_id,
                mp.price_kopecks,
                cpm.yookassa_method_id
            FROM memberships m
            JOIN membership_plans mp ON mp.id = m.plan_id
            JOIN client_payment_methods cpm
                ON cpm.client_id = m.client_id
                AND cpm.unlinked_at IS NULL
                AND cpm.autopay_enabled = true
                AND cpm.consent_recorded_at IS NOT NULL
            WHERE m.status = 'active'
              AND m.end_date >= :today
              AND m.end_date <= :window_end
        """),
        {"today": today, "window_end": today + timedelta(days=window_days)},
    )
```

**Claim-before-charge idempotency** — INSERT claim first, check for conflict:
```python
    # INSERT claim row — ON CONFLICT DO NOTHING is the primary double-charge guard.
    # (APAY-03 discipline: claim first, call YooKassa second)
    result = await session.execute(
        text("""
            INSERT INTO autopay_charges
                (membership_id, period_end, status, amount_kopecks)
            VALUES (:membership_id, :period_end, 'pending', :amount_kopecks)
            ON CONFLICT (membership_id, period_end) DO NOTHING
            RETURNING id
        """),
        {...},
    )
    if result.rowcount == 0:
        continue  # already claimed — skip (Pitfall 4 SQL gate)
```

**Audit emit pattern** — literal strings, actor_user_id=None (system cron):
```python
    await audit.emit(
        session,
        "autopay_charge_initiated",      # LITERAL (Phase 15 INFRA-11 AST gate)
        actor_user_id=None,              # system-driven cron — no human actor
        resource_type="autopay",         # LITERAL
        resource_id=charge_row_id,
        membership_id=str(membership_id),
        amount_kopecks=amount_kopecks,
        period_end=str(period_end),
    )
```

---

### `app/core/audit.py` — LOCKED_AUDIT_EVENTS additions (config, modify)

**Analog:** `app/core/audit.py` lines 459–467 (Phase 83 `loyalty_redeemed` block — last addition)

Add after line 467 (the `loyalty_redeemed` pair):
```python
        # v2.3 (Phase 84 lock — INFRA-15; registered BEFORE any callsite in
        # charge_expiring_autopay / autopay service)
        # Autopay charge lifecycle (APAY-01 cron initiated + APAY-03 failure):
        # Pre-registered BEFORE any callsite per INFRA-15 discipline.
        ("autopay_charge_initiated", "autopay"),
        ("autopay_charge_failed", "autopay"),
```

---

### `app/core/audit_payloads.py` — new payload classes + registry entries (config, modify)

**Analog:** `app/core/audit_payloads.py` lines 1273–1412 (LoyaltyAccruedPayload + LoyaltyRedeemedPayload + AUDIT_PAYLOAD_SCHEMAS additions)

**New payload classes** (append after LoyaltyRedeemedPayload at line ~1311):
```python
# ---------------------------------------------------------------------------
# Autopay charge lifecycle (Phase 84 APAY-01/APAY-03)
# ---------------------------------------------------------------------------


class AutopayChargeInitiatedPayload(BaseModel):
    """Payload schema for ("autopay_charge_initiated", "autopay") — Phase 84 APAY-01.

    Emitted by the charge_expiring_autopay cron when a charge claim is inserted
    and the YooKassa call is made. resource_id = autopay_charges.id.
    Pre-registered BEFORE callsite per INFRA-15 discipline.
    """

    model_config = ConfigDict(extra="forbid")

    membership_id: UUID
    amount_kopecks: int
    period_end: str          # ISO date string (JSONB-serialisable, no date type)


class AutopayChargeFailedPayload(BaseModel):
    """Payload schema for ("autopay_charge_failed", "autopay") — Phase 84 APAY-03.

    Emitted on a synchronous YooKassa decline/error.
    failure_reason carries the YooKassaPaymentResult.classification or error_code.
    """

    model_config = ConfigDict(extra="forbid")

    membership_id: UUID
    amount_kopecks: int
    period_end: str          # ISO date string
    failure_reason: str
```

**AUDIT_PAYLOAD_SCHEMAS entries** (append after line ~1411):
```python
    # v2.3 (Phase 84 lock — autopay lifecycle):
    ("autopay_charge_initiated", "autopay"): AutopayChargeInitiatedPayload,
    ("autopay_charge_failed", "autopay"): AutopayChargeFailedPayload,
```

---

### `tests/unit/test_audit_taxonomy.py` — count-lock bump (test, modify)

**Analog:** `tests/unit/test_audit_taxonomy.py` lines 237–242

Two new LOCKED events → bump 103 → 105:
```python
    assert len(LOCKED_AUDIT_EVENTS) == 105, (
        "LOCKED_AUDIT_EVENTS size drifted: expected 105 "
        ...
        f"got {len(LOCKED_AUDIT_EVENTS)}"
    )
```

---

### `tests/integration/test_phase51_audit_chain_invariants.py` — count-lock bump (test, modify)

**Analog:** `tests/integration/test_phase51_audit_chain_invariants.py` lines 57–63

Same bump — both count assertions must move together:
```python
    assert len(LOCKED_AUDIT_EVENTS) == 105, (
        f"Expected 105 LOCKED_AUDIT_EVENTS after Phase 84 (v2.3), got {len(LOCKED_AUDIT_EVENTS)}. "
        "+2 v2.3/P84: autopay_charge_initiated + autopay_charge_failed (APAY-01/APAY-03, INFRA-15)."
    )
```

---

### `app/modules/autopay_charges/notifications.py` (service, event-driven)

**Analog:** `app/modules/online_payments/tasks.py` (full file) + `app/modules/online_payments/notifications.py`

**Claim-before-send idempotency pattern** (lines 399–424 of online_payments/tasks.py):
```python
# CLAIM via idempotency INSERT (channel discriminator) — claim-before-send (D-52-02).
# Use a separate notifications ledger or piggyback on autopay_charges.status per-channel
# (TBD at plan time — see online_payments/repository.py:claim_payment_notification).
claimed = await claim_autopay_notification(
    session_factory, kind=kind, channel=channel, autopay_charge_id=charge_id
)
if not claimed:
    _log.info("autopay_notification_idempotent_replay", ...)
    continue
```

**Cross-channel loop** (lines 352–499 of online_payments/tasks.py) — for channel in ("telegram", "email"):
```python
for channel in ("telegram", "email"):
    # 1. resolve recipient
    # 2. claim idempotency
    # 3. send (best-effort — never re-raise, one channel failure never blocks the other)
    try:
        if channel == "telegram":
            await telegram_sender.send_text_dm(bot, chat_id=chat_id, text=text)
        else:
            await dispatcher(template_id="EMAIL_AUTOPAY_CHARGE_SUCCEEDED", ...)
    except Exception:
        _log.exception("autopay_notification_send_failed", ...)
        continue
```

**Bot construction pattern** (line 321 of online_payments/tasks.py) — fresh per invocation:
```python
bot = build_bot(token=settings.telegram_bot_token.get_secret_value())
```

**Cross-module table access pattern** (lines 71–97 of online_payments/tasks.py) — use `Base.metadata.tables["memberships"]` etc., never import another module's ORM:
```python
def _memberships_table() -> Any:
    from app.core.database import Base
    return Base.metadata.tables["memberships"]
```

---

## Shared Patterns

### Caller-Owns-Transaction (all service helpers called from cron)
**Source:** `app/modules/memberships/service.py` line 1469 + `app/workers/scheduled/expire_memberships.py` lines 63–71
**Apply to:** `_charge_expiring_autopay_memberships` helper AND the `charge_expiring_autopay` cron entry

Pattern: helper carries `# noqa: SVC001 caller-owns-txn` marker; cron function wraps `async with session_factory() as session:` → calls helper → `await session.commit()` → summary log after commit.

### SQL-Level Idempotency Gate
**Source:** `app/workers/__init__.py` (docstring Pitfall 4, lines 26–31) + `app/modules/memberships/service.py` lines 1483–1489
**Apply to:** `charge_expiring_autopay` cron

Pattern: `INSERT ... ON CONFLICT DO NOTHING` on `autopay_charges(membership_id, period_end)` is the REAL gate. ARQ `unique=True` is second line. Never rely on application-level dedup alone.

### Deterministic Idempotency Key for YooKassa
**Source:** `app/integrations/yookassa/client.py` lines 154–167 (UUID | str param, "D-48-11 + D-49-08 widening") + `IDEMPOTENCE_KEY_HEADER` line 77
**Apply to:** off-session `create_payment` call in autopay service

Pattern: derive key deterministically from `(membership_id, period_end)` — e.g. `hashlib.sha256(f"{membership_id}:{period_end}".encode()).hexdigest()`. Pass as `str` to `create_payment(idempotency_key=...)`. The adapter sends it verbatim in `Idempotence-Key` header (ONE 't').

### Audit Pre-Registration (INFRA-15)
**Source:** `app/core/audit.py` lines 275–467 (LOCKED_AUDIT_EVENTS frozenset)
**Apply to:** `autopay_charge_initiated` and `autopay_charge_failed` pairs

Pattern: add pairs to `LOCKED_AUDIT_EVENTS` AND `AUDIT_PAYLOAD_SCHEMAS` AND bump count-lock tests BEFORE writing any callsite. Callsite added after the frozenset update in the same phase. Literal strings only at emit() callsites (AST gate).

### Cross-Module Read (raw SQL, D-54-08)
**Source:** `app/modules/payment_methods/repository.py` lines 1–14 + `app/modules/online_payments/tasks.py` lines 71–97
**Apply to:** any autopay service query that touches `memberships`, `membership_plans`, `client_payment_methods`, `clients`

Pattern: `from sqlalchemy import text` + bind-param `text("SELECT ... WHERE id = :id")` dict form; OR `Base.metadata.tables["table_name"]` for column-level SA Table references. Never import another module's ORM model from a service that is not in that module.

### YooKassaPaymentResult Classification
**Source:** `app/integrations/yookassa/types.py` lines 54–106 + `app/integrations/yookassa/client.py` lines 271–322
**Apply to:** off-session charge result handling in `_charge_expiring_autopay_memberships`

Pattern: `result.classification` switches on `Literal["ok", "validation_error", "transient_error", "permanent_error"]`. On `ok`: update claim row `status='pending'`, store `yookassa_payment_id`. On failure: update claim row `status='failed'`, store `failure_reason=result.classification` (or `result.error_code`), emit `autopay_charge_failed`, dispatch failure notification.

### Notification Channel Idempotency (D-52-02 channel discriminator)
**Source:** `app/modules/online_payments/tasks.py` lines 399–424 + `app/modules/payments/models.py` lines 124–196 (PaymentReceipt UNIQUE on payment_id+channel)
**Apply to:** autopay success/failure notification dispatch

Pattern: claim-before-send — INSERT notification claim row with UNIQUE(charge_id, channel) before sending; on conflict skip (idempotent replay). Never re-raise send exception (best-effort, D-52-02 / D-45-08). Loop over `("telegram", "email")` channels.

### Webhook-Locked Activation (D-06)
**Source:** `app/api/v1/_internal/yookassa/handlers.py` lines 346–671 (`handle_payment_succeeded`)
**Apply to:** renewal membership creation on autopay charge success

Pattern: the `charge_expiring_autopay` cron ONLY initiates the charge (POST /v3/payments). Membership renewal DOES NOT happen in the cron. When the `payment.succeeded` webhook fires, the EXISTING `handle_payment_succeeded` UoW path creates/extends the membership. No code changes needed in handlers.py — the autopay payment flow goes through the same webhook handler as regular online payments (subject_kind='membership', subject_id=membership_plan_id in the OnlinePayment row created by the charge).

### Summary Log Shape (CD-03 convention)
**Source:** `app/workers/scheduled/expire_memberships.py` line 71
**Apply to:** `charge_expiring_autopay` cron

Pattern: `_log.info("<job_name>_complete", count=N)` AFTER `await session.commit()` returns. NOT an audit event — ops summary line only. job_id/job_name are on the contextvars stack automatically from `on_job_start`.

---

## Count-Lock Test Locations

Both count-lock tests must be bumped from 103 → 105 in the same commit as the `LOCKED_AUDIT_EVENTS` addition:

| File | Line | Current value | New value |
|---|---|---|---|
| `tests/unit/test_audit_taxonomy.py` | 237 | 103 | 105 |
| `tests/integration/test_phase51_audit_chain_invariants.py` | 57 | 103 | 105 |

---

## No Analog Found

All files have close analogs. No new patterns without precedent.

---

## Metadata

**Analog search scope:** `apps/backend/app/workers/`, `apps/backend/app/integrations/yookassa/`, `apps/backend/app/modules/{payment_methods,payments,memberships,online_payments}/`, `apps/backend/app/core/`, `apps/backend/alembic/versions/0054*`, `apps/backend/alembic/versions/0055*`, `apps/backend/alembic/env.py`, `apps/backend/tests/`
**Files scanned:** 20
**Pattern extraction date:** 2026-06-05
