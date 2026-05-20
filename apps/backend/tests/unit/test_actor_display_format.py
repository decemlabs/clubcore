"""Unit tests for format_actor_display (Phase 45 D-45-12).

Pure-function tests — no fixtures, no db.
"""

from __future__ import annotations

import pytest

from app.modules.users.display import format_actor_display


@pytest.mark.parametrize(
    ("full_name", "expected"),
    [
        ("Анна Петрова", "Анна П."),  # noqa: RUF001 — D-45-12 canonical example
        ("Иван", "Иван"),  # noqa: RUF001 — single token kept verbatim
        ("Анна Мария Петрова", "Анна М."),  # noqa: RUF001 — first + initial of second
        ("", "Сотрудник"),  # noqa: RUF001 — empty fallback (Cyrillic)
        ("   ", "Сотрудник"),  # noqa: RUF001 — whitespace-only fallback
        ("John Doe", "John D."),  # ASCII sanity case
    ],
)
def test_format_actor_display(full_name: str, expected: str) -> None:
    assert format_actor_display(full_name) == expected


def test_pure_determinism() -> None:
    """Same input → same output across N invocations (no hidden state)."""
    for _ in range(10):
        assert format_actor_display("Анна Петрова") == "Анна П."  # noqa: RUF001
