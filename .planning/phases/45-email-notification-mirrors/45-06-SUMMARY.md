---
phase: 45-email-notification-mirrors
plan: 06
subsystem: payments
tags: [email, templates, notify-12, locked-russian-copy]
requires: []
provides: [EMAIL_PAYMENT_RECEIPT_SALE, EMAIL_PAYMENT_RECEIPT_REFUND]
affects: [payments]
tech-stack:
  added: []
  patterns: [locked-template-registry, sandboxed-jinja2, ruf100-tripwire]
key-files:
  created:
    - apps/backend/app/modules/payments/email_templates.py
  modified:
    - apps/backend/ruff.toml
decisions:
  - D-45-15 / NOTIFY-12: payments-owned template registry (2 receipts)
  - Pure-literal subjects per D-45-19 (no Jinja for subject side)
  - Caller pre-renders NBSP-safe amount/paid_at (D-45-17)
metrics:
  duration: ~10min
  completed: 2026-05-20
---

# Phase 45 Plan 06: Payment-Receipt Email Templates Summary

2 locked Russian email templates for payment receipts (SALE + REFUND) registered in the payments module — wave 1 of NOTIFY-12.

## What shipped

- `app/modules/payments/email_templates.py` — `TEMPLATES: Final[dict[str, EmailTemplate]]` with exactly 2 keys (`EMAIL_PAYMENT_RECEIPT_SALE`, `EMAIL_PAYMENT_RECEIPT_REFUND`), both pre-registered in `LOCKED_EMAIL_TEMPLATES` (audit.py:285-286).
- Subjects are pure `Final[str]` literals: `"Чек: оплата"` / `"Чек: возврат"` (D-45-19).
- HTML + text bodies render via `SandboxedEnvironment` (mirrors `auth/email_templates.py`).
- Body voice (NOTIFY-12 verbatim): SALE → `"Принял: {{ actor_display_name }}"`; REFUND → `"Оформил: {{ actor_display_name }}"`.
- Footer: `Sportzal · noreply@mail.sportzal.ru`.
- `ruff.toml`: added per-file `RUF100` allowance for the disciplinary `# noqa: RUF001` tripwires (mirrors Phase 42 auth precedent).

## Verification

- `python -c "from app.modules.payments.email_templates import TEMPLATES; assert len(TEMPLATES)==2"` exits 0.
- `ruff check` + `mypy --strict` clean.
- HTML render smoke test passes with all 4 vars; SALE body contains `"Принял"` + `"Анна П."` + `"1 200 ₽"`; REFUND body contains `"Оформил"` + `"Сумма возврата"`.

## Deviations from Plan

**1. [Rule 3 - Blocking] ruff.toml RUF100 allowance**
- **Found during:** Task 1 verification (ruff check failed on 24 RUF100 "unused noqa" findings).
- **Issue:** Every `# noqa: RUF001` tripwire was flagged unused because the shipped Cyrillic is unambiguous.
- **Fix:** Added `"app/modules/payments/email_templates.py" = ["RUF100"]` to `[lint.per-file-ignores]` — mirrors the Phase 42 auth/email_templates.py precedent already present in the same file.
- **Files modified:** `apps/backend/ruff.toml`.
- **Commit:** 74920ca.

## Out-of-scope (Plan 45-06b)

Dispatcher walker extension (`_resolve_template`) + 3 `.importlinter` `ignore_imports` entries are deferred to Plan 45-06b (Wave 2) per PATTERNS.md correction #3.

## Self-Check: PASSED

- FOUND: apps/backend/app/modules/payments/email_templates.py
- FOUND commit: 74920ca
