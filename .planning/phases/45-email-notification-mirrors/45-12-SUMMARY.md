---
phase: 45-email-notification-mirrors
plan: 12
subsystem: backend/tests
tags: [tests, ast-gate, locked-templates, phase-closure, D-45-27]
requires: [04, 05, 06, 07, 08, 09, 10]
provides: [phase45-ast-gate-closure]
affects: [LOCKED_EMAIL_TEMPLATES enforcement at Phase 45 surface]
tech_stack_added: []
patterns: [ast-walker, parametrized-tests, per-module-count-pin]
key_files_created:
  - apps/backend/tests/unit/test_locked_email_templates_phase45.py
key_files_modified: []
decisions: [D-45-27 closed]
metrics:
  duration_min: 4
  tasks_completed: 1
  files_changed: 1
  tests_added: 9
completed: 2026-05-20
---

# Phase 45 Plan 12: Locked Email Templates AST Gate Closure Summary

One-liner: Closes D-45-27 with a 9-case parametrized AST gate that enumerates all 12 Phase 45 template IDs against LOCKED_EMAIL_TEMPLATES and asserts ast.Constant(str) literal discipline across all 14 callsites in 4 source files.

## What Shipped

- `tests/unit/test_locked_email_templates_phase45.py` — 3 test groups (9 parametrized cases): enumeration (1) + AST walker over 4 source files (4) + per-module callsite counts (4).
- Walker is broader than Phase 41 (catches both `get_email_dispatcher()(...)` double-Call and pre-bound `dispatcher(...)` shapes) by keying off the `template_id` kwarg name.
- Per-module counts pinned: memberships/notifications.py=6 (EMAIL_EXPIRING_*), bookings/notifications.py=4 (EMAIL_BOOKING_*), memberships/service.py=2 + pt_packages/service.py=2 (EMAIL_PAYMENT_RECEIPT_*) = 14 callsites.

## Verification

- `cd apps/backend && uv run pytest tests/unit/ -k "locked_email_templates" -v` → 16 passed (6 Phase 41 + 9 Phase 45 + 1 booking-templates membership).
- `uv run ruff check` + `uv run mypy --strict` on new test file → clean.

## Deviations from Plan

None - plan executed exactly as written.

## Self-Check: PASSED
- FOUND: apps/backend/tests/unit/test_locked_email_templates_phase45.py
- FOUND: commit 79f5438
