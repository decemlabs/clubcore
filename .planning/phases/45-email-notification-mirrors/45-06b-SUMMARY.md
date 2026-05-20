---
phase: 45-email-notification-mirrors
plan: 06b
subsystem: integrations/email
tags: [dispatcher, walker, import-linter, NOTIFY-08, NOTIFY-10, NOTIFY-12]
requires: [45-04, 45-05, 45-06]
provides: [dispatcher-walker-extended-memberships-bookings-payments]
affects: [apps/backend/app/integrations/email/dispatcher.py, apps/backend/.importlinter]
tech-stack:
  added: []
  patterns: [function-scoped-imports, ignore_imports-allowlist]
key-files:
  created: []
  modified:
    - apps/backend/app/integrations/email/dispatcher.py
    - apps/backend/.importlinter
decisions:
  - "Override D-45-24's 'zero .importlinter changes' claim per PATTERNS.md correction #3 — grimp parses function-scope imports so each new template registry requires its own ignore_imports allowlist entry."
metrics:
  duration_minutes: 5
  completed: 2026-05-20
requirements: [NOTIFY-08, NOTIFY-10, NOTIFY-12]
---

# Phase 45 Plan 06b: Dispatcher Walker + Import-Linter Allowlist Extension Summary

Extended `_resolve_template` with memberships/bookings/payments TEMPLATES lookups (3 function-scoped imports + 3 if-blocks above the existing `raise KeyError`) and added 3 matching `ignore_imports` entries to the `integrations-not-depend-on-modules` contract.

## What Changed

- `apps/backend/app/integrations/email/dispatcher.py` — Added function-scoped imports for `MEMBERSHIPS_TEMPLATES`, `BOOKINGS_TEMPLATES`, `PAYMENTS_TEMPLATES` and 3 lookup if-blocks (in plan-prescribed order: MEMBERSHIPS → BOOKINGS → PAYMENTS) above `raise KeyError`. Updated docstring + KeyError message to name Phase 45 sources. Imports themselves were alphabetised (auth, bookings, memberships, payments, users) to satisfy ruff isort; lookup order remains semantic.
- `apps/backend/.importlinter` — Added 3 `ignore_imports` entries to the `integrations-not-depend-on-modules` contract, scoped narrowly to `dispatcher.py -> modules/{memberships,bookings,payments}.email_templates`. Comment block documents the D-45-24 override.

## Verification

- `uv run ruff check app/integrations/email/dispatcher.py` — All checks passed.
- `uv run mypy --strict app/integrations/email/dispatcher.py` — Success: no issues found.
- `uv run lint-imports` — 3 contracts kept, 0 broken (151 files, 422 dependencies analysed).
- Walker probe: `EMAIL_PAYMENT_RECEIPT_SALE`, `EMAIL_EXPIRING_7D_VARIANT_A`, `EMAIL_BOOKING_CONFIRMED`, `EMAIL_OTP_LOGIN` all resolve; `DOES_NOT_EXIST` still raises `KeyError`.

## Deviations from Plan

None — plan executed as written.

## Commits

- `bea9651` — feat(45-06b): extend dispatcher walker + import-linter for memberships/bookings/payments templates (NOTIFY-08, NOTIFY-10, NOTIFY-12)

## Self-Check: PASSED

- File `apps/backend/app/integrations/email/dispatcher.py`: FOUND, contains MEMBERSHIPS_TEMPLATES + BOOKINGS_TEMPLATES + PAYMENTS_TEMPLATES (9 references).
- File `apps/backend/.importlinter`: FOUND, contains 3 new allowlist entries.
- Commit `bea9651`: FOUND in `git log`.
