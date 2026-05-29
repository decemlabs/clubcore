---
phase: 999.2
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - apps/backend/app/modules/online_payments/email_templates.py
  - apps/backend/app/integrations/email/dispatcher.py
  - apps/backend/tests/unit/integrations/email/test_dispatcher.py
autonomous: true
requirements: [RUN-03-F1]
must_haves:
  truths:
    - "_resolve_template returns an EmailTemplate (no KeyError) for all 4 online-payment template_ids"
    - "Each of the 4 templates renders with its dispatcher-supplied vars: subject == locked literal, body contains locked phrasing, no leftover '{{'"
    - "ruff check + ruff format --check + mypy --strict + lint-imports all exit 0 (import-linter contracts unchanged — the dispatcher→online_payments edge ignore already present at .importlinter:189)"
    - "AST gate test (test_locked_email_templates_ast.py) still passes — tasks.py callsites unchanged"
    - "Full pytest green"
  artifacts:
    - path: "apps/backend/app/modules/online_payments/email_templates.py"
      provides: "TEMPLATES dict with 4 frozen EmailTemplate records (locked Russian copy)"
      contains: "TEMPLATES"
    - path: "apps/backend/app/integrations/email/dispatcher.py"
      provides: "_resolve_template branch for ONLINE_PAYMENTS_TEMPLATES"
      contains: "ONLINE_PAYMENTS_TEMPLATES"
    - path: "apps/backend/tests/unit/integrations/email/test_dispatcher.py"
      provides: "resolve+render assertions for all 4 online-payment template_ids"
  key_links:
    - from: "app.integrations.email.dispatcher._resolve_template"
      to: "app.modules.online_payments.email_templates.TEMPLATES"
      via: "function-scoped import + if template_id in ONLINE_PAYMENTS_TEMPLATES branch"
      pattern: "ONLINE_PAYMENTS_TEMPLATES\\[template_id\\]"
---

<objective>
Close email-wiring gap RUN-03-F1: the 4 Phase-52 online-payment email template identifiers are registered in `LOCKED_EMAIL_TEMPLATES` but have NO rendered copy and are NOT resolvable by the dispatcher — so `_dispatch_email(...)` → `dispatcher(template_id="EMAIL_ONLINE_PAYMENT_*")` → `_resolve_template` raises `KeyError`, swallowed by the best-effort `try/except … continue`. The email channel silently no-ops; only the Telegram DM is delivered.

Fix = (1) author the 4 locked `EmailTemplate` records mirroring `payments/email_templates.py`, (2) add the 6th `_resolve_template` branch in the dispatcher, (3) integration/unit test proving all 4 resolve + render with their dispatcher-supplied vars.

Purpose: make resolution succeed so online-payment emails actually send (NOT change error handling).
Output: TEMPLATES dict (4 records), dispatcher branch, dispatcher test cases.
</objective>

<execution_context>
@/Users/andre/Workspace/Development/clubcore/.claude/get-shit-done/workflows/execute-plan.md
@/Users/andre/Workspace/Development/clubcore/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/quick/260529-olc-wire-online-payment-emails/260529-olc-CONTEXT.md
@.planning/STATE.md
@./CLAUDE.md

# Pattern to mirror EXACTLY (EmailTemplate dataclass, two sandboxed Jinja envs, CLUB_BRAND footer, RUF001 noqa):
@apps/backend/app/modules/payments/email_templates.py

# File to extend (keep the existing Final[str] identifier constants; ADD the TEMPLATES dict):
@apps/backend/app/modules/online_payments/email_templates.py

# Dispatcher to extend (_resolve_template — 5 existing branches, add the 6th):
@apps/backend/app/integrations/email/dispatcher.py

# Test module to extend (mirror _FakeArqPool fixture + resolve/render assertions):
@apps/backend/tests/unit/integrations/email/test_dispatcher.py

<interfaces>
<!-- Contracts the executor needs — no further codebase exploration required. -->

From apps/backend/app/modules/payments/email_templates.py (the shape to mirror):
```python
from dataclasses import dataclass
from typing import Final
from jinja2 import Template
from jinja2.sandbox import SandboxedEnvironment
from app.core.branding import CLUB_BRAND

_ENV: Final[SandboxedEnvironment] = SandboxedEnvironment(autoescape=True)
_ENV_TEXT: Final[SandboxedEnvironment] = SandboxedEnvironment(autoescape=False)

@dataclass(frozen=True)
class EmailTemplate:
    subject: str       # pure Final[str] literal — NO interpolation (D-45-19)
    html: Template     # _ENV.from_string(...)
    text: Template     # _ENV_TEXT.from_string(...)

TEMPLATES: Final[dict[str, EmailTemplate]] = { "EMAIL_...": EmailTemplate(...) }
```
RUF001 noqa is required on EVERY line carrying Cyrillic text (subject literal + each Jinja string fragment + the CLUB_BRAND footer f-string).

Dispatcher var map (from online_payments/tasks.py `_dispatch_email`, verified) — Jinja var names MUST match these EXACTLY:
| template_id | kind | vars dispatcher passes |
|---|---|---|
| EMAIL_ONLINE_PAYMENT_SUCCEEDED | payment_succeeded | first_name, amount_rub |
| EMAIL_ONLINE_PAYMENT_REFUNDED  | refund_succeeded  | first_name, amount_rub |
| EMAIL_ONLINE_PAYMENT_CANCELED  | payment_canceled  | payment_id, yookassa_payment_id |
| EMAIL_FISCAL_RECEIPT_FAILED    | fiscal_failed     | payment_id, failure_reason |

Existing dispatcher `_resolve_template` branch shape (add a 6th, alongside the 5 existing):
```python
from app.modules.online_payments.email_templates import TEMPLATES as ONLINE_PAYMENTS_TEMPLATES
...
if template_id in ONLINE_PAYMENTS_TEMPLATES:
    return ONLINE_PAYMENTS_TEMPLATES[template_id]
```

Test fixtures available in test_dispatcher.py: `_FakeArqPool`, autouse `_reset_pool_slot`. `_resolve_template(template_id)` returns the EmailTemplate; `.subject`, `.html.render(**vars)`, `.text.render(**vars)` are the consumption surface.
</interfaces>
</context>

<tasks>

<task type="auto">
  <name>Task 1: Author the 4 locked EmailTemplate records + wire the dispatcher branch</name>
  <files>apps/backend/app/modules/online_payments/email_templates.py, apps/backend/app/integrations/email/dispatcher.py</files>
  <action>
In `online_payments/email_templates.py`: KEEP the existing `Final[str]` identifier constants (they satisfy the AST-gate doc + import-linter MATCHED edge). ADD — mirroring `payments/email_templates.py` byte-for-byte in shape — the imports (`dataclass`, `Final`, `jinja2.Template`, `SandboxedEnvironment`, `CLUB_BRAND`), the two module-level sandboxed envs (`_ENV` autoescape=True, `_ENV_TEXT` autoescape=False), the frozen `EmailTemplate` dataclass (subject: str / html: Template / text: Template), and a `TEMPLATES: Final[dict[str, EmailTemplate]]` with these 4 records (RUF001 noqa on every Cyrillic line). Bake the OWNER-SIGNED-OFF copy from CONTEXT.md VERBATIM. Subjects are pure literals (no interpolation, D-45-19). Bodies are Jinja using the EXACT dispatcher var names. Footer line `{CLUB_BRAND} · noreply@mail.clubcore.ru` on every template (f-string, like payments). For HTML use `<h1>`subject + `<p>` body lines mirroring payments (Claude's discretion per CONTEXT). amount_rub is pre-formatted upstream — pass through verbatim, do NOT add NBSP (D-45-17).

  Records (subject → body text; HTML mirrors with `<h1>`/`<p>`):
  - "EMAIL_ONLINE_PAYMENT_SUCCEEDED": subject "Оплата получена"; body "Здравствуйте, {{ first_name }}! Оплата на сумму {{ amount_rub }} успешно получена. Ваш абонемент / пакет тренировок активирован. Ждём вас в зале!" (vars: first_name, amount_rub)
  - "EMAIL_ONLINE_PAYMENT_REFUNDED": subject "Возврат обработан"; body "Здравствуйте, {{ first_name }}! Возврат на сумму {{ amount_rub }} успешно обработан. Средства поступят на ваш счёт в течение нескольких рабочих дней. Если у вас есть вопросы — обратитесь к администратору." (vars: first_name, amount_rub)
  - "EMAIL_ONLINE_PAYMENT_CANCELED": subject "Платёж отменён — требуется проверка"; body "[ОПОВЕЩЕНИЕ ВЛАДЕЛЬЦА] Платёж отменён. payment_id: {{ payment_id }}, yookassa_payment_id: {{ yookassa_payment_id }}. Требуется проверка." (vars: payment_id, yookassa_payment_id)
  - "EMAIL_FISCAL_RECEIPT_FAILED": subject "Ошибка фискального чека — требуется проверка"; body "[ОПОВЕЩЕНИЕ ВЛАДЕЛЬЦА] Ошибка формирования фискального чека. payment_id: {{ payment_id }}, причина: {{ failure_reason }}. Требуется ручная проверка в ЮKassa." (vars: payment_id, failure_reason)

In `dispatcher.py` `_resolve_template`: add the function-scoped import `from app.modules.online_payments.email_templates import TEMPLATES as ONLINE_PAYMENTS_TEMPLATES` alongside the existing 5, and an `if template_id in ONLINE_PAYMENTS_TEMPLATES: return ONLINE_PAYMENTS_TEMPLATES[template_id]` branch placed before the final `raise KeyError`. Optionally extend the KeyError message to mention the online_payments registry. Do NOT add a new `.importlinter` ignore — the edge ignore already exists at apps/backend/.importlinter:189 (Phase 47 INFRA-40); just keep `lint-imports` green. Do NOT touch tasks.py callsites or the swallow wrapper.
  </action>
  <verify>
    <automated>cd apps/backend && uv run ruff check app && uv run ruff format --check app && uv run mypy --strict app && uv run lint-imports && uv run python -c "from app.integrations.email.dispatcher import _resolve_template; [print(_resolve_template(t).subject) for t in ('EMAIL_ONLINE_PAYMENT_SUCCEEDED','EMAIL_ONLINE_PAYMENT_REFUNDED','EMAIL_ONLINE_PAYMENT_CANCELED','EMAIL_FISCAL_RECEIPT_FAILED')]"</automated>
  </verify>
  <done>All 4 template_ids resolve to EmailTemplate (no KeyError); ruff + ruff format --check + mypy --strict + lint-imports exit 0; existing Final[str] identifier constants retained; tasks.py + .importlinter unchanged.</done>
</task>

<task type="auto">
  <name>Task 2: Integration/unit test — all 4 resolve + render with dispatcher-supplied vars</name>
  <files>apps/backend/tests/unit/integrations/email/test_dispatcher.py</files>
  <action>
Extend the existing `test_dispatcher.py` (mirror its `_FakeArqPool` + autouse `_reset_pool_slot` fixtures; do NOT create a new module). Add test cases covering all 4 online-payment template_ids:

  1. A resolve test per template_id: `_resolve_template("EMAIL_ONLINE_PAYMENT_SUCCEEDED")` (and the other 3) returns an EmailTemplate whose `.subject` equals the locked literal and whose `.html`/`.text` have a `.render` method (no KeyError). Parametrize over (template_id, expected_subject).

  2. A render test per template_id asserting the dispatcher-supplied vars interpolate: render `.html` and `.text` with the EXACT kwargs the dispatcher passes (succeeded/refunded → first_name + amount_rub; canceled → payment_id + yookassa_payment_id; fiscal_failed → payment_id + failure_reason). Assert each rendered body contains a locked phrase substring (e.g. "успешно получена" for SUCCEEDED, "Возврат на сумму" for REFUNDED, "[ОПОВЕЩЕНИЕ ВЛАДЕЛЬЦА]" + "yookassa_payment_id:" for CANCELED, "Ошибка формирования фискального чека" + "причина:" for FISCAL), that the supplied var VALUES appear in the rendered output, and that NO leftover "{{" remains (`assert "{{" not in rendered_html and "{{" not in rendered_text`). Use RUF001 noqa on Cyrillic assertion literals as needed to keep ruff green.

  Optionally add one end-to-end `enqueue_email_dispatch` happy-path test (mirroring `test_enqueue_email_dispatch_renders_and_enqueues`) for one online-payment template_id, asserting the envelope subject == locked literal and the rendered html contains the interpolated value.
  </action>
  <verify>
    <automated>cd apps/backend && uv run pytest tests/unit/integrations/email/test_dispatcher.py tests/unit/test_locked_email_templates_ast.py -q</automated>
  </verify>
  <done>New cases prove all 4 template_ids resolve (locked subjects) and render with dispatcher vars (locked phrasing present, var values present, no leftover "{{"); AST gate test still passes.</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| dispatcher → Jinja render | template_vars (first_name, amount_rub, payment_id, yookassa_payment_id, failure_reason) originate from DB/ЮKassa, rendered into email bodies |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-999.2-01 | Tampering/Injection (XSS) | online_payments/email_templates.py `_ENV.from_string` HTML render | mitigate | HTML env uses `SandboxedEnvironment(autoescape=True)` (mirrors payments) — user-supplied vars (first_name) are HTML-escaped on render; text env is explicit passthrough plain/text. |
| T-999.2-02 | Information disclosure | EMAIL_ONLINE_PAYMENT_CANCELED / EMAIL_FISCAL_RECEIPT_FAILED bodies contain internal ids | accept | Owner-alert templates (NOT-04/NOT-05) route ONLY to owner_alert_email per tasks.py routing — never to client. Routing is out-of-scope-unchanged here; templates carry the `[ОПОВЕЩЕНИЕ ВЛАДЕЛЬЦА]` marker. |
| T-999.2-03 | Tampering | Locked owner-signed-off Russian copy altered | mitigate | Copy baked verbatim from CONTEXT.md; render tests assert locked phrasing substrings — drift fails CI. Subjects are pure `Final[str]` literals (no interpolation). |
</threat_model>

<verification>
- `cd apps/backend && uv run ruff check app && uv run ruff format --check app && uv run mypy --strict app && uv run lint-imports` all exit 0.
- `_resolve_template` returns an EmailTemplate for all 4 online-payment template_ids (no KeyError).
- Each template renders with its dispatcher-supplied vars: subject == locked literal, body contains locked phrasing, var values present, no leftover `{{`.
- AST gate `tests/unit/test_locked_email_templates_ast.py` still passes (tasks.py callsites unchanged, literal template_ids).
- Full `cd apps/backend && uv run pytest` green.
</verification>

<success_criteria>
- 4 locked `EmailTemplate` records authored verbatim from CONTEXT.md, mirroring payments/email_templates.py shape (frozen dataclass, two sandboxed envs, CLUB_BRAND footer, RUF001 noqa).
- Dispatcher `_resolve_template` resolves all 4 template_ids via the new ONLINE_PAYMENTS_TEMPLATES branch; no new `.importlinter` ignore added.
- Existing identifier `Final[str]` constants retained; tasks.py callsites + swallow wrapper untouched.
- New dispatcher tests pass; AST gate intact; full pytest green; all lint/type/import gates exit 0.
</success_criteria>

<output>
After completion, create `.planning/quick/260529-olc-wire-online-payment-emails/260529-olc-SUMMARY.md`
</output>
