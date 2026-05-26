"""Phase 43 WR-07 regression — _format_expires_ru renders in Europe/Moscow.

The locked USER_INVITATION_EMAIL template carries Russian-language text that
reads naturally as Moscow-local time (CLAUDE.md project i18n convention).
Pre-fix: render in UTC -> 3-hour off-by-one for Moscow invitees. This test
locks the fix to Europe/Moscow + (MSK) suffix in Cyrillic.
"""

from __future__ import annotations

from datetime import UTC, datetime

from app.modules.users.service import _format_expires_ru


def test_format_expires_ru_moscow_time_summer() -> None:
    # 09:00 UTC on 26 May 2026 -> 12:00 Europe/Moscow (UTC+3, no DST since 2014).
    dt = datetime(2026, 5, 26, 9, 0, tzinfo=UTC)
    result = _format_expires_ru(dt)
    assert result == "26 мая 2026 в 12:00 (МСК)"  # noqa: RUF001


def test_format_expires_ru_day_rollover_at_tz_boundary() -> None:
    # 21:30 UTC on 15 Jan 2026 -> 00:30 Europe/Moscow on 16 Jan 2026.
    dt = datetime(2026, 1, 15, 21, 30, tzinfo=UTC)
    result = _format_expires_ru(dt)
    assert result == "16 января 2026 в 00:30 (МСК)"  # noqa: RUF001


def test_format_expires_ru_always_contains_msk_suffix() -> None:
    # Regression-prevention: any future revert to UTC rendering drops Cyrillic MSK.
    dt = datetime(2026, 12, 1, 0, 0, tzinfo=UTC)
    assert "(МСК)" in _format_expires_ru(dt)  # noqa: RUF001
