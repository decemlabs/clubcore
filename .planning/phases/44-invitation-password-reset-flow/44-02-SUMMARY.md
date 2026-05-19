---
phase: 44-invitation-password-reset-flow
plan: 02
status: complete
sign_off: D-44-OWNER-COPY-LOCK approved 2026-05-19
requirements:
  - RESET-03
tags:
  - email-template
  - owner-copy-lock
  - locked-russian-copy
commits:
  - 69f801e  # feat(44-02): append PASSWORD_RESET_EMAIL entry to auth TEMPLATES dict (worktree commit 346d245 cherry-picked to master)
---

# Plan 44-02 — PASSWORD_RESET_EMAIL locked Russian template

## What landed

- `apps/backend/app/modules/auth/email_templates.py` — appended `PASSWORD_RESET_EMAIL` entry to the module-level `TEMPLATES: Final[dict[str, EmailTemplate]]` registry adjacent to the Phase 42 `EMAIL_OTP_LOGIN` entry. `EmailTemplate` shape unchanged (subject + html + text). Sandboxed Jinja2 envs (`_ENV` autoescape=True, `_ENV_TEXT` autoescape=False) reused from Phase 42 D-42-05. Single `noqa: RUF001` on the Cyrillic-bearing literal block.

## D-44-OWNER-COPY-LOCK — Approved 2026-05-19

The verbatim Python source strings below are the audit anchor. Future verifiers reproduce the locked content by diffing this SUMMARY against `apps/backend/app/modules/auth/email_templates.py:TEMPLATES['PASSWORD_RESET_EMAIL']`.

### Subject (locked `Final[str]` — no interpolation)

```
Восстановление пароля Sportzal
```

### HTML source template (verbatim)

```python
"<h1>Восстановление пароля Sportzal</h1>"
"<p>Перейдите по ссылке, чтобы задать новый пароль:</p>"
'<p><a href="{{ reset_url }}">{{ reset_url }}</a></p>'
"<p>Ссылка действительна до {{ expires_at_human }}. "
"Если вы не запрашивали восстановление пароля — "
"проигнорируйте это письмо.</p>"
"<p>Sportzal · noreply@mail.sportzal.ru</p>"
```

### Text source template (verbatim)

```python
"Восстановление пароля Sportzal\n\n"
"Перейдите по ссылке, чтобы задать новый пароль:\n"
"{{ reset_url }}\n\n"
"Ссылка действительна до {{ expires_at_human }}. "
"Если вы не запрашивали восстановление пароля — "
"проигнорируйте это письмо.\n\n"
"Sportzal · noreply@mail.sportzal.ru"
```

## Verification anchors

- `TEMPLATES.keys()` exactly = `{EMAIL_OTP_LOGIN, PASSWORD_RESET_EMAIL}` — no other entries
- `{{ reset_url }}` interpolation count = **3** (HTML href, HTML visible body, text body)
- `{{ expires_at_human }}` interpolation count = **2** (HTML, text)
- `{{ full_name }}` interpolation count = **0** (D-44-25 anti-oracle invariant — no name leak, stolen-mailbox replay defence)
- `subject` is a `Final[str]` literal — no interpolation (D-44-26 / D-42-23 lineage)
- `EMAIL_OTP_LOGIN` entry byte-for-byte untouched (verified via cherry-pick diff)
- `ruff check apps/backend/app/modules/auth/email_templates.py` — clean (worktree-side check)
- `mypy --strict` — clean (worktree-side check)
- Smoke render: substituted placeholder values produce no residual `{{` tokens

## Lineage

- D-41-12 — Phase 41 pre-locked `PASSWORD_RESET_EMAIL` identifier in `LOCKED_EMAIL_TEMPLATES` (apps/backend/app/core/audit.py:271). This plan ships the content for that pre-registered identifier.
- D-42-06 — per-domain template ownership (auth templates live in `auth/email_templates.py`, NOT `integrations/email/`).
- D-42-23 — anti-oracle template content discipline (no `{full_name}`, locked Final subject).
- D-44-25 — explicit prohibition on `{{ full_name }}` in this template (mirrors `EMAIL_OTP_LOGIN`).
- D-44-26 — locked subject `"Восстановление пароля Sportzal"`.
- D-27-OWNER-COPY-LOCK (v1.3) — per-template owner sign-off enumerated by constant name; this SUMMARY is the v1.6 instance for `PASSWORD_RESET_EMAIL`.

## Downstream consumer

Phase 44 plan 44-04 (Wave 2) consumes this template via:

```python
from app.modules.auth.email_templates import TEMPLATES
envelope = render_envelope(TEMPLATES["PASSWORD_RESET_EMAIL"], reset_url=..., expires_at_human=...)
await get_email_dispatcher()(template_id="PASSWORD_RESET_EMAIL", to=email, ...)
```

The locked `template_id="PASSWORD_RESET_EMAIL"` literal at the dispatcher callsite is enforced by the AST gate at `tests/unit/test_locked_email_templates_ast.py` (extended in plan 44-09 per D-44-36).
