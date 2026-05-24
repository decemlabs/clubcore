"""Reports service — read-only aggregator (Phase 55 REV-01..05, CLR-01..04, VIS-R-01..04).

Read-only aggregator role: orchestrates calls to repository.py which reads
cross-module data via raw SQL ``text()`` SELECTs (D-54-08 / D-49-03 precedent).

INVARIANTS (locked):
- ZERO INSERT / UPDATE / DELETE on any business table.
- SVC001 commit-gate does NOT apply (no write paths, no ``session.commit``).
- Never imports another module's ORM model — reads go through repository.py
  raw SQL readers exclusively.
"""

from __future__ import annotations

from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ValidationAppError
from app.modules.reports import repository
from app.modules.reports.constants import GRAIN_MONTH
from app.modules.reports.schemas import (
    RevenueBucket,
    RevenueBucketByMethod,
    RevenueBucketBySubjectKind,
    RevenueReportQuery,
    RevenueReportResponse,
)


class ReportRangeTooLargeError(ValidationAppError):
    """Date range exceeds 366-day cap (D-06). Code LOCKED per CONTEXT.md."""

    code = "report_range_too_large"
    status_code = 422


def _validate_date_range(from_date: date, to_date: date) -> None:
    """Raise ValidationAppError when range is invalid.

    Raises:
        ValidationAppError: when to_date < from_date (D-05).
        ReportRangeTooLargeError: when (to_date - from_date).days > 366 (D-06).
    """
    if to_date < from_date:
        raise ValidationAppError("to must be >= from")
    if (to_date - from_date).days > 366:
        raise ReportRangeTooLargeError("Date range exceeds 366-day limit")


def _pivot_revenue_buckets(
    rows: list[dict[str, object]],
    query: RevenueReportQuery,
) -> RevenueReportResponse:
    """Pivot raw aggregate rows into the nested RevenueReportResponse shape.

    Row columns: period (date), method (str), subject_kind (str), total_kopecks (int).

    Pivot logic (D-01):
    - net_kopecks accumulates signed total_kopecks for ALL rows in the period,
      including refunds (subject_kind='refund', negative amount). This ensures
      REV-04: sale + same-period refund nets to zero.
    - by_method accumulates by method ('cash' / 'online') for ALL rows.
    - by_subject_kind accumulates ONLY for 'membership' and 'pt_package' rows;
      refund rows are excluded from the breakdown (D-01).
    """
    # Use dict to maintain insertion order (Python 3.7+); order follows SQL ORDER BY period.
    buckets: dict[str, tuple[int, RevenueBucketByMethod, RevenueBucketBySubjectKind]] = {}

    for row in rows:
        period_raw = row["period"]
        # period_raw is a Python date object from Postgres (both day + month date_trunc).
        # day -> "YYYY-MM-DD"; month date_trunc returns month-start date -> "YYYY-MM".
        period_str = (
            str(period_raw)[:7] if query.group_by == GRAIN_MONTH else str(period_raw)
        )

        if period_str not in buckets:
            buckets[period_str] = (
                0,
                RevenueBucketByMethod(),
                RevenueBucketBySubjectKind(),
            )

        net, by_method, by_subject_kind = buckets[period_str]
        total = int(row["total_kopecks"])  # type: ignore[call-overload]
        net += total

        method = str(row["method"])
        if method == "cash":
            by_method = RevenueBucketByMethod(
                cash=by_method.cash + total,
                online=by_method.online,
            )
        elif method == "online":
            by_method = RevenueBucketByMethod(
                cash=by_method.cash,
                online=by_method.online + total,
            )

        subject_kind = str(row["subject_kind"])
        if subject_kind == "membership":
            by_subject_kind = RevenueBucketBySubjectKind(
                membership=by_subject_kind.membership + total,
                pt_package=by_subject_kind.pt_package,
            )
        elif subject_kind == "pt_package":
            by_subject_kind = RevenueBucketBySubjectKind(
                membership=by_subject_kind.membership,
                pt_package=by_subject_kind.pt_package + total,
            )
        # 'refund' subject_kind: fold into net only, skip by_subject_kind (D-01)

        buckets[period_str] = (net, by_method, by_subject_kind)

    bucket_list = [
        RevenueBucket(
            period=period_str,
            net_kopecks=net,
            by_method=by_method,
            by_subject_kind=by_subject_kind,
        )
        for period_str, (net, by_method, by_subject_kind) in buckets.items()
    ]

    return RevenueReportResponse(
        buckets=bucket_list,
        from_date=query.from_date,
        to_date=query.to_date,
        group_by=query.group_by,
    )


async def get_revenue_report(
    session: AsyncSession,
    query: RevenueReportQuery,
) -> RevenueReportResponse:
    """Aggregate payments ledger by period bucket (REV-01..05).

    Read-only: NO session.commit(), NO session.flush().
    """
    _validate_date_range(query.from_date, query.to_date)
    rows = await repository.fetch_revenue_buckets(session, query)
    return _pivot_revenue_buckets(rows, query)
