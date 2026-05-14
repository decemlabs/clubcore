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

from typing import Any
from uuid import UUID

from sqlalchemy import Select, and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.pagination import PaginatedData
from app.modules.trainers.models import Trainer
from app.modules.trainers.schemas import (
    TrainerCreateRequest,
    TrainerListQuery,
    TrainerUpdateRequest,
)


async def get_alive(session: AsyncSession, trainer_id: UUID) -> Trainer | None:
    """Return alive (not soft-deleted) trainer by id, or None."""
    stmt: Select[tuple[Trainer]] = select(Trainer).where(
        Trainer.id == trainer_id,
        Trainer.deleted_at.is_(None),
    )
    result: Trainer | None = await session.scalar(stmt)
    return result


async def list_alive(
    session: AsyncSession, query: TrainerListQuery
) -> PaginatedData[Trainer]:
    """Paginated list of alive trainers with optional is_active filter (D-31-09).

    Returns a `PaginatedData` instance constructed via `model_construct` to skip
    Pydantic validation against the generic parameter.
    """
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


async def insert_trainer(
    session: AsyncSession,
    data: TrainerCreateRequest,
) -> Trainer:
    """Insert new trainer; caller owns flush + audit emit (D-03).

    Always sets is_active=True on create (D-31-02).
    """
    trainer = Trainer(
        full_name=data.full_name,
        phone=data.phone,
        is_active=True,  # always active on create (D-31-02)
    )
    session.add(trainer)
    return trainer


async def update_trainer(
    session: AsyncSession,
    trainer: Trainer,
    data: TrainerUpdateRequest,
) -> dict[str, object]:
    """Apply PATCH to existing alive Trainer.

    Returns {field_name: previous_value} for fields that actually changed.
    Uses data.model_dump(exclude_unset=True) to respect PATCH semantics (D-01).
    """
    updates = data.model_dump(exclude_unset=True)
    changed: dict[str, object] = {}
    for key, value in updates.items():
        previous = getattr(trainer, key)
        if previous != value:
            changed[key] = previous
            setattr(trainer, key, value)
    return changed


async def hard_delete_trainer(session: AsyncSession, trainer: Trainer) -> None:
    """Hard-delete the trainer row. FK constraint from pt_sessions raises
    IntegrityError (pgcode 23503) if trainer_in_use — caller maps to 409."""
    await session.delete(trainer)
