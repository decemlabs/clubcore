"""Unit tests for app.core.formatters (Phase 45 D-45-17 / NOTIFY-12).

Pure-function tests — no fixtures, no db.
"""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from app.core.formatters import _format_ru_datetime, format_money

_MSK = ZoneInfo("Europe/Moscow")
_NBSP = " "


@pytest.mark.parametrize(
    ("kopecks", "expected"),
    [
        (0, f"0{_NBSP}₽"),
        (100, f"1{_NBSP}₽"),
        (120000, f"1{_NBSP}200{_NBSP}₽"),
        (150, f"1,50{_NBSP}₽"),
        (-5000, f"-50{_NBSP}₽"),
        (123456789, f"1{_NBSP}234{_NBSP}567,89{_NBSP}₽"),
    ],
)
def test_format_money(kopecks: int, expected: str) -> None:
    assert format_money(kopecks) == expected


def test_format_money_uses_nbsp_not_regular_space() -> None:
    """Defensive: U+00A0 between thousand groups, NOT a regular space."""
    out = format_money(120000)
    # U+00A0 must be present, regular " 200" must NOT appear
    assert _NBSP in out
    assert " 200" not in out


def test_format_money_negative_sign_is_leading() -> None:
    """Refund signs render with a leading minus, not trailing."""
    out = format_money(-5000)
    assert out.startswith("-")
    assert not out.endswith("-")


@pytest.mark.parametrize(
    ("dt", "expected"),
    [
        (
            datetime(2026, 5, 16, 14, 30, tzinfo=_MSK),
            "16 мая 2026 г. в 14:30",  # noqa: RUF001 — Cyrillic canonical example
        ),
        (
            datetime(2026, 1, 1, 0, 0, tzinfo=_MSK),
            "1 января 2026 г. в 00:00",  # noqa: RUF001 — Cyrillic
        ),
        (
            datetime(2026, 12, 31, 23, 59, tzinfo=_MSK),
            "31 декабря 2026 г. в 23:59",  # noqa: RUF001 — Cyrillic
        ),
    ],
)
def test_format_ru_datetime(dt: datetime, expected: str) -> None:
    assert _format_ru_datetime(dt) == expected


def test_format_ru_datetime_converts_utc_to_msk() -> None:
    """Aware UTC datetime is converted to Europe/Moscow before rendering."""
    utc_dt = datetime(2026, 5, 16, 11, 30, tzinfo=ZoneInfo("UTC"))
    assert _format_ru_datetime(utc_dt) == "16 мая 2026 г. в 14:30"  # noqa: RUF001


def test_format_ru_datetime_naive_assumed_msk() -> None:
    """Naive datetimes are assumed Europe/Moscow per project tz pin."""
    naive = datetime(2026, 5, 16, 14, 30)  # noqa: DTZ001 — naive intentional
    assert _format_ru_datetime(naive) == "16 мая 2026 г. в 14:30"  # noqa: RUF001
