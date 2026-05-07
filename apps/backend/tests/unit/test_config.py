"""Unit tests for app.core.config.Settings (Phase 19 D-11).

Pure Settings construction tests — no DB, no network.

D-11: midnight-spanning gym hours rejected by model_validator at boot.
"""

from __future__ import annotations

from datetime import time

import pytest
from pydantic import ValidationError

# Required fields for Settings instantiation in tests (no .env loaded).
# PostgresDsn and RedisDsn validators require RFC-3986-compliant URIs.
_REQUIRED_SETTINGS = {
    "database_url": "postgresql+asyncpg://user:pass@localhost:5432/testdb",
    "redis_url": "redis://localhost:6379/0",
    "secret_key": "test-secret-key-not-real-minimum-length",
}


class TestGymHoursValidator:
    """D-11: model_validator rejects gym_hours_end <= gym_hours_start."""

    def test_midnight_spanning_rejected(self) -> None:
        """end < start (23:00 → 07:00 spanning midnight) → ValidationError."""
        from app.core.config import Settings

        with pytest.raises((ValidationError, ValueError)):
            Settings(
                **_REQUIRED_SETTINGS,
                gym_hours_start=time(23, 0),
                gym_hours_end=time(7, 0),
                _env_file=None,  # type: ignore[call-arg]
            )

    def test_equal_start_and_end_rejected(self) -> None:
        """end == start → ValidationError (interval must be strictly positive)."""
        from app.core.config import Settings

        with pytest.raises((ValidationError, ValueError)):
            Settings(
                **_REQUIRED_SETTINGS,
                gym_hours_start=time(7, 0),
                gym_hours_end=time(7, 0),
                _env_file=None,  # type: ignore[call-arg]
            )

    def test_valid_window_accepted(self) -> None:
        """end > start → Settings constructed without error."""
        from app.core.config import Settings

        s = Settings(
            **_REQUIRED_SETTINGS,
            gym_hours_start=time(8, 0),
            gym_hours_end=time(22, 0),
            _env_file=None,  # type: ignore[call-arg]
        )
        assert s.gym_hours_start == time(8, 0)
        assert s.gym_hours_end == time(22, 0)

    def test_default_values_accepted(self) -> None:
        """Default gym_hours_start=07:00, gym_hours_end=23:00 satisfy the invariant."""
        from app.core.config import Settings

        s = Settings(
            **_REQUIRED_SETTINGS,
            _env_file=None,  # type: ignore[call-arg]
        )
        assert s.gym_hours_start == time(7, 0)
        assert s.gym_hours_end == time(23, 0)
