---
phase: 45-email-notification-mirrors
plan: 05
subsystem: bookings
requirements: [NOTIFY-10]
decisions: [D-45-15, D-45-17, D-45-19, D-27-OWNER-COPY-LOCK]
key-files:
  created:
    - apps/backend/app/modules/bookings/email_templates.py
    - apps/backend/tests/unit/test_booking_email_templates.py
  modified: []
metrics: { completed: 2026-05-20, duration: ~10min, tasks: 1, files: 2 }
---

# Phase 45 Plan 05: Bookings Email Templates Summary

4 locked Russian email templates for booking lifecycle + 24h reminder. Module structure mirrors `app/modules/auth/email_templates.py` byte-for-byte (D-45-15): dual `SandboxedEnvironment(autoescape=True/False)` + frozen `EmailTemplate` dataclass + `TEMPLATES: Final[dict[str, EmailTemplate]]`. Voice mirrors Telegram-side `BOOKING_*_DM` at `app/modules/bookings/notifications.py:31-34`. NBSP discipline (D-45-17): HTML `&nbsp;` and plain-text literal U+00A0 between trainer-name and time-of-day.

## Owner Sign-Off (D-27-OWNER-COPY-LOCK / D-45-18)

The 4 constant names below are owner-signed-off as the verbatim shipped Russian copy at this commit. Subsequent edits to either subject or body strings require a NEW sign-off entry:
- `EMAIL_BOOKING_CONFIRMED` — subject "Запись подтверждена"
- `EMAIL_BOOKING_CANCELLED_BY_CLIENT` — subject "Запись отменена (по вашей просьбе)"
- `EMAIL_BOOKING_CANCELLED_BY_OWNER` — subject "Запись отменена"
- `EMAIL_BOOKING_REMINDER_24H` — subject "Напоминание: тренировка завтра"

## Verification
- `uv run python -c "from app.modules.bookings.email_templates import TEMPLATES; assert len(TEMPLATES)==4"` → ok
- `uv run ruff check app/modules/bookings/email_templates.py` → All checks passed
- `uv run mypy --strict app/modules/bookings/email_templates.py` → Success
- `uv run pytest tests/unit/test_booking_email_templates.py` → 15 passed
- `uv run pytest tests/unit/test_locked_email_templates_ast.py` → 6 passed (existing gate untouched)
- `grep -c "EMAIL_BOOKING_" apps/backend/app/modules/bookings/email_templates.py` → 4

## Deviations
None — plan executed as written. Per-line `# noqa: RUF001` discipline was sufficient (bookings copy contains genuinely RUF001-ambiguous Cyrillic at the boundaries marked, so no `ruff.toml` allowance entry was needed, unlike Plan 45-04 memberships where the copy is unambiguous).

## Commits
- `b06eb8a` — `test(45-05): add failing test for 4 EMAIL_BOOKING locked Russian templates (NOTIFY-10)`
- `3461f92` — `feat(45-05): 4 EMAIL_BOOKING locked Russian templates (NOTIFY-10)`

## Self-Check: PASSED
- File `apps/backend/app/modules/bookings/email_templates.py`: FOUND
- File `apps/backend/tests/unit/test_booking_email_templates.py`: FOUND
- Commit `b06eb8a`: FOUND
- Commit `3461f92`: FOUND
