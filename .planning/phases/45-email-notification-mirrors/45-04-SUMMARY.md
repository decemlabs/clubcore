---
phase: 45-email-notification-mirrors
plan: 04
subsystem: memberships
requirements: [NOTIFY-08]
decisions: [D-45-15, D-45-17, D-45-19, D-45-16, D-27-OWNER-COPY-LOCK]
key-files:
  created: [apps/backend/app/modules/memberships/email_templates.py]
  modified: [apps/backend/ruff.toml]
metrics: { completed: 2026-05-20, duration: ~12min }
---

# Phase 45 Plan 04: Memberships Email Templates Summary

6 locked Russian email templates mirror the Phase 27 Telegram anti-oracle (D-45-16). Subject `Ваш абонемент скоро истекает` literal across all 6 (variant differentiation body-only). HTML `&nbsp;` + plain-text literal U+00A0 between `{{ end_date }}` and `г.` (D-45-17). Structural byte-for-byte mirror of `app/modules/auth/email_templates.py` (D-45-15).

## Owner Sign-Off (D-27-OWNER-COPY-LOCK / D-45-18)

The 6 constant names below are owner-signed-off as the verbatim shipped Russian copy at this commit. Subsequent edits require a NEW sign-off entry:
- `EMAIL_EXPIRING_7D_VARIANT_A` / `EMAIL_EXPIRING_7D_VARIANT_B`
- `EMAIL_EXPIRING_3D_VARIANT_A` / `EMAIL_EXPIRING_3D_VARIANT_B`
- `EMAIL_EXPIRING_1D_VARIANT_A` / `EMAIL_EXPIRING_1D_VARIANT_B`

## Verification
- `uv run python -c "from app.modules.memberships.email_templates import TEMPLATES; ..."` → ok
- `uv run ruff check app/modules/memberships/email_templates.py` → All checks passed
- `uv run mypy --strict app/modules/memberships/email_templates.py` → Success
- `uv run pytest tests/unit/test_locked_email_templates_ast.py` → 6 passed

## Deviations
**[Rule 3 - Blocking]** Added `"app/modules/memberships/email_templates.py" = ["RUF001", "RUF002", "RUF100"]` to `ruff.toml`. D-45-17 mandates literal U+00A0 + Russian `г.`, both RUF001-ambiguous. Per-line `# noqa: RUF001` tripwires preserved as review-intent signal. Same allowance shape as `app/core/formatters.py`.

## Commits
- `ed077a1` — `feat(45-04): 6 EMAIL_EXPIRING locked Russian templates (NOTIFY-08)`

## Self-Check: PASSED
- File `apps/backend/app/modules/memberships/email_templates.py`: FOUND
- Commit `ed077a1`: FOUND
