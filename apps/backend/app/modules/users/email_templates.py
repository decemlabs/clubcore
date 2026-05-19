"""Phase 43 users module email templates (USERS-03 / D-43-22/23/24).

Locked Russian templates for owner-managed operator onboarding.

D-43-OWNER-COPY-LOCK — owner sign-off enumerated by constant name in the
plan SUMMARY (D-27-OWNER-COPY-LOCK lineage). Constants below MUST NOT be
mutated outside an explicit owner-sign-off plan.

Template render contract (D-43-24):
  - Render at enqueue time (not at transport time) in service.create_user.
  - The rendered EmailEnvelope (subject + html + text) is passed via kwargs
    to get_email_dispatcher()(template_id='USER_INVITATION_EMAIL', ...).
  - The ARQ dispatch_email task never imports this module — import-linter
    contract 3 (integrations ⊥ modules) holds.

Template variables (Jinja2 SandboxedEnvironment, autoescape=True for HTML):
  - full_name: invitee full name (operator-typed at POST /users)
  - role_ru: Russian role string ('администратор' | 'администратор стойки'),
    sourced from the ROLE_RU lookup table below.
  - invitation_url: full URL https://<frontend_base>/auth/accept-invite#token=<raw>
  - expires_at_human: Russian long-form datetime (e.g. '26 мая 2026 в 12:00')
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from jinja2 import Template
from jinja2.sandbox import SandboxedEnvironment

from app.core.permissions import Role

_ENV: Final[SandboxedEnvironment] = SandboxedEnvironment(autoescape=True)
_ENV_TEXT: Final[SandboxedEnvironment] = SandboxedEnvironment(autoescape=False)


@dataclass(frozen=True)
class EmailTemplate:
    """Locked email template — subject is a Final[str] literal; html+text are Jinja Templates."""

    subject: str
    html: Template
    text: Template


# D-43-OWNER-COPY-LOCK — owner sign-off REQUIRED before mutation.
_SUBJECT_USER_INVITATION: Final[str] = "Приглашение в Sportzal"

_HTML_USER_INVITATION: Final[Template] = _ENV.from_string(
    "<p>Здравствуйте, {{ full_name }}!</p>"
    "<p>Вас пригласили в&nbsp;Sportzal в&nbsp;роли «{{ role_ru }}».</p>"  # noqa: RUF001
    "<p>Чтобы установить пароль и&nbsp;войти, перейдите по&nbsp;ссылке:</p>"
    '<p><a href="{{ invitation_url }}">{{ invitation_url }}</a></p>'
    "<p>Ссылка действительна до&nbsp;{{ expires_at_human }}.</p>"
    "<p>Если вы&nbsp;не&nbsp;ожидали это приглашение — просто проигнорируйте письмо.</p>"
)

_TEXT_USER_INVITATION: Final[Template] = _ENV_TEXT.from_string(
    "Здравствуйте, {{ full_name }}!\n\n"
    "Вас пригласили в Sportzal в роли «{{ role_ru }}».\n\n"  # noqa: RUF001
    "Чтобы установить пароль и войти, перейдите по ссылке:\n"
    "{{ invitation_url }}\n\n"
    "Ссылка действительна до {{ expires_at_human }}.\n\n"
    "Если вы не ожидали это приглашение — просто проигнорируйте письмо.\n"
)

# Public registry — keys MUST be members of app.core.audit.LOCKED_EMAIL_TEMPLATES.
TEMPLATES: Final[dict[str, EmailTemplate]] = {
    "USER_INVITATION_EMAIL": EmailTemplate(
        subject=_SUBJECT_USER_INVITATION,
        html=_HTML_USER_INVITATION,
        text=_TEXT_USER_INVITATION,
    ),
}


ROLE_RU: Final[dict[Role, str]] = {
    Role.OWNER: "администратор",
    Role.RECEPTION: "администратор стойки",
}
"""Russian role label per D-43-23 — owner-copy-locked."""
