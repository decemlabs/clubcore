"""Locked Russian email templates for booking lifecycle + reminder.

Phase 45 D-45-15 / NOTIFY-10 / D-39-02 — module owns its email copy
(mirrors Telegram-side at ``bookings/notifications.py`` lines 31-34
``BOOKING_*_DM`` for cross-channel voice consistency).

Module structure mirrors ``app/modules/auth/email_templates.py`` byte-for-byte
(D-42-06 / D-42-23): dual ``SandboxedEnvironment`` instances, frozen
``EmailTemplate`` dataclass, ``TEMPLATES: Final[dict[str, EmailTemplate]]``
registry. All 4 identifiers locked at ``app/core/audit.py:280-283``.

NBSP discipline (D-45-17):
  - HTML body uses ``&nbsp;`` between trainer-name and time-of-day.
  - Plain-text body uses literal U+00A0 (non-breaking space) at the same boundary.

Owner sign-off (D-45-18 / D-27-OWNER-COPY-LOCK lineage) enumerates these 4
constants in ``45-05-SUMMARY.md`` at plan close. Any edit to the verbatim
Russian copy below requires a new owner sign-off entry.

Variables interpolated (caller pre-formats per D-39-11 — Europe/Moscow timezone):
  - ``{{ trainer_name }}`` — full trainer display name (e.g. "Алексей Иванов")
  - ``{{ slot_start_msk }}`` — pre-formatted slot start (e.g. "завтра в 19:00")
  - ``{{ slot_date }}`` — REMINDER_24H only (e.g. "16 мая")
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from jinja2 import Template
from jinja2.sandbox import SandboxedEnvironment

# Two sandboxed Jinja environments: HTML side autoescapes interpolated vars
# (defence in depth, D-42-05 / D-45-19); text/plain side is explicit passthrough.
_ENV: Final[SandboxedEnvironment] = SandboxedEnvironment(autoescape=True)
_ENV_TEXT: Final[SandboxedEnvironment] = SandboxedEnvironment(autoescape=False)


@dataclass(frozen=True)
class EmailTemplate:
    """Locked email template record (D-42-06).

    - ``subject`` is a fully baked literal — no interpolation. Locking the
      subject prevents stolen-email oracle attacks (anti-oracle, D-42-23).
    - ``html`` / ``text`` are pre-compiled ``jinja2.Template`` objects bound
      to sandboxed environments at module import.
    """

    subject: str
    html: Template
    text: Template


# D-45-15 / D-45-17 locked Russian copy. Per project-wide convention
# (mirrors ``app/modules/auth/email_templates.py`` and
# ``app/integrations/telegram/sender.py``), every line carrying Cyrillic
# letters that ruff RUF001 flags as ambiguous-with-Latin is suppressed
# with an inline RUF001 noqa directive. Reviewers diff exact byte strings.
TEMPLATES: Final[dict[str, EmailTemplate]] = {
    "EMAIL_BOOKING_CONFIRMED": EmailTemplate(
        subject="Запись подтверждена",
        html=_ENV.from_string(
            "<h1>Запись подтверждена</h1>"
            "<p>Тренировка с {{ trainer_name }}&nbsp;{{ slot_start_msk }}.</p>"  # noqa: RUF001
            "<p>Sportzal · noreply@mail.sportzal.ru</p>"
        ),
        text=_ENV_TEXT.from_string(
            "Запись подтверждена\n\n"
            "Тренировка с {{ trainer_name }} {{ slot_start_msk }}.\n\n"  # noqa: RUF001
            "Sportzal · noreply@mail.sportzal.ru"
        ),
    ),
    "EMAIL_BOOKING_CANCELLED_BY_CLIENT": EmailTemplate(
        subject="Запись отменена (по вашей просьбе)",
        html=_ENV.from_string(
            "<h1>Запись отменена</h1>"
            "<p>Тренировка с {{ trainer_name }}&nbsp;{{ slot_start_msk }} "  # noqa: RUF001
            "отменена по вашей просьбе.</p>"
            "<p>Sportzal · noreply@mail.sportzal.ru</p>"
        ),
        text=_ENV_TEXT.from_string(
            "Запись отменена\n\n"
            "Тренировка с {{ trainer_name }} {{ slot_start_msk }} "  # noqa: RUF001
            "отменена по вашей просьбе.\n\n"
            "Sportzal · noreply@mail.sportzal.ru"
        ),
    ),
    "EMAIL_BOOKING_CANCELLED_BY_OWNER": EmailTemplate(
        subject="Запись отменена",
        html=_ENV.from_string(
            "<h1>Запись отменена</h1>"
            "<p>К сожалению, тренировка с {{ trainer_name }}&nbsp;"  # noqa: RUF001
            "{{ slot_start_msk }} отменена администратором.</p>"
            "<p>Sportzal · noreply@mail.sportzal.ru</p>"
        ),
        text=_ENV_TEXT.from_string(
            "Запись отменена\n\n"
            "К сожалению, тренировка с {{ trainer_name }} {{ slot_start_msk }} "  # noqa: RUF001
            "отменена администратором.\n\n"
            "Sportzal · noreply@mail.sportzal.ru"
        ),
    ),
    "EMAIL_BOOKING_REMINDER_24H": EmailTemplate(
        subject="Напоминание: тренировка завтра",
        html=_ENV.from_string(
            "<h1>Напоминание о тренировке</h1>"  # noqa: RUF001
            "<p>Завтра, {{ slot_date }}, тренировка с "  # noqa: RUF001
            "{{ trainer_name }}&nbsp;{{ slot_start_msk }}.</p>"
            "<p>Sportzal · noreply@mail.sportzal.ru</p>"
        ),
        text=_ENV_TEXT.from_string(
            "Напоминание о тренировке\n\n"  # noqa: RUF001
            "Завтра, {{ slot_date }}, тренировка с "  # noqa: RUF001
            "{{ trainer_name }} {{ slot_start_msk }}.\n\n"  # noqa: RUF001
            "Sportzal · noreply@mail.sportzal.ru"
        ),
    ),
}
