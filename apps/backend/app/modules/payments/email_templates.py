"""Payments module locked email-template registry (Phase 45 NOTIFY-12 / D-45-15).

Two locked Russian email templates for payment receipts:
  - ``EMAIL_PAYMENT_RECEIPT_SALE`` — cash sale receipt (positive signed_amount).
  - ``EMAIL_PAYMENT_RECEIPT_REFUND`` — refund receipt (negative signed_amount).

Per D-45-15 templates live next to their owning domain module — *NOT* in
``app/integrations/email/templates/``. The ``integrations/email`` layer
transports rendered bytes, this module owns the Russian-locale copy.

Lineage:
  - D-45-15 — per-domain template ownership (this module).
  - D-45-17 — NBSP discipline: the ``{{ amount }}`` variable is pre-rendered
    upstream by ``app.core.formatters.format_money`` (Plan 45-02), which
    inserts U+00A0 between digit groups AND between digits and the
    currency sign. Templates do NOT inject additional NBSPs around the
    amount — pass-through verbatim.
  - D-45-12 — ``{{ actor_display_name }}`` is pre-formatted upstream by
    ``app.modules.users.display.format_actor_display`` (e.g. ``"Анна П."``)
    and snapshotted into the audit payload at receipt-fanout time so a
    future user rename does not rewrite history.
  - D-41-11 — ``LOCKED_EMAIL_TEMPLATES`` frozenset in ``app.core.audit``
    (entries 285-286) is the runtime source of truth for the AST gate
    at ``tests/unit/test_locked_email_templates_ast.py``.
  - D-27-OWNER-COPY-LOCK — owner sign-off at VER-14 (Phase 46) is
    recorded by enumerating ``LOCKED_EMAIL_TEMPLATES`` members; any
    edit to the verbatim Russian copy below requires re-running that
    sign-off.

This module deliberately does NOT import ``LOCKED_EMAIL_TEMPLATES`` —
the AST gate reads the ``template_id`` literal at the dispatcher
callsite, not via runtime cross-reference from here. Keep the
dependency direction core → modules unbroken.

Rendering pipeline contract (D-45-15 / NOTIFY-12 verbatim):
  - ``EmailTemplate.subject`` is a ``Final[str]`` — pure literal, no
    interpolation. Locked subjects:
      ``"Чек: оплата"`` for SALE, ``"Чек: возврат"`` for REFUND.
  - HTML template uses ``SandboxedEnvironment(autoescape=True)``.
  - Text template uses ``SandboxedEnvironment(autoescape=False)``.
  - Variables exposed to the body templates (caller pre-renders all
    NBSP-safe formatting per D-45-17):
      * ``{{ amount }}``           — ``format_money(payment.amount_kopecks)``
      * ``{{ paid_at }}``          — ``_format_ru_datetime(payment.recorded_at)``
      * ``{{ plan_snapshot }}``    — payment subject description snapshot
      * ``{{ actor_display_name }}`` — ``format_actor_display(actor.full_name)``
  - Body MUST include the literal phrase ``"Принял: {{ actor_display_name }}"``
    on the SALE template per CONTEXT.md NOTIFY-12 verbatim example;
    the REFUND template mirrors with ``"Оформил: {{ actor_display_name }}"``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from jinja2 import Template
from jinja2.sandbox import SandboxedEnvironment

# Two sandboxed Jinja environments: HTML side autoescapes user-supplied
# variables; text/plain side is explicit passthrough. Mirrors the Phase 42
# auth/email_templates.py shape (D-42-06).
_ENV: Final[SandboxedEnvironment] = SandboxedEnvironment(autoescape=True)
_ENV_TEXT: Final[SandboxedEnvironment] = SandboxedEnvironment(autoescape=False)


@dataclass(frozen=True)
class EmailTemplate:
    """Locked email template record (D-45-15, mirrors D-42-06 shape).

    - ``subject`` is a fully baked literal — no interpolation (pure
      ``Final[str]`` per D-45-19).
    - ``html`` / ``text`` are pre-compiled ``jinja2.Template`` objects
      bound to sandboxed environments at module import.
    """

    subject: str
    html: Template
    text: Template


# D-45-15 locked Russian copy. RUF001 noqa is required on every line that
# carries Cyrillic text (project-wide convention; mirrors
# ``app/modules/auth/email_templates.py`` Phase 42 lineage).
TEMPLATES: Final[dict[str, EmailTemplate]] = {
    "EMAIL_PAYMENT_RECEIPT_SALE": EmailTemplate(  # noqa: RUF001
        subject="Чек: оплата",  # noqa: RUF001
        html=_ENV.from_string(
            "<h1>Чек: оплата</h1>"  # noqa: RUF001
            "<p>Сумма: {{ amount }}</p>"  # noqa: RUF001
            "<p>Дата: {{ paid_at }}</p>"  # noqa: RUF001
            "<p>{{ plan_snapshot }}</p>"
            "<p>Принял: {{ actor_display_name }}</p>"  # noqa: RUF001
            "<p>Sportzal · noreply@mail.sportzal.ru</p>"  # noqa: RUF001
        ),
        text=_ENV_TEXT.from_string(
            "Чек: оплата\n\n"  # noqa: RUF001
            "Сумма: {{ amount }}\n"  # noqa: RUF001
            "Дата: {{ paid_at }}\n"  # noqa: RUF001
            "{{ plan_snapshot }}\n\n"
            "Принял: {{ actor_display_name }}\n\n"  # noqa: RUF001
            "Sportzal · noreply@mail.sportzal.ru"  # noqa: RUF001
        ),
    ),
    "EMAIL_PAYMENT_RECEIPT_REFUND": EmailTemplate(  # noqa: RUF001
        subject="Чек: возврат",  # noqa: RUF001
        html=_ENV.from_string(
            "<h1>Чек: возврат</h1>"  # noqa: RUF001
            "<p>Сумма возврата: {{ amount }}</p>"  # noqa: RUF001
            "<p>Дата: {{ paid_at }}</p>"  # noqa: RUF001
            "<p>{{ plan_snapshot }}</p>"
            "<p>Оформил: {{ actor_display_name }}</p>"  # noqa: RUF001
            "<p>Sportzal · noreply@mail.sportzal.ru</p>"  # noqa: RUF001
        ),
        text=_ENV_TEXT.from_string(
            "Чек: возврат\n\n"  # noqa: RUF001
            "Сумма возврата: {{ amount }}\n"  # noqa: RUF001
            "Дата: {{ paid_at }}\n"  # noqa: RUF001
            "{{ plan_snapshot }}\n\n"
            "Оформил: {{ actor_display_name }}\n\n"  # noqa: RUF001
            "Sportzal · noreply@mail.sportzal.ru"  # noqa: RUF001
        ),
    ),
}
