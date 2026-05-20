"""Russian-locale formatting helpers for backend email rendering.

Phase 45 D-45-17 / NOTIFY-12 — single canonical implementation of NBSP-safe
RUB formatting + Russian long-form datetime rendering. Plans 45-09 and 45-10
import from this module so the receipt-render contract has NO per-orchestrator
divergence. Mirrors the v1 frontend ``formatMoney`` semantics
(frontend/src/shared/lib/money.ts) for the backend's Python receipt path.

Pure functions — no I/O, no DB.
"""

from __future__ import annotations

from datetime import datetime
from typing import Final
from zoneinfo import ZoneInfo

_MSK: Final[ZoneInfo] = ZoneInfo("Europe/Moscow")
_NBSP: Final[str] = " "
_RU_MONTHS_GEN: Final[tuple[str, ...]] = (
    "января",  # noqa: RUF001 — Cyrillic genitive months (D-45-17)
    "февраля",  # noqa: RUF001
    "марта",  # noqa: RUF001
    "апреля",  # noqa: RUF001
    "мая",  # noqa: RUF001
    "июня",  # noqa: RUF001
    "июля",  # noqa: RUF001
    "августа",  # noqa: RUF001
    "сентября",  # noqa: RUF001
    "октября",  # noqa: RUF001
    "ноября",  # noqa: RUF001
    "декабря",  # noqa: RUF001
)


def _group_thousands(value: int) -> str:
    """Render a non-negative int with NBSP between thousand groups (e.g. 1200 -> '1 200')."""
    s = str(value)
    chunks: list[str] = []
    while len(s) > 3:
        chunks.append(s[-3:])
        s = s[:-3]
    chunks.append(s)
    return _NBSP.join(reversed(chunks))


def format_money(kopecks: int) -> str:
    """Render kopecks as a Russian-locale RUB string with NBSPs.

    Examples:
        format_money(0) == "0 ₽"
        format_money(120000) == "1 200 ₽"
        format_money(150) == "1,50 ₽"
        format_money(-5000) == "-50 ₽"

    Whole-ruble values drop the fractional part; sub-ruble residue renders as
    ",XX" with Russian decimal comma + 2 digits. NBSP (U+00A0) separates digit
    groups and the digit/currency boundary (mirrors v1 frontend ``formatMoney``).
    Negative values render with a leading minus sign.
    """
    sign = "-" if kopecks < 0 else ""
    abs_k = abs(kopecks)
    rubles, frac = divmod(abs_k, 100)
    body = _group_thousands(rubles)
    if frac == 0:
        return f"{sign}{body}{_NBSP}₽"
    return f"{sign}{body},{frac:02d}{_NBSP}₽"


def _format_ru_datetime(dt: datetime) -> str:
    """Render a datetime as Russian long-form in Europe/Moscow.

    Example: ``datetime(2026, 5, 16, 14, 30, tzinfo=MSK) -> "16 мая 2026 г. в 14:30"``

    Naive datetimes are assumed Europe/Moscow (project tz pin); aware datetimes
    are converted to Europe/Moscow before rendering. Pure function — no I/O.
    """
    msk = dt.replace(tzinfo=_MSK) if dt.tzinfo is None else dt.astimezone(_MSK)
    month_ru = _RU_MONTHS_GEN[msk.month - 1]
    return (
        f"{msk.day} {month_ru} {msk.year} г. в "  # noqa: RUF001 — Cyrillic "г." (D-45-17)
        f"{msk.hour:02d}:{msk.minute:02d}"
    )
