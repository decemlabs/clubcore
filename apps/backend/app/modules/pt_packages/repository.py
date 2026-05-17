"""PT-packages repository — single point of access to the PT-package ORM (mirror MEM-PLAN-02).

This is the ONLY module in the codebase that imports the PtPackagePlan + PtPackage
ORM models from `pt_packages.models`. The service layer calls these module-level
async helpers and never executes `select(PtPackagePlan)` directly. That single
rule constructively guarantees the alive-bias soft-delete invariant for plans.

Soft-delete invariant (PtPackagePlan only): every read helper appends
`PtPackagePlan.deleted_at IS NULL`. `soft_delete_plan` is the ONLY mutation point
that touches `deleted_at`. PtPackage has NO soft-delete column (D-33-03; lifecycle
is purely status-based).

Transaction control: NO `session.commit()` and NO `session.flush()` calls live here
(mirror memberships D-14). The caller (service) owns the transactional moment so
it can co-write the audit_log row in the same UoW.

`from __future__ import annotations` is required: list helpers are annotated with
`PaginatedData[PtPackagePlan]` / `PaginatedData[PtPackage]`, and the SA ORM classes
are not Pydantic-compatible. Without PEP 563 deferred evaluation, importing this
module triggers `PaginatedData.__class_getitem__(...)` at runtime, which delegates
to Pydantic's generic schema-builder and raises `PydanticSchemaGenerationError`
(mirrors memberships/repository.py rationale).
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, date, datetime
from typing import Any
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import Row, Select, and_, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.pagination import PaginatedData
from app.modules.pt_packages.models import PtPackage, PtPackagePlan
from app.modules.pt_packages.schemas import (
    PtPackageCreateRequest,
    PtPackageListQuery,
    PtPackageListSort,
    PtPackagePlanCreateRequest,
    PtPackagePlanListQuery,
    PtPackagePlanSort,
)

# ---------------------------------------------------------------------------
# Plan helpers (PT-01 / PT-02)
# ---------------------------------------------------------------------------


async def get_plan_alive(session: AsyncSession, plan_id: UUID) -> PtPackagePlan | None:
    """Return alive plan by id, or None for missing/soft-deleted (D-33-08)."""
    stmt: Select[tuple[PtPackagePlan]] = select(PtPackagePlan).where(
        PtPackagePlan.id == plan_id,
        PtPackagePlan.deleted_at.is_(None),
    )
    result: PtPackagePlan | None = await session.scalar(stmt)
    return result


async def list_plans_paginated(
    session: AsyncSession, query: PtPackagePlanListQuery
) -> PaginatedData[PtPackagePlan]:
    """Paginated list of plans with optional ``include_archived`` toggle (PT-02).

    Mirrors memberships.repository.list_alive: `model_construct` to skip
    Pydantic validation against the generic parameter (the SA ORM is not a
    Pydantic-compatible type and `PaginatedData[PtPackagePlan](...)` would
    raise `PydanticSchemaGenerationError` at the runtime parametrisation step).
    """
    predicates: list[Any] = []
    if not query.include_archived:
        predicates.append(PtPackagePlan.deleted_at.is_(None))

    where_clause = and_(*predicates) if predicates else None

    total_stmt = select(func.count()).select_from(PtPackagePlan)
    if where_clause is not None:
        total_stmt = total_stmt.where(where_clause)
    total = await session.scalar(total_stmt) or 0

    stmt: Select[tuple[PtPackagePlan]] = select(PtPackagePlan)
    if where_clause is not None:
        stmt = stmt.where(where_clause)
    if query.sort == PtPackagePlanSort.NAME_ASC:
        stmt = stmt.order_by(
            func.lower(PtPackagePlan.name).asc(),
            PtPackagePlan.created_at.desc(),
            PtPackagePlan.id.desc(),
        )
    else:  # CREATED_AT_DESC default
        stmt = stmt.order_by(
            PtPackagePlan.created_at.desc(),
            PtPackagePlan.id.desc(),
        )

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
    data: PtPackagePlanCreateRequest,
) -> PtPackagePlan:
    """Insert a new plan; caller owns flush + audit emit + commit (D-14)."""
    plan = PtPackagePlan(
        name=data.name,
        session_count=data.session_count,
        price_kopecks=data.price_kopecks,
        validity_days=data.validity_days,
    )
    session.add(plan)
    return plan


async def update_plan_row(
    session: AsyncSession,
    plan: PtPackagePlan,
    *,
    name: str | None,
) -> dict[str, object]:
    """Apply mutable-only updates and return ``{field: previous_value}`` for changed fields.

    Only ``name`` is mutable post-creation (D-33-07). Immutability of
    session_count / price_kopecks / validity_days is enforced by the service
    layer BEFORE this helper is invoked (via FieldImmutableError).
    """
    changed: dict[str, object] = {}
    if name is not None and name != plan.name:
        changed["name"] = plan.name
        plan.name = name
    return changed


async def soft_delete_plan(
    session: AsyncSession,
    plan: PtPackagePlan,
) -> PtPackagePlan:
    """Soft-delete: set deleted_at to now(); never DELETE the row (D-33-08)."""
    plan.deleted_at = datetime.now(tz=UTC)
    return plan


async def has_instances_for_plan(session: AsyncSession, plan_id: UUID) -> bool:
    """True iff any pt_packages row references ``plan_id`` (D-33-08 archive guard).

    Used by service.archive_pt_package_plan as the primary pre-flight check
    before flipping deleted_at. Status is irrelevant — even cancelled /
    expired / exhausted rows keep their FK pointer for audit-trail integrity
    (mirrors memberships D-06).
    """
    stmt = select(PtPackage.id).where(PtPackage.plan_id == plan_id).limit(1)
    return (await session.scalar(stmt)) is not None


# ---------------------------------------------------------------------------
# Instance helpers (PT-04..09 — Plans 33-02 / 33-03 consume; provided here so
# sibling plans need not modify repository.py during Wave 2).
# ---------------------------------------------------------------------------


async def get_pt_package(
    session: AsyncSession, pt_package_id: UUID
) -> PtPackage | None:
    """Return PtPackage by id, or None.

    NO soft-delete filter — PtPackage has no `deleted_at` column (D-33-03 /
    Phase 17 D-12 mirror). Cancelled / expired / exhausted rows are still
    returned; lifecycle is purely status-based.
    """
    stmt: Select[tuple[PtPackage]] = select(PtPackage).where(
        PtPackage.id == pt_package_id
    )
    result: PtPackage | None = await session.scalar(stmt)
    return result


async def find_active_for_client(
    session: AsyncSession, client_id: UUID
) -> PtPackage | None:
    """Return the canonical active PT-package for ``client_id`` (D-33-12 resolver).

    Consumed by:
      - service.create_pt_package — defensive pre-flight before the partial
        UNIQUE catches the race at DB layer (Plan 33-02).
      - service.resolve_active_pt_package — public resolver exported via the
        ``ActivePtPackage`` Protocol slot wired in app/main.py (Phase 34
        PT-session sale consumes via core.dependencies.resolve_active_pt_package).

    Live-window guard (WR-06 from Phase 33 review): a row whose
    ``end_date < today`` is effectively-expired even if the cron has not
    yet flipped its ``status`` to ``'expired'`` (the cron tick at 06:25
    MSK can lag the actual end-of-day by ~30 hours worst-case). This
    helper now refilters ``end_date >= today OR end_date IS NULL`` so
    Phase 34's PT-session sale will not record a session against an
    effectively-expired package. ``end_date IS NULL`` is the
    ``validity_days IS NULL`` (бессрочный) class — never time-expires
    (D-33-14).

    Single-row read; orders by created_at desc as a tiebreak in case the
    partial UNIQUE invariant is ever violated by a manual DB write (unlikely
    in v1.4 but mirrors memberships.find_active_for_client discipline).
    """
    today = datetime.now(ZoneInfo("Europe/Moscow")).date()
    stmt = (
        select(PtPackage)
        .where(
            PtPackage.client_id == client_id,
            PtPackage.status == "active",
            or_(
                PtPackage.end_date.is_(None),
                PtPackage.end_date >= today,
            ),
        )
        .order_by(PtPackage.created_at.desc())
        .limit(1)
    )
    result: PtPackage | None = await session.scalar(stmt)
    return result


async def insert_pt_package(
    session: AsyncSession,
    data: PtPackageCreateRequest,
    *,
    plan: PtPackagePlan,
    start_date: date,
    end_date: date | None,
) -> PtPackage:
    """Insert a PtPackage row. Caller MUST flush + commit (Plan 33-02 / D-33-09).

    Snapshot fields are copied from the resolved ``plan`` ORM ref so subsequent
    plan edits / archives never propagate to this row.

    Phase 38 PKG-01: ``data.trainer_id`` (optional) is persisted directly on
    the new row. NULL means "any trainer" per C-08; the bookings module's
    trainer-mismatch guard short-circuits on NULL.
    """
    pt_package = PtPackage(
        client_id=data.client_id,
        plan_id=plan.id,
        trainer_id=data.trainer_id,
        plan_name_snapshot=plan.name,
        session_count_snapshot=plan.session_count,
        price_kopecks_snapshot=plan.price_kopecks,
        validity_days_snapshot=plan.validity_days,
        sessions_remaining=plan.session_count,
        status="active",
        start_date=start_date,
        end_date=end_date,
    )
    session.add(pt_package)
    return pt_package


async def update_pt_package_status(
    session: AsyncSession,
    pt_package: PtPackage,
    *,
    status: str,
    cancellation_reason: str | None = None,
) -> PtPackage:
    """Narrow setter for lifecycle transitions (Plans 33-02 / 33-03 / Phase 34).

    Used by cancel (target='cancelled' + free-text reason), refund (target=
    'cancelled' + 'refunded' sentinel), Plan 33-02 cron expire (target=
    'expired' / no reason), and Phase 34 decrement (target='exhausted' /
    no reason). Caller owns flush + commit.
    """
    pt_package.status = status
    if cancellation_reason is not None:
        pt_package.cancellation_reason = cancellation_reason
    return pt_package


async def list_pt_packages_paginated(
    session: AsyncSession, query: PtPackageListQuery
) -> PaginatedData[PtPackage]:
    """Paginated PT-package list with optional client_id + status filters.

    Mirrors memberships.list_memberships — `model_construct` to skip Pydantic
    validation against the SA ORM generic parameter.
    """
    predicates: list[Any] = []
    if query.client_id is not None:
        predicates.append(PtPackage.client_id == query.client_id)
    if query.status is not None:
        predicates.append(PtPackage.status == query.status.value)

    where_clause = and_(*predicates) if predicates else None

    total_stmt = select(func.count()).select_from(PtPackage)
    if where_clause is not None:
        total_stmt = total_stmt.where(where_clause)
    total = await session.scalar(total_stmt) or 0

    stmt: Select[tuple[PtPackage]] = select(PtPackage)
    if where_clause is not None:
        stmt = stmt.where(where_clause)
    if query.sort == PtPackageListSort.END_DATE_DESC:
        stmt = stmt.order_by(
            PtPackage.end_date.desc(),
            PtPackage.created_at.desc(),
            PtPackage.id.desc(),
        )
    elif query.sort == PtPackageListSort.START_DATE_DESC:
        stmt = stmt.order_by(
            PtPackage.start_date.desc(),
            PtPackage.created_at.desc(),
            PtPackage.id.desc(),
        )
    else:  # CREATED_AT_DESC default
        stmt = stmt.order_by(
            PtPackage.created_at.desc(),
            PtPackage.id.desc(),
        )

    offset = (query.page - 1) * query.page_size
    stmt = stmt.offset(offset).limit(query.page_size)
    rows = (await session.scalars(stmt)).all()
    return PaginatedData.model_construct(
        items=list(rows),
        total=total,
        page=query.page,
        page_size=query.page_size,
    )


# ---------------------------------------------------------------------------
# ARQ cron helper — bulk-expire (Plan 33-02 / D-33-13)
# ---------------------------------------------------------------------------


async def expire_due_pt_packages_bulk_returning(
    session: AsyncSession, today: date
) -> Sequence[Row[tuple[UUID, UUID, date | None]]]:
    """Bulk-flip overdue active PT-packages to expired (D-33-13).

    Single-statement
        UPDATE pt_packages SET status='expired'
        WHERE status='active' AND end_date IS NOT NULL AND end_date < :today
        RETURNING id, client_id, end_date

    Caller (worker entry via ``_expire_due_pt_packages`` in service.py) owns
    flush + commit; this helper issues no flush, no commit.

    Status filter is the SQL-level idempotency gate (re-run on the same day
    skips rows already flipped to 'expired'). NULL end_date rows are excluded
    (D-33-14 — бессрочные packages never expire by time).

    Returns rows from RETURNING for per-row audit emission (pt_package_expired).
    """
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
