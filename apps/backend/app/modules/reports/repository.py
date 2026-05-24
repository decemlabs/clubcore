"""Reports repository — raw-SQL read aggregator (Phase 55 REV-01..05, CLR-01..04, VIS-R-01..04).

CROSS-MODULE READ DISCIPLINE (D-54-08 / Phase 49 D-49-03 precedent):
  - ``from sqlalchemy import text`` — NEVER import another module's ORM model.
  - Bind params via ``:name`` placeholders + a dict; cast UUIDs to ``str``.
  - ``.mappings().all()`` for aggregate/list reads.
  - ``.mappings().one()`` for scalar count reads.
  - Each reader documents verified columns + source file:line of the foreign table.

This discipline means zero new ``ignore_imports`` edges in ``.importlinter``
while reading across ``payments``, ``memberships``, ``clients``, ``visits``,
and ``audit_log`` tables.

INVARIANTS:
  - ZERO INSERT / UPDATE / DELETE in this file.
  - No ORM model imports from other modules.
"""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.reports.constants import GRAIN_DAY
from app.modules.reports.schemas import RevenueReportQuery

__all__ = ("fetch_revenue_buckets",)


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
