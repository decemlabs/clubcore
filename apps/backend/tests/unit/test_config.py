"""Unit tests for app.core.config.Settings (Phase 19 D-11).

Pure Settings construction tests — no DB, no network.

D-11: midnight-spanning gym hours rejected by model_validator at boot.
"""

from __future__ import annotations

from datetime import time
from typing import TYPE_CHECKING, Any

import pytest
from pydantic import ValidationError

if TYPE_CHECKING:
    from app.core.config import Settings

# Required fields for Settings instantiation in tests (no .env loaded).
# PostgresDsn and RedisDsn validators require RFC-3986-compliant URIs.
_REQUIRED_SETTINGS: dict[str, Any] = {
    "database_url": "postgresql+asyncpg://user:pass@localhost:5432/testdb",
    "redis_url": "redis://localhost:6379/0",
    "secret_key": "test-secret-key-not-real-minimum-length",
}


def _build_settings(**overrides: Any) -> Settings:
    """Construct Settings with required defaults + caller overrides.

    Centralises the ``_env_file=None`` boilerplate (REVIEW-62.1 IN-03) so
    per-test setup is a single-keyword call. The Any-typed kwargs deliberately
    bypass the BaseSettings TypedDict constraint that mypy strict otherwise
    rejects when expanding the required-fields dict alongside test overrides.
    """
    from app.core.config import Settings

    return Settings(
        **_REQUIRED_SETTINGS,
        **overrides,
        _env_file=None,
    )


class TestGymHoursValidator:
    """D-11: model_validator rejects gym_hours_end <= gym_hours_start."""

    def test_midnight_spanning_rejected(self) -> None:
        """end < start (23:00 → 07:00 spanning midnight) → ValidationError."""
        with pytest.raises((ValidationError, ValueError)):
            _build_settings(
                gym_hours_start=time(23, 0),
                gym_hours_end=time(7, 0),
            )

    def test_equal_start_and_end_rejected(self) -> None:
        """end == start → ValidationError (interval must be strictly positive)."""
        with pytest.raises((ValidationError, ValueError)):
            _build_settings(
                gym_hours_start=time(7, 0),
                gym_hours_end=time(7, 0),
            )

    def test_valid_window_accepted(self) -> None:
        """end > start → Settings constructed without error."""
        s = _build_settings(
            gym_hours_start=time(8, 0),
            gym_hours_end=time(22, 0),
        )
        assert s.gym_hours_start == time(8, 0)
        assert s.gym_hours_end == time(22, 0)

    def test_default_values_accepted(self) -> None:
        """Default gym_hours_start=07:00, gym_hours_end=23:00 satisfy the invariant."""
        s = _build_settings()
        assert s.gym_hours_start == time(7, 0)
        assert s.gym_hours_end == time(23, 0)


class TestEmailFromResolution:
    """Phase 62 D-62-03 — env-driven email FROM resolver.

    Resolution: CLUBCORE_EMAIL_FROM env override, else hardcoded brand default
    ``"noreply@mail.sportzal.ru"`` (preserved per D-62-02 / D-10-BRAND-DISTINCTION:
    brand-mail literal is operator DNS work, NOT part of the source rename).
    """

    def test_neither_env_set_preserves_hardcoded_default(self) -> None:
        """When no env is set, EmailProviderSettings.from_address keeps
        its hardcoded default ``"noreply@mail.sportzal.ru"``.
        """
        s = _build_settings()
        assert s.clubcore_email_from is None
        assert s.email.from_address == "noreply@mail.sportzal.ru"

    def test_clubcore_email_from_overrides_from_address(self) -> None:
        """When CLUBCORE_EMAIL_FROM is set, it overrides from_address."""
        s = _build_settings(clubcore_email_from="alice@example.com")
        assert s.email.from_address == "alice@example.com"

    def test_empty_clubcore_email_from_rejected(self) -> None:
        """REVIEW-62.1 WR-01/WR-02: empty-string override raises ValidationError.

        EmailStr typing makes pydantic reject "" at field validation time,
        restoring the fail-fast invariant the deleted multi-env chain
        implicitly provided.
        """
        with pytest.raises(ValidationError):
            _build_settings(clubcore_email_from="")

    def test_malformed_clubcore_email_from_rejected(self) -> None:
        """REVIEW-62.1 WR-02: override missing '@' raises ValidationError."""
        with pytest.raises(ValidationError):
            _build_settings(clubcore_email_from="ops-team")
