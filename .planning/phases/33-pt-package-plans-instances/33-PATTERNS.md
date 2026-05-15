# Phase 33: PT-Package Plans + Instances — Pattern Map

**Mapped:** 2026-05-15
**Files analyzed:** 18 (new/modified)
**Analogs found:** 18 / 18 (every file has at least a role-match)

This phase materialises `app/modules/pt_packages/` (placeholder shell exists from Phase 30) into a full module mirroring the **memberships** module shape (plans + instances) and the **payments** module patterns (Protocol-slot consumption, append-only ledger reuse, idempotency).

## File Classification

### New files

| New File | Role | Data Flow | Closest Analog | Match Quality |
|----------|------|-----------|----------------|---------------|
| `apps/backend/alembic/versions/0013_pt_package_plans.py` | migration | DDL | `alembic/versions/0004_membership_plans.py` | exact |
| `apps/backend/alembic/versions/0014_pt_packages.py` | migration | DDL | `alembic/versions/0005_memberships.py` | exact |
| `apps/backend/app/modules/pt_packages/constants.py` | constants | static-data | `app/modules/memberships/constants.py` | exact |
| `apps/backend/app/modules/pt_packages/models.py` | model (ORM) | persistence | `app/modules/memberships/models.py` (MembershipPlan + Membership) | exact |
| `apps/backend/app/modules/pt_packages/repository.py` | repository | CRUD | `app/modules/memberships/repository.py` | exact |
| `apps/backend/app/modules/pt_packages/schemas.py` | schema (DTO) | request-response | `app/modules/memberships/schemas.py` | exact |
| `apps/backend/app/modules/pt_packages/service.py` *(populate stub)* | service | request-response + orchestration | `app/modules/memberships/service.py` (create/cancel/refund/expire-due) | exact |
| `apps/backend/app/modules/pt_packages/router.py` | router | request-response | `app/modules/memberships/router.py` (plans_router + memberships_router) | exact |
| `apps/backend/app/modules/pt_packages/permissions.py` *(optional)* | permissions | RBAC | `app/modules/payments/permissions.py` (or inline-in-router per memberships) | role-match |
| `apps/backend/app/workers/scheduled/expire_pt_packages.py` | worker (cron) | batch | `app/workers/scheduled/expire_memberships.py` | exact |
| `apps/backend/tests/unit/pt_packages/test_state_machine.py` | test | unit | `tests/unit/memberships/test_state_machine.py` *(referenced by precedent)* | exact |
| `apps/backend/tests/integration/test_pt_package_plans_crud.py` | test | integration | `tests/integration/test_membership_plans_*.py` | role-match |
| `apps/backend/tests/integration/test_pt_packages_sale.py` | test | integration | `tests/integration/test_memberships_sale.py` *(Plan 32-02)* | role-match |
| `apps/backend/tests/integration/test_pt_packages_cancel.py` | test | integration | `tests/integration/test_memberships_cancel.py` | role-match |
| `apps/backend/tests/integration/test_pt_packages_refund.py` | test | integration | `tests/integration/test_membership_refund_*.py` *(Plan 32-03)* | exact |
| `apps/backend/tests/integration/test_expire_pt_packages_cron.py` | test | integration | `tests/integration/test_expire_memberships_cron.py` *(Plan 18-01)* | role-match |

### Modified files

| Modified File | Role | Data Flow | Closest Analog (existing block to mirror) | Match Quality |
|---------------|------|-----------|-------------------------------------------|---------------|
| `apps/backend/app/core/dependencies.py` | slot/Protocol | resolver | Existing `ActiveMembership` block (lines 65-119) | exact |
| `apps/backend/app/main.py` | composition root | wiring | Existing `register_active_membership_resolver(...)` block (lines 117-124) | exact |
| `apps/backend/app/workers/__init__.py` | worker config | cron-registration | Existing `cron(expire_memberships, ...)` entry (lines 88-95) | exact |
| `apps/backend/app/api/v1/router.py` | aggregator | router-mounting | Existing `plans_router` + `memberships_router` `include_router` (lines 25-26) | exact |
| `apps/backend/app/modules/payments/service.py` | service | orchestration | Existing `issue_refund` branch on `SUBJECT_KIND_MEMBERSHIP` (lines 164-170) | exact |
| `apps/backend/app/modules/pt_packages/__init__.py` | module index | exports | Existing memberships `__init__.py` (or empty) | role-match |
| `apps/backend/tests/unit/test_worker_cron_resolution.py` | test (invariant) | assertion | Existing assertion shape | exact |

---

## Pattern Assignments

### `alembic/versions/0013_pt_package_plans.py` (migration, DDL)

**Analog:** `apps/backend/alembic/versions/0004_membership_plans.py`

**Header pattern** (lines 1-26):
```python
"""pt_package_plans

Revision ID: 0013_pt_package_plans
Revises: 0012_payments
Create Date: 2026-05-15 ...

Phase 33 PT-01 — owner-only PT-package catalog SKU table.

Notes:
- Partial-unique on lower(name) WHERE deleted_at IS NULL is an EXPRESSION index;
  SQLAlchemy autogenerate cannot represent it. Installed via raw op.execute(...).
- Constraint name "uq_pt_package_plans_name_alive" is referenced as a literal
  string by app/modules/pt_packages/service.py:_is_plan_name_conflict (mirror D-02).
"""
from collections.abc import Sequence
import sqlalchemy as sa
from alembic import op

revision: str = "0013_pt_package_plans"
down_revision: str | None = "0012_payments"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None
```

**create_table + expression unique** (lines 29-65):
```python
def upgrade() -> None:
    op.create_table(
        "pt_package_plans",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("session_count", sa.Integer(), nullable=False),
        sa.Column("price_kopecks", sa.BigInteger(), nullable=False),
        sa.Column("validity_days", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("session_count > 0", name=op.f("ck_pt_package_plans_session_count_positive")),
        sa.CheckConstraint("price_kopecks > 0", name=op.f("ck_pt_package_plans_price_kopecks_positive")),
        sa.CheckConstraint("validity_days IS NULL OR validity_days > 0",
                           name=op.f("ck_pt_package_plans_validity_days_positive")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_pt_package_plans")),
    )
    op.execute(
        "CREATE UNIQUE INDEX uq_pt_package_plans_name_alive "
        "ON pt_package_plans (lower(name)) WHERE deleted_at IS NULL"
    )

def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_pt_package_plans_name_alive")
    op.drop_table("pt_package_plans")
```

---

### `alembic/versions/0014_pt_packages.py` (migration, DDL)

**Analog:** `apps/backend/alembic/versions/0005_memberships.py` (table shape + DESC composite index pattern); `0012_payments.py` (partial UNIQUE).

**Header pattern** (analog lines 1-32):
```python
revision: str = "0014_pt_packages"
down_revision: str | None = "0013_pt_package_plans"
```

**FK ON DELETE RESTRICT + status CHECK pattern** (analog 0005 lines 86-100):
```python
sa.ForeignKeyConstraint(
    ["client_id"], ["clients.id"],
    name=op.f("fk_pt_packages_client_id_clients"),
    ondelete="RESTRICT",
),
sa.ForeignKeyConstraint(
    ["plan_id"], ["pt_package_plans.id"],
    name=op.f("fk_pt_packages_plan_id_pt_package_plans"),
    ondelete="RESTRICT",
),
sa.CheckConstraint(
    "status IN ('active', 'exhausted', 'expired', 'cancelled')",
    name=op.f("ck_pt_packages_status"),
),
sa.CheckConstraint(
    "sessions_remaining >= 0 AND sessions_remaining <= session_count_snapshot",
    name=op.f("ck_pt_packages_sessions_remaining_bounded"),
),
```

**Partial UNIQUE on (client_id) WHERE status='active'** — mirror `uq_payments_refund_of_alive` (0012 lines 113-119):
```python
op.create_index(
    "uq_pt_packages_active_per_client",
    "pt_packages",
    ["client_id"],
    unique=True,
    postgresql_where=sa.text("status = 'active'"),
)
```

**Indexes** (mirror 0005 composite + 0012 simple indexes):
```python
op.create_index("ix_pt_packages_client_id", "pt_packages", ["client_id"])
op.create_index("ix_pt_packages_status", "pt_packages", ["status"])
op.create_index("ix_pt_packages_plan_id", "pt_packages", ["plan_id"])
```

**start_date Europe/Moscow default** — note: `start_date` default is computed in application (not DB) per D-33-03 stored-not-virtual choice; mirror `memberships.start_date` (no server_default `now()` — application computes). Same applies to `end_date` (NULL allowed when `validity_days_snapshot IS NULL`).

---

### `app/modules/pt_packages/constants.py` (constants, static-data)

**Analog:** `app/modules/memberships/constants.py` (lines 19-29 + 49-64)

**FSM Mapping + sentinel + subject-kind constants** (analog lines 19-64):
```python
from collections.abc import Mapping
from types import MappingProxyType

PT_PACKAGE_STATUS_TRANSITIONS: Mapping[str, frozenset[str]] = MappingProxyType(
    {
        "active": frozenset({"exhausted", "expired", "cancelled"}),
        "exhausted": frozenset({"cancelled"}),  # refund of exhausted
        "expired": frozenset({"cancelled"}),    # refund of expired
        "cancelled": frozenset(),               # terminal
    }
)

# Mirror memberships.constants.CANCELLATION_REASON_REFUNDED (line 53; D-32-08).
CANCELLATION_REASON_REFUNDED = "refunded"

# Mirror memberships.constants.PAYMENT_SUBJECT_KIND_MEMBERSHIP (lines 56-64; D-32-09).
# Importlinter forbids importing payments.constants — pin literal to migration CHECK value.
PAYMENT_SUBJECT_KIND_PT_PACKAGE = "pt_package"

__all__ = [
    "CANCELLATION_REASON_REFUNDED",
    "PAYMENT_SUBJECT_KIND_PT_PACKAGE",
    "PT_PACKAGE_STATUS_TRANSITIONS",
]
```

---

### `app/modules/pt_packages/models.py` (model, persistence)

**Analog:** `app/modules/memberships/models.py` (MembershipPlan lines 54-86; Membership lines 89-190)

**Imports + Base composition** (analog lines 30-51):
```python
from __future__ import annotations
from datetime import date, datetime
from uuid import UUID as UUIDType  # noqa: N811

from sqlalchemy import (
    BigInteger, CheckConstraint, Date, DateTime, ForeignKey,
    Index, Integer, String, Text, text,
)
from sqlalchemy.dialects.postgresql import UUID as PgUUID  # noqa: N811
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, SoftDeleteMixin, TimestampMixin, UUIDPkMixin


class PtPackagePlan(Base, UUIDPkMixin, TimestampMixin, SoftDeleteMixin):
    """PT-package plan / SKU (PT-01)."""

    __tablename__ = "pt_package_plans"

    name: Mapped[str] = mapped_column(String(120), nullable=False)
    session_count: Mapped[int] = mapped_column(Integer, nullable=False)
    price_kopecks: Mapped[int] = mapped_column(BigInteger, nullable=False)
    validity_days: Mapped[int | None] = mapped_column(Integer, nullable=True)

    __table_args__ = (
        CheckConstraint("session_count > 0", name="session_count_positive"),
        CheckConstraint("price_kopecks > 0", name="price_kopecks_positive"),
        CheckConstraint(
            "validity_days IS NULL OR validity_days > 0",
            name="validity_days_positive",
        ),
        Index(
            "uq_pt_package_plans_name_alive",
            text("lower(name)"),
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
    )
```

**PtPackage instance (mirror Membership)** — NO `SoftDeleteMixin` (status-based lifecycle, matches Phase 17 D-12 precedent on `Membership` model docstring lines 95-104):
```python
class PtPackage(Base, UUIDPkMixin, TimestampMixin):
    """PT-package instance (PT-04). Lifecycle is purely status-based; NO SoftDeleteMixin."""

    __tablename__ = "pt_packages"

    client_id: Mapped[UUIDType] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("clients.id", ondelete="RESTRICT",
                   name="fk_pt_packages_client_id_clients"),
        nullable=False,
    )
    plan_id: Mapped[UUIDType] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("pt_package_plans.id", ondelete="RESTRICT",
                   name="fk_pt_packages_plan_id_pt_package_plans"),
        nullable=False,
    )
    plan_name_snapshot: Mapped[str] = mapped_column(String(120), nullable=False)
    session_count_snapshot: Mapped[int] = mapped_column(Integer, nullable=False)
    price_kopecks_snapshot: Mapped[int] = mapped_column(BigInteger, nullable=False)
    validity_days_snapshot: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sessions_remaining: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(
        String(16), server_default=text("'active'"), nullable=False,
    )
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    cancellation_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        CheckConstraint(
            "status IN ('active', 'exhausted', 'expired', 'cancelled')",
            name="status",
        ),
        CheckConstraint(
            "sessions_remaining >= 0 AND sessions_remaining <= session_count_snapshot",
            name="sessions_remaining_bounded",
        ),
        Index(
            "uq_pt_packages_active_per_client",
            "client_id",
            unique=True,
            postgresql_where=text("status = 'active'"),
        ),
        Index("ix_pt_packages_client_id", "client_id"),
        Index("ix_pt_packages_status", "status"),
        Index("ix_pt_packages_plan_id", "plan_id"),
    )
```

---

### `app/modules/pt_packages/repository.py` (repository, CRUD)

**Analog:** `app/modules/memberships/repository.py`

**Module docstring + `from __future__ import annotations`** (analog lines 1-49) — required because helpers return `PaginatedData[PtPackage]` (SA ORM not Pydantic-compatible).

**Soft-delete-aware plan reads** (analog `get_alive` lines 74-81 + `get_plan_for_renewal` 84-101):
```python
async def get_plan_alive(session: AsyncSession, plan_id: UUID) -> PtPackagePlan | None:
    stmt: Select[tuple[PtPackagePlan]] = select(PtPackagePlan).where(
        PtPackagePlan.id == plan_id,
        PtPackagePlan.deleted_at.is_(None),
    )
    return await session.scalar(stmt)
```

**Plan list with `?include_archived`** (analog `list_alive` lines 104-149) — mirrors `MembershipPlanListQuery`/`active` filter idiom.

**Plan in-use check (mirrors soft_delete_plan EXISTS pattern)** (analog `service.soft_delete_plan` lines 474-480):
```python
async def has_instances_for_plan(session: AsyncSession, plan_id: UUID) -> bool:
    stmt = select(PtPackage.id).where(PtPackage.plan_id == plan_id).limit(1)
    return (await session.scalar(stmt)) is not None
```

**Instance read by id** (analog `get_membership` lines 241-250):
```python
async def get_pt_package(session: AsyncSession, pt_package_id: UUID) -> PtPackage | None:
    stmt: Select[tuple[PtPackage]] = select(PtPackage).where(PtPackage.id == pt_package_id)
    return await session.scalar(stmt)
```

**Active-for-client resolver helper** (analog `find_active_for_client` lines 361-423) — used by Protocol slot:
```python
async def find_active_for_client(session: AsyncSession, client_id: UUID) -> PtPackage | None:
    stmt = (
        select(PtPackage)
        .where(PtPackage.client_id == client_id, PtPackage.status == "active")
        .order_by(PtPackage.created_at.desc())
        .limit(1)
    )
    return await session.scalar(stmt)
```

**Bulk-expire helper** (analog `expire_due_rows` lines 431-467):
```python
async def expire_due_pt_packages_bulk_returning(
    session: AsyncSession, today: date,
) -> Sequence[Row[tuple[UUID, UUID, date]]]:
    stmt = (
        update(PtPackage)
        .where(
            PtPackage.status == "active",
            PtPackage.end_date.is_not(None),
            PtPackage.end_date < today,
        )
        .values(status="expired")
        .returning(PtPackage.id, PtPackage.client_id, PtPackage.end_date)
    )
    result = await session.execute(stmt)
    return result.all()
```

**Narrow status setter** (analog `update_membership_status` lines 338-358):
```python
async def update_pt_package_status(
    session: AsyncSession,
    pt_package: PtPackage,
    *,
    status: str,
    cancellation_reason: str | None = None,
) -> PtPackage:
    pt_package.status = status
    if cancellation_reason is not None:
        pt_package.cancellation_reason = cancellation_reason
    return pt_package
```

---

### `app/modules/pt_packages/schemas.py` (schema, request-response)

**Analog:** `app/modules/memberships/schemas.py`

**`BackendSchemaBase` + `extra='forbid'`** (auto inherited) — analog lines 36-46.

**Plan create/update/response** — mirror `MembershipPlanCreateRequest` (lines 51-65) / `MembershipPlanUpdateRequest` (lines 70-101) / `MembershipPlanResponse` (lines 107-119). D-33-07: `PtPackagePlanUpdate` INCLUDES `session_count`/`price_kopecks`/`validity_days` as `Optional[int]` so service can return 409 `field_immutable` (NOT 422):
```python
class PtPackagePlanUpdateRequest(BackendSchemaBase):
    """PATCH body. Immutable fields included so service can return 409 field_immutable
    (NOT schema-level 422). Mirror v1.2 membership_plans pattern; D-33-07."""
    name: str | None = Field(default=None, min_length=1, max_length=120)
    # Included so service can compare and reject — NOT for actual mutation.
    session_count: int | None = Field(default=None, ge=1)
    price_kopecks: int | None = Field(default=None, ge=1)
    validity_days: int | None = Field(default=None, ge=1)
    # _reject_explicit_null model_validator copied verbatim from analog lines 84-95.
```

**Instance create/cancel/refund/response** — mirror `MembershipCreateRequest` (lines 178-192), `MembershipCancelRequest` (lines 198-221), `MembershipRefundRequest` (lines 227-248), `MembershipResponse` (lines 254-284).

**Refund schema (required `reason: str ≤200`, `extra='forbid'`)** (analog memberships/schemas.py lines 227-248):
```python
class PtPackageRefundRequest(BackendSchemaBase):
    """POST /pt-packages/{id}/refund body. Mirror MembershipRefundRequest (REF-05/06)."""
    reason: str = Field(min_length=1, max_length=200)


class PtPackageCancelRequest(BackendSchemaBase):
    """POST /pt-packages/{id}/cancel body (D-33-10). reason is REQUIRED for cancel-without-refund."""
    reason: str = Field(min_length=1, max_length=200)


class PtPackageCreateRequest(BackendSchemaBase):
    """POST /pt-packages body (D-33-09).

    `amount_kopecks` is REQUIRED (snapshot symmetry — server validates
    amount_kopecks == plan.price_kopecks, raises 422 amount_mismatch on
    disagreement; mirrors Phase 32 PAY-05).
    """
    client_id: UUID
    plan_id: UUID
    amount_kopecks: int = Field(ge=1)
```

**Response** — full snapshot + status + sessions_remaining + dates (D-33-09 line 37):
```python
class PtPackageResponse(ResponseData):
    id: UUID
    client_id: UUID
    plan_id: UUID
    plan_name_snapshot: str
    session_count_snapshot: int
    price_kopecks_snapshot: int
    validity_days_snapshot: int | None
    sessions_remaining: int
    status: PtPackageStatus  # StrEnum mirror MembershipStatus
    start_date: date
    end_date: date | None
    cancellation_reason: str | None
    created_at: datetime
    updated_at: datetime
```

---

### `app/modules/pt_packages/service.py` (service, request-response + orchestration)

**Analog:** `app/modules/memberships/service.py`

**Imports + module docstring discipline** (analog lines 1-122) — emphasises caller-owns-txn, audit emit ordering, constraint-name literal references, importlinter cross-module discipline.

**Imports must include** (analog line 77):
```python
from app.core.dependencies import CurrentUser, get_payment_recorder, get_payment_refunder
```

**Status FSM central guard + wrappers** (analog `_assert_can_transition` lines 198-251):
```python
def _assert_can_transition(pt_package: PtPackage, *, target: str) -> None:
    allowed = PT_PACKAGE_STATUS_TRANSITIONS.get(pt_package.status, frozenset())
    if target not in allowed:
        raise InvalidTransitionError(
            "invalid_transition",
            fields={"from_status": pt_package.status, "to_status": target},
        )

def _assert_can_cancel(pkg: PtPackage) -> None:
    _assert_can_transition(pkg, target="cancelled")

def _assert_can_expire(pkg: PtPackage) -> None:
    _assert_can_transition(pkg, target="expired")

def _assert_can_exhaust(pkg: PtPackage) -> None:
    _assert_can_transition(pkg, target="exhausted")
```

**Constraint-name discriminators** (analog `_is_plan_name_conflict` lines 125-135):
```python
def _is_pt_package_plan_name_conflict(exc: IntegrityError) -> bool:
    constraint = getattr(exc.orig, "constraint_name", None) or ""
    if constraint == "uq_pt_package_plans_name_alive":
        return True
    return "uq_pt_package_plans_name_alive" in str(exc.orig)


def _is_active_pt_package_conflict(exc: IntegrityError) -> bool:
    constraint = getattr(exc.orig, "constraint_name", None) or ""
    if constraint == "uq_pt_packages_active_per_client":
        return True
    return "uq_pt_packages_active_per_client" in str(exc.orig)
```

**Sale orchestrator** — mirror `memberships.service.create_membership` (lines 514-596):
```python
async def create_pt_package(
    session: AsyncSession,
    actor: CurrentUser,
    data: PtPackageCreateRequest,
) -> PtPackageResponse:
    """Sell a PT-package (PT-07). reception+owner per B-07. Orchestrator owns UoW.

    Order (mirror D-32-11 + Plan 32-02):
      1. Load plan via repository.get_plan_alive (404 pt_package_plan_not_found).
      2. Validate amount_kopecks == plan.price_kopecks → 422 amount_mismatch (D-33-17).
      3. Pre-flight existence check (active pkg for client) → 409 active_pt_package_already_exists.
      4. Compute start_date Europe/Moscow + end_date = start_date + validity_days - 1 (or None).
      5. INSERT instance with snapshots + sessions_remaining=plan.session_count + status='active'.
      6. Flush — surfaces FK + uq_pt_packages_active_per_client race → 409.
      7. Call payment_recorder Protocol slot (snapshot symmetry).
      8. audit.emit('pt_package_sold', ...).
      9. await session.commit().
    """
    plan = await repository.get_plan_alive(session, data.plan_id)
    if plan is None:
        raise PtPackagePlanNotFoundError("pt_package_plan_not_found")

    if data.amount_kopecks != plan.price_kopecks:  # D-33-17
        raise ValidationAppError("amount_mismatch",
                                 fields={"expected": plan.price_kopecks,
                                         "received": data.amount_kopecks})

    if await repository.find_active_for_client(session, data.client_id) is not None:
        raise ActivePtPackageAlreadyExistsError("active_pt_package_already_exists")

    start_date = datetime.now(ZoneInfo("Europe/Moscow")).date()
    end_date = (
        start_date + timedelta(days=plan.validity_days - 1)
        if plan.validity_days is not None else None
    )

    pt_package = await repository.insert_pt_package(
        session, data, plan=plan, start_date=start_date, end_date=end_date,
    )
    try:
        await session.flush()
    except IntegrityError as exc:
        await session.rollback()
        if _is_active_pt_package_conflict(exc):
            raise ActivePtPackageAlreadyExistsError("active_pt_package_already_exists") from exc
        raise

    payment = await get_payment_recorder()(
        session,
        subject_kind=PAYMENT_SUBJECT_KIND_PT_PACKAGE,
        subject_id=pt_package.id,
        amount_kopecks=pt_package.price_kopecks_snapshot,
        method="cash",
        received_by_user_id=actor.id,
        audit_actor=actor,
    )

    await audit.emit(
        session,
        "pt_package_sold",  # LITERAL — INFRA-11 AST gate
        actor_user_id=actor.id,
        resource_type="pt_package",  # LITERAL
        resource_id=pt_package.id,
        pt_package_id=str(pt_package.id),
        client_id=str(pt_package.client_id),
        plan_id=str(pt_package.plan_id),
        session_count_snapshot=pt_package.session_count_snapshot,
        price_kopecks_snapshot=pt_package.price_kopecks_snapshot,
        validity_days_snapshot=pt_package.validity_days_snapshot,
        payment_id=str(payment.id),
    )
    await session.commit()
    return PtPackageResponse.model_validate(pt_package, from_attributes=True)
```

**Refund orchestrator** — mirror `memberships.service.refund_membership` (lines 690-802) VERBATIM minus freeze guard / renewal-source guard:
```python
async def refund_pt_package(
    session: AsyncSession,
    actor: CurrentUser,
    pt_package_id: UUID,
    data: PtPackageRefundRequest,
) -> PtPackageResponse:
    """Refund a PT-package (REF-02 / B-07). reception+owner. Orchestrator owns UoW.

    Sources allowed: {active, exhausted, expired}. cancelled → 409 invalid_transition.
    NO freeze guard (v1.4 has no PT-freeze). NO renewed-source guard (v1.4 has no
    PT-renewal).
    """
    pt_package = await repository.get_pt_package(session, pt_package_id)
    if pt_package is None:
        raise PtPackageNotFoundError("pt_package_not_found")

    _assert_can_transition(pt_package, target="cancelled")

    refund_payment = await get_payment_refunder()(
        session,
        subject_kind=PAYMENT_SUBJECT_KIND_PT_PACKAGE,
        subject_id=pt_package_id,
        refund_user_id=actor.id,
        reason=data.reason,
        audit_actor=actor,
    )

    await repository.update_pt_package_status(
        session, pt_package, status="cancelled",
        cancellation_reason=CANCELLATION_REASON_REFUNDED,
    )
    await session.flush()

    await audit.emit(
        session,
        "pt_package_refunded",  # LITERAL
        actor_user_id=actor.id,
        resource_type="pt_package",  # LITERAL
        resource_id=pt_package.id,
        pt_package_id=str(pt_package.id),
        client_id=str(pt_package.client_id),
        refund_payment_id=str(refund_payment.id),
        reason=data.reason,
    )
    await session.refresh(pt_package, attribute_names=["updated_at"])
    await session.commit()
    return PtPackageResponse.model_validate(pt_package, from_attributes=True)
```

**Cancel-without-refund** — mirror `cancel_membership` (lines 599-682), strip frozen-source branch:
```python
async def cancel_pt_package(
    session: AsyncSession,
    actor: CurrentUser,
    pt_package_id: UUID,
    data: PtPackageCancelRequest,
) -> PtPackageResponse:
    """Cancel a PT-package without refund (PT-08, owner-only). D-33-10.

    Distinct from refund (REF-02): NO payment row insert; NO payment_refunder call.
    Use case: operator commits a sales error with manual out-of-band refund handling.
    """
    pt_package = await repository.get_pt_package(session, pt_package_id)
    if pt_package is None:
        raise PtPackageNotFoundError("pt_package_not_found")

    _assert_can_cancel(pt_package)
    prior_status = pt_package.status

    await repository.update_pt_package_status(
        session, pt_package, status="cancelled",
        cancellation_reason=data.reason,  # free-text, NOT 'refunded' sentinel
    )
    await session.flush()

    await audit.emit(
        session,
        "pt_package_cancelled",  # LITERAL
        actor_user_id=actor.id,
        resource_type="pt_package",  # LITERAL
        resource_id=pt_package.id,
        pt_package_id=str(pt_package.id),
        client_id=str(pt_package.client_id),
        cancellation_reason=data.reason,
    )
    await session.refresh(pt_package, attribute_names=["updated_at"])
    await session.commit()
    return PtPackageResponse.model_validate(pt_package, from_attributes=True)
```

**ARQ-helper `_expire_due_pt_packages`** — mirror `_expire_due_memberships` (lines 1271-1330):
```python
async def _expire_due_pt_packages(  # noqa: SVC001 caller-owns-txn
    session: AsyncSession,
    today: date | None = None,
) -> int:
    """Bulk-flip overdue active PT-packages to expired + emit per-row audits.

    Worker is transaction owner. Helper carries `# noqa: SVC001 caller-owns-txn`.
    NULL end_date rows are excluded (D-33-14 — бессрочные пакеты).
    """
    if today is None:
        today = datetime.now(ZoneInfo("Europe/Moscow")).date()

    rows = await repository.expire_due_pt_packages_bulk_returning(session, today)

    for pt_package_id, client_id, end_date in rows:
        await audit.emit(
            session,
            "pt_package_expired",  # LITERAL
            actor_user_id=None,    # system-driven cron
            resource_type="pt_package",  # LITERAL
            resource_id=pt_package_id,
            pt_package_id=str(pt_package_id),
            client_id=str(client_id),
            end_date=end_date.isoformat(),  # PtPackageExpiredPayload expects str
        )

    return len(rows)
```

**Plan CRUD** — mirror `create_plan`/`update_plan`/`soft_delete_plan` (lines 353-506) verbatim with:
- `audit.emit('pt_package_plan_created' | '_updated' | '_archived', ...)`
- Immutability check in `update_pt_package_plan` (D-33-07): compare incoming non-None values for `session_count`/`price_kopecks`/`validity_days` to current — if any differ, raise `FieldImmutableError("field_immutable")` → 409.
- `soft_delete_pt_package_plan` runs `repository.has_instances_for_plan` pre-flight (mirror analog lines 474-480) → 409 `plan_in_use`.

**Active-pt-package resolver export** (D-33-12) — mirror `resolve_active_membership_by_client` (analog `service.resolve_active_membership_by_client` near line 1240):
```python
async def resolve_active_pt_package(session: AsyncSession, client_id: UUID) -> PtPackage | None:
    """Public resolver consumed by core.dependencies slot (D-33-12).

    Returns the canonical active package for `client_id` (Phase 34 PT-session
    sale validates active pkg via this Protocol slot). Silent-None semantics
    (mirror _active_membership_resolver line 117).
    """
    return await repository.find_active_for_client(session, client_id)
```

---

### `app/modules/pt_packages/router.py` (router, request-response)

**Analog:** `app/modules/memberships/router.py`

**Two `APIRouter()` instances** mirror Phase 16+17 split (analog lines 104 + 228): one for `/pt-package-plans` (owner-only CRUD), one for `/pt-packages` (mixed RBAC).

**Owner-only CRUD pattern** (analog plans_router lines 107-206) — apply for every PT-package-plans endpoint.

**Reception+owner sale endpoint with Idempotency-Key** (analog `create_membership` lines 280-373) — full pattern including raw-body hash, two-phase Redis claim, replay branch:
```python
@pt_packages_router.post(
    "",
    response_model=ResponseEnvelope[PtPackageResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Sell a PT-package (reception+owner; requires Idempotency-Key — PAY-09 forward seam)",
)
async def create_pt_package(
    payload: PtPackageCreateRequest,
    request: Request,
    actor: Annotated[
        CurrentUser,
        Depends(require_permission(Action.CREATE, Resource.PT_PACKAGES)),
    ],
    _csrf: Annotated[None, Depends(verify_csrf)],
    idempotency_key: Annotated[str, Depends(verify_idempotency)],
    redis: Annotated[Redis, Depends(get_redis)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> Response:
    # Body-hash replay block — copy lines 322-373 from memberships/router.py verbatim,
    # substitute `service.create_pt_package(session, actor, payload)` and `pt_package` var.
    ...
```

**Refund endpoint pattern** (analog `refund_membership` lines 514-561) — reception+owner per B-07, CSRF required, NO Idempotency-Key (DB partial UNIQUE provides natural idempotency per D-32-20):
```python
@pt_packages_router.post(
    "/{pt_package_id}/refund",
    response_model=ResponseEnvelope[PtPackageResponse],
    status_code=status.HTTP_200_OK,
    summary=("Refund a PT-package (reception+owner per B-07; "
             "409 invalid_transition / already_refunded; 422 amountKopecks)"),
)
async def refund_pt_package(
    pt_package_id: UUID,
    payload: PtPackageRefundRequest,
    actor: Annotated[
        CurrentUser, Depends(require_permission(Action.REFUND, Resource.PT_PACKAGES)),
    ],
    _csrf: Annotated[None, Depends(verify_csrf)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ResponseEnvelope[PtPackageResponse]:
    pt_package = await service.refund_pt_package(session, actor, pt_package_id, payload)
    return envelope(pt_package)
```

**Cancel (owner-only)** — mirror `cancel_membership` lines 376-409 (CSRF required, REFUND-style endpoint shape; D-33-16 says **Idempotency-Key REQUIRED on cancel too** — diverges from membership cancel; add `verify_idempotency` Depends + replay block from sale).

**RBAC-04 ordering invariant** preserved on every mutation: `require_permission` BEFORE `verify_csrf` BEFORE `verify_idempotency` (analog lines 290-300).

---

### `app/workers/scheduled/expire_pt_packages.py` (worker, batch)

**Analog:** `app/workers/scheduled/expire_memberships.py` (verbatim — only module/function names change)

**Full file pattern** (analog lines 1-72):
```python
"""ARQ scheduled job: flip expired PT-packages (Phase 33 PT-12).

Per Phase 18 D-09: this worker file MAY import
`app.modules.pt_packages.service` — same shape as memberships.

Transaction ownership: this function is the transaction owner. The service
helper `_expire_due_pt_packages` (Plan 33-0X) issues bulk UPDATE +
per-row audit emits but does NOT commit (carries `# noqa: SVC001 caller-owns-txn`).
"""

from __future__ import annotations
from typing import Any
import structlog

from app.modules.pt_packages import service as pt_packages_service

_log = structlog.get_logger("workers.scheduled.expire_pt_packages")


async def expire_pt_packages(ctx: dict[str, Any]) -> int:
    """Flip overdue active PT-packages to expired; return count of newly-expired rows."""
    session_factory = ctx["sessionmaker"]
    async with session_factory() as session:
        count = await pt_packages_service._expire_due_pt_packages(session)
        await session.commit()

    _log.info("expire_pt_packages_complete", count=count)  # CD-03 convention
    return count
```

---

### `app/workers/__init__.py` (worker config, cron-registration) — MODIFIED

**Analog:** Existing `expire_memberships` cron entry (lines 88-95) + import (line 61) + function list (line 77)

**Add import** (analog line 61):
```python
from app.workers.scheduled.expire_pt_packages import expire_pt_packages
```

**Append to `functions` list** (analog line 77):
```python
functions: ClassVar[list[Any]] = [
    expire_memberships, send_expiring_notifications, expire_pt_packages,
]
```

**Append to `cron_jobs` list** (analog lines 88-103) — `hour=3, minute=25` UTC = 06:25 Europe/Moscow per D-33-13 / Pitfall 4:
```python
cron_jobs: ClassVar[list[Any]] = [
    cron(expire_memberships,           hour=3, minute=5,  unique=True, keep_result=60),
    cron(send_expiring_notifications,  hour=3, minute=15, unique=True, keep_result=60),
    cron(expire_pt_packages,           hour=3, minute=25, unique=True, keep_result=60),
]
```

**Cron-resolution invariant** (analog lines 117-125) — already a static assertion in `on_startup`; new entry must pass automatically. Extend `test_worker_cron_resolution.py` to cover `expire_pt_packages` explicitly.

---

### `app/core/dependencies.py` (slot/Protocol) — MODIFIED

**Analog:** Existing `ActiveMembership` block (lines 65-119)

**Insert after `ActiveMembership` block, before `ClientByTelegram`** (or after `TrainerById` to keep v1.4 slots clustered):
```python
class ActivePtPackage(Protocol):
    """Structural type for the active-PT-package row (Phase 33 D-33-12).

    Per D-33-12: attributes consumed by Phase 34 pt_sessions service.
    The SA `PtPackage` ORM structurally satisfies this Protocol — no DTO
    conversion at the resolver boundary (mirrors ActiveMembership line 65).
    """

    id: UUID
    client_id: UUID
    status: str
    sessions_remaining: int
    end_date: date | None


ActivePtPackageResolver = Callable[[AsyncSession, UUID], Awaitable[ActivePtPackage | None]]

_active_pt_package_resolver: ActivePtPackageResolver | None = None


def register_active_pt_package_resolver(resolver: ActivePtPackageResolver) -> None:
    """Composition-root setter — called once by `app.main.create_app` in Phase 33.

    Mirrors register_active_membership_resolver (line 93). Wired EXCLUSIVELY
    from app/main.py (NOT telegram_bot.py — bot is not a PT-session consumer;
    mirrors D-32-14 payment recorder discipline; D-33-12).
    """
    global _active_pt_package_resolver
    _active_pt_package_resolver = resolver


async def resolve_active_pt_package(
    session: AsyncSession, client_id: UUID,
) -> ActivePtPackage | None:
    """Consumer entry point — used by app.modules.pt_sessions in Phase 34.

    Silent-None when slot is unset (mirrors _active_membership_resolver
    line 117). Defensive-raise pattern is reserved for payment recorder/refunder
    (D-33-12 explicit choice — package absence is an expected state).
    """
    if _active_pt_package_resolver is None:
        return None
    return await _active_pt_package_resolver(session, client_id)
```

---

### `app/main.py` (composition root) — MODIFIED

**Analog:** Existing `register_active_membership_resolver(...)` block (lines 117-124) + Phase 32 payment slot block (lines 147-159)

**Insert after `register_payment_refunder(...)` (line 159)**:
```python
# Phase 33 D-33-12 — register ActivePtPackage resolver. Wired EXCLUSIVELY
# here (NOT telegram_bot.py — bot is not a PT-session participant in v1.4;
# mirrors D-32-14 payment recorder discipline). Phase 34 pt_sessions service
# will call resolve_active_pt_package() through the slot.
from app.core.dependencies import register_active_pt_package_resolver  # local-import to keep import diff narrow
from app.modules.pt_packages import service as pt_packages_service

register_active_pt_package_resolver(pt_packages_service.resolve_active_pt_package)
```

---

### `app/api/v1/router.py` (aggregator) — MODIFIED

**Analog:** Existing memberships dual-router include (lines 12-26)

**Add imports + includes** (mirror analog lines 12-18 + 25-27):
```python
from app.modules.pt_packages.router import (
    plans_router as pt_package_plans_router,  # owner-only CRUD on plans
)
from app.modules.pt_packages.router import (
    pt_packages_router,  # instance lifecycle (sale/cancel/refund/list/get)
)

v1.include_router(pt_package_plans_router, prefix="/pt-package-plans", tags=["pt-package-plans"])
v1.include_router(pt_packages_router,       prefix="/pt-packages",       tags=["pt-packages"])
```

---

### `app/modules/payments/service.py` (service) — MODIFIED

**Analog:** Existing `issue_refund` branch on `SUBJECT_KIND_MEMBERSHIP` (lines 164-170)

**Replace `NotImplementedError` for `pt_package`** with concrete branch that loads original via a new repository helper `get_original_pt_package_payment` (symmetric to `get_original_membership_payment` lines 101-123 of `payments/repository.py`):
```python
# In payments/service.py, lines 164-170 replacement:
if subject_kind == SUBJECT_KIND_MEMBERSHIP:
    original = await repository.get_original_membership_payment(session, subject_id)
elif subject_kind == SUBJECT_KIND_PT_PACKAGE:  # Phase 33 REF-02
    original = await repository.get_original_pt_package_payment(session, subject_id)
else:
    raise NotImplementedError(f"refund subject_kind={subject_kind!r} not supported")
```

**Add constant + helper** in `payments/constants.py` + `payments/repository.py`:
```python
# constants.py
SUBJECT_KIND_PT_PACKAGE = "pt_package"

# repository.py (mirror get_original_membership_payment lines 101-123)
async def get_original_pt_package_payment(
    session: AsyncSession, pt_package_id: UUID,
) -> Payment | None:
    stmt: Select[tuple[Payment]] = (
        select(Payment)
        .where(
            Payment.subject_kind == SUBJECT_KIND_PT_PACKAGE,
            Payment.subject_id == pt_package_id,
            Payment.amount_kopecks > 0,
        )
        .order_by(Payment.received_at.asc())
        .limit(1)
    )
    return await session.scalar(stmt)
```

---

### Test files (4 integration + 1 unit + 1 cron + 1 invariant)

**Analogs:** memberships integration tests + Plan 32-03 refund tests + Plan 18-01 cron tests.

**`tests/unit/pt_packages/test_state_machine.py`** — exhaustive 16-cell transition matrix (4 sources × 4 targets) mirroring memberships 9-cell pattern.

**`tests/integration/test_pt_packages_refund.py`** — mirror Plan 32-03 REF-TEST-01 verbatim (concurrent-refund race; expect 1×201 + 1×409 `already_refunded` via `uq_payments_refund_of_alive`). Postgres-only marker `@pytest.mark.postgres`; SQLite skip.

**`tests/integration/test_pt_packages_sale.py`** — golden path; snapshot symmetry mismatch 422; archived plan 404; already-active client 409 (both pre-check AND DB-level race).

**`tests/integration/test_expire_pt_packages_cron.py`** — mirror Plan 18-01 cron tests; verify `pt_package_expired` audit emit per row; rerun same day = 0 (idempotent SQL guard); NULL `end_date_snapshot` row never expires (D-33-14).

**`tests/unit/test_worker_cron_resolution.py`** — extend existing assertion to cover `expire_pt_packages` entry.

---

## Shared Patterns

### Authentication / RBAC

**Source:** `app/core/dependencies.py:require_permission` + `app/core/permissions.py:OWNER_ONLY` (lines 78-89 already contain PT-package OWNER_ONLY entries from Phase 30).

**Apply to:** All endpoints in `pt_packages/router.py`.

**Pattern** (analog `memberships/router.py` lines 280-300):
```python
actor: Annotated[
    CurrentUser,
    Depends(require_permission(Action.CREATE, Resource.PT_PACKAGES)),
],
_csrf: Annotated[None, Depends(verify_csrf)],
```

**RBAC matrix** (D-33-06, validated against `app/core/permissions.py:55-89`):

| Endpoint | Action | Resource | In OWNER_ONLY? | Allowed |
|----------|--------|----------|----------------|---------|
| `POST /pt-package-plans` | CREATE | PT_PACKAGE_PLANS | ✅ | owner |
| `GET /pt-package-plans[/{id}]` | VIEW | PT_PACKAGE_PLANS | ✅ | owner |
| `PATCH /pt-package-plans/{id}` | EDIT | PT_PACKAGE_PLANS | ✅ | owner |
| `DELETE /pt-package-plans/{id}` | DELETE | PT_PACKAGE_PLANS | ✅ | owner |
| `POST /pt-packages` | CREATE | PT_PACKAGES | ❌ | reception+owner |
| `GET /pt-packages[/{id}]` | VIEW | PT_PACKAGES | ❌ | reception+owner |
| `POST /pt-packages/{id}/cancel` | CANCEL | PT_PACKAGES | ✅ | owner |
| `POST /pt-packages/{id}/refund` | REFUND | PT_PACKAGES | ❌ | reception+owner (B-07) |

### Error handling (typed AppError → status code)

**Source:** `app/core/exceptions.py` + per-module subclasses (e.g. `memberships.service.MustUnfreezeFirstError` lines 170-181).

**Apply to:** `pt_packages/service.py` — declare per-error class with `code` + `status_code` (mirror memberships pattern). Required new classes:
- `PtPackagePlanNotFoundError(NotFoundError)` — 404 `pt_package_plan_not_found`
- `PtPackageNotFoundError(NotFoundError)` — 404 `pt_package_not_found`
- `ActivePtPackageAlreadyExistsError(ConflictError)` — 409 `active_pt_package_already_exists`
- `PlanInUseError` — reuse existing (memberships) or shadow with `PtPackagePlanInUseError("plan_in_use")` → 409
- `FieldImmutableError(ConflictError)` — 409 `field_immutable` (D-33-07; new shared in `app/core/exceptions.py` OR module-local)

**Pattern excerpt** (analog `memberships/service.py` lines 170-195):
```python
class MustUnfreezeFirstError(ConflictError):
    """Raised on POST /memberships/{id}/refund when source status is 'frozen'."""
    code = "must_unfreeze_first"
    status_code = 409
```

### Audit emit (LITERAL strings + str-cast UUIDs)

**Source:** `app/core/audit.py` AST gate (INFRA-11) + Plan 32-02 lesson on UUID JSONB encoding.

**Apply to:** Every state-mutating service function.

**Pattern** (analog `memberships/service.py` lines 578-589):
```python
await audit.emit(
    session,
    "pt_package_sold",  # LITERAL — Phase 15 INFRA-11 AST gate
    actor_user_id=actor.id,
    resource_type="pt_package",  # LITERAL
    resource_id=pt_package.id,                    # UUID — column type
    pt_package_id=str(pt_package.id),              # JSONB — str-cast
    client_id=str(pt_package.client_id),           # JSONB — str-cast
    ...,
)
```

### Caller-owns-txn (SVC001 gate)

**Source:** `tests/unit/test_service_commit_gate.py` walker; Phase 30 INFRA-21 scope (already includes `pt_packages/service.py`).

**Apply to:** Every public state-mutating function in `pt_packages/service.py`.

**Pattern:**
- Public orchestrators (`create_pt_package` / `cancel_pt_package` / `refund_pt_package` / `create_pt_package_plan` / `update_pt_package_plan` / `archive_pt_package_plan`): MUST call `await session.commit()` explicitly at end.
- Private helpers (`_expire_due_pt_packages`, `_assert_can_*`): use `# noqa: SVC001 caller-owns-txn` on the `def` line if state-mutating; leading underscore + marker BOTH required (analog `_expire_due_memberships` line 1271).

### Idempotency-Key Redis namespace

**Source:** `app/core/idempotency.py` (Phase 32 PAY-09); `verify_idempotency` + `begin_idempotency` + `load_idempotency_response`.

**Apply to:** `POST /pt-packages` (sale), `POST /pt-packages/{id}/cancel`, `POST /pt-packages/{id}/refund` per D-33-16.

**Pattern** (analog `memberships/router.py` lines 280-373, lines 322-373 body):
```python
idempotency_key: Annotated[str, Depends(verify_idempotency)],
redis: Annotated[Redis, Depends(get_redis)],
# ... then in body, full two-phase Redis claim + replay branch verbatim.
```

**NOTE — D-33-16 deviation from membership refund:** Membership refund (analog `refund_membership` router) does NOT use `Idempotency-Key` (DB partial UNIQUE provides natural idempotency per D-32-20 — verbatim from analog router lines 537-541). PT-package CONTEXT.md D-33-16 says ALL three endpoints require it. **Planner: reconcile this divergence — likely D-33-16 is correct (additional protection layer) and refund still falls through to DB partial UNIQUE for replay-with-different-body case.**

### Cross-module Protocol-slot consumption

**Source:** `app/core/dependencies.py:get_payment_recorder()` / `get_payment_refunder()` (lines 321-342).

**Apply to:** `pt_packages/service.create_pt_package` (recorder) + `pt_packages/service.refund_pt_package` (refunder).

**Pattern:**
- NEVER `from app.modules.payments import service` in `pt_packages/service.py` (would violate `modules-independent` contract; Phase 30 INFRA-20).
- Always go through `core.dependencies.get_payment_{recorder,refunder}()` defensive accessors.
- Mirrors `memberships/service.py:565-573` (recorder) and `757-764` (refunder).

### Pagination envelope

**Source:** `app/core/pagination.py:PaginatedData[T]` + `model_construct` rationale (analog `memberships/repository.py:143-149`).

**Apply to:** Every list endpoint response (`list_pt_package_plans`, `list_pt_packages`).

**Pattern:**
```python
return PaginatedData.model_construct(
    items=[PtPackageResponse.model_validate(p) for p in rows],
    total=total, page=query.page, page_size=query.page_size,
)
```

### Audit payload schema verification (CRITICAL)

**Source:** `app/core/audit_payloads.py` (Phase 30 Plan 30-01 — already locked).

**Verification per CONTEXT.md line 235-248 (`planner MUST verify`):**

Compare D-33-15 expected payloads against `audit_payloads.py` actual schemas. **Identified mismatches (planner must address):**

| Event | CONTEXT D-33-15 expected | `audit_payloads.py` actual | Action |
|-------|---------------------------|----------------------------|--------|
| `pt_package_sold` | `{pt_package_id, client_id, plan_id, plan_name_snapshot, session_count_snapshot, price_kopecks_snapshot, validity_days_snapshot, start_date, end_date}` | `{pt_package_id, client_id, plan_id, session_count_snapshot, price_kopecks_snapshot, validity_days_snapshot, payment_id}` (lines 176-187) | **Mismatch.** Schema is missing `plan_name_snapshot`, `start_date`, `end_date`; has `payment_id` instead. Planner: either (a) emit per schema (drop the extras from emit kwargs — recommended, schema is frozen contract) or (b) add supplementary plan to extend schema. Recommendation: **option (a)** — payment_id linkage is forensically more useful than start/end dates (which are stored on the row anyway). |
| `pt_package_cancelled` | `{pt_package_id, client_id, reason, prior_status}` | `{pt_package_id, client_id, cancellation_reason}` (lines 190-197) | **Mismatch.** Schema uses `cancellation_reason` not `reason`; no `prior_status` field. Planner: emit `cancellation_reason=<reason>` (schema-aligned); drop `prior_status` OR add it via supplementary plan to extend schema (extra='forbid' will reject otherwise). |
| `pt_package_refunded` | `{pt_package_id, client_id, refund_payment_id, reason}` | `{pt_package_id, client_id, refund_payment_id, reason}` (lines 200-208) | **Match.** |
| `pt_package_expired` | `{pt_package_id, client_id, end_date}` | `{pt_package_id, client_id, end_date: str}` (lines 220-231) | **Match** — but `end_date` is `str` (ISO format), so emit with `.isoformat()` cast (mirror Plan 18-01 `membership_expired` pattern). |
| `pt_package_exhausted` | `{pt_package_id, client_id, exhausted_at}` | `{pt_package_id, client_id}` (lines 211-217) | **Mismatch** — schema has no `exhausted_at`. Phase 33 does NOT emit this event (Phase 34 owns callsite). Defer reconciliation. |

**Recommendation for planner:** Open a sub-plan or inline action item in Plan 33-0X to align emit-side kwargs with the locked Pydantic schemas (extra='forbid' will fail at runtime otherwise). **Do not extend schemas additively unless absolutely necessary** — the frozenset entries are LOCKED contract from Phase 30; only the payload fields are flexible. Adding fields to the Pydantic model is OK; renaming is breaking.

---

## No Analog Found

All 18 files map to existing analogs. There are NO files in this phase without a precedent.

---

## Metadata

**Analog search scope:**
- `apps/backend/app/modules/memberships/` — primary plans+instances precedent (Phase 16, 17, 18, 24, 25, 26, 32)
- `apps/backend/app/modules/payments/` — Protocol-slot consumer pattern + append-only ledger
- `apps/backend/app/modules/trainers/` — module shape (constants/models/repository/schemas/service/router) precedent
- `apps/backend/app/workers/scheduled/expire_memberships.py` — cron worker precedent
- `apps/backend/app/core/dependencies.py` — Protocol-slot machinery
- `apps/backend/app/core/audit.py` + `audit_payloads.py` + `permissions.py` — locked bedrock from Phase 30
- `apps/backend/alembic/versions/0004_membership_plans.py`, `0005_memberships.py`, `0012_payments.py` — migration precedents

**Files scanned:** 22 source files (read fully or in relevant sections).

**Pattern extraction date:** 2026-05-15.

**Key cross-references for planner:**
- Phase 32 Plan 32-02 (sale-flow snapshot symmetry) → mirror for Plan 33-02 PT-sale.
- Phase 32 Plan 32-03 (refund orchestrator) → mirror for Plan 33-03 PT-refund.
- Phase 18 Plan 18-01 (ARQ cron + caller-owns-txn) → mirror for `expire_pt_packages`.
- Phase 30 INFRA-17/18/19/20/21 — all bedrock for PT_PACKAGE_* resources/audit/contract is in place.
- D-33-15 ↔ `audit_payloads.py` schema audit — planner MUST resolve the 3 listed mismatches before implementation begins.
