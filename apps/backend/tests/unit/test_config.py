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


class TestEmailFromResolution:
    """Phase 62 D-62-03 — env-driven email FROM with v1.10-shim fallback chain.

    Precedence: CLUBCORE_EMAIL_FROM → SPORTZAL_EMAIL_FROM (warn) → hardcoded default.
    The hardcoded default literal ``"noreply@mail.sportzal.ru"`` is preserved per
    CONTEXT line 172 — operator DNS work, not a code rename.
    """

    def test_neither_env_set_preserves_hardcoded_default(self) -> None:
        """When neither env is set, EmailProviderSettings.from_address keeps
        its hardcoded default ``"noreply@mail.sportzal.ru"``.
        """
        from app.core.config import Settings

        s = Settings(
            **_REQUIRED_SETTINGS,
            _env_file=None,  # type: ignore[call-arg]
        )
        assert s.clubcore_email_from is None
        assert s.sportzal_email_from is None
        assert s.email.from_address == "noreply@mail.sportzal.ru"

    def test_clubcore_email_from_wins_without_warning(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """When CLUBCORE_EMAIL_FROM is set, it overrides from_address with no warning."""
        import logging

        from app.core.config import Settings

        caplog.set_level(logging.WARNING)
        s = Settings(
            **_REQUIRED_SETTINGS,
            clubcore_email_from="alice@example.com",
            _env_file=None,  # type: ignore[call-arg]
        )
        assert s.email.from_address == "alice@example.com"
        assert not any(
            "env_fallback_used" in record.getMessage() or "env_fallback_used" in str(record)
            for record in caplog.records
        ), f"unexpected fallback warning emitted: {[r.getMessage() for r in caplog.records]}"

    def test_sportzal_email_from_used_with_deprecated_warning(self) -> None:
        """When only SPORTZAL_EMAIL_FROM is set, it overrides from_address AND
        emits a structlog warning naming the canonical env + removal target.
        """
        import structlog
        from structlog.testing import capture_logs

        from app.core.config import Settings

        # Bind a temp processor chain that capture_logs can intercept.
        structlog.configure(
            processors=[structlog.processors.KeyValueRenderer()],
            wrapper_class=structlog.BoundLogger,
            context_class=dict,
            logger_factory=structlog.PrintLoggerFactory(),
        )
        with capture_logs() as cap:
            s = Settings(
                **_REQUIRED_SETTINGS,
                sportzal_email_from="bob@example.com",
                _env_file=None,  # type: ignore[call-arg]
            )
        assert s.email.from_address == "bob@example.com"
        # Exactly one env_fallback_used warning record.
        matches = [r for r in cap if r.get("event") == "env_fallback_used"]
        assert len(matches) == 1, f"expected 1 env_fallback_used record, got: {cap}"
        rec = matches[0]
        assert rec["log_level"] == "warning"
        assert rec["env"] == "SPORTZAL_EMAIL_FROM"
        assert rec["canonical"] == "CLUBCORE_EMAIL_FROM"
        assert rec["removal_target"] == "v1.11/Phase 67/RUN-07"

    def test_clubcore_wins_when_both_envs_set(self) -> None:
        """When both envs are set, CLUBCORE_EMAIL_FROM wins; no warning emitted."""
        from structlog.testing import capture_logs

        from app.core.config import Settings

        with capture_logs() as cap:
            s = Settings(
                **_REQUIRED_SETTINGS,
                clubcore_email_from="alice@example.com",
                sportzal_email_from="bob@example.com",
                _env_file=None,  # type: ignore[call-arg]
            )
        assert s.email.from_address == "alice@example.com"
        # No env_fallback_used record because the canonical env was set.
        assert not any(r.get("event") == "env_fallback_used" for r in cap), (
            f"unexpected fallback warning when canonical env present: {cap}"
        )
