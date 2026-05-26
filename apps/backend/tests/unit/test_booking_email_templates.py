"""Unit tests for ``app.modules.bookings.email_templates`` (Phase 45 NOTIFY-10 / D-45-15).

Asserts the 4 locked Russian email templates exist, carry the kind-specific literal
subjects from CONTEXT.md specifics, render with realistic vars, and place a literal
``&nbsp;`` (HTML side) / U+00A0 (text side) between trainer-name and time-of-day
per D-45-17.
"""

from __future__ import annotations

import pytest

from app.core.audit import LOCKED_EMAIL_TEMPLATES
from app.modules.bookings.email_templates import TEMPLATES

EXPECTED_KEYS = frozenset(
    {
        "EMAIL_BOOKING_CONFIRMED",
        "EMAIL_BOOKING_CANCELLED_BY_CLIENT",
        "EMAIL_BOOKING_CANCELLED_BY_OWNER",
        "EMAIL_BOOKING_REMINDER_24H",
    }
)


def test_templates_has_exactly_four_locked_keys() -> None:
    assert len(TEMPLATES) == 4
    assert set(TEMPLATES.keys()) == EXPECTED_KEYS


def test_all_keys_are_members_of_locked_email_templates() -> None:
    for key in TEMPLATES:
        assert key in LOCKED_EMAIL_TEMPLATES, key


@pytest.mark.parametrize(
    "template_id,expected_subject",
    [
        ("EMAIL_BOOKING_CONFIRMED", "Запись подтверждена"),
        (
            "EMAIL_BOOKING_CANCELLED_BY_CLIENT",
            "Запись отменена (по вашей просьбе)",
        ),
        ("EMAIL_BOOKING_CANCELLED_BY_OWNER", "Запись отменена"),
        ("EMAIL_BOOKING_REMINDER_24H", "Напоминание: тренировка завтра"),
    ],
)
def test_kind_specific_literal_subjects(template_id: str, expected_subject: str) -> None:
    assert TEMPLATES[template_id].subject == expected_subject


@pytest.mark.parametrize(
    "template_id",
    [
        "EMAIL_BOOKING_CONFIRMED",
        "EMAIL_BOOKING_CANCELLED_BY_CLIENT",
        "EMAIL_BOOKING_CANCELLED_BY_OWNER",
    ],
)
def test_html_body_renders_with_nbsp_between_trainer_and_time(template_id: str) -> None:
    html = TEMPLATES[template_id].html.render(
        trainer_name="Алексей Иванов",
        slot_start_msk="завтра в 19:00",
    )
    assert "&nbsp;" in html
    # NBSP must appear between trainer-name and slot.
    assert "Алексей Иванов&nbsp;завтра в 19:00" in html


def test_reminder_24h_html_body_renders_with_slot_date_and_nbsp() -> None:
    html = TEMPLATES["EMAIL_BOOKING_REMINDER_24H"].html.render(
        trainer_name="Алексей Иванов",
        slot_start_msk="в 19:00",
        slot_date="16 мая",
    )
    assert "&nbsp;" in html
    assert "16 мая" in html
    assert "Алексей Иванов&nbsp;в 19:00" in html


@pytest.mark.parametrize(
    "template_id",
    [
        "EMAIL_BOOKING_CONFIRMED",
        "EMAIL_BOOKING_CANCELLED_BY_CLIENT",
        "EMAIL_BOOKING_CANCELLED_BY_OWNER",
    ],
)
def test_text_body_uses_literal_u00a0_between_trainer_and_time(template_id: str) -> None:
    text = TEMPLATES[template_id].text.render(
        trainer_name="Алексей Иванов",
        slot_start_msk="завтра в 19:00",
    )
    assert chr(0x00A0) in text  # U+00A0 NBSP literal
    assert "Алексей Иванов завтра в 19:00" in text  # noqa: RUF001
    # Plain-text body MUST NOT contain HTML entity literal.
    assert "&nbsp;" not in text


def test_reminder_24h_text_body_uses_literal_u00a0() -> None:
    text = TEMPLATES["EMAIL_BOOKING_REMINDER_24H"].text.render(
        trainer_name="Алексей Иванов",
        slot_start_msk="в 19:00",
        slot_date="16 мая",
    )
    assert chr(0x00A0) in text  # U+00A0 NBSP literal
    assert "&nbsp;" not in text
    assert "16 мая" in text


def test_footer_present_in_all_bodies() -> None:
    for template_id, tpl in TEMPLATES.items():
        if template_id == "EMAIL_BOOKING_REMINDER_24H":
            html = tpl.html.render(
                trainer_name="X",
                slot_start_msk="y",
                slot_date="z",
            )
            text = tpl.text.render(
                trainer_name="X",
                slot_start_msk="y",
                slot_date="z",
            )
        else:
            html = tpl.html.render(trainer_name="X", slot_start_msk="y")
            text = tpl.text.render(trainer_name="X", slot_start_msk="y")
        assert "Sportzal · noreply@mail.sportzal.ru" in html
        assert "Sportzal · noreply@mail.sportzal.ru" in text
