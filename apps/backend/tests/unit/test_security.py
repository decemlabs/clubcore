"""Placeholder unit test for app.core.security.

Phase A has no real auth logic (BE-05 — security.py is empty placeholder).
This test exists so the unit suite is non-empty and pytest discovery works.
Real tests for password hashing / JWT issue/verify land in Phase C+.
"""
from __future__ import annotations

import app.core.security  # noqa: F401 — import smoke-test only


def test_security_module_is_importable() -> None:
    """Smoke: importing app.core.security must not raise."""
    # The import on the line above already proves this. Assertion is intentionally
    # trivial — promoted to a real assertion in Phase C+.
    assert True
