"""Phase 113 promo_codes admin CRUD repository (PROMO-01/PROMO-02).

No commit() or flush() here. Caller (service) owns the unit of work so it
can co-write audit rows in the same transaction if needed (mirrors
users/repository.py D-43-09 discipline and clients/repository.py D-03 lineage).

Returns ORM objects or PaginatedData. Pydantic validation happens in the
caller (service) via model_validate.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import and_, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.pagination import PaginatedData
from app.modules.promo_codes.models import PromoCode, PromoRedemption
from app.modules.promo_codes.schemas import (
    PromoCodeListItemResponse,
    PromoCodeListQuery,
)


async def list_promo_codes(
    session: AsyncSession, query: PromoCodeListQuery
) -> PaginatedData[PromoCodeListItemResponse]:
    """Paginated promo code list with used_count aggregate (PROMO-02).

    Predicates:
      - deleted_at IS NULL (alive rows only)
      - is_active filter when query.active is not None

    used_count: correlated scalar subquery counting promo_redemptions rows
    per PromoCode row (mirrors raw-SQL discipline for cross-module aggregates).

    Sort: created_at DESC, id DESC (mirrors users/clients convention).
    """
    predicates = [PromoCode.deleted_at.is_(None)]
    if query.active is not None:
        predicates.append(PromoCode.is_active.is_(query.active))

    # COUNT with predicates for total
    total: int = await session.scalar(
        select(func.count()).select_from(PromoCode).where(and_(*predicates))
    ) or 0

    # Correlated scalar subquery — used_count per PromoCode row
    used_count_subq = (
        select(func.count())
        .select_from(PromoRedemption)
        .where(PromoRedemption.promo_code_id == PromoCode.id)
        .correlate(PromoCode)
        .scalar_subquery()
    )

    stmt = (
        select(PromoCode, used_count_subq.label("used_count"))
        .where(and_(*predicates))
        .order_by(PromoCode.created_at.desc(), PromoCode.id.desc())
        .offset((query.page - 1) * query.page_size)
        .limit(query.page_size)
    )

    rows = (await session.execute(stmt)).all()
    items = [
        PromoCodeListItemResponse(
            id=row.PromoCode.id,
            code=row.PromoCode.code,
            discount_type=row.PromoCode.discount_type,
            discount_value=row.PromoCode.discount_value,
            max_uses=row.PromoCode.max_uses,
            per_client_limit=row.PromoCode.per_client_limit,
            valid_from=row.PromoCode.valid_from,
            valid_until=row.PromoCode.valid_until,
            is_active=row.PromoCode.is_active,
            applicable_to=row.PromoCode.applicable_to,
            description=row.PromoCode.description,
            used_count=row.used_count,
            created_at=row.PromoCode.created_at,
        )
        for row in rows
    ]

    return PaginatedData.model_construct(
        items=items,
        total=total,
        page=query.page,
        page_size=query.page_size,
    )


async def get_alive(session: AsyncSession, promo_id: UUID) -> PromoCode | None:
    """Return alive PromoCode by id, or None if missing/soft-deleted."""
    result: PromoCode | None = await session.scalar(
        select(PromoCode).where(
            PromoCode.id == promo_id,
            PromoCode.deleted_at.is_(None),
        )
    )
    return result


async def insert_promo_code(
    session: AsyncSession,
    *,
    code: str,
    discount_type: str,
    discount_value: int,
    max_uses: int | None,
    per_client_limit: int | None,
    valid_from: object | None,
    valid_until: object | None,
    applicable_to: str | None,
    description: str | None,
) -> PromoCode:
    """Insert a new PromoCode row. No flush/commit — caller owns the UoW."""
    promo = PromoCode(
        code=code,
        discount_type=discount_type,
        discount_value=discount_value,
        max_uses=max_uses,
        per_client_limit=per_client_limit,
        valid_from=valid_from,
        valid_until=valid_until,
        applicable_to=applicable_to,
        description=description,
    )
    session.add(promo)
    return promo


async def update_promo_code(
    session: AsyncSession,
    promo: PromoCode,
    *,
    values: dict[str, object],
) -> None:
    """Apply a dict of field updates to an alive PromoCode ORM instance.

    No flush/commit — caller owns the UoW.
    values keys match PromoCode column names (snake_case).
    """
    for field, value in values.items():
        setattr(promo, field, value)


async def deactivate_promo_code(
    session: AsyncSession,
    *,
    promo_id: UUID,
) -> None:
    """Set is_active=False on an alive PromoCode via bulk UPDATE.

    No flush/commit — caller owns the UoW.
    WHERE deleted_at IS NULL ensures soft-deleted rows are never touched.
    """
    await session.execute(
        update(PromoCode)
        .where(PromoCode.id == promo_id, PromoCode.deleted_at.is_(None))
        .values(is_active=False)
    )
