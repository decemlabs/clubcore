"""Online payments email template identifiers + locked copy (Phase 49 D-49-01 /
Phase 52 NOTIFY-02 / quick-task 260529-olc RUN-03-F1).

Phase 49 note — this file exists so the import-linter ignore
``app.integrations.email.dispatcher → app.modules.online_payments.email_templates``
(``.importlinter:189``) becomes MATCHED, dropping the ``warn`` for that
one edge.

Phase 52 note (D-52-07) — 4 ``Final[str]`` email template identifier constants
are added below and registered in ``LOCKED_EMAIL_TEMPLATES`` (15 → 19).

IMPORTANT — AST gate constraint (D-52-07):
  The AST gate in ``tests/unit/test_locked_email_templates_ast.py`` requires
  ``template_id=`` arguments at every ``get_email_dispatcher()()`` callsite to be
  **string literals** — NOT variable references. The constants defined here are
  for documentation and import-linter satisfaction ONLY; the ``tasks.py``
  dispatcher calls MUST use the literal strings directly, e.g.::

      await dispatcher(template_id="EMAIL_ONLINE_PAYMENT_SUCCEEDED", ...)

  A variable reference such as ``template_id=EMAIL_ONLINE_PAYMENT_SUCCEEDED``
  would silently bypass the AST gate.

Quick-task 260529-olc (RUN-03-F1) — adds the ``TEMPLATES`` dict with all 4
locked ``EmailTemplate`` records so ``_resolve_template`` can resolve them.
Mirrors ``payments/email_templates.py`` shape exactly (frozen dataclass, two
sandboxed Jinja envs, ``CLUB_BRAND`` footer, ``RUF001 noqa`` on Cyrillic lines).
Copy is owner-signed-off 2026-05-29; baked verbatim per D-27-OWNER-COPY-LOCK.

Rendering pipeline contract (mirrors D-45-15):
  - ``EmailTemplate.subject`` is a ``Final[str]`` — pure literal, no
    interpolation (D-45-19).
  - HTML template uses ``SandboxedEnvironment(autoescape=True)``.
  - Text template uses ``SandboxedEnvironment(autoescape=False)``.
  - ``amount_rub`` is pre-formatted upstream by ``format_money`` (D-45-17);
    do NOT inject additional NBSPs around it — pass through verbatim.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from jinja2 import Template
from jinja2.sandbox import SandboxedEnvironment

from app.core.branding import CLUB_BRAND

# Phase 52 NOTIFY-02 — email template identifiers. All four are registered in
# LOCKED_EMAIL_TEMPLATES (app/core/audit.py). The OWNER-COPY-LOCK lineage
# mirrors the DM template sign-off discipline (D-52-07).
EMAIL_ONLINE_PAYMENT_SUCCEEDED: Final[str] = "EMAIL_ONLINE_PAYMENT_SUCCEEDED"  # OWNER-COPY-LOCK
EMAIL_ONLINE_PAYMENT_REFUNDED: Final[str] = "EMAIL_ONLINE_PAYMENT_REFUNDED"  # OWNER-COPY-LOCK
# owner-alert (NOT-05): routed to owner, never sent to client
EMAIL_ONLINE_PAYMENT_CANCELED: Final[str] = "EMAIL_ONLINE_PAYMENT_CANCELED"  # OWNER-COPY-LOCK
# owner-alert (NOT-04): fiscal-failed operator notification
EMAIL_FISCAL_RECEIPT_FAILED: Final[str] = "EMAIL_FISCAL_RECEIPT_FAILED"  # OWNER-COPY-LOCK

# Two sandboxed Jinja environments: HTML side autoescapes user-supplied
# variables; text/plain side is explicit passthrough. Mirrors payments/email_templates.py
# shape (D-45-15 / D-42-06).
_ENV: Final[SandboxedEnvironment] = SandboxedEnvironment(autoescape=True)
_ENV_TEXT: Final[SandboxedEnvironment] = SandboxedEnvironment(autoescape=False)


@dataclass(frozen=True)
class EmailTemplate:
    """Locked email template record (mirrors payments/email_templates.py D-45-15 / D-42-06 shape).

    - ``subject`` is a fully baked literal — no interpolation (pure
      ``Final[str]`` per D-45-19).
    - ``html`` / ``text`` are pre-compiled ``jinja2.Template`` objects
      bound to sandboxed environments at module import.
    """

    subject: str
    html: Template
    text: Template


# 260529-olc RUN-03-F1: locked Russian copy. Owner-signed-off 2026-05-29.
# RUF001 noqa is required on every line carrying Cyrillic text (project-wide
# convention; mirrors payments/email_templates.py lineage).
TEMPLATES: Final[dict[str, EmailTemplate]] = {
    "EMAIL_ONLINE_PAYMENT_SUCCEEDED": EmailTemplate(  # noqa: RUF001
        subject="Оплата получена",  # noqa: RUF001
        html=_ENV.from_string(
            "<h1>Оплата получена</h1>"  # noqa: RUF001
            "<p>Здравствуйте, {{ first_name }}!"  # noqa: RUF001
            " Оплата на сумму {{ amount_rub }} успешно получена.</p>"  # noqa: RUF001
            "<p>Ваш абонемент / пакет тренировок активирован. Ждём вас в зале!</p>"  # noqa: RUF001
            f"<p>{CLUB_BRAND} · noreply@mail.clubcore.ru</p>"  # noqa: RUF001
        ),
        text=_ENV_TEXT.from_string(
            "Оплата получена\n\n"  # noqa: RUF001
            "Здравствуйте, {{ first_name }}! Оплата на сумму {{ amount_rub }} успешно получена.\n"  # noqa: RUF001
            "Ваш абонемент / пакет тренировок активирован. Ждём вас в зале!\n\n"  # noqa: RUF001
            f"{CLUB_BRAND} · noreply@mail.clubcore.ru"  # noqa: RUF001
        ),
    ),
    "EMAIL_ONLINE_PAYMENT_REFUNDED": EmailTemplate(  # noqa: RUF001
        subject="Возврат обработан",  # noqa: RUF001
        html=_ENV.from_string(
            "<h1>Возврат обработан</h1>"  # noqa: RUF001
            "<p>Здравствуйте, {{ first_name }}!"  # noqa: RUF001
            " Возврат на сумму {{ amount_rub }} успешно обработан.</p>"  # noqa: RUF001
            "<p>Средства поступят на ваш счёт в течение нескольких рабочих дней.</p>"  # noqa: RUF001
            "<p>Если у вас есть вопросы — обратитесь к администратору.</p>"  # noqa: RUF001
            f"<p>{CLUB_BRAND} · noreply@mail.clubcore.ru</p>"  # noqa: RUF001
        ),
        text=_ENV_TEXT.from_string(
            "Возврат обработан\n\n"  # noqa: RUF001
            "Здравствуйте, {{ first_name }}! Возврат на сумму {{ amount_rub }} успешно обработан.\n"  # noqa: RUF001
            "Средства поступят на ваш счёт в течение нескольких рабочих дней.\n"  # noqa: RUF001
            "Если у вас есть вопросы — обратитесь к администратору.\n\n"  # noqa: RUF001
            f"{CLUB_BRAND} · noreply@mail.clubcore.ru"  # noqa: RUF001
        ),
    ),
    "EMAIL_ONLINE_PAYMENT_CANCELED": EmailTemplate(  # noqa: RUF001
        subject="Платёж отменён — требуется проверка",  # noqa: RUF001
        html=_ENV.from_string(
            "<h1>Платёж отменён — требуется проверка</h1>"  # noqa: RUF001
            "<p>[ОПОВЕЩЕНИЕ ВЛАДЕЛЬЦА] Платёж отменён.</p>"  # noqa: RUF001
            "<p>payment_id: {{ payment_id }}, yookassa_payment_id: {{ yookassa_payment_id }}.</p>"
            "<p>Требуется проверка.</p>"  # noqa: RUF001
            f"<p>{CLUB_BRAND} · noreply@mail.clubcore.ru</p>"  # noqa: RUF001
        ),
        text=_ENV_TEXT.from_string(
            "Платёж отменён — требуется проверка\n\n"  # noqa: RUF001
            "[ОПОВЕЩЕНИЕ ВЛАДЕЛЬЦА] Платёж отменён.\n"  # noqa: RUF001
            "payment_id: {{ payment_id }}, yookassa_payment_id: {{ yookassa_payment_id }}.\n"
            "Требуется проверка.\n\n"  # noqa: RUF001
            f"{CLUB_BRAND} · noreply@mail.clubcore.ru"  # noqa: RUF001
        ),
    ),
    "EMAIL_FISCAL_RECEIPT_FAILED": EmailTemplate(  # noqa: RUF001
        subject="Ошибка фискального чека — требуется проверка",  # noqa: RUF001
        html=_ENV.from_string(
            "<h1>Ошибка фискального чека — требуется проверка</h1>"  # noqa: RUF001
            "<p>[ОПОВЕЩЕНИЕ ВЛАДЕЛЬЦА] Ошибка формирования фискального чека.</p>"  # noqa: RUF001
            "<p>payment_id: {{ payment_id }}, причина: {{ failure_reason }}.</p>"  # noqa: RUF001
            "<p>Требуется ручная проверка в ЮKassa.</p>"  # noqa: RUF001
            f"<p>{CLUB_BRAND} · noreply@mail.clubcore.ru</p>"  # noqa: RUF001
        ),
        text=_ENV_TEXT.from_string(
            "Ошибка фискального чека — требуется проверка\n\n"  # noqa: RUF001
            "[ОПОВЕЩЕНИЕ ВЛАДЕЛЬЦА] Ошибка формирования фискального чека.\n"  # noqa: RUF001
            "payment_id: {{ payment_id }}, причина: {{ failure_reason }}.\n"  # noqa: RUF001
            "Требуется ручная проверка в ЮKassa.\n\n"  # noqa: RUF001
            f"{CLUB_BRAND} · noreply@mail.clubcore.ru"  # noqa: RUF001
        ),
    ),
}
