"""CSV export helper — BOM + RFC-4180 + StreamingResponse (Phase 56 EXP-01..04, D-11..12).

Single source of truth for:
  - UTF-8 BOM first yield (U+FEFF) for Excel Cyrillic detection (EXP-04).
  - stdlib csv.writer with QUOTE_MINIMAL + ',' delimiter + '\\r\\n' terminator (RFC 4180).
  - StreamingResponse with media_type='text/csv; charset=utf-8' +
    Content-Disposition: attachment; filename='<name>.csv'.
  - Money formatting: kopecks -> rubles as '%.2f' (period decimal, no grouping) (D-13).
  - Date formatting: datetime -> 'YYYY-MM-DD HH:MM:SS' MSK (D-14).

No try/except in this module — errors bubble to the registered AppError handler.
"""

from __future__ import annotations

import csv
import io
from collections.abc import AsyncIterator, Iterator
from datetime import datetime, timedelta, timezone

from fastapi.responses import StreamingResponse

# MSK = UTC+3, no DST (permanent standard time since 2014)
_MSK = timezone(timedelta(hours=3), name="MSK")

# UTF-8 BOM: U+FEFF — written as Python escape (NOT a literal glyph).
# A literal U+FEFF glyph in source is a defect (D-11, SC#4, EXP-04).
BOM = "\ufeff"


def _row_to_csv_line(row: list[object]) -> str:
    """Write a single row to a CSV string via csv.writer (RFC-4180 escaping).

    Uses the 'excel' dialect: comma delimiter, \\r\\n line terminator, QUOTE_MINIMAL.
    Fields containing comma, double-quote, or newline are RFC-4180 quote-escaped.

    Args:
        row: List of cell values (will be str()-coerced by csv.writer).

    Returns:
        CSV-encoded line ending with '\\r\\n'.
    """
    buf = io.StringIO()
    writer = csv.writer(buf, dialect="excel")  # excel: comma + \r\n + QUOTE_MINIMAL
    writer.writerow(row)
    return buf.getvalue()


def make_csv_streaming_response(
    rows: Iterator[list[object]],
    headers: tuple[str, ...],
    filename: str,
) -> StreamingResponse:
    """Wrap a sync row-iterator in a StreamingResponse with BOM + header row first.

    Generator yields:
      1. UTF-8 BOM chunk (U+FEFF) — Excel Cyrillic auto-detect (EXP-04).
      2. Header row as RFC-4180 line.
      3. Each data row as RFC-4180 line.

    Args:
        rows: Sync iterator of cell lists (e.g. from a list-backed generator).
        headers: Column name tuple written as the first data row after BOM.
        filename: Value for Content-Disposition attachment filename.

    Returns:
        StreamingResponse with media_type='text/csv; charset=utf-8'.
    """

    def _generate() -> Iterator[str]:
        yield BOM
        yield _row_to_csv_line(list(headers))
        for row in rows:
            yield _row_to_csv_line(row)

    return StreamingResponse(
        _generate(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def make_async_csv_streaming_response(
    rows: AsyncIterator[list[object]],
    headers: tuple[str, ...],
    filename: str,
) -> StreamingResponse:
    """Wrap an async row-iterator in a StreamingResponse (for audit-log CSV, D-16).

    Async generator yields BOM + header row + each data row, same contract
    as make_csv_streaming_response but consuming an async iterator so the
    database cursor is streamed row-by-row without full materialisation.

    Args:
        rows: Async iterator of cell lists (e.g. stream_audit_log_rows generator).
        headers: Column name tuple written as the first data row after BOM.
        filename: Value for Content-Disposition attachment filename.

    Returns:
        StreamingResponse with media_type='text/csv; charset=utf-8'.
    """

    async def _generate() -> AsyncIterator[str]:
        yield BOM
        yield _row_to_csv_line(list(headers))
        async for row in rows:
            yield _row_to_csv_line(row)

    return StreamingResponse(
        _generate(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def format_kopecks_as_rubles(kopecks: int) -> str:
    """Format signed kopecks as rubles with 2 decimals, period separator (D-13).

    Uses period as decimal separator and no thousands grouping — keeps the field
    delimiter-safe in RFC-4180 CSV (SC#4, D-13).

    Examples:
        >>> format_kopecks_as_rubles(250000)
        '2500.00'
        >>> format_kopecks_as_rubles(-100)
        '-1.00'
        >>> format_kopecks_as_rubles(0)
        '0.00'
    """
    return f"{kopecks / 100:.2f}"


def format_datetime_msk(dt: datetime) -> str:
    """Convert an aware datetime to MSK and format as 'YYYY-MM-DD HH:MM:SS' (D-14).

    No offset suffix — human-readable for Excel. MSK = UTC+3 (no DST).

    Args:
        dt: Timezone-aware datetime (any tz; typically UTC from the DB).

    Returns:
        String in 'YYYY-MM-DD HH:MM:SS' format, Europe/Moscow local time.

    Example:
        >>> from datetime import timezone
        >>> format_datetime_msk(datetime(2026, 3, 1, 0, 30, tzinfo=timezone.utc))
        '2026-03-01 03:30:00'
    """
    msk_dt = dt.astimezone(_MSK)
    return msk_dt.strftime("%Y-%m-%d %H:%M:%S")
