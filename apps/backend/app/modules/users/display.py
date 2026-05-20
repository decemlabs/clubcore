"""Operator name formatting helpers for user-facing copy.

Phase 45 D-45-12 — single canonical implementation of "first-name + last-initial"
format. Snapshotted at audit/render time so future user renames don't rewrite
history (NOTIFY-12). Pure function — no I/O, no DB.
"""

from __future__ import annotations


def format_actor_display(full_name: str) -> str:
    """Render operator display name as "First-name + initial-of-last-name + period".

    Examples (per D-45-12):
        format_actor_display("Анна Петрова") == "Анна П."
        format_actor_display("Иван") == "Иван"
        format_actor_display("") == "Сотрудник"

    Pure function: no I/O, no global state. Whitespace-only input returns the
    Cyrillic defensive fallback ``"Сотрудник"`` because ``str.split()`` returns
    an empty list for blank strings.
    """
    parts = full_name.split()
    if not parts:
        return "Сотрудник"  # noqa: RUF001 — Cyrillic defensive fallback (D-45-12)
    if len(parts) == 1:
        return parts[0]
    return f"{parts[0]} {parts[1][0]}."
