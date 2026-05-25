# Phase 58: Payroll Foundations + Ledger — Pattern Map

**Mapped:** 2026-05-25
**Files analyzed:** 21 new + 7 edited = 28 total
**Analogs found:** 28 / 28 (100% coverage — all new files mirror established v1.4/v1.7/v1.8 disciplines verbatim)

---

## File Classification

### Backend — NEW module `app/modules/payroll/`

| New File | Role | Data Flow | Closest Analog | Match Quality |
|----------|------|-----------|----------------|---------------|
| `apps/backend/app/modules/payroll/__init__.py` | module marker | n/a | `apps/backend/app/modules/payments/__init__.py` | exact |
| `apps/backend/app/modules/payroll/constants.py` | constants (subject-kind literals, error codes) | n/a | `apps/backend/app/modules/pt_packages/constants.py` (locally-pinned literal pattern) | exact |
| `apps/backend/app/modules/payroll/models.py` | ORM (append-only ledger + INSERT-only versioned config) | DB writes | `apps/backend/app/modules/payments/models.py` (Payment append-only) + `apps/backend/app/modules/memberships/models.py` (snapshot columns) | exact (hybrid) |
| `apps/backend/app/modules/payroll/schemas.py` | Pydantic request/response (ResponseEnvelope shape) | wire format | `apps/backend/app/modules/payments/schemas.py` | exact |
| `apps/backend/app/modules/payroll/repository.py` | DB INSERTs + raw-SQL `text()` cross-module reads | DB I/O | `apps/backend/app/modules/reports/repository.py` (raw-SQL cross-module read) + `apps/backend/app/modules/payments/repository.py` (caller-owns-flush INSERT) | exact (hybrid) |
| `apps/backend/app/modules/payroll/service.py` | orchestrator (preview, run, mark-paid, list, clawback recorder) | request-response | `apps/backend/app/modules/pt_packages/service.py:1038` `refund_pt_package` (D-33-11 atomic UoW) + `apps/backend/app/modules/payments/service.py:168` `issue_refund` (caller-owns-txn Protocol-slot consumer) | exact (hybrid) |
| `apps/backend/app/modules/payroll/router.py` | FastAPI router (7 owner-only endpoints) | request-response | `apps/backend/app/modules/payments/router.py` (owner-only RBAC + ResponseEnvelope) | exact |

### Backend — EDIT

| Edited File | Role | Insertion Pattern | Closest Analog |
|-------------|------|-------------------|----------------|
| `apps/backend/app/core/permissions.py` | RBAC frozenset growth | Append 4-6 tuples + bump count comment 35 → 39-41 | Phase 54 INFRA-42 audit-log tuple insertion at lines 125-129 |
| `apps/backend/app/core/audit.py` | LOCKED_AUDIT_EVENTS frozenset growth | Append 4-6 `(event, resource_type)` tuples at end of frozenset (line 394) | Phase 51 online_refund insertion at lines 386-394 |
| `apps/backend/app/core/audit_payloads.py` | Pydantic payload schemas + AUDIT_PAYLOAD_SCHEMAS registry | New `class TrainerCompConfigSetPayload(BaseModel)` + `class PayrollAccrual*Payload(BaseModel)` + 4-6 new registry entries at end of dict | `RefundIssuedPayload` (line 114) + registry append pattern at lines 1140-1147 |
| `apps/backend/app/core/dependencies.py` | Protocol slot getter + register fn | Add `class PayrollClawbackRecorder(Protocol)` + `_payroll_clawback_recorder` global + `register_*` + `get_*` defensive accessor | `PaymentRefunder` Protocol at lines 373-396 + `register_payment_refunder` at line 409 + `get_payment_refunder` at line 427 |
| `apps/backend/app/main.py` | Protocol slot wiring at startup | Add `from app.modules.payroll import service as payroll_service` + `register_payroll_clawback_recorder(payroll_service.record_clawback_for_pt_package_refund)` | `register_payment_refunder(payments_service.issue_refund)` at line 246 |
| `apps/backend/app/modules/pt_packages/service.py:1038` `refund_pt_package` | Insert clawback hook call between current steps 6 and 8 | `clawback_id = await get_payroll_clawback_recorder()(session, actor=actor, refund_payment_id=refund_payment.id, pt_package_id=pt_package.id)` BEFORE `await session.commit()` (line 1170) | Step 3 PaymentRefunder consumption at lines 1126-1136 |
| `apps/backend/.importlinter` | Add `app.modules.payroll` to `modules-independent` `modules =` list | Sorted append (after `app.modules.online_refunds`), with comment `# Phase 58 INFRA-15 / D-58-18 — payroll module ...` | Phase 54 D-54-09 `reports` preemptive add at lines 26-31 of `.importlinter` |
| `apps/backend/app/api/v1/router.py` | Mount `payroll_router` under `/api/v1/payroll/` | Add `from app.modules.payroll.router import router as payroll_router` + `v1.include_router(payroll_router, prefix="/payroll", tags=["payroll"])` (alphabetical after `payments_router`) | Line 52: `v1.include_router(payments_router, prefix="/payments", tags=["payments"])` |

### Backend — NEW Alembic migration

| New File | Role | Closest Analog | Match Quality |
|----------|------|----------------|---------------|
| `apps/backend/alembic/versions/0041_payroll_foundations.py` | Schema migration (2 new tables) | `apps/backend/alembic/versions/0034_online_payments.py` (full table create with FKs, CHECKs, partial UNIQUE) | exact |

### Backend — NEW tests

| New File | Role | Closest Analog |
|----------|------|----------------|
| `apps/backend/tests/integration/payroll/__init__.py` | package marker | `apps/backend/tests/integration/reports/__init__.py` |
| `apps/backend/tests/integration/payroll/conftest.py` | re-exports owner/reception clients + payroll factories | `apps/backend/tests/integration/reports/conftest.py:1-65` |
| `apps/backend/tests/integration/payroll/test_payroll_comp_config.py` (PAY-01) | integration test (PUT/GET) | `apps/backend/tests/integration/reports/test_reports_revenue.py` |
| `apps/backend/tests/integration/payroll/test_payroll_preview.py` (PAY-02) | integration test | same |
| `apps/backend/tests/integration/payroll/test_payroll_accrual_create.py` (PAY-03) | integration test (409/422 surfaces) | same |
| `apps/backend/tests/integration/payroll/test_payroll_mark_paid.py` (PAY-04) | integration test (409 already_paid) | same |
| `apps/backend/tests/integration/payroll/test_payroll_list.py` (PAY-05) | integration test (pagination) | same |
| `apps/backend/tests/integration/payroll/test_payroll_clawback.py` (PAY-06) | integration test (same-UoW invariant) | same + `apps/backend/tests/integration/pt_packages/test_pt_package_refund.py` (if exists) |
| `apps/backend/tests/integration/payroll/test_payroll_rbac.py` | RBAC denial for reception (all 7 endpoints) | `apps/backend/tests/integration/reports/test_reports_revenue.py::test_reception_forbidden` |

### Frontend — EDIT (admin-web — only files allowed in v1.9)

| Edited File | Role | Pattern |
|-------------|------|---------|
| `apps/admin-web/src/shared/session/can.ts` | OWNER_ONLY array byte-semantic mirror | Append 4-6 `{ action, resource }` entries verbatim mirroring permissions.py (with Phase 58 comment block mirroring Phase 54 audit-log block at lines 63-66) |
| `apps/admin-web/src/shared/session/registry.ts` | resource union (NO CHANGE — `payroll`/`compensation` already exist at lines 8-9; only confirm parity) | n/a |

---

## Pattern Assignments

### 1. `apps/backend/app/modules/payroll/models.py` (ORM, append-only ledger + INSERT-only config)

**Analog A (Payment append-only):** `apps/backend/app/modules/payments/models.py:44-121`
**Analog B (snapshot columns):** `apps/backend/app/modules/memberships/models.py:128-167`

**Imports + base composition** (mirror `payments/models.py:21-41`):
```python
from __future__ import annotations
from datetime import date, datetime
from uuid import UUID as UUIDType  # noqa: N811

from sqlalchemy import (
    CheckConstraint, Date, DateTime, ForeignKey, Index, Integer, Text,
    UniqueConstraint, func, text,
)
from sqlalchemy.dialects.postgresql import UUID as PgUUID  # noqa: N811
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, UUIDPkMixin
```

**`TrainerCompConfig` (INSERT-only versioned, D-58-02)** — derive shape from `Payment` (no TimestampMixin, no SoftDeleteMixin; single temporal column `effective_from` per D-58-02). Pattern:
```python
class TrainerCompConfig(Base, UUIDPkMixin):
    __tablename__ = "trainer_comp_configs"

    trainer_id: Mapped[UUIDType] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("trainers.id", ondelete="RESTRICT",
                   name="fk_trainer_comp_configs_trainer_id_trainers"),
        nullable=False,
    )
    commission_pct_bps: Mapped[int | None] = mapped_column(Integer, nullable=True)
    session_fee_kopecks: Mapped[int | None] = mapped_column(Integer, nullable=True)
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(),
    )
    created_by_user_id: Mapped[UUIDType | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT",
                   name="fk_trainer_comp_configs_created_by_user_id_users"),
        nullable=True,
    )

    __table_args__ = (
        CheckConstraint(
            "commission_pct_bps IS NULL OR (commission_pct_bps >= 0 AND commission_pct_bps <= 10000)",
            name="commission_pct_bps_range",
        ),
        CheckConstraint(
            "session_fee_kopecks IS NULL OR session_fee_kopecks >= 0",
            name="session_fee_kopecks_nonneg",
        ),
        Index("ix_trainer_comp_configs_trainer_effective",
              "trainer_id", text("effective_from DESC")),
    )
```

**`TrainerPayrollAccrual` (append-only signed-amount, D-58-03)** — mirrors `Payment` (no TimestampMixin) plus snapshot columns from `Membership.plan_name_snapshot`/`price_kopecks_snapshot` discipline. CRITICAL invariants:

- **NO `TimestampMixin`** (`apps/backend/app/modules/payments/models.py:47`: "NO TimestampMixin (no created_at/updated_at)") — `accrued_at` is the single creation temporal column; `paid_at` is the lifecycle column.
- **Snapshot columns frozen at INSERT** (mirror `memberships/models.py:128-131`: `plan_name_snapshot`, `duration_days_snapshot`, `price_kopecks_snapshot`, `freeze_days_limit_snapshot`).
- **Self-FK for clawback** mirrors `Payment.refund_of` (`payments/models.py:81-89`).
- **Partial UNIQUE excluding clawback rows** mirrors `uq_payments_refund_of_alive` (`payments/models.py:112-117`).

Pattern excerpt (column block — derive remaining from analog):
```python
class TrainerPayrollAccrual(Base, UUIDPkMixin):
    """Append-only payroll accrual row (PAY-03 / D-58-03).

    NO TimestampMixin (no created_at/updated_at), NO SoftDeleteMixin —
    accrued_at is the SINGLE creation temporal column per D-58-03.
    UPDATE/DELETE banned by AST gate tests/unit/test_payroll_appendonly.py
    (planner to add — mirrors test_payments_appendonly.py).
    """
    __tablename__ = "trainer_payroll_accruals"

    trainer_id: Mapped[UUIDType] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("trainers.id", ondelete="RESTRICT",
                   name="fk_trainer_payroll_accruals_trainer_id_trainers"),
        nullable=False,
    )
    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)
    sessions_count: Mapped[int] = mapped_column(Integer, nullable=False)
    revenue_kopecks: Mapped[int] = mapped_column(Integer, nullable=False)
    commission_pct_bps_snapshot: Mapped[int | None] = mapped_column(Integer, nullable=True)
    session_fee_kopecks_snapshot: Mapped[int | None] = mapped_column(Integer, nullable=True)
    comp_config_id_snapshot: Mapped[UUIDType] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("trainer_comp_configs.id", ondelete="RESTRICT",
                   name="fk_trainer_payroll_accruals_comp_config_id_snapshot"),
        nullable=False,
    )
    accrual_kopecks: Mapped[int] = mapped_column(Integer, nullable=False)  # signed
    status: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("'pending'"),
    )
    accrued_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(),
    )
    paid_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    paid_by_user_id: Mapped[UUIDType | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT",
                   name="fk_trainer_payroll_accruals_paid_by_user_id_users"),
        nullable=True,
    )
    # Clawback self-FK (mirror Payment.refund_of)
    clawback_of_accrual_id: Mapped[UUIDType | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("trainer_payroll_accruals.id", ondelete="RESTRICT",
                   name="fk_trainer_payroll_accruals_clawback_of_accrual_id"),
        nullable=True,
    )
    source_refund_payment_id: Mapped[UUIDType | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("payments.id", ondelete="RESTRICT",
                   name="fk_trainer_payroll_accruals_source_refund_payment_id"),
        nullable=True,
    )
    audit_log_id: Mapped[UUIDType | None] = mapped_column(  # mirror Payment.audit_log_id
        PgUUID(as_uuid=True),
        ForeignKey("audit_log.id", ondelete="SET NULL",
                   name="fk_trainer_payroll_accruals_audit_log_id_audit_log"),
        nullable=True,
    )

    __table_args__ = (
        CheckConstraint("status IN ('pending','paid')", name="status"),
        CheckConstraint(
            "(clawback_of_accrual_id IS NULL AND source_refund_payment_id IS NULL) "
            "OR (clawback_of_accrual_id IS NOT NULL AND source_refund_payment_id IS NOT NULL)",
            name="clawback_fks_paired",
        ),
        # PARTIAL UNIQUE (mirror payments/models.py:112-117 uq_payments_refund_of_alive)
        Index(
            "uq_trainer_payroll_accruals_period_alive",
            "trainer_id", "period_start", "period_end",
            unique=True,
            postgresql_where=text("clawback_of_accrual_id IS NULL"),
        ),
        Index("ix_trainer_payroll_accruals_trainer_accrued",
              "trainer_id", text("accrued_at DESC")),
        Index("ix_trainer_payroll_accruals_status_period",
              "status", text("period_start DESC")),
    )
```

**Constraints to preserve:**
- Mirror `Payment` "NO TimestampMixin" comment block verbatim (`apps/backend/app/modules/payments/models.py:1-19`) to document append-only intent.
- Constraint naming uses NAMING_CONVENTION short names (`name="status"` expands to `ck_trainer_payroll_accruals_status` automatically — see `payments/models.py:104-110` for the precedent).
- Partial UNIQUE `WHERE clawback_of_accrual_id IS NULL` (D-58-03) — never a full UNIQUE that breaks clawback inserts.

---

### 2. `apps/backend/alembic/versions/0041_payroll_foundations.py` (Alembic migration)

**Analog:** `apps/backend/alembic/versions/0034_online_payments.py` (lines 1-167) — full `op.create_table` with FKs, CHECKs, partial UNIQUE indexes via `postgresql_where`.

**Header pattern** (lines 1-44):
```python
"""trainer_comp_configs + trainer_payroll_accruals tables (Phase 58 PAY-01..03 / D-58-02..05).

Revision ID: 0041_payroll_foundations
Revises: 0040_audit_log_report_indexes
Create Date: 2026-05-25 00:00:00.000000

Phase 58 PAY-01..06 schema. Ships TWO tables + partial UNIQUE (excluding
clawback rows per D-58-03) in ONE migration (atomic per success-criterion #5).

Partial UNIQUE pattern mirrors Phase 32 uq_payments_refund_of_alive and
Phase 49 uq_online_payments_*_double_tap precedent.

ORM model is intentionally NOT added by this migration; Plan 58-02 owns
``app/modules/payroll/models.py``.
"""
from __future__ import annotations
from collections.abc import Sequence
import sqlalchemy as sa
from sqlalchemy import text
from sqlalchemy.dialects import postgresql
from alembic import op

revision: str = "0041_payroll_foundations"
down_revision: str | None = "0040_audit_log_report_indexes"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None
```

**`op.create_table` shape** (mirror `0034_online_payments.py:47-136`):
```python
op.create_table(
    "trainer_payroll_accruals",
    sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
              nullable=False, server_default=sa.text("gen_random_uuid()")),
    sa.Column("trainer_id", postgresql.UUID(as_uuid=True),
        sa.ForeignKey("trainers.id", ondelete="RESTRICT",
                      name=op.f("fk_trainer_payroll_accruals_trainer_id_trainers")),
        nullable=False),
    # ... (all snapshot + lifecycle columns per D-58-03)
    sa.CheckConstraint("status IN ('pending','paid')",
                       name=op.f("ck_trainer_payroll_accruals_status")),
    sa.CheckConstraint(
        "(clawback_of_accrual_id IS NULL AND source_refund_payment_id IS NULL) "
        "OR (clawback_of_accrual_id IS NOT NULL AND source_refund_payment_id IS NOT NULL)",
        name=op.f("ck_trainer_payroll_accruals_clawback_fks_paired"),
    ),
)
# Partial UNIQUE — mirror payments/models.py:112-117 + 0034:139-156
op.create_index(
    "uq_trainer_payroll_accruals_period_alive",
    "trainer_payroll_accruals",
    ["trainer_id", "period_start", "period_end"],
    unique=True,
    postgresql_where=text("clawback_of_accrual_id IS NULL"),
)
```

**`downgrade()` pattern** (mirror `0034_online_payments.py:159-166`): drop indexes in reverse order, then `op.drop_table`.

**Invariants to preserve:**
- `down_revision: str | None = "0040_audit_log_report_indexes"` — head 0040 → 0041 (only successor).
- All constraint names go through `op.f(...)` for NAMING_CONVENTION consistency (mirror lines 63, 73, 83 throughout `0034_online_payments.py`).
- `gen_random_uuid()` server_default on `id` columns (mirror line 55).
- `server_default=sa.func.now()` on temporal columns (mirror line 97-98).

---

### 3. `apps/backend/app/modules/payroll/repository.py` (raw-SQL cross-module reads + ORM INSERTs)

**Analog A (raw-SQL cross-module read):** `apps/backend/app/modules/reports/repository.py:56-93` (`fetch_revenue_buckets`)
**Analog B (caller-owns-flush INSERT):** `apps/backend/app/modules/payments/repository.py:65-95` (`insert_payment`)

**Module docstring discipline** (mirror `reports/repository.py:1-27`):
```python
"""Payroll repository — raw-SQL cross-module reads + ORM writes for payroll tables.

CROSS-MODULE READ DISCIPLINE (D-58-19 / D-54-08 / Phase 49 D-49-03 precedent):
  - ``from sqlalchemy import text`` — NEVER import another module's ORM model.
  - Bind params via ``:name`` placeholders + a dict; cast UUIDs to ``str``.
  - ``.mappings().one()`` for scalar/aggregate reads.
  - Each reader documents verified columns + source file:line of the foreign table.

OWN-MODULE WRITE DISCIPLINE (D-32-10 caller-owns-txn precedent):
  - NO ``session.flush()`` / ``session.commit()`` calls here.
  - Service layer owns the transactional moment so audit row + accrual row co-write.

INVARIANTS:
  - ZERO INSERT/UPDATE/DELETE against pt_sessions, payments, pt_packages.
  - ORM model imports from other modules (app.modules.*): FORBIDDEN.
  - ORM model imports from app.modules.payroll.*: ALLOWED (own module).
"""
```

**Cross-module read pattern (`fetch_trainer_session_revenue`)** — verbatim mirror of `reports/repository.py:79-93` + ARCHITECTURE.md Q1 SQL shape. Use **verified column comments** mirroring `reports/repository.py:62-67`:
```python
async def fetch_trainer_session_revenue(
    session: AsyncSession,
    trainer_id: UUID,
    period_start: date,
    period_end: date,
) -> dict[str, int]:
    """CROSS-MODULE READ — raw SQL text() only; NO ORM import.

    Verified columns:
      - pt_sessions.trainer_id, pt_package_id, performed_at, cancelled_at
        (apps/backend/app/modules/pt_sessions/models.py — VERIFY at plan time)
      - payments.subject_kind, subject_id, amount_kopecks, received_at
        (apps/backend/app/modules/payments/models.py:53-67)
      - pt_packages.id, trainer_id (FK bridge — VERIFY trainer_id non-nullable)

    -- attribution: assigned-at-sale (pct of pt_packages.trainer_id)
    -- attribution: conducting (session_fee on pt_sessions.trainer_id)
    Per D-58-21 every cross-module query carries an attribution comment.
    """
    row = (
        await session.execute(
            text(
                "SELECT "
                "  COUNT(DISTINCT ps.id) FILTER (WHERE ps.cancelled_at IS NULL) "
                "    AS session_count, "
                "  COALESCE(SUM(p.amount_kopecks) FILTER ("
                "    WHERE p.subject_kind = 'pt_package' AND p.amount_kopecks > 0"
                "  ), 0) AS revenue_kopecks "
                "FROM pt_sessions ps "
                "JOIN pt_packages pkg ON pkg.id = ps.pt_package_id "
                "JOIN payments p ON p.subject_id = pkg.id "
                "  AND p.subject_kind = 'pt_package' AND p.amount_kopecks > 0 "
                "WHERE ps.trainer_id = :trainer_id "
                "  AND (ps.performed_at AT TIME ZONE 'Europe/Moscow')::date "
                "      BETWEEN :period_start AND :period_end "
            ),
            {"trainer_id": str(trainer_id),
             "period_start": period_start, "period_end": period_end},
        )
    ).mappings().one()
    return {"session_count": int(row["session_count"]),
            "revenue_kopecks": int(row["revenue_kopecks"])}
```

**Own-module INSERT (`insert_accrual_idempotent`) — DB-wins-the-race idempotency (D-58-06)**, mirror `payments/repository.py:65-95` shape + the `ON CONFLICT DO NOTHING RETURNING id` pattern noted in research:
```python
async def insert_accrual_idempotent(
    session: AsyncSession,
    *,
    trainer_id: UUID,
    period_start: date,
    period_end: date,
    # ... snapshot kwargs ...
    accrual_kopecks: int,
) -> UUID | None:
    """INSERT-ON-CONFLICT-DO-NOTHING (D-58-06). Returns new id or None on conflict.

    Service layer maps None → PayrollPeriodAlreadyRunError (409). Caller owns flush.
    """
    result = await session.execute(
        text(
            "INSERT INTO trainer_payroll_accruals "
            "  (id, trainer_id, period_start, period_end, sessions_count, "
            "   revenue_kopecks, commission_pct_bps_snapshot, session_fee_kopecks_snapshot, "
            "   comp_config_id_snapshot, accrual_kopecks, status) "
            "VALUES "
            "  (gen_random_uuid(), :trainer_id, :period_start, :period_end, "
            "   :sessions_count, :revenue_kopecks, :pct_bps, :fee, "
            "   :comp_id, :accrual_kopecks, 'pending') "
            "ON CONFLICT (trainer_id, period_start, period_end) "
            "WHERE clawback_of_accrual_id IS NULL DO NOTHING "
            "RETURNING id"
        ),
        {"trainer_id": str(trainer_id), ...},
    )
    row = result.mappings().first()
    return row["id"] if row else None
```

**Resolver for INSERT-only versioned config (D-58-02)**: `ORDER BY effective_from DESC LIMIT 1 WHERE effective_from <= :as_of_date` — own-module ORM `select()` (no raw-SQL needed; payroll owns `trainer_comp_configs`).

---

### 4. `apps/backend/app/modules/payroll/service.py` (orchestrator — preview, run, mark-paid, list, clawback recorder)

**Analog A (atomic UoW + audit BEFORE commit + Protocol-slot mediated cross-module write):** `apps/backend/app/modules/pt_packages/service.py:1038-1190` (`refund_pt_package` D-33-11 sequence — flush → audit → commit).
**Analog B (caller-owns-txn Protocol-slot consumer for `record_clawback_for_pt_package_refund`):** `apps/backend/app/modules/payments/service.py:168-245` (`issue_refund` — flush + audit emit, no commit).

**Imports pattern** (mirror `pt_packages/service.py:80-110` for slot consumption + `payments/service.py:32-43` for caller-owns-txn slot bodies):
```python
from __future__ import annotations
from datetime import date
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import audit
from app.core.dependencies import CurrentUser
from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.modules.payroll import repository
from app.modules.payroll.constants import (
    ERROR_COMP_CONFIG_MISSING,
    ERROR_PAYROLL_PERIOD_ALREADY_RUN,
    ERROR_ALREADY_PAID,
    SUBJECT_KIND_PT_PACKAGE,  # locally-pinned literal (D-58-19 / pt_packages constants precedent)
)
from app.modules.payroll.models import TrainerCompConfig, TrainerPayrollAccrual
```

**Typed exceptions** (mirror `payments/service.py:46-67`):
```python
class CompConfigMissingError(ValidationError):
    code = "comp_config_missing"
    status_code = 422

class PayrollPeriodAlreadyRunError(ConflictError):
    code = "payroll_period_already_run"
    status_code = 409

class AlreadyPaidError(ConflictError):
    code = "already_paid"
    status_code = 409
```

**Orchestrator-owns-commit `run_payroll_period` (PAY-03)** — mirror `pt_packages/service.py:1038-1170` D-33-11 sequence:
```python
async def run_payroll_period(
    session: AsyncSession,
    actor: CurrentUser,
    trainer_id: UUID,
    period_start: date,
    period_end: date,
) -> TrainerPayrollAccrual:
    """PAY-03 / D-58-13 — atomic UoW (orchestrator owns commit).

    Sequence (D-33-11 mirror):
      1. Resolve comp config (own-module SELECT) — 422 comp_config_missing if no row.
      2. Cross-module raw-SQL read of session count + revenue (D-58-19).
      3. Compute accrual_kopecks via integer math + math.ceil (D-58-04).
      4. INSERT ON CONFLICT DO NOTHING (D-58-06) → None means 409.
      5. session.flush() — surfaces deferred FK/CHECK violations.
      6. audit.emit("payroll_accrual_created", ...) BEFORE commit (D-58-17).
      7. session.commit() — SVC001 gate enforces.
      8. Return ORM row.
    """
    config = await repository.resolve_active_comp_config(session, trainer_id, period_end)
    if config is None or (config.commission_pct_bps is None
                          and config.session_fee_kopecks is None):
        raise CompConfigMissingError("comp_config_missing")

    rev = await repository.fetch_trainer_session_revenue(
        session, trainer_id, period_start, period_end)
    accrual_kopecks = _compute_accrual(rev, config)  # ceil integer math, D-58-04

    accrual_id = await repository.insert_accrual_idempotent(
        session, trainer_id=trainer_id, period_start=period_start,
        period_end=period_end, ..., accrual_kopecks=accrual_kopecks)
    if accrual_id is None:
        raise PayrollPeriodAlreadyRunError("payroll_period_already_run")

    await session.flush()

    await audit.emit(
        session,
        "payroll_accrual_created",  # LITERAL (INFRA-11 AST gate)
        actor_user_id=actor.id,
        resource_type="payroll_accrual",  # LITERAL
        resource_id=accrual_id,
        # ... payload kwargs per PayrollAccrualCreatedPayload schema ...
    )
    await session.commit()
    return await repository.get_accrual(session, accrual_id)
```

**Protocol-slot body — `record_clawback_for_pt_package_refund`** — mirrors `payments/service.py:168-245` `issue_refund` (caller-owns-txn, NO commit, audit emit before caller's commit):
```python
async def record_clawback_for_pt_package_refund(  # noqa: SVC001 caller-owns-txn — pt_packages refund orchestrator owns UoW
    session: AsyncSession,
    *,
    actor: CurrentUser,
    refund_payment_id: UUID,
    pt_package_id: UUID,
) -> UUID | None:
    """PayrollClawbackRecorder Protocol-slot body (D-58-20).

    Caller-owns-txn: pt_packages.service.refund_pt_package owns the UoW.
    Returns the new clawback accrual id, or None if no payroll impact.

    Sequence:
      1. Raw-SQL look up pt_package.trainer_id (assigned-at-sale per D-58-21).
      2. Raw-SQL lookup whether refund_payment.subject (pt_package) appears in
         any status='paid' accrual covering that package's bucket date.
         If none → return None (no payroll impact).
      3. Compute negative clawback_kopecks (proportional to refund).
      4. INSERT new accrual row with clawback_of_accrual_id + source_refund_payment_id set;
         status='pending'.
      5. session.flush() — surface deferred FK/CHECK.
      6. audit.emit("payroll_clawback_recorded", ...) BEFORE caller's commit.
      7. Return new accrual id.
    """
    # ... body per D-58-17 atomic chain ordering ...
```

**Mark-paid (PAY-04 D-58-08)** — `SELECT ... FOR UPDATE` mirroring single-transition pattern used in `pt_packages.status` (own-module ORM `select().with_for_update()`); 409 `already_paid` on second attempt.

**Constraints to preserve:**
- Audit emit BEFORE commit (`pt_packages/service.py:1154-1170` — `await audit.emit(...)` is line 1154; `await session.commit()` is line 1170).
- `# noqa: SVC001 caller-owns-txn` marker ONLY on `record_clawback_for_pt_package_refund` (the Protocol-slot consumer); all other service functions own commit.
- LITERAL audit event/resource_type strings (INFRA-11 AST gate — see `pt_packages/service.py:1156-1158` precedent).
- Locally-pinned `SUBJECT_KIND_PT_PACKAGE = "pt_package"` in `payroll/constants.py` (no import of `payments.constants` per D-58-19; mirror `pt_packages/constants.py:43-51`).

---

### 5. `apps/backend/app/modules/payroll/router.py` (7 endpoints under `/api/v1/payroll/`)

**Analog:** `apps/backend/app/modules/payments/router.py:1-108` (owner-only routes + ResponseEnvelope + `Depends(require_permission(...))`).

**Imports + RBAC guard pattern** (mirror `payments/router.py:18-35`):
```python
from typing import Annotated
from uuid import UUID
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import CurrentUser, require_permission
from app.core.pagination import PaginatedData
from app.core.permissions import Action, Resource
from app.core.schemas import ResponseEnvelope, envelope
from app.modules.payroll import service
from app.modules.payroll.schemas import (
    TrainerCompConfigRequest, TrainerCompConfigResponse,
    PayrollPreviewResponse, PayrollAccrualResponse, ...,
)

router = APIRouter()
```

**Endpoint pattern** (mirror `payments/router.py:38-58` for owner-only + ResponseEnvelope):
```python
@router.put(
    "/trainer-configs/{trainer_id}",
    response_model=ResponseEnvelope[TrainerCompConfigResponse],
    summary="Set/replace trainer comp config (INSERT-only versioned; owner-only PAY-01)",
)
async def set_trainer_comp_config(
    trainer_id: UUID,
    body: TrainerCompConfigRequest,
    actor: Annotated[
        CurrentUser, Depends(require_permission(Action.CREATE, Resource.COMPENSATION))
    ],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ResponseEnvelope[TrainerCompConfigResponse]:
    config = await service.set_comp_config(session, actor, trainer_id, body)
    return envelope(TrainerCompConfigResponse.model_validate(config, from_attributes=True))
```

**Endpoint inventory (D-58-10..14):**
| Method | Path | RBAC pair | Service fn |
|--------|------|-----------|------------|
| PUT | `/trainer-configs/{trainer_id}` | `(CREATE, COMPENSATION)` | `set_comp_config` |
| GET | `/trainer-configs/{trainer_id}` | `(VIEW, COMPENSATION)` (already in OWNER_ONLY) | `get_active_comp_config` |
| GET | `/preview` | `(VIEW, PAYROLL)` (already in OWNER_ONLY) | `preview_accrual` |
| POST | `/accruals` | `(CREATE, PAYROLL)` | `run_payroll_period` |
| POST | `/accruals/{id}/mark-paid` | `(EDIT, PAYROLL)` | `mark_accrual_paid` |
| GET | `/accruals` | `(LIST, PAYROLL)` | `list_accruals` |

**Constraints to preserve:**
- All endpoints owner-only via `Depends(require_permission(Action.X, Resource.Y))` (mirror `payments/router.py:46`).
- Response envelope `ResponseEnvelope[...]` + `envelope(...)` helper (mirror `payments/router.py:30, 57`).
- Pagination response uses `PaginatedData[PayrollAccrualResponse]` for list endpoint (mirror `payments/router.py:48-49, 56-57`).

---

### 6. `apps/backend/app/modules/payroll/schemas.py` (Pydantic request/response)

**Analog:** `apps/backend/app/modules/payments/schemas.py` (BackendSchemaBase with camelCase wire). Length ~78 lines.

**Pattern:**
```python
from datetime import date, datetime
from uuid import UUID
from pydantic import Field

from app.core.schemas import BackendSchemaBase  # auto camelCase via to_camel

class TrainerCompConfigRequest(BackendSchemaBase):
    commission_pct_bps: int | None = Field(default=None, ge=0, le=10000)
    session_fee_kopecks: int | None = Field(default=None, ge=0)
    effective_from: date

class TrainerCompConfigResponse(BackendSchemaBase):
    id: UUID
    trainer_id: UUID
    commission_pct_bps: int | None
    session_fee_kopecks: int | None
    effective_from: date
    created_at: datetime

class PayrollPreviewResponse(BackendSchemaBase):
    session_count: int
    fixed_kopecks: int
    commission_kopecks: int
    total_kopecks: int

class PayrollAccrualResponse(BackendSchemaBase):
    id: UUID
    trainer_id: UUID
    period_start: date
    period_end: date
    sessions_count: int
    revenue_kopecks: int
    commission_pct_bps_snapshot: int | None
    session_fee_kopecks_snapshot: int | None
    accrual_kopecks: int
    status: str
    accrued_at: datetime
    paid_at: datetime | None
    paid_by_user_id: UUID | None
    clawback_of_accrual_id: UUID | None
    source_refund_payment_id: UUID | None
```

---

### 7. `apps/backend/app/modules/payroll/constants.py` (subject-kind literals + error codes)

**Analog:** `apps/backend/app/modules/pt_packages/constants.py:1-57` (locally-pinned literal pattern with explanatory docstring about modules-independent contract).

**Pattern** (mirror `pt_packages/constants.py:18-29` rationale block):
```python
"""Payroll module constants (Phase 58 D-58-19 / D-58-21).

`PAYMENT_SUBJECT_KIND_PT_PACKAGE` is the subject-kind literal passed to
cross-module raw-SQL `text()` SELECTs. The importlinter modules-independent
contract forbids `app.modules.payroll -> app.modules.payments`, so we cannot
import `payments.constants.SUBJECT_KIND_PT_PACKAGE`. The literal must match
the migration 0012_payments CHECK constraint ck_payments_subject_kind value
'pt_package'; payments.constants.SUBJECT_KIND_PT_PACKAGE is the same string.
Cross-module pinning is enforced by the runtime CHECK and by both modules
anchoring on the migration value (mirrors pt_packages D-33 / memberships D-32-09).
"""

PAYMENT_SUBJECT_KIND_PT_PACKAGE = "pt_package"

# Error codes (snake_case per project convention — D-58-07)
ERROR_COMP_CONFIG_MISSING = "comp_config_missing"
ERROR_PAYROLL_PERIOD_ALREADY_RUN = "payroll_period_already_run"
ERROR_ALREADY_PAID = "already_paid"
```

---

### 8. EDIT `apps/backend/app/core/permissions.py` — add OWNER_ONLY pairs (D-58-15)

**Analog:** Phase 54 audit-log block at lines 125-129 (comment + 2 new tuples).

**Insertion point:** End of `OWNER_ONLY` frozenset (just before closing `}` on line 130). Append comment block + 4-6 tuples:
```python
        # v1.9 Phase 58 INFRA-15 / D-58-15 — Payroll + compensation write/run/refund
        # pairs. Reception has zero payroll visibility. Existing (VIEW, PAYROLL) and
        # (VIEW, COMPENSATION) at lines 66-67 remain unchanged.
        (Action.CREATE, Resource.COMPENSATION),
        (Action.CREATE, Resource.PAYROLL),
        (Action.EDIT, Resource.PAYROLL),
        (Action.REFUND, Resource.PAYROLL),
        (Action.LIST, Resource.PAYROLL),
        # Optional (planner refines per D-58-15): (Action.EDIT, Resource.COMPENSATION).
```

**Bump count comment** at line 60:
```python
# Verbatim mirror of apps/admin-web/src/shared/session/can.ts (40 entries after Phase 58 INFRA-15).
```
(From 35 → 40 if 5 new pairs ship; planner adjusts based on final pair count.)

**Invariants to preserve:**
- frozenset literal stays a `set` literal `{...}` (not `tuple`); ordering is irrelevant for `frozenset` equality but comments group by phase chronologically (mirror lines 81-117).
- No new `Resource` enum members needed — `Resource.PAYROLL` (line 40) and `Resource.COMPENSATION` (line 41) already exist.
- No new `Action` enum members needed — `CREATE`, `EDIT`, `REFUND`, `LIST` all exist (lines 21-31).

---

### 9. EDIT `apps/backend/app/core/audit.py` — add LOCKED_AUDIT_EVENTS tuples (D-58-16)

**Analog:** Phase 51 online_refund block at lines 386-394 (3-event group with section comment).

**Insertion point:** End of `LOCKED_AUDIT_EVENTS` frozenset (just before closing `}` on line 395). Append:
```python
        # v1.9 (Phase 58 lock — INFRA-15; emitted in Phase 58 service body)
        # Payroll lifecycle (PAY-01..06 / D-58-16):
        ("trainer_comp_config_set", "trainer_comp_config"),
        ("payroll_accrual_created", "payroll_accrual"),
        ("payroll_accrual_paid", "payroll_accrual"),
        ("payroll_clawback_recorded", "payroll_accrual"),
```

**Constraints to preserve:**
- Tuple shape `(event_name, resource_type)` (mirror every existing entry; lines 290-394).
- Section comment naming the phase + the requirement IDs (mirror line 309 "v1.4 (Phase 30 lock — emitted in Phases 31/32/33/34 per INFRA-17 / B-03 / D-30-02)").
- New entries also need corresponding Pydantic payload schemas in `app/core/audit_payloads.py` (see §10 below) + registry entries in `AUDIT_PAYLOAD_SCHEMAS` dict.

---

### 10. EDIT `apps/backend/app/core/audit_payloads.py` — add 4 new Pydantic payload schemas

**Analog:** `RefundIssuedPayload` (line 114) + `MembershipRefundedPayload` (line 135) + registry append at lines 1140-1147.

**Pattern (new payload class)** — mirror existing `PaymentRecordedPayload` (line 84) for kopecks + actor:
```python
class TrainerCompConfigSetPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    comp_config_id: UUID
    trainer_id: UUID
    commission_pct_bps: int | None = Field(default=None, ge=0, le=10000)
    session_fee_kopecks: int | None = Field(default=None, ge=0)
    effective_from: date

class PayrollAccrualCreatedPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    accrual_id: UUID
    trainer_id: UUID
    period_start: date
    period_end: date
    sessions_count: int
    revenue_kopecks: int
    accrual_kopecks: int
    comp_config_id_snapshot: UUID

class PayrollAccrualPaidPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    accrual_id: UUID
    trainer_id: UUID
    paid_by_user_id: UUID
    accrual_kopecks: int

class PayrollClawbackRecordedPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    clawback_accrual_id: UUID
    clawback_of_accrual_id: UUID
    trainer_id: UUID
    source_refund_payment_id: UUID
    pt_package_id: UUID
    accrual_kopecks: int  # signed negative
```

**Registry append** at end of `AUDIT_PAYLOAD_SCHEMAS` dict (mirror lines 1140-1147 online_refund entries):
```python
    # v1.9 (Phase 58 lock — INFRA-15; emitted in Phase 58 service body)
    ("trainer_comp_config_set", "trainer_comp_config"): TrainerCompConfigSetPayload,
    ("payroll_accrual_created", "payroll_accrual"): PayrollAccrualCreatedPayload,
    ("payroll_accrual_paid", "payroll_accrual"): PayrollAccrualPaidPayload,
    ("payroll_clawback_recorded", "payroll_accrual"): PayrollClawbackRecordedPayload,
```

**Constraints to preserve:**
- Plain `pydantic.BaseModel` + `model_config = ConfigDict(extra="forbid")` — NOT `BackendSchemaBase` (mirror module docstring rationale at lines 16-22).
- `app.core.audit_payloads` MUST NOT import from `app.modules.*` (mirror line 30-31 architectural boundary).

---

### 11. EDIT `apps/backend/app/core/dependencies.py` — add `PayrollClawbackRecorder` Protocol slot

**Analog:** `PaymentRefunder` Protocol at lines 373-396 + register/getter at lines 409-436.

**Insertion point:** After the `get_payment_refunder()` definition (line 436), before the next phase's section header at line 439. Pattern:
```python
# Phase 58 D-58-20 — PayrollClawbackRecorder Protocol slot.
#
# 17th composition-root carve-out (after register_payment_refunder Phase 32, ...,
# register_pt_package_activator Phase 47). The PT-package refund orchestrator
# (pt_packages.service.refund_pt_package, Phase 33 D-33-11 / Plan 58-XX) consumes
# PayrollClawbackRecorder. The slot inserts an append-only negative clawback row
# in the SAME UoW as the refund payment row — caller-owns-txn discipline (D-32-10
# mirror). NO commit/flush inside the slot body; the refund orchestrator's
# session.commit() (step 8 of D-33-11) atomically commits payment row + payment
# audit + pt_package audit + clawback row + clawback audit.
#
# Defensive accessor (raises if not registered) — mirrors get_payment_refunder
# at line 427; a missing slot is misconfiguration, not a silent skip.
# ─────────────────────────────────────────────────────────────────────────────


class PayrollClawbackRecorder(Protocol):
    """Structural type for the payroll clawback recorder (Phase 58 D-58-20).

    Takes ``(refund_payment_id, pt_package_id)`` so cross-module callers
    (pt_packages.service.refund_pt_package) never need to import
    ``app.modules.payroll.*`` — preserves the modules-independent importlinter
    contract. The recorder internally inspects whether any status='paid' accrual
    references the refunded payment's bucket date for the package's trainer.

    Return type ``UUID | None`` — UUID of the new clawback accrual row, or None
    if no payroll impact (no paid accrual covers the refund).
    """

    async def __call__(
        self,
        session: AsyncSession,
        *,
        actor: CurrentUser,
        refund_payment_id: UUID,
        pt_package_id: UUID,
    ) -> UUID | None: ...


_payroll_clawback_recorder: PayrollClawbackRecorder | None = None


def register_payroll_clawback_recorder(recorder: PayrollClawbackRecorder) -> None:
    """Composition-root setter — called by app.main.create_app() (NOT bot)."""
    global _payroll_clawback_recorder
    _payroll_clawback_recorder = recorder


def get_payroll_clawback_recorder() -> PayrollClawbackRecorder:
    """Defensive accessor (D-58-20) — raises if slot not registered.

    Mirrors ``get_payment_refunder`` defensive raise at line 427. The refund flow
    cannot silently skip clawback — that would silently overpay trainers.
    """
    if _payroll_clawback_recorder is None:
        raise RuntimeError("payroll_clawback_recorder not registered")
    return _payroll_clawback_recorder
```

**Constraints to preserve:**
- `Protocol` import already present (line 20). No new imports needed beyond the existing `Protocol`, `UUID`, `AsyncSession`, `CurrentUser`.
- Defensive raise variant (NOT silent-None) — mirror `get_payment_refunder` rationale at lines 430-433 (the refund flow cannot proceed without a registered slot; silent absence would corrupt the payroll ledger).

---

### 12. EDIT `apps/backend/app/main.py` — wire the new slot at startup

**Analog:** Lines 241-246 `register_payment_recorder` / `register_payment_refunder` wiring.

**Imports** (extend the `from app.core.dependencies import (...)` block at lines 56-71):
```python
    register_payroll_clawback_recorder,  # Phase 58 D-58-20
```

**Wiring call** (add after line 246 `register_payment_refunder(payments_service.issue_refund)`):
```python
    # Phase 58 D-58-20: 17th composition-root carve-out — the PT-package refund
    # orchestrator (pt_packages.service.refund_pt_package, D-33-11 step 6.5)
    # consumes the PayrollClawbackRecorder slot in the same UoW. Exclusively
    # wired here (NOT in telegram_bot.py — bot is not a refund participant).
    # Defensive raise on missing slot (D-58-20) — silent absence would corrupt
    # the payroll ledger.
    from app.modules.payroll import (
        service as payroll_service,
    )

    register_payroll_clawback_recorder(
        payroll_service.record_clawback_for_pt_package_refund
    )
```

**Constraints to preserve:**
- Local `from app.modules.payroll import service as payroll_service` inside `create_app()` body (mirror line 241-243 `from app.modules.payments import service as payments_service` — `app.main` is the only file exempt from `core-not-depend-on-modules` since the contract's `source_modules = app.core`, not `app`).
- Wired ONLY in `create_app()`, NOT in `app/workers/telegram_bot.py` (the bot is not a refund participant — mirror line 237-238 rationale block).

---

### 13. EDIT `apps/backend/app/modules/pt_packages/service.py:1038` — insert clawback hook

**Analog:** Existing D-33-11 sequence already documents 8 numbered steps (lines 1046-1075). The clawback hook lands as step 6.5.

**Insertion point:** Between line 1164 (closing parenthesis of `pt_package_refunded` audit emit) and line 1167 (`await session.refresh(pt_package, ...)`). NEW imports at top of file:
```python
    get_payroll_clawback_recorder,  # Phase 58 D-58-20
```

**Hook call body** (insert after line 1164):
```python
    # 6.5. Phase 58 PAY-06 / D-58-20 — payroll clawback hook. Same UoW as
    # the refund row + pt_package audit. The slot internally checks whether
    # the refunded payment's revenue appears in any status='paid' accrual; if
    # so, INSERTs a negative clawback row + emits payroll_clawback_recorded
    # audit BEFORE this orchestrator's session.commit() (step 8) so the entire
    # chain (refund row + 3 audits + clawback row) is atomic.
    #
    # Audit chain order for refund-with-clawback:
    #   payment_recorded (original sale) → refund_issued (payment-side, inside
    #   issue_refund) → pt_package_refunded (subject-side, step 6 above) →
    #   payroll_clawback_recorded (payroll-side, inside the slot call).
    #
    # Slot returns None if no payroll impact (no paid accrual covers the
    # refund's bucket) — that branch is silent (not an error). Returns a UUID
    # when a clawback row is INSERTed.
    #
    # Modules-independent contract: this orchestrator does NOT import
    # app.modules.payroll.*; the cross-module call goes through the Protocol
    # slot in app.core.dependencies (D-58-20, mirror Phase 32 D-32-14).
    await get_payroll_clawback_recorder()(
        session,
        actor=actor,
        refund_payment_id=refund_payment.id,
        pt_package_id=pt_package.id,
    )
```

**Invariants to preserve:**
- Hook fires BEFORE `session.refresh()` at line 1167 (which is a SA detail; clawback emits its own audit which must land before commit).
- Hook fires BEFORE `await session.commit()` at line 1170 — the D-58-17 atomic chain requires it.
- Step 8 `await session.commit()` at line 1170 still owns the entire UoW (refund row + 3 audits + clawback row + clawback audit = 1 commit).
- No new ignore_imports edges added — the slot mediates the cross-module call.
- D-33-11 docstring at lines 1046-1075 must be updated to mention "6.5. Phase 58 PAY-06 / D-58-20 — payroll clawback hook (same UoW)" in the numbered sequence comment block.

---

### 14. EDIT `apps/backend/.importlinter` — register `app.modules.payroll` in modules-independent

**Analog:** Phase 54 D-54-09 `reports` preemptive registration (current `.importlinter` lines 26-31 the `# Phase 54 INFRA-41 / D-54-09` comment block).

**Insertion point:** In `[importlinter:contract:modules-independent]` `modules =` list (currently 17 modules, alphabetical-ish but actually phase-chronological). Add after `app.modules.reports` (alphabetical) or at end of list:
```
    app.modules.payroll
    # Phase 58 INFRA-15 / D-58-18 — payroll module registered preemptively
    # (INFRA-15 discipline, mirrors Phases 54 D-54-09 / 47 INFRA-40 / 51).
    # Cross-module reads (pt_sessions / pt_packages / payments) go via raw
    # SQL text() SELECTs in payroll/repository.py (D-58-19 / D-54-08 lineage),
    # so ZERO new ignore_imports edges are needed.
    # Cross-module write (clawback into payroll from pt_packages.service)
    # goes via the PayrollClawbackRecorder Protocol slot in app.core.dependencies
    # (D-58-20), so the pt_packages → payroll import remains forbidden as
    # intended (mirror Phase 32 D-32-14 PaymentRefunder pattern).
```

**Invariants to preserve:**
- ZERO new `ignore_imports` edges (D-58-18 / SC#3) — `.importlinter` `ignore_imports` section gets ZERO additions.
- `unmatched_ignore_imports_alerting = warn` (line ~110) stays unchanged.
- Module registered BEFORE any payroll code lands (INFRA-15 preemption — register in the same plan that ships `__init__.py`).

---

### 15. EDIT `apps/backend/app/api/v1/router.py` — mount `payroll_router`

**Analog:** Line 22 `from app.modules.payments.router import router as payments_router` + line 52 `v1.include_router(payments_router, prefix="/payments", tags=["payments"])`.

**Imports (alphabetical after `online_refunds`/`payments`):**
```python
from app.modules.payroll.router import router as payroll_router
```

**Mount (alphabetical position — after `payments_router` line 52):**
```python
v1.include_router(payroll_router, prefix="/payroll", tags=["payroll"])
```

---

### 16. Frontend EDIT `apps/admin-web/src/shared/session/can.ts` — mirror new OWNER_ONLY pairs

**Analog:** Phase 54 INFRA-42 audit-log block at lines 63-66 (4-entry section with phase comment).

**Insertion point:** End of `OWNER_ONLY` array (just before closing `]` on line 67). Append (byte-for-byte mirror of new permissions.py tuples — D-58-15):
```typescript
  // v1.9 (Phase 58 INFRA-15 / D-58-15 — Payroll + compensation write/run/refund pairs;
  // reception has zero payroll visibility per D-58-15). Existing { action: 'view', resource: 'payroll' }
  // and { action: 'view', resource: 'compensation' } at lines 15-16 remain unchanged.
  { action: 'create', resource: 'compensation' },
  { action: 'create', resource: 'payroll' },
  { action: 'edit', resource: 'payroll' },
  { action: 'refund', resource: 'payroll' },
  { action: 'list', resource: 'payroll' },
```

**Invariants to preserve:**
- Byte-semantic mirror of `permissions.py` new tuples — TEST-06 RBAC parity test asserts equality of `(Action, Resource)` pair sets between backend frozenset and TS array.
- No new `Resource` or `Action` types added — `payroll`, `compensation` already exist in `registry.ts:8-9`; `create`/`edit`/`refund`/`list` actions all exist in `registry.ts:27-36`.
- Format: object literal `{ action: 'X', resource: 'Y' }` matching existing entries (no semicolons in this file per project Prettier config).

---

### 17. Frontend EDIT `apps/admin-web/src/shared/session/registry.ts` — NO CHANGE

**Analog:** Lines 8-9 — `payroll` and `compensation` already in the Resource union (legacy from Phase 1/2).

**Action:** Confirm parity only; NO file edit required in Phase 58. The three-way parity test (TEST-06) will auto-detect that the new OWNER_ONLY pairs in `can.ts` reference resources that already exist in the union.

---

### 18. Tests (group section — all 7 integration test files share fixtures + analog)

**Analog A (fixture re-export pattern):** `apps/backend/tests/integration/reports/conftest.py:1-30`
**Analog B (test file structure, owner+reception clients, ResponseEnvelope assertions):** `apps/backend/tests/integration/reports/test_reports_revenue.py:1-90`

**`tests/integration/payroll/conftest.py` pattern** (mirror reports/conftest.py lines 17-30):
```python
"""Shared fixtures for payroll integration tests (Phase 58 PAY-01..06)."""
from __future__ import annotations
from collections.abc import Awaitable, Callable
from datetime import date, datetime, UTC
from uuid import UUID
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.payroll.models import TrainerCompConfig, TrainerPayrollAccrual

# Re-export memberships package fixtures (owner / reception clients, factories)
from tests.integration.memberships.conftest import (  # noqa: F401
    _client_app_overrides,
    authed_client_owner,
    authed_client_reception,
    db_session_real_commit,
    make_client,
    make_plan,  # for PT-package factory chain
    make_user,
    redis_clean,
    seeded_owner,
    seeded_reception,
)
# Trainers factory (Phase 31)
from tests.integration.trainers.conftest import (  # noqa: F401
    make_trainer,
)

@pytest_asyncio.fixture
async def make_comp_config(
    db_session: AsyncSession,
) -> Callable[..., Awaitable[TrainerCompConfig]]:
    """Insert a TrainerCompConfig row with explicit effective_from."""
    async def _make(*, trainer_id: UUID, commission_pct_bps: int | None = None,
                    session_fee_kopecks: int | None = None,
                    effective_from: date = date(2026, 1, 1)) -> TrainerCompConfig:
        config = TrainerCompConfig(
            trainer_id=trainer_id, commission_pct_bps=commission_pct_bps,
            session_fee_kopecks=session_fee_kopecks, effective_from=effective_from,
        )
        db_session.add(config)
        await db_session.commit()
        await db_session.refresh(config)
        return config
    return _make
```

**`test_payroll_*.py` pattern** (mirror `test_reports_revenue.py` test functions):
- Owner GET/POST → 200/201 + ResponseEnvelope shape assertion.
- Reception → 403 + `body["code"] == "forbidden"` (mirror `test_reports_revenue.py:42-52`).
- Idempotency: second POST `/payroll/accruals` with same `(trainer_id, period_start, period_end)` → 409 `payroll_period_already_run` (PAY-03).
- 422 `comp_config_missing` when no comp config (PAY-03 D-58-07).
- 409 `already_paid` on second `/mark-paid` (PAY-04 D-58-08).
- Clawback test (PAY-06): create accrual → mark paid → refund PT-package → assert new row exists with `clawback_of_accrual_id IS NOT NULL` AND `accrual_kopecks < 0` AND `source_refund_payment_id` matches the refund payment's id (D-58-20).
- Same-UoW invariant test: simulate IntegrityError after pt_package_refunded audit → assert NEITHER the refund payment row NOR the clawback row exists post-rollback (mirror Phase 32 atomic chain test).
- RBAC denial test (`test_payroll_rbac.py`): all 6 mutation endpoints + the LIST endpoint return 403 for `authed_client_reception` (mirror `test_reports_revenue.py:42-52` for each route).

**Constraints to preserve:**
- Use `authed_client_owner` / `authed_client_reception` (re-exported from `memberships/conftest.py`) — mirror `reports/conftest.py:20-21`.
- All tests `async def test_...` with `httpx.AsyncClient` injection — mirror `test_reports_revenue.py:31`.
- DB seeding via `make_client` / `make_trainer` / `make_comp_config` factories (avoid raw ORM INSERT in test bodies).
- SAVEPOINT rollback per test (no explicit cleanup needed — `db_session` fixture handles it).

---

## Shared Patterns

### Authentication / RBAC (every router endpoint)

**Source:** `apps/backend/app/core/dependencies.py:require_permission(Action, Resource)`
**Apply to:** All 7 endpoints in `payroll/router.py`.

```python
actor: Annotated[
    CurrentUser, Depends(require_permission(Action.X, Resource.PAYROLL))
],
```

Reception receives 403 `forbidden` because `(Action.X, Resource.PAYROLL) ∈ OWNER_ONLY` after the Phase 58 RBAC edits (D-58-15). Three-way parity test (`tests/integration/test_rbac_parity.py`) auto-bumps.

---

### Error Handling (typed `AppError` subclasses, 4xx mapping)

**Source:** `apps/backend/app/modules/payments/service.py:46-67` (`OriginalPaymentNotFoundError`, `AlreadyRefundedError`).
**Apply to:** `payroll/service.py` (`CompConfigMissingError`, `PayrollPeriodAlreadyRunError`, `AlreadyPaidError`).

```python
class CompConfigMissingError(ValidationError):
    code = "comp_config_missing"  # snake_case (D-58-07 project convention)
    status_code = 422
```

Centralized handler (`app/core/exceptions.py:register_exception_handlers`) maps to JSON response `{"code": "X", "message": "..."}` — no manual try/catch in routes.

---

### Atomic Audit Chain (UoW owns commit; emit BEFORE commit)

**Source:** `apps/backend/app/modules/pt_packages/service.py:1038-1170` (D-33-11 sequence — flush → audit emit → commit).
**Apply to:** `payroll/service.run_payroll_period` (PAY-03), `payroll/service.mark_accrual_paid` (PAY-04), `payroll/service.record_clawback_for_pt_package_refund` (PAY-06 — caller-owns-txn variant for Protocol-slot body, mirror `payments/service.issue_refund` instead).

Sequence:
1. Service body INSERTs ORM row (or repository helper does).
2. `await session.flush()` — surfaces deferred FK/CHECK violations as `IntegrityError`.
3. `await audit.emit("locked_event_name", resource_type="locked_resource", actor_user_id=actor.id, resource_id=row.id, **payload)` — LITERAL strings (INFRA-11 AST gate).
4. `await session.commit()` — orchestrator-owns-commit (SVC001 gate). Protocol-slot bodies (`record_clawback_for_pt_package_refund`) are marked `# noqa: SVC001 caller-owns-txn` and skip this step (caller commits).

---

### Cross-Module Reads (raw-SQL `text()` only)

**Source:** `apps/backend/app/modules/reports/repository.py:56-93` (`fetch_revenue_buckets`).
**Apply to:** `payroll/repository.py` reads against `pt_sessions`, `pt_packages`, `payments` (D-58-19).

Rules:
- Use `text("SELECT ... WHERE col = :param")` + dict bind params. Cast UUIDs to `str` (D-49-03 / D-54-08 lineage).
- Each query carries a `# Verified columns: ...` comment naming the foreign table's source file:line (mirror `reports/repository.py:62-67`).
- Each payroll query carries a `-- attribution: assigned-at-sale` or `-- attribution: conducting` inline comment per D-58-21.
- ZERO `from app.modules.pt_sessions import ...` / `from app.modules.payments import ...` / `from app.modules.pt_packages import ...` — those imports violate `modules-independent` contract.
- Inclusive `[start, end]` MSK boundaries: `(performed_at AT TIME ZONE 'Europe/Moscow')::date BETWEEN :start AND :end` (D-58-05).

---

### Protocol-Slot Cross-Module Write (caller-owns-txn, defensive accessor)

**Source:** `apps/backend/app/core/dependencies.py:373-436` (`PaymentRefunder` Protocol + register/getter).
**Apply to:** New `PayrollClawbackRecorder` Protocol slot (D-58-20).

Three-piece pattern (mirror `PaymentRefunder`):
1. **Protocol class** in `app/core/dependencies.py` — structural type, `Any` return if return type would force module import (here `UUID | None` works because `UUID` is stdlib).
2. **`register_*` setter** at module level + `_*` global — called once from `app.main.create_app()`.
3. **`get_*` defensive accessor** — raises `RuntimeError("X not registered")` if slot is unwired (mirror `get_payment_refunder` at line 427).

Caller (`pt_packages.service.refund_pt_package`):
- `await get_payroll_clawback_recorder()(session, actor=actor, refund_payment_id=..., pt_package_id=...)`
- NO commit/flush inside slot body — orchestrator owns UoW.
- Slot return value (UUID or None) optionally inspected by caller for logging; not used to gate commit.

---

### Snapshot Discipline (rate / config / counts frozen at INSERT)

**Source:** `apps/backend/app/modules/memberships/models.py:128-131` (`plan_name_snapshot`, `duration_days_snapshot`, `price_kopecks_snapshot`, `freeze_days_limit_snapshot` — Phase 17 v1.2 lock).
**Apply to:** `TrainerPayrollAccrual.commission_pct_bps_snapshot`, `session_fee_kopecks_snapshot`, `comp_config_id_snapshot`, `sessions_count`, `revenue_kopecks` (D-58-03).

Rule: snapshot columns are `NOT NULL` (except where economics fields legitimately NULL per D-58-09) and are written exactly once at INSERT. No UPDATE path. The append-only AST gate (`tests/unit/test_payroll_appendonly.py` — planner to add, mirror `test_payments_appendonly.py`) enforces this at CI.

---

### DB-Wins-the-Race Idempotency (INSERT ON CONFLICT DO NOTHING RETURNING)

**Source:** `apps/backend/app/modules/payments/models.py:112-117` partial UNIQUE + `issue_refund` IntegrityError discriminator pattern at `payments/service.py:215-221`.
**Apply to:** `payroll/repository.py:insert_accrual_idempotent` (D-58-06 — POST `/payroll/accruals` 409 surface).

Rule: NEVER pre-flight `SELECT ... WHERE` then `INSERT`. Always:
```python
result = await session.execute(text(
    "INSERT INTO trainer_payroll_accruals (...) VALUES (...) "
    "ON CONFLICT (trainer_id, period_start, period_end) "
    "WHERE clawback_of_accrual_id IS NULL DO NOTHING "
    "RETURNING id"
))
row = result.mappings().first()
if row is None:
    raise PayrollPeriodAlreadyRunError("payroll_period_already_run")
```

Partial UNIQUE in the schema (`uq_trainer_payroll_accruals_period_alive` `WHERE clawback_of_accrual_id IS NULL`) ensures clawback rows can multiplicatively offset one accrual.

---

### Locally-Pinned Subject-Kind Literals (no cross-module constants import)

**Source:** `apps/backend/app/modules/pt_packages/constants.py:43-51` (`PAYMENT_SUBJECT_KIND_PT_PACKAGE = "pt_package"` with explicit rationale block).
**Apply to:** `payroll/constants.py` (per D-58-19, planner discretion in CONTEXT.md `<decisions>` "Claude's Discretion").

The literal must match the migration 0012_payments CHECK value verbatim. Two-module pinning + DB CHECK is the cross-module pinning guarantee.

---

## No Analog Found

All 28 new/edited files have at least one strong analog. Coverage 100%.

| File | Reason |
|------|--------|
| (none) | All payroll work mirrors v1.4 ledger / v1.7 Protocol-slot / v1.8 raw-SQL-cross-module-read disciplines verbatim. |

---

## Metadata

**Analog search scope:**
- `apps/backend/app/core/{permissions,audit,audit_payloads,dependencies}.py`
- `apps/backend/app/main.py`
- `apps/backend/app/modules/{payments,memberships,pt_packages,reports}/{models,schemas,repository,service,router,constants}.py`
- `apps/backend/app/api/v1/router.py`
- `apps/backend/alembic/versions/{0034,0040}_*.py`
- `apps/backend/.importlinter`
- `apps/backend/tests/conftest.py`, `tests/integration/reports/{conftest,test_reports_revenue}.py`
- `apps/admin-web/src/shared/session/{can,registry}.ts`

**Files scanned:** ~22 source files + 1 importlinter + 2 frontend RBAC mirrors.
**Pattern extraction date:** 2026-05-25.

---

*Phase: 58-payroll-foundations-ledger*
*Patterns mapped: 2026-05-25*
