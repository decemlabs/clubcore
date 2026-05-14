"""Trainers service — orchestration between router and repository (Phase 31 TRN-01..07).

Module-level async functions. Each mutation function:
  1. Validates / prepares data
  2. Calls `repository.<fn>` (caller-owns-txn D-03)
  3. Handles `IntegrityError` → raises appropriate AppError (D-31-03/D-31-07)
  4. `await audit.emit(session, ...)` (D-31-16 co-transactional)
  5. `await session.flush()` to surface DB-level constraint conflicts
  6. `await session.commit()` to persist the unit of work (SVC001 gate)

D-31-12 audit emission:
  - trainer_created: trainer_id + full_name + phone (required even when None)
  - trainer_deactivated: trainer_id only (TrainerDeactivatedPayload)
  - trainer_reactivated: trainer_id only (TrainerReactivatedPayload)
  - trainer_updated: trainer_id + changed_fields (sorted, non-is_active fields)
  Combined PATCH → both state-flip event + trainer_updated (2 events atomically).

D-31-15: resolve_trainer_by_id — Protocol slot consumer for Phase 34 PT-session
validator. Returns alive Trainer regardless of is_active (caller decides).
"""

from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import audit
from app.core.dependencies import CurrentUser
from app.core.exceptions import PhoneExistsError, TrainerInUseError, TrainerNotFoundError
from app.core.pagination import PaginatedData
from app.modules.trainers import repository
from app.modules.trainers.models import Trainer
from app.modules.trainers.schemas import (
    TrainerCreateRequest,
    TrainerListQuery,
    TrainerResponse,
    TrainerUpdateRequest,
)


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


async def create_trainer(
    session: AsyncSession,
    actor: CurrentUser,
    data: TrainerCreateRequest,
) -> TrainerResponse:
    """Create a new trainer (TRN-02).

    Order: insert → flush (surface DB constraints) → emit audit on success.
    TrainerCreatedPayload requires phone kwarg even when None (D-31-16).
    """
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
        trainer_id=str(trainer.id),
        full_name=trainer.full_name,
        phone=trainer.phone,  # required by TrainerCreatedPayload even when None
    )
    await session.commit()
    return TrainerResponse.model_validate(trainer)


async def update_trainer(
    session: AsyncSession,
    actor: CurrentUser,
    trainer_id: UUID,
    data: TrainerUpdateRequest,
) -> TrainerResponse:
    """Partial update with PATCH semantics (TRN-03, D-31-11/D-31-12).

    D-31-12: detect is_active state flip and emit state-flip event;
    emit trainer_updated for other field changes separately (2 events if both).
    No-op PATCH (no changed fields) returns current state without audit/flush/commit.
    """
    trainer = await repository.get_alive(session, trainer_id)
    if trainer is None:
        raise TrainerNotFoundError("trainer_not_found")

    prev_is_active = trainer.is_active
    changed_previous = await repository.update_trainer(session, trainer, data)

    if not changed_previous:
        # D-31-09: idempotent no-op PATCH → skip emit, skip flush, skip commit.
        return TrainerResponse.model_validate(trainer)

    try:
        await session.flush()
    except IntegrityError as exc:
        await session.rollback()
        if _is_phone_conflict(exc):
            raise PhoneExistsError("phone_exists") from exc
        raise

    # D-31-12: detect is_active state flip and emit separate events.
    is_active_changed = "is_active" in changed_previous
    other_changed = {k: v for k, v in changed_previous.items() if k != "is_active"}

    if is_active_changed:
        if prev_is_active and not trainer.is_active:
            await audit.emit(
                session,
                "trainer_deactivated",
                actor_user_id=actor.id,
                resource_type="trainer",
                resource_id=trainer.id,
                trainer_id=str(trainer.id),
            )
        else:
            await audit.emit(
                session,
                "trainer_reactivated",
                actor_user_id=actor.id,
                resource_type="trainer",
                resource_id=trainer.id,
                trainer_id=str(trainer.id),
            )

    if other_changed:
        await audit.emit(
            session,
            "trainer_updated",
            actor_user_id=actor.id,
            resource_type="trainer",
            resource_id=trainer.id,
            trainer_id=str(trainer.id),
            changed_fields=sorted(other_changed.keys()),
        )

    await session.refresh(trainer, attribute_names=["updated_at"])
    await session.commit()
    return TrainerResponse.model_validate(trainer)


async def delete_trainer(
    session: AsyncSession,
    actor: CurrentUser,
    trainer_id: UUID,
) -> None:
    """Hard-delete a trainer (TRN-05, D-31-06/D-31-07).

    Maps IntegrityError pgcode 23503 → TrainerInUseError (409) pre-emptively
    for Phase 34 pt_sessions FK (D-31-07). No audit event for hard-delete.
    """
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


async def list_trainers(
    session: AsyncSession,
    query: TrainerListQuery,
) -> PaginatedData[TrainerResponse]:
    """Return paginated alive trainers with optional is_active filter (TRN-04, D-31-09).

    Read-side: no audit emit, no actor required.
    """
    page = await repository.list_alive(session, query)
    return PaginatedData[TrainerResponse](
        items=[TrainerResponse.model_validate(t) for t in page.items],
        total=page.total,
        page=page.page,
        page_size=page.page_size,
    )


async def get_trainer(
    session: AsyncSession,
    trainer_id: UUID,
) -> TrainerResponse:
    """Return alive trainer by id; raise 404 for missing/soft-deleted (TRN-02)."""
    trainer = await repository.get_alive(session, trainer_id)
    if trainer is None:
        raise TrainerNotFoundError("trainer_not_found")
    return TrainerResponse.model_validate(trainer)


async def resolve_trainer_by_id(
    session: AsyncSession,
    trainer_id: UUID,
) -> Trainer | None:
    """Protocol slot consumer for Phase 34 PT-session validator (D-31-15).

    Returns alive Trainer regardless of is_active (caller decides).
    Returns None if missing or soft-deleted.
    """
    return await repository.get_alive(session, trainer_id)
