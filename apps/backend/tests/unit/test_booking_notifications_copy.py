"""Unit tests for app.modules.bookings.notifications render helpers (Phase 39 NOTIFY-01 / NOTIFY-02)."""  # noqa: E501

from __future__ import annotations

import pytest

from app.modules.bookings import notifications


def test_render_booking_confirmed_dm_substitutes_all_three_placeholders() -> None:
    text = notifications.render_booking_confirmed_dm(
        client_name="Иван",
        trainer_name="Пётр Сидоров",
        slot_start_msk="20.05.2026 10:00",
    )
    assert "Иван" in text
    assert "Пётр Сидоров" in text
    assert "20.05.2026 10:00" in text
    assert "{" not in text  # no unsubstituted placeholders
    assert "}" not in text


def test_render_booking_cancelled_by_client_dm_substitutes_all_three_placeholders() -> None:
    text = notifications.render_booking_cancelled_by_client_dm(
        client_name="Иван",
        trainer_name="Пётр Сидоров",
        slot_start_msk="20.05.2026 10:00",
    )
    assert "Иван" in text
    assert "Пётр Сидоров" in text
    assert "20.05.2026 10:00" in text
    assert "{" not in text
    assert "}" not in text


def test_render_booking_cancelled_by_owner_dm_substitutes_all_three_placeholders() -> None:
    text = notifications.render_booking_cancelled_by_owner_dm(
        client_name="Иван",
        trainer_name="Пётр Сидоров",
        slot_start_msk="20.05.2026 10:00",
    )
    assert "Иван" in text
    assert "Пётр Сидоров" in text
    assert "20.05.2026 10:00" in text
    assert "{" not in text
    assert "}" not in text


def test_render_booking_reminder_24h_dm_substitutes_all_three_placeholders() -> None:
    text = notifications.render_booking_reminder_24h_dm(
        client_name="Иван",
        trainer_name="Пётр Сидоров",
        slot_start_msk="20.05.2026 10:00",
    )
    assert "Иван" in text
    assert "Пётр Сидоров" in text
    assert "20.05.2026 10:00" in text
    assert "{" not in text
    assert "}" not in text


def test_render_raises_keyerror_when_template_has_unknown_placeholder(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Regression sentinel for D-39-04: renderers MUST use ``str.format`` (not f-strings).

    If a template ever carries an unknown placeholder key, the renderer must surface it
    as ``KeyError`` at call time -- silent shadowing would let bad copy ship.
    """
    monkeypatch.setattr(
        notifications,
        "BOOKING_CONFIRMED_DM",
        "Привет, {client_name}! {unknown_key}",
    )
    with pytest.raises(KeyError):
        notifications.render_booking_confirmed_dm(
            client_name="x",
            trainer_name="y",
            slot_start_msk="z",
        )


def test_bot_book_denied_dm_constant_is_non_empty() -> None:
    """NOTIFY-02 anti-oracle constant -- Phase 40 consumes it; Phase 39 just locks its existence."""
    assert isinstance(notifications._BOT_BOOK_DENIED_DM, str)
    assert len(notifications._BOT_BOOK_DENIED_DM) > 0


def test_bot_book_denied_dm_constant_has_no_placeholders() -> None:
    """NOTIFY-02 / C-12 anti-oracle discipline: the single denial string MUST NOT carry
    any ``{...}`` placeholder -- it covers all three negative outcomes ("no active PT-package",
    "no slots available", "client not linked") without distinguishing them.
    """
    assert "{" not in notifications._BOT_BOOK_DENIED_DM
    assert "}" not in notifications._BOT_BOOK_DENIED_DM
