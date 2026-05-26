"""Unit tests for visits anti-fraud helpers (Phase 19 D-10, CD-07).

Pure function tests — no DB, no FastAPI.

Key invariant (CD-07): the gym-hours interval is half-open [start, end).
At gym_hours_end (e.g. 23:00) the door is CLOSED — the helper raises.
"""

from __future__ import annotations

from datetime import time
from unittest.mock import MagicMock, patch

import pytest

from app.core.exceptions import OutsideGymHoursError
from app.modules.visits.service import _assert_within_gym_hours


def _mock_settings(start: time, end: time) -> MagicMock:
    """Return a mock Settings object with the given gym-hours window."""
    m = MagicMock()
    m.gym_hours_start = start
    m.gym_hours_end = end
    return m


class TestAssertWithinGymHours:
    """Boundary cases for the half-open [start, end) interval (CD-07)."""

    @patch("app.modules.visits.service.get_settings")
    def test_at_open_time_ok(self, mock_get_settings: MagicMock) -> None:
        """Exactly at gym_hours_start → inside interval → no exception."""
        mock_get_settings.return_value = _mock_settings(time(7, 0), time(23, 0))
        # Should NOT raise
        _assert_within_gym_hours(time(7, 0))

    @patch("app.modules.visits.service.get_settings")
    def test_one_minute_before_open_raises(self, mock_get_settings: MagicMock) -> None:
        """06:59 is before gym_hours_start (07:00) → OutsideGymHoursError raised."""
        mock_get_settings.return_value = _mock_settings(time(7, 0), time(23, 0))
        with pytest.raises(OutsideGymHoursError):
            _assert_within_gym_hours(time(6, 59))

    @patch("app.modules.visits.service.get_settings")
    def test_one_minute_before_close_ok(self, mock_get_settings: MagicMock) -> None:
        """22:59 is inside [07:00, 23:00) → no exception."""
        mock_get_settings.return_value = _mock_settings(time(7, 0), time(23, 0))
        # Should NOT raise
        _assert_within_gym_hours(time(22, 59))

    @patch("app.modules.visits.service.get_settings")
    def test_at_close_time_raises(self, mock_get_settings: MagicMock) -> None:
        """CD-07: end is exclusive — at 23:00 the door is closed."""
        mock_get_settings.return_value = _mock_settings(time(7, 0), time(23, 0))
        with pytest.raises(OutsideGymHoursError):
            _assert_within_gym_hours(time(23, 0))

    @patch("app.modules.visits.service.get_settings")
    def test_midday_ok(self, mock_get_settings: MagicMock) -> None:
        """12:00 is well inside [07:00, 23:00) → no exception."""
        mock_get_settings.return_value = _mock_settings(time(7, 0), time(23, 0))
        # Should NOT raise
        _assert_within_gym_hours(time(12, 0))

    @patch("app.modules.visits.service.get_settings")
    def test_exception_carries_open_close_fields(self, mock_get_settings: MagicMock) -> None:
        """OutsideGymHoursError.fields must carry open and close ISO strings."""
        mock_get_settings.return_value = _mock_settings(time(7, 0), time(23, 0))
        with pytest.raises(OutsideGymHoursError) as exc_info:
            _assert_within_gym_hours(time(3, 0))
        err = exc_info.value
        assert hasattr(err, "fields") and err.fields is not None
        assert "open" in err.fields
        assert "close" in err.fields
