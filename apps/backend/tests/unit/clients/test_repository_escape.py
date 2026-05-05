"""Unit tests for `_escape_like_pattern` (Phase 14 — CR-01 closure).

The helper escapes SQL `LIKE` metacharacters in user-supplied search input
before it is wrapped in `%...%` for ILIKE. Order matters: backslash MUST
be escaped first so we don't double-escape escapes we add for `%` / `_`.
"""

from __future__ import annotations

from app.modules.clients.repository import _escape_like_pattern


def test_plain_alphanumeric_is_unchanged() -> None:
    assert _escape_like_pattern("Иванов") == "Иванов"
    assert _escape_like_pattern("foo123") == "foo123"


def test_percent_is_escaped() -> None:
    assert _escape_like_pattern("50%") == "50\\%"


def test_underscore_is_escaped() -> None:
    assert _escape_like_pattern("a_b") == "a\\_b"


def test_backslash_is_doubled() -> None:
    # Single literal backslash → two literal backslashes.
    assert _escape_like_pattern("a\\b") == "a\\\\b"


def test_mixed_metacharacters_apply_in_correct_order() -> None:
    # Order check: backslash must be escaped FIRST so the escapes we
    # then add for %/_ are not themselves re-escaped.
    # Input bytes:  1 0 0 % _ x \ y
    # Expected:     1 0 0 \ % \ _ x \ \ y
    assert _escape_like_pattern("100%_x\\y") == "100\\%\\_x\\\\y"


def test_escape_like_false_returns_input_unchanged() -> None:
    # Opt-out hook (Phase 14 SC #1). No production caller passes False today.
    assert _escape_like_pattern("100%", escape_like=False) == "100%"
    assert _escape_like_pattern("a_b\\c", escape_like=False) == "a_b\\c"
