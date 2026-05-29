---
phase: 999.2
plan: 01
subsystem: online_payments / email
tags: [email, notifications, online_payments, dispatcher, jinja, ruf001]
dependency_graph:
  requires:
    - app.modules.online_payments.email_templates (extended)
    - app.integrations.email.dispatcher (extended)
  provides:
    - TEMPLATES dict: 4 locked EmailTemplate records for online-payment events
    - dispatcher._resolve_template: 6th branch resolving ONLINE_PAYMENTS_TEMPLATES
    - test_dispatcher.py: 21 new assertions (resolve + render + end-to-end)
  affects:
    - apps/backend/app/modules/online_payments/email_templates.py
    - apps/backend/app/integrations/email/dispatcher.py
    - apps/backend/tests/unit/integrations/email/test_dispatcher.py
    - apps/backend/ruff.toml
tech_stack:
  added: []
  patterns:
    - Frozen EmailTemplate dataclass with two sandboxed Jinja environments (autoescape=True HTML, autoescape=False text)
    - Per-file RUF100 suppression for disciplinary RUF001 tripwires on locked Cyrillic copy
    - Function-scoped dispatcher import + if-branch pattern (mirrors Phase 42-45 precedent)
key_files:
  created: []
  modified:
    - apps/backend/app/modules/online_payments/email_templates.py
    - apps/backend/app/integrations/email/dispatcher.py
    - apps/backend/tests/unit/integrations/email/test_dispatcher.py
    - apps/backend/ruff.toml
decisions:
  - "RUF100 per-file-ignore added to ruff.toml for online_payments/email_templates.py and test_dispatcher.py (mirrors payments/email_templates.py and test_actor_display_format.py precedents) — disciplinary RUF001 tripwires fire on future ambiguous Cyrillic edits, RUF100 suppression prevents noise on today's unambiguous copy"
metrics:
  duration: ~15 minutes
  completed: 2026-05-29
  tasks_completed: 2/2
  files_modified: 4
---

# Phase 999.2 Plan 01: Wire online-payment email templates into dispatcher (260529-olc) Summary

**One-liner:** Closed RUN-03-F1 by authoring 4 locked Jinja EmailTemplate records for online-payment events and adding the 6th `_resolve_template` branch so the dispatcher no longer silently swallows KeyErrors on those IDs.

## What Was Built

### Task 1 — EmailTemplate records + dispatcher branch (`03d342cc`)

**`apps/backend/app/modules/online_payments/email_templates.py`**

Added the full `TEMPLATES: Final[dict[str, EmailTemplate]]` dict with 4 owner-signed-off (2026-05-29) records, mirroring `payments/email_templates.py` shape byte-for-byte:

| template_id | subject | vars |
|---|---|---|
| `EMAIL_ONLINE_PAYMENT_SUCCEEDED` | `Оплата получена` | `first_name`, `amount_rub` |
| `EMAIL_ONLINE_PAYMENT_REFUNDED` | `Возврат обработан` | `first_name`, `amount_rub` |
| `EMAIL_ONLINE_PAYMENT_CANCELED` | `Платёж отменён — требуется проверка` | `payment_id`, `yookassa_payment_id` |
| `EMAIL_FISCAL_RECEIPT_FAILED` | `Ошибка фискального чека — требуется проверка` | `payment_id`, `failure_reason` |

Structure: frozen `EmailTemplate` dataclass, `_ENV = SandboxedEnvironment(autoescape=True)`, `_ENV_TEXT = SandboxedEnvironment(autoescape=False)`, `CLUB_BRAND` footer f-string, `# noqa: RUF001` tripwire on every Cyrillic line. Existing `Final[str]` identifier constants retained (AST gate + import-linter satisfaction).

**`apps/backend/app/integrations/email/dispatcher.py`**

Added the 6th `_resolve_template` branch:
```python
from app.modules.online_payments.email_templates import (
    TEMPLATES as ONLINE_PAYMENTS_TEMPLATES,
)
...
if template_id in ONLINE_PAYMENTS_TEMPLATES:
    return ONLINE_PAYMENTS_TEMPLATES[template_id]
```
No new `.importlinter` ignore added — the edge `app.integrations.email.dispatcher -> app.modules.online_payments.email_templates` already exists at `.importlinter:189` (Phase 47 INFRA-40). `lint-imports` stays green (3 contracts kept, 0 broken).

**`apps/backend/ruff.toml`**

Added `"app/modules/online_payments/email_templates.py" = ["RUF100"]` under `[lint.per-file-ignores]` mirroring the `payments/email_templates.py` and `auth/email_templates.py` precedent.

### Task 2 — Resolve + render tests (`762947fe`)

**`apps/backend/tests/unit/integrations/email/test_dispatcher.py`**

21 new test cases appended to the existing module:
- `test_online_payment_templates_resolve_with_locked_subjects` — parametrized over all 4 IDs; asserts locked subject + `hasattr(tpl.html, "render")` + `hasattr(tpl.text, "render")`
- `test_online_payment_succeeded_renders_with_dispatcher_vars` — verifies `first_name` + `amount_rub` interpolate; `"успешно получена"` present; no leftover `{{`
- `test_online_payment_refunded_renders_with_dispatcher_vars` — verifies `first_name` + `amount_rub`; `"Возврат на сумму"` present; no leftover `{{`
- `test_online_payment_canceled_renders_with_dispatcher_vars` — verifies `payment_id` + `yookassa_payment_id`; `"[ОПОВЕЩЕНИЕ ВЛАДЕЛЬЦА]"` + `"yookassa_payment_id:"` present; no leftover `{{`
- `test_fiscal_receipt_failed_renders_with_dispatcher_vars` — verifies `payment_id` + `failure_reason`; `"Ошибка формирования фискального чека"` + `"причина:"` present; no leftover `{{`
- `test_enqueue_email_dispatch_online_payment_succeeded_end_to_end` — full `enqueue_email_dispatch` happy-path; asserts locked subject on ARQ envelope + interpolated body fragment + `audit_correlation_id` serialised correctly

**`apps/backend/ruff.toml`**

Added `"tests/unit/integrations/email/test_dispatcher.py" = ["RUF100"]` (mirrors `test_actor_display_format.py` precedent for test files with disciplinary `RUF001` tripwires).

## Verification

All gates passed:

```
ruff check app               → All checks passed!
ruff format --check app      → 210 files already formatted
mypy --strict app            → Success: no issues found in 210 source files
lint-imports                 → Contracts: 3 kept, 0 broken
pytest tests/unit/integrations/email/test_dispatcher.py tests/unit/test_locked_email_templates_ast.py -q
                             → 26 passed in 0.21s
pytest tests/unit/ -q        → 931 passed, 1 pre-existing failure (test_audit_taxonomy.py::test_locked_audit_events_has_expected_count — count drift unrelated to this task, confirmed pre-existing by stash check)
```

Smoke test output:
```
$ python -c "from app.integrations.email.dispatcher import _resolve_template; [print(_resolve_template(t).subject) for t in ('EMAIL_ONLINE_PAYMENT_SUCCEEDED','EMAIL_ONLINE_PAYMENT_REFUNDED','EMAIL_ONLINE_PAYMENT_CANCELED','EMAIL_FISCAL_RECEIPT_FAILED')]"
Оплата получена
Возврат обработан
Платёж отменён — требуется проверка
Ошибка фискального чека — требуется проверка
```

## Deviations from Plan

**1. [Rule 2 - Missing config] Added `ruff.toml` per-file-ignores for the new files**
- **Found during:** Task 1 verification (`ruff check app` exit 1 on RUF100 for unused RUF001 directives)
- **Issue:** The plan specified `# noqa: RUF001` on every Cyrillic line (project convention) but didn't mention that ruff.toml needs a corresponding `RUF100` suppression entry — the same pattern that `payments/email_templates.py`, `auth/email_templates.py`, and several other files use.
- **Fix:** Added two entries to `[lint.per-file-ignores]` in `ruff.toml`: one for `online_payments/email_templates.py` and one for `test_dispatcher.py`, with explanatory comments mirroring the existing precedents.
- **Files modified:** `apps/backend/ruff.toml`
- **Commits:** `03d342cc` (email_templates entry), `762947fe` (test_dispatcher entry)

## Known Stubs

None — all 4 templates fully render with real Jinja variable interpolation. No hardcoded empty values or placeholder text in the rendered output paths.

## Threat Flags

No new threat surface introduced. The implementation mitigates T-999.2-01 (XSS via `SandboxedEnvironment(autoescape=True)` for HTML templates). T-999.2-02 and T-999.2-03 are addressed by design (owner-alert routing unchanged in tasks.py; locked phrasing enforced by render tests).

## Self-Check: PASSED

- `apps/backend/app/modules/online_payments/email_templates.py` — FOUND, TEMPLATES dict with 4 records present
- `apps/backend/app/integrations/email/dispatcher.py` — FOUND, ONLINE_PAYMENTS_TEMPLATES branch present
- `apps/backend/tests/unit/integrations/email/test_dispatcher.py` — FOUND, 21 new test cases present
- Commit `03d342cc` — FOUND
- Commit `762947fe` — FOUND
