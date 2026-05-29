"""Auth module locked email-template registry (Phase 42 AUTH-EM-03 / D-42-23).

Establishes the per-module template ownership precedent (D-42-06 + D-39-02):
templates live next to their owning domain module — *NOT* in
``app/integrations/email/templates/``. The ``integrations/email`` layer
transports rendered bytes, this module owns the Russian-locale copy.

Lineage:
  - D-42-06 — per-domain template ownership (this module).
  - D-39-02 — original "module renders, worker transports" boundary
    decision (PT-sessions / bookings notifications established the
    pattern; Phase 42 lifts it to email).
  - D-41-11 — ``LOCKED_EMAIL_TEMPLATES`` frozenset in
    ``app.core.audit`` is the runtime source of truth for the AST gate
    at ``tests/unit/test_locked_email_templates_ast.py``.
  - D-27-OWNER-COPY-LOCK — owner sign-off at VER-14 (Phase 46) is
    recorded by enumerating ``LOCKED_EMAIL_TEMPLATES`` members; any
    edit to the verbatim Russian copy below requires re-running that
    sign-off.

This module deliberately does NOT import ``LOCKED_EMAIL_TEMPLATES`` —
the AST gate reads the ``template_id`` literal at the dispatcher
callsite (Wave 3, plan 42-09 / D-42-27), not via runtime cross-reference
from here. Keep the dependency direction core → modules unbroken.

Rendering pipeline contract (D-42-06):
  - ``EmailTemplate.subject`` is a ``Final[str]`` — no interpolation,
    locked at module import (anti-oracle for stolen-email replay
    per D-42-23).
  - HTML template uses ``SandboxedEnvironment(autoescape=True)`` —
    ``{{ otp_code }}`` is HTML-escaped even though OTP codes are
    6-digit numerics (defence in depth, T-42-05-01).
  - Text template uses ``SandboxedEnvironment(autoescape=False)`` —
    explicit passthrough; safe because the only variable is a closed
    numeric character class.
  - ONLY ``{{ otp_code }}`` is exposed to the template — NO
    ``{full_name}``, NO email, NO user id (anti-oracle, D-42-23 /
    T-42-05-02).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from jinja2 import Template
from jinja2.sandbox import SandboxedEnvironment

from app.core.branding import CLUB_BRAND

# Two sandboxed Jinja environments: HTML side autoescapes ``{{ otp_code }}``
# (defence in depth, T-42-05-01); text/plain side is explicit passthrough.
_ENV: Final[SandboxedEnvironment] = SandboxedEnvironment(autoescape=True)
_ENV_TEXT: Final[SandboxedEnvironment] = SandboxedEnvironment(autoescape=False)


@dataclass(frozen=True)
class EmailTemplate:
    """Locked email template record (D-42-06).

    - ``subject`` is a fully baked literal — no interpolation. Locking
      the subject prevents stolen-email oracle attacks (T-42-05-02).
    - ``html`` / ``text`` are pre-compiled ``jinja2.Template`` objects
      bound to sandboxed environments at module import.
    """

    subject: str
    html: Template
    text: Template


# D-42-23 locked Russian copy. RUF001 noqa is required on Cyrillic-bearing
# lines (project-wide convention; mirrors ``integrations/telegram/sender.py``
# line 19 precedent for the locked OTP DM body).
TEMPLATES: Final[dict[str, EmailTemplate]] = {
    "EMAIL_OTP_LOGIN": EmailTemplate(  # noqa: RUF001
        subject=f"Код входа в {CLUB_BRAND}",
        html=_ENV.from_string(
            f"<h1>Код входа в {CLUB_BRAND}</h1>"
            "<p>Ваш код для входа: <strong>{{ otp_code }}</strong></p>"
            "<p>Срок действия: 10 минут. Если вы не запрашивали код — "
            "проигнорируйте это письмо.</p>"
            f"<p>{CLUB_BRAND} · noreply@mail.clubcore.ru</p>"
        ),
        text=_ENV_TEXT.from_string(
            f"Код входа в {CLUB_BRAND}\n\n"
            "Ваш код для входа: {{ otp_code }}\n\n"
            "Срок действия: 10 минут. Если вы не запрашивали код — "
            "проигнорируйте это письмо.\n\n"
            f"{CLUB_BRAND} · noreply@mail.clubcore.ru"
        ),
    ),
    "PASSWORD_RESET_EMAIL": EmailTemplate(  # noqa: RUF001
        subject=f"Восстановление пароля {CLUB_BRAND}",
        html=_ENV.from_string(
            f"<h1>Восстановление пароля {CLUB_BRAND}</h1>"
            "<p>Перейдите по ссылке, чтобы задать новый пароль:</p>"
            '<p><a href="{{ reset_url }}">{{ reset_url }}</a></p>'
            "<p>Ссылка действительна до {{ expires_at_human }}. "
            "Если вы не запрашивали восстановление пароля — "
            "проигнорируйте это письмо.</p>"
            f"<p>{CLUB_BRAND} · noreply@mail.clubcore.ru</p>"
        ),
        text=_ENV_TEXT.from_string(
            f"Восстановление пароля {CLUB_BRAND}\n\n"
            "Перейдите по ссылке, чтобы задать новый пароль:\n"
            "{{ reset_url }}\n\n"
            "Ссылка действительна до {{ expires_at_human }}. "
            "Если вы не запрашивали восстановление пароля — "
            "проигнорируйте это письмо.\n\n"
            f"{CLUB_BRAND} · noreply@mail.clubcore.ru"
        ),
    ),
}
