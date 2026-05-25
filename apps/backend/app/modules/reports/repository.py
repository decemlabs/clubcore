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

from collections.abc import AsyncIterator
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
    "fetch_trainer_usage",
    "fetch_visits_daily",
    "fetch_visits_hourly",
    "stream_audit_log_rows",
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


async def fetch_trainer_usage(
    session: AsyncSession,
    from_date: date,
    to_date: date,
) -> list[dict[str, object]]:
    """Per-trainer aggregated load, revenue, and payroll for [from_date, to_date] MSK.

    CROSS-MODULE READ — raw SQL text() only; ZERO ORM imports from other modules.
    Verified columns per module (D-54-08 / D-60-01 / D-60-02):

    pt_sessions (apps/backend/app/modules/pt_sessions/models.py:52-111):
      - trainer_id            UUID NOT NULL (FK->trainers)
      - pt_package_id         UUID NOT NULL (FK->pt_packages)
      - performed_at          DateTime(timezone=True) NOT NULL -- period filter column
      - cancelled_at          DateTime(timezone=True) nullable -- NULL = conducted session
      - booking_id            UUID nullable (FK->bookings; NULL = walk-in session, D-38-04)
      - trainer_name_snapshot Text NOT NULL (B-05 snapshot at INSERT time)

    pt_packages (apps/backend/app/modules/pt_packages/models.py:104-187):
      - id                    UUID PK
      - client_id             UUID NOT NULL (FK->clients)
      - trainer_id            UUID nullable (FK->trainers ON DELETE RESTRICT;
                              D-58-21 assigned-at-sale)

    bookings (apps/backend/app/modules/bookings/models.py):
      - id                    UUID PK
      - slot_id               UUID NOT NULL (FK->trainer_availability_slots)

    trainer_availability_slots (apps/backend/app/modules/schedule/models.py:64-152):
      - id                    UUID PK
      - trainer_id            UUID NOT NULL (FK->trainers)
      - start_time            DateTime(timezone=True) NOT NULL -- slot period filter column
      - end_time              DateTime(timezone=True) NOT NULL
      - status                String(16) CHECK IN ('active','booked','cancelled')

    payments (apps/backend/app/modules/payments/models.py:44-121):
      - subject_id            UUID NOT NULL
      - subject_kind          Text NOT NULL ('membership' | 'pt_package' | 'refund')
      - amount_kopecks        Integer NOT NULL signed (positive for sales)
      - received_at           DateTime(timezone=True) NOT NULL  <- sole temporal column
                              (D-32-01..04)

    trainer_payroll_accruals (apps/backend/app/modules/payroll/models.py:108-256):
      - trainer_id            UUID NOT NULL (FK->trainers)
      - period_start          Date NOT NULL (inclusive MSK, D-58-05)
      - period_end            Date NOT NULL (inclusive MSK, D-58-05)
      - accrual_kopecks       Integer NOT NULL signed (negative for clawback rows, D-58-03)
      - status                Text ('pending' | 'paid')

    trainers (apps/backend/app/modules/trainers/models.py:23-43):
      - id                    UUID PK
      - full_name             Text NOT NULL
      - is_active             Boolean NOT NULL  -- NOT FILTERED (PITFALL 11: deactivated trainers
                              with historical sessions MUST appear in the report)

    Security (T-60-04): SQL template is a compile-time constant string.
    All user values flow through :from_date / :to_date bind params only.
    No f-string interpolation of user input.

    Design notes:
    - total_hours: derived from booked slot (end_time - start_time) via the
      pt_sessions->bookings->trainer_availability_slots chain (D-60-04 / D-38-04
      1:1 link). Walk-in sessions (booking_id IS NULL) contribute 0.0 hours.
    - utilization_pct: NULL when no active|booked slots exist in the period
      (REQUIREMENTS RPT-01 verbatim). Cancelled slots excluded from BOTH numerator
      AND denominator (D-60-06).
    - revenue attribution: pt_packages.trainer_id (assigned-at-sale, D-58-21),
      NOT pt_sessions.trainer_id (PITFALL 6 -- see inline SQL comment).
    - payroll overlap: accruals overlap the window when
      period_start <= to_date AND period_end >= from_date
      (D-60-05); signed SUM nets clawbacks automatically (D-58-03).
    - Result rows ordered session_count DESC, full_name ASC, t.id ASC for
      deterministic tie-breaking in golden tests.
    """
    rows = (
        await session.execute(
            text(
                """
WITH session_agg AS (
    -- conducting-trainer aggregation; period filter on performed_at MSK date (PITFALL 12)
    SELECT
        ps.trainer_id,
        COUNT(*) FILTER (WHERE ps.cancelled_at IS NULL)          AS session_count,
        COUNT(*) FILTER (WHERE ps.cancelled_at IS NOT NULL)      AS cancelled_session_count,
        COUNT(DISTINCT pkg.client_id)
            FILTER (WHERE ps.cancelled_at IS NULL)               AS unique_client_count,
        COALESCE(SUM(
            EXTRACT(EPOCH FROM (s.end_time - s.start_time)) / 3600.0
        ) FILTER (WHERE ps.cancelled_at IS NULL), 0.0)           AS total_hours
    FROM pt_sessions ps
    LEFT JOIN pt_packages pkg ON pkg.id = ps.pt_package_id
    LEFT JOIN bookings b      ON b.id   = ps.booking_id
    LEFT JOIN trainer_availability_slots s ON s.id = b.slot_id
    WHERE (ps.performed_at AT TIME ZONE 'Europe/Moscow')::date
          BETWEEN :from_date AND :to_date
    GROUP BY ps.trainer_id
),
slot_agg AS (
    -- published capacity and booking fill for utilization_pct (D-60-06)
    -- cancelled slots excluded from both numerator AND denominator
    SELECT
        trainer_id,
        COALESCE(SUM(
            EXTRACT(EPOCH FROM (end_time - start_time)) / 3600.0
        ) FILTER (WHERE status IN ('active', 'booked')), 0.0)    AS published_hours,
        COALESCE(SUM(
            EXTRACT(EPOCH FROM (end_time - start_time)) / 3600.0
        ) FILTER (WHERE status = 'booked'), 0.0)                 AS booked_hours,
        COUNT(*) FILTER (WHERE status IN ('active', 'booked'))   AS published_slot_count
    FROM trainer_availability_slots
    WHERE (start_time AT TIME ZONE 'Europe/Moscow')::date
          BETWEEN :from_date AND :to_date
    GROUP BY trainer_id
),
revenue_agg AS (
    -- attribution: assigned-at-sale (D-58-21) -- use pkg.trainer_id, NOT ps.trainer_id (PITFALL 6)
    SELECT
        pkg.trainer_id,
        COALESCE(SUM(p.amount_kopecks) FILTER (
            WHERE p.subject_kind = 'pt_package' AND p.amount_kopecks > 0
        ), 0)                                                     AS revenue_kopecks
    FROM pt_packages pkg
    JOIN payments p ON p.subject_id = pkg.id
                   AND p.subject_kind = 'pt_package'
    WHERE pkg.trainer_id IS NOT NULL
      AND (p.received_at AT TIME ZONE 'Europe/Moscow')::date
          BETWEEN :from_date AND :to_date
    GROUP BY pkg.trainer_id
),
payroll_agg AS (
    -- period overlap (D-60-05): accruals straddling the window included in full (no proration)
    -- signed SUM nets clawback rows automatically (D-58-03)
    SELECT
        trainer_id,
        COALESCE(SUM(accrual_kopecks), 0)                        AS total_accrued_kopecks,
        COALESCE(SUM(accrual_kopecks) FILTER (WHERE status = 'paid'), 0)
                                                                 AS total_paid_kopecks
    FROM trainer_payroll_accruals
    WHERE period_start <= :to_date AND period_end >= :from_date
    GROUP BY trainer_id
)
SELECT
    t.id                                                         AS trainer_id,
    t.full_name                                                  AS trainer_name_snapshot,
    COALESCE(sa.session_count, 0)                               AS session_count,
    COALESCE(sa.cancelled_session_count, 0)                     AS cancelled_session_count,
    COALESCE(sa.total_hours, 0.0)                               AS total_hours,
    COALESCE(sa.unique_client_count, 0)                         AS unique_client_count,
    CASE
        WHEN COALESCE(sla.published_slot_count, 0) = 0 THEN NULL
        ELSE (COALESCE(sla.booked_hours, 0.0)
              / NULLIF(sla.published_hours, 0.0)) * 100.0
    END                                                          AS utilization_pct,
    COALESCE(ra.revenue_kopecks, 0)                             AS revenue_kopecks,
    CASE
        WHEN COALESCE(sa.session_count, 0) = 0 THEN NULL
        ELSE COALESCE(ra.revenue_kopecks, 0) / sa.session_count
    END                                                          AS avg_revenue_per_session,
    COALESCE(pa.total_accrued_kopecks, 0)                       AS total_accrued_kopecks,
    COALESCE(pa.total_paid_kopecks, 0)                          AS total_paid_kopecks
-- PITFALL 11: NO is_active filter -- deactivated trainers with historical sessions appear
FROM trainers t
LEFT JOIN session_agg sa  ON sa.trainer_id = t.id
LEFT JOIN slot_agg sla    ON sla.trainer_id = t.id
LEFT JOIN revenue_agg ra  ON ra.trainer_id  = t.id
LEFT JOIN payroll_agg pa  ON pa.trainer_id  = t.id
ORDER BY session_count DESC, t.full_name ASC, t.id ASC
"""
            ),
            {"from_date": from_date, "to_date": to_date},
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
        # Case-insensitive substring match (AUD-02). ORM .ilike() emits a parameterized
        # bind (no SQL injection), but LIKE metacharacters in user input would otherwise
        # corrupt filter semantics (WR-01): a bare '%' matches every row, '_' any char.
        # Escape \, %, _ and declare the escape char so the substring is matched literally.
        escaped = (
            query.actor_email_snapshot.replace("\\", "\\\\")
            .replace("%", "\\%")
            .replace("_", "\\_")
        )
        like_pattern = f"%{escaped}%"
        predicates.append(AuditLog.actor_email_snapshot.ilike(like_pattern, escape="\\"))

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


async def stream_audit_log_rows(
    session: AsyncSession,
    query: AuditLogQuery,
    *,
    from_: date | None = None,
    to: date | None = None,
) -> AsyncIterator[AuditLog]:
    """Yield AuditLog rows one-by-one for CSV streaming (EXP-02, D-16).

    No offset/limit — streams ALL rows matching the filters so CSV export
    can produce an unbounded file without materialising the full result set
    in memory. Memory is bounded by AsyncSession.stream_scalars() cursor
    semantics (row-by-row server-side streaming).

    Ordering: created_at DESC, id DESC — consistent with the JSON paginated
    listing (AUD-06) so CSV and JSON render rows in the same stable order.

    from_/to are keyword-only args (mirroring fetch_audit_log_page from Plan 01;
    the query model has no from_/to fields — they arrive as route-level params).

    INVARIANT: ZERO INSERT / UPDATE / DELETE. Read-only.
    """
    predicates = _build_audit_predicates(query, from_=from_, to=to)
    stmt = (
        select(AuditLog)
        .where(and_(true(), *predicates))
        .order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
    )
    result = await session.stream_scalars(stmt)
    async for row in result:
        yield row
