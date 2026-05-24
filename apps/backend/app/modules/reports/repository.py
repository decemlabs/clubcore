"""Reports repository — raw-SQL read aggregator + ORM audit-log reader.

Phase 55: REV-01..05, CLR-01..04, VIS-R-01..04.
Phase 56: AUD-01..06 (ORM read path for audit_log).

CROSS-MODULE READ DISCIPLINE (D-54-08 / Phase 49 D-49-03 precedent):
  - ``from sqlalchemy import text`` — NEVER import another module's ORM model.
  - Bind params via ``:name`` placeholders + a dict; cast UUIDs to ``str``.
  - ``.mappings().all()`` for aggregate/list reads.
  - ``.mappings().one()`` for scalar count reads.
  - Each reader documents verified columns + source file:line of the foreign table.

This discipline means zero new ``ignore_imports`` edges in ``.importlinter``
while reading across ``payments``, ``memberships``, ``clients``, ``visits``,
and ``audit_log`` tables.

EXCEPTION — AuditLog ORM import (app.core.audit_models):
  ``app.core`` is NOT a cross-module boundary: audit_models lives in the core
  package which is a free import target for all modules (only module↔module ORM
  imports are banned by import-linter). Importing AuditLog from app.core is NOT
  a violation. See D-04 (Phase 56 CONTEXT.md).

INVARIANTS:
  - ZERO INSERT / UPDATE / DELETE in this file.
  - ORM model imports from other modules (app.modules.*): FORBIDDEN.
  - ORM model imports from app.core.*: ALLOWED (see exception above).
"""

from __future__ import annotations

from datetime import date
from typing import Any

from sqlalchemy import and_, cast, func, select, text, true
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.types import Date

from app.core.audit_models import AuditLog  # core is free import target (D-04 / Phase 56)
from app.core.pagination import PaginatedData
from app.modules.reports.constants import GRAIN_DAY
from app.modules.reports.schemas import AuditLogQuery, RevenueReportQuery

__all__ = (
    "fetch_active_memberships_count",
    "fetch_audit_log_page",
    "fetch_expiring_memberships_count",
    "fetch_new_clients_count",
    "fetch_revenue_buckets",
    "fetch_visits_daily",
    "fetch_visits_hourly",
)


async def fetch_revenue_buckets(
    session: AsyncSession,
    query: RevenueReportQuery,
) -> list[dict[str, object]]:
    """Aggregate payments by period bucket, method, subject_kind.

    CROSS-MODULE READ — raw SQL text() only; NO ORM import of Payment.
    Verified columns (apps/backend/app/modules/payments/models.py:52-64):
      - amount_kopecks  Integer (signed; negative for subject_kind='refund')
      - method          Text ('cash' | 'online')
      - subject_kind    Text ('membership' | 'pt_package' | 'refund')
      - received_at     DateTime(timezone=True)  <- sole temporal column

    Security (T-55-02): period_expr is chosen from an internal branch keyed on
    the validated Literal["day","month"] enum — NEVER from a raw user string.
    All user values (from_date, to_date) go through :from_date / :to_date bind
    params only. No f-string interpolation of user input.
    """
    period_expr = (
        "(received_at AT TIME ZONE 'Europe/Moscow')::date"
        if query.group_by == GRAIN_DAY
        else "date_trunc('month', (received_at AT TIME ZONE 'Europe/Moscow')::date)"
    )
    rows = (
        await session.execute(
            text(
                f"SELECT {period_expr} AS period, method, subject_kind, "  # noqa: S608 — period_expr is chosen from internal literals (GRAIN_DAY/GRAIN_MONTH), never from user input
                "SUM(amount_kopecks) AS total_kopecks "
                "FROM payments "
                "WHERE (received_at AT TIME ZONE 'Europe/Moscow')::date "
                "    BETWEEN :from_date AND :to_date "
                "GROUP BY period, method, subject_kind "
                "ORDER BY period"
            ),
            {"from_date": query.from_date, "to_date": query.to_date},
        )
    ).mappings().all()
    return [dict(r) for r in rows]


async def fetch_active_memberships_count(session: AsyncSession) -> int:
    """Count active memberships for live clients (CLR-01).

    CROSS-MODULE READ — raw SQL text() only; NO ORM import of Membership or Client.
    Verified columns (apps/backend/app/modules/memberships/models.py:134):
      - status  String(16) ('active' | 'expired' | 'cancelled' | 'frozen')
    Verified columns (apps/backend/app/modules/clients/models.py:58):
      - deleted_at  nullable DateTime(timezone=True) (SoftDeleteMixin)

    "Active" = membership.status = 'active' AND the owning client is not soft-deleted.
    This is a point-in-time ("as of now") count — ignores the report date range (D-05).
    """
    row = (
        await session.execute(
            text(
                "SELECT COUNT(*) AS cnt FROM memberships m "
                "JOIN clients c ON c.id = m.client_id "
                "WHERE m.status = 'active' AND c.deleted_at IS NULL"
            )
        )
    ).mappings().one()
    return int(row["cnt"])


async def fetch_expiring_memberships_count(session: AsyncSession, within: int) -> int:
    """Count active memberships expiring within N days (CLR-02).

    CROSS-MODULE READ — raw SQL text() only; NO ORM imports.
    Verified columns (apps/backend/app/modules/memberships/models.py:133):
      - end_date  Date (inclusive)
    Verified columns (apps/backend/app/modules/clients/models.py:58):
      - deleted_at  nullable DateTime(timezone=True) (SoftDeleteMixin)

    Window: end_date BETWEEN today_msk AND today_msk + within (inclusive bounds).
    `within` is a service-layer-validated int in 1..30 — safe to bind (T-55-06).
    """
    row = (
        await session.execute(
            text(
                "SELECT COUNT(*) AS cnt FROM memberships m "
                "JOIN clients c ON c.id = m.client_id "
                "WHERE m.status = 'active' "
                "  AND c.deleted_at IS NULL "
                "  AND m.end_date BETWEEN "
                "    (now() AT TIME ZONE 'Europe/Moscow')::date "
                "    AND (now() AT TIME ZONE 'Europe/Moscow')::date "
                "    + CAST(:within AS integer)"
            ),
            {"within": within},
        )
    ).mappings().one()
    return int(row["cnt"])


async def fetch_new_clients_count(
    session: AsyncSession,
    from_date: date,
    to_date: date,
) -> int:
    """Count clients created within [from_date, to_date] MSK, excluding soft-deleted (CLR-03/04).

    CROSS-MODULE READ — raw SQL text() only; NO ORM import of Client.
    Verified columns (apps/backend/app/modules/clients/models.py:58-120):
      - created_at  DateTime(timezone=True) (TimestampMixin)
      - deleted_at  nullable DateTime(timezone=True) (SoftDeleteMixin — CLR-04)

    Bounds are inclusive MSK dates (D-04). Soft-deleted clients excluded (CLR-04).
    """
    row = (
        await session.execute(
            text(
                "SELECT COUNT(*) AS cnt FROM clients "
                "WHERE deleted_at IS NULL "
                "  AND (created_at AT TIME ZONE 'Europe/Moscow')::date "
                "    BETWEEN :from_date AND :to_date"
            ),
            {"from_date": from_date, "to_date": to_date},
        )
    ).mappings().one()
    return int(row["cnt"])


async def fetch_visits_daily(
    session: AsyncSession,
    from_date: date,
    to_date: date,
) -> list[dict[str, object]]:
    """Daily visit counts grouped by gym_date (VIS-R-01, VIS-R-04).

    CROSS-MODULE READ — raw SQL text() only; NO ORM import of Visit.
    Verified columns (apps/backend/app/modules/visits/models.py:77-84):
      - gym_date      Date STORED GENERATED (checked_in_at AT TIME ZONE 'Europe/Moscow')::date

    Filter gym_date directly — no secondary TZ conversion needed (D-04, VIS-R-04).
    Sparse buckets: only dates with visits appear (D-08).
    """
    rows = (
        await session.execute(
            text(
                "SELECT gym_date AS date, COUNT(*) AS count "
                "FROM visits "
                "WHERE gym_date BETWEEN :from_date AND :to_date "
                "GROUP BY gym_date ORDER BY gym_date"
            ),
            {"from_date": from_date, "to_date": to_date},
        )
    ).mappings().all()
    return [dict(r) for r in rows]


async def fetch_visits_hourly(
    session: AsyncSession,
    from_date: date,
    to_date: date,
) -> list[dict[str, object]]:
    """Hour-of-day visit distribution (Europe/Moscow) across the full range (VIS-R-02).

    CROSS-MODULE READ — raw SQL text() only; NO ORM import of Visit.
    Verified columns (apps/backend/app/modules/visits/models.py:72-84):
      - checked_in_at  DateTime(timezone=True) — raw timestamptz; used for hour extraction
      - gym_date       Date STORED GENERATED — used as range filter (VIS-R-04)

    Aggregated across all days in the range for peak-hour analysis.
    Sparse buckets: only hours with visits appear (D-08).
    """
    rows = (
        await session.execute(
            text(
                "SELECT "
                "EXTRACT(HOUR FROM checked_in_at AT TIME ZONE 'Europe/Moscow')::int AS hour, "
                "COUNT(*) AS count "
                "FROM visits "
                "WHERE gym_date BETWEEN :from_date AND :to_date "
                "GROUP BY hour ORDER BY hour"
            ),
            {"from_date": from_date, "to_date": to_date},
        )
    ).mappings().all()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Audit-log ORM read path (Phase 56 AUD-01..06)
# ---------------------------------------------------------------------------


def _build_audit_predicates(
    query: AuditLogQuery,
    *,
    from_: date | None = None,
    to: date | None = None,
) -> list[Any]:
    """Build SQLAlchemy predicate list for audit_log filtering (D-05, D-06).

    All filter values flow through ORM column ops (==, .ilike(), cast/func.timezone)
    which emit parameterized binds — no f-string interpolation into raw SQL (T-56-02).

    Args:
        query: Non-date filters (actorUserId, actorEmailSnapshot, resourceType, action).
        from_: Inclusive MSK day lower bound (keyword-only; NOT a query model field).
        to: Inclusive MSK day upper bound (keyword-only; NOT a query model field).
    """
    predicates: list[Any] = []

    if query.actor_user_id is not None:
        predicates.append(AuditLog.actor_user_id == query.actor_user_id)

    if query.actor_email_snapshot is not None:
        # Case-insensitive substring match (AUD-02). ORM .ilike() emits parameterized bind.
        like_pattern = f"%{query.actor_email_snapshot}%"
        predicates.append(AuditLog.actor_email_snapshot.ilike(like_pattern))

    if query.resource_type is not None:
        predicates.append(AuditLog.resource_type == query.resource_type)

    if query.action is not None:
        predicates.append(AuditLog.action == query.action)

    if from_ is not None or to is not None:
        # D-06: inclusive MSK day bounds on created_at via AT TIME ZONE conversion.
        msk_date = cast(func.timezone("Europe/Moscow", AuditLog.created_at), Date)
        if from_ is not None:
            predicates.append(msk_date >= from_)
        if to is not None:
            predicates.append(msk_date <= to)

    return predicates


async def fetch_audit_log_page(
    session: AsyncSession,
    query: AuditLogQuery,
    *,
    from_: date | None = None,
    to: date | None = None,
) -> PaginatedData[AuditLog]:
    """Keyset-paginated audit-log listing via ORM select (AUD-01, AUD-06, D-04, D-08).

    Ordering is always created_at DESC, id DESC — covers ix_audit_log_created_at
    composite index for stable pagination under concurrent inserts (SC#3, D-08).

    from_/to are keyword-only args (not model fields — see AuditLogQuery docstring).

    Returns PaginatedData.model_construct with ORM AuditLog rows in items
    (conversion to AuditLogItem happens in the service layer).

    INVARIANT: ZERO INSERT / UPDATE / DELETE. Read-only.
    """
    predicates = _build_audit_predicates(query, from_=from_, to=to)

    # COUNT with the same predicates (no ORDER/LIMIT).
    # Use and_(true(), *predicates) to avoid SADeprecationWarning when predicates is empty.
    total_stmt = (
        select(func.count()).select_from(AuditLog).where(and_(true(), *predicates))
    )
    total: int = (await session.scalar(total_stmt)) or 0

    # List with keyset ordering and offset/limit.
    offset = (query.page - 1) * query.page_size
    list_stmt = (
        select(AuditLog)
        .where(and_(true(), *predicates))
        .order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
        .offset(offset)
        .limit(query.page_size)
    )
    rows = (await session.scalars(list_stmt)).all()

    return PaginatedData.model_construct(
        items=list(rows),
        total=total,
        page=query.page,
        page_size=query.page_size,
    )
