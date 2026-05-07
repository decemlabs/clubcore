# Phase 19: Visits — DB + reception check-in (backend) — Pattern Map

**Mapped:** 2026-05-07
**Files analyzed:** 18 (12 NEW + 5 MODIFY + 1 regenerated artifact)
**Analogs found:** 17 / 18 (one new pattern: Pydantic v2 `model_validator(mode='after')` for `Settings` cross-field — net-new)

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `apps/backend/alembic/versions/0006_visits.py` | migration | DDL/structural | `apps/backend/alembic/versions/0005_memberships.py` | role-match (NO `Computed` precedent — net-new for project) |
| `apps/backend/app/modules/visits/models.py` | model | ORM | `apps/backend/app/modules/memberships/models.py:85-161` (Membership — UUIDPkMixin + TimestampMixin, NO SoftDeleteMixin) | exact |
| `apps/backend/app/modules/visits/schemas.py` | schema | request-response (Pydantic) | `apps/backend/app/modules/memberships/schemas.py` | exact |
| `apps/backend/app/modules/visits/repository.py` | repository | CRUD | `apps/backend/app/modules/memberships/repository.py` | exact |
| `apps/backend/app/modules/visits/service.py` | service | CRUD + audit + multi-step orchestration | `apps/backend/app/modules/memberships/service.py` (+ deviation per D-05) | role-match (DEVIATES on reject-path commit) |
| `apps/backend/app/modules/visits/router.py` | controller | request-response | `apps/backend/app/modules/memberships/router.py:207-306` (memberships_router section) | exact |
| `apps/backend/app/modules/visits/__init__.py` | package init | n/a | `apps/backend/app/modules/clients/__init__.py` | exact |
| `apps/backend/app/core/dependencies.py` (extension) | dependency / Protocol slot | event-driven (registered callback) | same file lines 65-119 (`ActiveMembership` Protocol block) | exact |
| `apps/backend/app/core/exceptions.py` (5 new) | utility | n/a | same file lines 81-167 (existing `*NotFoundError` / `*Error(ConflictError)` classes) | exact |
| `apps/backend/app/core/config.py` (2 fields + validator) | config | config-load | same file (Settings) + Pydantic v2 docs (model_validator) | partial — net-new pattern |
| `apps/backend/.env.example` (2 lines) | config | config-load | (additive) | n/a |
| `apps/backend/app/modules/clients/service.py` (new function) | service | request-response (read) | `apps/backend/app/modules/auth/service.py:load_user_by_id` (loader pattern) | role-match |
| `apps/backend/app/main.py` (1 line) | composition root | event-driven (registration) | same file line 108 (`register_active_membership_resolver(...)`) | exact |
| `apps/backend/app/api/v1/router.py` (1 line) | route mount | request-response | same file line 23 (`memberships_router` mount) | exact |
| `apps/backend/openapi.json` | generated artifact | n/a | regenerated via `scripts/export_openapi.py` | n/a |
| `apps/backend/tests/integration/visits/*.py` | test | request-response | `apps/backend/tests/integration/memberships/test_memberships_audit.py` + `test_memberships_crud.py` + `test_memberships_rbac.py` | exact |
| `apps/backend/tests/integration/visits/conftest.py` | fixture | n/a | `apps/backend/tests/integration/memberships/conftest.py` (+ sibling fixture for D-13 real-commit) | role-match (D-13 sibling is partial-new) |
| `apps/backend/tests/integration/visits/test_alembic_visits.py` | test | DDL/migration | `apps/backend/tests/integration/test_alembic_clean.py` | role-match (extends with row-INSERT proof) |
| `apps/backend/tests/unit/visits/*.py` | test | unit (no DB) | `apps/backend/tests/unit/memberships/` | exact |

---

## Pattern Assignments

### `apps/backend/alembic/versions/0006_visits.py` (migration, DDL)

**Analog:** `apps/backend/alembic/versions/0005_memberships.py`

**Header pattern** (0005_memberships.py:1-31):
```python
"""memberships

Revision ID: 0005_memberships
Revises: 0004_membership_plans
Create Date: 2026-05-07 13:00:00.000000

Phase 17 / MEM-01 — membership instance table + composite resolver index.

Notes:
- Composite index (client_id, status, end_date DESC) installs DESC ordering on
  end_date via raw op.execute(); SQLAlchemy autogenerate cannot reliably
  represent the DESC qualifier inside a multi-column index. If autogenerate
  flags drift on this index, suppress via alembic/env.py:_include_object.
- The constraint name "fk_memberships_plan_id_membership_plans" is referenced
  as a literal string by app/modules/memberships/service.py:_is_plan_in_use_conflict
  (Phase 17 D-05). Renaming the FK requires updating the service helper.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0005_memberships"
down_revision: str | None = "0004_membership_plans"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None
```

**Phase 19 mapping:** revision = "0006_visits", down_revision = "0005_memberships". Docstring pinned literals: `uq_visits_client_id_gym_date` (referenced by service `_is_duplicate_visit_conflict`), `ck_visits_channel`.

**Table create + naming convention pattern** (0005_memberships.py:34-100):
```python
def upgrade() -> None:
    op.create_table(
        "memberships",
        sa.Column(
            "id", sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("client_id", sa.UUID(), nullable=False),
        sa.Column("plan_id", sa.UUID(), nullable=False),
        ...
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.text("now()"), nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('active', 'expired', 'cancelled')",
            name=op.f("ck_memberships_status"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_memberships")),
        sa.ForeignKeyConstraint(
            ["client_id"], ["clients.id"],
            name=op.f("fk_memberships_client_id_clients"),
            ondelete="RESTRICT",
        ),
        ...
    )
```

**Composite index via raw SQL** (0005_memberships.py:104-107):
```python
    op.execute(
        "CREATE INDEX ix_memberships_client_id_status_end_date "
        "ON memberships (client_id, status, end_date DESC)"
    )
```

**Phase 19 mirror:** `op.execute("CREATE INDEX ix_visits_client_id_checked_in_at ON visits (client_id, checked_in_at DESC)")`. UNIQUE on `(client_id, gym_date)` declared inline as `sa.UniqueConstraint("client_id", "gym_date", name="uq_visits_client_id_gym_date")` — composite UNIQUE has no DESC requirement so it stays in `op.create_table(...)`.

**Downgrade pattern** (0005_memberships.py:110-112):
```python
def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_memberships_client_id_status_end_date")
    op.drop_table("memberships")
```

**NET-NEW PATTERN — Postgres GENERATED ALWAYS … STORED column.** No precedent in `apps/backend/alembic/versions/`. Use SA 2.0 stock `Computed`:
```python
sa.Column(
    "gym_date", sa.Date,
    sa.Computed(
        "(checked_in_at AT TIME ZONE 'Europe/Moscow')::date",
        persisted=True,  # STORED (not VIRTUAL)
    ),
    nullable=False,
),
```
Cross-reference: `.planning/research/PITFALLS.md` Pitfall 5 #1 (canonical mitigation rationale); SA 2.0 docs cited in CONTEXT.md `<canonical_refs>` lines 259-261.

---

### `apps/backend/app/modules/visits/models.py` (model, ORM)

**Analog:** `apps/backend/app/modules/memberships/models.py:85-161` (Membership class — same composition: UUIDPkMixin + TimestampMixin, NO SoftDeleteMixin).

**Imports + composition pattern** (memberships/models.py:29-50):
```python
from __future__ import annotations

from datetime import date, datetime
from uuid import UUID as UUIDType  # noqa: N811

from sqlalchemy import (
    BigInteger, Boolean, CheckConstraint, Date, DateTime,
    ForeignKey, Index, Integer, String, Text, text,
)
from sqlalchemy.dialects.postgresql import UUID as PgUUID  # noqa: N811
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, SoftDeleteMixin, TimestampMixin, UUIDPkMixin
```

**Class shape pattern** (memberships/models.py:85-161):
```python
class Membership(Base, UUIDPkMixin, TimestampMixin):
    """Membership instance — client X bought plan Y on date Z (MEM-01).

    Snapshot pricing is immutable; status drives lifecycle. NO soft-delete
    column (Phase 17 D-12 / CONTEXT.md domain line 12) — cancelled rows
    keep their FK reference and block plan deletion (D-06).
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
    ...
    status: Mapped[str] = mapped_column(
        String(16),
        server_default=text("'active'"),
        nullable=False,
    )
    ...

    __table_args__ = (
        CheckConstraint(
            "status IN ('active', 'expired', 'cancelled')",
            name="status",  # NAMING_CONVENTION → ck_memberships_status
        ),
        Index(
            "ix_memberships_client_id_status_end_date",
            "client_id",
            "status",
            text("end_date DESC"),
        ),
    )
```

**Phase 19 mirror:**
- `class Visit(Base, UUIDPkMixin, TimestampMixin):` (NO SoftDeleteMixin per CD-04).
- `client_id`, `membership_id` FK ON DELETE RESTRICT; `checked_in_by` FK to `users.id` ON DELETE SET NULL.
- `gym_date` mapped with `Computed("(checked_in_at AT TIME ZONE 'Europe/Moscow')::date", persisted=True)` — same Computed string as the migration so autogen stays in sync.
- `__table_args__` with `CheckConstraint("channel IN ('reception', 'telegram_bot')", name="channel")` and `UniqueConstraint("client_id", "gym_date", name="uq_visits_client_id_gym_date")` and `Index("ix_visits_client_id_checked_in_at", "client_id", text("checked_in_at DESC"))`.

**Telegram-link column reference** (clients/models.py:89-92, 104):
```python
telegram_user_id: Mapped[int | None] = mapped_column(
    BigInteger,
    nullable=True,
)
...
UniqueConstraint("telegram_user_id", name="uq_clients_telegram_user_id"),
```
This is the column `resolve_client_by_telegram_user_id` (D-02) queries.

---

### `apps/backend/app/modules/visits/schemas.py` (schema, Pydantic v2)

**Analog:** `apps/backend/app/modules/memberships/schemas.py`.

**BackendSchemaBase contract** (core/schemas.py:36-53):
```python
class BackendSchemaBase(ContractModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        validate_by_name=True,
        validate_by_alias=True,
        extra="forbid",
    )
```

**Sealed request body pattern** (memberships/schemas.py:158-172):
```python
class MembershipCreateRequest(BackendSchemaBase):
    """POST /api/v1/memberships body (Phase 17 D-03).

    start_date / end_date / status / activation_policy are server-computed
    (D-04) and intentionally absent — the inherited extra='forbid' will reject
    any payload that includes them.
    """

    client_id: UUID
    plan_id: UUID
    paid_at: datetime | None = None
    notes: str | None = Field(default=None, max_length=1000)
```
**Phase 19 mirror:** `VisitCreateRequest(BackendSchemaBase)` declares `client_id: UUID` ONLY. Every other field (membershipId, checkedInAt, gymDate, channel, checkedInBy) is server-derived (D-01); `extra='forbid'` rejects them with stock 422.

**Response shape pattern** (memberships/schemas.py:207-229):
```python
class MembershipResponse(ResponseData):
    id: UUID
    client_id: UUID
    plan_id: UUID
    ...
    created_at: datetime
    updated_at: datetime
```

**List query with PageQuery extension** (memberships/schemas.py:235-247):
```python
class MembershipListQuery(PageQuery):
    """GET /api/v1/memberships query parameters (Phase 17 D-09)."""

    client_id: UUID | None = None
    status: MembershipStatus | None = None
    sort: MembershipListSort = MembershipListSort.CREATED_AT_DESC
```
**Phase 19 mirror:** `VisitListQuery(PageQuery)` with `client_id: UUID | None = None`, `from_: date | None = None` (alias `from`), `to: date | None = None`. NO sort enum (D-09 fixed `checked_in_at DESC`).

---

### `apps/backend/app/modules/visits/repository.py` (repository, CRUD)

**Analog:** `apps/backend/app/modules/memberships/repository.py`.

**Module docstring contract** (memberships/repository.py:1-23):
```python
"""Memberships repository — single point of access to the `MembershipPlan` ORM (MEM-PLAN-02).

This is the ONLY module in the codebase that imports the `MembershipPlan` ORM model.
The service layer calls these module-level async helpers and never executes
`select(MembershipPlan)` directly. ...

Transaction control: NO `session.commit()` and NO `session.flush()` calls live here.
The caller (service) owns the transactional moment so it can co-write the audit log
row in the same UoW (D-14, mirroring clients D-03).

`from __future__ import annotations` is required: `list_alive` is annotated with
`PaginatedData[MembershipPlan]`, and `MembershipPlan` is a SQLAlchemy ORM class
without a Pydantic core schema. ...
"""

from __future__ import annotations
```

**`get` helper pattern** (memberships/repository.py:193-202):
```python
async def get_membership(session: AsyncSession, membership_id: UUID) -> Membership | None:
    """Return Membership by id, or None.

    NO soft-delete filter — Memberships have no `deleted_at` column.
    """
    stmt: Select[tuple[Membership]] = select(Membership).where(Membership.id == membership_id)
    result: Membership | None = await session.scalar(stmt)
    return result
```
**Phase 19 mirror:** `get(session, visit_id)` — same shape, no soft-delete filter.

**`list_*` paginated pattern** (memberships/repository.py:205-257) — predicates list, count select, ordered+paginated select, `PaginatedData.model_construct(...)` (skips Pydantic validation against SA ORM generic).

**`insert` (caller-owns-flush) pattern** (memberships/repository.py:163-190):
```python
async def insert_membership(
    session: AsyncSession,
    data: MembershipCreateRequest,
    *,
    plan: MembershipPlan,
    start_date: date,
    end_date: date,
) -> Membership:
    """Create a Membership row. Caller MUST flush + commit (D-04 + Phase 16 pattern).
    ..."""
    membership = Membership(...)
    session.add(membership)
    return membership
```
**Phase 19 mirror:** `create(session, *, client_id, membership_id, channel, checked_in_by) -> Visit` — `session.add(...)` only; service catches `IntegrityError` on its own flush call.

---

### `apps/backend/app/modules/visits/service.py` (service, multi-step orchestration + audit)

**Analog (with deviation):** `apps/backend/app/modules/memberships/service.py`.

**`_is_X_conflict(exc)` IntegrityError-translation pattern.**

`_is_phone_conflict` (clients/service.py:99-104):
```python
def _is_phone_conflict(exc: IntegrityError) -> bool:
    """Return True iff `exc` was caused by `uq_clients_phone_alive` (D-11)."""
    constraint = getattr(exc.orig, "constraint_name", None) or ""
    if constraint == "uq_clients_phone_alive":
        return True
    return "uq_clients_phone_alive" in str(exc.orig)
```

`_is_plan_name_conflict` + `_is_plan_in_use_conflict` (memberships/service.py:73-101):
```python
def _is_plan_name_conflict(exc: IntegrityError) -> bool:
    """Return True iff `exc` was caused by `uq_membership_plans_name_alive` (D-02).

    Direct mirror of clients `_is_phone_conflict` with constraint name substituted.
    Checks `constraint_name` attribute first (asyncpg exposes this), then falls back
    to substring search on the stringified exception for drivers that don't expose it.
    """
    constraint = getattr(exc.orig, "constraint_name", None) or ""
    if constraint == "uq_membership_plans_name_alive":
        return True
    return "uq_membership_plans_name_alive" in str(exc.orig)


def _is_plan_in_use_conflict(exc: IntegrityError) -> bool:
    """Return True iff `exc` was the FK `fk_memberships_plan_id_membership_plans` (D-05).
    ...
    """
    constraint = getattr(exc.orig, "constraint_name", None) or ""
    if constraint == "fk_memberships_plan_id_membership_plans":
        return True
    return "fk_memberships_plan_id_membership_plans" in str(exc.orig)
```

**Phase 19 mirror — `_is_duplicate_visit_conflict`:**
```python
def _is_duplicate_visit_conflict(exc: IntegrityError) -> bool:
    """Return True iff `exc` was caused by `uq_visits_client_id_gym_date`."""
    constraint = getattr(exc.orig, "constraint_name", None) or ""
    if constraint == "uq_visits_client_id_gym_date":
        return True
    return "uq_visits_client_id_gym_date" in str(exc.orig)
```

**Pre-mutation guard helper pattern** (memberships/service.py:104-115):
```python
def _assert_can_cancel(membership: Membership) -> None:
    """Phase 17 D-12 + D-15: only status='active' may transition to 'cancelled'.

    Raised BEFORE any mutation so 409 path leaves zero side effects (D-15
    invariant). ...
    """
    if membership.status != "active":
        raise InvalidTransitionError(
            "invalid_transition",
            fields={"from_status": membership.status, "to_status": "cancelled"},
        )
```
**Phase 19 mirror — `_assert_within_gym_hours(now_msk: time)`:** raises `OutsideGymHoursError(...)` if `now_msk < gym_hours_start or now_msk >= gym_hours_end`. Pure synchronous helper, testable without DB (covered by `tests/unit/visits/test_anti_fraud_helpers.py`). Note the boundary: end is exclusive (CD-07).

**Standard "mutate → flush → IntegrityError translate → emit → commit" pattern** (memberships/service.py:161-195):
```python
async def create_plan(
    session: AsyncSession,
    actor: CurrentUser,
    data: MembershipPlanCreateRequest,
) -> MembershipPlanResponse:
    """Create a new membership plan (MEM-PLAN-EP-02).

    Order: insert → flush (surface DB constraints) → emit audit on success (D-14).
    For inserts we cannot emit before flush — the IntegrityError on
    `uq_membership_plans_name_alive` surfaces only when the row hits the DB. ...
    """
    plan = await repository.insert_plan(session, data)
    try:
        await session.flush()
    except IntegrityError as exc:
        await session.rollback()
        if _is_plan_name_conflict(exc):
            raise PlanNameExistsError("plan_name_exists") from exc
        raise

    await audit.emit(
        session,
        "membership_plan_created",
        actor_user_id=actor.id,
        resource_type="membership_plan",
        resource_id=plan.id,
        name=plan.name,
        duration_days=plan.duration_days,
        price_kopecks=plan.price_kopecks,
    )
    await session.commit()
    return MembershipPlanResponse.model_validate(plan)
```

**DEVIATION (Phase 19 D-05): reject paths emit + commit + raise.**

The standard Phase 16/17 "no commit on raise" rule is INVERTED for visits anti-fraud rejections so the audit log carries `visit_rejected_*` rows. The planner MUST document this deviation in the service module docstring so future contributors don't normalize it back. Skeleton structure for the private chain:

```python
async def _create_visit_with_anti_fraud(
    session: AsyncSession,
    *,
    client_id: UUID,
    channel: str,  # 'reception' | 'telegram_bot'
    checked_in_by: UUID | None,
    audit_actor_user_id: UUID | None,
) -> VisitResponse:
    # Step 1 — gym hours
    now_msk = datetime.now(ZoneInfo("Europe/Moscow")).time()
    if not (settings.gym_hours_start <= now_msk < settings.gym_hours_end):
        await audit.emit(
            session,
            "visit_rejected_outside_hours",  # LITERAL (Phase 15 INFRA-11 AST gate)
            actor_user_id=audit_actor_user_id,
            resource_type="visit",
            resource_id=None,
            client_id=str(client_id),
            channel=channel,
        )
        await session.commit()  # D-05 — preserve the rejection audit row
        raise OutsideGymHoursError(
            "outside_gym_hours",
            fields={
                "open": settings.gym_hours_start.isoformat(),
                "close": settings.gym_hours_end.isoformat(),
            },
        )

    # Step 2 — active membership
    membership = await resolve_active_membership(session, client_id)
    if membership is None:
        await audit.emit(
            session, "visit_rejected_no_membership",
            actor_user_id=audit_actor_user_id,
            resource_type="visit", resource_id=None,
            client_id=str(client_id), channel=channel,
        )
        await session.commit()  # D-05
        raise NoActiveMembershipError(
            "no_active_membership",
            fields={"client_id": str(client_id)},
        )

    # Step 3 — insert + duplicate
    visit = await repository.create(
        session,
        client_id=client_id,
        membership_id=membership.id,
        channel=channel,
        checked_in_by=checked_in_by,
    )
    try:
        await session.flush()
    except IntegrityError as exc:
        await session.rollback()  # poisoned session must roll back first
        if _is_duplicate_visit_conflict(exc):
            await audit.emit(
                session, "visit_rejected_duplicate",
                actor_user_id=audit_actor_user_id,
                resource_type="visit", resource_id=None,
                client_id=str(client_id), channel=channel,
                gym_date=str(_today_msk()),
            )
            await session.commit()  # D-05
            raise DuplicateCheckinError(
                "duplicate_checkin",
                fields={"client_id": str(client_id), "gym_date": str(_today_msk())},
            ) from exc
        raise  # Untranslated DB error — boundary `get_db.rollback()` cleans up.

    # Step 4 — success
    await audit.emit(
        session, "visit_created",
        actor_user_id=audit_actor_user_id,
        resource_type="visit", resource_id=visit.id,
        client_id=str(client_id),
        membership_id=str(membership.id),
        channel=channel,
    )
    await session.commit()
    return VisitResponse.model_validate(visit)
```

**Note on `audit.emit` payload shape (D-16 vs `app/core/audit.py:46` docstring drift):**
- `app/core/audit.py:46` (docstring): `visit_created — {visit_id, client_id, membership_id, channel, gym_date}`.
- CONTEXT.md D-16: `visit_created — {client_id, membership_id, channel}` with `resource_id=visit.id`.

The CONTEXT D-16 shape is correct (visit_id lives in `resource_id`, not payload — same convention as `membership_created` which OMITS `membership_id` from payload because `resource_id` carries it; see memberships/service.py:371-380 + audit_test assertion `set(payload.keys()) == {"client_id", "plan_id", "end_date"}` at memberships audit test line 121). The audit.py docstring drift should be reconciled in 19-01-PLAN.md (either update the docstring to match D-16, or document the deviation as VERIFICATION note). `gym_date` may be added to the success payload for consistency with the duplicate-rejection payload — planner should pick.

**Resolver-consumer pattern** (memberships/service.py:472-489) — Phase 19's `clients.service.resolve_client_by_telegram_user_id` mirrors:
```python
async def resolve_active_membership_by_client(
    session: AsyncSession,
    client_id: UUID,
) -> Membership | None:
    """Return the canonical active membership for `client_id`, or None (MEM-04, CD-06).
    ...
    """
    return await repository.find_active_for_client(session, client_id)
```
**Phase 19 mirror — `app/modules/clients/service.py`:**
```python
async def resolve_client_by_telegram_user_id(
    session: AsyncSession,
    tg_user_id: int,
) -> "Client" | None:
    """Look up alive client by Telegram user id (Phase 19 D-02).

    Used by Phase 19 visits service via `core.dependencies.resolve_client_by_telegram_user_id`
    (resolver Protocol slot). Wired in `app.main.create_app()` via
    `register_client_by_telegram_resolver(...)` — mirror of Phase 17's
    `register_active_membership_resolver` pattern.
    """
    stmt = select(Client).where(
        Client.telegram_user_id == tg_user_id,
        Client.deleted_at.is_(None),
    )
    return await session.scalar(stmt)
```

---

### `apps/backend/app/modules/visits/router.py` (controller, request-response)

**Analog:** `apps/backend/app/modules/memberships/router.py:207-306` (`memberships_router` block).

**Imports + APIRouter init** (memberships/router.py:60-83, 207):
```python
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import CurrentUser, require_permission, verify_csrf
from app.core.pagination import PaginatedData
from app.core.permissions import Action, Resource
from app.core.schemas import ResponseEnvelope, envelope
from app.modules.memberships import service
from app.modules.memberships.schemas import (...)

router = APIRouter()
```
**Phase 19 mirror:** `router = APIRouter()` (single — no second router needed; CD-05 ships `/visits` only).

**GET list pattern** (memberships/router.py:210-232):
```python
@memberships_router.get(
    "",
    response_model=ResponseEnvelope[PaginatedData[MembershipResponse]],
    summary="List memberships filtered by clientId/status with pagination",
)
async def list_memberships(
    query: Annotated[MembershipListQuery, Depends()],
    _actor: Annotated[
        CurrentUser,
        Depends(require_permission(Action.VIEW, Resource.MEMBERSHIPS)),
    ],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ResponseEnvelope[PaginatedData[MembershipResponse]]:
    page = await service.list_memberships(session, query)
    return envelope(page)
```

**GET by id pattern** (memberships/router.py:235-250) — same shape, 404 raised inside `service.get_*`.

**POST mutation pattern with RBAC-04 ordering (permission BEFORE csrf)** (memberships/router.py:253-275):
```python
@memberships_router.post(
    "",
    response_model=ResponseEnvelope[MembershipResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Sell a membership (reception+owner; 404 plan_not_found, 409 plan_inactive)",
)
async def create_membership(
    payload: MembershipCreateRequest,
    actor: Annotated[
        CurrentUser,
        Depends(require_permission(Action.CREATE, Resource.MEMBERSHIPS)),
    ],
    _csrf: Annotated[None, Depends(verify_csrf)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ResponseEnvelope[MembershipResponse]:
    """... CREATE permission + CSRF required.

    (CREATE, MEMBERSHIPS) is NOT in OWNER_ONLY — reception receives 201 on success.
    """
    membership = await service.create_membership(session, actor, payload)
    return envelope(membership)
```

**Phase 19 mirror:** 3 routes — `GET /` (list, `Action.VIEW, Resource.VISITS`), `GET /{id}` (get, `Action.VIEW`), `POST /` (create, `Action.CHECK_IN, Resource.VISITS` + `verify_csrf`). RBAC-04 ordering literal: in `create_visit` signature `Depends(require_permission(...))` parameter (`actor`) is declared BEFORE the `_csrf: Depends(verify_csrf)` parameter. `tests/integration/test_route_introspection.py` (Phase 6) enforces statically.

**Module docstring should also call out RBAC-04 ordering** (memberships/router.py:40-45 cited verbatim):
> "RBAC-04 ordering (clients/router.py precedent): in every mutation endpoint, `Depends(require_permission(...))` is declared BEFORE `Depends(verify_csrf)` in the function signature. FastAPI resolves signature dependencies in declaration order, so 401 (auth) fires before 403 (rbac/csrf), preserving the invariant that an unauthenticated caller never sees a CSRF error. `tests/integration/test_route_introspection.py` enforces this invariant statically."

---

### `apps/backend/app/core/dependencies.py` (extension — `ClientByTelegram` resolver block)

**Analog:** SAME FILE, lines 65-119 (the `ActiveMembership` Protocol block — Phase 17 D-18 precedent).

**Quote verbatim — the literal template Phase 19 mirrors** (dependencies.py:65-119):
```python
class ActiveMembership(Protocol):
    """Structural type for the active-membership row (MEM-05).

    Per D-18: only the 4 attributes consumed by Phase 19 visits service.
    Snapshot fields, plan_id, dates other than end_date, audit timestamps are
    NOT in the Protocol (visits doesn't need them). The SA `Membership` ORM
    structurally satisfies this Protocol because all 4 attributes are mapped
    — no DTO conversion at the resolver boundary.
    """

    id: UUID
    client_id: UUID
    end_date: date
    status: str


ActiveMembershipResolver = Callable[[AsyncSession, UUID], Awaitable[ActiveMembership | None]]
"""Async callable: (session, client_id) -> ActiveMembership | None.

Returns None when the client has no active membership (the canonical case the
visits service treats as 'no membership'). ...
"""

_active_membership_resolver: ActiveMembershipResolver | None = None


def register_active_membership_resolver(resolver: ActiveMembershipResolver) -> None:
    """Composition-root setter — called once by `app.main.create_app` in Phase 17.

    Second loader slot after `register_user_loader` (Phase 5 D-15). Idempotent:
    re-registering replaces the slot, useful for tests that inject a stub
    resolver via `create_app()`. Phase 17 wires
    `app.modules.memberships.service.resolve_active_membership_by_client`.
    """
    global _active_membership_resolver
    _active_membership_resolver = resolver


async def resolve_active_membership(
    session: AsyncSession, client_id: UUID
) -> ActiveMembership | None:
    """Consumer entry point — used by `app.modules.visits.service` in Phase 19.

    Per CONTEXT.md `<code_context>` line 224: returns None when the slot is
    unset (production code always registers in `create_app()`; tests can
    register a stub or rely on the default-None behaviour). ...
    """
    if _active_membership_resolver is None:
        return None
    return await _active_membership_resolver(session, client_id)
```

**Phase 19 net-new (D-02) — `ClientByTelegram` block.** Symbol-by-symbol mirror; only the type signature changes (`(session, telegram_user_id: int) -> ClientByTelegram | None`). Phase 19's `ClientByTelegram` Protocol declares ONLY `id: UUID` (visits service consumes only `.id` — see CONTEXT.md `<domain>` line 46). Rationale framing in the docstring should explicitly say "third resolver slot after `register_user_loader` and `register_active_membership_resolver`" so v1.3+ contributors recognise the pattern.

---

### `apps/backend/app/core/exceptions.py` (5 new exception classes)

**Analog:** SAME FILE. Existing precedents:

`ClientNotFoundError` shape (exceptions.py:81-85) — Phase 19's `VisitNotFoundError` and `ClientNotLinkedError`:
```python
class ClientNotFoundError(NotFoundError):
    """Raised when GET/PATCH/DELETE references a non-existent or soft-deleted client."""

    code = "client_not_found"
    status_code = 404
```

`PhoneExistsError` / `PlanInactiveError` shape (exceptions.py:88-93, 120-129) — Phase 19's `DuplicateCheckinError`, `OutsideGymHoursError`, `NoActiveMembershipError`:
```python
class PhoneExistsError(ConflictError):
    """Raised on POST/PATCH when phone collides with an alive client (Phase 8 D-11)."""

    code = "phone_exists"
    status_code = 409


class PlanInactiveError(ConflictError):
    """Raised on POST /memberships when target plan.active=False (Phase 17 D-02).

    Service-layer defence against UI bypass: the reception sell screen filters
    via ?active=true (Phase 16 D-08), but a malformed/replayed POST can still
    reference a deactivated plan.
    """

    code = "plan_inactive"
    status_code = 409
```

**Phase 19 additions** (D-12 + CONTEXT `<domain>` lines 60-65):
- `class NoActiveMembershipError(ConflictError): code = "no_active_membership"; status_code = 409`
- `class DuplicateCheckinError(ConflictError): code = "duplicate_checkin"; status_code = 409`
- `class OutsideGymHoursError(ConflictError): code = "outside_gym_hours"; status_code = 409`
- `class VisitNotFoundError(NotFoundError): code = "visit_not_found"; status_code = 404`
- `class ClientNotLinkedError(NotFoundError): code = "client_not_linked"; status_code = 404`

Constructor pattern with `fields={...}` (Phase 17 `InvalidTransitionError` precedent, exceptions.py:145-160):
```python
class InvalidTransitionError(ConflictError):
    """Raised on POST /memberships/{id}/cancel for non-active source state (Phase 17 D-12).

    Constructor populates `fields={'from_status': ..., 'to_status': ...}` packed
    into the response envelope's `fields` key (per AppError.__init__ signature at
    core/exceptions.py:13-16).

    Usage:
        raise InvalidTransitionError(
            "invalid_transition",
            fields={"from_status": membership.status, "to_status": "cancelled"},
        )
    """

    code = "invalid_transition"
    status_code = 409
```
Phase 19 `OutsideGymHoursError(..., fields={'open': ..., 'close': ...})` and `DuplicateCheckinError(..., fields={'client_id': ..., 'gym_date': ...})` follow this constructor convention.

---

### `apps/backend/app/core/config.py` (2 new fields + cross-field validator)

**Analog:** SAME FILE — Settings class skeleton at config.py:10-46. NET-NEW PATTERN: project has zero pre-existing `model_validator(mode='after')` on `Settings`; usages exist only in Pydantic *request* schemas (memberships/schemas.py:83, 190; clients/schemas.py:152), all `mode='before'`.

**Existing Settings structure** (config.py:10-46):
```python
class Settings(BaseSettings):
    """Read configuration from environment + .env file. No prefix; raw env var names."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: PostgresDsn
    redis_url: RedisDsn
    environment: Literal["dev", "staging", "prod"] = "dev"
    debug: bool = False
    secret_key: SecretStr

    access_token_ttl_seconds: int = 900
    refresh_token_ttl_seconds: int = 2_592_000
    ...
```

**Phase 19 additions** (D-10 / D-11 / VIS-05):
```python
from datetime import time
from pydantic import model_validator

class Settings(BaseSettings):
    ...
    # Phase 19 additions (VIS-05): gym hours window in Europe/Moscow.
    # Pydantic v2 parses "07:00" env strings → time(7, 0) natively.
    gym_hours_start: time = time(7, 0)
    gym_hours_end: time = time(23, 0)

    @model_validator(mode="after")
    def _gym_hours_range_invariant(self) -> "Settings":
        # D-11: no midnight-spanning gym hours in v1.2.
        if self.gym_hours_end <= self.gym_hours_start:
            raise ValueError(
                "gym_hours_end must be strictly greater than gym_hours_start "
                "(midnight-spanning ranges deferred to v1.3+)."
            )
        return self
```

**`.env.example` addition pattern** — append under a comment header. Defaults `GYM_HOURS_START=07:00` and `GYM_HOURS_END=23:00`. Production overrides via `apps/backend/docker-compose.yml environment:` block per CR-01 precedence.

---

### `apps/backend/app/main.py` (single-line addition in `create_app()`)

**Analog:** SAME FILE, line 108 (`register_active_membership_resolver(...)` — Phase 17 precedent).

**Existing block** (main.py:88-108):
```python
    # D-15: composition root fills the Phase 4 loader slot. This is the ONLY
    # place where app.main reaches into app.modules.*. The importlinter
    # contract scopes source_modules=app.core, so app.main is intentionally
    # outside the scope.
    #
    # WR-05 (Phase 9 review): register_user_loader is idempotent by design —
    # see app/core/dependencies.py:54-61. Re-registering replaces the slot,
    # which is intentional so tests can inject a stub loader through
    # create_app(). Calling it on every create_app() (per-test, per-export)
    # is therefore safe; ...
    register_user_loader(load_user_by_id)

    # Phase 17 MEM-05: second composition-root carve-out (after register_user_loader,
    # Phase 5 D-15). Same architectural exception — app.main is NOT in the
    # core-not-depend-on-modules importlinter scope. The visits service (Phase 19)
    # will call resolve_active_membership() through the slot; production wires the
    # real resolver here, tests can override via create_app() because the slot is
    # idempotent (mirrors WR-05 reasoning for register_user_loader).
    register_active_membership_resolver(resolve_active_membership_by_client)
```

**Phase 19 addition (single line + 4-line comment block):**
```python
    # Phase 19 D-02: third composition-root carve-out — visits self-checkin path
    # needs to look up Client by telegram_user_id without crossing the
    # modules-independent contract. Same idempotent slot pattern; tests can
    # override via create_app().
    register_client_by_telegram_resolver(
        clients.service.resolve_client_by_telegram_user_id,
    )
```
Imports added at top: `from app.core.dependencies import register_client_by_telegram_resolver` (extends existing import line 34) and `from app.modules.clients.service import resolve_client_by_telegram_user_id` (or `from app.modules import clients`).

---

### `apps/backend/app/api/v1/router.py` (single-line addition)

**Analog:** SAME FILE — current 4 mounts.

**Existing mount block** (api/v1/router.py:19-23):
```python
v1 = APIRouter()
v1.include_router(auth_router, prefix="/auth", tags=["auth"])
v1.include_router(clients_router, prefix="/clients", tags=["clients"])
v1.include_router(plans_router, prefix="/membership-plans", tags=["membership-plans"])
v1.include_router(memberships_router, prefix="/memberships", tags=["memberships"])
```

**Phase 19 addition (single line at the end):**
```python
v1.include_router(visits_router, prefix="/visits", tags=["visits"])
```
Plus import: `from app.modules.visits.router import router as visits_router`. Mounting last preserves the byte-stable `openapi.json` diff gate (per ARCHITECTURE.md line 450 / CONTEXT line 53).

---

### `apps/backend/tests/integration/visits/*.py` (test, request-response)

**Analogs:**
- Audit: `apps/backend/tests/integration/memberships/test_memberships_audit.py`
- CRUD: `apps/backend/tests/integration/memberships/test_memberships_crud.py`
- RBAC: `apps/backend/tests/integration/memberships/test_memberships_rbac.py`
- Conftest: `apps/backend/tests/integration/memberships/conftest.py`

**Authed-client + CSRF header pattern** (test_memberships_audit.py:25-65):
```python
def _csrf_headers(client: AsyncClient) -> dict[str, str]:
    return {"X-CSRF-Token": client.cookies.get("sportzal_csrf") or ""}


VALID_PLAN: dict[str, Any] = {
    "name": "Базовый",
    "durationDays": 30,
    "priceKopecks": 250000,
    "active": True,
}


async def _create_plan(authed: AsyncClient, **overrides: Any) -> dict[str, Any]:
    payload = {**VALID_PLAN, **overrides}
    r = await authed.post(
        "/api/v1/membership-plans",
        json=payload,
        headers=_csrf_headers(authed),
    )
    assert r.status_code == 201, r.text
    data: dict[str, Any] = r.json()["data"]
    return data
```

**Audit-row direct-query assertion pattern** (test_memberships_audit.py:101-122):
```python
async def test_membership_created_payload_shape(
    authed_client_owner: AsyncClient,
    db_session: AsyncSession,
    seeded_owner: User,
) -> None:
    ...
    rows = (
        await db_session.scalars(
            select(AuditLog).where(
                AuditLog.action == "membership_created",
                AuditLog.resource_id == membership_id,
            )
        )
    ).all()
    assert len(rows) == 1, f"expected exactly 1 row, got {len(rows)}"
    row = rows[0]
    assert row.actor_user_id == seeded_owner.id
    assert row.resource_type == "membership"
    assert row.resource_id == membership_id

    payload = row.payload
    assert payload["client_id"] == client["id"]
    ...
    # Defensive: only the 3 documented keys (membership_id is in resource_id).
    assert set(payload.keys()) == {"client_id", "plan_id", "end_date"}
```

**No-audit-on-failed-mutation assertion pattern** (test_memberships_audit.py:233-270) — Phase 19 INVERTS this: rejection paths SHOULD write an audit row (D-05). Test pattern becomes:

```python
async def test_outside_hours_rejection_writes_audit(
    authed_client_reception: AsyncClient,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """D-05: rejection emit + commit + raise — audit row IS persisted."""
    # Force outside-hours via Settings monkeypatch
    monkeypatch.setattr(settings, "gym_hours_start", time(0, 0))
    monkeypatch.setattr(settings, "gym_hours_end", time(0, 1))
    ...
    r = await authed_client_reception.post("/api/v1/visits", json={"clientId": str(client_id)}, headers=_csrf_headers(...))
    assert r.status_code == 409
    assert r.json()["code"] == "outside_gym_hours"

    rows = (await db_session.scalars(
        select(AuditLog).where(
            AuditLog.action == "visit_rejected_outside_hours",
            AuditLog.payload["client_id"].astext == str(client_id),
        )
    )).all()
    assert len(rows) == 1  # D-05 invariant
```

**Conftest fixture-factory pattern (per-role authed client + DB-direct seeders)** (memberships/conftest.py:79-256). Phase 19 conftest mirrors with role-cell fixtures + `make_client`, `make_membership` factories, plus the **D-13 sibling fixture `db_session_real_commit`** for VIS-TEST-01 only. Document inline:
> "VIS-TEST-01 concurrent test uses `db_session_real_commit` (NOT `db_session`) because the SAVEPOINT-based isolation interferes with concurrent INSERT serialization against the UNIQUE index. Real BEGIN/COMMIT per request + TRUNCATE `visits, audit_log` at fixture exit."

---

### `apps/backend/tests/integration/visits/test_alembic_visits.py` (migration smoke test)

**Analog:** `apps/backend/tests/integration/test_alembic_clean.py` (the entire file).

**Subprocess-driven `alembic upgrade head + alembic check`** (test_alembic_clean.py:36-69):
```python
async def test_alembic_check_clean(db_session: AsyncSession) -> None:
    """SC #3: alembic upgrade head + alembic check empty diff."""
    upgrade = subprocess.run(  # noqa: ASYNC221
        ["uv", "run", "alembic", "upgrade", "head"],  # noqa: S607
        cwd=str(BACKEND_DIR),
        capture_output=True,
        text=True,
        check=False,
    )
    assert upgrade.returncode == 0, ...

    check = subprocess.run(  # noqa: ASYNC221
        ["uv", "run", "alembic", "check"],
        cwd=str(BACKEND_DIR),
        capture_output=True,
        text=True,
        check=False,
    )
    assert check.returncode == 0, ...
    assert "No new upgrade operations detected" in check.stdout, ...
```

**Phase 19 EXTENSION (D-15, Pitfall 5 mandate) — prove `gym_date` STORED GENERATED column on real Postgres 16:**
```python
async def test_gym_date_generated_column_msk_shifted(db_session: AsyncSession) -> None:
    """D-15 / Pitfall 5: STORED GENERATED gym_date computes MSK-local date.

    UTC 22:30 on 2026-05-07 = MSK 01:30 on 2026-05-08, so gym_date = 2026-05-08.
    SQLite cannot represent this — runs only against real Postgres 16.
    """
    visit = Visit(
        client_id=...,
        membership_id=...,
        channel="reception",
        checked_in_at=datetime(2026, 5, 7, 22, 30, tzinfo=UTC),
    )
    db_session.add(visit)
    await db_session.flush()
    await db_session.refresh(visit, attribute_names=["gym_date"])
    assert visit.gym_date == date(2026, 5, 8)
```

---

### `apps/backend/tests/unit/visits/*.py` (test, unit)

**Analog:** `apps/backend/tests/unit/memberships/` (existing dir per ls output above).

Pure-function unit tests: `test_anti_fraud_helpers.py` covers `_assert_within_gym_hours(now)` boundary cases; `test_schemas.py` covers `BackendSchemaBase` invariants (extra='forbid' rejects `gymDate` in `VisitCreateRequest`); `tests/unit/test_config.py` extension covers the `model_validator(mode='after')` rejecting midnight-spanning ranges. No fixtures, no DB, no `app` instance.

---

## Shared Patterns

### Authentication / Authorization (RBAC-04 ordering)
**Source:** `apps/backend/app/modules/memberships/router.py:259-275`
**Apply to:** Visits POST endpoint (the only mutation in Phase 19's surface).

```python
async def create_X(
    payload: XCreateRequest,
    actor: Annotated[
        CurrentUser,
        Depends(require_permission(Action.X, Resource.X)),  # ← BEFORE csrf
    ],
    _csrf: Annotated[None, Depends(verify_csrf)],          # ← AFTER permission
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ResponseEnvelope[XResponse]:
    ...
```
Statically enforced by `apps/backend/tests/integration/test_route_introspection.py` (Phase 6).

### Co-transactional audit emit
**Source:** `apps/backend/app/core/audit.py:119-173`
**Apply to:** Every Phase 19 service mutation function.

`audit.emit(session, event, *, actor_user_id, resource_type, resource_id, **payload)` NEVER calls `session.commit()` or `session.flush()` — the caller (service) owns the transactional moment. The AuditLog row enrolls in whatever transaction `session` is part of and commits or rolls back atomically with the caller's mutation. **Phase 19 D-05 deviation:** rejection paths emit + commit explicitly so the audit row is preserved even when the mutation raises (audit-as-anti-fraud signal per Pitfall 9).

`audit.emit` validates `(event, resource_type) ∈ LOCKED_AUDIT_EVENTS` BEFORE structlog/DB writes — raises `AuditEventNotLockedError` (`ValueError` subclass) on any non-locked pair. Phase 19's four pairs (`("visit_created", "visit")`, `("visit_rejected_no_membership", "visit")`, `("visit_rejected_duplicate", "visit")`, `("visit_rejected_outside_hours", "visit")`) are already in the frozenset (`app/core/audit.py:111-114`). The Phase 15 INFRA-11 AST literal-only walker (`tests/unit/test_audit_taxonomy.py`) catches typos at the new callsites.

### IntegrityError translation helper
**Source:** `apps/backend/app/modules/memberships/service.py:73-101` (`_is_plan_name_conflict` + `_is_plan_in_use_conflict`)
**Apply to:** Phase 19 visits service `_is_duplicate_visit_conflict(exc)` against `uq_visits_client_id_gym_date`.

Standard skeleton — check `getattr(exc.orig, 'constraint_name', None)` first (asyncpg exposes it), then substring fallback on `str(exc.orig)`. The constraint name string is the literal coupling point between the migration and the service helper.

### Cross-module Protocol resolver
**Source:** `apps/backend/app/core/dependencies.py:65-119` + `apps/backend/app/main.py:108`
**Apply to:** Phase 19 D-02 `ClientByTelegram` resolver.

Five elements: (1) `Protocol` declaring only the attributes the consumer reads; (2) typed `Callable[..., Awaitable[X | None]]` resolver alias; (3) module-level `_X_resolver: Resolver | None = None` slot; (4) `register_X_resolver(...)` setter (idempotent); (5) `resolve_X(session, ...)` async consumer that returns `None` when slot is unset.

### Repository single-point-of-access
**Source:** `apps/backend/app/modules/memberships/repository.py:1-23` (module docstring)
**Apply to:** `apps/backend/app/modules/visits/repository.py`.

Only repository imports the `Visit` ORM. Service imports `from app.modules.visits import repository` and never executes `select(Visit)` directly. Repository never calls `session.flush()` or `session.commit()` — service owns the transactional moment.

### Test SAVEPOINT fixture (default) + real-commit sibling (D-13)
**Source:** `apps/backend/tests/conftest.py:56-109` (the `db_session` fixture)
**Apply to:** All Phase 19 integration tests use the existing fixture EXCEPT `test_visits_concurrent.py` (VIS-TEST-01) which uses the new `db_session_real_commit` sibling defined in `tests/integration/visits/conftest.py`. Document the rationale in the conftest docstring (D-13: SAVEPOINT interferes with concurrent INSERT serialization against the UNIQUE index).

---

## No Analog Found

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| `app/core/config.py` `model_validator(mode='after')` for cross-field range | config | config-load | No pre-existing `mode='after'` model_validator on Settings. NET-NEW pattern; Pydantic v2 stock feature (CONTEXT canonical-refs link to docs). Planner cites Pydantic docs as the analog. |
| `apps/backend/alembic/versions/0006_visits.py` `Computed("...", persisted=True)` STORED GENERATED column | migration | DDL | No precedent in `apps/backend/alembic/versions/`. NET-NEW for project. SA 2.0 stock feature (CONTEXT canonical-refs lines 259-261). |
| `db_session_real_commit` fixture (D-13) | fixture | test infrastructure | The existing `db_session` is SAVEPOINT-only; no real-commit sibling exists. Built fresh in Phase 19; documented inline. |

---

## Key Cross-Cutting Notes for Planner

1. **Audit payload drift between `app/core/audit.py:46` docstring and CONTEXT D-16.** The docstring says `visit_created — {visit_id, client_id, membership_id, channel, gym_date}`; CONTEXT D-16 says `{client_id, membership_id, channel}` with `visit_id` in `resource_id`. The CONTEXT shape is correct (matches `membership_created` precedent at `memberships/service.py:371-380` which puts `membership_id` in `resource_id` and asserts `set(payload.keys()) == {"client_id", "plan_id", "end_date"}` at `test_memberships_audit.py:121`). The audit.py docstring should be reconciled in 19-01-PLAN.md — either update the docstring to match D-16, or extend D-16 payload to include `gym_date` (consistent with the duplicate-rejection payload). The `LOCKED_AUDIT_EVENTS` frozenset doesn't care about payload shape — only `(event, resource_type)` pairs.

2. **`app/core/database.py` Base + mixins.** Phase 19 ORM imports `Base, UUIDPkMixin, TimestampMixin` (NO `SoftDeleteMixin` per CD-04). Same pattern as `Membership` — see imports at `memberships/models.py:50`.

3. **The byte-stable `openapi.json` diff gate** (per ARCHITECTURE.md line 450 / CONTEXT line 53). Phase 19's mount of `visits_router` LAST preserves business-surface ordering (clients → plans → memberships → visits) and keeps the regen diff additive (no reorder of existing operation IDs). Run `uv run python apps/backend/scripts/export_openapi.py` after the router mounts.

4. **Pydantic v2 `time` env parsing.** No conversion code needed — `gym_hours_start: time = time(7, 0)` parses `GYM_HOURS_START="07:00"` natively. Validate at unit-test level (`tests/unit/test_config.py` extension).

5. **The `_create_visit_with_anti_fraud` private + two public wrappers (D-04) is the single most consequential structural pattern in the phase.** Reception (`create_visit_reception(session, actor, payload)`) and bot (`create_visit_self_checkin(session, telegram_user_id)`) are thin wrappers that resolve the actor and call the private. Adding a third channel (NFC turnstile, v2+) is one new public wrapper + one new `channel` enum value. Anti-fraud lives in the service, never in the handler (Pitfall 7 mandate).

---

## Metadata

**Analog search scope:**
- `apps/backend/app/core/{audit.py, config.py, dependencies.py, exceptions.py, pagination.py, schemas.py}`
- `apps/backend/app/modules/{auth,clients,memberships}/`
- `apps/backend/alembic/versions/0005_memberships.py`
- `apps/backend/app/main.py`, `apps/backend/app/api/v1/router.py`
- `apps/backend/tests/{conftest.py, integration/{memberships,clients}/, integration/test_alembic_clean.py}`

**Files scanned:** ~25 source files + 5 test files

**Pattern extraction date:** 2026-05-07
