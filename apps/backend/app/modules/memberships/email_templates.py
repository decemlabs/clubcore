"""Memberships module locked email-template registry (Phase 45 NOTIFY-08 / D-45-15).

Phase 45 expiring-soon email mirrors for the Telegram DM templates at
``app/integrations/telegram/copy.py:40-45 EXPIRING_*_VARIANT_*``. Same
``client_id.bytes[0] & 1`` anti-oracle A/B variant chooser is reused for
the email channel (D-45-16) — a client who would have received variant A
on Telegram receives ``EMAIL_EXPIRING_*_VARIANT_A`` if the email fallback
ever fires at 06:15 Europe/Moscow (D-45 cron lineage).

Lineage:
  - D-45-15 — per-domain template ownership; NEW file in this module,
    NOT in ``app/integrations/email/templates/`` (D-39-02 + D-42-06).
  - D-45-17 — NBSP discipline: ``&nbsp;`` between rendered ``{{ end_date }}``
    and the ``г.`` abbreviation on the HTML side; literal U+00A0 in the
    plain-text side (Outlook-NBSP fix inherited from Phase 42).
  - D-45-19 — Jinja2 ``SandboxedEnvironment(autoescape=True)`` on HTML,
    passthrough on text; pure-literal subjects are ``Final[str]``.
  - D-41-11 / D-41-12 — All 6 identifiers below are pre-registered in
    ``app.core.audit.LOCKED_EMAIL_TEMPLATES`` (audit.py:273-278) and the
    AST gate at ``tests/unit/test_locked_email_templates_ast.py`` asserts
    dispatcher callsites pass a literal name resolving to a member.
  - D-27-OWNER-COPY-LOCK — owner sign-off is recorded by enumerating the
    6 constant names in ``45-04-SUMMARY.md`` (D-45-18 owner sign-off line).
    Any edit to the Russian copy below requires a new sign-off entry.

Anti-oracle (Phase 27 D-27 lineage): Variant A vs Variant B for the same
``(client, kind)`` MUST render to visibly different strings — a side-by-side
observer cannot infer client identity from which variant a recipient
received. The two variants below differ in tone (A terse + neutral; B
slightly warmer / more conversational), mirroring the Telegram-side
``EXPIRING_*_VARIANT_*`` voice.

Rendering pipeline contract (D-45-19):
  - ``EmailTemplate.subject`` is a ``Final[str]`` literal — no
    interpolation. All 6 share ``"Ваш абонемент скоро истекает"``;
    variant differentiation is body-only (CONTEXT.md specifics).
  - HTML uses ``SandboxedEnvironment(autoescape=True)`` — defence in
    depth even though the only variable is a pre-formatted Russian date.
  - Text uses ``SandboxedEnvironment(autoescape=False)`` — explicit
    passthrough; safe because the only variable is a formatted date.
  - ONLY ``{{ end_date }}`` is exposed — NO client name, NO email, NO
    user id (anti-oracle, mirrors D-42-23 / Phase 27 D-27-10).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from jinja2 import Template
from jinja2.sandbox import SandboxedEnvironment

# Two sandboxed Jinja environments: HTML side autoescapes ``{{ end_date }}``
# (defence in depth even for pre-formatted date strings); text/plain side is
# explicit passthrough. Mirrors ``app/modules/auth/email_templates.py:51-52``.
_ENV: Final[SandboxedEnvironment] = SandboxedEnvironment(autoescape=True)
_ENV_TEXT: Final[SandboxedEnvironment] = SandboxedEnvironment(autoescape=False)


@dataclass(frozen=True)
class EmailTemplate:
    """Locked email template record (D-45-15 / D-42-06 lineage).

    - ``subject`` is a fully baked literal — no interpolation. All 6
      expiring templates share the same subject; variant + window
      differentiation is body-only (anti-oracle, D-27-10 lineage).
    - ``html`` / ``text`` are pre-compiled ``jinja2.Template`` objects
      bound to sandboxed environments at module import.
    """

    subject: str
    html: Template
    text: Template


# D-45-15 locked Russian copy. RUF001 noqa is required on Cyrillic-bearing
# lines (project-wide convention; mirrors ``app/modules/auth/email_templates.py``
# lines 73-112 precedent). The 6 keys MUST match audit.py:273-278 verbatim.
TEMPLATES: Final[dict[str, EmailTemplate]] = {
    "EMAIL_EXPIRING_7D_VARIANT_A": EmailTemplate(  # noqa: RUF001
        subject="Ваш абонемент скоро истекает",
        html=_ENV.from_string(
            "<h1>Ваш абонемент скоро истекает</h1>"
            "<p>Срок действия абонемента истекает {{ end_date }}&nbsp;г. "
            "Самое время продлить — обратитесь к администратору.</p>"
            "<p>Sportzal · noreply@mail.sportzal.ru</p>"
        ),
        text=_ENV_TEXT.from_string(
            "Ваш абонемент скоро истекает\n\n"
            "Срок действия абонемента истекает {{ end_date }} г. "
            "Самое время продлить — обратитесь к администратору.\n\n"
            "Sportzal · noreply@mail.sportzal.ru"
        ),
    ),
    "EMAIL_EXPIRING_7D_VARIANT_B": EmailTemplate(  # noqa: RUF001
        subject="Ваш абонемент скоро истекает",
        html=_ENV.from_string(
            "<h1>Напоминание о сроке абонемента</h1>"
            "<p>Напоминаем, что ваш абонемент действует до {{ end_date }}&nbsp;г. "
            "Продление через администратора стойки.</p>"
            "<p>Sportzal · noreply@mail.sportzal.ru</p>"
        ),
        text=_ENV_TEXT.from_string(
            "Напоминание о сроке абонемента\n\n"
            "Напоминаем, что ваш абонемент действует до {{ end_date }} г. "
            "Продление через администратора стойки.\n\n"
            "Sportzal · noreply@mail.sportzal.ru"
        ),
    ),
    "EMAIL_EXPIRING_3D_VARIANT_A": EmailTemplate(  # noqa: RUF001
        subject="Ваш абонемент скоро истекает",
        html=_ENV.from_string(
            "<h1>До конца абонемента осталось 3 дня</h1>"
            "<p>Срок действия абонемента истекает {{ end_date }}&nbsp;г. "
            "Подойдите к стойке для продления.</p>"
            "<p>Sportzal · noreply@mail.sportzal.ru</p>"
        ),
        text=_ENV_TEXT.from_string(
            "До конца абонемента осталось 3 дня\n\n"
            "Срок действия абонемента истекает {{ end_date }} г. "
            "Подойдите к стойке для продления.\n\n"
            "Sportzal · noreply@mail.sportzal.ru"
        ),
    ),
    "EMAIL_EXPIRING_3D_VARIANT_B": EmailTemplate(  # noqa: RUF001
        subject="Ваш абонемент скоро истекает",
        html=_ENV.from_string(
            "<h1>Скоро истекает ваш абонемент</h1>"
            "<p>Ваш абонемент действителен до {{ end_date }}&nbsp;г. "
            "Не забудьте продлить его у администратора.</p>"
            "<p>Sportzal · noreply@mail.sportzal.ru</p>"
        ),
        text=_ENV_TEXT.from_string(
            "Скоро истекает ваш абонемент\n\n"
            "Ваш абонемент действителен до {{ end_date }} г. "
            "Не забудьте продлить его у администратора.\n\n"
            "Sportzal · noreply@mail.sportzal.ru"
        ),
    ),
    "EMAIL_EXPIRING_1D_VARIANT_A": EmailTemplate(  # noqa: RUF001
        subject="Ваш абонемент скоро истекает",
        html=_ENV.from_string(
            "<h1>Завтра — последний день абонемента</h1>"
            "<p>Срок действия абонемента истекает завтра, {{ end_date }}&nbsp;г. "
            "Заходите продлевать.</p>"
            "<p>Sportzal · noreply@mail.sportzal.ru</p>"
        ),
        text=_ENV_TEXT.from_string(
            "Завтра — последний день абонемента\n\n"
            "Срок действия абонемента истекает завтра, {{ end_date }} г. "
            "Заходите продлевать.\n\n"
            "Sportzal · noreply@mail.sportzal.ru"
        ),
    ),
    "EMAIL_EXPIRING_1D_VARIANT_B": EmailTemplate(  # noqa: RUF001
        subject="Ваш абонемент скоро истекает",
        html=_ENV.from_string(
            "<h1>Последний день вашего абонемента</h1>"
            "<p>Внимание: ваш абонемент истекает завтра, {{ end_date }}&nbsp;г. "
            "Зайдите к нам, чтобы продлить.</p>"
            "<p>Sportzal · noreply@mail.sportzal.ru</p>"
        ),
        text=_ENV_TEXT.from_string(
            "Последний день вашего абонемента\n\n"
            "Внимание: ваш абонемент истекает завтра, {{ end_date }} г. "
            "Зайдите к нам, чтобы продлить.\n\n"
            "Sportzal · noreply@mail.sportzal.ru"
        ),
    ),
}
