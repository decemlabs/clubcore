"""Unit tests for _format_gym_hours (Phase 20 D-20-8).

Pins the U+2013 EN DASH and the [:5] slice on Phase 19's time.isoformat()
output. The KeyError defensive raise asserts the cross-phase contract
(Phase 19 service.py:99-100, 142 must keep populating fields={'open','close'}).
"""

from __future__ import annotations

import pytest

from app.core.exceptions import OutsideGymHoursError
from app.integrations.telegram.handlers import _format_gym_hours


def test_format_gym_hours_basic() -> None:
    exc = OutsideGymHoursError(
        "outside_gym_hours",
        fields={"open": "07:00:00", "close": "23:00:00"},
    )
    result = _format_gym_hours(exc)
    assert result == "07:00–23:00"  # noqa: RUF001 — U+2013 EN DASH
    # Belt-and-braces: the dash is U+2013, not '-' (U+002D) and not '—' (U+2014).
    assert "–" in result  # noqa: RUF001 — U+2013 EN DASH assertion
    assert "—" not in result
    assert "-" not in result


def test_format_gym_hours_non_round() -> None:
    exc = OutsideGymHoursError(
        "outside_gym_hours",
        fields={"open": "07:30:00", "close": "22:45:00"},
    )
    assert _format_gym_hours(exc) == "07:30–22:45"  # noqa: RUF001 — U+2013 EN DASH


def test_format_gym_hours_missing_fields_raises() -> None:
    exc = OutsideGymHoursError("outside_gym_hours", fields={})
    with pytest.raises(RuntimeError, match="Phase 19 regression"):
        _format_gym_hours(exc)
