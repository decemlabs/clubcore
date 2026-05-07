"""Memberships repository — single point of access to the `MembershipPlan` ORM (MEM-PLAN-02).

This is the ONLY module in the codebase that imports the `MembershipPlan` ORM model.
The service layer calls these module-level async helpers and never executes
`select(MembershipPlan)` directly. That single rule constructively guarantees
MEM-PLAN-02: "all queries through `list_alive` / `get_alive`".

Soft-delete invariant: every read helper appends `MembershipPlan.deleted_at IS NULL`
as the first predicate. `soft_delete_plan` is the ONLY mutation point that touches
`deleted_at`.

Transaction control: NO `session.commit()` and NO `session.flush()` calls live here.
The caller (service) owns the transactional moment so it can co-write the audit log
row in the same UoW (D-14, mirroring clients D-03).

`from __future__ import annotations` is required: `list_alive` is annotated with
`PaginatedData[MembershipPlan]`, and `MembershipPlan` is a SQLAlchemy ORM class
without a Pydantic core schema. Without PEP 563 deferred evaluation, importing this
module triggers `PaginatedData.__class_getitem__(MembershipPlan)` at runtime, which
delegates to Pydantic's generic schema-builder and raises `PydanticSchemaGenerationError`.
Deferring annotation evaluation keeps the type information for mypy while preventing
the import-time schema build (mirrors clients/repository.py:18-23).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import Select, and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.pagination import PaginatedData
from app.modules.memberships.models import MembershipPlan
from app.modules.memberships.schemas import (
    MembershipPlanCreateRequest,
    MembershipPlanListQuery,
    MembershipPlanSort,
    MembershipPlanUpdateRequest,
)


async def get_alive(session: AsyncSession, plan_id: UUID) -> MembershipPlan | None:
    """Return alive plan by id, or None for missing/soft-deleted (MEM-PLAN-02)."""
    stmt: Select[tuple[MembershipPlan]] = select(MembershipPlan).where(
        MembershipPlan.id == plan_id,
        MembershipPlan.deleted_at.is_(None),
    )
    result: MembershipPlan | None = await session.scalar(stmt)
    return result


async def list_alive(
    session: AsyncSession, query: MembershipPlanListQuery
) -> PaginatedData[MembershipPlan]:
    """Paginated list of alive plans with optional active filter + sort applied (MEM-PLAN-EP-01).

    Returns a `PaginatedData` instance constructed via `model_construct` to skip
    Pydantic validation against the generic parameter. The SQLAlchemy `MembershipPlan`
    ORM is not a Pydantic-compatible type and `PaginatedData[MembershipPlan](...)` would
    trigger a `PydanticSchemaGenerationError` at the runtime parametrisation step.
    The service layer immediately re-wraps the result as `PaginatedData[MembershipPlanResponse]`,
    so skipping validation here is safe.

    D-08: default filter = alive only; optional `?active` filter; no `?q` (D-09).
    """
    predicates: list[Any] = [MembershipPlan.deleted_at.is_(None)]

    # D-08: optional active filter; omit = both active and inactive alive rows.
    if query.active is not None:
        predicates.append(MembershipPlan.active == query.active)

    # Total count — same predicate list, no ORDER/LIMIT.
    total_stmt = select(func.count()).select_from(MembershipPlan).where(and_(*predicates))
    total = await session.scalar(total_stmt) or 0

    # Items
    stmt: Select[tuple[MembershipPlan]] = select(MembershipPlan).where(and_(*predicates))
    if query.sort == MembershipPlanSort.NAME_ASC:
        # Case-insensitive sort; stable tie-break on created_at desc.
        stmt = stmt.order_by(
            func.lower(MembershipPlan.name).asc(), MembershipPlan.created_at.desc()
        )
    else:  # default CREATED_AT_DESC
        # Stable tie-break on id desc.
        stmt = stmt.order_by(MembershipPlan.created_at.desc(), MembershipPlan.id.desc())

    offset = (query.page - 1) * query.page_size
    stmt = stmt.offset(offset).limit(query.page_size)

    rows = (await session.scalars(stmt)).all()

    return PaginatedData.model_construct(
        items=list(rows),
        total=total,
        page=query.page,
        page_size=query.page_size,
    )


async def insert_plan(
    session: AsyncSession,
    data: MembershipPlanCreateRequest,
) -> MembershipPlan:
    """Insert a new plan; caller owns the transactional flush + audit emit (D-14).

    No `created_by_user_id` parameter — plans have no creator FK (MEM-PLAN-01).
    No flush() here — caller (service) catches IntegrityError on its own flush call.
    """
    plan = MembershipPlan(
        name=data.name,
        duration_days=data.duration_days,
        price_kopecks=data.price_kopecks,
        active=data.active,
    )
    session.add(plan)
    return plan


async def update_plan(
    session: AsyncSession,
    plan: MembershipPlan,
    data: MembershipPlanUpdateRequest,
) -> dict[str, object]:
    """Apply PATCH update to an existing alive MembershipPlan.

    Returns a dict of {field_name: previous_value} for the fields that actually
    changed. Service layer uses this to (a) decide whether to emit
    `membership_plan_updated` (D-09 no-op skip) and (b) build the
    `changed_fields` audit payload (D-12).

    Keys can only be `name | price_kopecks | active` because `MembershipPlanUpdateRequest`
    declares no other writable fields (D-07, D-04).
    """
    updates = data.model_dump(exclude_unset=True)
    changed: dict[str, object] = {}

    for key, value in updates.items():
        previous = getattr(plan, key)
        if previous != value:
            changed[key] = previous
            setattr(plan, key, value)

    return changed


async def soft_delete_plan(session: AsyncSession, plan: MembershipPlan) -> MembershipPlan:
    """Soft-delete: set deleted_at to now(); never DELETE the row (MEM-PLAN-02)."""
    plan.deleted_at = datetime.now(tz=UTC)
    return plan
