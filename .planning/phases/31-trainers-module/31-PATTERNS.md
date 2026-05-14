# Phase 31: Trainers Module — Pattern Map

**Mapped:** 2026-05-14
**Files analyzed:** 28 (15 backend, 13 admin-web)
**Analogs found:** 27 / 28 (1 partial-new: `ActiveFilterPill` has nearest analog in badge-styled tabs, no direct equivalent)

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `apps/backend/alembic/versions/0011_trainers.py` | migration | batch | `alembic/versions/0002_clients.py` | exact (simpler) |
| `apps/backend/app/modules/trainers/__init__.py` | config | — | `app/modules/clients/__init__.py` | exact |
| `apps/backend/app/modules/trainers/models.py` | model | CRUD | `app/modules/clients/models.py` | exact (stripped) |
| `apps/backend/app/modules/trainers/schemas.py` | model | request-response | `app/modules/clients/schemas.py` | exact (stripped) |
| `apps/backend/app/modules/trainers/repository.py` | service | CRUD | `app/modules/clients/repository.py` | exact (simplified) |
| `apps/backend/app/modules/trainers/service.py` | service | CRUD | `app/modules/clients/service.py` | exact (simplified) |
| `apps/backend/app/modules/trainers/router.py` | controller | request-response | `app/modules/clients/router.py` | exact (simplified) |
| `apps/backend/app/core/dependencies.py` | middleware | request-response | `app/core/dependencies.py` lines 140–191 | exact (append slot) |
| `apps/backend/app/main.py` | config | — | `app/main.py` lines 113–133 | exact (append call) |
| `apps/backend/app/workers/telegram_bot.py` | utility | event-driven | `app/workers/telegram_bot.py` lines 56–63 | exact (append call) |
| `apps/backend/app/api/v1/router.py` | config | — | `app/api/v1/router.py` | exact (append line) |
| `apps/backend/tests/integration/test_trainers_crud.py` | test | request-response | `tests/integration/clients/test_clients_crud.py` | exact |
| `apps/backend/tests/integration/test_trainers_audit.py` | test | request-response | `tests/integration/clients/test_audit_writes.py` | exact |
| `apps/backend/tests/integration/test_trainers_rbac.py` | test | request-response | `tests/integration/clients/test_clients_rbac.py` | exact |
| `apps/backend/openapi.json` | config | — | regenerate (no analog needed) | — |
| `apps/admin-web/src/shared/api/services/mock/trainers.ts` | service | CRUD | `mock/clients.ts` | exact |
| `apps/admin-web/src/shared/api/services/mock/index.ts` | config | — | `mock/index.ts` | exact (append export) |
| `apps/admin-web/src/features/trainers/model/schema.ts` | model | transform | `features/memberships/model/schema.ts` | role-match |
| `apps/admin-web/src/features/trainers/api/keys.ts` | utility | request-response | `features/memberships/api/keys.ts` | exact |
| `apps/admin-web/src/features/trainers/api/hooks.ts` | utility | request-response | `features/memberships/api/hooks.ts` | exact |
| `apps/admin-web/src/features/trainers/components/TrainersTable.tsx` | component | request-response | `features/memberships/components/MembershipPlansPage.tsx` | role-match |
| `apps/admin-web/src/features/trainers/components/TrainerFormDialog.tsx` | component | request-response | `features/memberships/components/MembershipPlanFormDialog.tsx` | exact |
| `apps/admin-web/src/features/trainers/components/DeleteTrainerAlertDialog.tsx` | component | request-response | `features/memberships/components/CancelMembershipDialog.tsx` | role-match |
| `apps/admin-web/src/features/trainers/components/ActiveFilterPill.tsx` | component | request-response | `features/memberships/components/MembershipsListPage.tsx` (status pill) | partial-match |
| `apps/admin-web/src/features/trainers/components/TrainerStatusBadge.tsx` | component | transform | `features/memberships/components/StatusBadge.tsx` | exact |
| `apps/admin-web/src/routes/_protected/trainers.tsx` | route | request-response | `routes/_protected/membership-plans.tsx` | exact |
| `apps/admin-web/src/shared/i18n/ru.ts` | config | — | `shared/i18n/ru.ts` | exact (append block) |
| `apps/admin-web/src/features/trainers/__tests__/*.test.tsx` | test | request-response | `features/memberships/api/hooks.test.ts` | role-match |

---

## Pattern Assignments

### `apps/backend/alembic/versions/0011_trainers.py` (migration, batch)

**Analog:** `apps/backend/alembic/versions/0002_clients.py`

**Header pattern** (lines 1–35):
```python
"""trainers

Revision ID: 0011_trainers
Revises: 0010_notifications
Create Date: 2026-05-14 ...

Phase 31 TRN-01 — trainers table.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy import text

from alembic import op

revision: str = "0011_trainers"
down_revision: str | None = "0010_notifications"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None
```

**Core table pattern** (analog lines 42–116 from 0002_clients.py — stripped to trainers shape):
```python
def upgrade() -> None:
    op.create_table(
        "trainers",
        sa.Column("full_name", sa.Text(), nullable=False),
        sa.Column("phone", sa.Text(), nullable=True),
        sa.Column(
            "is_active",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
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
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_trainers")),
    )
    # D-31-03: partial unique on phone WHERE deleted_at IS NULL AND phone IS NOT NULL
    op.create_index(
        "uq_trainers_phone_alive",
        "trainers",
        ["phone"],
        unique=True,
        postgresql_where=text("deleted_at IS NULL AND phone IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_trainers_phone_alive", table_name="trainers")
    op.drop_table("trainers")
```

**Key differences from clients migration:**
- No `pg_trgm` extension (no text search needed)
- No FK columns (`created_by_user_id` omitted per D-31-01)
- `phone` is nullable (`nullable=True`)
- Extra partial UNIQUE predicate: `AND phone IS NOT NULL` (phone is nullable)
- No GIN trigram indexes, no JSONB columns, no `ARRAY` columns

---

### `apps/backend/app/modules/trainers/models.py` (model, CRUD)

**Analog:** `apps/backend/app/modules/clients/models.py`

**Imports + class pattern** (analog lines 27–111 — stripped):
```python
"""Trainer ORM (Phase 31 TRN-01, D-31-01/D-31-02/D-31-03).

Composes three base/mixin classes:
    Base + UUIDPkMixin + TimestampMixin + SoftDeleteMixin

NO created_by_user_id FK — trainers are owner-only reference data
without creator-attribution requirement (D-31-01).

Schema invariants:
- Partial unique index `uq_trainers_phone_alive WHERE deleted_at IS NULL AND
  phone IS NOT NULL` (D-31-03) — lives in __table_args__ + migration.
- `is_active BOOLEAN NOT NULL DEFAULT TRUE` — deactivation via PATCH (TRN-03).
- `deleted_at` column present (SoftDeleteMixin) but only for partial UNIQUE
  support; hard-delete is the actual delete operation (D-31-06).
"""

from sqlalchemy import Boolean, Index, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import text

from app.core.database import Base, SoftDeleteMixin, TimestampMixin, UUIDPkMixin


class Trainer(Base, UUIDPkMixin, TimestampMixin, SoftDeleteMixin):
    """Gym trainer / personal training staff (TRN-01)."""

    __tablename__ = "trainers"

    full_name: Mapped[str] = mapped_column(Text, nullable=False)
    phone: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("true"),
    )

    __table_args__ = (
        Index(
            "uq_trainers_phone_alive",
            "phone",
            unique=True,
            postgresql_where=text("deleted_at IS NULL AND phone IS NOT NULL"),
        ),
    )
```

---

### `apps/backend/app/modules/trainers/schemas.py` (model, request-response)

**Analog:** `apps/backend/app/modules/clients/schemas.py`

**PHONE_REGEX reuse pattern** (analog line 42):
```python
PHONE_REGEX = r"^\+[1-9]\d{1,14}$"  # E.164 (D-10 reuse per D-31-05)
```

**BackendSchemaBase chain pattern** (analog lines 105–224):
```python
from app.core.pagination import PageQuery
from app.core.schemas import BackendSchemaBase, ResponseData


class TrainerCreateRequest(BackendSchemaBase):
    """POST /api/v1/trainers body. Required: fullName. Phone optional."""
    full_name: str = Field(min_length=1, max_length=200)
    phone: str | None = Field(default=None, pattern=PHONE_REGEX)


class TrainerUpdateRequest(BackendSchemaBase):
    """PATCH /api/v1/trainers/{id} body.

    PATCH semantics: omit key to leave unchanged (D-01).
    is_active accepted on PATCH for deactivate/reactivate (D-31-11).
    """
    full_name: str | None = Field(default=None, min_length=1, max_length=200)
    phone: str | None = Field(default=None, pattern=PHONE_REGEX)
    is_active: bool | None = None


class TrainerResponse(ResponseData):
    """Single trainer read DTO. from_attributes=True inherited via ContractModel."""
    id: UUID
    full_name: str
    phone: str | None = None
    is_active: bool
    created_at: datetime
    updated_at: datetime


class TrainerListQuery(PageQuery):
    """GET /api/v1/trainers query params.

    active=true → WHERE is_active = true AND deleted_at IS NULL
    active=false → WHERE is_active = false AND deleted_at IS NULL
    omit → both (D-31-09)
    """
    active: bool | None = None
```

**Key differences from clients schemas:**
- No `ClientSort` enum (trainers list is simpler — just `created_at DESC`)
- No `EmergencyContact`, no `Gender`, no `TAG_REGEX`, no `@field_validator` on tags
- `is_active: bool | None` on UpdateRequest (for deactivate/reactivate toggle)
- No `_reject_explicit_null` model_validator (trainers PATCH is simpler — explicit null for phone is acceptable as "clear phone")

---

### `apps/backend/app/modules/trainers/repository.py` (service, CRUD)

**Analog:** `apps/backend/app/modules/clients/repository.py`

**Module docstring pattern** (analog lines 1–24):
```python
"""Trainers repository — single point of access to the `Trainer` ORM (TRN-01, D-31-08).

This is the ONLY module that imports the `Trainer` ORM model. Service layer
calls these module-level async helpers and never executes `select(Trainer)` directly.

Soft-delete invariant: every read helper appends `Trainer.deleted_at IS NULL` as the
first predicate. `hard_delete_trainer` is the only deletion point (D-31-06).

Transaction control (D-03): NO session.commit() and NO session.flush() here.
Caller (service.py) owns the transactional moment for co-writing the audit log.

`from __future__ import annotations` required: PaginatedData[Trainer] annotation
at runtime would trigger PydanticSchemaGenerationError (same pitfall as clients).
"""

from __future__ import annotations
```

**get_alive pattern** (analog lines 47–54):
```python
async def get_alive(session: AsyncSession, trainer_id: UUID) -> Trainer | None:
    """Return alive (not soft-deleted) trainer by id, or None."""
    stmt = select(Trainer).where(
        Trainer.id == trainer_id,
        Trainer.deleted_at.is_(None),
    )
    return await session.scalar(stmt)
```

**list_alive pattern** (analog lines 57–139 — simplified):
```python
async def list_alive(
    session: AsyncSession, query: TrainerListQuery
) -> PaginatedData[Trainer]:
    predicates: list[Any] = [Trainer.deleted_at.is_(None)]

    if query.active is not None:
        predicates.append(Trainer.is_active == query.active)

    total_stmt = select(func.count()).select_from(Trainer).where(and_(*predicates))
    total = await session.scalar(total_stmt) or 0

    stmt = select(Trainer).where(and_(*predicates))
    stmt = stmt.order_by(Trainer.created_at.desc(), Trainer.id.desc())

    offset = (query.page - 1) * query.page_size
    stmt = stmt.offset(offset).limit(query.page_size)
    rows = (await session.scalars(stmt)).all()

    return PaginatedData.model_construct(
        items=list(rows),
        total=total,
        page=query.page,
        page_size=query.page_size,
    )
```

**insert pattern** (analog lines 142–165):
```python
async def insert_trainer(
    session: AsyncSession,
    data: TrainerCreateRequest,
) -> Trainer:
    """Insert new trainer; caller owns flush + audit emit (D-03)."""
    trainer = Trainer(
        full_name=data.full_name,
        phone=data.phone,
        is_active=True,  # always active on create (D-31-02)
    )
    session.add(trainer)
    return trainer
```

**update pattern** (analog lines 168–197):
```python
async def update_trainer(
    session: AsyncSession,
    trainer: Trainer,
    data: TrainerUpdateRequest,
) -> dict[str, object]:
    """Apply PATCH to existing alive Trainer. Returns {field_name: previous_value}."""
    updates = data.model_dump(exclude_unset=True)
    changed: dict[str, object] = {}
    for key, value in updates.items():
        previous = getattr(trainer, key)
        if previous != value:
            changed[key] = previous
            setattr(trainer, key, value)
    return changed
```

**hard_delete pattern** (unique to trainers — replaces soft_delete_client):
```python
async def hard_delete_trainer(session: AsyncSession, trainer: Trainer) -> None:
    """Hard-delete the trainer row. FK constraint from pt_sessions raises
    IntegrityError (pgcode 23503) if trainer_in_use — caller maps to 409."""
    await session.delete(trainer)
```

---

### `apps/backend/app/modules/trainers/service.py` (service, CRUD)

**Analog:** `apps/backend/app/modules/clients/service.py`

**Imports pattern** (analog lines 44–61):
```python
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import audit
from app.core.dependencies import CurrentUser
from app.core.exceptions import TrainerNotFoundError, PhoneExistsError, TrainerInUseError
from app.core.pagination import PaginatedData
from app.modules.trainers import repository
from app.modules.trainers.models import Trainer
from app.modules.trainers.schemas import (
    TrainerCreateRequest,
    TrainerListQuery,
    TrainerResponse,
    TrainerUpdateRequest,
)
```

**Phone conflict helper** (analog lines 101–106):
```python
def _is_phone_conflict(exc: IntegrityError) -> bool:
    """Return True iff exc was caused by uq_trainers_phone_alive (D-31-03)."""
    constraint = getattr(exc.orig, "constraint_name", None) or ""
    if constraint == "uq_trainers_phone_alive":
        return True
    return "uq_trainers_phone_alive" in str(exc.orig)


def _is_fk_violation(exc: IntegrityError) -> bool:
    """Return True iff exc was caused by a FK reference (pgcode 23503).
    Used to detect trainer_in_use when pt_sessions FK exists (D-31-07)."""
    orig = exc.orig
    pgcode = getattr(orig, "pgcode", None) or ""
    return pgcode == "23503"
```

**create pattern** (analog lines 109–144):
```python
async def create_trainer(
    session: AsyncSession,
    actor: CurrentUser,
    data: TrainerCreateRequest,
) -> TrainerResponse:
    trainer = await repository.insert_trainer(session, data)
    try:
        await session.flush()
    except IntegrityError as exc:
        await session.rollback()
        if _is_phone_conflict(exc):
            raise PhoneExistsError("phone_exists") from exc
        raise

    await audit.emit(
        session,
        "trainer_created",
        actor_user_id=actor.id,
        resource_type="trainer",
        resource_id=trainer.id,
        trainer_id=trainer.id,
        full_name=trainer.full_name,
    )
    await session.commit()
    return TrainerResponse.model_validate(trainer)
```

**update pattern with deactivate/reactivate detection** (analog lines 147–202 + D-31-12):
```python
async def update_trainer(
    session: AsyncSession,
    actor: CurrentUser,
    trainer_id: UUID,
    data: TrainerUpdateRequest,
) -> TrainerResponse:
    trainer = await repository.get_alive(session, trainer_id)
    if trainer is None:
        raise TrainerNotFoundError("trainer_not_found")

    prev_is_active = trainer.is_active
    changed_previous = await repository.update_trainer(session, trainer, data)

    if not changed_previous:
        return TrainerResponse.model_validate(trainer)

    try:
        await session.flush()
    except IntegrityError as exc:
        await session.rollback()
        if _is_phone_conflict(exc):
            raise PhoneExistsError("phone_exists") from exc
        raise

    # D-31-12: detect is_active state flip and emit state-flip event;
    # emit trainer_updated for other field changes separately (2 events if both).
    is_active_changed = "is_active" in changed_previous
    other_changed = {k: v for k, v in changed_previous.items() if k != "is_active"}

    if is_active_changed:
        if prev_is_active and not trainer.is_active:
            await audit.emit(
                session, "trainer_deactivated",
                actor_user_id=actor.id, resource_type="trainer",
                resource_id=trainer.id, trainer_id=trainer.id,
            )
        else:
            await audit.emit(
                session, "trainer_reactivated",
                actor_user_id=actor.id, resource_type="trainer",
                resource_id=trainer.id, trainer_id=trainer.id,
            )

    if other_changed:
        await audit.emit(
            session, "trainer_updated",
            actor_user_id=actor.id, resource_type="trainer",
            resource_id=trainer.id, trainer_id=trainer.id,
            changed_fields=sorted(other_changed.keys()),
        )

    await session.refresh(trainer, attribute_names=["updated_at"])
    await session.commit()
    return TrainerResponse.model_validate(trainer)
```

**hard delete pattern** (replaces soft_delete_client; D-31-06/D-31-07):
```python
async def delete_trainer(
    session: AsyncSession,
    actor: CurrentUser,
    trainer_id: UUID,
) -> None:
    trainer = await repository.get_alive(session, trainer_id)
    if trainer is None:
        raise TrainerNotFoundError("trainer_not_found")

    try:
        await repository.hard_delete_trainer(session, trainer)
        await session.flush()
    except IntegrityError as exc:
        await session.rollback()
        if _is_fk_violation(exc):
            raise TrainerInUseError("trainer_in_use") from exc
        raise

    await session.commit()
```

**Protocol slot function** (D-31-15):
```python
async def resolve_trainer_by_id(
    session: AsyncSession,
    trainer_id: UUID,
) -> Trainer | None:
    """Protocol slot consumer for Phase 34 PT-session validator.
    Returns alive Trainer regardless of is_active (caller decides).
    Returns None if missing or soft-deleted."""
    return await repository.get_alive(session, trainer_id)
```

**SVC001 note:** Every mutation function (`create_trainer`, `update_trainer`, `delete_trainer`) MUST call `await session.commit()` at the end. SVC001 AST walker already includes `trainers/service.py` in scope (Plan 30-03).

---

### `apps/backend/app/modules/trainers/router.py` (controller, request-response)

**Analog:** `apps/backend/app/modules/clients/router.py`

**RBAC-04 ordering invariant** — `require_permission` BEFORE `verify_csrf` in every mutation (analog lines 91–143):
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
from app.modules.trainers import service
from app.modules.trainers.schemas import (
    TrainerCreateRequest,
    TrainerListQuery,
    TrainerResponse,
    TrainerUpdateRequest,
)

router = APIRouter()

# GET — VIEW, no CSRF (both owner + reception per D-31-09)
@router.get("", response_model=ResponseEnvelope[PaginatedData[TrainerResponse]])
async def list_trainers(
    query: Annotated[TrainerListQuery, Depends()],
    _actor: Annotated[CurrentUser, Depends(require_permission(Action.VIEW, Resource.TRAINERS))],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ResponseEnvelope[PaginatedData[TrainerResponse]]: ...

@router.get("/{trainer_id}", response_model=ResponseEnvelope[TrainerResponse])
async def get_trainer(
    trainer_id: UUID,
    _actor: Annotated[CurrentUser, Depends(require_permission(Action.VIEW, Resource.TRAINERS))],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ResponseEnvelope[TrainerResponse]: ...

# POST — EDIT + CSRF (RBAC-04: permission BEFORE csrf)
@router.post("", response_model=ResponseEnvelope[TrainerResponse], status_code=status.HTTP_201_CREATED)
async def create_trainer(
    payload: TrainerCreateRequest,
    actor: Annotated[CurrentUser, Depends(require_permission(Action.CREATE, Resource.TRAINERS))],
    _csrf: Annotated[None, Depends(verify_csrf)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ResponseEnvelope[TrainerResponse]: ...

# PATCH — EDIT + CSRF (handles deactivate/reactivate per D-31-11)
@router.patch("/{trainer_id}", response_model=ResponseEnvelope[TrainerResponse])
async def update_trainer(
    trainer_id: UUID,
    payload: TrainerUpdateRequest,
    actor: Annotated[CurrentUser, Depends(require_permission(Action.EDIT, Resource.TRAINERS))],
    _csrf: Annotated[None, Depends(verify_csrf)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ResponseEnvelope[TrainerResponse]: ...

# DELETE — owner-only + CSRF; returns 204
@router.delete("/{trainer_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_trainer(
    trainer_id: UUID,
    actor: Annotated[CurrentUser, Depends(require_permission(Action.DELETE, Resource.TRAINERS))],
    _csrf: Annotated[None, Depends(verify_csrf)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> None: ...
```

---

### `apps/backend/app/core/dependencies.py` — MODIFY (middleware, request-response)

**Analog:** `apps/backend/app/core/dependencies.py` lines 122–191 (ClientByTelegram slot — the 3rd slot)

**Copy the exact slot pattern for the 4th slot** — append after line 191:
```python
# ─────────────────────────────────────────────────────────────────────────────
# Phase 31 D-31-13/D-31-14 — TrainerById resolver slot.
#
# Fourth composition-root carve-out after register_user_loader (Phase 5),
# register_active_membership_resolver (Phase 17), and
# register_client_by_telegram_resolver (Phase 19). Phase 34's pt_sessions
# service needs to validate trainer existence + is_active status without
# crossing the modules-independent importlinter contract.
# ─────────────────────────────────────────────────────────────────────────────


class TrainerById(Protocol):
    """Structural type for alive Trainer lookup result (Phase 31 D-31-13).
    Phase 34 pt_sessions service checks id + is_active."""
    id: UUID
    is_active: bool


TrainerByIdResolver = Callable[[AsyncSession, UUID], Awaitable[TrainerById | None]]

_trainer_by_id_resolver: TrainerByIdResolver | None = None


def register_trainer_by_id_resolver(resolver: TrainerByIdResolver) -> None:
    """Composition-root setter — called by app.main.create_app() AND
    app.workers.telegram_bot.main() (defensive double-wiring per REG-29-03)."""
    global _trainer_by_id_resolver
    _trainer_by_id_resolver = resolver


async def resolve_trainer_by_id(session: AsyncSession, trainer_id: UUID) -> TrainerById | None:
    """Consumer entry point — Phase 34 pt_sessions service will call this."""
    if _trainer_by_id_resolver is None:
        return None
    return await _trainer_by_id_resolver(session, trainer_id)
```

---

### `apps/backend/app/main.py` — MODIFY (config, —)

**Analog:** `apps/backend/app/main.py` lines 113–133

**Append 4th registration** (after the existing `register_client_by_telegram_resolver` call, before `app.include_router(api)`):
```python
# Phase 31 D-31-14: fourth composition-root carve-out — pt_sessions service
# (Phase 34) will validate trainer existence via this Protocol slot.
# Defensive: bot worker also registers (see telegram_bot.py). Idempotent.
from app.modules.trainers import (
    service as trainers_service,
)

register_trainer_by_id_resolver(trainers_service.resolve_trainer_by_id)
```

Also add `register_trainer_by_id_resolver` to the top-level imports from `app.core.dependencies`.

---

### `apps/backend/app/workers/telegram_bot.py` — MODIFY (utility, event-driven)

**Analog:** `apps/backend/app/workers/telegram_bot.py` lines 27–63

**Append 3rd registration** (REG-29-03 defensive double-wiring — after the existing two `register_*` calls in `main()`):
```python
# Phase 31 D-31-14: defensive double-wiring for trainer resolver.
# Bot is not a consumer in v1.4 but must register to match API process exactly
# (per REG-29-03 lesson from Phase 29 verification).
from app.modules.trainers import service as trainers_service  # add to imports

register_trainer_by_id_resolver(trainers_service.resolve_trainer_by_id)
```

Also add `register_trainer_by_id_resolver` to the `from app.core.dependencies import ...` block.

---

### `apps/backend/app/api/v1/router.py` — MODIFY (config, —)

**Analog:** `apps/backend/app/api/v1/router.py` (full file — append one line)

**Append trainers router** (alphabetically after clients, before memberships):
```python
from app.modules.trainers.router import router as trainers_router

v1.include_router(trainers_router, prefix="/trainers", tags=["trainers"])
```

---

### `apps/backend/tests/integration/test_trainers_crud.py` (test, request-response)

**Analog:** `apps/backend/tests/integration/clients/test_clients_crud.py` + `clients/conftest.py`

**Conftest pattern** (analog `clients/conftest.py` lines 1–161):
- Place conftest.py in `tests/integration/trainers/conftest.py`
- Mirror `_seed_user`, `_login`, `authed_client_owner`, `authed_client_reception` fixtures
- Use trainer-specific email constants: `TRAINER_OWNER_EMAIL = "trainers-owner@example.com"`
- `ASGITransport` + `AsyncClient` with real `/api/v1/auth/login` cookie flow

**CSRF helper + VALID_TRAINER constant pattern**:
```python
def _csrf_headers(client: AsyncClient) -> dict[str, str]:
    return {"X-CSRF-Token": client.cookies.get("sportzal_csrf", "")}

VALID_TRAINER: dict[str, Any] = {
    "fullName": "Иванов Иван",
    "phone": "+79991234567",
}
```

**Core test pattern** (analog `test_clients_crud.py` lines 53–200):
```python
async def test_create_happy_returns_201_envelope(authed_client_owner: AsyncClient) -> None:
    r = await authed_client_owner.post(
        "/api/v1/trainers",
        json=VALID_TRAINER,
        headers=_csrf_headers(authed_client_owner),
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert "data" in body
    data = body["data"]
    assert data["fullName"] == "Иванов Иван"
    UUID(data["id"])
    assert data["isActive"] is True  # new trainers always active
```

**409 phone_exists test** (analog `test_create_duplicate_phone_alive_returns_409_phone_exists`):
```python
async def test_create_duplicate_phone_returns_409_phone_exists(
    authed_client_owner: AsyncClient,
) -> None:
    await authed_client_owner.post("/api/v1/trainers", json=VALID_TRAINER,
                                    headers=_csrf_headers(authed_client_owner))
    r = await authed_client_owner.post("/api/v1/trainers", json=VALID_TRAINER,
                                        headers=_csrf_headers(authed_client_owner))
    assert r.status_code == 409
    assert r.json()["code"] == "phone_exists"
```

**409 trainer_in_use via monkeypatched IntegrityError** (Claude's Discretion option c — D-31-07):
```python
async def test_delete_returns_409_when_fk_violation(
    authed_client_owner: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Pre-emptive FK 409 mapping test — synthetic via monkeypatched IntegrityError.
    Phase 34 will add a real pt_sessions FK; this exercises the mapping logic now."""
    from sqlalchemy.exc import IntegrityError as SAIntegrityError

    class FakePGError:
        pgcode = "23503"

    created = await _create(authed_client_owner, phone="+79990009999")

    import app.modules.trainers.repository as repo
    original = repo.hard_delete_trainer

    async def _fake_delete(session: Any, trainer: Any) -> None:
        raise SAIntegrityError("mocked", {}, FakePGError())

    monkeypatch.setattr(repo, "hard_delete_trainer", _fake_delete)

    r = await authed_client_owner.delete(
        f"/api/v1/trainers/{created['id']}",
        headers=_csrf_headers(authed_client_owner),
    )
    assert r.status_code == 409
    assert r.json()["code"] == "trainer_in_use"
```

**PATCH deactivate/reactivate tests**:
```python
async def test_patch_deactivate_returns_200_is_active_false(
    authed_client_owner: AsyncClient,
) -> None:
    created = await _create(authed_client_owner, phone="+79990001111")
    r = await authed_client_owner.patch(
        f"/api/v1/trainers/{created['id']}",
        json={"isActive": False},
        headers=_csrf_headers(authed_client_owner),
    )
    assert r.status_code == 200
    assert r.json()["data"]["isActive"] is False
```

---

### `apps/backend/tests/integration/test_trainers_audit.py` (test, request-response)

**Analog:** `apps/backend/tests/integration/clients/test_audit_writes.py`

**Core audit test pattern** (analog lines 48–100):
```python
async def test_trainer_created_writes_audit_row(
    authed_client_owner: AsyncClient,
    db_session: AsyncSession,
    seeded_owner: User,
) -> None:
    created = await _create(authed_client_owner, phone="+79990002001")
    trainer_id = UUID(created["id"])

    rows = (
        await db_session.scalars(
            select(AuditLog).where(
                AuditLog.action == "trainer_created",
                AuditLog.resource_id == trainer_id,
            )
        )
    ).all()
    assert len(rows) == 1
    row = rows[0]
    assert row.actor_user_id == seeded_owner.id
    assert row.resource_type == "trainer"
    assert row.payload["trainer_id"] == str(trainer_id)
    assert "full_name" in row.payload


async def test_trainer_deactivated_writes_audit_row(
    authed_client_owner: AsyncClient,
    db_session: AsyncSession,
) -> None:
    created = await _create(authed_client_owner, phone="+79990002002")
    await authed_client_owner.patch(
        f"/api/v1/trainers/{created['id']}",
        json={"isActive": False},
        headers=_csrf_headers(authed_client_owner),
    )
    rows = (
        await db_session.scalars(
            select(AuditLog).where(
                AuditLog.action == "trainer_deactivated",
                AuditLog.resource_id == UUID(created["id"]),
            )
        )
    ).all()
    assert len(rows) == 1
```

---

### `apps/backend/tests/integration/test_trainers_rbac.py` (test, request-response)

**Analog:** `apps/backend/tests/integration/clients/test_clients_rbac.py`

**Core RBAC test pattern** (analog lines 42–75):
```python
async def test_create_reception_returns_403_forbidden(
    authed_client_reception: AsyncClient,
) -> None:
    """(CREATE, TRAINERS) is in OWNER_ONLY → reception 403."""
    r = await authed_client_reception.post(
        "/api/v1/trainers",
        json=VALID_TRAINER,
        headers=_csrf_headers(authed_client_reception),
    )
    assert r.status_code == 403

async def test_list_reception_active_returns_200(
    authed_client_owner: AsyncClient,
    authed_client_reception: AsyncClient,
) -> None:
    """(VIEW, TRAINERS) NOT in OWNER_ONLY → reception can list active trainers."""
    r = await authed_client_reception.get("/api/v1/trainers?active=true")
    assert r.status_code == 200

async def test_delete_unauthed_returns_401_not_403(
    async_client: AsyncClient,
) -> None:
    """RBAC-04: 401 fires before 403 — unauthenticated DELETE returns 401."""
    r = await async_client.delete(
        "/api/v1/trainers/00000000-0000-0000-0000-000000000001",
        headers={"X-CSRF-Token": "fake"},
    )
    assert r.status_code == 401
```

---

### `apps/admin-web/src/shared/api/services/mock/trainers.ts` (service, CRUD)

**Analog:** `apps/admin-web/src/shared/api/services/mock/clients.ts`

**Full file structure pattern** (analog lines 1–141):
```typescript
import { faker } from '@faker-js/faker'
import type { Trainer, TrainerId } from '@/entities/trainer'
import { DomainError } from '@/shared/api/errors'
import { can } from '@/shared/session/can'
import { useSessionStore } from '@/shared/session/store'
import { createTrainerSchema, updateTrainerSchema } from '@/features/trainers/model/schema'
import { loadDB, saveDB } from './_db'
import { delay } from './_latency'

function role() {
  return useSessionStore.getState().role
}

function ensure(action: 'view' | 'create' | 'edit' | 'delete', resource: 'trainers') {
  if (!can(role(), action, resource)) {
    throw new DomainError('forbidden', 'Доступ запрещён')
  }
}
```

**Lazy seed pattern** (D-31-23 — seed 8 trainers on first `list()` call):
```typescript
function seedTrainers(): Trainer[] {
  // 8 trainers: 5 active, 3 inactive; 50% have phone
  const trainers: Trainer[] = []
  for (let i = 0; i < 8; i++) {
    const isActive = i < 5
    const hasPhone = i % 2 === 0
    trainers.push({
      id: faker.string.uuid() as TrainerId,
      fullName: faker.person.fullName(),
      phone: hasPhone ? `+7${faker.string.numeric(10)}` : null,
      isActive,
      createdAt: faker.date.recent({ days: 180 }).toISOString(),
      updatedAt: faker.date.recent({ days: 30 }).toISOString(),
    })
  }
  return trainers
}
```

**list method pattern** (analog lines 37–50 — with active filter):
```typescript
async list(query: { active?: boolean; page: number; pageSize: number }) {
  await delay()
  ensure('view', 'trainers')
  const db = loadDB()
  if (!db.trainers) {
    db.trainers = seedTrainers()
    saveDB(db)
  }
  const filtered = query.active !== undefined
    ? db.trainers.filter((t) => t.isActive === query.active)
    : db.trainers
  const sorted = [...filtered].sort((a, b) => b.createdAt.localeCompare(a.createdAt))
  const total = sorted.length
  const start = (query.page - 1) * query.pageSize
  const items = sorted.slice(start, start + query.pageSize)
  return { items, total, page: query.page, pageSize: query.pageSize }
}
```

**create method pattern with phone uniqueness** (analog lines 61–91):
```typescript
async create(input: unknown) {
  await delay()
  ensure('create', 'trainers')
  const parsed = createTrainerSchema.safeParse(input)
  if (!parsed.success) { /* ... throw DomainError validation_failed */ }
  const db = loadDB()
  if (!db.trainers) { db.trainers = seedTrainers(); saveDB(db) }
  if (parsed.data.phone && db.trainers.some((t) => t.phone === parsed.data.phone)) {
    throw new DomainError('validation_failed', 'Дубликат телефона', {
      phone: ['Тренер с таким телефоном уже существует'],
    })
  }
  const newTrainer: Trainer = {
    id: faker.string.uuid() as TrainerId,
    fullName: parsed.data.fullName,
    phone: parsed.data.phone ?? null,
    isActive: true,
    createdAt: new Date().toISOString(),
    updatedAt: new Date().toISOString(),
  }
  db.trainers = [newTrainer, ...db.trainers]
  saveDB(db)
  return newTrainer
}
```

**Note:** `_db.ts` needs `trainers: Trainer[]` added to the `DB` interface and `loadDB`/`saveDB` will carry it. No localStorage key version bump needed (within-version migration, D-31-23).

---

### `apps/admin-web/src/shared/api/services/mock/index.ts` — MODIFY (config, —)

**Current file** (lines 1–15):
```typescript
import { auth } from './auth'
import { clients } from './clients'
import { memberships } from './memberships'
import { visits } from './visits'

export const services = { auth, clients, memberships, visits } as const
```

**After modification** — add trainers import + export:
```typescript
import { trainers } from './trainers'

export const services = { auth, clients, memberships, visits, trainers } as const
```

---

### `apps/admin-web/src/features/trainers/model/schema.ts` (model, transform)

**Analog:** `apps/admin-web/src/features/memberships/model/schema.ts` (re-exports from entities)

**Note from UI-SPEC.md:** Schema lives directly in `features/trainers/model/schema.ts` (not re-exported from entities — trainers is simpler and no cross-feature entity needed).

```typescript
import { z } from 'zod'

// E.164 regex — matches backend PHONE_REGEX (D-31-05 reuse)
const PHONE_REGEX = /^\+[1-9]\d{1,14}$/

export const createTrainerSchema = z.object({
  fullName: z.string().min(1, 'Укажите ФИО').max(200),
  phone: z.string().regex(PHONE_REGEX, 'Введите телефон в формате +7XXXXXXXXXX')
    .nullable()
    .optional(),
})

export const updateTrainerSchema = createTrainerSchema.extend({
  isActive: z.boolean(),
})

export type CreateTrainerInput = z.infer<typeof createTrainerSchema>
export type UpdateTrainerInput = z.infer<typeof updateTrainerSchema>
```

---

### `apps/admin-web/src/features/trainers/api/keys.ts` (utility, request-response)

**Analog:** `apps/admin-web/src/features/memberships/api/keys.ts`

Per UI-SPEC.md contract:
```typescript
export const trainersKeys = {
  all: ['trainers'] as const,
  list: (q: { active?: string; page: number; pageSize: number }) =>
    ['trainers', 'list', q] as const,
  detail: (id: string) => ['trainers', 'detail', id] as const,
} as const
```

---

### `apps/admin-web/src/features/trainers/api/hooks.ts` (utility, request-response)

**Analog:** `apps/admin-web/src/features/memberships/api/hooks.ts` lines 1–80

**Imports pattern** (analog lines 1–15):
```typescript
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { trainersKeys } from './keys'
import { services } from '@/shared/api/services'
import { isDomainError } from '@/shared/api/errors'
import { t } from '@/shared/i18n'
import type { CreateTrainerInput, UpdateTrainerInput } from '../model/schema'
```

**useQuery hook pattern** (analog lines 25–51):
```typescript
export function useTrainersList(search: { active?: string; page: number; pageSize: number }) {
  return useQuery({
    queryKey: trainersKeys.list(search),
    queryFn: () => services.trainers.list({
      active: search.active === 'true' ? true : search.active === 'false' ? false : undefined,
      page: search.page,
      pageSize: search.pageSize,
    }),
    staleTime: 30_000,
  })
}
```

**useMutation pattern** (analog lines 62–80):
```typescript
export function useCreateTrainer() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (input: CreateTrainerInput) => services.trainers.create(input),
    onSettled: () => {
      void qc.invalidateQueries({ queryKey: trainersKeys.all })
    },
  })
}

export function useDeleteTrainer() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => services.trainers.delete(id),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: trainersKeys.all })
    },
    // Note: do NOT invalidate on error — 409 trainer_in_use stays visible in AlertDialog
  })
}
```

---

### `apps/admin-web/src/features/trainers/components/TrainersTable.tsx` (component, request-response)

**Analog:** `apps/admin-web/src/features/memberships/components/MembershipPlansPage.tsx` (column definitions section, lines 50–96)

**Column definitions pattern** (analog lines 50–96 — adapted for trainers):
```typescript
const columns: ColumnDef<Trainer>[] = [
  { accessorKey: 'fullName', header: t('trainers.columns.fullName') },
  {
    accessorKey: 'phone',
    header: t('trainers.columns.phone'),
    cell: ({ row }) => row.original.phone ?? '—',
  },
  {
    id: 'isActive',
    header: t('trainers.columns.status'),
    cell: ({ row }) => <TrainerStatusBadge isActive={row.original.isActive} />,
  },
  {
    id: 'actions',
    header: '',
    cell: ({ row }) => {
      const t = row.original
      return (
        <div className="flex justify-end gap-1">
          <Button variant="ghost" size="sm" onClick={() => onEdit(t)}>
            <Pencil className="h-4 w-4" />
          </Button>
          <Button variant="ghost" size="sm" className="text-destructive" onClick={() => onDelete(t)}>
            <Trash2 className="h-4 w-4" />
          </Button>
        </div>
      )
    },
  },
]
```

**DataGrid usage pattern** (analog lines 98–124):
```typescript
const table = useReactTable({
  data: data?.items ?? [],
  columns,
  getCoreRowModel: getCoreRowModel(),
  manualPagination: true,
  pageCount: data ? Math.ceil(data.total / data.pageSize) : 0,
  state: { pagination: { pageIndex: data ? data.page - 1 : 0, pageSize: data?.pageSize ?? search.pageSize } },
  onPaginationChange: (updater) => { /* navigate with search params */ },
})
// Render:
<DataGrid table={table} recordCount={data.total} tableLayout={{ headerSticky: true }}>
  <DataGridContainer><DataGridTable /></DataGridContainer>
  <DataGridPagination sizes={[20, 50, 100]} />
</DataGrid>
```

---

### `apps/admin-web/src/features/trainers/components/TrainerFormDialog.tsx` (component, request-response)

**Analog:** `apps/admin-web/src/features/memberships/components/MembershipPlanFormDialog.tsx`

**Full Dialog + RHF + zodResolver pattern** (analog lines 1–223):
```typescript
import { useEffect } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { toast } from 'sonner'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from '@/shared/ui/dialog'
import { Button } from '@/shared/ui/button'
import { Label } from '@/shared/ui/label'
import { Input } from '@/shared/ui/input'
import { Alert, AlertDescription } from '@/shared/ui/alert'
import { t } from '@/shared/i18n'
import { isDomainError } from '@/shared/api/errors'
import { createTrainerSchema, updateTrainerSchema, type CreateTrainerInput, type UpdateTrainerInput } from '../model/schema'
import { useCreateTrainer, useUpdateTrainer } from '../api/hooks'

interface Props {
  open: boolean
  onClose: () => void
  trainer?: Trainer  // if provided → edit mode
}

export function TrainerFormDialog({ open, onClose, trainer }: Props) {
  const isEdit = !!trainer
  // ...
  const form = useForm<CreateTrainerInput | UpdateTrainerInput>({
    resolver: zodResolver(isEdit ? updateTrainerSchema : createTrainerSchema),
    defaultValues: {
      fullName: trainer?.fullName ?? '',
      phone: trainer?.phone ?? undefined,
      ...(isEdit ? { isActive: trainer.isActive } : {}),
    },
  })
  // useEffect reset on trainer change (analog lines 47–54)
  // onSubmit → mutate → toast.success → handleClose (analog lines 61–117)
  // Inline error for 409 phone_exists → <Alert variant="destructive"> (analog lines 201–205)
}
```

**isActive Checkbox — edit mode only** (new pattern not in analog):
```typescript
{isEdit && (
  <div className="flex items-center gap-2">
    <Checkbox id="isActive" {...form.register('isActive')} />
    <Label htmlFor="isActive" className="cursor-pointer">
      {t('trainers.form.fields.isActive')}
    </Label>
  </div>
)}
```

---

### `apps/admin-web/src/features/trainers/components/DeleteTrainerAlertDialog.tsx` (component, request-response)

**Analog:** `apps/admin-web/src/features/memberships/components/CancelMembershipDialog.tsx`

**AlertDialog with inline error pattern** (analog lines 62–117):
```typescript
import { useState } from 'react'
import { toast } from 'sonner'
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel,
  AlertDialogContent, AlertDialogDescription, AlertDialogFooter,
  AlertDialogHeader, AlertDialogTitle,
} from '@/shared/ui/alert-dialog'
import { Alert, AlertDescription } from '@/shared/ui/alert'
import { isDomainError } from '@/shared/api/errors'
import { t } from '@/shared/i18n'
import { useDeleteTrainer } from '../api/hooks'

interface Props {
  open: boolean
  onClose: () => void
  trainer: Trainer
}

export function DeleteTrainerAlertDialog({ open, onClose, trainer }: Props) {
  const deleteTrainer = useDeleteTrainer()
  const [inlineError, setInlineError] = useState<string | null>(null)

  const handleConfirm = () => {
    setInlineError(null)
    deleteTrainer.mutate(trainer.id, {
      onSuccess: () => {
        toast.success(t('trainers.toast.deleted'))
        onClose()
      },
      onError: (err) => {
        if (isDomainError(err) && err.code === 'trainer_in_use') {
          setInlineError(t('trainers.errors.trainerInUse'))
          // Dialog stays open — user reads error and dismisses manually
        } else {
          toast.error(t('common.errors.network'))
          onClose()
        }
      },
    })
  }

  return (
    <AlertDialog open={open} onOpenChange={(o) => { if (!o) { setInlineError(null); onClose() } }}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>{t('trainers.dialog.deleteTitle')}</AlertDialogTitle>
          <AlertDialogDescription>
            {t('trainers.dialog.deleteBody').replace('{fullName}', trainer.fullName)}
          </AlertDialogDescription>
        </AlertDialogHeader>

        {inlineError && (
          <Alert variant="destructive" className="mb-3">
            <AlertDescription>{inlineError}</AlertDescription>
          </Alert>
        )}

        <AlertDialogFooter>
          <AlertDialogCancel onClick={onClose}>{t('trainers.dialog.deleteCancel')}</AlertDialogCancel>
          <AlertDialogAction
            className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            onClick={handleConfirm}
            disabled={deleteTrainer.isPending}
          >
            {deleteTrainer.isPending ? '…' : t('trainers.dialog.deleteConfirm')}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  )
}
```

**Key difference from CancelMembershipDialog:** No textarea (no reason field); dialog stays open on 409 (does not call `onClose()` on trainer_in_use error).

---

### `apps/admin-web/src/features/trainers/components/ActiveFilterPill.tsx` (component, request-response)

**Closest analog:** `apps/admin-web/src/features/memberships/components/MembershipsListPage.tsx` status filter (partial match — no direct `ToggleGroup` analog; UI-SPEC.md specifies 3 `<Button>` styled as segmented control)

**Implementation pattern** per UI-SPEC.md:
```typescript
interface Props {
  value: 'true' | 'false' | undefined
  onChange: (value: 'true' | 'false' | undefined) => void
}

export function ActiveFilterPill({ value, onChange }: Props) {
  return (
    <div className="flex gap-1">
      {([
        { label: t('trainers.filter.active'),   filterVal: 'true'      },
        { label: t('trainers.filter.inactive'), filterVal: 'false'     },
        { label: t('trainers.filter.all'),      filterVal: undefined   },
      ] as const).map(({ label, filterVal }) => (
        <Button
          key={label}
          size="sm"
          variant={value === filterVal ? 'default' : 'outline'}
          onClick={() => onChange(filterVal)}
        >
          {label}
        </Button>
      ))}
    </div>
  )
}
```

---

### `apps/admin-web/src/routes/_protected/trainers.tsx` (route, request-response)

**Analog:** `apps/admin-web/src/routes/_protected/membership-plans.tsx`

**Exact copy pattern** (analog lines 1–34 — adapted):
```typescript
import { createFileRoute, redirect } from '@tanstack/react-router'
import { z } from 'zod'
import { can } from '@/shared/session/can'
import { trainersKeys } from '@/features/trainers/api/keys'
import { services } from '@/shared/api/services'
import { TrainersPage } from '@/features/trainers/components/TrainersPage'

const searchSchema = z.object({
  active: z.enum(['true', 'false']).optional(),
  page: z.coerce.number().int().min(1).default(1),
  pageSize: z.coerce.number().int().min(10).max(100).default(20),
})

export const Route = createFileRoute('/_protected/trainers')({
  validateSearch: searchSchema,
  beforeLoad: ({ context, location }) => {
    const { role } = context.getSession()
    if (!can(role, 'view', 'trainers')) {
      throw redirect({
        to: '/',
        search: { forbidden: location.pathname + (location.searchStr ?? '') },
      })
    }
  },
  loaderDeps: ({ search }) => ({ search }),
  loader: ({ context, deps: { search } }) =>
    context.queryClient.ensureQueryData({
      queryKey: trainersKeys.list({
        active: search.active ?? 'true',  // default "Активные" view (D-31-22)
        page: search.page,
        pageSize: search.pageSize,
      }),
      queryFn: () =>
        services.trainers.list({
          active: search.active === 'true' ? true : search.active === 'false' ? false : true,
          page: search.page,
          pageSize: search.pageSize,
        }),
    }),
  component: TrainersPage,
})
```

---

### `apps/admin-web/src/shared/i18n/ru.ts` — MODIFY (config, —)

**Analog:** `apps/admin-web/src/shared/i18n/ru.ts` (existing keys structure)

**Append block** under `shell.nav` (add `trainers: 'Тренеры'`) and new top-level `trainers` key. Full key list per UI-SPEC.md Copywriting Contract:
```typescript
// In shell.nav block:
trainers: 'Тренеры',  // shell.nav.trainers

// New top-level block (append after existing domain blocks):
trainers: {
  heading: 'Тренеры',
  actions: {
    create: 'Добавить тренера',
    edit: 'Редактировать тренера',
    delete: 'Удалить тренера',
  },
  columns: {
    fullName: 'ФИО',
    phone: 'Телефон',
    status: 'Статус',
  },
  status: {
    active: 'Активен',
    inactive: 'Неактивен',
  },
  filter: {
    active: 'Активные',
    inactive: 'Неактивные',
    all: 'Все',
  },
  form: {
    createHeading: 'Добавить тренера',
    editHeading: 'Редактировать тренера',
    fields: {
      fullName: 'ФИО',
      phone: 'Телефон',
      isActive: 'Активный тренер',
    },
    saveCreate: 'Добавить тренера',
    saveEdit: 'Сохранить изменения',
    submitting: 'Сохраняется…',
    cancel: 'Отмена',
  },
  dialog: {
    deleteTitle: 'Удалить тренера?',
    deleteBody: 'Тренер {fullName} будет удалён без возможности восстановления.',
    deleteConfirm: 'Удалить',
    deleteCancel: 'Не удалять',
  },
  empty: {
    heading: 'Тренеров пока нет',
    body: 'Добавьте первого тренера, нажав «Добавить тренера».',
  },
  noResults: {
    heading: 'Нет тренеров',
    body: 'Попробуйте изменить фильтр.',
  },
  errorState: {
    heading: 'Не удалось загрузить тренеров',
  },
  toast: {
    created: 'Тренер добавлен',
    updated: 'Тренер сохранён',
    deactivated: 'Тренер деактивирован',
    reactivated: 'Тренер активирован',
    deleted: 'Тренер удалён',
  },
  errors: {
    phoneDuplicate: 'Тренер с таким телефоном уже существует',
    phoneFormat: 'Введите телефон в формате +7XXXXXXXXXX',
    fullNameRequired: 'Укажите ФИО',
    trainerInUse: 'Тренер ведёт персональные тренировки и не может быть удалён. Деактивируйте тренера вместо удаления.',
  },
},
```

---

## Shared Patterns

### Authentication + RBAC (backend)
**Source:** `apps/backend/app/core/dependencies.py` — `require_permission`, `verify_csrf`, `get_current_user`
**Apply to:** All trainer router endpoints
```python
# Pattern: permission Depends BEFORE csrf Depends (RBAC-04)
actor: Annotated[CurrentUser, Depends(require_permission(Action.CREATE, Resource.TRAINERS))],
_csrf: Annotated[None, Depends(verify_csrf)],
```

### IntegrityError → AppError mapping (backend service)
**Source:** `apps/backend/app/modules/clients/service.py` lines 101–106
**Apply to:** `trainers/service.py` create + update (phone_exists) + delete (trainer_in_use)
```python
def _is_phone_conflict(exc: IntegrityError) -> bool:
    constraint = getattr(exc.orig, "constraint_name", None) or ""
    if constraint == "uq_trainers_phone_alive":
        return True
    return "uq_trainers_phone_alive" in str(exc.orig)
```

### Audit emit pattern (backend service)
**Source:** `apps/backend/app/modules/clients/service.py` lines 131–143
**Apply to:** All 4 trainer lifecycle transitions in `trainers/service.py`
```python
await audit.emit(
    session,
    "trainer_created",          # one of: trainer_created/updated/deactivated/reactivated
    actor_user_id=actor.id,
    resource_type="trainer",    # literal string — AST gate requires literal
    resource_id=trainer.id,
    trainer_id=trainer.id,      # payload kwargs verbatim per locked schema
    full_name=trainer.full_name,
)
await session.commit()          # SVC001: every mutation must commit explicitly
```

### SVC001 commit discipline
**Source:** `apps/backend/tests/unit/test_service_commit_gate.py` (SVC001 walker)
**Apply to:** Every mutation function in `trainers/service.py`
**Rule:** Every function that mutates data MUST call `await session.commit()` at its end. No exceptions — SVC001 AST walker will fail CI.

### ResponseEnvelope wrapping (backend router)
**Source:** `apps/backend/app/modules/clients/router.py` line 66 + `app/core/schemas.py`
**Apply to:** All trainer router endpoints
```python
return envelope(trainer)        # wraps response in ResponseEnvelope[T]
```

### DomainError + inline Alert (admin-web)
**Source:** `apps/admin-web/src/features/memberships/components/CancelMembershipDialog.tsx` lines 89–91
**Apply to:** `DeleteTrainerAlertDialog.tsx` (409 trainer_in_use) + `TrainerFormDialog.tsx` (409 phone_exists)
```typescript
{inlineError && (
  <Alert variant="destructive" className="mb-3">
    <AlertDescription>{inlineError}</AlertDescription>
  </Alert>
)}
```

### can() role enforcement (admin-web mock)
**Source:** `apps/admin-web/src/shared/api/services/mock/clients.ts` lines 16–24
**Apply to:** `mock/trainers.ts` — all methods
```typescript
function ensure(action: 'view' | 'create' | 'edit' | 'delete', resource: 'trainers') {
  if (!can(role(), action, resource)) {
    throw new DomainError('forbidden', 'Доступ запрещён')
  }
}
```

### loadDB/saveDB + delay() (admin-web mock)
**Source:** `apps/admin-web/src/shared/api/services/mock/_db.ts` + `_latency.ts`
**Apply to:** `mock/trainers.ts`
- `delay()` called at start of every method (120–300ms)
- `loadDB()` reads from `localStorage['sportzal:mock:v1']`
- `saveDB(db)` persists changes
- `db.trainers` initialized lazily on first `list()` call

### beforeLoad owner-only redirect (admin-web route)
**Source:** `apps/admin-web/src/routes/_protected/membership-plans.tsx` lines 15–23
**Apply to:** `routes/_protected/trainers.tsx`
```typescript
beforeLoad: ({ context, location }) => {
  const { role } = context.getSession()
  if (!can(role, 'view', 'trainers')) {
    throw redirect({
      to: '/',
      search: { forbidden: location.pathname + (location.searchStr ?? '') },
    })
  }
}
```

### Loading / Error / Empty state (admin-web component)
**Source:** `apps/admin-web/src/features/memberships/components/MembershipPlansPage.tsx` lines 159–193
**Apply to:** `TrainersPage.tsx` (route component composing all sub-components)
```typescript
{query.isError && (
  <div className="space-y-3 rounded-md border p-6 text-center">
    <h2 className="text-lg font-semibold">{t('trainers.errorState.heading')}</h2>
    <Button onClick={() => void query.refetch()}>{t('common.retryLoad')}</Button>
  </div>
)}
{query.isLoading && (
  <div className="space-y-3 rounded-md border p-4">
    {Array.from({ length: 5 }).map((_, i) => (
      <div key={i} className="flex gap-4">
        <Skeleton className="h-4 w-48" />
        <Skeleton className="h-4 w-28" />
        <Skeleton className="h-4 w-16" />
        <Skeleton className="h-4 w-12" />
      </div>
    ))}
  </div>
)}
```

---

## No Analog Found

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| `apps/admin-web/src/features/trainers/components/ActiveFilterPill.tsx` | component | request-response | No existing 3-way segmented Button filter pill in the codebase — closest is status badge but not interactive; pattern derived from UI-SPEC.md contract using shadcn Button variant toggling |

---

## Notes for Planner

1. **`_db.ts` must be extended:** `DB` interface needs `trainers: Trainer[]` field added. `loadDB` default factory must include `trainers: []`. This is a modification to `shared/api/services/mock/_db.ts`, not listed in the original file list but required for the mock service to work.

2. **`Trainer` entity type:** The mock service imports `Trainer` and `TrainerId` from `@/entities/trainer`. This entity may need to be created in `apps/admin-web/src/entities/trainer/index.ts` with the type definition. Check if it exists — if not, planner should add it to Plan 31-02 scope.

3. **`TrainersPage` component:** UI-SPEC.md specifies `TrainersPage` as the route component that composes all sub-components. This is not in the original file list but is the natural route component. Planner should include it.

4. **`TrainerStatusBadge`:** UI-SPEC.md specifies this as a separate component from `TrainersTable`. Planner should include it alongside `TrainersTable`.

5. **Test file location:** Backend integration tests should follow existing `tests/integration/clients/` subdirectory pattern — place in `tests/integration/trainers/` with its own `conftest.py`, `test_trainers_crud.py`, `test_trainers_audit.py`, `test_trainers_rbac.py`.

6. **audit_payloads.py payload kwargs:** The 4 locked payload schemas in `app/core/audit_payloads.py` (Plan 30-01) define exact kwargs for `audit.emit()`. Service must pass kwargs verbatim matching `TrainerCreatedPayload`, `TrainerUpdatedPayload`, `TrainerDeactivatedPayload`, `TrainerReactivatedPayload` fields. Planner should read `app/core/audit_payloads.py` lines 42–74 before specifying exact emit callsites.

---

## Metadata

**Analog search scope:** `apps/backend/app/modules/clients/`, `apps/backend/alembic/versions/`, `apps/backend/app/core/`, `apps/backend/app/api/`, `apps/backend/app/workers/`, `apps/backend/tests/integration/clients/`, `apps/admin-web/src/features/memberships/`, `apps/admin-web/src/shared/api/services/mock/`, `apps/admin-web/src/routes/_protected/`
**Files scanned:** 22 source files read
**Pattern extraction date:** 2026-05-14
