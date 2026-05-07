"""Visits repository — single point of access to the `Visit` ORM (Phase 19 VIS-02).

This is the ONLY module in the codebase that imports the `Visit` ORM model.
The service layer calls these module-level async helpers and never executes
`select(Visit)` directly.

Transaction control: no commit, no flush — the caller (service) owns the
transactional moment so it can co-write the audit log row in the same UoW
(mirror of memberships D-14, clients D-03).

`from __future__ import annotations` is required: list_by_query is annotated
with `PaginatedData[Visit]`, and `Visit` is a SQLAlchemy ORM class without a
Pydantic core schema.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.pagination import PaginatedData
from app.modules.visits.models import Visit
from app.modules.visits.schemas import VisitListQuery


async def get(session: AsyncSession, visit_id: UUID) -> Visit | None:
    """Return Visit by id, or None.

    NO soft-delete filter — Visits have no `deleted_at` column (CD-04).
    """
    stmt: Select[tuple[Visit]] = select(Visit).where(Visit.id == visit_id)
    result: Visit | None = await session.scalar(stmt)
    return result


async def list_by_query(
    session: AsyncSession, query: VisitListQuery
) -> PaginatedData[Visit]:
    """List Visit rows filtered by client_id / from / to (D-09).

    Default sort `checked_in_at DESC` (D-09 — no sort enum). Filters use
    `gym_date` for date-bounded windows (inclusive on both ends — CD-08).
    """
    predicates = []
    if query.client_id is not None:
        predicates.append(Visit.client_id == query.client_id)
    if query.from_ is not None:
        predicates.append(Visit.gym_date >= query.from_)
    if query.to is not None:
        predicates.append(Visit.gym_date <= query.to)

    count_stmt = select(func.count()).select_from(Visit)
    if predicates:
        count_stmt = count_stmt.where(*predicates)
    total = (await session.scalar(count_stmt)) or 0

    list_stmt: Select[tuple[Visit]] = select(Visit)
    if predicates:
        list_stmt = list_stmt.where(*predicates)
    list_stmt = (
        list_stmt.order_by(Visit.checked_in_at.desc())
        .offset((query.page - 1) * query.page_size)
        .limit(query.page_size)
    )
    rows = (await session.scalars(list_stmt)).all()

    # PaginatedData.model_construct skips Pydantic validation against the SA
    # ORM generic — same trick as memberships/repository.py.
    return PaginatedData.model_construct(
        items=list(rows),
        total=total,
        page=query.page,
        page_size=query.page_size,
    )


async def create(
    session: AsyncSession,
    *,
    client_id: UUID,
    membership_id: UUID,
    channel: str,
    checked_in_by: UUID | None,
) -> Visit:
    """Insert a new Visit row. Caller MUST flush then commit (D-04 + INFRA-13).

    NOTE: `gym_date` is the STORED GENERATED column (D-06) — DO NOT pass it.
    `checked_in_at` defaults to DB now() (D-07) — DO NOT pass it in production.
    """
    visit = Visit(
        client_id=client_id,
        membership_id=membership_id,
        channel=channel,
        checked_in_by=checked_in_by,
    )
    session.add(visit)
    return visit
